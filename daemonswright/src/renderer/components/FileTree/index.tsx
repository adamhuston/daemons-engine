/**
 * FileTree Component
 *
 * Displays the hierarchical file structure of the world_data directory.
 * Allows navigation and selection of YAML files for editing.
 */

import { Tree, Input } from 'antd';
import { FolderOutlined, FileTextOutlined } from '@ant-design/icons';
import type { DataNode } from 'antd/es/tree';
import type { FileEntry } from '../../shared/types';
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

  // Convert flat file list to tree structure
  const treeData = useMemo(() => {
    if (!files.length) return [];

    const buildTree = (entries: FileEntry[]): DataNode[] => {
      return entries.map((entry) => ({
        key: entry.path,
        title: entry.name,
        icon: entry.isDirectory ? <FolderOutlined /> : <FileTextOutlined />,
        isLeaf: entry.isFile,
        children: entry.isDirectory ? [] : undefined, // Will be loaded on expand
      }));
    };

    return buildTree(files);
  }, [files]);

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
      // Only select files, not directories
      const file = files.find((f) => f.path === key);
      if (file?.isFile && file.name.endsWith('.yaml')) {
        onSelect(key);
      }
    }
  };

  const handleExpand = (keys: React.Key[]) => {
    setExpandedKeys(keys.map(String));
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
