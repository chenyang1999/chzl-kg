"""Three bounded parent business counterexamples, synthetic fixtures only."""
from copy import deepcopy
import pytest
from tests.pipeline.test_r6_local_revision import native, proposal, call, A, B, DATE


def test_second_distinct_incomplete_target_can_be_reviewed_without_restarting_base(native):
    n = native
    original_state = n.sp.read_bytes()
    call(n, proposal(), {A:[1,2,6,7]}, revision='first-target')
    current_summary = n.a.file_version(n.root, n.summary_path)
    current_r6_path = n.root / n.summary['artifacts']['R6']
    current_r6 = n.a.file_version(n.root, current_r6_path)
    (n.root / 'synthetic.proposal.json').write_text(__import__('json').dumps(proposal((B,))))
    result = n.s.run_r6_revision(n.root, DATE, 'second-target',
        baseline_summary_sha256=current_summary['sha256'], baseline_r6_sha256=current_r6['sha256'],
        targets={B:[1,2,6,7]}, hermes=str(n.fake))
    assert result['coverage']['completed'] == [A,B]
    assert result['coverage']['formal_review_completed'] is True
    assert (n.root / 'model.count').read_text() == '2'
    assert n.sp.read_bytes() == original_state
    updated = n.a.read_object(n.summary_path)
    assert n.b.consume_authorized_inputs(updated, root=n.root)['R6']['hard_rejects']


def test_new_hard_reject_without_original_contract_evidence_is_rejected(native):
    n = native
    original = n.a.read_object(n.root / n.summary['artifacts']['R6'])
    sources = {u:p for u,p in n.b.consume_authorized_inputs(n.summary,root=n.root).items() if u != 'R6'}
    delta = proposal()
    delta['hard_rejects'] = [{'ts_code':A, 'mode_id':6}]
    with pytest.raises(ValueError):
        n.a.merge_r6_revision(original, delta, {A:[1,2,6,7]}, [A,B], sources)


def test_new_valid_evidence_can_replace_old_incomplete_null_reference(native):
    n = native
    original = n.a.read_object(n.root / n.summary['artifacts']['R6'])
    sources = deepcopy({u:p for u,p in n.b.consume_authorized_inputs(n.summary,root=n.root).items() if u != 'R6'})
    sources['R5']['previously_missing'] = None
    old_ref = {'source':'R5', 'json_pointer':'/previously_missing'}
    original['patterns_status'] = {'mode7':{'mode_id':7,'candidate_checks':[
        {'ts_code':A,'completion':'incomplete','evidence_refs':[old_ref],
         'missing_evidence':['original missing value; retained in the immutable baseline']}]}}
    frozen = deepcopy(original)
    delta = proposal()
    delta['candidate_checks'] = [x for x in delta['candidate_checks'] if x['mode_id'] == 7]
    revised, coverage = n.a.merge_r6_revision(original, delta, {A:[7]}, [A,B], sources)
    assert original == frozen
    assert revised['counter_arguments'] == original['counter_arguments']
    assert revised['hard_rejects'] == original['hard_rejects']
    check = n.a.r6_checks(revised)[7,A]
    assert check['completion'] == 'completed'
    assert check['evidence_refs'] == delta['candidate_checks'][0]['evidence_refs']
    assert coverage['formal_review_completed'] is False


def test_partial_review_updates_explicit_zero_evaluated_count(native):
    n = native
    original = n.a.read_object(n.root / n.summary['artifacts']['R6'])
    original['candidates_evaluated'] = 0
    sources = {u:p for u,p in n.b.consume_authorized_inputs(n.summary,root=n.root).items() if u != 'R6'}
    revised, coverage = n.a.merge_r6_revision(original, proposal(), {A:[1,2,6,7]}, [A,B], sources)
    assert coverage['evaluated'] == [A]
    assert revised['candidates_evaluated'] == 1
    assert revised['formal_review_completed'] is False
