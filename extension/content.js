(() => {
  if (window.__CLAIMRADAR_BG_LOADED__) return;
  window.__CLAIMRADAR_BG_LOADED__ = true;

  const DEFAULT_APP = 'https://dyrakarmy-claimradar-bg.hf.space';
  const SOURCE_DOMAINS = {
    'икономика': ['nsi.bg', 'bnb.bg', 'ec.europa.eu/eurostat'],
    'инфлация': ['nsi.bg', 'ec.europa.eu/eurostat', 'bnb.bg'],
    'пенсии': ['nssi.bg', 'nsi.bg'],
    'данъци': ['nra.bg', 'minfin.bg'],
    'избори': ['cik.bg', 'parliament.bg'],
    'закони': ['parliament.bg', 'dv.parliament.bg', 'gov.bg'],
    'бюджет': ['minfin.bg', 'parliament.bg', 'nsi.bg'],
    'здравеопазване': ['mh.government.bg', 'nhif.bg', 'nsi.bg'],
    'образование': ['mon.bg', 'nsi.bg'],
    'енергетика': ['me.government.bg', 'dker.bg', 'bnb.bg'],
    'ес': ['ec.europa.eu/eurostat', 'commission.europa.eu'],
    'друго': ['factcheck.bg', 'bta.bg', 'bnr.bg', 'nsi.bg']
  };
  const KEYWORDS = {
    'инфлация': ['инфлация', 'цени', 'поскъп', 'ипц', 'храни', 'горива'],
    'пенсии': ['пенсия', 'пенсии', 'пенсионер', 'нои', 'осигур'],
    'данъци': ['данък', 'данъци', 'ддс', 'акциз', 'нап'],
    'избори': ['избор', 'избори', 'цик', 'мандат', 'партия', 'глас'],
    'закони': ['закон', 'парламент', 'народно събрание', 'депутат', 'държавен вестник'],
    'бюджет': ['бюджет', 'дефицит', 'дълг', 'финанси', 'разходи', 'приходи'],
    'здравеопазване': ['здраве', 'болница', 'нзок', 'лекар', 'пациент'],
    'образование': ['училище', 'учител', 'мон', 'образование', 'университет'],
    'енергетика': ['ток', 'газ', 'енерг', 'кевр', 'електро', 'петрол'],
    'ес': ['ес', 'европа', 'евростат', 'европейски', 'шенген', 'еврозона'],
    'икономика': ['бвп', 'иконом', 'безработ', 'заплати', 'доходи', 'растеж', 'инвестиции']
  };
  const SUBJECTIVE = ['мисля', 'според мен', 'вярвам', 'ужасен', 'страхотен', 'предател', 'мафия', 'срам'];

  let config = {
    enabled: true,
    inputMode: 'captions',
    floatingMini: false,
    autoOpenTranscript: true,
    autoStartYouTube: true,
    appUrl: DEFAULT_APP
  };
  let active = false;
  let timer = null;
  let lastText = '';
  let lastClaims = [];
  let minimized = false;

  const style = document.createElement('style');
  style.textContent = `
    #claimradar-bg-root{position:fixed;right:18px;bottom:18px;width:420px;max-width:calc(100vw - 30px);z-index:2147483647;font-family:Inter,Arial,sans-serif;color:#e5e7eb;}
    #claimradar-bg-panel{border:1px solid rgba(34,211,238,.35);border-radius:22px;background:linear-gradient(135deg,rgba(2,6,23,.96),rgba(30,27,75,.92));box-shadow:0 0 38px rgba(34,211,238,.22),inset 0 0 40px rgba(168,85,247,.10);overflow:hidden;backdrop-filter:blur(14px)}
    .cr-head{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid rgba(148,163,184,.18)}
    .cr-brand{display:grid;gap:2px}.cr-brand b{font-size:14px;color:white}.cr-brand span{font-size:10px;color:#67e8f9;letter-spacing:.12em;text-transform:uppercase}.cr-actions{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}.cr-btn{cursor:pointer;border:1px solid rgba(34,211,238,.28);background:rgba(15,23,42,.70);color:#e0f2fe;border-radius:999px;padding:7px 9px;font-size:11px}.cr-btn.primary{background:linear-gradient(90deg,#0891b2,#7c3aed);border:0;color:white}.cr-btn.danger{border-color:rgba(248,113,113,.45);color:#fecaca}.cr-body{padding:12px;display:grid;gap:10px;max-height:540px;overflow:auto}.cr-status{font-size:12px;color:#cbd5e1}.cr-toolbar{display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px}.cr-card{border:1px solid rgba(34,211,238,.20);border-radius:16px;background:rgba(15,23,42,.55);padding:10px;display:grid;gap:8px}.cr-top{display:flex;gap:6px;flex-wrap:wrap;align-items:center}.cr-pill{font-size:10px;border-radius:999px;padding:4px 7px;background:rgba(37,99,235,.20);border:1px solid rgba(59,130,246,.25);color:#bfdbfe}.cr-pill.v{background:rgba(168,85,247,.20);border-color:rgba(168,85,247,.28);color:#e9d5ff}.cr-claim{font-size:12px;line-height:1.35;color:#f8fafc}.cr-meter{height:5px;background:rgba(148,163,184,.15);border-radius:99px;overflow:hidden}.cr-meter span{display:block;height:100%;background:linear-gradient(90deg,#22d3ee,#a855f7)}.cr-links{display:flex;gap:6px;flex-wrap:wrap}.cr-links a{font-size:10px;color:#cffafe!important;text-decoration:none;border:1px solid rgba(34,211,238,.22);border-radius:999px;padding:4px 7px;background:rgba(8,145,178,.12)}.cr-mini{position:fixed;right:18px;bottom:18px;z-index:2147483647;border:1px solid rgba(34,211,238,.35);background:linear-gradient(90deg,#0891b2,#7c3aed);color:white;border-radius:999px;padding:10px 13px;font:700 13px Arial;box-shadow:0 0 24px rgba(34,211,238,.3);cursor:pointer}.cr-hidden{display:none!important}.cr-muted{color:#94a3b8;font-size:11px}.cr-copyrow{display:flex;gap:6px;flex-wrap:wrap}.cr-copyrow button{font-size:10px;padding:5px 7px}.cr-mode{font-size:10px;color:#94a3b8}.cr-hint{border:1px dashed rgba(34,211,238,.25);border-radius:14px;padding:8px;color:#cbd5e1;font-size:11px;background:rgba(8,145,178,.10)}
  `;
  document.documentElement.appendChild(style);

  const root = document.createElement('div');
  root.id = 'claimradar-bg-root';
  root.innerHTML = `
    <div id="claimradar-bg-panel">
      <div class="cr-head">
        <div class="cr-brand"><b>ClaimRadar BG</b><span>extension polish · v2.2</span><em class="cr-mode">captions mode</em></div>
        <div class="cr-actions">
          <button class="cr-btn primary" data-cr="toggle">Старт</button>
          <button class="cr-btn" data-cr="selection">Селекция</button>
          <button class="cr-btn" data-cr="app">App</button>
          <button class="cr-btn" data-cr="min">—</button>
        </div>
      </div>
      <div class="cr-body">
        <div class="cr-status">Готов. Captions/audio/selection режим според настройките.</div>
        <div class="cr-toolbar">
          <button class="cr-btn" data-cr="copy-all">Copy</button>
          <button class="cr-btn" data-cr="send-app">Send app</button>
          <button class="cr-btn danger" data-cr="report">Report</button>
        </div>
        <div class="cr-hint">YouTube: ако няма текст, отвори transcript/captions. Extension-ът ще се опита автоматично.</div>
        <div class="cr-results"></div>
      </div>
    </div>`;
  document.documentElement.appendChild(root);

  const mini = document.createElement('button');
  mini.className = 'cr-mini cr-hidden';
  mini.textContent = 'ClaimRadar BG';
  document.documentElement.appendChild(mini);

  const $ = (sel) => root.querySelector(sel);
  const resultsEl = $('.cr-results');
  const statusEl = $('.cr-status');
  const modeEl = $('.cr-mode');

  function escapeHtml(str) {
    return String(str || '').replace(/[&<>'"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[ch]));
  }

  async function loadConfig() {
    try {
      const loaded = await chrome.runtime.sendMessage({ type: 'CR_GET_CONFIG' });
      config = { ...config, ...(loaded || {}) };
    } catch (_) {}
    applyConfig();
  }

  function applyConfig() {
    const enabled = config.enabled !== false;
    root.classList.toggle('cr-hidden', !enabled || minimized || config.floatingMini);
    mini.classList.toggle('cr-hidden', !enabled || (!minimized && !config.floatingMini));
    modeEl.textContent = `${config.inputMode || 'captions'} mode`;
    if (!enabled) stop('Overlay изключен от popup настройките.');
    if (config.inputMode === 'audio') statusEl.textContent = 'Audio mode: натисни Realtime бутона в overlay.';
  }

  function topicFor(text) {
    const low = text.toLowerCase();
    let best = 'друго', bestScore = 0;
    Object.entries(KEYWORDS).forEach(([topic, words]) => {
      const score = words.reduce((n, w) => n + (low.includes(w) ? 1 : 0), 0);
      if (score > bestScore) { bestScore = score; best = topic; }
    });
    return best;
  }

  function scoreClaim(text) {
    const low = text.toLowerCase();
    let score = 18;
    const reasons = [];
    if (/\d/.test(text)) { score += 32; reasons.push('число/година'); }
    if (['%', 'процент', 'милиона', 'милиарда', 'млн', 'млрд', 'лв', 'евро'].some(x => low.includes(x))) { score += 20; reasons.push('мерима стойност'); }
    if (['повече', 'по-малко', 'увелич', 'намал', 'спрямо', 'най-', 'първи', 'последни'].some(x => low.includes(x))) { score += 18; reasons.push('сравнение'); }
    if (Object.values(KEYWORDS).flat().some(x => low.includes(x))) { score += 15; reasons.push('публична тема'); }
    if (SUBJECTIVE.some(x => low.includes(x))) { score -= 25; reasons.push('възможно мнение'); }
    score = Math.max(5, Math.min(96, score));
    const label = score >= 70 ? 'вероятно проверимо' : score >= 45 ? 'за проверка' : SUBJECTIVE.some(x => low.includes(x)) ? 'мнение' : 'нужни са източници';
    return { score, label, reasons: reasons.join(', ') || 'общо твърдение' };
  }

  function splitSentences(text) {
    return (text || '').replace(/\s+/g, ' ').split(/(?<=[.!?])\s+|\n+/).map(s => s.trim()).filter(s => s.length > 25);
  }

  function tryOpenYouTubeTranscript() {
    if (!location.hostname.includes('youtube.com') || config.autoOpenTranscript === false) return;
    const needles = ['show transcript', 'transcript', 'показване на препис', 'препис', 'транскрипт'];
    const candidates = [...document.querySelectorAll('button, tp-yt-paper-item, ytd-menu-service-item-renderer, yt-button-shape button')];
    const btn = candidates.find(el => needles.some(n => (el.innerText || el.textContent || el.getAttribute('aria-label') || '').toLowerCase().includes(n)));
    if (btn && !document.querySelector('ytd-transcript-renderer, ytd-engagement-panel-section-list-renderer[target-id="engagement-panel-searchable-transcript"]')) {
      try { btn.click(); statusEl.textContent = 'Опитвам да отворя YouTube transcript panel...'; } catch (_) {}
    }
  }

  function collectYouTubeText() {
    const selectors = ['.ytp-caption-segment', 'ytd-transcript-segment-renderer .segment-text', 'yt-formatted-string.segment-text', '.caption-window span', '[class*="caption"] span'];
    const parts = [];
    selectors.forEach(sel => document.querySelectorAll(sel).forEach(el => {
      const txt = (el.innerText || el.textContent || '').trim();
      if (txt && txt.length > 1) parts.push(txt);
    }));
    return [...new Set(parts)].join(' ');
  }

  function collectPageText() {
    const selection = String(window.getSelection && window.getSelection()).trim();
    if (config.inputMode === 'selection' && selection.length > 10) return selection;
    if (selection.length > 40) return selection;
    if (location.hostname.includes('youtube.com')) {
      tryOpenYouTubeTranscript();
      const yt = collectYouTubeText();
      if (yt.length > 30) return yt;
    }
    const article = document.querySelector('article, main, [role="main"]');
    return (article ? article.innerText : document.body.innerText || '').slice(0, 4000);
  }

  function searchUrl(claim, domain) {
    return 'https://duckduckgo.com/?q=' + encodeURIComponent(`${claim.slice(0, 120)} site:${domain}`);
  }

  async function saveHistory(kind, text, claims = []) {
    try { await chrome.runtime.sendMessage({ type: 'CR_ADD_HISTORY', item: { kind, url: location.href, title: document.title, text, claims: claims.slice(0, 5) } }); } catch (_) {}
  }

  function render(text, sourceLabel = 'автоматичен overlay') {
    const claims = splitSentences(text).map(claim => {
      const topic = topicFor(claim);
      const meta = scoreClaim(claim);
      return { claim, topic, ...meta };
    }).filter(x => x.score >= 35).slice(0, 8);

    lastClaims = claims;
    statusEl.textContent = `${sourceLabel}: открити ${claims.length} твърдения`;
    if (!claims.length) {
      resultsEl.innerHTML = '<div class="cr-card"><div class="cr-claim">Няма достатъчно ясни твърдения. Включи subtitles/transcript или маркирай текст.</div></div>';
      return;
    }

    resultsEl.innerHTML = claims.map((item, i) => {
      const domains = SOURCE_DOMAINS[item.topic] || SOURCE_DOMAINS['друго'];
      const links = domains.map(d => `<a href="${searchUrl(item.claim, d)}" target="_blank">${d}</a>`).join('');
      return `<div class="cr-card" data-claim-index="${i}"><div class="cr-top"><span class="cr-pill">#${String(i + 1).padStart(2, '0')}</span><span class="cr-pill">${item.topic}</span><span class="cr-pill v">${item.label}</span></div><div class="cr-claim">${escapeHtml(item.claim)}</div><div class="cr-meter"><span style="width:${item.score}%"></span></div><div class="cr-status">${item.score}% · ${item.reasons}</div><div class="cr-links">${links}</div><div class="cr-copyrow"><button class="cr-btn" data-cr="copy-claim" data-index="${i}">Copy claim</button><button class="cr-btn" data-cr="send-claim" data-index="${i}">Send to app</button><button class="cr-btn danger" data-cr="report-claim" data-index="${i}">Report</button></div></div>`;
    }).join('');
    saveHistory(sourceLabel, text.slice(0, 1000), claims);
  }

  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); statusEl.textContent = 'Копирано.'; }
    catch (_) { statusEl.textContent = 'Не успях да копирам автоматично.'; }
  }

  function claimsAsText() {
    return lastClaims.map((c, i) => `${i + 1}. [${c.topic}] [${c.label}] ${c.claim}`).join('\n');
  }

  function openAppWithText(text, kind = 'claim') {
    const url = `${config.appUrl || DEFAULT_APP}?extension=${encodeURIComponent(kind)}&text=${encodeURIComponent(text.slice(0, 900))}`;
    window.open(url, '_blank');
  }

  function reportText(text) {
    saveHistory('report', text, lastClaims);
    copyText(`REPORT ClaimRadar BG\nURL: ${location.href}\nTITLE: ${document.title}\nTEXT:\n${text}`);
    window.open(`${config.appUrl || DEFAULT_APP}`, '_blank');
    statusEl.textContent = 'Report записан в local history и копиран. Отвори feedback таба в app.';
  }

  function start() {
    if (config.enabled === false) return applyConfig();
    active = true;
    $('[data-cr="toggle"]').textContent = 'Стоп';
    tick();
    timer = setInterval(tick, 4500);
  }

  function stop(message = 'Спряно.') {
    active = false;
    $('[data-cr="toggle"]').textContent = 'Старт';
    clearInterval(timer);
    timer = null;
    statusEl.textContent = message;
  }

  function tick() {
    if (config.inputMode === 'audio') {
      statusEl.textContent = 'Audio mode: използвай бутона Realtime.';
      return;
    }
    const text = collectPageText();
    if (!text || text === lastText) return;
    lastText = text;
    render(text, location.hostname.includes('youtube') ? 'YouTube captions/transcript' : 'страница/селекция');
  }

  root.addEventListener('click', (e) => {
    const action = e.target && e.target.getAttribute('data-cr');
    if (!action) return;
    const idx = Number(e.target.getAttribute('data-index'));
    const claim = Number.isFinite(idx) && lastClaims[idx] ? lastClaims[idx].claim : '';
    if (action === 'toggle') active ? stop() : start();
    if (action === 'selection') render(String(window.getSelection()).trim() || collectPageText(), 'ръчен анализ');
    if (action === 'app') window.open(config.appUrl || DEFAULT_APP, '_blank');
    if (action === 'min') { minimized = true; root.classList.add('cr-hidden'); mini.classList.remove('cr-hidden'); }
    if (action === 'copy-all') copyText(claimsAsText() || collectPageText().slice(0, 1500));
    if (action === 'send-app') openAppWithText(claimsAsText() || collectPageText().slice(0, 1500), 'claims');
    if (action === 'report') reportText(claimsAsText() || collectPageText().slice(0, 1500));
    if (action === 'copy-claim') copyText(claim);
    if (action === 'send-claim') openAppWithText(claim, 'claim');
    if (action === 'report-claim') reportText(claim);
  });

  mini.addEventListener('click', () => {
    minimized = false;
    config.floatingMini = false;
    mini.classList.add('cr-hidden');
    root.classList.remove('cr-hidden');
  });

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === 'CR_CONFIG_UPDATED') {
      config = { ...config, ...(message.config || {}) };
      applyConfig();
      statusEl.textContent = 'Настройките са обновени от popup.';
    }
  });

  loadConfig().then(() => {
    if (config.enabled !== false && location.hostname.includes('youtube.com') && config.autoStartYouTube !== false && config.inputMode !== 'audio') {
      setTimeout(start, 1500);
    }
  });
})();
