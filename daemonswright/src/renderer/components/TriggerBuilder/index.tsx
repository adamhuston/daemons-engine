/**
 * TriggerBuilder Component
 *
 * A form-based builder for creating and editing game triggers.
 * Provides dropdowns for event types, conditions, and actions
 * with dynamic parameter fields based on the selected type.
 */

import { useState, useCallback } from 'react';
import { Form, Select, Input, InputNumber, Button, Card, Space, Collapse, Switch, Tooltip } from 'antd';
import { PlusOutlined, DeleteOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import './TriggerBuilder.css';

const { Option } = Select;
const { Panel } = Collapse;
const { TextArea } = Input;

// Event types and their required fields
const EVENT_TYPES = [
  { value: 'on_enter', label: 'On Enter', description: 'Triggers when player enters the room/area' },
  { value: 'on_exit', label: 'On Exit', description: 'Triggers when player leaves the room/area' },
  { value: 'on_command', label: 'On Command', description: 'Triggers when player types a matching command', requiresField: 'command_pattern' },
  { value: 'on_kill', label: 'On Kill', description: 'Triggers when player kills an NPC' },
  { value: 'on_pickup', label: 'On Pickup', description: 'Triggers when player picks up an item' },
  { value: 'on_drop', label: 'On Drop', description: 'Triggers when player drops an item' },
  { value: 'on_time', label: 'On Time', description: 'Triggers at specific time of day', requiresField: 'time' },
  { value: 'on_interval', label: 'On Interval', description: 'Triggers every N seconds', requiresField: 'interval' },
];

// Condition types and their parameters
const CONDITION_TYPES = [
  { 
    value: 'flag_set', 
    label: 'Flag Set', 
    description: 'Check if a player flag has a specific value',
    params: [
      { name: 'flag', type: 'string', label: 'Flag Name', required: true },
      { name: 'expected', type: 'any', label: 'Expected Value', required: true },
    ]
  },
  { 
    value: 'level', 
    label: 'Player Level', 
    description: 'Check if player is within a level range',
    params: [
      { name: 'min_level', type: 'number', label: 'Min Level', required: true },
      { name: 'max_level', type: 'number', label: 'Max Level', required: false },
    ]
  },
  { 
    value: 'has_item', 
    label: 'Has Item', 
    description: 'Check if player has an item in inventory',
    params: [
      { name: 'item_id', type: 'string', label: 'Item Template ID', required: true },
      { name: 'quantity', type: 'number', label: 'Quantity', required: false },
    ]
  },
  { 
    value: 'has_quest', 
    label: 'Has Quest', 
    description: 'Check if player has a specific quest',
    params: [
      { name: 'quest_id', type: 'string', label: 'Quest ID', required: true },
    ]
  },
  { 
    value: 'quest_status', 
    label: 'Quest Status', 
    description: 'Check quest completion status',
    params: [
      { name: 'quest_id', type: 'string', label: 'Quest ID', required: true },
      { name: 'status', type: 'enum', label: 'Status', required: true, options: ['active', 'completed', 'failed'] },
    ]
  },
  { 
    value: 'time_range', 
    label: 'Time Range', 
    description: 'Check if current time is within range',
    params: [
      { name: 'start_hour', type: 'number', label: 'Start Hour (0-23)', required: true },
      { name: 'end_hour', type: 'number', label: 'End Hour (0-23)', required: true },
    ]
  },
  { 
    value: 'visibility_level', 
    label: 'Visibility Level', 
    description: 'Check room lighting level',
    params: [
      { name: 'level', type: 'enum', label: 'Light Level', required: true, options: ['pitch_black', 'dim', 'normal', 'bright', 'enhanced'], nested: true },
    ]
  },
  { 
    value: 'faction_standing', 
    label: 'Faction Standing', 
    description: 'Check player reputation with a faction',
    params: [
      { name: 'faction_id', type: 'string', label: 'Faction ID', required: true },
      { name: 'min_standing', type: 'number', label: 'Minimum Standing', required: true },
    ]
  },
  { 
    value: 'class_check', 
    label: 'Class Check', 
    description: 'Check if player is a specific class',
    params: [
      { name: 'class_id', type: 'string', label: 'Class ID', required: true },
    ]
  },
];

// Action types and their parameters
const ACTION_TYPES = [
  { 
    value: 'message_player', 
    label: 'Message Player', 
    description: 'Send a message to the player',
    params: [
      { name: 'text', type: 'textarea', label: 'Message Text', required: true, nested: true },
    ]
  },
  { 
    value: 'message_room', 
    label: 'Message Room', 
    description: 'Send a message to everyone in the room',
    params: [
      { name: 'message', type: 'textarea', label: 'Message Text', required: true },
    ]
  },
  { 
    value: 'set_flag', 
    label: 'Set Flag', 
    description: 'Set a player flag to a value',
    params: [
      { name: 'flag_name', type: 'string', label: 'Flag Name', required: true, nested: true },
      { name: 'value', type: 'any', label: 'Value', required: true, nested: true },
    ]
  },
  { 
    value: 'give_item', 
    label: 'Give Item', 
    description: 'Add an item to player inventory',
    params: [
      { name: 'item_id', type: 'string', label: 'Item Template ID', required: true },
      { name: 'quantity', type: 'number', label: 'Quantity', required: false },
    ]
  },
  { 
    value: 'remove_item', 
    label: 'Remove Item', 
    description: 'Remove an item from player inventory',
    params: [
      { name: 'item_id', type: 'string', label: 'Item Template ID', required: true },
      { name: 'quantity', type: 'number', label: 'Quantity', required: false },
    ]
  },
  { 
    value: 'spawn_npc', 
    label: 'Spawn NPC', 
    description: 'Create an NPC instance',
    params: [
      { name: 'template_id', type: 'string', label: 'NPC Template ID', required: true },
      { name: 'room_id', type: 'string', label: 'Room ID (optional)', required: false },
    ]
  },
  { 
    value: 'despawn_npc', 
    label: 'Despawn NPC', 
    description: 'Remove an NPC instance',
    params: [
      { name: 'npc_id', type: 'string', label: 'NPC Instance ID', required: true },
    ]
  },
  { 
    value: 'reveal_exit', 
    label: 'Reveal Exit', 
    description: 'Make a hidden exit visible',
    params: [
      { name: 'direction', type: 'string', label: 'Direction', required: true, nested: true },
      { name: 'target_room', type: 'string', label: 'Target Room (optional)', required: false, nested: true },
    ]
  },
  { 
    value: 'hide_exit', 
    label: 'Hide Exit', 
    description: 'Hide an exit',
    params: [
      { name: 'direction', type: 'string', label: 'Direction', required: true, nested: true },
    ]
  },
  { 
    value: 'open_exit', 
    label: 'Open Exit', 
    description: 'Add or reveal an exit',
    params: [
      { name: 'direction', type: 'string', label: 'Direction', required: true, nested: true },
      { name: 'destination', type: 'string', label: 'Destination Room', required: true, nested: true },
    ]
  },
  { 
    value: 'close_exit', 
    label: 'Close Exit', 
    description: 'Remove an exit',
    params: [
      { name: 'direction', type: 'string', label: 'Direction', required: true },
    ]
  },
  { 
    value: 'open_door', 
    label: 'Open Door', 
    description: 'Open a closed door',
    params: [
      { name: 'direction', type: 'string', label: 'Direction', required: true, nested: true },
    ]
  },
  { 
    value: 'close_door', 
    label: 'Close Door', 
    description: 'Close an open door',
    params: [
      { name: 'direction', type: 'string', label: 'Direction', required: true, nested: true },
    ]
  },
  { 
    value: 'lock_door', 
    label: 'Lock Door', 
    description: 'Lock a door',
    params: [
      { name: 'direction', type: 'string', label: 'Direction', required: true, nested: true },
      { name: 'key_item_id', type: 'string', label: 'Key Item ID (optional)', required: false, nested: true },
    ]
  },
  { 
    value: 'unlock_door', 
    label: 'Unlock Door', 
    description: 'Unlock a locked door',
    params: [
      { name: 'direction', type: 'string', label: 'Direction', required: true, nested: true },
    ]
  },
];

interface TriggerCondition {
  type: string;
  params?: Record<string, unknown>;
  [key: string]: unknown;
}

interface TriggerAction {
  type: string;
  params?: Record<string, unknown>;
  [key: string]: unknown;
}

interface TriggerData {
  id: string;
  event: string;
  description?: string;
  command_pattern?: string;
  time?: string;
  interval?: number;
  conditions: TriggerCondition[];
  actions: TriggerAction[];
  max_fires?: number;
  enabled?: boolean;
}

interface TriggerBuilderProps {
  data: Record<string, unknown>;
  onChange: (data: Record<string, unknown>) => void;
}

export function TriggerBuilder({ data, onChange }: TriggerBuilderProps) {
  const triggerData = data as unknown as TriggerData;
  const [activeConditionPanels, setActiveConditionPanels] = useState<string[]>([]);
  const [activeActionPanels, setActiveActionPanels] = useState<string[]>([]);

  // Update a top-level field
  const updateField = useCallback((field: string, value: unknown) => {
    onChange({ ...data, [field]: value });
  }, [data, onChange]);

  // Get the selected event type config
  const selectedEvent = EVENT_TYPES.find(e => e.value === triggerData.event);

  // Add a new condition
  const addCondition = useCallback(() => {
    const conditions = triggerData.conditions || [];
    const newCondition: TriggerCondition = { type: 'flag_set' };
    onChange({ ...data, conditions: [...conditions, newCondition] });
    setActiveConditionPanels([...activeConditionPanels, `condition-${conditions.length}`]);
  }, [data, triggerData.conditions, onChange, activeConditionPanels]);

  // Remove a condition
  const removeCondition = useCallback((index: number) => {
    const conditions = [...(triggerData.conditions || [])];
    conditions.splice(index, 1);
    onChange({ ...data, conditions });
  }, [data, triggerData.conditions, onChange]);

  // Update a condition
  const updateCondition = useCallback((index: number, updates: Partial<TriggerCondition>) => {
    const conditions = [...(triggerData.conditions || [])];
    conditions[index] = { ...conditions[index], ...updates };
    onChange({ ...data, conditions });
  }, [data, triggerData.conditions, onChange]);

  // Add a new action
  const addAction = useCallback(() => {
    const actions = triggerData.actions || [];
    const newAction: TriggerAction = { type: 'message_player', params: { text: '' } };
    onChange({ ...data, actions: [...actions, newAction] });
    setActiveActionPanels([...activeActionPanels, `action-${actions.length}`]);
  }, [data, triggerData.actions, onChange, activeActionPanels]);

  // Remove an action
  const removeAction = useCallback((index: number) => {
    const actions = [...(triggerData.actions || [])];
    actions.splice(index, 1);
    onChange({ ...data, actions });
  }, [data, triggerData.actions, onChange]);

  // Update an action
  const updateAction = useCallback((index: number, updates: Partial<TriggerAction>) => {
    const actions = [...(triggerData.actions || [])];
    actions[index] = { ...actions[index], ...updates };
    onChange({ ...data, actions });
  }, [data, triggerData.actions, onChange]);

  // Render parameter input based on type
  const renderParamInput = (
    param: { name: string; type: string; label: string; required: boolean; options?: string[]; nested?: boolean },
    value: unknown,
    onParamChange: (name: string, value: unknown, nested?: boolean) => void
  ) => {
    const inputValue = value ?? '';
    
    switch (param.type) {
      case 'number':
        return (
          <InputNumber
            value={inputValue as number}
            onChange={(v) => onParamChange(param.name, v, param.nested)}
            style={{ width: '100%' }}
          />
        );
      case 'textarea':
        return (
          <TextArea
            value={inputValue as string}
            onChange={(e) => onParamChange(param.name, e.target.value, param.nested)}
            rows={3}
          />
        );
      case 'enum':
        return (
          <Select
            value={inputValue as string}
            onChange={(v) => onParamChange(param.name, v, param.nested)}
            style={{ width: '100%' }}
          >
            {param.options?.map(opt => (
              <Option key={opt} value={opt}>{opt}</Option>
            ))}
          </Select>
        );
      case 'any':
        return (
          <Input
            value={String(inputValue)}
            onChange={(e) => {
              // Try to parse as number or boolean
              const val = e.target.value;
              if (val === 'true') onParamChange(param.name, true, param.nested);
              else if (val === 'false') onParamChange(param.name, false, param.nested);
              else if (!isNaN(Number(val)) && val !== '') onParamChange(param.name, Number(val), param.nested);
              else onParamChange(param.name, val, param.nested);
            }}
            placeholder="true, false, number, or string"
          />
        );
      default:
        return (
          <Input
            value={inputValue as string}
            onChange={(e) => onParamChange(param.name, e.target.value, param.nested)}
          />
        );
    }
  };

  // Render a condition panel
  const renderCondition = (condition: TriggerCondition, index: number) => {
    const conditionType = CONDITION_TYPES.find(c => c.value === condition.type);
    
    const handleParamChange = (name: string, value: unknown, nested?: boolean) => {
      if (nested) {
        updateCondition(index, { 
          params: { ...(condition.params || {}), [name]: value }
        });
      } else {
        updateCondition(index, { [name]: value });
      }
    };

    // Get current value for a param (check both nested params and top-level)
    const getParamValue = (param: { name: string; nested?: boolean }) => {
      if (param.nested && condition.params) {
        return condition.params[param.name];
      }
      return condition[param.name];
    };

    return (
      <Panel
        key={`condition-${index}`}
        header={
          <Space>
            <span>Condition {index + 1}: {conditionType?.label || condition.type}</span>
            <Tooltip title={conditionType?.description}>
              <QuestionCircleOutlined />
            </Tooltip>
          </Space>
        }
        extra={
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={(e) => { e.stopPropagation(); removeCondition(index); }}
            size="small"
          />
        }
      >
        <Form layout="vertical" size="small">
          <Form.Item label="Condition Type">
            <Select
              value={condition.type}
              onChange={(v) => updateCondition(index, { type: v, params: {} })}
            >
              {CONDITION_TYPES.map(c => (
                <Option key={c.value} value={c.value}>{c.label}</Option>
              ))}
            </Select>
          </Form.Item>
          
          {conditionType?.params.map(param => (
            <Form.Item 
              key={param.name} 
              label={param.label}
              required={param.required}
            >
              {renderParamInput(param, getParamValue(param), handleParamChange)}
            </Form.Item>
          ))}
        </Form>
      </Panel>
    );
  };

  // Render an action panel
  const renderAction = (action: TriggerAction, index: number) => {
    const actionType = ACTION_TYPES.find(a => a.value === action.type);
    
    const handleParamChange = (name: string, value: unknown, nested?: boolean) => {
      if (nested) {
        updateAction(index, { 
          params: { ...(action.params || {}), [name]: value }
        });
      } else {
        updateAction(index, { [name]: value });
      }
    };

    // Get current value for a param (check both nested params and top-level)
    const getParamValue = (param: { name: string; nested?: boolean }) => {
      if (param.nested && action.params) {
        return action.params[param.name];
      }
      return action[param.name];
    };

    return (
      <Panel
        key={`action-${index}`}
        header={
          <Space>
            <span>Action {index + 1}: {actionType?.label || action.type}</span>
            <Tooltip title={actionType?.description}>
              <QuestionCircleOutlined />
            </Tooltip>
          </Space>
        }
        extra={
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={(e) => { e.stopPropagation(); removeAction(index); }}
            size="small"
          />
        }
      >
        <Form layout="vertical" size="small">
          <Form.Item label="Action Type">
            <Select
              value={action.type}
              onChange={(v) => updateAction(index, { type: v, params: {} })}
            >
              {ACTION_TYPES.map(a => (
                <Option key={a.value} value={a.value}>{a.label}</Option>
              ))}
            </Select>
          </Form.Item>
          
          {actionType?.params.map(param => (
            <Form.Item 
              key={param.name} 
              label={param.label}
              required={param.required}
            >
              {renderParamInput(param, getParamValue(param), handleParamChange)}
            </Form.Item>
          ))}
        </Form>
      </Panel>
    );
  };

  return (
    <div className="trigger-builder">
      {/* Basic Info */}
      <Card title="Basic Information" size="small" className="trigger-section">
        <Form layout="vertical" size="small">
          <Form.Item label="Trigger ID" required>
            <Input
              value={triggerData.id || ''}
              onChange={(e) => updateField('id', e.target.value)}
              placeholder="unique_trigger_id"
            />
          </Form.Item>

          <Form.Item label="Description">
            <TextArea
              value={triggerData.description || ''}
              onChange={(e) => updateField('description', e.target.value)}
              rows={2}
              placeholder="What this trigger does..."
            />
          </Form.Item>

          <Form.Item 
            label={
              <Space>
                Event Type
                <Tooltip title={selectedEvent?.description}>
                  <QuestionCircleOutlined />
                </Tooltip>
              </Space>
            }
            required
          >
            <Select
              value={triggerData.event || 'on_enter'}
              onChange={(v) => updateField('event', v)}
            >
              {EVENT_TYPES.map(e => (
                <Option key={e.value} value={e.value}>{e.label}</Option>
              ))}
            </Select>
          </Form.Item>

          {/* Event-specific fields */}
          {selectedEvent?.requiresField === 'command_pattern' && (
            <Form.Item label="Command Pattern" required>
              <Input
                value={triggerData.command_pattern || ''}
                onChange={(e) => updateField('command_pattern', e.target.value)}
                placeholder="search*, look*"
              />
            </Form.Item>
          )}

          {selectedEvent?.requiresField === 'time' && (
            <Form.Item label="Time (HH:MM)" required>
              <Input
                value={triggerData.time || ''}
                onChange={(e) => updateField('time', e.target.value)}
                placeholder="06:00"
              />
            </Form.Item>
          )}

          {selectedEvent?.requiresField === 'interval' && (
            <Form.Item label="Interval (seconds)" required>
              <InputNumber
                value={triggerData.interval || 60}
                onChange={(v) => updateField('interval', v)}
                min={1}
                style={{ width: '100%' }}
              />
            </Form.Item>
          )}

          <Space>
            <Form.Item label="Max Fires">
              <InputNumber
                value={triggerData.max_fires}
                onChange={(v) => updateField('max_fires', v)}
                min={1}
                placeholder="Unlimited"
              />
            </Form.Item>

            <Form.Item label="Enabled">
              <Switch
                checked={triggerData.enabled !== false}
                onChange={(v) => updateField('enabled', v)}
              />
            </Form.Item>
          </Space>
        </Form>
      </Card>

      {/* Conditions */}
      <Card 
        title="Conditions" 
        size="small" 
        className="trigger-section"
        extra={
          <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={addCondition}>
            Add Condition
          </Button>
        }
      >
        {triggerData.conditions?.length > 0 ? (
          <Collapse 
            activeKey={activeConditionPanels}
            onChange={(keys) => setActiveConditionPanels(keys as string[])}
          >
            {triggerData.conditions.map((condition, index) => renderCondition(condition, index))}
          </Collapse>
        ) : (
          <div className="empty-section">
            No conditions - trigger will fire on every event
          </div>
        )}
      </Card>

      {/* Actions */}
      <Card 
        title="Actions" 
        size="small" 
        className="trigger-section"
        extra={
          <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={addAction}>
            Add Action
          </Button>
        }
      >
        {triggerData.actions?.length > 0 ? (
          <Collapse 
            activeKey={activeActionPanels}
            onChange={(keys) => setActiveActionPanels(keys as string[])}
          >
            {triggerData.actions.map((action, index) => renderAction(action, index))}
          </Collapse>
        ) : (
          <div className="empty-section">
            No actions defined - add at least one action
          </div>
        )}
      </Card>
    </div>
  );
}
