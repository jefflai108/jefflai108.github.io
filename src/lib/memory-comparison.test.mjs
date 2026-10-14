import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {buildComparison,comparisonMarkup} from '../../scripts/memory-comparison-report.mjs';
const read=name=>JSON.parse(fs.readFileSync(new URL('../../public/line-v3/'+name,import.meta.url),'utf8'));
test('matched before/after counts preserve output, update-case and per-stage denominators',()=>{
  const a=read('memory-models-results-v4.public.json'),b=read('memory-models-results.public.json');
  const c=buildComparison(a,b);
  assert.deepEqual(c.rows.map(r=>[r.armId,r.facts.before.errors,r.facts.after.errors,r.summary.before.errors,r.summary.after.errors]),[['baseline',26,2,50,39],['luna-medium',24,2,6,4],['luna-high',25,2,3,4],['luna-sol',25,0,2,5]]);
  assert(c.rows.every(r=>r.updates.before.n===38&&r.updates.after.n===38));
  assert.equal(c.rows.find(r=>r.armId==='luna-sol').updates.after.passed,38);
  assert.deepEqual(c.tokenEvidence,{perCallCap:16384,candidateCalls:1153,tokenLimitHits:0,maxCompletionTokens:9239,factsMaxAllowedAcrossTwoCalls:32768});
  const html=comparisonMarkup(c);assert.match(html,/25\.0% → 0\.0%/);assert.match(html,/32,768/);assert.match(html,/摘要沒有使用這個更新器/);
});
test('different corpora or model controls cannot be presented as the same comparison',()=>{
  const a=read('memory-models-results-v4.public.json'),b=read('memory-models-results.public.json');
  b.manifest.casesHash='0'.repeat(64);assert.throws(()=>buildComparison(a,b),/corpus/);
  b.manifest.casesHash=a.manifest.casesHash;b.manifest.arms[3].facts.effort='high';assert.throws(()=>buildComparison(a,b),/controls/);
});
