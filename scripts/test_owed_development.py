import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('public_owed_dev',Path(__file__).with_name('owed_development.py'))
dev=importlib.util.module_from_spec(spec);spec.loader.exec_module(dev)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def proof(complete=False):
    value={**dev.TRUST['proof'],'plan_sha256':'1'*64,'canonical_plan_sha256':'2'*64}
    if complete:value.update({key:'3'*64 for key in ('binding_sha256','native_receipts_sha256',
        'judge_attempts_sha256','retained_quality_sha256','packets_sha256','controls_sha256','mapping_sha256')})
    return value


def native_usage(attempts):
    return {'attempts':attempts,'request_sent_attempts':attempts,'failed_attempts':attempts,
        'invalid_output_attempts':attempts,'token_usage':{field:{'known_tokens':None,
         'known_attempts':0,'unknown_attempts':attempts} for field in dev.TOKEN_FIELDS}}


def complete_snapshot():
    native=[];rows=[]
    for arm in dev.ARMS:
        for index in range(16):
            native.append({'arm':arm,'kind':'positive','assessment':{
                'setup_and_capture_ready':True,'late_answer_delivered':False,'closures':1,
                'native_outcomes':[{'native_code':'provider_invalid_output','outcome':'provider_invalid_output'}],
                'diagnostics':{'rows':[{'attempt_id':'secret-id','parsed_json':'PRIVATE REJECTED BODY',
                    'available':False,'unavailable_reason':'no_parsed_final_return'}]}}})
            rows.append({'arm':arm,'slot':'private-slot-id','reason':'PRIVATE JUDGE REASON',
                'judgments':{index:{field:False for field in dev.FIELDS} for index in ('1','2')}})
        native.extend({'arm':arm,'kind':'withhold','assessment':{
            'setup_and_capture_ready':True,'withholding_passed':True,'request_uploaded':0}} for _ in range(8))
    return {'proof':proof(True),'complete':True,'native':native,
        'native_usage':{arm:native_usage(16) for arm in dev.ARMS},'quality':{
            'judging_complete':True,'controls_passed':True,'quality_ready':True,
            'publication_ready':False,'held_out':False,'positive_denominator':48,
            'withholding_denominator':24,'planned_judgments':130,'retained_attempts':130,
            'missing_judgments':0,'primary_pass':1,'controls':[{'as_expected':True} for _ in range(34)],
            'rows':rows,'withholding':[{} for _ in range(24)],'judge_usage':native_usage(130)}}


class Projection(unittest.TestCase):
    def test_pending_fixed_scope_and_no_quality(self):
        value=dev.project({'proof':proof(),'complete':False})
        self.assertEqual(dev.validate_public(value),value)
        self.assertEqual((value['planned_cells'],value['positive_denominator'],value['withholding_denominator']), (72,48,24))
        self.assertEqual((value['max_native_calls'],value['max_judge_calls']), (48,130))
        self.assertEqual(len(value['tasks']),8);self.assertEqual(len(value['withholding']),4)
        self.assertEqual(sum(row['scope']=='private' for row in value['tasks']),6)
        self.assertEqual(value['schedule']['secondary_order_offset'],3)
        self.assertIsNone(value['results']);self.assertFalse(value['quality_complete'])
        for key in ('full_study_result','publication_ready','held_out'):self.assertIs(value[key],False)
        bad=copy.deepcopy(value);bad['private_path']='/Users/SECRET'
        with self.assertRaises(ValueError):dev.validate_public(bad)

    def test_unfavorable_outputs_remain_in_all_denominators_and_private_data_dropped(self):
        value=dev.project(complete_snapshot());dev.validate_public(value)
        encoded=json.dumps(value)
        for secret in ('secret-id','PRIVATE REJECTED BODY','private-slot-id','PRIVATE JUDGE REASON','parsed_json'):
            self.assertNotIn(secret,encoded)
        for row in value['results']['arms'].values():
            self.assertEqual(row['positive_denominator'],16);self.assertEqual(row['closures'],16)
            self.assertEqual(row['judgments']['answered'],0);self.assertEqual(row['withholding_passed'],8)
            self.assertEqual(row['diagnostic_availability'],{'no_parsed_final_return':16})
            self.assertEqual(row['native_codes'],{'provider_invalid_output':16})
            self.assertIsNone(row['native_usage']['token_usage']['total_tokens']['known_tokens'])
            self.assertEqual(row['native_usage']['token_usage']['total_tokens']['unknown_attempts'],16)
            self.assertFalse(row['native_usage']['usage_complete'])

    def test_failed_control_missing_judgment_observer_and_zero_call_gate_refuse(self):
        for mutate in (lambda x:x['quality']['controls'][0].update(as_expected=False),
                       lambda x:x['quality'].update(missing_judgments=1),
                       lambda x:x['quality']['rows'].pop(),
                       lambda x:x['native'][0]['assessment'].update(setup_and_capture_ready=False),
                       lambda x:x['native'][16]['assessment'].update(request_uploaded=1)):
            with self.subTest(mutate=mutate):
                value=complete_snapshot();mutate(value)
                with self.assertRaises(ValueError):dev.project(value)

    def test_provider_outcome_does_not_invent_missing_native_code(self):
        snapshot=complete_snapshot()
        snapshot['native'][0]['assessment']['native_outcomes']=[{'native_code':None,'outcome':'provider_timeout'}]
        value=dev.project(snapshot);dev.validate_public(value)
        row=value['results']['arms']['engine_medium']
        self.assertEqual(row['native_codes'],{'provider_invalid_output':15})
        self.assertEqual(row['native_outcomes'],{'provider_timeout':1,'provider_invalid_output':15})
        self.assertEqual(row['unknown_native_code_attempts'],1)
        self.assertEqual(row['positive_denominator'],16)

    def test_public_results_closed_schema(self):
        value=dev.project(complete_snapshot())
        for mutate in (lambda x:x['results']['arms']['engine_medium'].update(parsed_json='SECRET'),
                       lambda x:x['proof'].update(foreign_sha256='a'*64),
                       lambda x:x['results']['arms']['engine_medium']['judgments'].update(answered=17),
                       lambda x:x['results']['judge_usage']['token_usage']['total_tokens'].update(known_tokens=0)):
            bad=copy.deepcopy(value);mutate(bad)
            with self.assertRaises(ValueError):dev.validate_public(bad)


class ColdBinding(unittest.TestCase):
    def make(self,root):
        source=root/'source';prefix=source/'serve/line_agent_v3/evals/always_on'
        prefix.mkdir(parents=True)
        for directory in (source/'serve',source/'serve/line_agent_v3',source/'serve/line_agent_v3/evals',prefix):
            (directory/'__init__.py').write_text('')
        code="import json\ndef verify(root):return json.loads((root/'plan.private.json').read_text())\n"
        (prefix/'owed_development.py').write_text(code)
        (prefix/'owed_development_cases.json').write_text('{}')
        files={path.relative_to(source).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
               for path in source.rglob('*') if path.is_file()}
        trusted=copy.deepcopy(dev.TRUST)
        trusted['proof']['source_files_sha256']=digest(files)
        trusted['proof']['corpus_sha256']=hashlib.sha256(b'{}').hexdigest()
        trusted['proof']['schedule_sha256']=digest([])
        plan={'source_files':files,'source_ref':trusted['source_ref'],'native_source_ref':trusted['native_source_ref'],
              'configurations':trusted['configurations'],'configuration_sha256':trusted['proof']['configuration_sha256'],
              'settings':trusted['settings'],'execution_order':[],'notice':'保留原生計畫的繁體中文'}
        (root/'plan.private.json').write_text(json.dumps(plan))
        return trusted,plan,prefix

    def test_cold_plan_verification_preserves_input_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);trusted,_plan,_prefix=self.make(root)
            before={str(path.relative_to(root)):path.read_bytes() for path in root.rglob('*') if path.is_file()}
            with patch.object(dev,'TRUST',trusted):value=dev.verified_projection(root)
            self.assertEqual(value['status'],'pending')
            self.assertEqual(value['proof']['canonical_plan_sha256'],hashlib.sha256(
                json.dumps(_plan,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())
            after={str(path.relative_to(root)):path.read_bytes() for path in root.rglob('*') if path.is_file()}
            self.assertEqual(before,after);self.assertFalse(list(root.rglob('*.pyc')))

    def test_self_rehashed_foreign_code_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);trusted,plan,prefix=self.make(root);marker=root/'EXECUTED'
            (prefix/'owed_development.py').write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n")
            plan['source_files']['serve/line_agent_v3/evals/always_on/owed_development.py']=hashlib.sha256((prefix/'owed_development.py').read_bytes()).hexdigest()
            (root/'plan.private.json').write_text(json.dumps(plan))
            with patch.object(dev,'TRUST',trusted),self.assertRaises(ValueError):dev.verified_projection(root)
            self.assertFalse(marker.exists())

    def test_added_shadow_bytecode_and_symlink_directory_are_rejected(self):
        for kind in ('shadow','bytecode','symlink'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);trusted,plan,_prefix=self.make(root)
                if kind=='symlink':
                    target=root/'foreign';target.mkdir();(target/'__init__.py').write_text("raise RuntimeError('foreign')")
                    (root/'source/foreign').symlink_to(target,target_is_directory=True)
                else:
                    name='tempfile.py' if kind=='shadow' else 'foreign.pyc'
                    (root/'source'/name).write_bytes(b'foreign')
                    plan['source_files'][name]=hashlib.sha256(b'foreign').hexdigest()
                    (root/'plan.private.json').write_text(json.dumps(plan))
                with patch.object(dev,'TRUST',trusted),self.assertRaises(ValueError):dev.verified_projection(root)

    def test_semantically_equal_original_bytes_must_match_before_judge_import(self):
        for target in ('plan.private.json','plan.sha256.json','receipts/fixed.json','receipts/fixed.started.json',
                       'receipts/foreign.json','symlink_claim','symlink_receipts','symlink_copied_receipts',
                       'allowed_supervisor'):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as temp:
                root=Path(temp)/'native';root.mkdir();trusted,plan,prefix=self.make(root)
                marker=Path(temp)/'EXECUTED'
                (prefix/'owed_development.py').write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n")
                plan['source_files']={path.relative_to(root/'source').as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                                     for path in (root/'source').rglob('*') if path.is_file()}
                trusted['proof']['source_files_sha256']=digest(plan['source_files'])
                plan['execution_order']=[{'slot':'fixed'}]
                trusted['proof']['schedule_sha256']=digest(plan['execution_order'])
                (root/'plan.private.json').write_text(json.dumps(plan))
                (root/'plan.sha256.json').write_text('{"sha256":"native"}\n')
                (root/'receipts').mkdir()
                for name in ('fixed.json','fixed.started.json'):(root/'receipts'/name).write_text('{"same":true}\n')
                judging=Path(temp)/'judge';shutil.copytree(root/'source',judging/'source/engine')
                shutil.copytree(root/'receipts',judging/'inputs/receipts')
                for name in ('plan.private.json','plan.sha256.json'):
                    (judging/'inputs'/name).write_bytes((root/name).read_bytes())
                changed=root/target
                if target=='receipts/foreign.json':changed.write_text('{"foreign":"attempt"}\n')
                elif target=='symlink_claim':
                    claim=root/'receipts/fixed.started.json';claim.unlink()
                    claim.symlink_to(judging/'inputs/receipts/fixed.started.json')
                elif target in ('symlink_receipts','symlink_copied_receipts'):
                    directory=(root/'receipts') if target=='symlink_receipts' else (judging/'inputs/receipts')
                    retained=directory.with_name('retained-receipts');directory.rename(retained)
                    directory.symlink_to(retained,target_is_directory=True)
                elif target=='allowed_supervisor':
                    (root/'receipts/fixed.supervisor.json').write_text('{"usage":"unknown; never retry"}\n')
                else:
                    changed.write_text(json.dumps(json.loads(changed.read_text()),indent=2)+'\n')
                    self.assertEqual(json.loads(changed.read_text()),json.loads((judging/'inputs'/target).read_text()))
                with patch.object(dev,'TRUST',trusted),self.assertRaises(ValueError):dev.verified_projection(root,judging)
                self.assertEqual(marker.exists(),target=='allowed_supervisor')


if __name__=='__main__':unittest.main()
