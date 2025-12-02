/**
 * RoomNode Component
 *
 * Custom React Flow node for representing a room on the canvas.
 */

import { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Card, Tooltip } from 'antd';

interface RoomNodeData {
  label: string;
  room_id: string;
  room_type?: string;
  description?: string;
}

function RoomNode({ data, selected }: NodeProps<RoomNodeData>) {
  // Room type emoji mapping
  const roomTypeEmoji: Record<string, string> = {
    indoor: '🏠',
    outdoor: '🌲',
    underground: '⛏️',
    dungeon: '🏰',
    shop: '🏪',
    inn: '🏨',
    temple: '⛪',
    water: '🌊',
    default: '📍',
  };

  const emoji = roomTypeEmoji[data.room_type ?? 'default'] ?? roomTypeEmoji.default;

  return (
    <Tooltip title={data.description} placement="right">
      <Card
        size="small"
        className={`room-node ${selected ? 'selected' : ''}`}
        style={{
          minWidth: 120,
          border: selected ? '2px solid #1890ff' : '1px solid #434343',
        }}
      >
        {/* Direction handles for exits */}
        <Handle
          type="source"
          position={Position.Top}
          id="north"
          style={{ background: '#52c41a' }}
        />
        <Handle
          type="source"
          position={Position.Right}
          id="east"
          style={{ background: '#52c41a' }}
        />
        <Handle
          type="source"
          position={Position.Bottom}
          id="south"
          style={{ background: '#52c41a' }}
        />
        <Handle
          type="source"
          position={Position.Left}
          id="west"
          style={{ background: '#52c41a' }}
        />

        {/* Target handles */}
        <Handle
          type="target"
          position={Position.Top}
          id="north-in"
          style={{ background: '#1890ff', top: -4 }}
        />
        <Handle
          type="target"
          position={Position.Right}
          id="east-in"
          style={{ background: '#1890ff', right: -4 }}
        />
        <Handle
          type="target"
          position={Position.Bottom}
          id="south-in"
          style={{ background: '#1890ff', bottom: -4 }}
        />
        <Handle
          type="target"
          position={Position.Left}
          id="west-in"
          style={{ background: '#1890ff', left: -4 }}
        />

        <div className="room-node-content">
          <span className="room-emoji">{emoji}</span>
          <span className="room-label">{data.label}</span>
          <span className="room-id">{data.room_id}</span>
        </div>
      </Card>
    </Tooltip>
  );
}

export const RoomNodeComponent = memo(RoomNode);
