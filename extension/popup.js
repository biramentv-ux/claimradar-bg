const DEFAULT_APP = 'https://dyrakarmy-claimradar-bg.hf.space';
const DEFAULT_WS = 'wss://dyrakarmy-claimradar-bg.hf.space/ws/realtime';

function $(id) { return document.getElementById(id); }
function setStatus(text) { $('status').textContent = text; }

async function loadConfig() {
  const config = await chrome.runtime.sendMessage({ type: 'CR_GET_CONFIG' });
  $('enabled').checked = config.enabled !== false;
  $('floatingMini').checked = Boolean(config.floatingMini);
  $('autoOpenTranscript').checked = config.autoOpenTranscript !== false;
  $('autoStartYouTube').checked = config.autoStartYouTube !== false;
  $('inputMode').value = config.inputMode || 'captions';
  $('backendUrl').value = config.backendUrl || DEFAULT_WS;
  $('chunkMs').value = config.chunkMs || 1400;
}

async function saveConfig() {
  const backendUrl = $('backendUrl').value.trim() || DEFAULT_WS;
  const chunkMs = Math.max(600, Math.min(8000, Number($('chunkMs').value || 1400)));
  const config = {
    enabled: $('enabled').checked,
    floatingMini: $('floatingMini').checked,
    autoOpenTranscript: $('autoOpenTranscript').checked,
    autoStartYouTube: $('autoStartYouTube').checked,
    inputMode: $('inputMode').value,
    backendUrl,
    chunkMs,
    realtimeMode: true,
    appUrl: DEFAULT_APP
  };
  await chrome.runtime.sendMessage({ type: 'CR_SAVE_CONFIG', config });
  setStatus('Настройките са запазени.');
  return config;
}

async function pushConfigToActiveTab() {
  const config = await saveConfig();
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id) {
    await chrome.tabs.sendMessage(tab.id, { type: 'CR_CONFIG_UPDATED', config }).catch(() => null);
  }
  setStatus('Приложено към текущия tab.');
}

async function renderHistory() {
  const response = await chrome.runtime.sendMessage({ type: 'CR_GET_HISTORY' });
  const history = response?.history || [];
  const box = $('history');
  if (!history.length) {
    box.innerHTML = '<div class="muted">Local history е празна.</div>';
    return;
  }
  box.innerHTML = history.slice(0, 8).map(item => `
    <div class="item">
      <b>${escapeHtml(item.kind || 'claim')} · ${new Date(item.createdAt || Date.now()).toLocaleString()}</b>
      <p>${escapeHtml((item.text || '').slice(0, 180))}</p>
    </div>
  `).join('');
}

function escapeHtml(str) {
  return String(str || '').replace(/[&<>'"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[ch]));
}

$('openApp').addEventListener('click', () => chrome.tabs.create({ url: DEFAULT_APP }));
$('openYouTube').addEventListener('click', () => chrome.tabs.create({ url: 'https://www.youtube.com/results?search_query=българия+дебат+интервю+политика' }));
$('saveBackend').addEventListener('click', saveConfig);
$('sendConfig').addEventListener('click', pushConfigToActiveTab);
$('clearHistory').addEventListener('click', async () => {
  await chrome.runtime.sendMessage({ type: 'CR_CLEAR_HISTORY' });
  await renderHistory();
  setStatus('Local history е изчистена.');
});

loadConfig().then(renderHistory).catch(err => setStatus(String(err?.message || err)));
