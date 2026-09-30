import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';

const renderer=fileURLToPath(new URL('../../scripts/render-natural-bridges.mjs',import.meta.url));
const sha=value=>crypto.createHash('sha256').update(value).digest('hex');
const hostToolBudget='Both arms share a benchmark-only cap of 12 admitted host tool calls per task attempt; production has no such benchmark cap.';
function render({text='合成問題',mismatch=false,extraQuality=false,amendStudy=()=>{},amendQuality=()=>{},
  corruptGuard=false,guardReject=[],reason=null}={}){
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'bridge-publication-'));
  try{
    const publicDir=path.join(root,'public/line-v3');fs.mkdirSync(publicDir,{recursive:true});
    for(const page of ['index','delegation','taiwan','recovery','tts-followup','burst-turns'])
      fs.writeFileSync(path.join(publicDir,page+'.html'),'<nav class="tabs"></nav>');
    const source='a'.repeat(40);
    const data={metadata:{source_ref:source,accounts:['primary'],repeats:1,models:{foreground:'fixture',executor:'fixture'},host_tool_budget:hostToolBudget},
      cases:[{id:'NB001',category:'fixture',rubric:[],turns:[{text}]}],receipts:['baseline','natural'].map(arm=>
        ({case_id:'NB001',account:'primary',repeat:1,arm,status:'error',turns:[]}))};
    amendStudy(data);
    const results=path.join(root,'results.json');fs.writeFileSync(results,JSON.stringify(data));
    const guardPath='source/serve/line_agent_v2/evals/line_architecture/publication.py';
    const judgePath='source/serve/line_agent_v3/evals/natural_bridges/judge.py';
    // Test double for the existing cross-repository guard's contract. The real
    // CLI loads the exact module authenticated by the frozen study's plan.
    const guard=`class PublicationError(ValueError): pass
def _secret_values(value):
    result = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"api_key", "secret"} and isinstance(child, str): result.add(child)
            result.update(_secret_values(child))
    elif isinstance(value, list):
        for child in value: result.update(_secret_values(child))
    return result
def sanitize_results(value, *, sensitive_values=()):
    assert value["metadata"]["variants"] == ["natural_bridges"]
    texts = value["cases"][0]["natural_bridges"]["messages"][0]["texts"]
    assert all(isinstance(text, str) for text in texts)
    if any(text in ${JSON.stringify(guardReject)} or any(secret in text for secret in sensitive_values) for text in texts):
        raise PublicationError("measured_answer_requires_review")
    return {"do_not_publish_rewritten_copy": True}
`;
    const judge='# Synthetic frozen judge fixture.\n';
    for(const [name,contents] of [[guardPath,guard],[judgePath,judge]]){
      fs.mkdirSync(path.dirname(path.join(root,name)),{recursive:true});
      fs.writeFileSync(path.join(root,name),contents);
    }
    const plan={source_ref:source,files:{[guardPath]:sha(guard),[judgePath]:sha(judge)}};
    const planBytes=JSON.stringify(plan);fs.writeFileSync(path.join(root,'plan.json'),planBytes);
    const samples=reason===null?[]:[{case_id:'NB001',account:'primary',repeat:1,turn_index:0}];
    const sampleBytes=JSON.stringify(samples);fs.writeFileSync(path.join(root,'quality-samples.json'),sampleBytes);
    const binding={source_ref:source,results_sha256:mismatch?'wrong':sha(fs.readFileSync(results)),
      plan_sha256:sha(planBytes),quality_samples_sha256:sha(sampleBytes),judge_sha256:sha(judge)};
    const quality={model:'fixture',...binding,bridge_dimensions:[],final_dimensions:[],
      results:extraQuality?[{id:'UNKNOWN.primary.r1.t0',status:'error'}]:reason===null?[]:[{
        ...binding,id:'NB001.primary.r1.t0',status:'ok',bridge_winner:'not_applicable',
        arms:Object.fromEntries(['baseline','natural'].map(arm=>[arm,{bridge:{},final:{},reason}]))}]};
    amendQuality(quality);
    const scores=path.join(root,'quality.json');fs.writeFileSync(scores,JSON.stringify(quality));
    if(corruptGuard)fs.appendFileSync(path.join(root,guardPath),'# Changed after freezing.\n');
    const child=spawnSync(process.execPath,[renderer,results,scores],{cwd:root,encoding:'utf8'});
    const file=path.join(publicDir,'natural-bridges.html');
    const publicFile=path.join(publicDir,'natural-bridges-results.public.json');
    return{status:child.status,stderr:child.stderr,exists:fs.existsSync(file),html:fs.existsSync(file)?fs.readFileSync(file,'utf8'):'',
      public:fs.existsSync(publicFile)?JSON.parse(fs.readFileSync(publicFile,'utf8')):null};
  }finally{fs.rmSync(root,{recursive:true,force:true});}
}
test('both-arm failures remain visible and planned text is escaped',()=>{
  const actual=render({text:'合成 <script>alert(1)</script>'});
  assert.equal(actual.status,0,actual.stderr);
  assert.match(actual.html,/NB001/);
  assert.equal((actual.html.match(/這一側沒有可用的回合紀錄/g)??[]).length,2);
  assert.match(actual.html,/&lt;script&gt;alert/);
  assert.doesNotMatch(actual.html,/<script>alert/);
});
test('a quality file from another study cannot be published',()=>{
  const actual=render({mismatch:true});assert.notEqual(actual.status,0);assert.equal(actual.exists,false);
});
test('unplanned quality pairs cannot enter aggregates',()=>{
  const actual=render({extraQuality:true});assert.notEqual(actual.status,0);assert.equal(actual.exists,false);
});
for(const text of ['/Users/example/private.txt','https://user:password@example.com/x','https://example.com/?token=private','data:image/png;base64,AAAA'])
  test('unsafe planned text is rejected even when both workers fail: '+text,()=>{
    const actual=render({text});assert.notEqual(actual.status,0);assert.equal(actual.exists,false);
  });

test('frozen guard and complete study binding are required before any public write',()=>{
  for(const options of [{corruptGuard:true},{amendQuality:q=>q.plan_sha256='b'.repeat(64)},
    {amendQuality:q=>q.quality_samples_sha256='b'.repeat(64)},{amendQuality:q=>q.judge_sha256='b'.repeat(64)}]){
    const actual=render(options);assert.notEqual(actual.status,0);assert.equal(actual.exists,false);assert.equal(actual.public,null);
  }
});
test('the Python guard receives planned text and every quality reason',()=>{
  for(const options of [{text:'guard rejects this planned text',guardReject:['guard rejects this planned text']},
    {reason:'guard rejects this quality reason',guardReject:['guard rejects this quality reason']}]){
    const actual=render(options);assert.notEqual(actual.status,0);assert.match(actual.stderr,/visible_text_requires_review/);
    assert.equal(actual.public,null);
  }
});
test('known secret values come from raw study and quality fields even when those fields are omitted publicly',()=>{
  const secret='synthetic-private-canary';
  for(const options of [{text:secret,amendStudy:data=>data.private={api_key:secret}},
    {reason:secret,amendQuality:quality=>quality.private={secret}}]){
    const actual=render(options);assert.notEqual(actual.status,0);assert.match(actual.stderr,/visible_text_requires_review/);
    assert.equal(actual.public,null);
  }
});
test('safe public URLs retain their exact text and do not use the sanitizer replacement',()=>{
  const text='官方頁面 https://example.org/home/help';
  const actual=render({text});assert.equal(actual.status,0,actual.stderr);
  assert.equal(actual.public.cases[0].turns[0].text,text);
  assert.doesNotMatch(actual.html,/do_not_publish_rewritten_copy/);
  assert.doesNotMatch(actual.html,/實際承接文字的完全相同率與差異/);
});
test('foreign cached judgments and duplicate capture receipts cannot enter aggregates',()=>{
  for(const options of [{reason:'fixture',amendQuality:q=>q.results[0].results_sha256='b'.repeat(64)},
    {amendStudy:data=>data.receipts.push(data.receipts[0])}]){
    const actual=render(options);assert.notEqual(actual.status,0);assert.equal(actual.public,null);
  }
});
function capturedStudy(data){
  for(const row of data.receipts){
    const natural=row.arm==='natural';
    row.status='measured';
    row.turns=[{turn_index:0,user_text:data.cases[0].turns[0].text,status:'final_captured',drain_requested:true,
      metrics:{frontend_latency_ms:natural?150:100,executor_start_ms:natural?220:200,routing_calls:1,
        bridge_captured_latency_ms:natural?200:150,final_captured_latency_ms:natural?400:500},
      interaction:[{action:'delegate'}],foreground_ledger:{response_phase:{role:'bridge',outcome:'accepted',awaiting_result:true}},
      messages:[{semantic_role:'bridge',texts:['捕捉的承接文字。'],elapsed_ms:natural?200:150,kind:'reply'},
        {semantic_role:'final',texts:['捕捉的最終成果。'],elapsed_ms:natural?400:500,kind:'push'}]}];
  }
}
test('captured metrics reach the page and public JSON with paired denominators',()=>{
  const actual=render({amendStudy:capturedStudy});assert.equal(actual.status,0,actual.stderr);
  assert.match(actual.html,/前景模型呼叫耗時/);assert.match(actual.html,/背景執行起點/);
  assert.match(actual.html,/可比較配對 \/ 任一側有觀測/);
  assert.match(actual.html,/實際承接文字的完全相同率與差異/);
  assert.match(actual.html,/每次任務嘗試最多接納 12 次呼叫/);
  assert.match(actual.html,/正式環境沒有這項限制/);
  assert.equal(actual.public.host_tool_budget,hostToolBudget);
  assert.deepEqual(actual.public.statistics.paired_delta_ms.final,
    {n:1,median:-100,p95:-100,observed_either:1,planned_pairs:1});
  assert.equal(actual.public.receipts[0].turns[0].messages[0].texts[0],'捕捉的承接文字。');
});
test('Python publication validation also receives captured bridge and final copy',()=>{
  for(const rejected of ['捕捉的承接文字。','捕捉的最終成果。']){
    const actual=render({amendStudy:capturedStudy,guardReject:[rejected]});
    assert.notEqual(actual.status,0);assert.match(actual.stderr,/visible_text_requires_review/);assert.equal(actual.public,null);
  }
});
