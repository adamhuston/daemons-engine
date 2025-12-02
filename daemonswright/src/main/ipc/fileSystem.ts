/**
 * File System IPC Handlers
 *
 * Handles all file system operations from the renderer process:
 * - Open folder dialog
 * - Read/write/delete YAML files
 * - Directory listing
 * - File watching for external changes
 */

import { ipcMain, dialog } from 'electron';
import fs from 'fs/promises';
import path from 'path';
import chokidar, { FSWatcher } from 'chokidar';

// Track active file watchers
const watchers = new Map<string, FSWatcher>();

export function registerFileSystemHandlers(): void {
  // Open folder dialog
  ipcMain.handle('fs:openFolder', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openDirectory'],
      title: 'Open world_data folder',
    });

    if (result.canceled || result.filePaths.length === 0) {
      return null;
    }

    return result.filePaths[0];
  });

  // List directory contents
  ipcMain.handle('fs:listDirectory', async (_event, dirPath: string) => {
    try {
      const entries = await fs.readdir(dirPath, { withFileTypes: true });
      return entries.map((entry) => ({
        name: entry.name,
        path: path.join(dirPath, entry.name),
        isDirectory: entry.isDirectory(),
        isFile: entry.isFile(),
      }));
    } catch (error) {
      throw new Error(`Failed to list directory: ${error}`);
    }
  });

  // Read file content
  ipcMain.handle('fs:readFile', async (_event, filePath: string) => {
    try {
      const content = await fs.readFile(filePath, 'utf-8');
      return content;
    } catch (error) {
      throw new Error(`Failed to read file: ${error}`);
    }
  });

  // Write file content
  ipcMain.handle('fs:writeFile', async (_event, filePath: string, content: string) => {
    try {
      await fs.writeFile(filePath, content, 'utf-8');
      return true;
    } catch (error) {
      throw new Error(`Failed to write file: ${error}`);
    }
  });

  // Delete file
  ipcMain.handle('fs:deleteFile', async (_event, filePath: string) => {
    try {
      await fs.unlink(filePath);
      return true;
    } catch (error) {
      throw new Error(`Failed to delete file: ${error}`);
    }
  });

  // Start watching a directory
  ipcMain.handle('fs:watchDirectory', async (_event, dirPath: string) => {
    // Stop existing watcher if any
    const existingWatcher = watchers.get(dirPath);
    if (existingWatcher) {
      await existingWatcher.close();
    }

    const watcher = chokidar.watch(dirPath, {
      ignored: /(^|[\/\\])\../, // Ignore dotfiles
      persistent: true,
      ignoreInitial: true,
    });

    watcher.on('all', (eventType, filePath) => {
      // Send event to renderer
      const { BrowserWindow } = require('electron');
      const windows = BrowserWindow.getAllWindows();
      windows.forEach((window: Electron.BrowserWindow) => {
        window.webContents.send('fs:fileChange', eventType, filePath);
      });
    });

    watchers.set(dirPath, watcher);
    return true;
  });

  // Stop watching a directory
  ipcMain.handle('fs:unwatchDirectory', async (_event, dirPath: string) => {
    const watcher = watchers.get(dirPath);
    if (watcher) {
      await watcher.close();
      watchers.delete(dirPath);
    }
    return true;
  });
}
