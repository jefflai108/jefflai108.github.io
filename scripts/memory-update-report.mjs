import crypto from 'node:crypto';

const canonical=v=>Array.isArray(v)?'['+v.map(canonical).join(',')+']':v&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}':JSON.stringify(v);
const sha=v=>crypto.createHash('sha256').update(v).digest('hex');
const same=(a,b)=>canonical(a)===canonical(b);
const fail=s=>{throw new Error(s)};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(v,n=1)=>Number(v).toFixed(n);
export const updateStudy=data=>['memory-models-quality-v5-mem0','memory-models-quality-v6-mem0'].includes(data.version);
export function httpRetryCount(r){
  const stages=new Map();
  for(const a of r.attempts)stages.set(a.stage||'single',(stages.get(a.stage||'single')||0)+1);
  return [...stages.values()].reduce((n,count)=>n+Math.max(0,count-1),0);
}
export function recordCost(r,prices){
  const [input,cached,output]=prices[r.config.model];
  const stages=r.extractionReceipt?[r.extractionReceipt,...(r.reconciliation?.usage?[r.reconciliation]:[])]:[r];
  return stages.reduce((n,s)=>{
    const usage=s.usage,c=usage.prompt_tokens_details?.cached_tokens||0,w=usage.prompt_tokens_details?.cache_write_tokens||0;
    return n+(Math.max(0,(usage.prompt_tokens||0)-c-w)*input+c*cached+w*input*1.25+(usage.completion_tokens||0)*output)/1e6;
  },0);
}

function checkStage(s,r){
  if(!same(s.config,r.config)||s.maxCompletionTokens!==16384||!Number.isFinite(s.latencySeconds)||s.latencySeconds<=0||!Array.isArray(s.attempts)||!s.attempts.length)fail('Memory stage receipt missing');
  if(s.apiOk){
    if(s.modelReturned!==r.config.model)fail('Memory stage model changed');
    for(const key of ['prompt_tokens','completion_tokens','total_tokens'])if(!Number.isInteger(s.usage[key])||s.usage[key]<0)fail('Memory stage usage missing');
    if(s.usage.completion_tokens>16384||s.usage.total_tokens!==s.usage.prompt_tokens+s.usage.completion_tokens||(s.usage.completion_tokens_details?.reasoning_tokens||0)>s.usage.completion_tokens)fail('Memory stage token ceiling changed');
  }
}

function checkActions(u,fresh,c){
  const old=new Map(u.candidateProjection.map(v=>[v.id,v])),usedOld=new Set(),usedNew=new Set();
  for(const a of u.actions){
    let keys;
    if(a.event==='ADD')keys=['event','fact'];
    else if(a.event==='UPDATE')keys=['event','id','old_memory','fact','evidence_seq','evidence'];
    else if(a.event==='DELETE')keys=['event','id','old_memory','evidence_seq','evidence'];
    else if(a.event==='NONE')keys=['event','id',...('fact' in a?['fact']:[])];
    else fail('Unknown memory action');
    if(!same(Object.keys(a).sort(),keys.sort()))fail('Memory action grammar changed');
    if('id' in a){if(!old.has(a.id)||usedOld.has(a.id))fail('Memory target binding changed');usedOld.add(a.id);}
    if('fact' in a){if(!Number.isInteger(a.fact)||a.fact<1||a.fact>fresh.length||usedNew.has(a.fact))fail('Memory fresh fact binding changed');usedNew.add(a.fact);}
    if(['UPDATE','DELETE'].includes(a.event)){
      const source=c.turns.find(t=>t.seq===a.evidence_seq);
      if(a.old_memory!==old.get(a.id).text||!source||typeof a.evidence!=='string'||a.evidence.length<2||!source.text.includes(a.evidence))fail('Memory transition original source changed');
      if(a.event==='UPDATE'){
        const f=fresh[a.fact-1];
        if(f.key!==old.get(a.id).key||f.turn_seq!==a.evidence_seq||!a.evidence.includes(f.value))fail('Memory replacement source changed');
      }
    }
    if(a.event==='NONE'&&'fact' in a&&fresh[a.fact-1].key!==old.get(a.id).key)fail('Memory no-op category changed');
  }
  if(usedNew.size!==fresh.length)fail('Unassigned new memory fact');
}

export function checkUpdatePipeline(data){
  const m=data.memoryUpdate,cases=new Map(data.cases.map(c=>[c.id,c]));
  if(!m||m.maxCandidates!==32||m.upstreamCommit!=='d26ba5e4518cef7fff3c66d4f715b21adf9feabe'||!same(data.manifest.memoryUpdate.promptTemplateHash,m.promptTemplateHash)||sha(m.promptTemplate)!==m.promptTemplateHash||sha(canonical(m.responseFormat))!==m.schemaHash)fail('Memory update protocol missing');
  const counts={updateCalls:0,skipped:0,extractionCalls:0,summaryCalls:0,invalidUpdates:0};
  for(const r of data.records){
    if(r.task!=='facts'){counts.summaryCalls++;if(r.extractionReceipt||r.reconciliation)fail('Summary pipeline changed');continue;}
    counts.extractionCalls++;
    const first=r.extractionReceipt,u=r.reconciliation,c=cases.get(r.caseId);
    if(!first||first.raw!==r.raw||first.promptHash!==r.promptHash)fail('Extraction receipt binding changed');
    checkStage(first,r);
    if(!u){
      if(r.formatOk||r.latencySeconds!==first.latencySeconds||!same(r.usage,first.usage))fail('Missing planner stage');
      continue;
    }
    const fresh=r.accepted.facts.map(f=>({key:f.key,value:f.value,turn_seq:f.evidence_seq}));
    if(sha(canonical(fresh))!==u.freshFactsHash||u.schemaHash!==m.schemaHash||!same(u.config,r.config)||u.maxCompletionTokens!==16384||!Array.isArray(u.candidateProjection)||u.candidateProjection.length>32)fail('Memory planner inputs changed');
    for(const [i,v] of u.candidateProjection.entries())if(!same(Object.keys(v).sort(),['id','key','text'])||v.id!==String(i+1)||!c.priorFacts.some(f=>f.key===v.key&&f.value===v.text))fail('Memory candidate privacy projection changed');
    // Every source in this fixed 100-case corpus is short enough for the exact
    // source view. Larger future corpora need their own bounded-view verifier.
    const required=[...new Set(fresh.map(f=>f.turn_seq))].sort((a,b)=>a-b);
    const order=[...required,...c.turns.map(t=>t.seq).filter(seq=>!required.includes(seq))];
    if(c.turns.length>32||c.turns.some(t=>t.text.length>5000))fail('Update corpus exceeds exact view verifier');
    const input={recorded_date:c.date,existing_memory:u.candidateProjection,
      new_facts:fresh.map((f,i)=>({fact:i+1,key:f.key,text:f.value,evidence_seq:f.turn_seq})),
      current_user_turns:order.map(seq=>({seq,text:c.turns.find(t=>t.seq===seq).text,text_complete:true}))};
    if(u.promptHash!==sha(canonical(m.promptTemplate+'\nDATA JSON:\n'+canonical(input))))fail('Exact memory update prompt changed');
    if(u.skipped){
      counts.skipped++;
      if(u.skipped!=='no_related_memory'||u.candidateProjection.length||u.raw||u.usage||r.latencySeconds!==first.latencySeconds||!same(r.usage,first.usage))fail('Unmeasured skipped planner');
    }else{
      counts.updateCalls++;checkStage(u,r);
      if(r.apiOk!==(first.apiOk&&u.apiOk)||Math.abs(r.latencySeconds-first.latencySeconds-u.latencySeconds)>.00011)fail('Combined stage latency changed');
      for(const key of ['prompt_tokens','completion_tokens','total_tokens'])if(r.usage[key]!==((first.usage[key]||0)+(u.usage[key]||0)))fail('Combined stage tokens changed');
      for(const [detail,key] of [['prompt_tokens_details','cached_tokens'],['completion_tokens_details','reasoning_tokens']])if(r.usage[detail][key]!==((first.usage[detail]?.[key]||0)+(u.usage[detail]?.[key]||0)))fail('Combined detailed tokens changed');
      const attempts=[...first.attempts.map(a=>({...a,stage:'extract'})),...u.attempts.map(a=>({...a,stage:'update'}))];
      if(!same(attempts,r.attempts))fail('Transport stages changed');
    }
    if(r.formatOk){
      if(!u.applied||u.queueWouldRemainPending||!Array.isArray(u.actions))fail('Applied memory plan missing');
      checkActions(u,fresh,c);
    }else{
      counts.invalidUpdates++;
      if(!u.queueWouldRemainPending||r.profileConstruction.addedFacts.length||r.profileConstruction.removedFacts.length)fail('Rejected planner changed memory');
    }
  }
  for(const [key,value] of Object.entries(counts))if(m[key]!==value)fail('Memory stage denominator changed');
  for(const a of data.aggregates){
    const rows=data.records.filter(r=>r.armId===a.armId&&r.task===a.task&&(a.difficulty==='all'||r.difficulty===a.difficulty));
    if(a.retryOutputs!==rows.filter(r=>httpRetryCount(r)>0).length)fail('Required second call counted as a retry');
  }
}

export function updateStageMarkup(r){
  if(!r.extractionReceipt)return '';
  const u=r.reconciliation,rows=[['抽取',r.extractionReceipt],...(u&&!u.skipped?[['操作管理',u]]:[])];
  return `<details class="memory-stages"><summary>兩階段呼叫、候選與實際操作</summary><div class="scroll"><table><thead><tr><th>階段</th><th>completion上限</th><th>實用completion</th><th>次要延遲</th><th>HTTP重試</th></tr></thead><tbody>${rows.map(([label,s])=>`<tr><th>${label}</th><td>${s.maxCompletionTokens.toLocaleString('en-US')}</td><td>${s.usage?.completion_tokens??'未回報'}</td><td>${fmt(s.latencySeconds)}s</td><td>${Math.max(0,s.attempts.length-1)}</td></tr>`).join('')}</tbody></table></div>${u?.skipped?'<p>沒有相關舊事實：未呼叫操作管理模型，直接處理有原文的新事實。</p>':''}${u?`<h5>本次操作模型實際可見的舊事實</h5><pre>${esc(JSON.stringify(u.candidateProjection,null,2))}</pre><h5>接受的操作與儲存結果</h5><pre>${esc(JSON.stringify({actions:u.actions||[],stats:r.profileConstruction.actionStats,pending:Boolean(u.queueWouldRemainPending),parseError:u.parseError||u.applyError||null},null,2))}</pre>${u.raw?`<h5>操作模型完整原始輸出</h5><pre>${esc(u.raw)}</pre>`:''}`:''}<p class="small">每個API階段上限16,384；兩階段最多32,768。上限與實用token分別列出，延遲合計兩個API階段。必要的第二階段不算重試。</p></details>`;
}

export function updateProtocolMarkup(data){
  if(!updateStudy(data))return '';
  const m=data.memoryUpdate,calls=m.extractionCalls+m.summaryCalls+m.updateCalls;
  return `<section class="panel"><h2>Mem0 操作管理：原文抽取 → 比較 → 中央更新</h2><p>這次100題重新生成800份任務輸出，實際API階段${calls}次：抽取${m.extractionCalls}、操作管理${m.updateCalls}、一般摘要${m.summaryCalls}；另${m.skipped}份沒有相關舊事實而跳過操作呼叫。${m.invalidUpdates}份操作提案未通過，仍列入分母。</p><p>ADD／UPDATE／DELETE／NONE 改寫自固定版本的 Mem0 prompt。抽取只讀本次本人原話；操作模型只讀相關的未編輯舊事實與有原文的新事實。保存前仍由 Machi 在同一 SQLite 交易重查來源、人物、時間、狀態與權限。JSON可解析而不符證據或分類契約的提案，也算管線失敗。</p><p class="notice">四配置共用 prompt template；第二階段的完整輸入會隨各模型新抽取的事實而不同。每個API階段16,384，耐久檔案最多兩次、合計32,768；與前次單次抽取的運算量不同。</p><p>沿用作者已檢視的100題與原70／30標籤，並非未看過的holdout或真實使用者研究。${data.version==='memory-models-quality-v6-mem0'?'v6依v5觀察澄清跨分類操作與現在的撤回證據；':''}所有失敗保留。</p><details><summary>完整操作管理 prompt</summary><pre>${esc(m.promptTemplate)}</pre></details><p><a href="memory-models-v4.html">v4：前次完整比較與 Luna high 三版 prompt</a> · <a href="memory-models-v5.html">v5：第一版 Mem0 操作管理完整結果</a> · <a href="https://github.com/mem0ai/mem0/blob/${m.upstreamCommit}/mem0/configs/prompts.py">Mem0 原始 prompt（固定版本）</a></p></section>`;
}
