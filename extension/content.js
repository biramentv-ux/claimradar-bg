(() => {
  if (window.__CLAIMRADAR_BG_LOADED__) return;
  window.__CLAIMRADAR_BG_LOADED__ = true;

  const APP_URL = 'https://dyrakarmy-claimradar-bg.hf.space';
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

  let active = false;
  let timer = null;
  let lastText = '';
  let minimized = false;

  const style = document.createElement('style');
  style.textContent = `
    #claimradar-bg-root{position:fixed;right:18px;bottom:18px;width:390px;max-width:calc(100vw - 30px);z-index:2147483647;font-family:Inter,Arial,sans-serif;color:#e5e7eb;}
    #claimradar-bg-panel{border:1px solid rgba(34,211,238,.35);border-radius:22px;background:linear-gradient(135deg,rgba(2,6,23,.96),rgba(30,27,75,.92));box-shadow:0 0 38px rgba(34,211,238,.22),inset 0 0 40px rgba(168,85,247,.10);overflow:hidden;backdrop-filter:blur(14px)}
    .cr-head{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid rgba(148,163,184,.18)}
    .cr-brand{display:grid;gap:2px}.cr-brand b{font-size:14px;color:white}.cr-brand span{font-size:10px;color:#67e8f9;letter-spacing:.12em;text-transform:uppercase}.cr-actions{display:flex;gap:7px}.cr-btn{cursor:pointer;border:1px solid rgba(34,211,238,.28);background:rgba(15,23,42,.70);color:#e0f2fe;border-radius:999px;padding:7px 9px;font-size:11px}.cr-btn.primary{background:linear-gradient(90deg,#0891b2,#7c3aed);border:0;color:white}.cr-body{padding:12px;display:grid;gap:10px;max-height:500px;overflow:auto}.cr-status{font-size:12px;color:#cbd5e1}.cr-card{border:1px solid rgba(34,211,238,.20);border-radius:16px;background:rgba(15,23,42,.55);padding:10px;display:grid;gap:8px}.cr-top{display:flex;gap:6px;flex-wrap:wrap;align-items:center}.cr-pill{font-size:10px;border-radius:999px;padding:4px 7px;background:rgba(37,99,235,.20);border:1px solid rgba(59,130,246,.25);color:#bfdbfe}.cr-pill.v{background:rgba(168,85,247,.20);border-color:rgba(168,85,247,.28);color:#e9d5ff}.cr-claim{font-size:12px;line-height:1.35;color:#f8fafc}.cr-meter{height:5px;background:rgba(148,163,184,.15);border-radius:99px;overflow:hidden}.cr-meter span{display:block;height:100%;background:linear-gradient(90deg,#22d3ee,#a855f7)}.cr-links{display:flex;gap:6px;flex-wrap:wrap}.cr-links a{font-size:10px;color:#cffafe!important;text-decoration:none;border:1px solid rgba(34,211,238,.22);border-radius:999px;padding:4px 7px;background:rgba(8,145,178,.12)}.cr-mini{position:fixed;right:18px;bottom:18px;z-index:2147483647;border:1px solid rgba(34,211,238,.35);background:linear-gradient(90deg,#0891b2,#7c3aed);color:white;border-radius:999px;padding:10px 13px;font:700 13px Arial;box-shadow:0 0 24px rgba(34,211,238,.3);cursor:pointer}.cr-hidden{display:none!important}
  `;
  document.documentElement.appendChild(style);

  const root = document.createElement('div');
  root.id = 'claimradar-bg-root';
  root.innerHTML = `
    <div id="claimradar-bg-panel">
      <div class="cr-head">
        <div class="cr-brand"><b>ClaimRadar BG</b><span>live overlay · v1.0</span></div>
        <div class="cr-actions">
          <button class="cr-btn primary" data-cr="toggle">Старт</button>
          <button class="cr-btn" data-cr="selection">Селекция</button>
          <button class="cr-btn" data-cr="app">App</button>
          <button class="cr-btn" data-cr="min">—</button>
        </div>
      </div>
      <div class="cr-body"><div class="cr-status">Готов. Отвори YouTube captions/transcript или маркирай текст.</div><div class="cr-results"></div></div>
    </div>`;
  document.documentElement.appendChild(root);

  const mini = document.createElement('button');
  mini.className = 'cr-mini cr-hidden';
  mini.textContent = 'ClaimRadar BG';
  document.documentElement.appendChild(mini);

  const $ = (sel) => root.querySelector(sel);
  const resultsEl = $('.cr-results');
  const statusEl = $('.cr-status');

  function topicFor(text) {
    const low = text.toLowerCase();
    let best = 'друго';
    let bestScore = 0;
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

  function collectYouTubeText() {
    const selectors = [
      '.ytp-caption-segment',
      'ytd-transcript-segment-renderer .segment-text',
      'yt-formatted-string.segment-text',
      '.caption-window span',
      '[class*="caption"] span'
    ];
    const parts = [];
    selectors.forEach(sel => document.querySelectorAll(sel).forEach(el => {
      const txt = (el.innerText || el.textContent || '').trim();
      if (txt && txt.length > 1) parts.push(txt);
    }));
    return [...new Set(parts)].join(' ');
  }

  function collectPageText() {
    const selection = String(window.getSelection && window.getSelection()).trim();
    if (selection.length > 40) return selection;
    const yt = collectYouTubeText();
    if (yt.length > 30) return yt;
    const article = document.querySelector('article, main, [role="main"]');
    return (article ? article.innerText : document.body.innerText || '').slice(0, 4000);
  }

  function searchUrl(claim, domain) {
    return 'https://duckduckgo.com/?q=' + encodeURIComponent(`${claim.slice(0, 120)} site:${domain}`);
  }

  function render(text, sourceLabel = 'автоматичен overlay') {
    const claims = splitSentences(text).map(claim => {
      const topic = topicFor(claim);
      const meta = scoreClaim(claim);
      return { claim, topic, ...meta };
    }).filter(x => x.score >= 35).slice(0, 8);

    statusEl.textContent = `${sourceLabel}: открити ${claims.length} твърдения`;
    if (!claims.length) {
      resultsEl.innerHTML = '<div class="cr-card"><div class="cr-claim">Няма достатъчно ясни твърдения. Включи subtitles/transcript или маркирай текст.</div></div>';
      return;
    }

    resultsEl.innerHTML = claims.map((item, i) => {
      const domains = SOURCE_DOMAINS[item.topic] || SOURCE_DOMAINS['друго'];
      const links = domains.map(d => `<a href="${searchUrl(item.claim, d)}" target="_blank">${d}</a>`).join('');
      return `<div class="cr-card"><div class="cr-top"><span class="cr-pill">#${String(i + 1).padStart(2, '0')}</span><span class="cr-pill">${item.topic}</span><span class="cr-pill v">${item.label}</span></div><div class="cr-claim">${escapeHtml(item.claim)}</div><div class="cr-meter"><span style="width:${item.score}%"></span></div><div class="cr-status">${item.score}% · ${item.reasons}</div><div class="cr-links">${links}</div></div>`;
    }).join('');
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>'"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[ch]));
  }

  function start() {
    active = true;
    $('[data-cr="toggle"]').textContent = 'Стоп';
    tick();
    timer = setInterval(tick, 4500);
  }

  function stop() {
    active = false;
    $('[data-cr="toggle"]').textContent = 'Старт';
    clearInterval(timer);
    timer = null;
    statusEl.textContent = 'Спряно.';
  }

  function tick() {
    const text = collectPageText();
    if (!text || text === lastText) return;
    lastText = text;
    render(text, location.hostname.includes('youtube') ? 'YouTube/live режим' : 'страница/селекция');
  }

  root.addEventListener('click', (e) => {
    const action = e.target && e.target.getAttribute('data-cr');
    if (!action) return;
    if (action === 'toggle') active ? stop() : start();
    if (action === 'selection') render(String(window.getSelection()).trim() || collectPageText(), 'ръчен анализ');
    if (action === 'app') window.open(APP_URL, '_blank');
    if (action === 'min') {
      minimized = true;
      root.classList.add('cr-hidden');
      mini.classList.remove('cr-hidden');
    }
  });

  mini.addEventListener('click', () => {
    minimized = false;
    mini.classList.add('cr-hidden');
    root.classList.remove('cr-hidden');
  });

  if (location.hostname.includes('youtube.com')) {
    setTimeout(start, 1500);
  }
})();
