# Battlefield Area - Design Document

## Overview
The Battlefield is a large-scale PvE combat zone featuring dynamic faction warfare between the **Silver Sanctum** and **Shadow Syndicate**. This area is designed to create an immersive war-torn environment where NPCs from opposing factions roam the area seeking combat with each other and are hostile to all players.

## Area Specifications

### Core Properties
- **ID**: `area_battlefield`
- **Name**: The Contested Battlefield
- **Recommended Level**: 5-10
- **Danger Level**: 8 (High)
- **Theme**: Faction Warfare
- **Biome**: Mixed terrain (ruins, forest, open battlefield)
- **Climate**: Temperate
- **Area Flags**:
  - `safe_zone: false`
  - `pvp_enabled: true` (optional, for player vs player)
  - `magic_enhanced: true` (residual war magic)

### Size & Layout
The battlefield is divided into **5 major zones** arranged from west to east:

```
[West Base] → [West Forest] → [Central Ruins] → [East Forest] → [East Base]
 (Sanctum)      (Dense)       (War-torn)        (Dense)        (Syndicate)
```

## Terrain Zones

### 1. Western Base - Silver Sanctum Stronghold
**Location**: Far western edge of the battlefield
**Room Count**: 5-7 rooms in a fortified layout

**Description Theme**:
- Gleaming white marble walls
- Holy banners and symbols
- Light-based ambient effects
- Fortified defensive positions

**Features**:
- Sanctum Command Post (spawn point for Sanctum NPCs)
- Healing shrine (non-functional for players)
- Armory
- Watch tower
- Supply depot

**NPC Spawns**:
- 3-5 Sanctum Warriors (melee fighters)
- 2-3 Sanctum Clerics (healers/support)
- 1-2 Sanctum Paladins (elite units)
- 1 Sanctum Commander (boss-tier, rarely leaves base)

### 2. Western Forest
**Location**: Between Sanctum base and central ruins
**Room Count**: 8-12 rooms

**Description Theme**:
- Dense forest with strategic clearings
- Abandoned siege equipment
- Scarred trees from magical attacks
- Hidden paths and ambush points

**Features**:
- Natural cover and strategic positions
- Patrol routes for Sanctum scouts
- Hidden caches (potential loot containers)
- Ruined watchtowers

**NPC Spawns**:
- Sanctum patrol groups (2-3 NPCs)
- Occasional Shadow Syndicate scouts
- Neutral wildlife (deer, wolves)

### 3. Central Ruins - The Heart of Battle
**Location**: Dead center of the battlefield
**Room Count**: 15-20 rooms in a maze-like structure

**Description Theme**:
- Ancient castle ruins from a forgotten empire
- Crumbling stone architecture
- Blast marks and magical scarring everywhere
- Bodies of fallen warriors (atmospheric)
- Contested territory - heaviest combat zone

**Features**:
- Multiple levels (ground, towers, underground passages)
- Strategic choke points
- Central courtyard (main battle arena)
- Ruined throne room (high-value loot area)
- Siege weapons (catapults, ballistae - decorative/atmospheric)
- Magical anomalies from concentrated warfare

**NPC Spawns**:
- Heaviest NPC density
- Both faction patrols converge here
- Elite units from both sides
- Occasional boss spawns
- High respawn rate to maintain constant conflict

**Special Mechanics**:
- NPCs from opposing factions prioritize fighting each other
- Players can be caught in crossfire
- Loot spawns from NPC vs NPC combat

### 4. Eastern Forest
**Location**: Between central ruins and Syndicate base
**Room Count**: 8-12 rooms

**Description Theme**:
- Dark, shadowy forest
- Trapped paths and hidden dangers
- Poisoned vegetation
- Concealed Syndicate ambush points

**Features**:
- Shadow magic-corrupted areas
- Rogue hideouts
- Trapped routes
- Secret passages to ruins

**NPC Spawns**:
- Shadow Syndicate patrol groups (2-3 NPCs)
- Assassins in stealth
- Occasional Sanctum scouts
- Corrupted wildlife

### 5. Eastern Base - Shadow Syndicate Hideout
**Location**: Far eastern edge of the battlefield
**Room Count**: 5-7 rooms in a hidden/fortified layout

**Description Theme**:
- Dark stone and wooden structures
- Shadow magic effects
- Concealed entrances
- Criminal organization aesthetics

**Features**:
- Syndicate War Room (spawn point for Syndicate NPCs)
- Black market trader (sells stolen goods)
- Poison lab
- Thieves' den
- Hidden vault

**NPC Spawns**:
- 3-5 Syndicate Rogues (assassins/scouts)
- 2-3 Shadow Mages (dark magic users)
- 1-2 Syndicate Enforcers (elite units)
- 1 Crime Lord (boss-tier, rarely leaves base)

## Faction System Integration

### Silver Sanctum
**Faction Traits**:
- Lawful Good alignment
- Holy/Light magic users
- Heavy armor and defensive tactics
- Organized military formations

**NPC Types to Create**:
1. **Sanctum Warrior** (Base Unit)
   - Level: 5-7
   - Melee fighter with sword and shield
   - Abilities: Slash, Shield Bash, Rally
   - Faction: Silver Sanctum

2. **Sanctum Cleric** (Support Unit)
   - Level: 6-8
   - Holy magic caster
   - Abilities: Heal, Smite, Light
   - Can heal allied Sanctum NPCs

3. **Sanctum Paladin** (Elite Unit)
   - Level: 8-10
   - Heavy melee with holy powers
   - Abilities: Slash, Smite, Rally, Shield Bash
   - Higher stats and better loot

4. **Sanctum Commander** (Boss)
   - Level: 12
   - Legendary warrior
   - Multiple abilities and high stats
   - Guards the Sanctum base
   - Best loot drops

### Shadow Syndicate
**Faction Traits**:
- Chaotic Neutral alignment
- Shadow/Poison magic users
- Light armor and stealth tactics
- Guerrilla warfare approach

**NPC Types to Create**:
1. **Syndicate Rogue** (Base Unit)
   - Level: 5-7
   - Dual-wielding dagger fighter
   - Abilities: Slash (dual), Stealth Strike, Poison
   - Faction: Shadow Syndicate

2. **Shadow Mage** (Caster Unit)
   - Level: 6-8
   - Dark magic specialist
   - Abilities: Shadow Bolt, Darkness, Drain
   - Fragile but high damage

3. **Syndicate Enforcer** (Elite Unit)
   - Level: 8-10
   - Bruiser/tank type
   - Abilities: Slash, Intimidate, Knock Down
   - Guards key locations

4. **Crime Lord** (Boss)
   - Level: 12
   - Master of shadow arts
   - Multiple abilities including stealth and poison
   - Guards the Syndicate base
   - Best loot drops

## NPC Behavior System

### Roaming Patterns
**Patrol Routes**:
- Each faction has defined patrol routes from their base toward the center
- NPCs travel in groups of 2-4
- Higher chance of encountering enemy factions near the center
- Elite units patrol less frequently but cover more ground

**Aggression Rules**:
1. **Priority Target**: Enemy faction NPCs
2. **Secondary Target**: Players who enter detection range
3. **Pursuit**: Will chase targets for a limited distance from patrol route
4. **Return**: Return to patrol route if target escapes or is defeated

### Combat Behavior
**Faction vs Faction**:
- When two opposing faction NPCs meet, they immediately engage
- Fight to the death (no fleeing between factions)
- Allied NPCs will assist if nearby
- Players can observe or join the fight

**Faction vs Player**:
- All faction NPCs are hostile to players
- Will attack on sight
- May temporarily ignore player if engaged with enemy faction
- Will call for help from same-faction NPCs

**Cooperation Mechanics**:
- Same-faction NPCs assist each other
- Healing abilities prioritize same-faction targets
- Rally and buff abilities affect all nearby allies

## Loot System

### NPC Drops
**Common Drops** (All faction NPCs):
- Gold coins (variable by level)
- Health/mana potions
- Faction tokens (for potential reputation system)

**Faction-Specific Drops**:

**Silver Sanctum**:
- Holy symbols
- Light-infused weapons
- Sanctum armor pieces
- Blessing scrolls
- Paladin equipment

**Shadow Syndicate**:
- Shadow gems
- Poisoned daggers
- Dark leather armor
- Stealth cloaks
- Criminal contracts

**Elite/Boss Drops**:
- Rare faction-specific weapons
- Unique armor sets
- Powerful consumables
- Magical artifacts
- Faction reputation items

### Environmental Loot
**Ruins Loot**:
- Ancient weapons
- Historical artifacts
- Magical residue
- Rare crafting materials

**Battlefield Loot** (from NPC vs NPC combat):
- Dropped weapons and armor
- Bodies of fallen NPCs can be looted
- Loot from faction conflict persists for a time

## Connectivity & Entry Points

### Entry Points
1. **Northern Approach** - Neutral entry from northern regions
   - Enters at western forest edge
   - Safe starting point

2. **Southern Approach** - Neutral entry from southern regions
   - Enters at eastern forest edge
   - Safe starting point

3. **Ruins Portal** - Teleport point (requires quest completion)
   - Direct access to central ruins
   - Dangerous but convenient

### Exit Points
- Return portals at northern and southern entry points
- Emergency teleport stones (consumable items)
- Death respawn at nearest safe zone (outside battlefield)

## Progression & Difficulty

### Level Zones
- **West/East Forests**: Level 5-7 content
- **Outer Ruins**: Level 7-9 content
- **Central Ruins**: Level 9-11 content
- **Faction Bases**: Level 10-12 content (very dangerous)

### Scaling Difficulty
- NPC density increases toward the center
- Elite spawns increase in central ruins
- Boss NPCs at faction bases are raid-tier difficulty
- Environmental hazards in ruins

## Future Expansion Ideas

### Phase 1 (Initial Implementation)
- Basic 5-zone layout
- Core faction NPCs
- Simple patrol routes
- Basic loot tables

### Phase 2 (Enhancement)
- Dynamic faction balance (one side can "win" temporarily)
- Player reputation system (help one faction secretly)
- Siege events (coordinated NPC assaults)
- Environmental destruction (destructible walls, etc.)

### Phase 3 (Advanced)
- Player clan warfare integration
- Capturable control points
- Dynamic objectives (supply runs, assassinations)
- Faction commander AI improvements
- Legendary weapons tied to faction victories

### Phase 4 (Epic Content)
- Faction alliance options for players
- Large-scale siege battles
- Faction storyline quests
- Unique abilities learned from factions
- Area-wide events (magical storms, reinforcements)

## Technical Considerations

### Performance
- **NPC Cap**: Maximum 40-50 NPCs active at once
- **Spawn Throttling**: Stagger respawns to avoid lag spikes
- **Patrol Optimization**: Use waypoint system for efficient pathfinding
- **Combat Culling**: Despawn completed NPC vs NPC battles that are unobserved

### Database
- Faction reputation tracking (if implemented)
- NPC spawn timers and locations
- Loot instance management
- Area state persistence

### AI Coordination
- Faction affiliation checks
- Target priority system
- Group behavior for patrols
- Call-for-help radius and logic
- Retreat and reinforcement mechanics

## Testing Checklist

### Core Functionality
- [ ] All 5 zones properly connected
- [ ] NPCs spawn correctly in all zones
- [ ] Patrol routes function properly
- [ ] Faction NPCs attack each other on sight
- [ ] Faction NPCs attack players on sight
- [ ] Loot drops correctly from all NPC types
- [ ] Respawn timers work correctly

### Faction Warfare
- [ ] NPCs prioritize enemy faction over players
- [ ] Same-faction NPCs assist each other
- [ ] Combat doesn't break AI behavior
- [ ] Elite units behave differently from base units
- [ ] Boss NPCs remain in their bases appropriately

### Balance
- [ ] Difficulty appropriate for recommended levels
- [ ] Both factions are equally powerful
- [ ] Loot rewards match difficulty
- [ ] Players can escape combat if needed
- [ ] XP gains are balanced

### Performance
- [ ] No lag with maximum NPC count
- [ ] Pathfinding works smoothly
- [ ] Respawns don't cause stuttering
- [ ] Memory usage is acceptable

## Content Creation TODO

### NPCs to Create (YAML Files)
#### Silver Sanctum Faction
- [ ] `sanctum_warrior.yaml`
- [ ] `sanctum_cleric.yaml`
- [ ] `sanctum_paladin.yaml`
- [ ] `sanctum_commander.yaml`

#### Shadow Syndicate Faction
- [ ] `syndicate_rogue.yaml`
- [ ] `shadow_mage.yaml`
- [ ] `syndicate_enforcer.yaml`
- [ ] `crime_lord.yaml`

### Areas to Create (YAML Files)
#### Western Section
- [ ] `battlefield_sanctum_base.yaml` (+ 5-7 rooms)
- [ ] `battlefield_west_forest.yaml` (+ 8-12 rooms)

#### Central Section
- [ ] `battlefield_central_ruins.yaml` (+ 15-20 rooms)

#### Eastern Section
- [ ] `battlefield_east_forest.yaml` (+ 8-12 rooms)
- [ ] `battlefield_syndicate_base.yaml` (+ 5-7 rooms)

### Items to Create (Faction-Specific Loot)
#### Silver Sanctum Items
- [ ] `sanctum_longsword.yaml`
- [ ] `holy_symbol.yaml`
- [ ] `blessed_armor.yaml`
- [ ] `light_crystal.yaml`

#### Shadow Syndicate Items
- [ ] `shadow_blade.yaml`
- [ ] `poisoned_dagger.yaml`
- [ ] `dark_leather.yaml`
- [ ] `void_gem.yaml`

### System Enhancements Needed
- [ ] Faction affiliation system in NPC model
- [ ] Faction hostility matrix
- [ ] Enhanced AI for faction warfare
- [ ] Loot persistence for NPC vs NPC battles
- [ ] Patrol route waypoint system

## Room Descriptions - Style Guide

### Atmospheric Elements to Include
- **War-torn environment**: Craters, scorched earth, broken weapons
- **Faction presence**: Banners, symbols, encampments
- **Active conflict**: Sounds of battle, distant explosions
- **Dynamic weather**: Storm clouds, smoke, magical distortions
- **Tension**: Eerie quiet interrupted by conflict

### Example Description Template
```
[Zone Name]

The [terrain type] bears the scars of endless warfare. [Specific damage description]. 
[Faction presence description]. In the distance, you can [sight/sound of conflict]. 
[Atmospheric element]. [Strategic element - cover, elevation, etc.].

[Current conflict state - patrols, combat, etc.]
```

---

## Notes
- This design uses existing factions (Silver Sanctum and Shadow Syndicate) from `world_data/factions/core.yaml`
- The battlefield should feel alive with constant NPC movement and combat
- Players are always outnumbered but can use faction conflicts to their advantage
- High risk, high reward gameplay
- Can serve as a late-game grinding area or a challenging mid-game zone
- Foundation for future faction reputation and alliance systems
