/**
 * ErrorPanel Component
 *
 * Displays validation errors and warnings in a centralized panel.
 * Shows issues from schema validation, reference validation, etc.
 */

import { useCallback, useMemo } from 'react';
import { Badge, Collapse, Empty, Tag, Tooltip, Button } from 'antd';
import {
  WarningOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  FileTextOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import type { ValidationError } from '../../../shared/types';
import './ErrorPanel.css';

const { Panel } = Collapse;

interface ErrorPanelProps {
  errors: ValidationError[];
  onErrorClick?: (error: ValidationError) => void;
  onRefresh?: () => void;
  loading?: boolean;
}

export function ErrorPanel({ errors, onErrorClick, onRefresh, loading }: ErrorPanelProps) {
  // Group errors by file path
  const groupedErrors = useMemo(() => {
    const groups: Record<string, ValidationError[]> = {};
    
    errors.forEach((error) => {
      const path = error.filePath || 'Unknown';
      if (!groups[path]) {
        groups[path] = [];
      }
      groups[path].push(error);
    });
    
    return groups;
  }, [errors]);

  // Count by severity
  const counts = useMemo(() => {
    const result = { error: 0, warning: 0, info: 0 };
    errors.forEach((e) => {
      const severity = e.severity || 'error';
      result[severity as keyof typeof result]++;
    });
    return result;
  }, [errors]);

  // Get severity icon
  const getSeverityIcon = useCallback((severity?: string) => {
    switch (severity) {
      case 'warning':
        return <WarningOutlined style={{ color: '#faad14' }} />;
      case 'info':
        return <InfoCircleOutlined style={{ color: '#1890ff' }} />;
      case 'error':
      default:
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
    }
  }, []);

  // Get severity tag color
  const getSeverityColor = useCallback((severity?: string) => {
    switch (severity) {
      case 'warning':
        return 'warning';
      case 'info':
        return 'processing';
      case 'error':
      default:
        return 'error';
    }
  }, []);

  // Extract filename from path
  const getFilename = useCallback((path: string) => {
    return path.split(/[/\\]/).pop() || path;
  }, []);

  if (errors.length === 0) {
    return (
      <div className="error-panel error-panel-empty">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="No errors or warnings"
        />
        {onRefresh && (
          <Button
            icon={<ReloadOutlined />}
            onClick={onRefresh}
            loading={loading}
            style={{ marginTop: 16 }}
          >
            Validate All
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="error-panel">
      <div className="error-panel-header">
        <div className="error-panel-counts">
          {counts.error > 0 && (
            <Badge count={counts.error} style={{ backgroundColor: '#ff4d4f' }}>
              <Tag icon={<CloseCircleOutlined />} color="error">
                Errors
              </Tag>
            </Badge>
          )}
          {counts.warning > 0 && (
            <Badge count={counts.warning} style={{ backgroundColor: '#faad14' }}>
              <Tag icon={<WarningOutlined />} color="warning">
                Warnings
              </Tag>
            </Badge>
          )}
          {counts.info > 0 && (
            <Badge count={counts.info} style={{ backgroundColor: '#1890ff' }}>
              <Tag icon={<InfoCircleOutlined />} color="processing">
                Info
              </Tag>
            </Badge>
          )}
        </div>
        {onRefresh && (
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={onRefresh}
            loading={loading}
          >
            Refresh
          </Button>
        )}
      </div>

      <Collapse
        className="error-panel-list"
        defaultActiveKey={Object.keys(groupedErrors)}
        ghost
      >
        {Object.entries(groupedErrors).map(([path, fileErrors]) => (
          <Panel
            key={path}
            header={
              <div className="error-file-header">
                <FileTextOutlined />
                <span className="error-file-name">{getFilename(path)}</span>
                <Badge
                  count={fileErrors.length}
                  style={{ backgroundColor: fileErrors.some((e) => e.severity === 'error') ? '#ff4d4f' : '#faad14' }}
                />
              </div>
            }
          >
            <div className="error-file-path">
              <Tooltip title={path}>
                <span>{path}</span>
              </Tooltip>
            </div>
            <div className="error-items">
              {fileErrors.map((error, index) => (
                <div
                  key={index}
                  className={`error-item ${onErrorClick ? 'clickable' : ''}`}
                  onClick={() => onErrorClick?.(error)}
                >
                  <div className="error-item-header">
                    {getSeverityIcon(error.severity)}
                    <span className="error-field">{error.field || 'General'}</span>
                    {error.line && (
                      <span className="error-line">Line {error.line}</span>
                    )}
                  </div>
                  <div className="error-message">{error.message}</div>
                </div>
              ))}
            </div>
          </Panel>
        ))}
      </Collapse>
    </div>
  );
}
