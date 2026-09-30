import {test} from 'node:test';
import assert from 'node:assert/strict';
import {latency,summarize} from '../../scripts/natural-bridges-metrics.mjs';

const message=(role,texts,elapsed_ms)=>({role,texts,elapsed_ms});
function fixture(){
  const baseline=[
    {messages:[message('bridge',['固定承接。'],1000),message('final',['完成。'],5000)],metrics:{frontend_latency_ms:120,executor_start_ms:1500}},
    {messages:[message('bridge',['固定承接。'],2000),message('duplicate',['不能當多樣性樣本'],2100)],
      metrics:{frontend_latency_ms:220,executor_start_ms:2500,final_captured_latency_ms:9999}},
  ];
  const natural=[
    {messages:[message('bridge',['對應情境的承接。'],1500),message('final',['完成。'],4500)],metrics:{frontend_latency_ms:130,executor_start_ms:2000}},
    {messages:[message('direct_answer',['直接回答。'],800)],metrics:{frontend_latency_ms:230,executor_start_ms:null,final_captured_latency_ms:800}},
  ];
  const pairs=new Map(baseline.map((turn,index)=>[index,{baseline:turn,natural:natural[index]}]));
  pairs.set(2,{}); // Both workers failed: still part of the planned denominator.
  return {data:{receipts:[{arm:'baseline',turns:baseline},{arm:'natural',turns:natural}]},pairs};
}
test('headline stages use observed numeric samples and retain planned denominators',()=>{
  const {data,pairs}=fixture(),result=summarize(data,pairs);
  assert.deepEqual(result.latency.baseline.frontend,{n:2,median:170,p95:220,planned_turns:3});
  assert.deepEqual(result.latency.natural.executor_start,{n:1,median:2000,p95:2000,planned_turns:3});
  assert.equal(result.latency.baseline.final.n,1);
  assert.equal(result.latency.natural.direct_answer.n,1);
});
test('paired deltas require the same delivered phase on both sides, never a waiting or direct final metric',()=>{
  const {data,pairs}=fixture(),result=summarize(data,pairs);
  assert.deepEqual(result.paired_delta_ms.bridge,{n:1,median:500,p95:500,observed_either:2,planned_pairs:3});
  assert.deepEqual(result.paired_delta_ms.final,{n:1,median:-500,p95:-500,observed_either:1,planned_pairs:3});
  assert.equal(latency(pairs.get(1).baseline,'final'),null);
  assert.equal(latency(pairs.get(1).natural,'final'),null);
});
test('diversity counts exact delivered bridge envelopes and preserves message boundaries',()=>{
  const {data,pairs}=fixture();
  assert.deepEqual(summarize(data,pairs).bridge_diversity,{baseline:{n:2,distinct_exact:1},natural:{n:1,distinct_exact:1}});
  data.receipts[0].turns[0].messages[0].texts=['a','b'];
  data.receipts[0].turns[1].messages[0].texts=['a\nb'];
  assert.equal(summarize(data,pairs).bridge_diversity.baseline.distinct_exact,2);
});
test('empty stages stay missing, and bridge capture uses the first proven message',()=>{
  assert.equal(latency({messages:[message('bridge',['first'],10),message('bridge',['second'],20)]},'bridge'),10);
  const empty=summarize({receipts:[]},new Map([[0,{}]]));
  assert.deepEqual(empty.paired_delta_ms.final,{n:0,median:null,p95:null,observed_either:0,planned_pairs:1});
  assert.deepEqual(empty.bridge_diversity.baseline,{n:0,distinct_exact:0});
});
