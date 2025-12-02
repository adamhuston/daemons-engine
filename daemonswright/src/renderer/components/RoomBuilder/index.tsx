/**
 * RoomBuilder Component
 *
 * Visual room editor using React Flow.
 * Displays rooms as nodes and exits as edges on a 2D canvas.
 */

import { useCallback, useEffect, useMemo } from 'react';
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
} from 'reactflow';
import 'reactflow/dist/style.css';
import type { RoomNode, RoomConnection } from '../../shared/types';
import { RoomNodeComponent } from './RoomNode';

interface RoomBuilderProps {
  rooms: RoomNode[];
  connections: RoomConnection[];
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
  onRoomSelect,
  onRoomMove,
  onConnectionCreate,
  onConnectionDelete,
}: RoomBuilderProps) {
  // Convert rooms to React Flow nodes
  const initialNodes: Node[] = useMemo(
    () =>
      rooms.map((room) => ({
        id: room.id,
        type: 'room',
        position: room.position,
        data: {
          label: room.name,
          room_id: room.room_id,
          room_type: room.room_type,
          description: room.description,
        },
      })),
    [rooms]
  );

  // Convert connections to React Flow edges
  const initialEdges: Edge[] = useMemo(
    () =>
      connections.map((conn) => ({
        id: conn.id,
        source: conn.source,
        target: conn.target,
        sourceHandle: conn.sourceHandle,
        targetHandle: conn.targetHandle,
        type: 'smoothstep',
        animated: false,
      })),
    [connections]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

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
        onConnectionCreate(params.source, params.target, params.sourceHandle);
        setEdges((eds) => addEdge(params, eds));
      }
    },
    [onConnectionCreate, setEdges]
  );

  // Handle node click
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onRoomSelect(node.id);
    },
    [onRoomSelect]
  );

  // Handle node drag end
  const onNodeDragStop = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onRoomMove(node.id, node.position);
    },
    [onRoomMove]
  );

  return (
    <div className="room-builder">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
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
