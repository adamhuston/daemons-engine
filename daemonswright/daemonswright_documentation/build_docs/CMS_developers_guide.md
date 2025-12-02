# CMS Development Guide for Daemons Game Engine

This document provides all essential information for building a fully-featured Content Management System (CMS) for the Daemons game engine. The server API is complete and ready for CMS integration.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Authentication & Authorization](#authentication--authorization)
3. [Content Types & Schema System](#content-types--schema-system)
4. [API Endpoints Reference](#api-endpoints-reference)
5. [Schema Fetching & TypeScript Generation](#schema-fetching--typescript-generation)
6. [File Management Operations](#file-management-operations)
7. [Validation System](#validation-system)
8. [Content Querying & Dependencies](#content-querying--dependencies)
9. [Bulk Operations](#bulk-operations)
10. [Dynamic Options Population](#dynamic-options-population)
11. [Recommended CMS Architecture](#recommended-cms-architecture)

---

## Architecture Overview

The Daemons server uses a **YAML-based content system** where all game content (rooms, items, NPCs, quests, etc.) is defined in YAML files under the `world_data/` directory. The CMS workflow is:

```
CMS UI → Admin API → YAML files → Git → Deployment → Hot Reload → Database → Game Engine
```

### Key Systems

| System | File Location | Purpose |
|--------|--------------|---------|
| Schema Registry | `engine/systems/schema_registry.py` | Caches `_schema.yaml` files, provides API access |
| File Manager | `engine/systems/file_manager.py` | Secure YAML file read/write operations |
| Validation Service | `engine/systems/validation_service.py` | Syntax, schema, and reference validation |
| Query Service | `engine/systems/query_service.py` | Content search, dependency tracking, analytics |
| Bulk Service | `engine/systems/bulk_service.py` | Batch import/export with ZIP archives |

---

## Authentication & Authorization

All admin API endpoints require JWT authentication with appropriate roles.

### Roles & Permissions

| Role | Level | Capabilities |
|------|-------|-------------|
| `player` | 0 | No admin access |
| `moderator` | 1 | Read-only access to schemas, content files, search |
| `game_master` | 2 | Write access: upload, validate, reload content |
| `admin` | 3 | Full access: account management, server control |

### Authentication Flow

```http
POST /auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password"
}

Response:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### Using Tokens

```http
GET /api/admin/schemas
Authorization: Bearer eyJ...
```

---

## Content Types & Schema System

### 13 Content Types

Each content type has a dedicated directory under `world_data/` with a `_schema.yaml` file documenting the expected structure.

| Content Type | Directory | Primary ID Field | Description |
|--------------|-----------|------------------|-------------|
| `abilities` | `abilities/` | `ability_id` | Spells, skills, powers |
| `areas` | `areas/` | `area_id` | World regions with time/weather |
| `classes` | `classes/` | `class_id` | Character class definitions |
| `dialogues` | `dialogues/` | `dialogue_id` | NPC conversation trees |
| `factions` | `factions/` | `faction_id` | Reputation systems |
| `item_instances` | `item_instances/` | `instance_id` | Pre-placed items in world |
| `items` | `items/` | `item_id` | Item template definitions |
| `npc_spawns` | `npc_spawns/` | `spawn_id` | NPC spawn locations |
| `npcs` | `npcs/` | `npc_id` | NPC template definitions |
| `quest_chains` | `quest_chains/` | `quest_chain_id` | Linked quest series |
| `quests` | `quests/` | `quest_id` | Quest definitions |
| `rooms` | `rooms/` | `room_id` | Individual locations |
| `triggers` | `triggers/` | `trigger_id` | Event-driven actions |

### Schema File Structure

Each `_schema.yaml` documents:
- **Required fields** with types and examples
- **Optional fields** with default values
- **Validation rules** (constraints, formats)
- **Cross-references** to other content types
- **Complete examples** for content creators

---

## API Endpoints Reference

All endpoints are prefixed with `/api/admin`.

### Schema Registry (Phase 12.1)

| Method | Endpoint | Role Required | Purpose |
|--------|----------|---------------|---------|
| `GET` | `/schemas` | MODERATOR+ | Fetch all schema definitions |
| `GET` | `/schemas?content_type=X` | MODERATOR+ | Filter by content type |
| `GET` | `/schemas/version` | MODERATOR+ | Get version info for cache invalidation |
| `POST` | `/schemas/reload` | GAME_MASTER+ | Hot-reload schemas from disk |

### File Management (Phase 12.2)

| Method | Endpoint | Role Required | Purpose |
|--------|----------|---------------|---------|
| `GET` | `/content/files` | MODERATOR+ | List all YAML files |
| `GET` | `/content/files?content_type=X` | MODERATOR+ | Filter by content type |
| `GET` | `/content/download?file_path=X` | MODERATOR+ | Download YAML file content |
| `POST` | `/content/upload` | GAME_MASTER+ | Create/update YAML file |
| `DELETE` | `/content/file?file_path=X` | GAME_MASTER+ | Delete YAML file |
| `GET` | `/content/stats` | MODERATOR+ | File count statistics |

### Validation (Phase 12.3)

| Method | Endpoint | Role Required | Purpose |
|--------|----------|---------------|---------|
| `POST` | `/content/validate-enhanced` | MODERATOR+ | Full validation with line/column errors |
| `POST` | `/content/validate-references` | MODERATOR+ | Reference-only validation |
| `POST` | `/content/rebuild-reference-cache` | GAME_MASTER+ | Rebuild reference cache |

### Content Querying (Phase 12.4)

| Method | Endpoint | Role Required | Purpose |
|--------|----------|---------------|---------|
| `GET` | `/content/search?q=X` | MODERATOR+ | Full-text search |
| `GET` | `/content/dependencies?entity_type=X&entity_id=Y` | MODERATOR+ | Get dependency graph |
| `GET` | `/content/analytics` | MODERATOR+ | Content health metrics |
| `POST` | `/content/rebuild-dependency-graph` | GAME_MASTER+ | Rebuild dependency index |

### Bulk Operations (Phase 12.5)

| Method | Endpoint | Role Required | Purpose |
|--------|----------|---------------|---------|
| `POST` | `/content/bulk-import` | GAME_MASTER+ | Import multiple YAML files |
| `POST` | `/content/bulk-export` | GAME_MASTER+ | Export to ZIP archive |
| `POST` | `/content/batch-validate` | MODERATOR+ | Validate multiple files |

### Live Data Endpoints (Dynamic Options)

| Method | Endpoint | Role Required | Purpose |
|--------|----------|---------------|---------|
| `GET` | `/classes` | MODERATOR+ | All loaded class definitions |
| `GET` | `/abilities` | MODERATOR+ | All loaded ability definitions |
| `GET` | `/world/rooms` | MODERATOR+ | All rooms in world |
| `GET` | `/world/npcs` | MODERATOR+ | All NPCs in world |
| `GET` | `/world/items` | MODERATOR+ | All items in world |
| `GET` | `/world/areas` | MODERATOR+ | All areas in world |

### Content Reload

| Method | Endpoint | Role Required | Purpose |
|--------|----------|---------------|---------|
| `POST` | `/content/reload` | GAME_MASTER+ | Hot-reload YAML → Database |
| `POST` | `/classes/reload` | GAME_MASTER+ | Reload class system |

---

## Schema Fetching & TypeScript Generation

### Fetching All Schemas

```typescript
const response = await fetch('/api/admin/schemas', {
  headers: { 'Authorization': `Bearer ${token}` }
});

const data = await response.json();
// data.schemas = [
//   { content_type: "classes", content: "# Schema YAML...", checksum: "abc123" },
//   { content_type: "items", content: "...", checksum: "def456" },
//   ...
// ]
```

### Schema Version Checking

Poll `/schemas/version` to detect schema changes:

```typescript
const version = await fetch('/api/admin/schemas/version');
// { version: "1.0.0", last_modified: "2025-11-29T...", schema_count: 13 }

if (version.last_modified > cachedVersion) {
  // Invalidate TypeScript types, re-fetch schemas
}
```

### TypeScript Type Generation

Parse each `_schema.yaml` to generate TypeScript interfaces:

```typescript
// From classes/_schema.yaml
interface ClassDefinition {
  class_id: string;
  name: string;
  description: string;
  base_stats: {
    strength: number;
    dexterity: number;
    intelligence: number;
    vitality: number;
  };
  stat_growth: Record<string, { per_level: number; per_milestone?: Record<number, number> }>;
  starting_resources: Record<string, number>;
  available_abilities: string[];
  ability_slots: Record<number, number>;
  // Optional fields
  gcd_config?: Record<string, number>;
  icon?: string;
  keywords?: string[];
}
```

---

## File Management Operations

### Listing Files

```typescript
// List all files
const files = await fetch('/api/admin/content/files');

// Filter by content type
const rooms = await fetch('/api/admin/content/files?content_type=rooms');

// Response:
{
  "files": [
    { "file_path": "rooms/ethereal/room_1_1_1.yaml", "content_type": "rooms", "size_bytes": 456 },
    ...
  ],
  "stats": { "total": 73, "rooms": 36, "items": 7, ... }
}
```

### Downloading Content

```typescript
const content = await fetch('/api/admin/content/download?file_path=classes/warrior.yaml');
// { content: "class_id: warrior\nname: Warrior\n...", checksum: "abc123" }
```

### Uploading/Creating Content

```typescript
await fetch('/api/admin/content/upload', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({
    file_path: 'classes/my_class.yaml',
    content: 'class_id: my_class\nname: My Class\n...',
    validate_only: false  // Set true for dry-run validation
  })
});
```

---

## Validation System

### Full Validation (Real-time Monaco feedback)

```typescript
const result = await fetch('/api/admin/content/validate-enhanced', {
  method: 'POST',
  body: JSON.stringify({
    yaml_content: editorContent,
    content_type: 'rooms',
    check_references: true,
    file_path: 'rooms/my_room.yaml'
  })
});

// Response:
{
  "valid": false,
  "errors": [
    {
      "severity": "error",
      "message": "Missing required field: 'description'",
      "line": null,
      "column": null,
      "field_path": "description",
      "error_type": "schema",
      "suggestion": "Add 'description' field to the YAML file"
    },
    {
      "severity": "error",
      "message": "Exit 'north' points to non-existent room 'tavern_upstairs'",
      "field_path": "exits.north",
      "error_type": "reference",
      "suggestion": "Create room 'tavern_upstairs' or fix the exit destination"
    }
  ],
  "warnings": []
}
```

### Validation Error Types

| Type | Description | Example |
|------|-------------|---------|
| `syntax` | YAML parsing errors | Malformed YAML, bad indentation |
| `schema` | Missing/invalid required fields | Missing `name` field |
| `reference` | Broken cross-content links | Exit to non-existent room |
| `validation` | General validation issues | Invalid enum value |

### Reference Validation

The server tracks these reference relationships:

| Source Type | Field | Target Type |
|-------------|-------|-------------|
| `rooms` | `exits.*` | `rooms` |
| `rooms` | `area_id` | `areas` |
| `classes` | `available_abilities` | `abilities` |
| `npcs` | `faction_id` | `factions` |
| `npcs` | `dialogue_id` | `dialogues` |
| `npc_spawns` | `npc_id` | `npcs` |
| `npc_spawns` | `room_id` | `rooms` |
| `quest_chains` | `quests` | `quests` |

---

## Content Querying & Dependencies

### Full-Text Search

```typescript
const results = await fetch('/api/admin/content/search?q=warrior&content_type=classes');

// Response:
{
  "results": [
    {
      "content_type": "classes",
      "file_path": "classes/warrior.yaml",
      "entity_id": "warrior",
      "entity_name": "Warrior",
      "match_field": "id",
      "match_value": "warrior",
      "context_snippet": "warrior",
      "score": 10.0  // Exact ID match = highest score
    }
  ]
}
```

### Search Scoring

| Match Type | Score | Description |
|------------|-------|-------------|
| Exact ID match | 10.0 | Query equals entity ID |
| Exact field match | 5.0 | Query equals any field |
| Starts with | 3.0 | Field starts with query |
| Contains | 1.0 | Field contains query |

### Dependency Graph

Check what references an entity before deletion:

```typescript
const deps = await fetch('/api/admin/content/dependencies?entity_type=abilities&entity_id=slash');

// Response:
{
  "entity_id": "slash",
  "references": [],  // What this ability references
  "referenced_by": [
    { "source_type": "classes", "source_id": "warrior", "relationship": "has_ability" },
    { "source_type": "classes", "source_id": "rogue", "relationship": "has_ability" }
  ],
  "safe_to_delete": false,  // Other entities depend on this
  "blocking_references": [
    { "source_type": "classes", "source_id": "warrior" },
    { "source_type": "classes", "source_id": "rogue" }
  ]
}
```

### Content Analytics

Health dashboard metrics:

```typescript
const analytics = await fetch('/api/admin/content/analytics');

// Response:
{
  "total_entities": 73,
  "entities_by_type": { "rooms": 36, "items": 7, "npcs": 4, ... },
  "broken_reference_count": 2,
  "broken_references": [
    { "source_type": "rooms", "source_id": "tavern", "target_id": "tavern_upstairs" }
  ],
  "orphaned_entity_count": 5,
  "orphaned_entities": [
    { "type": "items", "id": "old_sword" }
  ],
  "most_referenced_entities": [
    { "type": "rooms", "id": "town_square", "reference_count": 8 }
  ]
}
```

---

## Bulk Operations

### Bulk Import

```typescript
await fetch('/api/admin/content/bulk-import', {
  method: 'POST',
  body: JSON.stringify({
    files: {
      'classes/fighter.yaml': 'class_id: fighter\nname: Fighter\n...',
      'classes/mage.yaml': 'class_id: mage\nname: Mage\n...'
    },
    validate_only: false,  // true for dry-run
    rollback_on_error: true  // All-or-nothing
  })
});

// Response:
{
  "success": true,
  "total_files": 2,
  "files_written": 2,
  "files_failed": 0,
  "rolled_back": false
}
```

### Bulk Export

```typescript
const response = await fetch('/api/admin/content/bulk-export', {
  method: 'POST',
  body: JSON.stringify({
    content_types: ['classes', 'abilities'],  // null = all
    include_schema_files: true
  })
});

// Response is a ZIP file download
const blob = await response.blob();
```

---

## Dynamic Options Population

For CMS dropdowns and autocomplete, use these endpoints to get currently loaded entities:

### Fetching Options for Form Fields

```typescript
// Room exits dropdown - get all room IDs
const rooms = await fetch('/api/admin/world/rooms');
const roomOptions = rooms.map(r => ({ value: r.room_id, label: r.name }));

// Class abilities dropdown - get all ability IDs
const abilities = await fetch('/api/admin/abilities');
const abilityOptions = abilities.map(a => ({ value: a.ability_id, label: a.name }));

// NPC faction dropdown - get faction IDs from file search
const factions = await fetch('/api/admin/content/files?content_type=factions');
// Then parse each file or use search
```

### Building Reference Caches

On CMS startup, build reference caches:

```typescript
// Rebuild server-side reference cache
await fetch('/api/admin/content/rebuild-reference-cache', { method: 'POST' });

// Get cached entity counts
const result = await response.json();
// { cached_entities: { rooms: 36, items: 7, npcs: 4, ... } }
```

---

## Recommended CMS Architecture

### Tech Stack Suggestion

- **Framework**: Next.js or Vite + React
- **Editor**: Monaco Editor (VS Code's editor)
- **State**: React Query / TanStack Query for API caching
- **Forms**: React Hook Form + Zod for validation
- **UI**: Tailwind CSS + Shadcn/ui components

### CMS Features Roadmap

| Phase | Feature | Server Endpoints Used |
|-------|---------|----------------------|
| 1 | Schema system + TypeScript types | `/schemas`, `/schemas/version` |
| 2A | File explorer | `/content/files`, `/content/download` |
| 2B | Monaco YAML editor with validation | `/content/upload`, `/content/validate-enhanced` |
| 3A | Dependency visualization | `/content/dependencies`, `/content/analytics` |
| 3B | Safe delete warnings | `/content/dependencies` |
| 4A | Bulk import/export | `/content/bulk-import`, `/content/bulk-export` |
| 4B | CSV import tools | Client-side CSV→YAML + bulk import |
| 5 | Form builders from schemas | `/schemas` + dynamic form generation |

### Key Implementation Patterns

#### 1. Schema-Driven Forms

```typescript
// Fetch schema, generate form fields dynamically
const schema = await fetchSchema('classes');
const formFields = parseSchemaToFormConfig(schema.content);
// Render form with proper field types, validation, descriptions
```

#### 2. Real-Time Validation

```typescript
// On Monaco editor content change (debounced)
const validate = async (content: string, contentType: string) => {
  const result = await fetch('/api/admin/content/validate-enhanced', {
    method: 'POST',
    body: JSON.stringify({
      yaml_content: content,
      content_type: contentType,
      check_references: true
    })
  });
  // Map errors to Monaco editor markers
  return result.errors.map(e => ({
    severity: monaco.MarkerSeverity.Error,
    startLineNumber: e.line || 1,
    message: e.message
  }));
};
```

#### 3. Safe Delete Flow

```typescript
const handleDelete = async (entityType: string, entityId: string) => {
  // Check dependencies first
  const deps = await fetch(`/api/admin/content/dependencies?entity_type=${entityType}&entity_id=${entityId}`);

  if (!deps.safe_to_delete) {
    // Show warning with blocking_references
    showDialog(`Cannot delete: ${deps.blocking_references.length} entities depend on this`);
    return;
  }

  // Proceed with deletion
  await fetch(`/api/admin/content/file?file_path=...`, { method: 'DELETE' });
};
```

#### 4. Dynamic Dropdown Options

```typescript
// For room exit destinations
const useRoomOptions = () => {
  return useQuery(['rooms'], async () => {
    const response = await fetch('/api/admin/world/rooms');
    return response.json();
  });
};

// In form field
<Select options={roomOptions.map(r => ({ value: r.room_id, label: r.name }))} />
```

---

## Error Handling

### Common HTTP Status Codes

| Status | Meaning | Action |
|--------|---------|--------|
| 401 | Token expired/invalid | Refresh token or re-login |
| 403 | Insufficient permissions | Check user role |
| 400 | Invalid request (validation failed) | Show error details to user |
| 404 | Content not found | File may have been deleted |
| 503 | Engine not ready | Wait and retry |

### Validation Error Response Format

```json
{
  "success": false,
  "valid": false,
  "errors": [
    {
      "severity": "error",
      "message": "Human-readable error",
      "line": 15,
      "column": 3,
      "field_path": "exits.north",
      "error_type": "reference",
      "suggestion": "Create room 'x' or fix destination"
    }
  ],
  "warnings": []
}
```

---

## Quick Reference Card

### Essential Endpoints

```
GET  /api/admin/schemas                    # Fetch all schemas
GET  /api/admin/content/files              # List all YAML files
GET  /api/admin/content/download?file_path=X  # Get file content
POST /api/admin/content/upload             # Save file
POST /api/admin/content/validate-enhanced  # Validate with details
GET  /api/admin/content/search?q=X         # Search content
GET  /api/admin/content/dependencies       # Check references
POST /api/admin/content/reload             # Hot-reload to database
```

### Required Headers

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Minimum Role Requirements

- **Read operations**: MODERATOR
- **Write operations**: GAME_MASTER
- **Account management**: ADMIN
