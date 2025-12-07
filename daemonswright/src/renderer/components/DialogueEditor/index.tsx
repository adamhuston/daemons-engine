/**
 * DialogueEditor Component
 *
 * Visual dialogue tree editor using React Flow.
 * Shows conversation branches and responses.
 * Includes a tree list and properties panel.
 */

import { useCallback, useEffect, useState } from 'react';
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
  useReactFlow,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Layout, Button, Empty, Spin, Modal, Form, Input, List, Card, message } from 'antd';
import { PlusOutlined, MessageOutlined } from '@ant-design/icons';
import { DialogueNodeComponent } from './DialogueNode';
import { DialoguePropertiesPanel } from './DialoguePropertiesPanel';
import { useDialogues } from '../../hooks/useDialogues';
import type { DialogueNode } from '../../hooks/useDialogues';
import './DialogueEditor.css';

const { Content, Sider } = Layout;

interface DialogueEditorProps {
  worldDataPath: string | null;
}

// Custom node types
const nodeTypes: NodeTypes = {
  dialogue: DialogueNodeComponent,
};

export function DialogueEditor({ worldDataPath }: DialogueEditorProps) {
  const {
    dialogueTrees,
    selectedTree,
    loading,
    selectTree,
    createDialogueTree,
    updateNodePosition,
    updateNode,
    addNode,
    deleteNode,
  } = useDialogues({ worldDataPath });

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Selected node for properties panel
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Create dialogue tree modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createForm] = Form.useForm();

  // Add node modal
  const [addNodeModalOpen, setAddNodeModalOpen] = useState(false);
  const [addNodeForm] = Form.useForm();

  // Convert dialogue tree nodes to React Flow nodes
  useEffect(() => {
    if (!selectedTree) {
      setNodes([]);
      setEdges([]);
      return;
    }

    // nodes is a Record<string, DialogueNode> - convert to array
    const nodeEntries = Object.entries(selectedTree.nodes || {});
    const layout = selectedTree.layout || {};
    
    // Convert to React Flow nodes
    const flowNodes: Node[] = nodeEntries.map(([nodeId, node], index) => {
      const position = layout[nodeId] || { 
        x: 100 + (index % 4) * 250, 
        y: 100 + Math.floor(index / 4) * 150 
      };
      
      return {
        id: nodeId,
        type: 'dialogue',
        position,
        data: {
          text: node.text || '',
          nodeType: 'npc', // Default type
          options: node.options,
        },
      };
    });

    // Convert options to edges (connections between nodes)
    const flowEdges: Edge[] = [];
    nodeEntries.forEach(([nodeId, node]) => {
      if (node.options) {
        node.options.forEach((option, optionIndex) => {
          if (option.next_node) {
            flowEdges.push({
              id: `${nodeId}-${optionIndex}-${option.next_node}`,
              source: nodeId,
              target: option.next_node,
              label: option.text.substring(0, 20) + (option.text.length > 20 ? '...' : ''),
              markerEnd: { type: MarkerType.ArrowClosed },
              style: { stroke: '#888' },
            });
          }
        });
      }
    });

    setNodes(flowNodes);
    setEdges(flowEdges);
    // Clear selection when tree changes
    setSelectedNodeId(null);
  }, [selectedTree, setNodes, setEdges]);

  // Get selected node data
  const selectedNode = selectedNodeId && selectedTree?.nodes
    ? { id: selectedNodeId, ...selectedTree.nodes[selectedNodeId] }
    : null;

  // Get all node IDs for linking
  const allNodeIds = selectedTree?.nodes ? Object.keys(selectedTree.nodes) : [];

  // Handle node click
  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  // Handle pane click (deselect)
  const handlePaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  // Handle node position change
  const handleNodeDragStop = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      if (selectedTree) {
        updateNodePosition(node.id, node.position);
      }
    },
    [selectedTree, updateNodePosition]
  );

  // Handle new connection
  const handleConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            markerEnd: { type: MarkerType.ArrowClosed },
            style: { stroke: '#888' },
          },
          eds
        )
      );

      // TODO: Update the dialogue tree with new connection
    },
    [setEdges]
  );

  // Handle tree selection
  const handleTreeSelect = useCallback(
    (npcTemplateId: string) => {
      selectTree(npcTemplateId);
      setSelectedNodeId(null);
    },
    [selectTree]
  );

  // Handle save node
  const handleSaveNode = useCallback(
    async (nodeId: string, updates: Partial<DialogueNode>) => {
      const success = await updateNode(nodeId, updates);
      if (success) {
        message.success('Node saved');
      } else {
        message.error('Failed to save node');
      }
      return success;
    },
    [updateNode]
  );

  // Handle delete node
  const handleDeleteNode = useCallback(
    async (nodeId: string) => {
      const success = await deleteNode(nodeId);
      if (success) {
        setSelectedNodeId(null);
        message.success('Node deleted');
      } else {
        message.error('Failed to delete node');
      }
    },
    [deleteNode]
  );

  // Handle add node
  const handleAddNode = useCallback(async () => {
    try {
      const values = await addNodeForm.validateFields();
      const success = await addNode(values.nodeId, {
        text: 'New dialogue text...',
        options: [],
      });

      if (success) {
        message.success('Node added');
        setAddNodeModalOpen(false);
        addNodeForm.resetFields();
        setSelectedNodeId(values.nodeId);
      }
    } catch {
      // Validation failed
    }
  }, [addNode, addNodeForm]);

  // Handle navigate to node (from properties panel link)
  const handleNavigateToNode = useCallback((nodeId: string) => {
    // Select the target node
    setSelectedNodeId(nodeId);
    
    // Find the node in the flow and highlight it
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        selected: n.id === nodeId,
      }))
    );
  }, [setNodes]);

  // Handle create tree
  const handleCreateTree = useCallback(async () => {
    try {
      const values = await createForm.validateFields();
      const success = await createDialogueTree({
        npc_template_id: values.npc_template_id,
        entry_node: 'greet',
        nodes: {
          greet: {
            text: 'Hello, traveler.',
            options: [
              { text: 'Goodbye', next_node: null }
            ],
          },
        },
      });

      if (success) {
        message.success('Dialogue tree created');
        setCreateModalOpen(false);
        createForm.resetFields();
      }
    } catch (err) {
      // Validation failed
    }
  }, [createForm, createDialogueTree]);

  // Get node count from the nodes Record
  const getNodeCount = (nodes: Record<string, unknown> | undefined): number => {
    if (!nodes) return 0;
    return Object.keys(nodes).length;
  };

  return (
    <Layout className="dialogue-editor">
      {/* Left sidebar - Tree list */}
      <Sider width={250} className="dialogue-tree-list">
        <div className="tree-list-header">
          <h3>Dialogue Trees</h3>
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => setCreateModalOpen(true)}
          >
            New
          </Button>
        </div>

        {loading ? (
          <div className="loading-container">
            <Spin />
          </div>
        ) : dialogueTrees.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No dialogue trees"
          />
        ) : (
          <List
            dataSource={dialogueTrees}
            renderItem={(tree) => (
              <List.Item
                key={tree.npc_template_id}
                className={`tree-list-item ${selectedTree?.npc_template_id === tree.npc_template_id ? 'selected' : ''}`}
                onClick={() => handleTreeSelect(tree.npc_template_id)}
              >
                <Card size="small" className="tree-card">
                  <div className="tree-card-content">
                    <MessageOutlined className="tree-icon" />
                    <div className="tree-info">
                      <div className="tree-name">{tree.npc_template_id}</div>
                      <div className="tree-node-count">
                        {getNodeCount(tree.nodes)} nodes
                      </div>
                    </div>
                  </div>
                </Card>
              </List.Item>
            )}
          />
        )}
      </Sider>

      {/* Main canvas */}
      <Content className="dialogue-canvas">
        {!selectedTree ? (
          <Empty
            description="Select a dialogue tree or create a new one"
            style={{ marginTop: 100 }}
          />
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={handleConnect}
            onNodeDragStop={handleNodeDragStop}
            onNodeClick={handleNodeClick}
            onPaneClick={handlePaneClick}
            nodeTypes={nodeTypes}
            fitView
            snapToGrid
            snapGrid={[20, 20]}
          >
            <Controls />
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
          </ReactFlow>
        )}
      </Content>

      {/* Right sidebar - Properties panel */}
      <Sider width={320} className="dialogue-properties-sider">
        <DialoguePropertiesPanel
          node={selectedNode}
          allNodeIds={allNodeIds}
          onSave={handleSaveNode}
          onDelete={handleDeleteNode}
          onAddNode={() => setAddNodeModalOpen(true)}
          onNavigateToNode={handleNavigateToNode}
        />
      </Sider>

      {/* Create tree modal */}
      <Modal
        title="Create Dialogue Tree"
        open={createModalOpen}
        onOk={handleCreateTree}
        onCancel={() => setCreateModalOpen(false)}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="npc_template_id"
            label="NPC Template ID"
            rules={[
              { required: true, message: 'NPC Template ID is required' },
              { pattern: /^[a-z0-9_]+$/, message: 'ID must be lowercase with underscores' },
            ]}
          >
            <Input placeholder="e.g., merchant_bob" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Add node modal */}
      <Modal
        title="Add Dialogue Node"
        open={addNodeModalOpen}
        onOk={handleAddNode}
        onCancel={() => setAddNodeModalOpen(false)}
      >
        <Form form={addNodeForm} layout="vertical">
          <Form.Item
            name="nodeId"
            label="Node ID"
            rules={[
              { required: true, message: 'Node ID is required' },
              { pattern: /^[a-z0-9_]+$/, message: 'ID must be lowercase with underscores' },
              {
                validator: (_, value) =>
                  allNodeIds.includes(value)
                    ? Promise.reject('Node ID already exists')
                    : Promise.resolve(),
              },
            ]}
          >
            <Input placeholder="e.g., ask_about_quest" />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
}
