"""Schema-2 publication gates and deterministic pages; synthetic fixtures stay in tests."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import hashlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('always_on', HERE/'render-line-always-on.py')
always_on = importlib.util.module_from_spec(spec)
spec.loader.exec_module(always_on)


def verdict(**changes):
    value={'warranted':True,'timing':4,'useful':4,'tone':5,'not_annoying':4,'grounded':True,'private':True,
           'decision_progress':None,'reason':'只提對話裡的事情。','grounding_issues':['none']}
    return dict(value,**changes)


def fixture():
    episodes=[{'id':'PV01','scope':'private','feature':'P1','polarity':'positive','title':'週六爬山',
               'tests':'出發前關心一次。','timezone':'Asia/Taipei','turns':[{'at':'2026-10-14T19:00:00+08:00','from':'user','text':'週六去爬山 <script>'}],
               'expect':{'proactive':{'min':1,'max':1,'windows':[]},'horizon':'2026-10-20T00:00:00+08:00'}}]
    rate={'hits':2,'total':2,'rate':1.0}
    arms={arm:{'recall':dict(rate),'negative_silence':{'hits':0,'total':0,'rate':None},
               'judge':{'timing':4,'useful':4,'tone':5,'not_annoying':4,'decision_progress':None,'appropriate':dict(rate)},
               'foreground':{'first_reply_ms':{'p50':5200,'p90':9300,'n':2}},'unmeasured':{'runs':0}} for arm in always_on.ARMS}
    controls={'judgments':2,'as_expected':2,'items':[{'id':'C01','judged':[{'pass':i,'as_expected':True,'verdict':verdict()} for i in (1,2)]}]}
    judge={'passes':2,'missing_judgments':0,'packet_count':2,'control_count':1,'model':'test-only-model','calibration_only':False,
           'rubric_sha256':'e'*64,'judge_sha256':'f'*64,'packets_sha256':'0'*64,'consistency':{'warranted':1.0}}
    runs=[{'episode_id':'PV01','arm':arm,'repeat':repeat,'replies':[{'at':'2026-10-14T19:00:06+08:00','text':'收到！'}],
           'proactive':[{'at':'2026-10-16T19:00:00+08:00','text':'裝備整理好了沒～','role':'unsolicited','lane':'proactive','verdict':verdict()}] if arm=='engine' else [],
           'turns':[],'checks':{'count_ok':True,'window_hit':True}} for arm in always_on.ARMS for repeat in range(2)]
    return {'schema_version':2,'complete':True,'replay_complete':True,'judging_complete':True,'publication_ready':True,'incomplete_episodes':[],
            'refs':{'existing':'a'*40,'engine':'b'*40},'models':{'foreground':'test-only-model','judge':{'model':'test-only-judge'}},
            'metadata':{'smoke':False,'executor':True,'repeats':2,'episode_count':1,'slot_count':4,
                        'host_notices':{arm:{'count':1,'sha256':'c'*64} for arm in always_on.ARMS},
                        'degraded_untagged':{arm:0 for arm in always_on.ARMS},'judge':deepcopy(judge),'judge_foreground':deepcopy(judge)},
            'episodes':episodes,'runs':runs,'summary':arms,'comparison':{'clusters':1,'recall_difference':0,'recall_difference_ci95':[-1,1]},
            'gates':{arm:{'decisions':{'suppressed':1},'by_gate':{'suppressed':{'quiet_hours':1}}} for arm in always_on.ARMS},
            'foreground_judge':{arm:{'judged':2,**{key:dict(rate) for key in ('answered','no_rejection','honest','grounded','alternatives')}} for arm in always_on.ARMS},
            'judge_controls':deepcopy(controls),'foreground_controls':deepcopy(controls),'slot_status':{arm+':measured':2 for arm in always_on.ARMS}}


def variant_fixture():
    data=fixture()
    data.update(schema_version=3,arms=list(always_on.VARIANT_ARMS))
    data['refs'].update({arm:data['refs']['engine'] for arm in always_on.VARIANT_ARMS[1:]})
    mapping={arm:'existing' if arm=='existing' else 'engine' for arm in always_on.VARIANT_ARMS}
    for field in ('summary','gates','foreground_judge'):
        old=data[field]
        data[field]={arm:deepcopy(old[source]) for arm,source in mapping.items()}
    old=data['runs']
    data['runs']=[dict(deepcopy(row),arm=arm) for arm,source in mapping.items()
                  for row in old if row['arm']==source]
    configs={'existing':{'always_on':None}}
    for arm,provider,model,level in (('engine_medium','gemini','gemini-3.8-flash','medium'),
            ('engine_high','gemini','gemini-3.8-flash','high'),('engine_sol_low','openai','gpt-6.1-sol','low')):
        configs[arm]={'always_on':{'provider':provider,'model':model,'thinking_level':level,
                                  'max_output_tokens':32768,'timeout_s':120}}
    meta=data['metadata']
    meta.update(arms=data['arms'],arm_configs=configs,configuration_sha256='d'*64,source_by_arm=mapping,slot_count=8)
    capture={'capture_complete':True,'attempts':1,'request_sent_attempts':1,'failed_attempts':0,
             'invalid_output_attempts':0,'outcomes':{'ok':1},'elapsed_ms':{'p50':1000,'p90':1000,'n':1},
             'token_usage':{'total_tokens':{'known_tokens':100,'known_attempts':1,'unknown_attempts':0}},
             'by_lane':{},'by_provider':{},'usage_complete':True}
    meta['background_models']={arm:deepcopy(capture) for arm in data['arms']}
    meta['background_parameters_verified']={arm:True for arm in data['arms']}
    for field in ('host_notices','degraded_untagged'):
        old=meta[field]
        meta[field]={arm:deepcopy(old[source]) for arm,source in mapping.items()}
    meta['judge']['packet_count']=6
    meta['judge_foreground']['packet_count']=8
    data['slot_status']={arm+':measured':2 for arm in always_on.VARIANT_ARMS}
    pairs=[('existing',candidate) for candidate in always_on.VARIANT_ARMS[1:]]+[
        ('engine_medium','engine_high'),('engine_medium','engine_sol_low'),('engine_high','engine_sol_low')]
    comparison=data.pop('comparison')
    data['comparisons']={candidate+'_vs_'+baseline:dict(deepcopy(comparison),baseline=baseline,candidate=candidate)
                         for baseline,candidate in pairs}
    return data


def revision_fixture():
    attempts = {'attempts':10, 'ok':6, 'errors':4,
                'known_token_usage':{'input_tokens':200, 'output_tokens':40, 'total_tokens':240},
                'unknown_usage_attempts':4,
                'unknown_usage_components':{'input_tokens':4, 'output_tokens':4, 'total_tokens':4}}
    new = {'attempts':3, 'ok':2, 'errors':1,
           'known_token_usage':{'input_tokens':20, 'output_tokens':4, 'total_tokens':24},
           'unknown_usage_attempts':1,
           'unknown_usage_components':{'input_tokens':1, 'output_tokens':1, 'total_tokens':1}}
    phase = {'changed_units':1, 'reused_units':2, 'changed_judgments':2, 'reused_judgments':4,
             'message_units':2, 'control_units':1, 'reused_control_judgments':2,
             'effective_judgments_required':6, 'original_attempts':attempts, 'new_attempts':new}
    return {'protocol':always_on.EVALUATION_REVISION_PROTOCOL,
            'original_plan_sha256':'1'*64, 'original_capture_sha256':'2'*64,
            'corrected_eval_ref':'3'*40, 'corrected_code_sha256':'4'*64, 'manifest_sha256':'5'*64,
            'maximum_new_provider_calls':12, 'limits':'獨立開發評估；不是新一次模型重播或真人校準。',
            'phases':{name:deepcopy(phase) for name in ('proactive','foreground')}}


class RenderTest(unittest.TestCase):
    def test_four_arm_model_study_preserves_all_timelines_and_six_paired_comparisons(self):
        data=always_on.project(variant_fixture(),generated_at='2026-10-14')
        page=always_on.render(data)
        self.assertEqual(len(data['runs']),8)
        self.assertEqual(len(data['comparisons']),6)
        for arm in always_on.VARIANT_ARMS:
            self.assertIn('data-arm="'+always_on.ARM_LABELS[arm]+'"',page)
        self.assertIn('--arm-count:4',page)
        self.assertIn('GPT-6.1-Sol · Low − Gemini · High',page)
        self.assertEqual(data['summary']['engine_sol_low']['judge']['appropriate']['total'],2)

    def test_variant_names_cannot_substitute_for_complete_runs_or_actual_frozen_parameters(self):
        mutations=[lambda d:d['arms'].pop(),lambda d:d['runs'].pop(),
            lambda d:d['metadata']['arm_configs']['engine_high']['always_on'].update(thinking_level='medium'),
            lambda d:d['metadata']['arm_configs']['engine_sol_low']['always_on'].update(model='gpt-6-sol'),
            lambda d:d['metadata']['arm_configs']['engine_medium']['always_on'].update(max_output_tokens=4096),
            lambda d:d['metadata']['background_parameters_verified'].update(engine_sol_low=False),
            lambda d:d['metadata']['background_models']['engine_high'].update(capture_complete=False),
            lambda d:d['refs'].update(engine_sol_low='c'*40),
            lambda d:d['comparisons'].pop('engine_sol_low_vs_engine_high')]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                data=variant_fixture();mutate(data)
                with self.assertRaises(ValueError):always_on.project(data,generated_at='2026-10-14')

    def test_unreported_usage_remains_unknown_when_a_complete_capture_contains_provider_failures(self):
        data=variant_fixture()
        capture=data['metadata']['background_models']['engine_high']
        capture.update(failed_attempts=1,invalid_output_attempts=1,outcomes={'provider_invalid_output':1},usage_complete=False)
        capture['token_usage']['total_tokens']={'known_tokens':None,'known_attempts':0,'unknown_attempts':1}
        page=always_on.render(always_on.project(data,generated_at='2026-10-14'))
        self.assertIn('未回報 · 已知 0 次 / 未知 1 次',page)
        self.assertIn('未知不是零',page)

    def test_absolute_components_keep_zero_exposure_denominators_and_host_failures_visible(self):
        data=variant_fixture()
        runs=[row for row in data['runs'] if row['arm']=='engine_high']
        runs[0]['proactive'][0]['verdict']=verdict(grounded=False)
        runs[1]['proactive'][0]['verdict']=verdict(private=False,warranted=False)
        host=data['summary']['engine_high']
        host['foreground'].update(nomiss={'hits':1,'total':2,'rate':.5},
                                  fast={'hits':0,'total':2,'rate':0},
                                  fast_turns={'hits':2,'total':5,'rate':.4})
        host['redlines']={'total':5,'privacy':1,'quiet_hours':2,'duplicates':1,'over_count':1,'invented':1}
        page=always_on.absolute_component_table(always_on.project(data,generated_at='2026-10-14'))
        self.assertIn('0/0',page)
        self.assertIn('50.0% · 1/2',page)
        self.assertIn('0.0% · 0/2',page)
        self.assertIn('40.0% · 2/5',page)
        self.assertIn('主機／評審紅線總次數',page)
        self.assertIn('<td>5</td>',page)
        self.assertIn('無資料',page)

    def test_paired_recall_interval_and_lane_exposure_show_consistent_units(self):
        data=variant_fixture()
        comparison=next(iter(data['comparisons'].values()))
        comparison.update(recall_difference=.1,recall_difference_ci95=[-.2,.3])
        self.assertIn('-20.0 個百分點 至 +30.0 個百分點',always_on.paired_comparisons(data))
        data['metadata']['background_models']['engine_medium']['by_lane']={
            'composer':{'request_sent_attempts':1,'attempts':2,'failed_attempts':1}}
        self.assertIn('1/2 次已送出／嘗試',always_on.background_model_panel(data))

    def test_evidence_is_scoped_to_each_reply_and_background_send_and_escaped(self):
        data=fixture()
        run=next(row for row in data['runs'] if row['proactive'])
        evidence=[{'time':'2026-10-14 12:00','kind':'公開查詢結果','text':'可見來源 <script>限定本則</script>'}]
        run['proactive'][0]['tool_evidence']=deepcopy(evidence)
        page=always_on.timeline(data['episodes'][0],run)
        self.assertEqual(page.count('本則回答可見的工具證據'),1)
        self.assertIn('&lt;script&gt;限定本則&lt;/script&gt;',page)
        self.assertNotIn('<script>限定本則',page)
        reply={'at':'2026-10-14T12:00:00+08:00','text':'已查到','tool_evidence':deepcopy(evidence)}
        run['replies']=[reply]
        self.assertEqual(always_on.timeline(data['episodes'][0],run).count('本則回答可見的工具證據'),2)
        reply['tool_evidence'][0]['source_session_id']='private-authority'
        with self.assertRaises(ValueError):always_on.timeline(data['episodes'][0],run)

    def test_projects_actual_schema_and_escapes_case_text(self):
        projected=always_on.project(fixture(),generated_at='2026-10-14')
        self.assertIn('metadata',projected)
        self.assertNotIn('design',projected)
        page=always_on.render(projected)
        self.assertIn('&lt;script&gt;',page)
        self.assertNotIn('爬山 <script>',page)
        self.assertIn('麻吉 · 自主關心',page)
        self.assertIn('data-explorer',page)

    def test_composite_is_recomputed_and_privacy_cannot_be_offset_by_warmth(self):
        data=fixture()
        for run in data['runs']:
            for message in run['proactive']:message['verdict']=verdict(private=False,tone=5)
        projected=always_on.project(data,generated_at='2026-10-14')
        self.assertEqual(projected['summary']['engine']['judge']['appropriate'],{'hits':0,'total':2,'rate':0})
        self.assertEqual(projected['summary']['existing']['judge']['appropriate']['total'],0)

    def test_complete_flags_do_not_override_missing_evidence(self):
        mutations=[lambda d:d.update(publication_ready=False),lambda d:d.update(replay_complete=False),
                   lambda d:d['metadata'].update(smoke=True),lambda d:d['metadata'].update(executor=False),
                   lambda d:d['runs'].pop(),lambda d:d['runs'].append(deepcopy(d['runs'][0])),
                   lambda d:d['slot_status'].update({'engine:pending':1}),
                   lambda d:d['metadata']['host_notices']['engine'].update(count=0),
                   lambda d:d['metadata']['degraded_untagged'].update(engine=1),
                   lambda d:d['summary']['engine']['unmeasured'].update(runs=1),
                   lambda d:d['metadata']['judge'].update(missing_judgments=1),
                   lambda d:d['metadata']['judge_foreground'].update(passes=1),
                   lambda d:d['metadata']['judge'].update(calibration_only=True),
                   lambda d:d['foreground_controls']['items'][0]['judged'][0].update(as_expected=False),
                   lambda d:d['judge_controls']['items'][0]['judged'].pop(),
                   lambda d:d.update(foreground_judge=None),
                   lambda d:next(r for r in d['runs'] if r['proactive'])['proactive'][0].update(verdict=None)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                data=fixture();mutate(data)
                with self.assertRaises(ValueError):always_on.project(data,generated_at='2026-10-14')

    def test_private_fields_and_nonfinite_values_are_rejected(self):
        for key,value in [('credentials','secret'),('path','/Users/private/study'),('count',float('nan'))]:
            data=fixture();data['metadata'][key]=value
            with self.assertRaises(ValueError):always_on.project(data,generated_at='2026-10-14')

    def test_a_complete_quiet_result_is_publishable_but_missing_judgments_are_not(self):
        data=fixture()
        for run in data['runs']:
            run['proactive']=[]
        data['metadata']['judge']['packet_count']=0
        self.assertEqual(always_on.project(data,generated_at='2026-10-14')['summary']['engine']['judge']['appropriate'],
                         {'hits':0,'total':0,'rate':None})
        data=fixture()
        data['metadata']['judge']['packet_count']=0
        with self.assertRaises(ValueError):always_on.project(data,generated_at='2026-10-14')

    def test_pending_page_contains_no_fixture_performance(self):
        page=always_on.render({'status':'pending'})
        self.assertIn('尚未有可發布',page)
        self.assertIn('等待完整量測',page)
        self.assertNotIn('100.0%',page)
        self.assertNotIn('test-only',page)

    def test_calibration_is_separate_from_engine_comparison(self):
        calibration=json.loads((always_on.PUBLIC/always_on.CALIBRATION_NAME).read_text())
        self.assertTrue(calibration['calibration_only'])
        self.assertFalse(calibration['engine_performance_evidence'])
        self.assertEqual([phase['as_expected'] for phase in calibration['phases']],[20,22])
        with self.assertRaises(ValueError):always_on.project(calibration,generated_at='2026-10-14')
        with self.assertRaises(ValueError):always_on.calibration_panel(dict(calibration,engine_performance_evidence=True))
        page=always_on.render({'status':'pending','judge_calibration':calibration})
        self.assertIn('沒有測量主動引擎的效能',page)
        self.assertIn('完整題組的分數、改善幅度與勝負結論仍待完成',page)

    def test_published_protocol_digest_covers_its_immutable_cases(self):
        import hashlib
        cases=json.loads((always_on.PUBLIC/always_on.CASES_NAME).read_text())
        protocol=json.loads((always_on.PUBLIC/cases['protocol_file']).read_text())
        canonical=json.dumps(protocol,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(),cases['protocol_sha256'])
        self.assertEqual(protocol['cases']['episodes'],cases['episodes'])
        self.assertNotIn('protocol_file',protocol['cases'])

    def test_method_has_blinding_controls_and_explicit_development_limits(self):
        source={'episodes':fixture()['episodes']}
        cases=always_on.public_cases(source,'a'*40,'b'*64)
        page=always_on.render_method(cases)
        for text in ('教學示意','不是人類偏好證據','第 1 次','holdout','沒有量測出的麻吉回答','data-clock'):
            self.assertIn(text,page)
        self.assertNotIn('test-only',page)

    def test_public_cases_keep_the_full_synthetic_foreground_and_privacy_oracle(self):
        episode=fixture()['episodes'][0]
        episode['expect'].update(foreground={'recap':{'decided':['加入後重述的日期'],'open':[]}},
                                 forbidden_mentions=['加入前的四人房'])
        cases=always_on.public_cases({'episodes':[episode]},'a'*40,'b'*64)
        self.assertEqual(cases['episodes'][0]['expect'],episode['expect'])
        self.assertIn('完整預先指定的檢查',always_on.render_method(cases))

    def test_control_additions_change_the_frozen_count_and_method_copy(self):
        source="CONTROLS=[{'id':'C01'}]\nFOREGROUND_CONTROLS=[{'id':'FC01'}]\nFOREGROUND_CONTROLS += [{'id':'FC02'}]\n"
        counts=always_on.literal_control_counts(source)
        self.assertEqual(counts,{'CONTROLS':1,'FOREGROUND_CONTROLS':2})
        cases=always_on.public_cases({'episodes':fixture()['episodes']},'a'*40,'b'*64)
        cases['control_counts']=counts
        self.assertIn('1 題訊息控制、2 題前景控制，兩次共 6 次',always_on.render_method(cases))
        with self.assertRaises(ValueError):
            always_on.literal_control_counts(source+"FOREGROUND_CONTROLS += [{'id':'FC02'}]\n")

    def test_protocol_source_must_match_an_actual_committed_revision(self):
        import hashlib
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            def git(*args):
                return subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,check=True).stdout.strip()
            git('init','-q')
            (root/'cases.json').write_text('{"episodes":[]}\n')
            git('add','cases.json')
            git('-c','user.name=Benchmark test','-c','user.email=benchmark@example.invalid','commit','-qm','fixture')
            protocol={'source_ref':git('rev-parse','HEAD'),'files_sha256':{
                'cases.json':hashlib.sha256((root/'cases.json').read_bytes()).hexdigest()}}
            always_on.verify_committed_protocol(protocol,root)
            with self.assertRaises(ValueError):always_on.verify_committed_protocol(dict(protocol,source_ref='0'*40),root)
            protocol['files_sha256']['cases.json']=hashlib.sha256(b'changed').hexdigest()
            with self.assertRaises(ValueError):always_on.verify_committed_protocol(protocol,root)

    def test_new_tabs_share_the_layout_asset(self):
        for page in (always_on.render({'status':'pending'}),always_on.render_method(always_on.public_cases({'episodes':fixture()['episodes']},'a'*40,'b'*64))):
            self.assertIn('report-layout.css',page)
            self.assertIn('benchmark-page',page)
            self.assertNotIn('max-width:1450px',page)

    def test_committed_pages_reproduce(self):
        public=always_on.PUBLIC
        data=json.loads((public/always_on.JSON_NAME).read_text())
        cases=json.loads((public/always_on.CASES_NAME).read_text())
        index=json.loads((public/always_on.ITERATIONS_NAME).read_text())
        self.assertEqual(always_on.render(data,index['iterations']),(public/always_on.PAGE_NAME).read_text())
        self.assertEqual(always_on.render_method(cases,has_results=data.get('publication_ready') is True,
            diagnostic=data.get('owed_diagnostic'),planned_study=data.get('planned_study'),
            interruption=data.get('study_interruption'),owed_development=data.get('owed_development'),
            owed_development_host_interruption=data.get('owed_development_host_interruption'),
            generated_at=data.get('generated_at','2026-10-14')),(public/always_on.METHOD_NAME).read_text())


class EvaluationRevisionPublicationTest(unittest.TestCase):
    def capture(self, directory, messages):
        root = Path(directory)
        (root/'receipts').mkdir()
        (root/'plan.json').write_text(json.dumps({'execution_order':[{'slot':'GR01.engine.r0'}]}))
        (root/'receipts/GR01.engine.r0.json').write_text(json.dumps({'sends':[{'messages':messages}]}))
        return root

    def test_original_text_v2_capture_cannot_be_qualified_by_old_summary_or_metadata_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.capture(directory, [{'type':'textV2','text':'{member} 記得喝水',
                                             'substitution':{'member':{'type':'mention','mentionee':{'type':'user'}}}}])
            (root/'results.json').write_text(json.dumps({'publication_ready':True,
                'metadata':{'evaluation_revision':{'verified':True}}}))
            with mock.patch('subprocess.run') as invoke:
                with self.assertRaisesRegex(ValueError, 'evaluation_revision_required_for_text_v2'):
                    always_on.verify_study_capture(root)
            invoke.assert_not_called()

    def test_detection_uses_wire_message_type_and_retains_legacy_text_fallback(self):
        for messages in ([{'type':'text','text':'討論 textV2 名稱'}], None, []):
            with self.subTest(messages=messages), tempfile.TemporaryDirectory() as directory:
                self.assertFalse(always_on.capture_contains_text_v2(self.capture(directory, messages)))

    def test_capture_symlink_is_refused_before_any_evaluator_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.capture(directory, [])
            (root/'plan-original.json').write_bytes((root/'plan.json').read_bytes())
            (root/'plan.json').unlink()
            (root/'plan.json').symlink_to('plan-original.json')
            with mock.patch('subprocess.run') as invoke:
                with self.assertRaisesRegex(ValueError, 'symlink_publication_capture'):
                    always_on.verify_study_capture(root)
            invoke.assert_not_called()

    def test_revision_disclosure_separates_actual_attempts_from_effective_reused_judgments(self):
        data = fixture()
        data['metadata']['evaluation_revision'] = revision_fixture()
        page = always_on.render(always_on.project(data, generated_at='2026-10-16'))
        self.assertIn('有效判讀共 12 次：更正 4 次、重用 8 次', page)
        self.assertIn('原始評審實際保留 20 次嘗試，其中 8 次錯誤', page)
        self.assertIn('更正後新增', page)
        self.assertIn('未知用量不補成零', page)
        self.assertIn('主統計仍固定取第一次判讀', page)
        self.assertIn('input／output／total 未知次數', page)
        self.assertIn('更正評估來源', page)
        for changed in (lambda r:r.update(original_study='/Users/private/source'),
                        lambda r:r['phases']['foreground'].update(reused_judgments=2),
                        lambda r:r['phases']['proactive']['new_attempts'].update(unknown_usage_attempts=4),
                        lambda r:r['phases']['foreground'].update(message_units=3),
                        lambda r:r.update(maximum_new_provider_calls=100)):
            with self.subTest(mutation=changed):
                bad = deepcopy(data); changed(bad['metadata']['evaluation_revision'])
                with self.assertRaises(ValueError): always_on.project(bad, generated_at='2026-10-16')

    def revision_archive(self, directory):
        """A committed fixture evaluator, a real immutable copy, and a tiny CLI."""
        root = Path(directory).resolve()
        original, revision, source = (root/name for name in ('original','revision','normal-git'))
        for path in (original/'harness', original/'source/engine/serve', original/'receipts',
                     original/'judge/foreground', source, revision/'harness'):
            path.mkdir(parents=True)
        (original/'harness/runner.py').write_text("raise AssertionError('original evaluator must not execute')\n")
        (original/'source/engine/serve/__init__.py').write_text('')
        (original/'judge/quality.json').write_text('{}\n')
        (original/'judge/foreground/quality.json').write_text('{}\n')
        (original/'receipts/GR01.engine.r0.json').write_text(json.dumps({'sends':[
            {'messages':[{'type':'textV2','text':'{member} 喝水'}]}]}))
        sha = lambda data:hashlib.sha256(data).hexdigest()
        digest = lambda value:sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
            separators=(',',':'), allow_nan=False).encode())
        plan = {'execution_order':[{'slot':'GR01.engine.r0'}], 'refs':fixture()['refs'],
                'files':{name:sha((original/name).read_bytes()) for name in (
                    'harness/runner.py','source/engine/serve/__init__.py')}}
        (original/'plan.json').write_text(json.dumps(plan))
        (original/'results.json').write_text('original-results-remain-unchanged\n')
        code = {'__init__.py':'', 'cases.json':'{}\n', 'evaluation_revision.py':'# committed fixture closure\n',
                'runner.py':'''HARNESS_FILES = ('__init__.py', 'runner.py', 'cases.json')
if __name__ == '__main__':
 import argparse,json
 from pathlib import Path
 p=argparse.ArgumentParser();p.add_argument('command',choices=['summary']);p.add_argument('--out',required=True);p.add_argument('--evaluation-revision',required=True)
 a=p.parse_args();r=Path(a.evaluation_revision)
 (r/'cli-arguments.private.json').write_text(json.dumps({'command':a.command,'out':a.out,'revision':a.evaluation_revision}))
 (r/'results.json').write_bytes((r/'fixture-result.private.json').read_bytes())
'''}
        for name, text in code.items():
            path = source/always_on.EVALUATION_PREFIX/name
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            (revision/'harness'/name).write_text(text)
        def git(*args):
            return subprocess.check_output(['git','-c','core.hooksPath=/dev/null','-C',str(source),*args],
                stderr=subprocess.DEVNULL)
        git('-c','init.templateDir=','init','-q')
        git('add','serve')
        git('-c','user.name=Offline fixture','-c','user.email=fixture@example.invalid',
            '-c','commit.gpgsign=false','commit','-qm','fixture evaluator')
        ref = git('rev-parse','HEAD').decode().strip()
        inputs = {path.relative_to(original).as_posix():sha(path.read_bytes())
                  for path in original.rglob('*') if path.is_file() and path.name!='results.json'}
        for name in inputs:
            target = revision/'inputs/study'/name
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original/name,target)
        code_files = {name:sha(text.encode()) for name,text in code.items()}
        plan_sha = sha((original/'plan.json').read_bytes())
        capture_sha = digest({'plan_sha256':plan_sha,
                             'receipts_sha256':{'GR01.engine.r0':inputs['receipts/GR01.engine.r0.json']}})
        manifest = {'protocol':always_on.EVALUATION_REVISION_PROTOCOL,'corrected_eval_ref':ref,
                    'code_files':code_files,'input_files':inputs,'original_study':str(original),
                    'original_plan_sha256':plan_sha,'original_capture_sha256':capture_sha,
                    'passes':2,'max_attempts_per_changed_judgment':3,'maximum_new_provider_calls':12}
        (revision/'manifest.private.json').write_text(json.dumps(manifest))
        (revision/'manifest.sha256.json').write_text(json.dumps({'sha256':digest(manifest)}))
        metadata = revision_fixture()
        metadata.update(original_plan_sha256=plan_sha,original_capture_sha256=capture_sha,
            corrected_eval_ref=ref,corrected_code_sha256=digest(code_files),manifest_sha256=digest(manifest))
        results = fixture();results['metadata']['evaluation_revision']=metadata
        (revision/'fixture-result.private.json').write_text(json.dumps(results))
        return original, revision, source, ref, manifest

    def test_approved_revision_runs_the_dedicated_cli_and_preserves_original_results(self):
        with tempfile.TemporaryDirectory() as directory:
            original, revision, source, ref, _ = self.revision_archive(directory)
            old = (original/'results.json').read_bytes()
            result = always_on.verify_study_capture(original,evaluation_revision=revision,
                evaluator_ref=ref,evaluator_source=source)
            self.assertEqual(result,(revision/'results.json').read_bytes())
            self.assertEqual((original/'results.json').read_bytes(),old)
            self.assertEqual(json.loads((revision/'cli-arguments.private.json').read_text()),
                {'command':'summary','out':str(original),'revision':str(revision)})
            projected = always_on.project(json.loads(result),generated_at='2026-10-16')
            self.assertEqual(projected['refs'],fixture()['refs'])
            self.assertNotIn(str(original),json.dumps(projected))
            self.assertNotIn(str(source),json.dumps(projected))

    def test_revision_requires_explicit_git_pin_and_refuses_self_rehashed_foreign_closure(self):
        for fault in ('missing-pin','wrong-ref','foreign-code','added-pyc','changed-mode','changed-input','symlink-code'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as directory:
                original, revision, source, ref, manifest = self.revision_archive(directory)
                selected = None if fault=='missing-pin' else 'f'*40 if fault=='wrong-ref' else ref
                if fault=='foreign-code':
                    (revision/'harness/runner.py').write_text("raise AssertionError('untrusted')\n")
                    manifest['code_files']['runner.py']=hashlib.sha256((revision/'harness/runner.py').read_bytes()).hexdigest()
                    (revision/'manifest.private.json').write_text(json.dumps(manifest))
                    sha=hashlib.sha256(json.dumps(manifest,ensure_ascii=False,sort_keys=True,
                        separators=(',',':'),allow_nan=False).encode()).hexdigest()
                    (revision/'manifest.sha256.json').write_text(json.dumps({'sha256':sha}))
                elif fault=='added-pyc':(revision/'harness/runner.pyc').write_bytes(b'unbound')
                elif fault=='changed-mode':(revision/'harness/runner.py').chmod(0o755)
                elif fault=='changed-input':(revision/'inputs/study/receipts/GR01.engine.r0.json').write_text('{}')
                elif fault=='symlink-code':
                    (revision/'harness/runner.py').unlink()
                    (revision/'harness/runner.py').symlink_to(source/always_on.EVALUATION_PREFIX/'runner.py')
                with self.assertRaises(ValueError):
                    always_on.verify_study_capture(original,evaluation_revision=revision,
                        evaluator_ref=selected,evaluator_source=source)
                self.assertFalse((revision/'cli-arguments.private.json').exists())

    def test_revision_output_must_pass_gate_and_match_verified_provenance(self):
        for fault in ('unqualified','forged-provenance'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as directory:
                original, revision, source, ref, _ = self.revision_archive(directory)
                path=revision/'fixture-result.private.json';value=json.loads(path.read_text())
                if fault=='unqualified': value['publication_ready']=False
                else: value['metadata']['evaluation_revision']['original_capture_sha256']='f'*64
                path.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError,'evaluation_revision_result_binding_mismatch'):
                    always_on.verify_study_capture(original,evaluation_revision=revision,
                        evaluator_ref=ref,evaluator_source=source)
                self.assertEqual((original/'results.json').read_text(),'original-results-remain-unchanged\n')


class OwedHostInterruptionTest(unittest.TestCase):
    def archive(self, directory):
        root=Path(directory)/'native';root.mkdir();(root/'receipts').mkdir()
        digest=always_on._owed_host_digest
        sha=lambda raw:hashlib.sha256(raw).hexdigest()
        configs={arm:{'provider':provider,'model':model,'thinking_level':level,
                      'max_output_tokens':32768,'timeout_s':120}
                 for arm,provider,model,level in (
                    ('engine_medium','gemini','gemini-3.8-flash','medium'),
                    ('engine_high','gemini','gemini-3.8-flash','high'),
                    ('engine_sol_low','openai','gpt-6.1-sol','low'))}
        order=[{'slot':f'cell{index:02d}','episode_id':f'OP{index//6+2:02d}',
                'arm':list(configs)[index%3],'account':('primary','secondary')[index%2],
                'kind':'positive' if index<48 else 'withhold'} for index in range(72)]
        plan={'source_ref':always_on.OWED_HOST_SOURCE_REF,'native_source_ref':always_on.OWED_HOST_NATIVE_REF,
              'planned_cells':72,'execution_order':order,'configurations':configs,
              'configuration_sha256':digest(configs),'source_files':{'example.py':'a'*64}}
        (root/'plan.private.json').write_text(json.dumps(plan))
        receipts={};claims={}
        for index,item in enumerate(order[:32]):
            outcome,code=('provider_timeout','provider_timeout') if index<24 else (
                ('provider_invalid_output','false_action') if index<29 else ('ok','ok'))
            binding=dict(item,plan_sha256=digest(plan),source_ref=plan['source_ref'])
            row=dict(binding,native_source_ref=plan['native_source_ref'],status='measured',
                configuration_sha256=plan['configuration_sha256'],
                background_parameters={'attempts':[dict(configs[item['arm']],lane='owed',
                    channel=item['account'],outcome=outcome,native_code=code)]},
                sends=[{'lane':'owed_answer','failure_notice':code!='ok'}],
                development_boundary={'line_attempts':[{'account':item['account'],'accepted':True,'duplicate':False}]})
            for value,suffix,mapping in ((row,'.json',receipts),(binding,'.started.json',claims)):
                path=root/'receipts'/(item['slot']+suffix)
                path.write_text(json.dumps(value));mapping[path.name]=sha(path.read_bytes())
        evidence=Path(directory)/'host.private.json'
        incident={'completed':32,'ready':32,'delivered':3,'claims_are_spent':True,
                  'original_inputs_unchanged':True,'receipts_sha256':receipts,'claims_sha256':claims,
                  'raw_diagnostic':'/private/not-for-publication host detail'}
        evidence.write_text(json.dumps(incident))
        proofs=dict(always_on.OWED_HOST_PROOFS,plan_sha256=sha((root/'plan.private.json').read_bytes()),
            canonical_plan_sha256=digest(plan),configuration_sha256=digest(configs),
            source_files_sha256=digest(plan['source_files']),host_evidence_sha256=sha(evidence.read_bytes()),
            affected_receipts_sha256=digest(receipts),affected_claims_sha256=digest(claims))
        development={'source_ref':plan['source_ref'],'native_source_ref':plan['native_source_ref'],
            'planned_cells':72,'positive_denominator':48,'withholding_denominator':24,
            'status':'complete','proof':{key:proofs[key] for key in
                ('plan_sha256','canonical_plan_sha256','configuration_sha256','source_files_sha256')}}
        return root,evidence,development,proofs

    def repin_evidence(self, evidence, proofs):
        raw=evidence.read_bytes();incident=json.loads(raw)
        proofs.update(host_evidence_sha256=hashlib.sha256(raw).hexdigest(),
            affected_receipts_sha256=always_on._owed_host_digest(incident['receipts_sha256']),
            affected_claims_sha256=always_on._owed_host_digest(incident['claims_sha256']))

    def repin_receipt(self, root, evidence, proofs, name, row):
        path=root/'receipts'/name;path.write_text(json.dumps(row))
        incident=json.loads(evidence.read_text())
        incident['receipts_sha256'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
        evidence.write_text(json.dumps(incident));self.repin_evidence(evidence,proofs)

    def test_reviewed_observation_binds_original_inputs_and_derives_all_retained_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            root,evidence,development,proofs=self.archive(directory)
            before={path.relative_to(root).as_posix():path.read_bytes() for path in root.rglob('*') if path.is_file()}
            with mock.patch.object(always_on,'OWED_HOST_PROOFS',proofs),mock.patch('subprocess.run') as invoke:
                note=always_on.verified_owed_host_interruption(root,evidence,development)
                always_on.require_owed_host_interruption(development,note)
            invoke.assert_not_called()
            self.assertEqual(note['retained_outcomes'],{'timeouts':24,'false_action':5,'delivered':3})
            self.assertEqual((note['planned_cells'],note['affected_completed_cells'],note['excluded_cells'],note['replayed_cells']),
                             (72,32,0,0))
            self.assertFalse(note['model_capability_ranking'])
            public=json.dumps(note,ensure_ascii=False)
            for private in (str(root),str(evidence),'raw_diagnostic','host detail','cell00'):
                self.assertNotIn(private,public)
            self.assertEqual(before,{path.relative_to(root).as_posix():path.read_bytes()
                                     for path in root.rglob('*') if path.is_file()})

    def test_changed_evidence_plan_receipt_or_claim_cannot_reuse_the_reviewed_proof(self):
        for changed in ('evidence','plan','receipt','claim'):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as directory:
                root,evidence,development,proofs=self.archive(directory)
                path={'evidence':evidence,'plan':root/'plan.private.json',
                      'receipt':root/'receipts/cell00.json','claim':root/'receipts/cell00.started.json'}[changed]
                path.write_bytes(path.read_bytes()+b'\n')
                with mock.patch.object(always_on,'OWED_HOST_PROOFS',proofs),self.assertRaisesRegex(ValueError,'owed_host'):
                    always_on.verified_owed_host_interruption(root,evidence,development)

    def test_symlinked_observation_plan_capture_or_study_is_refused(self):
        for changed in ('evidence','plan','receipt','claim','receipts','study'):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as directory:
                root,evidence,development,proofs=self.archive(directory)
                path={'evidence':evidence,'plan':root/'plan.private.json','receipt':root/'receipts/cell00.json',
                      'claim':root/'receipts/cell00.started.json','receipts':root/'receipts','study':root}[changed]
                target=path.with_name(path.name+'.original');path.rename(target);path.symlink_to(target)
                with mock.patch.object(always_on,'OWED_HOST_PROOFS',proofs),self.assertRaisesRegex(ValueError,'owed_host'):
                    always_on.verified_owed_host_interruption(root,evidence,development)

    def test_self_rehashed_inventory_cannot_select_unplanned_or_later_cells(self):
        for selected in ('foreign-cell','cell50'):
            with self.subTest(selected=selected),tempfile.TemporaryDirectory() as directory:
                root,evidence,development,proofs=self.archive(directory)
                incident=json.loads(evidence.read_text())
                for key,suffix in (('receipts_sha256','.json'),('claims_sha256','.started.json')):
                    incident[key][selected+suffix]=incident[key].pop('cell00'+suffix)
                evidence.write_text(json.dumps(incident));self.repin_evidence(evidence,proofs)
                with mock.patch.object(always_on,'OWED_HOST_PROOFS',proofs),self.assertRaisesRegex(ValueError,'inventory'):
                    always_on.verified_owed_host_interruption(root,evidence,development)

    def test_self_rehashed_receipt_must_still_match_source_configuration_account_and_claim(self):
        for key,value in (('source_ref','f'*40),('native_source_ref','e'*40),('configuration_sha256','d'*64),
                          ('account','secondary'),('slot','cell01')):
            with self.subTest(field=key),tempfile.TemporaryDirectory() as directory:
                root,evidence,development,proofs=self.archive(directory)
                row=json.loads((root/'receipts/cell00.json').read_text());row[key]=value
                self.repin_receipt(root,evidence,proofs,'cell00.json',row)
                with mock.patch.object(always_on,'OWED_HOST_PROOFS',proofs),self.assertRaisesRegex(ValueError,'binding'):
                    always_on.verified_owed_host_interruption(root,evidence,development)

    def test_retained_counts_are_recomputed_instead_of_accepting_an_evidence_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root,evidence,development,proofs=self.archive(directory)
            row=json.loads((root/'receipts/cell00.json').read_text())
            row['background_parameters']['attempts'][0].update(outcome='ok',native_code='ok')
            row['sends'][0]['failure_notice']=False
            self.repin_receipt(root,evidence,proofs,'cell00.json',row)
            with mock.patch.object(always_on,'OWED_HOST_PROOFS',proofs),self.assertRaisesRegex(ValueError,'outcome_count'):
                always_on.verified_owed_host_interruption(root,evidence,development)

    def test_completed_affected_cohort_requires_the_bound_note_and_cannot_publish_a_metadata_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            root,evidence,development,proofs=self.archive(directory)
            with mock.patch.object(always_on,'OWED_HOST_PROOFS',proofs):
                with self.assertRaisesRegex(ValueError,'required'):
                    always_on.require_owed_host_interruption(development,None)
                always_on.require_owed_host_interruption(dict(development,status='pending'),None)
                with self.assertRaisesRegex(ValueError,'invalid_owed_host'):
                    always_on.require_owed_host_interruption(development,{'verified':True})
                note=always_on.verified_owed_host_interruption(root,evidence,development)
                for bad in (dict(note,excluded_cells=1),dict(note,model_capability_ranking=True),
                            dict(note,diagnostic='/private/hidden')):
                    with self.assertRaisesRegex(ValueError,'invalid_owed_host'):
                        always_on.require_owed_host_interruption(development,bad)
                with self.assertRaisesRegex(ValueError,'binding'):
                    always_on.require_owed_host_interruption(dict(development,native_source_ref='f'*40),note)

    def test_fixed_notice_is_visible_before_results_and_proof_hashes_can_wrap(self):
        with tempfile.TemporaryDirectory() as directory:
            root,evidence,development,proofs=self.archive(directory)
            development.update(tasks=[],withholding=[],results=None,limits='固定開發限制。')
            with mock.patch.object(always_on,'OWED_HOST_PROOFS',proofs),mock.patch.object(always_on,'owed_development_module'):
                note=always_on.verified_owed_host_interruption(root,evidence,development)
                panel=always_on.owed_development_panel(development,note)
            self.assertIn(always_on.OWED_HOST_NOTICE,panel)
            self.assertIn('72 槽與 130 次判讀的原定門檻、分母及第一次判讀優先原則不變',panel)
            self.assertIn('<ul class="iteration-meta">',panel)
            self.assertIn(always_on.OWED_HOST_INTERRUPTION_NAME,panel)


if __name__=='__main__':unittest.main()
