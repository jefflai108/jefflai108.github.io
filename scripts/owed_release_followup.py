"""Separate integrated-release owed follow-up; no final freeze is implied.

The original 617/e110 v2 exporter, trust and artifacts remain intact. A fresh
private instance reuses that reviewed verifier only after a new trust binding
is supplied. Profile setup is independently checked against every receipt.

A reviewed binding contains ``v2`` (the original closed trust schema, with
the final reviewed native/helper/source/plan hashes), both reused-file hashes,
and the exact profile declaration below. The committed entry intentionally has
no binding while native/helper and execution freezes are pending.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re

TRUST = json.loads(Path(__file__).with_name('owed_release_followup_trust.json').read_text())
TRUST_PROTOCOL = 'owed_release_followup_public_trust_v1'
KIND = 'native_owed_integrated_release_followup'
ALIAS = 'line-always-on-owed-release-followup.public.json'
BASE_EXPORTER_SHA256 = '8013fb0958102bdd6dad6d439fa1165aed100e723e16cd8596d1f8471a955df8'
BASE_TRUST_SHA256 = 'b46d3bf4cfc5438066367c87ec9cfd41ac0ba65e2dc9f9a8f5643bdca7ad5f6a'
OWED_PROMPT_SHA256 = 'd6ffecb0b394bdb3d10ad4b731a18db9eb1a334985b9540d500d72fd8978a5ec'
PROFILE_SETUP = {
    'version': 1, 'hook': 'durable_profile.extract_profile', 'result': 'empty_profile',
    'source_projection': 'native_owned_history', 'source_validation_and_privacy_fences': 'native',
    'provider_stage': 'scripted_no_credentials_or_uploads', 'quality_measured': False,
    'application_factory': 'sidecar._line_diary_application',
    'derivation_driver': 'native_claim_run_line_derivation_settle',
    'derivation_schedule': 'after_turn_before_engine_and_before_tick',
    'derivation_pass_limit': 64,
    'summary_provider_stage': 'scripted_existing_fixture_summary_5_or_6_no_credentials_or_uploads',
    'derivation_errors': 'invalidate_setup',
}
CALL_KEYS = {'module', 'source_count', 'sources_sha256', 'code', 'credential_read', 'real_socket_upload'}
LIMITS = ('這是整合釋出版本的獨立欠答追蹤，沿用 v2 原生／判讀協定；不是單獨 guard 修補的因果實驗。'
          '原生版本、profile／context 來源與明示的確定性 profile 設定均已改變；與 617/e110 或其他舊輪的差異不能單獨歸因於 guard 或模型，亦不合併或重算舊結果。'
          '本輪三組候選共用同一整合原生版本、非模型設定與 profile 腳本，只改已列出的模型政策。8 個重用的作者設計正例不是 holdout，不宣告模型排名或正式環境可靠度。'
          'profile 安裝與實際呼叫分開報告；允許原生路徑未呼叫，腳本不衡量 profile 模型品質。'
          '本輪明示使用原生應用與派生工作流程，在每回合後、引擎與每次 tick 前處理；每次最多 64 輪，派生錯誤使設定不合格。摘要使用既有固定 5／6 腳本，與空 profile 設定皆不讀憑證或進行模型上傳；不據此比較延遲或 profile 品質。'
          '只衡量此欠答題組，不衡量 M6 的抽取、主動關心或 composer 品質。所有正例、失敗、收尾及停止控制保留原分母；未知用量不當成零。'
          'AI 品質通過與可泛化／可發布的結論分開；評審與 Sol 共享模型家族，真人校準尚未完成。')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode())


def _base_module():
    path = Path(__file__).with_name('owed_development_v2.py')
    trust = path.with_name('owed_development_v2_trust.json')
    if path.is_symlink() or trust.is_symlink() or sha(path.read_bytes()) != BASE_EXPORTER_SHA256 \
            or sha(trust.read_bytes()) != BASE_TRUST_SHA256:
        raise ValueError('owed_followup_reused_verifier_changed')
    spec = importlib.util.spec_from_file_location('site_owed_release_private_v2', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def trusted_module():
    if set(TRUST) != {'protocol', 'status', 'binding'} or TRUST.get('protocol') != TRUST_PROTOCOL \
            or TRUST.get('status') != 'reviewed' or type(TRUST.get('binding')) is not dict:
        raise ValueError('owed_followup_reviewed_freeze_required')
    binding = TRUST['binding']
    if set(binding) != {'v2', 'reused_exporter_sha256', 'prior_v2_trust_sha256', 'profile_setup'} \
            or binding['reused_exporter_sha256'] != BASE_EXPORTER_SHA256 \
            or binding['prior_v2_trust_sha256'] != BASE_TRUST_SHA256 \
            or digest(binding['profile_setup']) != digest(PROFILE_SETUP):
        raise ValueError('owed_followup_invalid_trust_binding')
    module = _base_module()
    prior = copy.deepcopy(module.trusted())
    current = copy.deepcopy(binding['v2'])
    if type(current) is not dict or any(not re.fullmatch('[0-9a-f]{40}', str(current.get(key)))
                                      for key in ('source_ref', 'native_source_ref')) \
            or current['source_ref'] == prior['source_ref'] \
            or current['native_source_ref'] == prior['native_source_ref'] \
            or digest(current.get('configurations')) != digest(prior['configurations']) \
            or digest(current.get('settings')) != digest({**prior['settings'], 'reviewed_profile_setup': PROFILE_SETUP}) \
            or any(current.get('proof', {}).get(key) != prior['proof'][key] for key in
                   ('corpus_sha256', 'configuration_sha256', 'schedule_sha256', 'judge_sha256', 'rubric_sha256')):
        raise ValueError('owed_followup_changed_fixed_method')
    # Local instance only: neither the published module nor its trust file is
    # assigned to, edited or repinned. Its original strict guards still run.
    module.NATIVE_REF = current['native_source_ref']
    module.TRUST = current
    module.trusted()
    return module, prior


def _read(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('owed_followup_input_not_plain_file')
    return path.read_bytes()


def _inventory(directory):
    if directory.is_symlink(): raise ValueError('owed_followup_symlink_capture')
    if not directory.exists(): return {}
    result = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink(): raise ValueError('owed_followup_symlink_capture')
        if path.is_file(): result[path.relative_to(directory).as_posix()] = sha(path.read_bytes())
    return result


def profile_snapshot(study, binding):
    """Read only declared setup metadata, with raw plan and capture bindings."""
    root = Path(study)
    if root.is_symlink(): raise ValueError('owed_followup_symlink_archive')
    wire = _read(root / 'plan.private.json')
    plan = json.loads(wire)
    if sha(wire) != binding['proof']['plan_sha256'] or digest(plan) != binding['proof']['canonical_plan_sha256'] \
            or digest(plan.get('settings', {}).get('reviewed_profile_setup')) != digest(PROFILE_SETUP):
        raise ValueError('owed_followup_profile_plan_mismatch')
    prompt = root / 'source/serve/memory/prompts/line_owed_answer_zh.txt'
    if sha(_read(prompt)) != OWED_PROMPT_SHA256:
        raise ValueError('owed_followup_prompt_changed')
    captures = _inventory(root / 'receipts')
    by_arm = {arm: {'receipt_cells': 0, 'cells_with_calls': 0, 'observed_calls': 0, 'source_count': 0}
              for arm in ('engine_medium', 'engine_high', 'engine_sol_low')}
    private = {}
    for item in plan['execution_order']:
        path = root / 'receipts' / (item['slot'] + '.json')
        if not path.exists(): continue
        data = json.loads(_read(path))
        boundary = data.get('development_boundary', {})
        setup = boundary.get('reviewed_profile_setup')
        if type(setup) is not dict or set(setup) != {'declaration', 'installed', 'calls'} \
                or digest(setup['declaration']) != digest(PROFILE_SETUP) or setup['installed'] is not True \
                or type(setup['calls']) is not list or boundary.get('blocked') != []:
            raise ValueError('owed_followup_profile_receipt_unverified')
        for call in setup['calls']:
            if type(call) is not dict or set(call) != CALL_KEYS \
                    or call['module'] not in ('durable_profile', 'serve.memory.durable_profile') \
                    or type(call['source_count']) is not int or call['source_count'] <= 0 \
                    or type(call['sources_sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', call['sources_sha256']) \
                    or call['code'] != 'empty_reviewed_profile_setup' \
                    or call['credential_read'] is not False or call['real_socket_upload'] is not False:
                raise ValueError('owed_followup_profile_call_unverified')
        counters = by_arm[item['arm']]
        counters['receipt_cells'] += 1
        counters['cells_with_calls'] += bool(setup['calls'])
        counters['observed_calls'] += len(setup['calls'])
        counters['source_count'] += sum(call['source_count'] for call in setup['calls'])
        private[item['slot']] = setup
    totals = {key: sum(row[key] for row in by_arm.values()) for key in next(iter(by_arm.values()))}
    return {'profile': {'declaration': dict(PROFILE_SETUP), **totals, 'by_arm': by_arm,
                        'complete': totals['receipt_cells'] == 72},
            'profile_metadata_sha256': digest(private), 'native_capture_sha256': digest(captures)}


def project(study, profile, prior):
    module, expected_prior = trusted_module()
    if prior != expected_prior: raise ValueError('owed_followup_prior_changed')
    module.validate_public(study)
    if profile['native_capture_sha256'] != study['proof']['native_capture_sha256'] \
            or profile['profile']['receipt_cells'] != study['native']['completed_cells']:
        raise ValueError('owed_followup_capture_changed')
    result = {'schema_version': 1, 'kind': KIND, 'native_protocol': module.PROTOCOL,
        'comparison_scope': 'integrated_release_followup', 'quality_scope': 'owed_answers_only',
        'guard_only_causality': False, 'pooled_with_prior_studies': False,
        'publication_ready': False, 'held_out': False,
        'quality_ready': study['status'] == 'complete' and profile['profile']['complete'],
        'prior_study': {'source_ref': prior['source_ref'], 'native_source_ref': prior['native_source_ref'],
                        'public_alias': 'line-always-on-owed-development-v2.public.json'},
        'study': study, 'profile_setup': profile['profile'],
        'proof': {'reused_exporter_sha256': BASE_EXPORTER_SHA256, 'prior_v2_trust_sha256': BASE_TRUST_SHA256,
                  'profile_metadata_sha256': profile['profile_metadata_sha256']}, 'limits': LIMITS}
    return validate_public(result)


def verified_projection(study, judging=None):
    module, prior = trusted_module()  # Closed before archive reads or execution.
    before = profile_snapshot(study, module.TRUST)
    value = module.verified_projection(study, judging)
    after = profile_snapshot(study, module.TRUST)
    if before != after: raise ValueError('owed_followup_profile_capture_changed')
    return project(value, after, prior)


def validate_public(value):
    module, prior = trusted_module()
    if type(value) is not dict or type(value.get('study')) is not dict or type(value.get('profile_setup')) is not dict:
        raise ValueError('invalid_public_owed_followup')
    study = module.validate_public(value['study'])
    profile = value['profile_setup']
    keys = {'declaration', 'receipt_cells', 'cells_with_calls', 'observed_calls', 'source_count', 'by_arm', 'complete'}
    if set(profile) != keys or digest(profile['declaration']) != digest(PROFILE_SETUP) or set(profile['by_arm']) != set(module.ARMS):
        raise ValueError('invalid_public_owed_followup_profile')
    for row in [profile, *profile['by_arm'].values()]:
        maximum = 72 if row is profile else 24
        module.count(row['receipt_cells'], maximum)
        module.count(row['cells_with_calls'], row['receipt_cells'])
        for key in ('observed_calls', 'source_count'):
            if type(row[key]) is not int or row[key] < row['cells_with_calls']:
                raise ValueError('invalid_public_owed_followup_profile_counts')
        if row['source_count'] < row['observed_calls'] \
                or (row['observed_calls'] == 0) is not (row['cells_with_calls'] == 0) \
                or row['observed_calls'] == 0 and row['source_count'] != 0:
            raise ValueError('invalid_public_owed_followup_profile_counts')
        if row is not profile and set(row) != {'receipt_cells', 'cells_with_calls', 'observed_calls', 'source_count'}:
            raise ValueError('invalid_public_owed_followup_profile')
    if any(profile[key] != sum(row[key] for row in profile['by_arm'].values())
           for key in ('receipt_cells', 'cells_with_calls', 'observed_calls', 'source_count')) \
            or profile['receipt_cells'] != study['native']['completed_cells'] \
            or type(profile['complete']) is not bool or profile['complete'] is not (profile['receipt_cells'] == 72):
        raise ValueError('invalid_public_owed_followup_profile_counts')
    proof = value.get('proof', {})
    if set(proof) != {'reused_exporter_sha256', 'prior_v2_trust_sha256', 'profile_metadata_sha256'} \
            or proof['reused_exporter_sha256'] != BASE_EXPORTER_SHA256 or proof['prior_v2_trust_sha256'] != BASE_TRUST_SHA256:
        raise ValueError('invalid_public_owed_followup_proof')
    module.hexproof(proof['profile_metadata_sha256'])
    expected = {'schema_version': 1, 'kind': KIND, 'native_protocol': module.PROTOCOL,
        'comparison_scope': 'integrated_release_followup', 'quality_scope': 'owed_answers_only',
        'guard_only_causality': False, 'pooled_with_prior_studies': False,
        'publication_ready': False, 'held_out': False,
        'quality_ready': study['status'] == 'complete' and profile['complete'],
        'prior_study': {'source_ref': prior['source_ref'], 'native_source_ref': prior['native_source_ref'],
                        'public_alias': 'line-always-on-owed-development-v2.public.json'},
        'study': study, 'profile_setup': profile, 'proof': proof, 'limits': LIMITS}
    if value != expected or any(type(value[key]) is not bool for key in
            ('guard_only_causality', 'pooled_with_prior_studies', 'publication_ready', 'held_out', 'quality_ready')):
        raise ValueError('invalid_public_owed_followup')
    return value
