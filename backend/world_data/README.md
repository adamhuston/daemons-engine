# World Data - YAML Schema Documentation

This directory contains the world content definitions in YAML format.

## Directory Structure

```
world_data/
├── areas/          # Area definitions (regions with time scales, environments)
└── rooms/          # Room definitions (individual locations)
```

## Area Schema

File: `areas/{area_id}.yaml`

```yaml
id: string                    # Unique identifier (e.g., "area_ethereal_nexus")
name: string                  # Display name (e.g., "The Ethereal Nexus")
description: string           # Detailed description of the area

# Time System
time_scale: float            # Time flow multiplier (1.0 = normal, 2.0 = 2x faster, 0.5 = 2x slower)
starting_day: int            # Initial day when area is created (default: 1)
starting_hour: int           # Initial hour 0-23 (default: 6 = dawn)
starting_minute: int         # Initial minute 0-59 (default: 0)

# Environmental Properties
biome: string                # Ecosystem type (ethereal, temporal, forest, desert, etc.)
climate: string              # Weather pattern (mild, harsh, chaotic, etc.)
ambient_lighting: string     # Light quality (bright, dim, prismatic, distorted, etc.)
weather_profile: string      # Current weather (clear, stable, stormy, shifting, etc.)

# Gameplay Properties
danger_level: int            # Threat rating 1-10
magic_intensity: string      # Magical energy (low, medium, high, extreme)

# Atmospheric Details
ambient_sound: string        # Area-specific ambient audio description (optional)

# Time Phase Flavor Text
time_phases:                 # Custom descriptions for each time of day
  dawn: string              # 5:00-6:59
  morning: string           # 7:00-11:59
  afternoon: string         # 12:00-16:59
  dusk: string              # 17:00-18:59
  evening: string           # 19:00-21:59
  night: string             # 22:00-4:59

# Entry Points
entry_points:                # List of room IDs that serve as entrances
  - room_id_1
  - room_id_2
```

## Room Schema (Future)

File: `rooms/{room_id}.yaml`

```yaml
id: string                   # Unique identifier
area_id: string             # Which area this room belongs to (optional)
name: string                # Display name
description: string         # Full description
room_type: string           # Type category (ethereal, dungeon, forest, etc.)

# Exits
exits:
  north: room_id            # Optional - room to the north
  south: room_id
  east: room_id
  west: room_id
  up: room_id
  down: room_id

# Effects (optional)
on_enter_effect: string     # Message when entering
on_exit_effect: string      # Message when leaving
```

## Loading Process

1. **Development**: Edit YAML files directly
2. **Migration**: Run `alembic upgrade head` to load YAML → Database
3. **Runtime**: Engine loads from Database → WorldEngine

## Future: Map Builder API

The YAML files can be generated/edited by a separate Map Builder tool:

```
Map Builder UI → Map Builder API → YAML files → Git → Deployment → Database
```

This allows:
- Visual editing via web interface
- Version control via git
- Team collaboration via branches
- CI/CD validation
- Export/import capabilities
