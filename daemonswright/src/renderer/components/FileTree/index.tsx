/**
 * FileTree Component
 *
 * Displays the hierarchical file structure of the world_data directory.
 * Allows navigation and selection of YAML files for editing.
 */

import { Tree, Input } from 'antd';
import { FolderOutlined, FileTextOutlined } from '@ant-design/icons';
import type { DataNode } from 'antd/es/tree';
import type { FileEntry } from '../../../shared/types';
import { useMemo, useState } from 'react';

const { Search } = Input;

interface FileTreeProps {
  files: FileEntry[];
  selectedFile: string | null;
  onSelect: (filePath: string) => void;
  worldDataPath: string | null;
}

export function FileTree({ files, selectedFile, onSelect, worldDataPath }: FileTreeProps) {
  const [searchValue, setSearchValue] = useState('');
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
  // Map of directory path -> children entries loaded on demand
  const [loadedChildren, setLoadedChildren] = useState<Record<string, FileEntry[]>>({});

  // Convert flat file list to tree structure
  const treeData = useMemo(() => {
    if (!files.length) return [];

    const buildTree = (entries: FileEntry[]): DataNode[] => {
      return entries.map((entry) => {
        const childrenEntries = entry.isDirectory ? loadedChildren[entry.path] : undefined;
        return {
          key: entry.path,
          title: entry.name,
          icon: entry.isDirectory ? <FolderOutlined /> : <FileTextOutlined />,
          isLeaf: entry.isFile,
          children: entry.isDirectory
            ? childrenEntries
              ? buildTree(childrenEntries)
              : []
            : undefined,
        };
      });
    };

    return buildTree(files);
  }, [files, loadedChildren]);

  // Filter tree based on search
  const filteredTreeData = useMemo(() => {
    if (!searchValue) return treeData;

    const filterTree = (nodes: DataNode[]): DataNode[] => {
      return nodes.filter((node) => {
        const title = String(node.title).toLowerCase();
        return title.includes(searchValue.toLowerCase());
      });
    };

    return filterTree(treeData);
  }, [treeData, searchValue]);

  const handleSelect = (selectedKeys: React.Key[]) => {
    if (selectedKeys.length > 0) {
      const key = String(selectedKeys[0]);
      // Find file in root files or any loaded children recursively
      const findIn = (entries: FileEntry[] | undefined, pathKey: string): FileEntry | undefined => {
        if (!entries) return undefined;
        for (const e of entries) {
          if (e.path === pathKey) return e;
          if (e.isDirectory) {
            const childList = loadedChildren[e.path];
            const found = findIn(childList, pathKey);
            if (found) return found;
          }
        }
        return undefined;
      };

      const file = findIn(files, key);
      if (file?.isFile && file.name.endsWith('.yaml')) {
        onSelect(key);
      }
    }
  };

  const handleExpand = (keys: React.Key[]) => {
    const stringKeys = keys.map(String);
    setExpandedKeys(stringKeys);

    // For any newly expanded directory that we haven't loaded yet, fetch its children
    const newlyExpanded = stringKeys.filter((k) => !loadedChildren[k]);
    newlyExpanded.forEach(async (dirPath) => {
      try {
        if (window.daemonswright && window.daemonswright.fs && typeof window.daemonswright.fs.listDirectory === 'function') {
          const entries = await window.daemonswright.fs.listDirectory(dirPath);
          // Only set children if we got entries
          if (entries && entries.length) {
            setLoadedChildren((prev) => ({ ...prev, [dirPath]: entries }));
          }
        }
      } catch (err) {
        // Ignore errors loading a directory (permissions etc.)
        // eslint-disable-next-line no-console
        console.warn('Failed to load directory children for', dirPath, err);
      }
    });
  };

  if (!worldDataPath) {
    return (
      <div className="file-tree-empty">
        <p>No folder open</p>
        <p className="hint">Use File → Open Folder to get started</p>
      </div>
    );
  }

  return (
    <div className="file-tree">
      <Search
        placeholder="Search files..."
        value={searchValue}
        onChange={(e) => setSearchValue(e.target.value)}
        className="file-tree-search"
      />
      <Tree
        showIcon
        treeData={filteredTreeData}
        selectedKeys={selectedFile ? [selectedFile] : []}
        expandedKeys={expandedKeys}
        onSelect={handleSelect}
        onExpand={handleExpand}
        className="file-tree-content"
      />
    </div>
  );
}
