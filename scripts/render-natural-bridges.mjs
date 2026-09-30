import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {latencyNames, summarize} from './natural-bridges-metrics.mjs';

const [resultFile, qualityFile] = process.argv.slice(2);
if (!resultFile || !qualityFile) throw new Error('Usage: node scripts/render-natural-bridges.mjs RESULTS QUALITY');
const resultBytes = fs.readFileSync(resultFile);
const study = JSON.parse(resultBytes);
const rawQuality = JSON.parse(fs.readFileSync(qualityFile, 'utf8'));
const hash = bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
if(rawQuality.source_ref!==study.metadata.source_ref || rawQuality.results_sha256!==hash(resultBytes))throw new Error('Quality report belongs to a different study');
if(!Number.isInteger(study.metadata.repeats)||study.metadata.repeats<1||!study.metadata.accounts.length
  ||new Set(study.metadata.accounts).size!==study.metadata.accounts.length
  ||study.metadata.accounts.some(a=>!['primary','secondary'].includes(a))
  ||new Set(study.cases.map(c=>c.id)).size!==study.cases.length
  ||study.cases.some(c=>!/^NB\d{3}$/.test(c.id)||!c.turns.length))throw new Error('Invalid study identities');
const expectedPairs=new Set(study.cases.flatMap(c=>study.metadata.accounts.flatMap(account=>
  Array.from({length:study.metadata.repeats},(_,i)=>c.turns.map((_,turn)=>`${c.id}.${account}.r${i+1}.t${turn}`)).flat())));
const expectedSlots=new Set(study.cases.flatMap(c=>study.metadata.accounts.flatMap(account=>
  Array.from({length:study.metadata.repeats},(_,i)=>['baseline','natural'].map(arm=>`${c.id}.${account}.${arm}.r${i+1}`)).flat())));
const seenSlots=new Set();
for(const receipt of study.receipts){
  const slot=`${receipt.case_id}.${receipt.account}.${receipt.arm}.r${receipt.repeat}`;
  if(!expectedSlots.has(slot)||seenSlots.has(slot))throw new Error('Unknown or duplicate study receipt');
  seenSlots.add(slot);
  const seenTurns=new Set();
  for(const turn of receipt.turns??[]){
    const id=`${receipt.case_id}.${receipt.account}.r${receipt.repeat}.t${turn.turn_index}`;
    if(!expectedPairs.has(id)||seenTurns.has(id))throw new Error('Unknown or duplicate study turn');
    seenTurns.add(id);
  }
}
const seenQuality=new Set();
for(const q of rawQuality.results){
  if(!expectedPairs.has(q.id)||seenQuality.has(q.id))throw new Error('Unknown or duplicate quality pair');
  seenQuality.add(q.id);
}
const projectScores = (scores,dimensions)=>Object.fromEntries(dimensions.map(d=>{
  const n=scores[d];if(n!==null&&(!Number.isInteger(n)||n<1||n>5))throw new Error('Invalid public score');return[d,n];
}));
const quality={model:rawQuality.model,method:rawQuality.method,source_ref:rawQuality.source_ref,
  results_sha256:rawQuality.results_sha256,plan_sha256:rawQuality.plan_sha256,quality_samples_sha256:rawQuality.quality_samples_sha256,
  judge_sha256:rawQuality.judge_sha256,
  bridge_dimensions:rawQuality.bridge_dimensions,final_dimensions:rawQuality.final_dimensions,
  results:rawQuality.results.map(q=>({id:q.id,status:q.status,bridge_winner:q.bridge_winner,error_type:q.error_type,
    ...(q.status==='ok'?{arms:Object.fromEntries(['baseline','natural'].map(a=>[a,{
      bridge:projectScores(q.arms[a].bridge,rawQuality.bridge_dimensions),
      final:projectScores(q.arms[a].final,rawQuality.final_dimensions),reason:q.arms[a].reason}]))}:{})}))};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const publicTurn = t => ({turn_index:t.turn_index,user_text:t.user_text,status:t.status,drain_requested:t.drain_requested,
  host_condition:t.host_condition,metrics:t.metrics,all_attempt_latency_ms:t.all_attempt_latency_ms,
  phase:t.foreground_ledger?.response_phase ? {role:t.foreground_ledger.response_phase.role,
    outcome:t.foreground_ledger.response_phase.outcome,awaiting_result:t.foreground_ledger.response_phase.awaiting_result} : null,
  messages:t.messages.map(m=>({role:m.semantic_role,texts:m.texts,elapsed_ms:m.elapsed_ms,transport:m.kind})),
  route:t.interaction?.map(x=>x.action),routing_calls:t.metrics.routing_calls});
const data = {schema_version:1,source_ref:study.metadata.source_ref,models:study.metadata.models,
  generated_at:new Date().toISOString(),accounts:study.metadata.accounts,repeats:study.metadata.repeats,
  case_count:study.cases.length,transport:study.metadata.transport,scheduling:study.metadata.scheduling,
  shared_changes:study.metadata.shared_changes,baseline_instrumentation:study.metadata.baseline_instrumentation,
  host_tool_budget:study.metadata.host_tool_budget??null,
  limits:study.metadata.limits,cases:study.cases.map(c=>({id:c.id,category:c.category,rubric:c.rubric,
    turns:c.turns.map(t=>({text:t.text,drain_requested:t.drain??true}))})),
  receipts:study.receipts.map(r=>({case_id:r.case_id,account:r.account,arm:r.arm,repeat:r.repeat,status:r.status,
    checks:r.checks,error_type:r.error_type,turns:(r.turns??[]).map(publicTurn)})),quality};
const allObserved=(caseId,index,check)=>{
  const receipts=study.receipts.filter(r=>r.case_id===caseId);
  return receipts.length===study.metadata.accounts.length*2*study.metadata.repeats
    &&receipts.every(r=>r.turns?.some(t=>t.turn_index===index&&check(t)));
};
data.observed_limitations=[];
if(allObserved('NB006',1,t=>t.interaction?.some(x=>x.error_code==='task_control_not_requested')
  &&t.messages?.some(m=>m.semantic_role==='direct_answer'&&m.texts?.length)
  &&t.foreground_ledger?.response_phase?.outcome!=='revised')){
  const priorResults=allObserved('NB006',1,t=>t.messages?.some(m=>m.semantic_role==='other_task_or_revision'&&m.texts?.length));
  data.observed_limitations.push('NB006 的修改回合皆出現 task_control_not_requested，並交付直接回覆；未觀測到 revised 狀態。'
    +(priorResults?'各回合另有交付，標為另一個任務／版本的結果，不計為本次修訂完成。':''));
}
if(allObserved('NB007',1,t=>t.interaction?.some(x=>x.status==='failed'&&x.degraded)))
  data.observed_limitations.push('NB007 的狀態詢問全部出現降級回覆，未成功走過預期的狀態查詢路由。');
if(allObserved('NB008',1,t=>t.foreground_ledger?.response_phase?.outcome==='accepted'
  &&t.interaction?.some(x=>x.action==='delegate')))
  data.observed_limitations.push('NB008 的第二回合均以新委派 accepted 承接，沒有觀測到 resubmitted 分支。');
if(allObserved('NB009',0,t=>t.interaction?.some(x=>x.action==='direct')
  &&Array.isArray(t.capability_events)&&t.capability_events.length===0))
  data.observed_limitations.push('NB009 的危機查詢均直接回覆，沒有工具呼叫，不計為危機情境的背景查詢覆蓋。');
const observedNotes=data.observed_limitations.length?`<div class="note"><p>題目分類記錄測試意圖，不代表成功走過同名分支。本次實際觀測：</p><ul>${data.observed_limitations.map(note=>`<li>${esc(note)}</li>`).join('')}</ul></div>`:'';
const arms=['baseline','natural'];
const toolBudgetText=data.host_tool_budget==='Both arms share a benchmark-only cap of 12 admitted host tool calls per task attempt; production has no such benchmark cap.'
  ?'兩個版本共用基準測試的宿主工具呼叫上限：每次任務嘗試最多接納 12 次呼叫。這個上限只用於基準測試，正式環境沒有這項限制。'
  :data.host_tool_budget??'本次來源未記錄宿主工具呼叫上限。';
const names={baseline:'Hermes + Gemini',natural:'Hermes + Gemini · Natural bridges'};
const metricNames={relevance:'情境關聯',naturalness:'自然度',status_fidelity:'狀態忠實',care_and_tone:'關懷與語氣',
  taiwan_usage:'台灣用語',task_completion:'任務完成',grounding:'依據',usefulness:'實用性',clarity:'清晰度',
  character:'麻吉個性',instruction_following:'遵循指示'};
const seconds = n=>typeof n==='number'&&Number.isFinite(n)?`${(n/1000).toFixed(2)} s`:'—';
const deltaSeconds = n=>typeof n==='number'&&Number.isFinite(n)?`${n>0?'+':''}${seconds(n)}`:'—';
const qRows=group=>quality[group+'_dimensions'].map(d=>`<tr><th scope="row">${metricNames[d]??esc(d)}</th>${arms.map(a=>{
  const v=quality.results.filter(q=>q.status==='ok').map(q=>q.arms[a]?.[group]?.[d]).filter(x=>typeof x==='number');
  return `<td>${v.length?(v.reduce((s,x)=>s+x,0)/v.length).toFixed(2):'—'} / 5 <small>n=${v.length}</small></td>`;
}).join('')}</tr>`).join('');
const paired=new Map();
for(const c of study.cases)for(const account of study.metadata.accounts)for(let repeat=1;repeat<=study.metadata.repeats;repeat++)
  c.turns.forEach((t,turn_index)=>{
    const id=`${c.id}.${account}.r${repeat}.t${turn_index}`;
    paired.set(id,{id,case_id:c.id,account,repeat,turn_index,user_text:t.text});
  });
for(const receipt of data.receipts)for(const turn of receipt.turns){
  const id=`${receipt.case_id}.${receipt.account}.r${receipt.repeat}.t${turn.turn_index}`;
  paired.get(id)[receipt.arm]=turn;
}
data.statistics=summarize(data,paired);
const latencyRows=Object.entries(latencyNames).map(([kind,title])=>`<tr><th scope="row">${title}</th>${arms.map(a=>{
  const s=data.statistics.latency[a][kind];return `<td>${s.n} / ${s.planned_turns}</td><td>${seconds(s.median)}</td><td>${seconds(s.p95)}</td>`;
}).join('')}</tr>`).join('');
const deltaRows=Object.entries(data.statistics.paired_delta_ms).map(([kind,s])=>`<tr><th scope="row">${latencyNames[kind]}</th>
  <td>${s.n} / ${s.observed_either}</td><td>${deltaSeconds(s.median)}</td><td>${deltaSeconds(s.p95)}</td></tr>`).join('');
const diversity=data.statistics.bridge_diversity;
const diversityHtml=arms.some(a=>diversity[a].n)?`<details><summary>實際承接文字的完全相同率與差異</summary>
  <div class="scroll"><table><thead><tr><th>版本</th><th>承接交付 n</th><th>不重複的原始文字組</th></tr></thead><tbody>${arms.map(a=>
  `<tr><th scope="row">${names[a]}</th><td>${diversity[a].n}</td><td>${diversity[a].distinct_exact} / ${diversity[a].n}</td></tr>`).join('')}</tbody></table></div>
  <p class="small">只計宿主確認的 bridge 交付，逐字保留空白、表情與訊息分段；未採用的生成候選、狀態通知及最終答案不計入。這是文字多樣性的描述，受主題與路由分布影響，不是品質分數。</p></details>`:'';
const qualityMap=new Map(quality.results.map(q=>[q.id,q]));
const categoryMap=new Map(data.cases.map(c=>[c.id,c.category]));
const roles={bridge:'Bridge · 等待結果',terminal_notice:'Status notice · 本次沒有新結果等待',final:'Final · 背景工作成果',
  direct_answer:'Direct answer · 直接回答',other_task_or_revision:'另一個任務／版本的結果',task_notice:'Task notice',
  unconfirmed_task_delivery:'未確認的工作交付',unconfirmed_foreground:'未確認的前景訊息'};
function armHtml(row,arm){
  const t=row[arm],q=qualityMap.get(row.id)?.arms?.[arm];
  if(!t)return `<section class="arm"><h3>${names[arm]}</h3><p>這一側沒有可用的回合紀錄；保留為缺失，不推定成功。</p></section>`;
  return `<section class="arm"><h3>${names[arm]}</h3><p class="small">路由 ${esc(t.route?.join(', ')??'未記錄')} · ${esc(t.status)} · LLM ${seconds(t.metrics.frontend_latency_ms)}</p>
  <p class="small">Bridge ${seconds(t.metrics.bridge_captured_latency_ms)} · Final ${seconds(t.metrics.final_captured_latency_ms)} · 背景執行起點 ${seconds(t.metrics.executor_start_ms)} · 路由推論 ${t.routing_calls} 次</p>
  ${t.phase?`<p class="badge">${esc(t.phase.outcome)} · ${t.phase.awaiting_result?'承接時綁定待回覆任務':'本次沒有新的工作結果等待'}</p>`:''}
  ${t.drain_requested===false?'<p class="note small">本回合刻意不推進背景執行，用來觀察承接或控制狀態；未測量背景最終成果。</p>':''}
  ${t.host_condition?.requested?`<p class="note small">注入宿主條件：${esc(t.host_condition.condition)}；實際觸發 ${esc(t.host_condition.applied)}</p>`:''}
  ${t.messages.filter(m=>m.texts?.length).map(m=>`<div class="bubble ${m.role==='bridge'?'bridge':''}"><h4>${esc(roles[m.role]??m.role)} <small>${seconds(m.elapsed_ms)}</small></h4><p>${esc(m.texts.join('\n\n'))}</p></div>`).join('')||'<p>沒有捕捉到文字交付。</p>'}
  ${q?`<details><summary>盲評分數與理由</summary><p>${esc(q.reason)}</p><dl>${['bridge','final'].map(group=>
    Object.entries(q[group]).map(([key,value])=>`<dt>${group==='bridge'?'承接':'成果'} · ${metricNames[key]??esc(key)}</dt><dd>${value??'未評'}</dd>`).join('')).join('')}</dl></details>`:''}</section>`;
}
const cards=[...paired.values()].map(row=>`<article class="case" data-account="${row.account}" data-category="${esc(categoryMap.get(row.case_id))}" data-search="${esc(row.case_id+' '+row.user_text)}">
  <p class="eyebrow">${row.case_id} · ${row.account} · repeat ${row.repeat} · turn ${row.turn_index+1} · ${esc(categoryMap.get(row.case_id))}</p>
  <h2>${esc(row.user_text)}</h2><div class="arms">${arms.map(a=>armHtml(row,a)).join('')}</div></article>`).join('');
const successful=quality.results.filter(q=>q.status==='ok');
const wins=Object.fromEntries(['baseline','natural','tie','not_applicable'].map(a=>[a,successful.filter(q=>q.bridge_winner===a).length]));
const errors=data.receipts.filter(r=>r.status!=='measured');
const html=`<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>HeyMachi · Natural bridges</title><link rel="canonical" href="https://jefflai108.github.io/line-v3/natural-bridges.html"><style>
*{box-sizing:border-box}body{margin:0;background:#f3f3ee;color:#193a31;font:15px/1.65 system-ui,-apple-system,'PingFang TC',sans-serif}header,main,.navwrap{max-width:1450px;margin:auto;padding:24px 28px}h1{font-size:clamp(32px,5vw,52px);line-height:1.15;margin:15px 0}h2{font-size:22px;line-height:1.4}h3{font-size:18px}h4{font-size:13px;margin:0 0 7px}a{color:#23695d}a:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid #269890;outline-offset:3px}.eyebrow,.small,small{font-size:12px;color:#526c61}.panel,.case{border:1px solid #d6e0d7;border-radius:15px;background:white;padding:24px;margin-bottom:22px}.arms{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.arm{min-width:0;border-top:4px solid #56796a;background:#f6f8f4;padding:18px;border-radius:7px}.arm:last-child{border-color:#378e80}.bubble{background:white;border:1px solid #dce5de;border-radius:9px;padding:14px;margin:14px 0}.bubble p{white-space:pre-wrap;overflow-wrap:anywhere;margin:0}.bridge{background:#eaf5f0}.badge{display:inline-block;font-size:12px;background:#dcece4;border-radius:8px;padding:4px 8px}.note{padding:12px;background:#f8f0db;border-radius:8px}.tabs{display:flex;gap:5px;flex-wrap:wrap;background:#e3e9e2;padding:6px;border-radius:10px}.tabs a{padding:8px 12px;text-decoration:none;border-radius:7px;font-size:13px}.tabs [aria-current]{background:white;font-weight:700}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:10px;border-bottom:1px solid #e1e8e1;white-space:nowrap}td small{display:block}.flow{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.flow span{padding:10px 14px;border:1px solid #b9d4c7;border-radius:8px;background:#f0f7f1}.controls{display:flex;gap:14px;flex-wrap:wrap;align-items:end}label{font-size:13px;display:flex;flex-direction:column;gap:6px}input,select{font:inherit;padding:9px;border:1px solid #b8cbbc;border-radius:7px;background:white;max-width:100%}details{font-size:13px;margin:16px 0}summary{cursor:pointer}dl{display:grid;grid-template-columns:1fr auto;gap:5px}dd{margin:0}.case[hidden]{display:none}.skip{position:absolute;left:-10000px}.skip:focus{left:16px;top:5px;background:white;padding:10px}footer{padding:22px 0;font-size:12px;overflow-wrap:anywhere}@media(max-width:760px){header,main,.navwrap{padding:16px}.arms{grid-template-columns:1fr}.panel,.case{padding:16px}.tabs a{padding:7px}.flow{font-size:13px}}
</style></head><body><a class="skip" href="#content">跳到比較結果</a><header><p class="eyebrow">HeyMachi · LINE v3 · matched development benchmark</p><h1>Natural bridges</h1><p>同一個 Hermes + Gemini 執行後端，對照固定承接與自然承接。承接訊息與真正的最終成果分開呈現、分開計時。</p></header><div class="navwrap"><nav class="tabs" aria-label="比較分頁"><a href="index.html">Interaction tasks</a><a href="delegation.html">Delegation tasks</a><a href="taiwan.html">台灣用語</a><a href="recovery.html">困難任務與失敗恢復</a><a href="tts-followup.html">TTS follow-up</a><a href="burst-turns.html">Burst turns</a><a href="natural-bridges.html" aria-current="page">Natural bridges</a></nav></div><main id="content">
<section class="panel"><h2>Bridge ≠ Final answer</h2><div class="flow"><span>使用者要求</span>→<span>同次推論：路由＋承接文字</span>→<span>宿主確認狀態</span>→<span>Bridge</span>→<span>背景執行</span>→<span>Final Push</span></div><p>兩個 LINE 帳號共用同一份 v3 實作。Bridge 有宿主指定的任務與版本綁定；Reply／Push 傳送完成只結束前景交付，不能完成背景工作。修改被保留、拒絕或取消時，狀態通知不會冒充成果，也不會承諾不存在的後續答案。</p><p class="small">自然承接與路由同次生成，沒有額外的 bridge LLM 呼叫。這些委派訊息不使用 follow-up TTS。</p></section>
<section class="panel"><h2>Latency</h2><p>交付與背景執行起點，從合成 LINE 事件進入原生處理流程開始計時；前景模型列則是該回合路由呼叫的耗時合計。包含真實模型與工具等待；<strong>不包含實際 LINE API、手機網路或通知延遲</strong>。背景工作在前景回合後由測試程式依序推進，不是生產並行排程測量。</p>
<div class="scroll"><table><thead><tr><th rowspan="2">階段</th><th colspan="3">固定承接</th><th colspan="3">自然承接</th></tr><tr><th>n / 計畫回合</th><th>p50</th><th>p95</th><th>n / 計畫回合</th><th>p50</th><th>p95</th></tr></thead><tbody>${latencyRows}</tbody></table></div>
<p class="small">n 是有觀測到該階段的回合數；分母包含直接回答及刻意不執行背景工作的控制回合，不代表完成率，各階段不可相加。p95 使用 nearest rank，小樣本僅供描述；直接回覆與控制回合不混入委派最終結果。${data.case_count} 個情境 × ${data.accounts.length} 帳號 × 2 版本 × ${data.repeats} 次；測試槽 ${data.receipts.length} / ${expectedSlots.size}，已記錄槽錯誤 ${errors.length}。</p>
<h3>相同回合的延遲差：自然承接 − 固定承接</h3><div class="scroll"><table><thead><tr><th>階段</th><th>可比較配對 / 任一側有觀測</th><th>配對差 p50</th><th>配對差 p95</th></tr></thead><tbody>${deltaRows}</tbody></table></div>
<p class="small">共計畫 ${paired.size} 個配對回合。只比較同情境、帳號、重複次數及回合，且兩側都觀測到同一語意階段的配對；沒有配對觀測就不推算差值。負值表示自然承接較快，正值表示較慢。此表是配對差的分布，不是兩側 p50 或 p95 相減。</p></section>
<section class="panel"><h2>Bridge quality</h2><p>隨機 A/B 標籤，${esc(quality.model)} 評分；${successful.length} / ${quality.results.length} 組評審紀錄有效，計畫共有 ${paired.size} 個配對回合。只看實際送出的訊息與所附宿主／工具證據。這是 AI 盲評與開發用題組，沒有獨立真人評審或未見測試集。</p><div class="scroll"><table><thead><tr><th>指標</th><th>固定承接</th><th>自然承接</th></tr></thead><tbody>${qRows('bridge')}</tbody></table></div><p class="small">自然承接勝 ${wins.natural} · 固定承接勝 ${wins.baseline} · 平手 ${wins.tie} · 不適用 ${wins.not_applicable}。沒有承接的回合不計承接平均。</p>${diversityHtml}<details><summary>最終文字的既有七項品質指標</summary><div class="scroll"><table><thead><tr><th>指標</th><th>固定承接</th><th>自然承接</th></tr></thead><tbody>${qRows('final')}</tbody></table></div></details></section>
<section class="panel"><h2>測試範圍與版本</h2><p>前景 ${esc(data.models.foreground)}（${esc(data.models.foreground_thinking)}）；Hermes 執行後端 ${esc(data.models.executor)}（${esc(data.models.executor_reasoning)}）。兩側使用相同來源快照，只切換自然承接 prompt／呈現；語意階段的觀测與執行腦的歷史角色規則共用。</p><p>${esc(toolBudgetText)}</p><p>包含查詢、讀取連結、提醒、修改、取消、狀態、危機與缺附件。額外的 admission／held／unresolved 情境會明示注入條件及是否觸發，不能拿來估計生產失敗率。保留模型實際路由、缺失與錯誤，不把等待訊息補成成果。</p>${observedNotes}<p class="small">Source <code>${esc(data.source_ref)}</code> · <a href="natural-bridges-results.public.json" download>下載合成結果 JSON</a></p></section>
<section class="panel controls"><label>搜尋<input id="search" type="search" placeholder="情境 ID 或問題"></label><label>LINE 帳號<select id="account"><option value="">兩個帳號</option><option value="primary">Primary</option><option value="secondary">Secondary</option></select></label><label>情境<select id="category"><option value="">全部</option>${[...new Set(data.cases.map(c=>c.category))].map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('')}</select></label><span id="count" role="status" aria-live="polite"></span></section>${cards}
<footer>所有問題與對話均為合成測試資料。此頁是基準測試，不代表功能已部署到正式 LINE。發布時間 ${esc(data.generated_at)}。</footer></main><script>
const controls=['search','account','category'].map(id=>document.getElementById(id));const cases=[...document.querySelectorAll('.case')];function filter(){const[q,a,c]=controls.map(e=>e.value.toLowerCase());let n=0;for(const row of cases){row.hidden=!!((q&&!row.dataset.search.toLowerCase().includes(q))||(a&&row.dataset.account!==a)||(c&&row.dataset.category!==c));if(!row.hidden)n++;}document.getElementById('count').textContent=n+' / '+cases.length+' 個配對回合';}controls.forEach(e=>e.addEventListener('input',filter));filter();
</script></body></html>`;
const destination=path.resolve('public/line-v3');
// Measured copy is never rewritten to conceal a leak. Refuse publication.
function scanPublic(value){
  if(typeof value==='string'){
    if(/file:\/\/[^\s<>"']+|(?<![A-Za-z0-9:/])(?:\/(?:Users|home|root|tmp|private|var|opt|etc|Volumes)\/|~\/|[A-Za-z]:[\\/])[^\s<>"']+/.test(value))throw new Error('Local path in public data');
    if(/(?:file:\/\/|data:(?:image|audio|application)\/|localhost|127\.0\.0\.1|-----BEGIN [A-Z ]*PRIVATE KEY|\bsk-[A-Za-z0-9_-]{20,}|\bgh[opusr]_[A-Za-z0-9_]{20,}|\bAIza[A-Za-z0-9_-]{20,})/i.test(value))throw new Error('Unsafe private material in public data');
    for(const match of value.matchAll(/https?:\/\/[^\s<>"')\]]+/g)){
      let url;try{url=new URL(match[0]);}catch{throw new Error('Invalid URL in measured public copy');}
      if(url.username||url.password||/^(?:10\.|127\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)/.test(url.hostname)
        ||/\.(?:local|internal)$/.test(url.hostname)||/\/(?:line\/media|followup-audio)\//.test(url.pathname)
        ||[...url.searchParams.keys()].some(k=>/^(?:token|key|api_key|access_token|secret|signature)$/i.test(k)))throw new Error('Private or credential URL in measured public copy');
    }
  }else if(Array.isArray(value))value.forEach(scanPublic);
  else if(value&&typeof value==='object')Object.values(value).forEach(scanPublic);
}
scanPublic(data);
const checker=fileURLToPath(new URL('./check-natural-bridges-publication.py',import.meta.url));
const checked=spawnSync(process.env.NATURAL_BRIDGES_PYTHON??'python3',[
  '-I','-B',checker,'--results',path.resolve(resultFile),'--quality',path.resolve(qualityFile)],{
  input:JSON.stringify(data),encoding:'utf8',timeout:30000,maxBuffer:1024*1024,
  env:{PATH:process.env.PATH??'',LANG:'C.UTF-8'},
});
if(checked.error||checked.status!==0)throw new Error(`Publication check failed: ${checked.error?.code??checked.stderr.trim()}`);
const publicationCheck=JSON.parse(checked.stdout);
if(publicationCheck.status!=='passed')throw new Error('Publication check did not confirm safe copy');
fs.writeFileSync(path.join(destination,'natural-bridges-results.public.json'),JSON.stringify(data,null,2)+'\n');
fs.writeFileSync(path.join(destination,'natural-bridges.html'),html);
for(const filename of ['index.html','delegation.html','taiwan.html','recovery.html','tts-followup.html','burst-turns.html']){
  const target=path.join(destination,filename);let text=fs.readFileSync(target,'utf8');
  if(!text.includes('href="natural-bridges.html"'))text=text.replace(/(<nav class="tabs"[^>]*>.*?)(<\/nav>)/s,'$1<a href="natural-bridges.html">Natural bridges</a>$2');
  fs.writeFileSync(target,text);
}
console.log(JSON.stringify({cases:data.case_count,slots:data.receipts.length,paired_turns:paired.size,quality:successful.length}));
