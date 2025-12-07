/**
 * ContentPalette Component
 *
 * Left sidebar for Room Builder that displays draggable NPC and Item templates.
 * Users can drag templates onto room nodes to create spawns/instances.
 */

import { useState, useMemo, useCallback } from 'react';
import { Tabs, Input, List, Card, Empty, Tooltip, Tag } from 'antd';
import { UserOutlined, ShoppingOutlined, SearchOutlined, DragOutlined } from '@ant-design/icons';
import type { NpcTemplate, ItemTemplate } from '../../hooks/useRoomContents';
import './ContentPalette.css';

const { Search } = Input;

// Drag data types for identifying what's being dragged
export const DRAG_TYPE_NPC = 'application/x-npc-template';
export const DRAG_TYPE_ITEM = 'application/x-item-template';

export interface ContentPaletteProps {
  npcTemplates: NpcTemplate[];
  itemTemplates: ItemTemplate[];
  loading?: boolean;
}

/**
 * Single draggable NPC template card
 */
function NpcTemplateCard({ template }: { template: NpcTemplate }) {
  const handleDragStart = useCallback((e: React.DragEvent) => {
    // Set the drag data - the template ID
    e.dataTransfer.setData(DRAG_TYPE_NPC, template.id);
    e.dataTransfer.effectAllowed = 'copy';
    
    // Create a custom drag image
    const dragImage = document.createElement('div');
    dragImage.className = 'drag-ghost';
    dragImage.innerHTML = `<span>👤 ${template.name}</span>`;
    dragImage.style.cssText = `
      position: absolute;
      top: -1000px;
      background: #1f1f1f;
      color: #52c41a;
      padding: 8px 12px;
      border-radius: 4px;
      border: 1px solid #52c41a;
      font-size: 12px;
      white-space: nowrap;
    `;
    document.body.appendChild(dragImage);
    e.dataTransfer.setDragImage(dragImage, 0, 0);
    
    // Clean up drag ghost after drag ends
    setTimeout(() => {
      document.body.removeChild(dragImage);
    }, 0);
  }, [template]);

  return (
    <Card
      size="small"
      className="palette-card npc-card"
      draggable
      onDragStart={handleDragStart}
    >
      <div className="palette-card-content">
        <div className="palette-card-icon">
          <UserOutlined />
        </div>
        <div className="palette-card-info">
          <div className="palette-card-name">{template.name}</div>
          <div className="palette-card-id">{template.id}</div>
        </div>
        <div className="palette-card-drag">
          <Tooltip title="Drag to room">
            <DragOutlined />
          </Tooltip>
        </div>
      </div>
    </Card>
  );
}

/**
 * Single draggable Item template card
 */
function ItemTemplateCard({ template }: { template: ItemTemplate }) {
  const handleDragStart = useCallback((e: React.DragEvent) => {
    // Set the drag data - the template ID
    e.dataTransfer.setData(DRAG_TYPE_ITEM, template.id);
    e.dataTransfer.effectAllowed = 'copy';
    
    // Create a custom drag image
    const dragImage = document.createElement('div');
    dragImage.className = 'drag-ghost';
    dragImage.innerHTML = `<span>📦 ${template.name}</span>`;
    dragImage.style.cssText = `
      position: absolute;
      top: -1000px;
      background: #1f1f1f;
      color: #faad14;
      padding: 8px 12px;
      border-radius: 4px;
      border: 1px solid #faad14;
      font-size: 12px;
      white-space: nowrap;
    `;
    document.body.appendChild(dragImage);
    e.dataTransfer.setDragImage(dragImage, 0, 0);
    
    // Clean up drag ghost after drag ends
    setTimeout(() => {
      document.body.removeChild(dragImage);
    }, 0);
  }, [template]);

  return (
    <Card
      size="small"
      className="palette-card item-card"
      draggable
      onDragStart={handleDragStart}
    >
      <div className="palette-card-content">
        <div className="palette-card-icon">
          <ShoppingOutlined />
        </div>
        <div className="palette-card-info">
          <div className="palette-card-name">{template.name}</div>
          <div className="palette-card-id">{template.id}</div>
        </div>
        <div className="palette-card-drag">
          <Tooltip title="Drag to room">
            <DragOutlined />
          </Tooltip>
        </div>
      </div>
    </Card>
  );
}

/**
 * Main ContentPalette component
 */
export function ContentPalette({
  npcTemplates,
  itemTemplates,
  loading = false,
}: ContentPaletteProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState<'npcs' | 'items'>('npcs');

  // Filter NPCs by search term
  const filteredNpcs = useMemo(() => {
    if (!searchTerm.trim()) return npcTemplates;
    const term = searchTerm.toLowerCase();
    return npcTemplates.filter(
      (npc) =>
        npc.name.toLowerCase().includes(term) ||
        npc.id.toLowerCase().includes(term) ||
        (npc.description && npc.description.toLowerCase().includes(term))
    );
  }, [npcTemplates, searchTerm]);

  // Filter Items by search term
  const filteredItems = useMemo(() => {
    if (!searchTerm.trim()) return itemTemplates;
    const term = searchTerm.toLowerCase();
    return itemTemplates.filter(
      (item) =>
        item.name.toLowerCase().includes(term) ||
        item.id.toLowerCase().includes(term) ||
        (item.description && item.description.toLowerCase().includes(term))
    );
  }, [itemTemplates, searchTerm]);

  const tabItems = [
    {
      key: 'npcs',
      label: (
        <span>
          <UserOutlined /> NPCs
          <Tag className="count-tag">{filteredNpcs.length}</Tag>
        </span>
      ),
      children: (
        <div className="palette-list">
          {filteredNpcs.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={searchTerm ? 'No NPCs match search' : 'No NPC templates found'}
            />
          ) : (
            <List
              dataSource={filteredNpcs}
              renderItem={(npc) => (
                <List.Item key={npc.id} className="palette-list-item">
                  <NpcTemplateCard template={npc} />
                </List.Item>
              )}
              loading={loading}
            />
          )}
        </div>
      ),
    },
    {
      key: 'items',
      label: (
        <span>
          <ShoppingOutlined /> Items
          <Tag className="count-tag">{filteredItems.length}</Tag>
        </span>
      ),
      children: (
        <div className="palette-list">
          {filteredItems.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={searchTerm ? 'No items match search' : 'No item templates found'}
            />
          ) : (
            <List
              dataSource={filteredItems}
              renderItem={(item) => (
                <List.Item key={item.id} className="palette-list-item">
                  <ItemTemplateCard template={item} />
                </List.Item>
              )}
              loading={loading}
            />
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="content-palette">
      <div className="palette-header">
        <h3>Content Palette</h3>
        <p className="palette-hint">Drag items to rooms</p>
      </div>

      <div className="palette-search">
        <Search
          placeholder="Search templates..."
          prefix={<SearchOutlined />}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          allowClear
        />
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as 'npcs' | 'items')}
        items={tabItems}
        className="palette-tabs"
      />
    </div>
  );
}
