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

**Graph Designers (React Flow):**
- [ ] Quest designer (quest chains as flowcharts)
- [ ] Dialogue tree editor (branching conversation nodes)
- [ ] Trigger builder (visual condition/action flow)
- [ ] Reusable node graph architecture for all three

**Validation & Navigation:**
- [ ] Reference validation (detect broken links locally)
- [ ] "Jump to definition" for referenced content
- [ ] Error panel showing all validation issues

**Success Criteria:**
- Can place NPCs/items in rooms from palette
- Entity Editor generates valid YAML from forms
- Quest chains visualized as flowcharts
- Dialogue trees show branching structure
- Clicking content badge opens Entity Editor


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

**Phase 2 Complete When:** 🔄 Partial
- [x] Room canvas shows all rooms in an area with grid layout
- [ ] Rooms snap to grid when dragged
- [x] Layer tabs appear based on room Z values
- [ ] Creating exit by dragging updates source room YAML
- [ ] Creating room creates both YAML file and `_layout.yaml` entry
- [ ] NPC/item badges appear on rooms (from spawn/instance files)
- [x] Undo/redo works for all room operations

**Phase 3 Complete When:**
- [ ] Dragging NPC from palette to room updates spawn file
- [ ] Entity Editor forms generate valid YAML
- [ ] Quest chains render as flowcharts
- [ ] Clicking room content badge opens Entity Editor
- [ ] Reference validation catches broken links

**Phase 4 Complete When:**
- [ ] `daemons-studio` launches from command line
- [ ] Saving triggers hot-reload on connected server
- [ ] Packages build for Windows/Mac/Linux

---

## Phase 2 Remaining Work Summary

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

### 🔄 Remaining Work (Lower Priority)
1. **Bidirectional exit prompt** - Ask to create return exit on new connection
2. **Vertical exit layer creation** - Prompt to create room on new layer when creating up/down exit
3. **Canvas state persistence** - Remember zoom/pan/active layer between sessions


