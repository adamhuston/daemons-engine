/**
 * FormEditor Component
 *
 * Auto-generated form editor for content types that don't need
 * visual graph representation (items, NPCs, abilities, classes, etc.)
 */

import { useCallback, useMemo } from 'react';
import { Form, Input, InputNumber, Select, Switch, Card, Button, Divider } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import type { SchemaDefinition, SchemaField } from '../../shared/types';

const { TextArea } = Input;
const { Option } = Select;

interface FormEditorProps {
  schema: SchemaDefinition;
  data: Record<string, unknown>;
  onChange: (data: Record<string, unknown>) => void;
  contentType: string;
}

export function FormEditor({ schema, data, onChange, contentType }: FormEditorProps) {
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
                {field.enum.map((value) => (
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

    for (const [name, field] of Object.entries(schema.fields)) {
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
