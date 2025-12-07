// Preload script for security isolation
import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron';
import type { DaemonswrightAPI } from './shared/types';

// Expose a minimal, safe API to the renderer under `window.daemonswright`
const fsApi = {
	openFolder: async (): Promise<string | null> => {
		return ipcRenderer.invoke('fs:openFolder');
	},
	selectSaveFolder: async (defaultName?: string): Promise<string | null> => {
		return ipcRenderer.invoke('fs:selectSaveFolder', defaultName);
	},
	createDirectory: async (dirPath: string): Promise<boolean> => {
		return ipcRenderer.invoke('fs:createDirectory', dirPath);
	},
	listDirectory: async (dirPath: string) => {
		return ipcRenderer.invoke('fs:listDirectory', dirPath);
	},
	readFile: async (filePath: string) => {
		return ipcRenderer.invoke('fs:readFile', filePath);
	},
	fileExists: async (filePath: string) => {
		return ipcRenderer.invoke('fs:fileExists', filePath);
	},
	writeFile: async (filePath: string, content: string) => {
		return ipcRenderer.invoke('fs:writeFile', filePath, content);
	},
	deleteFile: async (filePath: string) => {
		return ipcRenderer.invoke('fs:deleteFile', filePath);
	},
	watchDirectory: async (dirPath: string) => {
		return ipcRenderer.invoke('fs:watchDirectory', dirPath);
	},
	unwatchDirectory: async (dirPath: string) => {
		return ipcRenderer.invoke('fs:unwatchDirectory', dirPath);
	},
	// Register a callback for file change events. Returns an unsubscribe function.
	onFileChange: (cb: (eventType: string, filePath: string) => void) => {
		const listener = (_event: IpcRendererEvent, eventType: string, filePath: string) => {
			try {
				cb(eventType, filePath);
			} catch (err) {
				console.error('Error in onFileChange callback', err);
			}
		};
		ipcRenderer.on('fs:fileChange', listener);
		return () => ipcRenderer.removeListener('fs:fileChange', listener);
	},
};

	// Implement schema and server APIs so the typed DaemonswrightAPI is complete
	const schemaApi = {
		loadSchemas: async (worldDataPath: string) => ipcRenderer.invoke('schema:loadSchemas', worldDataPath),
		validateContent: async (content: string, contentType: string) => ipcRenderer.invoke('schema:validateContent', content, contentType),
		getSchemaForType: async (contentType: string) => ipcRenderer.invoke('schema:getSchemaForType', contentType),
	};

	const serverApi = {
		connect: async (url: string) => ipcRenderer.invoke('server:connect', url),
		disconnect: async () => ipcRenderer.invoke('server:disconnect'),
		isConnected: async () => ipcRenderer.invoke('server:isConnected'),
		hotReload: async (contentType: string) => ipcRenderer.invoke('server:hotReload', contentType),
		validateEnhanced: async (content: string, contentType: string) => ipcRenderer.invoke('server:validateEnhanced', content, contentType),
	};

	const settingsApi = {
		getLastFolder: async (): Promise<string | null> => ipcRenderer.invoke('settings:getLastFolder'),
		getRecentFolders: async (): Promise<string[]> => ipcRenderer.invoke('settings:getRecentFolders'),
		addRecentFolder: async (folderPath: string) => ipcRenderer.invoke('settings:addRecentFolder', folderPath),
	};

	// Expose the full API and assert it matches the shared type
	contextBridge.exposeInMainWorld('daemonswright', {
		fs: fsApi,
		schema: schemaApi,
		server: serverApi,
		settings: settingsApi,
	} as unknown as DaemonswrightAPI);

	// Do not redeclare the global Window type here; use the shared `DaemonswrightAPI` in `src/shared/types.ts` instead.
