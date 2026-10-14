import fs from 'node:fs';
import crypto from 'node:crypto';
import {errorOrigin} from '../public/line-v3/memory-quality-origin.js';
import {checkUpdatePipeline,updateStudy,updateStageMarkup,updateProtocolMarkup,httpRetryCount,recordCost} from './memory-update-report.mjs';

const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])).replace(/[ \t]+(?=\r?\n)/g,s=>[...s].map(c=>c==='\t'?'&#9;':'&#32;').join(''));
const fmt=(v,n=1)=>Number(v).toFixed(n);
const canonical=v=>Array.isArray(v)?'['+v.map(canonical).join(',')+']':v&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}':JSON.stringify(v);
const sha=v=>crypto.createHash('sha256').update(v).digest('hex');
const same=(a,b)=>canonical(a)===canonical(b);
const fail=s=>{throw new Error(s)};
const tasks={facts:'耐久個人檔案',summary:'一般摘要＋累積印象'};
const errors={past_as_current:'過去當現在',wrong_person:'人物／關係錯置',negation:'否定反轉',unsupported:'無來源的新增事實',source_instruction:'遵循資料偽指令',correction:'錯誤更正',uncertainty:'未知變成確定'};
const quantile=(values,p)=>{const a=[...values].sort((x,y)=>x-y),i=(a.length-1)*p;return a[Math.floor(i)]+(a[Math.ceil(i)]-a[Math.floor(i)])*(i-Math.floor(i));};

function checkProfile(r,c){
  if(r.task!=='facts')return;
  const state=r.profileConstruction;
  if(!state||state.profileGroups.length!==6||state.profileGroups.some(g=>g.facts.length>8))fail('Actual constructed profile missing');
  for(const f of state.storedFacts){
    const source=(f.sourceStage==='prior'?c.priorTurns:c.turns).find(t=>t.seq===f.evidence_seq);
    if(!source||!source.text.includes(f.value))fail('Profile original source missing');
  }
  if(state.profileGroups.flatMap(g=>g.facts).some(f=>!state.storedFacts.some(v=>same(v,f))))fail('Profile projection changed');
  if(!same(state.updateChecks.map(({passed,...u})=>u),c.expectedUpdates))fail('Update expectations changed');
  for(const u of state.updateChecks){
    const active=state.storedFacts.some(f=>f.key===u.key&&f.value===u.value);
    if(u.passed!==(active===(u.action==='keep')))fail('Profile update result changed');
  }
  const old=c.priorFacts.map(f=>[f.key,f.value]);
  const added=state.storedFacts.filter(f=>!old.some(([k,v])=>k===f.key&&v===f.value));
  const removed=c.priorFacts.filter(f=>!state.storedFacts.some(v=>v.key===f.key&&v.value===f.value));
  if(!same(added,state.addedFacts)||!same(removed,state.removedFacts))fail('Profile diff changed');
}

function checkQuotes(e,r,c){
  const targets=c.gold[r.task==='facts'?'factTargets':'summaryTargets'];
  if(!same(e.coverage.map(v=>v.targetId).sort(),targets.map(t=>t.id).sort()))fail('Coverage targets mismatch');
  for(const v of e.coverage)if(typeof v.covered!=='boolean'||v.covered&&(!v.outputQuote||!r.judgedOutput.includes(v.outputQuote))||!v.covered&&v.outputQuote)fail('Coverage quote mismatch');
  for(const error of e.errors){
    const source=[...c.priorTurns,...c.turns].find(t=>t.seq===error.sourceSeq);
    if(!Object.hasOwn(errors,error.type)||!error.outputQuote||!r.judgedOutput.includes(error.outputQuote)||!source||!error.sourceQuote||!source.text.includes(error.sourceQuote))fail('Judge evidence mismatch');
  }
}

function checkQuality(e,r,c){
  checkQuotes(e,r,c);
  const coverage=e.coverage.filter(v=>v.covered).length/e.coverage.length;
  const current=r.task==='facts'?new Set(c.gold.factTargets.filter(t=>t.kind==='current').map(t=>t.id)):new Set(e.coverage.map(v=>v.targetId));
  const checks=e.coverage.filter(v=>current.has(v.targetId));
  const newCoverage=checks.filter(v=>v.covered).length/checks.length;
  const updates=r.profileConstruction?.updateChecks||[],updatePass=updates.every(u=>u.passed);
  const passed=Boolean(r.formatOk&&!e.errors.length&&coverage>=.8&&newCoverage>=.8&&updatePass);
  const score=r.formatOk?(e.errors.length?0:60)+40*coverage:0;
  if(r.quality.pass!==passed||r.quality.errorCount!==e.errors.length||Math.abs(r.quality.score-score)>.0011||r.quality.coverage!==coverage||r.quality.newCoverage!==newCoverage||r.quality.updatePass!==updatePass||r.quality.updateFailures!==updates.filter(u=>!u.passed).length||!same(r.quality.errors,e.errors)||!same(r.quality.coverageChecks,e.coverage))fail('Quality changed after judgment');
}

function checkPackets(data,packets,records,labels,stage,attachQuality=true){
  const map=new Map(records.map(r=>[r.id,r])),cases=new Map(data.cases.map(c=>[c.id,c])),judged=new Set();
  for(const j of packets){
    if(j.evaluations.length!==labels||new Set(j.evaluations.map(e=>e.label)).size!==labels||Object.keys(j.mapping).length!==labels)fail('Judge label binding mismatch');
    const first=map.get(Object.values(j.mapping)[0]),c=cases.get(first?.caseId);
    if(!first||!c||j.id!==`${first.caseId}:${first.task}:${stage==='main'?'r1':stage}`)fail('Judge packet identity mismatch');
    for(const e of j.evaluations){
      const r=map.get(j.mapping[e.label]);
      if(!r||r.caseId!==c.id||r.task!==first.task||judged.has(r.id))fail('Judge candidate binding mismatch');
      judged.add(r.id);
      if(attachQuality){if(r.quality.judgePacketId!==j.id)fail('Judge quality binding mismatch');checkQuality(e,r,c);}
      else checkQuotes(e,r,c);
    }
    const packet={task:first.task,source:[...c.priorTurns,...c.turns].map(t=>({seq:t.seq,text:t.text})),priorSourceSeqs:c.priorTurns.map(t=>t.seq),
      correctionCandidates:c.correctionCandidates,targets:c.gold[first.task==='facts'?'factTargets':'summaryTargets'],mustNotAssert:c.gold.mustNotAssert,scope:c.gold.scope,
      candidates:Object.entries(j.mapping).map(([label,id])=>({label,output:map.get(id).judgedOutput})),
      inputProfile:first.task==='summary'?c.profile:'',inputRecent:first.task==='summary'?c.recent:[]};
    if(j.packetHash!==sha(canonical(packet))||j.promptHash!==sha(canonical(data.judge.rubric+'\nDATA JSON:\n'+canonical(packet))))fail('Judge input or protocol changed');
  }
  if(attachQuality&&judged.size!==records.length)fail('Unjudged outputs');
}

function checkAggregates(rows,aggregates){
  for(const a of aggregates){
    const selected=rows.filter(r=>r.task===a.task&&r.armId===a.armId&&(a.difficulty==='all'||r.difficulty===a.difficulty));
    if(a.n!==selected.length||a.passes!==selected.filter(r=>r.quality.pass).length||a.unsafeOutputs!==selected.filter(r=>r.quality.errorCount>0).length||a.apiFailures!==selected.filter(r=>!r.apiOk).length||a.formatFailures!==selected.filter(r=>r.apiOk&&!r.formatOk).length)fail('Aggregate changed after measurement');
    const errorTypes={};for(const r of selected)for(const e of r.quality.errors)errorTypes[e.type]=(errorTypes[e.type]||0)+1;
    if(a.materialErrors!==selected.reduce((n,r)=>n+r.quality.errors.length,0)||!same(a.errorTypes,errorTypes)||a.retryOutputs!==selected.filter(r=>httpRetryCount(r)>0).length||Math.abs(a.costUsd-selected.reduce((n,r)=>n+r.costUsd,0))>.00000051)fail('Error/cost aggregate changed after measurement');
    for(const [key,p] of [['latencyP50',.5],['latencyP95',.95]])if(Math.abs(a[key]-quantile(selected.map(r=>r.latencySeconds),p))>.00051)fail('Latency changed after measurement');
    for(const [key,get] of [['newCoveragePercent',r=>r.quality.newCoverage],['coveragePercent',r=>r.quality.coverage],['updatePassPercent',r=>r.quality.updatePass]])if(Math.abs(a[key]-100*selected.reduce((s,r)=>s+Number(get(r)),0)/selected.length)>.0051)fail('Quality aggregate changed');
  }
}

export function validateQuality(data,receiptHash){
  if(/(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9_.-]{16,}|\/Users\/|\/srv\/heymachi\/|OPENAI_API_KEY)/.test(JSON.stringify(data)))fail('Private material in public artifact');
  if(data.cases.length!==100||data.records.length!==800||data.manifest.repeats!==1||data.manifest.maxCompletionTokens!==16384||data.manifest.productionDefaultCap!==8192||data.manifest.productionHighDefaultCap!==16384||sha(canonical(data.cases))!==data.manifest.casesHash)fail('Incomplete 100-case extended-budget study');
  if(['hard','simple'].some(d=>data.cases.filter(c=>c.difficulty===d).length!==50)||data.cases.filter(c=>c.split==='holdout').length!==30)fail('Paired corpus or holdout missing');
  const expected=[['baseline','gpt-5.6-luna',null,'gpt-5.6-terra',null],['luna-medium','gpt-6-luna','medium','gpt-6-luna','medium'],['luna-high','gpt-6-luna','high','gpt-6-luna','high'],['luna-sol','gpt-6-luna','medium','gpt-6.1-sol','low']];
  if(data.manifest.arms.length!==4||data.manifest.arms.some((a,i)=>!same([a.id,a.summary.model,a.summary.effort,a.facts.model,a.facts.effort],expected[i])||data.manifest.armCompletionCaps[a.id]!==16384))fail('Requested model configuration changed');
  const cases=new Map(data.cases.map(c=>[c.id,c])),records=new Map(data.records.map(r=>[r.id,r]));
  if(cases.size!==100||records.size!==800)fail('Duplicate receipt/case');
  const checkRecord=r=>{
    const c=cases.get(r.caseId);
    if(!c||r.receiptHash!==receiptHash(r)||r.maxCompletionTokens!==16384||r.difficulty!==c.difficulty||r.split!==c.split||r.apiOk&&r.modelReturned!==r.config.model||!Number.isFinite(r.latencySeconds)||r.latencySeconds<=0)fail('Generation receipt changed after measurement');
    if(Math.abs(r.costUsd-recordCost(r,data.method.pricesPerMillion))>1e-9)fail('Generation cost changed after measurement');
    checkProfile(r,c);
  };
  for(const c of data.cases)for(const task of ['facts','summary'])for(const arm of data.manifest.arms){
    const r=records.get(`${c.id}:${task}:${arm.id}:r1`);
    if(!r||r.repeat!==1||r.task!==task||r.armId!==arm.id||!same(r.config,arm[task])||r.promptHash!==data.manifest.prompts[`${c.id}:${task}`])fail('Generation binding mismatch');checkRecord(r);
  }
  if(data.judge.primaryEvaluations.length!==200||data.judge.mirrorRecords.length!==48||data.judge.config.model!=='gpt-6-astra'||data.judge.config.effort!=='medium')fail('Judge denominator/configuration mismatch');
  checkPackets(data,data.judge.primaryEvaluations,data.records,4,'main');
  if(data.aggregates.length!==24)fail('Aggregate denominator missing');checkAggregates(data.records,data.aggregates);
  for(const split of ['development','holdout']){
    if(data.splitAggregates[split]?.length!==24)fail('Split aggregate denominator missing');
    checkAggregates(data.records.filter(r=>r.split===split),data.splitAggregates[split]);
  }
  if(data.judge.calibration.length!==4||data.judge.calibration.some(c=>{const e=Object.fromEntries(c.evaluations.map(v=>[v.label,v]));return !e.A||e.A.errors.length||e.A.coverage.some(v=>!v.covered)||!e.B.errors.length||!e.C.errors.length||e.D.errors.length||e.D.coverage.some(v=>v.covered)}))fail('Judge calibration failed');
  if(data.judge.mirrorRecords.filter(m=>m.originalPass===m.reversedPass).length/48!==data.judge.passAgreement)fail('Judge agreement changed');
  if(updateStudy(data)){
    checkUpdatePipeline(data);
    return data;
  }
  const tuning=data.promptIterations;
  if(!tuning||tuning.records.length!==600||tuning.primaryEvaluations.length!==200||tuning.developmentEvaluations.length!==140||tuning.mirrorRecords.length!==36||tuning.plans.length!==3||tuning.holdoutCases!==30||tuning.developmentCases!==70)fail('Three complete prompt iterations required');
  const ids=new Set();
  for(const r of tuning.records){
    if(ids.has(r.id)||r.id!==`${r.caseId}:${r.task}:luna-high:p${r.promptRound}`||![1,2,3].includes(r.promptRound)||!same(r.config,data.manifest.arms[2][r.task]))fail('Prompt iteration binding mismatch');ids.add(r.id);checkRecord(r);
    if(r.promptRound===1){const original=records.get(r.parentGenerationId);if(!original||r.raw!==original.raw||r.promptHash!==original.promptHash||r.latencySeconds!==original.latencySeconds||!same(r.profileConstruction,original.profileConstruction))fail('Round one is not its original measured output');}
  }
  checkPackets(data,tuning.primaryEvaluations,tuning.records,3,'final');
  const dev=tuning.records.filter(r=>r.split==='development'&&r.promptRound!==3);
  checkPackets(data,tuning.developmentEvaluations,dev,2,'development-2',false);
  for(const p of tuning.plans)if(p.maxCompletionTokens!==16384||p.round!==1&&(!p.reviewedDevelopmentEvidenceHash||Object.values(p.revisionTexts).some(v=>!v.trim())))fail('Prompt plan incomplete');
  if(tuning.aggregates.length!==54)fail('Iteration aggregate denominator missing');
  for(const number of [1,2,3])for(const split of ['all','development','holdout'])checkAggregates(tuning.records.filter(r=>r.promptRound===number&&(split==='all'||r.split===split)),tuning.aggregates.filter(a=>a.promptRound===number&&a.split===split));
  if(tuning.mirrorRecords.filter(m=>m.originalPass===m.reversedPass).length/36!==tuning.passAgreement)fail('Iteration judge agreement changed');
  return data;
}

function sourceFor(c,f){return [...c.priorTurns,...c.turns].find(t=>t.seq===f.evidence_seq);}
function groups(groups,c){
  return `<div class="profile-grid">${groups.map(g=>`<section class="profile-group"><h5>${esc(g.category)} <small>${g.facts.length}/8</small></h5>${g.facts.length?`<ul>${g.facts.map(f=>`<li>${esc(f.value)}<details><summary>來源 [${f.evidence_seq}] · ${f.sourceStage==='prior'?'既有':'本次'}</summary><blockquote>${esc(sourceFor(c,f)?.text)}</blockquote><small>保存範圍 ${esc(f.temporal_scope)}；記錄日期不等於事件日期。</small></details></li>`).join('')}</ul>`:'<p class="small">（沒有可確認的資料）</p>'}${g.omitted?`<p class="small">另 ${g.omitted} 筆仍存於資料庫，超過本次分類視圖上限。</p>`:''}</section>`).join('')}</div>`;
}
function errorsMarkup(list,record){return list.length?`<ul class="errors">${list.map(e=>`<li><b>${esc(errors[e.type])}</b> <span class="chip">${{new:'本次新寫入',retained:'舊資料仍有效',unknown:'引用來源重疊，待人工歸因'}[errorOrigin(record,e)]}</span><blockquote>${esc(e.outputQuote)}</blockquote><p>原話 [${e.sourceSeq}]：${esc(e.sourceQuote)}</p><small>${esc(e.reason)}</small></li>`).join('')}</ul>`:'<p class="small">本次 AI 判讀未指出重大語義錯誤。</p>';}
function answer(data,r,c){
  const arm=data.manifest.arms.find(a=>a.id===r.armId),q=r.quality,round=r.promptRound||1,state=r.profileConstruction;
  const targets=c.gold[r.task==='facts'?'factTargets':'summaryTargets'];
  const failedUpdates=state?.updateChecks.filter(u=>!u.passed)||[];
  return `<article class="answer ${q.pass?'':'failed'}" data-answer data-task="${r.task}" data-arm="${r.armId}" data-round="${round}" data-pass="${q.pass}" data-errors="${q.errorCount}" data-update-failed="${failedUpdates.length>0}"><h3>${esc(arm.label)} ${r.armId==='luna-high'?`<span class="chip">Prompt ${round}</span>`:''} <span class="chip ${q.pass?'ok':'bad'}">${q.pass?'合格':'未合格'}</span></h3><p>${tasks[r.task]} · ${r.task==='facts'?'新資訊覆蓋':'摘要目標覆蓋'} <b>${fmt(q.newCoverage*100)}%</b> · 全部目標 ${fmt(q.coverage*100)}% · 重大錯誤 <b>${q.errorCount}</b></p><p class="small">${esc(r.config.model)} · ${esc(r.config.effort||'未指定thinking')} · ${r.extractionReceipt?'每階段上限':'上限'} ${r.maxCompletionTokens.toLocaleString('en-US')} · 合计實用 ${r.usage.completion_tokens??'未回報'} completion tokens（含推理） · 次要延遲 ${fmt(r.latencySeconds)}s</p>${!r.apiOk?`<p class="notice warning">API失敗 ${esc(r.error)}；仍列入分母，既有檔案繼續保留。</p>`:!r.formatOk?`<p class="notice warning">格式／管線未通過 ${esc(r.parseError)}；這次没有寫入新的記憶。</p>`:''}${state?`<p class="change-counts">新增 <b>${state.addedFacts.length}</b> · 退下舊事實 <b>${state.removedFacts.length}</b> · 更新檢查 ${state.updateChecks.filter(u=>u.passed).length}/${state.updateChecks.length}</p>${failedUpdates.length?`<p class="notice warning">${failedUpdates.map(u=>`${u.action==='keep'?'原有正確事實未保留':'應退下的舊事實仍有效'}：${esc(u.value)}`).join('；')}</p>`:''}<h4>保存後仍有效的六類個人檔案</h4>${groups(state.profileGroups,c)}<details><summary>每一項舊資料的更新檢查</summary><ul>${state.updateChecks.map(u=>`<li>${u.passed?'✓':'✕'} ${esc(u.value)} · 預期 ${u.action==='keep'?'保留':u.action==='replace'?'取代':'移除'}</li>`).join('')}</ul><p class="small">移除是退出有效檔案；舊資料與更正歷史仍可保留供稽核。取代還須有覆蓋到的新資訊，不能只刪舊值。</p></details><details><summary>模型提案與解析器拒絕紀錄</summary><pre>${esc(JSON.stringify(r.accepted?.validation||{},null,2))}</pre><pre>${esc(JSON.stringify(r.accepted?.facts||[],null,2))}</pre></details>`:`<h4>本次談話與實際累積印象</h4><pre>${esc(r.judgedOutput)}</pre>`}${updateStageMarkup(r)}${errorsMarkup(q.errors,r)}<details><summary>逐項覆蓋與 AI 理由</summary><ul class="coverage">${q.coverageChecks.map(v=>`<li class="${v.covered?'':'missing'}">${v.covered?'✓':'缺'} ${esc(targets.find(t=>t.id===v.targetId)?.meaning)}${v.covered?`<small>輸出依據：${esc(v.outputQuote)}</small>`:''}</li>`).join('')}</ul><p>${esc(q.note)}</p></details><details><summary>完整模型原始輸出</summary><pre>${esc(r.raw||'（未取得文字）')}</pre></details><p class="small">${esc(r.id)} · ${esc(r.finishReason||'API失敗')} · 估計 $${fmt(r.costUsd,4)}</p></article>`;
}
function caseMarkup(data,c){
  const main=data.records.filter(r=>r.caseId===c.id);
  const tuned=(data.promptIterations?.records||[]).filter(r=>r.caseId===c.id&&r.promptRound!==1);
  return `<details class="case" data-case data-difficulty="${c.difficulty}" data-split="${c.split}"${['MM01-hard','MM02-hard'].includes(c.id)?' open':''}><summary><b>${esc(c.id)} · ${esc(c.family)}</b><span class="chip">${c.difficulty.toUpperCase()}</span><span class="chip">${updateStudy(data)?(c.split==='holdout'?'原30題':'原70題'):(c.split==='holdout'?'Holdout':'Development')}</span><span class="small" data-case-count>${main.length+tuned.length} 份輸出</span></summary><details><summary>更新前的六類個人檔案與原始來源</summary>${groups(c.initialProfileGroups,c)}<h4>一般摘要實際可見的既有側寫</h4><pre>${esc(c.profile)}</pre></details><details><summary>本次新資訊與不能混淆的地方</summary><ol class="source">${c.turns.map(t=>`<li><span>[${t.seq}]</span><div class="bubble">${esc(t.text)}</div></li>`).join('')}</ol>${updateStudy(data)?'<p class="small">操作模型可見的相關舊事實，依各配置的新抽取結果而異；完整候選與操作列在各答案的兩階段紀錄。</p>':`<h4>目前可更正候選</h4><pre>${esc(JSON.stringify(c.correctionCandidates,null,2))}</pre>`}<ul>${c.gold.mustNotAssert.map(v=>`<li>${esc(v)}</li>`).join('')}</ul></details><div class="answers">${main.concat(tuned).map(r=>answer(data,r,c)).join('')}</div></details>`;
}
function metricRows(data,task,difficulty){return data.aggregates.filter(a=>a.task===task&&a.difficulty===difficulty).map(a=>`<tr><th>${esc(data.manifest.arms.find(v=>v.id===a.armId).label)}</th><td><b>${fmt(a.passPercent)}%</b><small>${a.passes}/${a.n} · 95%區間 ${a.passInterval.map(v=>fmt(v)).join('–')}%</small></td><td>${fmt(a.newCoveragePercent)}%<small>全部目標 ${fmt(a.coveragePercent)}%</small></td><td>${task==='facts'?fmt(a.updatePassPercent)+'%':'—'}</td><td><b>${a.unsafeOutputs}/${a.n}</b><small>${a.materialErrors} 個重大錯誤</small></td><td>${a.apiFailures} / ${a.formatFailures}</td><td>${fmt(a.latencyP50)}s / ${fmt(a.latencyP95)}s</td></tr>`).join('');}
function updateTable(data){
  return `<section class="panel"><h2>只看確實需要取代／移除的案例</h2><p>上方的更新比例包含只需保留或新增資料的案例。這裡只計已有舊值需要退下的情境，避免把沒有更正的案例算成更正成功。</p><div class="scroll"><table><thead><tr><th>配置</th><th>難度</th><th>取代／移除全通過</th><th>未更動的正確事實保留</th></tr></thead><tbody>${data.manifest.arms.flatMap(arm=>['hard','simple'].map(difficulty=>{
    const rows=data.records.filter(r=>r.armId===arm.id&&r.task==='facts'&&r.difficulty===difficulty);
    const required=rows.filter(r=>r.profileConstruction.updateChecks.some(u=>u.action!=='keep'));
    const kept=rows.flatMap(r=>r.profileConstruction.updateChecks.filter(u=>u.action==='keep'));
    return `<tr><th>${esc(arm.label)}</th><td>${difficulty.toUpperCase()}</td><td><b>${required.filter(r=>r.profileConstruction.updateChecks.every(u=>u.passed)).length}/${required.length}</b></td><td>${kept.filter(u=>u.passed).length}/${kept.length}</td></tr>`;
  })).join('')}</tbody></table></div><p class="small">這項檢查確認旧值退出有效檔案；新的語義內容是否完整，另由資訊覆蓋與原話盲評檢查。不可把只刪舊值當成正確取代。</p></section>`;
}

const metricHead='<tr><th>配置</th><th>合格</th><th>資訊覆蓋</th><th>更新全通過</th><th>有幻覺／錯置的輸出</th><th>API / 格式或管線失敗</th><th>次要：p50 / p95</th></tr>';
function tuningMarkup(data){
  const t=data.promptIterations;
  if(!t)return `<section class="panel"><h2>前次 Luna high 的三版 prompt</h2><p>三版調整屬於先前單次抽取引擎，完整結果保留在封存研究。這次更換操作管理器後，四配置全部重新生成，沒有把前次成績當作新引擎的結果。</p><a href="memory-models-v4.html">查看完整前次研究與三版 prompt</a></section>`;
  return `<section class="panel" id="prompt-iterations"><h2>Luna high：三次 prompt 迭代</h2><p>第 1 版沿用所有模型共用的正式 prompt；第 2、3 版只根據 70 題 development 的問題修訂。30 題 holdout 的結果在第三版固定後才檢視。每版100題、兩種記憶；三版的任何失敗或退步都保留。</p><p class="notice">主表是四配置共用 prompt 的比較；以下是同模型三種 prompt 的獨立盲評。兩者的第 1 版輸出相同，AI 評分可能因判讀波動而不同。</p>${t.plans.map(p=>`<details><summary>Prompt ${p.round}：${esc(p.note)}</summary><p class="small">固定時間 ${esc(p.frozenAt)} · ${p.round===1?'共用主研究實測':'先固定template與development證據的hash，才發出新呼叫'}</p>${Object.entries(p.revisionTexts).map(([task,text])=>`<h4>${tasks[task]}新增指示</h4><pre>${esc(text)}</pre>`).join('')}</details>`).join('')}${['holdout','development'].map(split=>`<h3>${split==='holdout'?'Holdout：保留30題':'Development：用於修訂的70題'}</h3><div class="scroll"><table><thead><tr><th>任務 / 難度</th><th>Prompt</th><th>合格</th><th>資訊覆蓋</th><th>更新全通過</th><th>有幻覺／錯置</th><th>次要：p50 / p95</th></tr></thead><tbody>${t.aggregates.filter(a=>a.split===split&&a.difficulty!=='all').map(a=>`<tr><th>${tasks[a.task]} · ${a.difficulty.toUpperCase()}</th><td>${a.promptRound}</td><td><b>${a.passes}/${a.n}</b><small>${fmt(a.passPercent)}% · ${a.passInterval.map(v=>fmt(v)).join('–')}%</small></td><td>${fmt(a.newCoveragePercent)}%</td><td>${a.task==='facts'?fmt(a.updatePassPercent)+'%':'—'}</td><td>${a.unsafeOutputs}/${a.n}<small>${a.materialErrors} 個重大錯誤</small></td><td>${fmt(a.latencyP50)}s / ${fmt(a.latencyP95)}s</td></tr>`).join('')}</tbody></table></div>`).join('')}<p class="small">同樣100題的模型生成共1200次：四配置主研究800次，加上 high 的第二、三版各200次。第一版在兩種評審中使用同一批200次生成，沒有重抽。三prompt反轉順序合格一致率 ${fmt(t.passAgreement*100)}%（36份）。${esc(t.note)}</p></section>`;
}

export function renderQuality(data,view='profiles'){
  const halluc=view==='hallucinations',title=halluc?'Memory：幻覺與來源錯置':'Memory：耐久檔案的建立與更新';
  const version=sha(JSON.stringify(data)).slice(0,12),asset=name=>sha(fs.readFileSync(new URL('../public/line-v3/'+name,import.meta.url))).slice(0,12);
  const pipeline=updateStudy(data);
  const fresh=data.records.concat((data.promptIterations?.records||[]).filter(r=>r.promptRound!==1));
  const apiFailures=fresh.filter(r=>!r.apiOk).length,formatFailures=fresh.filter(r=>r.apiOk&&!r.formatOk).length;
  const cost=fresh.reduce((n,r)=>n+r.costUsd,0)+data.judge.costUsd+(data.promptIterations?.judgeCostUsd||0);
  return `<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Machi · ${title}</title><link rel="canonical" href="https://jefflai108.github.io/line-v3/${halluc?'memory-hallucinations':'memory-models'}.html"><link rel="stylesheet" href="memory-models.css?v=${asset('memory-models.css')}"><script type="module" src="memory-quality.js?v=${asset('memory-quality.js')}"></script></head><body class="benchmark-page nojs"><a class="skip" href="#content">跳到內容</a><nav class="tabs" aria-label="比較分頁"><a href="memory-models.html"${halluc?'':' aria-current="page"'}>Memory 檔案</a><a href="memory-hallucinations.html"${halluc?' aria-current="page"':''}>Memory 幻覺</a></nav><header><p class="eyebrow">HeyMachi / LINE v3 · ${esc(new Date(data.publishedAt).toLocaleDateString('en-CA',{timeZone:'Asia/Taipei'}))} · 完整實測</p><h1>${title}</h1><p>${halluc?'會不會把舊日記當現在、把朋友當前室友、把引文當成本人資料？逐项查有來源的重大語義錯誤。':'已有六類個人檔案，收到新資訊後，該新增的有沒有加、該退下的有沒有退、原本正確的有沒有留？查看實際保存後的檔案與原文。'}</p><div class="tiles"><div class="tile"><b>100 題</b><span>50 SIMPLE / 50 HARD · 50配對題族</span></div><div class="tile"><b>16,384 tokens</b><span>${pipeline?'每API階段同上限；檔案最多兩階段':'Baseline 與三選項全部同上限'}</span></div><div class="tile"><b>${pipeline?'ADD · UPDATE · DELETE · NONE':'3 版 high prompt'}</b><span>${pipeline?'100題已檢視的合成回歸案例':'70 development / 30 holdout'}</span></div><div class="tile"><b>${fresh.length} 份任務輸出</b><span>API失敗 ${apiFailures} · 格式或管線失敗 ${formatFailures}</span></div></div><p class="notice"><b>品質、可靠更新與幻覺是主要指標；延遲是次要指標。</b>一般LINE記憶派生在背景佇列執行，回覆不等待記憶LLM。此處的p50/p95只計生成API，不含ASR、LINE、佇列、SQLite或評審。現行正式普通Luna/Terra呼叫仍預設8192，這份比較對所有候選都用16384。</p></header><main id="content" data-memory-report data-view="${view}" data-version="${data.version}" data-results="memory-models-results.public.json?v=${version}"><section class="panel"><h2>${pipeline?'共用template':'共同prompt'}：${halluc?'先看重大錯誤，再看覆蓋':'先看完整性與正確更新'}</h2><div class="filters interactive"><label>記憶任務<select data-metric="task"><option value="facts">耐久個人檔案</option><option value="summary">一般摘要＋累積印象</option></select></label><label>難度<select data-metric="difficulty"><option value="hard">HARD</option><option value="simple">SIMPLE</option><option value="all">全部100題</option></select></label><label>資料範圍<select data-metric="split"><option value="all">全部</option><option value="holdout">${pipeline?'原30題（已檢視）':'Holdout'}</option><option value="development">${pipeline?'原70題（已檢視）':'Development'}</option></select></label></div><p class="status" data-metric-caption>耐久個人檔案 · HARD · 每配置50次；所有計畫呼叫都列入分母。</p><p class="load-status notice warning" data-load-status role="status"></p><div data-plot></div><div class="scroll"><table class="numeric metric-table"><thead>${metricHead}</thead><tbody data-metric-rows>${metricRows(data,'facts','hard')}</tbody></table></div><div data-error-types></div><p class="small">合格＝${esc(data.method.qualityRule)}。耐久個人檔案另外要求本次新資訊覆蓋至少80%；摘要覆蓋率評本次談話與累積印象的全部目標。空輸出也不能靠零幻覺拿到好成績。區間按50題族群bootstrap；每題每配置每任務只取一次，沒有重抽失敗。</p><details><summary>一般摘要 HARD 靜態表</summary><div class="scroll"><table><thead>${metricHead}</thead><tbody>${metricRows(data,'summary','hard')}</tbody></table></div></details><details><summary>SIMPLE 靜態表</summary>${['facts','summary'].map(task=>`<h3>${tasks[task]}</h3><div class="scroll"><table><thead>${metricHead}</thead><tbody>${metricRows(data,task,'simple')}</tbody></table></div>`).join('')}</details></section><section class="panel"><h2>${halluc?'什麼算幻覺？':'建立、更新與保留分開查'}</h2>${halluc?`<p>逐項查 ${Object.values(errors).join('、')}。每個重大錯誤都要引用實際保存的輸出與對應原話。漏掉資訊歸覆蓋率；沒有捏造但漏掉新資訊仍然失敗。</p><p>錯誤另按來源區分：本次新寫入、既有錯誤未退出有效檔案、以及短引用重疊而無法唯一歸因。這個來源標籤依保存事實與原始引用比對，不改AI成績。拒絕的模型提案不算已保存的幻覺。更新未成功而繼續有效的舊錯誤算記憶錯誤；API或格式失敗則同時列出，避免把沒有完成的新寫入誤算成功。</p>`:`<p>每個案例先有帶來源的合成個人檔案。${pipeline?'先從本次原話抽取新事實，再對照相關舊事實提案四種操作，以真實的中央更新交易寫入隔離SQLite，评保存後仍有效的資料。':'耐久模型只收到正式V2允許的本次原話與相關更正候選，接著用真實解析器、correction/merge與分類方法寫入隔離SQLite，評保存後仍有效的資料。'}一般摘要還會收到既有側寫。</p><p>新增看本次資訊覆蓋；替換和移除查旧事實有沒有退出有效檔案；保留查未更動的正確事實是否還在。保存後的六類檔案每類最多8點，原文和證據編號可以逐點展開。</p>`}<p>舊女友、前室友、地址／工作更新、目標取消、愛好部分更新、多位近似名字、借住／同居、資格／學習、未知日期、引文與偽指令均有對應案例。這些是合成人物與自述，沒有使用學生身分或私密日記。</p></section>${updateTable(data)}${updateProtocolMarkup(data)}${tuningMarkup(data)}<section class="panel"><h2>四種配置</h2><div class="scroll"><table><thead><tr><th>配置</th><th>一般摘要</th><th>耐久檔案抽取${pipeline?'／操作管理':''}</th><th>候選completion上限</th></tr></thead><tbody>${data.manifest.arms.map(a=>`<tr><th>${esc(a.label)}</th>${['summary','facts'].map(task=>`<td><code>${a[task].model}</code><small>${a[task].effort||'未指定thinking，與正式基線一致'}</small></td>`).join('')}<td>16,384</td></tr>`).join('')}</tbody></table></div><p class="small">${pipeline?'主表共用template，操作管理使用同一配置的耐久模型與thinking。日記標題、摘要與新耐久事實共用第一階段呼叫；只有相關舊事實才另呼叫操作管理。':'主表本次共用prompt。V2的日記標題、摘要與耐久事實共用一次抽取模型呼叫；'}另測的一般摘要路徑是session_zh.txt。Option 1與Option 3的一般摘要使用相同模型／thinking參數，差異來自獨立生成。資訊覆蓋欄：耐久檔案計本次新資訊，摘要計全部摘要目標。此評估沒有自動切換正式模型，也沒有把個別案例最好的答案拼成結果。</p></section><section data-explorer><h2>逐題看更新前／後、原文與幻覺</h2><div class="filters interactive"><label>難度<select data-filter="difficulty"><option value="hard">HARD</option><option value="simple">SIMPLE</option><option value="">全部</option></select></label><label>任務<select data-filter="task"><option value="facts">耐久個人檔案</option><option value="summary">一般摘要</option><option value="">兩種</option></select></label><label>配置<select data-filter="arm"><option value="">全部配置</option>${data.manifest.arms.map(a=>`<option value="${a.id}">${esc(a.label)}</option>`).join('')}</select></label><label>Prompt<select data-filter="round"><option value="1">本次共用prompt</option>${data.promptIterations?'<option value="2">Luna high · 第2版</option><option value="3">Luna high · 第3版</option>':''}<option value="">所有版本</option></select></label><label>資料範圍<select data-filter="split"><option value="">全部</option><option value="development">${pipeline?'原70題（已檢視）':'Development'}</option><option value="holdout">${pipeline?'原30題（已檢視）':'Holdout'}</option></select></label><label>檢查<select data-filter="problem"><option value="">所有輸出</option><option value="hallucination"${halluc?' selected':''}>有重大錯誤</option><option value="update">更新檢查失敗</option><option value="failed">所有未合格</option></select></label><label>搜尋<input type="search" data-filter="search" placeholder="例如：前室友、當護士"></label></div><p class="status" data-visible aria-live="polite">100題 · ${fresh.length}份實測輸出</p>${data.cases.map(c=>caseMarkup(data,c)).join('')}</section><section class="panel method"><h2>AI評審與可重查證據</h2><p><code>gpt-6-astra · medium · 16384</code>，匿名判讀，看不到候選模型、thinking、延遲或費用。目標與失敗條件在生成前固定。已知正確、錯時間、錯人物和空輸出的4組控制題均通過；引用不存在時拒絕判讀，最多重新判讀一次。</p><p>四配置主研究的反轉順序合格一致率 ${fmt(data.judge.passAgreement*100)}%（48份）${data.promptIterations?`；三prompt一致率 ${fmt(data.promptIterations.passAgreement*100)}%（36份）`: ''}。AI仍可能誤判，原始覆蓋、錯誤引用和不同判讀都保留於下載資料。</p><details><summary>完整判讀規則</summary><pre>${esc(data.judge.rubric)}</pre></details><p>候選／評審各最多12併發、共用API帳號且部分重疊；HTTP暫時錯誤最多3次，不重抽語義或格式失敗、沒有跨模型fallback。總成本估計 $${fmt(cost,2)}，按2026-10-14標準牌價與API用量推算，含推理tokens；不是帳單。</p><p>來源程式版本 <code>${esc(data.manifest.sourceCommit)}</code>。完整prompt、程式、題集與receipt的hash保留於manifest。${pipeline?'沿用已檢視的作者合成案例，用於回歸檢查，原70／30標籤並不代表未看過的holdout。兩階段改變運算量，不能把差異全歸因於模型。 部分覆蓋未合格源於保守的來源、人物或時序門檻；仍依凍結目標計分，不事後調整答案。模型來源視圖有長度上限，因此長訊息尾端的資訊可能遺漏；正式保存驗證使用完整原文。':'公開修訂文字見上方迭代。此題集由作者設計，holdout限制prompt調整，但不是外部真實使用者驗證。'}</p><div class="download"><a href="memory-models-results.public.json?v=${version}" download>下載完整100題、${fresh.length}份輸出與AI判讀（JSON）</a><a href="memory-models-summary.csv?v=${version}" download>四配置彙總（CSV）</a>${data.promptIterations?`<a href="memory-prompt-iterations-summary.csv?v=${version}" download>三prompt／development／holdout彙總（CSV）</a>`: ''}<a href="memory-models-8192-profile-v2.public.json" download>前次32題／8192完整原始結果（不同題集，不合併成績）</a></div><p class="small">價格資料：${data.method.pricingLinks.map(url=>`<a href="${esc(url)}">${esc(url.split('/').pop())}</a>`).join(' · ')}。</p></section><noscript><p class="notice">保留靜態成績與所有案例；篩選和互動圖需啟用JavaScript。</p></noscript><footer>品質、可靠更新與幻覺優先；延遲次要。沒有依此比較自動切換正式記憶模型。</footer></main></body></html>`;
}
