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

### **Phase 1: Core Editor (3-4 weeks)**
**Goal:** Working YAML editor with schema validation

**Critical Path:**
- [ ] Electron + React + TypeScript project boilerplate
- [ ] Basic UI shell (file tree, editor panel, status bar)
- [ ] Local schema parser (read `world_data/*/_schema.yaml` directly)
- [ ] Zod validator generation from schemas
- [ ] Monaco YAML editor integration
- [ ] Schema-aware IntelliSense (auto-complete fields/values)
- [ ] Real-time validation as you type
- [ ] Save/load YAML files to disk
- [ ] File watcher (detect external changes)
- [ ] Settings persistence (last opened folder, window state)

**Success Criteria:**
- Can open a `world_data/` folder
- Edit any YAML file with auto-complete and validation
- Changes save to disk immediately

---

### **Phase 2: Room Builder (2-3 weeks)**
**Goal:** Visual room editing

**Critical Path:**
- [ ] React Flow canvas integration
- [ ] Load rooms from YAML → canvas nodes
- [ ] Visual room node creation (drag-and-drop)
- [ ] Exit connections (click-drag between rooms)
- [ ] Room property editor (sidebar panel)
- [ ] Bidirectional sync (canvas ↔ YAML files)
- [ ] Undo/redo for all operations
- [ ] Copy/paste rooms
- [ ] Canvas state persistence (zoom, pan, selection)

**Success Criteria:**
- Can create and connect rooms visually
- Changes sync bidirectionally with YAML
- Undo/redo works reliably

---

### **Phase 3: Visual Tools (3-4 weeks)**
**Goal:** Extend visual editing to other content types

**Critical Path:**
- [ ] Quest designer (node graph with React Flow)
- [ ] Dialogue tree editor (reuses quest graph architecture)
- [ ] Trigger builder (visual condition/action flow)
- [ ] Form-based editors for simple content types:
  - [ ] Items (weapons, armor, consumables)
  - [ ] NPCs (templates)
  - [ ] Abilities/Classes
- [ ] Reference validation (detect broken links locally)
- [ ] "Jump to definition" for referenced content

**Success Criteria:**
- Quest chains visualized as flowcharts
- Dialogue trees show branching structure
- Form editors for content that doesn't need visualization

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

**Phase 1 Complete When:**
- Opening `world_data/` shows file tree
- Editing `rooms/ethereal/room_1_1_1.yaml` shows IntelliSense
- Invalid YAML shows red squiggles with error messages

**Phase 2 Complete When:**
- Room canvas shows all rooms in an area
- Dragging creates new rooms with YAML files
- Canvas state persists between sessions

**Phase 3 Complete When:**
- Quest chains render as flowcharts
- Clicking a node opens the quest in editor
- Form editors generate valid YAML

**Phase 4 Complete When:**
- `daemons-studio` launches from command line
- Saving triggers hot-reload on connected server
- Packages build for Windows/Mac/Linux
