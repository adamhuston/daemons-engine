/**
 * WorldSummary Component
 *
 * Displays a summary of the loaded world_data folder content,
 * showing counts of each content type (NPCs, Items, Abilities, etc.)
 */

import { useState, useEffect, useMemo } from 'react';
import { Card, Row, Col, Statistic, Typography, Space, Spin } from 'antd';
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
} from '@ant-design/icons';
import './WorldSummary.css';

const { Title, Text } = Typography;

interface ContentCount {
  key: string;
  label: string;
  icon: React.ReactNode;
  folder: string;
  count: number;
}

interface WorldSummaryProps {
  worldDataPath: string;
}

// Content types to count
const CONTENT_TYPES = [
  { key: 'rooms', label: 'Rooms', icon: <HomeOutlined />, folder: 'rooms' },
  { key: 'npcs', label: 'NPCs', icon: <UserOutlined />, folder: 'npcs' },
  { key: 'items', label: 'Items', icon: <GiftOutlined />, folder: 'items' },
  { key: 'abilities', label: 'Abilities', icon: <ThunderboltOutlined />, folder: 'abilities' },
  { key: 'classes', label: 'Classes', icon: <TeamOutlined />, folder: 'classes' },
  { key: 'quests', label: 'Quests', icon: <FlagOutlined />, folder: 'quests' },
  { key: 'dialogues', label: 'Dialogues', icon: <CommentOutlined />, folder: 'dialogues' },
  { key: 'flora', label: 'Flora', icon: <span role="img" aria-label="flora">🌿</span>, folder: 'flora' },
  { key: 'fauna', label: 'Fauna', icon: <BugOutlined />, folder: 'npcs/fauna' },
  { key: 'areas', label: 'Areas', icon: <EnvironmentOutlined />, folder: 'areas' },
  { key: 'triggers', label: 'Triggers', icon: <ThunderboltOutlined />, folder: 'triggers' },
];

export function WorldSummary({ worldDataPath }: WorldSummaryProps) {
  const [contentCounts, setContentCounts] = useState<ContentCount[]>([]);
  const [loading, setLoading] = useState(true);

  // Extract the folder name from the path for display
  const folderName = useMemo(() => {
    const parts = worldDataPath.split(/[/\\]/);
    return parts[parts.length - 1] || 'world_data';
  }, [worldDataPath]);

  // Count YAML files in each content folder
  useEffect(() => {
    async function countContent() {
      if (!window.daemonswright?.fs) {
        setLoading(false);
        return;
      }

      setLoading(true);
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
        });
      }

      setContentCounts(counts);
      setLoading(false);
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

  if (loading) {
    return (
      <div className="world-summary loading">
        <Spin size="large" />
        <Text type="secondary">Loading world data...</Text>
      </div>
    );
  }

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
              <Card className="world-summary-card" hoverable>
                <Statistic
                  title={content.label}
                  value={content.count}
                  prefix={content.icon}
                />
              </Card>
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
