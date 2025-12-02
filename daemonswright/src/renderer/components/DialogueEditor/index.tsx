/**
 * DialogueEditor Component
 *
 * Visual dialogue tree editor using React Flow.
 * Shows conversation branches and responses.
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
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { DialogueNodeComponent } from './DialogueNode';

interface DialogueNode {
  id: string;
  type: 'npc' | 'player' | 'action';
  text: string;
  responses?: string[]; // IDs of response nodes
  condition?: string;
  action?: string;
  position: { x: number; y: number };
}

interface DialogueEditorProps {
  nodes: DialogueNode[];
  onNodeSelect: (nodeId: string) => void;
  onNodeMove: (nodeId: string, position: { x: number; y: number }) => void;
  onConnectionCreate: (sourceId: string, targetId: string) => void;
  onConnectionDelete: (sourceId: string, targetId: string) => void;
}

// Custom node types
const nodeTypes: NodeTypes = {
  dialogue: DialogueNodeComponent,
};

export function DialogueEditor({
  nodes: dialogueNodes,
  onNodeSelect,
  onNodeMove,
  onConnectionCreate,
  onConnectionDelete,
}: DialogueEditorProps) {
  // Convert dialogue nodes to React Flow nodes
  const initialNodes: Node[] = useMemo(
    () =>
      dialogueNodes.map((node) => ({
        id: node.id,
        type: 'dialogue',
        position: node.position,
        data: {
          text: node.text,
          nodeType: node.type,
          condition: node.condition,
          action: node.action,
        },
      })),
    [dialogueNodes]
  );

  // Create edges from responses
  const initialEdges: Edge[] = useMemo(() => {
    const edges: Edge[] = [];
    dialogueNodes.forEach((node) => {
      node.responses?.forEach((responseId) => {
        edges.push({
          id: `${node.id}->${responseId}`,
          source: node.id,
          target: responseId,
          type: 'smoothstep',
          markerEnd: {
            type: MarkerType.ArrowClosed,
          },
        });
      });
    });
    return edges;
  }, [dialogueNodes]);

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
      if (params.source && params.target) {
        onConnectionCreate(params.source, params.target);
        setEdges((eds) => addEdge({
          ...params,
          type: 'smoothstep',
          markerEnd: { type: MarkerType.ArrowClosed },
        }, eds));
      }
    },
    [onConnectionCreate, setEdges]
  );

  // Handle node click
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeSelect(node.id);
    },
    [onNodeSelect]
  );

  // Handle node drag end
  const onNodeDragStop = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeMove(node.id, node.position);
    },
    [onNodeMove]
  );

  return (
    <div className="dialogue-editor">
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
