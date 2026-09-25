type Benchmark = typeof import('../data/tts-benchmark.json');
export {};

const dataNode = document.querySelector<HTMLScriptElement>('#tts-data');
const modelSelect = document.querySelector<HTMLSelectElement>('#tts-model');
const paragraphSelect = document.querySelector<HTMLSelectElement>('#tts-paragraph');
const playAll = document.querySelector<HTMLButtonElement>('[data-play-all]');
const status = document.querySelector<HTMLElement>('[data-playback-status]');
const players = Array.from(document.querySelectorAll<HTMLAudioElement>('audio[data-voice-name]'));

if (dataNode && modelSelect && paragraphSelect && playAll && status && players.length) {
  const data: Benchmark = JSON.parse(dataNode.textContent!);
  const previous = document.querySelector<HTMLButtonElement>('[data-previous]')!;
  const next = document.querySelector<HTMLButtonElement>('[data-next]')!;
  const rows = players.map(player => player.closest<HTMLElement>('[data-voice-row]')!);
  const records = new Map(data.records.map(record => [`${record.modelId}/${record.paragraphId}/${record.voiceId}`, record]));
  let queued = false;
  let queueIndex = -1;
  let active: HTMLAudioElement | null = null;
  let playbackVersion = 0;

  function clearQueue() {
    queued = false;
    queueIndex = -1;
    playbackVersion++;
    playAll!.textContent = 'Play all seven';
  }

  function stopPlayers() {
    clearQueue();
    active = null;
    players.forEach((player, index) => {
      player.pause();
      delete rows[index].dataset.playing;
    });
  }

  async function playNext(index: number) {
    queueIndex = index;
    const version = playbackVersion;
    const player = players[index];
    player.currentTime = 0;
    try {
      await player.play();
    } catch {
      if (!queued || queueIndex !== index || playbackVersion !== version) return;
      clearQueue();
      status!.textContent = `Unable to play ${player.dataset.voiceName}. Try its player or download the MP3.`;
    }
  }

  function updateSelection(updateUrl = true) {
    stopPlayers();
    const paragraphIndex = data.paragraphs.findIndex(p => p.id === paragraphSelect!.value);
    const paragraph = data.paragraphs[paragraphIndex];
    const model = data.models.find(m => m.id === modelSelect!.value)!;
    document.querySelector('#sample-transcript')!.textContent = paragraph.text;
    document.querySelector('[data-passage-category]')!.textContent = `${paragraph.category} · ${paragraph.sentences} ${paragraph.sentences === 1 ? 'sentence' : 'sentences'}`;
    document.querySelector('[data-passage-count]')!.textContent = `${String(paragraphIndex + 1).padStart(2, '0')} / ${data.paragraphs.length}`;
    document.querySelector('[data-current-model]')!.textContent = `${model.label} · 07 voices`;
    document.querySelector<HTMLElement>('[data-identity-note]')!.hidden = model.id !== 'eleven_v3_conversational';
    previous.disabled = paragraphIndex === 0;
    next.disabled = paragraphIndex === data.paragraphs.length - 1;
    players.forEach((player, index) => {
      const row = rows[index];
      const record = records.get(`${model.id}/${paragraph.id}/${row.dataset.voiceId}`)!;
      if (player.getAttribute('src') !== record.audioPath) {
        player.src = record.audioPath;
        player.load();
      } else {
        player.currentTime = 0;
      }
      row.querySelector('[data-duration]')!.textContent = `${record.durationSeconds.toFixed(2)}s audio`;
      row.querySelector('[data-ttfb]')!.textContent = `${Math.round(record.ttfbMs).toLocaleString('en-US')} ms`;
      row.querySelector('[data-total]')!.textContent = `${(record.totalMs / 1000).toFixed(2)} s`;
      row.querySelector<HTMLAnchorElement>('[data-download]')!.href = record.audioPath;
    });
    status!.textContent = `${model.label} · ${paragraph.title}. Choose a voice or play all seven.`;
    if (updateUrl) {
      const url = new URL(window.location.href);
      url.searchParams.set('model', model.id);
      url.searchParams.set('paragraph', paragraph.id);
      window.history.replaceState(null, '', url);
    }
  }

  players.forEach((player, index) => {
    const row = rows[index];
    player.addEventListener('play', () => {
      if (player.paused) return;
      if (queued && index !== queueIndex) clearQueue();
      active = player;
      players.forEach(other => {
        if (other !== player) other.pause();
      });
      row.dataset.playing = '';
      status.textContent = `Playing ${queued ? `${index + 1} of ${players.length} · ` : ''}${player.dataset.voiceName}`;
    });
    player.addEventListener('pause', () => {
      if (!player.paused) return;
      delete row.dataset.playing;
      if (player !== active || player.ended) return;
      clearQueue();
      status.textContent = `Paused · ${player.dataset.voiceName}`;
    });
    player.addEventListener('ended', () => {
      delete row.dataset.playing;
      if (player !== active) return;
      active = null;
      if (queued && queueIndex === index && index + 1 < players.length) {
        void playNext(index + 1);
        return;
      }
      const finishedQueue = queued;
      clearQueue();
      status.textContent = finishedQueue ? 'All seven samples played. Choose another passage or model.' : `Finished · ${player.dataset.voiceName}`;
    });
    player.addEventListener('error', () => {
      if (!player.error) return;
      delete row.dataset.playing;
      if (player === active || (queued && queueIndex === index)) clearQueue();
      status.textContent = `Audio unavailable for ${player.dataset.voiceName}. Try downloading the MP3.`;
    });
  });

  playAll.addEventListener('click', () => {
    const wasQueued = queued;
    stopPlayers();
    if (wasQueued) {
      status.textContent = 'Playback stopped. Choose a voice or play all seven again.';
      return;
    }
    queued = true;
    playAll.textContent = 'Stop playback';
    void playNext(0);
  });
  modelSelect.addEventListener('change', () => updateSelection());
  paragraphSelect.addEventListener('change', () => updateSelection());
  previous.addEventListener('click', () => {
    paragraphSelect.selectedIndex = Math.max(0, paragraphSelect.selectedIndex - 1);
    updateSelection();
  });
  next.addEventListener('click', () => {
    paragraphSelect.selectedIndex = Math.min(data.paragraphs.length - 1, paragraphSelect.selectedIndex + 1);
    updateSelection();
  });

  const parameters = new URLSearchParams(window.location.search);
  const requestedModel = parameters.get('model');
  const requestedParagraph = parameters.get('paragraph');
  if (data.models.some(m => m.id === requestedModel)) modelSelect.value = requestedModel!;
  if (data.paragraphs.some(p => p.id === requestedParagraph)) paragraphSelect.value = requestedParagraph!;
  updateSelection(false);
  modelSelect.disabled = false;
  paragraphSelect.disabled = false;
  document.querySelector<HTMLElement>('[data-passage-navigation]')!.hidden = false;
  playAll.hidden = false;
}
