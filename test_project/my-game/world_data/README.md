# World Data - YAML Schema Documentation

This directory contains the world content definitions in YAML format.

## Schema Documentation

Each subdirectory contains a `_schema.yaml` file that documents the expected structure for that content type. These schema files are essential references for CMS developers and content creators.

### Available Schemas

- **areas/_schema.yaml** - Area definitions (regions with time systems, biomes, environmental properties)
- **rooms/_schema.yaml** - Room definitions (individual locations with exits, triggers, descriptions)
- **items/_schema.yaml** - Item template definitions (weapons, armor, consumables, containers)
- **item_instances/_schema.yaml** - Specific item instances (pre-placed items in the world)
- **npcs/_schema.yaml** - NPC template definitions (enemies, merchants, quest givers)
- **npc_spawns/_schema.yaml** - NPC spawn configurations (where NPCs appear)
- **triggers/_schema.yaml** - Trigger definitions (event-driven actions)
- **quests/_schema.yaml** - Quest definitions (objectives, rewards, dialogue)
- **quest_chains/_schema.yaml** - Quest chain definitions (linked quest series)
- **dialogues/_schema.yaml** - Dialogue tree definitions (branching NPC conversations)
- **factions/_schema.yaml** - Faction definitions (reputation systems, NPC organizations)
- **classes/_schema.yaml** - Character class definitions (stats, abilities, progression)
- **abilities/_schema.yaml** - Ability definitions (spells, skills, powers)

### Database Schema

For database table structure and field documentation, see:
- **../documentation/DATABASE_SCHEMA.md** - Comprehensive database schema reference

This includes all SQLAlchemy models, table structures, relationships, and JSON field formats.

## Directory Structure

```
world_data/
├── areas/           # World regions (ethereal_nexus, dark_caves, etc.)
├── rooms/           # Individual locations organized by area
│   ├── ethereal/   # Rooms in the Ethereal Nexus
│   ├── caves/      # Rooms in the Dark Caves
│   └── meadow/     # Rooms in the Sunlit Meadow
├── items/           # Item templates
│   ├── weapons/    # Swords, bows, staffs
│   ├── armor/      # Helmets, chest pieces, boots
│   ├── consumables/ # Potions, food, scrolls
│   └── containers/  # Backpacks, chests, bags
├── item_instances/  # Pre-placed specific items
├── npcs/            # NPC templates (enemies, merchants, etc.)
├── npc_spawns/      # Where NPCs appear (organized by area)
├── triggers/        # Standalone trigger definitions
├── quests/          # Quest definitions
│   └── main/       # Main storyline quests
├── quest_chains/    # Linked quest series
├── dialogues/       # NPC conversation trees
├── factions/        # Reputation factions
├── classes/         # Character classes
└── abilities/       # Character abilities
```

## Content Creation Workflow

1. **Reference Schema**: Check the `_schema.yaml` file for the content type you're creating
2. **Create YAML File**: Create your content file following the schema structure
3. **Validate**: Use the admin API endpoint `/api/admin/content/validate` to check for errors
4. **Test Locally**: Load content in development environment
5. **Commit**: Add to version control with descriptive commit message
6. **Deploy**: Use hot-reload endpoint `/api/admin/content/reload` on live server

## For CMS Developers

The schema files provide:
- **Field Definitions**: All required and optional fields with types
- **Default Values**: What happens when fields are omitted
- **Examples**: Complete working examples for each content type
- **Validation Rules**: Constraints and expected formats
- **Database Mapping**: How YAML maps to database tables

The DATABASE_SCHEMA.md provides:
- **Table Structures**: All database tables with column definitions
- **Relationships**: Foreign keys and table relationships
- **Indexes**: Optimized query paths
- **JSON Formats**: Structure of JSON fields
- **Best Practices**: Integration guidelines for CMS tools

## Loading Process

1. **Development**: Edit YAML files directly
2. **Validation**: Use admin API or YAML parser to validate
3. **Migration**: Run `alembic upgrade head` to apply database changes
4. **Hot Reload**: Use `/api/admin/content/reload` to load YAML → Database without restart
5. **Runtime**: Engine loads from Database → WorldEngine

## Future: CMS Integration (Daemonswright)

The YAML files can be generated/edited by a CMS tool:

```
CMS UI → Admin API → YAML files → Git → Deployment → Hot Reload → Database
```

This allows:
- Visual editing via web interface
- Real-time validation feedback
- Version control via git
- Team collaboration via branches
- CI/CD validation
- Export/import capabilities
- Live preview mode

See `../daemonswright/daemonswright.md` for CMS design considerations.

## Related Documentation

- **YAML_IMPLEMENTATION.md** - How the engine loads and processes YAML content
- **ARCHITECTURE.md** - Overall system architecture
- **protocol.md** - Client-server communication protocol
- **daemonswright/daemonswright.md** - CMS design considerations
- **DATABASE_SCHEMA.md** - Complete database schema reference
