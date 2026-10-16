"""Synthetic public-projection fixtures; no real archives or model calls."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


followup = load('capture_followup_test', 'm6_profile_capture_followup.py')
legacy = load('capture_followup_legacy_fixtures', 'test_m6_profile_diagnostic.py')
renderer = load('capture_followup_renderer_test', 'render-line-always-on.py')
base = followup.base


def proof():
    return {**followup.REFS, **{k: 'b'*64 for k in followup.PIN_KEYS-followup.REFS.keys()},
            'native_outcomes_adapter_sha256': base.sha(base.NATIVE_OUTCOMES_ADAPTER.encode())}


def summaries():
    native, judging = legacy.summaries()
    for row in native['cells']:
        row.update(checkin_capture_complete=True, checkin_observed=2, checkin_projectable_records=1)
    # All values are synthetic. Keep the first-pass adverse flags in the old
    # fixture, but use the new separately declared calibration denominator.
    judging.update(logical_jobs=144, valid_jobs=144, started_attempts=146,
        valid_controls=94, matched_controls=94, failed_controls=0,
        candidate_jobs={'planned': 50, 'started': 50, 'valid': 50},
        usage=[{'total_tokens': 9} for _ in range(144)]+[None, None])
    return native, judging


def projected():
    native, judging = summaries()
    return followup.project(native, judging, proof=proof())


class Projection(unittest.TestCase):
    def test_null_trust_refuses_before_path_reads_or_cli_and_does_not_mutate_old_trust(self):
        old = deepcopy(base.TRUST)
        awaiting = {'protocol': followup.TRUST_PROTOCOL, 'status': 'awaiting_reviewed_freeze', 'binding': None}
        with patch.object(followup, 'TRUST', awaiting), patch.object(base, 'inventory') as read, \
                patch.object(base, '_summary') as execute:
            with self.assertRaisesRegex(ValueError, 'reviewed_freeze_required'):
                followup.verified_projection('/not/read', '/not/read/either')
        read.assert_not_called(); execute.assert_not_called()
        self.assertEqual(old, base.TRUST)

    def test_trust_is_iteration_specific_and_never_accepts_the_old_native_ref(self):
        pins = {k: v for k, v in proof().items() if k in followup.PIN_KEYS}
        trust = {'protocol': followup.TRUST_PROTOCOL, 'status': 'reviewed', 'binding': pins}
        with patch.object(followup, 'TRUST', trust): self.assertEqual(pins, followup.trusted())
        for key in followup.REFS:
            bad = deepcopy(trust); bad['binding'][key] = 'a'*40
            with patch.object(followup, 'TRUST', bad), self.assertRaisesRegex(ValueError, 'wrong_iteration'):
                followup.trusted()
        previous = deepcopy(trust)
        previous['binding']['evaluator_ref'] = '63371da79ddfeb94d909a830e47052c41206e271'
        with patch.object(followup, 'TRUST', previous), self.assertRaisesRegex(ValueError, 'wrong_iteration'):
            followup.trusted()

    def test_all12_adverse_flags_usage_uncertainty_and_history_are_retained(self):
        native, judging = summaries(); before = deepcopy((native, judging))
        value = followup.project(native, judging, proof=proof())
        self.assertEqual(12, len(value['cells']))
        self.assertEqual(94, value['judging']['control_jobs'])
        self.assertEqual(182, value['judging']['max_logical_jobs'])
        self.assertEqual(546, value['judging']['request_ceiling'])
        self.assertEqual(1, value['judging']['phases']['profile']['flags']['supported']['false'])
        self.assertEqual(1, value['judging']['phases']['foreground']['flags']['answered']['false'])
        self.assertEqual(2, value['judging']['usage']['total_tokens']['unknown_attempts'])
        self.assertEqual(12, value['native']['checkin_capture_complete_cells'])
        self.assertEqual(followup.HISTORY, value['history'])
        self.assertEqual(4, len(value['history']))
        self.assertEqual('02e3bf552486adea209cc736e13e5a50e80335467c83136ff9d9e957b09e7d95', value['history'][-1]['sha256'])
        self.assertEqual(native['provider_attempts'], value['native']['provider_attempts'])
        self.assertEqual(base._usage(judging['usage']), value['judging']['usage'])  # History is never added to current costs.
        self.assertEqual(before, (native, judging))
        self.assertNotIn('PRIVATE', json.dumps(value))
        self.assertTrue(value['quality_ready'])  # Ready does not mean all flags true.

    def test_old_and_new_schemas_and_denominators_cannot_cross_qualify(self):
        with self.assertRaises(ValueError): followup.validate_public(legacy.projected())
        with self.assertRaises(ValueError): base.validate_public(projected())
        for key, bad in (('control_jobs', 70), ('max_logical_jobs', 158), ('request_ceiling', 474)):
            value = projected(); value['judging'][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError): followup.validate_public(value)

    def test_host_record_counts_are_availability_not_synthetic_success(self):
        for change in ({'checkin_observed': None}, {'checkin_observed': 0},
                       {'checkin_projectable_records': 3}, {'checkin_capture_complete': False}):
            value = projected(); value['cells'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError): followup.validate_public(value)
        value = projected(); value['cells'][0].update(checkin_observed=0, checkin_projectable_records=0)
        followup.validate_public(value)
        self.assertNotIn('successful_operations', json.dumps(value))

    def test_incomplete_native_horizon_is_unavailable_and_cannot_gain_quality_ready(self):
        native, judging = summaries(); row = native['cells'][0]
        row.update(status='incomplete', horizon_complete=False, capture_complete=False, profile_available=False,
            checkin_capture_complete=False, checkin_observed=None, checkin_projectable_records=0,
            original_outcome=None, observed_tick_sends=None, send_observation='unavailable',
            required_window_outcome='unavailable')
        judging.update(quality_ready=False, primary={p: [] for p in base.PHASES},
            consistency={p: {'paired_packets': 0, 'same_flags': 0} for p in base.PHASES})
        value = followup.project(native, judging, proof=proof())
        self.assertEqual(1, value['native']['required_windows']['unavailable'])
        self.assertIsNone(value['cells'][0]['original_outcome'])
        value.update(quality_ready=True, status='qualified')
        with self.assertRaisesRegex(ValueError, 'invalid_readiness'): followup.validate_public(value)

    def test_valid_failed_and_partial_controls_remain_visible_without_candidate_scores(self):
        native, judging = summaries()
        judging.update(quality_ready=False, logical_jobs=144, valid_jobs=94, started_attempts=94,
            technical_errors=0, interrupted_attempts=0, valid_controls=94, matched_controls=93, failed_controls=1,
            candidate_jobs={'planned': 50, 'started': 0, 'valid': 0}, controls_qualified=False,
            calibration_status='failed_valid_final', usage=[None]*94,
            primary={p: [] for p in base.PHASES}, consistency={p: {'paired_packets': 0, 'same_flags': 0} for p in base.PHASES})
        value = followup.project(native, judging, proof=proof())
        self.assertEqual(1, value['judging']['failed_controls'])
        self.assertEqual(0, value['judging']['phases']['profile']['primary_units'])
        self.assertIsNone(value['judging']['usage']['total_tokens']['observed_tokens'])
        judging.update(valid_jobs=10, started_attempts=10, valid_controls=10, matched_controls=9,
                       calibration_status='pending', usage=[None]*10)
        partial = followup.project(native, judging, proof=proof())
        self.assertEqual('pending', partial['judging']['calibration_status'])
        self.assertEqual(1, partial['judging']['failed_controls'])

    def test_private_fields_and_history_changes_are_rejected(self):
        for edit in (lambda v:v['cells'][0].update(user_id='PRIVATE'),
                     lambda v:v['proof'].update(private_file_map={}),
                     lambda v:v['history'][0].update(sha256='a'*64),
                     lambda v:v['evidence_contract'].update(model_promise_is_operation_proof=0)):
            value = projected(); edit(value)
            with self.assertRaises(ValueError): followup.validate_public(value)


class Accounting(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();(self.root/'receipts').mkdir()
        for name, source in legacy.predicate_sources().items():
            p=self.root/'source'/base.PREFIX/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(source)
        self.controls=[]
        for phase, count in followup.CONTROL_COUNTS.items():
            field={'foreground':'answered','proactive':'warranted','profile':'coverage'}[phase]
            self.controls += [{'id':phase+str(i),'phase':phase,'expect':{field:True}} for i in range(count)]
        (self.root/'controls.json').write_text(json.dumps(self.controls))
        self.binding={'valid_verdict_final':True,'control_failed_valid_final':True,'calibrate_before_candidates':True,
            'jobs':[{'id':r['id']+'.p'+str(p),'packet':r['id'],'pass':p,'control':True}
                    for r in self.controls for p in (1,2)]}
        self.binding['jobs'] += [{'id':'candidate.p'+str(p),'packet':'candidate','pass':p,'control':False} for p in (1,2)]

    def write(self, job, attempt, result):
        stem=self.root/'receipts'/(job+'.a'+str(attempt))
        Path(str(stem)+'.started.json').write_text('{}')
        if result is not None:Path(str(stem)+'.json').write_text(json.dumps(result))

    def fill_controls(self, fail=False):
        for i,job in enumerate(self.binding['jobs'][:94]):
            control=next(r for r in self.controls if r['id']==job['packet'])
            verdict={k: not v if fail and i==0 else v for k,v in control['expect'].items()}
            self.write(job['id'],1,{'status':'ok','verdict':verdict,'usage':{'total_tokens':3}})

    def test_all94_with_final_failure_are_not_treated_as_technical_errors(self):
        self.fill_controls(fail=True)
        result=followup._accounting(self.root,self.binding,{'started_attempts':94,'valid_jobs':94,'controls_qualified':False})
        self.assertEqual((94,93,1,0),(result['valid_controls'],result['matched_controls'],result['failed_controls'],result['technical_errors']))
        self.assertEqual({'planned':2,'started':0,'valid':0},result['candidate_jobs'])
        self.assertEqual('failed_valid_final',result['calibration_status'])

    def test_technical_and_missing_receipts_keep_unknown_usage_and_original_attempts(self):
        self.fill_controls()
        self.write('candidate.p1',1,{'status':'error','usage':None})
        self.write('candidate.p1',2,{'status':'ok','verdict':{},'usage':{'total_tokens':4}})
        self.write('candidate.p2',1,None)
        result=followup._accounting(self.root,self.binding,{'started_attempts':97,'valid_jobs':95,'controls_qualified':True})
        self.assertEqual((1,1),(result['technical_errors'],result['interrupted_attempts']))
        self.assertEqual({'planned':2,'started':2,'valid':1},result['candidate_jobs'])
        self.assertEqual(2,base._usage(result['usage'])['total_tokens']['unknown_attempts'])
        self.write('candidate.p1',3,{'status':'ok','verdict':{},'usage':None})
        with self.assertRaisesRegex(ValueError,'valid_verdict_replaced'):
            followup._accounting(self.root,self.binding,{'started_attempts':98,'valid_jobs':95,'controls_qualified':True})


class PreSummaryGate(unittest.TestCase):
    """Synthetic metadata closure only; mocks do not qualify a native pipeline."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.study=Path(self.tmp.name).resolve()/'native';self.judge=Path(self.tmp.name).resolve()/'judge'
        for root in (self.study,self.judge):
            for name in ('m6_profile_pilot.py','m6_profile_capture.py','runner.py','judge.py','metrics.py','m6_profile_judge.py'):
                p=root/'source'/base.PREFIX/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('')
            for name in ('serve/line_agent_v3/checkins.py','serve/memory/durable_profile.py'):
                p=root/'source'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('')
        p=self.judge/'source'/base.PREFIX/'m6_foreground_rubric.md';p.write_text('')
        self.schedule=[{'slot':s+'.'+a,'case':s,'account':a} for s in base.SCENARIOS for a in base.ACCOUNTS]
        plan={'native_ref':followup.REFS['native_ref'],'source_ref':followup.REFS['helper_ref'],'schedule':self.schedule}
        cases=[{'id':s,'expect':{} if s=='PV42' else {'foreground':{}}} for s in base.SCENARIOS]
        for name,value in (('plan.json',plan),('cases.json',cases)):(self.study/name).write_text(json.dumps(value))
        (self.judge/'inputs').mkdir()
        original={}
        for name in ('plan.json','cases.json'):
            raw=(self.study/name).read_bytes();original[name]=base.sha(raw);(self.judge/'inputs'/name).write_bytes(raw)
        binding={'protocol':followup.JUDGE_PROTOCOL,'native_source_ref':followup.REFS['native_ref'],
            'helper_ref':followup.REFS['helper_ref'],'evaluator_source_ref':followup.REFS['evaluator_ref'],
            'native_plan_sha256':base.sha((self.study/'plan.json').read_bytes()),'original_study':str(self.study),
            'original_input_files':original,'passes':2,'primary_pass':1,'max_attempts_per_job':3,
            'judge_model':'gpt-6-sol','reasoning':'high','max_output_tokens':32768,'timeout_s':120,'store':False,
            'controls':47,'control_counts':followup.CONTROL_COUNTS,'max_logical_jobs':182,'max_provider_calls':546,
            'jobs':[{'id':'control'+str(i),'control':True} for i in range(94)]}
        (self.judge/'binding.json').write_text(json.dumps(binding))
        self.pins={**followup.REFS,'plan_sha256':base.sha((self.study/'plan.json').read_bytes()),
            'judge_binding_sha256':base.sha((self.judge/'binding.json').read_bytes()),
            'native_files_sha256':base.digest(base.inventory(self.study)),
            'judge_files_sha256':base.digest(base.inventory(self.judge)),
            'native_seal_sha256':'d'*64,'judge_seal_sha256':'e'*64}
        self.trust={'protocol':followup.TRUST_PROTOCOL,'status':'reviewed','binding':self.pins}

    def test_unpinned_extra_or_changed_source_refuses_before_summary(self):
        for root in (self.study,self.judge):
            p=root/'source'/'shadow.py';p.write_text('raise RuntimeError("must not run")')
            with patch.object(followup,'TRUST',self.trust),patch.object(base,'_summary') as execute:
                with self.assertRaisesRegex(ValueError,'untrusted_inventory'):
                    followup.verified_projection(self.study,self.judge)
            execute.assert_not_called();p.unlink()
        rubric=self.judge/'source'/base.PREFIX/'m6_foreground_rubric.md';rubric.unlink()
        self.pins['judge_files_sha256']=base.digest(base.inventory(self.judge))
        with patch.object(followup,'TRUST',self.trust),patch.object(base,'_summary') as execute:
            with self.assertRaisesRegex(ValueError,'incomplete_foreground_rubric_source'):
                followup.verified_projection(self.study,self.judge)
        execute.assert_not_called()

    def test_old70_control_contract_refuses_before_summary_even_when_externally_pinned(self):
        p=self.judge/'binding.json';binding=json.loads(p.read_text());binding['controls']=35;p.write_text(json.dumps(binding))
        self.pins.update(judge_binding_sha256=base.sha(p.read_bytes()),judge_files_sha256=base.digest(base.inventory(self.judge)))
        with patch.object(followup,'TRUST',self.trust),patch.object(base,'_summary') as execute:
            with self.assertRaisesRegex(ValueError,'judge_contract_changed'):
                followup.verified_projection(self.study,self.judge)
        execute.assert_not_called()

    def test_foreground_origin_is_checked_against_original_cases_before_native_scoring(self):
        available={r['slot']:{'foreground_expectation_origin':'authored'} for r in self.schedule}
        summaries=[{'protocol':followup.NATIVE_PROTOCOL,'planned_cells':12},
            {'protocol':followup.JUDGE_PROTOCOL,'planned_cells':12,'control_jobs':94,'logical_jobs':94,'availability':available}]
        with patch.object(followup,'TRUST',self.trust),patch.object(base,'_summary',side_effect=summaries), \
                patch.object(base,'_native_outcomes') as score:
            with self.assertRaisesRegex(ValueError,'availability_changed'):
                followup.verified_projection(self.study,self.judge)
        score.assert_not_called()


class Panel(unittest.TestCase):
    def test_none_preserves_both_existing_pages_byte_for_byte(self):
        cases=json.loads((renderer.PUBLIC/renderer.CASES_NAME).read_text())
        self.assertEqual(renderer.render({'status':'pending'}),
                         renderer.render({'status':'pending'},m6_profile_capture_followup=None))
        self.assertEqual(renderer.render_method(cases),renderer.render_method(cases,m6_profile_capture_followup=None))

    def test_pending_in_both_tabs_has_no_results_and_keeps_old_diagnostic(self):
        cases=json.loads((renderer.PUBLIC/renderer.CASES_NAME).read_text());old=legacy.projected();before=deepcopy(old)
        for page in (renderer.render({'status':'pending'},m6_profile_diagnostic=old,m6_profile_capture_followup=followup.pending_projection()),
                     renderer.render_method(cases,m6_profile_diagnostic=old,m6_profile_capture_followup=followup.pending_projection())):
            new=page.split('<h2>側寫與關心：',1)[1].split('</section>',1)[0]
            self.assertIn('目前沒有本輪成績',new)
            self.assertIn('回應涵蓋',new)
            self.assertIn('不代表操作成功',new)
            self.assertIn('J7 校準符合預期 93/94',new)
            self.assertIn('245,667 tokens',new)
            self.assertNotIn('有效控制 94/94',new)
            self.assertIn('較早的側寫診斷、限制與原始判讀',page)
            self.assertIn('評審無法據此核對操作結果',page)
            self.assertNotIn('<style',new)
        self.assertEqual(before,old)

    def test_measured_panel_keeps_negative_flags_94_controls_history_and_unknown_components(self):
        value=projected();page=renderer.m6_capture_panel(value)
        for text in ('有效控制 94/94','負面 1','reasoning_tokens 已知 未回報','未知 2 次',
                     '不能歸因於單一修正','並不表示所有品質旗標通過','模型承諾本身不當成操作成功',
                     '回應涵蓋 11/12','不代表操作成功','J7 校準符合預期 93/94','候選判讀 0 次',
                     '245,667 tokens','原生用量不重複加總'):
            self.assertIn(text,page)
        for row in followup.HISTORY:self.assertIn(row['file'],page)
        for label in ('時機','有用','語氣','不打擾','決定進展'):self.assertIn('<th>'+label+'</th>',page)
        self.assertEqual(5,page.count('1 / 5（N=1）'))
        value['judging']['phases']['proactive']['scores']['decision_progress']={'sum':0,'applicable':0}
        unrated=renderer.m6_capture_panel(value)
        self.assertIn('<th>決定進展</th><td>未判讀／不適用</td>',unrated)
        self.assertNotIn('0/0',unrated);self.assertNotIn('0 / 0',unrated)
        for s in base.SCENARIOS:
            for a in base.ACCOUNTS:self.assertIn(s+' · '+a,page)
        self.assertNotIn('PRIVATE',page)

    def test_explicit_ci_selection_includes_new_module_once(self):
        root=Path(__file__).resolve().parents[1]
        for name in ('always-on-review.yml','deploy.yml'):
            source=(root/'.github/workflows'/name).read_text()
            line=next(l for l in source.splitlines() if 'python3 -B -m unittest scripts/test_line_always_on.py' in l)
            self.assertEqual(1,line.count('scripts/test_m6_profile_capture_followup.py'))
