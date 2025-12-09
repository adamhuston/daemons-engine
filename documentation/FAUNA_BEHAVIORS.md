# Fauna Behaviors Documentation

This document describes the fauna behavior system, how to configure fauna NPCs, and the available behavior scripts.

## Overview

Fauna are wildlife NPCs that respond to their environment through ecological behaviors. Unlike standard NPCs, fauna have:
- **Hunger** that increases over time
- **Biome compatibility** for spawning in appropriate areas
- **Activity periods** (diurnal, nocturnal, crepuscular)
- **Predator-prey relationships**
- **Pack spawning**
- **Migration patterns**

## YAML Configuration

### Basic Fauna NPC Template

```yaml
id: fauna_rabbit
name: Rabbit
description: A small brown rabbit with long ears.

# Mark as fauna (required for fauna behaviors)
is_fauna: true

# Fauna-specific data
fauna_data:
  fauna_type: mammal          # mammal, bird, reptile, amphibian, fish, insect, arachnid
  diet: herbivore             # herbivore, carnivore, omnivore, scavenger
  activity_period: crepuscular # diurnal, nocturnal, crepuscular, always
  
  # Biome compatibility - must match area's biome fauna_tags
  biome_tags:
    - meadow
    - forest
    - grassland
  
  # Tags for predator-prey matching
  fauna_tags:
    - small_prey
    - rodent
  
  # What hunts this creature (for flee behavior)
  predator_tags:
    - canine
    - feline
    - raptor
  
  # Temperature tolerance (Fahrenheit)
  temperature_tolerance: [20, 95]
  
  # Pack spawning
  pack_size: [2, 5]           # Spawn 2-5 at a time
  
  # Territory
  territorial: false
  territory_radius: 3
  
  # Migration
  migratory: false
  migration_seasons: []       # ["winter"] if migratory
  migration_tendency: 0.05    # Chance to explore per tick
  
  # Combat/flee behavior
  aggression: 0.0             # 0.0 = passive, 1.0 = attacks on sight
  flee_threshold: 0.5         # Health % to flee at

# AI behaviors - the behavior scripts to run
behavior:
  - grazes                    # Eats flora when hungry
  - flees_predators           # Runs from predators
  - wanders_sometimes         # Random movement
```

### Predator Example

```yaml
id: fauna_wolf
name: Wolf
description: A grey wolf with piercing yellow eyes.

is_fauna: true

fauna_data:
  fauna_type: mammal
  diet: carnivore
  activity_period: always
  
  biome_tags:
    - forest
    - tundra
    - mountain
  
  fauna_tags:
    - canine
    - pack_hunter
  
  # What this creature hunts
  prey_tags:
    - small_prey
    - rodent
    - deer
  
  temperature_tolerance: [-10, 85]
  pack_size: [3, 6]
  pack_leader_template: fauna_alpha_wolf  # Optional leader variant
  
  territorial: true
  territory_radius: 5
  
  aggression: 0.3
  flee_threshold: 0.2

behavior:
  - hunts                     # Hunts prey when hungry
  - territorial               # Defends territory
  - wanders_sometimes
```

---

## Available Fauna Behaviors

### `grazes`

**Purpose:** Herbivore grazing behavior - reduces hunger by consuming flora.

**Priority:** 30 (runs before wandering)

**Configuration:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `graze_hunger_threshold` | 50 | Start grazing when hunger exceeds this |
| `graze_hunger_reduction` | 30 | How much hunger is reduced per graze |
| `graze_chance` | 0.6 | Chance to find food in the room |
| `idle_interval_min` | 10.0 | Minimum seconds between graze checks |
| `idle_interval_max` | 30.0 | Maximum seconds between graze checks |

**Behavior:**
1. Checks if NPC's hunger exceeds threshold
2. If hungry, attempts to find flora in the room
3. On success: reduces hunger and emits flavor message
4. On failure: does nothing (may wander to find food)

**Example Message:** `"The rabbit grazes contentedly."`

---

### `hunts`

**Purpose:** Carnivore hunting behavior - catches and eats prey.

**Priority:** 25 (runs before grazing)

**Configuration:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `hunt_hunger_threshold` | 70 | Start hunting when hunger exceeds this |
| `hunt_success_chance` | 0.4 | Chance to catch prey |
| `idle_interval_min` | 15.0 | Minimum seconds between hunt checks |
| `idle_interval_max` | 45.0 | Maximum seconds between hunt checks |

**Behavior:**
1. Checks if NPC's hunger exceeds threshold
2. Looks for prey in the room (matches `prey_tags` against other fauna's `fauna_tags`)
3. If prey found, attempts to catch it
4. On success: fully feeds predator, removes prey (abstract death - no corpse)
5. On failure: prey escapes, flavor message

**Example Messages:**
- `"The wolf catches and devours the rabbit!"`
- `"The wolf lunges at the rabbit but misses!"`

---

### `flees_predators`

**Purpose:** Prey animal survival instinct - flees when predators are present.

**Priority:** 10 (highest priority - survival first)

**Configuration:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `flee_chance` | 0.8 | Chance to flee when predator detected |

**Behavior:**
1. Checks for predators in the room (matches `predator_tags` against other fauna's `fauna_tags`)
2. If predator found, decides whether to flee
3. If fleeing, moves to a random connected room
4. If trapped (no exits), emits panic message

**Example Messages:**
- `"The rabbit flees north from the wolf!"`
- `"The rabbit looks around frantically!"` (trapped)

---

### `territorial`

**Purpose:** Territorial creature warns/attacks intruders in its territory.

**Priority:** 20

**Configuration:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `aggro_chance` | 0.5 | Chance to become aggressive toward intruders |

**Behavior:**
1. Checks if creature has `territorial: true` in fauna_data
2. Looks for players in the room
3. If player found, may become aggressive
4. Emits warning growl (actual combat handled by combat system)

**Example Message:** `"The wolf growls menacingly at you!"`

---

## Standard NPC Behaviors (Also Usable by Fauna)

These behaviors from the standard NPC system also work with fauna:

### `wanders_sometimes`
Random movement to adjacent rooms. Good for giving fauna realistic movement.

### `patrols`
Follows a set path between rooms. Useful for creatures with regular routes.

### `aggressive`
Attacks players on sight. Use for hostile creatures like bears.

### `cowardly`
Flees when health drops below threshold. Already built into flee_threshold.

---

## Hunger System

Fauna have a hunger value from 0 (full) to 100 (starving):

- **Hunger increases** over time via `population.update_fauna_hunger()`
- **Herbivores graze** when hunger > 50 (default)
- **Carnivores hunt** when hunger > 70 (default)
- **Starving fauna** (hunger = 100) may despawn or become desperate

The hunger system drives natural behaviors - well-fed fauna are calm, hungry fauna actively seek food.

---

## Predator-Prey Tag System

The tag system allows flexible predator-prey relationships:

### Prey Tags (on prey creatures)
```yaml
fauna_tags:
  - small_prey      # Hunted by many predators
  - rodent          # Hunted by owls, snakes
  - deer            # Hunted by wolves, cougars
```

### Predator Tags (on prey creatures)
```yaml
predator_tags:
  - canine          # Flees from wolves, foxes
  - feline          # Flees from cougars, bobcats
  - raptor          # Flees from hawks, eagles
```

### Prey Tags (on predator creatures)
```yaml
prey_tags:
  - small_prey      # Wolves hunt rabbits
  - deer            # Wolves hunt deer
```

---

## Biome-Based Spawning

Fauna spawn automatically based on biome compatibility:

1. Each area has a `biome` field (e.g., "temperate_forest")
2. Biomes have `fauna_tags` (e.g., ["forest", "woodland"])
3. Fauna templates have `biome_tags` (e.g., ["forest", "meadow"])
4. Fauna only spawn in areas where tags overlap

### Area Fauna Density

Areas can set fauna density:
```yaml
fauna_density: moderate  # sparse, moderate, dense, lush
```

| Density | Max Fauna Per Room |
|---------|-------------------|
| sparse | 2 |
| moderate | 4 |
| dense | 8 |
| lush | 12 |

---

## Activity Periods

Fauna have activity periods that affect spawning and behavior:

| Period | Active Hours | Description |
|--------|--------------|-------------|
| `diurnal` | Dawn, Day (5-17) | Active during daylight |
| `nocturnal` | Dusk, Night (17-5) | Active at night |
| `crepuscular` | Dawn, Dusk (5-7, 17-20) | Active at twilight |
| `always` | All hours | Always active |

Inactive fauna are less likely to spawn and may "sleep" (skip behaviors).

---

## Pack Spawning

Fauna can spawn in groups:

```yaml
fauna_data:
  pack_size: [3, 6]                      # Spawn 3-6 at a time
  pack_leader_template: fauna_alpha_wolf  # Optional leader variant
```

When a pack spawns:
1. If leader template specified and pack size > 1, spawn leader first
2. Spawn remaining pack members of base template

---

## Migration

Migratory fauna can move between areas:

```yaml
fauna_data:
  migratory: true
  migration_seasons: ["winter"]    # Seasons when fauna migrates away
  migration_tendency: 0.05         # Chance per tick to explore
```

During migration seasons, migratory fauna won't spawn in the area.

---

## Example: Complete Ecosystem

### Meadow Area
```yaml
id: area_sunlit_meadow
biome: temperate_meadow
fauna_density: moderate
```

### Rabbit (Prey)
```yaml
id: fauna_rabbit
is_fauna: true
fauna_data:
  diet: herbivore
  biome_tags: [meadow, grassland]
  fauna_tags: [small_prey]
  predator_tags: [canine, feline, raptor]
  pack_size: [2, 4]
behavior:
  - grazes
  - flees_predators
  - wanders_sometimes
```

### Fox (Predator)
```yaml
id: fauna_fox
is_fauna: true
fauna_data:
  diet: carnivore
  biome_tags: [meadow, forest]
  fauna_tags: [canine]
  prey_tags: [small_prey, rodent]
  pack_size: [1, 2]
behavior:
  - hunts
  - territorial
  - wanders_sometimes
```

### Result
- Rabbits spawn in meadow, graze on flora
- Foxes spawn in meadow, hunt rabbits when hungry
- Rabbits flee when foxes enter the room
- Natural population balance emerges

---

## Debugging

Enable debug logging to see fauna behavior:

```python
import logging
logging.getLogger("daemons.engine.behaviors.fauna").setLevel(logging.DEBUG)
logging.getLogger("daemons.engine.systems.fauna").setLevel(logging.DEBUG)
```

This will show:
- Fauna spawns and despawns
- Hunger updates
- Grazing/hunting attempts
- Flee events
- Migration decisions
