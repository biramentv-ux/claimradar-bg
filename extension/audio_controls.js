(() => {
  if (window.__CLAIMRADAR_AUDIO_CONTROLS__) return;
  window.__CLAIMRADAR_AUDIO_CONTROLS__ = true;

  function waitForPanel() {
    const root = document.getElementById('claimradar-bg-root');
    const actions = root && root.querySelector('.cr-actions');
    if (!root || !actions) {
      setTimeout(waitForPanel, 500);
      return;
    }
    install(root, actions);
  }

  function install(root, actions) {
    const start = document.createElement('button');
    start.className = 'cr-btn primary';
    start.textContent = 'Аудио';
    start.title = 'Старт на tab audio capture към streaming backend';

    const stop = document.createElement('button');
    stop.className = 'cr-btn';
    stop.textContent = 'Stop audio';
    stop.title = 'Спира tab audio capture';

    const settings = document.createElement('button');
    settings.className = 'cr-btn';
    settings.textContent = 'Backend';
    settings.title = 'Настрой websocket backend URL';

    actions.prepend(stop);
    actions.prepend(settings);
    actions.prepend(start);

    const statusEl = root.querySelector('.cr-status');
    const resultsEl = root.querySelector('.cr-results');

    function setStatus(text) {
      if (statusEl) statusEl.textContent = text;
    }

    function safe(text) {
      return String(text || '').replace(/[&<>'"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[ch]));
    }

    function renderStreaming(transcript, claims) {
      if (!resultsEl) return;
      if (!claims || !claims.length) {
        resultsEl.innerHTML = `<div class="cr-card"><div class="cr-claim"><b>Live transcript:</b><br>${safe(transcript || 'Очаквам говор...')}</div></div>`;
        return;
      }
      resultsEl.innerHTML = claims.slice(0, 8).map((item, i) => {
        const score = Math.max(5, Math.min(96, Number(item.confidence || item.score || 50)));
        const links = (item.sources || []).slice(0, 4).map(src => `<a href="${safe(src.url || '#')}" target="_blank">${safe(src.name || src.domain || 'източник')}</a>`).join('');
        return `<div class="cr-card"><div class="cr-top"><span class="cr-pill">LIVE #${String(i + 1).padStart(2, '0')}</span><span class="cr-pill">${safe(item.topic || 'друго')}</span><span class="cr-pill v">${safe(item.label || 'за проверка')}</span></div><div class="cr-claim">${safe(item.claim || '')}</div><div class="cr-meter"><span style="width:${score}%"></span></div><div class="cr-status">${score}% · ${safe(item.reason || 'streaming speech-to-text')}</div><div class="cr-links">${links}</div></div>`;
      }).join('');
    }

    start.addEventListener('click', async () => {
      setStatus('Стартирам tab audio capture...');
      const config = await chrome.runtime.sendMessage({ type: 'CR_GET_CONFIG' });
      const response = await chrome.runtime.sendMessage({
        type: 'CR_START_TAB_AUDIO',
        backendUrl: config.backendUrl,
        chunkMs: config.chunkMs
      });
      if (!response?.ok) setStatus('Грешка: ' + (response?.error || 'неуспешен старт'));
    });

    stop.addEventListener('click', async () => {
      await chrome.runtime.sendMessage({ type: 'CR_STOP_TAB_AUDIO' });
      setStatus('Audio capture stop signal sent.');
    });

    settings.addEventListener('click', async () => {
      const current = await chrome.runtime.sendMessage({ type: 'CR_GET_CONFIG' });
      const backendUrl = prompt('WebSocket backend URL:', current.backendUrl || 'ws://127.0.0.1:7861/ws/transcribe');
      if (!backendUrl) return;
      const chunkMsRaw = prompt('Chunk milliseconds:', String(current.chunkMs || 4000));
      const chunkMs = Math.max(1000, Math.min(15000, Number(chunkMsRaw || 4000)));
      await chrome.runtime.sendMessage({ type: 'CR_SAVE_CONFIG', config: { backendUrl, chunkMs } });
      setStatus('Backend записан: ' + backendUrl);
    });

    chrome.runtime.onMessage.addListener((message) => {
      if (message?.type !== 'CR_TRANSCRIPT_UPDATE') return;
      if (message.status) setStatus(message.status);
      if (message.transcript || message.claims) renderStreaming(message.transcript, message.claims || []);
    });
  }

  waitForPanel();
})();
