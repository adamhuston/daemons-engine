/**
 * RoomNode Component
 *
 * Custom React Flow node for representing a room on the canvas.
 * Renders as a square with directional handles for exits.
 * Shows + buttons on unused exit handles for creating new rooms.
 */

import { memo, useCallback } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Tooltip } from 'antd';
import { PlusOutlined } from '@ant-design/icons';

interface RoomNodeData {
  label: string;
  room_id: string;
  room_type?: string;
  description?: string;
  z_level?: number;
  isActive?: boolean;
  isActiveRoom?: boolean; // True if this room is shown in the properties panel
  exits?: Record<string, string>; // direction -> target room id
  onCreateFromExit?: (roomId: string, direction: string, position: { x: number; y: number }) => void;
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

function RoomNode({ data, selected, xPos, yPos }: NodeProps<RoomNodeData>) {
  const isActive = data.isActive !== false;
  const isActiveRoom = data.isActiveRoom === true;
  const baseColor = roomTypeColors[data.room_type ?? 'default'] ?? roomTypeColors.default;
  const exits = data.exits || {};
  
  // Square room dimensions for grid layout
  const size = 80;
  const GRID_SIZE = 150; // Must match the grid size in RoomBuilder

  // Direction offsets for creating new rooms
  const directionOffsets: Record<string, { x: number; y: number }> = {
    north: { x: 0, y: -GRID_SIZE },
    south: { x: 0, y: GRID_SIZE },
    east: { x: GRID_SIZE, y: 0 },
    west: { x: -GRID_SIZE, y: 0 },
    up: { x: GRID_SIZE, y: -GRID_SIZE }, // Diagonal for vertical
    down: { x: GRID_SIZE, y: GRID_SIZE },
  };

  // Handle click on plus button to create new room
  const handlePlusClick = useCallback((direction: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.onCreateFromExit) {
      const offset = directionOffsets[direction];
      const newPosition = {
        x: xPos + offset.x,
        y: yPos + offset.y,
      };
      data.onCreateFromExit(data.room_id, direction, newPosition);
    }
  }, [data, xPos, yPos]);

  // Render a handle that can be both source (drag from) and target (drop to)
  const renderHandle = (
    direction: string,
    position: Position,
    style: React.CSSProperties,
    isVertical: boolean = false
  ) => {
    const hasExit = direction in exits;
    const handleColor = isVertical ? '#faad14' : '#52c41a';
    
    return (
      <div key={direction} style={{ position: 'absolute', ...style }}>
        {/* Source handle - for dragging FROM this exit */}
        <Handle
          type="source"
          position={position}
          id={direction}
          isConnectableStart={true}
          isConnectableEnd={true}
          style={{ 
            background: hasExit ? handleColor : '#666',
            width: 12, 
            height: 12,
            border: '2px solid rgba(255,255,255,0.5)',
            cursor: 'crosshair',
          }}
        />
        {/* Plus button for exits that don't exist */}
        {!hasExit && isActive && (
          <Tooltip title={`Create room to the ${direction}`}>
            <div
              className="exit-plus-button"
              onClick={(e) => handlePlusClick(direction, e)}
              style={{
                position: 'absolute',
                width: 16,
                height: 16,
                background: '#1890ff',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                border: '1px solid #fff',
                zIndex: 10,
                // Position the plus button outside the handle
                ...(position === Position.Top && { top: -20, left: -2 }),
                ...(position === Position.Bottom && { bottom: -20, left: -2 }),
                ...(position === Position.Left && { left: -20, top: -2 }),
                ...(position === Position.Right && { right: -20, top: -2 }),
              }}
            >
              <PlusOutlined style={{ fontSize: 10, color: '#fff' }} />
            </div>
          </Tooltip>
        )}
      </div>
    );
  };

  const nodeContent = (
    <div
      className={`room-node-grid ${selected ? 'selected' : ''} ${isActiveRoom ? 'active-room' : ''}`}
      style={{
        width: size,
        height: size,
        position: 'relative',
        // Outline effect: gold for active room in panel, blue for RF selection
        outline: isActiveRoom 
          ? '3px solid #faad14'  // Gold for properties panel selection
          : selected 
            ? '3px solid #1890ff'  // Blue for React Flow selection
            : 'none',
        outlineOffset: 4,
        borderRadius: 10,
      }}
    >
      {/* Square room shape */}
      <div
        style={{
          width: '100%',
          height: '100%',
          background: baseColor,
          border: isActiveRoom 
            ? '3px solid #fff'
            : selected 
              ? '3px solid #fff' 
              : '2px solid rgba(255,255,255,0.3)',
          // Simplified shadow - no expensive blurs or transitions
          boxShadow: '2px 4px 8px rgba(0,0,0,0.4)',
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

      {/* Cardinal direction handles with plus buttons */}
      {/* North (top center) */}
      {renderHandle('north', Position.Top, { top: -6, left: '50%', transform: 'translateX(-50%)' })}
      {/* South (bottom center) */}
      {renderHandle('south', Position.Bottom, { bottom: -6, left: '50%', transform: 'translateX(-50%)' })}
      {/* East (right center) */}
      {renderHandle('east', Position.Right, { right: -6, top: '50%', transform: 'translateY(-50%)' })}
      {/* West (left center) */}
      {renderHandle('west', Position.Left, { left: -6, top: '50%', transform: 'translateY(-50%)' })}
      
      {/* Vertical direction handles (up/down) */}
      {renderHandle('up', Position.Top, { top: -6, right: 8, left: 'auto' }, true)}
      {renderHandle('down', Position.Bottom, { bottom: -6, right: 8, left: 'auto' }, true)}
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
