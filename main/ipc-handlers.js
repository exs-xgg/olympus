/**
 * IPC Handler implementations — OS-level capabilities
 * 
 * Only the main process can access these. The renderer
 * goes through the preload bridge.
 */

const { ipcMain } = require('electron');
const { exec } = require('child_process');
const fs = require('fs').promises;
const path = require('path');

function registerIpcHandlers() {
  // Execute shell command
  ipcMain.handle('run-command', async (event, { command, cwd }) => {
    return new Promise((resolve) => {
      const options = {
        cwd: cwd || process.cwd(),
        timeout: 120000,
        maxBuffer: 1024 * 1024 * 10,
        shell: true,
      };

      exec(command, options, (error, stdout, stderr) => {
        resolve({
          success: !error,
          stdout: stdout || '',
          stderr: stderr || '',
          exitCode: error ? error.code : 0,
          error: error ? error.message : null,
        });
      });
    });
  });

  // Read file
  ipcMain.handle('read-file', async (event, filePath) => {
    try {
      const content = await fs.readFile(filePath, 'utf-8');
      return { success: true, content };
    } catch (err) {
      return { success: false, error: err.message };
    }
  });

  // Write file
  ipcMain.handle('write-file', async (event, { filePath, content }) => {
    try {
      await fs.mkdir(path.dirname(filePath), { recursive: true });
      await fs.writeFile(filePath, content, 'utf-8');
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  });
}

module.exports = { registerIpcHandlers };
