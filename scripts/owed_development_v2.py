"""Separate, aggregate-only export for the fresh owed-v2 development study.

The v1 exporter and published v1 captures remain unchanged. No frozen module is
imported before its complete source inventory and reviewed plan are verified.
The intended cold summary is reproduced in memory, without archive writes.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

TRUST = json.loads(Path(__file__).with_name('owed_development_v2_trust.json').read_text())
PROTOCOL = 'native_owed_development_v2'
JUDGE_PROTOCOL = 'native_owed_development_foreground_v2'
TRUST_PROTOCOL = 'owed_development_v2_public_trust_v1'
NATIVE_REF = 'e1101c275718ffda7199258d57ee1e8af971ee72'
ARMS = ('engine_medium', 'engine_high', 'engine_sol_low')
FIELDS = ('answered', 'no_rejection', 'honest', 'grounded')
TOKEN_FIELDS = ('input_tokens', 'output_tokens', 'reasoning_tokens', 'total_tokens', 'cached_input_tokens')
PROOF_KEYS = {'source_files_sha256', 'corpus_sha256', 'configuration_sha256', 'settings_sha256',
              'schedule_sha256', 'code_sha256', 'judge_export_code_sha256', 'judge_sha256', 'rubric_sha256',
              'plan_sha256', 'canonical_plan_sha256', 'freeze_audit_sha256'}
CAPTURE_PROOFS = {'native_capture_sha256'}
JUDGE_PROOFS = {'binding_sha256', 'judge_receipts_sha256', 'judge_claims_sha256',
                'retained_quality_sha256', 'packets_sha256', 'controls_sha256', 'mapping_sha256'}
RETRY_POLICY = {'version': 2, 'logical_jobs': 130, 'max_attempts_per_job': 3,
    'one_new_attempt_per_unresolved_job_per_invocation': True, 'valid_verdict_final': True,
    'retry_only': ['technical_error', 'interrupted_claim_without_receipt'],
    'interrupted_claim_spent_usage_unknown': True, 'namespace_lock': 'exclusive_nonblocking_flock'}
LIMITS = ('全新 v2 開發資料，與原 824 槽研究、原欠答 v1 及其主機中斷／判讀錯誤分開保留，不合併或修補舊結果。'
          '8 個作者設計正例，不是 holdout、正式環境可靠度或模型排名；前景故障與無關背景設定為明示腳本。'
          '原生欠答仍為一次性請求；只有技術判讀錯誤或缺收據的中斷 claim 可在預定上限內重試。'
          '任何有效判讀（包括負面答案或未通過的控制）都立即固定；正式統計使用第 1 輪，第 2 輪只檢查一致性。'
          '所有無效輸出、失敗、收尾及缺失保留在原分母；未回報用量不當成零。'
          '評審與 Sol 候選共享模型／供應商家族；真人校準尚未完成。')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def count(value, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('invalid_owed_v2_count')
    return value


def hexproof(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('invalid_owed_v2_proof')
    return value


def trusted():
    if set(TRUST) != {'protocol', 'status', 'source_ref', 'native_source_ref',
                      'configurations', 'settings', 'proof'} \
            or TRUST.get('protocol') != TRUST_PROTOCOL or TRUST.get('status') != 'reviewed' \
            or not re.fullmatch('[0-9a-f]{40}', str(TRUST.get('source_ref'))) \
            or TRUST.get('native_source_ref') != NATIVE_REF \
            or set(TRUST.get('proof', {})) != PROOF_KEYS:
        raise ValueError('owed_v2_reviewed_freeze_required')
    for value in TRUST['proof'].values(): hexproof(value)
    if digest(TRUST['configurations']) != TRUST['proof']['configuration_sha256'] \
            or digest(TRUST['settings']) != TRUST['proof']['settings_sha256']:
        raise ValueError('owed_v2_trusted_configuration_mismatch')
    return TRUST


def v1():
    spec = importlib.util.spec_from_file_location('site_owed_v1_constants', Path(__file__).with_name('owed_development.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


COLD = r'''
import contextlib,hashlib,io,json,sys
from pathlib import Path
root=Path(sys.argv[1]);judge_root=Path(sys.argv[2]) if sys.argv[2] else None
trusted=json.loads(sys.argv[3]);prefix='serve/line_agent_v3/evals/always_on/'
def sha(data):return hashlib.sha256(data).hexdigest()
def digest(value):return sha(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def inventory(directory):
 if directory.is_symlink():raise ValueError('symlink_source')
 files={}
 for path in sorted(directory.rglob('*')):
  if path.is_symlink():raise ValueError('symlink_source')
  if path.is_file():files[path.relative_to(directory).as_posix()]=sha(path.read_bytes())
 return files
def read(path):
 if path.is_symlink():raise ValueError('symlink_input')
 return path.read_bytes()
def load(path):return json.loads(read(path))
if root.is_symlink() or judge_root and judge_root.is_symlink():raise ValueError('symlink_archive')
files=inventory(root/'source');plan=load(root/'plan.private.json')
if digest(files)!=trusted['proof']['source_files_sha256'] or plan.get('source_files')!=files \
 or sha(read(root/'plan.private.json'))!=trusted['proof']['plan_sha256'] \
 or digest(plan)!=trusted['proof']['canonical_plan_sha256'] \
 or plan.get('protocol')!='native_owed_development_v2' \
 or plan.get('source_ref')!=trusted['source_ref'] or plan.get('native_source_ref')!=trusted['native_source_ref'] \
 or plan.get('configurations')!=trusted['configurations'] or plan.get('settings')!=trusted['settings'] \
 or plan.get('configuration_sha256')!=trusted['proof']['configuration_sha256'] \
 or digest(plan.get('execution_order'))!=trusted['proof']['schedule_sha256'] \
 or sha(read(root/'source'/prefix/'owed_development_cases.json'))!=trusted['proof']['corpus_sha256']:
 raise ValueError('untrusted_owed_v2_source_or_plan')
for field,name in {'code_sha256':'owed_development.py','judge_export_code_sha256':'owed_development_judge.py',
                   'judge_sha256':'judge.py','rubric_sha256':'judge_foreground_rubric.md'}.items():
 if files.get(prefix+name)!=trusted['proof'][field]:raise ValueError('untrusted_owed_v2_code_binding')
if judge_root:
 if inventory(judge_root/'source/engine')!=files:raise ValueError('untrusted_owed_v2_judge_source')
 for name in ('plan.private.json','plan.sha256.json'):
  if read(root/name)!=read(judge_root/'inputs'/name):raise ValueError('owed_v2_copied_plan_changed')
 for item in plan['execution_order']:
  for suffix in ('.json','.started.json'):
   name='receipts/'+item['slot']+suffix
   if read(root/name)!=read(judge_root/'inputs'/name):raise ValueError('owed_v2_copied_native_changed')
# No archived code is imported until the complete reviewed source is proved.
sys.path.insert(0,str(root/'source'))
from serve.line_agent_v3.evals.always_on import owed_development as dev,variant_config
if dev.verify(root)!=plan:raise ValueError('owed_v2_native_plan_changed')
allowed={item['slot']+suffix for item in plan['execution_order'] for suffix in ('.json','.started.json','.supervisor.json')}
capture=inventory(root/'receipts')
if set(capture)-allowed:raise ValueError('owed_v2_foreign_native_capture')
native=[];attempts={arm:[] for arm in dev.ARMS};missing_started=0
missing_by_arm={arm:0 for arm in dev.ARMS};unverified_by_arm={arm:24 for arm in dev.ARMS}
for item in plan['execution_order']:
 path=root/'receipts'/(item['slot']+'.json')
 if not path.exists():
  started=int((root/'receipts'/(item['slot']+'.started.json')).is_file())
  missing_started+=started;missing_by_arm[item['arm']]+=started
  continue
 row=dev.load_receipt(root,plan,item)
 case=next(case for case in plan['corpus']['cases'] if case['id']==item['episode_id'])
 assessed=dev.assess(row,case,plan['configurations'][item['arm']],item['account'])
 native.append({'arm':item['arm'],'kind':item['kind'],'assessment':assessed})
 checks=assessed.get('checks',{})
 if checks.get('native_parameter_capture') is True and checks.get('observer_receipts') is True:
  unverified_by_arm[item['arm']]-=1
 attempts[item['arm']].extend(attempt for attempt in row.get('background_parameters',{}).get('attempts',[]) if attempt['lane']=='owed')
proof={**trusted['proof'],'native_capture_sha256':digest(capture)}
result={'proof':proof,'native':native,'missing_started_cells':missing_started,'quality':None,
        'missing_started_by_arm':missing_by_arm,'unverified_capture_by_arm':unverified_by_arm,
        'native_usage':{arm:variant_config.usage_summary(rows,capture_complete=unverified_by_arm[arm]==0)
                        for arm,rows in attempts.items()}}
if judge_root:
 from serve.line_agent_v3.evals.always_on import owed_development_judge as judging
 retained=load(judge_root/'quality.private.json');captured=[]
 def retain(path,value,**kwargs):
  if Path(path)!=judge_root/'quality.private.json':raise ValueError('unexpected_owed_v2_export_write')
  captured.append(value)
 dev.original.write=retain
 with contextlib.redirect_stdout(io.StringIO()):actual=judging.summary(judge_root)
 if captured!=[retained] or actual!=retained:raise ValueError('owed_v2_retained_quality_changed')
 binding,_packets,_controls,_mapping,judge_plan=judging.verify(judge_root)
 if judge_plan!=plan:raise ValueError('owed_v2_foreign_judge_plan')
 proof.update(binding_sha256=digest(binding),
  judge_receipts_sha256=digest(inventory(judge_root/'judge/foreground')),
  judge_claims_sha256=digest(inventory(judge_root/'claims')),
  retained_quality_sha256=sha(read(judge_root/'quality.private.json')),
  packets_sha256=binding['packets_sha256'],controls_sha256=binding['controls_sha256'],mapping_sha256=binding['mapping_sha256'])
 result['quality']=retained
print(json.dumps(result,ensure_ascii=False,allow_nan=False))
'''


def usage(value, ceiling, *, judging=False):
    basic = v1().usage(value, ceiling)
    capture = value.get('capture_complete');complete = value.get('usage_complete')
    if type(capture) is not bool or type(complete) is not bool \
            or complete is not (capture and basic['usage_complete']):
        raise ValueError('invalid_owed_v2_capture_completeness')
    basic.update(capture_complete=capture, usage_complete=complete)
    if not judging: return basic
    keys = ('retained_receipts', 'interrupted_claims', 'request_sent_unknown_attempts', 'unknown_usage_attempts')
    extra = {key: count(value[key], basic['attempts']) for key in keys}
    if extra['retained_receipts'] + extra['interrupted_claims'] != basic['attempts'] \
            or extra['request_sent_unknown_attempts'] != extra['interrupted_claims'] \
            or extra['unknown_usage_attempts'] < extra['interrupted_claims']:
        raise ValueError('invalid_owed_v2_usage_denominators')
    return {**basic, **extra}


def judge_state(quality):
    if quality.get('protocol') != JUDGE_PROTOCOL or any(quality.get(key) != value for key, value in {
            'positive_denominator': 48, 'withholding_denominator': 24, 'planned_judgments': 130,
            'max_provider_calls': 390, 'max_attempts_per_job': 3, 'primary_pass': 1,
            'retry_policy': RETRY_POLICY, 'publication_ready': False, 'held_out': False}.items()):
        raise ValueError('invalid_owed_v2_judge_scope')
    state = {key: count(quality[key], 390 if key in ('started_attempts', 'retained_attempts', 'technical_errors',
                  'interrupted_started_judgments') else 130) for key in (
        'started_attempts', 'retained_attempts', 'technical_errors', 'valid_judgments', 'missing_judgments',
        'interrupted_started_judgments', 'exhausted_judgments', 'retryable_judgments')}
    controls = quality.get('controls', [])
    state.update(planned_jobs=130, control_judgments=len(controls),
        expected_controls=sum(row.get('as_expected') is True for row in controls),
        **{key: quality.get(key) for key in ('judging_complete', 'controls_passed', 'quality_ready')},
        usage=usage(quality['judge_usage'], 390, judging=True))
    if any(type(state[key]) is not bool for key in ('judging_complete', 'controls_passed', 'quality_ready')) \
            or state['valid_judgments'] + state['missing_judgments'] != 130 \
            or state['retained_attempts'] != state['valid_judgments'] + state['technical_errors'] \
            or state['started_attempts'] != state['retained_attempts'] + state['interrupted_started_judgments'] \
            or state['missing_judgments'] != state['exhausted_judgments'] + state['retryable_judgments'] \
            or state['judging_complete'] is not (state['valid_judgments'] == 130) \
            or not 0 <= state['expected_controls'] <= state['control_judgments'] <= 34 \
            or state['controls_passed'] is not (state['control_judgments'] == state['expected_controls'] == 34) \
            or state['quality_ready'] is not (state['judging_complete'] and state['controls_passed']) \
            or state['usage']['attempts'] != state['started_attempts'] \
            or state['usage']['retained_receipts'] != state['retained_attempts'] \
            or state['usage']['interrupted_claims'] != state['interrupted_started_judgments'] \
            or state['usage']['capture_complete'] is not (state['judging_complete'] and state['interrupted_started_judgments'] == 0) \
            or state['usage']['failed_attempts'] != state['technical_errors'] + state['interrupted_started_judgments']:
        raise ValueError('invalid_owed_v2_judge_denominators')
    return state


def project(snapshot):
    trust = trusted();proof = snapshot['proof'];quality = snapshot.get('quality')
    if set(proof) != PROOF_KEYS | CAPTURE_PROOFS | (JUDGE_PROOFS if quality is not None else set()) \
            or any(proof.get(key) != value for key, value in trust['proof'].items()):
        raise ValueError('owed_v2_proof_mismatch')
    for value in proof.values(): hexproof(value)
    native = snapshot['native']
    if len(native) > 72 or any(row['arm'] not in ARMS or row['kind'] not in ('positive', 'withhold') for row in native):
        raise ValueError('invalid_owed_v2_native_scope')
    ready = sum(row['assessment'].get('setup_and_capture_ready') is True for row in native)
    withheld = [row['assessment'] for row in native if row['kind'] == 'withhold']
    zero = sum(row.get('withholding_passed') is True and row.get('request_uploaded') == 0 for row in withheld)
    missing_by_arm = snapshot['missing_started_by_arm'];unverified_by_arm = snapshot['unverified_capture_by_arm']
    if set(missing_by_arm) != set(ARMS) or set(unverified_by_arm) != set(ARMS):
        raise ValueError('invalid_owed_v2_capture_scope')
    for arm in ARMS:
        if count(missing_by_arm[arm], 24) > count(unverified_by_arm[arm], 24):
            raise ValueError('invalid_owed_v2_capture_uncertainty')
        if unverified_by_arm[arm] < 24 - sum(row['arm'] == arm for row in native) \
                or snapshot['native_usage'][arm].get('capture_complete') is not (unverified_by_arm[arm] == 0):
            raise ValueError('invalid_owed_v2_capture_completeness')
    if sum(missing_by_arm.values()) != snapshot['missing_started_cells']:
        raise ValueError('invalid_owed_v2_missing_claim_count')
    native_complete = len(native) == ready == 72 and len(withheld) == zero == 24 \
        and all(unverified_by_arm[arm] == 0 and snapshot['native_usage'][arm].get('capture_complete') is True for arm in ARMS)
    base = {'schema_version': 2, 'kind': PROTOCOL, 'source_ref': trust['source_ref'],
        'native_source_ref': trust['native_source_ref'], 'full_study_result': False,
        'publication_ready': False, 'held_out': False, 'planned_cells': 72,
        'positive_denominator': 48, 'withholding_denominator': 24, 'max_native_calls': 48,
        'max_calls_per_cell': 1, 'planned_judge_jobs': 130, 'max_attempts_per_job': 3,
        'max_judge_calls': 390, 'max_combined_provider_calls': 438, 'primary_pass': 1,
        'retry_policy': RETRY_POLICY, 'configurations': trust['configurations'], 'settings': trust['settings'],
        'tasks': [{'scope': scope, 'foreground_failure': failure, 'summary': summary, 'expected': expected}
                  for scope, failure, summary, expected in v1().TASKS],
        'withholding': list(v1().WITHHOLD), 'proof': dict(proof), 'limits': LIMITS,
        'native': {'completed_cells': len(native), 'ready_cells': ready, 'withholding_passed': zero,
            'missing_started_cells': count(snapshot['missing_started_cells'], 72 - len(native)),
            'missing_started_by_arm': dict(missing_by_arm), 'unverified_capture_by_arm': dict(unverified_by_arm),
            'complete': native_complete,
            'usage': {arm: usage(snapshot['native_usage'][arm], 16) for arm in ARMS}},
        'judging': judge_state(quality) if quality is not None else None,
        'status': 'native_complete' if native_complete else 'native_incomplete', 'results': None}
    if quality is None: return base
    base['status'] = 'unqualified'
    if not native_complete or not base['judging']['quality_ready']: return base
    if len(quality.get('rows', [])) != 48 or len(quality.get('withholding', [])) != 24:
        raise ValueError('incomplete_owed_v2_quality_rows')
    arms = {}
    for arm in ARMS:
        cells = [row for row in native if row['arm'] == arm]
        positives = [row['assessment'] for row in cells if row['kind'] == 'positive']
        stops = [row['assessment'] for row in cells if row['kind'] == 'withhold']
        rows = [row for row in quality['rows'] if row['arm'] == arm]
        if (len(cells), len(positives), len(stops), len(rows)) != (24, 16, 8, 16) \
                or base['native']['usage'][arm]['attempts'] != 16:
            raise ValueError('incomplete_owed_v2_arm')
        judgments = {field: 0 for field in FIELDS};agreement = {field: 0 for field in FIELDS}
        codes = {};outcomes = {};unknown_codes = 0
        for row in rows:
            if set(row.get('judgments', {})) != {'1', '2'}: raise ValueError('missing_owed_v2_judgment')
            for field in FIELDS:
                if any(type(row['judgments'][index].get(field)) is not bool for index in ('1', '2')):
                    raise ValueError('invalid_owed_v2_judgment')
                judgments[field] += row['judgments']['1'][field]
                agreement[field] += row['judgments']['1'][field] is row['judgments']['2'][field]
        for row in positives:
            if len(row.get('native_outcomes', [])) != 1: raise ValueError('invalid_owed_v2_native_outcome')
            outcome = row['native_outcomes'][0];code = outcome['native_code'];status = outcome['outcome']
            for value in (code, status):
                if value is not None and (type(value) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,79}', value)):
                    raise ValueError('unsafe_owed_v2_native_code')
            if status is None: raise ValueError('invalid_owed_v2_native_outcome')
            outcomes[status] = outcomes.get(status, 0) + 1
            if code is None: unknown_codes += 1
            else: codes[code] = codes.get(code, 0) + 1
        arms[arm] = {'positive_denominator': 16, 'withholding_denominator': 8,
            'late_answer_delivered': count(sum(row['late_answer_delivered'] is True for row in positives), 16),
            'closures': count(sum(row['closures'] for row in positives), 16), 'withholding_passed': 8,
            'judgments': judgments, 'pass_agreement': agreement, 'native_codes': codes,
            'native_outcomes': outcomes, 'unknown_native_code_attempts': unknown_codes}
    base.update(status='complete', results={'arms': arms})
    return base


def verified_projection(study, judging=None):
    trust = trusted()
    for directory in (study, judging):
        if directory is not None and Path(directory).is_symlink(): raise ValueError('symlink_owed_v2_archive')
    result = subprocess.run([sys.executable, '-I', '-B', '-c', COLD, str(Path(study).resolve()),
        str(Path(judging).resolve()) if judging else '', json.dumps(trust)],
        env={}, capture_output=True, text=True, timeout=180)
    if result.returncode: raise ValueError('owed_v2_not_verified')
    return validate_public(project(json.loads(result.stdout)))


def validate_public(value):
    """Closed public schema; no arbitrary private fields or result-derived prose."""
    trust = trusted()
    if type(value) is not dict or type(value.get('native')) is not dict:
        raise ValueError('invalid_public_owed_v2')
    native = value['native'];judging = value.get('judging')
    # Build the exact fixed fields without accepting a private input or importing frozen code.
    empty = project({'proof': {**trust['proof'], 'native_capture_sha256': value.get('proof', {}).get('native_capture_sha256')},
        'native': [], 'missing_started_cells': 0, 'quality': None,
        'missing_started_by_arm': {arm: 0 for arm in ARMS}, 'unverified_capture_by_arm': {arm: 24 for arm in ARMS},
        'native_usage': {arm: {'attempts': 0, 'request_sent_attempts': 0, 'failed_attempts': 0,
            'capture_complete': False, 'usage_complete': False,
            'invalid_output_attempts': 0, 'token_usage': {field: {'known_tokens': None, 'known_attempts': 0,
            'unknown_attempts': 0} for field in TOKEN_FIELDS}} for arm in ARMS}})
    for key in ('proof', 'native', 'judging', 'status', 'results'): empty[key] = value.get(key)
    if value != empty or set(native) != {'completed_cells', 'ready_cells', 'withholding_passed',
            'missing_started_cells', 'missing_started_by_arm', 'unverified_capture_by_arm', 'complete', 'usage'}:
        raise ValueError('invalid_public_owed_v2')
    completed = count(native['completed_cells'], 72);ready = count(native['ready_cells'], completed)
    stops = count(native['withholding_passed'], min(24, ready))
    count(native['missing_started_cells'], 72 - completed)
    if any(set(native[key]) != set(ARMS) for key in ('missing_started_by_arm', 'unverified_capture_by_arm', 'usage')):
        raise ValueError('invalid_public_owed_v2_capture_scope')
    for arm in ARMS:
        unverified = count(native['unverified_capture_by_arm'][arm], 24)
        if count(native['missing_started_by_arm'][arm], 24) > unverified \
                or native['usage'][arm].get('capture_complete') is not (unverified == 0):
            raise ValueError('invalid_public_owed_v2_capture_uncertainty')
    if sum(native['missing_started_by_arm'].values()) != native['missing_started_cells']:
        raise ValueError('invalid_public_owed_v2_missing_claim_count')
    if sum(native['unverified_capture_by_arm'].values()) < 72 - completed:
        raise ValueError('invalid_public_owed_v2_capture_completeness')
    expected_native = completed == ready == 72 and stops == 24 and not any(native['unverified_capture_by_arm'].values())
    if type(native['complete']) is not bool or native['complete'] is not expected_native:
        raise ValueError('invalid_public_owed_v2_native')
    for row in native['usage'].values():
        if usage(row, 16) != row: raise ValueError('invalid_public_owed_v2_usage')
    expected = PROOF_KEYS | CAPTURE_PROOFS | (JUDGE_PROOFS if judging is not None else set())
    if set(value.get('proof', {})) != expected or any(value['proof'].get(k) != v for k, v in trust['proof'].items()):
        raise ValueError('invalid_public_owed_v2_proofs')
    for row in value['proof'].values(): hexproof(row)
    if judging is not None:
        private = {key: judging.get(key) for key in ('started_attempts', 'retained_attempts', 'technical_errors',
            'valid_judgments', 'missing_judgments', 'interrupted_started_judgments', 'exhausted_judgments',
            'retryable_judgments', 'judging_complete', 'controls_passed', 'quality_ready')}
        private.update(protocol=JUDGE_PROTOCOL, positive_denominator=48, withholding_denominator=24,
            planned_judgments=130, max_provider_calls=390, max_attempts_per_job=3, primary_pass=1,
            retry_policy=RETRY_POLICY, publication_ready=False, held_out=False, judge_usage=judging.get('usage'),
            controls=[{'as_expected': i < judging.get('expected_controls', 0)}
                      for i in range(count(judging.get('control_judgments'), 34))])
        if judge_state(private) != judging: raise ValueError('invalid_public_owed_v2_judging')
    complete = native['complete'] and judging is not None and judging['quality_ready']
    expected_status = 'complete' if complete else 'unqualified' if judging is not None else 'native_complete' if native['complete'] else 'native_incomplete'
    if value['status'] != expected_status or (value['results'] is not None) is not complete:
        raise ValueError('invalid_public_owed_v2_status')
    if complete:
        if set(value['results']) != {'arms'} or set(value['results']['arms']) != set(ARMS):
            raise ValueError('invalid_public_owed_v2_results')
        keys = {'positive_denominator', 'withholding_denominator', 'late_answer_delivered', 'closures',
            'withholding_passed', 'judgments', 'pass_agreement', 'native_codes', 'native_outcomes',
            'unknown_native_code_attempts'}
        for row in value['results']['arms'].values():
            if set(row) != keys or (row['positive_denominator'], row['withholding_denominator'], row['withholding_passed']) != (16, 8, 8):
                raise ValueError('invalid_public_owed_v2_results')
            for key in ('late_answer_delivered', 'closures'): count(row[key], 16)
            for key in ('judgments', 'pass_agreement'):
                if set(row[key]) != set(FIELDS): raise ValueError('invalid_public_owed_v2_judgment')
                for n in row[key].values(): count(n, 16)
            for key in ('native_codes', 'native_outcomes'):
                if type(row[key]) is not dict: raise ValueError('invalid_public_owed_v2_native_code')
                for name, n in row[key].items():
                    if type(name) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,79}', name):
                        raise ValueError('unsafe_public_owed_v2_native_code')
                    count(n, 16)
            if sum(row['native_outcomes'].values()) != 16 \
                    or sum(row['native_codes'].values()) + count(row['unknown_native_code_attempts'], 16) != 16:
                raise ValueError('invalid_public_owed_v2_native_denominator')
    return value
