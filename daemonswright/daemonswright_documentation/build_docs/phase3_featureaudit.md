## Phase 3 Feature Audit

### ✅ **Room Builder - Content Placement** (LARGELY COMPLETE)

| Feature | Status | Notes |
|---------|--------|-------|
| Palette panel with NPC/item browser | ✅ | ContentPalette.tsx - fully implemented with search, tabs, draggable cards |
| Search/filter NPCs and items | ✅ | Both tabs have search functionality |
| Drag-to-place NPC → spawn file | ⚠️ | Drag handlers exist but need to verify drop handler on `RoomNode` |
| Drag-to-place item → instance file | ⚠️ | Same - drag data types defined, need to check drop completion |
| Remove content from room | ❓ | Need to verify in RoomPropertiesPanel |
| Quick-create NPC/item from context menu | ❌ | Not implemented - no context menu on room nodes |

### ✅ **Entity Editor (Form-Based)** (SUBSTANTIALLY COMPLETE)

| Feature | Status | Notes |
|---------|--------|-------|
| Auto-generated forms from schema | ✅ | `FormEditor` renders fields from schema definitions |
| Toggle Form ↔ YAML view | ✅ | Segmented control in EntityEditor header |
| Real-time schema validation | ✅ | Via YamlEditor in YAML mode |
| NPC Templates | ✅ | Listed in ENTITY_CATEGORIES |
| Item Templates | ✅ | Listed in ENTITY_CATEGORIES |
| Abilities | ✅ | Listed in ENTITY_CATEGORIES |
| Classes | ✅ | Listed in ENTITY_CATEGORIES |
| Factions | ❌ | **Missing from ENTITY_CATEGORIES** |
| Triggers | ✅ | Custom TriggerBuilder component |
| Cross-reference links | ✅ | `inferRefType()` + LinkOutlined button |
| Jump to Entity from Room Builder | ⚠️ | `onNavigateToEntity` prop exists but needs wiring |

### ⚠️ **Quest Designer** (SCAFFOLDED - NEEDS REFINEMENT)

| Feature | Status | Notes |
|---------|--------|-------|
| React Flow canvas | ✅ | Working with QuestNode |
| Prerequisite edges | ✅ | Auto-generated from quest data |
| Quest node with basic info | ✅ | Shows name, ID, objective count badge, rewards badge |
| **Quest chain sidebar** | ❌ | Not implemented - no chain browser |
| **Objective icons on node** | ❌ | Shows count only, not type icons (⚔️📦📍💬) |
| **Reward summary on node** | ⚠️ | Has "Rewards" badge but not itemized |
| **Chain sequence indicators** | ❌ | No dotted lines for chains |
| **Dagre auto-layout** | ❌ | Uses default positioning |
| **Tabbed Properties Panel** | ⚠️ | Single scrolling form, not tabs |
| Objective list editor | ✅ | Working with add/remove/edit |
| **Rewards editor** | ❌ | Missing entirely in properties panel |
| **Dialogue tab** | ❌ | Missing - no accept/progress/complete text |

### ⚠️ **Dialogue Editor** (SCAFFOLDED - NEEDS REFINEMENT)

| Feature | Status | Notes |
|---------|--------|-------|
| React Flow canvas | ✅ | Working with DialogueNode |
| Tree sidebar | ✅ | Lists dialogue trees by NPC |
| Node selection + properties | ✅ | Working |
| **NPC/Option node split** | ❌ | Single node type for all |
| **Hierarchical tree layout** | ❌ | Uses default flat positioning |
| Option editing | ✅ | Working in Collapse panels |
| Next node links | ✅ | Working with navigation |
| **Action badges (🎯🎁🚀)** | ❌ | No visual indicators for quest/item actions |
| **Entry overrides panel** | ❌ | No UI for conditional entry points |
| **Condition builder** | ❌ | No condition editor |
| **Actions editor** | ⚠️ | Only text + next_node, missing quest/item/flag/XP actions |

### ✅ **Validation & Navigation** (PARTIALLY COMPLETE)

| Feature | Status | Notes |
|---------|--------|-------|
| Reference validation | ✅ | `useReferenceValidation` hook working |
| Error panel | ✅ | `ErrorPanel` component with grouping |
| Jump to definition | ⚠️ | Works in FormEditor, needs broader integration |

---

## Recommended TODO List for Phase 3 Completion 

Completed (1/6) *Document Phase 3 feature audit*

## Summary: Phase 3 Current State vs Roadmap

### What's Built and Working Well:
1. **EntityEditor** - Solid foundation with form/YAML toggle, schema-driven forms, most entity types
2. **ContentPalette** - Drag UI complete with search, tabs, custom drag images
3. **QuestDesigner** - Basic canvas working, prerequisite edges, objectives list editor
4. **DialogueEditor** - Tree list, node selection, options editing with navigation
5. **TriggerBuilder** - Comprehensive form-based builder with condition/action types
6. **Reference Validation** - Working hook that indexes entities and validates refs
7. **Error Panel** - Groups errors by file, severity icons, click-to-navigate

### Key Gaps to Address:

| Priority | Component | Gap | Effort |
|----------|-----------|-----|--------|
| **High** | Quest Designer | No quest chain sidebar/visualization | 1-2 days |
| **High** | Quest Designer | Missing rewards editor in properties | 0.5 day |
| **High** | Dialogue Editor | Flat node layout instead of tree | 1-2 days |
| **High** | Dialogue Editor | No action badges or condition UI | 1 day |
| **Medium** | Quest Designer | Objective icons on nodes (not just count) | 0.5 day |
| **Medium** | Dialogue Editor | NPC/Option node type split | 1 day |
| **Medium** | Room Builder | Drop handler completion for drag-to-place | 0.5 day |
| **Medium** | Room Builder | Context menu for quick-add | 0.5 day |
| **Low** | Entity Editor | Add factions category | 0.5 hour |
| **Low** | Entity Editor | Broader cross-ref navigation | 0.5 day |

### Recommended Implementation Order:

1. **Shared Infrastructure** (first) - Add dagre layout library, create shared components
2. **Quest Designer** - Chain sidebar, tabbed properties with rewards
3. **Dialogue Editor** - Tree layout, option node type, action badges
4. **Room Builder** - Complete drag-drop, add context menu
5. **Entity Editor** - Add factions, improve navigation

---

**Pausing here as requested.** Would you like me to:
1. Start with the shared infrastructure (layout library + common components)?
2. Dive into Quest Designer refinements first?
3. Focus on Dialogue Editor tree layout?
4. Something else?