const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('claimRadarDesktop', {
  localStatus: () => ipcRenderer.invoke('claimradar:local-status'),
  backendDiagnostics: () => ipcRenderer.invoke('claimradar:backend-diagnostics'),
  startBackend: () => ipcRenderer.invoke('claimradar:start-backend'),
  openDesktop: () => ipcRenderer.invoke('claimradar:open-desktop')
});
