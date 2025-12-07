/**
 * QuestDesigner Component
 *
 * Visual quest chain editor using React Flow.
 * Displays quests as nodes with prerequisite connections.
 * Includes a properties panel for editing quest details.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
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
  Panel,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Layout, Button, Empty, Spin, Modal, Form, Input, Select, message } from 'antd';
import { PlusOutlined, SaveOutlined } from '@ant-design/icons';
import { QuestNodeComponent } from './QuestNode';
import { QuestPropertiesPanel } from './QuestPropertiesPanel';
import { useQuests } from '../../hooks/useQuests';
import type { Quest } from '../../hooks/useQuests';
import './QuestDesigner.css';

const { Content, Sider } = Layout;
const { TextArea } = Input;

interface QuestDesignerProps {
  worldDataPath: string | null;
}

// Custom node types
const nodeTypes: NodeTypes = {
  quest: QuestNodeComponent,
};

export function QuestDesigner({ worldDataPath }: QuestDesignerProps) {
  const {
    quests,
    loading,
    createQuest,
    updateQuest,
    deleteQuest,
    updateQuestPosition,
    addPrerequisite,
    removePrerequisite,
  } = useQuests({ worldDataPath, enabled: true });

  console.log('[QuestDesigner] worldDataPath:', worldDataPath, 'quests:', quests.length, 'loading:', loading);
  console.log('[QuestDesigner] quest data:', quests);

  const [selectedQuestId, setSelectedQuestId] = useState<string | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createForm] = Form.useForm();

  const selectedQuest = useMemo(
    () => quests.find((q) => q.id === selectedQuestId) || null,
    [quests, selectedQuestId]
  );

  // Convert quests to React Flow nodes
  const initialNodes: Node[] = useMemo(
    () => {
      const nodes = quests.map((quest) => ({
        id: quest.id,
        type: 'quest',
        position: quest.position || { x: 0, y: 0 },
        data: {
          label: quest.name,
          quest_id: quest.id,
          description: quest.description,
          objectives: quest.objectives,
          rewards: quest.rewards,
          category: quest.category,
        },
        selected: quest.id === selectedQuestId,
      }));
      console.log('[QuestDesigner] initialNodes:', nodes);
      return nodes;
    },
    [quests, selectedQuestId]
  );

  // Create edges from prerequisites
  const initialEdges: Edge[] = useMemo(() => {
    const edges: Edge[] = [];
    quests.forEach((quest) => {
      quest.prerequisites?.forEach((prereqId) => {
        // Only create edge if prerequisite quest exists
        if (quests.some((q) => q.id === prereqId)) {
          edges.push({
            id: `${prereqId}->${quest.id}`,
            source: prereqId,
            target: quest.id,
            type: 'smoothstep',
            animated: true,
            markerEnd: {
              type: MarkerType.ArrowClosed,
            },
            style: { stroke: '#1890ff' },
          });
        }
      });
    });
    return edges;
  }, [quests]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  console.log('[QuestDesigner] React Flow nodes state:', nodes);

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
        addPrerequisite(params.target, params.source);
        setEdges((eds) =>
          addEdge(
            {
              ...params,
              type: 'smoothstep',
              animated: true,
              markerEnd: { type: MarkerType.ArrowClosed },
              style: { stroke: '#1890ff' },
            },
            eds
          )
        );
      }
    },
    [addPrerequisite, setEdges]
  );

  // Handle edge deletion
  const onEdgesDelete = useCallback(
    (deletedEdges: Edge[]) => {
      deletedEdges.forEach((edge) => {
        if (edge.source && edge.target) {
          removePrerequisite(edge.target, edge.source);
        }
      });
    },
    [removePrerequisite]
  );

  // Handle node click
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    console.log('[QuestDesigner] Node clicked:', node.id);
    setSelectedQuestId(node.id);
  }, []);

  // Handle node drag end
  const onNodeDragStop = useCallback(
    (_: React.MouseEvent, node: Node) => {
      updateQuestPosition(node.id, node.position);
    },
    [updateQuestPosition]
  );

  // Handle pane click (deselect)
  const onPaneClick = useCallback(() => {
    setSelectedQuestId(null);
  }, []);

  // Handle create quest
  const handleCreate = useCallback(async () => {
    try {
      const values = createForm.getFieldsValue();
      const success = await createQuest({
        id: values.id,
        name: values.name || values.id,
        description: values.description || '',
        category: values.category || 'side',
        objectives: [],
      });

      if (success) {
        setCreateModalOpen(false);
        createForm.resetFields();
        message.success(`Created quest: ${values.name || values.id}`);
      } else {
        message.error('Failed to create quest');
      }
    } catch (err) {
      console.error('Failed to create quest:', err);
      message.error('Failed to create quest');
    }
  }, [createForm, createQuest]);

  // Handle save quest
  const handleSaveQuest = useCallback(
    async (questId: string, updates: Partial<Quest>) => {
      const success = await updateQuest(questId, updates);
      if (success) {
        message.success('Quest saved');
      } else {
        message.error('Failed to save quest');
      }
      return success;
    },
    [updateQuest]
  );

  // Handle delete quest
  const handleDeleteQuest = useCallback(
    async (questId: string) => {
      Modal.confirm({
        title: 'Delete Quest',
        content: 'Are you sure you want to delete this quest? This cannot be undone.',
        okText: 'Delete',
        okType: 'danger',
        onOk: async () => {
          const success = await deleteQuest(questId);
          if (success) {
            setSelectedQuestId(null);
            message.success('Quest deleted');
          } else {
            message.error('Failed to delete quest');
          }
        },
      });
    },
    [deleteQuest]
  );

  if (!worldDataPath) {
    return (
      <div className="quest-designer-empty">
        <Empty description="Open a world_data folder to design quests" />
      </div>
    );
  }

  return (
    <Layout className="quest-designer-layout">
      <Content className="quest-designer-content">
        <Spin spinning={loading} wrapperClassName="quest-designer-spin">
          <div className="quest-designer" style={{ height: '100%', width: '100%' }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onEdgesDelete={onEdgesDelete}
              onNodeClick={onNodeClick}
              onNodeDragStop={onNodeDragStop}
              onPaneClick={onPaneClick}
              nodeTypes={nodeTypes}
              fitView
              deleteKeyCode={['Backspace', 'Delete']}
            >
              <Controls />
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
              <Panel position="top-left">
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setCreateModalOpen(true)}
                >
                  New Quest
                </Button>
              </Panel>
            </ReactFlow>
          </div>
        </Spin>
      </Content>

      <Sider width={320} className="quest-designer-sider">
        <QuestPropertiesPanel
          quest={selectedQuest}
          allQuests={quests}
          onSave={handleSaveQuest}
          onDelete={handleDeleteQuest}
        />
      </Sider>

      {/* Create Quest Modal */}
      <Modal
        title="Create New Quest"
        open={createModalOpen}
        onOk={handleCreate}
        onCancel={() => {
          setCreateModalOpen(false);
          createForm.resetFields();
        }}
        okText="Create"
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="id"
            label="Quest ID"
            rules={[
              { required: true, message: 'Please enter an ID' },
              { pattern: /^[a-z0-9_]+$/, message: 'ID must be lowercase letters, numbers, and underscores' },
            ]}
          >
            <Input placeholder="e.g., goblin_threat, wisp_investigation" />
          </Form.Item>
          <Form.Item name="name" label="Quest Name">
            <Input placeholder="e.g., The Goblin Menace" />
          </Form.Item>
          <Form.Item name="category" label="Category" initialValue="side">
            <Select>
              <Select.Option value="main">Main Quest</Select.Option>
              <Select.Option value="side">Side Quest</Select.Option>
              <Select.Option value="daily">Daily</Select.Option>
              <Select.Option value="repeatable">Repeatable</Select.Option>
              <Select.Option value="epic">Epic</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="description" label="Description">
            <TextArea rows={3} placeholder="Quest description..." />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
}
