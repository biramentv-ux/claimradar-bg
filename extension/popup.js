async function loadConfig() {
  const config = await chrome.runtime.sendMessage({ type: 'CR_GET_CONFIG' });
  document.getElementById('backendUrl').value = config.backendUrl || 'ws://127.0.0.1:7861/ws/transcribe';
  document.getElementById('chunkMs').value = config.chunkMs || 4000;
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
  const backendUrl = document.getElementById('backendUrl').value.trim();
  const chunkMs = Math.max(1000, Math.min(15000, Number(document.getElementById('chunkMs').value || 4000)));
  await chrome.runtime.sendMessage({ type: 'CR_SAVE_CONFIG', config: { backendUrl, chunkMs } });
  setStatus('Запазено. Отвори страница и натисни „Аудио“ в overlay панела.');
});

loadConfig().catch(err => setStatus(String(err?.message || err)));
