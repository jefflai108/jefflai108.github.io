// Exercise async editor behavior without changing production data or driving a browser.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import ts from 'typescript';
const source = readFileSync(new URL('../../src/scripts/taigi-review.ts', import.meta.url), 'utf8');
const script = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
function deferred() { let resolve, reject; const promise = new Promise((a,b) => {resolve=a; reject=b;}); return {promise,resolve,reject}; }
class Element {
  constructor() { this.value=''; this.textContent=''; this.children=[]; this.dataset={}; this.hidden=false; this.disabled=false; this.handlers={}; this.attributes={}; this.classList={toggle(){}}; this.paused=true; }
  addEventListener(type,fn) { (this.handlers[type]??=[]).push(fn); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children=children; }
  setAttribute(k,v) {this.attributes[k]=v;}
  removeAttribute(k) {delete this.attributes[k];}
  hasAttribute(k) {return k in this.attributes;}
  focus(){} scrollIntoView(){} load(){} pause(){this.paused=true;} play(){this.paused=false;return Promise.resolve();} click(){}
}
function harness({storage=new Map(), before, failPath}={}) {
  const elements=new Map(); const get=id=>{ if(!elements.has(id))elements.set(id,new Element());return elements.get(id); };
  get('filter').value='all';get('editor').value='Alice';get('speed').value='1';
  storage.set('taigi-review:editor','Alice');
  storage.delete('taigi-review:key'); // Bootstrap explicitly after each test configures the mock server.
  const rows=Array.from({length:3},(_,i)=>({id:`taigi-${String(768192+i).padStart(8,'0')}`,position:i,original:'A',annotation:'A',status:'unreviewed',revision:0,updated_by:null,updated_at:null,duration:1}));
  let seq=0; const calls=[]; const intervals=[]; const tools=[];
  let failing=failPath;
  const response=body=>new Response(JSON.stringify(body),{headers:{'Content-Type':'application/json'}});
  const fetch=async(url,init={})=>{
    const path=new URL(url).pathname; const call={path,method:init.method||'GET',body:init.body&&JSON.parse(init.body)};calls.push(call);
    if(failing===path)throw new Error('Offline');
    if(call.method==='PUT') {
      const row=rows.find(r=>path.endsWith(r.id)); const p=call.body;
      if(row.revision!==p.revision && (row.annotation!==p.annotation||row.status!==p.status)) return new Response(JSON.stringify({error:'Conflict',clip:{...row}}),{status:409});
      if(row.revision===p.revision) {row.annotation=p.annotation;row.status=p.status;row.revision++;row.updated_by=p.editor;seq++;}
      const result=response({clip:{...row}});if(before)await before(call);return result;
    }
    if(before)await before(call);
    if(path==='/api/meta')return response({stats:{total:3,reviewed:rows.filter(r=>r.status==='reviewed').length,flagged:0,corrected:rows.filter(r=>r.annotation!=='A').length},sequence:seq});
    if(path==='/api/clips')return response({clips:rows,total:3,offset:0});
    if(path==='/api/changes')return response({clips:rows.filter(r=>r.revision>0),sequence:seq});
    if(path.endsWith('/audio'))return new Response(new Uint8Array([1,2,3]));
    if(path.endsWith('/history'))return response({history:[]});
    const row=rows.find(r=>path.endsWith(r.id));if(row)return response({clip:row});
    throw new Error('Unexpected test request '+path);
  };
  const window=new Element();const document=new Element();document.hidden=false;
  document.getElementById=get;document.createElement=()=>new Element();document.createTextNode=text=>({textContent:text});document.modelContext={registerTool(tool){tools.push(tool);}};
  const context=vm.createContext({document,window,location:{hash:''},history:{replaceState(){}},navigator:{clipboard:{writeText:async()=>{}}},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},fetch,URL,URLSearchParams,Response,Blob,AbortController,AbortSignal,console,setTimeout:()=>1,clearTimeout(){},setInterval:fn=>intervals.push(fn)});
  vm.runInContext(script+`\nthis.api={start,openClip,flush,poll,draft,read:()=>({current,conflicting,dirty:dirty(),navigating,ready,base:draftBaseRevision}),edit:text=>{annotation.value=text;onEdit();},setKey:()=>{accessKey='test-only';}};`,context);
  context.api.setKey();
  return {api:context.api,elements,get,storage,rows,calls,intervals,tools,setFailure(value){failing=value;}};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
test('a restored stale draft preserves its base revision across editing and reopening',async()=>{
  const h=harness();h.rows[0].annotation='Shared';h.rows[0].revision=1;
  h.storage.set('taigi-review:draft:taigi-00768192',JSON.stringify({id:h.rows[0].id,annotation:'Draft',status:'unreviewed',revision:0}));
  await h.api.start();assert.ok(h.api.read().conflicting);
  h.api.edit('Draft revised');h.api.draft();assert.equal(JSON.parse(h.storage.get('taigi-review:draft:taigi-00768192')).revision,0);
  const second=harness({storage:new Map(h.storage)});second.rows[0].annotation='Shared';second.rows[0].revision=1;await second.api.start();
  assert.ok(second.api.read().conflicting);await second.api.poll();assert.equal(second.calls.filter(c=>c.method==='PUT').length,0);
});
test('navigation locks the editor through a pending save and only opens one requested clip',async()=>{
  const saveGate=deferred(),loadGate=deferred();let gate=false;
  const h=harness({before:call=>gate?(call.method==='PUT'?saveGate.promise:call.path==='/api/clips/taigi-00768193'?loadGate.promise:undefined):undefined});
  await h.api.start();h.api.edit('B');gate=true;
  const saving=h.api.flush();const first=h.api.openClip(h.rows[1].id);const second=h.api.openClip(h.rows[2].id);
  assert.equal(h.api.read().navigating,true);assert.equal(h.get('annotation').disabled,true);assert.equal(await second,false);
  saveGate.resolve();await saving;await settle();assert.equal(h.get('annotation').disabled,true);
  loadGate.resolve();assert.equal(await first,true);assert.equal(h.api.read().current.id,h.rows[1].id);
  assert.equal(h.calls.filter(c=>c.path==='/api/clips/taigi-00768194').length,0);
});
test('reverting during a lost save response retains the intended text and surfaces a conflict',async()=>{
  const gate=deferred();let pending=false;
  const h=harness({before:c=>pending&&c.method==='PUT'?gate.promise:undefined});await h.api.start();
  h.api.edit('B');pending=true;const saving=h.api.flush();h.api.edit('A');
  assert.equal(JSON.parse(h.storage.get('taigi-review:draft:taigi-00768192')).annotation,'A');
  gate.reject(new Error('Response lost'));assert.equal(await saving,false);pending=false;await h.api.poll();
  assert.equal(h.get('annotation').value,'A');assert.ok(h.api.read().conflicting);
});
test('reverting during a successful pending save follows up against its new revision',async()=>{
  const gate=deferred();let first=true;
  const h=harness({before:c=>{if(c.method==='PUT'&&first){first=false;return gate.promise;}}});await h.api.start();
  h.api.edit('B');const saving=h.api.flush();h.api.edit('A');gate.resolve();assert.equal(await saving,true);
  const writes=h.calls.filter(c=>c.method==='PUT');assert.deepEqual(writes.map(c=>[c.body.annotation,c.body.revision]),[['B',0],['A',1]]);
  assert.equal(h.rows[0].annotation,'A');assert.equal(h.api.read().dirty,false);
});
for(const path of ['/api/meta','/api/clips'])test(`startup automatically recovers after ${path} failure`,async()=>{
  const h=harness({failPath:path});await h.api.start();assert.equal(h.api.read().ready,false);
  h.setFailure(null);h.intervals[0]();for(let i=0;i<5;i++)await settle();
  assert.equal(h.api.read().ready,true);assert.equal(h.get('annotation').value,'A');
});
test('optional tool contracts register, save through the editor, and reject invalid input',async()=>{
  const h=harness();await h.api.start();assert.deepEqual(h.tools.map(t=>t.name),['read_current_taigi_clip','save_taigi_annotation']);
  const read=h.tools[0],save=h.tools[1];assert.equal(read.annotations.readOnlyHint,true);assert.equal(read.execute({}).annotation,'A');
  const result=await save.execute({id:h.rows[0].id,annotation:'Corrected',status:'reviewed',editor:'Bob'});
  assert.equal(result.saved,true);assert.equal(h.get('annotation').value,'Corrected');assert.equal(h.rows[0].annotation,'Corrected');
  await assert.rejects(save.execute({id:h.rows[0].id,annotation:42,status:'reviewed',editor:'Bob'}));
  assert.equal(h.rows[0].revision,1);
});
