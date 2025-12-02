/**
 * Server IPC Handlers
 *
 * Handles optional connection to a running Daemons server:
 * - Connect/disconnect to server
 * - Hot-reload content
 * - Enhanced validation with server-side checks
 */

import { ipcMain } from 'electron';

// Server connection state
let serverUrl: string | null = null;
let authToken: string | null = null;

export function registerServerHandlers(): void {
  // Connect to server
  ipcMain.handle('server:connect', async (_event, url: string) => {
    try {
      // Test connection by fetching schemas
      const response = await fetch(`${url}/api/admin/schemas/version`, {
        headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      serverUrl = url;
      return { connected: true, url };
    } catch (error) {
      serverUrl = null;
      throw new Error(`Failed to connect to server: ${error}`);
    }
  });

  // Disconnect from server
  ipcMain.handle('server:disconnect', async () => {
    serverUrl = null;
    authToken = null;
    return true;
  });

  // Check if connected
  ipcMain.handle('server:isConnected', async () => {
    return serverUrl !== null;
  });

  // Trigger hot-reload on server
  ipcMain.handle('server:hotReload', async (_event, contentType: string) => {
    if (!serverUrl) {
      throw new Error('Not connected to server');
    }

    try {
      const response = await fetch(`${serverUrl}/api/admin/content/reload`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        body: JSON.stringify({ content_type: contentType }),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      throw new Error(`Failed to trigger hot-reload: ${error}`);
    }
  });

  // Enhanced validation via server
  ipcMain.handle('server:validateEnhanced', async (_event, content: string, contentType: string) => {
    if (!serverUrl) {
      throw new Error('Not connected to server');
    }

    try {
      const response = await fetch(`${serverUrl}/api/admin/content/validate-enhanced`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        body: JSON.stringify({ content_type: contentType, content }),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      throw new Error(`Failed to validate: ${error}`);
    }
  });
}
