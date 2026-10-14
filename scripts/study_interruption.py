"""Data-only, source-bound historical interruption note; never partial scores."""
import hashlib
import json
from pathlib import Path
import re

NOTICE=('第一次研究的凍結來源中意外產生未列入計畫的 Python 快取，完整性門檻因此拒絕後續部分執行。'
        '已逐一確認本次產生的快取對應原已釘定原始碼，只移除這些快取；原計畫、來源與已產生收據保留。'
        '第一次資料留作中斷紀錄，不當成完整成績，也不與新一輪合併。新一輪另有獨立的凍結來源與計畫。')
PROOFS={'original_plan_sha256','original_configuration_sha256','original_planned_public_sha256',
        'agent_inventory_sha256','incident_sha256','restoration_sha256','read_only_snapshot_protection_sha256'}

def sha(data):return hashlib.sha256(data).hexdigest()


def verified_projection(records, inventory, original_public):
    records=Path(records);inventory=Path(inventory);original_public=Path(original_public)
    raw={name:(records/name).read_bytes() for name in
         ('incident.private.json','restoration.json','read-only-snapshot-protection.json')}
    incident,restored,protected=(json.loads(raw[name]) for name in raw)
    agent_bytes=inventory.read_bytes();agent=json.loads(agent_bytes)
    old_bytes=original_public.read_bytes();old=json.loads(old_bytes)
    import importlib.util
    spec=importlib.util.spec_from_file_location('interruption_planned_guard',Path(__file__).with_name('planned_study.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.validate_public(old)
    count=incident.get('generated_cache_count')
    if type(count) is not int or count!=15 or restored.get('removed_count')!=count \
            or restored.get('unexpected_files')!=[] or len(incident.get('caches',[]))!=count \
            or any(row.get('code_equals_compile_of_pinned_source') is not True for row in incident['caches']) \
            or incident.get('plan_sha256')!=old['proof']['plan_sha256'] \
            or incident.get('pinned_files_verified')!=restored.get('pinned_files_verified') \
            or protected.get('pinned_bytes_verified')!=incident['pinned_files_verified'] \
            or protected.get('state_receipts_permissions_unchanged') is not True \
            or protected.get('source_and_harness_permissions')!={'files':'0444','directories':'0555'} \
            or agent.get('cache_count')!=count or len(agent.get('cache_inventory',[]))!=count \
            or agent.get('pinned_hash_mismatches')!=[] \
            or agent.get('plan_sha256_now')!=old['proof']['plan_sha256'] \
            or agent.get('configuration_sha256_now')!=old['proof']['configuration_sha256']:
        raise ValueError('unverified_interruption_record')
    peer={row['sha256']:row for row in agent['cache_inventory']}
    if len(peer)!=count or any(row['sha256'] not in peer
            or peer[row['sha256']].get('source_sha256')!=row.get('pinned_source_sha256')
            or peer[row['sha256']].get('manifest_source_sha256')!=row.get('pinned_source_sha256')
            or peer[row['sha256']].get('cache_in_manifest') is not False for row in incident['caches']):
        raise ValueError('unverified_owned_cache_identity')
    value={'schema_version':1,'kind':'always_on_historical_interruption','original_refs':old['refs'],
        'original_planned_file':original_public.name,'complete_study_result':False,'partial_scores_published':False,
        'generated_owned_caches':count,'pinned_source_bytes_verified':True,'owned_caches_removed':True,
        'original_receipts_retained':True,'source_snapshot_protected':True,
        'proof':{'original_plan_sha256':old['proof']['plan_sha256'],
            'original_configuration_sha256':old['proof']['configuration_sha256'],
            'original_planned_public_sha256':sha(old_bytes),'agent_inventory_sha256':sha(agent_bytes),
            **{name.split('.')[0].replace('-','_')+'_sha256':sha(data) for name,data in raw.items()}},
        'notice':NOTICE}
    return validate_public(value)


def validate_public(value):
    keys={'schema_version','kind','original_refs','original_planned_file','complete_study_result',
          'partial_scores_published','generated_owned_caches','pinned_source_bytes_verified',
          'owned_caches_removed','original_receipts_retained','source_snapshot_protected','proof','notice'}
    refs=value.get('original_refs',{})
    if set(value)!=keys or value.get('notice')!=NOTICE \
            or value.get('schema_version')!=1 or value.get('kind')!='always_on_historical_interruption' \
            or value.get('generated_owned_caches')!=15 \
            or any(value.get(key) is not True for key in ('pinned_source_bytes_verified','owned_caches_removed',
                   'original_receipts_retained','source_snapshot_protected')) \
            or any(value.get(key) is not False for key in ('complete_study_result','partial_scores_published')) \
            or not re.fullmatch(r'line-always-on-planned-study-[0-9a-f]{12}\.public\.json',value.get('original_planned_file','')) \
            or set(value.get('proof',{}))!=PROOFS \
            or any(not re.fullmatch(r'[0-9a-f]{64}',digest) for digest in value['proof'].values()) \
            or set(refs)!={'existing','engine','engine_medium','engine_high','engine_sol_low'} \
            or any(not re.fullmatch(r'[0-9a-f]{40}',ref) for ref in refs.values()) \
            or any(refs[arm]!=refs['engine'] for arm in ('engine_medium','engine_high','engine_sol_low')) \
            or value['original_planned_file']!='line-always-on-planned-study-'+value['proof']['original_planned_public_sha256'][:12]+'.public.json':
        raise ValueError('invalid_public_interruption_note')
    return value
