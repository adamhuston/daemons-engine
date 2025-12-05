# Daemonswright User Experience Design

> **Purpose:** Define the complete user experience for the Daemonswright Content Studio, with focus on the Room Builder as the primary visual editor.

---

## Editor Categories

Daemonswright provides three categories of editors, each optimized for different content types:

| Editor | Purpose | Visual Component | Content Types |
|--------|---------|------------------|---------------|
| **Room Builder** | Spatial content with connections | React Flow canvas | Rooms, exits, layers |
| **Entity Editor** | Template-based content | Form-based with YAML toggle | NPCs, Items, Abilities, Classes |
| **Graph Designer** | Branching/sequential content | React Flow canvas | Quests, Dialogues (future) |

---

## Room Builder

The Room Builder is the primary visual editor for world geography. It provides a canvas-based interface for creating and connecting rooms.

### Core Concept

The Room Builder is a **visual, bidirectional editor** where:
- The canvas visualizes YAML files from `world_data/rooms/`
- Every action on the canvas writes to YAML files
- Every YAML file change updates the canvas (via file watcher)
- Room contents (NPCs, items) are managed through separate spawn/instance files

### Data Architecture

Based on the existing schema structure:

```
world_data/
├── rooms/
│   ├── _schema.yaml        # Room field definitions
│   ├── _layout.yaml        # Canvas positions (CMS-only, TBD)
│   └── {area}/
│       └── *.yaml          # Room definitions
├── npc_spawns/
│   └── *.yaml              # NPC → room_id mappings
└── item_instances/
    └── *.yaml              # Item → room_id mappings
```

**Key Insight:** Rooms do NOT contain lists of NPCs/items. Instead:
- NPCs reference rooms via `room_id` in `npc_spawns/*.yaml`
- Items reference rooms via `room_id` in `item_instances/*.yaml`

This means the Room Builder must scan spawn/instance files to display room contents.

---

## Room Builder Features

### 1. Canvas & Navigation

| Feature | Behavior | File Impact |
|---------|----------|-------------|
| Pan & Zoom | Navigate the map | None |
| Multi-layer view | Tabs or z-level selector for floors | None |
| Grid snapping | Optional alignment grid | None |
| Minimap | Overview of large maps | None |
| Layer switching | Click layer tab to view that z_level | None |

### 2. Room Nodes

| Feature | Behavior | File Impact |
|---------|----------|-------------|
| **Add Room** | Click canvas or [+] button, enter ID | Creates `rooms/{area}/{id}.yaml` |
| **Select Room** | Click node → properties panel opens | None |
| **Move Room** | Drag node on canvas | Updates `_layout.yaml` (position only) |
| **Delete Room** | Delete key or context menu | Deletes room YAML, updates exit references |
| **Edit Properties** | Sidebar form fields | Updates room YAML fields |

**Room Properties Panel:**
- `id` (read-only after creation)
- `name` (display name)
- `description` (room text, multiline)
- `area_id` (area association)
- `z_level` (vertical layer)
- `room_type` (ethereal, forest, cave, urban, etc.)
- `lighting_override` (optional)
- `on_enter_effect` / `on_exit_effect` (optional)

### 3. Exit Edges

| Feature | Behavior | File Impact |
|---------|----------|-------------|
| **Create Exit** | Drag from room edge to another room | Adds `exits.{direction}` to source room YAML |
| **Bidirectional Exit** | Toggle or prompt | Adds exits to both room YAMLs |
| **Delete Exit** | Click edge → delete | Removes exit from room YAML(s) |
| **Edit Exit Properties** | Click edge → sidebar | Updates exit in room YAML |

**Exit Properties:**
- `direction` (north, south, east, west, up, down, or custom)
- `destination` (target room ID)
- Additional properties can be stored in extended exit format

**Standard Directions:**
- Cardinal: north, south, east, west
- Vertical: up, down
- Custom: any string (e.g., "portal", "secret", "trapdoor")

### 4. Layers (Z-Levels)

| Feature | Behavior | File Impact |
|---------|----------|-------------|
| **Layer Tabs** | Switch between z_levels | None (view only) |
| **Auto-detect Layers** | Scan rooms for unique z_level values | None |
| **Create Up/Down Exit** | Creates exit + prompts for new room | Creates room YAML with offset z_level |
| **Layer Overview** | Optional stacked/side-by-side view | None |

**Layer Behavior:**
- Layers are derived from room `z_level` values (integer)
- Creating an "up" exit to empty space prompts: "Create new room on Layer {z+1}?"
- New rooms auto-populate with correct `z_level`
- Layer names can be stored in `_layout.yaml` (optional, CMS-only)

### 5. Room Contents (NPCs & Items)

| Feature | Behavior | File Impact |
|---------|----------|-------------|
| **View Contents** | Badges/icons on room node | None (read from spawn/instance files) |
| **Add NPC to Room** | Drag from palette or picker | Adds entry to `npc_spawns/*.yaml` |
| **Add Item to Room** | Drag from palette or picker | Adds entry to `item_instances/*.yaml` |
| **Remove from Room** | Context menu or drag out | Removes entry from spawn/instance file |
| **Quick-Create NPC** | Right-click → "New NPC here" | Creates NPC template + spawn entry |
| **Quick-Create Item** | Right-click → "New Item here" | Creates item template + instance entry |
| **Edit Spawn/Instance** | Click content badge → sidebar | Updates spawn/instance YAML |

**Content Display:**
- Room nodes show badges: 👤 (NPC count), 📦 (item count)
- Hover or click to see list of contents
- Contents panel in sidebar when room selected

---

## UI Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ [File] [Edit] [View] [Tools]                          [🔗 Server]  │
├────────────┬────────────────────────────────────────┬───────────────┤
│  LAYERS    │                                        │  PROPERTIES   │
│            │                                        │               │
│ [+] Add    │     ┌─────┐    ┌─────┐                │ Room: cave    │
│            │     │Cave │────│Hall │                │               │
│ ○ Layer 2  │     └──┬──┘    └─────┘                │ Name: [     ] │
│ ○ Layer 1  │        │                              │ Desc: [     ] │
│ ● Layer 0  │     ┌──┴──┐                           │ Zone: [     ] │
│   (current)│     │Pit  │                           │ Type: [     ] │
│            │     └─────┘                           │               │
│ ─────────  │                                        │ ─── Exits ─── │
│  PALETTE   │        [CANVAS]                       │ N → hall      │
│            │                                        │ D → pit       │
│ 📦 Items   │                                        │               │
│ 👤 NPCs    │                                        │ ─ Contents ── │
│            │                                        │ 👤 goblin (1) │
│ [Search]   │                                        │ 📦 torch  (2) │
│            │                                        │ [+ Add...]    │
├────────────┴────────────────────────────────────────┴───────────────┤
│ Layer 0 │ Rooms: 12 │ 💾 Saved │ Selected: cave                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Interaction Patterns

### Creating a Room

1. Double-click empty canvas space (or click [+] button in toolbar)
2. Modal appears: enter room ID (validated: lowercase, no spaces, unique)
3. Room node appears at click location
4. Properties panel opens with focus on Name field
5. Fill in name, description, room_type
6. On save: `rooms/{area}/{id}.yaml` is created

### Creating an Exit

1. Hover over room node → directional handles appear (N/S/E/W edges, U/D corners)
2. Drag from handle toward destination room
3. Edge snaps to destination room
4. Exit direction auto-determined by handle used
5. Source room's YAML updated with exit
6. Prompt: "Create return exit?" → if yes, destination room also updated

### Creating Vertical Exits (Up/Down)

1. Select room → click "Add Exit" dropdown → choose "Up" or "Down"
2. If room exists at target z_level: connect to it
3. If no room exists: prompt "Create new room on Layer {z}?"
4. If yes: new room created, layer tab added if needed
5. Both rooms' YAMLs updated with reciprocal exits

### Placing NPCs/Items

1. Expand Palette panel (left sidebar)
2. Search or browse existing NPC templates / item templates
3. Drag onto a room node
4. For NPCs: entry added to `npc_spawns/{area}_spawns.yaml`
5. For Items: entry added to `item_instances/{area}_items.yaml`
6. Room node updates to show content badge

### Quick-Create NPC/Item

1. Right-click room node → "New NPC here" or "New Item here"
2. Entity Editor opens in modal/side panel
3. Fill in template properties (name, stats, etc.)
4. On save: template created + spawn/instance entry created
5. Room updates to show new content

---

## File Operations Summary

| User Action | Files Read | Files Written |
|-------------|------------|---------------|
| Open Room Builder | `rooms/**/*.yaml`, `npc_spawns/*.yaml`, `item_instances/*.yaml`, `_layout.yaml` | None |
| Move room on canvas | None | `_layout.yaml` |
| Edit room properties | None | `rooms/{area}/{id}.yaml` |
| Create room | None | `rooms/{area}/{id}.yaml`, `_layout.yaml` |
| Delete room | None | Deletes `rooms/{area}/{id}.yaml`, updates `_layout.yaml`, updates rooms with exits to deleted room |
| Create exit | None | Source room YAML (+ destination if bidirectional) |
| Delete exit | None | Room YAML(s) containing the exit |
| Place NPC | None | `npc_spawns/{file}.yaml` |
| Place Item | None | `item_instances/{file}.yaml` |
| Remove NPC/Item | None | Corresponding spawn/instance file |

---

## Entity Editor

The Entity Editor handles creation and editing of templates that don't require spatial visualization:

- **NPC Templates** (`npcs/*.yaml`)
- **Item Templates** (`items/*.yaml`)
- **Abilities** (`abilities/*.yaml`)
- **Classes** (`classes/*.yaml`)
- **Factions** (`factions/*.yaml`)
- **Triggers** (`triggers/*.yaml`)

### Features

- **Form View:** Auto-generated forms from `_schema.yaml` definitions
- **YAML View:** Toggle to raw Monaco editor with syntax highlighting
- **Validation:** Real-time schema validation in both views
- **Preview:** Where applicable (item stats, NPC combat preview)
- **Cross-references:** Links to related content (e.g., NPC → Dialogue)

### Relationship to Room Builder

- Room Builder handles **placement** (where things spawn)
- Entity Editor handles **definition** (what things are)
- Quick-create in Room Builder opens Entity Editor in modal
- Clicking a content badge can jump to Entity Editor for that template

---

## Graph Designer (Future)

For content with branching/sequential structure:

- **Quest Designer:** Quest chains as flowcharts
- **Dialogue Editor:** Conversation trees

Uses same React Flow foundation as Room Builder, but with different node types and connection semantics.

---

## Layout System

### Overview

Room positions on the canvas are stored separately from room content in `_layout.yaml` files. This decouples visual layout from game data, allowing:

- Room IDs to be descriptive (no encoded coordinates)
- Easy layout reorganization without touching room content
- CMS-only data that doesn't affect the game engine

### Coordinate System

Positions use **grid coordinates**, not pixel coordinates:

- **X axis:** East (+) / West (-)
- **Y axis:** North (-) / South (+) — matches screen coordinates where Y increases downward
- **Z axis:** Up (+) / Down (-) — vertical layers

The CMS multiplies grid coordinates by a configurable grid size (e.g., 150px) for canvas rendering.

### Grid Snapping

When moving rooms on the canvas:
- Rooms snap to the nearest grid intersection
- Grid coordinates are integers
- Visual feedback shows grid lines during drag

### Layer Visualization

Layers (Z-levels) are displayed with visual offset to create a stacking effect:
- Each layer's grid is offset diagonally (e.g., +20px X, -20px Y per Z level)
- Lower layers appear "behind" higher layers
- Layer tabs switch which layer is actively editable
- Non-active layers can be dimmed or hidden

### File Location

Layout files are stored per-area in the rooms directory:

```
world_data/rooms/
├── _schema.yaml
├── caves/
│   ├── _layout.yaml      # Layout for caves area
│   └── *.yaml            # Room files
├── meadow/
│   ├── _layout.yaml      # Layout for meadow area
│   └── *.yaml
└── ethereal/
    ├── _layout.yaml
    └── *.yaml
```

### `_layout.yaml` Schema

```yaml
# Layout file for an area
# Managed by Daemonswright, not the game engine

# Schema version for future migrations
version: 1

# Grid size in pixels (optional, default: 150)
grid_size: 150

# Room positions in grid coordinates
rooms:
  room_cave_entrance:
    x: 0
    y: 0
    z: 0
  room_cave_tunnel_north:
    x: 0
    y: -1
    z: 0
  room_cave_tunnel_east:
    x: 1
    y: 0
    z: 0
  room_cave_depths:
    x: 0
    y: -2
    z: 0
  room_cave_upper_chamber:
    x: 0
    y: -1
    z: 1    # One level up, directly above tunnel_north
  room_cave_basement:
    x: 1
    y: 0
    z: -1   # One level down, below tunnel_east

# Optional: human-readable layer names
layer_names:
  -1: "Basement"
  0: "Ground Level"
  1: "Upper Chambers"

# Optional: viewport state (restored on open)
viewport:
  center_x: 0
  center_y: 0
  zoom: 1.0
  active_layer: 0
```

### Behavior

**On Room Builder Open:**
1. Load all room YAMLs from area directory
2. Load `_layout.yaml` for positions
3. Rooms without layout entries are placed at (0, 0, 0) or auto-arranged
4. Derive layer tabs from unique Z values in layout

**On Room Move:**
1. Snap to nearest grid coordinate
2. Update `rooms.{id}.x`, `rooms.{id}.y` in `_layout.yaml`
3. Z only changes via explicit layer move action

**On Room Create:**
1. Place at clicked grid coordinate
2. Add entry to `_layout.yaml`
3. Create room YAML file

**On Room Delete:**
1. Remove entry from `_layout.yaml`
2. Delete room YAML file

**On Layer Change (move room to different Z):**
1. Update `rooms.{id}.z` in `_layout.yaml`
2. Update `z_level` in room YAML (keeps game data in sync)

### Auto-Layout for New Areas

When opening an area with rooms but no `_layout.yaml`:
- Auto-generate positions based on exit connections
- Use graph layout algorithm (e.g., force-directed)
- Save generated layout to `_layout.yaml`
- User can manually adjust afterward

---

## Remaining Design Decisions

### Spawn File Organization
When placing an NPC in a room, which spawn file to update?
- One spawn file per area (e.g., `ethereal_spawns.yaml`)
- One spawn file per room (granular but many files)
- User chooses / CMS decides based on area

**Current approach:** Match existing pattern - area-based spawn files.

### Bulk Operations
Future consideration:
- Multi-select rooms → bulk move, bulk property change
- Multi-select exits → bulk delete
- Select region → move to different area

---

## Implementation Priority

### Phase 1: Core Canvas
1. Room node display from YAML files
2. Exit edge display
3. Layer tabs from z_level values
4. Pan, zoom, select

### Phase 2: Room Editing
1. Properties panel with form fields
2. Save to YAML on change
3. Create new rooms
4. Delete rooms

### Phase 3: Exit Editing
1. Create exits by dragging
2. Bidirectional exit creation
3. Delete exits
4. Vertical exits with layer creation

### Phase 4: Content Placement
1. Display NPC/item badges on rooms
2. Palette panel with search
3. Drag-to-place functionality
4. Remove content from rooms

### Phase 5: Entity Editor Integration
1. Quick-create from Room Builder
2. Jump to Entity Editor from content badge
3. Unified save/validation

---

## Technical Considerations

### File Watching
- Use `chokidar` to watch `world_data/` directory
- Debounce rapid changes
- Handle external edits (user editing YAML directly)
- Conflict resolution if CMS and external edit collide

### Performance
- Lazy load room contents (don't scan all spawn files on open)
- Cache parsed YAML with invalidation on file change
- Virtual rendering for large maps (100+ rooms)

### Undo/Redo
- Track YAML file changes as undo stack
- Undo = restore previous file content
- Consider git integration for persistent undo

---

*Last Updated: December 2024*
*Status: Design Phase*
