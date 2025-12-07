/**
 * useReferenceValidation Hook
 * 
 * Validates that referenced IDs in content actually exist in the world data.
 * Checks things like:
 * - npc_template_id references existing NPCs
 * - item_template_id references existing items
 * - room_id references existing rooms
 * - quest_id references existing quests
 */
import { useState, useCallback, useEffect, useMemo } from 'react';
import yaml from 'js-yaml';
import type { ValidationError, FileEntry } from '../../shared/types';

interface EntityIndex {
  npcs: Set<string>;
  items: Set<string>;
  rooms: Set<string>;
  quests: Set<string>;
  abilities: Set<string>;
  dialogues: Set<string>;
  areas: Set<string>;
}

interface ReferenceValidationResult {
  errors: ValidationError[];
  isValidating: boolean;
}

// Fields that reference other entities
const REFERENCE_FIELDS: Record<string, keyof EntityIndex> = {
  npc_template_id: 'npcs',
  npc_template: 'npcs',
  giver_npc_template: 'npcs',
  turn_in_npc_template: 'npcs',
  target_template_id: 'npcs', // Could be NPC or item - we check both
  item_template_id: 'items',
  template_id: 'items', // Often used in item references
  room_id: 'rooms',
  target_room_id: 'rooms',
  start_room: 'rooms',
  quest_id: 'quests',
  accept_quest: 'quests',
  turn_in_quest: 'quests',
  prerequisite: 'quests',
  ability_id: 'abilities',
  area_id: 'areas',
};

export function useReferenceValidation(worldDataPath: string | null) {
  const [entityIndex, setEntityIndex] = useState<EntityIndex>({
    npcs: new Set(),
    items: new Set(),
    rooms: new Set(),
    quests: new Set(),
    abilities: new Set(),
    dialogues: new Set(),
    areas: new Set(),
  });
  const [isIndexing, setIsIndexing] = useState(false);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [isValidating, setIsValidating] = useState(false);

  // Build index of all entity IDs in the world data
  const buildEntityIndex = useCallback(async () => {
    if (!worldDataPath) return;

    setIsIndexing(true);
    const newIndex: EntityIndex = {
      npcs: new Set(),
      items: new Set(),
      rooms: new Set(),
      quests: new Set(),
      abilities: new Set(),
      dialogues: new Set(),
      areas: new Set(),
    };

    try {
      // Helper to scan a folder for entity IDs
      const scanFolder = async (folder: keyof EntityIndex, idField: string = 'id') => {
        try {
          const folderPath = `${worldDataPath}/${folder}`;
          const entries = await window.daemonswright.fs.listDirectory(folderPath);
          
          for (const entry of entries) {
            if (entry.isFile && (entry.name.endsWith('.yaml') || entry.name.endsWith('.yml')) && !entry.name.startsWith('_')) {
              try {
                const content = await window.daemonswright.fs.readFile(entry.path);
                const data = yaml.load(content) as Record<string, unknown>;
                
                if (data && typeof data === 'object') {
                  // Get ID from the specified field or filename
                  const id = (data[idField] as string) || entry.name.replace(/\.ya?ml$/, '');
                  if (id) {
                    newIndex[folder].add(id);
                  }
                }
              } catch {
                // Skip files that can't be parsed
              }
            } else if (entry.isDirectory && !entry.name.startsWith('_')) {
              // Recurse into subdirectories
              await scanSubfolder(entry.path, folder, idField);
            }
          }
        } catch {
          // Folder doesn't exist, skip
        }
      };

      // Helper to scan subdirectories
      const scanSubfolder = async (dirPath: string, folder: keyof EntityIndex, idField: string) => {
        try {
          const entries = await window.daemonswright.fs.listDirectory(dirPath);
          for (const entry of entries) {
            if (entry.isFile && (entry.name.endsWith('.yaml') || entry.name.endsWith('.yml')) && !entry.name.startsWith('_')) {
              try {
                const content = await window.daemonswright.fs.readFile(entry.path);
                const data = yaml.load(content) as Record<string, unknown>;
                
                if (data && typeof data === 'object') {
                  const id = (data[idField] as string) || entry.name.replace(/\.ya?ml$/, '');
                  if (id) {
                    newIndex[folder].add(id);
                  }
                }
              } catch {
                // Skip files that can't be parsed
              }
            } else if (entry.isDirectory && !entry.name.startsWith('_')) {
              await scanSubfolder(entry.path, folder, idField);
            }
          }
        } catch {
          // Skip
        }
      };

      // Scan all entity folders
      await Promise.all([
        scanFolder('npcs'),
        scanFolder('items'),
        scanFolder('rooms'),
        scanFolder('quests'),
        scanFolder('abilities', 'ability_id'),  // Individual ability files use ability_id
        scanFolder('areas'),
      ]);

      // Dialogues use npc_template_id as key
      try {
        const dialoguesPath = `${worldDataPath}/dialogues`;
        const dialogueEntries = await window.daemonswright.fs.listDirectory(dialoguesPath);
        for (const entry of dialogueEntries) {
          if (entry.isFile && (entry.name.endsWith('.yaml') || entry.name.endsWith('.yml')) && !entry.name.startsWith('_')) {
            try {
              const content = await window.daemonswright.fs.readFile(entry.path);
              const data = yaml.load(content) as Record<string, unknown>;
              if (data?.npc_template_id) {
                newIndex.dialogues.add(data.npc_template_id as string);
              }
            } catch {
              // Skip
            }
          }
        }
      } catch {
        // Dialogues folder doesn't exist
      }

      setEntityIndex(newIndex);
      console.log('[ReferenceValidation] Built entity index:', {
        npcs: newIndex.npcs.size,
        items: newIndex.items.size,
        rooms: newIndex.rooms.size,
        quests: newIndex.quests.size,
        abilities: newIndex.abilities.size,
        areas: newIndex.areas.size,
      });
    } finally {
      setIsIndexing(false);
    }
  }, [worldDataPath]);

  // Build index when world data path changes
  useEffect(() => {
    buildEntityIndex();
  }, [buildEntityIndex]);

  // Validate a single file for reference errors
  const validateFile = useCallback(async (filePath: string, content: string): Promise<ValidationError[]> => {
    const errors: ValidationError[] = [];
    
    try {
      const data = yaml.load(content) as Record<string, unknown>;
      if (!data || typeof data !== 'object') return errors;

      // Recursive function to check all fields
      const checkReferences = (obj: unknown, path: string = '') => {
        if (!obj || typeof obj !== 'object') return;

        if (Array.isArray(obj)) {
          obj.forEach((item, index) => checkReferences(item, `${path}[${index}]`));
          return;
        }

        const record = obj as Record<string, unknown>;
        for (const [key, value] of Object.entries(record)) {
          const fieldPath = path ? `${path}.${key}` : key;
          
          // Check if this field is a reference field
          const entityType = REFERENCE_FIELDS[key];
          if (entityType && typeof value === 'string' && value) {
            // Special case: target_template_id could be NPC or item
            if (key === 'target_template_id') {
              if (!entityIndex.npcs.has(value) && !entityIndex.items.has(value)) {
                errors.push({
                  message: `Referenced entity "${value}" not found in NPCs or Items`,
                  field: fieldPath,
                  severity: 'warning',
                  filePath,
                });
              }
            } else if (!entityIndex[entityType].has(value)) {
              errors.push({
                message: `Referenced ${entityType.slice(0, -1)} "${value}" not found`,
                field: fieldPath,
                severity: 'warning',
                filePath,
              });
            }
          }

          // Recurse into nested objects
          if (typeof value === 'object' && value !== null) {
            checkReferences(value, fieldPath);
          }
        }
      };

      checkReferences(data);
    } catch {
      // YAML parse error - skip
    }

    return errors;
  }, [entityIndex]);

  // Validate all files in world data
  const validateAll = useCallback(async () => {
    if (!worldDataPath) return;

    setIsValidating(true);
    const allErrors: ValidationError[] = [];

    try {
      // Folders to validate
      const folders = ['npcs', 'items', 'rooms', 'quests', 'abilities', 'dialogues', 'npc_spawns', 'item_instances'];

      for (const folder of folders) {
        try {
          const folderPath = `${worldDataPath}/${folder}`;
          const entries = await window.daemonswright.fs.listDirectory(folderPath);
          
          for (const entry of entries) {
            if (entry.isFile && (entry.name.endsWith('.yaml') || entry.name.endsWith('.yml')) && !entry.name.startsWith('_')) {
              try {
                const content = await window.daemonswright.fs.readFile(entry.path);
                const fileErrors = await validateFile(entry.path, content);
                allErrors.push(...fileErrors);
              } catch {
                // Skip files that can't be read
              }
            }
          }
        } catch {
          // Folder doesn't exist
        }
      }

      setValidationErrors(allErrors);
      console.log('[ReferenceValidation] Found', allErrors.length, 'reference errors');
    } finally {
      setIsValidating(false);
    }
  }, [worldDataPath, validateFile]);

  return {
    entityIndex,
    validationErrors,
    isIndexing,
    isValidating,
    buildEntityIndex,
    validateFile,
    validateAll,
  };
}
