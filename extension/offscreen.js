let recorder = null;
let stream = null;
let socket = null;
let currentTabId = null;
let seq = 0;

function sendToTab(payload) {
  chrome.runtime.sendMessage({ type: 'CR_TRANSCRIPT_UPDATE', tabId: currentTabId, ...payload });
}

function connectSocket(url) {
  socket = new WebSocket(url);
  socket.binaryType = 'arraybuffer';
  socket.onopen = () => sendToTab({ status: 'Свързано към streaming backend.' });
  socket.onclose = () => sendToTab({ status: 'Streaming връзката е затворена.' });
  socket.onerror = () => sendToTab({ status: 'Грешка при streaming връзката.' });
  socket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      sendToTab({
        status: msg.status || 'Получен резултат.',
        transcript: msg.transcript || '',
        claims: msg.claims || [],
        partial: Boolean(msg.partial)
      });
    } catch {
      sendToTab({ status: String(event.data || '') });
    }
  };
}

async function startCapture({ streamId, backendUrl, chunkMs, tabId }) {
  currentTabId = tabId;
  seq = 0;
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
  recorder = new MediaRecorder(stream, { mimeType });

  recorder.ondataavailable = async (event) => {
    if (!event.data || event.data.size === 0) return;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    const header = JSON.stringify({ type: 'chunk', seq: seq++, mimeType, ts: Date.now() });
    socket.send(header);
    socket.send(await event.data.arrayBuffer());
  };

  recorder.onstop = () => {
    if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'stop' }));
    if (stream) stream.getTracks().forEach(t => t.stop());
    sendToTab({ status: 'Tab audio capture stopped.' });
  };

  recorder.start(Number(chunkMs || 4000));
  sendToTab({ status: 'Tab audio capture started.' });
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
