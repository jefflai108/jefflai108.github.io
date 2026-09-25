const players = Array.from(document.querySelectorAll<HTMLAudioElement>('audio[data-voice-name]'));
const playAll = document.querySelector<HTMLButtonElement>('[data-play-all]');
const status = document.querySelector<HTMLElement>('[data-playback-status]');

if (playAll && status && players.length) {
  let queued = false;
  let queueIndex = -1;
  let active: HTMLAudioElement | null = null;

  function updateButton() {
    playAll!.textContent = queued ? 'Stop playback' : 'Play all five';
  }

  function clearQueue() {
    queued = false;
    queueIndex = -1;
    updateButton();
  }

  async function playNext(index: number) {
    queueIndex = index;
    const player = players[index];
    player.currentTime = 0;
    try {
      await player.play();
    } catch {
      if (!queued || queueIndex !== index) return;
      clearQueue();
      status!.textContent = `Unable to play ${player.dataset.voiceName}. Try its player or download the MP3.`;
    }
  }

  players.forEach((player, index) => {
    const row = player.closest<HTMLElement>('[data-voice-row]')!;
    player.addEventListener('play', () => {
      if (queued && index !== queueIndex) clearQueue();
      active = player;
      players.forEach((other) => {
        if (other !== player) other.pause();
      });
      row.dataset.playing = '';
      status.textContent = `Playing ${queued ? `${index + 1} of ${players.length} · ` : ''}${player.dataset.voiceName}`;
    });
    player.addEventListener('pause', () => {
      delete row.dataset.playing;
      if (player !== active || player.ended) return;
      clearQueue();
      status.textContent = `Paused · ${player.dataset.voiceName}`;
    });
    player.addEventListener('ended', () => {
      delete row.dataset.playing;
      if (queued && queueIndex === index && index + 1 < players.length) {
        void playNext(index + 1);
        return;
      }
      const finishedQueue = queued;
      clearQueue();
      status.textContent = finishedQueue ? 'All five samples played. Listen again or choose a voice.' : `Finished · ${player.dataset.voiceName}`;
    });
    player.addEventListener('error', () => {
      delete row.dataset.playing;
      if (player === active || (queued && queueIndex === index)) clearQueue();
      status.textContent = `Audio unavailable for ${player.dataset.voiceName}. Try downloading the MP3.`;
    });
  });

  playAll.hidden = false;
  playAll.addEventListener('click', () => {
    const wasQueued = queued;
    clearQueue();
    active = null;
    players.forEach((player) => {
      player.pause();
    });
    if (wasQueued) {
      status.textContent = 'Playback stopped. Choose a voice or play all five again.';
      return;
    }
    queued = true;
    updateButton();
    void playNext(0);
  });
}
