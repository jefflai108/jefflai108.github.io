"""Public-safe, separate twelve-store M6 development diagnostic.

The committed null trust deliberately prevents real archive export. A later
reviewed binding must pin canonical digests of the complete terminal native and
judge inventories, including their committed source closures, before offline summary
CLIs may execute. No paid run, preparation, retry, or source import occurs here.
"""
from copy import deepcopy
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

TRUST_PROTOCOL = 'm6_profile_public_trust_v1'
PROTOCOL = 'm6_profile_public_diagnostic_v1'
NATIVE_PROTOCOL = 'native_m6_profile_pv41_46_development_v1'
JUDGE_PROTOCOL = 'native_m6_profile_pv41_46_judging_v1'
ALIAS = 'line-always-on-m6-profile-diagnostic.public.json'
PREFIX = 'serve/line_agent_v3/evals/always_on/'
TRUST = json.loads(Path(__file__).with_name('m6_profile_diagnostic_trust.json').read_text())
SCENARIOS = tuple('PV'+str(n) for n in range(41, 47))
ACCOUNTS = ('primary', 'secondary')
PHASES = ('profile', 'foreground', 'proactive')
PROFILE_FIELDS = ('supported', 'citations_valid', 'owner_correct', 'current', 'coverage')
FOREGROUND_FIELDS = ('answered', 'no_rejection', 'honest', 'grounded', 'alternatives', 'recap_correct',
                    'confirmed', 'resurfaced', 'no_resurface', 'media_acknowledged', 'care', 'offered', 'bridge')
FOREGROUND_ORIGINS = ('authored', 'universal_only_no_authored_foreground')
PROACTIVE_FIELDS = ('warranted', 'grounded', 'private')
SCORE_FIELDS = ('timing', 'useful', 'tone', 'not_annoying', 'decision_progress')
TOKENS = ('input_tokens', 'output_tokens', 'reasoning_tokens', 'total_tokens')
REQUIRED_SCENARIOS = ('PV41', 'PV44')
# ASTs of the three pure predicates in the reviewed frozen evaluator. A new
# evaluator may change control reference data, but cannot silently change the
# meaning of these mirrored comparisons.
CONTROL_PREDICATE_AST = {
    'judge.py': {'control_ok': '0add04773c8c5ff0a164e12418b137720d891991eb7656049fc7ed02bd365b88',
                'foreground_control_ok': '4017f97ba75235337eeac40d569f2b5b1eeb4fa766a28769eb7177138eff3202'},
    'm6_profile_judge.py': {'control_passed': 'bf7620be8664b8ee424862fef707f60fe0665a519f6eb8abf1f5bd59a1da7dfd'}}
LIMITS = ('單一已部署政策的 12 個合成開發 cells：原始 PV41–46，各兩個合成帳號。'
          '原生完成、profile 可用性與 profile／前景／主動訊息品質分開，不作模型排名或 holdout 結論。'
          '第 1 輪固定為主要判讀，第 2 輪只報一致性；70 個新控制判讀先於候選，所有有效負評與失敗控制均為最終結果。'
          '穩定願望不等於同意排程；可選邀請未出現不算 profile 遺漏。主動品質只以實際訊息為分母。'
          '原始對話同時可見，不能把回憶歸因於 profile；原生串行重播不代表正式環境的啟動或併發可靠度。'
          '原始 authored bounds／raw window 命中與 AI 訊息品質分列；未完成 horizon 不當成安靜通過或已證明漏接。'
          '未知用量不當成零；這是開發診斷，不宣告 Linux、速度或正式環境泛化通過。')
H1 = {'status': 'aborted_not_pooled', 'planned_cells': 12, 'incomplete_cells': 3,
      'interrupted_cells': 1, 'unstarted_cells': 8, 'complete_horizons': 0,
      'provider_attempts': 16, 'known_total_token_attempts': 15,
      'known_total_tokens': 177166, 'unknown_total_token_attempts': 1, 'judge_attempts': 0}
# Fixed, reviewed J3/J4 records, in that order; not an extensible ledger. Later
# evaluator bindings cannot replace or pool these failed calibrations. A record
# matching the current binding is the same displayed record, not more cost.
RETAINED_CALIBRATIONS = [{
    'evaluator_ref': '4e619c06019bc120012711cfd6144688880bd3c3',
    'judge_binding_sha256': 'fbf204c0068435455527794f4e5c302b3ca1122553e5a3d1b380d75154800b7b',
    'judge_inventory_sha256': '2298fe258323c427976f5a40fbb14636e2715ff8531fd6f1140485bedd1539b2',
    'seal_proof_sha256': '159ba09585a445654312890f35e2e8a83a6cf6b380128e359309af5a799e789f',
    'status': 'valid_final_failed_not_pooled', 'control_jobs': 70, 'valid_controls': 70,
    'matched_controls': 68, 'failed_controls': 2, 'candidate_jobs': {'planned': 68, 'started': 0, 'valid': 0},
    'started_attempts': 70, 'technical_errors': 0, 'interrupted_attempts': 0,
    'known_total_token_attempts': 70, 'known_total_tokens': 171417, 'unknown_total_token_attempts': 0}, {
    'evaluator_ref': '09316aa0c0e155f7161c22415c138ae901c79747',
    'judge_binding_sha256': '148624cc7baf5d17dc15fdc950c7ecbc28b014d5dcaf844315fdacc6cbbc0a9b',
    'judge_inventory_sha256': '103c072fc21edf6f538ddb7eaa720549c41a935913a5afa22eb32c9726d51a95',
    'seal_proof_sha256': '1132977bac061a1bf2e6ed5fa3cb3b5a976d412bc2bb196feafbad77cccf593f',
    'status': 'valid_final_failed_not_pooled', 'control_jobs': 70, 'valid_controls': 70,
    'matched_controls': 69, 'failed_controls': 1, 'candidate_jobs': {'planned': 68, 'started': 0, 'valid': 0},
    'started_attempts': 70, 'technical_errors': 0, 'interrupted_attempts': 0,
    'known_total_token_attempts': 70, 'known_total_tokens': 171887, 'unknown_total_token_attempts': 0}]

# HermesRuntime preserves opaque warm-cache data beside each receipt's state
# roots. Both accounts are initialized inside each slot, so their names need
# not match. Only descendants of these exact cache directories may contain
# bytecode; source/ and inputs/ retain the executable-source rejection. Every
# accepted byte remains in the externally pinned inventory, never an import path.
OPAQUE_RUNTIME_CACHE_PREFIX = (r'^receipts/PV4[1-6]\.(?:primary|secondary)/'
                               r'hermes-(?:primary|secondary)\.pycache-[0-9a-f]{32}/')

# Fixed, stdout-only offline adapter. Parent checks both entire inventories;
# the child independently rechecks the native inventory before importing the
# exact pinned metrics.py and again after scoring. No sys.path modification,
# provider call, private text output, or AI verdict attachment occurs here.
NATIVE_OUTCOMES_ADAPTER = r'''
import hashlib, importlib.util, json, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
expected = json.loads(sys.stdin.read())
opaque_runtime_cache_prefix = __OPAQUE_RUNTIME_CACHE_PREFIX__
def read(path):
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('m6_outcomes_not_plain_file')
    return path.read_bytes()
def inventory():
    if any(p.is_symlink() for p in (root, *root.parents)) or not root.is_dir():
        raise ValueError('m6_outcomes_directory')
    result = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root).as_posix()
        bytecode = path.name == '__pycache__' or path.suffix in ('.pyc', '.pyo')
        if path.is_symlink() or bytecode and not re.match(opaque_runtime_cache_prefix, relative):
            raise ValueError('m6_outcomes_untrusted_entry')
        if path.is_file(): result[relative] = hashlib.sha256(read(path)).hexdigest()
        elif not path.is_dir(): raise ValueError('m6_outcomes_untrusted_entry')
    return result
if inventory() != expected: raise ValueError('m6_outcomes_source_or_capture_changed')
source = root/'source/serve/line_agent_v3/evals/always_on/metrics.py'
spec = importlib.util.spec_from_file_location('pinned_m6_native_metrics', source)
metrics = importlib.util.module_from_spec(spec); spec.loader.exec_module(metrics)
plan = json.loads(read(root/'plan.json'))
cases = {case['id']: case for case in json.loads(read(root/'cases.json'))}
rows = []
for slot in plan['schedule']:
    case = cases[slot['case']]
    path = root/'receipts'/slot['slot']/'receipt.json'
    receipt = json.loads(read(path)) if path.exists() else None
    capture = receipt.get('capture', {}) if receipt else {}
    complete = bool(receipt and receipt.get('status') == 'measured'
        and receipt.get('original_horizon_completed') is True and capture.get('complete') is True
        and capture.get('stopped') is None)
    bounds = case['expect'].get('proactive', {'min': 0, 'max': 0})
    required = any(not w.get('optional', False) for w in bounds.get('windows', []))
    row = {'scenario': slot['case'], 'account': slot['account'],
        'original_bounds': {'min': bounds.get('min', 0), 'max': bounds.get('max', 0)},
        'observed_tick_sends': None, 'send_observation': 'unavailable', 'original_outcome': None,
        'required_window_outcome': 'unavailable' if required else 'not_required'}
    if complete:
        scored = metrics.score_run(case, receipt)
        row.update(observed_tick_sends=len(metrics.proactive_sends(receipt)), send_observation='complete_horizon',
            required_window_outcome=('hit' if scored['window_hit'] else 'completed_miss') if required else 'not_required',
            original_outcome={key: scored[key] for key in ('count', 'count_ok', 'over_count', 'requested',
                'unsolicited', 'late_answers', 'quiet_hours_violations')})
        row['original_outcome']['windows'] = [{key: w[key] for key in ('kind', 'optional', 'hit')} for w in scored['windows']]
        row['original_outcome']['listed_scripted_occurrences'] = len(metrics.scripted_occurrences(case))
    elif receipt:
        timeline = receipt.get('native_path', {}).get('partial_timelines', {}).get(slot['account'])
        if type(timeline) is list:
            row.update(observed_tick_sends=sum(entry.get('phase') == 'tick' and
                entry.get('kind') in ('push', 'reply') and not entry.get('duplicate') for entry in timeline),
                send_observation='partial')
    rows.append(row)
if inventory() != expected: raise ValueError('m6_outcomes_source_or_capture_changed')
print(json.dumps(rows, ensure_ascii=False, allow_nan=False))
'''.replace('__OPAQUE_RUNTIME_CACHE_PREFIX__', repr(OPAQUE_RUNTIME_CACHE_PREFIX))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode())


def _integer(value, maximum=None):
    if type(value) is not int or value < 0 or maximum is not None and value > maximum:
        raise ValueError('m6_invalid_counter')


def _hash(value, length=64):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{'+str(length)+'}', value):
        raise ValueError('m6_invalid_pin')


def _plain(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('m6_input_not_plain_file')
    return path.read_bytes()


def inventory(root):
    root = Path(root)
    if any(p.is_symlink() for p in (root, *root.parents)) or not root.is_dir():
        raise ValueError('m6_invalid_archive_directory')
    result = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root).as_posix()
        bytecode = path.name == '__pycache__' or path.suffix in ('.pyc', '.pyo')
        if path.is_symlink() or bytecode and not re.match(OPAQUE_RUNTIME_CACHE_PREFIX, relative):
            raise ValueError('m6_untrusted_archive_entry')
        if path.is_file():
            result[relative] = sha(_plain(path))
        elif not path.is_dir():
            raise ValueError('m6_untrusted_archive_entry')
    return result


def trusted():
    if type(TRUST) is not dict or set(TRUST) != {'protocol', 'status', 'binding'} \
            or TRUST['protocol'] != TRUST_PROTOCOL or TRUST['status'] != 'reviewed' \
            or type(TRUST['binding']) is not dict:
        raise ValueError('m6_reviewed_freeze_required')
    value = TRUST['binding']
    if set(value) != {'native_ref', 'helper_ref', 'evaluator_ref', 'plan_sha256', 'judge_binding_sha256',
                     'native_files_sha256', 'judge_files_sha256', 'h1_terminal_audit_sha256'}:
        raise ValueError('m6_invalid_trust_binding')
    for key in ('native_ref', 'helper_ref', 'evaluator_ref'): _hash(value[key], 40)
    for key in ('plan_sha256', 'judge_binding_sha256', 'h1_terminal_audit_sha256',
                'native_files_sha256', 'judge_files_sha256'): _hash(value[key])
    return deepcopy(value)


def _require_source_paths(native_files, judge_files):
    # The entire source closure is externally pinned, not trusted from its own
    # manifest. Check required paths on computed private maps, never publish the
    # archive filenames (including blind judge IDs) in committed trust.
    for files in (native_files, judge_files):
        if any('source/'+PREFIX+name not in files for name in
               ('m6_profile_pilot.py', 'm6_profile_capture.py', 'runner.py', 'judge.py', 'metrics.py')):
            raise ValueError('m6_incomplete_source_closure')
    if 'source/'+PREFIX+'m6_profile_judge.py' not in judge_files:
        raise ValueError('m6_incomplete_source_closure')


def pending_projection():
    return {'schema_version': 1, 'kind': PROTOCOL, 'status': 'awaiting_reviewed_freeze',
            'planned_cells': 12, 'policy_count': 1, 'cohort': 'synthetic_development',
            'publication_ready': False, 'quality_ready': False,
            'cells': [{'scenario': scenario, 'account': account, 'status': 'not_exported',
                       'horizon_complete': None, 'capture_complete': None, 'profile_available': None,
                       'foreground_expectation_origin': None,
                       'original_bounds': None, 'observed_tick_sends': None, 'send_observation': 'not_exported',
                       'original_outcome': None, 'required_window_outcome': None}
                      for scenario in SCENARIOS for account in ACCOUNTS],
            'native': None, 'judging': None, 'proof': None, 'prior_aborted': deepcopy(H1),
            'retained_calibrations': deepcopy(RETAINED_CALIBRATIONS), 'limits': LIMITS}


def _usage(rows):
    result = {}
    for field in TOKENS:
        observed = [row[field] for row in rows if type(row) is dict
                    and type(row.get(field)) is int and row[field] >= 0]
        result[field] = {'known_attempts': len(observed), 'unknown_attempts': len(rows)-len(observed),
                         'observed_tokens': sum(observed) if observed else None}
    return result


def _control_ok(expect, verdict):
    checks = [verdict.get(key) is expect[key] for key in ("warranted", "grounded", "private") if key in expect]
    checks += [verdict["useful"] >= expect["min_useful"]] if "min_useful" in expect else []
    checks += [verdict["useful"] <= expect["max_useful"]] if "max_useful" in expect else []
    checks += [verdict["timing"] <= expect["max_timing"]] if "max_timing" in expect else []
    checks += [(verdict["decision_progress"] or 0) >= expect["min_progress"]] if "min_progress" in expect else []
    return all(checks)


def _foreground_control_ok(expect, verdict):
    return all(verdict.get(field) is value for field, value in expect.items())


def _control_passed(packet, verdict):
    if packet["phase"] == "proactive": return _control_ok(packet["expect"], verdict)
    if packet["phase"] == "foreground": return _foreground_control_ok(packet["expect"], verdict)
    for key, expected in packet["expect"].items():
        if key.startswith("min_"):
            if verdict[key[4:]] < expected: return False
        elif verdict.get(key) != expected: return False
    return True


def _check_control_predicates(judge):
    for filename, expected in CONTROL_PREDICATE_AST.items():
        tree = ast.parse(_plain(judge/'source'/PREFIX/filename))
        # Python 3.12 added the empty type_params field to FunctionDef. These
        # ordinary functions have no generics; keep the semantic pin portable
        # across supported interpreters without ignoring nonempty parameters.
        found = {node.name: sha(ast.dump(node, include_attributes=False).replace(', type_params=[]', '').encode())
                 for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in expected}
        if found != expected:
            raise ValueError('m6_control_predicate_changed')


def _judge_accounting(judge, binding, summary):
    """Count final validity, expected control matches and actual claim starts.

    Called only after the intended frozen summary has validated every bound
    request/claim/receipt. No candidate text or private verdict is projected.
    """
    _check_control_predicates(judge)
    if any(binding.get(key) is not True for key in
           ('valid_verdict_final', 'control_failed_valid_final', 'calibrate_before_candidates')):
        raise ValueError('m6_valid_final_contract_changed')
    rows = json.loads(_plain(judge/'controls.json'))
    controls = {row['id']: row for row in rows}
    if len(controls) != 35 or len(controls) != len(rows) \
            or len({job['id'] for job in binding['jobs']}) != len(binding['jobs']):
        raise ValueError('m6_control_denominator_changed')
    usage, errors, interrupted, valid_controls, matched, candidate_started, candidate_valid = [], 0, 0, 0, 0, 0, 0
    for job in binding['jobs']:
        valid, started = None, False
        for attempt in (1, 2, 3):
            stem = judge/'receipts'/(job['id']+'.a'+str(attempt))
            claim, receipt = Path(str(stem)+'.started.json'), Path(str(stem)+'.json')
            if not claim.exists(): continue
            started = True
            row = json.loads(_plain(receipt)) if receipt.exists() else None
            usage.append(row.get('usage') if row else None)
            interrupted += row is None
            errors += row is not None and row['status'] == 'error'
            if row is not None and row['status'] == 'ok':
                if valid is not None: raise ValueError('m6_valid_verdict_replaced')
                valid = row
        if job['control']:
            if valid is not None:
                valid_controls += 1
                matched += _control_passed(controls[job['packet']], valid['verdict'])
        else:
            candidate_started += started
            candidate_valid += valid is not None
    if len(usage) != summary['started_attempts'] or valid_controls+candidate_valid != summary['valid_jobs'] \
            or summary['controls_qualified'] is not (matched == 70):
        raise ValueError('m6_attempt_accounting_changed')
    return {'usage': usage, 'technical_errors': errors, 'interrupted_attempts': interrupted,
            'valid_controls': valid_controls, 'matched_controls': matched, 'failed_controls': valid_controls-matched,
            'candidate_jobs': {'planned': sum(job['control'] is False for job in binding['jobs']),
                               'started': candidate_started, 'valid': candidate_valid},
            'calibration_status': 'qualified' if matched == 70 else
                                  'failed_valid_final' if valid_controls == 70 else 'pending'}


def _phase(rows, phase):
    flags = PROFILE_FIELDS if phase == 'profile' else FOREGROUND_FIELDS if phase == 'foreground' else PROACTIVE_FIELDS
    required = PROFILE_FIELDS if phase == 'profile' else FOREGROUND_FIELDS[:4] if phase == 'foreground' else PROACTIVE_FIELDS
    for row in rows:
        if type(row) is not dict or any(type(row.get(field)) is not bool for field in required) \
                or any(row.get(field) is not None and type(row.get(field)) is not bool for field in flags):
            raise ValueError('m6_invalid_private_verdict')
        if phase == 'proactive' and any(row.get(field) is not None and
                (type(row[field]) is not int or not 1 <= row[field] <= 5) for field in SCORE_FIELDS):
            raise ValueError('m6_invalid_private_verdict')
    result = {'primary_units': len(rows), 'flags': {}}
    for field in flags:
        values = [row[field] for row in rows if type(row.get(field)) is bool]
        result['flags'][field] = {'true': sum(values), 'false': len(values)-sum(values), 'applicable': len(values)}
    result['scores'] = {}
    if phase == 'proactive':
        for field in SCORE_FIELDS:
            values = [row[field] for row in rows if type(row.get(field)) is int and 1 <= row[field] <= 5]
            result['scores'][field] = {'sum': sum(values), 'applicable': len(values)}
    return result


def project(native, judging, *, proof):
    """Reduce independently verified private summaries; never copy private text."""
    value = pending_projection()
    value.update(status='qualified' if judging['quality_ready'] else 'incomplete', quality_ready=judging['quality_ready'])
    if native['planned_cells'] != 12 or judging['planned_cells'] != 12:
        raise ValueError('m6_denominator_changed')
    cells = native['cells']
    expected = {(scenario, account) for scenario in SCENARIOS for account in ACCOUNTS}
    if len(cells) != 12 or {(row['scenario'], row['account']) for row in cells} != expected:
        raise ValueError('m6_denominator_changed')
    value['cells'] = [{key: row[key] for key in ('scenario', 'account', 'status', 'horizon_complete',
        'capture_complete', 'profile_available', 'foreground_expectation_origin',
        'original_bounds', 'observed_tick_sends', 'send_observation',
        'original_outcome', 'required_window_outcome')} for row in cells]
    value['native'] = {'provider_attempts': native['provider_attempts'], 'request_ceiling': 758,
        'complete_horizons': sum(row['horizon_complete'] for row in cells),
        'profile_available_cells': sum(row['profile_available'] for row in cells), 'usage': _usage(native['usage']),
        'required_windows': {'planned_cells': 4, **{outcome: sum(row['required_window_outcome'] == outcome for row in cells)
                                                 for outcome in ('hit', 'completed_miss', 'unavailable')}}}
    value['judging'] = {key: judging[key] for key in ('logical_jobs', 'valid_jobs', 'started_attempts',
        'technical_errors', 'interrupted_attempts', 'valid_controls', 'matched_controls', 'failed_controls',
        'candidate_jobs', 'calibration_status', 'controls_qualified')}
    value['judging'].update(control_jobs=70, primary_pass=1, consistency_pass=2, max_attempts_per_job=3,
        max_logical_jobs=158, request_ceiling=474, calibration_before_candidates=True,
        usage=_usage(judging['usage']), phases={phase: _phase(judging['primary'][phase], phase) for phase in PHASES},
        consistency=deepcopy(judging['consistency']))
    value['proof'] = deepcopy(proof)
    validate_public(value)
    return value


def _summary(root, filename, args):
    command = [sys.executable, '-I', '-B', str(root/'source'/PREFIX/filename), 'summary', *args]
    result = subprocess.run(command, env={}, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
    if result.returncode:
        raise ValueError('m6_frozen_summary_failed')
    return json.loads(result.stdout)


def _native_outcomes(study, expected_files):
    result = subprocess.run([sys.executable, '-I', '-B', '-c', NATIVE_OUTCOMES_ADAPTER, str(study)],
        input=json.dumps(expected_files).encode(), env={}, capture_output=True, timeout=120)
    if result.returncode:
        raise ValueError('m6_frozen_native_outcomes_failed')
    return json.loads(result.stdout)


def _foreground_origins(cases):
    """Derive provenance from original corpus bytes, never a judge's label.

    An authored empty object remains authored. Only an absent key permits the
    unchanged four universal criteria; malformed present values are refused.
    """
    if type(cases) is not list or any(type(row) is not dict or type(row.get('id')) is not str for row in cases):
        raise ValueError('m6_invalid_original_foreground')
    indexed = {row['id']: row for row in cases}
    if len(indexed) != len(cases) or not set(SCENARIOS) <= indexed.keys():
        raise ValueError('m6_invalid_original_foreground')
    result = {}
    for scenario in SCENARIOS:
        expected = indexed[scenario].get('expect')
        if type(expected) is not dict or 'foreground' in expected and type(expected['foreground']) is not dict:
            raise ValueError('m6_invalid_original_foreground')
        result[scenario] = 'authored' if 'foreground' in expected else 'universal_only_no_authored_foreground'
    return result


def verified_projection(study, judge):
    """Intended offline summary execution only after all external trust checks."""
    pins = trusted()  # Must precede every caller-controlled path read or execution.
    study, judge = Path(study), Path(judge)
    before = (inventory(study), inventory(judge))
    if (digest(before[0]), digest(before[1])) != (pins['native_files_sha256'], pins['judge_files_sha256']):
        raise ValueError('m6_untrusted_archive_inventory')
    _require_source_paths(*before)
    plan = json.loads(_plain(study/'plan.json'))
    binding = json.loads(_plain(judge/'binding.json'))
    if sha(_plain(study/'plan.json')) != pins['plan_sha256'] \
            or sha(_plain(judge/'binding.json')) != pins['judge_binding_sha256'] \
            or plan.get('native_ref') != pins['native_ref'] or plan.get('source_ref') != pins['helper_ref'] \
            or binding.get('native_source_ref') != pins['native_ref'] \
            or binding.get('helper_ref') != pins['helper_ref'] \
            or binding.get('evaluator_source_ref') != pins['evaluator_ref'] \
            or binding.get('native_plan_sha256') != pins['plan_sha256'] \
            or Path(binding.get('original_study', '')).absolute() != study.absolute():
        raise ValueError('m6_source_or_input_binding_changed')
    for name, pin in binding['original_input_files'].items():
        if sha(_plain(study/name)) != pin or _plain(study/name) != _plain(judge/'inputs'/name):
            raise ValueError('m6_original_copy_changed')
    origins = _foreground_origins(json.loads(_plain(study/'cases.json')))
    ns = _summary(study, 'm6_profile_pilot.py', ['--study', str(study), '--plan-sha256', pins['plan_sha256']])
    js = _summary(judge, 'm6_profile_judge.py', ['--out', str(judge), '--binding-sha256', pins['judge_binding_sha256']])
    if ns['protocol'] != NATIVE_PROTOCOL or js['protocol'] != JUDGE_PROTOCOL:
        raise ValueError('m6_protocol_changed')
    if js['control_jobs'] != 70 or len(binding['jobs']) != js['logical_jobs'] \
            or sum(job['control'] is True for job in binding['jobs']) != 70:
        raise ValueError('m6_job_denominator_changed')
    availability = js.get('availability')
    if type(availability) is not dict or set(availability) != {slot['slot'] for slot in plan['schedule']} \
            or any(type(availability.get(slot['slot'])) is not dict
            or availability[slot['slot']].get('foreground_expectation_origin') != origins[slot['case']]
            for slot in plan['schedule']):
        raise ValueError('m6_foreground_origin_changed')
    outcomes = _native_outcomes(study, before[0])
    if len(outcomes) != 12 or {(r['scenario'], r['account']) for r in outcomes} != \
            {(s, a) for s in SCENARIOS for a in ACCOUNTS}:
        raise ValueError('m6_native_outcome_denominator_changed')
    outcome_by_cell = {(r['scenario'], r['account']): r for r in outcomes}
    cells, usage = [], []
    for slot in plan['schedule']:
        key = slot['slot']; path = study/'receipts'/key
        available = js['availability'][key]
        receipt = json.loads(_plain(path/'receipt.json')) if (path/'receipt.json').exists() else None
        capture = receipt['capture'] if receipt else json.loads(_plain(path/'attempts.json')) if (path/'attempts.json').exists() else {}
        usage += [row.get('usage') for row in capture.get('attempts', [])]
        status = ('complete' if available['horizon_complete'] and available['capture_complete'] and available['stop_code'] is None
                  else 'incomplete' if receipt else 'interrupted' if (study/'receipts'/(key+'.started.json')).exists() else 'unstarted')
        cells.append({'scenario': slot['case'], 'account': slot['account'], 'status': status,
            **{k: available[k] for k in ('horizon_complete', 'capture_complete', 'profile_available',
                                       'foreground_expectation_origin')},
            **{k: v for k, v in outcome_by_cell[slot['case'], slot['account']].items() if k not in ('scenario', 'account')}})
    accounting = _judge_accounting(judge, binding, js)
    result = project({'planned_cells': ns['planned_cells'], 'cells': cells,
        'provider_attempts': len(usage), 'usage': usage}, {**js, **accounting,
        'primary': {phase: [row['verdict'] for row in js['primary'][phase]] for phase in PHASES},
        'consistency': js['second_pass_consistency']}, proof={
            'native_ref': pins['native_ref'], 'helper_ref': pins['helper_ref'], 'evaluator_ref': pins['evaluator_ref'],
            'plan_sha256': pins['plan_sha256'], 'judge_binding_sha256': pins['judge_binding_sha256'],
            'native_inventory_sha256': digest(before[0]), 'judge_inventory_sha256': digest(before[1]),
            'h1_terminal_audit_sha256': pins['h1_terminal_audit_sha256'],
            'native_outcomes_adapter_sha256': sha(NATIVE_OUTCOMES_ADAPTER.encode())})
    if before != (inventory(study), inventory(judge)):
        raise ValueError('m6_archive_changed_during_export')
    return result


def _validate_native_outcome(row):
    bounds = row['original_bounds']
    if type(bounds) is not dict or set(bounds) != {'min', 'max'}:
        raise ValueError('m6_invalid_original_bounds')
    _integer(bounds['min']); _integer(bounds['max'])
    if bounds['min'] > bounds['max']: raise ValueError('m6_invalid_original_bounds')
    required = row['scenario'] in REQUIRED_SCENARIOS
    if row['required_window_outcome'] not in (('hit', 'completed_miss') if required and row['status'] == 'complete'
            else ('unavailable',) if required else ('not_required',)):
        raise ValueError('m6_invalid_native_window_outcome')
    observed = row['observed_tick_sends']
    if observed is not None: _integer(observed)
    result = row['original_outcome']
    if row['status'] != 'complete':
        if result is not None or row['send_observation'] not in ('partial', 'unavailable') \
                or (row['send_observation'] == 'unavailable') != (observed is None) \
                or row['status'] in ('unstarted', 'interrupted') and row['send_observation'] != 'unavailable':
            raise ValueError('m6_incomplete_outcome_is_not_a_pass')
        return
    if row['send_observation'] != 'complete_horizon' or observed is None or type(result) is not dict \
            or set(result) != {'count', 'count_ok', 'over_count', 'requested', 'unsolicited', 'late_answers',
                              'quiet_hours_violations', 'windows', 'listed_scripted_occurrences'}:
        raise ValueError('m6_invalid_original_outcome')
    for field in ('count', 'over_count', 'requested', 'unsolicited', 'late_answers', 'quiet_hours_violations'):
        _integer(result[field], observed)
    _integer(result['listed_scripted_occurrences'])
    if type(result['count_ok']) is not bool or result['count_ok'] != (bounds['min'] <= result['count'] <= bounds['max']) \
            or result['over_count'] != max(0, result['count']-bounds['max']) \
            or sum(result[k] for k in ('requested', 'unsolicited', 'late_answers')) != observed:
        raise ValueError('m6_invalid_original_outcome')
    if type(result['windows']) is not list:
        raise ValueError('m6_invalid_original_windows')
    for window in result['windows']:
        if type(window) is not dict or set(window) != {'kind', 'optional', 'hit'} \
                or window['kind'] not in ('habit_checkin', 'followup') \
                or type(window['optional']) is not bool or type(window['hit']) is not bool:
            raise ValueError('m6_invalid_original_windows')
    required_windows = [w for w in result['windows'] if not w['optional']]
    if bool(required_windows) != required or required and row['required_window_outcome'] != (
            'hit' if all(w['hit'] for w in required_windows) else 'completed_miss'):
        raise ValueError('m6_invalid_native_window_outcome')


def validate_public(value):
    if type(value) is not dict or set(value) != set(pending_projection()) or type(value['schema_version']) is not int or value['schema_version'] != 1 \
            or value['kind'] != PROTOCOL or type(value['planned_cells']) is not int or value['planned_cells'] != 12 \
            or type(value['policy_count']) is not int or value['policy_count'] != 1 \
            or value['cohort'] != 'synthetic_development' or value['publication_ready'] is not False \
            or type(value['quality_ready']) is not bool or digest(value['prior_aborted']) != digest(H1) \
            or type(value['retained_calibrations']) is not list \
            or digest(value['retained_calibrations']) != digest(RETAINED_CALIBRATIONS) or value['limits'] != LIMITS:
        raise ValueError('m6_invalid_public_shape')
    if value['status'] == 'awaiting_reviewed_freeze':
        if digest(value) != digest(pending_projection()): raise ValueError('m6_invalid_pending_projection')
        return value
    if value['status'] not in ('qualified', 'incomplete') or (value['status'] == 'qualified') != value['quality_ready']:
        raise ValueError('m6_invalid_readiness')
    if len(value['cells']) != 12 or {(r['scenario'], r['account']) for r in value['cells']} != \
            {(s, a) for s in SCENARIOS for a in ACCOUNTS}:
        raise ValueError('m6_denominator_changed')
    for row in value['cells']:
        if set(row) != {'scenario', 'account', 'status', 'horizon_complete', 'capture_complete', 'profile_available',
                       'foreground_expectation_origin',
                       'original_bounds', 'observed_tick_sends', 'send_observation', 'original_outcome', 'required_window_outcome'} \
                or row['status'] not in ('complete', 'incomplete', 'interrupted', 'unstarted') \
                or row['foreground_expectation_origin'] not in FOREGROUND_ORIGINS \
                or any(type(row[k]) is not bool for k in ('horizon_complete', 'capture_complete', 'profile_available')):
            raise ValueError('m6_invalid_public_cell')
        if row['status'] == 'complete' and not (row['horizon_complete'] and row['capture_complete']) \
                or row['status'] in ('interrupted', 'unstarted') and any(row[k] for k in
                    ('horizon_complete', 'capture_complete', 'profile_available')):
            raise ValueError('m6_invalid_public_cell')
        _validate_native_outcome(row)
    native, judging = value['native'], value['judging']
    if type(native) is not dict or set(native) != {'provider_attempts', 'request_ceiling', 'complete_horizons', 'profile_available_cells', 'usage', 'required_windows'}:
        raise ValueError('m6_invalid_native_summary')
    required = native['required_windows']
    if type(required) is not dict or set(required) != {'planned_cells', 'hit', 'completed_miss', 'unavailable'} \
            or type(required['planned_cells']) is not int or required['planned_cells'] != 4:
        raise ValueError('m6_required_outcome_denominator_changed')
    for key in ('hit', 'completed_miss', 'unavailable'):
        _integer(required[key], 4)
        if required[key] != sum(row['required_window_outcome'] == key for row in value['cells']):
            raise ValueError('m6_required_outcome_denominator_changed')
    if sum(required[k] for k in ('hit', 'completed_miss', 'unavailable')) != 4:
        raise ValueError('m6_required_outcome_denominator_changed')
    for key, maximum in (('provider_attempts', 758), ('complete_horizons', 12), ('profile_available_cells', 12)):
        _integer(native[key], maximum)
    if type(native['request_ceiling']) is not int or native['request_ceiling'] != 758 or native['complete_horizons'] != sum(r['horizon_complete'] for r in value['cells']) \
            or native['profile_available_cells'] != sum(r['profile_available'] for r in value['cells']):
        raise ValueError('m6_invalid_native_summary')
    if type(judging) is not dict or set(judging) != {'logical_jobs', 'valid_jobs', 'started_attempts', 'technical_errors',
            'interrupted_attempts', 'valid_controls', 'matched_controls', 'failed_controls', 'candidate_jobs',
            'calibration_status', 'controls_qualified', 'control_jobs', 'primary_pass', 'consistency_pass',
            'max_attempts_per_job', 'max_logical_jobs', 'request_ceiling', 'calibration_before_candidates', 'usage', 'phases', 'consistency'}:
        raise ValueError('m6_invalid_judge_summary')
    for key, maximum in (('logical_jobs', 158), ('valid_jobs', 158), ('started_attempts', 474),
                         ('technical_errors', 474), ('interrupted_attempts', 474), ('valid_controls', 70),
                         ('matched_controls', 70), ('failed_controls', 70)):
        _integer(judging[key], maximum)
    if any(type(judging[key]) is not int for key in ('control_jobs', 'primary_pass', 'consistency_pass',
                'max_attempts_per_job', 'max_logical_jobs', 'request_ceiling')) \
            or (judging['control_jobs'], judging['primary_pass'], judging['consistency_pass'], judging['max_attempts_per_job'],
        judging['max_logical_jobs'], judging['request_ceiling']) != (70, 1, 2, 3, 158, 474) \
            or type(judging['controls_qualified']) is not bool or judging['calibration_before_candidates'] is not True \
            or judging['logical_jobs'] < 70 or judging['valid_jobs'] > judging['logical_jobs'] \
            or judging['valid_controls'] > judging['valid_jobs'] or judging['started_attempts'] < judging['valid_jobs'] \
            or judging['controls_qualified'] and judging['valid_controls'] != 70:
        raise ValueError('m6_invalid_judge_summary')
    candidate = judging['candidate_jobs']
    if type(candidate) is not dict or set(candidate) != {'planned', 'started', 'valid'}:
        raise ValueError('m6_invalid_candidate_summary')
    for key in candidate: _integer(candidate[key], 88)
    if candidate['valid'] > candidate['started'] or candidate['started'] > candidate['planned'] \
            or candidate['planned']+70 != judging['logical_jobs'] \
            or candidate['valid']+judging['valid_controls'] != judging['valid_jobs'] \
            or judging['started_attempts'] < judging['valid_controls']+candidate['started'] \
            or judging['valid_jobs']+judging['technical_errors']+judging['interrupted_attempts'] != judging['started_attempts'] \
            or judging['matched_controls']+judging['failed_controls'] != judging['valid_controls'] \
            or judging['controls_qualified'] != (judging['matched_controls'] == 70) \
            or judging['calibration_status'] != ('qualified' if judging['matched_controls'] == 70 else
                 'failed_valid_final' if judging['valid_controls'] == 70 else 'pending'):
        raise ValueError('m6_invalid_calibration_summary')
    if value['quality_ready'] and (not judging['controls_qualified'] or judging['valid_controls'] != 70
            or judging['valid_jobs'] != judging['logical_jobs'] or any(r['status'] != 'complete' or not r['profile_available'] for r in value['cells'])):
        raise ValueError('m6_invalid_readiness')
    for group, attempts in ((native, native['provider_attempts']), (judging, judging['started_attempts'])):
        if set(group['usage']) != set(TOKENS): raise ValueError('m6_invalid_usage')
        for row in group['usage'].values():
            if set(row) != {'known_attempts', 'unknown_attempts', 'observed_tokens'}: raise ValueError('m6_invalid_usage')
            _integer(row['known_attempts'], attempts); _integer(row['unknown_attempts'], attempts)
            if row['known_attempts']+row['unknown_attempts'] != attempts: raise ValueError('m6_invalid_usage')
            if row['known_attempts'] == 0:
                if row['observed_tokens'] is not None: raise ValueError('m6_unknown_usage_is_not_zero')
            else: _integer(row['observed_tokens'])
    if set(judging['phases']) != set(PHASES) or set(judging['consistency']) != set(PHASES):
        raise ValueError('m6_invalid_phase_summary')
    for phase, row in judging['phases'].items():
        expected_flags = PROFILE_FIELDS if phase == 'profile' else FOREGROUND_FIELDS if phase == 'foreground' else PROACTIVE_FIELDS
        if set(row) != {'primary_units', 'flags', 'scores'} or set(row['flags']) != set(expected_flags) \
                or set(row['scores']) != (set(SCORE_FIELDS) if phase == 'proactive' else set()):
            raise ValueError('m6_invalid_phase_summary')
        _integer(row['primary_units'], 20 if phase == 'proactive' else 12)
        for counts in row['flags'].values():
            if set(counts) != {'true', 'false', 'applicable'}: raise ValueError('m6_invalid_phase_summary')
            for count in counts.values(): _integer(count, row['primary_units'])
            if counts['true']+counts['false'] != counts['applicable']: raise ValueError('m6_invalid_phase_summary')
        for counts in row['scores'].values():
            if set(counts) != {'sum', 'applicable'}: raise ValueError('m6_invalid_phase_summary')
            _integer(counts['applicable'], row['primary_units']); _integer(counts['sum'], 5*counts['applicable'])
        pair = judging['consistency'][phase]
        if set(pair) != {'paired_packets', 'same_flags'}: raise ValueError('m6_invalid_consistency')
        _integer(pair['paired_packets'], row['primary_units']); _integer(pair['same_flags'], pair['paired_packets'])
    if judging['phases']['profile']['primary_units'] > native['profile_available_cells']:
        raise ValueError('m6_unavailable_profile_credited')
    if sum(row['primary_units'] for row in judging['phases'].values()) > candidate['valid']:
        raise ValueError('m6_unstarted_candidate_credited')
    proof = value['proof']
    if type(proof) is not dict or set(proof) != {'native_ref', 'helper_ref', 'evaluator_ref', 'plan_sha256',
            'judge_binding_sha256', 'native_inventory_sha256', 'judge_inventory_sha256', 'h1_terminal_audit_sha256',
            'native_outcomes_adapter_sha256'}:
        raise ValueError('m6_invalid_public_proof')
    for key, pin in proof.items(): _hash(pin, 40 if key.endswith('_ref') else 64)
    if proof['native_outcomes_adapter_sha256'] != sha(NATIVE_OUTCOMES_ADAPTER.encode()):
        raise ValueError('m6_native_outcomes_adapter_changed')
    for retained in value['retained_calibrations']:
        if proof['judge_binding_sha256'] == retained['judge_binding_sha256']:
            total = judging['usage']['total_tokens']
            if any(proof[key] != retained[key] for key in ('evaluator_ref', 'judge_inventory_sha256')) \
                    or any(judging[key] != retained[key] for key in ('control_jobs', 'valid_controls', 'matched_controls',
                        'failed_controls', 'candidate_jobs', 'started_attempts', 'technical_errors', 'interrupted_attempts')) \
                    or total != {'known_attempts': retained['known_total_token_attempts'],
                        'unknown_attempts': retained['unknown_total_token_attempts'], 'observed_tokens': retained['known_total_tokens']}:
                raise ValueError('m6_retained_current_record_changed')
    return value
