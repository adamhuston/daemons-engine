# Daemons Engine - LLM Context Index

_Generated: 2025-12-11 11:12_

This file provides an overview of the Daemons Engine codebase.
Attach this to your AI assistant for general questions about the project.
For specific tasks, also attach the relevant domain-specific context file.

## Quick Reference

| Context File | Use When |
|--------------|----------|
| `llm_context_index.md` | General questions, orientation |
| `llm_context_architecture.md` | Working on engine internals |
| `llm_context_protocol.md` | Building clients, WebSocket work |
| `llm_context_content.md` | Creating YAML content (rooms, NPCs, items) |

## Project Structure

```
daemons-engine/
├── backend/daemons/          # Engine source code
│   ├── engine/               # Core game engine
│   │   ├── systems/          # Modular game systems
│   │   ├── world.py          # Runtime world model
│   │   └── engine.py         # WorldEngine orchestrator
│   ├── models.py             # SQLAlchemy database models
│   ├── routes/               # HTTP API endpoints
│   └── main.py               # FastAPI application
├── docs/                     # Documentation
├── world_data/               # YAML game content
└── tests/                    # Test suite
```

## Documentation Files

- **`docs/ALEMBIC.md`**: Database Migrations with Alembic
- **`docs/ARCHITECTURE.md`**: Dungeon Crawler – Architecture & Goals
- **`docs/COVERAGE_CI_CD.md`**: Coverage & CI/CD Setup Guide
- **`docs/DATABASE_SCHEMA.md`**: Database Schema Reference
- **`docs/FAUNA_BEHAVIORS.md`**: Fauna Behaviors Documentation
- **`docs/LONGFORM_README.md`**: Daemons
- **`docs/OPERATIONS.md`**: Daemons Engine Operations Guide
- **`docs/Phase17_implementation.md`**: world_data/flora/_schema.yaml
- **`docs/SCHEMA_DOCUMENTATION_SUMMARY.md`**: Schema Documentation Summary
- **`docs/TEST_ARCHITECTURE.md`**: Test Architecture for Daemonswright
- **`docs/UTILITY_ABILITIES.md`**: Utility Abilities System
- **`docs/UTILITY_ABILITIES_EXAMPLES.md`**: Utility Abilities - Usage Examples
- **`docs/UTILITY_ABILITIES_SUMMARY.md`**: Utility Abilities Extension - Implementation Summary
- **`docs/YAML_IMPLEMENTATION.md`**: YAML-Based World Content System - Implementation Summary
- **`docs/build_docs\CMS_DEVELOPMENT_GUIDE.md`**: CMS Development Guide for Daemons Game Engine
- **`docs/build_docs\D20_CENTRALIZED_MECHANICS.md`**: D20 Mechanics - Centralized Source of Truth
- **`docs/build_docs\D20_CONVERSION_SUMMARY.md`**: D20 Mechanics Conversion Summary
- **`docs/build_docs\PHASE10.md`**: Phase 10: Social Systems, Factions, and Communication
- **`docs/build_docs\PHASE10_design.md`**: Phase 10 Design Document: Social Systems, Factions, and Communication
- **`docs/build_docs\PHASE10_implementation.md`**: Phase 10 Implementation Plan
- **`docs/build_docs\PHASE10_research_summary.md`**: Phase 10 Research & Design Summary
- **`docs/build_docs\PHASE11_design.md`**: Phase 11 Design Document: Light and Vision System
- **`docs/build_docs\PHASE12.1_SUMMARY.md`**: Phase 12.1 Implementation Summary
- **`docs/build_docs\PHASE12.2_SUMMARY.md`**: Phase 12.2 Implementation Summary
- **`docs/build_docs\PHASE12.3_SUMMARY.md`**: Phase 12.3: Enhanced Validation API - Implementation Summary
- **`docs/build_docs\PHASE12.4_SUMMARY.md`**: Phase 12.4: Content Querying API - Implementation Summary
- **`docs/build_docs\PHASE12.5_SUMMARY.md`**: Phase 12.5 - Bulk Operations API - Implementation Summary
- **`docs/build_docs\PHASE13_ability_testing_plan.md`**: Phase 13 - Abilities Audit: Comprehensive Testing Plan
- **`docs/build_docs\PHASE13_immediate_actions_complete.md`**: Phase 13 - Immediate Actions Completion Summary
- **`docs/build_docs\PHASE14_1_COMPLETE.md`**: Phase 14.1 - Universal Entity Ability Support: Implementation Summary
- **`docs/build_docs\PHASE14_1_REFACTOR.md`**: Phase 14.1 Refactor: Universal Entity Ability Support
- **`docs/build_docs\PHASE14_DESIGN.md`**: Phase 14 - Entity Abilities: Technical Design Document
- **`docs/build_docs\PHASE2_NOTES.md`**: Phase 2 Implementation Notes
- **`docs/build_docs\PHASE5.md`**: Phase 5 Design Document: World Structure, Triggers, and Scripting
- **`docs/build_docs\PHASE6.md`**: world_data/npcs/companions/faithful_hound.yaml
- **`docs/build_docs\PHASE7.md`**: Phase 7 Design Document: Accounts, Authentication, and Security
- **`docs/build_docs\PHASE8.MD`**: Phase 8 Design Document: Admin & Content Tools
- **`docs/build_docs\PHASE9_design.md`**: Phase 9 – Character Classes & Abilities System
- **`docs/build_docs\PHASE9_implementation.md`**: Phase 9 Implementation Plan – Succinct Roadmap
- **`docs/build_docs\PIPEDREAM_VOICE.md`**: Pipedream Voice Chat
- **`docs/build_docs\PhaseX.md`**: Phase X Design Document: Quest System and Narrative Progression
- **`docs/build_docs\Phase_14_world_entity_changes.md`**: build_docs\Phase_14_world_entity_changes.md
- **`docs/build_docs\build_docs_README.md`**: Build Documentation
- **`docs/build_docs\cms_gaps.md`**: MISSING - High Priority
- **`docs/build_docs\flora_and_fauna_ux.md`**: build_docs\flora_and_fauna_ux.md
- **`docs/build_docs\future_todos.md`**: build_docs\future_todos.md
- **`docs/build_docs\gaps.md`**: build_docs\gaps.md
- **`docs/build_docs\qa_todos.md`**: QA Testing Todo List for Daemons Engine
- **`docs/deployment_cheatsheet.md`**: Update deployment cheatsheet
- **`docs/flora_and_fauna.md`**: flora_and_fauna.md
- **`docs/protocol.md`**: WebSocket Protocol Documentation
- **`docs/pypi.md`**: 1. Delete old build artifacts
- **`docs/roadmap.md`**: roadmap.md

## Key Concepts

- **Room-based world**: Rooms connected by directional exits (north, south, etc.)
- **Real-time multiplayer**: WebSocket-based event-driven architecture
- **YAML content**: All game content defined in human-readable YAML files
- **Modular systems**: Combat, quests, effects, etc. are separate composable systems
- **Template/Instance pattern**: Templates define prototypes, instances are runtime copies
