// Public shell; private dataset and one authoritative Mac-hosted SQLite store.
import { reviewSession } from './taigi-session';
type Status = 'unreviewed' | 'reviewed' | 'flagged';
type Clip = { id: string; position: number; original: string; annotation: string; duration: number; status: Status; revision: number; updated_by: string | null; updated_at: string | null };
type Draft = { id: string; annotation: string; status: Status; revision: number; uncertain?: boolean };
const API = 'https://taigi-review-api.heymachi.live';
type ReviewSet = 'dev' | 'dev2';
let reviewSet: ReviewSet = 'dev', datasetRequest = 0, clipCount = 5424;
const setName = () => reviewSet === 'dev2' ? 'Dev2' : 'Dev';
const datasetKey = (key: string) => reviewSet === 'dev' ? key : `dev2:${key}`;
const el = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const input = (id: string) => el<HTMLInputElement>(id);
const button = (id: string) => el<HTMLButtonElement>(id);
const annotation = el<HTMLTextAreaElement>('annotation');
const audio = el<HTMLAudioElement>('audio');
const statusNames = { unreviewed: 'Not reviewed', reviewed: 'Reviewed', flagged: 'Needs another listen' };
const storage = {
  get(key: string) { try { return localStorage.getItem(`taigi-review:${key}`); } catch { return null; } },
  set(key: string, value: string) { try { localStorage.setItem(`taigi-review:${key}`, value); return true; } catch { return false; } },
  remove(key: string) { try { localStorage.removeItem(`taigi-review:${key}`); } catch {} },
};
let accessKey = new URLSearchParams(location.hash.slice(1)).get('key') || storage.get('key') || '';
let current: Clip | null = null;
let desiredStatus: Status = 'unreviewed';
let draftBaseRevision = 0;
let unresolvedSaveIntent = false;
let conflicting: Clip | null = null;
let clips: Clip[] = [];
let offset = 0, total = 0, sequence = 0;
let saveTimer: ReturnType<typeof setTimeout> | undefined;
let queueTimer: ReturnType<typeof setTimeout> | undefined;
let inFlight: Promise<boolean> | null = null;
let navigating = false, polling = false, composing = false, ready = false, initializing = false, reviewing = false;
let queueRequest = 0, selectionRequest = 0, audioRequest = 0;
let audioURL: string | null = null;
const audioCache = new Map<string, Blob>();
reviewSession.key = () => accessKey;
reviewSession.ready = () => ready;
reviewSession.leaveDev = async () => {
  if (navigating || composing || reviewing || initializing) return false;
  if (current && !(await flush())) return false;
  audio.pause();
  return true;
};
reviewSession.selectDev = async (tab: ReviewSet) => {
  if (tab === reviewSet) return true;
  if (!(await reviewSession.leaveDev())) return false;
  clearTimeout(saveTimer); clearTimeout(queueTimer);
  datasetRequest++; queueRequest++; selectionRequest++; audioRequest++;
  reviewSet = tab; ready = false; current = null; conflicting = null;
  clips = []; offset = 0; total = 0; sequence = 0;
  unresolvedSaveIntent = false; draftBaseRevision = 0;
  clipCount = tab === 'dev2' ? 5133 : 5424;
  annotation.value = ''; el<HTMLTextAreaElement>('original').value = '';
  input('search').value = ''; el<HTMLSelectElement>('filter').value = 'all';
  el('conflict').hidden = true; el('history-list').replaceChildren();
  el('clip-id').textContent = `Loading ${setName()} clips…`;
  el('clip-position').textContent = `${setName().toUpperCase()} CLIP`;
  el('clip-status').textContent = ''; el('change-label').textContent = ''; el('revision-label').textContent = '';
  el('duration').textContent = 'MAC-HOSTED AUDIO';
  audio.removeAttribute('src'); audio.load();
  if (audioURL) { URL.revokeObjectURL(audioURL); audioURL = null; }
  button('replay').disabled = true; button('back-five').disabled = true;
  el('audio-retry').hidden = true; el('audio-message').textContent = 'Audio loads when you open a clip.';
  el('dataset-source').textContent = `Taigi ${setName()} · HF ${tab === 'dev2' ? 'validation2' : 'validation'} split · ${clipCount.toLocaleString()} clips`;
  el('dev-panel').setAttribute('aria-labelledby', `tab-${tab}`);
  savedLabel(`Loading ${setName()} review…`, 'pending');
  renderQueue(); pendingProgress('Loading shared progress…');
  el('workspace').setAttribute('aria-busy', 'true');
  void start();
  return true;
};
input('editor').value = storage.get('editor') || '';
el<HTMLSelectElement>('speed').value = storage.get('speed') || '1';

function notice(message = '') { el('notice').textContent = message; el('notice').hidden = !message; }
function savedLabel(message: string, state = 'saved') { el('save-status').textContent = message; el('save-status').dataset.state = state; }
function connected(ok: boolean) { el('connection').textContent = ok ? 'Shared review connected' : 'Reconnecting…'; el('connection').classList.toggle('online', ok); }
function dirty() { return !!current && (unresolvedSaveIntent || annotation.value !== current.annotation || desiredStatus !== current.status); }
function draft() {
  if (!current) return;
  if (dirty()) storage.set(datasetKey(`draft:${current.id}`), JSON.stringify({ id: current.id, annotation: annotation.value, status: desiredStatus, revision: draftBaseRevision, uncertain: unresolvedSaveIntent }));
  else storage.remove(datasetKey(`draft:${current.id}`));
}
function updateActions() {
  for (const id of ['save', 'flag', 'review-next', 'previous', 'next']) button(id).disabled = !current || navigating || !!conflicting || composing;
  if (current) {
    button('previous').disabled ||= current.position === 0;
    button('next').disabled ||= current.position >= clipCount - 1;
  }
  annotation.disabled = !current || navigating;
  button('queue-prev').disabled = !ready || navigating || offset === 0;
  button('queue-next').disabled = !ready || navigating || offset + clips.length >= total;
}
class ApiError extends Error { constructor(public status: number, public body: any) { super(body.error || 'Request failed'); } }
async function request(path: string, init: RequestInit = {}, selected: ReviewSet = reviewSet) {
  const route = selected === 'dev2' ? path.replace(/^\/api\//, '/api/dev2/') : path;
  const response = await fetch(API + route, { ...init, cache: 'no-store', headers: { Authorization: `Bearer ${accessKey}`, ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...init.headers }, signal: AbortSignal.timeout(15000) });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: 'The Mac is unavailable. Keep this page open and retry when it is online.' }));
    throw new ApiError(response.status, body);
  }
  return response;
}
async function json(path: string, init: RequestInit = {}) { return (await request(path, init)).json(); }
function fail(error: unknown) {
  connected(false);
  if (error instanceof ApiError && error.status === 401) { el('access-panel').hidden = false; notice(error.message); }
  else notice(error instanceof ApiError ? error.message : 'The Mac is offline or the connection was interrupted. Keep your draft here; saving will retry when the connection returns.');
}
function updateStats(stats: { total: number; reviewed: number; flagged: number; corrected: number }) {
  clipCount = stats.total;
  const label = el('progress-label'); label.replaceChildren(document.createTextNode(stats.reviewed.toLocaleString() + ' '));
  const span = document.createElement('span'); span.textContent = `/ ${stats.total.toLocaleString()} reviewed`; label.append(span);
  el<HTMLProgressElement>('progress').value = stats.reviewed;
  el<HTMLProgressElement>('progress').max = stats.total;
  el('progress').hidden = false;
  el('progress-detail').textContent = `${stats.corrected.toLocaleString()} changed · ${stats.flagged.toLocaleString()} flagged · one shared copy`;
}
function pendingProgress(message: string) {
  el('progress-label').replaceChildren(document.createTextNode('—'));
  el('progress').hidden = true;
  el('progress-detail').textContent = message;
}
async function refreshStats() { const token = datasetRequest; const data = await json('/api/meta'); if (token === datasetRequest) updateStats(data.stats); return data; }
function renderQueue() {
  const list = el('clip-list'); list.replaceChildren();
  for (const clip of clips) {
    const item = document.createElement('button'); item.className = 'clip-item'; item.type = 'button';
    item.setAttribute('aria-current', String(current?.id === clip.id));
    item.setAttribute('aria-label', `${clip.id}, ${statusNames[clip.status]}`);
    const top = document.createElement('span'); top.className = 'clip-item-top';
    const id = document.createElement('span'); id.textContent = clip.id;
    const state = document.createElement('span'); state.className = 'clip-dot'; state.textContent = clip.status === 'reviewed' ? '✓' : clip.status === 'flagged' ? '⚑' : '○'; state.title = statusNames[clip.status];
    top.append(id, state);
    const text = document.createElement('span'); text.className = 'clip-item-text'; text.lang = 'nan-TW'; text.textContent = clip.annotation || '(No speech)';
    item.append(top, text); item.addEventListener('click', () => { void openClip(clip.id); }); list.append(item);
  }
  if (!clips.length) { const p = document.createElement('p'); p.className = 'empty'; p.textContent = 'No clips match this search or filter.'; list.append(p); }
  el('queue-count').textContent = `${total.toLocaleString()} clips`;
  el('queue-page').textContent = total ? `${offset + 1}–${offset + clips.length} of ${total.toLocaleString()}` : '0 clips';
  updateActions();
}
async function refreshQueue(): Promise<void> {
  const token = ++queueRequest;
  const params = new URLSearchParams({ offset: String(offset), limit: '30', q: input('search').value.trim(), status: el<HTMLSelectElement>('filter').value });
  const data = await json('/api/clips?' + params);
  if (token !== queueRequest) return;
  clips = data.clips; total = data.total;
  if (offset >= total && offset > 0) { offset = Math.max(0, Math.floor((total - 1) / 30) * 30); return refreshQueue(); }
  renderQueue();
}
function updateClipMetadata() {
  if (!current) return;
  el('clip-position').textContent = `${setName().toUpperCase()} CLIP ${current.position + 1} OF ${clipCount.toLocaleString()}`;
  el('clip-id').textContent = current.id;
  el('clip-status').textContent = statusNames[desiredStatus];
  el('clip-status').dataset.status = desiredStatus;
  el('duration').textContent = `${current.duration.toFixed(2)} SEC · MAC-HOSTED AUDIO`;
  el('change-label').textContent = annotation.value === current.original ? 'Same as original' : 'Transcript changed';
  el('revision-label').textContent = current.revision ? `· revision ${current.revision}` : '· no edits yet';
}
function showConflict(clip: Clip) {
  conflicting = clip; el('conflict').hidden = false;
  el('conflict-text').textContent = clip.annotation || '(No speech)';
  el('conflict-author').textContent = `Saved by ${clip.updated_by || 'a collaborator'} · ${statusNames[clip.status]} · revision ${clip.revision}`;
  savedLabel('Not saved — compare the two versions below', 'error'); updateActions();
}
function clearConflict() { conflicting = null; el('conflict').hidden = true; updateActions(); }
function acceptShared(clip: Clip, message = 'Saved to shared review') {
  current = clip; draftBaseRevision = clip.revision; desiredStatus = clip.status; annotation.value = clip.annotation;
  unresolvedSaveIntent = false;
  clearConflict(); draft(); updateClipMetadata();
  savedLabel(clip.updated_by ? `${message} · ${clip.updated_by}` : 'Ready to edit · original copied here');
}
async function flush(): Promise<boolean> {
  clearTimeout(saveTimer);
  if (inFlight) { if (!(await inFlight)) return false; return flush(); }
  if (!current || conflicting || composing) return false;
  if (!dirty()) return true;
  if (!input('editor').value.trim()) { savedLabel('Enter your name below to save your edits', 'pending'); draft(); return false; }
  const clipID = current.id;
  unresolvedSaveIntent = true;
  const submitted = { annotation: annotation.value, status: desiredStatus, revision: draftBaseRevision, editor: input('editor').value.trim() };
  savedLabel('Saving to shared review…', 'pending'); draft();
  inFlight = (async () => {
    try {
      const data = await json(`/api/clips/${clipID}`, { method: 'PUT', body: JSON.stringify(submitted) });
      if (current?.id === clipID) {
        current = data.clip; draftBaseRevision = data.clip.revision; unresolvedSaveIntent = false;
        draft(); updateClipMetadata();
        savedLabel(dirty() ? 'More changes waiting to save…' : '✓ Saved to shared review', dirty() ? 'pending' : 'saved');
      }
      connected(true); notice();
      clips = clips.map(c => c.id === clipID ? data.clip : c); renderQueue();
      void refreshStats().catch(() => {});
      if (el<HTMLDetailsElement>('history-details').open) void loadHistory();
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.status === 409 && current?.id === clipID) showConflict(error.body.clip);
      else { savedLabel('Not saved — your draft is still here. Retrying when connected.', 'error'); fail(error); }
      return false;
    }
  })();
  const pending = inFlight;
  const success = await pending;
  if (inFlight === pending) inFlight = null;
  if (success && dirty() && !conflicting && !composing) return flush();
  return success;
}
async function blobFor(id: string) {
  const key = `${reviewSet}:${id}`;
  if (audioCache.has(key)) return audioCache.get(key)!;
  const blob = await (await request(`/api/clips/${id}/audio`)).blob();
  audioCache.set(key, blob);
  while (audioCache.size > 5) audioCache.delete(audioCache.keys().next().value!);
  return blob;
}
async function loadAudio(clip: Clip) {
  const token = ++audioRequest;
  audio.pause(); audio.removeAttribute('src'); audio.load();
  if (audioURL) { URL.revokeObjectURL(audioURL); audioURL = null; }
  button('replay').disabled = true; button('back-five').disabled = true;
  el('audio-retry').hidden = true; el('audio-message').textContent = 'Loading recording from the Mac…';
  try {
    const blob = await blobFor(clip.id);
    if (token !== audioRequest) return;
    audioURL = URL.createObjectURL(blob); audio.src = audioURL; audio.load(); audio.playbackRate = Number(el<HTMLSelectElement>('speed').value);
    button('replay').disabled = false; button('back-five').disabled = false;
    el('audio-message').textContent = 'Ready to play · cached for instant replay';
    const next = clips.find(c => c.position === clip.position + 1);
    if (next) void blobFor(next.id).catch(() => {});
  } catch { if (token === audioRequest) { el('audio-message').textContent = 'Could not load this recording. Check that the Mac is online.'; el('audio-retry').hidden = false; } }
}
async function openClip(id: string): Promise<boolean> {
  if (navigating || composing) return false;
  if (current?.id === id) return true;
  navigating = true; updateActions();
  const token = ++selectionRequest;
  try {
    if (current && !(await flush())) { if (conflicting) el('conflict').scrollIntoView({ block: 'nearest' }); return false; }
    const data = await json(`/api/clips/${encodeURIComponent(id)}`);
    if (token !== selectionRequest) return false;
    current = data.clip; draftBaseRevision = current!.revision; desiredStatus = current!.status;
    unresolvedSaveIntent = false;
    el<HTMLTextAreaElement>('original').value = current!.original;
    annotation.value = current!.annotation; clearConflict();
    const savedDraft = storage.get(datasetKey(`draft:${id}`));
    if (savedDraft) {
      try {
        const restored: Draft = JSON.parse(savedDraft);
        if (restored.id === id && typeof restored.annotation === 'string' && restored.status in statusNames && Number.isInteger(restored.revision)) {
          if (restored.annotation !== current!.annotation || restored.status !== current!.status || restored.uncertain) {
            annotation.value = restored.annotation; desiredStatus = restored.status; draftBaseRevision = restored.revision;
            unresolvedSaveIntent = !!restored.uncertain;
            if (restored.revision !== current!.revision) showConflict(current!);
            else { savedLabel('Restored your unsaved draft — click Save now', 'pending'); notice('An unsaved draft from this browser has been restored. Review it, then save.'); }
          } else storage.remove(datasetKey(`draft:${id}`));
        }
      } catch {}
    }
    if (!dirty() && !conflicting) savedLabel(current!.updated_by ? `Saved by ${current!.updated_by} · shared revision ${current!.revision}` : 'Ready to edit · original copied here');
    updateClipMetadata(); renderQueue(); storage.set(datasetKey('last-clip'), id);
    void loadAudio(current!);
    if (el<HTMLDetailsElement>('history-details').open) void loadHistory();
    connected(true); return true;
  } catch (error) { fail(error); return false; }
  finally { navigating = false; updateActions(); }
}
async function go(direction: number) {
  if (!current || navigating) return;
  const position = current.position + direction;
  if (position < 0 || position >= clipCount) { notice(`You’ve reached the end of the ${setName()} set.`); return; }
  const token = datasetRequest;
  let target = clips.find(c => c.position === position)?.id;
  if (!target) {
    navigating = true; updateActions();
    try { target = (await json(`/api/clips?offset=${position}&limit=1`)).clips[0]?.id; }
    catch (error) { if (token === datasetRequest) fail(error); return; }
    finally { navigating = false; updateActions(); }
  }
  if (token !== datasetRequest || !target) return;
  if (await openClip(target)) {
    if (!input('search').value && el<HTMLSelectElement>('filter').value === 'all' && !clips.some(c => c.id === target)) {
      offset = Math.floor(position / 30) * 30; await refreshQueue().catch(fail);
    }
  }
}
async function reviewedNext() {
  if (!current || navigating || composing || conflicting || reviewing) return;
  if (!input('editor').value.trim()) { savedLabel('Enter your name below before marking reviewed', 'pending'); input('editor').focus(); return; }
  const before = current.id;
  reviewing = true;
  try {
  desiredStatus = 'reviewed'; updateClipMetadata(); draft();
  if (!(await flush()) || current?.id !== before) return;
  const filter = el<HTMLSelectElement>('filter').value;
  if (filter !== 'all' || input('search').value.trim()) {
    try {
      await refreshQueue();
      const next = clips.find(c => c.position > current!.position) || clips.find(c => c.id !== before);
      if (next) await openClip(next.id);
      else if (offset + clips.length < total) { offset += 30; await refreshQueue(); if (clips[0]) await openClip(clips[0].id); }
      else notice('This filtered queue is complete. Choose another filter to continue.');
    } catch (error) { fail(error); }
  } else await go(1);
  } finally { reviewing = false; }
}
async function loadHistory() {
  if (!current) return;
  const id = current.id;
  const token = datasetRequest;
  try {
    const data = await json(`/api/clips/${id}/history`);
    if (token !== datasetRequest || current?.id !== id) return;
    const container = el('history-list'); container.replaceChildren();
    if (!data.history.length) container.textContent = 'No edits yet. The human annotation still starts from the original label.';
    for (const row of data.history) {
      const entry = document.createElement('div'); entry.className = 'history-entry';
      const meta = document.createElement('small'); meta.textContent = `Revision ${row.revision} · ${row.editor} · ${new Date(row.saved_at).toLocaleString()} · ${statusNames[row.status as Status]}`;
      const text = document.createElement('p'); text.lang = 'nan-TW'; text.textContent = row.annotation || '(No speech)'; entry.append(meta, text); container.append(entry);
    }
  } catch { if (token === datasetRequest) el('history-list').textContent = 'Could not load revision history. Close and reopen to retry.'; }
}
async function poll() {
  if (!ready || polling || inFlight || navigating || document.hidden) return;
  polling = true;
  const token = datasetRequest;
  try {
    const data = await json(`/api/changes?since=${sequence}`);
    if (token !== datasetRequest || inFlight || navigating) return;
    for (const changed of data.clips as Clip[]) {
      if (current?.id === changed.id && changed.revision > current.revision) {
        if (dirty() || composing || conflicting) showConflict(changed);
        else acceptShared(changed, 'Synced from collaborator');
      }
    }
    sequence = data.sequence;
    if (data.clips.length) { await refreshStats(); if (token !== datasetRequest) return; await refreshQueue(); }
    if (token !== datasetRequest) return;
    connected(true);
    if (dirty() && !conflicting && !composing && input('editor').value.trim()) await flush();
  } catch (error) { if (token === datasetRequest) { connected(false); if (error instanceof ApiError && error.status === 401) fail(error); } }
  finally { polling = false; }
}
async function start() {
  if (initializing) return;
  if (!accessKey) {
    el('access-panel').hidden = false; el('connection').textContent = 'Private invitation required';
    pendingProgress('Open your invitation to see shared progress.');
    el('clip-list').textContent = 'Review locked. Open your invitation to load the saved corrections and history.';
    el('workspace').setAttribute('aria-busy', 'false'); return;
  }
  initializing = true;
  try {
    // Read cursor before clips, so initial loading cannot skip collaborator edits.
    const meta = await refreshStats(); sequence = meta.sequence;
    const remembered = storage.set('key', accessKey);
    el('access-panel').hidden = true;
    notice(remembered ? '' : 'This browser could not remember your access. Use your invitation link again when you return.');
    for (const id of ['search', 'filter', 'share', 'export']) (el(id) as HTMLInputElement).disabled = false;
    await refreshQueue();
    const last = storage.get(datasetKey('last-clip'));
    const target = last && /^taigi-(?:dev2-)?\d{8}$/.test(last) ? last : clips[0]?.id;
    if (!target) throw new Error('The dev queue is unavailable');
    let loaded = await openClip(target);
    if (!loaded && clips[0] && clips[0].id !== target) loaded = await openClip(clips[0].id);
    if (!loaded) throw new Error('The dev clip could not be loaded');
    ready = true;
    connected(true); updateActions();
  } catch (error) { ready = false; fail(error); }
  finally { initializing = false; el('workspace').setAttribute('aria-busy', 'false'); }
}
function unlockRememberedReview(key: string | null) {
  // A fragment navigation doesn't reload the app. Other open tabs receive the
  // remembered key through storage events. Never interrupt an active review.
  if (!key || ready || current || initializing) return;
  accessKey = key;
  void start();
}
window.addEventListener('hashchange', () => {
  unlockRememberedReview(new URLSearchParams(location.hash.slice(1)).get('key'));
});
window.addEventListener('storage', event => {
  if (event.key === 'taigi-review:key') unlockRememberedReview(event.newValue);
});
annotation.addEventListener('compositionstart', () => { composing = true; clearTimeout(saveTimer); updateActions(); });
annotation.addEventListener('compositionend', () => { composing = false; onEdit(); updateActions(); });
function onEdit() {
  if (!current) return;
  if (desiredStatus === 'reviewed') desiredStatus = 'unreviewed';
  updateClipMetadata(); draft(); clearTimeout(saveTimer);
  if (!conflicting) savedLabel(dirty() ? 'Unsaved changes…' : '✓ Saved to shared review', dirty() ? 'pending' : 'saved');
  if (!composing && !conflicting) saveTimer = setTimeout(() => { void flush(); }, 800);
}
annotation.addEventListener('input', onEdit);
input('editor').addEventListener('input', () => { storage.set('editor', input('editor').value); clearTimeout(saveTimer); saveTimer = setTimeout(() => { if (dirty()) void flush(); }, 800); });
button('save').addEventListener('click', () => { void flush(); });
button('flag').addEventListener('click', () => { if (!current) return; desiredStatus = desiredStatus === 'flagged' ? 'unreviewed' : 'flagged'; updateClipMetadata(); draft(); void flush(); });
button('review-next').addEventListener('click', () => { void reviewedNext(); });
button('previous').addEventListener('click', () => { void go(-1); });
button('next').addEventListener('click', () => { void go(1); });
button('use-shared').addEventListener('click', () => { if (conflicting) { acceptShared(conflicting); notice(); void refreshQueue().catch(fail); } });
button('use-mine').addEventListener('click', () => { if (!conflicting || !current) return; current = conflicting; draftBaseRevision = conflicting.revision; clearConflict(); draft(); void flush(); });
input('search').addEventListener('input', () => { clearTimeout(queueTimer); queueTimer = setTimeout(() => { offset = 0; void refreshQueue().catch(fail); }, 250); });
el('filter').addEventListener('change', () => { offset = 0; void refreshQueue().catch(fail); });
button('queue-prev').addEventListener('click', () => { offset = Math.max(0, offset - 30); void refreshQueue().catch(fail); });
button('queue-next').addEventListener('click', () => { offset += 30; void refreshQueue().catch(fail); });
el('history-details').addEventListener('toggle', () => { if (el<HTMLDetailsElement>('history-details').open) void loadHistory(); });
button('replay').addEventListener('click', () => { audio.currentTime = 0; void audio.play().catch(() => { el('audio-message').textContent = 'Press play on the audio player.'; }); });
button('back-five').addEventListener('click', () => { audio.currentTime = Math.max(0, audio.currentTime - 5); });
button('audio-retry').addEventListener('click', () => { if (current) void loadAudio(current); });
el('speed').addEventListener('change', () => { audio.playbackRate = Number(el<HTMLSelectElement>('speed').value); storage.set('speed', String(audio.playbackRate)); });
audio.addEventListener('error', () => { if (audio.hasAttribute('src')) { el('audio-message').textContent = 'Playback failed. Reload the recording.'; el('audio-retry').hidden = false; } });
el('access-form').addEventListener('submit', event => { event.preventDefault(); accessKey = input('access-key').value.trim(); input('access-key').value = ''; void start(); });
button('share').addEventListener('click', async () => {
  const link = `https://jefflai108.github.io/taigi-review/#key=${encodeURIComponent(accessKey)}`;
  try { await navigator.clipboard.writeText(link); notice('Invitation copied. Share it with your co-annotator; this link grants access to the same recordings and saved corrections.'); }
  catch { notice('Copy the private invitation from the address bar to share the review.'); history.replaceState(null, '', '#key=' + encodeURIComponent(accessKey)); }
});
button('export').addEventListener('click', async () => {
  if (current && !(await flush())) return;
  const selected = reviewSet;
  try {
    const data = await json('/api/export');
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a'); a.href = url; a.download = `taigi-${selected}-annotations-${new Date().toISOString().slice(0, 10)}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { fail(error); }
});
document.addEventListener('keydown', event => {
  if (reviewSession.activeTab === 'record') return;
  if (event.isComposing || composing) return;
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') { event.preventDefault(); void reviewedNext(); }
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') { event.preventDefault(); void flush(); }
  if (event.altKey && event.code === 'Space' && audio.hasAttribute('src')) { event.preventDefault(); if (audio.paused) void audio.play().catch(() => {}); else audio.pause(); }
});
window.addEventListener('beforeunload', event => { if (dirty() || inFlight) { draft(); event.preventDefault(); event.returnValue = ''; } });
document.addEventListener('visibilitychange', () => { if (document.hidden) { draft(); if (dirty()) void flush(); } else void poll(); });
window.addEventListener('online', () => { if (ready) void poll(); else void start(); });
setInterval(() => { if (ready) void poll(); else if (accessKey) void start(); }, 3000);
void start();

// Optional imperative tools reuse the visible editor and its conflict safeguards.
const modelContext = (document as Document & { modelContext?: { registerTool: (tool: any, options?: any) => Promise<void> | void } }).modelContext;
if (modelContext?.registerTool) {
  const lifecycle = new AbortController();
  const tools = [
    {
      name: 'read_current_taigi_clip', title: 'Read the current Taigi dev clip',
      description: 'Read the currently visible dev clip, working annotation, save state, and conflict state.',
      inputSchema: { type: 'object', properties: {}, additionalProperties: false },
      annotations: { readOnlyHint: true, untrustedContentHint: true },
      execute(args: unknown) {
        if (!args || typeof args !== 'object' || Array.isArray(args) || Object.keys(args).length) throw new Error('No arguments are accepted');
        if (!ready || !current || reviewSession.activeTab === 'record') throw new Error('Open a dev clip in the review tab first');
        return { ...current, split: reviewSet === 'dev2' ? 'validation2' : 'validation', editor_annotation: annotation.value, editor_status: desiredStatus, unsaved: dirty(), conflict: !!conflicting };
      },
    },
    {
      name: 'save_taigi_annotation', title: 'Save a human annotation',
      description: 'Save an explicitly provided transcript for the currently visible dev clip, using the same shared save and conflict checks as the editor. Does not infer or transcribe audio.',
      inputSchema: { type: 'object', properties: { id: { type: 'string' }, annotation: { type: 'string', maxLength: 10000 }, status: { type: 'string', enum: ['unreviewed', 'reviewed', 'flagged'] }, editor: { type: 'string', minLength: 1, maxLength: 80 } }, required: ['id', 'annotation', 'status', 'editor'], additionalProperties: false },
      annotations: { readOnlyHint: false, untrustedContentHint: true },
      async execute(args: any) {
        if (!args || typeof args !== 'object' || Array.isArray(args) || Object.keys(args).sort().join(',') !== 'annotation,editor,id,status' || typeof args.id !== 'string' || typeof args.annotation !== 'string' || args.annotation.length > 10000 || !Object.hasOwn(statusNames, args.status) || typeof args.editor !== 'string' || !args.editor.trim() || args.editor.length > 80) throw new Error('Invalid annotation input');
        if (!ready || !current || args.id !== current.id || reviewSession.activeTab === 'record') throw new Error('The requested dev clip must already be open in the review tab');
        if (dirty() || conflicting || inFlight || navigating || composing) throw new Error('Resolve or save the current human draft first');
        input('editor').value = args.editor; storage.set('editor', args.editor);
        annotation.value = args.annotation; desiredStatus = args.status; updateClipMetadata(); draft();
        if (!(await flush())) throw new Error('Annotation was not saved; review the visible save or conflict message');
        return { id: current.id, revision: current.revision, status: current.status, saved: true };
      },
    },
  ];
  for (const tool of tools) { try { void Promise.resolve(modelContext.registerTool(tool, { signal: lifecycle.signal })).catch(() => {}); } catch {} }
  window.addEventListener('pagehide', () => lifecycle.abort(), { once: true });
}
