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
  listDirectory: (dirPath: string) => Promise<FileEntry[]>;
  readFile: (filePath: string) => Promise<string>;
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
  position: { x: number; y: number };
}

export interface RoomConnection {
  id: string;
  source: string;
  target: string;
  sourceHandle: string; // direction (north, south, etc.)
  targetHandle: string;
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
