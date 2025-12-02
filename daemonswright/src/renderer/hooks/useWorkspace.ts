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

  // Open folder dialog
  const openFolder = useCallback(async () => {
    try {
      const path = await window.daemonswright.fs.openFolder();
      if (path) {
        const files = await window.daemonswright.fs.listDirectory(path);
        setState((prev) => ({
          ...prev,
          worldDataPath: path,
          files,
          selectedFile: null,
          fileContent: '',
          isDirty: false,
        }));

        // Start watching the directory
        await window.daemonswright.fs.watchDirectory(path);
      }
    } catch (error) {
      console.error('Failed to open folder:', error);
    }
  }, []);

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

    window.daemonswright.fs.onFileChange(handleFileChange);

    return () => {
      // Cleanup watcher on unmount
      if (state.worldDataPath) {
        window.daemonswright.fs.unwatchDirectory(state.worldDataPath);
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
