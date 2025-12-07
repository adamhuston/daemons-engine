/**
 * DialoguePropertiesPanel Component
 *
 * Properties panel for editing the selected dialogue node.
 * Allows editing node text and response options.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Empty,
  Form,
  Input,
  Space,
  Divider,
  Collapse,
  Select,
  InputNumber,
  Popconfirm,
} from 'antd';
import {
  DeleteOutlined,
  PlusOutlined,
  SaveOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons';
import type { DialogueNode, DialogueOption } from '../../hooks/useDialogues';

const { TextArea } = Input;
const { Panel } = Collapse;

interface DialoguePropertiesPanelProps {
  node: (Omit<DialogueNode, 'id'> & { id: string }) | null;
  allNodeIds: string[];
  onSave: (nodeId: string, updates: Partial<DialogueNode>) => Promise<boolean>;
  onDelete: (nodeId: string) => void;
  onAddNode: () => void;
  onNavigateToNode?: (nodeId: string) => void;
}

export function DialoguePropertiesPanel({
  node,
  allNodeIds,
  onSave,
  onDelete,
  onAddNode,
  onNavigateToNode,
}: DialoguePropertiesPanelProps) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [options, setOptions] = useState<DialogueOption[]>([]);

  // Reset form when node changes
  useEffect(() => {
    if (node) {
      form.setFieldsValue({
        text: node.text || '',
      });
      setOptions(node.options || []);
    } else {
      form.resetFields();
      setOptions([]);
    }
  }, [node, form]);

  // Handle save
  const handleSave = useCallback(async () => {
    if (!node) return;

    try {
      setSaving(true);
      const values = form.getFieldsValue();
      
      await onSave(node.id, {
        text: values.text,
        options: options,
      });
    } finally {
      setSaving(false);
    }
  }, [node, form, options, onSave]);

  // Handle option text change
  const handleOptionTextChange = useCallback((index: number, text: string) => {
    setOptions((prev) => {
      const newOptions = [...prev];
      newOptions[index] = { ...newOptions[index], text };
      return newOptions;
    });
  }, []);

  // Handle option next_node change
  const handleOptionNextChange = useCallback((index: number, nextNode: string | null) => {
    setOptions((prev) => {
      const newOptions = [...prev];
      newOptions[index] = { ...newOptions[index], next_node: nextNode };
      return newOptions;
    });
  }, []);

  // Add new option
  const handleAddOption = useCallback(() => {
    setOptions((prev) => [
      ...prev,
      { text: 'New response', next_node: null },
    ]);
  }, []);

  // Remove option
  const handleRemoveOption = useCallback((index: number) => {
    setOptions((prev) => prev.filter((_, i) => i !== index));
  }, []);

  if (!node) {
    return (
      <div className="dialogue-properties-empty">
        <Empty
          description="Select a node to edit"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button type="primary" icon={<PlusOutlined />} onClick={onAddNode}>
            Add Node
          </Button>
        </Empty>
      </div>
    );
  }

  return (
    <div className="dialogue-properties-panel">
      <div className="dialogue-properties-header">
        <span className="node-id">{node.id}</span>
        <Space>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            onClick={handleSave}
          >
            Save
          </Button>
        </Space>
      </div>

      <Divider style={{ margin: '12px 0' }} />

      <Form form={form} layout="vertical" className="dialogue-form">
        <Form.Item name="text" label="NPC Text">
          <TextArea
            rows={4}
            placeholder="What the NPC says..."
            autoSize={{ minRows: 3, maxRows: 8 }}
          />
        </Form.Item>
      </Form>

      <Divider orientation="left" style={{ margin: '12px 0' }}>
        Response Options ({options.length})
      </Divider>

      <div className="dialogue-options">
        <Collapse accordion>
          {options.map((option, index) => (
            <Panel
              key={index}
              header={
                <div className="option-header">
                  <span className="option-text">
                    {option.text.substring(0, 30)}
                    {option.text.length > 30 ? '...' : ''}
                  </span>
                  {option.next_node && (
                    <span
                      className="option-next option-next-link"
                      onClick={(e) => {
                        e.stopPropagation();
                        onNavigateToNode?.(option.next_node!);
                      }}
                      title={`Go to ${option.next_node}`}
                    >
                      <ArrowRightOutlined /> {option.next_node}
                    </span>
                  )}
                </div>
              }
              extra={
                <Popconfirm
                  title="Delete this option?"
                  onConfirm={(e) => {
                    e?.stopPropagation();
                    handleRemoveOption(index);
                  }}
                  onCancel={(e) => e?.stopPropagation()}
                >
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={(e) => e.stopPropagation()}
                  />
                </Popconfirm>
              }
            >
              <Form layout="vertical">
                <Form.Item label="Response Text">
                  <TextArea
                    value={option.text}
                    onChange={(e) => handleOptionTextChange(index, e.target.value)}
                    rows={2}
                    placeholder="Player's response..."
                  />
                </Form.Item>
                <Form.Item label="Next Node">
                  <Select
                    value={option.next_node}
                    onChange={(value) => handleOptionNextChange(index, value)}
                    allowClear
                    placeholder="End conversation"
                  >
                    {allNodeIds
                      .filter((id) => id !== node.id)
                      .map((id) => (
                        <Select.Option key={id} value={id}>
                          {id}
                        </Select.Option>
                      ))}
                  </Select>
                </Form.Item>
                
                {/* Advanced options (collapsed by default) */}
                {(option.accept_quest || option.turn_in_quest || option.grant_experience) && (
                  <>
                    <Divider style={{ margin: '8px 0' }} />
                    {option.accept_quest && (
                      <Form.Item label="Accept Quest">
                        <Input value={option.accept_quest} disabled />
                      </Form.Item>
                    )}
                    {option.turn_in_quest && (
                      <Form.Item label="Turn In Quest">
                        <Input value={option.turn_in_quest} disabled />
                      </Form.Item>
                    )}
                    {option.grant_experience && (
                      <Form.Item label="Grant XP">
                        <InputNumber value={option.grant_experience} disabled />
                      </Form.Item>
                    )}
                  </>
                )}
              </Form>
            </Panel>
          ))}
        </Collapse>

        <Button
          type="dashed"
          icon={<PlusOutlined />}
          onClick={handleAddOption}
          style={{ width: '100%', marginTop: 12 }}
        >
          Add Response Option
        </Button>
      </div>

      <Divider style={{ margin: '16px 0' }} />

      <div className="dialogue-actions">
        <Popconfirm
          title="Delete this node?"
          description="This will remove all connections to this node."
          onConfirm={() => onDelete(node.id)}
          okText="Delete"
          okType="danger"
        >
          <Button danger icon={<DeleteOutlined />} block>
            Delete Node
          </Button>
        </Popconfirm>
      </div>
    </div>
  );
}
