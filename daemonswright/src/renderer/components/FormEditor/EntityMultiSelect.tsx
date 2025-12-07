/**
 * EntityMultiSelect Component
 *
 * A multi-select component that loads available entities from a folder
 * and allows selecting multiple entity IDs.
 */

import { Select, Spin } from 'antd';
import { useEntityOptions } from '../../hooks/useEntityOptions';

const { Option } = Select;

interface EntityMultiSelectProps {
  value?: string[];
  onChange?: (value: string[]) => void;
  entityType: string;
  worldDataPath: string | null;
  placeholder?: string;
}

export function EntityMultiSelect({
  value = [],
  onChange,
  entityType,
  worldDataPath,
  placeholder,
}: EntityMultiSelectProps) {
  const { options, loading } = useEntityOptions(worldDataPath, entityType);

  return (
    <Select
      mode="multiple"
      value={value}
      onChange={onChange}
      placeholder={placeholder || `Select ${entityType}...`}
      loading={loading}
      showSearch
      optionFilterProp="children"
      style={{ width: '100%' }}
      notFoundContent={loading ? <Spin size="small" /> : 'No options found'}
    >
      {options.map((option) => (
        <Option key={option.id} value={option.id}>
          {option.name !== option.id ? `${option.name} (${option.id})` : option.id}
        </Option>
      ))}
    </Select>
  );
}
