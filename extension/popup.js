async function loadConfig() {
  const config = await chrome.runtime.sendMessage({ type: 'CR_GET_CONFIG' });
  document.getElementById('backendUrl').value = config.backendUrl || 'wss://dyrakarmy-claimradar-bg.hf.space/ws/realtime';
  document.getElementById('chunkMs').value = config.chunkMs || 1400;
}

function setStatus(text) {
  document.getElementById('status').textContent = text;
}

document.getElementById('openApp').addEventListener('click', () => {
  chrome.tabs.create({ url: 'https://dyrakarmy-claimradar-bg.hf.space' });
});

document.getElementById('openYouTube').addEventListener('click', () => {
  chrome.tabs.create({ url: 'https://www.youtube.com/results?search_query=българия+дебат+интервю+политика' });
});

document.getElementById('saveBackend').addEventListener('click', async () => {
  const backendUrl = document.getElementById('backendUrl').value.trim() || 'wss://dyrakarmy-claimradar-bg.hf.space/ws/realtime';
  const chunkMs = Math.max(600, Math.min(8000, Number(document.getElementById('chunkMs').value || 1400)));
  await chrome.runtime.sendMessage({ type: 'CR_SAVE_CONFIG', config: { backendUrl, chunkMs, realtimeMode: true } });
  setStatus('Запазено. Отвори страница и натисни „Realtime“ в overlay панела.');
});

loadConfig().catch(err => setStatus(String(err?.message || err)));
