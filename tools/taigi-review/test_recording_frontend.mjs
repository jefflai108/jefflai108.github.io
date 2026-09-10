import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import {webcrypto} from 'node:crypto';
import ts from 'typescript';
const source=readFileSync(new URL('../../src/scripts/taigi-recordings.ts',import.meta.url),'utf8').replace("import { reviewSession } from './taigi-session';",'');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
class Element{
  constructor(){this.value='';this.hidden=false;this.disabled=false;this.children=[];this.dataset={};this.handlers={};this.attributes={};this.paused=true;}
  addEventListener(type,fn){(this.handlers[type]??=[]).push(fn);}
  async emit(type,e={}){for(const fn of this.handlers[type]||[])await fn(e);}
  setAttribute(k,v){this.attributes[k]=v;}removeAttribute(k){delete this.attributes[k];}hasAttribute(k){return k in this.attributes;}
  replaceChildren(...nodes){this.children=nodes;}append(...nodes){this.children.push(...nodes);}focus(){}load(){}pause(){this.paused=true;}play(){this.paused=false;return Promise.resolve();}click(){}
}
function defer(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};}
function setup({store=new Map(),storage=new Map(),media,brokenRecorder=false}={}){
  const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  get('rec-status').value='unreviewed';storage.set('taigi-review:editor','Alice');
  const document=new Element(),window=new Element();document.hidden=false;document.getElementById=get;document.createElement=()=>new Element();window.confirm=()=>true;
  const indexedDB={open(){const request={};setImmediate(()=>{request.result={transaction(){const tx={};tx.objectStore=()=>({getAll:()=>operation(()=>[...store.values()]),put:value=>operation(()=>{store.set(value.id,structuredClone(value));}),delete:key=>operation(()=>{store.delete(key);})});function operation(action){const req={};setImmediate(()=>{req.result=action();req.onsuccess?.();setImmediate(()=>tx.oncomplete?.());});return req;}return tx;}};request.onsuccess();});return request;}};window.indexedDB=indexedDB;
  const track={stops:0,stop(){this.stops++;}};const stream={getTracks:()=>[track]};let recorderCount=0,lastRecorder;
  class Recorder{static isTypeSupported(){return true;}constructor(){recorderCount++;if(brokenRecorder)throw new Error('Constructor failed');this.mimeType='audio/webm;codecs=opus';this.state='inactive';lastRecorder=this;}start(){this.state='recording';}stop(){this.state='inactive';this.ondataavailable?.({data:new Blob([new Uint8Array(128)],{type:this.mimeType})});this.onstop?.();}}
  const rows=new Map(),calls=[];let fail=false;
  const fetch=async(url,init={})=>{const path=new URL(url).pathname;const body=init.body&&JSON.parse(init.body);calls.push({path,method:init.method||'GET',body});if(fail)throw new Error('Offline');
    let result;
    if(init.method==='POST'){const existing=rows.get(body.id);if(existing)result={recording:{...existing},created:false};else{const row={id:body.id,title:body.title||'Taigi take',annotation:body.annotation,status:body.status,duration:1,created_by:body.editor,updated_by:body.editor,created_at:'2026-09-08',updated_at:'2026-09-08',revision:0};rows.set(body.id,row);result={recording:{...row},created:true};}}
    else if(init.method==='PUT'){const id=path.split('/').at(-1);const row=rows.get(id);if(row.revision!==body.revision)return new Response(JSON.stringify({error:'Conflict',recording:row}),{status:409});Object.assign(row,{annotation:body.annotation,status:body.status,revision:row.revision+1,updated_by:body.editor});result={recording:{...row}};}
    else if(path==='/api/recordings')result={recordings:[...rows.values()],total:rows.size};
    else if(path.endsWith('/audio'))return new Response(new Blob([new Uint8Array(128)],{type:'audio/wav'}));
    else if(path.endsWith('/history'))result={history:[]};
    else result={recording:rows.get(path.split('/').at(-1))};
    return new Response(JSON.stringify(result),{headers:{'Content-Type':'application/json'}});
  };
  const session={activeTab:'record',key:()=> 'test',ready:()=>true,leaveDev:async()=>true,selectDev:async()=>true};
  const context=vm.createContext({reviewSession:session,document,window,indexedDB,MediaRecorder:Recorder,navigator:{mediaDevices:{getUserMedia:media||(async()=>stream)}},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},fetch,URL,URLSearchParams,Blob,Response,AbortSignal,crypto:webcrypto,performance:{now:()=>1000},btoa,console,setTimeout:()=>1,clearTimeout(){},setInterval:()=>1,clearInterval(){}});
  vm.runInContext(code+`\nthis.api={startRecording,stopRecording,saveAll,openRecording,refreshLocal,persistAnnotation,switchTab,read:()=>({capture,take,current,conflict,base,dirty:dirty()}),edit:value=>{text.value=value;onEdit();},persist:()=>persistChain};`,context);
  return{api:context.api,document,window,get,store,storage,track,stream,rows,calls,session,setFail(value){fail=value;},get recorderCount(){return recorderCount;}};
}
async function take(h){await h.api.startRecording();assert.equal(h.api.read().capture,'recording');h.api.stopRecording();await h.api.persist();assert.ok(h.api.read().take);}
test('record, stop mic, annotate, upload, and save a shared correction',async()=>{
  const h=setup();await take(h);assert.equal(h.track.stops,1);h.api.edit('逐家好');await h.api.persist();assert.equal(h.store.size,1);
  assert.equal(await h.api.saveAll(),true);assert.equal(h.store.size,0);assert.equal(h.rows.size,1);assert.equal(h.api.read().current.annotation,'逐家好');
  h.api.edit('逐家好，咱來講台語');assert.equal(await h.api.saveAll(),true);assert.equal(h.api.read().current.revision,1);assert.equal(h.api.read().dirty,false);
});
test('failed upload retains recoverable audio and transcript',async()=>{
  const h=setup();await take(h);h.api.edit('一段台語');h.setFail(true);assert.equal(await h.api.saveAll(),false);assert.equal(h.store.size,1);
  const second=setup({store:h.store});await second.api.refreshLocal();const card=second.get('rec-local-list').children[0];assert.ok(card);
  await card.children[0].emit('click');assert.equal(second.get('rec-transcript').value,'一段台語');assert.ok(second.api.read().take.blob.size);
  assert.equal(await second.api.saveAll(),true);assert.equal(second.rows.size,1);
});
test('permission resolving after page becomes hidden stops its tracks without recording',async()=>{
  const permission=defer();const h=setup({media:()=>permission.promise});const start=h.api.startRecording();h.document.hidden=true;await h.document.emit('visibilitychange');permission.resolve(h.stream);await start;
  assert.equal(h.recorderCount,0);assert.equal(h.track.stops,1);assert.equal(h.api.read().capture,'idle');
});
test('recorder construction failure releases microphone',async()=>{
  const h=setup({brokenRecorder:true});await h.api.startRecording();assert.equal(h.track.stops,1);assert.equal(h.api.read().capture,'idle');
});
test('restored stale annotation keeps its draft and base revision',async()=>{
  const h=setup();const row={id:'rec-11111111-1111-4111-8111-111111111111',title:'Shared take',annotation:'Their version',status:'reviewed',duration:1,revision:1,created_by:'Alice',updated_by:'Bob'};h.rows.set(row.id,row);
  h.storage.set(`taigi-review:record-draft:${row.id}`,JSON.stringify({annotation:'My version',status:'unreviewed',revision:0}));await h.api.openRecording(row);
  assert.equal(h.get('rec-transcript').value,'My version');assert.ok(h.api.read().conflict);h.api.persistAnnotation();assert.equal(JSON.parse(h.storage.get(`taigi-review:record-draft:${row.id}`)).revision,0);
});
test('duplicate upload with different revision-zero annotation requires explicit comparison',async()=>{
  const h=setup();await take(h);const draft=h.api.read().take;h.api.edit('My initial words');h.rows.set(draft.id,{id:draft.id,title:'Shared take',annotation:'Other initial words',status:'unreviewed',duration:1,revision:0,created_by:'Bob',updated_by:'Bob'});
  assert.equal(await h.api.saveAll(),false);assert.ok(h.api.read().conflict);assert.equal(h.get('rec-transcript').value,'My initial words');assert.equal(h.calls.filter(c=>c.method==='PUT').length,0);
  const stored=JSON.parse(h.storage.get(`taigi-review:record-draft:${draft.id}`));assert.equal(stored.conflict,true);
  const reopened=setup({storage:new Map(h.storage)});reopened.rows.set(draft.id,h.rows.get(draft.id));await reopened.api.openRecording(h.rows.get(draft.id));assert.ok(reopened.api.read().conflict);
});


test('three tabs preserve recording drafts and block leaving an active microphone',async()=>{
  const h=setup();let chosen=[];h.session.selectDev=async tab=>{chosen.push(tab);return true;};
  await h.api.startRecording();await h.api.switchTab('dev2');assert.equal(h.session.activeTab,'record');
  h.api.stopRecording();await h.api.persist();await h.api.switchTab('dev2');
  assert.equal(h.session.activeTab,'dev2');assert.deepEqual(chosen,['dev2']);
  assert.equal(h.get('dev-panel').hidden,false);assert.equal(h.get('record-panel').hidden,true);
  assert.equal(h.get('tab-dev2').attributes['aria-selected'],'true');assert.equal(h.store.size,1);
  await h.api.switchTab('dev');assert.equal(h.session.activeTab,'dev');
  h.session.leaveDev=async()=>false;await h.api.switchTab('record');assert.equal(h.session.activeTab,'dev');
  h.session.leaveDev=async()=>true;await h.api.switchTab('record');assert.equal(h.session.activeTab,'record');
  assert.equal(h.get('dev-panel').hidden,true);assert.equal(h.get('export').hidden,true);
});
