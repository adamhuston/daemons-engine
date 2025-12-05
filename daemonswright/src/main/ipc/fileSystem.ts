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
// We load chokidar dynamically at runtime (it may be published as an ESM-only package)
// Track active file watchers (use `any` to avoid type issues if types are missing)
const watchers = new Map<string, any>();

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

    // Dynamically import chokidar to support ESM-only distributions.
    // Use an indirect runtime import so TypeScript (when compiling to CommonJS)
    // doesn't rewrite it into a require() call which fails for ESM-only packages.
    let chokidarModule: any;
    try {
      // eslint-disable-next-line no-new-func
      const runtimeImport: (id: string) => Promise<any> = new Function('id', 'return import(id)') as any;
      chokidarModule = await runtimeImport('chokidar');
    } catch (err) {
      throw new Error(`Failed to load chokidar module: ${err}`);
    }

    const chokidarImpl = chokidarModule && (chokidarModule.default ?? chokidarModule);

    const watcher = chokidarImpl.watch(dirPath, {
      ignored: /(^|[\/\\])\../, // Ignore dotfiles
      persistent: true,
      ignoreInitial: true,
    });

    watcher.on('all', (eventType: string, filePath: string) => {
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
