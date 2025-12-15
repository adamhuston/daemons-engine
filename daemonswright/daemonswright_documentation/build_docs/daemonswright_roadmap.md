# Daemonswright Content Studio - Implementation Roadmap

> **Vision:** A batteries-included dev tool that ships with the Daemons engine package. Runs locally, works offline, uses local schemas. No cloud, no auth, no complexity.

```
pip install daemons-engine
daemons-studio  # launches content editor
```

---

## 4-Phase Implementation Roadmap

**Total Timeline: 10-13 weeks** (single developer)

---

### **Phase 1: Core Editor (3-4 weeks)** ✅ COMPLETE
**Goal:** Working YAML editor with schema validation

**Critical Path:**
- [x] Electron + React + TypeScript project boilerplate
- [x] Basic UI shell (file tree, editor panel, status bar)
- [x] Local schema parser (read `world_data/*/_schema.yaml` directly)
- [x] Zod validator generation from schemas
- [x] Monaco YAML editor integration
- [x] Schema-aware IntelliSense (auto-complete fields/values)
- [x] Real-time validation as you type
- [x] Save/load YAML files to disk
- [x] File watcher (detect external changes)
- [x] Settings persistence (last opened folder, window state)

**Success Criteria:** ✅ All met
- Can open a `world_data/` folder
- Edit any YAML file with auto-complete and validation
- Changes save to disk immediately

---

### **Phase 2: Room Builder (2-3 weeks)** 🔄 IN PROGRESS
**Goal:** Visual room editing with full CRUD operations

> **Reference:** See `daemonswright_userexperience.md` for complete UX specification

**Data Architecture:**
- Rooms stored in `world_data/rooms/{area}/*.yaml`
- Layout positions stored in `world_data/rooms/{area}/_layout.yaml` (CMS-only)
- NPCs reference rooms via `npc_spawns/*.yaml`
- Items reference rooms via `item_instances/*.yaml`


**Layout System:**
- [ ] Grid-based coordinate system (X=east/west, Y=north/south, Z=up/down)
- [ ] Per-area `_layout.yaml` files with room positions
- [ ] Grid snapping when moving rooms
- [x] Auto-layout generation for areas without `_layout.yaml` *(uses BFS from exits + isometric projection for coordinate IDs)*

**Canvas & Navigation:**
- [x] React Flow canvas integration
- [x] Pan and zoom controls
- [x] Layer tabs derived from unique Z values *(area filter + layer selector)*
- [x] Layer stacking visualization (diagonal offset per Z-level) *(isometric projection)*
- [x] Active layer highlighting (dim non-active layers) *(opacity-based, non-active layers at 25%)*

**Room Operations:**
- [x] Load rooms from YAML → canvas nodes
- [ ] Create room: click canvas → enter ID → create YAML + layout entry
- [ ] Delete room: remove YAML file + layout entry + update exit references
- [x] Move room: drag on canvas *(positions update in memory, not persisted to `_layout.yaml` yet)*
- [ ] Room properties panel (name, description, room_type, etc.)
- [ ] Bidirectional sync (canvas ↔ YAML files) *(read works, write not implemented)*

**Exit Operations:**
- [x] Display exits as edges between room nodes *(styled by direction: yellow for up/down, green for cardinal)*
- [x] Create exit: drag from directional handle to destination room *(connection callback exists)*
- [ ] Bidirectional exit prompt on creation
- [x] Delete exit: click edge → delete from room YAML(s)
- [ ] Vertical exits (up/down) with layer creation prompt

**Room Contents Display:**
- [x] Scan `npc_spawns/*.yaml` for NPCs in each room *(useRoomContents hook)*
- [x] Scan `item_instances/*.yaml` for items in each room *(useRoomContents hook)*
- [x] Display content badges on room nodes (👤 NPC count, 📦 item count)
- [x] Contents list in properties panel when room selected *(tabbed NPC/Items panels)*

**Core Features:**
- [x] Undo/redo for all operations *(history-based with Ctrl+Z/Ctrl+Shift+Z)*
- [x] Copy/paste rooms *(Ctrl+C/V with unique ID generation)*
- [ ] Canvas state persistence (zoom, pan, active layer)
- [x] File watcher for external YAML changes *(implemented in useFileWatcher hook)*

**Success Criteria:**
- [x] Room canvas shows all rooms in an area with grid layout
- [x] Rooms snap to grid when dragged *(snaps on drag stop)*
- [x] Layer tabs appear based on room Z values
- [x] Creating exit by dragging updates source room YAML
- [x] Creating room creates both YAML file and `_layout.yaml` entry
- [x] NPC/item badges appear on rooms (from spawn/instance files)
- [x] Undo/redo works for all room operations


---

### **Phase 3: Visual Tools & Entity Editors (3-4 weeks)**
**Goal:** Extend visual editing to other content types and complete Room Builder

> **Reference:** See `daemonswright_userexperience.md` for complete UX specification

**Room Builder - Content Placement:**
- [ ] Palette panel (left sidebar) with NPC/item browser
- [ ] Search/filter NPCs and items
- [ ] Drag-to-place: drop NPC → add to `npc_spawns/*.yaml`
- [ ] Drag-to-place: drop item → add to `item_instances/*.yaml`
- [ ] Remove content from room (update spawn/instance file)
- [ ] Quick-create NPC/item from room context menu

**Entity Editor (Form-Based):**
- [ ] Auto-generated forms from `_schema.yaml` definitions
- [ ] Toggle between Form view and YAML view
- [ ] Real-time schema validation in both views
- [ ] Entity types:
  - [ ] NPC Templates (`npcs/*.yaml`)
  - [ ] Item Templates (`items/*.yaml`)
  - [ ] Abilities (`abilities/*.yaml`)
  - [ ] Classes (`classes/*.yaml`)
  - [ ] Factions (`factions/*.yaml`)
  - [ ] Triggers (`triggers/*.yaml`)
- [ ] Cross-reference links (e.g., NPC → Dialogue)
- [ ] Jump to Entity Editor from Room Builder content badge

---

#### Quest Designer (Flowchart-Based) 🆕

**Current State:** Basic React Flow canvas with quest nodes and prerequisite edges exists but lacks content-focused UX.

**Problem:** Current implementation treats quests as simple connected boxes, but the real value is in editing objectives, rewards, and quest chain sequences.

**Recommended Architecture - "Quest Chain Flowchart":**

**Left Sidebar - Chain Browser:**
- [ ] Quest chain list with expand/collapse
- [ ] Chain shows member quests in sequence order
- [ ] Standalone quests section (not in any chain)
- [ ] Create new chain / Create new quest buttons

**Canvas - Chain Visualization:**
- [ ] Quest nodes show objective icons inline (⚔️ kill, 📦 collect, 📍 visit, 💬 talk)
- [ ] Reward summary visible on node (XP, key items)
- [ ] Prerequisite arrows between quests (solid)
- [ ] Chain sequence indicators (dotted lines within chain)
- [ ] Dagre auto-layout (top-to-bottom for chains)
- [ ] Manual repositioning with grid snap

**Quest Node Design:**
```
┌──────────────────────────────────────┐
│ 🏆 wisp_investigation                │
│ "Ethereal Mysteries"                 │
│ ─────────────────────────────────    │
│ 📍→📍→💬 (objectives sequence)       │
│ 🎁 50 XP, Health Potion ×2           │
└──────────────────────────────────────┘
```

**Properties Panel (Right Sidebar):**
- [ ] Tabs: Details | Objectives | Rewards | Dialogue
- [ ] **Details Tab:** name, description, category, giver NPC, level req
- [ ] **Objectives Tab:** 
  - Drag-to-reorder objective list
  - Add objective with type selector
  - Per-objective: type, description, target, count, hidden, optional
- [ ] **Rewards Tab:**
  - XP, gold inputs
  - Item picker with quantity
  - Flag setter
  - Ability unlocker
- [ ] **Dialogue Tab:**
  - Accept/progress/complete dialogue text areas
  - Link to full dialogue editor

**Chain Properties (when chain selected):**
- [ ] Chain name, description
- [ ] Quest sequence (drag to reorder)
- [ ] Chain bonus rewards editor
- [ ] Unlock requirements editor

**File Operations:**
| Action | Files Written |
|--------|---------------|
| Create quest | `quests/{category}/{id}.yaml`, `quests/_layout.yaml` |
| Edit quest | `quests/{category}/{id}.yaml` |
| Delete quest | Remove file, update references |
| Create chain | `quest_chains/{id}.yaml` |
| Edit chain | `quest_chains/{id}.yaml` |
| Reorder chain | `quest_chains/{id}.yaml` |

---

#### Dialogue Editor (Tree-Based) 🆕

**Current State:** Basic React Flow canvas with dialogue nodes exists but treats conversations as flat node graphs.

**Problem:** Dialogues are inherently branching trees, not arbitrary graphs. Player response options are the key UX element and need visual prominence.

**Recommended Architecture - "Conversation Tree":**

**Left Sidebar - Dialogue Browser:**
- [ ] NPC template list (dialogue trees keyed by NPC)
- [ ] Search/filter NPCs
- [ ] Create new dialogue tree button
- [ ] Entry overrides summary for selected tree

**Canvas - Tree Visualization:**
- [ ] Hierarchical tree layout (ELK or Dagre hierarchical)
- [ ] NPC nodes (larger, with text preview)
- [ ] Option nodes (smaller, player choice text)
- [ ] Visual connector: NPC → options branch out → next NPC nodes
- [ ] Entry point indicator (🎯 on entry node)
- [ ] Conditional entry indicators (⚡ on override targets)
- [ ] Action badges on options (🎯 quest, 🎁 items, 🚀 teleport)

**Node Types:**
```
NPC Node (large):
┌─────────────────────────────────────┐
│ 🎭 greet                      [📍]  │
│ "Ah, a traveler! Welcome,          │
│  welcome. Name's Aldric..."        │
└────────┬────────┬────────┬─────────┘
         │        │        │
         ▼        ▼        ▼
      Option   Option   Option
       nodes    nodes    nodes

Option Node (small):
┌─────────────────────────┐
│ "What help?"      🎯    │  ← 🎯 = accepts quest
└────────────┬────────────┘
             ▼
        NPC Node
```

**Properties Panel (Right Sidebar):**
- [ ] Tabs: Text | Options | Conditions | Actions
- [ ] **Text Tab:** Multi-line NPC dialogue editor
- [ ] **Options Tab:**
  - List of player response options
  - Per-option: text, next_node dropdown, action badges
  - Add/remove/reorder options
  - Quick-add option with auto-generated node
- [ ] **Conditions Tab (for entry overrides):**
  - Condition builder (quest status, flags, level)
  - Entry override list showing which node loads when
- [ ] **Actions Tab (per-option):**
  - Accept/turn-in quest selector
  - Give/remove items
  - Set flags
  - Grant XP
  - Teleport destination

**Entry Overrides Panel:**
- [ ] Visual list of conditional entry points
- [ ] Condition → Node mapping
- [ ] Drag to reorder priority
- [ ] "Test Conditions" simulator

**File Operations:**
| Action | Files Written |
|--------|---------------|
| Create dialogue tree | `dialogues/{npc_template_id}.yaml` |
| Edit node text | `dialogues/{npc_template_id}.yaml` |
| Add/edit option | `dialogues/{npc_template_id}.yaml` |
| Add node | `dialogues/{npc_template_id}.yaml` |
| Update layout | `dialogues/{npc_template_id}_layout.yaml` |

---

#### Shared Graph Infrastructure

Both Quest Designer and Dialogue Editor share React Flow foundation:

**Shared Components:**
- [ ] `GraphDesigner` base component with common patterns
- [ ] Auto-layout algorithms (Dagre for quest chains, ELK for dialogue trees)
- [ ] Properties panel framework with tabs
- [ ] Node context menus
- [ ] Edge creation/deletion patterns
- [ ] Layout persistence pattern (`*_layout.yaml`)
- [ ] Undo/redo history stack

**Shared Utilities:**
- [ ] YAML read/write helpers per content type
- [ ] Reference resolver (NPC → dialogue, quest → objectives)
- [ ] Validation helpers

---

**Validation & Navigation:**
- [ ] Reference validation (detect broken links locally)
- [ ] "Jump to definition" for referenced content
- [ ] Error panel showing all validation issues

**Success Criteria:**
- Can place NPCs/items in rooms from palette
- Entity Editor generates valid YAML from forms
- Quest chains visualized as flowcharts with objective previews
- Dialogue trees show branching structure with option nodes
- Clicking room content badge opens Entity Editor
- Quest/dialogue editors support full CRUD on nested data (objectives, options)


---

### **Phase 4: Server Integration & Polish (2-3 weeks)**
**Goal:** Optional server connection and packaging

**Server Integration (Optional Feature):**
- [ ] "Connect to Server" dialog (localhost:8000 default)
- [ ] Hot-reload on save (`POST /api/admin/content/reload`)
- [ ] Server-side validation (enhanced error messages)
- [ ] Live world state viewer (player count, active areas)

**Polish:**
- [ ] Packaging (Windows/Mac/Linux executables)
- [ ] Keyboard shortcuts (Ctrl+S, Ctrl+Z, Ctrl+F, etc.)
- [ ] Search across all files
- [ ] Recent folders list
- [ ] Error boundary + crash recovery

**Success Criteria:**
- Works fully offline with local files
- Optionally connects to running server for hot-reload
- Packages as standalone executable

---

## Critical Path

```
Phase 1: Schema Parser + Monaco Editor
    ↓
Phase 2: React Flow Room Builder
    ↓
Phase 3: Quest/Dialogue/Trigger Visualizers
    ↓
Phase 4: Server Connection (optional) + Packaging
```

---

## What's NOT Included (Intentionally)

| Feature | Reason |
|---------|--------|
| Git UI | Use VS Code, terminal, or GitHub Desktop |
| Multi-server support | Local dev tool - one folder at a time |
| Schema Registry API | Schemas are local files, no API needed |
| SQLite caching | YAML files are fast enough |
| JWT authentication | No auth - it's a local tool |
| Per-server schema caching | No servers to cache from |
| Auto-migration system | Manual for v1, add later if needed |
| Plugin marketplace | Out of scope |
| Analytics dashboard | Nice-to-have, post-launch |

---

## Technology Stack

**Core:**
- Electron (desktop packaging)
- React + TypeScript (UI)
- Monaco Editor (YAML editing)
- React Flow (visual graphs)
- Zod (schema validation)
- chokidar (file watching)

**UI Components:**
- Ant Design (component library)
- react-mosaic (split panes)

**NOT Needed:**
- ~~simple-git~~ (use external git tools)
- ~~SQLite~~
- ~~TanStack Query~~
- ~~JWT/Auth libraries~~
- ~~WebSocket client~~ (optional in Phase 4)

---

## Success Metrics

**Phase 1 Complete When:** ✅
- [x] Opening `world_data/` shows file tree
- [x] Editing `rooms/ethereal/room_1_1_1.yaml` shows IntelliSense
- [x] Invalid YAML shows red squiggles with error messages

**Phase 2 Complete When:** ✅ SUBSTANTIALLY COMPLETE
- [x] Room canvas shows all rooms in an area with grid layout
- [x] Rooms snap to grid when dragged *(snaps on drag stop)*
- [x] Layer tabs appear based on room Z values
- [x] Creating exit by dragging updates source room YAML
- [x] Creating room creates both YAML file and `_layout.yaml` entry
- [x] NPC/item badges appear on rooms (from spawn/instance files)
- [x] Undo/redo works for all room operations
- [ ] Bidirectional exit prompt *(lower priority)*
- [ ] Canvas state persistence *(lower priority)*

**Phase 3 Complete When:**
- [ ] Dragging NPC from palette to room updates spawn file
- [ ] Entity Editor forms generate valid YAML
- [ ] **Quest Designer:** Chains visualized with objective icons on nodes
- [ ] **Quest Designer:** Objectives/rewards editable in properties panel
- [ ] **Dialogue Editor:** Tree layout shows NPC→option→NPC branches
- [ ] **Dialogue Editor:** Options editable with action badges
- [ ] Clicking room content badge opens Entity Editor
- [ ] Reference validation catches broken links

**Phase 4 Complete When:**
- [ ] `daemons-studio` launches from command line
- [ ] Saving triggers hot-reload on connected server
- [ ] Packages build for Windows/Mac/Linux

---

## Phase 2 Status Summary

Phase 2 is now **substantially complete**. The Room Builder supports full CRUD operations for rooms and exits with YAML persistence.

### ✅ Completed Features
- Grid snapping (snaps on drag stop)
- `_layout.yaml` persistence
- Room properties panel with form editing
- Write room/exit changes to YAML (bidirectional sync)
- Create room (modal → YAML + layout)
- Delete room with exit cleanup
- Delete exit from YAML
- Scan spawn/instance files for NPC/item content
- Content badges (👤/📦 counts on room nodes)
- Properties panel dirty state tracking
- Copy/paste rooms (Ctrl+C/V with unique ID generation)
- Layer tabs derived from Z values
- Undo/redo for all operations
- File watcher for external changes

### 🔄 Remaining Work (Lower Priority)
1. **Bidirectional exit prompt** - Ask to create return exit on new connection
2. **Vertical exit layer creation** - Prompt to create room on new layer when creating up/down exit
3. **Canvas state persistence** - Remember zoom/pan/active layer between sessions

---

## Phase 3 Implementation Priority

Recommended order for Phase 3 work:

### Priority 1: Quest Designer Rework (1-2 weeks)
The current quest designer has scaffolding but needs content-focused UX:
1. Add quest chain sidebar browser
2. Redesign quest nodes with objective icons
3. Implement tabbed properties panel (Details/Objectives/Rewards/Dialogue)
4. Add objective list editor with type-specific forms
5. Add rewards editor
6. Implement Dagre auto-layout for chains

### Priority 2: Dialogue Editor Rework (1-2 weeks)
The current dialogue editor needs tree-focused UX:
1. Implement hierarchical tree layout (ELK)
2. Split nodes into NPC nodes + option nodes
3. Add option editor with action badges
4. Add entry overrides panel
5. Support creating nodes from options

### Priority 3: Room Builder Content Placement (1 week)
1. Content palette with NPC/item search
2. Drag-to-place functionality
3. Quick-create from context menu

### Priority 4: Entity Editor & Validation (1 week)
1. Form-based entity editor
2. Reference validation
3. Jump-to-definition navigation


