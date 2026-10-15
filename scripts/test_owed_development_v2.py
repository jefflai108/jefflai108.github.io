import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


def module(name, filename):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(filename))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


dev=module('site_owed_v2','owed_development_v2.py')
renderer=module('site_owed_v2_renderer','render-line-always-on.py')


def usage(attempts, *, failed=0, interrupted=0, capture_complete=True):
    return {'attempts':attempts,'request_sent_attempts':attempts-interrupted,'failed_attempts':failed,
        'invalid_output_attempts':0,'retained_receipts':attempts-interrupted,
        'interrupted_claims':interrupted,'request_sent_unknown_attempts':interrupted,
        'unknown_usage_attempts':attempts,'capture_complete':capture_complete,
        'usage_complete':capture_complete and attempts==0,'token_usage':{field:{'known_tokens':None,
            'known_attempts':0,'unknown_attempts':attempts} for field in dev.TOKEN_FIELDS}}


def snapshot(*, errors=10, interrupted=2):
    native=[];rows=[]
    for arm in dev.ARMS:
        for _ in range(16):
            native.append({'arm':arm,'kind':'positive','assessment':{
                'setup_and_capture_ready':True,'late_answer_delivered':False,'closures':1,
                'native_outcomes':[{'native_code':'provider_invalid_output','outcome':'provider_invalid_output'}],
                'diagnostics':{'parsed_json':'PRIVATE REJECTED MODEL TEXT','private_id':'do-not-publish'}}})
            rows.append({'arm':arm,'slot':'PRIVATE SLOT','reason':'PRIVATE REASON',
                'judgments':{'1':{field:False for field in dev.FIELDS},
                             '2':{field:True for field in dev.FIELDS}}})
        native += [{'arm':arm,'kind':'withhold','assessment':{
            'setup_and_capture_ready':True,'withholding_passed':True,'request_uploaded':0}} for _ in range(8)]
    proof={**dev.TRUST['proof'],**{key:'3'*64 for key in dev.CAPTURE_PROOFS|dev.JUDGE_PROOFS}}
    return {'proof':proof,'native':native,'missing_started_cells':0,
        'missing_started_by_arm':{arm:0 for arm in dev.ARMS},
        'unverified_capture_by_arm':{arm:0 for arm in dev.ARMS},
        'native_usage':{arm:usage(16) for arm in dev.ARMS},'quality':{
            'protocol':dev.JUDGE_PROTOCOL,'positive_denominator':48,'withholding_denominator':24,
            'planned_judgments':130,'max_provider_calls':390,'max_attempts_per_job':3,'primary_pass':1,
            'retry_policy':copy.deepcopy(dev.RETRY_POLICY),'publication_ready':False,'held_out':False,
            'started_attempts':130+errors+interrupted,'retained_attempts':130+errors,
            'technical_errors':errors,'valid_judgments':130,'missing_judgments':0,
            'interrupted_started_judgments':interrupted,'exhausted_judgments':0,'retryable_judgments':0,
            'judging_complete':True,'controls_passed':True,'quality_ready':True,
            'controls':[{'as_expected':True} for _ in range(34)],'rows':rows,'withholding':[{} for _ in range(24)],
            'judge_usage':usage(130+errors+interrupted,failed=errors+interrupted,interrupted=interrupted,
                                capture_complete=interrupted==0)}}


class Projection(unittest.TestCase):
    def test_reviewed_freeze_required_before_any_frozen_execution(self):
        with patch.object(dev,'TRUST',{'protocol':dev.TRUST_PROTOCOL,'status':'awaiting_reviewed_freeze'}), \
                patch.object(dev.subprocess,'run') as execute,self.assertRaisesRegex(ValueError,'reviewed_freeze_required'):
            dev.verified_projection(Path('/not-an-archive'))
        execute.assert_not_called()

    def test_negative_first_valid_verdict_is_final_and_errors_costs_are_retained(self):
        value=dev.project(snapshot());self.assertEqual(dev.validate_public(value),value)
        self.assertEqual(value['status'],'complete')
        self.assertEqual((value['planned_cells'],value['positive_denominator'],value['withholding_denominator']),(72,48,24))
        self.assertEqual((value['planned_judge_jobs'],value['max_judge_calls'],value['max_combined_provider_calls']),(130,390,438))
        self.assertEqual((value['judging']['valid_judgments'],value['judging']['retained_attempts'],value['judging']['started_attempts']),(130,140,142))
        self.assertEqual(value['judging']['technical_errors'],10)
        self.assertEqual(value['judging']['usage']['request_sent_unknown_attempts'],2)
        self.assertEqual(value['judging']['usage']['token_usage']['total_tokens']['unknown_attempts'],142)
        for row in value['results']['arms'].values():
            self.assertEqual(row['judgments'],{field:0 for field in dev.FIELDS})
            self.assertEqual(row['pass_agreement'],{field:0 for field in dev.FIELDS})
            self.assertEqual((row['positive_denominator'],row['closures'],row['withholding_passed']),(16,16,8))
        for secret in ('PRIVATE','parsed_json','private_id','PRIVATE SLOT','PRIVATE REASON'):
            self.assertNotIn(secret,json.dumps(value))
        for key in ('full_study_result','publication_ready','held_out'):self.assertIs(value[key],False)

    def test_failed_valid_control_withholds_scores_and_is_not_a_retry_instruction(self):
        raw=snapshot(errors=0,interrupted=0)
        raw['quality']['controls'][0]['as_expected']=False
        raw['quality'].update(controls_passed=False,quality_ready=False)
        value=dev.project(raw);dev.validate_public(value)
        self.assertEqual(value['status'],'unqualified');self.assertIsNone(value['results'])
        self.assertEqual((value['judging']['valid_judgments'],value['judging']['expected_controls']),(130,33))
        self.assertEqual(value['judging']['retryable_judgments'],0)

    def test_exhausted_missing_verdicts_keep_original_denominator_and_cost(self):
        raw=snapshot(errors=10,interrupted=2);q=raw['quality']
        q.update(valid_judgments=125,missing_judgments=5,exhausted_judgments=5,retryable_judgments=0,
            retained_attempts=135,started_attempts=137,judging_complete=False,controls_passed=False,quality_ready=False)
        q['controls']=q['controls'][:29];q['judge_usage']=usage(137,failed=12,interrupted=2,capture_complete=False)
        value=dev.project(raw);dev.validate_public(value)
        self.assertIsNone(value['results']);self.assertEqual(value['planned_judge_jobs'],130)
        self.assertEqual(value['judging']['exhausted_judgments'],5)

    def test_prepared_native_and_complete_native_without_judging_are_distinct(self):
        raw=snapshot();raw['quality']=None
        raw['proof']={k:v for k,v in raw['proof'].items() if k not in dev.JUDGE_PROOFS}
        value=dev.project(raw);dev.validate_public(value)
        self.assertEqual(value['status'],'native_complete');self.assertIsNone(value['results'])
        raw.update(native=[],missing_started_cells=1,
            missing_started_by_arm={arm:int(arm=='engine_medium') for arm in dev.ARMS},
            unverified_capture_by_arm={arm:24 for arm in dev.ARMS},
            native_usage={arm:usage(0,capture_complete=False) for arm in dev.ARMS})
        value=dev.project(raw);dev.validate_public(value)
        self.assertEqual(value['status'],'native_incomplete')
        self.assertEqual(value['native']['missing_started_cells'],1)

    def test_missing_started_and_incomplete_observer_never_claim_complete_known_usage(self):
        for missing in (True,False):
            with self.subTest(missing_started=missing):
                raw=snapshot();raw['quality']=None
                raw['proof']={k:v for k,v in raw['proof'].items() if k not in dev.JUDGE_PROOFS}
                if missing:
                    raw['native'].pop(0);raw['missing_started_cells']=1
                    raw['missing_started_by_arm']['engine_medium']=1
                else:raw['native'][0]['assessment']['setup_and_capture_ready']=False
                raw['unverified_capture_by_arm']['engine_medium']=1
                observed=15 if missing else 16
                known=usage(observed,capture_complete=False)
                known['unknown_usage_attempts']=0
                known['token_usage']={field:{'known_tokens':observed,'known_attempts':observed,'unknown_attempts':0}
                                      for field in dev.TOKEN_FIELDS}
                raw['native_usage']['engine_medium']=known
                value=dev.project(raw);dev.validate_public(value)
                native=value['native'];self.assertFalse(native['complete'])
                self.assertEqual(native['unverified_capture_by_arm']['engine_medium'],1)
                self.assertFalse(native['usage']['engine_medium']['capture_complete'])
                self.assertFalse(native['usage']['engine_medium']['usage_complete'])
                self.assertEqual(native['usage']['engine_medium']['token_usage']['total_tokens']['unknown_attempts'],0)
                bad=copy.deepcopy(value)
                bad['native']['usage']['engine_medium'].update(capture_complete=True,usage_complete=True)
                with self.assertRaises(ValueError):dev.validate_public(bad)

    def test_bad_capture_cannot_borrow_a_passing_judge_gate(self):
        raw=snapshot();raw['native'][16]['assessment']['request_uploaded']=1
        value=dev.project(raw);dev.validate_public(value)
        self.assertIsNone(value['results']);self.assertFalse(value['native']['complete'])

    def test_wrong_protocol_budget_scope_and_counts_are_rejected(self):
        mutations=(lambda x:x['quality'].update(protocol='native_owed_development_foreground_v1'),
            lambda x:x['quality'].update(started_attempts=391),
            lambda x:x['quality'].update(valid_judgments=129),
            lambda x:x['quality'].update(primary_pass=2),
            lambda x:x['quality']['retry_policy'].update(valid_verdict_final=False),
            lambda x:x['quality']['judge_usage'].update(request_sent_unknown_attempts=0))
        for mutate in mutations:
            raw=snapshot();mutate(raw)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):dev.project(raw)

    def test_public_schema_cannot_carry_private_data_or_claim_qualification(self):
        value=dev.project(snapshot())
        for mutate in (lambda x:x.update(path='/Users/PRIVATE'),lambda x:x.update(publication_ready=True),
                lambda x:x['judging'].update(raw_response='PRIVATE'),
                lambda x:x['results']['arms']['engine_medium'].update(parsed_json='PRIVATE'),
                lambda x:x['judging']['usage'].update(retained_receipts=141),
                lambda x:x['proof'].update(foreign_sha256='a'*64)):
            bad=copy.deepcopy(value);mutate(bad)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):dev.validate_public(bad)


class ColdBinding(unittest.TestCase):
    def make(self,root):
        prefix='serve/line_agent_v3/evals/always_on/'
        source=root/'source';directory=source/prefix;directory.mkdir(parents=True)
        for path in (source/'serve',source/'serve/line_agent_v3',source/'serve/line_agent_v3/evals',directory):
            (path/'__init__.py').write_text('')
        (directory/'owed_development.py').write_text("import json\nARMS=('engine_medium','engine_high','engine_sol_low')\ndef verify(root):return json.loads((root/'plan.private.json').read_text())\n")
        (directory/'owed_development_cases.json').write_text('{}')
        for name in ('owed_development_judge.py','judge.py','judge_foreground_rubric.md'):(directory/name).write_text('')
        (directory/'variant_config.py').write_text('def usage_summary(rows,**kwargs):\n value='+repr(usage(0))+
            '\n value.update(capture_complete=kwargs["capture_complete"],usage_complete=kwargs["capture_complete"])\n return value\n')
        inventory={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in source.rglob('*') if p.is_file()}
        trusted=copy.deepcopy(dev.TRUST)
        plan={'protocol':dev.PROTOCOL,'source_ref':trusted['source_ref'],'native_source_ref':trusted['native_source_ref'],
            'source_files':inventory,'configurations':trusted['configurations'],'settings':trusted['settings'],
            'configuration_sha256':trusted['proof']['configuration_sha256'],'execution_order':[]}
        (root/'receipts').mkdir();(root/'plan.private.json').write_text(json.dumps(plan,ensure_ascii=False))
        trusted['proof'].update(source_files_sha256=dev.digest(inventory),schedule_sha256=dev.digest([]),
            corpus_sha256=hashlib.sha256(b'{}').hexdigest(),plan_sha256=hashlib.sha256((root/'plan.private.json').read_bytes()).hexdigest(),
            canonical_plan_sha256=dev.digest(plan))
        for key,name in {'code_sha256':'owed_development.py','judge_export_code_sha256':'owed_development_judge.py',
                         'judge_sha256':'judge.py','rubric_sha256':'judge_foreground_rubric.md'}.items():
            trusted['proof'][key]=inventory[prefix+name]
        return trusted,plan,directory

    def test_intended_cold_plan_export_leaves_all_inputs_and_no_bytecode(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);trusted,_plan,_directory=self.make(root)
            before={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch.object(dev,'TRUST',trusted):value=dev.verified_projection(root)
            self.assertEqual((value['status'],value['native']['completed_cells']),('native_incomplete',0))
            after={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before,after);self.assertFalse(list(root.rglob('*.pyc')))

    def test_self_rehashed_foreign_code_never_imported(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);trusted,plan,directory=self.make(root);marker=root/'EXECUTED'
            (directory/'owed_development.py').write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n")
            plan['source_files']['serve/line_agent_v3/evals/always_on/owed_development.py']=hashlib.sha256((directory/'owed_development.py').read_bytes()).hexdigest()
            (root/'plan.private.json').write_text(json.dumps(plan))
            with patch.object(dev,'TRUST',trusted),self.assertRaises(ValueError):dev.verified_projection(root)
            self.assertFalse(marker.exists())

    def test_added_bytecode_extra_file_symlink_and_changed_plan_refuse(self):
        for kind in ('bytecode','extra','symlink','plan'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);trusted,_plan,directory=self.make(root)
                if kind=='symlink':(root/'source/foreign').symlink_to(directory,target_is_directory=True)
                elif kind=='plan':(root/'plan.private.json').write_text('{}')
                else:(directory/('foreign.pyc' if kind=='bytecode' else 'foreign.py')).write_bytes(b'foreign')
                with patch.object(dev,'TRUST',trusted),self.assertRaises(ValueError):dev.verified_projection(root)


class SeparateRendering(unittest.TestCase):
    def copy_public(self,target):
        source=Path(__file__).resolve().parents[1]/'public/line-v3'
        for path in source.glob('line-always-on*'):
            if path.is_file() and not path.name.startswith('line-always-on-owed-development-v2'):
                shutil.copy2(path,target/path.name)
        shutil.copytree(source/'always-on',target/'always-on')
        # Re-create the current two pages without the separate sidecar. The
        # original JSON and immutable iteration pages remain copied verbatim.
        with patch.object(renderer,'PUBLIC',target),patch('sys.argv',['renderer','--render']), \
                patch.object(renderer,'owed_development_v2_module',side_effect=AssertionError('absent v2 must not load')):
            renderer.main()

    def test_new_export_only_adds_v2_files_and_changes_current_two_html_pages(self):
        value=dev.project(snapshot())
        with tempfile.TemporaryDirectory() as temp:
            public=Path(temp);self.copy_public(public)
            before={p.relative_to(public).as_posix():p.read_bytes() for p in public.rglob('*') if p.is_file()}
            with patch.object(renderer,'PUBLIC',public),patch.object(renderer,'owed_development_v2_module',return_value=dev), \
                    patch.object(dev,'verified_projection',return_value=value), \
                    patch('sys.argv',['renderer','--render','--owed-development-v2-study','not-executed']):
                renderer.main()
            after={p.relative_to(public).as_posix():p.read_bytes() for p in public.rglob('*') if p.is_file()}
            changed=[name for name in before if before[name]!=after[name]]
            self.assertEqual(sorted(changed),sorted([renderer.METHOD_NAME,renderer.PAGE_NAME]))
            added=set(after)-set(before)
            self.assertEqual(len(added),2);self.assertIn(renderer.OWED_V2_NAME,added)
            for name in changed:
                text=after[name].decode()
                self.assertIn('全新欠答開發題組 · v2',text)
                self.assertIn('判讀已結束，未通過原定門檻',text)
                self.assertIn('技術嘗試共 142 次',text)
            self.assertEqual(json.loads(after[renderer.OWED_V2_NAME]),value)
            with patch.object(renderer,'PUBLIC',public),patch.object(renderer,'owed_development_v2_module',return_value=dev), \
                    patch('sys.argv',['renderer','--render']):renderer.main()
            self.assertEqual(after,{p.relative_to(public).as_posix():p.read_bytes() for p in public.rglob('*') if p.is_file()})

    def test_no_v2_input_preserves_old_json_and_immutable_pages_without_new_panel(self):
        with tempfile.TemporaryDirectory() as temp:
            public=Path(temp);self.copy_public(public)
            before={p.relative_to(public).as_posix():p.read_bytes() for p in public.rglob('*') if p.is_file()}
            with patch.object(renderer,'PUBLIC',public),patch('sys.argv',['renderer','--render']):renderer.main()
            after={p.relative_to(public).as_posix():p.read_bytes() for p in public.rglob('*') if p.is_file()}
            self.assertEqual(set(before),set(after))
            for name in before:
                if name not in (renderer.PAGE_NAME,renderer.METHOD_NAME):self.assertEqual(before[name],after[name])
            for name in (renderer.PAGE_NAME,renderer.METHOD_NAME):
                self.assertNotIn('全新欠答開發題組 · v2',after[name].decode())

    def test_unqualified_v2_exposes_spent_attempts_but_no_score_table(self):
        raw=snapshot();raw['quality']['controls'][0]['as_expected']=False
        raw['quality'].update(controls_passed=False,quality_ready=False)
        value=dev.project(raw)
        with patch.object(renderer,'owed_development_v2_module',return_value=dev):text=renderer.owed_development_v2_panel(value)
        self.assertIn('有效邏輯判讀：130/130',text)
        self.assertIn('符合預期的控制：33/34',text)
        self.assertIn('成績保留不公開',text)
        self.assertNotIn('<table',text)


if __name__=='__main__':unittest.main()
