"""
Sample YAML content for testing validation and file operations.

Provides valid and invalid YAML samples for various content types.
"""

# ============================================================================
# Valid YAML Samples
# ============================================================================

VALID_ROOM = """
room_id: test_room_001
name: Test Chamber
description: A simple test room for validation
room_type: test
exits:
  north: test_room_002
  south: test_room_000
"""

VALID_ITEM = """
item_id: test_sword_001
name: Iron Sword
description: A basic iron sword
type: weapon
weight: 5
value: 100
weapon_stats:
  damage: 10
  attack_speed: 1.0
"""

VALID_NPC = """
npc_id: test_npc_001
name: Test Guard
description: A vigilant guard standing watch
level: 5
faction_id: town_guard
dialogue_id: guard_greeting
"""

VALID_ABILITY = """
ability_id: test_fireball
name: Fireball
description: Launches a ball of fire at the target
cost_mp: 20
cooldown: 5
damage: 50
effect_type: damage
"""

VALID_QUEST = """
quest_id: test_quest_001
name: Test Quest
description: A simple test quest
level_requirement: 1
quest_giver_npc: test_npc_001
objectives:
  - type: kill
    target: goblin
    count: 5
rewards:
  xp: 100
  gold: 50
"""

# ============================================================================
# Invalid YAML Samples (for error testing)
# ============================================================================

INVALID_SYNTAX = """
room_id: test_room
name: Bad Room
  invalid: indentation
description: This has syntax errors
"""

MISSING_REQUIRED_FIELDS = """
room_id: incomplete_room
name: Incomplete Room
# Missing description field
"""

INVALID_REFERENCE = """
room_id: orphan_room
name: Orphan Room
description: This room has broken exits
exits:
  north: nonexistent_room_999
  east: also_missing_room
"""

WRONG_FIELD_TYPE = """
room_id: 12345
name: Type Error Room
description: The room_id should be string not int
level: not_a_number
"""

# ============================================================================
# Schema Samples
# ============================================================================

ROOM_SCHEMA = """
required_fields:
  - room_id
  - name
  - description
optional_fields:
  - exits
  - room_type
  - lighting_override
  - area_id
"""

ITEM_SCHEMA = """
required_fields:
  - item_id
  - name
  - description
  - type
optional_fields:
  - weight
  - value
  - weapon_stats
  - armor_stats
  - consumable_effects
"""

NPC_SCHEMA = """
required_fields:
  - npc_id
  - name
  - description
optional_fields:
  - level
  - faction_id
  - dialogue_id
  - spawn_location
  - loot_table
"""

# ============================================================================
# Bulk Import Samples
# ============================================================================

BULK_IMPORT_VALID = {
    "rooms/test_room_1.yaml": VALID_ROOM,
    "items/test_sword.yaml": VALID_ITEM,
    "npcs/test_guard.yaml": VALID_NPC,
}

BULK_IMPORT_MIXED = {
    "rooms/valid_room.yaml": VALID_ROOM,
    "rooms/invalid_room.yaml": INVALID_SYNTAX,
    "items/incomplete_item.yaml": MISSING_REQUIRED_FIELDS,
}

BULK_IMPORT_ALL_INVALID = {
    "rooms/syntax_error.yaml": INVALID_SYNTAX,
    "rooms/missing_fields.yaml": MISSING_REQUIRED_FIELDS,
    "rooms/bad_reference.yaml": INVALID_REFERENCE,
}
