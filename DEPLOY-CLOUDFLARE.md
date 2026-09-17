# 沧海巨浪笔记站（免费）

源码在 GitHub，网站用 **Cloudflare Pages** 发布。电脑关机不影响访问。不用给任何人 Cloudflare Token。

## Cloudflare 你只需要点这些

1. 打开 [Cloudflare Dashboard](https://dash.cloudflare.com/)（免费邮箱注册即可）
2. **Workers & Pages** → **Create** → **Pages** → **Connect to Git**
3. 授权 GitHub，选仓库 `chzl-kg`
4. 构建设置：

| 项 | 值 |
|---|---|
| Framework preset | None |
| Build command | `npx quartz build` |
| Build output directory | `public` |
| Environment variable | `NODE_VERSION` = `22` |

5. Save and Deploy。一两分钟后会得到 `https://xxxx.pages.dev`

可选：Settings → General 把项目名改成 `chzl-kg`，这样地址更接近 `chzl-kg.pages.dev`。然后把本仓库 `quartz.config.yaml` 里的 `baseUrl` 改成实际域名再 push 一次。

## 以后更新笔记

在本机 Obsidian 改 `沧海巨浪/chzl_kg` 之后：

```bash
/Users/chenyang/Downloads/demo/沧海巨浪/scripts/sync_chzl_kg_to_quartz.sh
cd /Users/chenyang/Downloads/demo/chzl-kg-web
git add content
git commit -m "sync notes"
git push
```

Cloudflare 会自动重建网站。
