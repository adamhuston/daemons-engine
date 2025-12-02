/**
 * useServer Hook
 *
 * Manages optional connection to a running Daemons server:
 * - Connect/disconnect
 * - Hot-reload content
 * - Enhanced server-side validation
 */

import { useState, useCallback } from 'react';

interface ServerState {
  isConnected: boolean;
  serverUrl: string | null;
  isConnecting: boolean;
  error: string | null;
}

export function useServer() {
  const [state, setState] = useState<ServerState>({
    isConnected: false,
    serverUrl: null,
    isConnecting: false,
    error: null,
  });

  // Connect to server
  const connect = useCallback(async (url: string = 'http://localhost:8000') => {
    setState((prev) => ({ ...prev, isConnecting: true, error: null }));

    try {
      await window.daemonswright.server.connect(url);
      setState({
        isConnected: true,
        serverUrl: url,
        isConnecting: false,
        error: null,
      });
      return true;
    } catch (error) {
      setState((prev) => ({
        ...prev,
        isConnecting: false,
        error: String(error),
      }));
      return false;
    }
  }, []);

  // Disconnect from server
  const disconnect = useCallback(async () => {
    await window.daemonswright.server.disconnect();
    setState({
      isConnected: false,
      serverUrl: null,
      isConnecting: false,
      error: null,
    });
  }, []);

  // Trigger hot-reload on server
  const hotReload = useCallback(async (contentType?: string) => {
    if (!state.isConnected) {
      throw new Error('Not connected to server');
    }

    try {
      return await window.daemonswright.server.hotReload(contentType ?? 'all');
    } catch (error) {
      console.error('Hot-reload failed:', error);
      throw error;
    }
  }, [state.isConnected]);

  // Enhanced validation via server
  const validateEnhanced = useCallback(async (content: string, contentType: string) => {
    if (!state.isConnected) {
      return null; // Fall back to local validation
    }

    try {
      return await window.daemonswright.server.validateEnhanced(content, contentType);
    } catch (error) {
      console.error('Server validation failed:', error);
      return null;
    }
  }, [state.isConnected]);

  return {
    isConnected: state.isConnected,
    serverUrl: state.serverUrl,
    isConnecting: state.isConnecting,
    error: state.error,
    connect,
    disconnect,
    hotReload,
    validateEnhanced,
  };
}
