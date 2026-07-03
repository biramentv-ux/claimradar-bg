const { app, BrowserWindow, shell, ipcMain } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

const BACKEND_PORT = process.env.CLAIMRADAR_LOCAL_PORT || '8765';
const LOCAL_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const DESKTOP_URL = `${LOCAL_URL}/desktop`;
let backendProcess = null;

function repoRoot() {
  return path.resolve(__dirname, '..', '..');
}

function existingFile(candidates) {
  return candidates.find(candidate => candidate && fs.existsSync(candidate));
}

function backendLaunchPlan() {
  const exeName = process.platform === 'win32' ? 'claimradar_backend.exe' : 'claimradar_backend';
  const resources = process.resourcesPath || __dirname;
  const packagedExe = existingFile([
    path.join(resources, 'backend', exeName),
    path.join(resources, 'backend', 'claimradar_backend', exeName),
    path.join(resources, 'app.asar.unpacked', 'backend', exeName),
    path.join(resources, 'app.asar.unpacked', 'backend', 'claimradar_backend', exeName),
    path.join(__dirname, '..', '..', 'dist', 'desktop-backend', 'claimradar_backend', exeName),
    path.join(__dirname, '..', '..', 'dist', 'desktop-backend', exeName)
  ]);
  if (packagedExe) {
    return { command: packagedExe, args: [], cwd: path.dirname(packagedExe), mode: 'executable' };
  }
  const script = path.join(repoRoot(), 'local_desktop_launch.py');
  if (fs.existsSync(script)) {
    const pythonCommand = process.platform === 'win32' ? 'python' : 'python3';
    return { command: pythonCommand, args: [script], cwd: repoRoot(), mode: 'python-dev' };
  }
  return { command: '', args: [], cwd: repoRoot(), mode: 'missing' };
}

function startBackend() {
  if (process.env.CLAIMRADAR_EXTERNAL_BACKEND === '1') return;
  const plan = backendLaunchPlan();
  const env = {
    ...process.env,
    APP_PORT: BACKEND_PORT,
    LOCAL_AI_ENABLED: '1',
    LOCAL_AI_MODE: process.env.LOCAL_AI_MODE || 'offline',
    LOCAL_AI_PROFILE: process.env.LOCAL_AI_PROFILE || 'auto',
    MODEL_MANAGER_ENABLED: '1',
    LOCAL_LLM_ENABLED: '1',
    LOCAL_SQLITE_ENABLED: '1',
    LOCAL_ARCHIVE_ENABLED: '1',
    MOBILE_REMOTE_ENABLED: '1',
    MOBILE_REMOTE_REQUIRE_PIN: '1',
    MOBILE_REMOTE_BIND_LAN: process.env.MOBILE_REMOTE_BIND_LAN || '1',
    OLLAMA_BASE_URL: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434',
    SUPABASE_AUTH_UI_ENABLED: '0',
    AUTH_ENABLED: '0',
    DB_ENABLED: '0',
    RATE_LIMIT_ENABLED: '0'
  };
  if (!plan.command) {
    console.error('ClaimRadar backend sidecar not found. Build backend with scripts/build_desktop_backend.py.');
    return;
  }
  try {
    console.log(`Starting ClaimRadar backend (${plan.mode}): ${plan.command} ${plan.args.join(' ')}`);
    backendProcess = spawn(plan.command, plan.args, { env, cwd: plan.cwd, windowsHide: true, stdio: 'ignore' });
    backendProcess.on('error', error => console.error('Backend process error:', error));
  } catch (error) {
    console.error('Failed to start backend sidecar:', error);
  }
}

async function waitForBackend(timeoutMs = 45000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(`${LOCAL_URL}/health`);
      if (response.ok) return true;
    } catch (_) {}
    try {
      const response = await fetch(`${LOCAL_URL}/api/local-ai/status`);
      if (response.ok) return true;
    } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 700));
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
    await win.loadURL(DESKTOP_URL);
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
