import fs from 'node:fs';
import path from 'node:path';
import {validateData,render} from './render-memory-models.mjs';

export function publishArchive(input,outputDirectory,tag){
  if(!['v4','v5'].includes(tag))throw new Error('Unknown memory archive');
  const data=validateData(JSON.parse(fs.readFileSync(input,'utf8')));
  if(data.version!==(tag==='v4'?'memory-models-quality-v4':'memory-models-quality-v5-mem0'))throw new Error('Memory archive version mismatch');
  for(const view of ['profiles','hallucinations']){
    const name=view==='profiles'?'memory-models':'memory-hallucinations';
    let html=render(data,view);
    for(const [from,to] of [['memory-models-results.public.json',`memory-models-results-${tag}.public.json`],['memory-models-summary.csv',`memory-models-summary-${tag}.csv`],['memory-prompt-iterations-summary.csv',`memory-prompt-iterations-summary-${tag}.csv`],['memory-models.html',`memory-models-${tag}.html`],['memory-hallucinations.html',`memory-hallucinations-${tag}.html`]])html=html.replaceAll(from,to);
    html=html.replace('<main id="content"',`<p class="notice">封存 ${tag}：${tag==='v4'?'前次單次抽取與 Luna high 三版 prompt':'第一版操作管理；後續v6澄清分類契約與目前撤回證據'}。<a href="memory-models.html">返回最新完整比較</a></p><main id="content"`);
    fs.writeFileSync(path.join(outputDirectory,`${name}-${tag}.html`),html);
  }
  const columns=['difficulty','task','armId','n','passes','passPercent','newCoveragePercent','updatePassPercent','unsafeOutputs','materialErrors','apiFailures','formatFailures','latencyP50','latencyP95','retryOutputs','costUsd'];
  fs.writeFileSync(path.join(outputDirectory,`memory-models-summary-${tag}.csv`),columns.join(',')+'\n'+data.aggregates.map(a=>columns.map(k=>a[k]).join(',')).join('\n')+'\n');
  if(data.promptIterations)fs.writeFileSync(path.join(outputDirectory,`memory-prompt-iterations-summary-${tag}.csv`),columns.concat('promptRound','split').join(',')+'\n'+data.promptIterations.aggregates.map(a=>columns.concat('promptRound','split').map(k=>a[k]).join(',')).join('\n')+'\n');
}
