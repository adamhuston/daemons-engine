/**
 * QuestNode Component
 *
 * Custom React Flow node for representing a quest in the designer.
 */

import { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Card, Badge, Tooltip, Tag } from 'antd';
import { TrophyOutlined, StarOutlined } from '@ant-design/icons';

interface QuestNodeData {
  label: string;
  quest_id: string;
  description?: string;
  objectives?: Array<{ type: string; target: string; count: number }>;
  rewards?: { experience?: number; items?: string[] };
}

function QuestNode({ data, selected }: NodeProps<QuestNodeData>) {
  // Objective type icons
  const objectiveTypeLabel: Record<string, string> = {
    kill: '⚔️',
    collect: '📦',
    visit: '📍',
    talk: '💬',
    deliver: '📬',
    default: '📋',
  };

  const objectiveCount = data.objectives?.length ?? 0;
  const hasRewards = data.rewards?.experience || data.rewards?.items?.length;

  return (
    <Tooltip title={data.description} placement="right">
      <Card
        size="small"
        className={`quest-node ${selected ? 'selected' : ''}`}
        style={{
          minWidth: 160,
          border: selected ? '2px solid #1890ff' : '1px solid #434343',
        }}
      >
        {/* Input handle (for prerequisites) */}
        <Handle
          type="target"
          position={Position.Left}
          style={{ background: '#1890ff' }}
        />

        {/* Output handle (for dependents) */}
        <Handle
          type="source"
          position={Position.Right}
          style={{ background: '#52c41a' }}
        />

        <div className="quest-node-content">
          <div className="quest-header">
            <TrophyOutlined style={{ color: '#faad14' }} />
            <span className="quest-label">{data.label}</span>
          </div>

          <div className="quest-id">{data.quest_id}</div>

          <div className="quest-meta">
            {objectiveCount > 0 && (
              <Tag color="blue" icon={<span>📋</span>}>
                {objectiveCount} objectives
              </Tag>
            )}
            {hasRewards && (
              <Tag color="gold" icon={<StarOutlined />}>
                Rewards
              </Tag>
            )}
          </div>
        </div>
      </Card>
    </Tooltip>
  );
}

export const QuestNodeComponent = memo(QuestNode);
