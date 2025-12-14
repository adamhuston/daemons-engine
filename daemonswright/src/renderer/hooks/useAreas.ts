/**
 * useAreas Hook
 *
 * Loads area YAML files from the workspace and provides
 * CRUD operations for area management.
 */

import { useState, useCallback, useEffect } from 'react';
import yaml from 'js-yaml';
import type { Area, TimePhase } from '../../shared/types';

interface AreaYaml {
  id: string;
  name: string;
  description?: string;
  time_scale?: number;
  biome?: string;
  climate?: string;
  ambient_lighting?: string;
  weather_profile?: string;
  danger_level?: number;
  magic_intensity?: string;
  ambient_sound?: string;
  default_respawn_time?: number;
  time_phases?: TimePhase[];
  entry_points?: string[];
  starting_day?: number;
  starting_hour?: number;
  starting_minute?: number;
}

interface UseAreasResult {
  areas: Area[];
  isLoading: boolean;
  error: string | null;
  loadAreas: () => Promise<void>;
  getArea: (areaId: string) => Area | undefined;
  updateArea: (areaId: string, updates: Partial<Area>) => Promise<boolean>;
  createArea: (areaData: Partial<Area>) => Promise<boolean>;
  deleteArea: (areaId: string) => Promise<boolean>;
}

/**
 * Recursively find all YAML files in the areas directory
 */
async function findAreaFiles(basePath: string): Promise<string[]> {
  const files: string[] = [];

  try {
    const entries = await window.daemonswright.fs.listDirectory(basePath);

    for (const entry of entries) {
      const fullPath = `${basePath}/${entry.name}`;

      if (entry.isDirectory) {
        // Recursively search subdirectories
        const subFiles = await findAreaFiles(fullPath);
        files.push(...subFiles);
      } else if (entry.isFile && entry.name.endsWith('.yaml') && !entry.name.startsWith('_')) {
        files.push(fullPath);
      }
    }
  } catch (err) {
    console.warn(`Failed to list directory: ${basePath}`, err);
  }

  return files;
}

export function useAreas(worldDataPath: string | null): UseAreasResult {
  const [areas, setAreas] = useState<Area[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load all area files from the workspace
  const loadAreas = useCallback(async () => {
    if (!worldDataPath) return;

    setIsLoading(true);
    setError(null);

    try {
      const areasPath = `${worldDataPath}/areas`;
      
      // Check if areas directory exists
      const exists = await window.daemonswright.fs.fileExists(areasPath);
      if (!exists) {
        console.warn('Areas directory not found:', areasPath);
        setAreas([]);
        return;
      }

      const areaFiles = await findAreaFiles(areasPath);

      const loadedAreas: Area[] = [];

      for (const filePath of areaFiles) {
        try {
          const content = await window.daemonswright.fs.readFile(filePath);
          const parsed = yaml.load(content) as AreaYaml;

          if (parsed && parsed.id) {
            loadedAreas.push({
              id: parsed.id,
              name: parsed.name || parsed.id,
              description: parsed.description,
              time_scale: parsed.time_scale ?? 1.0,
              biome: parsed.biome || 'mystical',
              climate: parsed.climate || 'temperate',
              ambient_lighting: parsed.ambient_lighting || 'dim',
              weather_profile: parsed.weather_profile,
              danger_level: parsed.danger_level ?? 1,
              magic_intensity: parsed.magic_intensity || 'moderate',
              ambient_sound: parsed.ambient_sound,
              default_respawn_time: parsed.default_respawn_time ?? 300,
              time_phases: parsed.time_phases,
              entry_points: parsed.entry_points || [],
              starting_day: parsed.starting_day ?? 1,
              starting_hour: parsed.starting_hour ?? 0,
              starting_minute: parsed.starting_minute ?? 0,
              filePath,
            });
          }
        } catch (err) {
          console.warn(`Failed to parse area file: ${filePath}`, err);
        }
      }

      // Sort areas by name
      loadedAreas.sort((a, b) => a.name.localeCompare(b.name));

      setAreas(loadedAreas);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load areas');
      console.error('Failed to load areas:', err);
    } finally {
      setIsLoading(false);
    }
  }, [worldDataPath]);

  // Auto-load areas when worldDataPath changes
  useEffect(() => {
    if (worldDataPath) {
      loadAreas();
    }
  }, [worldDataPath, loadAreas]);

  // Get a specific area by ID
  const getArea = useCallback(
    (areaId: string): Area | undefined => {
      return areas.find((a) => a.id === areaId);
    },
    [areas]
  );

  // Update an existing area
  const updateArea = useCallback(
    async (areaId: string, updates: Partial<Area>): Promise<boolean> => {
      const area = areas.find((a) => a.id === areaId);
      if (!area) {
        console.error('Area not found:', areaId);
        return false;
      }

      const filePath = area.filePath;
      if (!filePath) {
        console.error('Area file path not found:', areaId);
        return false;
      }

      try {
        // Read current file content
        let parsed: AreaYaml;
        try {
          const content = await window.daemonswright.fs.readFile(filePath);
          parsed = yaml.load(content) as AreaYaml;
        } catch (readErr) {
          console.error('Failed to read area file:', filePath, readErr);
          return false;
        }

        // Merge updates (exclude filePath from YAML)
        const { filePath: _, ...cleanUpdates } = updates;
        const updated: AreaYaml = {
          ...parsed,
          ...cleanUpdates,
          id: areaId, // Never change the ID
        };

        // Write back to file
        const newContent = yaml.dump(updated, {
          indent: 2,
          lineWidth: 120,
          noRefs: true,
        });

        await window.daemonswright.fs.writeFile(filePath, newContent);

        // Update local state
        setAreas((prev) =>
          prev.map((a) =>
            a.id === areaId
              ? { ...a, ...updates }
              : a
          )
        );

        return true;
      } catch (err) {
        console.error('Failed to save area:', err);
        return false;
      }
    },
    [areas]
  );

  // Create a new area
  const createArea = useCallback(
    async (areaData: Partial<Area>): Promise<boolean> => {
      if (!worldDataPath || !areaData.id) {
        console.error('World data path or area ID missing');
        return false;
      }

      // Normalize area ID
      const normalizedId = areaData.id.toLowerCase().replace(/\s+/g, '_');
      const areaIdWithPrefix = normalizedId.startsWith('area_')
        ? normalizedId
        : `area_${normalizedId}`;

      // Check if area already exists
      if (areas.find((a) => a.id === areaIdWithPrefix)) {
        console.error('Area already exists:', areaIdWithPrefix);
        return false;
      }

      const areasPath = `${worldDataPath}/areas`;
      const filePath = `${areasPath}/${normalizedId}.yaml`;

      try {
        // Ensure areas directory exists
        await window.daemonswright.fs.createDirectory(areasPath);

        // Create area YAML
        const areaYaml: AreaYaml = {
          id: areaIdWithPrefix,
          name: areaData.name || normalizedId,
          description: areaData.description || '',
          time_scale: areaData.time_scale ?? 1.0,
          biome: areaData.biome || 'mystical',
          climate: areaData.climate || 'temperate',
          ambient_lighting: areaData.ambient_lighting || 'dim',
          weather_profile: areaData.weather_profile,
          danger_level: areaData.danger_level ?? 1,
          magic_intensity: areaData.magic_intensity || 'moderate',
          ambient_sound: areaData.ambient_sound,
          default_respawn_time: areaData.default_respawn_time ?? 300,
          time_phases: areaData.time_phases,
          entry_points: areaData.entry_points || [],
          starting_day: areaData.starting_day ?? 1,
          starting_hour: areaData.starting_hour ?? 0,
          starting_minute: areaData.starting_minute ?? 0,
        };

        const content = yaml.dump(areaYaml, {
          indent: 2,
          lineWidth: 120,
          noRefs: true,
        });

        await window.daemonswright.fs.writeFile(filePath, content);

        // Also create the rooms subdirectory for this area
        const roomsSubdir = `${worldDataPath}/rooms/${normalizedId.replace('area_', '')}`;
        await window.daemonswright.fs.createDirectory(roomsSubdir);

        // Add to local state
        const newArea: Area = {
          ...areaYaml,
          filePath,
        };

        setAreas((prev) => [...prev, newArea].sort((a, b) => a.name.localeCompare(b.name)));

        return true;
      } catch (err) {
        console.error('Failed to create area:', err);
        return false;
      }
    },
    [worldDataPath, areas]
  );

  // Delete an area
  const deleteArea = useCallback(
    async (areaId: string): Promise<boolean> => {
      const area = areas.find((a) => a.id === areaId);
      if (!area || !area.filePath) {
        console.error('Area not found:', areaId);
        return false;
      }

      try {
        // Delete the area YAML file
        await window.daemonswright.fs.deleteFile(area.filePath);

        // Update local state
        setAreas((prev) => prev.filter((a) => a.id !== areaId));

        return true;
      } catch (err) {
        console.error('Failed to delete area:', err);
        return false;
      }
    },
    [areas]
  );

  return {
    areas,
    isLoading,
    error,
    loadAreas,
    getArea,
    updateArea,
    createArea,
    deleteArea,
  };
}
