const { app, BrowserWindow, shell, ipcMain } = require('electron');
const path = require('node:path');
const { spawn } = require('node:child_process');

const BACKEND_PORT = process.env.CLAIMRADAR_LOCAL_PORT || '8765';
const LOCAL_URL = `http://127.0.0.1:${BACKEND_PORT}`;
let backendProcess = null;

function backendExecutable() {
  const exeName = process.platform === 'win32' ? 'claimradar_backend.exe' : 'claimradar_backend';
  return path.join(process.resourcesPath || __dirname, 'backend', exeName);
}

function startBackend() {
  if (process.env.CLAIMRADAR_EXTERNAL_BACKEND === '1') return;
  const executable = backendExecutable();
  const env = {
    ...process.env,
    APP_PORT: BACKEND_PORT,
    LOCAL_AI_ENABLED: '1',
    LOCAL_AI_MODE: process.env.LOCAL_AI_MODE || 'offline',
    LOCAL_AI_PROFILE: process.env.LOCAL_AI_PROFILE || 'auto',
    OLLAMA_BASE_URL: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434',
    SUPABASE_AUTH_UI_ENABLED: '0',
    AUTH_ENABLED: '0',
    DB_ENABLED: '0',
    RATE_LIMIT_ENABLED: '0'
  };
  try {
    backendProcess = spawn(executable, [], { env, windowsHide: true, stdio: 'ignore' });
  } catch (error) {
    console.error('Failed to start backend sidecar:', error);
  }
}

async function waitForBackend(timeoutMs = 30000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(`${LOCAL_URL}/health`);
      if (response.ok) return true;
    } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 600));
  }
  return false;
}

async function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 1040,
    minHeight: 720,
    title: 'ClaimRadar BG Desktop',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://127.0.0.1')) return { action: 'allow' };
    shell.openExternal(url);
    return { action: 'deny' };
  });

  const ready = await waitForBackend();
  if (ready) {
    await win.loadURL(LOCAL_URL);
  } else {
    await win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  }
}

ipcMain.handle('claimradar:local-status', async () => {
  try {
    const response = await fetch(`${LOCAL_URL}/api/local-ai/status`);
    return await response.json();
  } catch (error) {
    return { ok: false, error: String(error) };
  }
});

app.whenReady().then(() => {
  startBackend();
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});
