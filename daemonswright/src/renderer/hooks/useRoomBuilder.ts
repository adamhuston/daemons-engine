/**
 * useRoomBuilder Hook
 *
 * Loads room YAML files from the workspace and converts them to
 * React Flow nodes and edges for the Room Builder canvas.
 */

import { useState, useCallback, useEffect, useMemo } from 'react';
import yaml from 'js-yaml';
import type { RoomNode, RoomConnection } from '../../shared/types';

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
  updateRoomPosition: (roomId: string, position: { x: number; y: number }) => void;
  addConnection: (source: string, target: string, direction: string) => void;
  removeConnection: (connectionId: string) => void;
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

      // Parse all room files
      for (const filePath of roomFiles) {
        try {
          const content = await window.daemonswright.fs.readFile(filePath);
          const parsed = yaml.load(content) as RoomYaml;

          if (parsed && parsed.id) {
            // Extract z_level from coordinate ID or use explicit field
            const coords = extractCoordinates(parsed.id);
            const zLevel = parsed.z_level ?? coords?.z ?? 0;

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
            });

            if (parsed.exits) {
              roomExits.set(parsed.id, parsed.exits);
            }
          }
        } catch (err) {
          console.warn(`Failed to parse room file: ${filePath}`, err);
        }
      }

      // Calculate positions using a simple layout algorithm
      const positionedRooms = calculateRoomPositions(loadedRooms, roomExits);

      // Build connections from exits
      const builtConnections = buildConnections(roomExits);

      setRooms(positionedRooms);
      setConnections(builtConnections);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load rooms');
      console.error('Failed to load rooms:', err);
    } finally {
      setIsLoading(false);
    }
  }, [worldDataPath]);

  // Auto-load rooms when worldDataPath changes
  useEffect(() => {
    if (worldDataPath) {
      loadRooms();
    }
  }, [worldDataPath, loadRooms]);

  // Update a room's position (called after drag)
  const updateRoomPosition = useCallback((roomId: string, position: { x: number; y: number }) => {
    setRooms((prev) =>
      prev.map((room) => (room.id === roomId ? { ...room, position } : room))
    );
  }, []);

  // Add a new connection
  const addConnection = useCallback((source: string, target: string, direction: string) => {
    const id = `${source}-${direction}-${target}`;
    setConnections((prev) => [
      ...prev,
      {
        id,
        source,
        target,
        sourceHandle: direction,
        targetHandle: oppositeDirection[direction] || 'any',
      },
    ]);
  }, []);

  // Remove a connection
  const removeConnection = useCallback((connectionId: string) => {
    setConnections((prev) => prev.filter((c) => c.id !== connectionId));
  }, []);

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
    addConnection,
    removeConnection,
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

// Simple force-directed-ish layout based on exits
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
  const seen = new Set<string>();

  for (const [sourceId, exits] of roomExits.entries()) {
    for (const [direction, targetId] of Object.entries(exits)) {
      // Skip null exits
      if (!targetId) continue;
      
      // Create unique key to avoid duplicates
      const key = [sourceId, targetId].sort().join('-');
      if (seen.has(key)) continue;
      seen.add(key);

      // Target handle is the opposite direction with '-in' suffix
      const opposite = oppositeDirection[direction] || direction;
      
      connections.push({
        id: `${sourceId}-${direction}-${targetId}`,
        source: sourceId,
        target: targetId,
        sourceHandle: direction,
        targetHandle: `${opposite}-in`,
      });
    }
  }

  return connections;
}
