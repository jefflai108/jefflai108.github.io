import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';

const renderer=fileURLToPath(new URL('../../scripts/render-natural-bridges.mjs',import.meta.url));
function render({text='合成問題',mismatch=false,extraQuality=false}={}){
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'bridge-publication-'));
  try{
    const publicDir=path.join(root,'public/line-v3');fs.mkdirSync(publicDir,{recursive:true});
    for(const page of ['index','delegation','taiwan','recovery','tts-followup','burst-turns'])
      fs.writeFileSync(path.join(publicDir,page+'.html'),'<nav class="tabs"></nav>');
    const source='a'.repeat(40);
    const data={metadata:{source_ref:source,accounts:['primary'],repeats:1,models:{foreground:'fixture',executor:'fixture'}},
      cases:[{id:'NB001',category:'fixture',rubric:[],turns:[{text}]}],receipts:['baseline','natural'].map(arm=>
        ({case_id:'NB001',account:'primary',repeat:1,arm,status:'error',turns:[]}))};
    const results=path.join(root,'results.json');fs.writeFileSync(results,JSON.stringify(data));
    const quality={model:'fixture',source_ref:source,results_sha256:mismatch?'wrong':crypto.createHash('sha256').update(fs.readFileSync(results)).digest('hex'),
      bridge_dimensions:[],final_dimensions:[],results:extraQuality?[{id:'UNKNOWN.primary.r1.t0',status:'error'}]:[]};
    const scores=path.join(root,'quality.json');fs.writeFileSync(scores,JSON.stringify(quality));
    const child=spawnSync(process.execPath,[renderer,results,scores],{cwd:root,encoding:'utf8'});
    const file=path.join(publicDir,'natural-bridges.html');
    return{status:child.status,stderr:child.stderr,exists:fs.existsSync(file),html:fs.existsSync(file)?fs.readFileSync(file,'utf8'):''};
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
