"""Separate public projection of four fresh explicit recurring-request cells.

Only externally reviewed complete terminal inventories enable the intended
offline summary CLIs. No captured runtime file is imported. Earlier M6 exports
and trust remain unchanged. Export under inherited OS network denial.
"""
from copy import deepcopy
import json
from pathlib import Path
import re
from types import ModuleType


def _base_module():
    path = Path(__file__).with_name('m6_profile_diagnostic.py')
    module = ModuleType('er_public_projection_helpers')
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


base = _base_module()
TRUST_PROTOCOL = 'm6_explicit_recurring_trust_v1'
PROTOCOL = 'm6_explicit_recurring_public_v1'
NATIVE_PROTOCOL = 'native_m6_explicit_recurring_request_v1'
JUDGE_PROTOCOL = 'native_m6_explicit_recurring_request_judging_v1'
ALIAS = 'line-always-on-m6-explicit-recurring.public.json'
TRUST = json.loads(Path(__file__).with_name('m6_explicit_recurring_trust.json').read_text())
REFS = {'native_ref': '453c4ecafea91c714cd3a63b52f66534f571b4d0',
        'helper_ref': '6bd20d09f89508a4e5138ab076a76203bd998051',
        'evaluator_ref': '28c310b27c8cec138f22f391db43ce89fc73940f'}
PIN_KEYS = {*REFS, 'plan_sha256', 'judge_binding_sha256', 'native_files_sha256',
            'judge_files_sha256', 'native_seal_sha256', 'judge_seal_sha256'}
CONTROL_COUNTS = {'foreground': 25, 'proactive': 10, 'profile': 12}
CONTROL_SHA = '007c3858e561fd6283cd27aecb3141e8964d4686abc41895be52966747c27181'
STRATA = ('current_delivered_cooking_offer', 'no_current_offer', 'other_or_unavailable')
SCHEDULE = [{'slot': f'ER01.repeat{repeat}.{account}', 'case': 'ER01', 'repeat': repeat, 'account': account}
            for repeat in (1, 2) for account in base.ACCOUNTS]
# Opaque receipt-local Hermes caches are data, including the other account's
# cache initialized by the fixture. Source/inputs bytecode is always rejected.
OPAQUE_RUNTIME_CACHE_PREFIX = (r'^receipts/ER01\.repeat[12]\.(?:primary|secondary)/'
                               r'hermes-(?:primary|secondary)\.pycache-[0-9a-f]{32}/')
CELL_KEYS = {'scenario', 'repeat', 'account', 'status', 'horizon_complete', 'capture_complete',
             'profile_available', 'request_context_available', 'offer_stratum', 'request_foreground_sent',
             'checkin_capture_complete', 'checkin_observed', 'checkin_projectable_records',
             'reserved_attempts', 'actual_http_attempts', 'request_sent_unknown_attempts'}
LIMITS = ('四個全新合成開發 cells，兩個帳號各重複兩次，使用同一策略與完整既有對話。'
          '四個軌跡預先指定同一則明確自我授權的每週請求；是否看見已送達提議只按實際發生分層，'
          '不是隨機分派、保證曝光或為取得提議而重抽。零樣本層仍保留。'
          '原生引擎包含後續修正，與較早 H3／J8 的差異不能解讀為單一修正的因果效果。'
          '沒有提議不等於失敗；原生預設晚上時間不等於使用者指定鐘點；'
          '模型承諾不等於成功保存排程，倫敦時區也必須有當時原生證據。'
          '沿用 J8 的規則、47 個控制題與全部 94 個先行判讀門檻；有效負評與失敗控制皆為最終結果。'
          '第 1 輪是主要品質判讀，第 2 輪只報一致性。未完成不當成通過，未知用量不當成零。'
          '多日時間範圍是本機日曆模擬，checkpoint 數與宿主總耗時不代表 API 完成延遲。'
          '不作模型排名、一般成功率、正式環境延遲或實際 LINE 送達結論。'
          '本輪原生與 AI 判讀成本分開，較早 J8／J7 的結果與成本不重算、不合併。')


def inventory(root):
    root = Path(root)
    if any(p.is_symlink() for p in (root, *root.parents)) or not root.is_dir():
        raise ValueError('er_invalid_archive_directory')
    result = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root).as_posix()
        bytecode = path.name == '__pycache__' or path.suffix in ('.pyc', '.pyo')
        if path.is_symlink() or bytecode and not re.match(OPAQUE_RUNTIME_CACHE_PREFIX, relative):
            raise ValueError('er_untrusted_archive_entry')
        if path.is_file(): result[relative] = base.sha(base._plain(path))
        elif not path.is_dir(): raise ValueError('er_untrusted_archive_entry')
    return result


def trusted():
    if type(TRUST) is not dict or set(TRUST) != {'protocol', 'status', 'binding'} \
            or TRUST['protocol'] != TRUST_PROTOCOL or TRUST['status'] != 'reviewed' \
            or type(TRUST['binding']) is not dict or set(TRUST['binding']) != PIN_KEYS:
        raise ValueError('er_reviewed_terminal_freeze_required')
    pins = TRUST['binding']
    if any(pins[key] != ref for key, ref in REFS.items()): raise ValueError('er_wrong_iteration')
    for key, value in pins.items(): base._hash(value, 40 if key.endswith('_ref') else 64)
    return deepcopy(pins)


def pending_projection():
    return {'schema_version': 1, 'kind': PROTOCOL, 'status': 'awaiting_reviewed_freeze',
        'planned_cells': 4, 'policy_count': 1, 'cohort': 'synthetic_development',
        'publication_ready': False, 'quality_ready': False,
        'cells': [{'scenario': s['case'], 'repeat': s['repeat'], 'account': s['account'],
                   'status': 'not_exported', **dict.fromkeys(sorted(CELL_KEYS-
                       {'scenario', 'repeat', 'account', 'status'}))} for s in SCHEDULE],
        'native': None, 'judging': None, 'strata': None, 'proof': None, 'limits': LIMITS}


def _accounting(judge, binding, summary):
    # Mirror only the already-pinned pure control predicates, after the intended
    # summary verifies actual request/claim/receipt bytes and finality.
    base._check_control_predicates(judge)
    controls = {r['id']: r for r in json.loads(base._plain(judge/'controls.json'))}
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
                if valid is not None: raise ValueError('er_valid_verdict_replaced')
                valid = row
        if job['control']:
            if valid is not None:
                valid_controls += 1
                matched += base._control_passed(controls[job['packet']], valid['verdict'])
        else:
            started_candidates += started
            valid_candidates += valid is not None
    if len(usage) != summary['started_attempts'] or valid_controls+valid_candidates != summary['valid_jobs'] \
            or summary['controls_qualified'] is not (matched == 94):
        raise ValueError('er_attempt_accounting_changed')
    return {'usage': base._usage(usage), 'technical_errors': errors, 'interrupted_attempts': interrupted,
        'valid_controls': valid_controls, 'matched_controls': matched, 'failed_controls': valid_controls-matched,
        'candidate_jobs': {'planned': sum(j['control'] is False for j in binding['jobs']),
                           'started': started_candidates, 'valid': valid_candidates},
        'calibration_status': 'qualified' if matched == 94 else
                              'failed_valid_final' if valid_controls == 94 else 'pending'}


def _strata(cells):
    return {name: {'observed_cells': sum(r['request_context_available'] and r['offer_stratum'] == name for r in cells),
                   'complete_cells': sum(r['horizon_complete'] and r['offer_stratum'] == name for r in cells),
                   'model_exposed_cells': sum(r['request_foreground_sent'] > 0 and r['offer_stratum'] == name for r in cells)}
            for name in STRATA}


def _cell_status(available, *, has_receipt, started):
    complete = has_receipt and all(available[k] is True for k in
        ('horizon_complete', 'capture_complete', 'request_context_available', 'checkin_capture_complete')) \
        and available['stop_code'] is None
    return 'complete' if complete else 'incomplete' if has_receipt else 'interrupted' if started else 'unstarted'


def _attempts(attempts):
    # A transport exception may be finished without an after_request_sent
    # callback. Only the exact native pretransport-policy branch proves a
    # non-upload; every other unconfirmed reservation remains uncertain.
    if type(attempts) is not list or any(type(r) is not dict or type(r.get('request_sent')) is not bool for r in attempts):
        raise ValueError('er_invalid_attempt_capture')
    denied = [r for r in attempts if r.get('outcome') == 'wire_policy_denied_before_transport']
    if any(r['request_sent'] is not False or r.get('finished') is not True for r in denied):
        raise ValueError('er_invalid_pretransport_denial')
    return {'reserved_attempts': len(attempts),
        'actual_http_attempts': sum(r['request_sent'] is True for r in attempts),
        'request_sent_unknown_attempts': sum(r['request_sent'] is False and
            r.get('outcome') != 'wire_policy_denied_before_transport' for r in attempts)}


def project(cells, native_usage, judging, *, proof):
    value = pending_projection()
    value.update(status='qualified' if judging['quality_ready'] else 'incomplete', quality_ready=judging['quality_ready'])
    value['cells'] = deepcopy(cells)
    value['strata'] = _strata(cells)
    value['native'] = {k: sum(r[k] for r in cells) for k in
        ('reserved_attempts', 'actual_http_attempts', 'request_sent_unknown_attempts')}
    value['native'].update(request_ceiling=180, complete_horizons=sum(r['horizon_complete'] for r in cells),
        profile_available_cells=sum(r['profile_available'] for r in cells),
        usage_capture_complete=all(r['status'] == 'complete' for r in cells), usage=base._usage(native_usage))
    value['judging'] = {k: deepcopy(judging[k]) for k in ('logical_jobs', 'valid_jobs', 'started_attempts',
        'technical_errors', 'interrupted_attempts', 'valid_controls', 'matched_controls', 'failed_controls',
        'candidate_jobs', 'calibration_status', 'controls_qualified', 'usage')}
    value['judging'].update(control_jobs=94, control_counts=deepcopy(CONTROL_COUNTS),
        primary_pass=1, consistency_pass=2, max_attempts_per_job=3, max_logical_jobs=126,
        request_ceiling=378, calibration_before_candidates=True,
        phases={p: base._phase(judging['primary'][p], p) for p in base.PHASES},
        consistency=deepcopy(judging['second_pass_consistency']))
    value['proof'] = deepcopy(proof)
    return validate_public(value)


def verified_projection(study, judge):
    pins = trusted()  # Before caller paths, private reads or summary execution.
    study, judge = Path(study), Path(judge)
    before = inventory(study), inventory(judge)
    if tuple(base.digest(v) for v in before) != (pins['native_files_sha256'], pins['judge_files_sha256']):
        raise ValueError('er_untrusted_inventory')
    base._require_source_paths(*before)
    for files in before:
        if any('source/'+base.PREFIX+name not in files for name in
               ('m6_explicit_recurring_pilot.py', 'm6_explicit_recurring_cases.json')):
            raise ValueError('er_incomplete_source_closure')
    if 'source/'+base.PREFIX+'m6_explicit_recurring_judge.py' not in before[1]:
        raise ValueError('er_incomplete_source_closure')
    plan, binding = (json.loads(base._plain(p)) for p in (study/'plan.json', judge/'binding.json'))
    if base.sha(base._plain(study/'plan.json')) != pins['plan_sha256'] \
            or base.sha(base._plain(judge/'binding.json')) != pins['judge_binding_sha256'] \
            or plan.get('protocol') != NATIVE_PROTOCOL or plan.get('schedule') != SCHEDULE \
            or plan.get('max_native_requests') != 180 or plan.get('native_ref') != pins['native_ref'] \
            or plan.get('source_ref') != pins['helper_ref'] \
            or any(binding.get(k) != pins[v] for k, v in
                   (('native_source_ref', 'native_ref'), ('helper_ref', 'helper_ref'), ('evaluator_source_ref', 'evaluator_ref'),
                    ('native_plan_sha256', 'plan_sha256'))) \
            or Path(binding.get('original_study', '')).absolute() != study.absolute():
        raise ValueError('er_source_binding_changed')
    fixed = {'protocol': JUDGE_PROTOCOL, 'passes': 2, 'primary_pass': 1, 'max_attempts_per_job': 3,
        'judge_model': 'gpt-6-sol', 'reasoning': 'high', 'max_output_tokens': 32768, 'timeout_s': 120,
        'store': False, 'planned_cells': 4, 'controls': 47, 'control_counts': CONTROL_COUNTS,
        'max_logical_jobs': 126, 'max_provider_calls': 378, 'valid_verdict_final': True,
        'control_failed_valid_final': True, 'calibrate_before_candidates': True}
    if any(base.digest(binding.get(k)) != base.digest(v) for k, v in fixed.items()):
        raise ValueError('er_judge_contract_changed')
    controls = json.loads(base._plain(judge/'controls.json'))
    if base.digest(controls) != CONTROL_SHA: raise ValueError('er_controls_changed')
    for name, pin in binding['original_input_files'].items():
        if base.sha(base._plain(study/name)) != pin or base._plain(study/name) != base._plain(judge/'inputs'/name):
            raise ValueError('er_original_copy_changed')
    ns = base._summary(study, 'm6_explicit_recurring_pilot.py', ['--study', str(study), '--plan-sha256', pins['plan_sha256']])
    js = base._summary(judge, 'm6_explicit_recurring_judge.py', ['--out', str(judge), '--binding-sha256', pins['judge_binding_sha256']])
    if ns['protocol'] != NATIVE_PROTOCOL or js['protocol'] != JUDGE_PROTOCOL \
            or ns['planned_cells'] != 4 or js['planned_cells'] != 4 or js['control_jobs'] != 94 \
            or len(binding['jobs']) != js['logical_jobs'] \
            or len({j['id'] for j in binding['jobs']}) != js['logical_jobs'] \
            or sum(j['control'] is True for j in binding['jobs']) != 94:
        raise ValueError('er_protocol_or_denominator_changed')
    available, native_rows = js['availability'], {r['slot']: r for r in ns['cells']}
    if set(available) != {s['slot'] for s in SCHEDULE} or set(native_rows) != set(available):
        raise ValueError('er_availability_changed')
    cells, usage = [], []
    for slot in SCHEDULE:
        key = slot['slot']; root = study/'receipts'/key
        a, n = available[key], native_rows[key]
        receipt = json.loads(base._plain(root/'receipt.json')) if (root/'receipt.json').exists() else None
        capture = receipt['capture'] if receipt else json.loads(base._plain(root/'attempts.json')) if (root/'attempts.json').exists() else {}
        attempts = capture.get('attempts', [])
        usage += [r.get('usage') for r in attempts]
        if a['offer_stratum'] != n['stratum'] or a['horizon_complete'] != n['horizon_completed']:
            raise ValueError('er_native_judge_context_disagreement')
        status = _cell_status(a, has_receipt=receipt is not None,
                              started=(study/'receipts'/(key+'.started.json')).exists())
        cells.append({'scenario': slot['case'], 'repeat': slot['repeat'], 'account': slot['account'], 'status': status,
            **{k: a[k] for k in ('horizon_complete', 'capture_complete', 'profile_available', 'request_context_available',
                'offer_stratum', 'checkin_capture_complete', 'checkin_observed', 'checkin_projectable_records')},
            'request_foreground_sent': n['request_foreground_sent'], **_attempts(attempts)})
    if any(js['offer_strata'][name] != {k: v for k, v in row.items() if k != 'model_exposed_cells'}
           for name, row in _strata(cells).items()):
        raise ValueError('er_strata_disagreement')
    result = project(cells, usage, {**js, **_accounting(judge, binding, js),
        'primary': {p: [r['verdict'] for r in js['primary'][p]] for p in base.PHASES}}, proof=pins)
    if before != (inventory(study), inventory(judge)):
        raise ValueError('er_archive_changed_during_export')
    return result


def _usage(value, attempts):
    if type(value) is not dict or set(value) != set(base.TOKENS): raise ValueError('er_invalid_usage')
    for row in value.values():
        if type(row) is not dict or set(row) != {'known_attempts', 'unknown_attempts', 'observed_tokens'}:
            raise ValueError('er_invalid_usage')
        for k in ('known_attempts', 'unknown_attempts'): base._integer(row[k], attempts)
        if row['known_attempts']+row['unknown_attempts'] != attempts: raise ValueError('er_invalid_usage')
        if row['known_attempts'] == 0:
            if row['observed_tokens'] is not None: raise ValueError('er_unknown_usage_is_not_zero')
        else: base._integer(row['observed_tokens'])


def validate_public(value):
    if type(value) is not dict or set(value) != set(pending_projection()) \
            or type(value['schema_version']) is not int or value['schema_version'] != 1 \
            or value['kind'] != PROTOCOL or type(value['planned_cells']) is not int or value['planned_cells'] != 4 \
            or type(value['policy_count']) is not int or value['policy_count'] != 1 \
            or value['cohort'] != 'synthetic_development' or value['publication_ready'] is not False \
            or type(value['quality_ready']) is not bool or value['limits'] != LIMITS:
        raise ValueError('er_invalid_public_shape')
    if value['status'] == 'awaiting_reviewed_freeze':
        if base.digest(value) != base.digest(pending_projection()): raise ValueError('er_invalid_pending')
        return value
    if value['status'] not in ('qualified', 'incomplete') or (value['status'] == 'qualified') != value['quality_ready']:
        raise ValueError('er_invalid_readiness')
    cells = value['cells']
    if type(cells) is not list or len(cells) != 4 \
            or {(r['scenario'], r['repeat'], r['account']) for r in cells} != {('ER01', s['repeat'], s['account']) for s in SCHEDULE}:
        raise ValueError('er_invalid_cells')
    for row in cells:
        if set(row) != CELL_KEYS or type(row['repeat']) is not int or row['status'] not in ('complete', 'incomplete', 'interrupted', 'unstarted') \
                or row['offer_stratum'] not in STRATA or any(type(row[k]) is not bool for k in
                    ('horizon_complete', 'capture_complete', 'profile_available', 'request_context_available', 'checkin_capture_complete')):
            raise ValueError('er_invalid_cell')
        for k in ('reserved_attempts', 'actual_http_attempts', 'request_sent_unknown_attempts'): base._integer(row[k], 45)
        base._integer(row['request_foreground_sent'], 8)
        if row['actual_http_attempts']+row['request_sent_unknown_attempts'] > row['reserved_attempts'] \
                or row['request_foreground_sent'] > row['actual_http_attempts']:
            raise ValueError('er_invalid_native_attempts')
        if row['checkin_observed'] is not None: base._integer(row['checkin_observed'], 128)
        base._integer(row['checkin_projectable_records'], 128)
        if row['checkin_observed'] is None and (row['checkin_capture_complete'] or row['checkin_projectable_records']) \
                or row['checkin_observed'] is not None and row['checkin_projectable_records'] > row['checkin_observed']:
            raise ValueError('er_invalid_host_observation')
        if row['status'] == 'complete' and not all(row[k] for k in
                ('horizon_complete', 'capture_complete', 'request_context_available', 'checkin_capture_complete')) \
                or row['status'] in ('unstarted', 'interrupted') and any(row[k] for k in
                    ('horizon_complete', 'capture_complete', 'request_context_available', 'profile_available', 'checkin_capture_complete')) \
                or not row['request_context_available'] and row['offer_stratum'] != 'other_or_unavailable':
            raise ValueError('er_invalid_cell_availability')
    if base.digest(value['strata']) != base.digest(_strata(cells)): raise ValueError('er_invalid_strata')
    native, judging = value['native'], value['judging']
    if type(native) is not dict or set(native) != {'reserved_attempts', 'actual_http_attempts', 'request_sent_unknown_attempts',
            'request_ceiling', 'complete_horizons', 'profile_available_cells', 'usage_capture_complete', 'usage'}:
        raise ValueError('er_invalid_native_summary')
    for k in ('reserved_attempts', 'actual_http_attempts', 'request_sent_unknown_attempts'):
        base._integer(native[k], 180)
        if native[k] != sum(r[k] for r in cells): raise ValueError('er_invalid_native_summary')
    for k in ('complete_horizons', 'profile_available_cells'): base._integer(native[k], 4)
    if type(native['request_ceiling']) is not int or native['request_ceiling'] != 180 \
            or native['complete_horizons'] != sum(r['horizon_complete'] for r in cells) \
            or native['profile_available_cells'] != sum(r['profile_available'] for r in cells) \
            or native['usage_capture_complete'] is not all(r['status'] == 'complete' for r in cells):
        raise ValueError('er_invalid_native_summary')
    fields = {'logical_jobs', 'valid_jobs', 'started_attempts', 'technical_errors', 'interrupted_attempts',
        'valid_controls', 'matched_controls', 'failed_controls', 'candidate_jobs', 'calibration_status', 'controls_qualified',
        'usage', 'control_jobs', 'control_counts', 'primary_pass', 'consistency_pass', 'max_attempts_per_job',
        'max_logical_jobs', 'request_ceiling', 'calibration_before_candidates', 'phases', 'consistency'}
    if type(judging) is not dict or set(judging) != fields: raise ValueError('er_invalid_judge_summary')
    fixed = {'control_jobs': 94, 'control_counts': CONTROL_COUNTS, 'primary_pass': 1, 'consistency_pass': 2,
        'max_attempts_per_job': 3, 'max_logical_jobs': 126, 'request_ceiling': 378, 'calibration_before_candidates': True}
    if any(base.digest(judging[k]) != base.digest(v) for k, v in fixed.items()) \
            or type(judging['controls_qualified']) is not bool: raise ValueError('er_invalid_judge_contract')
    for k in ('logical_jobs', 'valid_jobs'): base._integer(judging[k], 126)
    for k in ('started_attempts', 'technical_errors', 'interrupted_attempts'): base._integer(judging[k], 378)
    for k in ('valid_controls', 'matched_controls', 'failed_controls'): base._integer(judging[k], 94)
    candidate = judging['candidate_jobs']
    if type(candidate) is not dict or set(candidate) != {'planned', 'started', 'valid'}: raise ValueError('er_invalid_candidate_jobs')
    for k in candidate: base._integer(candidate[k], 32)
    if candidate['planned'] % 2 or candidate['valid'] > candidate['started'] or candidate['started'] > candidate['planned'] \
            or candidate['planned']+94 != judging['logical_jobs'] \
            or candidate['valid']+judging['valid_controls'] != judging['valid_jobs'] \
            or judging['valid_jobs']+judging['technical_errors']+judging['interrupted_attempts'] != judging['started_attempts'] \
            or judging['started_attempts'] < judging['valid_controls']+candidate['started'] \
            or judging['matched_controls']+judging['failed_controls'] != judging['valid_controls'] \
            or judging['controls_qualified'] != (judging['matched_controls'] == 94) \
            or judging['calibration_status'] != ('qualified' if judging['matched_controls'] == 94 else
                'failed_valid_final' if judging['valid_controls'] == 94 else 'pending'):
        raise ValueError('er_invalid_accounting')
    _usage(native['usage'], native['reserved_attempts']); _usage(judging['usage'], judging['started_attempts'])
    if set(judging['phases']) != set(base.PHASES) or set(judging['consistency']) != set(base.PHASES):
        raise ValueError('er_invalid_phases')
    for phase, row in judging['phases'].items():
        flags = base.PROFILE_FIELDS if phase == 'profile' else base.FOREGROUND_FIELDS if phase == 'foreground' else base.PROACTIVE_FIELDS
        if set(row) != {'primary_units', 'flags', 'scores'} or set(row['flags']) != set(flags) \
                or set(row['scores']) != (set(base.SCORE_FIELDS) if phase == 'proactive' else set()):
            raise ValueError('er_invalid_phase')
        base._integer(row['primary_units'], 8 if phase == 'proactive' else 4)
        for counts in row['flags'].values():
            if set(counts) != {'true', 'false', 'applicable'}: raise ValueError('er_invalid_flags')
            for n in counts.values(): base._integer(n, row['primary_units'])
            if counts['true']+counts['false'] != counts['applicable']: raise ValueError('er_invalid_flags')
        for counts in row['scores'].values():
            if set(counts) != {'sum', 'applicable'}: raise ValueError('er_invalid_scores')
            base._integer(counts['applicable'], row['primary_units']); base._integer(counts['sum'], 5*counts['applicable'])
        pair = judging['consistency'][phase]
        if set(pair) != {'paired_packets', 'same_flags'}: raise ValueError('er_invalid_consistency')
        base._integer(pair['paired_packets'], row['primary_units']); base._integer(pair['same_flags'], pair['paired_packets'])
    units = sum(r['primary_units'] for r in judging['phases'].values())
    if units > candidate['valid'] or judging['phases']['profile']['primary_units'] > native['profile_available_cells']:
        raise ValueError('er_unavailable_quality_credited')
    if not judging['controls_qualified'] and candidate['started']:
        raise ValueError('er_candidates_before_calibration')
    if value['quality_ready'] and (not judging['controls_qualified'] or judging['valid_jobs'] != judging['logical_jobs']
            or 2*units != candidate['planned'] or any(r['status'] != 'complete' or not r['profile_available'] for r in cells)):
        raise ValueError('er_invalid_readiness')
    proof = value['proof']
    if type(proof) is not dict or set(proof) != PIN_KEYS: raise ValueError('er_invalid_proof')
    for k, v in proof.items(): base._hash(v, 40 if k.endswith('_ref') else 64)
    if any(proof[k] != ref for k, ref in REFS.items()): raise ValueError('er_invalid_proof')
    return value
