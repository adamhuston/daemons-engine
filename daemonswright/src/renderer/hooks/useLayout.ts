/**
 * useLayout Hook
 *
 * Manages room layout positions stored in _layout.yaml files.
 * Layout files are CMS-only and store canvas positions for rooms.
 */

import { useState, useCallback, useEffect } from 'react';
import yaml from 'js-yaml';

// Layout file schema
export interface RoomPosition {
  x: number;  // Grid X coordinate
  y: number;  // Grid Y coordinate
  z: number;  // Z-level (layer)
}

export interface AreaLayout {
  version: number;
  grid_size?: number;
  rooms: Record<string, RoomPosition>;
  layer_names?: Record<number, string>;
  viewport?: {
    center_x: number;
    center_y: number;
    zoom: number;
    active_layer: number | 'all';
  };
}

interface UseLayoutResult {
  layouts: Map<string, AreaLayout>;
  isLoading: boolean;
  error: string | null;
  loadLayout: (areaPath: string) => Promise<AreaLayout | null>;
  saveLayout: (areaPath: string, layout: AreaLayout) => Promise<boolean>;
  updateRoomPosition: (areaPath: string, roomId: string, position: RoomPosition) => Promise<boolean>;
  getRoomPosition: (areaPath: string, roomId: string) => RoomPosition | null;
}

const DEFAULT_LAYOUT: AreaLayout = {
  version: 1,
  grid_size: 150,
  rooms: {},
  layer_names: {},
};

export function useLayout(worldDataPath: string | null): UseLayoutResult {
  const [layouts, setLayouts] = useState<Map<string, AreaLayout>>(new Map());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Get the layout file path for an area
  const getLayoutPath = useCallback((areaPath: string): string => {
    return `${areaPath}/_layout.yaml`;
  }, []);

  // Load a layout file for an area
  const loadLayout = useCallback(async (areaPath: string): Promise<AreaLayout | null> => {
    const layoutPath = getLayoutPath(areaPath);
    
    try {
      const content = await window.daemonswright.fs.readFile(layoutPath);
      const parsed = yaml.load(content) as AreaLayout;
      
      // Validate and normalize the layout
      const layout: AreaLayout = {
        version: parsed.version ?? 1,
        grid_size: parsed.grid_size ?? 150,
        rooms: parsed.rooms ?? {},
        layer_names: parsed.layer_names ?? {},
        viewport: parsed.viewport,
      };
      
      setLayouts((prev) => new Map(prev).set(areaPath, layout));
      return layout;
    } catch (err) {
      // File doesn't exist yet - return null (will be created on first save)
      console.log(`No layout file found for ${areaPath}, will create on first save`);
      return null;
    }
  }, [getLayoutPath]);

  // Save a layout file for an area
  const saveLayout = useCallback(async (areaPath: string, layout: AreaLayout): Promise<boolean> => {
    const layoutPath = getLayoutPath(areaPath);
    
    try {
      const content = yaml.dump(layout, {
        indent: 2,
        lineWidth: 120,
        noRefs: true,
      });
      
      await window.daemonswright.fs.writeFile(layoutPath, content);
      setLayouts((prev) => new Map(prev).set(areaPath, layout));
      return true;
    } catch (err) {
      console.error(`Failed to save layout: ${err}`);
      setError(`Failed to save layout: ${err}`);
      return false;
    }
  }, [getLayoutPath]);

  // Update a single room's position
  const updateRoomPosition = useCallback(async (
    areaPath: string,
    roomId: string,
    position: RoomPosition
  ): Promise<boolean> => {
    // Get existing layout or create new one
    let layout = layouts.get(areaPath);
    if (!layout) {
      layout = { ...DEFAULT_LAYOUT };
    }
    
    // Update the room position
    const updatedLayout: AreaLayout = {
      ...layout,
      rooms: {
        ...layout.rooms,
        [roomId]: position,
      },
    };
    
    return saveLayout(areaPath, updatedLayout);
  }, [layouts, saveLayout]);

  // Get a room's position from the layout
  const getRoomPosition = useCallback((areaPath: string, roomId: string): RoomPosition | null => {
    const layout = layouts.get(areaPath);
    if (!layout) return null;
    return layout.rooms[roomId] ?? null;
  }, [layouts]);

  // Load all layouts when worldDataPath changes
  useEffect(() => {
    if (!worldDataPath) return;
    
    const loadAllLayouts = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        // List all area directories
        const roomsPath = `${worldDataPath}/rooms`;
        const entries = await window.daemonswright.fs.listDirectory(roomsPath);
        
        // Load layout for each area directory
        for (const entry of entries) {
          if (entry.isDirectory && !entry.name.startsWith('_')) {
            await loadLayout(entry.path);
          }
        }
      } catch (err) {
        console.error('Failed to load layouts:', err);
        setError(`Failed to load layouts: ${err}`);
      } finally {
        setIsLoading(false);
      }
    };
    
    loadAllLayouts();
  }, [worldDataPath, loadLayout]);

  return {
    layouts,
    isLoading,
    error,
    loadLayout,
    saveLayout,
    updateRoomPosition,
    getRoomPosition,
  };
}
