/**
 * QuestDesigner Component
 *
 * Visual quest chain editor using React Flow.
 * Displays quests as nodes with prerequisite connections.
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
import { QuestNodeComponent } from './QuestNode';

interface Quest {
  id: string;
  quest_id: string;
  name: string;
  description?: string;
  objectives?: Array<{ type: string; target: string; count: number }>;
  rewards?: { experience?: number; items?: string[] };
  prerequisites?: string[];
  position: { x: number; y: number };
}

interface QuestDesignerProps {
  quests: Quest[];
  onQuestSelect: (questId: string) => void;
  onQuestMove: (questId: string, position: { x: number; y: number }) => void;
  onPrerequisiteCreate: (questId: string, prerequisiteId: string) => void;
  onPrerequisiteDelete: (questId: string, prerequisiteId: string) => void;
}

// Custom node types
const nodeTypes: NodeTypes = {
  quest: QuestNodeComponent,
};

export function QuestDesigner({
  quests,
  onQuestSelect,
  onQuestMove,
  onPrerequisiteCreate,
  onPrerequisiteDelete,
}: QuestDesignerProps) {
  // Convert quests to React Flow nodes
  const initialNodes: Node[] = useMemo(
    () =>
      quests.map((quest) => ({
        id: quest.id,
        type: 'quest',
        position: quest.position,
        data: {
          label: quest.name,
          quest_id: quest.quest_id,
          description: quest.description,
          objectives: quest.objectives,
          rewards: quest.rewards,
        },
      })),
    [quests]
  );

  // Create edges from prerequisites
  const initialEdges: Edge[] = useMemo(() => {
    const edges: Edge[] = [];
    quests.forEach((quest) => {
      quest.prerequisites?.forEach((prereqId) => {
        edges.push({
          id: `${prereqId}->${quest.id}`,
          source: prereqId,
          target: quest.id,
          type: 'smoothstep',
          animated: true,
          markerEnd: {
            type: MarkerType.ArrowClosed,
          },
        });
      });
    });
    return edges;
  }, [quests]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync with props changes
  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  useEffect(() => {
    setEdges(initialEdges);
  }, [initialEdges, setEdges]);

  // Handle new prerequisite connections
  const onConnect = useCallback(
    (params: Connection) => {
      if (params.source && params.target) {
        onPrerequisiteCreate(params.target, params.source);
        setEdges((eds) => addEdge({
          ...params,
          type: 'smoothstep',
          animated: true,
          markerEnd: { type: MarkerType.ArrowClosed },
        }, eds));
      }
    },
    [onPrerequisiteCreate, setEdges]
  );

  // Handle node click
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onQuestSelect(node.id);
    },
    [onQuestSelect]
  );

  // Handle node drag end
  const onNodeDragStop = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onQuestMove(node.id, node.position);
    },
    [onQuestMove]
  );

  return (
    <div className="quest-designer">
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
