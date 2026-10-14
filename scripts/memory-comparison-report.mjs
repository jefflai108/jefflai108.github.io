const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const pct=(count,n)=>n?100*count/n:0;
const fmt=n=>Number(n).toFixed(1);
const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const aggregate=(data,arm,task)=>data.aggregates.find(a=>a.armId===arm&&a.task===task&&a.difficulty==='all');
const updates=(data,arm)=>data.records.filter(r=>r.armId===arm&&r.task==='facts'&&r.profileConstruction.updateChecks.some(u=>u.action!=='keep')).map(r=>({passed:r.profileConstruction.updateChecks.every(u=>u.passed)}));
const stages=data=>data.records.flatMap(r=>r.task==='facts'&&r.extractionReceipt?[r.extractionReceipt,r.reconciliation].filter(s=>s?.apiOk):[r]).filter(s=>s.apiOk);
export function buildComparison(before,after){
  if(before.version!=='memory-models-quality-v4'||after.version!=='memory-models-quality-v6-mem0')throw new Error('Comparison study versions mismatch');
  if(before.manifest.casesHash!==after.manifest.casesHash||!same(before.cases,after.cases)||!same(before.manifest.arms,after.manifest.arms))throw new Error('Comparison corpus or model controls changed');
  const rows=after.manifest.arms.map(arm=>{
    const row={armId:arm.id,label:arm.label};
    for(const task of ['facts','summary']){
      const a=aggregate(before,arm.id,task),b=aggregate(after,arm.id,task);
      if(a?.n!==100||b?.n!==100)throw new Error('Comparison denominators mismatch');
      row[task]={before:{errors:a.unsafeOutputs,n:a.n,errorPercent:pct(a.unsafeOutputs,a.n),passes:a.passes,newCoveragePercent:a.newCoveragePercent},after:{errors:b.unsafeOutputs,n:b.n,errorPercent:pct(b.unsafeOutputs,b.n),passes:b.passes,newCoveragePercent:b.newCoveragePercent}};
    }
    const a=updates(before,arm.id),b=updates(after,arm.id);
    if(a.length!==38||b.length!==38)throw new Error('Comparison update denominator mismatch');
    row.updates={before:{passed:a.filter(u=>u.passed).length,n:a.length},after:{passed:b.filter(u=>u.passed).length,n:b.length}};
    return row;
  });
  const calls=stages(after);
  const tokenEvidence={perCallCap:16384,candidateCalls:calls.length,tokenLimitHits:calls.filter(c=>c.finishReason==='length').length,maxCompletionTokens:Math.max(...calls.map(c=>c.usage?.completion_tokens||0)),factsMaxAllowedAcrossTwoCalls:32768};
  return {version:'memory-before-after-v4-v6',beforeSource:before.manifest.sourceCommit,afterSource:after.manifest.sourceCommit,casesHash:after.manifest.casesHash,rows,tokenEvidence};
}
export function comparisonMarkup(comparison){
  if(!comparison)return '';
  return `<section class="panel" id="memory-before-after" data-memory-comparison><h2>相同100題：改版前 → 新記憶系統</h2><p>四種模型／thinking配置與題集相同。幻覺／錯置率：至少一項重大來源、人物、時間或無根據錯誤的輸出數，除以該配置、任務的100次計畫輸出；API／管線失敗另列。耐久檔案包含仍有效的舊錯誤，逐題會區分新增寫入與保留舊資料。</p><div class="scroll"><table><thead><tr><th>配置</th><th>耐久檔案錯誤率</th><th>一般摘要錯誤率</th><th>耐久品質合格</th><th>必要更新成功</th></tr></thead><tbody>${comparison.rows.map(r=>`<tr data-comparison-arm="${esc(r.armId)}"><th>${esc(r.label)}</th>${['facts','summary'].map(task=>`<td><b>${fmt(r[task].before.errorPercent)}% → ${fmt(r[task].after.errorPercent)}%</b><small>${r[task].before.errors}/${r[task].before.n} → ${r[task].after.errors}/${r[task].after.n}</small></td>`).join('')}<td>${r.facts.before.passes}/100 → ${r.facts.after.passes}/100</td><td>${r.updates.before.passed}/${r.updates.before.n} → ${r.updates.after.passed}/${r.updates.after.n}</td></tr>`).join('')}</tbody></table></div><p class="small">這是已檢視的合成回歸題集。新耐久管線多了操作管理階段，每階段最多16,384，兩階段合計最多32,768；不能把改善全歸因於模型。一般摘要沒有使用這個更新器，兩次獨立生成／評審的波動不能歸因於更新器。兩次研究的新保存耐久事實均沒有判定出的重大錯誤；下降的是保留在有效檔案裡的舊錯誤。</p><h3>16,384是否足夠？</h3><p>${comparison.tokenEvidence.candidateCalls.toLocaleString('en-US')}次候選API呼叫，token上限截斷 ${comparison.tokenEvidence.tokenLimitHits} 次；單次最高使用 ${comparison.tokenEvidence.maxCompletionTokens.toLocaleString('en-US')} completion tokens（含推理）。本次仍有漏記與管線失敗，不能把沒碰上限解讀為全部合格。</p><p><a href="memory-models-v4.html">查看改版前完整研究與三版high prompt</a> · <a href="memory-models-comparison.public.json" download>下載同題比較與token統計</a></p></section>`;
}
