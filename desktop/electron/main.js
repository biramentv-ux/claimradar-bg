const { app, BrowserWindow, shell, ipcMain } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

const BACKEND_PORT = process.env.CLAIMRADAR_LOCAL_PORT || '8765';
const LOCAL_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const DESKTOP_URL = `${LOCAL_URL}/desktop`;
let backendProcess = null;
let lastBackendPlan = null;
let backendLogs = [];

function pushLog(line) {
  const text = String(line || '').trim();
  if (!text) return;
  backendLogs.push(`[${new Date().toLocaleTimeString()}] ${text}`);
  backendLogs = backendLogs.slice(-120);
  console.log(text);
}

function repoRoot() {
  return path.resolve(__dirname, '..', '..');
}

function existingFile(candidates) {
  return candidates.find(candidate => candidate && fs.existsSync(candidate));
}

function backendCandidates() {
  const exeName = process.platform === 'win32' ? 'claimradar_backend.exe' : 'claimradar_backend';
  const resources = process.resourcesPath || __dirname;
  return [
    path.join(resources, 'backend', exeName),
    path.join(resources, 'backend', 'claimradar_backend', exeName),
    path.join(resources, 'app.asar.unpacked', 'backend', exeName),
    path.join(resources, 'app.asar.unpacked', 'backend', 'claimradar_backend', exeName),
    path.join(__dirname, '..', '..', 'dist', 'desktop-backend', 'claimradar_backend', exeName),
    path.join(__dirname, '..', '..', 'dist', 'desktop-backend', exeName)
  ];
}

function backendLaunchPlan() {
  const packagedExe = existingFile(backendCandidates());
  if (packagedExe) {
    return { command: packagedExe, args: [], cwd: path.dirname(packagedExe), mode: 'executable', candidates: backendCandidates() };
  }
  const script = path.join(repoRoot(), 'local_desktop_launch.py');
  if (fs.existsSync(script)) {
    const pythonCommand = process.platform === 'win32' ? 'python' : 'python3';
    return { command: pythonCommand, args: [script], cwd: repoRoot(), mode: 'python-dev', candidates: backendCandidates(), script };
  }
  return { command: '', args: [], cwd: repoRoot(), mode: 'missing', candidates: backendCandidates(), script };
}

function backendEnv() {
  return {
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
}

function startBackend(force = false) {
  if (process.env.CLAIMRADAR_EXTERNAL_BACKEND === '1') return { ok: true, skipped: true, reason: 'external_backend' };
  if (!force && backendProcess && backendProcess.poll === undefined && !backendProcess.killed) {
    return { ok: true, alreadyRunning: true, plan: lastBackendPlan };
  }
  const plan = backendLaunchPlan();
  lastBackendPlan = plan;
  if (!plan.command) {
    pushLog('Backend sidecar not found. Build backend or run from repository with Python installed.');
    return { ok: false, error: 'backend_not_found', plan };
  }
  try {
    pushLog(`Starting backend (${plan.mode}): ${plan.command} ${plan.args.join(' ')}`);
    backendProcess = spawn(plan.command, plan.args, { env: backendEnv(), cwd: plan.cwd, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    backendProcess.stdout.on('data', data => pushLog(String(data)));
    backendProcess.stderr.on('data', data => pushLog(String(data)));
    backendProcess.on('error', error => pushLog(`Backend process error: ${error.message || error}`));
    backendProcess.on('exit', (code, signal) => pushLog(`Backend exited: code=${code} signal=${signal}`));
    return { ok: true, plan, pid: backendProcess.pid };
  } catch (error) {
    pushLog(`Failed to start backend sidecar: ${error.message || error}`);
    return { ok: false, error: String(error), plan };
  }
}

async function checkUrl(url) {
  try {
    const response = await fetch(url);
    return { ok: response.ok, status: response.status, url };
  } catch (error) {
    return { ok: false, error: String(error), url };
  }
}

async function backendDiagnostics() {
  const plan = lastBackendPlan || backendLaunchPlan();
  const health = await checkUrl(`${LOCAL_URL}/health`);
  const localAi = await checkUrl(`${LOCAL_URL}/api/local-ai/status`);
  return {
    ok: health.ok || localAi.ok,
    localUrl: LOCAL_URL,
    desktopUrl: DESKTOP_URL,
    plan,
    process: backendProcess ? { pid: backendProcess.pid, killed: backendProcess.killed, exitCode: backendProcess.exitCode } : null,
    checks: { health, localAi },
    logs: backendLogs
  };
}

async function waitForBackend(timeoutMs = 45000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const status = await backendDiagnostics();
    if (status.ok) return true;
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

ipcMain.handle('claimradar:backend-diagnostics', async () => backendDiagnostics());
ipcMain.handle('claimradar:start-backend', async () => startBackend(true));
ipcMain.handle('claimradar:open-desktop', async () => shell.openExternal(DESKTOP_URL));

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
