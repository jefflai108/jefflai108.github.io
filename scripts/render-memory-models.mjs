import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';

const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(n,d=1)=>Number(n).toFixed(d);
const canonical=v=>Array.isArray(v)?'['+v.map(canonical).join(',')+']':v&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}':JSON.stringify(v);
const sha=v=>crypto.createHash('sha256').update(v).digest('hex');
const same=(a,b)=>canonical(a)===canonical(b);
const fail=message=>{throw new Error(message)};
const quantile=(values,p)=>{const a=[...values].sort((x,y)=>x-y),i=(a.length-1)*p;return a[Math.floor(i)]+(a[Math.ceil(i)]-a[Math.floor(i)])*(i-Math.floor(i));};
const receiptFields=['id','caseId','task','armId','repeat','config','promptHash','startedAt','completedAt','apiOk','formatOk','parseError','error','raw','accepted','modelReturned','finishReason','usage','attempts','latencySeconds','serviceTier'];
export const receiptHash=r=>sha(canonical(Object.fromEntries(receiptFields.filter(k=>Object.hasOwn(r,k)).map(k=>[k,r[k]]))));

export function validateData(data){
  if(/(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9_.-]{16,}|\/Users\/|\/srv\/heymachi\/|OPENAI_API_KEY)/.test(JSON.stringify(data)))fail('Private material in public artifact');
  if(data.version!=='memory-models-profile-v2'||data.cases.length!==32||data.records.length!==512)fail('Incomplete measured study');
  if(sha(canonical(data.cases))!==data.manifest.casesHash)fail('Cases changed after freezing');
  const expectedArms=[['baseline','gpt-5.6-luna',null,'gpt-5.6-terra',null],['luna-medium','gpt-6-luna','medium','gpt-6-luna','medium'],['luna-high','gpt-6-luna','high','gpt-6-luna','high'],['luna-sol','gpt-6-luna','medium','gpt-6.1-sol','low']];
  if(data.manifest.arms.length!==4)fail('Wrong arm count');
  for(const [i,expected] of expectedArms.entries()){
    const a=data.manifest.arms[i];if(!same([a.id,a.summary.model,a.summary.effort,a.facts.model,a.facts.effort],expected))fail('Requested model configurations changed');
  }
  const caseMap=new Map(data.cases.map(c=>[c.id,c]));
  if(caseMap.size!==32||['hard','simple'].some(d=>data.cases.filter(c=>c.difficulty===d).length!==16))fail('Paired corpus missing');
  const records=new Map(data.records.map(r=>[r.id,r]));
  if(records.size!==512)fail('Duplicate measured receipt');
  for(const c of data.cases)for(const task of ['facts','summary'])for(const arm of data.manifest.arms)for(const repeat of [1,2]){
    const id=`${c.id}:${task}:${arm.id}:r${repeat}`,r=records.get(id);
    if(!r||r.caseId!==c.id||r.task!==task||r.armId!==arm.id||r.repeat!==repeat||r.difficulty!==c.difficulty||!same(r.config,arm[task]))fail('Generation binding mismatch');
    if(r.receiptHash!==receiptHash(r))fail('Generation receipt changed after measurement');
    if(r.promptHash!==data.manifest.prompts[`${c.id}:${task}`]||r.apiOk&&r.modelReturned!==r.config.model)fail('Prompt or actual model mismatch');
    if(!Number.isFinite(r.latencySeconds)||r.latencySeconds<=0)fail('Measured latency missing');
    if(r.formatOk&&!r.accepted)fail('Accepted memory missing');
  }
  const judged=new Set();
  if(data.judge.primaryEvaluations.length!==128||data.judge.config.model!=='gpt-6-astra'||data.judge.config.effort!=='medium')fail('Judge denominator/configuration mismatch');
  for(const j of data.judge.primaryEvaluations){
    if(j.evaluations.length!==4||new Set(j.evaluations.map(e=>e.label)).size!==4||Object.keys(j.mapping).length!==4)fail('Judge label binding mismatch');
    for(const e of j.evaluations){
      const r=records.get(j.mapping[e.label]),c=caseMap.get(r?.caseId);
      if(!r||judged.has(r.id)||j.id!==`${r.caseId}:${r.task}:r${r.repeat}`||r.quality.judgePacketId!==j.id)fail('Judge/candidate binding mismatch');
      judged.add(r.id);
      const targets=c.gold[r.task==='facts'?'factTargets':'summaryTargets'];
      if(!same([...e.coverage.map(v=>v.targetId)].sort(),targets.map(t=>t.id).sort()))fail('Coverage targets mismatch');
      for(const v of e.coverage)if(typeof v.covered!=='boolean'||v.covered&&(!v.outputQuote||!r.judgedOutput.includes(v.outputQuote))||!v.covered&&v.outputQuote)fail('Coverage quote mismatch');
      for(const error of e.errors){
        const source=c.turns.find(t=>t.seq===error.sourceSeq);
        if(!error.outputQuote||!r.judgedOutput.includes(error.outputQuote)||!source||!error.sourceQuote||!source.text.includes(error.sourceQuote))fail('Judge evidence mismatch');
      }
      const coverage=e.coverage.filter(v=>v.covered).length/e.coverage.length;
      const score=r.formatOk?(e.errors.length?0:60)+40*coverage:0;
      if(r.quality.pass!==Boolean(r.formatOk&&!e.errors.length&&coverage>=.8)||Math.abs(r.quality.score-score)>.0011||r.quality.coverage!==coverage||!same(r.quality.errors,e.errors)||!same(r.quality.coverageChecks,e.coverage))fail('Quality changed after judgment');
    }
    const first=records.get(Object.values(j.mapping)[0]),c=caseMap.get(first.caseId);
    const packet={task:first.task,source:c.turns.map(t=>({seq:t.seq,text:t.text})),correctionCandidates:c.correctionCandidates,
      targets:c.gold[first.task==='facts'?'factTargets':'summaryTargets'],mustNotAssert:c.gold.mustNotAssert,scope:c.gold.scope,
      candidates:Object.entries(j.mapping).map(([label,id])=>({label,output:records.get(id).judgedOutput})),
      inputProfile:first.task==='summary'?c.profile:'',inputRecent:first.task==='summary'?c.recent:[]};
    if(j.packetHash!==sha(canonical(packet))||j.promptHash!==sha(canonical(data.judge.rubric+'\nDATA JSON:\n'+canonical(packet))))fail('Judge input or protocol changed');
  }
  if(judged.size!==records.size)fail('Unjudged outputs');
  if(data.judge.calibration.length!==4)fail('Judge calibration missing');
  for(const c of data.judge.calibration){
    const e=Object.fromEntries(c.evaluations.map(v=>[v.label,v]));
    if(!e.A||e.A.errors.length||e.A.coverage.some(v=>!v.covered)||!e.B.errors.length||!e.C.errors.length||e.D.errors.length||e.D.coverage.some(v=>v.covered))fail('Judge calibration failed');
  }
  if(data.judge.mirrorRecords.length!==96||new Set(data.judge.mirrorRecords.map(m=>m.generationId)).size!==96)fail('Reversed-order audit missing');
  const agreement=data.judge.mirrorRecords.filter(m=>m.originalPass===m.reversedPass).length/96;
  if(agreement!==data.judge.passAgreement)fail('Judge agreement changed');
  if(data.manifest.maxCompletionTokens!==8192||data.manifest.productionDefaultCap!==8192)fail('Memory token default mismatch');
  for(const r of data.records.filter(r=>r.task==='facts'&&r.formatOk)){
    const groups=r.accepted.profileGroups;
    if(!groups||groups.length!==6||groups.some(g=>g.facts.length>8))fail('Profile category cap missing');
    const flattened=groups.flatMap(g=>g.facts),facts=r.accepted.facts;
    if(flattened.length!==facts.length||flattened.some(f=>!facts.some(v=>same(v,f))))fail('Profile facts changed');
    const c=caseMap.get(r.caseId);
    for(const f of facts){
      const source=c.turns.find(t=>t.seq===f.evidence_seq);
      if(!source||!source.text.includes(f.value))fail('Fact original source missing');
    }
  }
  if(data.aggregates.length!==24)fail('Aggregate denominator missing');
  for(const a of data.aggregates){
    const selected=data.records.filter(r=>r.task===a.task&&r.armId===a.armId&&(a.difficulty==='all'||r.difficulty===a.difficulty));
    if(a.n!==selected.length||a.passes!==selected.filter(r=>r.quality.pass).length||a.unsafeOutputs!==selected.filter(r=>r.quality.errorCount>0).length||a.apiFailures!==selected.filter(r=>!r.apiOk).length||a.formatFailures!==selected.filter(r=>r.apiOk&&!r.formatOk).length)fail('Aggregate changed after measurement');
    for(const [key,p] of [['latencyP50',.5],['latencyP95',.95]])if(Math.abs(a[key]-quantile(selected.map(r=>r.latencySeconds),p))>.00051)fail('Latency changed after measurement');
  }
  const text=JSON.stringify(data);
  if(/(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9_.-]{16,}|\/Users\/|\/srv\/heymachi\/|OPENAI_API_KEY)/.test(text))fail('Private material in public artifact');
  return data;
}

const taskLabel={facts:'耐久事實抽取',summary:'一般摘要＋累積印象'};
const typeLabel={past_as_current:'把過去當現在',wrong_person:'人物／關係錯置',negation:'否定遺失',unsupported:'無依據新增',source_instruction:'資料偽指令',correction:'更正對象錯誤',uncertainty:'擅自補完未知'};
const colors=['#687b72','#27897b','#c08735','#7565a5'];
function metricRows(data,task,difficulty){
  return data.aggregates.filter(a=>a.task===task&&a.difficulty===difficulty).map((a,i)=>`<tr><th scope="row"><span class="swatch" style="background:${colors[i]}"></span> ${esc(data.manifest.arms[i].label)}</th><td><b>${fmt(a.passPercent)}%</b><small>${a.passes}/${a.n} · 區間 ${a.passInterval.map(v=>fmt(v)).join('–')}%</small></td><td>${a.unsafeOutputs}/${a.n}<small>${a.materialErrors} 個重大錯誤</small></td><td>${fmt(a.coveragePercent)}%<small>${fmt(a.scoreMean)} / 100 分</small></td><td><b>${fmt(a.latencyP50)}s</b></td><td>${fmt(a.latencyP95)}s<small>超過40s：${a.over40Seconds}/${a.n}</small></td><td>${a.apiFailures} / ${a.formatFailures}<small>API / 格式</small></td><td>$${fmt(a.costUsd/a.n,4)}<small>${Math.round(a.outputTokens/a.n).toLocaleString('en-US')} 輸出 tokens/次</small></td></tr>`).join('');
}
const metricHead='<tr><th>配置</th><th>合格率</th><th>有重大錯誤</th><th>覆蓋／品質</th><th>p50</th><th>p95</th><th>失敗</th><th>每次估計成本</th></tr>';
function quickTable(data,task){
  const rows=data.aggregates.filter(a=>a.task===task&&a.difficulty==='hard');
  return `<div class="scroll"><table class="numeric"><caption>${taskLabel[task]} · HARD</caption><thead><tr><th>配置</th><th>合格</th><th>p50 / p95</th></tr></thead><tbody>${rows.map((a,i)=>`<tr><th scope="row">${esc(data.manifest.arms[i].label)}</th><td>${a.passes}/${a.n}<small>${fmt(a.passPercent)}%</small></td><td>${fmt(a.latencyP50)}s / ${fmt(a.latencyP95)}s</td></tr>`).join('')}</tbody></table></div>`;
}
function errorsMarkup(errors){return errors.map(e=>`<div class="error"><b>${esc(typeLabel[e.type]||e.type)}</b> · ${esc(e.reason)}<q>${esc(e.outputQuote)}</q><small>原話 [${e.sourceSeq}]：${esc(e.sourceQuote)}</small></div>`).join('');}
function factProfile(r,c){
  if(!r.formatOk)return '<p class="empty">（本次沒有可保存的事實）</p>';
  return `<div class="profile-groups">${r.accepted.profileGroups.map(g=>`<section class="profile-group"><h5>${esc(g.category)} <small>${g.facts.length}/8</small></h5>${g.facts.length?`<ul>${g.facts.map(f=>{
    const source=c.turns.find(t=>t.seq===f.evidence_seq);
    return `<li><span class="fact-value">${esc(f.value)}</span><small>模型整理 · ${f.temporal_scope==='ongoing'?'持續近況':'耐久候選'} · 原話 [${f.evidence_seq}]${f.supersedes_ordinal?` · 更正候選 ${f.supersedes_ordinal}`:''}</small><details><summary>對照證據原話</summary><div class="bubble">${esc(source.text)}</div><p class="small">測試保存日 ${esc(c.date)}；不是事件發生日期。保留原文的以前、暫住、目標等限定。</p></details></li>`;
  }).join('')}</ul>`:'<p class="empty">本次沒有合格事實</p>'}</section>`).join('')}</div>`;
}
function answer(data,r,c){
  const arm=data.manifest.arms.find(a=>a.id===r.armId),q=r.quality;
  const targets=c.gold[r.task==='facts'?'factTargets':'summaryTargets'];
  const token=r.usage,stats=r.accepted?.validation;
  const mirror=data.judge.mirrorRecords.find(m=>m.generationId===r.id);
  const mirrorChanged=mirror&&(mirror.originalPass!==mirror.reversedPass||mirror.originalScore!==mirror.reversedScore);
  return `<article class="answer ${q.pass?'':'failed'}" data-answer data-task="${r.task}" data-arm="${r.armId}" data-repeat="${r.repeat}" data-pass="${q.pass}"><h3>${esc(arm.label)} <span class="chip ${q.pass?'ok':'bad'}">${q.pass?'合格':'未合格'}</span></h3><p>${taskLabel[r.task]} · 第 ${r.repeat} 次 · <b>${fmt(r.latencySeconds)}s</b> · ${fmt(q.score)} 分 · 覆蓋 ${fmt(q.coverage*100)}%</p><p><code>${esc(r.config.model)}</code> · ${r.config.effort?esc(r.config.effort):'未指定 thinking（現行呼叫）'} · ${token.prompt_tokens??'未回報'} 輸入／${token.completion_tokens??'未回報'} 輸出 tokens · 推理 ${token.completion_tokens_details?.reasoning_tokens??'未回報'}</p>${!r.apiOk?`<p class="notice warning">API失敗：${esc(r.error)}；仍列入分母。</p>`:!r.formatOk?`<p class="notice warning">${esc(r.parseError)}：正式解析器未接受這次輸出；仍列入分母。</p>`:''}<h4>${r.task==='facts'?'驗證後可保存的事實':'可保存的摘要與實際累積印象'}</h4>${r.task==='facts'?factProfile(r,c):`<pre>${esc(r.judgedOutput||'（沒有可保存的輸出）')}</pre>`}${stats?`<p>模型提案 ${stats.proposed} 筆 · 通過 ${stats.accepted} 筆 · 拒絕 ${Object.entries(stats.rejected).map(([k,v])=>esc(k)+': '+v).join('、')||'0 筆'}。拒絕的提案不算已存記憶錯誤，但會影響覆蓋率。</p>`:''}${errorsMarkup(q.errors)}<details><summary>AI 評審逐項覆蓋與理由</summary><ul class="coverage">${q.coverageChecks.map(v=>`<li class="${v.covered?'':'missing'}">${v.covered?'✓':'缺'} ${esc(targets.find(t=>t.id===v.targetId)?.meaning)}${v.covered?`<small>輸出依據：${esc(v.outputQuote)}</small>`:''}</li>`).join('')}</ul><p>${esc(q.note)}</p></details>${mirrorChanged?`<details><summary><span class="chip warning">反轉順序判讀有差異</span></summary><p>原始 ${fmt(mirror.originalScore)} 分／${mirror.originalPass?'合格':'未合格'}；反轉 ${fmt(mirror.reversedScore)} 分／${mirror.reversedPass?'合格':'未合格'}。主表固定使用原始盲評。</p>${errorsMarkup(mirror.reversedErrors)}<p>${esc(mirror.reversedNote)}</p></details>`:''}<details><summary>完整模型原始輸出</summary><pre>${esc(r.raw||'（未取得文字）')}</pre></details><p class="small">${esc(r.id)} · ${esc(r.finishReason??'API失敗')} · HTTP ${r.attempts.length} 次 · 估計 $${fmt(r.costUsd,4)}</p></article>`;
}
function caseMarkup(data,c){
  const records=data.records.filter(r=>r.caseId===c.id);
  const chars=c.turns.reduce((n,t)=>n+t.text.length,0);
  return `<details class="case" id="${c.id}" data-case data-difficulty="${c.difficulty}"${['MM01-hard','MM02-hard'].includes(c.id)?' open':''}><summary><b>${esc(c.id)} · ${esc(c.family)}</b><span class="chip">${c.difficulty.toUpperCase()}</span><span class="small">${c.turns.length} 則／${chars} 字</span><span class="small" data-case-count>16 份輸出</span></summary><details><summary>原始合成輸入、過時側寫與評分目標</summary><ol class="source">${c.turns.map(t=>`<li><span>[${t.seq}]</span><div class="bubble">${esc(t.text)}</div></li>`).join('')}</ol><h4>既有側寫（一般摘要可見；V2 事實抽取不使用）</h4><pre class="source-profile">${esc(c.profile||'（空）')}</pre>${c.correctionCandidates.length?`<h4>本次可更正候選</h4><pre>${esc(JSON.stringify(c.correctionCandidates,null,2))}</pre>`:''}<h4>不可混淆／擅自補完</h4><ul>${c.gold.mustNotAssert.map(t=>`<li>${esc(t)}</li>`).join('')}</ul><p class="small">目標意思只提供給評審，不提供給候選模型。逐項目標見各輸出的判讀明細。</p></details><div class="answers">${records.map(r=>answer(data,r,c)).join('')}</div></details>`;
}

export function render(data){
  validateData(data);
  const apiFailures=data.records.filter(r=>!r.apiOk).length,formatFailures=data.records.filter(r=>r.apiOk&&!r.formatOk).length;
  const cost=data.records.reduce((n,r)=>n+r.costUsd,0);
  const differences=data.hardPairedDifferences.map(d=>`<tr><th scope="row">${taskLabel[d.task]}</th><td>${esc(data.manifest.arms.find(a=>a.id===d.armId).label)}</td><td>${d.passPointDifference>0?'+':''}${fmt(d.passPointDifference)} pp</td><td>${d.pairedInterval.map(v=>fmt(v)).join(' 至 ')} pp</td></tr>`).join('');
  const version=sha(JSON.stringify(data)).slice(0,12);
  const cssVersion=sha(fs.readFileSync(new URL('../public/line-v3/memory-models.css',import.meta.url))).slice(0,12);
  const jsVersion=sha(fs.readFileSync(new URL('../public/line-v3/memory-models.js',import.meta.url))).slice(0,12);
  return `<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Machi · Memory 品質與延遲</title><meta name="description" content="Machi 記憶模型實測：耐久事實與一般摘要，HARD/SIMPLE配對、AI盲評、p50/p95時間與逐題原始輸出。"><link rel="canonical" href="https://jefflai108.github.io/line-v3/memory-models.html"><link rel="stylesheet" href="memory-models.css?v=${cssVersion}"><script src="memory-models.js?v=${jsVersion}" defer></script></head><body class="benchmark-page nojs"><a class="skip" href="#content">跳到內容</a><nav class="tabs" aria-label="比較分頁"><a href="memory-models.html" aria-current="page">Memory 記憶</a></nav><header><p class="eyebrow">HeyMachi / LINE v3 · ${esc(new Date(data.publishedAt).toLocaleDateString('en-CA',{timeZone:'Asia/Taipei'}))} · 完整實測</p><h1>Memory：品質與等待時間</h1><p>老日記的「有女朋友」能否保留過去的時間？現在借住的朋友會不會被記成前室友？用 16 組 HARD / SIMPLE 配對情境，比較四種模型配置的耐久事實與一般摘要，並保留每一次生成、驗證與 AI 盲評。</p><div class="tiles"><div class="tile"><b>32 題 × 2 次</b><span>16 題 HARD、16 題 SIMPLE；相同核心技能</span></div><div class="tile"><b>512 次</b><span>主研究 512 次；API失敗 ${apiFailures}、格式失敗 ${formatFailures}</span></div><div class="tile"><b>${fmt(data.judge.passAgreement*100)}%</b><span>AI 評審反轉順序合格判斷一致率 · ${data.judge.mirrorDecisions} 份輸出</span></div><div class="tile"><b>$${fmt(cost,2)}</b><span>主研究生成；所有評審 $${fmt(data.judge.costUsd,2)}</span></div></div><p class="notice"><b>這裡的時間是記憶生成 API 等到完整輸出的時間。</b>它不包含 ASR、LINE 回覆、AI 評審或整個應用流程。所有配置使用相同 prompt、解析器與 8192 completion tokens 上限；正式記憶預設同為8192。此處未包含應用流程，不能直接當成LINE回覆時間。</p></header><main id="content" data-memory-report data-version="${data.version}" data-results="memory-models-results.public.json?v=${version}"><section class="panel"><h2>兩種記憶，各自看品質與時間</h2><div class="grid2">${quickTable(data,'facts')}${quickTable(data,'summary')}</div><p class="small">合格＝正式格式可接受、沒有重大語義錯誤、目標覆蓋至少 80%。每一格 24 次；2 次重複只描述這些合成題的波動，不是正式使用者成功率。</p></section><section class="panel"><h2>品質、速度與成本一起比較</h2><div class="filters interactive"><label>記憶任務<select data-metric="task"><option value="facts">耐久事實抽取</option><option value="summary">一般摘要＋累積印象</option></select></label><label>題目難度<select data-metric="difficulty"><option value="hard">HARD</option><option value="simple">SIMPLE</option><option value="all">全部配對題</option></select></label></div><p class="status" data-metric-caption>耐久事實抽取 · HARD · 每組 24 次；全部計畫呼叫均列入分母。</p><p class="load-status notice warning" data-load-status role="status"></p><div data-plot></div><div class="legend">${data.manifest.arms.map((a,i)=>`<span><i class="swatch" style="background:${colors[i]}"></i>${['B','M','H','S'][i]} · ${esc(a.label)}</span>`).join('')}</div><div class="scroll"><table class="numeric metric-table"><thead>${metricHead}</thead><tbody data-metric-rows>${metricRows(data,'facts','hard')}</tbody></table></div><p class="small">區間：以 12 題族群為單位的 95% bootstrap；p95 是本次樣本的 95 百分位。延遲包含暫時 HTTP 錯誤的重試與退避。40 秒是供觀察的固定門檻，沒有模擬正式逾時與 fallback。</p><details><summary>所有 SIMPLE 結果（靜態表）</summary>${['facts','summary'].map(t=>`<h3>${taskLabel[t]}</h3><div class="scroll"><table class="numeric metric-table"><thead>${metricHead}</thead><tbody>${metricRows(data,t,'simple')}</tbody></table></div>`).join('')}</details><details><summary>HARD 一般摘要完整表</summary><div class="scroll"><table class="numeric metric-table"><thead>${metricHead}</thead><tbody>${metricRows(data,'summary','hard')}</tbody></table></div></details></section><section class="panel"><h2>相對現行模型配置，有多少改善？</h2><div class="scroll"><table class="numeric"><thead><tr><th>HARD 任務</th><th>候選配置</th><th>合格率差</th><th>配對 95% 區間</th></tr></thead><tbody>${differences}</tbody></table></div><p class="small">正值表示此題集的合格率較高；區間包含 0 時，這個樣本不足以確定較優。一般摘要在 Option 1 與 Option 3 使用完全相同的模型／參數，觀察差異來自獨立生成。</p><p><a href="#MM01-hard">檢查「舊日記→現在女友」案例</a> · <a href="#MM02-hard">檢查「借住朋友→前室友」案例</a></p></section><section class="panel"><h2>六大個人分類，逐點檢查來源</h2><p>個人背景、重要關係、工作與學習、喜好與習慣、生活目標、近期動態。每類最多八點；每次抽取最多32個原子事實。點數是上限，沒有資料就留空。原子事實保留使用者原文與證據編號，不合併成一段側寫。</p><p>新題族13至16檢查取消目標、學習與語言偏好、超過六個事實和八點上限。下方每份事實輸出按分類呈現，可展開對照原話；被驗證器拒絕的提案不會出現在可保存的個人分類中。即時LINE上下文仍按相關性與來源大小裁切。</p><p>本次已將正式記憶預設提高到8192並更新分類prompt；四種模型仍只是比較組，未因這份評估更換正式模型。</p></section><section class="panel"><h2>四種配置與實際測量範圍</h2><div class="scroll"><table class="arm-table"><thead><tr><th>配置</th><th>一般摘要＋累積印象</th><th>耐久事實抽取</th></tr></thead><tbody>${data.manifest.arms.map(a=>`<tr><th scope="row">${esc(a.label)}</th>${['summary','facts'].map(t=>`<td><code>${a[t].model}</code><small>${a[t].effort||'未指定 reasoning_effort，與現行呼叫一致'}</small></td>`).join('')}</tr>`).join('')}</tbody></table></div><p>一般摘要測量現有 <code>session_zh.txt</code> 產生的「本次談話＋累積印象」，不含日彙總。耐久事實測量現有 V2 儲存 prompt 的完整回覆與原子事實驗證，只評估會被接受的事實。V2 的日記標題與摘要和事實共用同一次模型呼叫，不能把它們誤認為另一個 Luna 呼叫。</p><p class="small">Baseline 是現行模型與 prompt 配置的受控比較；沒有模擬正式 2048 上限、語義重試或 Gemini fallback。沒有變更正式模型、記憶資料庫或部署時間保護修補。</p></section><section data-explorer><h2>逐題看原話、記憶與判讀</h2><p>題目使用合成人物與日記，重現時間、關係與來源錯置；沒有使用學生身分或原始私密日記。HARD 包含倒序補上傳、多人同名、多層引用、取消計畫、口誤修正與偽指令。</p><div class="filters interactive"><label>難度<select data-filter="difficulty"><option value="hard">HARD</option><option value="simple">SIMPLE</option><option value="">全部</option></select></label><label>任務<select data-filter="task"><option value="facts">耐久事實抽取</option><option value="summary">一般摘要＋累積印象</option><option value="">全部</option></select></label><label>配置<select data-filter="arm"><option value="">全部配置</option>${data.manifest.arms.map(a=>`<option value="${a.id}">${esc(a.label)}</option>`).join('')}</select></label><label>重複<select data-filter="repeat"><option value="1">第 1 次</option><option value="2">第 2 次</option><option value="">兩次都看</option></select></label><label>搜尋<input type="search" data-filter="search" placeholder="例如：前室友、250天"></label><label class="check"><input type="checkbox" data-filter="failed">只看未合格</label></div><p data-visible class="status" aria-live="polite">32 題 · 512 份輸出</p>${data.cases.map(c=>caseMarkup(data,c)).join('')}</section><section class="panel method"><h2>AI 評審怎麼判？</h2><p class="notice">${esc(data.judge.protocolRevision)} 本次所有成績統一使用事先固定的完整盲評。</p><p><code>gpt-6-astra · medium</code>。每次收到原話、事先寫好的語義目標與四份匿名輸出；看不到模型名稱、thinking、延遲或費用。四個匿名標籤固定隨機分配，分別判讀，不要求選勝者。</p><p>逐項檢查時間、人物歸屬、否定、來源與明確更正。重大錯誤必須引用實際輸出，以及對應原話編號與原句；引用不存在、少了標籤或目標時會判成無效，最多重新判讀一次。摘要若被驗證器清空而保留舊側寫，就評實際保留的側寫。空事實不會被判捏造，但沒有覆蓋分，不能合格。</p><p><b>分數：</b>${esc(data.method.scoreRule)} <b>合格：</b>${esc(data.method.qualityRule)}</p><div class="scroll"><table><thead><tr><th>控制題</th><th>已知正確</th><th>過去當現在</th><th>錯置人物</th><th>空答案</th></tr></thead><tbody>${data.judge.calibration.map(c=>`<tr><th scope="row">${esc(c.id.replace('calibration:',''))}</th><td>正確辨識</td><td>抓到錯誤</td><td>抓到錯誤</td><td>安全但零覆蓋</td></tr>`).join('')}</tbody></table></div><p>預先選定題族 1、2、12 的兩種難度、兩任務、兩次重複，反轉四份答案順序重新判讀：合格一致 ${fmt(data.judge.passAgreement*100)}%，${data.judge.mirrorDecisions} 份；品質分平均絕對差 ${fmt(data.judge.scoreMeanAbsoluteDifference,2)}。主成績固定取原始盲評；差異保留在案例與下載資料。</p><p class="notice warning">AI 評審通過控制題仍可能誤判。這份題集是作者設計的開發評估，不是未見過的正式留出測試，也不代表真實使用者偏好或多日記憶效果。</p><details><summary>完整 AI 評審規則</summary><pre>${esc(data.judge.rubric)}</pre></details></section><section class="panel method"><h2>可重查的測量紀錄</h2><p>固定日期 ${esc(data.cases[0].date)} · 隨機種子 ${data.manifest.seed} · 非串流 Chat Completions · 候選併發 ${data.manifest.concurrency} · <code>store:false</code>。同題各組使用同一份 prompt。${esc(data.method.judgeScheduling)}HTTP 暫時錯誤最多 3 次，格式或語義失敗不重抽；無跨模型 fallback。</p><p>成本按 2026-10-14 標準牌價估算，含 API 回報的快取讀取、1.25× 輸入價的快取寫入與輸出中的推理 tokens；不是帳單。未回報用量的失敗呼叫 ${data.method.unknownUsageCalls} 次。</p><p>來源程式版本：<code>${esc(data.manifest.sourceCommit)}</code>；原始 prompt、解析器、題集、runner 與 judge 的 SHA-256，均保留於下載的 manifest。原始後端 prompt 不隨公開報告發佈。</p><div class="download"><a href="memory-models-results.public.json?v=${version}" download>下載完整合成輸入、512 次輸出與 AI 判讀（JSON）</a><a href="memory-models-summary.csv?v=${version}" download>下載主研究品質與延遲彙總（CSV）</a></div><p class="small">價格與支援參數：${data.method.pricingLinks.map(url=>`<a href="${esc(url)}">${esc(url.split('/').pop())}</a>`).join(' · ')}。</p><ul>${data.method.limitations.map(t=>`<li>${esc(t)}</li>`).join('')}</ul></section><noscript><p class="notice">JavaScript 未開啟：保留靜態成績、所有案例和下載資料；篩選與互動圖表需要 JavaScript。</p></noscript><footer>Machi 記憶模型配對實測 · 品質、延遲、失敗和評審不一致均保留。記憶上限與分類prompt已更新；模型配置仍維持正式基準。</footer></main></body></html>`;
}

export function publish(input,outputDirectory){
  const data=validateData(JSON.parse(fs.readFileSync(input,'utf8')));
  const html=render(data);
  fs.mkdirSync(outputDirectory,{recursive:true});
  fs.writeFileSync(path.join(outputDirectory,'memory-models.html'),html);
  fs.writeFileSync(path.join(outputDirectory,'memory-models-results.public.json'),JSON.stringify(data,null,2)+'\n');
  const columns=['difficulty','task','armId','n','passes','passPercent','scoreMean','coveragePercent','unsafeOutputs','materialErrors','apiFailures','formatFailures','latencyP50','latencyP95','over40Seconds','inputTokens','cachedTokens','cacheWriteTokens','outputTokens','reasoningTokens','costUsd'];
  fs.writeFileSync(path.join(outputDirectory,'memory-models-summary.csv'),columns.join(',')+'\n'+data.aggregates.map(a=>columns.map(k=>a[k]).join(',')).join('\n')+'\n');
  console.log(`Published complete memory comparison: ${data.records.length} generations, ${data.judge.packetCount} blinded judge packets.`);
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  if(!process.argv[2])throw new Error('Usage: node scripts/render-memory-models.mjs results.json [output-directory]');
  publish(process.argv[2],path.resolve(process.argv[3]||'public/line-v3'));
}
