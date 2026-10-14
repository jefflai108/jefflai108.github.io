"""A source-bound public projection of a frozen plan; no run results are read."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ARMS = ('existing', 'engine_medium', 'engine_high', 'engine_sol_low')
PROOFS = ('plan_sha256', 'configuration_sha256', 'cohort_sha256', 'authored_cases_sha256',
          'code_sha256', 'source_files_sha256', 'protocol_sha256')

COLD_VERIFY = r'''
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
expected=json.loads(sys.argv[2])
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
plan_path=root/'plan.json'
if plan_path.is_symlink():raise ValueError('symlink_plan')
plan=json.loads(plan_path.read_text())
# Reject added bytecode and changed import files before loading the frozen runner.
for directory in (root/'source',root/'harness'):
 for path in directory.rglob('*'):
  name=path.relative_to(root).as_posix()
  if path.is_symlink() or path.is_file() and name not in plan['files']:
   raise ValueError('unbound_import_file')
for name,wanted in plan['files'].items():
 path=root/name
 if path.is_symlink() or path.resolve().is_relative_to(root) is not True or not path.is_file() or sha(path)!=wanted:
  raise ValueError('changed_frozen_file')
trusted=expected['files_sha256']
harness_files={path.relative_to(root/'harness').as_posix() for path in (root/'harness').rglob('*') if path.is_file()}
if harness_files!=set(trusted)|{'__init__.py'} or (root/'harness/__init__.py').read_bytes()!=b'':
 raise ValueError('untrusted_harness_inventory')
# The public, committed protocol is the authority before any archive code runs.
if plan.get('refs',{}).get('engine')!=expected['source_ref']:
 raise ValueError('planned_source_mismatch')
if sha(root/'harness/cases.json')!=expected['cases_sha256']:
 raise ValueError('planned_cohort_mismatch')
if any(plan['files'].get('harness/'+name)!=value or sha(root/'harness'/name)!=value for name,value in trusted.items()):
 raise ValueError('planned_protocol_code_mismatch')
if json.loads((root/'cases.json').read_text())!=json.loads((root/'harness/cases.json').read_text()):
 raise ValueError('planned_cohort_subset')
sys.path.insert(0,str(root/'harness'))
import runner
def no_write(*args,**kwargs):raise ValueError('unexpected_plan_write')
runner.write=no_write
verified,episodes=runner.verify(root,frozen=True)
if verified!=plan:
 raise ValueError('planned_source_mismatch')
schedule=plan['execution_order']
account_orders={account:[] for account in ('primary','secondary')}
for index in range(0,len(schedule),8):
 block=schedule[index:index+8]
 if len(block)!=8 or len({row['episode_id'] for row in block})!=1:
  raise ValueError('nonadjacent_account_schedule')
 first='primary' if index//8%2==0 else 'secondary'
 if [block[0]['account'],block[4]['account']]!=[first,'secondary' if first=='primary' else 'primary']:
  raise ValueError('nonalternating_account_schedule')
 for part in (block[:4],block[4:]):
  if len({row['account'] for row in part})!=1:raise ValueError('mixed_account_block')
  account_orders[part[0]['account']].append(tuple(row['arm'] for row in part))
for orders in account_orders.values():
 for index in range(0,len(orders)-23,24):
  if len(set(orders[index:index+24]))!=24:raise ValueError('unbalanced_permutation_cycle')
proof={'plan_sha256':sha(plan_path),'configuration_sha256':plan['configuration_sha256'],
 'cohort_sha256':sha(root/'cases.json'),'authored_cases_sha256':sha(root/'harness/cases.json'),
 'code_sha256':digest({name:value for name,value in plan['files'].items() if name.startswith('harness/')}),
 'source_files_sha256':digest({name:value for name,value in plan['files'].items() if name.startswith('source/')}),
 'protocol_sha256':expected['protocol_sha256']}
print(json.dumps({'refs':plan['refs'],'arms':plan['arms'],'arm_configs':plan['arm_configs'],
 'episode_count':plan['episode_count'],'slot_count':plan['slot_count'],'repeats':plan['repeats'],
 'workers':plan['workers'],'slot_timeout_s':plan['slot_timeout_s'],'smoke':plan['smoke'],
 'executor':plan['executor'],'study_design':plan['study_design'],'study_kind':plan['study_kind'],
 'proof':proof,'schedule_verified':True},sort_keys=True))
'''


def project(value):
    expected_configs = {'existing': {'always_on': None}}
    for arm in ARMS[1:]:
        sol = arm == 'engine_sol_low'
        expected_configs[arm] = {'always_on': {'provider': 'openai' if sol else 'gemini',
            'model': 'gpt-6.1-sol' if sol else 'gemini-3.8-flash',
            'thinking_level': 'low' if sol else arm.removeprefix('engine_'),
            'max_output_tokens': 32768, 'timeout_s': 120}}
    if value.get('arms') != list(ARMS) or value.get('arm_configs') != expected_configs \
            or value.get('smoke') is not False or value.get('executor') is not True \
            or value.get('study_design') != 'background_thinking_variants' \
            or value.get('study_kind') != 'model_quality' or value.get('schedule_verified') is not True \
            or any(type(value.get(key)) is not int or value[key] != count for key, count in
                   (('episode_count',103),('slot_count',824),('repeats',2),('workers',6),('slot_timeout_s',1800))):
        raise ValueError('invalid_planned_study_scope')
    refs, proof = value.get('refs', {}), value.get('proof', {})
    if set(refs) != {'existing','engine',*ARMS[1:]} \
            or any(type(ref) is not str or not re.fullmatch('[0-9a-f]{40}',ref) for ref in refs.values()) \
            or refs['existing'] == refs['engine'] or any(refs[arm] != refs['engine'] for arm in ARMS[1:]) \
            or set(proof) != set(PROOFS) \
            or any(type(digest) is not str or not re.fullmatch('[0-9a-f]{64}',digest) for digest in proof.values()):
        raise ValueError('invalid_planned_study_binding')
    return {'schema_version':1,'kind':'always_on_preregistered_plan','plan_verified':True,
        'full_study_result':False,'quality_complete':False,'publication_ready':False,
        'refs':dict(refs),'arms':list(ARMS),'arm_configs':expected_configs,
        **{key:value[key] for key in ('episode_count','slot_count','repeats','workers','slot_timeout_s')},
        'schedule':{'episode_adjacent_account_blocks':True,'alternating_first_account':True,
                    'per_account_permutation_cycle':24,'combined_chronological_perfect_cycle':False},
        'proof':dict(proof)}


def verified_projection(study, cases, protocol):
    encoded=json.dumps(protocol,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    if protocol.get('source_ref') != cases.get('source_ref') \
            or protocol.get('cases',{}).get('episodes') != cases.get('episodes') \
            or hashlib.sha256(encoded).hexdigest() != cases.get('protocol_sha256'):
        raise ValueError('planned_public_protocol_mismatch')
    expected={'source_ref':cases['source_ref'],'cases_sha256':cases['cases_sha256'],
              'protocol_sha256':cases['protocol_sha256'],'files_sha256':protocol['files_sha256']}
    result=subprocess.run([sys.executable,'-I','-B','-c',COLD_VERIFY,str(Path(study).resolve()),
                           json.dumps(expected)],env={},capture_output=True,text=True,timeout=60)
    if result.returncode:
        raise ValueError('planned_study_not_verified')
    return project(json.loads(result.stdout))


def validate_public(value):
    raw={**value,'smoke':False,'executor':True,'study_design':'background_thinking_variants',
         'study_kind':'model_quality','schedule_verified':True}
    if project(raw) != value:
        raise ValueError('invalid_public_planned_study')
    return value
