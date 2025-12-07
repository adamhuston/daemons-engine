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
  MarkerType,
  EdgeChange,
  reconnectEdge,
  ConnectionMode,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Select, Button, Tooltip, Modal, Form, Input, Popover, Space, message } from 'antd';
import { UndoOutlined, RedoOutlined, PlusOutlined, SwapOutlined, DeleteOutlined, CopyOutlined } from '@ant-design/icons';
import type { RoomNode, RoomConnection } from '../../../shared/types';
import { RoomNodeComponent } from './RoomNode';
import { AddableSelect } from '../AddableSelect';

// Grid size in pixels - rooms snap to this grid
const GRID_SIZE = 150;

// History entry for undo/redo
interface HistoryEntry {
  nodes: Node[];
  edges: Edge[];
}

// Content counts per room
interface RoomContentCounts {
  [roomId: string]: {
    npcCount: number;
    itemCount: number;
  };
}

// Copied room data for clipboard
interface CopiedRoomData {
  name: string;
  description: string;
  room_type: string;
  area_id: string;
  z_level: number;
  originalId: string; // For generating new ID
}

interface RoomBuilderProps {
  rooms: RoomNode[];
  connections: RoomConnection[];
  zLevels: number[];
  activeRoomId: string | null;
  onRoomSelect: (roomId: string) => void;
  onRoomMove: (roomId: string, position: { x: number; y: number }) => void;
  onRoomCreate: (roomData: {
    id: string;
    name: string;
    description: string;
    room_type: string;
    area_id: string;
    z_level: number;
  }, position: { x: number; y: number }, sourceRoomId?: string) => Promise<boolean>;
  onConnectionCreate: (source: string, target: string, direction: string) => Promise<boolean>;
  onConnectionDelete: (connectionId: string) => Promise<boolean>;
  onConnectionUpdate?: (oldConnectionId: string, newSource: string, newTarget: string, direction: string) => Promise<boolean>;
  onRemoveExit: (roomId: string, direction: string) => Promise<boolean>;
  onAreaCreate: (areaId: string, displayName: string) => Promise<boolean>;
  // Schema options for room types
  roomTypeOptions?: string[];
  onAddRoomType?: (newType: string) => Promise<boolean>;
  // Content counts for badges
  roomContentCounts?: RoomContentCounts;
  // Drag-and-drop handlers for NPC/Item placement
  onNpcDrop?: (roomId: string, npcTemplateId: string) => void;
  onItemDrop?: (roomId: string, itemTemplateId: string) => void;
}

// Custom node types
const nodeTypes: NodeTypes = {
  room: RoomNodeComponent,
};

export function RoomBuilder({
  rooms,
  connections,
  zLevels,
  activeRoomId,
  onRoomSelect,
  onRoomMove,
  onRoomCreate,
  onConnectionCreate,
  onConnectionDelete,
  onConnectionUpdate,
  onRemoveExit,
  onAreaCreate,
  roomTypeOptions = [],
  onAddRoomType,
  roomContentCounts = {},
  onNpcDrop,
  onItemDrop,
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

  // Create room modal state
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createPosition, setCreatePosition] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [createFromExit, setCreateFromExit] = useState<{ sourceRoomId: string; direction: string } | null>(null);
  const [createForm] = Form.useForm();
  const reactFlowInstance = useRef<ReactFlowInstance | null>(null);

  // Create area modal state
  const [createAreaModalOpen, setCreateAreaModalOpen] = useState(false);
  const [createAreaForm] = Form.useForm();

  // Selected edge state for edge editing
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null);
  const [edgePopoverOpen, setEdgePopoverOpen] = useState(false);
  const [edgePopoverPosition, setEdgePopoverPosition] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Handler for creating a room from an exit plus button
  const handleCreateFromExit = useCallback((sourceRoomId: string, direction: string, position: { x: number; y: number }) => {
    if (!selectedArea) return;
    
    setCreateFromExit({ sourceRoomId, direction });
    setCreatePosition(position);
    
    // Generate a unique room ID
    const timestamp = Date.now();
    const areaName = selectedArea.replace('area_', '');
    const defaultId = `${areaName}_room_${timestamp}`;
    
    createForm.setFieldsValue({
      id: defaultId,
      name: 'New Room',
      description: '',
      room_type: 'chamber',
      area_id: selectedArea,
      z_level: direction === 'up' ? (activeLayer === 'all' ? 1 : (activeLayer as number) + 1) 
             : direction === 'down' ? (activeLayer === 'all' ? -1 : (activeLayer as number) - 1)
             : (activeLayer === 'all' ? 0 : activeLayer),
    });
    
    setCreateModalOpen(true);
  }, [selectedArea, activeLayer, createForm]);

  // Auto-select first area when areas load
  useEffect(() => {
    if (areas.length > 0 && selectedArea === null) {
      setSelectedArea(areas[0]);
    }
  }, [areas, selectedArea]);

  // Fit view to show all rooms when area or layer changes
  useEffect(() => {
    if (reactFlowInstance.current && selectedArea) {
      // Small delay to let nodes update before fitting
      const timer = setTimeout(() => {
        reactFlowInstance.current?.fitView({
          padding: 0.2,
          duration: 300,
        });
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [selectedArea, activeLayer]);

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
        const isActiveRoom = room.id === activeRoomId;
        const contentCounts = roomContentCounts[room.id] || { npcCount: 0, itemCount: 0 };
        return {
          id: room.id,
          type: 'room',
          position: room.position,
          data: {
            label: room.name,
            room_id: room.id,
            room_type: room.room_type,
            description: room.description,
            z_level: room.z_level,
            opacity,
            isActive,
            isActiveRoom,
            exits: room.exits,
            onCreateFromExit: handleCreateFromExit,
            npcCount: contentCounts.npcCount,
            itemCount: contentCounts.itemCount,
            // Drag-and-drop handlers
            onNpcDrop,
            onItemDrop,
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
    [filteredRooms, getLayerOpacity, isOnActiveLayer, handleCreateFromExit, activeRoomId, roomContentCounts, onNpcDrop, onItemDrop]
  );

  // Check if a connection is bidirectional (by looking it up in connections array)
  const isConnectionBidirectional = useCallback((edgeId: string) => {
    const conn = connections.find((c) => c.id === edgeId);
    return conn?.bidirectional === true;
  }, [connections]);

  // Convert connections to React Flow edges with smooth curves and arrowheads
  const initialEdges: Edge[] = useMemo(
    () =>
      filteredConnections.map((conn) => {
        const isVertical = conn.sourceHandle === 'up' || conn.sourceHandle === 'down';
        // Use the bidirectional flag set by buildConnections
        const isBidirectional = conn.bidirectional === true;
        // Find source room to get its opacity
        const sourceRoom = filteredRooms.find((r) => r.id === conn.source);
        const targetRoom = filteredRooms.find((r) => r.id === conn.target);
        const edgeOpacity = Math.min(
          getLayerOpacity(sourceRoom?.z_level ?? 0),
          getLayerOpacity(targetRoom?.z_level ?? 0)
        );
        const strokeColor = isVertical ? '#faad14' : '#52c41a';
        const isSelected = selectedEdge?.id === conn.id;
        
        return {
          id: conn.id,
          source: conn.source,
          target: conn.target,
          sourceHandle: conn.sourceHandle,
          targetHandle: conn.targetHandle,
          type: 'bezier', // Bezier curves for smooth S-curves
          animated: isVertical,
          selected: isSelected,
          style: {
            stroke: isSelected ? '#1890ff' : strokeColor,
            strokeWidth: isSelected ? 3 : 2,
            opacity: edgeOpacity,
            cursor: 'pointer',
          },
          // Arrowhead on target end to show direction of travel
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: isSelected ? '#1890ff' : strokeColor,
            width: 20,
            height: 20,
          },
          // For bidirectional exits, also show arrow at source
          ...(isBidirectional && {
            markerStart: {
              type: MarkerType.ArrowClosed,
              color: isSelected ? '#1890ff' : strokeColor,
              width: 20,
              height: 20,
            },
          }),
        };
      }),
    [filteredConnections, filteredRooms, getLayerOpacity, selectedEdge]
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

  // Clipboard for copy/paste
  const clipboardRef = useRef<CopiedRoomData | null>(null);

  // Copy the currently selected room
  const copyRoom = useCallback(() => {
    if (!activeRoomId) {
      message.warning('No room selected to copy');
      return;
    }
    
    const room = rooms.find((r) => r.id === activeRoomId);
    if (!room) {
      message.error('Selected room not found');
      return;
    }
    
    clipboardRef.current = {
      name: room.name,
      description: room.description || '',
      room_type: room.room_type || 'chamber',
      area_id: room.area_id || selectedArea || '',
      z_level: room.z_level,
      originalId: room.id,
    };
    
    message.success(`Copied "${room.name}"`);
  }, [activeRoomId, rooms, selectedArea]);

  // Paste the copied room at a new position
  const pasteRoom = useCallback(async () => {
    if (!clipboardRef.current) {
      message.warning('Nothing to paste. Copy a room first (Ctrl+C)');
      return;
    }
    
    if (!selectedArea) {
      message.warning('Select an area first');
      return;
    }
    
    const copied = clipboardRef.current;
    
    // Generate unique ID based on original ID + timestamp
    const timestamp = Date.now();
    const baseId = copied.originalId.replace(/_copy_\d+$/, ''); // Remove any previous _copy suffix
    const newId = `${baseId}_copy_${timestamp}`;
    
    // Calculate paste position at center of current viewport with offset
    let pastePosition = { x: 0, y: 0 };
    if (reactFlowInstance.current) {
      const { x, y, zoom } = reactFlowInstance.current.getViewport();
      // Get the center of the visible area
      const centerX = -x / zoom + 400;
      const centerY = -y / zoom + 300;
      
      // Snap to grid with slight offset to avoid exact overlap
      pastePosition = {
        x: Math.round(centerX / GRID_SIZE) * GRID_SIZE + GRID_SIZE,
        y: Math.round(centerY / GRID_SIZE) * GRID_SIZE + GRID_SIZE,
      };
    }
    
    // Create the new room
    const success = await onRoomCreate(
      {
        id: newId,
        name: `${copied.name} (Copy)`,
        description: copied.description,
        room_type: copied.room_type,
        area_id: copied.area_id,
        z_level: activeLayer === 'all' ? copied.z_level : (activeLayer as number),
      },
      pastePosition
    );
    
    if (success) {
      message.success(`Pasted "${copied.name} (Copy)"`);
      // Select the newly created room
      onRoomSelect(newId);
    } else {
      message.error('Failed to paste room');
    }
  }, [selectedArea, activeLayer, onRoomCreate, onRoomSelect]);

  // Keyboard shortcuts for undo/redo and copy/paste
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
      // Copy: Ctrl/Cmd+C
      if ((e.metaKey || e.ctrlKey) && e.key === 'c') {
        // Only handle if not in an input/textarea
        if (document.activeElement?.tagName !== 'INPUT' && 
            document.activeElement?.tagName !== 'TEXTAREA') {
          e.preventDefault();
          copyRoom();
        }
      }
      // Paste: Ctrl/Cmd+V
      if ((e.metaKey || e.ctrlKey) && e.key === 'v') {
        // Only handle if not in an input/textarea
        if (document.activeElement?.tagName !== 'INPUT' && 
            document.activeElement?.tagName !== 'TEXTAREA') {
          e.preventDefault();
          pasteRoom();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, redo, copyRoom, pasteRoom]);

  // Sync with props changes
  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  useEffect(() => {
    setEdges(initialEdges);
  }, [initialEdges, setEdges]);

  // Validate connections - allow connections between different nodes
  const isValidConnection = useCallback((connection: Connection) => {
    // Don't allow self-connections
    if (connection.source === connection.target) return false;
    // Allow all other connections
    return true;
  }, []);

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
      setSelectedEdge(null);
      setEdgePopoverOpen(false);
      onRoomSelect(node.id);
    },
    [onRoomSelect]
  );

  // Handle edge click - show context menu for editing
  const onEdgeClick = useCallback(
    (event: React.MouseEvent, edge: Edge) => {
      event.stopPropagation();
      setSelectedEdge(edge);
      setEdgePopoverPosition({ x: event.clientX, y: event.clientY });
      setEdgePopoverOpen(true);
    },
    []
  );

  // Handle pane click to deselect edge
  const onPaneClickDeselect = useCallback(() => {
    setSelectedEdge(null);
    setEdgePopoverOpen(false);
  }, []);

  // Toggle bidirectional exit
  const handleToggleBidirectional = useCallback(async () => {
    if (!selectedEdge) return;
    
    // Look up the connection to check its bidirectional status
    const conn = connections.find((c) => c.id === selectedEdge.id);
    const isBidirectional = conn?.bidirectional === true;
    
    if (isBidirectional) {
      // To make unidirectional, we need to remove the reverse exit from the target room
      // The reverse exit goes from target to source in the opposite direction
      const oppositeDir: Record<string, string> = {
        north: 'south',
        south: 'north',
        east: 'west',
        west: 'east',
        up: 'down',
        down: 'up',
      };
      const reverseDirection = oppositeDir[selectedEdge.sourceHandle || 'north'] || 'south';
      // Call onRemoveExit to remove just the reverse exit (from target room)
      await onRemoveExit(selectedEdge.target, reverseDirection);
    } else {
      // Create the reverse connection to make it bidirectional
      const oppositeDir: Record<string, string> = {
        north: 'south',
        south: 'north',
        east: 'west',
        west: 'east',
        up: 'down',
        down: 'up',
      };
      const reverseDirection = oppositeDir[selectedEdge.sourceHandle || 'north'] || 'south';
      await onConnectionCreate(selectedEdge.target, selectedEdge.source, reverseDirection);
    }
    
    setEdgePopoverOpen(false);
    setSelectedEdge(null);
  }, [selectedEdge, connections, onConnectionCreate, onRemoveExit]);

  // Delete edge
  const handleDeleteEdge = useCallback(async () => {
    if (!selectedEdge) return;
    
    await onConnectionDelete(selectedEdge.id);
    setEdgePopoverOpen(false);
    setSelectedEdge(null);
  }, [selectedEdge, onConnectionDelete]);

  // Handle edge reconnection (drag edge to new node)
  const onReconnect = useCallback(
    async (oldEdge: Edge, newConnection: Connection) => {
      if (!newConnection.source || !newConnection.target || !newConnection.sourceHandle) return;
      
      saveToHistory();
      
      // Delete the old connection and create new one
      if (onConnectionUpdate) {
        await onConnectionUpdate(
          oldEdge.id,
          newConnection.source,
          newConnection.target,
          newConnection.sourceHandle
        );
      } else {
        // Fallback: delete old and create new
        await onConnectionDelete(oldEdge.id);
        await onConnectionCreate(
          newConnection.source,
          newConnection.target,
          newConnection.sourceHandle
        );
      }
      
      setEdges((eds) => reconnectEdge(oldEdge, newConnection, eds));
    },
    [onConnectionUpdate, onConnectionDelete, onConnectionCreate, setEdges, saveToHistory]
  );

  // Handle node drag start (save state before drag)
  const onNodeDragStart = useCallback(() => {
    saveToHistory();
  }, [saveToHistory]);

  // Handle node drag end - snap to grid and notify parent
  const onNodeDragStop = useCallback(
    (_: React.MouseEvent, node: Node) => {
      // Snap position to grid
      const snappedX = Math.round(node.position.x / GRID_SIZE) * GRID_SIZE;
      const snappedY = Math.round(node.position.y / GRID_SIZE) * GRID_SIZE;
      const snappedPosition = { x: snappedX, y: snappedY };
      
      // Update node position to snapped value
      setNodes((nds) =>
        nds.map((n) =>
          n.id === node.id ? { ...n, position: snappedPosition } : n
        )
      );
      
      onRoomMove(node.id, snappedPosition);
    },
    [onRoomMove, setNodes]
  );

  // Handle double-click on canvas to create new room
  const onPaneClick = useCallback((event: React.MouseEvent) => {
    // Only handle double-click
    if (event.detail !== 2) return;
    if (!reactFlowInstance.current) return;
    if (!selectedArea) return;
    
    // Get canvas position from screen coordinates
    const bounds = (event.target as HTMLElement).getBoundingClientRect();
    const position = reactFlowInstance.current.screenToFlowPosition({
      x: event.clientX - bounds.left,
      y: event.clientY - bounds.top,
    });
    
    // Snap to grid
    const snappedX = Math.round(position.x / GRID_SIZE) * GRID_SIZE;
    const snappedY = Math.round(position.y / GRID_SIZE) * GRID_SIZE;
    
    setCreatePosition({ x: snappedX, y: snappedY });
    
    // Generate a unique room ID
    const timestamp = Date.now();
    const areaName = selectedArea.replace('area_', '');
    const defaultId = `${areaName}_room_${timestamp}`;
    
    createForm.setFieldsValue({
      id: defaultId,
      name: 'New Room',
      description: '',
      room_type: 'chamber',
      area_id: selectedArea,
      z_level: activeLayer === 'all' ? 0 : activeLayer,
    });
    
    setCreateModalOpen(true);
  }, [selectedArea, activeLayer, createForm]);

  // Handle create room form submission
  const handleCreateRoom = useCallback(async () => {
    try {
      const values = await createForm.validateFields();
      // Pass sourceRoomId so the new room is created in the same folder
      const sourceRoomId = createFromExit?.sourceRoomId;
      const success = await onRoomCreate(values, createPosition, sourceRoomId);
      if (success) {
        // If we created from an exit, also create the connection
        if (createFromExit) {
          await onConnectionCreate(
            createFromExit.sourceRoomId,
            values.id,
            createFromExit.direction
          );
        }
        setCreateModalOpen(false);
        setCreateFromExit(null);
        createForm.resetFields();
      }
    } catch (err) {
      console.error('Create room validation failed:', err);
    }
  }, [createForm, createPosition, onRoomCreate, createFromExit, onConnectionCreate]);

  // Handle modal cancel
  const handleCreateModalCancel = useCallback(() => {
    setCreateModalOpen(false);
    setCreateFromExit(null);
    createForm.resetFields();
  }, [createForm]);

  // Handle create from toolbar button
  const handleCreateButtonClick = useCallback(() => {
    if (!selectedArea) return;
    
    // Clear any exit creation state
    setCreateFromExit(null);
    
    // Place at center of current view
    if (reactFlowInstance.current) {
      const { x, y, zoom } = reactFlowInstance.current.getViewport();
      // Get the center of the visible area
      const centerX = -x / zoom + 400;
      const centerY = -y / zoom + 300;
      
      // Snap to grid
      const snappedX = Math.round(centerX / GRID_SIZE) * GRID_SIZE;
      const snappedY = Math.round(centerY / GRID_SIZE) * GRID_SIZE;
      
      setCreatePosition({ x: snappedX, y: snappedY });
    } else {
      setCreatePosition({ x: 0, y: 0 });
    }
    
    // Generate a unique room ID
    const timestamp = Date.now();
    const areaName = selectedArea.replace('area_', '');
    const defaultId = `${areaName}_room_${timestamp}`;
    
    createForm.setFieldsValue({
      id: defaultId,
      name: 'New Room',
      description: '',
      room_type: 'chamber',
      area_id: selectedArea,
      z_level: activeLayer === 'all' ? 0 : activeLayer,
    });
    
    setCreateModalOpen(true);
  }, [selectedArea, activeLayer, createForm]);

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
        <Tooltip title="Create New Area">
          <Button
            type="default"
            icon={<PlusOutlined />}
            onClick={() => setCreateAreaModalOpen(true)}
          />
        </Tooltip>
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
        <Tooltip title="Create Room (Double-click canvas)">
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleCreateButtonClick}
            disabled={!selectedArea}
          >
            New Room
          </Button>
        </Tooltip>
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
        <Tooltip title="Copy Room (Ctrl+C)">
          <Button
            type="text"
            icon={<CopyOutlined />}
            onClick={copyRoom}
            disabled={!activeRoomId}
          />
        </Tooltip>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        isValidConnection={isValidConnection}
        onNodeClick={onNodeClick}
        onNodeDragStart={onNodeDragStart}
        onNodeDragStop={onNodeDragStop}
        onPaneClick={(e) => { onPaneClick(e); onPaneClickDeselect(); }}
        onEdgeClick={onEdgeClick}
        onReconnect={onReconnect}
        onInit={(instance) => { reactFlowInstance.current = instance; }}
        nodeTypes={nodeTypes}
        snapToGrid={true}
        snapGrid={[GRID_SIZE, GRID_SIZE]}
        connectionMode={ConnectionMode.Loose}
        fitView
      >
        <Controls />
        <Background variant={BackgroundVariant.Dots} gap={GRID_SIZE} size={2} />
      </ReactFlow>

      {/* Edge Context Menu Popover */}
      {edgePopoverOpen && selectedEdge && (
        <div
          className="edge-context-menu"
          style={{
            position: 'fixed',
            left: edgePopoverPosition.x,
            top: edgePopoverPosition.y,
            zIndex: 1000,
            background: 'var(--color-bg-secondary, #1f1f1f)',
            border: '1px solid var(--color-border, #434343)',
            borderRadius: 6,
            padding: 8,
            boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
          }}
        >
          <Space direction="vertical" size="small">
            <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>
              Exit: {selectedEdge.sourceHandle} → {rooms.find(r => r.id === selectedEdge.target)?.name || selectedEdge.target}
            </div>
            <Button
              size="small"
              icon={<SwapOutlined />}
              onClick={handleToggleBidirectional}
              block
            >
              {isConnectionBidirectional(selectedEdge.id) 
                ? 'Make One-Way' 
                : 'Make Two-Way'}
            </Button>
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={handleDeleteEdge}
              block
            >
              Delete Exit
            </Button>
          </Space>
        </div>
      )}

      {/* Create Room Modal */}
      <Modal
        title={createFromExit 
          ? `Create Room (${createFromExit.direction} from ${createFromExit.sourceRoomId})`
          : "Create New Room"
        }
        open={createModalOpen}
        onOk={handleCreateRoom}
        onCancel={handleCreateModalCancel}
        okText="Create"
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="id"
            label="Room ID"
            rules={[{ required: true, message: 'Room ID is required' }]}
          >
            <Input placeholder="unique_room_id" />
          </Form.Item>
          <Form.Item
            name="name"
            label="Name"
            rules={[{ required: true, message: 'Name is required' }]}
          >
            <Input placeholder="Room Name" />
          </Form.Item>
          <Form.Item
            name="description"
            label="Description"
          >
            <Input.TextArea rows={3} placeholder="A brief description of the room..." />
          </Form.Item>
          <Form.Item
            name="room_type"
            label="Room Type"
            rules={[{ required: true }]}
          >
            {onAddRoomType ? (
              <AddableSelect
                value={createForm.getFieldValue('room_type')}
                onChange={(val) => createForm.setFieldValue('room_type', val)}
                options={roomTypeOptions.length > 0 ? roomTypeOptions : [
                  'ethereal', 'forest', 'cave', 'urban', 'chamber', 'corridor',
                  'outdoor', 'indoor', 'dungeon', 'shop', 'inn', 'temple', 'water'
                ]}
                onAddOption={onAddRoomType}
                placeholder="Select room type"
              />
            ) : (
              <Select
                options={[
                  { value: 'ethereal', label: 'Ethereal' },
                  { value: 'forest', label: 'Forest' },
                  { value: 'cave', label: 'Cave' },
                  { value: 'urban', label: 'Urban' },
                  { value: 'chamber', label: 'Chamber' },
                  { value: 'corridor', label: 'Corridor' },
                  { value: 'outdoor', label: 'Outdoor' },
                  { value: 'indoor', label: 'Indoor' },
                  { value: 'dungeon', label: 'Dungeon' },
                  { value: 'shop', label: 'Shop' },
                  { value: 'inn', label: 'Inn' },
                  { value: 'temple', label: 'Temple' },
                  { value: 'water', label: 'Water' },
                ]}
              />
            )}
          </Form.Item>
          <Form.Item name="area_id" hidden>
            <Input />
          </Form.Item>
          <Form.Item name="z_level" hidden>
            <Input type="number" />
          </Form.Item>
        </Form>
        {createFromExit && (
          <div style={{ marginTop: 8, color: '#888', fontSize: 12 }}>
            This will also create an exit from <strong>{createFromExit.sourceRoomId}</strong> to the new room.
          </div>
        )}
      </Modal>

      {/* Create Area Modal */}
      <Modal
        title="Create New Area"
        open={createAreaModalOpen}
        onOk={async () => {
          try {
            const values = await createAreaForm.validateFields();
            const success = await onAreaCreate(values.id, values.name);
            if (success) {
              setCreateAreaModalOpen(false);
              createAreaForm.resetFields();
              // Select the newly created area
              const normalizedId = `area_${values.id.toLowerCase().replace(/\s+/g, '_').replace(/^area_/, '')}`;
              setSelectedArea(normalizedId);
            }
          } catch (err) {
            console.error('Failed to create area:', err);
          }
        }}
        onCancel={() => {
          setCreateAreaModalOpen(false);
          createAreaForm.resetFields();
        }}
        okText="Create"
      >
        <Form form={createAreaForm} layout="vertical">
          <Form.Item
            name="name"
            label="Area Name"
            rules={[{ required: true, message: 'Area name is required' }]}
          >
            <Input placeholder="Dark Forest" />
          </Form.Item>
          <Form.Item
            name="id"
            label="Area ID"
            rules={[
              { required: true, message: 'Area ID is required' },
              { pattern: /^[a-z0-9_]+$/, message: 'Only lowercase letters, numbers, and underscores allowed' }
            ]}
            extra="Used for folder name and room references"
          >
            <Input placeholder="dark_forest" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

