type Comparison = typeof import('../data/tts-comparison').comparison;
export {};

const dataNode = document.querySelector<HTMLScriptElement>('#tts-data');
const paragraphSelect = document.querySelector<HTMLSelectElement>('#tts-paragraph');
const benchmarkSelect = document.querySelector<HTMLSelectElement>('#tts-benchmark-language');
const playAll = document.querySelector<HTMLButtonElement>('[data-play-all]');
const status = document.querySelector<HTMLElement>('[data-playback-status]');
const players = Array.from(document.querySelectorAll<HTMLAudioElement>('audio[data-voice-name]'));

if (dataNode && paragraphSelect && benchmarkSelect && playAll && status && players.length) {
  const data: Comparison = JSON.parse(dataNode.textContent!);
  const previous = document.querySelector<HTMLButtonElement>('[data-previous]')!;
  const next = document.querySelector<HTMLButtonElement>('[data-next]')!;
  const panels = players.map(player => player.closest<HTMLElement>('[data-model-sample]')!);
  const records = new Map(data.records.map(record => [`${record.modelId}/${record.paragraphId}/${record.voiceId}`, record]));
  const pairButtons = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-play-pair]'));
  const pairs = new Map(pairButtons.map(button => [button, Array.from(button.closest('[data-voice-row]')!.querySelectorAll<HTMLAudioElement>('audio'))]));
  let queue: HTMLAudioElement[] = [];
  let queuePosition = -1;
  let queueOwner: HTMLButtonElement | null = null;
  let active: HTMLAudioElement | null = null;
  let playbackVersion = 0;

  function updateButtons() {
    playAll!.textContent = queue.length ? 'Stop playback' : 'Play all pairs';
    pairButtons.forEach(button => {
      const voice = pairs.get(button)![0].dataset.voiceName;
      const playingPair = queue.length > 0 && queueOwner === button;
      button.textContent = playingPair ? 'Stop pair' : 'Play pair';
      button.setAttribute('aria-label', playingPair ? `Stop pair for ${voice}` : `Play both models for ${voice}`);
    });
  }

  function clearQueue() {
    queue = [];
    queuePosition = -1;
    queueOwner = null;
    playbackVersion++;
    updateButtons();
  }

  function stopPlayers() {
    clearQueue();
    active = null;
    players.forEach((player, index) => {
      player.pause();
      delete panels[index].dataset.playing;
    });
  }

  function playerLabel(player: HTMLAudioElement) {
    return `${player.dataset.voiceName} · ${player.dataset.modelName}`;
  }

  async function playNext(position: number) {
    queuePosition = position;
    const version = playbackVersion;
    const player = queue[position];
    player.currentTime = 0;
    try {
      await player.play();
    } catch {
      if (queue[position] !== player || playbackVersion !== version) return;
      clearQueue();
      status!.textContent = `Unable to play ${playerLabel(player)}. Try its player or download the MP3.`;
    }
  }

  function startQueue(selected: HTMLAudioElement[], owner: HTMLButtonElement) {
    stopPlayers();
    queue = selected;
    queueOwner = owner;
    updateButtons();
    void playNext(0);
  }

  function updateBenchmark(language: string) {
    benchmarkSelect!.value = language;
    document.querySelectorAll<HTMLElement>('[data-benchmark-cohort]').forEach(panel => {
      panel.hidden = panel.dataset.language !== language;
    });
  }

  function updateSelection(updateUrl = true) {
    stopPlayers();
    const paragraphIndex = data.paragraphs.findIndex(p => p.id === paragraphSelect!.value);
    const paragraph = data.paragraphs[paragraphIndex];
    const transcript = document.querySelector<HTMLElement>('#sample-transcript')!;
    transcript.textContent = paragraph.text;
    transcript.lang = paragraph.language;
    document.querySelector('[data-passage-category]')!.textContent = `${paragraph.languageLabel} · ${paragraph.category} · ${paragraph.sentences} ${paragraph.sentences === 1 ? 'sentence' : 'sentences'}`;
    document.querySelector('[data-passage-count]')!.textContent = `${String(paragraphIndex + 1).padStart(2, '0')} / ${data.paragraphs.length}`;
    previous.disabled = paragraphIndex === 0;
    next.disabled = paragraphIndex === data.paragraphs.length - 1;
    players.forEach((player, index) => {
      const panel = panels[index];
      const voiceId = player.closest<HTMLElement>('[data-voice-row]')!.dataset.voiceId;
      const record = records.get(`${panel.dataset.modelId}/${paragraph.id}/${voiceId}`)!;
      if (player.getAttribute('src') !== record.audioPath) {
        player.src = record.audioPath;
        player.load();
      } else {
        player.currentTime = 0;
      }
      panel.querySelector('[data-duration]')!.textContent = `${record.durationSeconds.toFixed(2)}s audio`;
      panel.querySelector('[data-ttfb]')!.textContent = `${Math.round(record.ttfbMs).toLocaleString('en-US')} ms`;
      panel.querySelector('[data-total]')!.textContent = `${(record.totalMs / 1000).toFixed(2)} s`;
      panel.querySelector<HTMLAnchorElement>('[data-download]')!.href = record.audioPath;
    });
    updateBenchmark(paragraph.language);
    status!.textContent = `${paragraph.title}. Choose a player, play one voice pair, or play all pairs.`;
    if (updateUrl) {
      const url = new URL(window.location.href);
      url.searchParams.delete('model');
      url.searchParams.set('paragraph', paragraph.id);
      window.history.replaceState(null, '', url);
    }
  }

  players.forEach((player, index) => {
    const panel = panels[index];
    player.addEventListener('play', () => {
      if (player.paused) return;
      if (queue.length && queue[queuePosition] !== player) clearQueue();
      active = player;
      players.forEach(other => {
        if (other !== player) other.pause();
      });
      panel.dataset.playing = '';
      status.textContent = `Playing ${queue.length ? `${queuePosition + 1} of ${queue.length} · ` : ''}${playerLabel(player)}`;
    });
    player.addEventListener('pause', () => {
      if (!player.paused) return;
      delete panel.dataset.playing;
      if (player !== active || player.ended) return;
      clearQueue();
      status.textContent = `Paused · ${playerLabel(player)}`;
    });
    player.addEventListener('ended', () => {
      delete panel.dataset.playing;
      if (player !== active) return;
      active = null;
      if (queue[queuePosition] === player && queuePosition + 1 < queue.length) {
        void playNext(queuePosition + 1);
        return;
      }
      const finishedCount = queue.length;
      clearQueue();
      status.textContent = finishedCount === players.length
        ? 'All seven voice pairs played. Choose another passage.'
        : finishedCount > 0
          ? `${player.dataset.voiceName} · both models played. Choose another pair or passage.`
          : `Finished · ${playerLabel(player)}`;
    });
    player.addEventListener('error', () => {
      if (!player.error) return;
      delete panel.dataset.playing;
      if (player === active || queue[queuePosition] === player) clearQueue();
      status.textContent = `Audio unavailable for ${playerLabel(player)}. Try downloading the MP3.`;
    });
  });

  playAll.addEventListener('click', () => {
    if (queue.length) {
      stopPlayers();
      status.textContent = 'Playback stopped. Choose a player or play a voice pair.';
      return;
    }
    startQueue(players, playAll);
  });
  pairButtons.forEach(button => {
    button.hidden = false;
    button.addEventListener('click', () => {
      if (queueOwner === button) {
        stopPlayers();
        status.textContent = 'Pair stopped. Choose a player or play another pair.';
        return;
      }
      startQueue(pairs.get(button)!, button);
    });
  });
  paragraphSelect.addEventListener('change', () => updateSelection());
  benchmarkSelect.addEventListener('change', () => updateBenchmark(benchmarkSelect.value));
  previous.addEventListener('click', () => {
    paragraphSelect.selectedIndex = Math.max(0, paragraphSelect.selectedIndex - 1);
    updateSelection();
  });
  next.addEventListener('click', () => {
    paragraphSelect.selectedIndex = Math.min(data.paragraphs.length - 1, paragraphSelect.selectedIndex + 1);
    updateSelection();
  });

  const requestedParagraph = new URLSearchParams(window.location.search).get('paragraph');
  if (data.paragraphs.some(p => p.id === requestedParagraph)) paragraphSelect.value = requestedParagraph!;
  updateSelection(false);
  paragraphSelect.disabled = false;
  benchmarkSelect.disabled = false;
  document.querySelector<HTMLElement>('[data-passage-navigation]')!.hidden = false;
  playAll.hidden = false;
}
