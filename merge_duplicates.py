#!/usr/bin/env python3
"""
LLM Wiki 重复股票实体合并脚本
功能：扫描entities目录，按股票代码合并重复实体，合并tags/related/sources和正文内容
"""

import os
import re
import shutil
from collections import defaultdict
from datetime import datetime

ENTITIES_DIR = "/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/chzl/wiki/entities"
BACKUP_DIR = os.path.join(ENTITIES_DIR, "_backup_duplicates")

# 股票代码正则：6位数字，排除2026开头的日期
STOCK_PATTERN = re.compile(r'(?<!\d)(\d{6})(?!\d)')

def parse_frontmatter(content):
    """解析markdown的frontmatter"""
    if not content.startswith('---'):
        return {}, content
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content
    fm_text = parts[1]
    body = parts[2]
    fm = {}
    current_key = None
    for line in fm_text.split('\n'):
        line = line.rstrip()
        if not line or line.startswith('#'):
            continue
        # 列表格式: key: [a, b, c]
        m = re.match(r'^(\w+):\s*\[(.*)\]\s*$', line)
        if m:
            key = m.group(1)
            val = m.group(2)
            if val.strip():
                # 处理带引号和不带引号的元素
                items = []
                for item in val.split(','):
                    item = item.strip().strip('"').strip("'")
                    if item:
                        items.append(item)
                fm[key] = items
            else:
                fm[key] = []
            current_key = key
            continue
        # 简单key: value
        m = re.match(r'^(\w+):\s*(.*)$', line)
        if m:
            key = m.group(1)
            val = m.group(2).strip().strip('"').strip("'")
            fm[key] = val
            current_key = key
            continue
    return fm, body

def dump_frontmatter(fm):
    """生成frontmatter文本"""
    lines = ['---']
    list_keys = {'tags', 'related', 'sources'}
    for key in ['type', 'title', 'tags', 'related', 'sources', 'aliases', 'created', 'updated']:
        if key not in fm:
            continue
        val = fm[key]
        if key in list_keys and isinstance(val, list):
            # 格式化列表，带引号
            quoted = ', '.join(f'"{v}"' for v in val)
            lines.append(f'{key}: [{quoted}]')
        else:
            lines.append(f'{key}: {val}')
    # 其他key
    for key, val in fm.items():
        if key in {'type', 'title', 'tags', 'related', 'sources', 'aliases', 'created', 'updated'}:
            continue
        if isinstance(val, list):
            quoted = ', '.join(f'"{v}"' for v in val)
            lines.append(f'{key}: [{quoted}]')
        else:
            lines.append(f'{key}: {val}')
    lines.append('---')
    return '\n'.join(lines)

def get_exchange(code):
    """根据股票代码判断交易所"""
    if code.startswith(('6', '9')):
        return 'SH'
    elif code.startswith(('0', '2', '3')):
        return 'SZ'
    elif code.startswith(('4', '8')):
        return 'BJ'
    return 'SH'

def extract_stock_name(filename, code):
    """从文件名提取股票名称"""
    name = filename.replace('.md', '')
    # 先处理括号格式：名称（代码.交易所）或 名称(代码)
    name = re.sub(r'[（(]\s*' + code + r'\s*(\.|-)?\s*(SH|SZ|BJ)?\s*[）)]', '', name, flags=re.IGNORECASE)
    # 处理连字符格式：名称-代码-交易所 或 名称-代码.交易所 或 名称代码
    name = re.sub(r'[-—]*\s*' + code + r'\s*(\.|-)?\s*(SH|SZ|BJ)?\s*$', '', name, flags=re.IGNORECASE)
    # 处理名称在前代码在后：代码名称
    name = re.sub(r'^\s*' + code + r'\s*(\.|-)?\s*(SH|SZ|BJ)?\s*[-—]*', '', name, flags=re.IGNORECASE)
    # 清理残留的连字符和空格
    name = name.strip('-— 　')
    return name if name else filename

def extract_code_from_file(filepath):
    """从文件内容中提取股票代码，优先从frontmatter title提取"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(3000)
    except:
        return None
    
    # 1. 优先从frontmatter的title提取：title: "名称（600000.SH）" 或 title: 名称 (600000.SH)
    title_match = re.search(r"^title:\s*.*?(\d{6})\s*(\.|-)?\s*(SH|SZ|BJ)?", content, re.MULTILINE | re.IGNORECASE)
    if title_match:
        code = title_match.group(1)
        if code.startswith(('0', '3', '6', '8', '4', '9')) and not code.startswith('2026'):
            return code
    
    # 2. 从正文第一行的标题提取：# 名称（600000.SH）
    lines = content.split('\n')
    for line in lines[:10]:
        if line.startswith('#'):
            m = re.search(r'(\d{6})\s*(\.|-)?\s*(SH|SZ|BJ)?', line, re.IGNORECASE)
            if m:
                code = m.group(1)
                if code.startswith(('0', '3', '6', '8', '4', '9')) and not code.startswith('2026'):
                    return code
            break
    
    return None

def find_duplicates():
    """找出所有重复的股票实体"""
    files = [f for f in os.listdir(ENTITIES_DIR) if f.endswith('.md')]
    groups = defaultdict(list)
    
    for f in files:
        # 跳过备份目录和非实体文件
        if f.startswith('_'):
            continue
        
        code = None
        # 1. 先从文件名提取
        matches = STOCK_PATTERN.findall(f)
        if matches:
            code = matches[0]
            # 排除日期（2026开头的6位数）和不合理的代码
            if code.startswith('2026') or not code.startswith(('0', '3', '6', '8', '4', '9')):
                code = None
        
        # 2. 文件名没有就从内容提取
        if not code:
            code = extract_code_from_file(os.path.join(ENTITIES_DIR, f))
        
        if code:
            groups[code].append(f)
    
    return {k: v for k, v in groups.items() if len(v) > 1}

def names_consistent(names):
    """检查一组名称是否一致（允许ST/退市等前缀差异）"""
    if len(names) <= 1:
        return True
    # 清理名称：移除ST/*ST/退等前缀，移除A/B后缀
    def clean(n):
        n = re.sub(r'^[\*]*ST', '', n)
        n = re.sub(r'退$', '', n)
        n = re.sub(r'[AB]$', '', n)
        return n.strip()
    cleaned = set(clean(n) for n in names)
    # 如果清理后只有一个名称，说明一致
    if len(cleaned) == 1:
        return True
    # 如果有名称包含关系，也算一致（如"中船应急"和"ST应急"）
    names_list = list(cleaned)
    for i in range(len(names_list)):
        for j in range(len(names_list)):
            if i != j and names_list[i] and names_list[j]:
                if names_list[i] in names_list[j] or names_list[j] in names_list[i]:
                    return True
    return False

def merge_group(code, filenames):
    """合并一组重复的股票实体"""
    # 读取所有文件
    docs = []
    names = set()
    for fn in filenames:
        path = os.path.join(ENTITIES_DIR, fn)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        fm, body = parse_frontmatter(content)
        name = extract_stock_name(fn, code)
        names.add(name)
        docs.append({
            'filename': fn,
            'path': path,
            'fm': fm,
            'body': body.strip(),
            'body_len': len(body.strip()),
            'sources_count': len(fm.get('sources', [])),
            'name': name,
        })
    
    # 检查名称一致性
    name_ok = names_consistent(list(names))
    if not name_ok:
        return {
            'code': code,
            'skipped': True,
            'skip_reason': f'名称不一致: {"/".join(sorted(names))}',
            'filenames': filenames,
        }
    
    # 选择主文件：正文最长的优先，其次sources最多的
    docs.sort(key=lambda x: (x['body_len'], x['sources_count']), reverse=True)
    main = docs[0]
    others = docs[1:]
    
    # 提取股票名称
    name = main['name']
    exchange = get_exchange(code)
    standard_filename = f'{name}-{code}.{exchange}.md'
    
    # 合并frontmatter
    merged_fm = dict(main['fm'])
    merged_fm['title'] = f'{name}（{code}.{exchange}）'
    
    # 合并tags
    all_tags = list(main['fm'].get('tags', []))
    for d in others:
        for t in d['fm'].get('tags', []):
            if t not in all_tags:
                all_tags.append(t)
    merged_fm['tags'] = all_tags
    
    # 合并related
    all_related = list(main['fm'].get('related', []))
    for d in others:
        for r in d['fm'].get('related', []):
            if r not in all_related:
                all_related.append(r)
    merged_fm['related'] = all_related
    
    # 合并sources
    all_sources = list(main['fm'].get('sources', []))
    for d in others:
        for s in d['fm'].get('sources', []):
            if s not in all_sources:
                all_sources.append(s)
    merged_fm['sources'] = all_sources
    
    # 添加aliases（其他文件名中的标题变体）
    aliases = []
    for d in others:
        title = d['fm'].get('title', '')
        if title and title != merged_fm['title'] and title not in aliases:
            aliases.append(title)
    if aliases:
        merged_fm['aliases'] = aliases
    
    merged_fm['updated'] = datetime.now().strftime('%Y-%m-%d')
    
    # 合并正文
    merged_body = main['body']
    for d in others:
        if d['body'] and d['body'] not in merged_body:
            source_note = d['fm'].get('sources', ['未知来源'])
            source_str = ', '.join(source_note) if isinstance(source_note, list) else str(source_note)
            merged_body += f'\n\n---\n\n### 补充信息（来源：{source_str}）\n\n{d["body"]}'
    
    merged_content = dump_frontmatter(merged_fm) + '\n\n' + merged_body + '\n'
    
    return {
        'code': code,
        'name': name,
        'exchange': exchange,
        'standard_filename': standard_filename,
        'main_filename': main['filename'],
        'other_filenames': [d['filename'] for d in others],
        'merged_content': merged_content,
        'merged_fm': merged_fm,
    }

def execute_merge(result, dry_run=True):
    """执行合并"""
    code = result['code']
    print(f'\n=== {result["name"]} ({code}.{result["exchange"]}) ===')
    print(f'  主文件: {result["main_filename"]}')
    print(f'  标准名: {result["standard_filename"]}')
    print(f'  合并: {len(result["other_filenames"])}个重复文件')
    for f in result['other_filenames']:
        print(f'    - {f}')
    
    if dry_run:
        print('  [DRY RUN] 不执行实际操作')
        return
    
    # 创建备份目录
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # 写入主文件（如果标准名不同，先写标准名，再处理旧主文件）
    main_path = os.path.join(ENTITIES_DIR, result['main_filename'])
    standard_path = os.path.join(ENTITIES_DIR, result['standard_filename'])
    
    if result['main_filename'] != result['standard_filename']:
        # 主文件需要重命名：先备份旧主文件，再写新文件
        backup_path = os.path.join(BACKUP_DIR, result['main_filename'])
        shutil.move(main_path, backup_path)
        print(f'  备份主文件: {result["main_filename"]} -> _backup_duplicates/')
    
    # 写入合并后的内容到标准文件名
    with open(standard_path, 'w', encoding='utf-8') as f:
        f.write(result['merged_content'])
    print(f'  写入: {result["standard_filename"]}')
    
    # 备份其他重复文件（跳过标准文件名，因为刚写入了合并内容）
    for fn in result['other_filenames']:
        if fn == result['standard_filename']:
            print(f'  跳过: {fn} (标准文件名，已写入合并内容)')
            continue
        src = os.path.join(ENTITIES_DIR, fn)
        dst = os.path.join(BACKUP_DIR, fn)
        if os.path.exists(src):
            shutil.move(src, dst)
            print(f'  备份: {fn} -> _backup_duplicates/')

def main():
    print('LLM Wiki 重复股票实体合并工具')
    print('=' * 50)
    
    dups = find_duplicates()
    print(f'\n发现 {len(dups)} 只股票有重复实体')
    
    results = []
    skipped = []
    for code, filenames in sorted(dups.items()):
        result = merge_group(code, filenames)
        if result.get('skipped'):
            skipped.append(result)
        else:
            results.append(result)
    
    print('\n' + '=' * 50)
    print(f'可自动合并: {len(results)} 只股票')
    print(f'需人工确认(名称不一致): {len(skipped)} 只股票')
    if skipped:
        print('\n--- 需人工确认 ---')
        for s in skipped:
            print(f'  {s["code"]}: {s["skip_reason"]}')
            for f in s['filenames']:
                print(f'    - {f}')
    
    print('\n--- 自动合并计划 ---')
    total_removed = 0
    for r in results:
        print(f'  {r["name"]} ({r["code"]}): {len(r["other_filenames"])+1}个文件 -> 1个')
        total_removed += len(r['other_filenames'])
    print(f'\n共将减少 {total_removed} 个重复文件')
    
    # 先dry run
    print('\n--- DRY RUN ---')
    for r in results:
        execute_merge(r, dry_run=True)
    
    print('\n' + '=' * 50)
    print('DRY RUN 完成。确认无误后，将执行实际合并。')
    
    # 实际执行
    print('\n--- 执行实际合并 ---')
    for r in results:
        execute_merge(r, dry_run=False)
    
    print(f'\n✅ 合并完成！共处理 {len(results)} 只股票，减少 {total_removed} 个重复文件')
    print(f'   备份文件保存在: {BACKUP_DIR}')

if __name__ == '__main__':
    main()
