# QA Testing Todo List for Daemons Engine

## Core Systems

### Character & Player
- [ ] Character creation flow
- [ ] Character persistence (save/load)
- [ ] Stats and attribute calculations
- [ ] Leveling and experience gain
- [ ] Inventory management (add/remove/equip/use)
- [ ] Equipment slots and stat bonuses

### Movement & Navigation
- [ ] Room-to-room movement
- [ ] Door opening/closing/locking
- [ ] Locked door key requirements
- [ ] Room exit validation
- [ ] Blocked path handling

### Abilities & Skills
- [ ] Ability cooldowns
- [ ] Ability resource costs (mana/stamina)
- [ ] Ability targeting (self/enemy/ally/area)
- [ ] Ability effects application
- [ ] Passive vs active abilities
- [ ] Skill prerequisites

### Combat
- [ ] Turn/tick-based combat flow
- [ ] Attack calculations (hit/miss/crit)
- [ ] Damage types and resistances
- [ ] Death handling and respawn
- [ ] Combat state transitions (enter/exit)
- [ ] Multiple combatants (group fights)
- [ ] Flee/escape mechanics

### Room Triggers & Events
- [ ] On-enter triggers
- [ ] On-exit triggers
- [ ] Timed/scheduled triggers
- [ ] Conditional triggers
- [ ] Trigger chaining

### World Population
- [ ] Flora spawning and regrowth
- [ ] Fauna spawning and respawn timers
- [ ] Population caps per area
- [ ] Mob patrol/wander behavior
- [ ] Resource harvesting and depletion

### Communications
- [ ] Say (local room chat)
- [ ] Shout (area broadcast)
- [ ] Whisper (private messages)
- [ ] Clan/faction chat channels
- [ ] System announcements

### Factions & Clans
- [ ] Faction reputation tracking
- [ ] Faction-based NPC reactions
- [ ] Clan creation/disbanding
- [ ] Clan membership management
- [ ] Clan ranks/permissions

## Infrastructure

### Networking
- [ ] WebSocket connection stability
- [ ] Reconnection handling
- [ ] Multiple concurrent sessions
- [ ] Rate limiting (slowapi)
- [ ] Authentication/authorization (JWT)

### Persistence
- [ ] Database migrations (alembic)
- [ ] World state saving
- [ ] Crash recovery
- [ ] Data integrity on shutdown

### Performance
- [ ] Tick loop timing consistency
- [ ] Memory usage under load
- [ ] Connection scaling (10/50/100+ users)

## Edge Cases
- [ ] Simultaneous actions on same target
- [ ] Invalid command handling
- [ ] State corruption recovery
- [ ] Empty room/area handling
- [ ] Circular trigger prevention

Would you like me to expand any section with specific test cases?
