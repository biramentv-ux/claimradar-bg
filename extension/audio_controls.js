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
    start.textContent = 'Realtime';
    start.title = 'Старт на tab audio capture към realtime word backend';

    const stop = document.createElement('button');
    stop.className = 'cr-btn';
    stop.textContent = 'Stop';
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
    let wordStream = [];

    function setStatus(text) { if (statusEl) statusEl.textContent = text; }
    function safe(text) { return String(text || '').replace(/[&<>'"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[ch])); }

    async function saveHistory(kind, text, claims = []) {
      try { await chrome.runtime.sendMessage({ type: 'CR_ADD_HISTORY', item: { kind, url: location.href, title: document.title, text, claims: claims.slice(0, 5) } }); } catch (_) {}
    }

    function renderWords(transcript, words, newWords) {
      if (!resultsEl) return '';
      if (Array.isArray(newWords) && newWords.length) {
        wordStream.push(...newWords);
        wordStream = wordStream.slice(-160);
      } else if (transcript && !wordStream.length) {
        wordStream = transcript.split(/\s+/).slice(-160);
      }
      const chips = wordStream.map((w, idx) => {
        const isNew = idx >= Math.max(0, wordStream.length - (newWords?.length || 0));
        return `<span class="cr-word ${isNew ? 'new' : ''}">${safe(w)}</span>`;
      }).join('');
      return `<div class="cr-card cr-live-words"><div class="cr-top"><span class="cr-pill v">WORD STREAM</span><span class="cr-pill">${wordStream.length} думи</span></div><div class="cr-wordbox">${chips || safe(transcript || 'Очаквам говор...')}</div></div>`;
    }

    function renderStreaming(message) {
      if (!resultsEl) return;
      const transcript = message.transcript || '';
      const claims = message.claims || [];
      const wordHtml = renderWords(transcript, message.words || [], message.new_words || []);
      const claimHtml = claims.slice(0, 8).map((item, i) => {
        const score = Math.max(5, Math.min(96, Number(item.confidence || item.score || 50)));
        const links = (item.sources || []).slice(0, 4).map(src => `<a href="${safe(src.url || '#')}" target="_blank">${safe(src.name || src.domain || 'източник')}</a>`).join('');
        return `<div class="cr-card"><div class="cr-top"><span class="cr-pill">LIVE #${String(i + 1).padStart(2, '0')}</span><span class="cr-pill">${safe(item.topic || 'друго')}</span><span class="cr-pill v">${safe(item.label || 'за проверка')}</span></div><div class="cr-claim">${safe(item.claim || '')}</div><div class="cr-meter"><span style="width:${score}%"></span></div><div class="cr-status">${score}% · ${safe(item.reason || 'realtime speech-to-text')}</div><div class="cr-links">${links}</div></div>`;
      }).join('');
      resultsEl.innerHTML = wordHtml + (claimHtml || '<div class="cr-card"><div class="cr-claim">Транскрипцията върви. Чакам достатъчно фактическо твърдение...</div></div>');
      saveHistory('audio realtime', transcript.slice(0, 1200), claims);
    }

    const extraStyle = document.createElement('style');
    extraStyle.textContent = `.cr-wordbox{display:flex;flex-wrap:wrap;gap:5px;line-height:1.6}.cr-word{font-size:12px;color:#e5e7eb;background:rgba(15,23,42,.55);border:1px solid rgba(148,163,184,.15);border-radius:999px;padding:3px 7px}.cr-word.new{color:#020617;background:#67e8f9;border-color:#67e8f9;box-shadow:0 0 14px rgba(34,211,238,.35)}.cr-live-words{border-color:rgba(103,232,249,.35)}`;
    document.documentElement.appendChild(extraStyle);

    start.addEventListener('click', async () => {
      wordStream = [];
      setStatus('Стартирам realtime tab audio capture...');
      const config = await chrome.runtime.sendMessage({ type: 'CR_GET_CONFIG' });
      if (config.enabled === false) {
        setStatus('Overlay е изключен от popup настройките.');
        return;
      }
      const response = await chrome.runtime.sendMessage({
        type: 'CR_START_TAB_AUDIO',
        backendUrl: config.backendUrl,
        chunkMs: config.chunkMs,
        realtimeMode: true
      });
      if (!response?.ok) setStatus('Грешка: ' + (response?.error || 'неуспешен старт'));
    });

    stop.addEventListener('click', async () => {
      await chrome.runtime.sendMessage({ type: 'CR_STOP_TAB_AUDIO' });
      setStatus('Realtime audio stop signal sent.');
    });

    settings.addEventListener('click', async () => {
      const current = await chrome.runtime.sendMessage({ type: 'CR_GET_CONFIG' });
      const backendUrl = prompt('WebSocket backend URL:', current.backendUrl || 'wss://dyrakarmy-claimradar-bg.hf.space/ws/realtime');
      if (!backendUrl) return;
      const chunkMsRaw = prompt('Chunk milliseconds:', String(current.chunkMs || 1400));
      const chunkMs = Math.max(600, Math.min(8000, Number(chunkMsRaw || 1400)));
      await chrome.runtime.sendMessage({ type: 'CR_SAVE_CONFIG', config: { backendUrl, chunkMs, realtimeMode: true, inputMode: 'audio' } });
      setStatus('Realtime backend записан: ' + backendUrl);
    });

    chrome.runtime.onMessage.addListener((message) => {
      if (message?.type !== 'CR_TRANSCRIPT_UPDATE') return;
      if (message.status) setStatus(message.status);
      if (message.transcript || message.claims || message.words || message.new_words) renderStreaming(message);
    });
  }

  waitForPanel();
})();
