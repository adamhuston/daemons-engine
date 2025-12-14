/**
 * RoomPropertiesPanel Component
 *
 * Tabbed sidebar panel for viewing and editing room properties,
 * NPCs, items, and exits. Displays when a room is selected in the Room Builder.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  Form,
  Input,
  Select,
  Button,
  Divider,
  List,
  Tag,
  Empty,
  Spin,
  Typography,
  Tabs,
  Card,
  Badge,
  Modal,
  InputNumber,
  Space,
  Popconfirm,
  Switch,
  Tooltip,
} from 'antd';
import {
  SaveOutlined,
  DeleteOutlined,
  PlusOutlined,
  UserOutlined,
  InboxOutlined,
  CompassOutlined,
  EditOutlined,
  SearchOutlined,
  LockOutlined,
  UnlockOutlined,
} from '@ant-design/icons';
import type { RoomNode, NpcSpawn, ItemInstance, DoorState } from '../../../shared/types';
import { AddableSelect } from '../AddableSelect';

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

// Item location options
const ITEM_LOCATION_OPTIONS = [
  { value: 'ground', label: 'Ground' },
  { value: 'table', label: 'Table' },
  { value: 'shelf', label: 'Shelf' },
  { value: 'hidden', label: 'Hidden' },
  { value: 'container', label: 'In Container' },
];

// NPC behavior options
const NPC_BEHAVIOR_OPTIONS = [
  { value: 'stationary', label: 'Stationary' },
  { value: 'patrol', label: 'Patrol' },
  { value: 'wander', label: 'Wander' },
  { value: 'guard', label: 'Guard' },
  { value: 'merchant', label: 'Merchant' },
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

interface NpcTemplate {
  id: string;
  name: string;
  description?: string;
}

interface ItemTemplate {
  id: string;
  name: string;
  item_type?: string;
  description?: string;
}

interface RoomPropertiesPanelProps {
  selectedRoom: RoomNode | null;
  onSave: (roomId: string, updates: Partial<RoomFormData>) => Promise<void>;
  onDelete: (roomId: string) => Promise<void>;
  onExitClick: (exitDirection: string, targetRoomId: string) => void;
  onAddExit: (roomId: string, direction: string, targetRoomId: string) => void;
  onRemoveExit: (roomId: string, direction: string) => void;
  onUpdateDoor?: (roomId: string, direction: string, doorState: DoorState | null) => Promise<boolean>;
  isLoading?: boolean;
  isDirty?: boolean;
  onDirtyChange?: (isDirty: boolean) => void;
  roomTypeOptions?: string[];
  onAddRoomType?: (newType: string) => Promise<boolean>;
  // All rooms in the world for cross-area connections
  allRooms?: RoomNode[];
  // NPC management
  npcSpawns?: NpcSpawn[];
  npcTemplates?: NpcTemplate[];
  onAddNpcSpawn?: (roomId: string, spawn: Partial<NpcSpawn>) => Promise<boolean>;
  onUpdateNpcSpawn?: (spawnId: string, updates: Partial<NpcSpawn>) => Promise<boolean>;
  onRemoveNpcSpawn?: (spawnId: string) => Promise<boolean>;
  onEditNpcTemplate?: (templateId: string) => void;
  // Item management
  itemInstances?: ItemInstance[];
  itemTemplates?: ItemTemplate[];
  onAddItemInstance?: (roomId: string, instance: Partial<ItemInstance>) => Promise<boolean>;
  onUpdateItemInstance?: (instanceId: string, updates: Partial<ItemInstance>) => Promise<boolean>;
  onRemoveItemInstance?: (instanceId: string) => Promise<boolean>;
  onEditItemTemplate?: (templateId: string) => void;
}

export function RoomPropertiesPanel({
  selectedRoom,
  onSave,
  onDelete,
  onExitClick,
  onAddExit,
  onRemoveExit,
  onUpdateDoor,
  isLoading = false,
  isDirty = false,
  onDirtyChange,
  roomTypeOptions = [],
  onAddRoomType,
  allRooms = [],
  // NPC props
  npcSpawns = [],
  npcTemplates = [],
  onAddNpcSpawn,
  onUpdateNpcSpawn,
  onRemoveNpcSpawn,
  onEditNpcTemplate,
  // Item props
  itemInstances = [],
  itemTemplates = [],
  onAddItemInstance,
  onUpdateItemInstance,
  onRemoveItemInstance,
  onEditItemTemplate,
}: RoomPropertiesPanelProps) {
  const [form] = Form.useForm<RoomFormData>();
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('properties');
  
  // Modal states
  const [addNpcModalOpen, setAddNpcModalOpen] = useState(false);
  const [addItemModalOpen, setAddItemModalOpen] = useState(false);
  const [addExitModalOpen, setAddExitModalOpen] = useState(false);
  const [npcSearchQuery, setNpcSearchQuery] = useState('');
  const [itemSearchQuery, setItemSearchQuery] = useState('');
  const [exitSearchQuery, setExitSearchQuery] = useState('');
  const [selectedNpcTemplate, setSelectedNpcTemplate] = useState<string | null>(null);
  const [selectedItemTemplate, setSelectedItemTemplate] = useState<string | null>(null);
  const [selectedExitDirection, setSelectedExitDirection] = useState<string>('north');
  const [selectedTargetRoom, setSelectedTargetRoom] = useState<string | null>(null);
  
  // Door editing modal state
  const [doorModalOpen, setDoorModalOpen] = useState(false);
  const [editingDoorDirection, setEditingDoorDirection] = useState<string | null>(null);
  const [doorForm] = Form.useForm();
  
  // Add NPC/Item forms
  const [addNpcForm] = Form.useForm();
  const [addItemForm] = Form.useForm();

  // Filter NPCs/Items for this room
  const roomNpcSpawns = npcSpawns.filter((spawn) => spawn.room_id === selectedRoom?.id);
  const roomItemInstances = itemInstances.filter((inst) => inst.room_id === selectedRoom?.id);

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
      // Reset dirty state when switching rooms
      onDirtyChange?.(false);
    }
  }, [selectedRoom, form, onDirtyChange]);

  // Track form changes to update dirty state
  const handleValuesChange = useCallback(() => {
    onDirtyChange?.(true);
  }, [onDirtyChange]);

  // Handle form save
  const handleSave = useCallback(async () => {
    if (!selectedRoom) return;
    
    try {
      setSaving(true);
      const values = form.getFieldsValue();
      await onSave(selectedRoom.id, values);
      onDirtyChange?.(false);
    } finally {
      setSaving(false);
    }
  }, [selectedRoom, form, onSave, onDirtyChange]);

  // Handle delete
  const handleDelete = useCallback(async () => {
    if (!selectedRoom) return;
    await onDelete(selectedRoom.id);
  }, [selectedRoom, onDelete]);

  // Handle add NPC
  const handleAddNpc = useCallback(async () => {
    if (!selectedRoom || !selectedNpcTemplate || !onAddNpcSpawn) return;
    
    try {
      const values = addNpcForm.getFieldsValue();
      await onAddNpcSpawn(selectedRoom.id, {
        npc_template_id: selectedNpcTemplate,
        room_id: selectedRoom.id,
        quantity: values.quantity || 1,
        behavior: values.behavior || 'stationary',
        respawn_seconds: values.respawn_seconds || 0,
      });
      setAddNpcModalOpen(false);
      addNpcForm.resetFields();
      setSelectedNpcTemplate(null);
      setNpcSearchQuery('');
    } catch (error) {
      console.error('Failed to add NPC spawn:', error);
    }
  }, [selectedRoom, selectedNpcTemplate, onAddNpcSpawn, addNpcForm]);

  // Handle add Item
  const handleAddItem = useCallback(async () => {
    if (!selectedRoom || !selectedItemTemplate || !onAddItemInstance) return;
    
    try {
      const values = addItemForm.getFieldsValue();
      await onAddItemInstance(selectedRoom.id, {
        item_template_id: selectedItemTemplate,
        room_id: selectedRoom.id,
        quantity: values.quantity || 1,
        location: values.location || 'ground',
        container_id: values.container_id,
        hidden: values.hidden || false,
      });
      setAddItemModalOpen(false);
      addItemForm.resetFields();
      setSelectedItemTemplate(null);
      setItemSearchQuery('');
    } catch (error) {
      console.error('Failed to add item instance:', error);
    }
  }, [selectedRoom, selectedItemTemplate, onAddItemInstance, addItemForm]);

  // Handle opening door edit modal
  const handleEditDoor = useCallback((direction: string, currentDoor: DoorState | null) => {
    setEditingDoorDirection(direction);
    doorForm.setFieldsValue({
      has_door: currentDoor !== null,
      is_open: currentDoor?.is_open ?? true,
      is_locked: currentDoor?.is_locked ?? false,
      key_item_id: currentDoor?.key_item_id ?? '',
      door_name: currentDoor?.door_name ?? '',
    });
    setDoorModalOpen(true);
  }, [doorForm]);

  // Handle saving door changes
  const handleSaveDoor = useCallback(async () => {
    if (!selectedRoom || !editingDoorDirection || !onUpdateDoor) return;

    const values = doorForm.getFieldsValue();
    
    if (!values.has_door) {
      // Remove the door
      await onUpdateDoor(selectedRoom.id, editingDoorDirection, null);
    } else {
      // Create or update the door
      const doorState: DoorState = {
        is_open: values.is_open,
        is_locked: values.is_locked,
        key_item_id: values.key_item_id || undefined,
        door_name: values.door_name || undefined,
      };
      await onUpdateDoor(selectedRoom.id, editingDoorDirection, doorState);
    }

    setDoorModalOpen(false);
    setEditingDoorDirection(null);
    doorForm.resetFields();
  }, [selectedRoom, editingDoorDirection, onUpdateDoor, doorForm]);

  // Filter templates by search query
  const filteredNpcTemplates = npcTemplates.filter(
    (t) =>
      t.name.toLowerCase().includes(npcSearchQuery.toLowerCase()) ||
      t.id.toLowerCase().includes(npcSearchQuery.toLowerCase())
  );

  const filteredItemTemplates = itemTemplates.filter(
    (t) =>
      t.name.toLowerCase().includes(itemSearchQuery.toLowerCase()) ||
      t.id.toLowerCase().includes(itemSearchQuery.toLowerCase())
  );

  // Filter rooms for exit selection (exclude current room)
  // Group by area for easier navigation
  const filteredRooms = allRooms.filter(
    (r) =>
      r.id !== selectedRoom?.id && // Exclude current room
      (r.name.toLowerCase().includes(exitSearchQuery.toLowerCase()) ||
       r.id.toLowerCase().includes(exitSearchQuery.toLowerCase()) ||
       (r.area_id && r.area_id.toLowerCase().includes(exitSearchQuery.toLowerCase())))
  );

  // Group filtered rooms by area for display
  const roomsByArea = filteredRooms.reduce<Record<string, typeof filteredRooms>>((acc, room) => {
    const areaId = room.area_id || 'Unknown Area';
    if (!acc[areaId]) {
      acc[areaId] = [];
    }
    acc[areaId].push(room);
    return acc;
  }, {});

  // Available exit directions (excluding ones already used)
  const usedDirections = selectedRoom ? Object.keys(selectedRoom.exits || {}) : [];
  const availableDirections = ['north', 'south', 'east', 'west', 'up', 'down'].filter(
    (dir) => !usedDirections.includes(dir)
  );

  // Handle adding exit
  const handleAddExit = useCallback(() => {
    if (!selectedRoom || !selectedTargetRoom || !selectedExitDirection) return;
    
    onAddExit(selectedRoom.id, selectedExitDirection, selectedTargetRoom);
    setAddExitModalOpen(false);
    setSelectedTargetRoom(null);
    setExitSearchQuery('');
    // Reset to first available direction for next time
    const newAvailable = ['north', 'south', 'east', 'west', 'up', 'down'].filter(
      (dir) => !Object.keys(selectedRoom.exits || {}).includes(dir) && dir !== selectedExitDirection
    );
    setSelectedExitDirection(newAvailable[0] || 'north');
  }, [selectedRoom, selectedTargetRoom, selectedExitDirection, onAddExit]);

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

  // Get exits as an array for display, including door state
  const exits = Object.entries(selectedRoom.exits || {}).map(([direction, target]) => ({
    direction,
    target,
    door: selectedRoom.doors?.[direction] || null,
  }));

  // Count badges for tabs
  const npcCount = roomNpcSpawns.length;
  const itemCount = roomItemInstances.length;
  const exitCount = exits.length;

  return (
    <div className="room-properties-panel">
      {isLoading ? (
        <div className="loading-overlay">
          <Spin />
        </div>
      ) : (
        <>
          {/* Header */}
          <div className="panel-header">
            <Title level={5} style={{ margin: 0 }}>
              {selectedRoom.name}
            </Title>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {selectedRoom.id}
            </Text>
          </div>

          {/* Tabbed Interface */}
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            size="small"
            style={{ marginTop: 8 }}
            items={[
              {
                key: 'properties',
                label: (
                  <span>
                    <EditOutlined />
                    Properties
                  </span>
                ),
                children: (
                  <>
                    <Form
                      form={form}
                      layout="vertical"
                      size="small"
                      className="room-form"
                      onValuesChange={handleValuesChange}
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
                        {onAddRoomType ? (
                          <AddableSelect
                            value={form.getFieldValue('room_type')}
                            onChange={(val) => form.setFieldValue('room_type', val)}
                            options={roomTypeOptions.length > 0 ? roomTypeOptions : ROOM_TYPE_OPTIONS.map(o => o.value)}
                            onAddOption={onAddRoomType}
                            placeholder="Select room type"
                          />
                        ) : (
                          <Select options={ROOM_TYPE_OPTIONS} />
                        )}
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
                ),
              },
              {
                key: 'npcs',
                label: (
                  <Badge count={npcCount} size="small" offset={[8, 0]}>
                    <span>
                      <UserOutlined />
                      NPCs
                    </span>
                  </Badge>
                ),
                children: (
                  <div className="tab-content">
                    {roomNpcSpawns.length > 0 ? (
                      <List
                        size="small"
                        dataSource={roomNpcSpawns}
                        renderItem={(spawn) => {
                          const template = npcTemplates.find((t) => t.id === spawn.npc_template_id);
                          return (
                            <Card
                              size="small"
                              className="content-card"
                              style={{ marginBottom: 8 }}
                            >
                              <div className="content-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <Space>
                                  <UserOutlined />
                                  <Text strong>{template?.name || spawn.npc_template_id}</Text>
                                </Space>
                                <Popconfirm
                                  title="Remove NPC from room?"
                                  onConfirm={() => onRemoveNpcSpawn?.(spawn.spawn_id)}
                                  okText="Remove"
                                  cancelText="Cancel"
                                >
                                  <Button
                                    type="text"
                                    size="small"
                                    danger
                                    icon={<DeleteOutlined />}
                                  />
                                </Popconfirm>
                              </div>
                              <div className="content-card-details">
                                <Text type="secondary" style={{ fontSize: 11 }}>
                                  Template: {spawn.npc_template_id}
                                </Text>
                                <br />
                                <Text type="secondary" style={{ fontSize: 11 }}>
                                  Quantity: {spawn.quantity || 1}
                                  {spawn.behavior && ` • ${spawn.behavior}`}
                                </Text>
                              </div>
                              <div className="content-card-actions" style={{ marginTop: 8 }}>
                                <Button
                                  size="small"
                                  onClick={() => onEditNpcTemplate?.(spawn.npc_template_id)}
                                >
                                  Edit Template
                                </Button>
                              </div>
                            </Card>
                          );
                        }}
                      />
                    ) : (
                      <Empty
                        description="No NPCs in this room"
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        style={{ margin: '24px 0' }}
                      />
                    )}

                    <Divider style={{ margin: '12px 0' }} />

                    <Space direction="vertical" style={{ width: '100%' }}>
                      <Button
                        icon={<PlusOutlined />}
                        onClick={() => setAddNpcModalOpen(true)}
                        block
                      >
                        Add Existing NPC
                      </Button>
                      <Button
                        icon={<PlusOutlined />}
                        type="dashed"
                        onClick={() => {
                          // TODO: Open NPC template editor
                          console.log('Create new NPC template');
                        }}
                        block
                      >
                        Create New NPC
                      </Button>
                    </Space>
                  </div>
                ),
              },
              {
                key: 'items',
                label: (
                  <Badge count={itemCount} size="small" offset={[8, 0]}>
                    <span>
                      <InboxOutlined />
                      Items
                    </span>
                  </Badge>
                ),
                children: (
                  <div className="tab-content">
                    {roomItemInstances.length > 0 ? (
                      <List
                        size="small"
                        dataSource={roomItemInstances}
                        renderItem={(instance) => {
                          const template = itemTemplates.find((t) => t.id === instance.item_template_id);
                          return (
                            <Card
                              size="small"
                              className="content-card"
                              style={{ marginBottom: 8 }}
                            >
                              <div className="content-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <Space>
                                  <InboxOutlined />
                                  <Text strong>{template?.name || instance.item_template_id}</Text>
                                </Space>
                                <Popconfirm
                                  title="Remove item from room?"
                                  onConfirm={() => onRemoveItemInstance?.(instance.instance_id)}
                                  okText="Remove"
                                  cancelText="Cancel"
                                >
                                  <Button
                                    type="text"
                                    size="small"
                                    danger
                                    icon={<DeleteOutlined />}
                                  />
                                </Popconfirm>
                              </div>
                              <div className="content-card-details">
                                <Text type="secondary" style={{ fontSize: 11 }}>
                                  Template: {instance.item_template_id}
                                </Text>
                                <br />
                                <Text type="secondary" style={{ fontSize: 11 }}>
                                  Qty: {instance.quantity || 1}
                                  {instance.location && ` • ${instance.location}`}
                                  {instance.container_id && ` • in ${instance.container_id}`}
                                </Text>
                              </div>
                              <div className="content-card-actions" style={{ marginTop: 8 }}>
                                <Button
                                  size="small"
                                  onClick={() => onEditItemTemplate?.(instance.item_template_id)}
                                >
                                  Edit Template
                                </Button>
                              </div>
                            </Card>
                          );
                        }}
                      />
                    ) : (
                      <Empty
                        description="No items in this room"
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        style={{ margin: '24px 0' }}
                      />
                    )}

                    <Divider style={{ margin: '12px 0' }} />

                    <Space direction="vertical" style={{ width: '100%' }}>
                      <Button
                        icon={<PlusOutlined />}
                        onClick={() => setAddItemModalOpen(true)}
                        block
                      >
                        Add Existing Item
                      </Button>
                      <Button
                        icon={<PlusOutlined />}
                        type="dashed"
                        onClick={() => {
                          // TODO: Open item template editor
                          console.log('Create new item template');
                        }}
                        block
                      >
                        Create New Item
                      </Button>
                    </Space>
                  </div>
                ),
              },
              {
                key: 'exits',
                label: (
                  <Badge count={exitCount} size="small" offset={[8, 0]}>
                    <span>
                      <CompassOutlined />
                      Exits
                    </span>
                  </Badge>
                ),
                children: (
                  <div className="tab-content">
                    {exits.length > 0 ? (
                      <List
                        size="small"
                        dataSource={exits}
                        renderItem={(exit) => (
                          <List.Item
                            className="exit-item"
                            actions={[
                              <Tooltip key="door" title="Configure door">
                                <Button
                                  type="text"
                                  size="small"
                                  icon={exit.door ? (exit.door.is_locked ? <LockOutlined /> : <UnlockOutlined />) : <PlusOutlined />}
                                  onClick={() => handleEditDoor(exit.direction, exit.door)}
                                  style={{ color: exit.door ? (exit.door.is_locked ? '#faad14' : '#52c41a') : undefined }}
                                />
                              </Tooltip>,
                              <Popconfirm
                                key="delete"
                                title="Remove this exit?"
                                onConfirm={() => onRemoveExit(selectedRoom.id, exit.direction)}
                                okText="Remove"
                                cancelText="Cancel"
                              >
                                <Button
                                  type="text"
                                  size="small"
                                  danger
                                  icon={<DeleteOutlined />}
                                />
                              </Popconfirm>,
                            ]}
                          >
                            <div
                              className="exit-info"
                              onClick={() => onExitClick(exit.direction, exit.target)}
                              style={{ cursor: 'pointer', flex: 1 }}
                            >
                              <Space size={4}>
                                <Tag color={exit.direction === 'up' || exit.direction === 'down' ? 'gold' : 'green'}>
                                  {exit.direction}
                                </Tag>
                                {exit.door && (
                                  <Tag color={exit.door.is_locked ? 'orange' : (exit.door.is_open ? 'default' : 'blue')}>
                                    {exit.door.door_name || 'door'}
                                    {exit.door.is_locked ? ' 🔒' : (!exit.door.is_open ? ' [closed]' : '')}
                                  </Tag>
                                )}
                              </Space>
                              <Text ellipsis style={{ maxWidth: 100, marginLeft: 4 }}>
                                → {exit.target}
                              </Text>
                            </div>
                          </List.Item>
                        )}
                      />
                    ) : (
                      <Empty
                        description="No exits from this room"
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        style={{ margin: '24px 0' }}
                      />
                    )}

                    <Divider style={{ margin: '12px 0' }} />

                    <Button
                      icon={<PlusOutlined />}
                      onClick={() => {
                        // Set initial direction to first available
                        if (availableDirections.length > 0) {
                          setSelectedExitDirection(availableDirections[0]);
                        }
                        setAddExitModalOpen(true);
                      }}
                      block
                      disabled={availableDirections.length === 0}
                    >
                      Add Exit
                    </Button>
                    {availableDirections.length === 0 && (
                      <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
                        All exit directions are in use
                      </Text>
                    )}

                    <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 8 }}>
                      Tip: Drag from room edge to create exits visually, or use Add Exit for cross-area connections
                    </Text>
                  </div>
                ),
              },
            ]}
          />

          {/* Add NPC Modal */}
          <Modal
            title="Add NPC to Room"
            open={addNpcModalOpen}
            onCancel={() => {
              setAddNpcModalOpen(false);
              setSelectedNpcTemplate(null);
              setNpcSearchQuery('');
              addNpcForm.resetFields();
            }}
            onOk={handleAddNpc}
            okText="Add to Room"
            okButtonProps={{ disabled: !selectedNpcTemplate }}
          >
            <Input
              placeholder="Search NPCs..."
              prefix={<SearchOutlined />}
              value={npcSearchQuery}
              onChange={(e) => setNpcSearchQuery(e.target.value)}
              style={{ marginBottom: 12 }}
            />

            <div
              style={{
                maxHeight: 200,
                overflowY: 'auto',
                border: '1px solid #d9d9d9',
                borderRadius: 4,
                marginBottom: 16,
              }}
            >
              {filteredNpcTemplates.length > 0 ? (
                <List
                  size="small"
                  dataSource={filteredNpcTemplates}
                  renderItem={(template) => (
                    <List.Item
                      onClick={() => setSelectedNpcTemplate(template.id)}
                      style={{
                        cursor: 'pointer',
                        backgroundColor:
                          selectedNpcTemplate === template.id ? '#e6f7ff' : 'transparent',
                        padding: '8px 12px',
                      }}
                    >
                      <Space>
                        <UserOutlined />
                        <div>
                          <Text strong>{template.name}</Text>
                          <br />
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            {template.id}
                          </Text>
                        </div>
                      </Space>
                    </List.Item>
                  )}
                />
              ) : (
                <Empty
                  description="No NPCs found"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  style={{ margin: 16 }}
                />
              )}
            </div>

            <Form form={addNpcForm} layout="vertical" size="small">
              <Form.Item label="Quantity" name="quantity" initialValue={1}>
                <InputNumber min={1} max={99} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item label="Behavior" name="behavior" initialValue="stationary">
                <Select options={NPC_BEHAVIOR_OPTIONS} />
              </Form.Item>
              <Form.Item label="Respawn (seconds, 0 = never)" name="respawn_seconds" initialValue={0}>
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Form>
          </Modal>

          {/* Add Item Modal */}
          <Modal
            title="Add Item to Room"
            open={addItemModalOpen}
            onCancel={() => {
              setAddItemModalOpen(false);
              setSelectedItemTemplate(null);
              setItemSearchQuery('');
              addItemForm.resetFields();
            }}
            onOk={handleAddItem}
            okText="Add to Room"
            okButtonProps={{ disabled: !selectedItemTemplate }}
          >
            <Input
              placeholder="Search items..."
              prefix={<SearchOutlined />}
              value={itemSearchQuery}
              onChange={(e) => setItemSearchQuery(e.target.value)}
              style={{ marginBottom: 12 }}
            />

            <div
              style={{
                maxHeight: 200,
                overflowY: 'auto',
                border: '1px solid #d9d9d9',
                borderRadius: 4,
                marginBottom: 16,
              }}
            >
              {filteredItemTemplates.length > 0 ? (
                <List
                  size="small"
                  dataSource={filteredItemTemplates}
                  renderItem={(template) => (
                    <List.Item
                      onClick={() => setSelectedItemTemplate(template.id)}
                      style={{
                        cursor: 'pointer',
                        backgroundColor:
                          selectedItemTemplate === template.id ? '#e6f7ff' : 'transparent',
                        padding: '8px 12px',
                      }}
                    >
                      <Space>
                        <InboxOutlined />
                        <div>
                          <Text strong>{template.name}</Text>
                          <br />
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            {template.id}
                            {template.item_type && ` • ${template.item_type}`}
                          </Text>
                        </div>
                      </Space>
                    </List.Item>
                  )}
                />
              ) : (
                <Empty
                  description="No items found"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  style={{ margin: 16 }}
                />
              )}
            </div>

            <Form form={addItemForm} layout="vertical" size="small">
              <Form.Item label="Quantity" name="quantity" initialValue={1}>
                <InputNumber min={1} max={999} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item label="Location" name="location" initialValue="ground">
                <Select options={ITEM_LOCATION_OPTIONS} />
              </Form.Item>
              <Form.Item label="Container ID (if in container)" name="container_id">
                <Input placeholder="e.g., chest_01" />
              </Form.Item>
              <Form.Item label="Hidden" name="hidden" valuePropName="checked">
                <Select
                  options={[
                    { value: false, label: 'Visible' },
                    { value: true, label: 'Hidden (requires search)' },
                  ]}
                />
              </Form.Item>
            </Form>
          </Modal>

          {/* Add Exit Modal */}
          <Modal
            title="Add Exit to Another Room"
            open={addExitModalOpen}
            onCancel={() => {
              setAddExitModalOpen(false);
              setSelectedTargetRoom(null);
              setExitSearchQuery('');
            }}
            onOk={handleAddExit}
            okText="Create Exit"
            okButtonProps={{ disabled: !selectedTargetRoom || !selectedExitDirection }}
            width={500}
          >
            <Form layout="vertical" size="small">
              <Form.Item label="Exit Direction" required>
                <Select
                  value={selectedExitDirection}
                  onChange={setSelectedExitDirection}
                  options={availableDirections.map((dir) => ({
                    value: dir,
                    label: dir.charAt(0).toUpperCase() + dir.slice(1),
                  }))}
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Form>

            <Text strong style={{ display: 'block', marginBottom: 8 }}>Target Room</Text>
            <Input
              placeholder="Search rooms by name, ID, or area..."
              prefix={<SearchOutlined />}
              value={exitSearchQuery}
              onChange={(e) => setExitSearchQuery(e.target.value)}
              style={{ marginBottom: 12 }}
            />

            <div
              style={{
                maxHeight: 300,
                overflowY: 'auto',
                border: '1px solid var(--color-border, #424242)',
                borderRadius: 4,
                marginBottom: 16,
                background: 'var(--color-bg-primary, #141414)',
              }}
            >
              {Object.keys(roomsByArea).length > 0 ? (
                Object.entries(roomsByArea).map(([areaId, areaRooms]) => (
                  <div key={areaId}>
                    <div
                      style={{
                        padding: '8px 12px',
                        background: 'var(--color-bg-secondary, #1f1f1f)',
                        borderBottom: '1px solid var(--color-border, #424242)',
                        fontWeight: 600,
                        fontSize: 12,
                        position: 'sticky',
                        top: 0,
                        zIndex: 1,
                        color: 'var(--color-text, #e0e0e0)',
                      }}
                    >
                      <CompassOutlined style={{ marginRight: 6 }} />
                      {areaId}
                      {areaId !== selectedRoom?.area_id && (
                        <Tag color="blue" style={{ marginLeft: 8, fontSize: 10 }}>
                          Cross-Area
                        </Tag>
                      )}
                    </div>
                    <List
                      size="small"
                      dataSource={areaRooms}
                      renderItem={(room) => (
                        <List.Item
                          onClick={() => setSelectedTargetRoom(room.id)}
                          style={{
                            cursor: 'pointer',
                            backgroundColor:
                              selectedTargetRoom === room.id ? 'var(--color-bg-selected, #177ddc33)' : 'transparent',
                            padding: '8px 12px 8px 24px',
                          }}
                        >
                          <Space direction="vertical" size={0} style={{ width: '100%' }}>
                            <Text strong>{room.name}</Text>
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              {room.id} • z:{room.z_level}
                            </Text>
                          </Space>
                        </List.Item>
                      )}
                    />
                  </div>
                ))
              ) : (
                <Empty
                  description={exitSearchQuery ? 'No rooms match your search' : 'No other rooms available'}
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  style={{ margin: 16 }}
                />
              )}
            </div>

            {selectedTargetRoom && (
              <div style={{ padding: '8px 12px', background: 'var(--color-bg-success, #162312)', borderRadius: 4, marginBottom: 8 }}>
                <Text>
                  <strong>Preview:</strong> Exit {selectedExitDirection} → {selectedTargetRoom}
                </Text>
              </div>
            )}

            <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
              <strong>Tip:</strong> Use this to connect rooms across different areas (e.g., dungeon entrance from forest).
              The exit will be one-way; you'll need to create a return exit from the target room.
            </Text>
          </Modal>

          {/* Door Edit Modal */}
          <Modal
            title={`Configure Door - ${editingDoorDirection || ''} exit`}
            open={doorModalOpen}
            onCancel={() => {
              setDoorModalOpen(false);
              setEditingDoorDirection(null);
              doorForm.resetFields();
            }}
            onOk={handleSaveDoor}
            okText="Save"
            okButtonProps={{ disabled: !onUpdateDoor }}
          >
            <Form form={doorForm} layout="vertical" size="small">
              <Form.Item
                name="has_door"
                valuePropName="checked"
                label="Has Door"
              >
                <Switch
                  checkedChildren="Yes"
                  unCheckedChildren="No"
                />
              </Form.Item>

              <Form.Item noStyle shouldUpdate={(prev, cur) => prev.has_door !== cur.has_door}>
                {({ getFieldValue }) =>
                  getFieldValue('has_door') && (
                    <>
                      <Form.Item
                        name="door_name"
                        label="Door Name"
                        tooltip="Custom name like 'iron gate', 'wooden door', etc."
                      >
                        <Input placeholder="e.g., iron gate, wooden door" />
                      </Form.Item>

                      <Form.Item
                        name="is_open"
                        valuePropName="checked"
                        label="Open"
                        tooltip="An open door allows passage. A closed door blocks movement."
                      >
                        <Switch
                          checkedChildren="Open"
                          unCheckedChildren="Closed"
                        />
                      </Form.Item>

                      <Form.Item
                        name="is_locked"
                        valuePropName="checked"
                        label="Locked"
                        tooltip="A locked door must be unlocked (with a key or trigger) before it can be opened."
                      >
                        <Switch
                          checkedChildren="Locked"
                          unCheckedChildren="Unlocked"
                        />
                      </Form.Item>

                      <Form.Item noStyle shouldUpdate={(prev, cur) => prev.is_locked !== cur.is_locked}>
                        {({ getFieldValue: getVal }) =>
                          getVal('is_locked') && (
                            <Form.Item
                              name="key_item_id"
                              label="Key Item ID"
                              tooltip="The item template ID that can unlock this door (e.g., 'item_rusty_key')"
                            >
                              <Input placeholder="e.g., item_rusty_key" />
                            </Form.Item>
                          )
                        }
                      </Form.Item>
                    </>
                  )
                }
              </Form.Item>
            </Form>

            <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 12 }}>
              <strong>Tip:</strong> Doors are visible exits that can be opened/closed/locked.
              Use hidden exits for secret passages that need to be discovered.
            </Text>
          </Modal>
        </>
      )}
    </div>
  );
}
