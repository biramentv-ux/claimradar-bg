const OFFSCREEN_DOCUMENT_PATH = 'offscreen.html';

async function hasOffscreenDocument() {
  if (!chrome.offscreen || !chrome.runtime.getContexts) return false;
  const contexts = await chrome.runtime.getContexts({
    contextTypes: ['OFFSCREEN_DOCUMENT'],
    documentUrls: [chrome.runtime.getURL(OFFSCREEN_DOCUMENT_PATH)]
  });
  return contexts.length > 0;
}

async function setupOffscreenDocument() {
  if (await hasOffscreenDocument()) return;
  await chrome.offscreen.createDocument({
    url: OFFSCREEN_DOCUMENT_PATH,
    reasons: ['USER_MEDIA'],
    justification: 'Capture current tab audio for user-started Bulgarian realtime speech-to-text transcription.'
  });
}

async function getDefaultConfig() {
  return await chrome.storage.sync.get({
    backendUrl: 'wss://dyrakarmy-claimradar-bg.hf.space/ws/realtime',
    chunkMs: 1400,
    autoSendToOverlay: true,
    realtimeMode: true
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    if (message?.type === 'CR_GET_CONFIG') {
      sendResponse(await getDefaultConfig());
      return;
    }

    if (message?.type === 'CR_SAVE_CONFIG') {
      await chrome.storage.sync.set(message.config || {});
      sendResponse({ ok: true });
      return;
    }

    if (message?.type === 'CR_START_TAB_AUDIO') {
      await setupOffscreenDocument();
      const config = await getDefaultConfig();
      const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: sender.tab?.id });
      chrome.runtime.sendMessage({
        type: 'CR_OFFSCREEN_START',
        streamId,
        tabId: sender.tab?.id,
        backendUrl: message.backendUrl || config.backendUrl,
        chunkMs: Number(message.chunkMs || config.chunkMs || 1400),
        realtimeMode: Boolean(message.realtimeMode ?? config.realtimeMode)
      });
      sendResponse({ ok: true });
      return;
    }

    if (message?.type === 'CR_STOP_TAB_AUDIO') {
      chrome.runtime.sendMessage({ type: 'CR_OFFSCREEN_STOP' });
      sendResponse({ ok: true });
      return;
    }

    if (message?.type === 'CR_TRANSCRIPT_UPDATE' && message.tabId) {
      chrome.tabs.sendMessage(message.tabId, message).catch(() => {});
      sendResponse({ ok: true });
      return;
    }
  })().catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
  return true;
});
