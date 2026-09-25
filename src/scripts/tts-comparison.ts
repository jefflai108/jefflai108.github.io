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
  const records = new Map(data.records.map(record => [`${record.variantId}/${record.paragraphId}/${record.voiceId}`, record]));
  const voiceButtons = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-play-voice]'));
  const groups = new Map(voiceButtons.map(button => [button, Array.from(button.closest('[data-voice-row]')!.querySelectorAll<HTMLAudioElement>('audio'))]));
  const visible = (selected: HTMLAudioElement[]) => selected.filter(player => !player.closest<HTMLElement>('[data-model-sample]')!.hidden);
  let queue: HTMLAudioElement[] = [];
  let queuePosition = -1;
  let queueOwner: HTMLButtonElement | null = null;
  let active: HTMLAudioElement | null = null;
  let playbackVersion = 0;

  function updateButtons() {
    playAll!.textContent = queue.length ? 'Stop playback' : 'Play all voices';
    voiceButtons.forEach(button => {
      const group = groups.get(button)!;
      const voice = group[0].dataset.voiceName;
      const count = visible(group).length;
      const playingGroup = queue.length > 0 && queueOwner === button;
      button.textContent = playingGroup ? 'Stop playback' : count === 4 ? 'Play all four' : 'Play both';
      button.setAttribute('aria-label', playingGroup ? `Stop playback for ${voice}` : `Play all ${count} versions for ${voice}`);
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
    return `${player.dataset.voiceName} · ${player.dataset.versionName}`;
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
    queue = visible(selected);
    if (!queue.length) return;
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
    const mandarin = paragraph.language === 'zh-Hant-TW';
    document.querySelector('[data-generation-note]')!.textContent = mandarin
      ? 'Four versions of the same words: the original two models, Eleven v3 with one emotion tag, and Eleven v3 with one vocal reaction tag.'
      : 'Both models receive [strong American accent] before this passage. Eleven v3 plays first, then v3 Conversational.';
    document.querySelector<HTMLElement>('[data-style-notes]')!.hidden = !mandarin;
    for (const id of ['emotion', 'vocal']) {
      const version = paragraph.versions.find(v => v.variantId === id);
      document.querySelector(`[data-${id}-tag]`)!.textContent = version?.audioTags.join(' ') ?? '';
      document.querySelector(`[data-${id}-reason]`)!.textContent = version?.tagReason ?? '';
      document.querySelector(`[data-${id}-input]`)!.textContent = version?.text ?? '';
    }
    document.querySelector('[data-passage-category]')!.textContent = `${paragraph.languageLabel} · ${paragraph.category} · ${paragraph.sentences} ${paragraph.sentences === 1 ? 'sentence' : 'sentences'}`;
    document.querySelector('[data-passage-count]')!.textContent = `${String(paragraphIndex + 1).padStart(2, '0')} / ${data.paragraphs.length}`;
    document.querySelector('[data-version-count]')!.textContent = `07 voices · ${String(paragraph.versions.length).padStart(2, '0')} versions per voice`;
    document.querySelectorAll<HTMLElement>('[data-version-grid]').forEach(grid => { grid.dataset.versions = String(paragraph.versions.length); });
    previous.disabled = paragraphIndex === 0;
    next.disabled = paragraphIndex === data.paragraphs.length - 1;
    players.forEach((player, index) => {
      const panel = panels[index];
      const voiceId = player.closest<HTMLElement>('[data-voice-row]')!.dataset.voiceId;
      const version = paragraph.versions.find(v => v.variantId === panel.dataset.variantId);
      panel.hidden = !version;
      if (!version) {
        if (player.hasAttribute('src')) {
          player.removeAttribute('src');
          player.load();
        }
        panel.querySelector<HTMLAnchorElement>('[data-download]')!.removeAttribute('href');
        return;
      }
      const record = records.get(`${version.variantId}/${paragraph.id}/${voiceId}`)!;
      if (player.getAttribute('src') !== record.audioPath) {
        player.src = record.audioPath;
        player.load();
      } else {
        player.currentTime = 0;
      }
      panel.querySelector('[data-sample-tags]')!.textContent = version.audioTags.join(' ') || 'No tags';
      panel.querySelector('[data-duration]')!.textContent = `${record.durationSeconds.toFixed(2)}s audio`;
      panel.querySelector('[data-ttfb]')!.textContent = `${Math.round(record.ttfbMs).toLocaleString('en-US')} ms`;
      panel.querySelector('[data-total]')!.textContent = `${(record.totalMs / 1000).toFixed(2)} s`;
      panel.querySelector<HTMLAnchorElement>('[data-download]')!.href = record.audioPath;
    });
    updateButtons();
    updateBenchmark(paragraph.language);
    status!.textContent = `${paragraph.title}. Choose a player, compare one voice, or play all voices.`;
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
      if (panel.hidden) { player.pause(); return; }
      if (player.paused) return;
      if (queue.length && queue[queuePosition] !== player) clearQueue();
      active = player;
      players.forEach(other => { if (other !== player) other.pause(); });
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
      const allVoices = queueOwner === playAll;
      clearQueue();
      status.textContent = allVoices
        ? `All seven voices played (${finishedCount} clips). Choose another passage.`
        : finishedCount > 0
          ? `${player.dataset.voiceName} · all ${finishedCount} versions played. Choose another voice or passage.`
          : `Finished · ${playerLabel(player)}`;
    });
    player.addEventListener('error', () => {
      if (!player.error || panel.hidden || !player.hasAttribute('src')) return;
      delete panel.dataset.playing;
      if (player === active || queue[queuePosition] === player) clearQueue();
      status.textContent = `Audio unavailable for ${playerLabel(player)}. Try downloading the MP3.`;
    });
  });

  playAll.addEventListener('click', () => {
    if (queue.length) {
      stopPlayers();
      status.textContent = 'Playback stopped. Choose a player or compare another voice.';
      return;
    }
    startQueue(players, playAll);
  });
  voiceButtons.forEach(button => {
    button.hidden = false;
    button.addEventListener('click', () => {
      if (queueOwner === button) {
        stopPlayers();
        status.textContent = 'Playback stopped. Choose a player or compare another voice.';
        return;
      }
      startQueue(groups.get(button)!, button);
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
