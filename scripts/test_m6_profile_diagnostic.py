"""Synthetic fixtures only; no native/archive modules or providers are used."""
from copy import deepcopy
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


m6 = load('site_m6_projection_test', 'm6_profile_diagnostic.py')
renderer = load('site_m6_renderer_test', 'render-line-always-on.py')
old_tests = load('site_m6_existing_fixture', 'test_line_always_on.py')

# Actual native shape: each slot initializes both account runtimes. These
# deliberately invalid bytecode bytes must be hashed as receipt data, not run.
RUNTIME_BYTECODE = ('receipts/PV41.primary/hermes-secondary.pycache-df589e84876803a1c5c9194fddcf2db2/'
                   'Users/synthetic/benchmark-deps/always-on-hermes81-E-c26b834-20261016/'
                   'source/hermes_state_maintenance.cpython-313.pyc')


def predicate_sources():
    """Synthetic definitions must reproduce the pinned native predicate ASTs.

    Only the site's pure mirrors are read. No native source is imported or
    executed; the fixed native AST hashes prevent a changed mirror blessing
    itself through this fixture.
    """
    functions = {node.name: node for node in ast.parse(Path(m6.__file__).read_text()).body
                 if isinstance(node, ast.FunctionDef)}
    result = {}
    for filename, names in m6.CONTROL_PREDICATE_AST.items():
        nodes = []
        for name in names:
            node = deepcopy(functions['_'+name]); node.name = name
            if name == 'control_passed':
                for call in ast.walk(node):
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) \
                            and call.func.id in ('_control_ok', '_foreground_control_ok'):
                        call.func = ast.Attribute(value=ast.Call(func=ast.Name(id='modules', ctx=ast.Load()),
                            args=[], keywords=[]), attr=call.func.id[1:], ctx=ast.Load())
            nodes.append(node)
        result[filename] = ast.unparse(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])))+'\n'
    return result


def control_fixture():
    controls = [{'id': 'control'+str(i), 'phase': 'profile', 'expect': {'coverage': True}} for i in range(35)]
    jobs = [{'id': row['id']+'.p'+str(pass_id), 'packet': row['id'], 'pass': pass_id, 'control': True}
            for row in controls for pass_id in (1, 2)]
    return controls, {'jobs': jobs, 'valid_verdict_final': True,
                      'control_failed_valid_final': True, 'calibrate_before_candidates': True}


def authored(scenario):
    required = scenario in m6.REQUIRED_SCENARIOS
    optional = scenario == 'PV42'
    bounds = {'min': int(required), 'max': int(required or optional)}
    windows = [{'kind': 'habit_checkin' if required else 'followup', 'optional': optional, 'hit': required}] if required or optional else []
    count = int(required); requested = 3 if scenario == 'PV43' else count
    return {'original_bounds': bounds, 'observed_tick_sends': requested, 'send_observation': 'complete_horizon',
        'required_window_outcome': 'hit' if required else 'not_required', 'original_outcome': {
            'count': count, 'count_ok': True, 'over_count': 0, 'requested': requested, 'unsolicited': 0,
            'late_answers': 0, 'quiet_hours_violations': 0, 'windows': windows,
            'listed_scripted_occurrences': 3 if scenario == 'PV43' else 0}}


def summaries():
    cells = [{'scenario': s, 'account': a, 'status': 'complete', 'horizon_complete': True,
              'foreground_expectation_origin': 'universal_only_no_authored_foreground' if s=='PV42' else 'authored',
              'capture_complete': True, 'profile_available': True, **authored(s)} for s in m6.SCENARIOS for a in m6.ACCOUNTS]
    native = {'planned_cells': 12, 'cells': cells, 'provider_attempts': 2,
              'usage': [{'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120}, None]}
    profile = [{**dict.fromkeys(m6.PROFILE_FIELDS, True), 'reason': 'PRIVATE_REASON',
                'owner_id': 'PRIVATE_OWNER'} for _ in range(12)]
    profile[0]['supported'] = False
    fg = [dict.fromkeys(m6.FOREGROUND_FIELDS, True) for _ in range(12)]
    fg[0]['answered'] = False
    proactive = [{**dict.fromkeys(m6.PROACTIVE_FIELDS, False), **dict.fromkeys(m6.SCORE_FIELDS, 1)}]
    judging = {'planned_cells': 12, 'quality_ready': True, 'logical_jobs': 120, 'valid_jobs': 120,
        'started_attempts': 122, 'technical_errors': 1, 'interrupted_attempts': 1,
        'valid_controls': 70, 'matched_controls': 70, 'failed_controls': 0,
        'candidate_jobs': {'planned': 50, 'started': 50, 'valid': 50},
        'calibration_status': 'qualified', 'controls_qualified': True,
        'usage': [{'total_tokens': 9} for _ in range(121)]+[None],
        'primary': {'profile': profile, 'foreground': fg, 'proactive': proactive},
        'consistency': {p: {'paired_packets': len(rows), 'same_flags': len(rows)-1}
                        for p, rows in (('profile', profile), ('foreground', fg), ('proactive', proactive))}}
    return native, judging


def failed_calibration():
    native, judging = summaries()
    judging.update(quality_ready=False, logical_jobs=138, valid_jobs=70, started_attempts=70,
        technical_errors=0, interrupted_attempts=0, matched_controls=68, failed_controls=2,
        controls_qualified=False, calibration_status='failed_valid_final',
        candidate_jobs={'planned': 68, 'started': 0, 'valid': 0},
        usage=[{'total_tokens': 9} for _ in range(70)], primary={p: [] for p in m6.PHASES},
        consistency={p: {'paired_packets': 0, 'same_flags': 0} for p in m6.PHASES})
    return native, judging


def proof():
    return {**dict.fromkeys(('native_ref', 'helper_ref', 'evaluator_ref'), 'a'*40),
            **dict.fromkeys(('plan_sha256', 'judge_binding_sha256', 'native_inventory_sha256',
                            'judge_inventory_sha256', 'h1_terminal_audit_sha256'), 'b'*64),
            'native_outcomes_adapter_sha256': m6.sha(m6.NATIVE_OUTCOMES_ADAPTER.encode())}


def projected():
    native, judging = summaries()
    return m6.project(native, judging, proof=proof())


def original_calibration_projected(index=0):
    native,judging=failed_calibration();retained=m6.RETAINED_CALIBRATIONS[index]
    judging.update(matched_controls=retained['matched_controls'],failed_controls=retained['failed_controls'])
    judging['usage']=[{'total_tokens':retained['known_total_tokens']}]+[
        {'total_tokens':0} for _ in range(retained['known_total_token_attempts']-1)]
    pins=proof()
    pins.update({key:retained[key] for key in ('evaluator_ref','judge_binding_sha256','judge_inventory_sha256')})
    return m6.project(native,judging,proof=pins)


class Projection(unittest.TestCase):
    def test_null_trust_fails_before_any_archive_read_or_execution(self):
        awaiting = {'protocol': m6.TRUST_PROTOCOL, 'status': 'awaiting_reviewed_freeze', 'binding': None}
        with patch.object(m6, 'TRUST', awaiting), patch.object(m6, 'inventory') as read, \
                patch.object(m6, '_summary') as execute, patch.object(m6, '_native_outcomes') as score:
            with self.assertRaisesRegex(ValueError, 'reviewed_freeze_required'):
                m6.verified_projection('/not-a-study', '/not-a-judge')
        read.assert_not_called(); execute.assert_not_called(); score.assert_not_called()
        self.assertIsNone(awaiting['binding'])

    def test_pending_is_only_method_no_invented_measurements_or_pins(self):
        value = m6.pending_projection(); m6.validate_public(value)
        self.assertEqual(12, len(value['cells']))
        self.assertIsNone(value['native']); self.assertIsNone(value['judging']); self.assertIsNone(value['proof'])
        self.assertTrue(all(r['status'] == 'not_exported' and r['profile_available'] is None for r in value['cells']))
        self.assertTrue(all(r['foreground_expectation_origin'] is None for r in value['cells']))

    def test_foreground_provenance_is_closed_and_does_not_change_scores_or_denominators(self):
        native, judging = summaries(); before=deepcopy((native,judging))
        value=m6.project(native,judging,proof=proof())
        self.assertEqual(before,(native,judging))
        self.assertEqual(12,len(value['cells']))
        self.assertEqual(10,sum(row['foreground_expectation_origin']=='authored' for row in value['cells']))
        self.assertEqual({'PV42'}, {row['scenario'] for row in value['cells']
            if row['foreground_expectation_origin']=='universal_only_no_authored_foreground'})
        self.assertEqual(12,value['judging']['phases']['foreground']['primary_units'])
        self.assertEqual(1,value['judging']['phases']['foreground']['flags']['answered']['false'])
        for bad in (None,'default',True,{}):
            changed=deepcopy(value);changed['cells'][0]['foreground_expectation_origin']=bad
            with self.assertRaises(ValueError):m6.validate_public(changed)

    def test_only_absent_original_foreground_uses_universal_criteria(self):
        cases=[{'id':s,'expect':{} if s=='PV42' else {'foreground':{}}} for s in m6.SCENARIOS]
        before=deepcopy(cases)
        self.assertEqual({s:'universal_only_no_authored_foreground' if s=='PV42' else 'authored'
            for s in m6.SCENARIOS},m6._foreground_origins(cases))
        self.assertEqual(before,cases)
        cases[1]['expect']['foreground']={}
        self.assertEqual('authored',m6._foreground_origins(cases)['PV42'])
        for malformed in (None,False,[],0,''):
            cases[1]['expect']['foreground']=malformed
            with self.assertRaisesRegex(ValueError,'m6_invalid_original_foreground'):
                m6._foreground_origins(cases)

    def test_all_twelve_and_adverse_verdicts_stay_in_their_own_phase(self):
        value = projected()
        self.assertEqual(12, len(value['cells']))
        self.assertEqual({'true': 11, 'false': 1, 'applicable': 12}, value['judging']['phases']['profile']['flags']['supported'])
        self.assertEqual(1, value['judging']['phases']['foreground']['flags']['answered']['false'])
        self.assertEqual(1, value['judging']['phases']['proactive']['primary_units'])
        self.assertEqual(1, value['judging']['phases']['proactive']['flags']['private']['false'])
        wire = json.dumps(value)
        self.assertNotIn('PRIVATE_REASON', wire); self.assertNotIn('PRIVATE_OWNER', wire)

    def test_incomplete_interrupted_unstarted_and_profile_availability_are_distinct(self):
        native, judging = summaries()
        for i, row in enumerate(native['cells']):
            row.update(status='incomplete' if i < 3 else 'interrupted' if i == 3 else 'unstarted',
                       horizon_complete=False, capture_complete=i < 3, profile_available=i < 3,
                       original_outcome=None, observed_tick_sends=0 if i < 3 else None,
                       send_observation='partial' if i < 3 else 'unavailable',
                       required_window_outcome='unavailable' if row['scenario'] in m6.REQUIRED_SCENARIOS else 'not_required')
        judging['quality_ready'] = False
        judging['primary']['profile'] = judging['primary']['profile'][:2]
        judging['consistency']['profile'] = {'paired_packets': 2, 'same_flags': 1}
        value = m6.project(native, judging, proof=proof())
        self.assertEqual('incomplete', value['status']); self.assertEqual(12, len(value['cells']))
        self.assertEqual(0, value['native']['complete_horizons'])
        self.assertEqual(3, value['native']['profile_available_cells'])
        self.assertEqual(8, sum(r['status'] == 'unstarted' for r in value['cells']))
        # An actual reviewed empty result is available; unavailable has no such credit.
        native['cells'][0]['profile_available'] = False
        other = m6.project(native, judging, proof=proof())
        self.assertEqual(2, other['native']['profile_available_cells'])

    def test_valid_failed_control_is_retained_and_never_turned_into_ready(self):
        native, judging = summaries()
        judging.update(controls_qualified=False, quality_ready=False, matched_controls=69,
                       failed_controls=1, calibration_status='failed_valid_final')
        value = m6.project(native, judging, proof=proof())
        self.assertEqual(70, value['judging']['valid_controls'])
        self.assertEqual(122, value['judging']['started_attempts'])
        self.assertFalse(value['quality_ready'])
        self.assertEqual(1, value['judging']['phases']['profile']['flags']['supported']['false'])
        value['quality_ready'] = True; value['status'] = 'qualified'
        with self.assertRaisesRegex(ValueError, 'invalid_readiness'): m6.validate_public(value)

    def test_failed_calibration_retains_native_completion_and_spent_usage_without_candidate_scores(self):
        native, judging = failed_calibration(); before=deepcopy((native, judging))
        value=m6.project(native, judging, proof=proof())
        self.assertEqual(before, (native, judging))
        self.assertEqual(12, value['native']['complete_horizons'])
        self.assertEqual((70, 68, 2), tuple(value['judging'][k] for k in
            ('valid_controls', 'matched_controls', 'failed_controls')))
        self.assertEqual({'planned': 68, 'started': 0, 'valid': 0}, value['judging']['candidate_jobs'])
        self.assertEqual('failed_valid_final', value['judging']['calibration_status'])
        self.assertEqual(0, value['judging']['technical_errors'])
        self.assertEqual(630, value['judging']['usage']['total_tokens']['observed_tokens'])
        self.assertFalse(value['quality_ready'])
        self.assertTrue(all(row['primary_units']==0 for row in value['judging']['phases'].values()))

    def test_partial_controls_do_not_imply_terminal_calibration_or_zero_candidate_quality(self):
        native, judging=failed_calibration()
        judging.update(valid_jobs=10, started_attempts=12, valid_controls=10, matched_controls=9,
            failed_controls=1, technical_errors=1, interrupted_attempts=1, calibration_status='pending',
            usage=[{'total_tokens':9} for _ in range(11)]+[None])
        value=m6.project(native, judging, proof=proof())
        self.assertEqual('pending', value['judging']['calibration_status'])
        self.assertEqual(1, value['judging']['failed_controls'])
        self.assertEqual(1, value['judging']['usage']['total_tokens']['unknown_attempts'])
        for edit in (lambda d:d['judging'].update(calibration_status='failed_valid_final'),
                     lambda d:d['judging'].update(matched_controls=10),
                     lambda d:d['judging']['candidate_jobs'].update(started=13),
                     lambda d:d['judging'].update(technical_errors=0),
                     lambda d:d['judging'].update(controls_qualified=True)):
            changed=deepcopy(value);edit(changed)
            with self.subTest(edit=edit),self.assertRaises(ValueError):m6.validate_public(changed)

    def test_second_pass_only_consistency_never_replaces_first_adverse(self):
        value = projected()
        self.assertEqual(1, value['judging']['primary_pass']); self.assertEqual(2, value['judging']['consistency_pass'])
        self.assertEqual(11, value['judging']['consistency']['profile']['same_flags'])
        self.assertEqual(1, value['judging']['phases']['profile']['flags']['supported']['false'])

    def test_unknown_component_is_not_zero_or_inferred_from_known_total(self):
        value = projected(); usage = value['native']['usage']
        self.assertEqual({'known_attempts': 1, 'unknown_attempts': 1, 'observed_tokens': 120}, usage['total_tokens'])
        self.assertEqual({'known_attempts': 0, 'unknown_attempts': 2, 'observed_tokens': None}, usage['reasoning_tokens'])
        value['native']['usage']['reasoning_tokens']['observed_tokens'] = 0
        with self.assertRaisesRegex(ValueError, 'unknown_usage_is_not_zero'): m6.validate_public(value)

    def test_h1_is_fixed_separate_and_not_added_to_current_attempts(self):
        value = projected()
        self.assertEqual(2, value['native']['provider_attempts'])
        self.assertEqual(16, value['prior_aborted']['provider_attempts'])
        self.assertEqual(177166, value['prior_aborted']['known_total_tokens'])
        self.assertEqual(0, value['prior_aborted']['judge_attempts'])

    def test_j3_j4_fixed_list_is_preserved_in_pending_and_later_bindings_without_pooling(self):
        for value in (m6.pending_projection(),projected()):
            retained=value['retained_calibrations']
            self.assertEqual(m6.RETAINED_CALIBRATIONS,retained)
            self.assertEqual([(70,68,2),(70,69,1)],[tuple(row[k] for k in
                ('valid_controls','matched_controls','failed_controls')) for row in retained])
            self.assertEqual([171417,171887],[row['known_total_tokens'] for row in retained])
            self.assertTrue(all(row['candidate_jobs']=={'planned':68,'started':0,'valid':0} for row in retained))
            for index in (0,1):
                for key,bad in (('failed_controls',0),('known_total_tokens',0),('seal_proof_sha256','c'*64)):
                    changed=deepcopy(value);changed['retained_calibrations'][index][key]=bad
                    with self.subTest(index=index,key=key),self.assertRaises(ValueError):m6.validate_public(changed)
            for edit in (lambda d:d['retained_calibrations'].pop(),
                         lambda d:d['retained_calibrations'].reverse(),
                         lambda d:d['retained_calibrations'].append(deepcopy(d['retained_calibrations'][0])),
                         lambda d:d.pop('retained_calibrations')):
                changed=deepcopy(value);edit(changed)
                with self.subTest(edit=edit),self.assertRaises(ValueError):m6.validate_public(changed)
        current=projected()
        self.assertEqual(122,current['judging']['started_attempts'])
        self.assertEqual(1089,current['judging']['usage']['total_tokens']['observed_tokens'])
        self.assertEqual([70,70],[row['started_attempts'] for row in current['retained_calibrations']])

    def test_either_current_binding_must_match_its_fixed_inventory_counts_and_usage(self):
        for index in (0,1):
            value=original_calibration_projected(index);m6.validate_public(value)
            self.assertEqual(70,value['judging']['started_attempts'])
            self.assertEqual(m6.RETAINED_CALIBRATIONS[index]['known_total_tokens'],
                value['judging']['usage']['total_tokens']['observed_tokens'])
            for edit in (lambda d:d['proof'].update(evaluator_ref='a'*40),
                         lambda d:d['proof'].update(judge_inventory_sha256='c'*64),
                         lambda d:d['judging']['usage']['total_tokens'].update(observed_tokens=171418)):
                changed=deepcopy(value);edit(changed)
                with self.subTest(index=index,edit=edit),self.assertRaisesRegex(ValueError,'retained_current_record_changed'):
                    m6.validate_public(changed)

    def test_completed_required_zero_send_is_native_miss_not_hidden_by_ai_denominator(self):
        native, judging = summaries(); row = native['cells'][0]
        row.update(observed_tick_sends=0, required_window_outcome='completed_miss')
        row['original_outcome'].update(count=0, count_ok=False, requested=0)
        row['original_outcome']['windows'][0]['hit'] = False
        value = m6.project(native, judging, proof=proof())
        self.assertEqual({'planned_cells': 4, 'hit': 3, 'completed_miss': 1, 'unavailable': 0}, value['native']['required_windows'])
        self.assertFalse(value['cells'][0]['original_outcome']['count_ok'])
        # AI units are still only actual judged messages; no fabricated no-send AI packet.
        self.assertEqual(1, value['judging']['phases']['proactive']['primary_units'])

    def test_optional_zero_is_valid_and_pv43_scripted_occurrences_are_descriptive(self):
        value = projected()
        optional = next(row for row in value['cells'] if row['scenario'] == 'PV42')
        self.assertEqual(0, optional['observed_tick_sends']); self.assertTrue(optional['original_outcome']['count_ok'])
        self.assertEqual('not_required', optional['required_window_outcome'])
        stopped = next(row for row in value['cells'] if row['scenario'] == 'PV43')
        self.assertEqual(3, stopped['original_outcome']['requested'])
        self.assertEqual(3, stopped['original_outcome']['listed_scripted_occurrences'])
        self.assertEqual(0, stopped['original_outcome']['count']); self.assertTrue(stopped['original_outcome']['count_ok'])
        for scenario in ('PV45', 'PV46'):
            row = next(row for row in value['cells'] if row['scenario'] == scenario)
            self.assertEqual({'min': 0, 'max': 0}, row['original_bounds'])

    def test_incomplete_required_cell_keeps_observed_partial_zero_without_final_credit(self):
        native, judging = summaries(); row = native['cells'][0]
        row.update(status='incomplete', horizon_complete=False, original_outcome=None,
                   observed_tick_sends=0, send_observation='partial', required_window_outcome='unavailable')
        judging['quality_ready'] = False
        value = m6.project(native, judging, proof=proof())
        self.assertEqual({'planned_cells': 4, 'hit': 3, 'completed_miss': 0, 'unavailable': 1}, value['native']['required_windows'])
        self.assertIsNone(value['cells'][0]['original_outcome'])
        self.assertEqual(0, value['cells'][0]['observed_tick_sends'])
        value['cells'][0]['original_outcome'] = authored('PV41')['original_outcome']
        with self.assertRaisesRegex(ValueError, 'incomplete_outcome'): m6.validate_public(value)

    def test_closed_public_shape_rejects_private_fields_types_and_fake_denominators(self):
        edits = [lambda d: d.update(raw_chat='PRIVATE'), lambda d: d['proof'].update(path='/private/study'),
                 lambda d: d['cells'][0].update(owner_id='PRIVATE'), lambda d: d['cells'].pop(),
                 lambda d: d.update(policy_count=True), lambda d: d['judging'].update(primary_pass=True),
                 lambda d: d['judging']['phases']['profile']['flags']['supported'].update(true=12),
                 lambda d: d['native']['usage']['total_tokens'].update(observed_tokens=float('nan'))]
        for edit in edits:
            value = projected(); edit(value)
            with self.subTest(edit=edit), self.assertRaises((ValueError, TypeError)): m6.validate_public(value)

    def test_bad_private_verdict_cannot_disappear_from_denominator(self):
        native, judging = summaries(); judging['primary']['profile'][0]['supported'] = 'false'
        with self.assertRaisesRegex(ValueError, 'private_verdict'): m6.project(native, judging, proof=proof())


class ControlAccounting(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        for name, source in predicate_sources().items():
            target=self.root/'source'/m6.PREFIX/name
            target.parent.mkdir(parents=True,exist_ok=True);target.write_text(source)
        self.controls,self.binding=control_fixture()
        self.write_controls()

    def write_controls(self):
        (self.root/'controls.json').write_text(json.dumps(self.controls))

    def attempt(self, job, attempt=1, *, status='ok', coverage=True):
        # Raw accounting runs only after the intended native summary validates
        # the complete claim/wire/receipt bindings; this fixture isolates counts.
        stem=self.root/'receipts'/(job['id']+'.a'+str(attempt))
        stem.parent.mkdir(exist_ok=True)
        Path(str(stem)+'.started.json').write_text('{}')
        if status is not None:
            Path(str(stem)+'.json').write_text(json.dumps({'status':status,
                'verdict':{'coverage':coverage,'reason':'PRIVATE_CONTROL_REASON'},
                'usage':{'input_tokens':1,'output_tokens':2,'total_tokens':3}}))

    def test_full_valid_calibration_counts_expected_matches_not_technical_success(self):
        for job in self.binding['jobs']:
            self.attempt(job,coverage=job['packet']!='control0')
        summary={'started_attempts':70,'valid_jobs':70,'controls_qualified':False}
        result=m6._judge_accounting(self.root,self.binding,summary)
        self.assertEqual((70,68,2),tuple(result[k] for k in ('valid_controls','matched_controls','failed_controls')))
        self.assertEqual('failed_valid_final',result['calibration_status'])
        self.assertEqual({'planned':0,'started':0,'valid':0},result['candidate_jobs'])
        self.assertEqual((0,0),(result['technical_errors'],result['interrupted_attempts']))
        self.assertEqual(210,m6._usage(result['usage'])['total_tokens']['observed_tokens'])
        self.assertNotIn('PRIVATE_CONTROL_REASON',json.dumps(result))
        # A separately bound reference correction changes data, not predicates.
        self.controls[0]['expect']['coverage']=False;self.write_controls()
        corrected=m6._judge_accounting(self.root,self.binding,{**summary,'controls_qualified':True})
        self.assertEqual((70,0,'qualified'),(corrected['matched_controls'],corrected['failed_controls'],corrected['calibration_status']))

    def test_claim_starts_and_all_technical_attempt_usage_are_retained(self):
        for job in self.binding['jobs']:self.attempt(job)
        candidates=[{'id':'candidate'+str(i),'packet':'private'+str(i),'pass':1,'control':False} for i in range(4)]
        self.binding['jobs']+=candidates
        self.attempt(candidates[0],status=None)
        self.attempt(candidates[1],status='error');self.attempt(candidates[1],2)
        self.attempt(candidates[3])
        result=m6._judge_accounting(self.root,self.binding,
            {'started_attempts':74,'valid_jobs':72,'controls_qualified':True})
        self.assertEqual({'planned':4,'started':3,'valid':2},result['candidate_jobs'])
        self.assertEqual((1,1),(result['technical_errors'],result['interrupted_attempts']))
        self.assertEqual({'known_attempts':73,'unknown_attempts':1,'observed_tokens':219},m6._usage(result['usage'])['total_tokens'])
        self.assertNotIn('private',json.dumps(result))

    def test_partial_controls_are_pending_and_summary_or_finality_drift_is_refused(self):
        self.attempt(self.binding['jobs'][0],coverage=False)
        summary={'started_attempts':1,'valid_jobs':1,'controls_qualified':False}
        result=m6._judge_accounting(self.root,self.binding,summary)
        self.assertEqual(('pending',0,1),(result['calibration_status'],result['matched_controls'],result['failed_controls']))
        for bad in ({**summary,'started_attempts':0},{**summary,'valid_jobs':0},{**summary,'controls_qualified':True}):
            with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'attempt_accounting_changed'):
                m6._judge_accounting(self.root,self.binding,bad)
        for name in ('valid_verdict_final','control_failed_valid_final','calibrate_before_candidates'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'valid_final_contract_changed'):
                m6._judge_accounting(self.root,{**self.binding,name:False},summary)

    def test_pinned_predicate_ast_matches_the_mirror_and_changed_predicate_is_refused(self):
        m6._check_control_predicates(self.root)
        self.assertFalse(m6._control_passed({'phase':'foreground','expect':{'answered':True}}, {'answered':False}))
        self.assertTrue(m6._control_passed({'phase':'foreground','expect':{'answered':True}}, {'answered':True}))
        packet={'phase':'proactive','expect':{'warranted':True,'min_useful':3,'max_useful':4,'max_timing':2,'min_progress':1}}
        verdict={'warranted':True,'useful':3,'timing':2,'decision_progress':1}
        self.assertTrue(m6._control_passed(packet,verdict))
        for key,bad in (('warranted',False),('useful',2),('useful',5),('timing',3),('decision_progress',None)):
            with self.subTest(key=key,bad=bad):self.assertFalse(m6._control_passed(packet,{**verdict,key:bad}))
        self.assertTrue(m6._control_passed({'phase':'profile','expect':{'coverage':True,'min_useful':3}}, {'coverage':True,'useful':3}))
        self.assertFalse(m6._control_passed({'phase':'profile','expect':{'coverage':True,'min_useful':3}}, {'coverage':True,'useful':2}))
        target=self.root/'source'/m6.PREFIX/'judge.py'
        target.write_text(target.read_text().replace('return all(checks)','return True'))
        with self.assertRaisesRegex(ValueError,'control_predicate_changed'):m6._check_control_predicates(self.root)


class PreImport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.study = Path(self.tmp.name).resolve()/'native'; self.judge = Path(self.tmp.name).resolve()/'judge'
        for root in (self.study, self.judge):
            for name in ('m6_profile_pilot.py', 'm6_profile_capture.py', 'runner.py', 'judge.py', 'metrics.py', 'm6_profile_judge.py'):
                path = root/'source'/m6.PREFIX/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('')
        for name, source in predicate_sources().items():
            (self.judge/'source'/m6.PREFIX/name).write_text(source)
        self.pins = {'native_ref': 'a'*40, 'helper_ref': 'b'*40, 'evaluator_ref': 'c'*40,
            'plan_sha256': 'd'*64, 'judge_binding_sha256': 'e'*64,
            'native_files_sha256': m6.digest(m6.inventory(self.study)),
            'judge_files_sha256': m6.digest(m6.inventory(self.judge)),
            'h1_terminal_audit_sha256': 'f'*64}
        self.trust = {'protocol': m6.TRUST_PROTOCOL, 'status': 'reviewed', 'binding': self.pins}

    def test_summary_origin_cannot_override_the_pinned_original_corpus(self):
        schedule=[{'slot':s+'.'+a,'case':s,'account':a} for s in m6.SCENARIOS for a in m6.ACCOUNTS]
        plan={'native_ref':self.pins['native_ref'],'source_ref':self.pins['helper_ref'],'schedule':schedule}
        cases=[{'id':s,'expect':{} if s=='PV42' else {'foreground':{}}} for s in m6.SCENARIOS]
        (self.study/'plan.json').write_text(json.dumps(plan));(self.study/'cases.json').write_text(json.dumps(cases))
        (self.judge/'inputs').mkdir();(self.judge/'inputs'/'cases.json').write_bytes((self.study/'cases.json').read_bytes())
        self.pins['plan_sha256']=m6.sha((self.study/'plan.json').read_bytes())
        binding={'native_source_ref':self.pins['native_ref'],'helper_ref':self.pins['helper_ref'],
            'evaluator_source_ref':self.pins['evaluator_ref'],'native_plan_sha256':self.pins['plan_sha256'],
            'original_study':str(self.study),'original_input_files':{'cases.json':m6.sha((self.study/'cases.json').read_bytes())},
            'jobs':[{'id':'control'+str(i),'control':True} for i in range(70)]}
        (self.judge/'binding.json').write_text(json.dumps(binding))
        self.pins.update(judge_binding_sha256=m6.sha((self.judge/'binding.json').read_bytes()),
            native_files_sha256=m6.digest(m6.inventory(self.study)),judge_files_sha256=m6.digest(m6.inventory(self.judge)))
        available={row['slot']:{'foreground_expectation_origin':'authored' if row['case']!='PV42'
            else 'universal_only_no_authored_foreground'} for row in schedule}
        for bad in (None,'authored','unreviewed_default'):
            forged=deepcopy(available);forged['PV42.primary']['foreground_expectation_origin']=bad
            summaries=[{'protocol':m6.NATIVE_PROTOCOL}, {'protocol':m6.JUDGE_PROTOCOL,'control_jobs':70,
                'logical_jobs':70,'availability':forged}]
            with patch.object(m6,'TRUST',self.trust),patch.object(m6,'_summary',side_effect=summaries), \
                    patch.object(m6,'_native_outcomes') as native_score:
                with self.assertRaisesRegex(ValueError,'m6_foreground_origin_changed'):
                    m6.verified_projection(self.study,self.judge)
            native_score.assert_not_called()

    def test_foreign_self_rehashed_source_and_shadow_module_reject_before_cli(self):
        for name in ('source/'+m6.PREFIX+'runner.py', 'source/tempfile.py'):
            with self.subTest(name=name):
                path = self.study/name; path.write_text('raise RuntimeError("SHOULD_NOT_RUN")')
                # An attacker can rewrite its own manifest, never the reviewed external inventory.
                (self.study/'plan.json').write_text(json.dumps({'source_files': m6.inventory(self.study)}))
                with patch.object(m6, 'TRUST', self.trust), patch.object(m6, '_summary') as execute:
                    with self.assertRaisesRegex(ValueError, 'untrusted_archive_inventory'):
                        m6.verified_projection(self.study, self.judge)
                execute.assert_not_called()
                if name.endswith('tempfile.py'): path.unlink()

    def test_only_receipt_runtime_bytecode_is_opaque_and_no_links_or_special_files_are_allowed(self):
        target = Path(self.tmp.name)/'foreign'; target.mkdir()
        entries = [('symlink', 'source/foreign'), ('symlink', RUNTIME_BYTECODE),
                   ('fifo', RUNTIME_BYTECODE), ('pyc', 'source/module.pyc'),
                   ('pyc', 'inputs/module.pyc'), ('directory', 'source/__pycache__'),
                   ('directory', 'inputs/__pycache__'), ('pyc', 'inputs/'+RUNTIME_BYTECODE),
                   ('pyc', RUNTIME_BYTECODE.replace('PV41.primary', 'PV40.primary')),
                   ('pyc', RUNTIME_BYTECODE.replace('hermes-secondary.', 'hermes-foreign.')),
                   ('pyc', RUNTIME_BYTECODE.replace('df589e84876803a1c5c9194fddcf2db2/', 'df589e84876803a1c5c9194fddcf2db2extra/'))]
        for mode, name in entries:
            with self.subTest(mode=mode, name=name):
                path = self.study/name; path.parent.mkdir(parents=True, exist_ok=True)
                if mode == 'symlink': path.symlink_to(target, target_is_directory=True)
                elif mode == 'fifo': os.mkfifo(path)
                elif mode == 'directory': path.mkdir()
                else: path.write_bytes(b'bytecode')
                with patch.object(m6, 'TRUST', self.trust), patch.object(m6, '_summary') as execute, \
                        patch.object(m6, '_native_outcomes') as score:
                    with self.assertRaisesRegex(ValueError, 'untrusted_archive_entry'):
                        m6.verified_projection(self.study, self.judge)
                execute.assert_not_called(); score.assert_not_called()
                if mode == 'directory': path.rmdir()
                else: path.unlink()

    def test_runtime_bytecode_requires_exact_external_pin_before_any_cli(self):
        path = self.study/RUNTIME_BYTECODE; path.parent.mkdir(parents=True)
        original_pin = self.pins['native_files_sha256']
        for mode in ('unpinned', 'changed'):
            with self.subTest(mode=mode):
                self.pins['native_files_sha256'] = original_pin
                path.write_bytes(b'opaque runtime bytecode')
                if mode == 'changed':
                    self.pins['native_files_sha256'] = m6.digest(m6.inventory(self.study))
                    path.write_bytes(b'changed runtime bytecode')
                with patch.object(m6, 'TRUST', self.trust), patch.object(m6, '_summary') as execute, \
                        patch.object(m6, '_native_outcomes') as score:
                    with self.assertRaisesRegex(ValueError, 'untrusted_archive_inventory'):
                        m6.verified_projection(self.study, self.judge)
                execute.assert_not_called(); score.assert_not_called(); path.unlink()

    def test_full_externally_pinned_inventory_is_required_not_a_loader_allowlist(self):
        (self.study/'source'/m6.PREFIX/'runner.py').unlink()
        # Even an independently pinned incomplete inventory cannot execute.
        self.pins['native_files_sha256'] = m6.digest(m6.inventory(self.study))
        with patch.object(m6, 'TRUST', self.trust), patch.object(m6, '_summary') as execute, \
                self.assertRaisesRegex(ValueError, 'incomplete_source_closure'):
            m6.verified_projection(self.study, self.judge)
        execute.assert_not_called()

    def test_reviewed_trust_contains_only_inventory_digests_not_private_filenames(self):
        private = self.judge/'receipts'/'synthetic-blind-unit.p1.a1.json'
        private.parent.mkdir(); private.write_text('{}')
        self.pins['judge_files_sha256'] = m6.digest(m6.inventory(self.judge))
        with patch.object(m6, 'TRUST', self.trust):
            pins = m6.trusted()
        self.assertNotIn('synthetic-blind-unit', json.dumps(pins))
        self.assertNotIn('receipts/', json.dumps(pins)); self.assertNotIn('source/', json.dumps(pins))
        for key in ('native_files_sha256', 'judge_files_sha256'):
            self.assertRegex(pins[key], r'^[0-9a-f]{64}$')

    def test_intended_isolated_summary_cli_with_synthetic_sources_only_and_no_writes(self):
        schedule = [{'slot': s+'.'+a, 'case': s, 'account': a} for s in m6.SCENARIOS for a in m6.ACCOUNTS]
        plan = {'native_ref': self.pins['native_ref'], 'source_ref': self.pins['helper_ref'], 'schedule': schedule}
        cases = [{'id': scenario, 'expect': {**({'foreground': {}} if scenario!='PV42' else {}),
                  'proactive': {**authored(scenario)['original_bounds'],
                  'windows': authored(scenario)['original_outcome']['windows']}}} for scenario in m6.SCENARIOS]
        for name, content in (('plan.json', plan), ('cases.json', cases), ('policy.json', {}), ('hermes-binding.json', {})):
            path = self.study/name; path.write_text(json.dumps(content))
            target = self.judge/'inputs'/name; target.parent.mkdir(exist_ok=True); target.write_bytes(path.read_bytes())
        self.pins['plan_sha256'] = m6.sha((self.study/'plan.json').read_bytes())
        controls, control_binding=control_fixture()
        (self.judge/'controls.json').write_text(json.dumps(controls))
        binding = {**control_binding, 'native_source_ref': self.pins['native_ref'], 'helper_ref': self.pins['helper_ref'],
            'evaluator_source_ref': self.pins['evaluator_ref'], 'native_plan_sha256': self.pins['plan_sha256'],
            'original_study': str(self.study), 'original_input_files': m6.inventory(self.judge/'inputs')}
        (self.judge/'binding.json').write_text(json.dumps(binding))
        self.pins['judge_binding_sha256'] = m6.sha((self.judge/'binding.json').read_bytes())
        summaries = [({'protocol': m6.NATIVE_PROTOCOL, 'planned_cells': 12}, self.study, 'm6_profile_pilot.py'),
            ({'protocol': m6.JUDGE_PROTOCOL, 'planned_cells': 12, 'quality_ready': False,
              'availability': {r['slot']: {'horizon_complete': False, 'capture_complete': False,
                   'foreground_expectation_origin': 'authored' if r['case']!='PV42' else 'universal_only_no_authored_foreground',
                   'profile_available': False, 'stop_code': 'native_cell_unavailable'} for r in schedule},
              'primary': {p: [] for p in m6.PHASES}, 'second_pass_consistency': {p: {'paired_packets': 0, 'same_flags': 0} for p in m6.PHASES},
              'logical_jobs': 70, 'control_jobs': 70, 'valid_jobs': 0, 'started_attempts': 0, 'controls_qualified': False},
             self.judge, 'm6_profile_judge.py')]
        for value, root, filename in summaries:
            # A tiny synthetic stdout-only CLI, not copied or imported native code.
            target=root/'source'/m6.PREFIX/filename
            target.write_text(target.read_text()+'print('+repr(json.dumps(value))+')\n')
        runtime = self.study/RUNTIME_BYTECODE; runtime.parent.mkdir(parents=True)
        runtime.write_bytes(b'opaque, intentionally invalid Python bytecode')
        nested = runtime.parent/'__pycache__'/'preserved.pyo'; nested.parent.mkdir()
        nested.write_bytes(b'also opaque')
        native_inventory = m6.inventory(self.study)
        self.assertEqual(m6.sha(runtime.read_bytes()), native_inventory[RUNTIME_BYTECODE])
        self.assertEqual(m6.sha(nested.read_bytes()), native_inventory[nested.relative_to(self.study).as_posix()])
        self.pins.update(native_files_sha256=m6.digest(m6.inventory(self.study)),
                         judge_files_sha256=m6.digest(m6.inventory(self.judge)))
        before = deepcopy(self.pins)
        with patch.object(m6, 'TRUST', self.trust), patch.object(m6.subprocess, 'run', wraps=m6.subprocess.run) as command:
            result = m6.verified_projection(self.study, self.judge)
        self.assertEqual(3, command.call_count)
        for call in command.call_args_list:
            self.assertEqual(['-I', '-B'], call.args[0][1:3]); self.assertEqual({}, call.kwargs['env'])
        for call in command.call_args_list[:2]:
            self.assertEqual('summary', call.args[0][4])
        self.assertEqual('-c', command.call_args_list[2].args[0][3])
        self.assertEqual(12, len(result['cells'])); self.assertEqual(0, result['native']['provider_attempts'])
        self.assertEqual(before['native_files_sha256'], m6.digest(m6.inventory(self.study)))
        self.assertEqual(before['judge_files_sha256'], m6.digest(m6.inventory(self.judge)))

    def test_adapter_rechecks_source_and_opaque_runtime_inventory_before_importing(self):
        marker = Path(self.tmp.name).resolve()/'must-not-execute'
        metrics = self.study/'source'/m6.PREFIX/'metrics.py'
        for mode in ('source', 'runtime_bytecode'):
            with self.subTest(mode=mode):
                if mode == 'source':
                    expected = m6.inventory(self.study)
                    metrics.write_text('open('+repr(str(marker))+',"w").write("bad")')
                else:
                    # metrics now contains the marker-writing source and is
                    # itself pinned: the changed opaque data must stop import.
                    runtime = self.study/RUNTIME_BYTECODE; runtime.parent.mkdir(parents=True)
                    runtime.write_bytes(b'original opaque bytes')
                    expected = m6.inventory(self.study)
                    runtime.write_bytes(b'changed opaque bytes')
                with self.assertRaisesRegex(ValueError, 'native_outcomes_failed'):
                    m6._native_outcomes(self.study, expected)
                self.assertFalse(marker.exists())

    def test_adapter_uses_raw_hit_and_only_actually_observable_partial_sends(self):
        schedule = [{'slot': s+'.'+a, 'case': s, 'account': a} for s in m6.SCENARIOS for a in m6.ACCOUNTS]
        (self.study/'plan.json').write_text(json.dumps({'schedule': schedule}))
        cases=[]
        for scenario in m6.SCENARIOS:
            base=authored(scenario)
            score={**base['original_outcome'], 'window_hit': scenario in m6.REQUIRED_SCENARIOS,
                   'judged_window_hit': True}
            if scenario=='PV41':
                score.update(count=0, count_ok=False, requested=0, window_hit=False)
                score['windows'][0]['hit']=False
            cases.append({'id':scenario,'expect':{'proactive':{**base['original_bounds'],'windows':score['windows']}},
                          'synthetic_score':score})
        (self.study/'cases.json').write_text(json.dumps(cases))
        (self.study/'source'/m6.PREFIX/'metrics.py').write_text(
            'def score_run(case, receipt): return case["synthetic_score"]\n'
            'def proactive_sends(receipt): return receipt["sends"]\n'
            'def scripted_occurrences(case): return [0]*case["synthetic_score"]["listed_scripted_occurrences"]\n')
        for slot in schedule:
            if slot['account']=='secondary':continue
            root=self.study/'receipts'/slot['slot'];root.mkdir(parents=True)
            case=next(case for case in cases if case['id']==slot['case'])
            count=case['synthetic_score']['requested']
            receipt={'status':'measured','original_horizon_completed':True,
                     'capture':{'complete':True,'stopped':None},'sends':[{} for _ in range(count)]}
            if slot['case']=='PV44':
                receipt.update(status='incomplete',original_horizon_completed=False,
                    native_path={'partial_timelines':{'primary':[{'phase':'tick','kind':'push','duplicate':False}]}})
            (root/'receipt.json').write_text(json.dumps(receipt))
        result=m6._native_outcomes(self.study,m6.inventory(self.study))
        failed=next(r for r in result if r['scenario']=='PV41' and r['account']=='primary')
        self.assertEqual('completed_miss',failed['required_window_outcome'])
        self.assertNotIn('judged_window_hit',json.dumps(result))
        optional=next(r for r in result if r['scenario']=='PV42' and r['account']=='primary')
        self.assertTrue(optional['original_outcome']['count_ok']);self.assertEqual(0,optional['observed_tick_sends'])
        partial=next(r for r in result if r['scenario']=='PV44' and r['account']=='primary')
        self.assertEqual('unavailable',partial['required_window_outcome']);self.assertIsNone(partial['original_outcome'])
        self.assertEqual(1,partial['observed_tick_sends']);self.assertEqual('partial',partial['send_observation'])
        unknown=next(r for r in result if r['scenario']=='PV44' and r['account']=='secondary')
        self.assertIsNone(unknown['observed_tick_sends']);self.assertEqual('unavailable',unknown['send_observation'])


class Panel(unittest.TestCase):
    def test_both_histories_stay_separate_and_either_current_binding_is_not_extra_cost(self):
        later=projected();before=deepcopy(later);cases=json.loads((renderer.PUBLIC/renderer.CASES_NAME).read_text())
        for page in (renderer.render({'status':'pending'},m6_profile_diagnostic=later),
                     renderer.render_method(cases,m6_profile_diagnostic=later)):
            for text in ('J3 原始校準獨立保留','J4 原始校準獨立保留','這份校準獨立保留，不併入本頁目前判讀數或用量',
                         '70 個有效控制判讀中，符合預期 68、未符合 2','候選工作已開始 0/68，有效 0',
                         '70 個有效控制判讀中，符合預期 69、未符合 1',
                         '已知 171,417 total tokens（70 次），未知 0 次','已知 171,887 total tokens（70 次），未知 0 次',
                         '獨立 AI 先讀題目與規準、再比對參考值',
                         '前瞻性修改一個 coverage 參考布林值','模型請求內容與 rubric 相同',
                         '全新 70 個控制判讀','修正前未查看任何候選判讀','不是人類驗證，也未重算或覆寫 J3',
                         'J5 採前瞻性校準試驗','Medium／4,000 改為 High／32,768',
                         '沿用規準、控制與門檻','結果依上方實際收據顯示'):
                self.assertIn(text,page)
        self.assertEqual(before,later)
        for index,label in enumerate(('J3','J4')):
            page=renderer.m6_profile_panel(original_calibration_projected(index))
            self.assertIn(f'本頁目前展示的就是這一份 {label} 記錄，並非額外的一筆用量',page)
            self.assertEqual(1,page.count('本頁目前展示的就是這一份'))
            self.assertEqual(1,page.count('這份校準獨立保留，不併入本頁目前判讀數或用量'))

    def test_failed_valid_calibration_is_visible_in_both_pages_without_zero_quality_scores(self):
        native,judging=failed_calibration();value=m6.project(native,judging,proof=proof())
        cases=json.loads((renderer.PUBLIC/renderer.CASES_NAME).read_text())
        for page in (renderer.render({'status':'pending'},m6_profile_diagnostic=value),
                     renderer.render_method(cases,m6_profile_diagnostic=value)):
            panel=page[page.index('<h2>M6／真實側寫路徑'):].split('</section>',1)[0]
            for text in ('原始 horizon 完成 12/12','有效控制 70/70（符合預期 68、未符合 2）',
                         '校準已由有效結果確定未通過','候選判讀工作：已開始 0/68，有效 0/68',
                         '尚未開始 68 個工作','技術錯誤 0 次','本輪未進入候選判讀',
                         '側寫、前景回答與主動訊息的 AI 品質皆未判讀、不可判定',
                         'AI 判讀 70 次已開始嘗試','total_tokens 已知 630（70 次）'):
                self.assertIn(text,panel)
            self.assertNotIn('0/0',panel)
            self.assertNotIn('目前只列方法',panel)

    def test_partial_controls_are_displayed_as_incomplete_without_failed_or_terminal_claim(self):
        native,judging=failed_calibration()
        judging.update(valid_jobs=10,started_attempts=10,valid_controls=10,matched_controls=9,
            failed_controls=1,calibration_status='pending',usage=[{'total_tokens':9} for _ in range(10)])
        page=renderer.m6_profile_panel(m6.project(native,judging,proof=proof()))
        self.assertIn('校準尚未完成',page)
        self.assertIn('有效控制 10/70（符合預期 9、未符合 1）',page)
        self.assertNotIn('本輪校準已確定未通過',page)
        self.assertNotIn('本輪未進入候選判讀',page)
        self.assertNotIn('0/0',page)

    def test_pending_panel_in_same_two_pages_has_h1_and_no_result_claim(self):
        pending = m6.pending_projection()
        cases = json.loads((renderer.PUBLIC/renderer.CASES_NAME).read_text())
        results = renderer.render({'status': 'pending'}, m6_profile_diagnostic=pending)
        method = renderer.render_method(cases, m6_profile_diagnostic=pending)
        for page in (results, method):
            self.assertIn('M6／真實側寫路徑', page); self.assertIn('177,166', page)
            self.assertIn('目前只列方法', page); self.assertIn('70 個新控制', page)
            self.assertNotIn('<style', page[page.index('M6／真實側寫路徑'):])
        self.assertEqual('', renderer.m6_profile_panel(None))

    def test_measured_panel_keeps_three_phases_and_all12_cells(self):
        value = projected(); page = renderer.m6_profile_panel(value)
        for text in ('側寫品質', '前景回答品質', '實際主動訊息品質', '第 1 輪', '第 2 輪', '未知 1 次'):
            self.assertIn(text, page)
        for scenario in m6.SCENARIOS:
            for account in m6.ACCOUNTS: self.assertIn(scenario+' · '+account, page)
        self.assertNotIn('PRIVATE', page)

    def test_both_pages_disclose_the_validated_foreground_source_classes(self):
        value=projected();cases=json.loads((renderer.PUBLIC/renderer.CASES_NAME).read_text())
        for page in (renderer.render({'status':'pending'},m6_profile_diagnostic=value),
                     renderer.render_method(cases,m6_profile_diagnostic=value)):
            for text in ('10 個 cells 保留原作者前景規格','2 個 cells 原題未提供前景規格（PV42）',
                         '完成回答、沒有直接拒絕、誠實、有依據 4 項既有通用要求','完整既有對話，不新增可選檢查',
                         '保留原定 12 個前景 cells 分母','前景僅通用 4 項'):
                self.assertIn(text,page)
        changed=deepcopy(value)
        for row in changed['cells']:row['foreground_expectation_origin']='authored'
        page=renderer.m6_profile_panel(changed)
        self.assertIn('12 個 cells 保留原作者前景規格；0 個 cells 原題未提供前景規格',page)

    def test_optional_none_preserves_exact_existing_render_bytes(self):
        raw = old_tests.fixture(); data = renderer.project(raw, generated_at='2026-10-16', artifact_sha256='a'*64)
        self.assertEqual(renderer.render(data), renderer.render(data, m6_profile_diagnostic=None))

    def test_existing_explicit_ci_lists_execute_this_module_once(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('always-on-review.yml', 'deploy.yml'):
            source = (root/'.github/workflows'/name).read_text()
            command = next(row for row in source.splitlines() if 'python3 -B -m unittest scripts/test_line_always_on.py' in row)
            self.assertEqual(1, command.count('scripts/test_m6_profile_diagnostic.py'))
