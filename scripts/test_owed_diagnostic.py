"""Diagnostic scope, frozen CLI reproduction and public projection gates."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,HERE/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
diagnostic=load('owed_diagnostic','owed_diagnostic.py')
renderer=load('always_on_owed_renderer','render-line-always-on.py')


def snapshot():
    quality={'protocol':'native_real_owed_blinded_foreground_v1','judging_complete':True,'controls_passed':True,
        'quality_ready':True,'publication_ready':False,'planned_slots':6,'planned_judgments':46,
        'retained_attempts':46,'missing_judgments':0,'primary_pass':1,
        'controls':[{'as_expected':True} for _ in range(34)],'rows':[]}
    native=[]
    for arm in diagnostic.ARMS:
        for account in diagnostic.ACCOUNTS:
            delivered=arm!='engine_medium'
            flags={field:field!='answered' or delivered for field in diagnostic.FIELDS}
            quality['rows'].append({'arm':arm,'account':account,'slot':'private-opaque-slot',
                'native_late_answer_delivered':delivered,'native_closures':int(not delivered),
                'judgments':{index:dict(flags,reason='private judge prose',packet_id='private-packet') for index in ('1','2')}})
            native.append({'arm':arm,'account':account,'assessment':{'setup_and_capture_ready':True,
                'request_uploaded':True,'late_answer_delivered':delivered,'closures':int(not delivered)}})
    proof={field:'a'*(40 if field.endswith('_ref') else 64) for field in diagnostic.PROOF_FIELDS}
    configs={arm:{'provider':'openai' if arm=='engine_sol_low' else 'gemini',
        'model':'gpt-6.1-sol' if arm=='engine_sol_low' else 'gemini-3.8-flash',
        'thinking_level':'low' if arm=='engine_sol_low' else arm.removeprefix('engine_'),
        'max_output_tokens':32768,'timeout_s':120} for arm in diagnostic.ARMS}
    return {'quality':quality,'native':native,'proof':proof,'configurations':configs,
            'raw_prompt':'private raw prompt','reasoning':'private raw thought','api_key':'private key'}


class OwedDiagnosticTests(unittest.TestCase):
    def test_semantic_projection_retains_every_closure_without_private_identifiers_or_prose(self):
        result=diagnostic.project(snapshot())
        renderer.check_public(result)
        text=json.dumps(result,ensure_ascii=False)
        for word in ('private-opaque-slot','private-packet','private judge prose','private raw prompt','private raw thought','private key'):
            self.assertNotIn(word,text)
        self.assertEqual(len(result['rows']),6)
        self.assertEqual(sum(row['late_answer_delivered'] for row in result['rows']),4)
        self.assertEqual(sum(row['closures'] for row in result['rows']),2)
        self.assertFalse(result['full_study_result']);self.assertFalse(result['publication_ready'])

    def test_failed_controls_missing_pass_unuploaded_request_and_subset_cannot_publish(self):
        changes=[lambda d:d['quality'].update(missing_judgments=1),
            lambda d:d['quality']['controls'][0].update(as_expected=False),
            lambda d:d['quality']['rows'].pop(),
            lambda d:d['native'][0]['assessment'].update(request_uploaded=False),
            lambda d:d['quality']['rows'][0]['judgments'].pop('2'),
            lambda d:d['quality']['rows'][0]['judgments']['1'].update(answered='true'),
            lambda d:d['configurations']['engine_high'].update(thinking_level='medium'),
            lambda d:d['proof'].update(extra_private_key='a'*64)]
        for change in changes:
            with self.subTest(change=change):
                value=snapshot();change(value)
                with self.assertRaises(ValueError):diagnostic.project(value)

    def test_panel_keeps_full_scores_pending_and_does_not_rank_one_question(self):
        result=diagnostic.project(snapshot())
        page=renderer.render({'status':'pending','owed_diagnostic':result})
        self.assertIn('尚未有可發布的完整 Always-on 研究',page)
        self.assertIn('與 824 個執行槽的完整研究分開',page)
        self.assertIn('沒有模型排名',page)
        self.assertIn('控制題 34/34',page)
        self.assertIn('2 次未補答',page)
        self.assertIn('前景等待時間不能當成速度成績',page)
        self.assertIn('第二帳號',page)
        self.assertNotIn('目前沒有實測分數',page)
        self.assertIn('report-layout.css',page)
        with self.assertRaises(ValueError):renderer.owed_diagnostic_panel(dict(result,full_study_result=True))

    def test_cli_gate_uses_isolated_frozen_summary_and_stops_on_reproduction_failure(self):
        from types import SimpleNamespace
        value=snapshot()
        with patch.object(diagnostic.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(value))) as run:
            self.assertTrue(diagnostic.verified_projection('/synthetic/archive')['diagnostic_complete'])
        args,kwargs=run.call_args
        self.assertEqual(args[0][1:4],['-I','-B','-c']);self.assertEqual(kwargs['env'],{})
        self.assertIn('module.main()',args[0][4]);self.assertIn('written[0] != retained',args[0][4])
        with patch.object(diagnostic.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='')):
            with self.assertRaisesRegex(ValueError,'invalid_frozen'):diagnostic.verified_projection('/synthetic/archive')


if __name__=='__main__':unittest.main()
