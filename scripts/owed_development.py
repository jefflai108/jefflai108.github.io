"""Public aggregate export of the separately frozen 72-cell owed development cohort.

The committed Git archive digest is checked before importing frozen code. Native
and judge summaries are reproduced in memory; no archive write or inference is
allowed. Rejected parsed model JSON is never part of this public projection.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

TRUST = json.loads(Path(__file__).with_name('owed_development_trust.json').read_text())
ARMS = ('engine_medium', 'engine_high', 'engine_sol_low')
FIELDS = ('answered', 'no_rejection', 'honest', 'grounded')
TOKEN_FIELDS = ('input_tokens', 'output_tokens', 'reasoning_tokens', 'total_tokens', 'cached_input_tokens')
TASKS = (
    ('private', 'timeout', '公告改寫', '四句保留提供的日期、地點'),
    ('private', 'unavailable', '三個相關優先順序問題', '逐題給可用步驟，不新增提醒'),
    ('private', 'invalid_output', '價格、重量與預算比較', '使用提供數值，保留正確算式與結論'),
    ('private', 'unavailable', '日期與預算更正後整理', '採用最新更正，捨棄舊值'),
    ('private', 'timeout', '兩個相關失敗回合', '原生合併兩個欠答承諾，只補答一次'),
    ('private', 'timeout', '夜間非緊急規劃', '原生延到隔日早晨，保留日期與補答開頭'),
    ('group', 'unavailable', '指名麻吉整理群組方案', '回覆原提問者與本群方案，不混入無關安靜留言'),
    ('group', 'invalid_output', '指名麻吉協助訂位', '誠實說明能力，給可用替代步驟，不虛構完成訂位'),
)
WITHHOLD = ('原問題經簽章收回', '原生清除個人資料', '同題稍後已獲原生有效回答',
            '另一個已知同群帳號記錄新成員加入')
LIMITS = ('獨立的八題開發題組與四項原生停止控制；不是 holdout、完整研究或模型排名。'
          '前景故障與無關設定為明示腳本，背景欠答使用原始模型、提示、解析、驗證與送出檢查。'
          '串行模擬恢復不能給正式環境可靠度、延遲或 FAST 成績。失敗、無效輸出、誠實收尾和缺失均保留在預定分母。'
          '群組整理題只挑戰本群路由與安靜成員留言的相關性，沒有跨群私人資料誘餌。'
          '評審與 Sol 候選共享供應商／模型家族；盲評不能消除偏誤，真人校準仍待完成。'
          '原六次診斷被丟棄的模型文字不可恢復；新私有診斷不會替代原資料，也不會供給回答或評分。')

COLD = r'''
import contextlib,hashlib,io,json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve();judge_root=Path(sys.argv[2]).resolve() if sys.argv[2] else None
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
def checked_json(path):
 if path.is_symlink():raise ValueError('symlink_input')
 return json.loads(path.read_text())
files=inventory(root/'source')
if digest(files)!=trusted['proof']['source_files_sha256']:raise ValueError('untrusted_source_inventory')
plan=checked_json(root/'plan.private.json')
if plan.get('source_files')!=files or plan.get('source_ref')!=trusted['source_ref'] \
 or plan.get('native_source_ref')!=trusted['native_source_ref'] \
 or plan.get('configuration_sha256')!=trusted['proof']['configuration_sha256'] \
 or plan.get('configurations')!=trusted['configurations'] or plan.get('settings')!=trusted['settings'] \
 or digest(plan.get('execution_order'))!=trusted['proof']['schedule_sha256'] \
 or sha((root/'source'/prefix/'owed_development_cases.json').read_bytes())!=trusted['proof']['corpus_sha256']:
 raise ValueError('untrusted_native_plan')
if judge_root:
 judge_files=inventory(judge_root/'source/engine')
 if judge_files!=files:raise ValueError('untrusted_judge_source_inventory')
# No frozen code is imported until the complete committed inventory is proved.
sys.path.insert(0,str(root/'source'))
from serve.line_agent_v3.evals.always_on import owed_development as dev
verified=dev.verify(root)
if verified!=plan:raise ValueError('native_plan_changed')
proof={**trusted['proof'],'plan_sha256':sha((root/'plan.private.json').read_bytes()),
       'canonical_plan_sha256':digest(plan)}
result={'proof':proof,'complete':False,'native':None,'quality':None}
if judge_root:
 from serve.line_agent_v3.evals.always_on import owed_development_judge as judging,variant_config
 retained=checked_json(judge_root/'quality.private.json');captured=[]
 def retain(path,value,**kwargs):
  if Path(path).resolve()!=judge_root/'quality.private.json':raise ValueError('unexpected_export_write')
  captured.append(value)
 dev.original.write=retain
 with contextlib.redirect_stdout(io.StringIO()):actual=judging.summary(judge_root)
 if captured!=[retained] or actual!=retained:raise ValueError('retained_quality_changed')
 binding,_packets,_controls,_mapping,judge_plan=judging.verify(judge_root)
 if judge_plan!=plan:raise ValueError('foreign_judge_plan')
 native=[];attempts={arm:[] for arm in dev.ARMS}
 for item in plan['execution_order']:
  row=dev.load_receipt(root,plan,item)
  copied=dev.load_receipt(judge_root/'inputs',plan,item)
  if row!=copied:raise ValueError('foreign_native_receipt')
  case=next(case for case in plan['corpus']['cases'] if case['id']==item['episode_id'])
  assessed=dev.assess(row,case,plan['configurations'][item['arm']],item['account'])
  native.append({'arm':item['arm'],'kind':item['kind'],'assessment':assessed})
  attempts[item['arm']].extend(attempt for attempt in row['background_parameters']['attempts'] if attempt['lane']=='owed')
 proof.update(binding_sha256=digest(binding),native_receipts_sha256=digest(inventory(judge_root/'inputs/receipts')),
  judge_attempts_sha256=digest({name:value for name,value in inventory(judge_root/'judge/foreground').items()
                              if name.startswith(('controls/','results/'))}),
  retained_quality_sha256=sha((judge_root/'quality.private.json').read_bytes()),
  packets_sha256=binding['packets_sha256'],controls_sha256=binding['controls_sha256'],
  mapping_sha256=binding['mapping_sha256'])
 result.update(complete=True,native=native,quality=retained,
  native_usage={arm:variant_config.usage_summary(rows,capture_complete=True) for arm,rows in attempts.items()})
print(json.dumps(result,ensure_ascii=False,allow_nan=False))
'''


def count(value, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('invalid_development_count')
    return value


def hexproof(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('invalid_development_proof')
    return value


def usage(value, ceiling):
    """Keep native provider component meanings and explicit unknown denominators."""
    attempts=count(value['attempts'],ceiling)
    tokens={}
    for field in TOKEN_FIELDS:
        row=value['token_usage'][field]
        known=count(row['known_attempts'],attempts);unknown=count(row['unknown_attempts'],attempts)
        if known+unknown!=attempts:raise ValueError('invalid_development_usage_denominator')
        total=row['known_tokens']
        if total is not None:count(total,10**12)
        if total is None and known or total is not None and not known and attempts:
            raise ValueError('invalid_development_usage_total')
        tokens[field]={'known_tokens':total,'known_attempts':known,'unknown_attempts':unknown}
    return {'attempts':attempts,'request_sent_attempts':count(value['request_sent_attempts'],attempts),
            'failed_attempts':count(value['failed_attempts'],attempts),
            'invalid_output_attempts':count(value['invalid_output_attempts'],attempts),
            'token_usage':tokens,'usage_complete':all(row['unknown_attempts']==0 for row in tokens.values())}


def project(snapshot):
    proof=snapshot['proof']
    if any(proof.get(key)!=value for key,value in TRUST['proof'].items()):
        raise ValueError('development_trusted_proof_mismatch')
    extra={'plan_sha256','canonical_plan_sha256'}
    if snapshot.get('complete') is True:
        extra|={'binding_sha256','native_receipts_sha256','judge_attempts_sha256','retained_quality_sha256',
                'packets_sha256','controls_sha256','mapping_sha256'}
    if set(proof)!=set(TRUST['proof'])|extra:raise ValueError('development_proof_inventory')
    for value in proof.values():hexproof(value)
    value={'schema_version':1,'kind':'native_owed_development','source_ref':TRUST['source_ref'],
        'native_source_ref':TRUST['native_source_ref'],'plan_verified':True,
        'full_study_result':False,'publication_ready':False,'held_out':False,
        'status':'pending','native_capture_complete':False,'quality_complete':False,
        'planned_cells':72,'positive_tasks':8,'positive_denominator':48,'withholding_controls':4,
        'withholding_denominator':24,'max_native_calls':48,'max_calls_per_cell':1,'max_judge_calls':130,
        'configurations':TRUST['configurations'],
        'schedule':{'candidate_permutations':6,'secondary_order_offset':3,'adjacent_account_blocks':True,
                    'alternating_first_account':True,'per_account_cycles':2,
                    'positive_candidate_position_counts':[6,5,5]},
        'judge':{'model':'gpt-6-sol','reasoning':'medium','passes':2,'primary_pass':1,
                 'max_output_tokens':4000,'timeout_s':120,'store':False,'controls':17,'control_judgments':34},
        'tasks':[{'scope':scope,'foreground_failure':failure,'summary':summary,'expected':expected}
                 for scope,failure,summary,expected in TASKS],
        'withholding':list(WITHHOLD),'proof':dict(proof),'results':None,'limits':LIMITS}
    if snapshot.get('complete') is not True:return value
    quality=snapshot['quality'];native=snapshot['native']
    if any(quality.get(key) is not True for key in ('judging_complete','controls_passed','quality_ready')) \
            or any(quality.get(key) is not False for key in ('publication_ready','held_out')) \
            or any(quality.get(key)!=n for key,n in (('positive_denominator',48),('withholding_denominator',24),
                ('planned_judgments',130),('retained_attempts',130),('missing_judgments',0),('primary_pass',1))) \
            or len(quality.get('controls',[]))!=34 or any(row.get('as_expected') is not True for row in quality['controls']):
        raise ValueError('incomplete_development_quality')
    if len(native)!=72 or len(quality.get('rows',[]))!=48 or len(quality.get('withholding',[]))!=24:
        raise ValueError('incomplete_development_denominator')
    arms={}
    for arm in ARMS:
        cells=[row for row in native if row['arm']==arm]
        positive=[row['assessment'] for row in cells if row['kind']=='positive']
        withheld=[row['assessment'] for row in cells if row['kind']=='withhold']
        rows=[row for row in quality['rows'] if row['arm']==arm]
        if (len(cells),len(positive),len(withheld),len(rows))!=(24,16,8,16) \
                or any(row['setup_and_capture_ready'] is not True for row in positive+withheld) \
                or any(row['withholding_passed'] is not True or row['request_uploaded']!=0 for row in withheld):
            raise ValueError('unqualified_development_native_capture')
        judgments={field:0 for field in FIELDS};agreement={field:0 for field in FIELDS};codes={};diagnostics={}
        for row in rows:
            if set(row['judgments'])!={'1','2'}:raise ValueError('missing_development_judgment')
            for field in FIELDS:
                if any(type(row['judgments'][index].get(field)) is not bool for index in ('1','2')):
                    raise ValueError('invalid_development_judgment')
                judgments[field]+=row['judgments']['1'][field]
                agreement[field]+=row['judgments']['1'][field] is row['judgments']['2'][field]
        for row in positive:
            for outcome in row['native_outcomes']:
                code=outcome['native_code'] or outcome['outcome']
                if type(code) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,79}',code):
                    raise ValueError('unsafe_development_native_code')
                codes[code]=codes.get(code,0)+1
            for diagnostic in row['diagnostics']['rows']:
                reason='available' if diagnostic['available'] is True else diagnostic['unavailable_reason']
                if type(reason) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,79}',reason):
                    raise ValueError('unsafe_development_diagnostic_reason')
                diagnostics[reason]=diagnostics.get(reason,0)+1
        if snapshot['native_usage'][arm]['attempts']!=16:raise ValueError('missing_development_native_attempt')
        arms[arm]={'positive_denominator':16,'withholding_denominator':8,
            'late_answer_delivered':count(sum(row['late_answer_delivered'] is True for row in positive),16),
            'closures':count(sum(row['closures'] for row in positive),16),'withholding_passed':8,
            'judgments':judgments,'pass_agreement':agreement,'native_codes':codes,
            'diagnostic_availability':diagnostics,'native_usage':usage(snapshot['native_usage'][arm],16)}
    if quality['judge_usage']['attempts']!=130:raise ValueError('missing_development_judge_attempt')
    value.update(status='complete',native_capture_complete=True,quality_complete=True,
        results={'arms':arms,'judgments':130,'controls_passed':34,
                 'judge_usage':usage(quality['judge_usage'],130)})
    return value


def verified_projection(study, judging=None):
    result=subprocess.run([sys.executable,'-I','-B','-c',COLD,str(Path(study).resolve()),
                           str(Path(judging).resolve()) if judging else '',json.dumps(TRUST)],
                          env={},capture_output=True,text=True,timeout=180)
    if result.returncode:raise ValueError('owed_development_not_verified')
    return project(json.loads(result.stdout))


def validate_public(value):
    # The safe view is deterministic, with exact fixed scope and no arbitrary prose.
    expected_proofs=set(TRUST['proof'])|{'plan_sha256','canonical_plan_sha256'}
    if value.get('status')=='complete':
        expected_proofs|={'binding_sha256','native_receipts_sha256','judge_attempts_sha256',
                         'retained_quality_sha256','packets_sha256','controls_sha256','mapping_sha256'}
    if set(value.get('proof',{}))!=expected_proofs:raise ValueError('invalid_public_development_proofs')
    for proof in value['proof'].values():hexproof(proof)
    base=project({'proof':{key:val for key,val in value.get('proof',{}).items()
                         if key in TRUST['proof'] or key in ('plan_sha256','canonical_plan_sha256')},'complete':False})
    for key in ('status','native_capture_complete','quality_complete','results','proof'):
        base[key]=value.get(key)
    if base!=value or value['status'] not in ('pending','complete') \
            or value['quality_complete'] is not (value['status']=='complete') \
            or value['native_capture_complete'] is not (value['status']=='complete') \
            or (value['results'] is None)!=(value['status']=='pending'):
        raise ValueError('invalid_public_owed_development')
    # Completed data can only be created by project; retained public re-rendering
    # still validates the fixed denominators and the strict aggregate-only schema.
    if value['status']=='complete':
        if set(value['results'])!={'arms','judgments','controls_passed','judge_usage'} \
                or value['results']['judgments']!=130 or value['results']['controls_passed']!=34 \
                or set(value['results']['arms'])!=set(ARMS):
            raise ValueError('invalid_public_development_results')
        for arm,row in value['results']['arms'].items():
            if set(row)!={'positive_denominator','withholding_denominator','late_answer_delivered','closures',
                          'withholding_passed','judgments','pass_agreement','native_codes',
                          'diagnostic_availability','native_usage'} \
                    or (row['positive_denominator'],row['withholding_denominator'],row['withholding_passed'])!=(16,8,8):
                raise ValueError('invalid_public_development_results')
            for key in ('late_answer_delivered','closures'):count(row[key],16)
            for key in ('judgments','pass_agreement'):
                if set(row[key])!=set(FIELDS):raise ValueError('invalid_public_development_components')
                for n in row[key].values():count(n,16)
            for key in ('native_codes','diagnostic_availability'):
                for name,n in row[key].items():
                    if not re.fullmatch('[a-z][a-z0-9_]{0,79}',name):raise ValueError('unsafe_public_development_code')
                    count(n,16)
            if usage(row['native_usage'],16)!=row['native_usage']:raise ValueError('unsafe_public_development_usage')
        if usage(value['results']['judge_usage'],130)!=value['results']['judge_usage']:
            raise ValueError('unsafe_public_development_usage')
    return value
