/**
 * useRoomContents Hook
 * 
 * Manages NPC spawns and item instances for rooms.
 * Handles loading from and saving to YAML files.
 * Uses shared types from types.ts for compatibility with other components.
 */
import { useState, useEffect, useCallback } from 'react';
import yaml from 'js-yaml';
import type { NpcSpawn, ItemInstance, FileEntry } from '../../shared/types';

// ============================================================================
// Types
// ============================================================================

// NPC and Item templates (for dropdowns)
export interface NpcTemplate {
  id: string;
  name: string;
  description?: string;
}

export interface ItemTemplate {
  id: string;
  name: string;
  description?: string;
}

// YAML file structures (what's actually stored in files)
interface NpcSpawnYamlEntry {
  template_id: string;
  room_id: string;
  respawn_time?: number;
  quantity?: number;
  behavior?: string;
  unique?: boolean;
  dialogue_id?: string;
  instance_data?: Record<string, unknown>;
}

interface NpcSpawnFileData {
  spawns: NpcSpawnYamlEntry[];
}

interface ItemInstanceYamlEntry {
  template_id: string;
  room_id?: string;
  quantity?: number;
  location?: string;
  container_id?: string;
  hidden?: boolean;
  locked?: boolean;
  instance_data?: Record<string, unknown>;
}

interface ItemInstanceFileData {
  items: ItemInstanceYamlEntry[];
}

export interface UseRoomContentsResult {
  // Data
  npcSpawns: NpcSpawn[];
  itemInstances: ItemInstance[];
  npcTemplates: NpcTemplate[];
  itemTemplates: ItemTemplate[];
  
  // Loading state
  loading: boolean;
  error: string | null;
  
  // NPC operations
  addNpcSpawn: (roomId: string, spawn: Partial<NpcSpawn>) => Promise<boolean>;
  updateNpcSpawn: (spawnId: string, updates: Partial<NpcSpawn>) => Promise<boolean>;
  removeNpcSpawn: (spawnId: string) => Promise<boolean>;
  getNpcSpawnsForRoom: (roomId: string) => NpcSpawn[];
  
  // Item operations
  addItemInstance: (roomId: string, instance: Partial<ItemInstance>) => Promise<boolean>;
  updateItemInstance: (instanceId: string, updates: Partial<ItemInstance>) => Promise<boolean>;
  removeItemInstance: (instanceId: string) => Promise<boolean>;
  getItemInstancesForRoom: (roomId: string) => ItemInstance[];
  
  // Reload data
  reload: () => Promise<void>;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Generate a unique ID for tracking spawns/instances internally
 */
function generateId(): string {
  return `spawn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Parse NPC spawn YAML file content into shared NpcSpawn type
 */
function parseNpcSpawnFile(content: string, filename: string): NpcSpawn[] {
  try {
    const data = yaml.load(content) as NpcSpawnFileData;
    if (!data || !Array.isArray(data.spawns)) {
      return [];
    }
    
    return data.spawns.map(entry => ({
      spawn_id: generateId(),
      npc_template_id: entry.template_id,
      room_id: entry.room_id,
      quantity: entry.quantity,
      behavior: entry.behavior as NpcSpawn['behavior'],
      respawn_seconds: entry.respawn_time,
      unique: entry.unique,
      dialogue_id: entry.dialogue_id,
      filePath: filename,
    }));
  } catch (err) {
    console.error(`Failed to parse NPC spawn file ${filename}:`, err);
    return [];
  }
}

/**
 * Parse item instance YAML file content into shared ItemInstance type
 */
function parseItemInstanceFile(content: string, filename: string): ItemInstance[] {
  try {
    const data = yaml.load(content) as ItemInstanceFileData;
    if (!data || !Array.isArray(data.items)) {
      return [];
    }
    
    return data.items
      .filter(entry => entry.room_id) // Only include entries with room_id
      .map(entry => ({
        instance_id: generateId(),
        item_template_id: entry.template_id,
        room_id: entry.room_id!,
        quantity: entry.quantity,
        location: entry.location as ItemInstance['location'],
        container_id: entry.container_id,
        hidden: entry.hidden,
        locked: entry.locked,
        filePath: filename,
      }));
  } catch (err) {
    console.error(`Failed to parse item instance file ${filename}:`, err);
    return [];
  }
}

/**
 * Convert NpcSpawn back to YAML entry format
 */
function spawnToYamlEntry(spawn: NpcSpawn): NpcSpawnYamlEntry {
  const entry: NpcSpawnYamlEntry = {
    template_id: spawn.npc_template_id,
    room_id: spawn.room_id,
  };
  if (spawn.respawn_seconds !== undefined) {
    entry.respawn_time = spawn.respawn_seconds;
  }
  if (spawn.quantity !== undefined && spawn.quantity > 1) {
    entry.quantity = spawn.quantity;
  }
  if (spawn.behavior) {
    entry.behavior = spawn.behavior;
  }
  if (spawn.unique) {
    entry.unique = spawn.unique;
  }
  if (spawn.dialogue_id) {
    entry.dialogue_id = spawn.dialogue_id;
  }
  return entry;
}

/**
 * Convert ItemInstance back to YAML entry format
 */
function instanceToYamlEntry(instance: ItemInstance): ItemInstanceYamlEntry {
  const entry: ItemInstanceYamlEntry = {
    template_id: instance.item_template_id,
  };
  if (instance.room_id) {
    entry.room_id = instance.room_id;
  }
  if (instance.quantity !== undefined && instance.quantity > 1) {
    entry.quantity = instance.quantity;
  }
  if (instance.location) {
    entry.location = instance.location;
  }
  if (instance.container_id) {
    entry.container_id = instance.container_id;
  }
  if (instance.hidden) {
    entry.hidden = instance.hidden;
  }
  if (instance.locked) {
    entry.locked = instance.locked;
  }
  return entry;
}

/**
 * Serialize NPC spawns back to YAML format
 */
function serializeNpcSpawns(spawns: NpcSpawn[]): string {
  const data: NpcSpawnFileData = {
    spawns: spawns.map(spawnToYamlEntry),
  };
  
  return yaml.dump(data, { 
    indent: 2,
    lineWidth: -1,
    noRefs: true,
  });
}

/**
 * Serialize item instances back to YAML format
 */
function serializeItemInstances(items: ItemInstance[]): string {
  const data: ItemInstanceFileData = {
    items: items.map(instanceToYamlEntry),
  };
  
  return yaml.dump(data, {
    indent: 2,
    lineWidth: -1,
    noRefs: true,
  });
}

// ============================================================================
// Hook Implementation
// ============================================================================

interface UseRoomContentsOptions {
  worldDataPath: string | null;
  enabled?: boolean;
}

export function useRoomContents(options: UseRoomContentsOptions): UseRoomContentsResult {
  const { worldDataPath, enabled = true } = options;
  const [npcSpawns, setNpcSpawns] = useState<NpcSpawn[]>([]);
  const [itemInstances, setItemInstances] = useState<ItemInstance[]>([]);
  const [npcTemplates, setNpcTemplates] = useState<NpcTemplate[]>([]);
  const [itemTemplates, setItemTemplates] = useState<ItemTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // -------------------------------------------------------------------------
  // Load NPC Templates
  // -------------------------------------------------------------------------
  const loadNpcTemplates = useCallback(async () => {
    if (!worldDataPath) return;
    
    try {
      const npcsPath = `${worldDataPath}/npcs`;
      const entries = await window.daemonswright.fs.listDirectory(npcsPath);
      const yamlFiles = entries.filter(
        (f: FileEntry) => f.isFile && (f.name.endsWith('.yaml') || f.name.endsWith('.yml')) && !f.name.startsWith('_')
      );
      
      const templates: NpcTemplate[] = [];
      for (const entry of yamlFiles) {
        try {
          const content = await window.daemonswright.fs.readFile(entry.path);
          const data = yaml.load(content) as Record<string, unknown>;
          if (data && typeof data === 'object') {
            // NPC files might have id in the content or use filename
            const id = (data.id as string) || entry.name.replace(/\.ya?ml$/, '');
            templates.push({
              id,
              name: (data.name as string) || id,
              description: data.description as string | undefined,
            });
          }
        } catch (err) {
          console.warn(`Failed to load NPC template ${entry.name}:`, err);
        }
      }
      
      setNpcTemplates(templates);
    } catch (err) {
      console.warn('Failed to load NPC templates:', err);
    }
  }, [worldDataPath]);

  // -------------------------------------------------------------------------
  // Load Item Templates
  // -------------------------------------------------------------------------
  const loadItemTemplates = useCallback(async () => {
    if (!worldDataPath) return;
    
    try {
      const itemsPath = `${worldDataPath}/items`;
      const entries = await window.daemonswright.fs.listDirectory(itemsPath);
      const yamlFiles = entries.filter(
        (f: FileEntry) => f.isFile && (f.name.endsWith('.yaml') || f.name.endsWith('.yml')) && !f.name.startsWith('_')
      );
      
      const templates: ItemTemplate[] = [];
      for (const entry of yamlFiles) {
        try {
          const content = await window.daemonswright.fs.readFile(entry.path);
          const data = yaml.load(content) as Record<string, unknown>;
          if (data && typeof data === 'object') {
            const id = (data.id as string) || entry.name.replace(/\.ya?ml$/, '');
            templates.push({
              id,
              name: (data.name as string) || id,
              description: data.description as string | undefined,
            });
          }
        } catch (err) {
          console.warn(`Failed to load item template ${entry.name}:`, err);
        }
      }
      
      setItemTemplates(templates);
    } catch (err) {
      console.warn('Failed to load item templates:', err);
    }
  }, [worldDataPath]);

  // -------------------------------------------------------------------------
  // Load NPC Spawns
  // -------------------------------------------------------------------------
  const loadNpcSpawns = useCallback(async () => {
    if (!worldDataPath) return;
    
    try {
      const spawnsPath = `${worldDataPath}/npc_spawns`;
      const entries = await window.daemonswright.fs.listDirectory(spawnsPath);
      const yamlFiles = entries.filter(
        (f: FileEntry) => f.isFile && (f.name.endsWith('.yaml') || f.name.endsWith('.yml')) && !f.name.startsWith('_')
      );
      
      const allSpawns: NpcSpawn[] = [];
      for (const entry of yamlFiles) {
        try {
          const content = await window.daemonswright.fs.readFile(entry.path);
          const spawns = parseNpcSpawnFile(content, entry.name);
          allSpawns.push(...spawns);
        } catch (err) {
          console.warn(`Failed to load spawn file ${entry.name}:`, err);
        }
      }
      
      setNpcSpawns(allSpawns);
    } catch (err) {
      console.warn('Failed to load NPC spawns:', err);
    }
  }, [worldDataPath]);

  // -------------------------------------------------------------------------
  // Load Item Instances
  // -------------------------------------------------------------------------
  const loadItemInstances = useCallback(async () => {
    if (!worldDataPath) return;
    
    try {
      const instancesPath = `${worldDataPath}/item_instances`;
      const entries = await window.daemonswright.fs.listDirectory(instancesPath);
      const yamlFiles = entries.filter(
        (f: FileEntry) => f.isFile && (f.name.endsWith('.yaml') || f.name.endsWith('.yml')) && !f.name.startsWith('_')
      );
      
      const allInstances: ItemInstance[] = [];
      for (const entry of yamlFiles) {
        try {
          const content = await window.daemonswright.fs.readFile(entry.path);
          const instances = parseItemInstanceFile(content, entry.name);
          allInstances.push(...instances);
        } catch (err) {
          console.warn(`Failed to load item instance file ${entry.name}:`, err);
        }
      }
      
      setItemInstances(allInstances);
    } catch (err) {
      console.warn('Failed to load item instances:', err);
    }
  }, [worldDataPath]);

  // -------------------------------------------------------------------------
  // Main Load Function
  // -------------------------------------------------------------------------
  const reload = useCallback(async () => {
    if (!worldDataPath) return;
    
    setLoading(true);
    setError(null);
    
    try {
      await Promise.all([
        loadNpcTemplates(),
        loadItemTemplates(),
        loadNpcSpawns(),
        loadItemInstances(),
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load room contents';
      setError(message);
      console.error('Failed to load room contents:', err);
    } finally {
      setLoading(false);
    }
  }, [worldDataPath, loadNpcTemplates, loadItemTemplates, loadNpcSpawns, loadItemInstances]);

  // Load on mount and when path changes (only if enabled)
  useEffect(() => {
    if (enabled) {
      reload();
    }
  }, [reload, enabled]);

  // -------------------------------------------------------------------------
  // Save Spawns to File
  // -------------------------------------------------------------------------
  const saveSpawnsToFile = useCallback(async (filename: string, spawns: NpcSpawn[]) => {
    if (!worldDataPath) return;
    
    const spawnsPath = `${worldDataPath}/npc_spawns/${filename}`;
    const content = serializeNpcSpawns(spawns);
    await window.daemonswright.fs.writeFile(spawnsPath, content);
  }, [worldDataPath]);

  // -------------------------------------------------------------------------
  // Save Item Instances to File
  // -------------------------------------------------------------------------
  const saveItemsToFile = useCallback(async (filename: string, items: ItemInstance[]) => {
    if (!worldDataPath) return;
    
    const instancesPath = `${worldDataPath}/item_instances/${filename}`;
    const content = serializeItemInstances(items);
    await window.daemonswright.fs.writeFile(instancesPath, content);
  }, [worldDataPath]);

  // -------------------------------------------------------------------------
  // NPC Spawn Operations
  // -------------------------------------------------------------------------
  const addNpcSpawn = useCallback(async (
    roomId: string, 
    spawn: Partial<NpcSpawn>
  ): Promise<boolean> => {
    if (!worldDataPath || !spawn.npc_template_id) return false;
    
    // Default to editor_spawns.yaml for new spawns
    const filename = 'editor_spawns.yaml';
    
    const newSpawn: NpcSpawn = {
      spawn_id: generateId(),
      npc_template_id: spawn.npc_template_id,
      room_id: roomId,
      quantity: spawn.quantity || 1,
      behavior: spawn.behavior || 'stationary',
      respawn_seconds: spawn.respawn_seconds || 0,
      unique: spawn.unique,
      dialogue_id: spawn.dialogue_id,
      filePath: filename,
    };
    
    // Update local state
    const updatedSpawns = [...npcSpawns, newSpawn];
    setNpcSpawns(updatedSpawns);
    
    // Group spawns by file and save
    try {
      const spawnsForFile = updatedSpawns.filter(s => s.filePath === filename);
      await saveSpawnsToFile(filename, spawnsForFile);
      return true;
    } catch (err) {
      console.error('Failed to save NPC spawn:', err);
      // Revert on error
      setNpcSpawns(npcSpawns);
      return false;
    }
  }, [worldDataPath, npcSpawns, saveSpawnsToFile]);

  const updateNpcSpawn = useCallback(async (
    spawnId: string, 
    updates: Partial<NpcSpawn>
  ): Promise<boolean> => {
    const spawn = npcSpawns.find(s => s.spawn_id === spawnId);
    if (!spawn) return false;
    
    const updatedSpawn = { ...spawn, ...updates };
    const updatedSpawns = npcSpawns.map(s => s.spawn_id === spawnId ? updatedSpawn : s);
    setNpcSpawns(updatedSpawns);
    
    // Save to file
    try {
      const filename = spawn.filePath || 'editor_spawns.yaml';
      const spawnsForFile = updatedSpawns.filter(s => s.filePath === filename);
      await saveSpawnsToFile(filename, spawnsForFile);
      return true;
    } catch (err) {
      console.error('Failed to update NPC spawn:', err);
      setNpcSpawns(npcSpawns);
      return false;
    }
  }, [npcSpawns, saveSpawnsToFile]);

  const removeNpcSpawn = useCallback(async (spawnId: string): Promise<boolean> => {
    const spawn = npcSpawns.find(s => s.spawn_id === spawnId);
    if (!spawn) return false;
    
    const updatedSpawns = npcSpawns.filter(s => s.spawn_id !== spawnId);
    setNpcSpawns(updatedSpawns);
    
    // Save to file
    try {
      const filename = spawn.filePath || 'editor_spawns.yaml';
      const spawnsForFile = updatedSpawns.filter(s => s.filePath === filename);
      await saveSpawnsToFile(filename, spawnsForFile);
      return true;
    } catch (err) {
      console.error('Failed to remove NPC spawn:', err);
      setNpcSpawns(npcSpawns);
      return false;
    }
  }, [npcSpawns, saveSpawnsToFile]);

  const getNpcSpawnsForRoom = useCallback((roomId: string): NpcSpawn[] => {
    return npcSpawns.filter(spawn => spawn.room_id === roomId);
  }, [npcSpawns]);

  // -------------------------------------------------------------------------
  // Item Instance Operations
  // -------------------------------------------------------------------------
  const addItemInstance = useCallback(async (
    roomId: string, 
    instance: Partial<ItemInstance>
  ): Promise<boolean> => {
    if (!worldDataPath || !instance.item_template_id) return false;
    
    const filename = 'editor_items.yaml';
    
    const newInstance: ItemInstance = {
      instance_id: generateId(),
      item_template_id: instance.item_template_id,
      room_id: roomId,
      quantity: instance.quantity ?? 1,
      location: instance.location || 'ground',
      container_id: instance.container_id,
      hidden: instance.hidden,
      locked: instance.locked,
      filePath: filename,
    };
    
    const updatedInstances = [...itemInstances, newInstance];
    setItemInstances(updatedInstances);
    
    try {
      const itemsForFile = updatedInstances.filter(i => i.filePath === filename);
      await saveItemsToFile(filename, itemsForFile);
      return true;
    } catch (err) {
      console.error('Failed to save item instance:', err);
      setItemInstances(itemInstances);
      return false;
    }
  }, [worldDataPath, itemInstances, saveItemsToFile]);

  const updateItemInstance = useCallback(async (
    instanceId: string, 
    updates: Partial<ItemInstance>
  ): Promise<boolean> => {
    const instance = itemInstances.find(i => i.instance_id === instanceId);
    if (!instance) return false;
    
    const updatedInstance = { ...instance, ...updates };
    const updatedInstances = itemInstances.map(i => i.instance_id === instanceId ? updatedInstance : i);
    setItemInstances(updatedInstances);
    
    try {
      const filename = instance.filePath || 'editor_items.yaml';
      const itemsForFile = updatedInstances.filter(i => i.filePath === filename);
      await saveItemsToFile(filename, itemsForFile);
      return true;
    } catch (err) {
      console.error('Failed to update item instance:', err);
      setItemInstances(itemInstances);
      return false;
    }
  }, [itemInstances, saveItemsToFile]);

  const removeItemInstance = useCallback(async (instanceId: string): Promise<boolean> => {
    const instance = itemInstances.find(i => i.instance_id === instanceId);
    if (!instance) return false;
    
    const updatedInstances = itemInstances.filter(i => i.instance_id !== instanceId);
    setItemInstances(updatedInstances);
    
    try {
      const filename = instance.filePath || 'editor_items.yaml';
      const itemsForFile = updatedInstances.filter(i => i.filePath === filename);
      await saveItemsToFile(filename, itemsForFile);
      return true;
    } catch (err) {
      console.error('Failed to remove item instance:', err);
      setItemInstances(itemInstances);
      return false;
    }
  }, [itemInstances, saveItemsToFile]);

  const getItemInstancesForRoom = useCallback((roomId: string): ItemInstance[] => {
    return itemInstances.filter(instance => instance.room_id === roomId);
  }, [itemInstances]);

  // -------------------------------------------------------------------------
  // Return Hook Result
  // -------------------------------------------------------------------------
  return {
    // Data
    npcSpawns,
    itemInstances,
    npcTemplates,
    itemTemplates,
    
    // Loading state
    loading,
    error,
    
    // NPC operations
    addNpcSpawn,
    updateNpcSpawn,
    removeNpcSpawn,
    getNpcSpawnsForRoom,
    
    // Item operations
    addItemInstance,
    updateItemInstance,
    removeItemInstance,
    getItemInstancesForRoom,
    
    // Reload
    reload,
  };
}
