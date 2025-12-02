# Daemonswright Technology Stack

> A focused stack for a local-first content editor. No cloud, no auth, no complexity.

## Core Framework

| Technology | Purpose |
|------------|---------|
| **Electron** | Desktop packaging (Windows/Mac/Linux) |
| **React** | UI framework |
| **TypeScript** | Type-safe development |

## Key Libraries

### Editing & Visualization

| Library | Purpose |
|---------|---------|
| **Monaco Editor** | YAML editing with IntelliSense (same as VS Code) |
| **React Flow** | Visual node graphs (rooms, quests, dialogues) |
| **Zod** | Schema validation (generated from `_schema.yaml`) |
| **chokidar** | File watching for external changes |

### UI Components

| Library | Purpose |
|---------|----------|
| **Ant Design** | Component library (Tree, Form, Modal, etc.) |
| **react-mosaic** | Split pane layouts |

## Development & Build

| Tool | Purpose |
|------|---------|
| **Vite** | Fast dev server and bundling |
| **Electron Builder** | Application packaging |
| **ESLint + Prettier** | Code quality |

## What's NOT Included

| Library | Why Not |
|---------|----------|
| simple-git | Use VS Code, terminal, or GitHub Desktop for git |
| SQLite | YAML files are fast enough |
| TanStack Query | No API to cache |
| JWT/Auth | Local tool, no auth needed |
| WebSocket | Only for optional live mode |
| Axios | Fetch API is sufficient |

## Architecture Patterns

- **Local-First** - Direct file system access, no server required
- **Schema-Driven** - Parse `_schema.yaml` → generate validators
- **File-Based** - YAML files as source of truth
- **Optional Server** - Connect for hot-reload when needed

## Package.json Dependencies

```json
{
  "dependencies": {
    "react": "^18.x",
    "react-dom": "^18.x",
    "@monaco-editor/react": "^4.x",
    "reactflow": "^11.x",
    "antd": "^5.x",
    "zod": "^3.x",
    "chokidar": "^3.x",
    "js-yaml": "^4.x",
    "react-mosaic-component": "^6.x"
  },
  "devDependencies": {
    "electron": "^28.x",
    "electron-builder": "^24.x",
    "typescript": "^5.x",
    "vite": "^5.x",
    "@vitejs/plugin-react": "^4.x"
  }
}
```

## File Structure

```
daemonswright-studio/
├── src/
│   ├── main/           # Electron main process
│   │   ├── index.ts
│   │   └── ipc.ts      # File system IPC handlers
│   ├── renderer/       # React app
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── FileTree/
│   │   │   ├── YamlEditor/
│   │   │   └── RoomBuilder/
│   │   ├── hooks/
│   │   │   ├── useSchema.ts
│   │   │   └── useFileWatcher.ts
│   │   └── lib/
│   │       ├── schemaParser.ts
│   │       └── zodGenerator.ts
│   └── shared/         # Types shared between main/renderer
├── electron-builder.yml
├── package.json
└── vite.config.ts
```
