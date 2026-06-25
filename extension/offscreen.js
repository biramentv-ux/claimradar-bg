let recorder = null;
let stream = null;
let socket = null;
let currentTabId = null;
let seq = 0;
let pendingQueue = [];

function sendToTab(payload) {
  chrome.runtime.sendMessage({ type: 'CR_TRANSCRIPT_UPDATE', tabId: currentTabId, ...payload });
}

function flushQueue() {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  while (pendingQueue.length) socket.send(pendingQueue.shift());
}

function connectSocket(url) {
  socket = new WebSocket(url);
  socket.binaryType = 'arraybuffer';
  socket.onopen = () => {
    sendToTab({ status: 'Свързано към realtime backend.' });
    flushQueue();
  };
  socket.onclose = () => sendToTab({ status: 'Realtime връзката е затворена.' });
  socket.onerror = () => sendToTab({ status: 'Грешка при realtime връзката.' });
  socket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      sendToTab({
        status: msg.status || 'Получен realtime резултат.',
        transcript: msg.transcript || '',
        window_transcript: msg.window_transcript || '',
        words: msg.words || [],
        new_words: msg.new_words || [],
        claims: msg.claims || [],
        partial: Boolean(msg.partial),
        elapsed: msg.elapsed || 0
      });
    } catch {
      sendToTab({ status: String(event.data || '') });
    }
  };
}

async function startCapture({ streamId, backendUrl, chunkMs, tabId, realtimeMode }) {
  currentTabId = tabId;
  seq = 0;
  pendingQueue = [];
  if (recorder && recorder.state !== 'inactive') recorder.stop();
  if (stream) stream.getTracks().forEach(t => t.stop());
  if (socket) socket.close();

  stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: {
        chromeMediaSource: 'tab',
        chromeMediaSourceId: streamId
      }
    },
    video: false
  });

  const audioContext = new AudioContext();
  const source = audioContext.createMediaStreamSource(stream);
  source.connect(audioContext.destination);

  connectSocket(backendUrl);

  const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? 'audio/webm;codecs=opus'
    : 'audio/webm';
  recorder = new MediaRecorder(stream, { mimeType, audioBitsPerSecond: 64000 });

  recorder.ondataavailable = async (event) => {
    if (!event.data || event.data.size === 0) return;
    const header = JSON.stringify({ type: 'chunk', seq: seq++, mimeType, ts: Date.now(), realtimeMode: Boolean(realtimeMode) });
    const audioBuffer = await event.data.arrayBuffer();
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      pendingQueue.push(header, audioBuffer);
      pendingQueue = pendingQueue.slice(-24);
      return;
    }
    socket.send(header);
    socket.send(audioBuffer);
  };

  recorder.onstop = () => {
    if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'stop' }));
    if (stream) stream.getTracks().forEach(t => t.stop());
    sendToTab({ status: 'Tab audio capture stopped.' });
  };

  recorder.start(Number(chunkMs || 1200));
  sendToTab({ status: `Tab audio realtime capture started: ${Number(chunkMs || 1200)} ms chunks.` });
}

function stopCapture() {
  if (recorder && recorder.state !== 'inactive') recorder.stop();
  if (stream) stream.getTracks().forEach(t => t.stop());
  if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'stop' }));
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === 'CR_OFFSCREEN_START') startCapture(message).catch(err => sendToTab({ status: 'Capture error: ' + String(err?.message || err) }));
  if (message?.type === 'CR_OFFSCREEN_STOP') stopCapture();
});
