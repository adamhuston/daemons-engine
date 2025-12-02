# Daemonswright Content Studio - Design Document

> **Vision:** A batteries-included content editor that ships with the Daemons engine. Works offline, reads local schemas, requires no server connection.

---

## Core Principles

1. **Local-First** - Works entirely with local `world_data/` files
2. **Batteries-Included** - Ships with the engine, zero configuration
3. **Schema-Driven** - Reads `_schema.yaml` files directly for validation
4. **File-Based** - YAML files are the source of truth
5. **Optional Server** - Connect to running server for hot-reload (optional)

---

## Technology Stack

### **Electron + React + TypeScript**

**Why This Stack:**
- React Flow for visual editing (room builder, quest graphs)
- Monaco Editor for YAML (same as VS Code)
- Electron for desktop packaging and file system access
- TypeScript for type safety

**Key Libraries:**
```
electron          # Desktop packaging
react + react-dom # UI framework
typescript        # Type safety
@monaco-editor/react  # YAML editor
reactflow         # Visual node graphs
zod               # Schema validation
chokidar          # File watching
antd              # UI components
```

### **What's NOT Needed**

| Library | Why Not |
|---------|---------|
| SQLite | YAML files are fast enough for local editing |
| TanStack Query | No API to cache - direct file system access |
| JWT/Auth | Local tool, no authentication needed |
| WebSocket | Only needed for optional live mode |

---

## Architecture

### **Data Flow**

```
world_data/           # Source of truth
├── rooms/
│   └── _schema.yaml  # Schema definition
│   └── *.yaml        # Content files
├── items/
│   └── _schema.yaml
│   └── *.yaml
└── ...

        ↓ (read)

Schema Parser         # Parse _schema.yaml → Zod validators

        ↓

Monaco Editor         # IntelliSense, validation, auto-complete

        ↓ (write)

YAML Files            # Save directly to disk
```

### **No Server Required**

The CMS reads schemas directly from `world_data/*/_schema.yaml` files. No API calls, no caching, no sync complexity.

**Optional Server Connection:**
- Connect to `localhost:8000` (or custom URL)
- Trigger hot-reload on save
- Enhanced validation with server-side checks
- View live world state (player count, etc.)

---

## Schema System

### **Reading Local Schemas**

Each content type has a `_schema.yaml` in its directory:

```
world_data/
├── rooms/_schema.yaml     # Room field definitions
├── items/_schema.yaml     # Item field definitions
├── npcs/_schema.yaml      # NPC field definitions
└── ...
```

**On Startup:**
1. Scan `world_data/` for `_schema.yaml` files
2. Parse each schema → extract field definitions
3. Generate Zod validators for runtime validation
4. Configure Monaco IntelliSense

**No API, No Caching:**
- Schemas are local files, read directly
- File watcher detects schema changes
- Re-parse schemas on change

### **Validation**

**Local Validation (Always):**
- YAML syntax checking
- Schema field validation (required fields, types, enums)
- Reference checking (do referenced IDs exist?)

**Server Validation (Optional):**
- When connected to server, use enhanced validation
- `POST /api/admin/content/validate-enhanced`
- Returns line/column positions for errors

---

## Core Features

### **1. File Tree + YAML Editor**

VS Code-like experience:
- Left sidebar: file tree organized by content type
- Main panel: Monaco editor with YAML syntax
- Status bar: file path, git status, server connection

**Monaco Features:**
- Schema-aware auto-complete
- Real-time validation (red squiggles)
- Hover tooltips from schema descriptions
- "Go to Definition" for referenced content

### **2. Room Builder**

Visual editor using React Flow:
- Each room is a node on the canvas
- Exits are edges between nodes
- Drag to create new rooms
- Click-drag to create exits
- Sidebar shows selected room properties

**Bidirectional Sync:**
- Canvas changes → write to YAML files
- YAML changes → update canvas (via file watcher)

### **3. Quest/Dialogue Visualizers**

Same React Flow approach:
- Quest chains as flowcharts
- Dialogue trees as branching graphs
- Trigger conditions as logic flows

### **4. Form-Based Editors**

For content that doesn't need visualization:
- Items, NPCs, Abilities, Classes
- Auto-generated forms from schemas
- Toggle between form and YAML view

---

## UI Layout

```
┌─────────────────────────────────────────────────────────┐
│ File  Edit  View  Git  Server                    [─][□][×]│
├──────────┬──────────────────────────────────────────────┤
│ EXPLORER │                                              │
│          │                                              │
│ ▼ rooms/ │     [Monaco Editor / React Flow Canvas]      │
│   cave.yaml   │                                              │
│   meadow.yaml │                                              │
│ ▼ items/ │                                              │
│   sword.yaml  │                                              │
│ ▼ npcs/  │                                              │
│   goblin.yaml │                                              │
│          │                                              │
├──────────┴──────────────────────────────────────────────────────┤
│ 💾 Offline │ rooms/cave.yaml                                 │
└─────────────────────────────────────────────────────────┘
```

---

## Optional: Server Connection

When a Daemons server is running, optionally connect for:

### **Hot-Reload on Save**
```typescript
// When connected and user saves a file:
await fetch('http://localhost:8000/api/admin/content/reload', {
  method: 'POST',
  body: JSON.stringify({ content_type: 'rooms' })
});
```

### **Enhanced Validation**
```typescript
// Get line/column error positions from server
const result = await fetch('/api/admin/content/validate-enhanced', {
  method: 'POST',
  body: JSON.stringify({ content_type: 'rooms', content: yamlString })
});
// Returns: { valid: false, errors: [{ line: 5, column: 3, message: "..." }] }
```

### **Live World State**
- Player count
- Active areas
- Recent events

**Connection is Optional:**
- CMS works fully offline
- Status bar shows connection state
- "Connect to Server" in menu

---

## Resolved Design Decisions

### **Why Not Multi-Server Support?**
- This is a local dev tool, not an enterprise CMS
- Work on one `world_data/` folder at a time
- Use git branches for different environments

### **Why Not SQLite Cache?**
- YAML files are small and fast
- No need to index for local editing
- Adds complexity without benefit

### **Why Not Schema Registry API?**
- Schemas are in the local files
- No need to fetch from server
- No need to cache or sync

### **Why Electron Instead of Tauri?**
- Monaco Editor is JavaScript (Tauri would need IPC)
- React Flow is JavaScript
- Bundle size is acceptable for a dev tool
- Faster development (familiar stack)

### **Why Ant Design?**
- Rich component library (Tree, Form, Modal, etc.)
- Desktop-appropriate aesthetic
- Good TypeScript support
- Can swap for Chakra/shadcn if preferred

---

## What's Out of Scope (v1)

| Feature | Reason |
|---------|--------|
| Plugin marketplace | Future feature |
| Multi-user collaboration | Use git instead |
| Mobile companion app | Desktop-first |
| Auto-migration system | Manual for v1 |
| Advanced git (merge, rebase) | Use terminal |
| Analytics dashboard | Nice-to-have, not essential |

---

## Conclusion

**Daemonswright Content Studio** is a focused, local-first tool for content creation:

- **Simple:** Open a folder, edit content, save to disk
- **Visual:** Room builder, quest graphs, dialogue trees
- **Validated:** Schema-aware editing with real-time feedback
- **Optional:** Connect to server for hot-reload and testing

**Timeline:** 10-13 weeks for a single developer

**Result:** A dev tool that ships with `pip install daemons-engine` and "just works."
