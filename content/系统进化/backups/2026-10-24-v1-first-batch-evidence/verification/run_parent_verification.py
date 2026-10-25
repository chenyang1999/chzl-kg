"""F1: freeze CURRENT reviewed files, run only fixed offline cohorts.
Run: <project>/.venv/bin/python -B <this file>
Never invokes a production entrypoint. Child processes may not spawn children.
Creates a fresh parent-<UTC>-<nonce> directory; does not reuse old test results.
"""
from pathlib import Path
import ast, hashlib, json, os, shutil, subprocess, sys, uuid
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
BASE = Path(__file__).resolve().parent
REPO = Path('/Users/chenyang/Downloads/demo/沧海巨浪')
SOURCES = '''trading/execution_authorization.py trading/order/qmt_context.py trading/load_plan.py
trading/watcher/run_once.py trading/watcher/dispatch.py trading/watcher/session_context.py
trading/schema/watchlist_plan.py trading/schema/normalize.py trading/positions_state.py trading/account_config.py
trading/after_close.py trading/entry_selector.py trading/executors/registry.py trading/executors/base.py
trading/executors/_buy_common.py trading/executors/_sell_common.py src/plan/buy_eligibility.py
src/execute/amygdala.py src/execute/watcher_daemon.py src/trading_agent/models.py src/trading_agent/journal.py
scripts/research/pipeline_artifacts.py scripts/execute/run_paper_plan_once.py scripts/execute/run_paper_trading.py
trading/paper/ledger.py trading/paper/safety.py trading/paper/__init__.py
src/plan/price_levels.py src/plan/risk_reward.py scripts/plan/apply_price_levels.py'''.split()
KINDS = '''daban_confirm exit_at_open exit_if_no_new_high intraday_break_exit leader_breakout
low_absorption_intraday sector_switch_exit stop_loss_break t_add_pullback t_reduce_resistance take_profit_hit
trend_pullback_buy volume_price_divergence'''.split()
SOURCES += ['trading/executors/execute_'+k+'.py' for k in KINDS]
TESTS = '''tests/test_v1_s1_execution_boundaries_20261024.py tests/test_v1_integration_authorization_20261024.py
 tests/test_v1_s2_paper_exit_safety_20261024.py tests/test_v1_s3_trigger_quote_safety_20261024.py
 tests/test_v1_independent_contract_review_20261024.py tests/test_canghai_paper_execution_20261023.py
 tests/test_canghai_paper_parent_review_20261023.py tests/test_canghai_paper_plan_driver_20261023.py
 tests/pipeline/test_plan_staging_freshness.py tests/test_canghai_rr_scope_20261023.py
 tests/test_canghai_rr_parent_review_20261023.py tests/test_v1_final_joint_acceptance_20261024.py
 tests/test_v1_regression_contract_closeout_20261024.py tests/test_v1_scan_date_binding_20261024.py'''.split()
# Safe initializers are copied exactly; side-effectful execute/order/executors
# initializers are intentionally NOT imported. Existing fixtures create package shims.
SOURCES += ['src/__init__.py','src/plan/__init__.py','trading/__init__.py','scripts/__init__.py']
EXPECTED = dict(s1=93,i1=71,paper=156,s2diagnostic=2,s2new=34,r1=12,staging=57,s3=129,
                s3diagnostic=5,rrparent=32,rrscope=109,f1=11,closeout=32,c1=47)  # new groups fixed from native --collect-only receipts
COHORTS = ['s1','i1','paper','s2diagnostic','s2new','r1','staging','s3','s3diagnostic','rrparent','rrscope','f1','closeout','c1']
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    import argparse
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--label',default='parent')
    ap.add_argument('--groups',nargs='+',choices=COHORTS,default=COHORTS)
    ap.add_argument('--rr-adapt',action=argparse.BooleanOptionalAction,default=False,help='deprecated; RR fixture now self-contained; enabling adaptation is forbidden')
    ap.add_argument('--collect-only',action='store_true',help='native audited collection; no tests executed')
    args=ap.parse_args()
    if args.rr_adapt:ap.error('RR harness adaptation removed; use the explicit source fixture')
    identity_contract=json.loads((BASE/'case-identity-contract.json').read_text())
    assert args.label.replace('-','').replace('_','').isalnum()
    root=BASE/(args.label+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    root.mkdir()
    frozen=root/'frozen'; frozen.mkdir()
    manifest={}
    for rel in sorted(set(SOURCES+TESTS)):
        src=REPO/rel
        assert src.is_file() and not src.is_symlink(), rel
        blob=src.read_bytes();ast.parse(blob)
        dest=frozen/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(blob)
        manifest[rel]={'sha256':hashlib.sha256(blob).hexdigest(),'bytes':len(blob),'origin':'current_worktree'}
    # Historical TESTS and genuine legacy writer are explicitly separate evidence,
    # never substituted for CURRENT implementation under test.
    for p in (BASE/'support').rglob('*.py'):
        rel=p.relative_to(BASE/'support'); dest=root/'support'/rel
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    shutil.copyfile(BASE/'audit_worker.py',root/'audit_worker.py')
    shutil.copyfile(BASE/'case-identity-contract.json',root/'case-identity-contract.json')
    (root/'source-manifest.json').write_text(json.dumps(manifest,indent=2))
    (root/'harness-manifest.json').write_text(json.dumps({
        str(p.relative_to(root)):digest(p) for p in [root/'audit_worker.py',root/'case-identity-contract.json',*sorted((root/'support').rglob('*.py'))]},indent=2))
    shutil.copyfile(Path(__file__).resolve(),root/'run_parent_verification.py')
    allrows=[]; runs=[]
    for group in args.groups:
        g=root/group; app=g/'app';fixtures=g/'fixtures';fixtures.mkdir(parents=True)
        shutil.copytree(frozen,app)
        # Explicit shim for side-effectful package initializers. Does not replace
        # any policy function. Manifest records synthetic package files below.
        for d in ['scripts/execute','scripts/research','scripts/plan','src/execute','src/trading_agent',
                  'trading/schema','trading/order','trading/executors','trading/watcher']:
            p=app/d/'__init__.py';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('')
        for name in ['test_audit_d_diagnostics.py','test_s3_ast_diagnostics.py']:
            shutil.copyfile(root/'support'/name,app/'tests'/name)
        # R1 old_writer fixture resolves this exact relative location.
        old=root/'pre/app/trading/paper/ledger.py';old.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/'support/legacy_s2_before_ledger.py',old)
        cmd=[sys.executable,'-B',str(root/'audit_worker.py'),group]
        if args.collect_only:cmd+=['--collect-only']
        env={k:v for k,v in os.environ.items() if k in ['PATH','HOME','LANG','LC_ALL','SYSTEMROOT','DYLD_LIBRARY_PATH']}
        env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(fixtures),TMP=str(fixtures),TEMP=str(fixtures))
        with (g/'pytest.log').open('w') as log:
            cp=subprocess.run(cmd,cwd=app,env=env,stdout=log,stderr=subprocess.STDOUT)
        meta=json.loads((g/'run.json').read_text()) if (g/'run.json').exists() else {'error':'missing run metadata'}
        rows=[]
        if (g/'junit.xml').exists():
            for case in ET.parse(g/'junit.xml').iter('testcase'):
                status=next((s for s in ['failure','error','skipped'] if case.find(s) is not None),'passed')
                identity=case.get('classname','')+'::'+case.get('name','')
                row=dict(identity=identity,group=group,status=status,evidence=str(g/'junit.xml'))
                if status!='passed':row['detail']=''.join(case.find(status).itertext())
                rows.append(row)
        allrows+=rows
        counts={k:sum(r['status']==k for r in rows) for k in ['passed','failure','error','skipped']}
        runs.append(dict(group=group,command=cmd,returncode=cp.returncode,counts=counts,
                         cases=meta.get('collected_count',0) if args.collect_only else len(rows),metadata=meta))
        print(json.dumps({'group':group,'exit':cp.returncode,**counts}),flush=True)
    identities={}
    for r in allrows:identities.setdefault(r['identity'],[]).append(r)
    unique=[dict(identity=k,observations=v) for k,v in identities.items()]
    drift=[r for r,m in manifest.items() if digest(REPO/r)!=m['sha256'] or digest(frozen/r)!=m['sha256']]
    copies=[]
    for group in args.groups:
        for rel,m in manifest.items():
            if digest(root/group/'app'/rel)!=m['sha256']:copies.append(group+':'+rel)
    coverage_errors=[dict(group=r['group'],expected=EXPECTED[r['group']],actual=r['cases'])
                     for r in runs if r['cases']!=EXPECTED[r['group']]]
    coverage_errors += [dict(group=r['group'],issue='collection_execution_count_mismatch',
                             collected=r['metadata'].get('collected_count'),executed=r['cases'])
                        for r in runs if not args.collect_only and r['metadata'].get('collected_count')!=r['cases']]
    for r in runs:
        group=r['group'];expected=identity_contract['groups'][group]
        collected=json.loads((root/group/'collected-nodeids.json').read_text())
        if sorted(collected)!=expected['collected']:
            coverage_errors.append(dict(group=group,issue='collection_identity_mismatch',
                missing=sorted(set(expected['collected'])-set(collected)),
                unexpected=sorted(set(collected)-set(expected['collected']))))
        if not args.collect_only:
            actual=sorted(row['identity'] for row in allrows if row['group']==group)
            if actual!=expected['junit']:
                coverage_errors.append(dict(group=group,issue='execution_identity_mismatch',
                    missing=sorted(set(expected['junit'])-set(actual)),
                    unexpected=sorted(set(actual)-set(expected['junit']))))
            if r['counts']['skipped']:
                coverage_errors.append(dict(group=group,issue='skipped_case_forbidden',count=r['counts']['skipped']))
    if len(allrows)!=len(unique):
        coverage_errors.append(dict(issue='duplicate_case_across_cohorts',observations=len(allrows),unique=len(unique)))
    if 'paper' in args.groups and not args.collect_only:
        paper=next(r for r in runs if r['group']=='paper')
        if paper['metadata'].get('subtest_count')!=65:
            coverage_errors.append(dict(group='paper_subtests',expected=65,actual=paper['metadata'].get('subtest_count')))
    result=dict(root=str(root),runs=runs,unique_cases=len(unique),case_observations=len(allrows),
                coverage_errors=coverage_errors,
                current_source_drift=drift,group_source_drift=copies,synthetic_only=True,
                fixture_shims='empty package initializers only; see script; not policy overrides',rr_fixture_adapted=False,
                collection_only=args.collect_only,collected_cases=sum(r['metadata'].get('collected_count',0) for r in runs))
    (root/'native-case-index.json').write_text(json.dumps(unique,ensure_ascii=False,indent=2))
    (root/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print('RESULT_ROOT='+str(root),flush=True)
    return int(bool(drift or copies or coverage_errors or any(r['returncode'] for r in runs)))
if __name__=='__main__':raise SystemExit(main())
