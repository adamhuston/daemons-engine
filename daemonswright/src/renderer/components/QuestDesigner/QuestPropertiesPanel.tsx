/**
 * QuestPropertiesPanel Component
 *
 * Sidebar panel for editing quest details.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  Form,
  Input,
  Select,
  Button,
  Divider,
  InputNumber,
  Empty,
  Card,
  List,
  Tag,
  Space,
  Popconfirm,
} from 'antd';
import {
  SaveOutlined,
  DeleteOutlined,
  PlusOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import type { Quest, QuestObjective } from '../../hooks/useQuests';

const { TextArea } = Input;

interface QuestPropertiesPanelProps {
  quest: Quest | null;
  allQuests: Quest[];
  onSave: (questId: string, updates: Partial<Quest>) => Promise<boolean>;
  onDelete: (questId: string) => void;
}

// Objective type options
const OBJECTIVE_TYPES = [
  { value: 'kill', label: 'Kill', icon: '⚔️' },
  { value: 'collect', label: 'Collect', icon: '📦' },
  { value: 'visit', label: 'Visit Location', icon: '📍' },
  { value: 'talk', label: 'Talk to NPC', icon: '💬' },
  { value: 'deliver', label: 'Deliver Item', icon: '📬' },
  { value: 'interact', label: 'Interact', icon: '🔧' },
  { value: 'escort', label: 'Escort', icon: '🚶' },
  { value: 'survive', label: 'Survive', icon: '⏱️' },
];

export function QuestPropertiesPanel({
  quest,
  allQuests,
  onSave,
  onDelete,
}: QuestPropertiesPanelProps) {
  const [form] = Form.useForm();
  const [isDirty, setIsDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [objectives, setObjectives] = useState<QuestObjective[]>([]);

  // Update form when quest changes
  useEffect(() => {
    if (quest) {
      form.setFieldsValue({
        name: quest.name,
        description: quest.description,
        category: quest.category,
        level_requirement: quest.level_requirement,
        giver_npc_template: quest.giver_npc_template,
        turn_in_npc_template: quest.turn_in_npc_template,
        prerequisites: quest.prerequisites || [],
      });
      setObjectives(quest.objectives || []);
      setIsDirty(false);
    }
  }, [quest, form]);

  // Handle form value changes
  const handleValuesChange = useCallback(() => {
    setIsDirty(true);
  }, []);

  // Handle save
  const handleSave = useCallback(async () => {
    if (!quest) return;

    setSaving(true);
    try {
      const values = form.getFieldsValue();
      await onSave(quest.id, {
        ...values,
        objectives,
      });
      setIsDirty(false);
    } finally {
      setSaving(false);
    }
  }, [quest, form, objectives, onSave]);

  // Add new objective
  const handleAddObjective = useCallback(() => {
    const newObjective: QuestObjective = {
      id: `obj_${Date.now()}`,
      type: 'kill',
      description: 'New objective',
      required_count: 1,
    };
    setObjectives((prev) => [...prev, newObjective]);
    setIsDirty(true);
  }, []);

  // Update objective
  const handleUpdateObjective = useCallback((index: number, updates: Partial<QuestObjective>) => {
    setObjectives((prev) =>
      prev.map((obj, i) => (i === index ? { ...obj, ...updates } : obj))
    );
    setIsDirty(true);
  }, []);

  // Remove objective
  const handleRemoveObjective = useCallback((index: number) => {
    setObjectives((prev) => prev.filter((_, i) => i !== index));
    setIsDirty(true);
  }, []);

  if (!quest) {
    return (
      <div className="quest-properties-empty">
        <Empty
          description="Select a quest to edit its properties"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </div>
    );
  }

  return (
    <div className="quest-properties-panel">
      <div className="quest-properties-header">
        <Space>
          <TrophyOutlined style={{ fontSize: 18, color: '#faad14' }} />
          <span className="quest-title">{quest.name}</span>
        </Space>
        <Tag color="blue">{quest.id}</Tag>
      </div>

      <Form
        form={form}
        layout="vertical"
        size="small"
        onValuesChange={handleValuesChange}
        className="quest-form"
      >
        <Form.Item label="Name" name="name" rules={[{ required: true }]}>
          <Input placeholder="Quest name" />
        </Form.Item>

        <Form.Item label="Description" name="description">
          <TextArea rows={3} placeholder="Quest description" />
        </Form.Item>

        <Form.Item label="Category" name="category">
          <Select>
            <Select.Option value="main">Main Quest</Select.Option>
            <Select.Option value="side">Side Quest</Select.Option>
            <Select.Option value="daily">Daily</Select.Option>
            <Select.Option value="repeatable">Repeatable</Select.Option>
            <Select.Option value="epic">Epic</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item label="Level Requirement" name="level_requirement">
          <InputNumber min={1} max={100} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item label="Quest Giver NPC" name="giver_npc_template">
          <Input placeholder="NPC template ID" />
        </Form.Item>

        <Form.Item label="Turn-in NPC" name="turn_in_npc_template">
          <Input placeholder="NPC template ID (optional)" />
        </Form.Item>

        <Form.Item label="Prerequisites" name="prerequisites">
          <Select
            mode="multiple"
            placeholder="Select prerequisite quests"
            options={allQuests
              .filter((q) => q.id !== quest.id)
              .map((q) => ({ label: q.name, value: q.id }))}
          />
        </Form.Item>
      </Form>

      <Divider orientation="left" style={{ margin: '12px 0' }}>
        Objectives ({objectives.length})
      </Divider>

      <div className="quest-objectives">
        <List
          size="small"
          dataSource={objectives}
          renderItem={(obj, index) => (
            <Card size="small" className="objective-card" style={{ marginBottom: 8 }}>
              <div className="objective-header">
                <Select
                  value={obj.type}
                  size="small"
                  style={{ width: 120 }}
                  onChange={(type) => handleUpdateObjective(index, { type: type as QuestObjective['type'] })}
                  options={OBJECTIVE_TYPES}
                />
                <Popconfirm
                  title="Remove this objective?"
                  onConfirm={() => handleRemoveObjective(index)}
                >
                  <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </div>
              <Input
                size="small"
                value={obj.description}
                placeholder="Objective description"
                onChange={(e) => handleUpdateObjective(index, { description: e.target.value })}
                style={{ marginTop: 8 }}
              />
              <Space style={{ marginTop: 8, width: '100%' }}>
                <Input
                  size="small"
                  value={obj.target_template_id}
                  placeholder="Target ID"
                  onChange={(e) => handleUpdateObjective(index, { target_template_id: e.target.value })}
                  style={{ flex: 1 }}
                />
                <InputNumber
                  size="small"
                  value={obj.required_count}
                  min={1}
                  placeholder="Count"
                  onChange={(val) => handleUpdateObjective(index, { required_count: val || 1 })}
                  style={{ width: 70 }}
                />
              </Space>
            </Card>
          )}
          locale={{ emptyText: 'No objectives' }}
        />
        <Button
          type="dashed"
          icon={<PlusOutlined />}
          onClick={handleAddObjective}
          block
          style={{ marginTop: 8 }}
        >
          Add Objective
        </Button>
      </div>

      <Divider style={{ margin: '16px 0' }} />

      <div className="quest-actions">
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={handleSave}
          loading={saving}
          disabled={!isDirty}
          block
        >
          Save Changes
        </Button>
        <Button
          danger
          icon={<DeleteOutlined />}
          onClick={() => onDelete(quest.id)}
          style={{ marginTop: 8 }}
          block
        >
          Delete Quest
        </Button>
      </div>
    </div>
  );
}
