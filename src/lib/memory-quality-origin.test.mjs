import {test} from 'node:test';
import assert from 'node:assert/strict';
import {errorOrigin,errorOriginCounts} from '../../public/line-v3/memory-quality-origin.js';

test('new assertions and old assertions left active have distinct source attribution',()=>{
  const r={task:'facts',profileConstruction:{storedFacts:[
    {key:'工作',value:'當護士',evidence_seq:1001,sourceStage:'prior',temporal_scope:'durable'},
    {key:'工作',value:'當老師',evidence_seq:1,sourceStage:'current',temporal_scope:'durable'}]},
    quality:{errors:[{outputQuote:'事實：當護士'},{outputQuote:'事實：當老師'}]}};
  assert.equal(errorOrigin(r,r.quality.errors[0]),'retained');
  assert.equal(errorOrigin(r,r.quality.errors[1]),'new');
  assert.deepEqual(errorOriginCounts([r]),{new:1,retained:1,unknown:0});
});
test('a short quote shared by opposite statements is left unattributed',()=>{
  const r={task:'facts',profileConstruction:{storedFacts:[
    {key:'興趣',value:'喜歡牛肉',evidence_seq:1001,sourceStage:'prior',temporal_scope:'durable'},
    {key:'興趣',value:'不喜歡牛肉',evidence_seq:1,sourceStage:'current',temporal_scope:'durable'}]}};
  assert.equal(errorOrigin(r,{outputQuote:'牛肉'}),'unknown');
});
test('an empty profile rewrite can retain an old error while writing a separate summary',()=>{
  const r={task:'summary',formatOk:true,accepted:{summary:'住台北。',profile:''},
    judgedOutput:'【本次談話】\n住台北。\n【實際累積印象】\n有女朋友。'};
  assert.equal(errorOrigin(r,{outputQuote:'住台北'}),'new');
  assert.equal(errorOrigin(r,{outputQuote:'有女朋友'}),'retained');
});
