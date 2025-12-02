/**
 * useFileWatcher Hook
 *
 * Watches for external file changes and triggers refresh callbacks.
 */

import { useEffect, useCallback } from 'react';

interface FileWatcherOptions {
  onAdd?: (path: string) => void;
  onChange?: (path: string) => void;
  onDelete?: (path: string) => void;
}

export function useFileWatcher(watchPath: string | null, options: FileWatcherOptions = {}) {
  const handleFileChange = useCallback((eventType: string, filePath: string) => {
    switch (eventType) {
      case 'add':
        options.onAdd?.(filePath);
        break;
      case 'change':
        options.onChange?.(filePath);
        break;
      case 'unlink':
        options.onDelete?.(filePath);
        break;
    }
  }, [options]);

  useEffect(() => {
    if (!watchPath) return;

    // Start watching
    window.daemonswright.fs.watchDirectory(watchPath);
    window.daemonswright.fs.onFileChange(handleFileChange);

    // Cleanup
    return () => {
      window.daemonswright.fs.unwatchDirectory(watchPath);
    };
  }, [watchPath, handleFileChange]);
}
