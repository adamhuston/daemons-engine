/**
 * Loader / Start Screen Component
 *
 * Animated start screen for Daemonswright CMS.
 * Features the DWCMS logo and options to create/open worlds.
 */

/// <reference path="../../assets.d.ts" />

import React, { useState, useEffect, useCallback } from 'react';
import { Button, Space, Tooltip, Typography, Divider, List } from 'antd';
import {
  PlusOutlined,
  FolderOpenOutlined,
  HistoryOutlined,
  RightOutlined,
} from '@ant-design/icons';
import logoImage from '../../assets/images/dw-art.png';
import './Loader.css';

const { Text, Title } = Typography;

interface LoaderProps {
  /** Optional loading message to display */
  message?: string;
  /** Whether to show as fullscreen overlay */
  fullscreen?: boolean;
  /** Whether to show a subtle background */
  transparent?: boolean;
}

export function Loader({
  message = 'Loading...',
  fullscreen = true,
  transparent = false,
}: LoaderProps) {
  return (
    <div className={`loader-container ${fullscreen ? 'fullscreen' : ''} ${transparent ? 'transparent' : ''}`}>
      <div className="loader-content minimal">
        {/* Logo with ominous glow - nothing else */}
        <div className="loader-logo-wrapper">
          <div className="loader-glow-red" />
          <img
            src={logoImage}
            alt="Daemonswright CMS"
            className="loader-logo"
          />
        </div>
      </div>
    </div>
  );
}

/**
 * Inline loader for smaller loading states
 */
export function InlineLoader({ message = 'Loading...' }: { message?: string }) {
  return (
    <div className="inline-loader">
      <div className="loader-dots small">
        <span className="dot" />
        <span className="dot" />
        <span className="dot" />
      </div>
      {message && <span className="inline-loader-message">{message}</span>}
    </div>
  );
}

/**
 * Start Screen - Main entry point for the app
 *
 * Shows options to:
 * - Create a new world
 * - Open an existing world
 * - Continue with the last opened world
 */
interface StartScreenProps {
  /** Callback when a world is selected/created */
  onWorldSelect: (worldPath: string) => Promise<void>;
  /** Optional last opened folder path */
  lastFolder?: string | null;
  /** Recent folders list */
  recentFolders?: string[];
  /** Whether currently loading */
  isLoading?: boolean;
}

export function StartScreen({
  onWorldSelect,
  lastFolder,
  recentFolders = [],
  isLoading = false,
}: StartScreenProps) {
  const [creating, setCreating] = useState(false);
  const [opening, setOpening] = useState(false);
  const [showRecent, setShowRecent] = useState(false);

  // Create a new world with starter schemas
  const handleNewWorld = useCallback(async () => {
    setCreating(true);
    try {
      // Let user choose where to save the new world
      const savePath = await window.daemonswright.fs.selectSaveFolder('world_data');
      if (!savePath) {
        setCreating(false);
        return;
      }

      // Create the directory structure
      await window.daemonswright.fs.createDirectory(savePath);

      // Create subdirectories for content types
      const subdirs = [
        'abilities',
        'areas',
        'biomes',
        'classes',
        'dialogues',
        'factions',
        'flora',
        'item_instances',
        'items',
        'npc_spawns',
        'npcs',
        'quest_chains',
        'quests',
        'rooms',
        'triggers',
      ];

      for (const subdir of subdirs) {
        await window.daemonswright.fs.createDirectory(`${savePath}/${subdir}`);
      }

      // Create starter schema files
      await createStarterSchemas(savePath);

      // Open the new world
      await onWorldSelect(savePath);
    } catch (error) {
      console.error('Failed to create new world:', error);
    } finally {
      setCreating(false);
    }
  }, [onWorldSelect]);

  // Open existing world folder
  const handleOpenWorld = useCallback(async () => {
    setOpening(true);
    try {
      const folderPath = await window.daemonswright.fs.openFolder();
      if (folderPath) {
        await onWorldSelect(folderPath);
      }
    } catch (error) {
      console.error('Failed to open world:', error);
    } finally {
      setOpening(false);
    }
  }, [onWorldSelect]);

  // Continue with last world
  const handleContinue = useCallback(async () => {
    if (lastFolder) {
      await onWorldSelect(lastFolder);
    }
  }, [lastFolder, onWorldSelect]);

  // Open a specific recent folder
  const handleOpenRecent = useCallback(async (folderPath: string) => {
    await onWorldSelect(folderPath);
  }, [onWorldSelect]);

  // Extract folder name from path
  const getFolderName = (path: string) => {
    const parts = path.split(/[/\\]/);
    return parts[parts.length - 1] || path;
  };

  return (
    <div className="start-screen">
      <div className="start-screen-content">
        {/* Logo section - featured prominently with ominous glow */}
        <div className="start-logo-section">
          <div className="start-logo-wrapper">
            <div className="loader-glow-red" />
            <img
              src={logoImage}
              alt="Daemonswright CMS"
              className="start-logo"
            />
          </div>

          <div className="start-text">
            <Title level={1} className="start-title">D&AElig;MONSWRIGHT</Title>
          </div>
        </div>

        {/* Action buttons */}
        <div className="start-actions">
          {lastFolder && (
            <>
              <div className="continue-section">
                <Button
                  type="primary"
                  size="large"
                  icon={<RightOutlined />}
                  onClick={handleContinue}
                  className="start-button continue"
                  loading={isLoading}
                >
                  Continue
                </Button>
                <span className="continue-subtitle">{getFolderName(lastFolder)}</span>
              </div>
              <Divider className="start-divider">or</Divider>
            </>
          )}

          <Space size="middle" className="start-button-group">
            <Tooltip title="Create a new world_data folder with starter schemas">
              <Button
                size="large"
                icon={<PlusOutlined />}
                onClick={handleNewWorld}
                loading={creating}
                className="start-button"
              >
                New World
              </Button>
            </Tooltip>

            <Tooltip title="Open an existing world_data folder">
              <Button
                size="large"
                icon={<FolderOpenOutlined />}
                onClick={handleOpenWorld}
                loading={opening}
                className="start-button"
              >
                Open World
              </Button>
            </Tooltip>

            {recentFolders.length > 0 && (
              <Tooltip title="Open a recently used world">
                <Button
                  size="large"
                  icon={<HistoryOutlined />}
                  onClick={() => setShowRecent(!showRecent)}
                  className="start-button"
                >
                  Recent
                </Button>
              </Tooltip>
            )}
          </Space>

          {/* Recent folders list */}
          {showRecent && recentFolders.length > 0 && (
            <div className="recent-folders">
              <List
                size="small"
                dataSource={recentFolders.slice(0, 5)}
                renderItem={(folder) => (
                  <List.Item
                    className="recent-folder-item"
                    onClick={() => handleOpenRecent(folder)}
                  >
                    <FolderOpenOutlined style={{ marginRight: 8 }} />
                    <div className="recent-folder-info">
                      <Text strong>{getFolderName(folder)}</Text>
                      <Text type="secondary" ellipsis style={{ fontSize: 11 }}>
                        {folder}
                      </Text>
                    </div>
                  </List.Item>
                )}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="start-footer">
          <Text type="secondary">
            ⛧ Ultra secret underground build ⛧
          </Text>
        </div>
      </div>
    </div>
  );
}

/**
 * Create starter schema files for a new world
 */
async function createStarterSchemas(worldPath: string): Promise<void> {
  // Room schema
  const roomSchema = `# Room Schema
# Defines the structure for room definitions

name: Room
description: A location in the game world

fields:
  id:
    type: string
    required: true
    description: Unique identifier for the room

  name:
    type: string
    required: true
    description: Display name shown to players

  description:
    type: string
    required: true
    description: The text shown when a player enters the room

  room_type:
    type: string
    enum:
      - ethereal
      - forest
      - cave
      - urban
      - chamber
      - corridor
      - outdoor
      - indoor
      - dungeon
      - shop
      - inn
      - temple
      - water
    description: The type/biome of the room

  area_id:
    type: string
    ref: areas
    description: Reference to the parent area

  z_level:
    type: integer
    default: 0
    description: Vertical layer (floor level)

  exits:
    type: object
    description: Map of direction to destination room_id

  lighting_override:
    type: string
    enum:
      - pitch_black
      - dim
      - normal
      - bright
      - prismatic
    description: Override the area's default lighting
`;

  // NPC schema
  const npcSchema = `# NPC Schema
# Defines non-player characters

name: NPC
description: A non-player character template

fields:
  id:
    type: string
    required: true
    description: Unique identifier for the NPC

  name:
    type: string
    required: true
    description: Display name of the NPC

  description:
    type: string
    description: Description shown when examining the NPC

  npc_type:
    type: string
    enum:
      - humanoid
      - beast
      - undead
      - elemental
      - construct
      - celestial
      - fiend
    description: The creature type

  level:
    type: integer
    default: 1
    description: NPC level for scaling

  faction_id:
    type: string
    ref: factions
    description: The faction this NPC belongs to

  dialogue_id:
    type: string
    ref: dialogues
    description: Reference to conversation tree
`;

  // Item schema
  const itemSchema = `# Item Schema
# Defines item templates

name: Item
description: An item template that can be instanced in the world

fields:
  id:
    type: string
    required: true
    description: Unique identifier for the item

  name:
    type: string
    required: true
    description: Display name of the item

  description:
    type: string
    description: Description shown when examining

  item_type:
    type: string
    enum:
      - weapon
      - armor
      - consumable
      - key
      - quest
      - misc
      - container
    description: Category of item

  value:
    type: integer
    default: 0
    description: Base gold value

  weight:
    type: number
    default: 0.1
    description: Weight in pounds

  stackable:
    type: boolean
    default: false
    description: Whether multiple can stack in inventory
`;

  // Write schema files
  await window.daemonswright.fs.writeFile(`${worldPath}/rooms/_schema.yaml`, roomSchema);
  await window.daemonswright.fs.writeFile(`${worldPath}/npcs/_schema.yaml`, npcSchema);
  await window.daemonswright.fs.writeFile(`${worldPath}/items/_schema.yaml`, itemSchema);

  // Create a starter room
  const starterRoom = `# Your first room!
# Edit this file or use the Room Builder to create your world

id: starting_room
name: The Beginning
description: |
  You find yourself in a simple room. The walls are bare stone,
  but there's potential here. This is where your world begins.
room_type: chamber
area_id: starter_area
z_level: 0
exits: {}
`;

  // Create a starter area
  const starterArea = `# Starter Area
# Areas group rooms together

id: starter_area
name: Starter Area
description: The starting zone for new adventurers
`;

  await window.daemonswright.fs.writeFile(`${worldPath}/rooms/starter_area/starting_room.yaml`, starterRoom);
  await window.daemonswright.fs.writeFile(`${worldPath}/areas/starter_area.yaml`, starterArea);
}

/**
 * App Loader - Handles loading transition
 *
 * Shows a loader while the app is initializing, with a minimum display time
 * for smooth transitions.
 */
interface AppLoaderProps {
  /** Whether the app is still loading */
  isLoading: boolean;
  /** Minimum time to show the loader in milliseconds */
  minDisplayTime?: number;
  /** Loading message */
  message?: string;
  /** Children to render when loading is complete */
  children: React.ReactNode;
}

export function AppLoader({
  isLoading,
  minDisplayTime = 1500,
  message = 'Loading...',
  children,
}: AppLoaderProps) {
  const [showLoader, setShowLoader] = useState(true);
  const [minTimeElapsed, setMinTimeElapsed] = useState(false);

  // Start the minimum display timer on mount
  useEffect(() => {
    const timer = setTimeout(() => {
      setMinTimeElapsed(true);
    }, minDisplayTime);

    return () => clearTimeout(timer);
  }, [minDisplayTime]);

  // Transition from loader to content
  useEffect(() => {
    if (!isLoading && minTimeElapsed) {
      // Small delay for smooth transition
      const timer = setTimeout(() => {
        setShowLoader(false);
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [isLoading, minTimeElapsed]);

  if (showLoader) {
    return <Loader message={message} fullscreen transparent={!isLoading && minTimeElapsed} />;
  }

  return <>{children}</>;
}

export default Loader;
