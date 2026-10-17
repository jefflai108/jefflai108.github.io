"""Synthetic ER public-projection boundaries; never use real benchmark archives."""
from copy import deepcopy
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


er = load('er_projection_tests', 'm6_explicit_recurring.py')
renderer = load('er_renderer_tests', 'render-line-always-on.py')
base = er.base


def proof():
    return {**er.REFS, **{k: 'b'*64 for k in er.PIN_KEYS-er.REFS.keys()}}


def fixture(*, proactive=False):
    cells = []
    for slot in er.SCHEDULE:
        cells.append({'scenario': slot['case'], 'repeat': slot['repeat'], 'account': slot['account'],
            'status': 'complete', 'horizon_complete': True, 'capture_complete': True, 'profile_available': True,
            'request_context_available': True, 'offer_stratum': 'no_current_offer', 'request_foreground_sent': 1,
            'checkin_capture_complete': True, 'checkin_observed': 1, 'checkin_projectable_records': 1,
            'reserved_attempts': 2, 'actual_http_attempts': 2, 'request_sent_unknown_attempts': 0})
    foreground = dict.fromkeys(base.FOREGROUND_FIELDS, None)
    foreground.update(answered=True, no_rejection=True, honest=False, grounded=False)
    profile = dict.fromkeys(base.PROFILE_FIELDS, True)
    primary = {'foreground': [deepcopy(foreground) for _ in cells], 'profile': [deepcopy(profile) for _ in cells],
               'proactive': []}
    if proactive:
        primary['proactive'] = [{**dict.fromkeys(base.PROACTIVE_FIELDS, True),
                                **dict.fromkeys(base.SCORE_FIELDS, 3)}]
    planned = 2*sum(map(len, primary.values()))
    judging = {'quality_ready': True, 'logical_jobs': 94+planned, 'valid_jobs': 94+planned,
        'started_attempts': 94+planned+1, 'technical_errors': 1, 'interrupted_attempts': 0,
        'valid_controls': 94, 'matched_controls': 94, 'failed_controls': 0,
        'candidate_jobs': {'planned': planned, 'started': planned, 'valid': planned},
        'calibration_status': 'qualified', 'controls_qualified': True,
        'usage': base._usage([{'total_tokens': 11}]*(94+planned)+[None]), 'primary': primary,
        'second_pass_consistency': {p: {'paired_packets': len(rows), 'same_flags': 0 if p == 'foreground' else len(rows)}
                                    for p, rows in primary.items()}}
    return cells, [{'total_tokens': 7}]*8, judging


def projected(**kwargs):
    cells, usage, judging = fixture(**kwargs)
    return er.project(cells, usage, judging, proof=proof())


class Projection(unittest.TestCase):
    def test_pending_has_four_unexported_cells_and_null_trust_precedes_all_private_access(self):
        value = er.pending_projection()
        self.assertEqual(4, len(value['cells']))
        self.assertTrue(all(r['request_context_available'] is None for r in value['cells']))
        self.assertIsNone(value['native']); self.assertIsNone(value['judging'])
        waiting = {'protocol': er.TRUST_PROTOCOL, 'status': 'awaiting_reviewed_freeze', 'binding': None}
        old = deepcopy(base.TRUST)
        with patch.object(er, 'TRUST', waiting), patch.object(er, 'inventory') as read, patch.object(base, '_summary') as cli:
            with self.assertRaisesRegex(ValueError, 'reviewed_terminal_freeze_required'):
                er.verified_projection('/never/read/native', '/never/read/judge')
        read.assert_not_called(); cli.assert_not_called(); self.assertEqual(old, base.TRUST)

    def test_exact_iteration_source_cannot_accept_old_J8_or_changed_native(self):
        trust = {'protocol': er.TRUST_PROTOCOL, 'status': 'reviewed', 'binding': proof()}
        with patch.object(er, 'TRUST', trust): self.assertEqual(proof(), er.trusted())
        for key in er.REFS:
            bad = deepcopy(trust); bad['binding'][key] = 'a'*40
            with self.subTest(key=key), patch.object(er, 'TRUST', bad), self.assertRaisesRegex(ValueError, 'wrong_iteration'):
                er.trusted()

    def test_zero_N_strata_and_actual_adverse_primary_are_preserved_without_mutating_input(self):
        cells, usage, judging = fixture(); before = deepcopy((cells, usage, judging))
        value = er.project(cells, usage, judging, proof=proof())
        self.assertEqual(before, (cells, usage, judging))
        self.assertEqual({'observed_cells': 0, 'complete_cells': 0, 'model_exposed_cells': 0}, value['strata'][er.STRATA[0]])
        self.assertEqual(4, value['strata']['no_current_offer']['observed_cells'])
        self.assertEqual(4, value['judging']['phases']['foreground']['flags']['honest']['false'])
        self.assertTrue(value['quality_ready'])  # Availability/calibration, not all-positive quality.
        self.assertEqual(0, value['judging']['phases']['proactive']['primary_units'])
        self.assertEqual(1, value['judging']['usage']['total_tokens']['unknown_attempts'])
        self.assertEqual(8, value['native']['actual_http_attempts'])

    def test_valid_failed_calibration_is_distinct_from_technical_errors_and_has_no_candidate_score(self):
        cells, usage, judging = fixture()
        judging.update(quality_ready=False, valid_jobs=94, started_attempts=94, technical_errors=0,
            matched_controls=93, failed_controls=1, controls_qualified=False,
            calibration_status='failed_valid_final', usage=base._usage([None]*94),
            candidate_jobs={'planned': 16, 'started': 0, 'valid': 0},
            primary={p: [] for p in base.PHASES},
            second_pass_consistency={p: {'paired_packets': 0, 'same_flags': 0} for p in base.PHASES})
        value = er.project(cells, usage, judging, proof=proof())
        html = renderer.m6_er_panel(value)
        self.assertIn('已確定未通過', html); self.assertIn('AI 品質不可判定', html)
        self.assertIn('未判讀／不可判定', html)
        self.assertNotIn('誠實 0/0', html)
        value['judging']['candidate_jobs']['started'] = 1
        with self.assertRaises(ValueError): er.validate_public(value)

    def test_interrupted_cell_retains_spent_attempt_and_usage_uncertainty(self):
        cells, usage, judging = fixture()
        cells[0].update(status='interrupted', horizon_complete=False, capture_complete=False, profile_available=False,
            request_context_available=False, offer_stratum='other_or_unavailable', request_foreground_sent=0,
            checkin_capture_complete=False, checkin_observed=None, checkin_projectable_records=0,
            actual_http_attempts=0, request_sent_unknown_attempts=2)
        judging['quality_ready'] = False
        judging['primary']['profile'] = judging['primary']['profile'][1:]
        judging['second_pass_consistency']['profile'] = {'paired_packets': 3, 'same_flags': 3}
        value = er.project(cells, [None, None]+usage[2:], judging, proof=proof())
        self.assertFalse(value['native']['usage_capture_complete'])
        self.assertEqual(2, value['native']['request_sent_unknown_attempts'])
        self.assertEqual(2, value['native']['usage']['total_tokens']['unknown_attempts'])
        self.assertEqual(0, value['strata']['other_or_unavailable']['observed_cells'])
        value.update(status='qualified', quality_ready=True)
        with self.assertRaisesRegex(ValueError, 'invalid_readiness'): er.validate_public(value)

    def test_finished_transport_error_stays_unknown_but_exact_pretransport_denial_is_not_uploaded(self):
        transport = {'request_sent': False, 'finished': True, 'outcome': 'transport_error'}
        denied = {'request_sent': False, 'finished': True, 'outcome': 'wire_policy_denied_before_transport'}
        self.assertEqual({'reserved_attempts': 1, 'actual_http_attempts': 0,
                          'request_sent_unknown_attempts': 1}, er._attempts([transport]))
        self.assertEqual({'reserved_attempts': 1, 'actual_http_attempts': 0,
                          'request_sent_unknown_attempts': 0}, er._attempts([denied]))
        self.assertEqual({'reserved_attempts': 2, 'actual_http_attempts': 1,
                          'request_sent_unknown_attempts': 1}, er._attempts([transport,
                              {'request_sent': True, 'finished': False, 'outcome': 'interrupted'}]))
        with self.assertRaisesRegex(ValueError, 'invalid_pretransport_denial'):
            er._attempts([{**denied, 'request_sent': True}])

    def test_missing_host_capture_exports_an_explicit_incomplete_cell(self):
        cells, usage, judging = fixture()
        available = {**cells[0], 'stop_code': None, 'checkin_capture_complete': False}
        before = deepcopy(available)
        cells[0].update(status=er._cell_status(available, has_receipt=True, started=True),
                        checkin_capture_complete=False)
        judging['quality_ready'] = False
        value = er.project(cells, usage, judging, proof=proof())
        self.assertEqual('incomplete', value['cells'][0]['status'])
        self.assertFalse(value['quality_ready'])
        self.assertEqual(before, available)
        self.assertEqual('complete', er._cell_status({**available, 'checkin_capture_complete': True},
                                                    has_receipt=True, started=True))
        self.assertEqual('interrupted', er._cell_status(available, has_receipt=False, started=True))

    def test_closed_public_shape_counters_and_account_scopes_reject_malformed_values(self):
        for mutate in (lambda v: v['cells'][0].update(repeat=True),
                lambda v: v['cells'][0].update(account='private-owner'),
                lambda v: v['cells'][0].update(checkin_projectable_records=2),
                lambda v: v['cells'][0].update(offer_stratum='assigned_offer'),
                lambda v: v['strata']['no_current_offer'].update(observed_cells=0),
                lambda v: v['judging'].update(control_jobs=70),
                lambda v: v['judging'].update(max_logical_jobs=182),
                lambda v: v['native']['usage']['total_tokens'].update(known_attempts=0, unknown_attempts=8, observed_tokens=0),
                lambda v: v.update(raw_prompt='PRIVATE')):
            value = projected(); mutate(value)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): er.validate_public(value)

    def test_runtime_bytecode_is_opaque_and_changed_or_unpinned_bytes_stop_before_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            cache = root/'receipts/ER01.repeat1.primary/hermes-secondary.pycache-df589e84876803a1c5c9194fddcf2db2/Users/example/state.cpython-313.pyc'
            cache.parent.mkdir(parents=True); cache.write_bytes(b'opaque runtime bytes')
            original = er.inventory(root)
            trust = {'protocol': er.TRUST_PROTOCOL, 'status': 'reviewed', 'binding': proof()}
            trust['binding'].update(native_files_sha256=base.digest(original), judge_files_sha256=base.digest(original))
            cache.write_bytes(b'changed opaque runtime bytes')
            with patch.object(er, 'TRUST', trust), patch.object(base, '_summary') as cli:
                with self.assertRaisesRegex(ValueError, 'untrusted_inventory'): er.verified_projection(root, root)
            cli.assert_not_called()
            trust['binding']['native_files_sha256'] = base.digest({})
            with patch.object(er, 'TRUST', trust), patch.object(base, '_summary') as cli:
                with self.assertRaisesRegex(ValueError, 'untrusted_inventory'): er.verified_projection(root, root)
            cli.assert_not_called()

    def test_source_inputs_malformed_cache_links_and_special_files_are_never_runtime_exceptions(self):
        for relative in ('source/module.pyc', 'inputs/__pycache__/module.pyc',
                'receipts/ER01.repeat3.primary/hermes-secondary.pycache-'+'a'*32+'/module.pyc',
                'receipts/ER01.repeat1.primary/hermes-secondary.pycache-'+'a'*32+'suffix/module.pyc'):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve(); path = root/relative
                path.parent.mkdir(parents=True); path.write_bytes(b'not executable authority')
                with self.subTest(relative=relative), self.assertRaisesRegex(ValueError, 'untrusted_archive_entry'):
                    er.inventory(root)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); (root/'link').symlink_to('/never/read')
            with self.assertRaisesRegex(ValueError, 'untrusted_archive_entry'): er.inventory(root)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); os.mkfifo(root/'special')
            with self.assertRaisesRegex(ValueError, 'untrusted_archive_entry'): er.inventory(root)

    def test_actual_claim_receipt_accounting_preserves_valid_control_failure_and_spent_errors(self):
        legacy = load('er_accounting_predicate_fixture', 'test_m6_profile_diagnostic.py')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); source = root/'source'/base.PREFIX
            source.mkdir(parents=True); receipts = root/'receipts'; receipts.mkdir()
            for filename, text in legacy.predicate_sources().items(): (source/filename).write_text(text)
            controls = [{'id': 'synthetic-'+str(i), 'phase': 'profile', 'expect': {'coverage': True}} for i in range(47)]
            (root/'controls.json').write_text(json.dumps(controls))
            jobs = []
            for control in controls:
                for pass_id in (1, 2):
                    key = control['id']+'.p'+str(pass_id)
                    jobs.append({'id': key, 'packet': control['id'], 'control': True})
                    (receipts/(key+'.a1.started.json')).write_text('{}')
                    (receipts/(key+'.a1.json')).write_text(json.dumps({'status': 'ok',
                        'verdict': {'coverage': not (control is controls[-1] and pass_id == 2)}, 'usage': {'total_tokens': 2}}))
            jobs.append({'id': 'candidate.p1', 'packet': 'candidate', 'control': False})
            (receipts/'candidate.p1.a1.started.json').write_text('{}')
            (receipts/'candidate.p1.a1.json').write_text(json.dumps({'status': 'error', 'usage': None}))
            (receipts/'candidate.p1.a2.started.json').write_text('{}')
            # This private fixture deliberately exercises accounting in isolation;
            # verified_projection separately rejects pre-calibration candidates.
            row = er._accounting(root, {'jobs': jobs}, {'started_attempts': 96, 'valid_jobs': 94, 'controls_qualified': False})
            self.assertEqual((94, 93, 1), (row['valid_controls'], row['matched_controls'], row['failed_controls']))
            self.assertEqual((1, 1), (row['technical_errors'], row['interrupted_attempts']))
            self.assertEqual('failed_valid_final', row['calibration_status'])
            self.assertEqual(2, row['usage']['total_tokens']['unknown_attempts'])

    def test_both_tabs_append_same_panel_preserve_old_output_when_absent_and_keep_existing_width(self):
        legacy = load('er_legacy_renderer_fixture', 'test_m6_profile_diagnostic.py')
        old = legacy.projected()
        cases = json.loads((renderer.PUBLIC/renderer.CASES_NAME).read_text())
        report = json.loads((renderer.PUBLIC/renderer.JSON_NAME).read_text())
        report_before = deepcopy(report)
        args = {'m6_profile_diagnostic': old}
        original_result = renderer.render(report, **args)
        original_method = renderer.render_method(cases, **args)
        self.assertEqual(original_result, renderer.render(report, m6_explicit_recurring=None, **args))
        self.assertEqual(original_method, renderer.render_method(cases, m6_explicit_recurring=None, **args))
        value = projected(proactive=True); panel = renderer.m6_er_panel(value)
        self.assertIn(panel, renderer.render(report, m6_explicit_recurring=value, **args))
        self.assertIn(panel, renderer.render_method(cases, m6_explicit_recurring=value, **args))
        self.assertIn('時機', panel); self.assertIn('3 / 5（N=1）', panel)
        self.assertIn('零樣本層仍保留', panel); self.assertIn('repeat 2 · secondary', panel)
        self.assertNotIn('raw_prompt', panel); self.assertIn('class="scroll"', panel)
        self.assertEqual(report_before, report)
        self.assertNotIn('style=', panel)  # Use unchanged shared widths and table scrolling.
        self.assertIn('.scroll{overflow-x:auto;max-width:100%}', renderer.CSS)


if __name__ == '__main__': unittest.main()
