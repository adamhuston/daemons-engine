/**
 * RoomBuilder Component
 *
 * Visual room editor using React Flow.
 * Displays rooms as nodes and exits as edges on a 2D canvas.
 */

import { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  NodeTypes,
  ReactFlowInstance,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Select, Button, Tooltip } from 'antd';
import { UndoOutlined, RedoOutlined } from '@ant-design/icons';
import type { RoomNode, RoomConnection } from '../../../shared/types';
import { RoomNodeComponent } from './RoomNode';

// History entry for undo/redo
interface HistoryEntry {
  nodes: Node[];
  edges: Edge[];
}

interface RoomBuilderProps {
  rooms: RoomNode[];
  connections: RoomConnection[];
  zLevels: number[];
  onRoomSelect: (roomId: string) => void;
  onRoomMove: (roomId: string, position: { x: number; y: number }) => void;
  onConnectionCreate: (source: string, target: string, direction: string) => void;
  onConnectionDelete: (connectionId: string) => void;
}

// Custom node types
const nodeTypes: NodeTypes = {
  room: RoomNodeComponent,
};

export function RoomBuilder({
  rooms,
  connections,
  zLevels,
  onRoomSelect,
  onRoomMove,
  onConnectionCreate,
  onConnectionDelete,
}: RoomBuilderProps) {
  // Get unique areas from rooms
  const areas = useMemo(() => {
    const areaSet = new Set<string>();
    rooms.forEach((room) => {
      if (room.area_id) areaSet.add(room.area_id);
    });
    return Array.from(areaSet).sort();
  }, [rooms]);

  // Selected area filter (null = all areas)
  const [selectedArea, setSelectedArea] = useState<string | null>(null);

  // Layer visibility - which z-levels are visible and their opacity
  const [activeLayer, setActiveLayer] = useState<number | 'all'>('all');

  // Auto-select first area when areas load
  useEffect(() => {
    if (areas.length > 0 && selectedArea === null) {
      setSelectedArea(areas[0]);
    }
  }, [areas, selectedArea]);

  // Filter rooms and connections by selected area
  const filteredRooms = useMemo(() => {
    if (!selectedArea) return rooms;
    return rooms.filter((room) => room.area_id === selectedArea);
  }, [rooms, selectedArea]);

  // Get z-levels for the current area
  const areaZLevels = useMemo(() => {
    const levels = new Set(filteredRooms.map((r) => r.z_level));
    return Array.from(levels).sort((a, b) => b - a); // Descending (highest first)
  }, [filteredRooms]);

  const filteredRoomIds = useMemo(
    () => new Set(filteredRooms.map((r) => r.id)),
    [filteredRooms]
  );

  const filteredConnections = useMemo(() => {
    if (!selectedArea) return connections;
    return connections.filter(
      (conn) => filteredRoomIds.has(conn.source) && filteredRoomIds.has(conn.target)
    );
  }, [connections, selectedArea, filteredRoomIds]);

  // Calculate opacity for a room based on its layer vs active layer
  const getLayerOpacity = useCallback((roomZLevel: number): number => {
    if (activeLayer === 'all') return 1;
    if (roomZLevel === activeLayer) return 1;
    // Other layers are semi-transparent like tracing paper
    return 0.25;
  }, [activeLayer]);

  // Check if a room is on the active layer (interactive)
  const isOnActiveLayer = useCallback((roomZLevel: number): boolean => {
    if (activeLayer === 'all') return true;
    return roomZLevel === activeLayer;
  }, [activeLayer]);

  // Convert rooms to React Flow nodes with layer-based opacity
  const initialNodes: Node[] = useMemo(
    () =>
      filteredRooms.map((room) => {
        const opacity = getLayerOpacity(room.z_level);
        const isActive = isOnActiveLayer(room.z_level);
        return {
          id: room.id,
          type: 'room',
          position: room.position,
          data: {
            label: room.name,
            room_id: room.room_id,
            room_type: room.room_type,
            description: room.description,
            z_level: room.z_level,
            opacity,
            isActive,
          },
          style: { 
            opacity,
            pointerEvents: isActive ? 'auto' : 'none',
          },
          selectable: isActive,
          draggable: isActive,
          connectable: isActive,
        };
      }),
    [filteredRooms, getLayerOpacity, isOnActiveLayer]
  );

  // Convert connections to React Flow edges with styling based on direction
  const initialEdges: Edge[] = useMemo(
    () =>
      filteredConnections.map((conn) => {
        const isVertical = conn.sourceHandle === 'up' || conn.sourceHandle === 'down';
        // Find source room to get its opacity
        const sourceRoom = filteredRooms.find((r) => r.id === conn.source);
        const targetRoom = filteredRooms.find((r) => r.id === conn.target);
        const edgeOpacity = Math.min(
          getLayerOpacity(sourceRoom?.z_level ?? 0),
          getLayerOpacity(targetRoom?.z_level ?? 0)
        );
        return {
          id: conn.id,
          source: conn.source,
          target: conn.target,
          sourceHandle: conn.sourceHandle,
          targetHandle: conn.targetHandle,
          type: 'straight', // Straight lines instead of curved
          animated: isVertical,
          style: {
            stroke: isVertical ? '#faad14' : '#52c41a', // Yellow for up/down, green for cardinal
            strokeWidth: 2,
            opacity: edgeOpacity,
          },
          labelStyle: { fontSize: 10, opacity: edgeOpacity },
          label: isVertical ? conn.sourceHandle : undefined,
        };
      }),
    [filteredConnections, filteredRooms, getLayerOpacity]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Undo/Redo history
  const historyRef = useRef<HistoryEntry[]>([]);
  const historyIndexRef = useRef(-1);
  const isUndoRedoRef = useRef(false);

  // Save state to history (called after user actions)
  const saveToHistory = useCallback(() => {
    if (isUndoRedoRef.current) return;
    
    // Truncate any future history if we're not at the end
    historyRef.current = historyRef.current.slice(0, historyIndexRef.current + 1);
    
    // Add current state
    historyRef.current.push({ nodes: [...nodes], edges: [...edges] });
    historyIndexRef.current = historyRef.current.length - 1;
    
    // Limit history size
    if (historyRef.current.length > 50) {
      historyRef.current.shift();
      historyIndexRef.current--;
    }
  }, [nodes, edges]);

  // Undo
  const undo = useCallback(() => {
    if (historyIndexRef.current <= 0) return;
    
    isUndoRedoRef.current = true;
    historyIndexRef.current--;
    const entry = historyRef.current[historyIndexRef.current];
    setNodes(entry.nodes);
    setEdges(entry.edges);
    setTimeout(() => { isUndoRedoRef.current = false; }, 0);
  }, [setNodes, setEdges]);

  // Redo
  const redo = useCallback(() => {
    if (historyIndexRef.current >= historyRef.current.length - 1) return;
    
    isUndoRedoRef.current = true;
    historyIndexRef.current++;
    const entry = historyRef.current[historyIndexRef.current];
    setNodes(entry.nodes);
    setEdges(entry.edges);
    setTimeout(() => { isUndoRedoRef.current = false; }, 0);
  }, [setNodes, setEdges]);

  // Keyboard shortcuts for undo/redo
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'z') {
        e.preventDefault();
        if (e.shiftKey) {
          redo();
        } else {
          undo();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, redo]);

  // Sync with props changes
  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  useEffect(() => {
    setEdges(initialEdges);
  }, [initialEdges, setEdges]);

  // Handle new connections
  const onConnect = useCallback(
    (params: Connection) => {
      if (params.source && params.target && params.sourceHandle) {
        saveToHistory();
        onConnectionCreate(params.source, params.target, params.sourceHandle);
        setEdges((eds) => addEdge(params, eds));
      }
    },
    [onConnectionCreate, setEdges, saveToHistory]
  );

  // Handle node click
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onRoomSelect(node.id);
    },
    [onRoomSelect]
  );

  // Handle node drag start (save state before drag)
  const onNodeDragStart = useCallback(() => {
    saveToHistory();
  }, [saveToHistory]);

  // Handle node drag end
  const onNodeDragStop = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onRoomMove(node.id, node.position);
    },
    [onRoomMove]
  );

  return (
    <div className="room-builder">
      <div className="room-builder-toolbar">
        <Select
          value={selectedArea}
          onChange={setSelectedArea}
          style={{ width: 240 }}
          placeholder="Select Area"
          options={[
            { value: null, label: 'All Areas' },
            ...areas.map((area) => ({
              value: area,
              label: area.replace('area_', '').replace(/_/g, ' '),
            })),
          ]}
        />
        {areaZLevels.length > 1 && (
          <Select
            value={activeLayer}
            onChange={setActiveLayer}
            style={{ width: 140 }}
            options={[
              { value: 'all', label: '🗂️ All Layers' },
              ...areaZLevels.map((z) => ({
                value: z,
                label: `${z >= 0 ? '↑' : '↓'} Level ${z}`,
              })),
            ]}
          />
        )}
        <span className="room-count">
          {filteredRooms.length} room{filteredRooms.length !== 1 ? 's' : ''}
        </span>
        <div className="toolbar-spacer" />
        <Tooltip title="Undo (Ctrl+Z)">
          <Button
            type="text"
            icon={<UndoOutlined />}
            onClick={undo}
            disabled={historyIndexRef.current <= 0}
          />
        </Tooltip>
        <Tooltip title="Redo (Ctrl+Shift+Z)">
          <Button
            type="text"
            icon={<RedoOutlined />}
            onClick={redo}
            disabled={historyIndexRef.current >= historyRef.current.length - 1}
          />
        </Tooltip>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onNodeDragStart={onNodeDragStart}
        onNodeDragStop={onNodeDragStop}
        nodeTypes={nodeTypes}
        fitView
      >
        <Controls />
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
      </ReactFlow>
    </div>
  );
}
