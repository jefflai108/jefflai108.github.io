import {errorOriginCounts} from './memory-quality-origin.js';
(() => {
  const root=document.querySelector('[data-memory-report][data-view]');
  if(!root)return;
  const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=(n,d=1)=>Number(n).toFixed(d);
  const colors=['#687b72','#27897b','#c08735','#7565a5'];
  const labels={past_as_current:'過去當現在',wrong_person:'人物／關係錯置',negation:'否定反轉',unsupported:'無來源的新增事實',source_instruction:'資料偽指令',correction:'錯誤更正',uncertainty:'未知變確定'};
  const controls=Object.fromEntries([...root.querySelectorAll('[data-metric]')].map(c=>[c.dataset.metric,c]));
  const explorer=root.querySelector('[data-explorer]');
  function filter(){
    const fields=Object.fromEntries([...explorer.querySelectorAll('[data-filter]')].map(c=>[c.dataset.filter,c.value]));
    const query=fields.search.trim().toLowerCase();let cases=0,answers=0;
    explorer.querySelectorAll('[data-case]').forEach(item=>{
      const matches=(!fields.difficulty||fields.difficulty===item.dataset.difficulty)&&(!fields.split||fields.split===item.dataset.split)&&(!query||item.textContent.toLowerCase().includes(query));
      let visible=0;
      item.querySelectorAll('[data-answer]').forEach(a=>{
        const problem=!fields.problem||fields.problem==='hallucination'&&Number(a.dataset.errors)>0||fields.problem==='update'&&a.dataset.updateFailed==='true'||fields.problem==='failed'&&a.dataset.pass==='false';
        const keep=matches&&problem&&['task','arm','round'].every(k=>!fields[k]||fields[k]===a.dataset[k]);
        a.hidden=!keep;if(keep)visible++;
      });
      item.hidden=!visible;item.querySelector('[data-case-count]').textContent=`${visible} 份輸出`;
      if(visible){cases++;answers+=visible;}
    });
    explorer.querySelector('[data-visible]').textContent=`${cases} 題 · ${answers} 份輸出`;
  }
  explorer.querySelectorAll('[data-filter]').forEach(c=>c.addEventListener('input',filter));
  filter();document.body.classList.remove('nojs');
  function plot(data,rows){
    const halluc=root.dataset.view==='hallucinations',width=900,height=310,left=62,right=16,top=38,bottom=68;
    let content='';
    const rate=r=>halluc?100*r.unsafeOutputs/r.n:r.passPercent;
    const maximum=halluc?Math.max(10,Math.ceil(Math.max(...rows.map(rate))/10)*10):100;
    for(let i=0;i<=4;i++){
      const v=maximum*i/4,y=top+(1-v/maximum)*(height-top-bottom);
      content+=`<line class="grid" x1="${left}" x2="${width-right}" y1="${y}" y2="${y}"/><text x="${left-10}" y="${y+4}" text-anchor="end">${fmt(v,0)}%</text>`;
    }
    rows.forEach((r,i)=>{
      const x=left+(i+.5)*(width-left-right)/4,w=82,y=top+(1-rate(r)/maximum)*(height-top-bottom),name=data.manifest.arms.find(a=>a.id===r.armId).label;
      content+=`<rect tabindex="0" x="${x-w/2}" y="${y}" width="${w}" height="${height-bottom-y}" fill="${colors[i]}"><title>${esc(name)}：${halluc?'有重大錯誤':'合格'} ${halluc?r.unsafeOutputs:r.passes}/${r.n}，新資訊覆蓋 ${r.newCoveragePercent}%，次要p50 ${r.latencyP50}s</title></rect><text x="${x}" y="${y-8}" text-anchor="middle">${fmt(rate(r))}%</text><text x="${x}" y="${height-bottom+26}" text-anchor="middle">${['Baseline','Luna medium','Luna high','Luna + Sol'][i]}</text>`;
    });
    content+=`<text x="${left}" y="18">${halluc?'有重大錯誤的輸出比例（越低越好；仍需看覆蓋與失敗）':'完整、可靠更新且沒有重大錯誤的合格率（越高越好）'}</text>`;
    return `<svg class="plot" viewBox="0 0 ${width} ${height}" role="img" aria-label="${halluc?'四配置重大錯誤比例':'四配置記憶品質合格率'}">${content}</svg>`;
  }
  function metrics(data){
    const all=controls.split.value==='all'?data.aggregates:data.splitAggregates[controls.split.value];
    const rows=all.filter(r=>r.task===controls.task.value&&r.difficulty===controls.difficulty.value);
    root.querySelector('[data-plot]').innerHTML=plot(data,rows);
    root.querySelector('[data-metric-rows]').innerHTML=rows.map(r=>`<tr><th>${esc(data.manifest.arms.find(a=>a.id===r.armId).label)}</th><td><b>${fmt(r.passPercent)}%</b><small>${r.passes}/${r.n} · 95%區間 ${r.passInterval.map(v=>fmt(v)).join('–')}%</small></td><td>${fmt(r.newCoveragePercent)}%<small>全部目標 ${fmt(r.coveragePercent)}%</small></td><td>${r.task==='facts'?fmt(r.updatePassPercent)+'%':'—'}</td><td><b>${r.unsafeOutputs}/${r.n}</b><small>${r.materialErrors} 個重大錯誤</small></td><td>${r.apiFailures} / ${r.formatFailures}</td><td>${fmt(r.latencyP50)}s / ${fmt(r.latencyP95)}s</td></tr>`).join('');
    root.querySelector('[data-metric-caption]').textContent=`${controls.task.options[controls.task.selectedIndex].text} · ${controls.difficulty.options[controls.difficulty.selectedIndex].text} · ${controls.split.options[controls.split.selectedIndex].text} · 每配置 ${rows[0].n} 次；所有計畫呼叫都列入分母。`;
    const sourceRows=rows.map(r=>{
      const selected=data.records.filter(v=>v.armId===r.armId&&v.task===r.task&&(controls.difficulty.value==='all'||v.difficulty===controls.difficulty.value)&&(controls.split.value==='all'||v.split===controls.split.value));
      return errorOriginCounts(selected);
    });
    root.querySelector('[data-error-types]').innerHTML=`<details${root.dataset.view==='hallucinations'?' open':''}><summary>重大錯誤類型（按錯誤數，非輸出數）</summary><div class="scroll"><table><thead><tr><th>類型</th>${rows.map(r=>`<th>${esc(data.manifest.arms.find(a=>a.id===r.armId).label)}</th>`).join('')}</tr></thead><tbody>${[['new','本次新寫入的錯誤'],['retained','舊資料仍有效的錯誤'],['unknown','引用重疊，無法唯一歸因']].map(([key,label])=>`<tr><th>${label}</th>${sourceRows.map(s=>`<td>${s[key]}</td>`).join('')}</tr>`).join('')}${Object.entries(labels).map(([key,label])=>`<tr><th>${label}</th>${rows.map(r=>`<td>${r.errorTypes[key]||0}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`;
  }
  fetch(root.dataset.results).then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}).then(data=>{
    if(data.version!==root.dataset.version)throw new Error('版本不一致');
    metrics(data);Object.values(controls).forEach(c=>c.addEventListener('input',()=>metrics(data)));
  }).catch(()=>{
    const status=root.querySelector('[data-load-status]');status.dataset.error='true';status.textContent='互動成績暫時無法載入；靜態成績、所有檔案與下載資料仍可檢查。';
    Object.values(controls).forEach(c=>c.disabled=true);
  });
})();
