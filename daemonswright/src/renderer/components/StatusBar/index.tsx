/**
 * StatusBar Component
 *
 * Displays current file info, validation status, and server connection state.
 */

import { Badge, Space, Tooltip } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  CloudOutlined,
  DisconnectOutlined,
  EditOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import type { ValidationError } from '../../shared/types';

interface StatusBarProps {
  filePath: string | null;
  isDirty: boolean;
  validationErrors: ValidationError[];
  isConnected: boolean;
  serverUrl?: string;
}

export function StatusBar({
  filePath,
  isDirty,
  validationErrors,
  isConnected,
  serverUrl,
}: StatusBarProps) {
  const hasErrors = validationErrors.length > 0;

  return (
    <div className="status-bar-content">
      <Space size="large">
        {/* Connection status */}
        <Tooltip title={isConnected ? `Connected to ${serverUrl}` : 'Offline mode'}>
          {isConnected ? (
            <Badge status="success" text={<CloudOutlined />} />
          ) : (
            <Badge status="default" text={<DisconnectOutlined />} />
          )}
        </Tooltip>

        {/* File path */}
        {filePath && (
          <span className="current-file">
            {filePath.split(/[/\\]/).slice(-2).join('/')}
          </span>
        )}

        {/* Dirty indicator */}
        {isDirty && (
          <Tooltip title="Unsaved changes">
            <EditOutlined style={{ color: '#faad14' }} />
          </Tooltip>
        )}
      </Space>

      <Space size="large">
        {/* Validation status */}
        <Tooltip
          title={
            hasErrors
              ? `${validationErrors.length} error(s)`
              : 'No validation errors'
          }
        >
          {hasErrors ? (
            <Badge count={validationErrors.length}>
              <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
            </Badge>
          ) : (
            <CheckCircleOutlined style={{ color: '#52c41a' }} />
          )}
        </Tooltip>

        {/* Save status */}
        {!isDirty && filePath && (
          <Tooltip title="All changes saved">
            <SaveOutlined style={{ color: '#52c41a' }} />
          </Tooltip>
        )}
      </Space>
    </div>
  );
}
