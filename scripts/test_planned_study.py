"""Plan-only publication bindings and cold import preflight, using synthetic fixtures."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,HERE/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
planned=load('planned_study','planned_study.py')
renderer=load('planned_renderer','render-line-always-on.py')


def snapshot():
    return {'refs':{'existing':'a'*40,'engine':'b'*40,**{arm:'b'*40 for arm in planned.ARMS[1:]}},
        'arms':list(planned.ARMS),'arm_configs':{'existing':{'always_on':None},**{arm:{'always_on':{
            'provider':'openai' if arm=='engine_sol_low' else 'gemini',
            'model':'gpt-6.1-sol' if arm=='engine_sol_low' else 'gemini-3.8-flash',
            'thinking_level':'low' if arm=='engine_sol_low' else arm.removeprefix('engine_'),
            'max_output_tokens':32768,'timeout_s':120}} for arm in planned.ARMS[1:]}},
        'episode_count':103,'slot_count':824,'repeats':2,'workers':6,'slot_timeout_s':1800,
        'smoke':False,'executor':True,'study_design':'background_thinking_variants','study_kind':'model_quality',
        'schedule_verified':True,'proof':{key:'c'*64 for key in planned.PROOFS},
        'execution_order':[{'slot':'private-slot'}],'environment':{'private_path':'/Users/private'},
        'receipts':[{'private_score':1}]}


def cold_fixture(root, runner_text, *, trusted_runner_digest=None, shadow_text=None):
    (root/'source').mkdir();(root/'harness').mkdir()
    cohort={'episodes':[]}
    for path,text in ((root/'harness/__init__.py',''),(root/'harness/runner.py',runner_text),
                      (root/'harness/cases.json',json.dumps(cohort)),(root/'cases.json',json.dumps(cohort))):
        path.write_text(text)
    if shadow_text is not None:
        (root/'harness/tempfile.py').write_text(shadow_text)
    files={path.relative_to(root).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
           for path in root.rglob('*') if path.is_file()}
    (root/'plan.json').write_text(json.dumps({'refs':{'engine':'a'*40},'files':files}))
    trusted={'runner.py':trusted_runner_digest or files['harness/runner.py'],
             'cases.json':files['harness/cases.json']}
    protocol={'source_ref':'a'*40,'cases':cohort,'files_sha256':trusted}
    digest=hashlib.sha256(json.dumps(protocol,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    cases={'source_ref':'a'*40,'episodes':[],'cases_sha256':files['harness/cases.json'],'protocol_sha256':digest}
    return cases,protocol


class PlannedStudyTests(unittest.TestCase):
    def test_projection_is_plan_only_with_all_denominators_and_no_live_receipts(self):
        value=planned.project(snapshot());planned.validate_public(value)
        text=json.dumps(value)
        for private in ('private-slot','private_path','private_score','execution_order','environment','receipts'):
            self.assertNotIn(private,text)
        self.assertEqual((value['episode_count'],value['slot_count'],value['workers'],value['slot_timeout_s']),(103,824,6,1800))
        self.assertFalse(value['quality_complete']);self.assertFalse(value['full_study_result'])
        self.assertFalse(value['schedule']['combined_chronological_perfect_cycle'])
        page=renderer.render({'status':'pending','planned_study':value})
        self.assertIn('完整題組的分數、改善幅度與勝負結論仍待完成',page)
        self.assertIn('24 種排列輪換',page);self.assertIn('1,800 秒',page)
        self.assertIn('沒有即時部分分數',page)

    def test_wrong_source_config_scope_or_quality_claim_is_rejected(self):
        for change in (lambda d:d.update(workers=8),lambda d:d.update(smoke=True),lambda d:d.update(slot_count=823),
                       lambda d:d['refs'].update(engine_high='d'*40),
                       lambda d:d['arm_configs']['engine_high']['always_on'].update(thinking_level='medium'),
                       lambda d:d['proof'].update(plan_sha256='bad')):
            value=snapshot();change(value)
            with self.assertRaises(ValueError):planned.project(value)
        value=planned.project(snapshot());value['quality_complete']=True
        with self.assertRaises(ValueError):renderer.planned_study_panel(value)
        value=planned.project(snapshot());value['arm_configs']['engine_high']['always_on']['max_output_tokens']=8192
        with self.assertRaises(ValueError):renderer.planned_study_panel(value)

    def test_protocol_mismatch_prevents_even_launching_the_cold_verifier(self):
        cases={'source_ref':'a'*40,'episodes':[],'protocol_sha256':'b'*64}
        with patch.object(planned.subprocess,'run') as run:
            with self.assertRaises(ValueError):planned.verified_projection('/synthetic',cases,{'source_ref':'c'*40})
            run.assert_not_called()

    def test_unbound_bytecode_is_rejected_before_frozen_runner_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'source').mkdir();(root/'harness').mkdir()
            marker=root/'imported'
            runner=root/'harness/runner.py'
            runner.write_text(f'from pathlib import Path\nPath({str(marker)!r}).write_text("bad import")\n')
            files={'harness/runner.py':hashlib.sha256(runner.read_bytes()).hexdigest()}
            (root/'plan.json').write_text(json.dumps({'files':files}))
            (root/'harness/runner.pyc').write_bytes(b'unbound cached code')
            protocol={'source_ref':'a'*40,'cases':{'episodes':[]},'files_sha256':{}}
            digest=hashlib.sha256(json.dumps(protocol,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            cases={'source_ref':'a'*40,'episodes':[],'cases_sha256':'b'*64,'protocol_sha256':digest}
            with self.assertRaisesRegex(ValueError,'planned_study_not_verified'):
                planned.verified_projection(root,cases,protocol)
            self.assertFalse(marker.exists())

    def test_self_rehashed_foreign_runner_cannot_execute_before_trusted_hash_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);marker=root/'foreign-runner-executed'
            text=f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n'
            cases,protocol=cold_fixture(root,text,trusted_runner_digest='b'*64)
            with self.assertRaisesRegex(ValueError,'planned_study_not_verified'):
                planned.verified_projection(root,cases,protocol)
            self.assertFalse(marker.exists())

    def test_self_bound_stdlib_shadow_module_cannot_execute_from_harness(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);marker=root/'shadow-module-executed'
            shadow=f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n'
            cases,protocol=cold_fixture(root,'import tempfile\n',shadow_text=shadow)
            with self.assertRaisesRegex(ValueError,'planned_study_not_verified'):
                planned.verified_projection(root,cases,protocol)
            self.assertFalse(marker.exists())

    def test_cold_child_has_no_environment_and_only_verifies_the_plan(self):
        from types import SimpleNamespace
        protocol={'source_ref':'b'*40,'cases':{'episodes':[]},'files_sha256':{}}
        digest=hashlib.sha256(json.dumps(protocol,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        cases={'source_ref':'b'*40,'episodes':[],'cases_sha256':'c'*64,'protocol_sha256':digest}
        with patch.object(planned.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(snapshot()))) as run:
            self.assertTrue(planned.verified_projection('/synthetic',cases,protocol)['plan_verified'])
        args,kwargs=run.call_args
        self.assertEqual(args[0][1:4],['-I','-B','-c']);self.assertEqual(kwargs['env'],{})
        self.assertIn('runner.verify(root,frozen=True)',args[0][4])
        self.assertNotIn('runner.run(',args[0][4]);self.assertNotIn('runner.summarize(',args[0][4])


if __name__=='__main__':unittest.main()
