/**
 * EntityEditor Component
 *
 * A tabbed interface for editing game entities (NPCs, Items, Abilities, etc.)
 * Uses the FormEditor component for schema-driven form generation.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Layout, Menu, List, Button, Input, Empty, Card, Spin, message, Modal, Form, Segmented } from 'antd';
import {
  UserOutlined,
  GiftOutlined,
  ThunderboltOutlined,
  PlusOutlined,
  SearchOutlined,
  DeleteOutlined,
  SaveOutlined,
  FormOutlined,
  CodeOutlined,
  TeamOutlined,
  BugOutlined,
} from '@ant-design/icons';
import yaml from 'js-yaml';
import { FormEditor } from '../FormEditor';
import { YamlEditor } from '../YamlEditor';
import { TriggerBuilder } from '../TriggerBuilder';
import type { SchemaDefinition, FileEntry } from '../../../shared/types';
import './EntityEditor.css';

const { Sider, Content } = Layout;
const { Search } = Input;

// Entity categories and their configurations
interface EntityCategory {
  key: string;
  label: string;
  icon: React.ReactNode;
  folder: string; // Folder name under world_data
  schemaId: string; // Schema ID to use
  useCustomEditor?: boolean; // Use a custom editor instead of FormEditor
}

const ENTITY_CATEGORIES: EntityCategory[] = [
  { key: 'npcs', label: 'NPCs', icon: <UserOutlined />, folder: 'npcs', schemaId: 'npcs' },
  { key: 'items', label: 'Items', icon: <GiftOutlined />, folder: 'items', schemaId: 'items' },
  { key: 'abilities', label: 'Abilities', icon: <ThunderboltOutlined />, folder: 'abilities', schemaId: 'abilities' },
  { key: 'classes', label: 'Classes', icon: <TeamOutlined />, folder: 'classes', schemaId: 'classes' },
  { key: 'triggers', label: 'Triggers', icon: <ThunderboltOutlined />, folder: 'triggers', schemaId: 'triggers', useCustomEditor: true },
  { key: 'flora', label: 'Flora', icon: <span role="img" aria-label="flora">🌿</span>, folder: 'flora', schemaId: 'flora' },
  { key: 'fauna', label: 'Fauna', icon: <BugOutlined />, folder: 'npcs/fauna', schemaId: 'npcs' },
];

interface EntityFile {
  name: string;
  path: string;
  data: Record<string, unknown>;
  isDirty: boolean;
}

interface EntityEditorProps {
  worldDataPath: string | null;
  schemas: Record<string, SchemaDefinition>;
}

export function EntityEditor({ worldDataPath, schemas }: EntityEditorProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>('npcs');
  const [entities, setEntities] = useState<EntityFile[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<EntityFile | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createForm] = Form.useForm();
  const [viewMode, setViewMode] = useState<'form' | 'yaml'>('form');
  const [yamlContent, setYamlContent] = useState<string>('');

  // Get the current category config
  const currentCategory = useMemo(
    () => ENTITY_CATEGORIES.find((c) => c.key === selectedCategory) || ENTITY_CATEGORIES[0],
    [selectedCategory]
  );

  // Get the schema for the current category
  const currentSchema = useMemo(() => {
    console.log('[EntityEditor] Available schemas:', Object.keys(schemas));
    console.log('[EntityEditor] Looking for schema:', currentCategory.schemaId);
    const schema = schemas[currentCategory.schemaId];
    console.log('[EntityEditor] Found schema:', schema ? 'yes' : 'no');
    return schema;
  }, [schemas, currentCategory]);

  // Load entities when category or path changes
  const loadEntities = useCallback(async () => {
    if (!worldDataPath) return;

    setLoading(true);
    try {
      const folderPath = `${worldDataPath}/${currentCategory.folder}`;
      
      // Recursively scan for YAML files, including subdirectories
      const scanDirectory = async (dirPath: string): Promise<FileEntry[]> => {
        const entries = await window.daemonswright.fs.listDirectory(dirPath);
        const results: FileEntry[] = [];
        
        for (const entry of entries) {
          if (entry.isFile && (entry.name.endsWith('.yaml') || entry.name.endsWith('.yml')) && !entry.name.startsWith('_')) {
            results.push(entry);
          } else if (!entry.isFile && !entry.name.startsWith('_') && !entry.name.startsWith('.')) {
            // Recursively scan subdirectories
            const subEntries = await scanDirectory(entry.path);
            results.push(...subEntries);
          }
        }
        
        return results;
      };
      
      const yamlFiles = await scanDirectory(folderPath);

      const loadedEntities: EntityFile[] = [];
      for (const entry of yamlFiles) {
        try {
          const content = await window.daemonswright.fs.readFile(entry.path);
          const data = yaml.load(content) as Record<string, unknown>;
          
          // Generate a display name that includes subdirectory path
          const relativePath = entry.path.replace(folderPath + '/', '').replace(/\.ya?ml$/, '');
          
          loadedEntities.push({
            name: relativePath,
            path: entry.path,
            data: data || {},
            isDirty: false,
          });
        } catch (err) {
          console.warn(`Failed to load entity file ${entry.name}:`, err);
        }
      }

      setEntities(loadedEntities);
      // Clear selection when switching categories
      setSelectedEntity(null);
    } catch (err) {
      console.warn(`Failed to load entities from ${currentCategory.folder}:`, err);
      setEntities([]);
    } finally {
      setLoading(false);
    }
  }, [worldDataPath, currentCategory]);

  useEffect(() => {
    loadEntities();
  }, [loadEntities]);

  // Sync YAML content when entity is selected or data changes
  useEffect(() => {
    if (selectedEntity) {
      const content = yaml.dump(selectedEntity.data, {
        indent: 2,
        lineWidth: -1,
        noRefs: true,
      });
      setYamlContent(content);
    } else {
      setYamlContent('');
    }
  }, [selectedEntity?.data, selectedEntity?.path]);

  // Filter entities by search query
  const filteredEntities = useMemo(() => {
    if (!searchQuery) return entities;
    const query = searchQuery.toLowerCase();
    return entities.filter(
      (e) =>
        e.name.toLowerCase().includes(query) ||
        ((e.data.name as string) || '').toLowerCase().includes(query)
    );
  }, [entities, searchQuery]);

  // Handle entity selection
  const handleSelectEntity = useCallback(
    (entity: EntityFile) => {
      if (selectedEntity?.isDirty) {
        Modal.confirm({
          title: 'Unsaved Changes',
          content: 'You have unsaved changes. Do you want to discard them?',
          onOk: () => setSelectedEntity(entity),
        });
      } else {
        setSelectedEntity(entity);
      }
    },
    [selectedEntity]
  );

  // Handle entity data change (from form)
  const handleEntityChange = useCallback(
    (newData: Record<string, unknown>) => {
      if (!selectedEntity) return;

      setSelectedEntity({
        ...selectedEntity,
        data: newData,
        isDirty: true,
      });

      // Update in the entities list too
      setEntities((prev) =>
        prev.map((e) => (e.path === selectedEntity.path ? { ...e, data: newData, isDirty: true } : e))
      );
    },
    [selectedEntity]
  );

  // Handle YAML content change (from code editor)
  const handleYamlChange = useCallback(
    (newContent: string) => {
      if (!selectedEntity) return;

      setYamlContent(newContent);

      // Try to parse the YAML and update the data
      try {
        const newData = yaml.load(newContent) as Record<string, unknown>;
        if (newData && typeof newData === 'object') {
          setSelectedEntity({
            ...selectedEntity,
            data: newData,
            isDirty: true,
          });

          setEntities((prev) =>
            prev.map((e) => (e.path === selectedEntity.path ? { ...e, data: newData, isDirty: true } : e))
          );
        }
      } catch {
        // YAML parse error - mark as dirty but don't update data
        setSelectedEntity({
          ...selectedEntity,
          isDirty: true,
        });
      }
    },
    [selectedEntity]
  );

  // Handle navigation to a referenced entity
  const handleNavigateToEntity = useCallback(
    async (refType: string, entityId: string) => {
      // Find the category that matches the ref type
      const targetCategory = ENTITY_CATEGORIES.find((c) => c.key === refType);
      if (!targetCategory) {
        message.warning(`Unknown reference type: ${refType}`);
        return;
      }

      // If we need to switch categories, do that first
      if (selectedCategory !== targetCategory.key) {
        setSelectedCategory(targetCategory.key);
        // Wait for entities to load after category switch
        await new Promise((resolve) => setTimeout(resolve, 100));
      }

      // Now we need to find the entity with this ID in the current entities list
      // This is tricky because entities might not be loaded yet - we'll search after a short delay
      const findAndSelectEntity = () => {
        // Search for the entity by checking if its name or template_id matches
        const found = entities.find((e) => {
          const templateId = e.data.template_id || e.data.id || e.name.replace('.yaml', '');
          return templateId === entityId || e.name === `${entityId}.yaml`;
        });

        if (found) {
          handleSelectEntity(found);
        } else {
          message.info(`Entity "${entityId}" not found in ${targetCategory.label}`);
        }
      };

      // If we switched categories, wait for load
      if (selectedCategory !== targetCategory.key) {
        setTimeout(findAndSelectEntity, 500);
      } else {
        findAndSelectEntity();
      }
    },
    [selectedCategory, entities, handleSelectEntity]
  );

  // Save the current entity
  const handleSave = useCallback(async () => {
    if (!selectedEntity) return;

    try {
      const content = yaml.dump(selectedEntity.data, {
        indent: 2,
        lineWidth: -1,
        noRefs: true,
      });
      await window.daemonswright.fs.writeFile(selectedEntity.path, content);

      // Update state to mark as clean
      setSelectedEntity({ ...selectedEntity, isDirty: false });
      setEntities((prev) =>
        prev.map((e) => (e.path === selectedEntity.path ? { ...e, isDirty: false } : e))
      );

      message.success(`Saved ${selectedEntity.name}`);
    } catch (err) {
      console.error('Failed to save entity:', err);
      message.error('Failed to save entity');
    }
  }, [selectedEntity]);

  // Create new entity
  const handleCreate = useCallback(async () => {
    if (!worldDataPath) return;

    try {
      const values = createForm.getFieldsValue();
      const id = values.id || `new_${currentCategory.key.slice(0, -1)}`;
      const filename = `${id}.yaml`;
      const filePath = `${worldDataPath}/${currentCategory.folder}/${filename}`;

      // Create initial data with id and name
      const initialData: Record<string, unknown> = {
        id,
        name: values.name || id,
      };

      const content = yaml.dump(initialData, {
        indent: 2,
        lineWidth: -1,
        noRefs: true,
      });

      await window.daemonswright.fs.writeFile(filePath, content);

      // Reload entities
      await loadEntities();

      // Select the new entity
      const newEntity = entities.find((e) => e.path === filePath);
      if (newEntity) {
        setSelectedEntity(newEntity);
      }

      setCreateModalOpen(false);
      createForm.resetFields();
      message.success(`Created ${filename}`);
    } catch (err) {
      console.error('Failed to create entity:', err);
      message.error('Failed to create entity');
    }
  }, [worldDataPath, currentCategory, createForm, loadEntities, entities]);

  // Delete entity
  const handleDelete = useCallback(async () => {
    if (!selectedEntity) return;

    Modal.confirm({
      title: 'Delete Entity',
      content: `Are you sure you want to delete "${selectedEntity.name}"?`,
      okText: 'Delete',
      okType: 'danger',
      onOk: async () => {
        try {
          await window.daemonswright.fs.deleteFile(selectedEntity.path);
          setSelectedEntity(null);
          await loadEntities();
          message.success(`Deleted ${selectedEntity.name}`);
        } catch (err) {
          console.error('Failed to delete entity:', err);
          message.error('Failed to delete entity');
        }
      },
    });
  }, [selectedEntity, loadEntities]);

  // Handle category change
  const handleCategoryChange = useCallback(
    (key: string) => {
      if (selectedEntity?.isDirty) {
        Modal.confirm({
          title: 'Unsaved Changes',
          content: 'You have unsaved changes. Do you want to discard them?',
          onOk: () => {
            setSelectedCategory(key);
          },
        });
      } else {
        setSelectedCategory(key);
      }
    },
    [selectedEntity]
  );

  if (!worldDataPath) {
    return (
      <div className="entity-editor-empty">
        <Empty description="Open a world_data folder to edit entities" />
      </div>
    );
  }

  return (
    <Layout className="entity-editor">
      {/* Category tabs on the left */}
      <Sider width={200} className="entity-categories">
        <Menu
          mode="inline"
          selectedKeys={[selectedCategory]}
          onSelect={({ key }) => handleCategoryChange(key)}
          items={ENTITY_CATEGORIES.map((cat) => ({
            key: cat.key,
            icon: cat.icon,
            label: cat.label,
          }))}
        />
      </Sider>

      {/* Entity list */}
      <Sider width={250} className="entity-list-sider">
        <div className="entity-list-header">
          <Search
            placeholder={`Search ${currentCategory.label.toLowerCase()}...`}
            prefix={<SearchOutlined />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            allowClear
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateModalOpen(true)}
            style={{ marginTop: 8 }}
            block
          >
            New {currentCategory.label.slice(0, -1)}
          </Button>
        </div>

        <Spin spinning={loading}>
          <List
            className="entity-list"
            dataSource={filteredEntities}
            renderItem={(entity) => (
              <List.Item
                className={`entity-list-item ${selectedEntity?.path === entity.path ? 'selected' : ''} ${
                  entity.isDirty ? 'dirty' : ''
                }`}
                onClick={() => handleSelectEntity(entity)}
              >
                <div className="entity-list-item-content">
                  <span className="entity-name">
                    {entity.isDirty && <span className="dirty-indicator">•</span>}
                    {(entity.data.name as string) || entity.name}
                  </span>
                  <span className="entity-id">{entity.name}</span>
                </div>
              </List.Item>
            )}
            locale={{ emptyText: <Empty description={`No ${currentCategory.label.toLowerCase()} found`} /> }}
          />
        </Spin>
      </Sider>

      {/* Entity editor */}
      <Content className="entity-editor-content">
        {selectedEntity ? (
          <div className="entity-form-container">
            <div className="entity-form-header">
              <div className="entity-form-title">
                <h2>
                  {(selectedEntity.data.name as string) || selectedEntity.name}
                  {selectedEntity.isDirty && <span className="dirty-marker"> (unsaved)</span>}
                </h2>
              </div>
              <div className="entity-form-actions">
                <Segmented
                  value={viewMode}
                  onChange={(value) => setViewMode(value as 'form' | 'yaml')}
                  options={[
                    { label: 'Form', value: 'form', icon: <FormOutlined /> },
                    { label: 'YAML', value: 'yaml', icon: <CodeOutlined /> },
                  ]}
                  style={{ marginRight: 16 }}
                />
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  onClick={handleSave}
                  disabled={!selectedEntity.isDirty}
                >
                  Save
                </Button>
                <Button danger icon={<DeleteOutlined />} onClick={handleDelete}>
                  Delete
                </Button>
              </div>
            </div>

            {viewMode === 'form' ? (
              currentCategory.useCustomEditor && currentCategory.key === 'triggers' ? (
                <TriggerBuilder
                  data={selectedEntity.data}
                  onChange={handleEntityChange}
                />
              ) : currentSchema ? (
                <FormEditor
                  schema={currentSchema}
                  data={selectedEntity.data}
                  onChange={handleEntityChange}
                  contentType={currentCategory.label.slice(0, -1)}
                  onNavigateToEntity={handleNavigateToEntity}
                  worldDataPath={worldDataPath}
                />
              ) : (
                <Card>
                  <Empty description={`No schema found for ${currentCategory.label}`} />
                </Card>
              )
            ) : (
              <div className="entity-yaml-editor">
                <YamlEditor
                  filePath={selectedEntity.path}
                  content={yamlContent}
                  onChange={handleYamlChange}
                  validationErrors={[]}
                  schemas={schemas}
                  onNavigateToEntity={handleNavigateToEntity}
                />
              </div>
            )}
          </div>
        ) : (
          <div className="entity-editor-placeholder">
            <Empty
              description={`Select a ${currentCategory.label.slice(0, -1).toLowerCase()} to edit, or create a new one`}
            />
          </div>
        )}
      </Content>

      {/* Create modal */}
      <Modal
        title={`Create New ${currentCategory.label.slice(0, -1)}`}
        open={createModalOpen}
        onOk={handleCreate}
        onCancel={() => {
          setCreateModalOpen(false);
          createForm.resetFields();
        }}
        okText="Create"
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="id"
            label="ID"
            rules={[
              { required: true, message: 'Please enter an ID' },
              { pattern: /^[a-z0-9_]+$/, message: 'ID must be lowercase letters, numbers, and underscores' },
            ]}
          >
            <Input placeholder="e.g., iron_sword, goblin_warrior" />
          </Form.Item>
          <Form.Item name="name" label="Display Name">
            <Input placeholder="e.g., Iron Sword, Goblin Warrior" />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
}
