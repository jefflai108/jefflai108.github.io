import { reviewSession } from './taigi-session';
type Status = 'unreviewed' | 'reviewed' | 'flagged';
type Recording = { id:string; title:string; annotation:string; status:Status; duration:number; created_by:string; created_at:string; updated_by:string; updated_at:string; revision:number };
type Take = { id:string; blob:Blob; title:string; annotation:string; status:Status; editor:string; createdAt:number };
const API='https://taigi-review-api.heymachi.live';
const el=<T extends HTMLElement=HTMLElement>(id:string)=>document.getElementById(id) as T;
const inp=(id:string)=>el<HTMLInputElement>(id);
const btn=(id:string)=>el<HTMLButtonElement>(id);
const text=el<HTMLTextAreaElement>('rec-transcript');
const player=el<HTMLAudioElement>('rec-audio');
const status=el<HTMLSelectElement>('rec-status');
const names={unreviewed:'Needs review',reviewed:'Reviewed',flagged:'Needs another listen'};
const read=(key:string)=>{try{return localStorage.getItem(`taigi-review:${key}`);}catch{return null;}};
const write=(key:string,value:string)=>{try{localStorage.setItem(`taigi-review:${key}`,value);}catch{}};
const remove=(key:string)=>{try{localStorage.removeItem(`taigi-review:${key}`);}catch{}};
let current:Recording|null=null, take:Take|null=null, conflict:Recording|null=null;
let base=0, uncertain=false, composing=false, moving=false, switching=false, saving:Promise<boolean>|null=null;
let capture:'idle'|'requesting'|'recording'|'stopping'='idle', recorder:MediaRecorder|null=null, stream:MediaStream|null=null;
let generation=0, started=0, ticker:ReturnType<typeof setInterval>|undefined, autoStop:ReturnType<typeof setTimeout>|undefined;
let objectURL:string|null=null, audioToken=0, saveTimer:ReturnType<typeof setTimeout>|undefined, listTimer:ReturnType<typeof setTimeout>|undefined;
let page=0,total=0,items:Recording[]=[],listToken=0,polling=false,loaded=false;
let pendingTakes:Take[]=[];
let idb:Promise<IDBDatabase>|null=null, persistChain:Promise<unknown>=Promise.resolve();
inp('rec-name').value=read('editor')||'';
function message(value=''){el('rec-notice').textContent=value;el('rec-notice').hidden=!value;}
function saveState(value:string,state='saved'){el('rec-save-state').textContent=value;el('rec-save-state').dataset.state=state;}
function dirty(){return !!current&&(uncertain||text.value!==current.annotation||status.value!==current.status);}
function active(){return reviewSession.activeTab==='record';}
function blocked(){return capture!=='idle'||moving||!!saving;}
function db(){
  if(!idb)idb=new Promise((resolve,reject)=>{
    if(!('indexedDB' in window)){reject(new Error('Local audio recovery is unavailable'));return;}
    const request=indexedDB.open('taigi-recording-drafts',1);
    request.onupgradeneeded=()=>request.result.createObjectStore('takes',{keyPath:'id'});
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
  });
  return idb;
}
async function localTakes(mode:'list'|'put'|'delete',value?:Take|string):Promise<any>{
  const database=await db();return new Promise((resolve,reject)=>{
    const transaction=database.transaction('takes',mode==='list'?'readonly':'readwrite');const store=transaction.objectStore('takes');
    const request=mode==='list'?store.getAll():mode==='put'?store.put(value):store.delete(value as string);
    let result:any;request.onsuccess=()=>{result=request.result;};
    transaction.oncomplete=()=>resolve(result);transaction.onerror=()=>reject(transaction.error);transaction.onabort=()=>reject(transaction.error);
  });
}
function persistTake(){
  if(!take)return persistChain;
  const snapshot={...take,title:inp('rec-title').value,annotation:text.value,status:status.value as Status,editor:inp('rec-name').value};
  take=snapshot;
  persistChain=persistChain.catch(()=>{}).then(()=>localTakes('put',snapshot)).catch(()=>{message('Local recovery is unavailable in this browser. Keep this page open until the recording is saved, or download the audio.');});
  return persistChain;
}
function persistAnnotation(){
  if(!current)return;
  if(dirty())write(`record-draft:${current.id}`,JSON.stringify({annotation:text.value,status:status.value,revision:base,uncertain,conflict:!!conflict}));
  else remove(`record-draft:${current.id}`);
}
function controls(){
  const busy=blocked();
  btn('rec-start').disabled=busy||!!take||!!current||!reviewSession.key();
  btn('rec-start').hidden=capture==='recording'||capture==='stopping';
  btn('rec-stop').hidden=capture!=='recording'&&capture!=='stopping';btn('rec-stop').disabled=capture!=='recording';
  btn('rec-save').disabled=busy||composing||!!conflict||(!take&&!current);
  btn('rec-save').textContent=current?'Save transcript':'Save recording & transcript →';
  btn('rec-new').disabled=busy;btn('rec-discard').disabled=busy;
  btn('rec-discard').hidden=!take;inp('rec-title').disabled=busy||!!current;inp('rec-name').disabled=busy;
  text.disabled=moving||!!saving;status.disabled=moving||!!saving||composing;
  el('rec-capture').hidden=!!take||!!current;el('rec-playback').hidden=!take&&!current;
  el('rec-history').hidden=!current;
  btn('rec-list-prev').disabled=page===0||moving;btn('rec-list-next').disabled=(page+1)*30>=total||moving;
  el('rec-capture').dataset.recording=String(capture==='recording');
}
class APIError extends Error{constructor(public code:number,public body:any){super(body.error||'The recording could not be saved');}}
async function request(path:string,body?:unknown,method?:string){
  const response=await fetch(API+path,{method:method||(body?'PUT':'GET'),headers:{Authorization:`Bearer ${reviewSession.key()}`,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,cache:'no-store',signal:AbortSignal.timeout(method==='POST'?120000:15000)});
  if(!response.ok)throw new APIError(response.status,await response.json().catch(()=>({error:'The Mac is unavailable. Keep this take and retry when it is online.'})));
  return response;
}
async function json(path:string,body?:unknown,method?:string){return(await request(path,body,method)).json();}
function errorMessage(error:unknown){message(error instanceof APIError?error.message:'Could not reach the shared workspace. Your take or transcript is still here; please retry when the Mac is online.');}
function metadata(){
  if(current){el('rec-kicker').textContent=`RECORDED BY ${current.created_by}`;el('rec-heading').textContent=current.title;el('rec-badge').textContent=names[status.value as Status];el('rec-revision').textContent=`Revision ${current.revision}`;}
  else{el('rec-kicker').textContent='NEW RECORDING';el('rec-heading').textContent=take?'Your take is ready.':'Make a little room for Taigi.';el('rec-badge').textContent=take?'Not uploaded yet':capture==='recording'?'Recording…':'Ready to record';el('rec-revision').textContent='';}
}
function audioBlob(blob:Blob){if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(blob);player.src=objectURL;player.load();}
async function loadAudio(record:Recording){
  const token=++audioToken;player.pause();player.removeAttribute('src');player.load();
  el('rec-audio-message').textContent='Loading saved audio…';el('rec-audio-retry').hidden=true;
  try{const blob=await(await request(`/api/recordings/${record.id}/audio`)).blob();if(token!==audioToken)return;audioBlob(blob);el('rec-audio-message').textContent='Saved recording · ready to play';el('rec-audio-detail').textContent=`${record.duration.toFixed(1)} SEC`;}
  catch{if(token===audioToken){el('rec-audio-message').textContent='Audio could not be loaded.';el('rec-audio-retry').hidden=false;}}
}
function stopTracks(){stream?.getTracks().forEach(track=>track.stop());stream=null;clearInterval(ticker);clearTimeout(autoStop);}
function stopRecording(){
  if(capture!=='recording'||!recorder)return;
  capture='stopping';controls();clearInterval(ticker);clearTimeout(autoStop);
  try{recorder.stop();}catch{stopTracks();capture='idle';controls();message('The recorder stopped unexpectedly. Please try a new take.');}
}
async function startRecording(){
  if(blocked()||take||current)return;
  if(!reviewSession.key()){message('Open your private review invitation before recording.');return;}
  if(!inp('rec-name').value.trim()){message('Enter your name above, then press Start recording.');inp('rec-name').focus();return;}
  if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==='undefined'){message('Microphone recording is unavailable in this browser. Open this HTTPS page in an updated Safari or Chrome.');return;}
  const token=++generation;capture='requesting';controls();message('Allow microphone access in your browser to begin.');
  try{
    const acquired=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:false,noiseSuppression:false,autoGainControl:false},video:false});
    if(token!==generation){acquired.getTracks().forEach(track=>track.stop());return;}
    if(!active()||document.hidden){acquired.getTracks().forEach(track=>track.stop());capture='idle';controls();return;}
    stream=acquired;player.pause();
    const mime=['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus'].find(type=>MediaRecorder.isTypeSupported(type));
    recorder=new MediaRecorder(acquired,{...(mime?{mimeType:mime}:{}),audioBitsPerSecond:128000});
    const chunks:Blob[]=[];const running=recorder;let recorderFailed=false;
    running.ondataavailable=event=>{if(event.data.size)chunks.push(event.data);};
    running.onerror=()=>{recorderFailed=true;message('Microphone recording was interrupted. Any captured audio will be kept for you to replay.');stopTracks();try{if(running.state!=='inactive')running.stop();}catch{capture='idle';controls();}};
    running.onstop=()=>{
      stopTracks();recorder=null;capture='idle';
      const blob=new Blob(chunks,{type:running.mimeType||mime||chunks[0]?.type||'audio/webm'});
      if(!blob.size){message('No audio was captured. Check your microphone and try again.');controls();return;}
      take={id:`rec-${crypto.randomUUID()}`,blob,title:inp('rec-title').value,annotation:text.value,status:status.value as Status,editor:inp('rec-name').value,createdAt:Date.now()};
      audioBlob(blob);el('rec-audio-message').textContent='Preview your take before saving';el('rec-audio-detail').textContent=`${Math.min(120,(performance.now()-started)/1000).toFixed(1)} SEC`;
      saveState('Not uploaded yet — save the recording when you’re ready.','pending');metadata();controls();void persistTake().then(refreshLocal);
      if(!recorderFailed)message();
    };
    running.start(250);started=performance.now();capture='recording';el('rec-timer').textContent='0:00';el('rec-instruction').textContent='Recording your Taigi…';message();controls();
    ticker=setInterval(()=>{const seconds=Math.floor((performance.now()-started)/1000);el('rec-timer').textContent=`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;},200);
    autoStop=setTimeout(()=>{stopRecording();message('Two minutes reached. Your recording is ready to annotate.');},120000);
  }catch(error){if(token!==generation)return;stopTracks();recorder=null;capture='idle';controls();const name=(error as DOMException).name;message(name==='NotAllowedError'?'Microphone access was denied. Allow the microphone for this site in your browser settings, then try again.':name==='NotFoundError'?'No microphone was found. Connect a microphone and try again.':'The microphone could not be started. Check that it is available and try again.');}
}
function showConflict(record:Recording){conflict=record;el('rec-conflict').hidden=false;el('rec-conflict-text').textContent=record.annotation||'(No speech)';el('rec-conflict-author').textContent=`Saved by ${record.updated_by} · revision ${record.revision}`;saveState('Not saved — compare the shared transcript below.','error');controls();}
function accept(record:Recording){current=record;base=record.revision;uncertain=false;conflict=null;text.value=record.annotation;status.value=record.status;inp('rec-title').value=record.title;el('rec-conflict').hidden=true;persistAnnotation();metadata();controls();saveState(`Saved to shared recordings · ${record.updated_by}`);}
async function base64(blob:Blob){const bytes=new Uint8Array(await blob.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));return btoa(binary);}
async function saveAll():Promise<boolean>{
  clearTimeout(saveTimer);
  if(saving){if(!(await saving))return false;return saveAll();}
  if(composing||conflict||capture!=='idle')return false;
  if(!take&&!dirty())return true;
  if(!inp('rec-name').value.trim()){saveState('Enter your name above to save.','pending');return false;}
  const localTake=take;const rid=current?.id;const submitted={annotation:text.value,status:status.value as Status,revision:base,editor:inp('rec-name').value.trim()};
  if(current)uncertain=true;persistAnnotation();
  saveState(take?'Uploading your recording…':'Saving transcript…','pending');
  saving=(async()=>{
    try{
      if(localTake)await persistTake();
      if(localTake){
        const data=await json('/api/recordings',{id:localTake.id,title:inp('rec-title').value,annotation:submitted.annotation,status:submitted.status,editor:submitted.editor,mime:localTake.blob.type,audio_base64:await base64(localTake.blob)},'POST');
        current=data.recording;base=current!.revision;take=null;uncertain=false;
        // A retry may return a recording someone has already annotated.
        if(!data.created&&(text.value!==current!.annotation||status.value!==current!.status)){base=0;showConflict(current!);}
        persistAnnotation();
        await persistChain;try{await localTakes('delete',localTake.id);}catch{}
        await refreshLocal();inp('rec-title').value=current!.title;void loadAudio(current!);
      }else if(rid){
        const data=await json(`/api/recordings/${rid}`,submitted);current=data.recording;base=current!.revision;uncertain=false;persistAnnotation();
      }
      if(!conflict)saveState(dirty()?'More changes waiting to save…':'✓ Saved to shared recordings',dirty()?'pending':'saved');
      metadata();if(!conflict)message();void refreshLibrary().catch(()=>{});if(el<HTMLDetailsElement>('rec-history').open)void loadHistory();
      return !conflict;
    }catch(error){
      if(error instanceof APIError&&error.code===409&&error.body.recording)showConflict(error.body.recording);
      else{saveState('Not saved — your recording or draft is still here. Retry when connected.','error');errorMessage(error);}
      return false;
    }
  })();controls();const pending=saving;const success=await pending;if(saving===pending)saving=null;controls();
  if(success&&dirty()&&!conflict&&!composing)return saveAll();return success;
}
async function leaveCurrent(){
  if(capture!=='idle'){message('Stop the recording before leaving this take.');return false;}
  if(take){await persistTake();message('Save or discard this take before opening another recording.');return false;}
  if(dirty()||saving)return saveAll();return true;
}
async function openRecording(record:Recording){
  if(moving||current?.id===record.id)return;moving=true;controls();
  try{
    if(!(await leaveCurrent()))return;
    const data=await json(`/api/recordings/${record.id}`);
    const stored=read(`record-draft:${record.id}`);accept(data.recording);
    if(stored){try{const d=JSON.parse(stored);if(typeof d.annotation==='string'&&Object.hasOwn(names,d.status)&&Number.isInteger(d.revision)&&(d.annotation!==current!.annotation||d.status!==current!.status||d.uncertain)){text.value=d.annotation;status.value=d.status;base=d.revision;uncertain=!!d.uncertain;if(base!==current!.revision||d.conflict)showConflict(current!);else saveState('Restored an unsaved transcript — save when ready.','pending');}}catch{}}
    persistAnnotation();metadata();void loadAudio(current!);renderLibrary();if(el<HTMLDetailsElement>('rec-history').open)void loadHistory();
  }catch(error){errorMessage(error);}finally{moving=false;controls();}
}
function reset(){
  current=null;take=null;conflict=null;uncertain=false;base=0;audioToken++;player.pause();player.removeAttribute('src');player.load();
  if(objectURL){URL.revokeObjectURL(objectURL);objectURL=null;}
  text.value='';inp('rec-title').value='';status.value='unreviewed';el('rec-conflict').hidden=true;el('rec-timer').textContent='0:00';el('rec-instruction').textContent='Press record and speak naturally.';
  saveState('Record a clip to get started.');message();metadata();controls();renderLibrary();
}
async function newRecording(){if(blocked())return;moving=true;controls();try{if(await leaveCurrent())reset();}finally{moving=false;controls();}}
async function discardTake(){
  if(!take||blocked())return;
  if(!window.confirm('Discard this unsaved recording and its transcript?'))return;
  moving=true;controls();const id=take.id;
  try{await persistChain;await localTakes('delete',id);reset();await refreshLocal();}catch{message('Could not remove the local take. Please retry.');}finally{moving=false;controls();}
}
async function refreshLocal(){
  try{pendingTakes=(await localTakes('list')).sort((a:Take,b:Take)=>b.createdAt-a.createdAt);}catch{return;}
  const holder=el('rec-local-list');holder.replaceChildren();
  for(const item of pendingTakes){if(item.id===take?.id)continue;const card=document.createElement('div');card.className='local-take';card.textContent=`Unsaved on this browser · ${item.title||new Date(item.createdAt).toLocaleString()}`;const open=document.createElement('button');open.textContent='Recover this take';open.addEventListener('click',async()=>{if(blocked())return;moving=true;controls();try{if(!(await leaveCurrent()))return;reset();take=item;inp('rec-title').value=item.title;inp('rec-name').value=item.editor;text.value=item.annotation;status.value=item.status;audioBlob(item.blob);saveState('Recovered recording — ready to save.','pending');metadata();controls();await refreshLocal();}finally{moving=false;controls();}});card.append(open);holder.append(card);}
}
function renderLibrary(){
  const holder=el('rec-list');holder.replaceChildren();
  for(const record of items){const item=document.createElement('button');item.className='record-item';item.setAttribute('aria-current',String(record.id===current?.id));const title=document.createElement('strong');title.textContent=record.title;const meta=document.createElement('small');meta.textContent=`${record.created_by} · ${record.duration.toFixed(1)}s · ${names[record.status]}`;const subtitle=document.createElement('p');subtitle.lang='nan-TW';subtitle.textContent=record.annotation||'Add a transcript…';item.append(title,meta,subtitle);item.addEventListener('click',()=>{void openRecording(record);});holder.append(item);}
  if(!items.length){const empty=document.createElement('p');empty.className='empty';empty.textContent=inp('rec-search').value?'No recordings match your search.':'Save your first recording to start the collection.';holder.append(empty);}
  el('rec-count').textContent=`${total} saved`;el('rec-list-page').textContent=total?`${page*30+1}–${page*30+items.length} of ${total}`:'0 recordings';controls();
}
async function refreshLibrary(){
  if(!reviewSession.key())return;const token=++listToken;
  const data=await json('/api/recordings?'+new URLSearchParams({q:inp('rec-search').value.trim(),offset:String(page*30)}));
  if(token!==listToken)return;items=data.recordings;total=data.total;loaded=true;renderLibrary();
}
async function loadHistory(){if(!current)return;const id=current.id;try{const data=await json(`/api/recordings/${id}/history`);if(current?.id!==id)return;const holder=el('rec-history-list');holder.replaceChildren();for(const revision of data.history){const item=document.createElement('div');item.className='history-entry';const meta=document.createElement('small');meta.textContent=`Revision ${revision.revision} · ${revision.editor} · ${new Date(revision.saved_at).toLocaleString()}`;const words=document.createElement('p');words.textContent=revision.annotation||'(No transcript)';item.append(meta,words);holder.append(item);}}catch{el('rec-history-list').textContent='History could not be loaded. Close and reopen to retry.';}}
async function poll(){
  if(!active()||document.hidden||blocked()||polling||!reviewSession.key())return;polling=true;
  try{await refreshLibrary();if(current){const id=current.id;const data=await json(`/api/recordings/${id}`);if(blocked()||current?.id!==id)return;const incoming:Recording=data.recording;if(incoming.revision>current.revision){if(dirty()||composing||conflict)showConflict(incoming);else accept(incoming);}if(dirty()&&!conflict&&!composing)await saveAll();}}catch(error){if(!loaded)errorMessage(error);}finally{polling=false;}
}
async function switchTab(tab:'dev'|'dev2'|'record'){
  if(switching||tab===reviewSession.activeTab)return;switching=true;
  try{
    if(tab==='record'&&!(await reviewSession.leaveDev()))return;
    if(tab!=='record'&&reviewSession.activeTab==='record'){
      if(capture==='requesting'){generation++;capture='idle';stopTracks();}
      else if(capture!=='idle'){message('Stop your recording before switching tabs.');return;}
      if(saving&&!(await saving))return;if(dirty()&&!(await saveAll()))return;
      if(take)await persistTake();player.pause();
    }
    if(tab!=='record'&&!(await reviewSession.selectDev(tab)))return;
    reviewSession.activeTab=tab;el('dev-panel').hidden=tab==='record';el('dev-intro').hidden=tab==='record';el('record-panel').hidden=tab!=='record';btn('export').hidden=tab==='record';
    for(const id of ['dev','dev2','record']){el(`tab-${id}`).setAttribute('aria-selected',String(id===tab));el(`tab-${id}`).tabIndex=id===tab?0:-1;}
    controls();if(tab==='record'){void refreshLocal();void refreshLibrary().catch(errorMessage);}
  }finally{switching=false;}
}
const tabs=['dev','dev2','record'] as const;
for(const tab of tabs){btn(`tab-${tab}`).addEventListener('click',()=>{void switchTab(tab);});btn(`tab-${tab}`).addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const index=tabs.indexOf(tab);const target=event.key==='Home'?'dev':event.key==='End'?'record':tabs[(index+(event.key==='ArrowRight'?1:tabs.length-1))%tabs.length];void switchTab(target).then(()=>btn(`tab-${reviewSession.activeTab}`).focus());}});}
function onEdit(){
  if(current&&status.value==='reviewed')status.value='unreviewed';persistAnnotation();if(take)void persistTake();metadata();
  if(!conflict)saveState(current?'Unsaved transcript changes…':take?'Not uploaded yet — save when ready.':'You can write a transcript before recording.','pending');
  clearTimeout(saveTimer);if(current&&!composing&&!conflict)saveTimer=setTimeout(()=>{void saveAll();},800);
}
text.addEventListener('input',onEdit);text.addEventListener('compositionstart',()=>{composing=true;clearTimeout(saveTimer);controls();});text.addEventListener('compositionend',()=>{composing=false;onEdit();controls();});
status.addEventListener('change',()=>{persistAnnotation();if(take)void persistTake();metadata();if(current)void saveAll();});
inp('rec-title').addEventListener('input',()=>{if(take)void persistTake();});inp('rec-name').addEventListener('input',()=>{write('editor',inp('rec-name').value);if(take)void persistTake();});
btn('rec-start').addEventListener('click',()=>{void startRecording();});btn('rec-stop').addEventListener('click',stopRecording);btn('rec-save').addEventListener('click',()=>{void saveAll();});btn('rec-new').addEventListener('click',()=>{void newRecording();});btn('rec-discard').addEventListener('click',()=>{void discardTake();});
btn('rec-use-shared').addEventListener('click',()=>{if(conflict){accept(conflict);message();void refreshLibrary().catch(errorMessage);}});
btn('rec-use-mine').addEventListener('click',()=>{if(conflict){current=conflict;base=conflict.revision;conflict=null;el('rec-conflict').hidden=true;persistAnnotation();void saveAll();}});
inp('rec-search').addEventListener('input',()=>{clearTimeout(listTimer);page=0;listTimer=setTimeout(()=>{void refreshLibrary().catch(errorMessage);},250);});
btn('rec-list-prev').addEventListener('click',()=>{page=Math.max(0,page-1);void refreshLibrary().catch(errorMessage);});btn('rec-list-next').addEventListener('click',()=>{page++;void refreshLibrary().catch(errorMessage);});
el('rec-history').addEventListener('toggle',()=>{if(el<HTMLDetailsElement>('rec-history').open)void loadHistory();});
btn('rec-audio-retry').addEventListener('click',()=>{if(current)void loadAudio(current);});
btn('rec-download').addEventListener('click',async()=>{try{const blob=take?.blob||(current?await(await request(`/api/recordings/${current.id}/audio`)).blob():null);if(!blob)return;const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;const ext=blob.type.includes('mp4')?'m4a':blob.type.includes('webm')?'webm':blob.type.includes('ogg')?'ogg':'wav';a.download=`${take?.id||current?.id}.${ext}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){errorMessage(error);}});
btn('rec-export').addEventListener('click',async()=>{if(dirty()&&!(await saveAll()))return;try{const data=await json('/api/recordings/export');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='taigi-user-recording-transcripts.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){errorMessage(error);}});
player.addEventListener('error',()=>{if(player.hasAttribute('src')){el('rec-audio-message').textContent='Playback failed. Download the audio or retry.';el('rec-audio-retry').hidden=!current;}});
document.addEventListener('keydown',event=>{if(!active()||event.isComposing||composing||moving||capture!=='idle')return;if((event.metaKey||event.ctrlKey)&&(event.key.toLowerCase()==='s'||event.key==='Enter')){event.preventDefault();void saveAll();}if(event.altKey&&event.code==='Space'&&player.hasAttribute('src')){event.preventDefault();if(player.paused)void player.play().catch(()=>{});else player.pause();}});
window.addEventListener('beforeunload',event=>{if(capture!=='idle'||take||dirty()||saving){persistAnnotation();if(take)void persistTake();event.preventDefault();event.returnValue='';}});
window.addEventListener('pagehide',()=>{generation++;if(recorder?.state==='recording')try{recorder.stop();}catch{}stopTracks();});
document.addEventListener('visibilitychange',()=>{if(document.hidden){if(capture==='requesting'){generation++;capture='idle';stopTracks();controls();}if(capture==='recording')stopRecording();persistAnnotation();if(take)void persistTake();}else void poll();});
window.addEventListener('online',()=>{void poll();});setInterval(()=>{if(active()){controls();void poll();}},4000);controls();
