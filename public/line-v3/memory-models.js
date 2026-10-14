(() => {
  const root = document.querySelector('[data-memory-report]');
  if (!root) return;
  const colors = ['#687b72','#27897b','#c08735','#7565a5'];
  const markers = ['B','M','H','S'];
  const escape = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = (value, digits=1) => Number(value).toFixed(digits);
  const task = root.querySelector('[data-metric=task]');
  const difficulty = root.querySelector('[data-metric=difficulty]');
  let data;
  function plot(rows) {
    const width=780, height=360, left=65, right=25, top=25, bottom=65;
    const max=Math.max(5,...rows.map(r=>r.latencyP50))*1.15;
    const x=s=>left+s/max*(width-left-right), y=p=>top+(100-p)/100*(height-top-bottom);
    let content='';
    [0,25,50,75,100].forEach(v=>content+=`<line class="grid" x1="${left}" x2="${width-right}" y1="${y(v)}" y2="${y(v)}"/><text x="${left-10}" y="${y(v)+4}" text-anchor="end">${v}%</text>`);
    for(let i=0;i<=4;i++){const v=max*i/4;content+=`<text x="${x(v)}" y="${height-bottom+25}" text-anchor="middle">${number(v)}s</text>`;}
    rows.forEach((r,i)=>{
      const name=data.manifest.arms[i].label;
      content+=`<g><circle tabindex="0" cx="${x(r.latencyP50)}" cy="${y(r.passPercent)}" r="13" fill="${colors[i]}" opacity=".9"><title>${escape(name)}：合格 ${r.passes}/${r.n}，p50 ${r.latencyP50}s，p95 ${r.latencyP95}s</title></circle><text class="mark-label" x="${x(r.latencyP50)}" y="${y(r.passPercent)+4}" text-anchor="middle" pointer-events="none">${markers[i]}</text></g>`;
    });
    content+=`<text x="${width/2}" y="${height-8}" text-anchor="middle">記憶生成時間 p50（秒；越左越快）</text><text x="${left}" y="15">合格率（越高越好）</text>`;
    return `<svg class="plot" viewBox="0 0 ${width} ${height}" role="img" aria-label="四種配置的記憶合格率與中位生成時間">${content}</svg>`;
  }
  function metrics() {
    if(!data)return;
    const rows=data.aggregates.filter(r=>r.task===task.value&&r.difficulty===difficulty.value);
    root.querySelector('[data-plot]').innerHTML=plot(rows);
    root.querySelector('[data-metric-rows]').innerHTML=rows.map((r,i)=>`<tr><th scope="row"><span class="swatch" style="background:${colors[i]}"></span> ${escape(data.manifest.arms[i].label)}</th><td><b>${number(r.passPercent)}%</b><small>${r.passes}/${r.n} · 區間 ${r.passInterval.map(v=>number(v)).join('–')}%</small></td><td>${r.unsafeOutputs}/${r.n}<small>${r.materialErrors} 個重大錯誤</small></td><td>${number(r.coveragePercent)}%<small>${number(r.scoreMean)} / 100 分</small></td><td><b>${number(r.latencyP50)}s</b></td><td>${number(r.latencyP95)}s<small>超過40s：${r.over40Seconds}/${r.n}</small></td><td>${r.apiFailures} / ${r.formatFailures}<small>API / 格式</small></td><td>$${number(r.costUsd/r.n,4)}<small>${Math.round(r.outputTokens/r.n).toLocaleString()} 輸出 tokens/次</small></td></tr>`).join('');
    root.querySelector('[data-metric-caption]').textContent=`${task.options[task.selectedIndex].text} · ${difficulty.options[difficulty.selectedIndex].text} · 每組 ${rows[0].n} 次；全部計畫呼叫均列入分母。`;
  }
  const explorer=root.querySelector('[data-explorer]');
  function filter() {
    const controls=Object.fromEntries(Array.from(explorer.querySelectorAll('select[data-filter]')).map(c=>[c.dataset.filter,c.value]));
    const query=explorer.querySelector('[data-filter=search]').value.trim().toLowerCase();
    const failures=explorer.querySelector('[data-filter=failed]').checked;
    let count=0, answers=0;
    explorer.querySelectorAll('[data-case]').forEach(item=>{
      let visible=0;
      const caseMatches=(!controls.difficulty||item.dataset.difficulty===controls.difficulty)&&(!query||item.textContent.toLowerCase().includes(query));
      item.querySelectorAll('[data-answer]').forEach(answer=>{
        const keep=caseMatches&&['task','arm','repeat'].every(k=>!controls[k]||answer.dataset[k]===controls[k])&&(!failures||answer.dataset.pass==='false');
        answer.hidden=!keep;
        if(keep)visible++;
      });
      item.hidden=visible===0;
      if(visible){count++;answers+=visible;}
      item.querySelector('[data-case-count]').textContent=`${visible} 份輸出`;
    });
    explorer.querySelector('[data-visible]').textContent=`${count} 題 · ${answers} 份輸出`;
  }
  explorer.querySelectorAll('[data-filter]').forEach(c=>c.addEventListener('input',filter));
  filter();
  document.body.classList.remove('nojs');
  [task,difficulty].forEach(c=>c.addEventListener('input',metrics));
  fetch(root.dataset.results).then(response=>{if(!response.ok)throw new Error('HTTP '+response.status);return response.json();}).then(value=>{
    if(value.version!==root.dataset.version)throw new Error('版本不一致');
    data=value;metrics();
  }).catch(()=>{
    const status=root.querySelector('[data-load-status]');status.dataset.error='true';
    status.textContent='互動圖表暫時無法載入。下方保留完整靜態成績與案例，也可下載原始結果。';
    task.disabled=true;difficulty.disabled=true;
  });
})();
