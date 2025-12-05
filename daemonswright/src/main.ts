import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'path';

// Register IPC handlers for filesystem, schema, and optional server
import { registerFileSystemHandlers } from './main/ipc/fileSystem';
import { registerSchemaHandlers } from './main/ipc/schema';
import { registerServerHandlers } from './main/ipc/server';
import { loadSettings, saveWindowState, getWindowState, getSetting, addRecentFolder } from './main/settings';

let mainWindow: BrowserWindow | null = null;

function createWindow() {
  // Load saved window state
  const windowState = getWindowState();

  mainWindow = new BrowserWindow({
    width: windowState.width,
    height: windowState.height,
    x: windowState.x,
    y: windowState.y,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  });

  if (windowState.isMaximized) {
    mainWindow.maximize();
  }

  mainWindow.loadFile(path.join(__dirname, 'index.html'));
  mainWindow.webContents.openDevTools();

  // Save window state on close
  mainWindow.on('close', () => {
    if (mainWindow) {
      const bounds = mainWindow.getBounds();
      saveWindowState({
        width: bounds.width,
        height: bounds.height,
        x: bounds.x,
        y: bounds.y,
        isMaximized: mainWindow.isMaximized(),
      });
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Load settings before anything else
loadSettings();

// Register IPC handlers early so renderer invocations succeed
registerFileSystemHandlers();
registerSchemaHandlers();
// server handlers are optional; register if available
try {
  registerServerHandlers();
} catch (err) {
  // ignore if the server handlers depend on optional modules
}

// Settings IPC handlers
ipcMain.handle('settings:getLastFolder', () => getSetting('lastOpenedFolder'));
ipcMain.handle('settings:getRecentFolders', () => getSetting('recentFolders') ?? []);
ipcMain.handle('settings:addRecentFolder', (_event, folderPath: string) => {
  addRecentFolder(folderPath);
  return true;
});

app.on('ready', createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});
