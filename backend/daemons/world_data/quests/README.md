# Quest and Dialogue YAML Definitions

This directory contains quest definitions and NPC dialogue trees.

## Directory Structure

```
quests/
    main/           # Main story quests
    side/           # Side quests
    daily/          # Repeatable daily quests
dialogues/
    <npc_template_id>.yaml  # Dialogue tree per NPC
```

## Quest YAML Format

```yaml
id: quest_unique_id
name: "Display Name"
description: "Quest description shown in journal"
category: main  # main, side, daily, repeatable

# Quest giver (optional - some quests auto-trigger)
giver_npc_template: npc_template_id
turn_in_npc_template: npc_template_id  # null = auto-complete

# Requirements
level_requirement: 1
prerequisites:
  - previous_quest_id
required_flags:
  flag_name: expected_value

# Objectives
objectives:
  - id: obj_id
    type: kill  # kill, collect, visit, talk, interact
    description: "Kill Goblins"
    target_template_id: goblin_warrior
    required_count: 5
    hidden: false
    optional: false

# Rewards
rewards:
  experience: 100
  items:
    - [item_template_id, quantity]
  flags:
    quest_complete_flag: true
```

## Dialogue YAML Format

```yaml
npc_template_id: npc_template_id
entry_node: greet

entry_overrides:
  - conditions:
      - type: quest_status
        params: { quest_id: "quest_id", status: "completed" }
    node_id: greet_quest_complete

nodes:
  greet:
    text: "Hello, {player.name}! Welcome to our village."
    options:
      - text: "Tell me about quests."
        next_node: quest_info
      - text: "Farewell."
        next_node: null
```
