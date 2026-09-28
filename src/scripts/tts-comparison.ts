type Comparison = typeof import('../data/tts-comparison').comparison;
export {};

const dataNode = document.querySelector<HTMLScriptElement>('#tts-data');
const paragraphSelect = document.querySelector<HTMLSelectElement>('#tts-paragraph');
const styleSelect = document.querySelector<HTMLSelectElement>('#tts-style');
const benchmarkStyleSelect = document.querySelector<HTMLSelectElement>('#tts-benchmark-style');
const benchmarkSelect = document.querySelector<HTMLSelectElement>('#tts-benchmark-language');
const playAll = document.querySelector<HTMLButtonElement>('[data-play-all]');
const status = document.querySelector<HTMLElement>('[data-playback-status]');
const players = Array.from(document.querySelectorAll<HTMLAudioElement>('audio[data-voice-name]'));


if (dataNode && paragraphSelect && styleSelect && benchmarkStyleSelect && benchmarkSelect && playAll && status && players.length) {
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
  let selectedStyle = 'plain';
  const allowedStyles = ['plain', 'emotion', 'vocal', 'all'];

  function updateButtons() {
    playAll!.textContent = queue.length ? 'Stop playback' : 'Play all voices';
    voiceButtons.forEach(button => {
      const group = groups.get(button)!;
      const voice = group[0].dataset.voiceName;
      const count = visible(group).length;
      const playingGroup = queue.length > 0 && queueOwner === button;
      button.textContent = playingGroup ? 'Stop playback' : `Play all ${count}`;
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

  // Switching to the fixed-passage pilot cancels the main queue immediately.
  document.addEventListener('play', event => {
    if (!(event.target instanceof HTMLAudioElement)) return;
    if (!players.includes(event.target)) {
      stopPlayers();
      status!.textContent = 'Use the microphone pilot players below to compare this tag.';
    }
    document.querySelectorAll('audio').forEach(player => {
      if (player !== event.target) player.pause();
    });
  }, true);

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

  function updateBenchmark(language: string, style = benchmarkStyleSelect!.value) {
    benchmarkSelect!.value = language;
    const mandarin = language === 'zh-Hant-TW';
    benchmarkStyleSelect!.disabled = !mandarin;
    benchmarkStyleSelect!.value = mandarin ? style : 'plain';
    benchmarkStyleSelect!.options[0].text = mandarin ? 'Plain text · 4 models' : 'American accent · 4 models';
    document.querySelectorAll<HTMLElement>('[data-benchmark-cohort]').forEach(panel => {
      panel.hidden = panel.dataset.language !== language;
      panel.querySelectorAll<HTMLElement>('[data-benchmark-style]').forEach(group => {
        group.hidden = benchmarkStyleSelect!.value !== 'all' && group.dataset.benchmarkStyle !== benchmarkStyleSelect!.value;
      });
    });
  }

  function updateSelection(updateUrl = true) {
    stopPlayers();
    const paragraphIndex = data.paragraphs.findIndex(p => p.id === paragraphSelect!.value);
    const paragraph = data.paragraphs[paragraphIndex];
    const transcript = document.querySelector<HTMLElement>('#sample-transcript')!;
    transcript.textContent = paragraph.spokenText ?? paragraph.text;
    transcript.lang = paragraph.language;
    const mandarin = paragraph.language === 'zh-Hant-TW';
    const currentStyle = mandarin ? selectedStyle : 'plain';
    styleSelect!.value = currentStyle;
    styleSelect!.disabled = !mandarin;
    styleSelect!.options[0].text = mandarin ? 'Plain text · 4 models' : 'American accent · 4 models';
    const selectedVersions = paragraph.versions.filter(v => currentStyle === 'all' || v.style === currentStyle);
    document.querySelector('[data-generation-note]')!.textContent = mandarin
      ? 'Compare four models with plain text, or three models with the exact same emotion or vocal-reaction tag. All styles shows all ten versions.'
      : 'All four models receive the same passage prefixed with [strong American accent].';
    document.querySelector<HTMLElement>('[data-style-notes]')!.hidden = !mandarin;
    for (const id of ['emotion', 'vocal']) {
      const version = paragraph.versions.find(v => v.variantId === id);
      document.querySelector(`[data-${id}-tag]`)!.textContent = version?.audioTags.join(' ') ?? '';
      document.querySelector(`[data-${id}-reason]`)!.textContent = version?.tagReason ?? '';
      document.querySelector(`[data-${id}-input]`)!.textContent = version?.text ?? '';
    }
    document.querySelector('[data-passage-category]')!.textContent = `${paragraph.languageLabel} · ${paragraph.category} · ${paragraph.sentences} ${paragraph.sentences === 1 ? 'sentence' : 'sentences'}`;
    document.querySelector('[data-passage-count]')!.textContent = `${String(paragraphIndex + 1).padStart(2, '0')} / ${data.paragraphs.length}`;
    document.querySelector('[data-version-count]')!.textContent = `07 voices · ${String(selectedVersions.length).padStart(2, '0')} of ${String(paragraph.versions.length).padStart(2, '0')} versions per voice`;
    document.querySelectorAll<HTMLElement>('[data-comparison-style]').forEach(group => {
      const style = group.dataset.comparisonStyle;
      const versions = selectedVersions.filter(v => v.style === style);
      group.hidden = versions.length === 0;
      group.querySelector<HTMLElement>('[data-version-grid]')!.dataset.versions = String(versions.length);
      group.querySelector('[data-style-title]')!.textContent = !mandarin ? 'American accent' : data.styles.find(s => s.id === style)!.label;
      group.querySelector('[data-style-tag]')!.textContent = versions[0]?.audioTags.join(' ') || 'No tags';
    });
    previous.disabled = paragraphIndex === 0;
    next.disabled = paragraphIndex === data.paragraphs.length - 1;
    players.forEach((player, index) => {
      const panel = panels[index];
      const voiceId = player.closest<HTMLElement>('[data-voice-row]')!.dataset.voiceId;
      const version = selectedVersions.find(v => v.variantId === panel.dataset.variantId);
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
      panel.querySelector('[data-recording-date]')!.textContent = version.generatedOn;
      panel.querySelector('[data-duration]')!.textContent = `${record.durationSeconds.toFixed(2)}s audio`;
      panel.querySelector('[data-ttfb]')!.textContent = `${Math.round(record.ttfbMs).toLocaleString('en-US')} ms`;
      panel.querySelector('[data-total]')!.textContent = `${(record.totalMs / 1000).toFixed(2)} s`;
      panel.querySelector<HTMLAnchorElement>('[data-download]')!.href = record.audioPath;
    });
    updateButtons();
    updateBenchmark(paragraph.language, currentStyle);
    status!.textContent = `${paragraph.title}. Choose a player, compare one voice, or play all voices.`;
    if (updateUrl) {
      const url = new URL(window.location.href);
      url.searchParams.delete('model');
      url.searchParams.set('paragraph', paragraph.id);
      if (mandarin && currentStyle !== 'plain') url.searchParams.set('style', currentStyle);
      else url.searchParams.delete('style');
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
  styleSelect.addEventListener('change', () => {
    selectedStyle = styleSelect.value;
    updateSelection();
  });
  benchmarkSelect.addEventListener('change', () => updateBenchmark(benchmarkSelect.value));
  benchmarkStyleSelect.addEventListener('change', () => updateBenchmark(benchmarkSelect.value));
  previous.addEventListener('click', () => {
    paragraphSelect.selectedIndex = Math.max(0, paragraphSelect.selectedIndex - 1);
    updateSelection();
  });
  next.addEventListener('click', () => {
    paragraphSelect.selectedIndex = Math.min(data.paragraphs.length - 1, paragraphSelect.selectedIndex + 1);
    updateSelection();
  });

  const params = new URLSearchParams(window.location.search);
  const requestedStyle = params.get('style');
  if (requestedStyle && allowedStyles.includes(requestedStyle)) selectedStyle = requestedStyle;
  const requestedParagraph = params.get('paragraph');
  if (data.paragraphs.some(p => p.id === requestedParagraph)) paragraphSelect.value = requestedParagraph!;
  updateSelection(false);
  paragraphSelect.disabled = false;
  benchmarkSelect.disabled = false;
  document.querySelector<HTMLElement>('[data-passage-navigation]')!.hidden = false;
  playAll.hidden = false;
}
