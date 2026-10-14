import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {validateData,render,receiptHash} from '../../scripts/render-memory-models.mjs';
import {publishArchive} from '../../scripts/publish-memory-archive.mjs';

const reportURL=new URL('../../public/line-v3/memory-models-results.public.json',import.meta.url);
const data=()=>JSON.parse(fs.readFileSync(reportURL,'utf8'));
test('complete requested model comparison binds quality to every planned generation',()=>{
  const d=validateData(data());
  assert.equal(d.records.length,800);
  assert.equal(d.judge.primaryEvaluations.length,200);
  assert.equal(d.judge.mirrorRecords.length,48);
  assert.equal(d.records.filter(r=>r.difficulty==='hard').length,400);
  assert.equal(d.cases.length,100);
  if(d.promptIterations){
    assert.equal(d.promptIterations.records.length,600);
    assert.equal(d.promptIterations.plans.length,3);
  }else{
    assert.equal(d.version,'memory-models-quality-v6-mem0');
    assert.equal(d.memoryUpdate.extractionCalls,400);
    assert.equal(d.memoryUpdate.summaryCalls,400);
  }
  assert(d.records.every(r=>r.maxCompletionTokens===16384));
});
test('incomplete, duplicated, altered, or unjudged evidence cannot be published',()=>{
  const edits=[d=>d.records.pop(),d=>d.records[0]=d.records[1],
    d=>d.records[0].quality.score+=1,d=>d.records[0].latencySeconds+=1,
    d=>d.cases[0].turns[0].text+=' altered',d=>d.judge.primaryEvaluations.pop(),
    d=>d.judge.mirrorRecords.pop(),d=>d.manifest.arms[3].facts.effort='high',
    d=>d.records[0].maxCompletionTokens=8192,
    d=>d.judge.primaryEvaluations[0].evaluations[0].coverage[0].outputQuote='fabricated quote'];
  if(data().promptIterations)edits.push(d=>d.promptIterations.records.pop(),
    d=>d.promptIterations.primaryEvaluations.pop(),d=>d.promptIterations.plans[2].reviewedDevelopmentEvidenceHash=null);
  for(const edit of edits){const d=data();edit(d);assert.throws(()=>validateData(d));}
});
test('an error must quote an actual candidate and an actual source turn',()=>{
  const d=data(),j=d.judge.primaryEvaluations[0],e=j.evaluations[0];
  e.errors.push({type:'wrong_person',outputQuote:'fabricated output',sourceSeq:1,sourceQuote:'fabricated source',reason:'bad'});
  assert.throws(()=>validateData(d),/evidence mismatch/);
});
test('known secret and private path patterns stop public output',()=>{
  for(const text of ['sk-proj-syntheticprivatecredential123456','/Users/synthetic/private.txt','Bearer syntheticprivatecredential123456']){
    const d=data();d.records[0].raw+='\n'+text;assert.throws(()=>validateData(d),/Private material/);
  }
});
test('candidate text is escaped and failures remain visible',()=>{
  const d=data();d.records[0].raw+='\n<script>alert("synthetic")</script>';
  if(d.records[0].extractionReceipt)d.records[0].extractionReceipt.raw=d.records[0].raw;
  d.records[0].receiptHash=receiptHash(d.records[0]);
  const html=render(d);
  assert.match(html,/&lt;script&gt;alert/);
  assert.doesNotMatch(html,/<script>alert/);
  assert.equal((html.match(/data-answer data-task=/g)||[]).length,d.records.length+(d.promptIterations?.records.filter(r=>r.promptRound!==1).length||0));
  assert.match(html,/所有計畫呼叫都列入分母/);
  assert.match(html,/p50/);assert.match(html,/p95/);
});
test('both API stages, original candidates and judged error counts are bound before publication',()=>{
  const archive=new URL('../../public/line-v3/memory-models-results-v5.public.json',import.meta.url);
  const base=()=>JSON.parse(fs.readFileSync(archive,'utf8'));
  validateData(base());
  const edits=[
    (d,r)=>r.extractionReceipt.maxCompletionTokens=8192,
    (d,r)=>r.reconciliation.maxCompletionTokens=8192,
    (d,r)=>r.reconciliation.config.model='synthetic-unrequested-model',
    (d,r)=>r.usage.completion_tokens+=1,
    (d,r)=>r.reconciliation.candidateProjection[0].fact_id=123,
    (d,r)=>r.reconciliation.freshFactsHash='0'.repeat(64),
    (d,r)=>r.reconciliation.promptHash='0'.repeat(64),
    (d,r)=>r.costUsd=999,
    d=>d.aggregates[0].materialErrors=999,
    d=>d.aggregates[0].errorTypes.unsupported=999,
    d=>{const r=d.records.find(r=>r.quality.errors.length);r.quality.errorCount=0;},
    d=>d.memoryUpdate.updateCalls-=1,
  ];
  for(const edit of edits){
    const d=base(),r=d.records.find(r=>r.reconciliation?.apiOk&&r.reconciliation.candidateProjection.length);
    edit(d,r);r.receiptHash=receiptHash(r);assert.throws(()=>validateData(d));
  }
});
test('archives keep their own study downloads and prior prompt iterations',()=>{
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'memory-archive-'));
  try{
    for(const tag of ['v4','v5']){
      const input=fileURLToPath(new URL(`../../public/line-v3/memory-models-results-${tag}.public.json`,import.meta.url));
      publishArchive(input,temp,tag);
      const html=fs.readFileSync(path.join(temp,`memory-models-${tag}.html`),'utf8');
      assert.match(html,new RegExp(`封存 ${tag}`));
      assert.match(html,new RegExp(`memory-models-results-${tag}\\.public\\.json`));
      assert.match(html,new RegExp(`memory-models-summary-${tag}\\.csv`));
      assert.doesNotMatch(html,/href="memory-models-summary\.csv/);
      assert.match(html,/href="memory-models.html">返回最新完整比較/);
      if(tag==='v4')assert.match(html,/三次 prompt 迭代/);
      else assert.doesNotMatch(html,/v6依v5觀察/);
    }
  }finally{fs.rmSync(temp,{recursive:true,force:true});}
});
test('all active tabs share report width, memory link and one return link after repeat builds',()=>{
  const normalizer=fileURLToPath(new URL('../../scripts/normalize-line-navigation.mjs',import.meta.url));
  const source=fs.readFileSync(normalizer,'utf8');
  const pages=[...source.matchAll(/\['([^']+\.html)',/g)].map(m=>m[1]);
  assert.equal(pages.length,15);
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'memory-nav-'));
  try{
    for(const name of [...pages,'navigation.css','navigation.js','report-layout.css'])
      fs.copyFileSync(new URL('../../public/line-v3/'+name,import.meta.url),path.join(temp,name));
    for(let pass=0;pass<2;pass++){
      const child=spawnSync(process.execPath,[normalizer,temp],{encoding:'utf8'});
      assert.equal(child.status,0,child.stderr);
      for(const page of pages){
        const html=fs.readFileSync(path.join(temp,page),'utf8');
        assert.equal((html.match(/class="benchmark-nav"/g)||[]).length,1,page);
        assert.equal((html.match(/href="\/line-latest\/"/g)||[]).length,1,page);
        assert.equal((html.match(/href="memory-models.html"/g)||[]).length,1,page);
        assert.match(html,/<body[^>]*class="[^"]*benchmark-page/);
        assert.match(html,/report-layout\.css\?v=[a-f0-9]{12}/);
        assert.equal((html.match(/aria-current="page"/g)||[]).length,1,page);
      }
    }
    const css=fs.readFileSync(path.join(temp,'report-layout.css'),'utf8');
    assert.match(css,/--benchmark-width:\s*1500px/);
    assert.match(css,/--benchmark-gutter:\s*16px/);
    assert.match(css,/max-width:\s*var\(--benchmark-width\)/);
    const nav=fs.readFileSync(path.join(temp,'navigation.css'),'utf8');
    assert.match(nav,/max-width:\s*var\(--benchmark-width, 1500px\)/);
  }finally{fs.rmSync(temp,{recursive:true,force:true});}
});
