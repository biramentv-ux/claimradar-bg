from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import Response

MODEL_MANAGER_JS = """
async function api(path, opts={}) {
  const response = await fetch(path, {headers: {'content-type': 'application/json'}, ...opts});
  return await response.json();
}
function setVal(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  if (el.type === 'checkbox') el.checked = !!value;
  else el.value = value ?? '';
}
function getVal(id) {
  const el = document.getElementById(id);
  return el && el.type === 'checkbox' ? el.checked : (el ? el.value : '');
}
async function refreshAll() {
  const data = await api('/api/local-ai/model-manager/status');
  const cfg = data.model_manager.config;
  setVal('profile', cfg.active_profile);
  setVal('engine', cfg.transcription_engine);
  setVal('device', cfg.whisper_device);
  setVal('compute', cfg.whisper_compute_type);
  setVal('offline', cfg.offline_mode);
  setVal('online', cfg.online_evidence_mode);
  setVal('whisperx', cfg.whisperx_enabled);
  setVal('ollamaLow', cfg.ollama_models.low);
  setVal('ollamaBalanced', cfg.ollama_models.balanced);
  setVal('ollamaPower', cfg.ollama_models.power);
  setVal('whisperLow', cfg.whisper_models.low);
  setVal('whisperBalanced', cfg.whisper_models.balanced);
  setVal('whisperPower', cfg.whisper_models.power);
  document.getElementById('statusOut').textContent = JSON.stringify(data, null, 2);
  document.getElementById('cacheOut').textContent = JSON.stringify(data.model_manager.whisper_cache, null, 2);
}
async function saveConfig() {
  const payload = {
    active_profile: getVal('profile'),
    offline_mode: getVal('offline'),
    online_evidence_mode: getVal('online'),
    transcription_engine: getVal('engine'),
    whisper_device: getVal('device'),
    whisper_compute_type: getVal('compute'),
    whisperx_enabled: getVal('whisperx'),
    ollama_models: {low: getVal('ollamaLow'), balanced: getVal('ollamaBalanced'), power: getVal('ollamaPower')},
    whisper_models: {low: getVal('whisperLow'), balanced: getVal('whisperBalanced'), power: getVal('whisperPower')}
  };
  const data = await api('/api/local-ai/model-manager/config', {method: 'POST', body: JSON.stringify(payload)});
  document.getElementById('statusOut').textContent = JSON.stringify(data, null, 2);
}
async function listOllama() {
  const data = await api('/api/local-ai/ollama/models');
  document.getElementById('ollamaOut').textContent = JSON.stringify(data, null, 2);
}
async function downloadSelected() {
  const profile = getVal('profile') === 'auto' ? 'balanced' : getVal('profile');
  const id = {low: 'ollamaLow', balanced: 'ollamaBalanced', power: 'ollamaPower'}[profile] || 'ollamaBalanced';
  const model = getVal(id);
  document.getElementById('ollamaOut').textContent = 'Downloading ' + model + ' ...';
  const data = await api('/api/local-ai/ollama/download', {method: 'POST', body: JSON.stringify({model})});
  document.getElementById('ollamaOut').textContent = JSON.stringify(data, null, 2);
}
async function refreshCache() {
  const data = await api('/api/local-ai/whisper/cache');
  document.getElementById('cacheOut').textContent = JSON.stringify(data, null, 2);
}
refreshAll();
"""


def register_local_model_manager_static_routes(app: FastAPI) -> None:
    @app.get("/local-ai/model-manager.js")
    def local_model_manager_js():
        return Response(MODEL_MANAGER_JS, media_type="application/javascript; charset=utf-8")
