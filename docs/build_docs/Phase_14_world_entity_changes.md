## Phase 14 Architecture Summary

### WorldEntity Universal Abilities
**Changed**: Moved `character_sheet` from WorldPlayer/WorldNpc to WorldEntity base class
- **Benefit**: All entities (players, NPCs) can have abilities with zero code duplication
- **Impact**: Eliminated ~60 lines of duplicate code, single source of truth
- **Backward compatible**: character_sheet is optional (None by default)

### WorldItem Optional Abilities & Combat
**Changed**: Added optional `character_sheet` and `combat_stats` to WorldItem
- **character_sheet**: Enables magic items with abilities (staffs with spells, enchanted weapons)
- **combat_stats**: Enables destructible items (doors, barrels, breakable objects)
- **Design**: Items are NOT entities - they opt-in to these features as needed

### EntityCombatStats Dataclass
**New**: Shared combat functionality for non-entity objects
- HP tracking, armor class, 6 damage resistances, active effects
- Used by WorldItem for destructible items
- Future: Can be used for environmental objects, traps, interactive world objects

### Database Changes
**Migration**: m5n6o7p8q9r0_phase14_item_abilities.py
- Added 6 columns to `item_templates`: class_id, default_abilities, ability_loadout, max_health, base_armor_class, resistances
- All nullable/optional - 100% backward compatible

### Result
- ✅ NPCs can cast spells and use abilities (same as players)
- ✅ Magic items can have charges and cast abilities
- ✅ Doors/barrels can be destroyed with HP tracking
- ✅ No code duplication - clean inheritance and composition
- ✅ Simple items stay simple - complexity is opt-in
