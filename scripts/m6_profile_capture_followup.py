"""Separate, public-safe projection of the operation/time capture follow-up.

Only reviewed terminal inventory digests may enable the intended offline summary
CLIs. The earlier diagnostic and its trust are never repinned or modified here.
Run exports with a scrubbed environment and inherited OS network denial.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path


def _base_module():
    spec = importlib.util.spec_from_file_location('site_m6_followup_helpers',
        Path(__file__).with_name('m6_profile_diagnostic.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _base_module()
TRUST_PROTOCOL = 'm6_profile_capture_followup_trust_v1'
PROTOCOL = 'm6_profile_capture_clock_followup_public_v1'
NATIVE_PROTOCOL = 'native_m6_profile_pv41_46_development_v1'
JUDGE_PROTOCOL = 'native_m6_profile_pv41_46_judging_v2'
ALIAS = 'line-always-on-m6-profile-capture-followup.public.json'
TRUST = json.loads(Path(__file__).with_name('m6_profile_capture_followup_trust.json').read_text())
REFS = {'native_ref': 'f20ced6884ccc39a93889bd56c8fb2e8f77d8d44',
        'helper_ref': '7e35eb4451c7c7dd76a970353305ce78f4b18e40',
        'evaluator_ref': 'e2b9b4994d7df593d195fe94b2269215c1bc885c'}
CONTROL_COUNTS = {'foreground': 25, 'proactive': 10, 'profile': 12}
CONTROL_JOBS, MAX_LOGICAL_JOBS, MAX_JUDGE_REQUESTS = 94, 182, 546
PIN_KEYS = {*REFS, 'plan_sha256', 'judge_binding_sha256', 'native_files_sha256',
            'judge_files_sha256', 'native_seal_sha256', 'judge_seal_sha256'}
HISTORY = [
    {'label': 'H2／J5 原始診斷', 'file': 'line-always-on-m6-profile-diagnostic-9cbbbfaaea55.public.json',
     'sha256': '9cbbbfaaea5551596a42b76a56e76a6cdc7bb593becc8949c6e6da1f6eb6bb5e'},
    {'label': 'J3 原始未通過校準', 'file': 'line-always-on-m6-profile-diagnostic-1080f6affbe1.public.json',
     'sha256': '1080f6affbe1d1e6b6bf36a17aa3d3cf9115bf9d31ef3ee9403f7f9f3ea108b9'},
    {'label': 'J4 原始未通過校準', 'file': 'line-always-on-m6-profile-diagnostic-fd29e6f9b4be.public.json',
     'sha256': 'fd29e6f9b4be94c52007b0392563daaefcff3592d74fa81beb588835f5c82213'},
    {'label': 'J7 原始未通過校準', 'file': 'line-always-on-m6-profile-capture-followup-02e3bf552486.public.json',
     'sha256': '02e3bf552486adea209cc736e13e5a50e80335467c83136ff9d9e957b09e7d95'}]
EVIDENCE = {'host_outcomes': 'matching_owner_account_chat_source_before_send',
            'profile_time': 'native_source_taipei_and_actual_request_asof',
            'model_promise_is_operation_proof': False, 'single_change_causal_ablation': False}
LIMITS = ('原始 PV41–46，各兩個合成帳號，共 12 個獨立開發 cells；不作模型排名或未見題目泛化結論。'
          '相對較早診斷，同時更換原生引擎及補齊操作與時間證據，不能把結果差異歸因於單一修正。'
          '本次只澄清專用前景評審的「回應涵蓋」，不代表操作成功，誠實與依據標準不變；這是已檢視控制後的開發修訂。'
          '沿用與 J7 相同的原生捕捉，不重跑或重複加總原生用量。'
          'J7 原始校準 93/94、候選判讀 0 次、已知 AI 判讀總用量 245,667 tokens 獨立保留。'
          '原始對話同時可見，不能把回憶歸因於 profile。可選邀請不製造曝光，主動品質只以實際訊息為分母。'
          '第 1 輪為主要判讀，第 2 輪只報一致性；94 個控制判讀先於候選，有效負評與失敗控制皆為最終結果。'
          '未完成或不可用不當成通過，未知用量不當成零；舊輪原始判讀與成本獨立保留，不重算或合併。')
CELL_KEYS = {'scenario', 'account', 'status', 'horizon_complete', 'capture_complete', 'profile_available',
             'foreground_expectation_origin', 'original_bounds', 'observed_tick_sends', 'send_observation',
             'original_outcome', 'required_window_outcome', 'checkin_capture_complete',
             'checkin_observed', 'checkin_projectable_records'}


def trusted():
    if type(TRUST) is not dict or set(TRUST) != {'protocol', 'status', 'binding'} \
            or TRUST['protocol'] != TRUST_PROTOCOL or TRUST['status'] != 'reviewed' \
            or type(TRUST['binding']) is not dict or set(TRUST['binding']) != PIN_KEYS:
        raise ValueError('m6_followup_reviewed_freeze_required')
    pins = TRUST['binding']
    if any(pins[key] != ref for key, ref in REFS.items()):
        raise ValueError('m6_followup_wrong_iteration')
    for key, value in pins.items(): base._hash(value, 40 if key.endswith('_ref') else 64)
    return deepcopy(pins)


def pending_projection():
    return {'schema_version': 1, 'kind': PROTOCOL, 'status': 'awaiting_reviewed_freeze',
        'planned_cells': 12, 'policy_count': 1, 'cohort': 'synthetic_development',
        'publication_ready': False, 'quality_ready': False,
        'cells': [{'scenario': s, 'account': a, 'status': 'not_exported',
                   **dict.fromkeys(sorted(CELL_KEYS-{'scenario', 'account', 'status'}))}
                  for s in base.SCENARIOS for a in base.ACCOUNTS],
        'native': None, 'judging': None, 'proof': None, 'evidence_contract': deepcopy(EVIDENCE),
        'history': deepcopy(HISTORY), 'limits': LIMITS}


def _accounting(judge, binding, summary):
    # The frozen summary has already validated every request, claim and receipt.
    # Pin the pure comparisons before mirroring their results as public counts.
    base._check_control_predicates(judge)
    if any(binding.get(k) is not True for k in
           ('valid_verdict_final', 'control_failed_valid_final', 'calibrate_before_candidates')):
        raise ValueError('m6_followup_finality_changed')
    rows = json.loads(base._plain(judge/'controls.json'))
    controls = {r['id']: r for r in rows}
    if len(rows) != 47 or len(controls) != 47 or {p: sum(r['phase'] == p for r in rows)
            for p in base.PHASES} != CONTROL_COUNTS \
            or len({j['id'] for j in binding['jobs']}) != len(binding['jobs']):
        raise ValueError('m6_followup_control_denominator_changed')
    usage, errors, interrupted, valid_controls, matched, started_candidates, valid_candidates = [], 0, 0, 0, 0, 0, 0
    for job in binding['jobs']:
        valid, started = None, False
        for attempt in (1, 2, 3):
            stem = judge/'receipts'/(job['id']+'.a'+str(attempt))
            claim, receipt = Path(str(stem)+'.started.json'), Path(str(stem)+'.json')
            if not claim.exists(): continue
            started = True
            row = json.loads(base._plain(receipt)) if receipt.exists() else None
            usage.append(row.get('usage') if row else None)
            interrupted += row is None
            errors += row is not None and row['status'] == 'error'
            if row is not None and row['status'] == 'ok':
                if valid is not None: raise ValueError('m6_followup_valid_verdict_replaced')
                valid = row
        if job['control']:
            if valid is not None:
                valid_controls += 1
                matched += base._control_passed(controls[job['packet']], valid['verdict'])
        else:
            started_candidates += started
            valid_candidates += valid is not None
    if len(usage) != summary['started_attempts'] or valid_controls+valid_candidates != summary['valid_jobs'] \
            or summary['controls_qualified'] is not (matched == CONTROL_JOBS):
        raise ValueError('m6_followup_attempt_accounting_changed')
    return {'usage': usage, 'technical_errors': errors, 'interrupted_attempts': interrupted,
        'valid_controls': valid_controls, 'matched_controls': matched, 'failed_controls': valid_controls-matched,
        'candidate_jobs': {'planned': sum(j['control'] is False for j in binding['jobs']),
                           'started': started_candidates, 'valid': valid_candidates},
        'calibration_status': 'qualified' if matched == CONTROL_JOBS else
                              'failed_valid_final' if valid_controls == CONTROL_JOBS else 'pending'}


def project(native, judging, *, proof):
    value = pending_projection()
    value.update(status='qualified' if judging['quality_ready'] else 'incomplete', quality_ready=judging['quality_ready'])
    value['cells'] = [{k: row[k] for k in sorted(CELL_KEYS)} for row in native['cells']]
    value['native'] = {'provider_attempts': native['provider_attempts'], 'request_ceiling': 758,
        'complete_horizons': sum(r['horizon_complete'] for r in value['cells']),
        'profile_available_cells': sum(r['profile_available'] for r in value['cells']),
        'checkin_capture_complete_cells': sum(r['checkin_capture_complete'] for r in value['cells']),
        'usage': base._usage(native['usage']),
        'required_windows': {'planned_cells': 4, **{k: sum(r['required_window_outcome'] == k for r in value['cells'])
                                                  for k in ('hit', 'completed_miss', 'unavailable')}}}
    value['judging'] = {k: judging[k] for k in ('logical_jobs', 'valid_jobs', 'started_attempts',
        'technical_errors', 'interrupted_attempts', 'valid_controls', 'matched_controls', 'failed_controls',
        'candidate_jobs', 'calibration_status', 'controls_qualified')}
    value['judging'].update(control_jobs=CONTROL_JOBS, control_counts=deepcopy(CONTROL_COUNTS),
        primary_pass=1, consistency_pass=2, max_attempts_per_job=3, max_logical_jobs=MAX_LOGICAL_JOBS,
        request_ceiling=MAX_JUDGE_REQUESTS, calibration_before_candidates=True,
        usage=base._usage(judging['usage']), phases={p: base._phase(judging['primary'][p], p) for p in base.PHASES},
        consistency=deepcopy(judging['consistency']))
    value['proof'] = deepcopy(proof)
    return validate_public(value)


def verified_projection(study, judge):
    pins = trusted()  # Before any caller-controlled path read or CLI execution.
    study, judge = Path(study), Path(judge)
    before = base.inventory(study), base.inventory(judge)
    if tuple(base.digest(v) for v in before) != (pins['native_files_sha256'], pins['judge_files_sha256']):
        raise ValueError('m6_followup_untrusted_inventory')
    base._require_source_paths(*before)
    for files in before:
        if any('source/'+p not in files for p in
               ('serve/line_agent_v3/checkins.py', 'serve/memory/durable_profile.py')):
            raise ValueError('m6_followup_incomplete_evidence_source')
    if 'source/'+base.PREFIX+'m6_foreground_rubric.md' not in before[1]:
        raise ValueError('m6_followup_incomplete_foreground_rubric_source')
    plan, binding = (json.loads(base._plain(p)) for p in (study/'plan.json', judge/'binding.json'))
    if base.sha(base._plain(study/'plan.json')) != pins['plan_sha256'] \
            or base.sha(base._plain(judge/'binding.json')) != pins['judge_binding_sha256'] \
            or plan.get('native_ref') != pins['native_ref'] or plan.get('source_ref') != pins['helper_ref'] \
            or any(binding.get(k) != pins[v] for k, v in
                   (('native_source_ref', 'native_ref'), ('helper_ref', 'helper_ref'), ('evaluator_source_ref', 'evaluator_ref'),
                    ('native_plan_sha256', 'plan_sha256'))) \
            or Path(binding.get('original_study', '')).absolute() != study.absolute():
        raise ValueError('m6_followup_source_binding_changed')
    fixed = {'protocol': JUDGE_PROTOCOL, 'passes': 2, 'primary_pass': 1, 'max_attempts_per_job': 3,
        'judge_model': 'gpt-6-sol', 'reasoning': 'high', 'max_output_tokens': 32768, 'timeout_s': 120,
        'store': False, 'controls': 47, 'control_counts': CONTROL_COUNTS,
        'max_logical_jobs': MAX_LOGICAL_JOBS, 'max_provider_calls': MAX_JUDGE_REQUESTS}
    if any(base.digest(binding.get(k)) != base.digest(v) for k, v in fixed.items()):
        raise ValueError('m6_followup_judge_contract_changed')
    for name, pin in binding['original_input_files'].items():
        if base.sha(base._plain(study/name)) != pin or base._plain(study/name) != base._plain(judge/'inputs'/name):
            raise ValueError('m6_followup_original_copy_changed')
    origins = base._foreground_origins(json.loads(base._plain(study/'cases.json')))
    ns = base._summary(study, 'm6_profile_pilot.py', ['--study', str(study), '--plan-sha256', pins['plan_sha256']])
    js = base._summary(judge, 'm6_profile_judge.py', ['--out', str(judge), '--binding-sha256', pins['judge_binding_sha256']])
    if ns['protocol'] != NATIVE_PROTOCOL or js['protocol'] != JUDGE_PROTOCOL \
            or ns['planned_cells'] != 12 or js['planned_cells'] != 12 \
            or js['control_jobs'] != CONTROL_JOBS or len(binding['jobs']) != js['logical_jobs'] \
            or sum(j['control'] is True for j in binding['jobs']) != CONTROL_JOBS:
        raise ValueError('m6_followup_protocol_or_denominator_changed')
    schedule, available = plan['schedule'], js['availability']
    if type(available) is not dict or set(available) != {r['slot'] for r in schedule} \
            or any(type(available[r['slot']]) is not dict or
                   available[r['slot']].get('foreground_expectation_origin') != origins[r['case']] for r in schedule):
        raise ValueError('m6_followup_availability_changed')
    outcomes = base._native_outcomes(study, before[0])
    if len(outcomes) != 12 or {(r['scenario'], r['account']) for r in outcomes} != \
            {(s, a) for s in base.SCENARIOS for a in base.ACCOUNTS}:
        raise ValueError('m6_followup_native_outcome_denominator_changed')
    outcomes = {(r['scenario'], r['account']): r for r in outcomes}
    cells, usage = [], []
    for slot in schedule:
        path, a = study/'receipts'/slot['slot'], available[slot['slot']]
        receipt = json.loads(base._plain(path/'receipt.json')) if (path/'receipt.json').exists() else None
        capture = receipt['capture'] if receipt else json.loads(base._plain(path/'attempts.json')) if (path/'attempts.json').exists() else {}
        usage += [r.get('usage') for r in capture.get('attempts', [])]
        status = ('complete' if a['horizon_complete'] and a['capture_complete'] and a['stop_code'] is None else
                  'incomplete' if receipt else 'interrupted' if (study/'receipts'/(slot['slot']+'.started.json')).exists() else 'unstarted')
        cells.append({'scenario': slot['case'], 'account': slot['account'], 'status': status,
            **{k: a[k] for k in ('horizon_complete', 'capture_complete', 'profile_available',
                'foreground_expectation_origin', 'checkin_capture_complete', 'checkin_observed', 'checkin_projectable_records')},
            **{k: v for k, v in outcomes[slot['case'], slot['account']].items() if k not in ('scenario', 'account')}})
    result = project({'cells': cells, 'provider_attempts': len(usage), 'usage': usage},
        {**js, **_accounting(judge, binding, js),
         'primary': {p: [r['verdict'] for r in js['primary'][p]] for p in base.PHASES},
         'consistency': js['second_pass_consistency']},
        proof={**pins, 'native_outcomes_adapter_sha256': base.sha(base.NATIVE_OUTCOMES_ADAPTER.encode())})
    if before != (base.inventory(study), base.inventory(judge)):
        raise ValueError('m6_followup_archive_changed_during_export')
    return result


def validate_public(value):
    if type(value) is not dict or set(value) != set(pending_projection()) \
            or type(value['schema_version']) is not int or value['schema_version'] != 1 \
            or value['kind'] != PROTOCOL or type(value['planned_cells']) is not int or value['planned_cells'] != 12 \
            or type(value['policy_count']) is not int or value['policy_count'] != 1 \
            or value['cohort'] != 'synthetic_development' or value['publication_ready'] is not False \
            or type(value['quality_ready']) is not bool or base.digest(value['evidence_contract']) != base.digest(EVIDENCE) \
            or base.digest(value['history']) != base.digest(HISTORY) or value['limits'] != LIMITS:
        raise ValueError('m6_followup_invalid_public_shape')
    if value['status'] == 'awaiting_reviewed_freeze':
        if base.digest(value) != base.digest(pending_projection()): raise ValueError('m6_followup_invalid_pending')
        return value
    if value['status'] not in ('qualified', 'incomplete') or (value['status'] == 'qualified') != value['quality_ready']:
        raise ValueError('m6_followup_invalid_readiness')
    cells = value['cells']
    if type(cells) is not list or len(cells) != 12 or {(r['scenario'], r['account']) for r in cells} != \
            {(s, a) for s in base.SCENARIOS for a in base.ACCOUNTS}:
        raise ValueError('m6_followup_cell_denominator_changed')
    for row in cells:
        if set(row) != CELL_KEYS or row['status'] not in ('complete', 'incomplete', 'interrupted', 'unstarted') \
                or row['foreground_expectation_origin'] not in base.FOREGROUND_ORIGINS \
                or any(type(row[k]) is not bool for k in
                       ('horizon_complete', 'capture_complete', 'profile_available', 'checkin_capture_complete')):
            raise ValueError('m6_followup_invalid_cell')
        if row['status'] == 'complete' and not all(row[k] for k in
                ('horizon_complete', 'capture_complete', 'checkin_capture_complete')) \
                or row['status'] in ('interrupted', 'unstarted') and any(row[k] for k in
                    ('horizon_complete', 'capture_complete', 'profile_available', 'checkin_capture_complete')):
            raise ValueError('m6_followup_invalid_cell')
        if row['checkin_observed'] is not None: base._integer(row['checkin_observed'], 128)
        base._integer(row['checkin_projectable_records'], 128)
        if row['checkin_observed'] is None and (row['checkin_capture_complete'] or row['checkin_projectable_records']) \
                or row['checkin_observed'] is not None and row['checkin_projectable_records'] > row['checkin_observed']:
            raise ValueError('m6_followup_invalid_evidence_count')
        base._validate_native_outcome(row)
    native, judging = value['native'], value['judging']
    if type(native) is not dict or set(native) != {'provider_attempts', 'request_ceiling', 'complete_horizons',
            'profile_available_cells', 'checkin_capture_complete_cells', 'usage', 'required_windows'}:
        raise ValueError('m6_followup_invalid_native_summary')
    base._integer(native['provider_attempts'], 758)
    for key in ('complete_horizons', 'profile_available_cells', 'checkin_capture_complete_cells'):
        base._integer(native[key], 12)
    if type(native['request_ceiling']) is not int or native['request_ceiling'] != 758 \
            or native['complete_horizons'] != sum(r['horizon_complete'] for r in cells) \
            or native['profile_available_cells'] != sum(r['profile_available'] for r in cells) \
            or native['checkin_capture_complete_cells'] != sum(r['checkin_capture_complete'] for r in cells):
        raise ValueError('m6_followup_invalid_native_summary')
    required = {'planned_cells': 4, **{k: sum(r['required_window_outcome'] == k for r in cells)
                                      for k in ('hit', 'completed_miss', 'unavailable')}}
    if base.digest(native['required_windows']) != base.digest(required) or sum(required[k] for k in required if k != 'planned_cells') != 4:
        raise ValueError('m6_followup_invalid_required_windows')
    expected_judge = {'logical_jobs', 'valid_jobs', 'started_attempts', 'technical_errors', 'interrupted_attempts',
        'valid_controls', 'matched_controls', 'failed_controls', 'candidate_jobs', 'calibration_status',
        'controls_qualified', 'control_jobs', 'control_counts', 'primary_pass', 'consistency_pass',
        'max_attempts_per_job', 'max_logical_jobs', 'request_ceiling', 'calibration_before_candidates',
        'usage', 'phases', 'consistency'}
    if type(judging) is not dict or set(judging) != expected_judge:
        raise ValueError('m6_followup_invalid_judge_summary')
    fixed = {'control_jobs': 94, 'control_counts': CONTROL_COUNTS, 'primary_pass': 1, 'consistency_pass': 2,
        'max_attempts_per_job': 3, 'max_logical_jobs': 182, 'request_ceiling': 546, 'calibration_before_candidates': True}
    if any(base.digest(judging[k]) != base.digest(v) for k, v in fixed.items()) \
            or type(judging['controls_qualified']) is not bool:
        raise ValueError('m6_followup_invalid_judge_contract')
    for k in ('logical_jobs', 'valid_jobs'): base._integer(judging[k], 182)
    for k in ('started_attempts', 'technical_errors', 'interrupted_attempts'): base._integer(judging[k], 546)
    for k in ('valid_controls', 'matched_controls', 'failed_controls'): base._integer(judging[k], 94)
    candidate = judging['candidate_jobs']
    if type(candidate) is not dict or set(candidate) != {'planned', 'started', 'valid'}:
        raise ValueError('m6_followup_invalid_candidate_jobs')
    for k in candidate: base._integer(candidate[k], 88)
    if candidate['planned'] % 2 or candidate['valid'] > candidate['started'] or candidate['started'] > candidate['planned'] \
            or candidate['planned']+94 != judging['logical_jobs'] \
            or candidate['valid']+judging['valid_controls'] != judging['valid_jobs'] \
            or judging['valid_jobs']+judging['technical_errors']+judging['interrupted_attempts'] != judging['started_attempts'] \
            or judging['started_attempts'] < judging['valid_controls']+candidate['started'] \
            or judging['matched_controls']+judging['failed_controls'] != judging['valid_controls'] \
            or judging['controls_qualified'] != (judging['matched_controls'] == 94) \
            or judging['calibration_status'] != ('qualified' if judging['matched_controls'] == 94 else
                'failed_valid_final' if judging['valid_controls'] == 94 else 'pending'):
        raise ValueError('m6_followup_invalid_accounting')
    for group, attempts in ((native, native['provider_attempts']), (judging, judging['started_attempts'])):
        if set(group['usage']) != set(base.TOKENS): raise ValueError('m6_followup_invalid_usage')
        for row in group['usage'].values():
            if set(row) != {'known_attempts', 'unknown_attempts', 'observed_tokens'}:
                raise ValueError('m6_followup_invalid_usage')
            for k in ('known_attempts', 'unknown_attempts'): base._integer(row[k], attempts)
            if row['known_attempts']+row['unknown_attempts'] != attempts:
                raise ValueError('m6_followup_invalid_usage')
            if row['known_attempts'] == 0:
                if row['observed_tokens'] is not None: raise ValueError('m6_followup_unknown_usage_is_not_zero')
            else: base._integer(row['observed_tokens'])
    if set(judging['phases']) != set(base.PHASES) or set(judging['consistency']) != set(base.PHASES):
        raise ValueError('m6_followup_invalid_phases')
    for phase, row in judging['phases'].items():
        flags = base.PROFILE_FIELDS if phase == 'profile' else base.FOREGROUND_FIELDS if phase == 'foreground' else base.PROACTIVE_FIELDS
        if set(row) != {'primary_units', 'flags', 'scores'} or set(row['flags']) != set(flags) \
                or set(row['scores']) != (set(base.SCORE_FIELDS) if phase == 'proactive' else set()):
            raise ValueError('m6_followup_invalid_phase')
        base._integer(row['primary_units'], 20 if phase == 'proactive' else 12)
        for counts in row['flags'].values():
            if set(counts) != {'true', 'false', 'applicable'}: raise ValueError('m6_followup_invalid_flags')
            for n in counts.values(): base._integer(n, row['primary_units'])
            if counts['true']+counts['false'] != counts['applicable']: raise ValueError('m6_followup_invalid_flags')
        for counts in row['scores'].values():
            if set(counts) != {'sum', 'applicable'}: raise ValueError('m6_followup_invalid_scores')
            base._integer(counts['applicable'], row['primary_units']); base._integer(counts['sum'], 5*counts['applicable'])
        pair = judging['consistency'][phase]
        if set(pair) != {'paired_packets', 'same_flags'}: raise ValueError('m6_followup_invalid_consistency')
        base._integer(pair['paired_packets'], row['primary_units']); base._integer(pair['same_flags'], pair['paired_packets'])
    units = sum(r['primary_units'] for r in judging['phases'].values())
    if units > candidate['valid'] or judging['phases']['profile']['primary_units'] > native['profile_available_cells']:
        raise ValueError('m6_followup_unavailable_quality_credited')
    if value['quality_ready'] and (not judging['controls_qualified'] or judging['valid_jobs'] != judging['logical_jobs']
            or 2*units != candidate['planned'] or any(r['status'] != 'complete' or not r['profile_available'] for r in cells)):
        raise ValueError('m6_followup_invalid_readiness')
    proof = value['proof']
    if type(proof) is not dict or set(proof) != PIN_KEYS | {'native_outcomes_adapter_sha256'}:
        raise ValueError('m6_followup_invalid_proof')
    for k, v in proof.items(): base._hash(v, 40 if k.endswith('_ref') else 64)
    if any(proof[k] != ref for k, ref in REFS.items()) \
            or proof['native_outcomes_adapter_sha256'] != base.sha(base.NATIVE_OUTCOMES_ADAPTER.encode()):
        raise ValueError('m6_followup_invalid_proof')
    return value
