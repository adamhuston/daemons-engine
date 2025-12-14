/**
 * Shared Type Definitions
 *
 * Types used by both main and renderer processes.
 */

// File system types
export interface FileEntry {
  name: string;
  path: string;
  isDirectory: boolean;
  isFile: boolean;
}

export interface FileSystemAPI {
  openFolder: () => Promise<string | null>;
  selectSaveFolder: (defaultName?: string) => Promise<string | null>;
  createDirectory: (dirPath: string) => Promise<boolean>;
  listDirectory: (dirPath: string) => Promise<FileEntry[]>;
  readFile: (filePath: string) => Promise<string>;
  fileExists: (filePath: string) => Promise<boolean>;
  writeFile: (filePath: string, content: string) => Promise<boolean>;
  deleteFile: (filePath: string) => Promise<boolean>;
  watchDirectory: (dirPath: string) => Promise<boolean>;
  unwatchDirectory: (dirPath: string) => Promise<boolean>;
  onFileChange: (callback: (event: string, path: string) => void) => void;
}

// Schema types
export interface SchemaField {
  type: string;
  description?: string;
  required?: boolean;
  default?: unknown;
  enum?: string[];
  ref?: string; // Reference to another content type
}

export interface SchemaDefinition {
  name: string;
  description?: string;
  fields: Record<string, SchemaField>;
  examples?: unknown[];
}

export interface ValidationError {
  line?: number;
  column?: number;
  message: string;
  severity?: 'error' | 'warning' | 'info';
  field?: string;
  filePath?: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
}

export interface SchemaAPI {
  loadSchemas: (worldDataPath: string) => Promise<Record<string, SchemaDefinition>>;
  validateContent: (content: string, contentType: string) => Promise<ValidationResult>;
  getSchemaForType: (contentType: string) => Promise<SchemaDefinition | null>;
}

// Server connection types
export interface ServerConnectionResult {
  connected: boolean;
  url: string;
}

export interface ServerAPI {
  connect: (url: string) => Promise<ServerConnectionResult>;
  disconnect: () => Promise<boolean>;
  isConnected: () => Promise<boolean>;
  hotReload: (contentType: string) => Promise<unknown>;
  validateEnhanced: (content: string, contentType: string) => Promise<ValidationResult>;
}

// Content types (matching Daemons engine)
export type ContentType =
  | 'abilities'
  | 'areas'
  | 'classes'
  | 'dialogues'
  | 'factions'
  | 'item_instances'
  | 'items'
  | 'npc_spawns'
  | 'npcs'
  | 'quest_chains'
  | 'quests'
  | 'rooms'
  | 'triggers';

// Door state for exits (matches backend DoorState dataclass)
export interface DoorState {
  is_open: boolean; // Whether the door is open (passable)
  is_locked: boolean; // Whether the door requires unlocking
  key_item_id?: string; // Item template ID that can unlock this door
  door_name?: string; // Custom display name (e.g., "iron gate", "wooden door")
}

// Time phase definitions for areas
export interface TimePhase {
  name: string; // e.g., 'night', 'morning', 'day', 'evening'
  ambient_text?: string; // Flavor text shown during this phase
  lighting?: string; // Override lighting for this phase
}

// Area types (matching Daemons engine Area model)
export interface Area {
  id: string;
  name: string;
  description?: string;
  time_scale?: number; // Day/night cycle speed multiplier
  biome?: string; // e.g., 'mystical', 'forest', 'cave', 'desert'
  climate?: string; // e.g., 'temperate', 'arctic', 'tropical'
  ambient_lighting?: string; // e.g., 'dim', 'bright', 'pitch_black', 'normal'
  weather_profile?: string; // Weather system configuration
  danger_level?: number; // 1-10 scale
  magic_intensity?: string; // e.g., 'none', 'low', 'moderate', 'high', 'extreme'
  ambient_sound?: string; // Background audio identifier
  default_respawn_time?: number; // Seconds for NPC/item respawn
  time_phases?: TimePhase[]; // Custom time phase configurations
  entry_points?: string[]; // Room IDs where players can spawn
  starting_day?: number; // Initial game day
  starting_hour?: number; // Initial hour (0-23)
  starting_minute?: number; // Initial minute (0-59)
  filePath?: string; // Original file path where the area was loaded from
}

// Room builder types
export interface RoomNode {
  id: string;
  room_id: string;
  name: string;
  description?: string;
  room_type?: string;
  area_id?: string;
  z_level: number;
  exits: Record<string, string>;
  doors?: Record<string, DoorState>; // Door states keyed by exit direction
  position: { x: number; y: number };
  filePath?: string; // Original file path where the room was loaded from
}

export interface RoomConnection {
  id: string;
  source: string;
  target: string;
  sourceHandle: string; // direction (north, south, etc.)
  targetHandle: string;
  bidirectional?: boolean; // true if both rooms have exits to each other
  door?: DoorState; // Door state on the source exit (if any)
}

// NPC Spawn types - represents an NPC placed in a room
export interface NpcSpawn {
  spawn_id: string;
  npc_template_id: string;
  room_id: string;
  quantity?: number;
  behavior?: 'stationary' | 'patrol' | 'wander' | 'guard' | 'merchant';
  respawn_seconds?: number;
  unique?: boolean;
  dialogue_id?: string;
  filePath?: string; // Source file for this spawn entry
}

// Item Instance types - represents an item placed in a room
export interface ItemInstance {
  instance_id: string;
  item_template_id: string;
  room_id: string;
  quantity?: number;
  location?: 'ground' | 'table' | 'shelf' | 'hidden' | 'container';
  container_id?: string;
  hidden?: boolean;
  locked?: boolean;
  filePath?: string; // Source file for this instance entry
}

// Editor state
export interface EditorState {
  currentFile: string | null;
  content: string;
  isDirty: boolean;
  validationErrors: ValidationError[];
}

// Application state
export interface AppState {
  worldDataPath: string | null;
  isServerConnected: boolean;
  serverUrl: string | null;
  schemas: Record<string, SchemaDefinition>;
  currentEditor: EditorState;
}

// Settings API
export interface SettingsAPI {
  getLastFolder: () => Promise<string | null>;
  getRecentFolders: () => Promise<string[]>;
  addRecentFolder: (folderPath: string) => Promise<boolean>;
}

// Window API exposed via preload
export interface DaemonswrightAPI {
  fs: FileSystemAPI;
  schema: SchemaAPI;
  server: ServerAPI;
  settings: SettingsAPI;
}

// Extend window type
declare global {
  interface Window {
    daemonswright: DaemonswrightAPI;
  }
}
