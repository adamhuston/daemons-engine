/**
 * Preload Script
 *
 * Exposes safe IPC methods to the renderer process via contextBridge.
 * This is the only way for the renderer to communicate with the main process.
 */

import { contextBridge, ipcRenderer } from 'electron';
import type { FileSystemAPI, SchemaAPI, ServerAPI } from '../shared/types';

// File system operations
const fileSystemAPI: FileSystemAPI = {
  openFolder: () => ipcRenderer.invoke('fs:openFolder'),
  listDirectory: (dirPath: string) => ipcRenderer.invoke('fs:listDirectory', dirPath),
  readFile: (filePath: string) => ipcRenderer.invoke('fs:readFile', filePath),
  writeFile: (filePath: string, content: string) => ipcRenderer.invoke('fs:writeFile', filePath, content),
  deleteFile: (filePath: string) => ipcRenderer.invoke('fs:deleteFile', filePath),
  watchDirectory: (dirPath: string) => ipcRenderer.invoke('fs:watchDirectory', dirPath),
  unwatchDirectory: (dirPath: string) => ipcRenderer.invoke('fs:unwatchDirectory', dirPath),
  onFileChange: (callback: (event: string, path: string) => void) => {
    ipcRenderer.on('fs:fileChange', (_event, eventType, path) => callback(eventType, path));
  },
};

// Schema operations
const schemaAPI: SchemaAPI = {
  loadSchemas: (worldDataPath: string) => ipcRenderer.invoke('schema:loadSchemas', worldDataPath),
  validateContent: (content: string, contentType: string) => ipcRenderer.invoke('schema:validateContent', content, contentType),
  getSchemaForType: (contentType: string) => ipcRenderer.invoke('schema:getSchemaForType', contentType),
};

// Optional server connection
const serverAPI: ServerAPI = {
  connect: (url: string) => ipcRenderer.invoke('server:connect', url),
  disconnect: () => ipcRenderer.invoke('server:disconnect'),
  isConnected: () => ipcRenderer.invoke('server:isConnected'),
  hotReload: (contentType: string) => ipcRenderer.invoke('server:hotReload', contentType),
  validateEnhanced: (content: string, contentType: string) => ipcRenderer.invoke('server:validateEnhanced', content, contentType),
};

// Expose APIs to renderer
contextBridge.exposeInMainWorld('daemonswright', {
  fs: fileSystemAPI,
  schema: schemaAPI,
  server: serverAPI,
});
