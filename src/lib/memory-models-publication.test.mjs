import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {validateData,render,receiptHash} from '../../scripts/render-memory-models.mjs';

const reportURL=new URL('../../public/line-v3/memory-models-results.public.json',import.meta.url);
const data=()=>JSON.parse(fs.readFileSync(reportURL,'utf8'));
test('complete requested model comparison binds quality to every planned generation',()=>{
  const d=validateData(data());
  assert.equal(d.records.length,512);
  assert.equal(d.judge.primaryEvaluations.length,128);
  assert.equal(d.judge.mirrorRecords.length,96);
  assert.equal(d.records.filter(r=>r.difficulty==='hard').length,192);
});
test('incomplete, duplicated, altered, or unjudged evidence cannot be published',()=>{
  const edits=[d=>d.records.pop(),d=>d.records[0]=d.records[1],
    d=>d.records[0].quality.score+=1,d=>d.records[0].latencySeconds+=1,
    d=>d.cases[0].turns[0].text+=' altered',d=>d.judge.primaryEvaluations.pop(),
    d=>d.judge.mirrorRecords.pop(),d=>d.manifest.arms[3].facts.effort='high',
    d=>d.judge.primaryEvaluations[0].evaluations[0].coverage[0].outputQuote='fabricated quote'];
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
  d.records[0].receiptHash=receiptHash(d.records[0]);
  const html=render(d);
  assert.match(html,/&lt;script&gt;alert/);
  assert.doesNotMatch(html,/<script>alert/);
  assert.equal((html.match(/data-answer data-task=/g)||[]).length,512);
  assert.match(html,/全部計畫呼叫均列入分母/);
  assert.match(html,/p50/);assert.match(html,/p95/);
});
test('all active tabs share report width, memory link and one return link after repeat builds',()=>{
  const normalizer=fileURLToPath(new URL('../../scripts/normalize-line-navigation.mjs',import.meta.url));
  const source=fs.readFileSync(normalizer,'utf8');
  const pages=[...source.matchAll(/\['([^']+\.html)',/g)].map(m=>m[1]);
  assert.equal(pages.length,14);
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
