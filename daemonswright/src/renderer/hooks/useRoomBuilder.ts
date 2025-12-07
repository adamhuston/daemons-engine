/**
 * useRoomBuilder Hook
 *
 * Loads room YAML files from the workspace and converts them to
 * React Flow nodes and edges for the Room Builder canvas.
 * Also manages layout persistence via _layout.yaml files.
 */

import { useState, useCallback, useEffect, useMemo } from 'react';
import yaml from 'js-yaml';
import type { RoomNode, RoomConnection } from '../../shared/types';
import { useLayout, type RoomPosition, type AreaLayout } from './useLayout';

// Grid size constant - must match RoomBuilder component
const GRID_SIZE = 150;

interface RoomYaml {
  id: string;
  area_id?: string;
  name: string;
  description?: string;
  room_type?: string;
  z_level?: number;
  exits?: Record<string, string>;
}

interface UseRoomBuilderResult {
  rooms: RoomNode[];
  connections: RoomConnection[];
  zLevels: number[];
  isLoading: boolean;
  error: string | null;
  loadRooms: () => Promise<void>;
  updateRoomPosition: (roomId: string, position: { x: number; y: number }) => Promise<void>;
  updateRoomProperties: (roomId: string, updates: Partial<RoomYaml>) => Promise<boolean>;
  createRoom: (roomData: RoomYaml, position: { x: number; y: number }, sourceRoomId?: string) => Promise<boolean>;
  deleteRoom: (roomId: string) => Promise<boolean>;
  addConnection: (source: string, target: string, direction: string) => Promise<boolean>;
  removeConnection: (connectionId: string) => Promise<boolean>;
  removeExit: (roomId: string, direction: string) => Promise<boolean>;
  createArea: (areaId: string, displayName: string) => Promise<boolean>;
}

// Direction to offset mapping for positioning exits
// up/down get diagonal offset to visually separate vertical layers
const directionOffsets: Record<string, { dx: number; dy: number }> = {
  north: { dx: 0, dy: -1 },
  northeast: { dx: 0.7, dy: -0.7 },
  east: { dx: 1, dy: 0 },
  southeast: { dx: 0.7, dy: 0.7 },
  south: { dx: 0, dy: 1 },
  southwest: { dx: -0.7, dy: 0.7 },
  west: { dx: -1, dy: 0 },
  northwest: { dx: -0.7, dy: -0.7 },
  up: { dx: -0.5, dy: -0.8 },   // Offset left and up (higher layer = higher on screen)
  down: { dx: 0.5, dy: 0.8 },   // Offset right and down (lower layer = lower on screen)
};

// Opposite direction mapping for bidirectional edges
const oppositeDirection: Record<string, string> = {
  north: 'south',
  south: 'north',
  east: 'west',
  west: 'east',
  northeast: 'southwest',
  southwest: 'northeast',
  northwest: 'southeast',
  southeast: 'northwest',
  up: 'down',
  down: 'up',
};

export function useRoomBuilder(worldDataPath: string | null): UseRoomBuilderResult {
  const [rooms, setRooms] = useState<RoomNode[]>([]);
  const [connections, setConnections] = useState<RoomConnection[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Layout management
  const { layouts, updateRoomPosition: updateLayoutPosition, loadLayout, saveLayout } = useLayout(worldDataPath);

  // Helper to get the area folder path from a room's file path
  const getAreaPathFromRoom = useCallback((room: RoomNode): string | null => {
    // If we have a stored file path, derive area path from it
    if (room.filePath) {
      // filePath is like: /path/to/rooms/caves/room_cave_chamber.yaml
      // We want: /path/to/rooms/caves
      const lastSlash = room.filePath.lastIndexOf('/');
      if (lastSlash > 0) {
        return room.filePath.substring(0, lastSlash);
      }
    }
    // Fall back to deriving from area_id (for newly created rooms)
    if (worldDataPath && room.area_id) {
      const areaName = room.area_id.replace('area_', '');
      return `${worldDataPath}/rooms/${areaName}`;
    }
    return null;
  }, [worldDataPath]);

  // Load all room files from the workspace
  const loadRooms = useCallback(async () => {
    if (!worldDataPath) return;

    setIsLoading(true);
    setError(null);

    try {
      const roomsPath = `${worldDataPath}/rooms`;
      const roomFiles = await findRoomFiles(roomsPath);

      const loadedRooms: RoomNode[] = [];
      const roomExits: Map<string, Record<string, string>> = new Map();
      const roomAreaPaths: Map<string, string> = new Map(); // Track which area each room belongs to

      // Parse all room files
      for (const filePath of roomFiles) {
        try {
          const content = await window.daemonswright.fs.readFile(filePath);
          const parsed = yaml.load(content) as RoomYaml;

          if (parsed && parsed.id) {
            // Extract z_level from coordinate ID or use explicit field
            const coords = extractCoordinates(parsed.id);
            const zLevel = parsed.z_level ?? coords?.z ?? 0;
            
            // Determine area path from file path (e.g., /path/rooms/caves/room.yaml -> /path/rooms/caves)
            const pathParts = filePath.split('/');
            pathParts.pop(); // Remove filename
            const areaPath = pathParts.join('/');
            roomAreaPaths.set(parsed.id, areaPath);

            loadedRooms.push({
              id: parsed.id,
              room_id: parsed.id,
              name: parsed.name || parsed.id,
              description: parsed.description,
              room_type: parsed.room_type,
              area_id: parsed.area_id,
              z_level: zLevel,
              exits: parsed.exits || {},
              position: { x: 0, y: 0 }, // Will be calculated
              filePath, // Store the original file path
            });

            if (parsed.exits) {
              roomExits.set(parsed.id, parsed.exits);
            }
          }
        } catch (err) {
          console.warn(`Failed to parse room file: ${filePath}`, err);
        }
      }

      // Calculate positions using layout files first, then fall back to auto-layout
      const positionedRooms = await calculateRoomPositionsWithLayouts(
        loadedRooms,
        roomExits,
        roomAreaPaths,
        layouts,
        loadLayout
      );

      // Build connections from exits
      const builtConnections = buildConnections(roomExits);

      // Save initial layout files for areas that don't have one
      // Group rooms by area path and check if layout exists
      const roomsByAreaPath = new Map<string, RoomNode[]>();
      for (const room of positionedRooms) {
        const areaPath = roomAreaPaths.get(room.id);
        if (areaPath) {
          if (!roomsByAreaPath.has(areaPath)) {
            roomsByAreaPath.set(areaPath, []);
          }
          roomsByAreaPath.get(areaPath)!.push(room);
        }
      }
      
      // Create layout files for areas that don't have them
      for (const [areaPath, areaRooms] of roomsByAreaPath.entries()) {
        const existingLayout = layouts.get(areaPath);
        if (!existingLayout) {
          // Create a new layout with the calculated positions
          const newLayout: AreaLayout = {
            version: 1,
            grid_size: GRID_SIZE,
            rooms: {},
            layer_names: {},
          };
          
          for (const room of areaRooms) {
            newLayout.rooms[room.id] = {
              x: Math.round(room.position.x / GRID_SIZE),
              y: Math.round(room.position.y / GRID_SIZE),
              z: room.z_level,
            };
          }
          
          // Save the layout file
          await saveLayout(areaPath, newLayout);
          console.log(`Created initial layout file for ${areaPath}`);
        }
      }

      setRooms(positionedRooms);
      setConnections(builtConnections);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load rooms');
      console.error('Failed to load rooms:', err);
    } finally {
      setIsLoading(false);
    }
  }, [worldDataPath, layouts, loadLayout, saveLayout]);

  // Auto-load rooms when worldDataPath changes
  useEffect(() => {
    if (worldDataPath) {
      loadRooms();
    }
  }, [worldDataPath, loadRooms]);

  // Update a room's position (called after drag) - persists to layout file
  const updateRoomPosition = useCallback(async (roomId: string, position: { x: number; y: number }) => {
    // Update local state immediately
    setRooms((prev) =>
      prev.map((room) => (room.id === roomId ? { ...room, position } : room))
    );
    
    // Find the room to get its area path and z_level
    const room = rooms.find((r) => r.id === roomId);
    if (room) {
      // Get area path from the room's actual file path
      const areaPath = getAreaPathFromRoom(room);
      if (!areaPath) return;
      
      // Convert pixel position to grid coordinates
      const gridPosition: RoomPosition = {
        x: Math.round(position.x / GRID_SIZE),
        y: Math.round(position.y / GRID_SIZE),
        z: room.z_level,
      };
      
      // Save to layout file
      await updateLayoutPosition(areaPath, roomId, gridPosition);
    }
  }, [rooms, getAreaPathFromRoom, updateLayoutPosition]);

  // Get the file path for a room - prefer stored filePath, fall back to deriving from area_id
  const getRoomFilePath = useCallback((room: RoomNode): string | null => {
    // Use stored file path if available (most reliable)
    if (room.filePath) {
      return room.filePath;
    }
    
    // Fall back to deriving from area_id (for newly created rooms)
    if (!worldDataPath || !room.area_id) return null;
    const areaName = room.area_id.replace('area_', '');
    return `${worldDataPath}/rooms/${areaName}/${room.id}.yaml`;
  }, [worldDataPath]);

  // Update room properties and save to YAML file
  const updateRoomProperties = useCallback(async (roomId: string, updates: Partial<RoomYaml>): Promise<boolean> => {
    const room = rooms.find((r) => r.id === roomId);
    if (!room) {
      console.error('Room not found:', roomId);
      return false;
    }
    
    const filePath = getRoomFilePath(room);
    if (!filePath) {
      console.error('Could not get file path for room:', roomId);
      return false;
    }
    
    try {
      // Try to read current file content, or create new if it doesn't exist
      let parsed: RoomYaml;
      try {
        const content = await window.daemonswright.fs.readFile(filePath);
        parsed = yaml.load(content) as RoomYaml;
      } catch (readErr) {
        // File doesn't exist, create from room state
        console.warn('Room file not found, creating:', filePath);
        parsed = {
          id: room.id,
          name: room.name,
          description: room.description || '',
          room_type: room.room_type || 'chamber',
          area_id: room.area_id || '',
          exits: room.exits || {},
        };
      }
      
      // Merge updates
      const updated: RoomYaml = {
        ...parsed,
        ...updates,
        id: roomId, // Never change the ID
      };
      
      // Write back to file
      const newContent = yaml.dump(updated, {
        indent: 2,
        lineWidth: 120,
        noRefs: true,
      });
      
      await window.daemonswright.fs.writeFile(filePath, newContent);
      
      // Update local state
      setRooms((prev) =>
        prev.map((r) =>
          r.id === roomId
            ? {
                ...r,
                name: updates.name ?? r.name,
                description: updates.description ?? r.description,
                room_type: updates.room_type ?? r.room_type,
              }
            : r
        )
      );
      
      return true;
    } catch (err) {
      console.error('Failed to save room:', err);
      return false;
    }
  }, [rooms, getRoomFilePath]);

  // Create a new room
  // If sourceRoomId is provided, the new room will be created in the same folder as the source room
  const createRoom = useCallback(async (
    roomData: RoomYaml, 
    position: { x: number; y: number },
    sourceRoomId?: string
  ): Promise<boolean> => {
    if (!worldDataPath) return false;
    
    let areaPath: string;
    let filePath: string;
    
    // If we have a source room, use its folder
    if (sourceRoomId) {
      const sourceRoom = rooms.find((r) => r.id === sourceRoomId);
      if (sourceRoom?.filePath) {
        // Get the folder from the source room's file path
        const lastSlash = sourceRoom.filePath.lastIndexOf('/');
        areaPath = sourceRoom.filePath.substring(0, lastSlash);
        filePath = `${areaPath}/${roomData.id}.yaml`;
      } else {
        // Fall back to deriving from area_id
        const areaName = (roomData.area_id || 'unknown').replace('area_', '');
        areaPath = `${worldDataPath}/rooms/${areaName}`;
        filePath = `${areaPath}/${roomData.id}.yaml`;
      }
    } else {
      // No source room - derive from area_id
      const areaName = (roomData.area_id || 'unknown').replace('area_', '');
      areaPath = `${worldDataPath}/rooms/${areaName}`;
      filePath = `${areaPath}/${roomData.id}.yaml`;
    }
    
    try {
      // Create the YAML content
      const content = yaml.dump(roomData, {
        indent: 2,
        lineWidth: 120,
        noRefs: true,
      });
      
      // Write the file
      await window.daemonswright.fs.writeFile(filePath, content);
      
      // Add to layout
      const gridPosition: RoomPosition = {
        x: Math.round(position.x / GRID_SIZE),
        y: Math.round(position.y / GRID_SIZE),
        z: roomData.z_level ?? 0,
      };
      await updateLayoutPosition(areaPath, roomData.id, gridPosition);
      
      // Add to local state
      const newRoom: RoomNode = {
        id: roomData.id,
        room_id: roomData.id,
        name: roomData.name,
        description: roomData.description,
        room_type: roomData.room_type,
        area_id: roomData.area_id,
        z_level: roomData.z_level ?? 0,
        exits: roomData.exits || {},
        position,
        filePath, // Store the file path we used to create it
      };
      
      setRooms((prev) => [...prev, newRoom]);
      
      return true;
    } catch (err) {
      console.error('Failed to create room:', err);
      return false;
    }
  }, [worldDataPath, rooms, updateLayoutPosition]);

  // Delete a room
  const deleteRoom = useCallback(async (roomId: string): Promise<boolean> => {
    const room = rooms.find((r) => r.id === roomId);
    if (!room) return false;
    
    const filePath = getRoomFilePath(room);
    if (!filePath) return false;
    
    try {
      // First, find all rooms that have exits pointing to this room and remove those exits
      const roomsWithExitsToDeleted = rooms.filter((r) => {
        if (r.id === roomId) return false;
        if (!r.exits) return false;
        return Object.values(r.exits).includes(roomId);
      });
      
      // Update each room that points to the deleted room
      for (const sourceRoom of roomsWithExitsToDeleted) {
        const sourceFilePath = getRoomFilePath(sourceRoom);
        if (!sourceFilePath) continue;
        
        try {
          const content = await window.daemonswright.fs.readFile(sourceFilePath);
          const parsed = yaml.load(content) as RoomYaml;
          
          if (parsed.exits) {
            // Remove all exits that point to the deleted room
            const updatedExits: Record<string, string> = {};
            for (const [direction, target] of Object.entries(parsed.exits)) {
              if (target !== roomId) {
                updatedExits[direction] = target;
              }
            }
            parsed.exits = updatedExits;
            
            // Write back the updated room
            const newContent = yaml.dump(parsed, {
              indent: 2,
              lineWidth: 120,
              noRefs: true,
            });
            await window.daemonswright.fs.writeFile(sourceFilePath, newContent);
          }
        } catch (err) {
          console.warn(`Failed to update exits for room ${sourceRoom.id}:`, err);
        }
      }
      
      // Delete the room's file
      await window.daemonswright.fs.deleteFile(filePath);
      
      // Remove from local state and update exits in other rooms
      setRooms((prev) => {
        return prev
          .filter((r) => r.id !== roomId)
          .map((r) => {
            if (!r.exits) return r;
            // Remove exits pointing to deleted room
            const hasExitToDeleted = Object.values(r.exits).includes(roomId);
            if (!hasExitToDeleted) return r;
            
            const updatedExits: Record<string, string> = {};
            for (const [direction, target] of Object.entries(r.exits)) {
              if (target !== roomId) {
                updatedExits[direction] = target;
              }
            }
            return { ...r, exits: updatedExits };
          });
      });
      
      // Remove connections to/from this room
      setConnections((prev) =>
        prev.filter((c) => c.source !== roomId && c.target !== roomId)
      );
      
      return true;
    } catch (err) {
      console.error('Failed to delete room:', err);
      return false;
    }
  }, [rooms, getRoomFilePath]);

  // Create a new area (folder with initial room, layout, and area definition)
  const createArea = useCallback(async (areaId: string, displayName: string): Promise<boolean> => {
    if (!worldDataPath) return false;
    
    try {
      // Normalize area_id to use underscores and lowercase
      const normalizedAreaId = `area_${areaId.toLowerCase().replace(/\s+/g, '_').replace(/^area_/, '')}`;
      const folderName = normalizedAreaId.replace('area_', '');
      const areaPath = `${worldDataPath}/rooms/${folderName}`;
      
      // Create the area definition file in /areas folder
      const areaDefPath = `${worldDataPath}/areas/${folderName}.yaml`;
      const initialRoomId = `${folderName}_start`;
      const areaDefContent = yaml.dump({
        id: normalizedAreaId,
        name: displayName,
        description: `${displayName} area.`,
        time_scale: 1.0,
        starting_day: 1,
        starting_hour: 6,
        starting_minute: 0,
        biome: 'outdoor',
        climate: 'temperate',
        ambient_lighting: 'natural',
        weather_profile: 'standard',
        danger_level: 1,
        magic_intensity: 'normal',
        default_respawn_time: 300,
        recommended_level: 1,
        theme: 'exploration',
        area_flags: {
          safe_zone: false,
          pvp_enabled: false,
          magic_enhanced: false,
        },
        entry_points: [initialRoomId],
      }, { indent: 2, lineWidth: 120, noRefs: true });
      await window.daemonswright.fs.writeFile(areaDefPath, areaDefContent);
      
      // Create empty layout file in rooms folder
      const layoutPath = `${areaPath}/_layout.yaml`;
      const layoutContent = yaml.dump({ positions: {} }, { indent: 2 });
      await window.daemonswright.fs.writeFile(layoutPath, layoutContent);
      
      // Create an initial room for the area
      const roomPath = `${areaPath}/${initialRoomId}.yaml`;
      const roomData: RoomYaml = {
        id: initialRoomId,
        area_id: normalizedAreaId,
        name: `${displayName} - Start`,
        description: `The starting point of ${displayName}.`,
        room_type: 'outdoor',
        z_level: 0,
        exits: {},
      };
      const roomContent = yaml.dump(roomData, { indent: 2, lineWidth: 120, noRefs: true });
      await window.daemonswright.fs.writeFile(roomPath, roomContent);
      
      // Update layout with initial room position
      const updatedLayout = yaml.dump({ 
        positions: { 
          [initialRoomId]: { x: 0, y: 0 } 
        } 
      }, { indent: 2 });
      await window.daemonswright.fs.writeFile(layoutPath, updatedLayout);
      
      // Reload rooms to pick up the new area
      await loadRooms();
      
      return true;
    } catch (err) {
      console.error('Failed to create area:', err);
      return false;
    }
  }, [worldDataPath, loadRooms]);

  // Add a new connection and save to room YAML
  const addConnection = useCallback(async (source: string, target: string, direction: string): Promise<boolean> => {
    const sourceRoom = rooms.find((r) => r.id === source);
    if (!sourceRoom) {
      console.error('Source room not found:', source);
      return false;
    }
    
    const filePath = getRoomFilePath(sourceRoom);
    if (!filePath) {
      console.error('Could not get file path for room:', source);
      return false;
    }
    
    try {
      // Read current file content
      let content: string;
      try {
        content = await window.daemonswright.fs.readFile(filePath);
      } catch (readErr) {
        // File might not exist yet - create it with the connection
        console.warn('Room file not found, creating new:', filePath);
        const newRoom: RoomYaml = {
          id: sourceRoom.id,
          name: sourceRoom.name,
          description: sourceRoom.description || '',
          room_type: sourceRoom.room_type || 'chamber',
          area_id: sourceRoom.area_id || '',
          exits: { [direction]: target },
        };
        const newContent = yaml.dump(newRoom, {
          indent: 2,
          lineWidth: 120,
          noRefs: true,
        });
        await window.daemonswright.fs.writeFile(filePath, newContent);
        
        // Update room's exits in state and rebuild connections
        setRooms((prev) => {
          const updatedRooms = prev.map((r) =>
            r.id === source
              ? { ...r, exits: { ...r.exits, [direction]: target } }
              : r
          );
          
          // Rebuild connections from updated room exits
          const updatedRoomExits = new Map<string, Record<string, string>>();
          updatedRooms.forEach((r) => {
            if (r.exits && Object.keys(r.exits).length > 0) {
              updatedRoomExits.set(r.id, r.exits);
            }
          });
          const newConnections = buildConnections(updatedRoomExits);
          setConnections(newConnections);
          
          return updatedRooms;
        });
        
        return true;
      }
      
      const parsed = yaml.load(content) as RoomYaml;
      
      // Add the exit
      const updatedExits = {
        ...(parsed.exits || {}),
        [direction]: target,
      };
      
      const updated: RoomYaml = {
        ...parsed,
        exits: updatedExits,
      };
      
      // Write back to file
      const newContent = yaml.dump(updated, {
        indent: 2,
        lineWidth: 120,
        noRefs: true,
      });
      
      await window.daemonswright.fs.writeFile(filePath, newContent);
      
      // Update local state
      const id = `${source}-${direction}-${target}`;
      // Update room's exits in state first
      setRooms((prev) => {
        const updatedRooms = prev.map((r) =>
          r.id === source
            ? { ...r, exits: { ...r.exits, [direction]: target } }
            : r
        );
        
        // Rebuild connections from updated room exits to properly detect bidirectional
        const updatedRoomExits = new Map<string, Record<string, string>>();
        updatedRooms.forEach((r) => {
          if (r.exits && Object.keys(r.exits).length > 0) {
            updatedRoomExits.set(r.id, r.exits);
          }
        });
        const newConnections = buildConnections(updatedRoomExits);
        setConnections(newConnections);
        
        return updatedRooms;
      });
      
      return true;
    } catch (err) {
      console.error('Failed to add connection:', err);
      return false;
    }
  }, [rooms, getRoomFilePath]);

  // Remove a connection and save to room YAML
  const removeConnection = useCallback(async (connectionId: string): Promise<boolean> => {
    // Parse connection ID to get source and direction
    const conn = connections.find((c) => c.id === connectionId);
    if (!conn) {
      console.error('Connection not found:', connectionId);
      return false;
    }
    
    const sourceRoom = rooms.find((r) => r.id === conn.source);
    if (!sourceRoom) {
      console.error('Source room not found for connection:', conn.source);
      // Still remove from local state
      setConnections((prev) => prev.filter((c) => c.id !== connectionId));
      return true;
    }
    
    const filePath = getRoomFilePath(sourceRoom);
    if (!filePath) {
      console.error('Could not get file path for room:', conn.source);
      return false;
    }
    
    try {
      // Read current file content
      let content: string;
      try {
        content = await window.daemonswright.fs.readFile(filePath);
      } catch (readErr) {
        console.warn('Room file not found when removing connection:', filePath);
        // Just update local state
        setConnections((prev) => prev.filter((c) => c.id !== connectionId));
        setRooms((prev) =>
          prev.map((r) => {
            if (r.id === conn.source) {
              const newExits = { ...r.exits };
              delete newExits[conn.sourceHandle];
              return { ...r, exits: newExits };
            }
            return r;
          })
        );
        return true;
      }
      
      const parsed = yaml.load(content) as RoomYaml;
      
      // Remove the exit
      const updatedExits = { ...(parsed.exits || {}) };
      delete updatedExits[conn.sourceHandle];
      
      const updated: RoomYaml = {
        ...parsed,
        exits: Object.keys(updatedExits).length > 0 ? updatedExits : undefined,
      };
      
      // Write back to file
      const newContent = yaml.dump(updated, {
        indent: 2,
        lineWidth: 120,
        noRefs: true,
      });
      
      await window.daemonswright.fs.writeFile(filePath, newContent);
      
      // Update local state
      setConnections((prev) => prev.filter((c) => c.id !== connectionId));
      
      // Update room's exits in state
      setRooms((prev) =>
        prev.map((r) => {
          if (r.id === conn.source) {
            const newExits = { ...r.exits };
            delete newExits[conn.sourceHandle];
            return { ...r, exits: newExits };
          }
          return r;
        })
      );
      
      return true;
    } catch (err) {
      console.error('Failed to remove connection:', err);
      return false;
    }
  }, [connections, rooms, getRoomFilePath]);

  // Remove a specific exit from a room (used for toggling bidirectional to unidirectional)
  const removeExit = useCallback(async (roomId: string, direction: string): Promise<boolean> => {
    const room = rooms.find((r) => r.id === roomId);
    if (!room) {
      console.error('Room not found:', roomId);
      return false;
    }
    
    const filePath = getRoomFilePath(room);
    if (!filePath) {
      console.error('Could not get file path for room:', roomId);
      return false;
    }
    
    try {
      // Read current file content
      const content = await window.daemonswright.fs.readFile(filePath);
      const parsed = yaml.load(content) as RoomYaml;
      
      // Remove the exit
      const updatedExits = { ...(parsed.exits || {}) };
      delete updatedExits[direction];
      
      const updated: RoomYaml = {
        ...parsed,
        exits: Object.keys(updatedExits).length > 0 ? updatedExits : undefined,
      };
      
      // Write back to file
      const newContent = yaml.dump(updated, {
        indent: 2,
        lineWidth: 120,
        noRefs: true,
      });
      
      await window.daemonswright.fs.writeFile(filePath, newContent);
      
      // Update room's exits in state
      setRooms((prev) =>
        prev.map((r) => {
          if (r.id === roomId) {
            const newExits = { ...r.exits };
            delete newExits[direction];
            return { ...r, exits: newExits };
          }
          return r;
        })
      );
      
      // Rebuild connections from updated room exits
      const updatedRoomExits = new Map<string, Record<string, string>>();
      rooms.forEach((r) => {
        if (r.id === roomId) {
          // Use updated exits without the removed direction
          const exits = { ...r.exits };
          delete exits[direction];
          if (Object.keys(exits).length > 0) {
            updatedRoomExits.set(r.id, exits);
          }
        } else if (r.exits && Object.keys(r.exits).length > 0) {
          updatedRoomExits.set(r.id, r.exits);
        }
      });
      const newConnections = buildConnections(updatedRoomExits);
      setConnections(newConnections);
      
      return true;
    } catch (err) {
      console.error('Failed to remove exit:', err);
      return false;
    }
  }, [rooms, getRoomFilePath]);

  // Compute unique z-levels from rooms
  const zLevels = useMemo(() => {
    const levels = new Set(rooms.map((r) => r.z_level));
    return Array.from(levels).sort((a, b) => b - a); // Descending (highest first)
  }, [rooms]);

  return {
    rooms,
    connections,
    zLevels,
    isLoading,
    error,
    loadRooms,
    updateRoomPosition,
    updateRoomProperties,
    createRoom,
    deleteRoom,
    addConnection,
    removeConnection,
    removeExit,
    createArea,
  };
}

// Find all room YAML files recursively
async function findRoomFiles(roomsPath: string): Promise<string[]> {
  const files: string[] = [];

  try {
    const entries = await window.daemonswright.fs.listDirectory(roomsPath);

    for (const entry of entries) {
      if (entry.isDirectory) {
        const subFiles = await findRoomFiles(entry.path);
        files.push(...subFiles);
      } else if (entry.name.endsWith('.yaml') && !entry.name.startsWith('_')) {
        files.push(entry.path);
      }
    }
  } catch {
    // Directory doesn't exist or can't be read
  }

  return files;
}

// Try to extract x,y,z coordinates from room ID (e.g., "room_1_2_0" -> {x:1, y:2, z:0})
function extractCoordinates(roomId: string): { x: number; y: number; z: number } | null {
  const match = roomId.match(/room_(\d+)_(\d+)_(\d+)/);
  if (match) {
    return {
      x: parseInt(match[1], 10),
      y: parseInt(match[2], 10),
      z: parseInt(match[3], 10),
    };
  }
  return null;
}

// Convert 3D coords to isometric 2D position
function toIsometric(x: number, y: number, z: number, gridSize: number): { x: number; y: number } {
  // Grid-aligned projection where:
  // - East (+X) → purely right on screen (horizontal axis)
  // - North (+Y) → up on screen (vertical axis)
  // - Up (+Z) → diagonal offset (up-right) to separate from north/south
  const isoX = x * gridSize + z * gridSize * 0.6; // Z offsets right
  const isoY = -y * gridSize - z * gridSize * 0.6; // Negative Y so north goes up, Z also goes up
  return { x: isoX, y: isoY };
}

// Calculate room positions using layout files first, then fall back to auto-layout
async function calculateRoomPositionsWithLayouts(
  rooms: RoomNode[],
  roomExits: Map<string, Record<string, string>>,
  roomAreaPaths: Map<string, string>,
  layouts: Map<string, AreaLayout>,
  loadLayout: (areaPath: string) => Promise<AreaLayout | null>
): Promise<RoomNode[]> {
  const positioned = new Map<string, { x: number; y: number }>();
  
  // Group rooms by area path
  const roomsByAreaPath = new Map<string, RoomNode[]>();
  for (const room of rooms) {
    const areaPath = roomAreaPaths.get(room.id) || '';
    if (!roomsByAreaPath.has(areaPath)) {
      roomsByAreaPath.set(areaPath, []);
    }
    roomsByAreaPath.get(areaPath)!.push(room);
  }
  
  // Process each area
  for (const [areaPath, areaRooms] of roomsByAreaPath.entries()) {
    // Try to load layout for this area
    let layout = layouts.get(areaPath);
    if (!layout && areaPath) {
      layout = await loadLayout(areaPath) ?? undefined;
    }
    
    // If we have a layout, use it for rooms that have positions
    if (layout) {
      for (const room of areaRooms) {
        const layoutPos = layout.rooms[room.id];
        if (layoutPos) {
          // Convert grid coordinates to pixel positions
          const gridSize = layout.grid_size ?? GRID_SIZE;
          positioned.set(room.id, {
            x: layoutPos.x * gridSize,
            y: layoutPos.y * gridSize,
          });
        }
      }
    }
  }
  
  // For rooms without layout positions, use auto-layout
  const unpositionedRooms = rooms.filter((r) => !positioned.has(r.id));
  if (unpositionedRooms.length > 0) {
    const autoPositioned = calculateRoomPositions(unpositionedRooms, roomExits);
    for (const room of autoPositioned) {
      if (!positioned.has(room.id)) {
        positioned.set(room.id, room.position);
      }
    }
  }
  
  // Apply positions to all rooms
  return rooms.map((room) => ({
    ...room,
    position: positioned.get(room.id) || { x: 0, y: 0 },
  }));
}

// Simple force-directed-ish layout based on exits (fallback when no layout file)
function calculateRoomPositions(
  rooms: RoomNode[],
  roomExits: Map<string, Record<string, string>>
): RoomNode[] {
  const positioned = new Map<string, { x: number; y: number }>();
  const gridSize = 150;
  const clusterGap = 500; // Gap between disconnected clusters

  // Group rooms by area_id for better initial clustering
  const roomsByArea = new Map<string, RoomNode[]>();
  for (const room of rooms) {
    const areaId = room.area_id || 'unknown';
    if (!roomsByArea.has(areaId)) {
      roomsByArea.set(areaId, []);
    }
    roomsByArea.get(areaId)!.push(room);
  }

  let clusterOffsetX = 0;

  // Process each area as a separate cluster
  for (const [areaId, areaRooms] of roomsByArea.entries()) {
    // Check if this area uses coordinate-based room IDs
    const hasCoordinates = areaRooms.some((r) => extractCoordinates(r.id) !== null);

    if (hasCoordinates) {
      // Use isometric projection for coordinate-based rooms
      for (const room of areaRooms) {
        const coords = extractCoordinates(room.id);
        if (coords) {
          const pos = toIsometric(coords.x, coords.y, coords.z, gridSize);
          positioned.set(room.id, { x: clusterOffsetX + pos.x, y: pos.y });
        }
      }
      // Calculate bounds for cluster offset
      let maxX = clusterOffsetX;
      for (const room of areaRooms) {
        const pos = positioned.get(room.id);
        if (pos) maxX = Math.max(maxX, pos.x);
      }
      clusterOffsetX = maxX + clusterGap;
    } else {
      // Use BFS-based layout for regular rooms
      const startRoom = areaRooms.find((r) => r.id.includes('center')) || areaRooms[0];
      if (!startRoom) continue;

      const queue: Array<{ roomId: string; x: number; y: number }> = [
        { roomId: startRoom.id, x: clusterOffsetX, y: 0 },
      ];
      positioned.set(startRoom.id, { x: clusterOffsetX, y: 0 });

      let minX = clusterOffsetX;
      let maxX = clusterOffsetX;

      while (queue.length > 0) {
        const current = queue.shift()!;
        const exits = roomExits.get(current.roomId) || {};

        for (const [direction, targetId] of Object.entries(exits)) {
          if (positioned.has(targetId)) continue;

          // Calculate position based on direction offset
          const offset = directionOffsets[direction] ?? { dx: 0, dy: 0 };
          const newX = current.x + offset.dx * gridSize;
          const newY = current.y + offset.dy * gridSize;

          positioned.set(targetId, { x: newX, y: newY });
          queue.push({ roomId: targetId, x: newX, y: newY });

          minX = Math.min(minX, newX);
          maxX = Math.max(maxX, newX);
        }
      }

      // Position any unvisited rooms in this area in a grid below
      let gridRow = 0;
      let gridCol = 0;
      for (const room of areaRooms) {
        if (!positioned.has(room.id)) {
          const x = clusterOffsetX + gridCol * gridSize;
          const y = 300 + gridRow * gridSize;
          positioned.set(room.id, { x, y });
          gridCol++;
          if (gridCol >= 3) {
            gridCol = 0;
            gridRow++;
          }
        }
      }

      // Move offset for next cluster
      clusterOffsetX = maxX + clusterGap;
    }
  }

  // Apply positions to rooms
  return rooms.map((room) => ({
    ...room,
    position: positioned.get(room.id) || { x: 0, y: 0 },
  }));
}

// Build connections from exits map
function buildConnections(roomExits: Map<string, Record<string, string>>): RoomConnection[] {
  const connections: RoomConnection[] = [];
  // Track edges we've already created (using sorted room IDs + direction pair as key)
  const processedPairs = new Set<string>();

  for (const [sourceId, exits] of roomExits.entries()) {
    for (const [direction, targetId] of Object.entries(exits)) {
      // Skip null exits
      if (!targetId) continue;
      
      // Create a canonical key for this pair of rooms (sorted IDs)
      const [first, second] = [sourceId, targetId].sort();
      const pairKey = `${first}--${second}`;
      
      // If we've already created an edge for this pair, skip
      if (processedPairs.has(pairKey)) continue;
      
      // Check if the target room has a reverse exit back to source
      const targetExits = roomExits.get(targetId);
      const reverseDirection = oppositeDirection[direction];
      const isBidirectional = targetExits && 
        Object.entries(targetExits).some(([dir, dest]) => 
          dest === sourceId && dir === reverseDirection
        );
      
      // Mark this pair as processed
      processedPairs.add(pairKey);
      
      // Target handle is the opposite direction (handles now work as both source and target)
      const opposite = oppositeDirection[direction] || direction;
      
      // Use a consistent ID (source is always the "first" room alphabetically for bidirectional)
      const id = isBidirectional 
        ? `${first}-${second}-bidirectional`
        : `${sourceId}-${direction}-${targetId}`;
      
      connections.push({
        id,
        source: sourceId,
        target: targetId,
        sourceHandle: direction,
        targetHandle: opposite,
        bidirectional: isBidirectional,
      });
    }
  }

  return connections;
}
