# Daemons Engine - Content Authoring Context

_Generated: 2025-12-11 11:12_

Attach this file when creating or editing YAML game content.

## Content Types


## Example Files

## Common Patterns

### IDs
- Use snake_case for all IDs
- Prefix with type: `room_`, `npc_`, `item_`, `quest_`
- Example: `room_tavern_main`, `npc_barkeeper`, `item_rusty_sword`

### References
- Reference other entities by ID
- Rooms reference other rooms in `exits`
- NPCs reference `spawn_room` and `drop_table` items
- Quests reference NPCs, items, and rooms

### Keywords
- Define `keywords` for player interaction
- Players can `look <keyword>` or `examine <keyword>`
- Example: `keywords: [sword, rusty, blade]`
