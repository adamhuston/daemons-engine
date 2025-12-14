/**
 * AreaPropertiesPanel Component
 *
 * Tabbed sidebar panel for viewing and editing area properties.
 * Displays when an area is selected in the Room Builder.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  Form,
  Input,
  Select,
  Button,
  Divider,
  Empty,
  Spin,
  Typography,
  Tabs,
  InputNumber,
  Space,
  Popconfirm,
  Slider,
  Tag,
  List,
  Collapse,
  Card,
} from 'antd';
import {
  SaveOutlined,
  DeleteOutlined,
  PlusOutlined,
  GlobalOutlined,
  ClockCircleOutlined,
  EnvironmentOutlined,
  SoundOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type { Area, TimePhase, RoomNode } from '../../../shared/types';

const { TextArea } = Input;
const { Text, Title } = Typography;
const { Panel } = Collapse;

// Biome options
const BIOME_OPTIONS = [
  { value: 'mystical', label: 'Mystical', color: '#9254de' },
  { value: 'forest', label: 'Forest', color: '#52c41a' },
  { value: 'cave', label: 'Cave', color: '#8c8c8c' },
  { value: 'desert', label: 'Desert', color: '#faad14' },
  { value: 'mountain', label: 'Mountain', color: '#595959' },
  { value: 'swamp', label: 'Swamp', color: '#389e0d' },
  { value: 'tundra', label: 'Tundra', color: '#69c0ff' },
  { value: 'volcanic', label: 'Volcanic', color: '#cf1322' },
  { value: 'coastal', label: 'Coastal', color: '#1890ff' },
  { value: 'urban', label: 'Urban', color: '#d4b106' },
  { value: 'underground', label: 'Underground', color: '#434343' },
  { value: 'ethereal', label: 'Ethereal', color: '#eb2f96' },
];

// Climate options
const CLIMATE_OPTIONS = [
  { value: 'temperate', label: 'Temperate' },
  { value: 'arctic', label: 'Arctic' },
  { value: 'tropical', label: 'Tropical' },
  { value: 'arid', label: 'Arid' },
  { value: 'humid', label: 'Humid' },
  { value: 'Mediterranean', label: 'Mediterranean' },
  { value: 'continental', label: 'Continental' },
  { value: 'subarctic', label: 'Subarctic' },
];

// Ambient lighting options
const LIGHTING_OPTIONS = [
  { value: 'pitch_black', label: 'Pitch Black', icon: '🌑' },
  { value: 'dim', label: 'Dim', icon: '🌙' },
  { value: 'normal', label: 'Normal', icon: '☀️' },
  { value: 'bright', label: 'Bright', icon: '✨' },
  { value: 'prismatic', label: 'Prismatic', icon: '🌈' },
];

// Magic intensity options
const MAGIC_INTENSITY_OPTIONS = [
  { value: 'none', label: 'None', color: '#595959' },
  { value: 'low', label: 'Low', color: '#52c41a' },
  { value: 'moderate', label: 'Moderate', color: '#1890ff' },
  { value: 'high', label: 'High', color: '#722ed1' },
  { value: 'extreme', label: 'Extreme', color: '#eb2f96' },
];

// Weather profile options
const WEATHER_OPTIONS = [
  { value: '', label: 'None (static)' },
  { value: 'temperate_cycle', label: 'Temperate Cycle' },
  { value: 'rainy', label: 'Rainy' },
  { value: 'stormy', label: 'Stormy' },
  { value: 'snowy', label: 'Snowy' },
  { value: 'foggy', label: 'Foggy' },
  { value: 'clear', label: 'Clear' },
  { value: 'sandstorm', label: 'Sandstorm' },
];

// Default time phases
const DEFAULT_TIME_PHASES: TimePhase[] = [
  { name: 'night', ambient_text: 'The darkness of night surrounds you.' },
  { name: 'morning', ambient_text: 'The first light of dawn breaks over the horizon.' },
  { name: 'day', ambient_text: 'The sun shines overhead.' },
  { name: 'evening', ambient_text: 'The sun begins to set, casting long shadows.' },
];

interface AreaFormData {
  name: string;
  description: string;
  biome: string;
  climate: string;
  ambient_lighting: string;
  weather_profile: string;
  danger_level: number;
  magic_intensity: string;
  ambient_sound: string;
  default_respawn_time: number;
  time_scale: number;
  starting_day: number;
  starting_hour: number;
  starting_minute: number;
}

interface AreaPropertiesPanelProps {
  selectedArea: Area | null;
  onSave: (areaId: string, updates: Partial<Area>) => Promise<void>;
  onDelete?: (areaId: string) => Promise<void>;
  isLoading?: boolean;
  isDirty?: boolean;
  onDirtyChange?: (isDirty: boolean) => void;
  // All rooms for entry point selection
  areaRooms?: RoomNode[];
  // Entry points management
  onUpdateEntryPoints?: (areaId: string, entryPoints: string[]) => Promise<void>;
  // Time phases management
  onUpdateTimePhases?: (areaId: string, timePhases: TimePhase[]) => Promise<void>;
  // Biome options from schema
  biomeOptions?: string[];
  onAddBiome?: (newBiome: string) => Promise<boolean>;
}

export function AreaPropertiesPanel({
  selectedArea,
  onSave,
  onDelete,
  isLoading = false,
  isDirty = false,
  onDirtyChange,
  areaRooms = [],
  onUpdateEntryPoints,
  onUpdateTimePhases,
  biomeOptions,
  onAddBiome,
}: AreaPropertiesPanelProps) {
  const [form] = Form.useForm<AreaFormData>();
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('general');
  const [entryPoints, setEntryPoints] = useState<string[]>([]);
  const [timePhases, setTimePhases] = useState<TimePhase[]>([]);
  const [editingPhaseIndex, setEditingPhaseIndex] = useState<number | null>(null);

  // Update form when selected area changes
  useEffect(() => {
    if (selectedArea) {
      form.setFieldsValue({
        name: selectedArea.name,
        description: selectedArea.description || '',
        biome: selectedArea.biome || 'mystical',
        climate: selectedArea.climate || 'temperate',
        ambient_lighting: selectedArea.ambient_lighting || 'dim',
        weather_profile: selectedArea.weather_profile || '',
        danger_level: selectedArea.danger_level ?? 1,
        magic_intensity: selectedArea.magic_intensity || 'moderate',
        ambient_sound: selectedArea.ambient_sound || '',
        default_respawn_time: selectedArea.default_respawn_time ?? 300,
        time_scale: selectedArea.time_scale ?? 1.0,
        starting_day: selectedArea.starting_day ?? 1,
        starting_hour: selectedArea.starting_hour ?? 0,
        starting_minute: selectedArea.starting_minute ?? 0,
      });
      setEntryPoints(selectedArea.entry_points || []);
      setTimePhases(selectedArea.time_phases || DEFAULT_TIME_PHASES);
      // Reset dirty state when switching areas
      onDirtyChange?.(false);
    }
  }, [selectedArea, form, onDirtyChange]);

  // Track form changes to update dirty state
  const handleValuesChange = useCallback(() => {
    onDirtyChange?.(true);
  }, [onDirtyChange]);

  // Handle form save
  const handleSave = useCallback(async () => {
    if (!selectedArea) return;

    try {
      setSaving(true);
      const values = form.getFieldsValue();
      await onSave(selectedArea.id, {
        ...values,
        entry_points: entryPoints,
        time_phases: timePhases,
      });
      onDirtyChange?.(false);
    } finally {
      setSaving(false);
    }
  }, [selectedArea, form, onSave, onDirtyChange, entryPoints, timePhases]);

  // Handle delete
  const handleDelete = useCallback(async () => {
    if (!selectedArea || !onDelete) return;
    await onDelete(selectedArea.id);
  }, [selectedArea, onDelete]);

  // Handle entry point toggle
  const handleToggleEntryPoint = useCallback((roomId: string) => {
    setEntryPoints((prev) => {
      const newPoints = prev.includes(roomId)
        ? prev.filter((id) => id !== roomId)
        : [...prev, roomId];
      onDirtyChange?.(true);
      return newPoints;
    });
  }, [onDirtyChange]);

  // Handle time phase update
  const handleUpdateTimePhase = useCallback((index: number, updates: Partial<TimePhase>) => {
    setTimePhases((prev) => {
      const newPhases = [...prev];
      newPhases[index] = { ...newPhases[index], ...updates };
      onDirtyChange?.(true);
      return newPhases;
    });
  }, [onDirtyChange]);

  // If no area is selected, show empty state
  if (!selectedArea) {
    return (
      <div className="area-properties-panel empty" style={{ padding: 24, textAlign: 'center' }}>
        <Empty
          description="Select an area to view properties"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </div>
    );
  }

  // Get biome color for display
  const biomeColor = BIOME_OPTIONS.find(b => b.value === selectedArea.biome)?.color || '#595959';

  const tabItems = [
    {
      key: 'general',
      label: (
        <span>
          <GlobalOutlined /> General
        </span>
      ),
      children: (
        <Form
          form={form}
          layout="vertical"
          onValuesChange={handleValuesChange}
          size="small"
        >
          <Form.Item label="Name" name="name" rules={[{ required: true }]}>
            <Input placeholder="Area name" />
          </Form.Item>

          <Form.Item label="Description" name="description">
            <TextArea
              rows={3}
              placeholder="A brief description of the area..."
              autoSize={{ minRows: 2, maxRows: 6 }}
            />
          </Form.Item>

          <Form.Item label="Biome" name="biome">
            <Select
              options={
                biomeOptions
                  ? biomeOptions.map((b) => ({
                      value: b,
                      label: b.charAt(0).toUpperCase() + b.slice(1),
                    }))
                  : BIOME_OPTIONS
              }
              placeholder="Select biome"
            />
          </Form.Item>

          <Form.Item label="Climate" name="climate">
            <Select options={CLIMATE_OPTIONS} placeholder="Select climate" />
          </Form.Item>

          <Form.Item
            label={
              <span>
                Danger Level{' '}
                <Text type="secondary" style={{ fontSize: 12 }}>
                  (1-10)
                </Text>
              </span>
            }
            name="danger_level"
          >
            <Slider
              min={1}
              max={10}
              marks={{
                1: '1',
                5: '5',
                10: '10',
              }}
              tooltip={{ formatter: (v) => `Danger: ${v}` }}
            />
          </Form.Item>

          <Form.Item label="Magic Intensity" name="magic_intensity">
            <Select placeholder="Select magic intensity">
              {MAGIC_INTENSITY_OPTIONS.map((opt) => (
                <Select.Option key={opt.value} value={opt.value}>
                  <Tag color={opt.color}>{opt.label}</Tag>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      ),
    },
    {
      key: 'environment',
      label: (
        <span>
          <EnvironmentOutlined /> Environment
        </span>
      ),
      children: (
        <Form
          form={form}
          layout="vertical"
          onValuesChange={handleValuesChange}
          size="small"
        >
          <Form.Item label="Ambient Lighting" name="ambient_lighting">
            <Select placeholder="Select lighting">
              {LIGHTING_OPTIONS.map((opt) => (
                <Select.Option key={opt.value} value={opt.value}>
                  {opt.icon} {opt.label}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item label="Weather Profile" name="weather_profile">
            <Select
              options={WEATHER_OPTIONS}
              placeholder="Select weather"
              allowClear
            />
          </Form.Item>

          <Form.Item label="Ambient Sound" name="ambient_sound">
            <Input placeholder="e.g., forest_ambience, cave_drips" />
          </Form.Item>

          <Form.Item
            label={
              <span>
                Default Respawn Time{' '}
                <Text type="secondary" style={{ fontSize: 12 }}>
                  (seconds)
                </Text>
              </span>
            }
            name="default_respawn_time"
          >
            <InputNumber
              min={0}
              max={86400}
              step={60}
              style={{ width: '100%' }}
              addonAfter="sec"
            />
          </Form.Item>

          <Divider orientation="left" plain>
            <Text type="secondary">Entry Points</Text>
          </Divider>

          <div style={{ marginBottom: 16 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Select rooms where players can spawn into this area:
            </Text>
          </div>

          {areaRooms.length === 0 ? (
            <Empty
              description="No rooms in this area"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          ) : (
            <List
              size="small"
              dataSource={areaRooms}
              style={{ maxHeight: 200, overflowY: 'auto' }}
              renderItem={(room) => (
                <List.Item
                  style={{
                    padding: '4px 8px',
                    cursor: 'pointer',
                    background: entryPoints.includes(room.id)
                      ? 'var(--color-primary-bg, rgba(24, 144, 255, 0.1))'
                      : 'transparent',
                    borderRadius: 4,
                  }}
                  onClick={() => handleToggleEntryPoint(room.id)}
                >
                  <Space>
                    {entryPoints.includes(room.id) ? (
                      <Tag color="blue">Entry</Tag>
                    ) : (
                      <Tag>—</Tag>
                    )}
                    <Text>{room.name}</Text>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      ({room.id})
                    </Text>
                  </Space>
                </List.Item>
              )}
            />
          )}
        </Form>
      ),
    },
    {
      key: 'time',
      label: (
        <span>
          <ClockCircleOutlined /> Time
        </span>
      ),
      children: (
        <Form
          form={form}
          layout="vertical"
          onValuesChange={handleValuesChange}
          size="small"
        >
          <Form.Item
            label={
              <span>
                Time Scale{' '}
                <Text type="secondary" style={{ fontSize: 12 }}>
                  (day/night speed)
                </Text>
              </span>
            }
            name="time_scale"
          >
            <Slider
              min={0.1}
              max={10}
              step={0.1}
              marks={{
                0.5: '0.5x',
                1: '1x',
                2: '2x',
                5: '5x',
                10: '10x',
              }}
              tooltip={{
                formatter: (v) => `${v}x speed`,
              }}
            />
          </Form.Item>

          <Divider orientation="left" plain>
            <Text type="secondary">Starting Time</Text>
          </Divider>

          <Space style={{ width: '100%' }} align="start">
            <Form.Item label="Day" name="starting_day" style={{ marginBottom: 8 }}>
              <InputNumber min={1} max={365} style={{ width: 80 }} />
            </Form.Item>
            <Form.Item label="Hour" name="starting_hour" style={{ marginBottom: 8 }}>
              <InputNumber min={0} max={23} style={{ width: 70 }} />
            </Form.Item>
            <Form.Item label="Minute" name="starting_minute" style={{ marginBottom: 8 }}>
              <InputNumber min={0} max={59} style={{ width: 70 }} />
            </Form.Item>
          </Space>

          <Divider orientation="left" plain>
            <Text type="secondary">Time Phases</Text>
          </Divider>

          <div style={{ marginBottom: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Customize ambient text for each time of day:
            </Text>
          </div>

          <Collapse size="small" accordion>
            {timePhases.map((phase, index) => (
              <Panel
                key={phase.name}
                header={
                  <Space>
                    <Text strong style={{ textTransform: 'capitalize' }}>
                      {phase.name}
                    </Text>
                    {phase.lighting && (
                      <Tag size="small">{phase.lighting}</Tag>
                    )}
                  </Space>
                }
              >
                <Form layout="vertical" size="small">
                  <Form.Item label="Ambient Text">
                    <TextArea
                      value={phase.ambient_text || ''}
                      onChange={(e) =>
                        handleUpdateTimePhase(index, { ambient_text: e.target.value })
                      }
                      rows={2}
                      placeholder="Text shown during this time phase..."
                    />
                  </Form.Item>
                  <Form.Item label="Lighting Override">
                    <Select
                      value={phase.lighting || ''}
                      onChange={(val) =>
                        handleUpdateTimePhase(index, { lighting: val || undefined })
                      }
                      allowClear
                      placeholder="Use area default"
                    >
                      {LIGHTING_OPTIONS.map((opt) => (
                        <Select.Option key={opt.value} value={opt.value}>
                          {opt.icon} {opt.label}
                        </Select.Option>
                      ))}
                    </Select>
                  </Form.Item>
                </Form>
              </Panel>
            ))}
          </Collapse>
        </Form>
      ),
    },
  ];

  return (
    <div
      className="area-properties-panel"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'var(--color-bg-secondary, #1f1f1f)',
        borderLeft: '1px solid var(--color-border, #434343)',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--color-border, #434343)',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <div
          style={{
            width: 12,
            height: 12,
            borderRadius: '50%',
            background: biomeColor,
          }}
        />
        <div style={{ flex: 1 }}>
          <Title level={5} style={{ margin: 0 }}>
            {selectedArea.name}
          </Title>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {selectedArea.id}
          </Text>
        </div>
        {isDirty && (
          <Tag color="orange" style={{ margin: 0 }}>
            Unsaved
          </Tag>
        )}
      </div>

      {/* Tabs Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '0 8px' }}>
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin />
          </div>
        ) : (
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={tabItems}
            size="small"
          />
        )}
      </div>

      {/* Footer Actions */}
      <div
        style={{
          padding: '12px 16px',
          borderTop: '1px solid var(--color-border, #434343)',
          display: 'flex',
          gap: 8,
        }}
      >
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={handleSave}
          loading={saving}
          disabled={!isDirty}
          style={{ flex: 1 }}
        >
          Save
        </Button>
        {onDelete && (
          <Popconfirm
            title="Delete this area?"
            description="This will also delete all rooms in this area."
            onConfirm={handleDelete}
            okText="Delete"
            cancelText="Cancel"
            okButtonProps={{ danger: true }}
          >
            <Button danger icon={<DeleteOutlined />} />
          </Popconfirm>
        )}
      </div>
    </div>
  );
}
