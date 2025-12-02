/**
 * DialogueNode Component
 *
 * Custom React Flow node for representing a dialogue entry.
 */

import { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Card, Tag } from 'antd';
import { UserOutlined, RobotOutlined, ThunderboltOutlined } from '@ant-design/icons';

interface DialogueNodeData {
  text: string;
  nodeType: 'npc' | 'player' | 'action';
  condition?: string;
  action?: string;
}

function DialogueNode({ data, selected }: NodeProps<DialogueNodeData>) {
  // Node type styling
  const typeConfig = {
    npc: {
      icon: <RobotOutlined />,
      color: '#1890ff',
      label: 'NPC',
    },
    player: {
      icon: <UserOutlined />,
      color: '#52c41a',
      label: 'Player',
    },
    action: {
      icon: <ThunderboltOutlined />,
      color: '#faad14',
      label: 'Action',
    },
  };

  const config = typeConfig[data.nodeType];

  return (
    <Card
      size="small"
      className={`dialogue-node ${data.nodeType} ${selected ? 'selected' : ''}`}
      style={{
        minWidth: 200,
        maxWidth: 300,
        borderColor: selected ? config.color : '#434343',
        borderWidth: selected ? 2 : 1,
      }}
    >
      {/* Input handle */}
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: config.color }}
      />

      {/* Output handle */}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: config.color }}
      />

      <div className="dialogue-node-content">
        <div className="dialogue-header">
          <Tag color={config.color} icon={config.icon}>
            {config.label}
          </Tag>
          {data.condition && (
            <Tag color="orange" size="small">
              Conditional
            </Tag>
          )}
        </div>

        <div className="dialogue-text">
          {data.text.length > 100 ? `${data.text.slice(0, 100)}...` : data.text}
        </div>

        {data.action && (
          <div className="dialogue-action">
            <Tag color="purple" size="small">
              → {data.action}
            </Tag>
          </div>
        )}
      </div>
    </Card>
  );
}

export const DialogueNodeComponent = memo(DialogueNode);
