"""Hermetic projection tests; synthetic freezes do not identify a real study."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dev = load('site_owed_followup_tests', 'owed_release_followup.py')
old = load('site_owed_followup_prior_tests', 'test_owed_development_v2.py')
renderer = old.renderer


def reviewed():
    binding = copy.deepcopy(old.dev.TRUST)
    binding.update(source_ref='b' * 40, native_source_ref='c' * 40)
    binding['settings']['reviewed_profile_setup'] = copy.deepcopy(dev.PROFILE_SETUP)
    binding['proof']['settings_sha256'] = dev.digest(binding['settings'])
    for key in ('source_files_sha256', 'plan_sha256', 'canonical_plan_sha256',
                'freeze_audit_sha256', 'code_sha256', 'judge_export_code_sha256'):
        binding['proof'][key] = 'e' * 64
    return {'protocol': dev.TRUST_PROTOCOL, 'status': 'reviewed', 'binding': {
        'v2': binding, 'profile_setup': copy.deepcopy(dev.PROFILE_SETUP),
        'reused_exporter_sha256': dev.BASE_EXPORTER_SHA256,
        'prior_v2_trust_sha256': dev.BASE_TRUST_SHA256}}


def projected(*, failed_control=False):
    module, prior = dev.trusted_module()
    raw = old.snapshot(errors=10, interrupted=2)
    raw['proof'].update(module.TRUST['proof'])
    if failed_control:
        raw['quality']['controls'][0]['as_expected'] = False
        raw['quality'].update(controls_passed=False, quality_ready=False)
    study = module.project(raw)
    by_arm = {arm: {'receipt_cells': 24, 'cells_with_calls': 16, 'observed_calls': 16, 'source_count': 32}
              for arm in module.ARMS}
    profile = {'declaration': copy.deepcopy(dev.PROFILE_SETUP), 'receipt_cells': 72,
        'cells_with_calls': 48, 'observed_calls': 48, 'source_count': 96, 'by_arm': by_arm, 'complete': True}
    return dev.project(study, {'profile': profile, 'profile_metadata_sha256': '4' * 64,
        'native_capture_sha256': study['proof']['native_capture_sha256']}, prior)


class Projection(unittest.TestCase):
    def test_null_final_freeze_blocks_before_any_archive_read_or_shared_import(self):
        awaiting = {'protocol':dev.TRUST_PROTOCOL,'status':'awaiting_reviewed_freeze','binding':None}
        with patch.object(dev,'TRUST',awaiting),patch.object(dev, '_base_module') as reused, \
                patch.object(dev, 'profile_snapshot') as read:
            with self.assertRaisesRegex(ValueError, 'reviewed_freeze_required'):
                dev.verified_projection(Path('/not-an-archive'))
        reused.assert_not_called()
        read.assert_not_called()

    def test_private_instance_preserves_the_original_617_trust_and_exporter(self):
        path = Path(dev.__file__).with_name('owed_development_v2_trust.json')
        before = path.read_bytes()
        original = copy.deepcopy(old.dev.TRUST)
        with patch.object(dev, 'TRUST', reviewed()):
            module, prior = dev.trusted_module()
            self.assertEqual(module.NATIVE_REF, 'c' * 40)
            self.assertEqual(prior, original)
            module.TRUST['source_ref'] = 'a' * 40
            fresh, _prior = dev.trusted_module()
            self.assertEqual(fresh.TRUST['source_ref'], 'b' * 40)
        self.assertEqual(old.dev.TRUST, original)
        self.assertEqual(path.read_bytes(), before)

    def test_reviewed_local_verifier_bytes_are_checked_before_loading(self):
        trust = reviewed();trust['binding']['reused_exporter_sha256'] = '0' * 64
        with patch.object(dev, 'TRUST', trust), patch.object(dev, 'BASE_EXPORTER_SHA256', '0' * 64), \
                patch.object(dev.importlib.util, 'spec_from_file_location') as execute:
            with self.assertRaisesRegex(ValueError, 'reused_verifier_changed'):dev.trusted_module()
        execute.assert_not_called()

    def test_changed_fixed_case_schedule_config_rubric_or_settings_cannot_be_rebound(self):
        for mutate in (lambda x:x['proof'].update(corpus_sha256='0'*64),
                lambda x:x['proof'].update(schedule_sha256='0'*64),
                lambda x:x['proof'].update(rubric_sha256='0'*64),
                lambda x:x['settings'].update(workers=2),
                lambda x:x['settings']['reviewed_profile_setup'].update(derivation_pass_limit=True),
                lambda x:x['settings']['reviewed_profile_setup'].pop('derivation_schedule'),
                lambda x:x['configurations']['engine_high'].update(timeout_s=121),
                lambda x:x.update(native_source_ref=old.dev.NATIVE_REF)):
            trust = reviewed();mutate(trust['binding']['v2'])
            with patch.object(dev, 'TRUST', trust), self.assertRaises(ValueError):dev.trusted_module()

    def test_all_failures_denominators_unknown_usage_and_first_pass_are_preserved(self):
        with patch.object(dev, 'TRUST', reviewed()):
            value = projected();dev.validate_public(value)
        self.assertTrue(value['quality_ready'])
        self.assertFalse(value['publication_ready']);self.assertFalse(value['held_out'])
        self.assertFalse(value['guard_only_causality']);self.assertFalse(value['pooled_with_prior_studies'])
        study = value['study']
        self.assertEqual((study['planned_cells'], study['positive_denominator'], study['withholding_denominator']), (72,48,24))
        self.assertEqual((study['planned_judge_jobs'],study['max_judge_calls'],study['max_combined_provider_calls']), (130,390,438))
        self.assertEqual(study['judging']['usage']['request_sent_unknown_attempts'], 2)
        self.assertEqual(study['judging']['usage']['token_usage']['total_tokens']['unknown_attempts'], 142)
        for row in study['results']['arms'].values():
            self.assertEqual(row['judgments'], {field:0 for field in old.dev.FIELDS})
            self.assertEqual((row['positive_denominator'],row['closures'],row['withholding_passed']), (16,16,8))
        for forbidden in ('PRIVATE','parsed_json','sources_sha256','slot','credential_read'):
            self.assertNotIn(forbidden, json.dumps(value))

    def test_a_valid_failed_control_withholds_results_without_a_favorable_retry(self):
        with patch.object(dev, 'TRUST', reviewed()):
            value = projected(failed_control=True);dev.validate_public(value)
        self.assertFalse(value['quality_ready'])
        self.assertIsNone(value['study']['results'])
        self.assertEqual(value['study']['judging']['valid_judgments'],130)
        self.assertEqual(value['study']['judging']['retryable_judgments'],0)

    def test_profile_completeness_and_private_fields_cannot_be_forged_publicly(self):
        with patch.object(dev, 'TRUST', reviewed()):
            value = projected()
            for mutate in (lambda x:x['profile_setup'].update(receipt_cells=71),
                    lambda x:x['profile_setup']['declaration'].update(quality_measured=0),
                    lambda x:x['profile_setup']['by_arm']['engine_medium'].update(cells_with_calls=0),
                    lambda x:x.update(private_id='secret'),lambda x:x.update(publication_ready=True)):
                bad = copy.deepcopy(value);mutate(bad)
                with self.assertRaises(ValueError):dev.validate_public(bad)

    def test_capture_recheck_prevents_mixed_receipt_snapshots(self):
        with patch.object(dev, 'TRUST', reviewed()):
            value = projected();module,prior = dev.trusted_module()
            profile = {'profile':value['profile_setup'],'profile_metadata_sha256':'4'*64,'native_capture_sha256':'0'*64}
            with self.assertRaisesRegex(ValueError,'capture_changed'):dev.project(value['study'],profile,prior)

    def test_optional_section_is_separate_on_both_current_pages_without_extra_tabs(self):
        prior = json.loads((renderer.PUBLIC/renderer.OWED_V2_NAME).read_text())
        old_html = renderer.owed_development_v2_panel(prior)
        cases = json.loads((renderer.PUBLIC/renderer.CASES_NAME).read_text())
        with patch.object(dev,'TRUST',reviewed()),patch.object(renderer,'owed_release_followup_module',return_value=dev):
            value = projected()
            method = renderer.render_method(cases,owed_development_v2=prior,owed_release_followup=value)
            result = renderer.render({'status':'pending'},owed_development_v2=prior,owed_release_followup=value)
            for page in (method,result):
                self.assertIn(old_html,page)
                self.assertIn('整合釋出版本 · 獨立欠答追蹤',page)
                self.assertIn(dev.ALIAS,page)
                self.assertIn('不是 holdout',page)
                self.assertIn('不能把跨輪變化單獨歸因',page)
                self.assertIn('未知',page)
                self.assertIn('每次最多 64 輪',page)
                self.assertIn('派生錯誤使設定不合格',page)
                self.assertIn('既有固定 5／6 腳本',page)
        self.assertEqual(renderer.owed_development_v2_panel(prior),old_html)
        self.assertEqual(renderer.owed_release_followup_panel(None),'')


class ProfileReceipts(unittest.TestCase):
    def fixture(self, root):
        prompt = root/'source/serve/memory/prompts/line_owed_answer_zh.txt'
        prompt.parent.mkdir(parents=True);prompt.write_bytes(b'synthetic prompt only')
        (root/'receipts').mkdir()
        order = [{'slot':f'synthetic-{arm}-{i}', 'arm':arm} for arm in old.dev.ARMS for i in range(24)]
        plan = {'settings':{'reviewed_profile_setup':copy.deepcopy(dev.PROFILE_SETUP)},'execution_order':order}
        wire = json.dumps(plan).encode();(root/'plan.private.json').write_bytes(wire)
        binding = {'proof':{'plan_sha256':dev.sha(wire),'canonical_plan_sha256':dev.digest(plan)}}
        for item in order:
            row = {'development_boundary':{'blocked':[],'reviewed_profile_setup':{
                'declaration':copy.deepcopy(dev.PROFILE_SETUP),'installed':True,'calls':[]}},
                'parsed_json':'PRIVATE TEXT NOT EXPORTED'}
            (root/'receipts'/(item['slot']+'.json')).write_text(json.dumps(row))
        return plan,binding,dev.sha(prompt.read_bytes())

    def test_installed_zero_call_cells_are_valid_without_invented_lane_exposure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,binding,prompt_sha=self.fixture(root)
            with patch.object(dev,'OWED_PROMPT_SHA256',prompt_sha):value=dev.profile_snapshot(root,binding)
        self.assertEqual((value['profile']['receipt_cells'],value['profile']['observed_calls']), (72,0))
        self.assertTrue(value['profile']['complete'])
        self.assertNotIn('PRIVATE',json.dumps(value))

    def test_native_flat_and_package_calls_are_aggregated_without_source_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,binding,prompt_sha=self.fixture(root)
            path=root/'receipts'/(plan['execution_order'][0]['slot']+'.json');row=json.loads(path.read_text())
            row['development_boundary']['reviewed_profile_setup']['calls']=[{
                'module':name,'source_count':2,'sources_sha256':'7'*64,'code':'empty_reviewed_profile_setup',
                'credential_read':False,'real_socket_upload':False}
                for name in ('durable_profile','serve.memory.durable_profile')]
            path.write_text(json.dumps(row))
            with patch.object(dev,'OWED_PROMPT_SHA256',prompt_sha):value=dev.profile_snapshot(root,binding)
        self.assertEqual((value['profile']['cells_with_calls'],value['profile']['observed_calls'],value['profile']['source_count']),(1,2,4))
        self.assertNotIn('7'*64,json.dumps(value))

    def test_profile_escapes_bad_sources_and_uninstalled_or_mistyped_attestations_fail_closed(self):
        def valid_call():return {'module':'durable_profile','source_count':1,'sources_sha256':'7'*64,
            'code':'empty_reviewed_profile_setup','credential_read':False,'real_socket_upload':False}
        mutations=(lambda b:b.update(blocked=['unexpected_memory_profile_provider_or_credential']),
            lambda b:b['reviewed_profile_setup'].update(installed=False),
            lambda b:b['reviewed_profile_setup']['declaration'].update(version=True),
            lambda b:b['reviewed_profile_setup']['declaration'].update(application_factory='browser_fixture'),
            lambda b:b['reviewed_profile_setup']['declaration'].update(derivation_driver='direct_sql'),
            lambda b:b['reviewed_profile_setup']['declaration'].pop('derivation_schedule'),
            lambda b:b['reviewed_profile_setup']['declaration'].update(derivation_pass_limit=True),
            lambda b:b['reviewed_profile_setup']['declaration'].update(summary_provider_stage='real_provider'),
            lambda b:b['reviewed_profile_setup']['declaration'].update(derivation_errors='ignore'),
            lambda b:b['reviewed_profile_setup']['calls'][0].update(credential_read=True),
            lambda b:b['reviewed_profile_setup']['calls'][0].update(real_socket_upload=True),
            lambda b:b['reviewed_profile_setup']['calls'][0].update(source_count=True),
            lambda b:b['reviewed_profile_setup']['calls'][0].update(sources_sha256='bad'))
        for mutate in mutations:
            with self.subTest(mutate=mutate),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);plan,binding,prompt_sha=self.fixture(root)
                path=root/'receipts'/(plan['execution_order'][0]['slot']+'.json');row=json.loads(path.read_text())
                row['development_boundary']['reviewed_profile_setup']['calls']=[valid_call()]
                mutate(row['development_boundary']);path.write_text(json.dumps(row))
                with patch.object(dev,'OWED_PROMPT_SHA256',prompt_sha),self.assertRaises(ValueError):
                    dev.profile_snapshot(root,binding)


if __name__ == '__main__':unittest.main()
