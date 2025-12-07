/**
 * MenuBar Component
 *
 * Application menu with file operations and settings.
 */

import { Menu, Dropdown, Space, Button } from 'antd';
import {
  FolderOpenOutlined,
  SaveOutlined,
  SettingOutlined,
  CloudServerOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';

export type EditorView = 'yaml' | 'room-builder' | 'entity-editor' | 'quest-designer' | 'dialogue-editor';

interface MenuBarProps {
  onOpenFolder: () => void;
  onSave: () => void;
  canSave: boolean;
  onConnect?: () => void;
  onReload?: () => void;
  isConnected?: boolean;
  currentView?: EditorView;
  onViewChange?: (view: EditorView) => void;
}

export function MenuBar({
  onOpenFolder,
  onSave,
  canSave,
  onConnect,
  onReload,
  isConnected = false,
  currentView = 'yaml',
  onViewChange,
}: MenuBarProps) {
  const fileMenuItems: MenuProps['items'] = [
    {
      key: 'open',
      icon: <FolderOpenOutlined />,
      label: 'Open Folder...',
      onClick: onOpenFolder,
    },
    { type: 'divider' },
    {
      key: 'save',
      icon: <SaveOutlined />,
      label: 'Save',
      onClick: onSave,
      disabled: !canSave,
    },
  ];

  const serverMenuItems: MenuProps['items'] = [
    {
      key: 'connect',
      icon: <CloudServerOutlined />,
      label: isConnected ? 'Disconnect' : 'Connect to Server...',
      onClick: onConnect,
    },
    {
      key: 'reload',
      icon: <ReloadOutlined />,
      label: 'Trigger Hot-Reload',
      onClick: onReload,
      disabled: !isConnected,
    },
  ];

  const viewMenuItems: MenuProps['items'] = [
    {
      key: 'yaml',
      label: 'YAML Editor',
      onClick: () => onViewChange?.('yaml'),
      style: currentView === 'yaml' ? { fontWeight: 'bold' } : undefined,
    },
    {
      key: 'room-builder',
      label: 'Room Builder',
      onClick: () => onViewChange?.('room-builder'),
      style: currentView === 'room-builder' ? { fontWeight: 'bold' } : undefined,
    },
    {
      key: 'entity-editor',
      label: 'Entity Editor',
      onClick: () => onViewChange?.('entity-editor'),
      style: currentView === 'entity-editor' ? { fontWeight: 'bold' } : undefined,
    },
    {
      key: 'quest-designer',
      label: 'Quest Designer',
      onClick: () => onViewChange?.('quest-designer'),
      style: currentView === 'quest-designer' ? { fontWeight: 'bold' } : undefined,
    },
    {
      key: 'dialogue-editor',
      label: 'Dialogue Editor',
      onClick: () => onViewChange?.('dialogue-editor'),
      style: currentView === 'dialogue-editor' ? { fontWeight: 'bold' } : undefined,
    },
  ];

  return (
    <div className="menu-bar">
      <Space>
        <Dropdown menu={{ items: fileMenuItems }} trigger={['click']}>
          <Button type="text">File</Button>
        </Dropdown>
        <Dropdown menu={{ items: viewMenuItems }} trigger={['click']}>
          <Button type="text">View</Button>
        </Dropdown>
        <Dropdown menu={{ items: serverMenuItems }} trigger={['click']}>
          <Button type="text">Server</Button>
        </Dropdown>
        <Button type="text" icon={<SettingOutlined />}>
          Settings
        </Button>
      </Space>
    </div>
  );
}
