document.getElementById('openApp').addEventListener('click', () => {
  chrome.tabs.create({ url: 'https://dyrakarmy-claimradar-bg.hf.space' });
});

document.getElementById('openYouTube').addEventListener('click', () => {
  chrome.tabs.create({ url: 'https://www.youtube.com/results?search_query=българия+дебат+интервю+политика' });
});
