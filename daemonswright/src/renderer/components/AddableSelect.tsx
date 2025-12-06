/**
 * AddableSelect Component
 * 
 * A Select dropdown that allows adding new options.
 * Shows a "Add new..." option at the bottom that opens a modal to add a custom value.
 */

import { useState } from 'react';
import { Select, Modal, Input, message } from 'antd';
import { PlusOutlined } from '@ant-design/icons';

interface AddableSelectProps {
  value?: string;
  onChange?: (value: string) => void;
  options: string[];
  onAddOption: (newOption: string) => Promise<boolean>;
  placeholder?: string;
  style?: React.CSSProperties;
  disabled?: boolean;
}

export function AddableSelect({
  value,
  onChange,
  options,
  onAddOption,
  placeholder = 'Select...',
  style,
  disabled = false,
}: AddableSelectProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newOptionValue, setNewOptionValue] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  // Format option for display (capitalize, replace underscores)
  const formatLabel = (option: string) => {
    return option
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  // Build select options including "Add new..."
  const selectOptions = [
    ...options.map((opt) => ({
      value: opt,
      label: formatLabel(opt),
    })),
    {
      value: '__add_new__',
      label: (
        <span style={{ color: '#1890ff' }}>
          <PlusOutlined /> Add new...
        </span>
      ),
    },
  ];

  const handleSelect = (selectedValue: string) => {
    if (selectedValue === '__add_new__') {
      setIsModalOpen(true);
    } else {
      onChange?.(selectedValue);
    }
  };

  const handleAddOption = async () => {
    if (!newOptionValue.trim()) {
      message.error('Please enter a value');
      return;
    }

    // Normalize the value (lowercase, replace spaces with underscores)
    const normalizedValue = newOptionValue.trim().toLowerCase().replace(/\s+/g, '_');

    // Check if already exists
    if (options.includes(normalizedValue)) {
      message.warning('This option already exists');
      onChange?.(normalizedValue);
      setIsModalOpen(false);
      setNewOptionValue('');
      return;
    }

    setIsAdding(true);
    try {
      const success = await onAddOption(normalizedValue);
      if (success) {
        message.success(`Added "${normalizedValue}" to options`);
        onChange?.(normalizedValue);
        setIsModalOpen(false);
        setNewOptionValue('');
      } else {
        message.error('Failed to add option');
      }
    } finally {
      setIsAdding(false);
    }
  };

  return (
    <>
      <Select
        value={value}
        onChange={handleSelect}
        options={selectOptions}
        placeholder={placeholder}
        style={style}
        disabled={disabled}
      />
      <Modal
        title="Add New Option"
        open={isModalOpen}
        onOk={handleAddOption}
        onCancel={() => {
          setIsModalOpen(false);
          setNewOptionValue('');
        }}
        okText="Add"
        confirmLoading={isAdding}
      >
        <Input
          value={newOptionValue}
          onChange={(e) => setNewOptionValue(e.target.value)}
          placeholder="Enter new option value..."
          onPressEnter={handleAddOption}
          autoFocus
        />
        <div style={{ marginTop: 8, color: '#888', fontSize: 12 }}>
          Will be saved as: <code>{newOptionValue.trim().toLowerCase().replace(/\s+/g, '_') || '...'}</code>
        </div>
      </Modal>
    </>
  );
}
