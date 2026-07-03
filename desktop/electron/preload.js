const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('claimRadarDesktop', {
  localStatus: () => ipcRenderer.invoke('claimradar:local-status')
});
