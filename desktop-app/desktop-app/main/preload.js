/**
 * Preload Script — Secure IPC bridge via contextBridge
 * 
 * Exposes a controlled API to the renderer process.
 * The renderer can ONLY access these methods — no direct Node.js access.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Shell execution
  runCommand: (command, cwd) => ipcRenderer.invoke('run-command', { command, cwd }),

  // File system
  readFile: (filePath) => ipcRenderer.invoke('read-file', filePath),
  writeFile: (filePath, content) => ipcRenderer.invoke('write-file', { filePath, content }),

  // Notifications
  showNotification: (title, body) => ipcRenderer.invoke('show-notification', { title, body }),

  // Listen for events from main process
  onNotification: (callback) => {
    ipcRenderer.on('notification', (event, data) => callback(data));
    return () => ipcRenderer.removeAllListeners('notification');
  },
});
