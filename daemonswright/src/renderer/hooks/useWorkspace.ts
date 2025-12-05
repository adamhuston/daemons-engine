/**
 * useWorkspace Hook
 *
 * Manages the workspace state including:
 * - Opening and closing world_data folders
 * - File listing and navigation
 * - File content reading/writing
 * - Dirty state tracking
 */

import { useState, useCallback, useEffect } from 'react';
import type { FileEntry } from '../../shared/types';

interface WorkspaceState {
  worldDataPath: string | null;
  files: FileEntry[];
  selectedFile: string | null;
  fileContent: string;
  isDirty: boolean;
}

export function useWorkspace() {
  const [state, setState] = useState<WorkspaceState>({
    worldDataPath: null,
    files: [],
    selectedFile: null,
    fileContent: '',
    isDirty: false,
  });

  // Helper to open a folder by path (used for both dialog and restore)
  const openFolderByPath = useCallback(async (folderPath: string) => {
    try {
      if (!window.daemonswright?.fs) return;
      const files = await window.daemonswright.fs.listDirectory(folderPath);
      setState((prev) => ({
        ...prev,
        worldDataPath: folderPath,
        files,
        selectedFile: null,
        fileContent: '',
        isDirty: false,
      }));

      // Save to recent folders
      await window.daemonswright.settings?.addRecentFolder(folderPath);

      // Start watching the directory
      await window.daemonswright.fs.watchDirectory(folderPath);
    } catch (error) {
      console.error('Failed to open folder:', error);
    }
  }, []);

  // Open folder dialog
  const openFolder = useCallback(async () => {
    try {
      if (!window.daemonswright?.fs) {
        throw new Error('Filesystem API not available (not running in Electron preload)');
      }
      const path = await window.daemonswright.fs.openFolder();
      if (path) {
        await openFolderByPath(path);
      }
    } catch (error) {
      console.error('Failed to open folder:', error);
    }
  }, [openFolderByPath]);

  // Restore last opened folder on mount
  useEffect(() => {
    const restoreLastFolder = async () => {
      try {
        const lastFolder = await window.daemonswright?.settings?.getLastFolder();
        if (lastFolder) {
          await openFolderByPath(lastFolder);
        }
      } catch (error) {
        console.error('Failed to restore last folder:', error);
      }
    };
    restoreLastFolder();
  }, [openFolderByPath]);

  // Select a file
  const selectFile = useCallback(async (filePath: string) => {
    try {
      const content = await window.daemonswright.fs.readFile(filePath);
      setState((prev) => ({
        ...prev,
        selectedFile: filePath,
        fileContent: content,
        isDirty: false,
      }));
    } catch (error) {
      console.error('Failed to read file:', error);
    }
  }, []);

  // Update file content (marks as dirty)
  const updateContent = useCallback((content: string) => {
    setState((prev) => ({
      ...prev,
      fileContent: content,
      isDirty: true,
    }));
  }, []);

  // Save file
  const saveFile = useCallback(async (filePath: string, content: string) => {
    try {
      await window.daemonswright.fs.writeFile(filePath, content);
      setState((prev) => ({
        ...prev,
        isDirty: false,
      }));
      return true;
    } catch (error) {
      console.error('Failed to save file:', error);
      return false;
    }
  }, []);

  // Refresh file list
  const refreshFiles = useCallback(async () => {
    if (state.worldDataPath) {
      try {
        const files = await window.daemonswright.fs.listDirectory(state.worldDataPath);
        setState((prev) => ({
          ...prev,
          files,
        }));
      } catch (error) {
        console.error('Failed to refresh files:', error);
      }
    }
  }, [state.worldDataPath]);

  // Listen for external file changes
  useEffect(() => {
    const handleFileChange = (eventType: string, filePath: string) => {
      console.log('File change detected:', eventType, filePath);
      refreshFiles();
    };

    let unsubscribe: (() => void) | null = null;
    try {
      if (window.daemonswright && window.daemonswright.fs && typeof window.daemonswright.fs.onFileChange === 'function') {
        const maybeUnsub = window.daemonswright.fs.onFileChange(handleFileChange) as unknown;
        if (typeof maybeUnsub === 'function') {
          unsubscribe = maybeUnsub as () => void;
        }
      }
    } catch (err) {
      console.warn('File change listener not available:', err);
    }

    return () => {
      // Cleanup listener and watcher on unmount
      if (unsubscribe) unsubscribe();
      if (state.worldDataPath && window.daemonswright && window.daemonswright.fs && typeof window.daemonswright.fs.unwatchDirectory === 'function') {
        window.daemonswright.fs.unwatchDirectory(state.worldDataPath).catch(() => {});
      }
    };
  }, [state.worldDataPath, refreshFiles]);

  return {
    worldDataPath: state.worldDataPath,
    files: state.files,
    selectedFile: state.selectedFile,
    fileContent: state.fileContent,
    isDirty: state.isDirty,
    openFolder,
    selectFile,
    updateContent,
    saveFile,
    refreshFiles,
  };
}
