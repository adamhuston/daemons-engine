/**
 * RoomPropertiesPanel Component
 *
 * Sidebar panel for viewing and editing room properties.
 * Displays when a room is selected in the Room Builder.
 */

import { useCallback, useEffect, useState } from 'react';
import { Form, Input, Select, Button, Divider, List, Tag, Empty, Spin, Typography } from 'antd';
import { SaveOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import type { RoomNode } from '../../../shared/types';

const { TextArea } = Input;
const { Text, Title } = Typography;

// Room type options (matching schema)
const ROOM_TYPE_OPTIONS = [
  { value: 'ethereal', label: 'Ethereal', color: '#9254de' },
  { value: 'forest', label: 'Forest', color: '#52c41a' },
  { value: 'cave', label: 'Cave', color: '#8c8c8c' },
  { value: 'urban', label: 'Urban', color: '#faad14' },
  { value: 'chamber', label: 'Chamber', color: '#1890ff' },
  { value: 'corridor', label: 'Corridor', color: '#595959' },
  { value: 'outdoor', label: 'Outdoor', color: '#73d13d' },
  { value: 'indoor', label: 'Indoor', color: '#d4b106' },
  { value: 'dungeon', label: 'Dungeon', color: '#722ed1' },
  { value: 'shop', label: 'Shop', color: '#fa8c16' },
  { value: 'inn', label: 'Inn', color: '#eb2f96' },
  { value: 'temple', label: 'Temple', color: '#13c2c2' },
  { value: 'water', label: 'Water', color: '#1890ff' },
];

// Lighting override options
const LIGHTING_OPTIONS = [
  { value: null, label: 'Default (from area)' },
  { value: 'pitch_black', label: 'Pitch Black' },
  { value: 'dim', label: 'Dim' },
  { value: 'normal', label: 'Normal' },
  { value: 'bright', label: 'Bright' },
  { value: 'prismatic', label: 'Prismatic' },
];

interface RoomFormData {
  name: string;
  description: string;
  room_type: string;
  area_id: string;
  z_level: number;
  lighting_override: string | null;
  on_enter_effect: string;
  on_exit_effect: string;
}

interface RoomPropertiesPanelProps {
  selectedRoom: RoomNode | null;
  onSave: (roomId: string, updates: Partial<RoomFormData>) => Promise<void>;
  onDelete: (roomId: string) => Promise<void>;
  onExitClick: (exitDirection: string, targetRoomId: string) => void;
  onAddExit: (roomId: string, direction: string, targetRoomId: string) => void;
  onRemoveExit: (roomId: string, direction: string) => void;
  isLoading?: boolean;
  isDirty?: boolean;
}

export function RoomPropertiesPanel({
  selectedRoom,
  onSave,
  onDelete,
  onExitClick,
  onAddExit,
  onRemoveExit,
  isLoading = false,
  isDirty = false,
}: RoomPropertiesPanelProps) {
  const [form] = Form.useForm<RoomFormData>();
  const [saving, setSaving] = useState(false);

  // Update form when selected room changes
  useEffect(() => {
    if (selectedRoom) {
      form.setFieldsValue({
        name: selectedRoom.name,
        description: selectedRoom.description || '',
        room_type: selectedRoom.room_type || 'ethereal',
        area_id: selectedRoom.area_id || '',
        z_level: selectedRoom.z_level,
        lighting_override: null,
        on_enter_effect: '',
        on_exit_effect: '',
      });
    }
  }, [selectedRoom, form]);

  // Handle form save
  const handleSave = useCallback(async () => {
    if (!selectedRoom) return;
    
    try {
      setSaving(true);
      const values = form.getFieldsValue();
      await onSave(selectedRoom.id, values);
    } finally {
      setSaving(false);
    }
  }, [selectedRoom, form, onSave]);

  // Handle delete
  const handleDelete = useCallback(async () => {
    if (!selectedRoom) return;
    await onDelete(selectedRoom.id);
  }, [selectedRoom, onDelete]);

  // If no room is selected, show empty state
  if (!selectedRoom) {
    return (
      <div className="room-properties-panel empty">
        <Empty
          description="Select a room to view properties"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </div>
    );
  }

  // Get exits as an array for display
  const exits = Object.entries(selectedRoom.exits || {}).map(([direction, target]) => ({
    direction,
    target,
  }));

  return (
    <div className="room-properties-panel">
      {isLoading ? (
        <div className="loading-overlay">
          <Spin />
        </div>
      ) : (
        <>
          <div className="panel-header">
            <Title level={5} style={{ margin: 0 }}>
              {selectedRoom.name}
            </Title>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {selectedRoom.id}
            </Text>
          </div>

          <Divider style={{ margin: '12px 0' }} />

          <Form
            form={form}
            layout="vertical"
            size="small"
            className="room-form"
          >
            <Form.Item label="Name" name="name" rules={[{ required: true }]}>
              <Input placeholder="Room name" />
            </Form.Item>

            <Form.Item label="Description" name="description">
              <TextArea
                rows={4}
                placeholder="Room description (what the player sees)"
              />
            </Form.Item>

            <Form.Item label="Room Type" name="room_type">
              <Select options={ROOM_TYPE_OPTIONS} />
            </Form.Item>

            <Form.Item label="Area" name="area_id">
              <Input placeholder="area_id" disabled />
            </Form.Item>

            <Form.Item label="Z-Level" name="z_level">
              <Input type="number" disabled />
            </Form.Item>

            <Form.Item label="Lighting Override" name="lighting_override">
              <Select
                options={LIGHTING_OPTIONS}
                allowClear
                placeholder="Use area default"
              />
            </Form.Item>

            <Form.Item label="On Enter Effect" name="on_enter_effect">
              <Input placeholder="Message when entering" />
            </Form.Item>

            <Form.Item label="On Exit Effect" name="on_exit_effect">
              <Input placeholder="Message when leaving" />
            </Form.Item>
          </Form>

          <Divider style={{ margin: '12px 0' }}>Exits</Divider>

          {exits.length > 0 ? (
            <List
              size="small"
              dataSource={exits}
              renderItem={(exit) => (
                <List.Item
                  className="exit-item"
                  actions={[
                    <Button
                      key="delete"
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => onRemoveExit(selectedRoom.id, exit.direction)}
                    />,
                  ]}
                >
                  <div
                    className="exit-info"
                    onClick={() => onExitClick(exit.direction, exit.target)}
                    style={{ cursor: 'pointer' }}
                  >
                    <Tag color={exit.direction === 'up' || exit.direction === 'down' ? 'gold' : 'green'}>
                      {exit.direction}
                    </Tag>
                    <Text ellipsis style={{ maxWidth: 120 }}>
                      → {exit.target}
                    </Text>
                  </div>
                </List.Item>
              )}
            />
          ) : (
            <Empty
              description="No exits"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}

          <Divider style={{ margin: '12px 0' }} />

          <div className="panel-actions">
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
              onClick={handleDelete}
              style={{ marginTop: 8 }}
              block
            >
              Delete Room
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
