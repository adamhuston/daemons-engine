# Daemonswright Content Studio

Visual content editor for the Daemons game engine.

## Development

```bash
# Install dependencies
npm install

# Run in development mode
npm run electron:dev

# Build for production
npm run electron:build
```

## Project Structure

```
daemonswright/
├── src/
│   ├── main/              # Electron main process
│   │   ├── index.ts       # Main entry point
│   │   ├── preload.ts     # Context bridge
│   │   └── ipc/           # IPC handlers
│   │       ├── fileSystem.ts
│   │       ├── schema.ts
│   │       └── server.ts
│   ├── renderer/          # React app (renderer process)
│   │   ├── main.tsx       # React entry
│   │   ├── App.tsx        # Main component
│   │   ├── components/    # UI components
│   │   │   ├── FileTree/
│   │   │   ├── YamlEditor/
│   │   │   ├── RoomBuilder/
│   │   │   ├── MenuBar/
│   │   │   └── StatusBar/
│   │   ├── hooks/         # React hooks
│   │   │   ├── useWorkspace.ts
│   │   │   ├── useSchema.ts
│   │   │   ├── useFileWatcher.ts
│   │   │   └── useServer.ts
│   │   ├── lib/           # Utilities
│   │   │   ├── schemaParser.ts
│   │   │   └── yamlUtils.ts
│   │   └── styles/        # CSS
│   └── shared/            # Shared types
│       └── types.ts
├── package.json
├── tsconfig.json
├── vite.config.ts
└── electron-builder.yml
```

## Features

- **Local-First**: Works entirely with local `world_data/` files
- **Schema-Driven**: Reads `_schema.yaml` files for validation
- **Visual Editing**: Room builder with React Flow
- **Monaco Editor**: VS Code-like YAML editing experience
- **Optional Server**: Connect to running Daemons server for hot-reload
