# Content Creator's Schema Guide

## Overview

This guide helps **content creators** navigate the YAML schema documentation for creating game content. Each content type (areas, rooms, items, NPCs, quests, etc.) has a `_schema.yaml` file with field definitions, examples, and validation rules. For database-level details, see `SCHEMAS_FOR_DEVS.md`.

## Documentation Structure

### YAML Content Schemas
Located in `backend/world_data/{subdirectory}/_schema.yaml`

Each schema file documents the structure, fields, and examples for its content type:

1. **areas/_schema.yaml** - Geographic regions with time systems and environmental properties
2. **rooms/_schema.yaml** - Individual locations with exits, triggers, and descriptions
3. **items/_schema.yaml** - Item templates (weapons, armor, consumables, containers)
4. **item_instances/_schema.yaml** - Specific pre-placed item instances
5. **npcs/_schema.yaml** - NPC templates (enemies, merchants, quest givers)
6. **npc_spawns/_schema.yaml** - NPC spawn point configurations
7. **triggers/_schema.yaml** - Event-driven actions and conditions
8. **quests/_schema.yaml** - Quest objectives, requirements, and rewards
9. **quest_chains/_schema.yaml** - Linked quest series with chain rewards
10. **dialogues/_schema.yaml** - NPC dialogue trees with branching conversations
11. **factions/_schema.yaml** - Reputation-based faction systems
12. **classes/_schema.yaml** - Character class definitions (already existed)
13. **abilities/_schema.yaml** - Character abilities and powers (already existed)

### Database Schema
Located in `documentation/DATABASE_SCHEMA.md`

Comprehensive reference covering:
- All 25+ database tables with complete field documentation
- Column types, constraints, defaults, and indexes
- Foreign key relationships and referential integrity
- JSON field structures and formats
- Best practices for CMS integration
- Migration history and versioning

## Schema File Features

Each `_schema.yaml` file includes:

### 1. Field Documentation
- **Required vs Optional** - Clearly marked field requirements
- **Data Types** - Explicit type definitions (string, int, float, bool, array, dictionary)
- **Default Values** - What happens when fields are omitted
- **Constraints** - Valid ranges, patterns, enumerations

### 2. Detailed Descriptions
- Purpose and usage of each field
- When to use optional fields
- Relationships to other content types
- Database mapping notes

### 3. Complete Examples
- Basic examples showing minimal required fields
- Advanced examples demonstrating all features
- Multiple patterns for common use cases
- Real-world scenarios with context

### 4. Integration Notes
- How YAML maps to database tables
- Which fields are stored as JSON
- Loading and validation process
- Hot-reload considerations

## Content Type Relationships

```
Areas
  └── Rooms (belongs to area)
       ├── Triggers (attached to rooms)
       ├── Item Instances (located in rooms)
       └── NPC Instances (spawned in rooms)

Item Templates
  └── Item Instances (based on templates)

NPC Templates
  ├── NPC Instances (based on templates)
  ├── NPC Spawns (configuration for instances)
  ├── Dialogues (attached to templates)
  └── Faction Membership (templates belong to factions)

Quests
  ├── Quest Chains (link multiple quests)
  ├── Dialogues (quest giver conversations)
  └── Objectives (kill, collect, visit, talk)

Factions
  └── NPC Templates (faction membership)

Classes
  └── Abilities (class-specific abilities)

Players (Database Only)
  ├── Account (authentication linkage)
  ├── Quest Progress (active and completed)
  ├── Player Flags (persistent state)
  ├── Inventory (item instances)
  └── Effects (active buffs/debuffs)
```

## Usage Workflows

### For Content Creators

1. **Starting Out**: Read the relevant `_schema.yaml` for your content type
2. **Creating Content**: Copy an example and modify for your needs
3. **Validation**: Use admin API to validate before committing
4. **Testing**: Load in dev environment and test functionality
5. **Deployment**: Commit to git and hot-reload on server

### For CMS Developers

1. **Understanding Structure**: Review all `_schema.yaml` files
2. **Database Integration**: Study `DATABASE_SCHEMA.md` for table structures
3. **Form Generation**: Use schema definitions to build UI forms
4. **Validation**: Implement client-side validation based on schemas
5. **Preview**: Query database for live world state
6. **Hot Reload**: Trigger reload endpoint after YAML changes

### For Game Designers

1. **World Building**: Start with areas → rooms → NPCs → items
2. **Quest Design**: Create quests → link with dialogues → form quest chains
3. **Balance**: Use triggers for dynamic content and progression gates
4. **Lore Integration**: Use factions for world-building and reputation systems
5. **Testing**: Use triggers and flags to test content flow

## Validation & Error Handling

### Schema Validation Points

1. **File Creation**: Schema documents expected structure
2. **YAML Parsing**: Python YAML parser validates syntax
3. **Type Checking**: Pydantic models validate data types
4. **Foreign Key Validation**: Database enforces referential integrity
5. **Business Logic**: Game engine validates gameplay rules

### Common Validation Errors

- **Missing Required Fields**: Check schema for required vs optional
- **Invalid Foreign Keys**: Ensure referenced IDs exist (rooms, items, NPCs)
- **Type Mismatches**: String where int expected, array where dict expected
- **Invalid Enumerations**: Value not in allowed options (room_type, npc_type)
- **JSON Structure**: Malformed nested dictionaries or arrays

## Best Practices

### Content Organization

1. **Naming Conventions**:
   - Prefix IDs with type: `area_`, `room_`, `item_`, `npc_`, `quest_`
   - Use descriptive names: `npc_goblin_scout` not `npc_001`

2. **File Structure**:
   - One area per file in `areas/`
   - Group rooms by area in `rooms/{area_name}/`
   - Organize items by category in `items/{category}/`

3. **Version Control**:
   - Commit related changes together
   - Descriptive commit messages
   - Use branches for experimental content

### CMS Integration

1. **Read-Only Database Access**: CMS should primarily read from DB for preview
2. **YAML as Source**: Always modify YAML files, not database directly
3. **Validation First**: Validate before writing files
4. **Atomic Operations**: Write complete, valid YAML files
5. **Error Feedback**: Surface validation errors to user clearly

## Documentation Maintenance

### When to Update Schemas

- New fields added to models
- Field types or constraints change
- New content patterns emerge
- Common errors identified
- Feature additions (new phases)

### Schema Versioning

- Schemas should match current phase/version
- Include phase notes for new features
- Document deprecated fields
- Maintain migration guides

## Quick Reference

### File Locations

```
backend/world_data/
├── areas/_schema.yaml
├── rooms/_schema.yaml
├── items/_schema.yaml
├── item_instances/_schema.yaml
├── npcs/_schema.yaml
├── npc_spawns/_schema.yaml
├── triggers/_schema.yaml
├── quests/_schema.yaml
├── quest_chains/_schema.yaml
├── dialogues/_schema.yaml
├── factions/_schema.yaml
├── classes/_schema.yaml
└── abilities/_schema.yaml

documentation/
└── DATABASE_SCHEMA.md
```

### Admin API Endpoints

- `POST /api/admin/content/validate` - Validate YAML before loading
- `POST /api/admin/content/reload` - Hot-reload YAML into database
- `GET /api/admin/world/state` - Get current world state

### Related Documentation

- **YAML_IMPLEMENTATION.md** - YAML loading system details
- **ARCHITECTURE.md** - Overall system architecture
- **protocol.md** - Client-server communication
- **daemonswright/daemonswright.md** - CMS design philosophy
- **build_docs/PHASE*.md** - Feature implementation guides

## Support & Contribution

For questions or improvements to schema documentation:

1. Check existing examples in world_data directories
2. Review DATABASE_SCHEMA.md for database-level questions
3. See CONTRIBUTING.md for contribution guidelines
4. Open an issue for unclear or missing documentation

---

**Last Updated**: Phase 11 (Lighting System)
**Maintained By**: Core development team
**Purpose**: Enable CMS development and content creation
