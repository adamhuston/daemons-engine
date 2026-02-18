/**
 * useEntityOptions Hook
 *
 * Loads available entity IDs from a specified content folder
 * for use in select/autocomplete components.
 */

import { useState, useEffect, useCallback } from 'react';
import yaml from 'js-yaml';

interface EntityOption {
  id: string;
  name: string;
  path: string;
}

interface UseEntityOptionsResult {
  options: EntityOption[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

// Map of entity types to their ID field names
const ID_FIELD_MAP: Record<string, string> = {
  abilities: 'ability_id',
  npcs: 'template_id',
  items: 'template_id',
  rooms: 'room_id',
  quests: 'quest_id',
  dialogues: 'npc_template_id',
  classes: 'class_id',
  areas: 'area_id',
  triggers: 'id',
  factions: 'id',  // Factions use 'id' not 'faction_id'
  biomes: 'biome_id',
};

// Name field to use for display
const NAME_FIELD_MAP: Record<string, string> = {
  abilities: 'name',
  npcs: 'name',
  items: 'name',
  rooms: 'name',
  quests: 'name',
  dialogues: 'npc_template_id',
  classes: 'name',
  areas: 'name',
  triggers: 'description',
  factions: 'name',
  biomes: 'name',
};

export function useEntityOptions(
  worldDataPath: string | null,
  entityType: string
): UseEntityOptionsResult {
  const [options, setOptions] = useState<EntityOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadOptions = useCallback(async () => {
    if (!worldDataPath || !entityType) {
      setOptions([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const folderPath = `${worldDataPath}/${entityType}`;
      const idField = ID_FIELD_MAP[entityType] || 'id';
      const nameField = NAME_FIELD_MAP[entityType] || 'name';

      // Recursively scan for YAML files
      const scanDirectory = async (dirPath: string): Promise<EntityOption[]> => {
        const results: EntityOption[] = [];
        
        try {
          const entries = await window.daemonswright.fs.listDirectory(dirPath);
          
          for (const entry of entries) {
            if (entry.isFile && (entry.name.endsWith('.yaml') || entry.name.endsWith('.yml')) && !entry.name.startsWith('_')) {
              try {
                const content = await window.daemonswright.fs.readFile(entry.path);
                const data = yaml.load(content) as Record<string, unknown>;
                
                if (data && typeof data === 'object') {
                  const id = (data[idField] as string) || entry.name.replace(/\.ya?ml$/, '');
                  const name = (data[nameField] as string) || id;
                  
                  results.push({
                    id,
                    name,
                    path: entry.path,
                  });
                }
              } catch {
                // Skip files that can't be parsed
              }
            } else if (!entry.isFile && !entry.name.startsWith('_') && !entry.name.startsWith('.')) {
              // Recursively scan subdirectories
              const subResults = await scanDirectory(entry.path);
              results.push(...subResults);
            }
          }
        } catch {
          // Directory doesn't exist or can't be read
        }
        
        return results;
      };

      const loadedOptions = await scanDirectory(folderPath);
      
      // Sort by name
      loadedOptions.sort((a, b) => a.name.localeCompare(b.name));
      
      setOptions(loadedOptions);
    } catch (err) {
      console.error(`Failed to load ${entityType} options:`, err);
      setError(`Failed to load ${entityType}`);
      setOptions([]);
    } finally {
      setLoading(false);
    }
  }, [worldDataPath, entityType]);

  useEffect(() => {
    loadOptions();
  }, [loadOptions]);

  return {
    options,
    loading,
    error,
    refresh: loadOptions,
  };
}
