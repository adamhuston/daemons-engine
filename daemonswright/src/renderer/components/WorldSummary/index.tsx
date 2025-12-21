/**
 * WorldSummary Component
 *
 * Displays a summary of the loaded world_data folder content,
 * showing counts of each content type (NPCs, Items, Abilities, etc.)
 * 
 * Stats blocks are clickable navigation components that take users
 * to the appropriate editor view for that content type.
 */

import { useState, useEffect, useMemo } from 'react';
import { Card, Row, Col, Statistic, Typography, Space, Tooltip } from 'antd';
import {
  UserOutlined,
  GiftOutlined,
  ThunderboltOutlined,
  HomeOutlined,
  TeamOutlined,
  CommentOutlined,
  FlagOutlined,
  BugOutlined,
  EnvironmentOutlined,
  RightOutlined,
} from '@ant-design/icons';
import '../../../shared/types'; // Import for Window type augmentation
import './WorldSummary.css';

const { Title, Text } = Typography;

// Define which view each content type navigates to
type EditorView = 'yaml' | 'room-builder' | 'entity-editor' | 'quest-designer' | 'dialogue-editor';

interface NavigationTarget {
  view: EditorView;
  category?: string; // For entity-editor, specifies which category to select
}

interface ContentCount {
  key: string;
  label: string;
  icon: React.ReactNode;
  folder: string;
  count: number;
  navigation: NavigationTarget;
}

interface WorldSummaryProps {
  worldDataPath: string;
  onNavigate?: (view: EditorView, category?: string) => void;
}

// Content types to count with their navigation targets
const CONTENT_TYPES: Omit<ContentCount, 'count'>[] = [
  { key: 'rooms', label: 'Rooms', icon: <HomeOutlined />, folder: 'rooms', navigation: { view: 'room-builder' } },
  { key: 'npcs', label: 'NPCs', icon: <UserOutlined />, folder: 'npcs', navigation: { view: 'entity-editor', category: 'npcs' } },
  { key: 'items', label: 'Items', icon: <GiftOutlined />, folder: 'items', navigation: { view: 'entity-editor', category: 'items' } },
  { key: 'abilities', label: 'Abilities', icon: <ThunderboltOutlined />, folder: 'abilities', navigation: { view: 'entity-editor', category: 'abilities' } },
  { key: 'classes', label: 'Classes', icon: <TeamOutlined />, folder: 'classes', navigation: { view: 'entity-editor', category: 'classes' } },
  { key: 'quests', label: 'Quests', icon: <FlagOutlined />, folder: 'quests', navigation: { view: 'quest-designer' } },
  { key: 'dialogues', label: 'Dialogues', icon: <CommentOutlined />, folder: 'dialogues', navigation: { view: 'dialogue-editor' } },
  { key: 'biomes', label: 'Biomes', icon: <span role="img" aria-label="biome">🌍</span>, folder: 'biomes', navigation: { view: 'entity-editor', category: 'biomes' } },
  { key: 'flora', label: 'Flora', icon: <span role="img" aria-label="flora">🌿</span>, folder: 'flora', navigation: { view: 'entity-editor', category: 'flora' } },
  { key: 'fauna', label: 'Fauna', icon: <BugOutlined />, folder: 'npcs/fauna', navigation: { view: 'entity-editor', category: 'fauna' } },
  { key: 'areas', label: 'Areas', icon: <EnvironmentOutlined />, folder: 'areas', navigation: { view: 'room-builder' } },
  { key: 'triggers', label: 'Triggers', icon: <ThunderboltOutlined />, folder: 'triggers', navigation: { view: 'entity-editor', category: 'triggers' } },
];

export function WorldSummary({ worldDataPath, onNavigate }: WorldSummaryProps) {
  const [contentCounts, setContentCounts] = useState<ContentCount[]>([]);

  // Extract the folder name from the path for display
  const folderName = useMemo(() => {
    const parts = worldDataPath.split(/[/\\]/);
    return parts[parts.length - 1] || 'world_data';
  }, [worldDataPath]);

  // Count YAML files in each content folder
  useEffect(() => {
    async function countContent() {
      if (!window.daemonswright?.fs) {
        return;
      }

      const counts: ContentCount[] = [];

      for (const contentType of CONTENT_TYPES) {
        const folderPath = `${worldDataPath}/${contentType.folder}`;
        let count = 0;

        try {
          // Recursively count YAML files
          const countYamlFiles = async (dirPath: string): Promise<number> => {
            let total = 0;
            try {
              const entries = await window.daemonswright.fs.listDirectory(dirPath);
              for (const entry of entries) {
                if (entry.isDirectory) {
                  total += await countYamlFiles(entry.path);
                } else if (entry.name.endsWith('.yaml') || entry.name.endsWith('.yml')) {
                  total += 1;
                }
              }
            } catch {
              // Folder doesn't exist or can't be read
            }
            return total;
          };

          count = await countYamlFiles(folderPath);
        } catch {
          // Folder doesn't exist
        }

        counts.push({
          ...contentType,
          count,
        } as ContentCount);
      }

      setContentCounts(counts);
    }

    countContent();
  }, [worldDataPath]);

  // Filter to only show content types that have items
  const nonEmptyCounts = useMemo(
    () => contentCounts.filter((c) => c.count > 0),
    [contentCounts]
  );

  // Calculate total content count
  const totalCount = useMemo(
    () => contentCounts.reduce((sum, c) => sum + c.count, 0),
    [contentCounts]
  );

  return (
    <div className="world-summary">
      <div className="world-summary-header">
        <Title level={2}>📁 {folderName}</Title>
        <Text type="secondary">
          {totalCount > 0
            ? `${totalCount} content files loaded`
            : 'No content files found'}
        </Text>
      </div>

      {nonEmptyCounts.length > 0 ? (
        <Row gutter={[16, 16]} className="world-summary-grid">
          {nonEmptyCounts.map((content) => (
            <Col xs={12} sm={8} md={6} lg={4} key={content.key}>
              <Tooltip title={`Open ${content.label} in editor`}>
                <Card 
                  className="world-summary-card" 
                  hoverable
                  onClick={() => onNavigate?.(content.navigation.view, content.navigation.category)}
                >
                  <Statistic
                    title={
                      <span className="card-title-with-arrow">
                        {content.label}
                        <RightOutlined className="navigate-arrow" />
                      </span>
                    }
                    value={content.count}
                    prefix={content.icon}
                  />
                </Card>
              </Tooltip>
            </Col>
          ))}
        </Row>
      ) : (
        <div className="world-summary-empty">
          <Text type="secondary">
            This folder appears to be empty. Use the menu to switch to a different view
            and start creating content.
          </Text>
        </div>
      )}

      <div className="world-summary-hint">
        <Space direction="vertical" size="small">
          <Text type="secondary">
            💡 <strong>Tip:</strong> Use the View menu to switch between editors:
          </Text>
          <ul className="hint-list">
            <li><strong>Room Builder</strong> - Visual map editor for rooms and connections</li>
            <li><strong>Entity Editor</strong> - Create and edit NPCs, items, abilities</li>
            <li><strong>Quest Designer</strong> - Design quest chains and objectives</li>
            <li><strong>Dialogue Editor</strong> - Write branching conversations</li>
          </ul>
          <Text type="secondary">
            Or click a file in the sidebar to edit it directly.
          </Text>
        </Space>
      </div>
    </div>
  );
}

export default WorldSummary;
