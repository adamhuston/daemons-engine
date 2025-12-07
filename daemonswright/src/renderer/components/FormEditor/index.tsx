/**
 * FormEditor Component
 *
 * Auto-generated form editor for content types that don't need
 * visual graph representation (items, NPCs, abilities, classes, etc.)
 */

import { useCallback, useMemo, useState, useEffect } from 'react';
import { Form, Input, InputNumber, Select, Switch, Card, Button, Divider, Space, Spin } from 'antd';
import { PlusOutlined, DeleteOutlined, LinkOutlined } from '@ant-design/icons';
import type { SchemaDefinition, SchemaField } from '../../shared/types';
import { EntityMultiSelect } from './EntityMultiSelect';

const { TextArea } = Input;
const { Option } = Select;

interface FormEditorProps {
  schema: SchemaDefinition;
  data: Record<string, unknown>;
  onChange: (data: Record<string, unknown>) => void;
  contentType: string;
  onNavigateToEntity?: (entityType: string, entityId: string) => void;
  worldDataPath?: string | null;
}

export function FormEditor({ schema, data, onChange, contentType, onNavigateToEntity, worldDataPath }: FormEditorProps) {
  const [form] = Form.useForm();

  // Initialize form with data
  useMemo(() => {
    form.setFieldsValue(data);
  }, [form, data]);

  // Handle form changes
  const handleValuesChange = useCallback(
    (_: unknown, allValues: Record<string, unknown>) => {
      onChange(allValues);
    },
    [onChange]
  );

  // Infer reference type from field name patterns
  const inferRefType = (fieldName: string): string | null => {
    if (fieldName.includes('npc_template') || fieldName === 'template_id' && schema.title?.toLowerCase().includes('npc')) {
      return 'npcs';
    }
    if (fieldName.includes('item_template') || fieldName.includes('item_id')) {
      return 'items';
    }
    if (fieldName.includes('room_id') || fieldName === 'location') {
      return 'rooms';
    }
    if (fieldName.includes('ability') || fieldName.includes('abilities')) {
      return 'abilities';
    }
    if (fieldName.includes('quest_id')) {
      return 'quests';
    }
    if (fieldName.includes('dialogue_id')) {
      return 'dialogues';
    }
    if (fieldName.includes('class_id') || fieldName === 'required_class') {
      return 'classes';
    }
    return null;
  };

  // Render field based on type
  const renderField = useCallback((name: string, field: SchemaField) => {
    const commonProps = {
      label: name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      name,
      tooltip: field.description,
      rules: field.required ? [{ required: true, message: `${name} is required` }] : [],
    };

    switch (field.type) {
      case 'string':
        if (field.enum) {
          return (
            <Form.Item key={name} {...commonProps}>
              <Select placeholder={`Select ${name}`}>
                {field.enum.map((value: string) => (
                  <Option key={value} value={value}>
                    {value}
                  </Option>
                ))}
              </Select>
            </Form.Item>
          );
        }
        // Check for multiline fields
        if (name.includes('description') || name.includes('text') || name.includes('message')) {
          return (
            <Form.Item key={name} {...commonProps}>
              <TextArea rows={4} placeholder={field.description} />
            </Form.Item>
          );
        }
        // Check for reference fields - add link button
        // Either explicit field.ref or auto-detect from field name patterns
        const inferredRef = field.ref || inferRefType(name);
        if (inferredRef && onNavigateToEntity) {
          const currentValue = data[name] as string | undefined;
          return (
            <Form.Item key={name} {...commonProps}>
              <Space.Compact style={{ width: '100%' }}>
                <Input placeholder={field.description} style={{ flex: 1 }} />
                {currentValue && (
                  <Button
                    type="default"
                    icon={<LinkOutlined />}
                    onClick={() => onNavigateToEntity(inferredRef, currentValue)}
                    title={`Go to ${currentValue}`}
                  />
                )}
              </Space.Compact>
            </Form.Item>
          );
        }
        return (
          <Form.Item key={name} {...commonProps}>
            <Input placeholder={field.description} />
          </Form.Item>
        );

      case 'number':
      case 'integer':
        return (
          <Form.Item key={name} {...commonProps}>
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
        );

      case 'boolean':
        return (
          <Form.Item key={name} {...commonProps} valuePropName="checked">
            <Switch />
          </Form.Item>
        );

      case 'array':
        // Check if this is a reference array (like available_abilities)
        const arrayRefType = field.ref || inferRefType(name);
        if (arrayRefType && worldDataPath) {
          return (
            <Form.Item key={name} {...commonProps}>
              <EntityMultiSelect
                entityType={arrayRefType}
                worldDataPath={worldDataPath}
                placeholder={`Select ${name.replace(/_/g, ' ')}...`}
              />
            </Form.Item>
          );
        }
        
        // Default array handling with Form.List
        return (
          <Form.Item key={name} {...commonProps}>
            <Form.List name={name}>
              {(fields, { add, remove }) => (
                <div className="form-list">
                  {fields.map((listField, index) => (
                    <div key={listField.key} className="form-list-item">
                      <Form.Item
                        {...listField}
                        noStyle
                      >
                        <Input placeholder={`Item ${index + 1}`} style={{ width: 'calc(100% - 40px)' }} />
                      </Form.Item>
                      <Button
                        type="text"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => remove(listField.name)}
                      />
                    </div>
                  ))}
                  <Button type="dashed" onClick={() => add()} icon={<PlusOutlined />} block>
                    Add Item
                  </Button>
                </div>
              )}
            </Form.List>
          </Form.Item>
        );

      case 'object':
        return (
          <Form.Item key={name} {...commonProps}>
            <TextArea
              rows={4}
              placeholder="Enter as JSON object"
            />
          </Form.Item>
        );

      default:
        return (
          <Form.Item key={name} {...commonProps}>
            <Input placeholder={field.description} />
          </Form.Item>
        );
    }
  }, []);

  // Group fields into sections
  const groupedFields = useMemo(() => {
    const groups: Record<string, Array<[string, SchemaField]>> = {
      required: [],
      optional: [],
    };

    for (const [name, field] of Object.entries(schema.fields) as [string, SchemaField][]) {
      if (field.required) {
        groups.required.push([name, field]);
      } else {
        groups.optional.push([name, field]);
      }
    }

    return groups;
  }, [schema.fields]);

  return (
    <div className="form-editor">
      <Card
        title={`Edit ${contentType}`}
        extra={<span className="schema-name">{schema.name}</span>}
      >
        <Form
          form={form}
          layout="vertical"
          onValuesChange={handleValuesChange}
        >
          {/* Required fields */}
          {groupedFields.required.length > 0 && (
            <>
              <Divider orientation="left">Required Fields</Divider>
              {groupedFields.required.map(([name, field]) => renderField(name, field))}
            </>
          )}

          {/* Optional fields */}
          {groupedFields.optional.length > 0 && (
            <>
              <Divider orientation="left">Optional Fields</Divider>
              {groupedFields.optional.map(([name, field]) => renderField(name, field))}
            </>
          )}
        </Form>
      </Card>
    </div>
  );
}
