/**
 * useRoomContents Hook
 *
 * Manages NPC spawns and item instances for rooms in the Room Builder.
 * Reads from npc_spawns/*.yaml and item_instances/*.yaml files,
 * and provides CRUD operations for placing/removing content from rooms.
 */

import { useState, useCallback, useEffect, useMemo } from 'react';
import type { NpcSpawn, ItemInstance } from '../../shared/types';

// Template types (simplified for room builder display)
export interface NpcTemplate {
  id: string;
  name: string;
  description?: string;
  npc_type?: string;
}

export interface ItemTemplate {
  id: string;
  name: string;
  description?: string;
  item_type?: string;
}

interface UseRoomContentsOptions {
  worldDataPath: string | null;
  enabled?: boolean;
}

interface UseRoomContentsResult {
  // NPC data
  npcSpawns: NpcSpawn[];
  npcTemplates: NpcTemplate[];
  npcSpawnsLoading: boolean;
  
  // Item data
  itemInstances: ItemInstance[];
  itemTemplates: ItemTemplate[];
  itemInstancesLoading: boolean;
  
  // NPC operations
  addNpcSpawn: (roomId: string, spawn: Partial<NpcSpawn>) => Promise<boolean>;
  updateNpcSpawn: (spawnId: string, updates: Partial<NpcSpawn>) => Promise<boolean>;
  removeNpcSpawn: (spawnId: string) => Promise<boolean>;
  
  // Item operations
  addItemInstance: (roomId: string, instance: Partial<ItemInstance>) => Promise<boolean>;
  updateItemInstance: (instanceId: string, updates: Partial<ItemInstance>) => Promise<boolean>;
  removeItemInstance: (instanceId: string) => Promise<boolean>;
  
  // Utility
  getSpawnsForRoom: (roomId: string) => NpcSpawn[];
  getItemsForRoom: (roomId: string) => ItemInstance[];
  refreshContent: () => Promise<void>;
}

/**
 * Hook for managing room contents (NPCs and items).
 * 
 * This hook:
 * 1. Loads NPC spawns from npc_spawns/*.yaml
 * 2. Loads item instances from item_instances/*.yaml
 * 3. Loads templates from npcs/*.yaml and items/*.yaml for display names
 * 4. Provides CRUD operations that write back to YAML files
 */
export function useRoomContents({
  worldDataPath,
  enabled = true,
}: UseRoomContentsOptions): UseRoomContentsResult {
  // State for spawns/instances
  const [npcSpawns, setNpcSpawns] = useState<NpcSpawn[]>([]);
  const [itemInstances, setItemInstances] = useState<ItemInstance[]>([]);
  
  // State for templates (for display purposes)
  const [npcTemplates, setNpcTemplates] = useState<NpcTemplate[]>([]);
  const [itemTemplates, setItemTemplates] = useState<ItemTemplate[]>([]);
  
  // Loading states
  const [npcSpawnsLoading, setNpcSpawnsLoading] = useState(false);
  const [itemInstancesLoading, setItemInstancesLoading] = useState(false);

  /**
   * Load all NPC spawns from npc_spawns directory
   */
  const loadNpcSpawns = useCallback(async () => {
    if (!worldDataPath || !enabled) return;
    
    setNpcSpawnsLoading(true);
    try {
      const spawnsPath = `${worldDataPath}/npc_spawns`;
      
      // Check if directory exists
      const entries = await window.daemonswright.fs.listDirectory(spawnsPath);
      
      const allSpawns: NpcSpawn[] = [];
      
      for (const entry of entries) {
        if (entry.isFile && entry.name.endsWith('.yaml')) {
          try {
            const content = await window.daemonswright.fs.readFile(entry.path);
            // Parse YAML content
            // TODO: Use actual YAML parser
            const parsed = parseYamlSpawns(content, entry.path);
            allSpawns.push(...parsed);
          } catch (err) {
            console.warn(`Failed to parse spawn file: ${entry.path}`, err);
          }
        }
      }
      
      setNpcSpawns(allSpawns);
    } catch (err) {
      console.error('Failed to load NPC spawns:', err);
      setNpcSpawns([]);
    } finally {
      setNpcSpawnsLoading(false);
    }
  }, [worldDataPath, enabled]);

  /**
   * Load all item instances from item_instances directory
   */
  const loadItemInstances = useCallback(async () => {
    if (!worldDataPath || !enabled) return;
    
    setItemInstancesLoading(true);
    try {
      const instancesPath = `${worldDataPath}/item_instances`;
      
      // Check if directory exists
      const entries = await window.daemonswright.fs.listDirectory(instancesPath);
      
      const allInstances: ItemInstance[] = [];
      
      for (const entry of entries) {
        if (entry.isFile && entry.name.endsWith('.yaml')) {
          try {
            const content = await window.daemonswright.fs.readFile(entry.path);
            // Parse YAML content
            // TODO: Use actual YAML parser
            const parsed = parseYamlInstances(content, entry.path);
            allInstances.push(...parsed);
          } catch (err) {
            console.warn(`Failed to parse instance file: ${entry.path}`, err);
          }
        }
      }
      
      setItemInstances(allInstances);
    } catch (err) {
      console.error('Failed to load item instances:', err);
      setItemInstances([]);
    } finally {
      setItemInstancesLoading(false);
    }
  }, [worldDataPath, enabled]);

  /**
   * Load NPC templates for display names
   */
  const loadNpcTemplates = useCallback(async () => {
    if (!worldDataPath || !enabled) return;
    
    try {
      const npcsPath = `${worldDataPath}/npcs`;
      const entries = await window.daemonswright.fs.listDirectory(npcsPath);
      
      const templates: NpcTemplate[] = [];
      
      for (const entry of entries) {
        if (entry.isFile && entry.name.endsWith('.yaml') && !entry.name.startsWith('_')) {
          try {
            const content = await window.daemonswright.fs.readFile(entry.path);
            const parsed = parseYamlTemplate(content);
            if (parsed) {
              templates.push({
                id: parsed.id || entry.name.replace('.yaml', ''),
                name: parsed.name || entry.name.replace('.yaml', ''),
                description: parsed.description,
                npc_type: parsed.npc_type,
              });
            }
          } catch (err) {
            console.warn(`Failed to parse NPC template: ${entry.path}`, err);
          }
        }
      }
      
      setNpcTemplates(templates);
    } catch (err) {
      console.error('Failed to load NPC templates:', err);
    }
  }, [worldDataPath, enabled]);

  /**
   * Load item templates for display names
   */
  const loadItemTemplates = useCallback(async () => {
    if (!worldDataPath || !enabled) return;
    
    try {
      const itemsPath = `${worldDataPath}/items`;
      const entries = await window.daemonswright.fs.listDirectory(itemsPath);
      
      const templates: ItemTemplate[] = [];
      
      for (const entry of entries) {
        if (entry.isFile && entry.name.endsWith('.yaml') && !entry.name.startsWith('_')) {
          try {
            const content = await window.daemonswright.fs.readFile(entry.path);
            const parsed = parseYamlTemplate(content);
            if (parsed) {
              templates.push({
                id: parsed.id || entry.name.replace('.yaml', ''),
                name: parsed.name || entry.name.replace('.yaml', ''),
                description: parsed.description,
                item_type: parsed.item_type,
              });
            }
          } catch (err) {
            console.warn(`Failed to parse item template: ${entry.path}`, err);
          }
        }
      }
      
      setItemTemplates(templates);
    } catch (err) {
      console.error('Failed to load item templates:', err);
    }
  }, [worldDataPath, enabled]);

  // Initial load
  useEffect(() => {
    if (worldDataPath && enabled) {
      loadNpcSpawns();
      loadItemInstances();
      loadNpcTemplates();
      loadItemTemplates();
    }
  }, [worldDataPath, enabled, loadNpcSpawns, loadItemInstances, loadNpcTemplates, loadItemTemplates]);

  /**
   * Add an NPC spawn to a room
   */
  const addNpcSpawn = useCallback(async (roomId: string, spawn: Partial<NpcSpawn>): Promise<boolean> => {
    if (!worldDataPath || !spawn.npc_template_id) return false;
    
    try {
      // Generate spawn ID
      const spawnId = `spawn_${spawn.npc_template_id}_${roomId}_${Date.now()}`;
      
      const newSpawn: NpcSpawn = {
        spawn_id: spawnId,
        npc_template_id: spawn.npc_template_id,
        room_id: roomId,
        quantity: spawn.quantity || 1,
        behavior: spawn.behavior || 'stationary',
        respawn_seconds: spawn.respawn_seconds || 0,
        unique: spawn.unique,
        dialogue_id: spawn.dialogue_id,
      };
      
      // TODO: Write to appropriate spawn file
      // For now, just update local state
      setNpcSpawns((prev) => [...prev, newSpawn]);
      
      console.log('Added NPC spawn:', newSpawn);
      return true;
    } catch (err) {
      console.error('Failed to add NPC spawn:', err);
      return false;
    }
  }, [worldDataPath]);

  /**
   * Update an existing NPC spawn
   */
  const updateNpcSpawn = useCallback(async (spawnId: string, updates: Partial<NpcSpawn>): Promise<boolean> => {
    try {
      setNpcSpawns((prev) =>
        prev.map((spawn) =>
          spawn.spawn_id === spawnId ? { ...spawn, ...updates } : spawn
        )
      );
      
      // TODO: Write changes to YAML file
      console.log('Updated NPC spawn:', spawnId, updates);
      return true;
    } catch (err) {
      console.error('Failed to update NPC spawn:', err);
      return false;
    }
  }, []);

  /**
   * Remove an NPC spawn
   */
  const removeNpcSpawn = useCallback(async (spawnId: string): Promise<boolean> => {
    try {
      setNpcSpawns((prev) => prev.filter((spawn) => spawn.spawn_id !== spawnId));
      
      // TODO: Update YAML file to remove spawn
      console.log('Removed NPC spawn:', spawnId);
      return true;
    } catch (err) {
      console.error('Failed to remove NPC spawn:', err);
      return false;
    }
  }, []);

  /**
   * Add an item instance to a room
   */
  const addItemInstance = useCallback(async (roomId: string, instance: Partial<ItemInstance>): Promise<boolean> => {
    if (!worldDataPath || !instance.item_template_id) return false;
    
    try {
      // Generate instance ID
      const instanceId = `inst_${instance.item_template_id}_${roomId}_${Date.now()}`;
      
      const newInstance: ItemInstance = {
        instance_id: instanceId,
        item_template_id: instance.item_template_id,
        room_id: roomId,
        quantity: instance.quantity || 1,
        location: instance.location || 'ground',
        container_id: instance.container_id,
        hidden: instance.hidden || false,
        locked: instance.locked || false,
      };
      
      // TODO: Write to appropriate instance file
      // For now, just update local state
      setItemInstances((prev) => [...prev, newInstance]);
      
      console.log('Added item instance:', newInstance);
      return true;
    } catch (err) {
      console.error('Failed to add item instance:', err);
      return false;
    }
  }, [worldDataPath]);

  /**
   * Update an existing item instance
   */
  const updateItemInstance = useCallback(async (instanceId: string, updates: Partial<ItemInstance>): Promise<boolean> => {
    try {
      setItemInstances((prev) =>
        prev.map((inst) =>
          inst.instance_id === instanceId ? { ...inst, ...updates } : inst
        )
      );
      
      // TODO: Write changes to YAML file
      console.log('Updated item instance:', instanceId, updates);
      return true;
    } catch (err) {
      console.error('Failed to update item instance:', err);
      return false;
    }
  }, []);

  /**
   * Remove an item instance
   */
  const removeItemInstance = useCallback(async (instanceId: string): Promise<boolean> => {
    try {
      setItemInstances((prev) => prev.filter((inst) => inst.instance_id !== instanceId));
      
      // TODO: Update YAML file to remove instance
      console.log('Removed item instance:', instanceId);
      return true;
    } catch (err) {
      console.error('Failed to remove item instance:', err);
      return false;
    }
  }, []);

  /**
   * Get all spawns for a specific room
   */
  const getSpawnsForRoom = useCallback((roomId: string): NpcSpawn[] => {
    return npcSpawns.filter((spawn) => spawn.room_id === roomId);
  }, [npcSpawns]);

  /**
   * Get all items for a specific room
   */
  const getItemsForRoom = useCallback((roomId: string): ItemInstance[] => {
    return itemInstances.filter((inst) => inst.room_id === roomId);
  }, [itemInstances]);

  /**
   * Refresh all content from disk
   */
  const refreshContent = useCallback(async () => {
    await Promise.all([
      loadNpcSpawns(),
      loadItemInstances(),
      loadNpcTemplates(),
      loadItemTemplates(),
    ]);
  }, [loadNpcSpawns, loadItemInstances, loadNpcTemplates, loadItemTemplates]);

  return {
    // NPC data
    npcSpawns,
    npcTemplates,
    npcSpawnsLoading,
    
    // Item data
    itemInstances,
    itemTemplates,
    itemInstancesLoading,
    
    // NPC operations
    addNpcSpawn,
    updateNpcSpawn,
    removeNpcSpawn,
    
    // Item operations
    addItemInstance,
    updateItemInstance,
    removeItemInstance,
    
    // Utility
    getSpawnsForRoom,
    getItemsForRoom,
    refreshContent,
  };
}

// ============================================================================
// YAML Parsing Helpers (simplified - should use proper YAML library)
// ============================================================================

/**
 * Parse NPC spawns from YAML content
 * TODO: Replace with proper YAML parsing (js-yaml)
 */
function parseYamlSpawns(content: string, filePath: string): NpcSpawn[] {
  const spawns: NpcSpawn[] = [];
  
  // Very basic YAML parsing - should use js-yaml in production
  const lines = content.split('\n');
  let currentSpawn: Partial<NpcSpawn> | null = null;
  
  for (const line of lines) {
    const trimmed = line.trim();
    
    if (trimmed.startsWith('- spawn_id:') || trimmed.startsWith('spawn_id:')) {
      if (currentSpawn && currentSpawn.spawn_id) {
        currentSpawn.filePath = filePath;
        spawns.push(currentSpawn as NpcSpawn);
      }
      currentSpawn = { spawn_id: trimmed.split(':')[1]?.trim() };
    } else if (currentSpawn && trimmed.includes(':')) {
      const [key, ...valueParts] = trimmed.split(':');
      const value = valueParts.join(':').trim();
      
      switch (key.trim()) {
        case 'npc_template_id':
          currentSpawn.npc_template_id = value;
          break;
        case 'room_id':
          currentSpawn.room_id = value;
          break;
        case 'quantity':
          currentSpawn.quantity = parseInt(value, 10) || 1;
          break;
        case 'behavior':
          currentSpawn.behavior = value as NpcSpawn['behavior'];
          break;
        case 'respawn_seconds':
          currentSpawn.respawn_seconds = parseInt(value, 10) || 0;
          break;
        case 'unique':
          currentSpawn.unique = value === 'true';
          break;
        case 'dialogue_id':
          currentSpawn.dialogue_id = value;
          break;
      }
    }
  }
  
  // Don't forget the last spawn
  if (currentSpawn && currentSpawn.spawn_id) {
    currentSpawn.filePath = filePath;
    spawns.push(currentSpawn as NpcSpawn);
  }
  
  return spawns;
}

/**
 * Parse item instances from YAML content
 * TODO: Replace with proper YAML parsing (js-yaml)
 */
function parseYamlInstances(content: string, filePath: string): ItemInstance[] {
  const instances: ItemInstance[] = [];
  
  // Very basic YAML parsing - should use js-yaml in production
  const lines = content.split('\n');
  let currentInstance: Partial<ItemInstance> | null = null;
  
  for (const line of lines) {
    const trimmed = line.trim();
    
    if (trimmed.startsWith('- instance_id:') || trimmed.startsWith('instance_id:')) {
      if (currentInstance && currentInstance.instance_id) {
        currentInstance.filePath = filePath;
        instances.push(currentInstance as ItemInstance);
      }
      currentInstance = { instance_id: trimmed.split(':')[1]?.trim() };
    } else if (currentInstance && trimmed.includes(':')) {
      const [key, ...valueParts] = trimmed.split(':');
      const value = valueParts.join(':').trim();
      
      switch (key.trim()) {
        case 'item_template_id':
          currentInstance.item_template_id = value;
          break;
        case 'room_id':
          currentInstance.room_id = value;
          break;
        case 'quantity':
          currentInstance.quantity = parseInt(value, 10) || 1;
          break;
        case 'location':
          currentInstance.location = value as ItemInstance['location'];
          break;
        case 'container_id':
          currentInstance.container_id = value;
          break;
        case 'hidden':
          currentInstance.hidden = value === 'true';
          break;
        case 'locked':
          currentInstance.locked = value === 'true';
          break;
      }
    }
  }
  
  // Don't forget the last instance
  if (currentInstance && currentInstance.instance_id) {
    currentInstance.filePath = filePath;
    instances.push(currentInstance as ItemInstance);
  }
  
  return instances;
}

/**
 * Parse a template YAML file for basic info
 * TODO: Replace with proper YAML parsing (js-yaml)
 */
function parseYamlTemplate(content: string): Record<string, string> | null {
  const result: Record<string, string> = {};
  
  const lines = content.split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith('#') && trimmed.includes(':')) {
      const [key, ...valueParts] = trimmed.split(':');
      const value = valueParts.join(':').trim();
      if (key && value) {
        result[key.trim()] = value;
      }
    }
  }
  
  return Object.keys(result).length > 0 ? result : null;
}
