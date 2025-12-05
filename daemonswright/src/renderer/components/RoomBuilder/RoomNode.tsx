/**
 * RoomNode Component
 *
 * Custom React Flow node for representing a room on the canvas.
 * Renders as an isometric parallelogram with directional handles.
 */

import { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Tooltip } from 'antd';

interface RoomNodeData {
  label: string;
  room_id: string;
  room_type?: string;
  description?: string;
  z_level?: number;
  isActive?: boolean;
}

// Room type to color mapping
const roomTypeColors: Record<string, string> = {
  ethereal: '#9254de',    // Purple
  forest: '#52c41a',      // Green
  cave: '#8c8c8c',        // Gray
  urban: '#faad14',       // Gold
  chamber: '#1890ff',     // Blue
  corridor: '#595959',    // Dark gray
  outdoor: '#73d13d',     // Light green
  indoor: '#d4b106',      // Mustard
  dungeon: '#722ed1',     // Dark purple
  shop: '#fa8c16',        // Orange
  inn: '#eb2f96',         // Pink
  temple: '#13c2c2',      // Cyan
  water: '#1890ff',       // Blue
  default: '#434343',     // Default gray
};

function RoomNode({ data, selected }: NodeProps<RoomNodeData>) {
  const isActive = data.isActive !== false;
  const baseColor = roomTypeColors[data.room_type ?? 'default'] ?? roomTypeColors.default;
  
  // Square room dimensions for grid layout
  const size = 80;

  const nodeContent = (
    <div
      className={`room-node-grid ${selected ? 'selected' : ''}`}
      style={{
        width: size,
        height: size,
        position: 'relative',
      }}
    >
      {/* Square room shape */}
      <div
        style={{
          width: '100%',
          height: '100%',
          background: baseColor,
          border: selected ? '3px solid #fff' : '2px solid rgba(255,255,255,0.3)',
          boxShadow: selected 
            ? '0 0 20px rgba(24,144,255,0.8)' 
            : '2px 4px 8px rgba(0,0,0,0.4)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 6,
        }}
      >
        <div
          style={{
            textAlign: 'center',
            color: '#fff',
            textShadow: '1px 1px 2px rgba(0,0,0,0.8)',
            padding: '4px',
            overflow: 'hidden',
          }}
        >
          <div style={{ fontSize: 10, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {data.label}
          </div>
          <div style={{ fontSize: 9, opacity: 0.8 }}>
            z:{data.z_level ?? 0}
          </div>
        </div>
      </div>

      {/* Direction handles - centered on each edge */}
      {/* North (top center) */}
      <Handle
        type="source"
        position={Position.Top}
        id="north"
        style={{ 
          background: '#52c41a', 
          width: 10, 
          height: 10,
          top: -5,
          left: '50%',
          transform: 'translateX(-50%)',
        }}
      />
      {/* South (bottom center) */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="south"
        style={{ 
          background: '#52c41a', 
          width: 10, 
          height: 10,
          bottom: -5,
          left: '50%',
          transform: 'translateX(-50%)',
        }}
      />
      {/* East (right center) */}
      <Handle
        type="source"
        position={Position.Right}
        id="east"
        style={{ 
          background: '#52c41a', 
          width: 10, 
          height: 10,
          right: -5,
          top: '50%',
          transform: 'translateY(-50%)',
        }}
      />
      {/* West (left center) */}
      <Handle
        type="source"
        position={Position.Left}
        id="west"
        style={{ 
          background: '#52c41a', 
          width: 10, 
          height: 10,
          left: -5,
          top: '50%',
          transform: 'translateY(-50%)',
        }}
      />
      {/* Up (top-right corner) */}
      <Handle
        type="source"
        position={Position.Top}
        id="up"
        style={{ 
          background: '#faad14', 
          width: 10, 
          height: 10,
          top: -5,
          right: 5,
          left: 'auto',
          borderRadius: '50%',
        }}
      />
      {/* Down (bottom-right corner) */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="down"
        style={{ 
          background: '#faad14', 
          width: 10, 
          height: 10,
          bottom: -5,
          right: 5,
          left: 'auto',
          borderRadius: '50%',
        }}
      />

      {/* Target handles (for incoming connections) */}
      <Handle type="target" position={Position.Top} id="north-in" style={{ opacity: 0, top: 0, left: '50%', transform: 'translateX(-50%)' }} />
      <Handle type="target" position={Position.Bottom} id="south-in" style={{ opacity: 0, bottom: 0, left: '50%', transform: 'translateX(-50%)' }} />
      <Handle type="target" position={Position.Right} id="east-in" style={{ opacity: 0, right: 0, top: '50%', transform: 'translateY(-50%)' }} />
      <Handle type="target" position={Position.Left} id="west-in" style={{ opacity: 0, left: 0, top: '50%', transform: 'translateY(-50%)' }} />
      <Handle type="target" position={Position.Top} id="up-in" style={{ opacity: 0, top: 0, right: 5, left: 'auto' }} />
      <Handle type="target" position={Position.Bottom} id="down-in" style={{ opacity: 0, bottom: 0, right: 5, left: 'auto' }} />
    </div>
  );

  // Only show tooltip for active (interactive) nodes
  if (isActive && data.description) {
    return (
      <Tooltip title={data.description} placement="right">
        {nodeContent}
      </Tooltip>
    );
  }

  return nodeContent;
}

export const RoomNodeComponent = memo(RoomNode);
