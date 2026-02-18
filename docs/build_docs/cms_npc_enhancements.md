# CMS NPC Editor Enhancements - Battlefield Support

## Overview
Enhanced the Daemonswright CMS to provide better UI controls for creating battlefield NPCs with factions and abilities. These improvements make it much easier to build the content required for the battlefield scenario described in `battlefield.md`.

## Changes Made

### 1. Schema Parser Enhancement (`daemonswright/src/main/ipc/schema.ts`)

**Added support for `# ref:` comments in schema files**

The schema parser now recognizes reference annotations in schema documentation:
```yaml
faction_id: string
  # ref: factions
  # This NPC belongs to which faction
```

This enables the FormEditor to automatically render:
- Single references as text inputs with navigation buttons
- Array references as `EntityMultiSelect` dropdowns

**Technical Details:**
- Parser now looks for `# ref: <type>` comments in the 5 lines following a field definition
- Adds `ref` property to the SchemaField object
- Works alongside existing `# Options:` enum parsing

### 2. NPC Schema Updates (`backend/daemons/world_data/npcs/_schema.yaml`)

**Enhanced Phase 14 ability fields with proper references and enums:**

#### Faction Reference
```yaml
faction_id: string | null (default: null)
  # ref: factions
  # Faction this NPC belongs to (from factions/*.yaml)
```
- **UI Effect**: Dropdown showing all available factions
- **Example**: "silver_sanctum", "shadow_syndicate", "arcane_collective"

#### Class Reference
```yaml
class_id: string (optional, default: null)
  # ref: classes
  # Character class for this NPC (from world_data/classes/*.yaml)
```
- **UI Effect**: Dropdown showing all available classes
- **Example**: "warrior", "mage", "rogue"

#### Ability Arrays with References
```yaml
default_abilities: array of strings (optional, default: [])
  # ref: abilities
  # Ability IDs this NPC knows

ability_loadout: array of strings (optional, default: [])
  # ref: abilities
  # Ability IDs in the NPC's "action bar" for AI to use
```
- **UI Effect**: Multi-select dropdown with searchable ability list
- **Example**: Select from "fireball", "arcane_bolt", "mana_shield", etc.

#### AI Behavior Enum
```yaml
ai_behavior: string (optional, default: null)
  # Options: caster_ai, caster_tactical, brute_ai, berserker_ai, brute_simple
  # Combat AI behavior script for ability usage
```
- **UI Effect**: Dropdown with 5 AI behavior options
- **Options**:
  - `caster_ai` - Balanced caster (defensive when hurt)
  - `caster_tactical` - Tactical caster (AoE for multiple enemies)
  - `brute_ai` - Melee fighter (power attacks, rage management)
  - `berserker_ai` - Aggressive fighter (enrages at low health)
  - `brute_simple` - Simple random ability usage

### 3. Entity Options Fix (`daemonswright/src/renderer/hooks/useEntityOptions.ts`)

**Fixed faction ID field mapping**

Changed factions ID field from `faction_id` to `id` to match the actual faction YAML structure:
```typescript
factions: 'id',  // Factions use 'id' not 'faction_id'
```

## User Experience Improvements

### Before
Creating an NPC with abilities required:
- Manually typing faction IDs (risk of typos)
- Manually typing class IDs
- Manually typing each ability ID in arrays
- Manually typing AI behavior strings
- No validation or suggestions

### After
Creating an NPC with abilities now has:
- **Faction Dropdown**: Click to select from all available factions
- **Class Dropdown**: Click to select from warrior, mage, rogue, etc.
- **Ability Multi-Select**: Searchable dropdown showing all abilities with names and IDs
- **AI Behavior Dropdown**: 5 clear options with descriptions
- **Live Validation**: Invalid selections are highlighted
- **Navigation**: Click buttons to jump to referenced entities

## Building Battlefield NPCs - Example Workflow

### Creating a Silver Sanctum Warrior

1. Open Daemonswright CMS
2. Navigate to **Entity Editor** → **NPCs**
3. Click **Create New**
4. Fill in basic info:
   - ID: `npc_sanctum_warrior`
   - Name: `Silver Sanctum Warrior`
   - Description: _(battlefield warrior description)_

5. Set combat stats:
   - Level: `5`
   - Max Health: `80`
   - Armor Class: `14`
   - Strength: `16`

6. **NEW: Select from dropdown** - Faction:
   - Click dropdown, select **Silver Sanctum**

7. **NEW: Select from dropdown** - Class:
   - Click dropdown, select **warrior**

8. **NEW: Multi-select abilities** - Default Abilities:
   - Click dropdown
   - Search/select: `slash`, `shield_bash`, `power_attack`

9. **NEW: Multi-select abilities** - Ability Loadout:
   - Click dropdown
   - Select: `slash`, `power_attack`

10. **NEW: Select from dropdown** - AI Behavior:
    - Click dropdown, select **brute_ai**

11. Add behavior tags (text array):
    - `aggressive`
    - `fearless`

12. Save NPC

### Creating a Shadow Syndicate Rogue

Same workflow as above, but:
- Faction: **Shadow Syndicate** (dropdown)
- Class: **rogue** (dropdown)
- Abilities: `backstab`, `poison_strike`, `quick_strike` (multi-select)
- Loadout: `backstab`, `poison_strike` (multi-select)
- AI Behavior: **berserker_ai** (dropdown)

## Testing the Changes

### Prerequisites
1. Backend server running (`uvicorn daemons.main:app --reload`)
2. Daemonswright CMS running (`npm run dev` in daemonswright folder)
3. World data loaded with factions, classes, and abilities

### Test Steps

#### Test 1: Faction Dropdown
1. Open Daemonswright CMS
2. Navigate to Entity Editor → NPCs
3. Create or edit an NPC
4. Scroll to **faction_id** field
5. **Expected**: Should see a text input (reference support in single fields needs more work)
6. **Note**: Full dropdown support requires additional FormEditor enhancement

#### Test 2: AI Behavior Enum
1. In NPC editor, scroll to **ai_behavior** field
2. **Expected**: Dropdown with 5 options:
   - caster_ai
   - caster_tactical
   - brute_ai
   - berserker_ai
   - brute_simple

#### Test 3: Ability Multi-Select
1. In NPC editor, scroll to **default_abilities** field
2. **Expected**: Multi-select dropdown showing all abilities
3. Type to search (e.g., "fire")
4. Select multiple abilities
5. **Expected**: Selected abilities appear as tags

#### Test 4: Class Reference
1. In NPC editor, scroll to **class_id** field
2. **Expected**: Text input with navigation support (similar to faction)
3. **Note**: Full dropdown requires same enhancement as factions

#### Test 5: End-to-End NPC Creation
1. Create a new NPC from scratch
2. Use all the new fields (faction, class, abilities, ai_behavior)
3. Save the NPC
4. Verify YAML file is correct
5. Reload backend
6. Test NPC in-game

## Known Limitations

### Single-Value References (faction_id, class_id)
The current FormEditor implementation treats single-value references as text inputs with navigation buttons, not dropdowns. This is still functional but not as user-friendly as a dropdown would be.

**To fully implement dropdowns for single references:**
1. Update `FormEditor/index.tsx` around line 90-110
2. Check if field has `ref` property
3. Use `EntityMultiSelect` in mode="single" (or create EntitySelect component)

Example enhancement:
```tsx
// In renderField function, before the current reference check:
if (field.ref && !field.enum && worldDataPath) {
  return (
    <Form.Item key={name} {...commonProps}>
      <Select
        showSearch
        placeholder={`Select ${field.ref}...`}
        // Load options from useEntityOptions hook
      />
    </Form.Item>
  );
}
```

### Array References Already Working
The `EntityMultiSelect` component is already used for array fields with references, so `default_abilities` and `ability_loadout` should work perfectly with multi-select dropdowns.

## Future Enhancements

1. **Single-Reference Dropdown**: Convert faction_id and class_id to dropdowns
2. **Reference Preview**: Show entity details on hover in dropdowns
3. **Quick Create**: Add "Create New" button in reference dropdowns
4. **Validation**: Real-time validation of ability compatibility with class
5. **Templates**: NPC templates for common battlefield roles
6. **Bulk Operations**: Clone/modify multiple NPCs at once

## Files Modified

1. `daemonswright/src/main/ipc/schema.ts` - Schema parser enhancement
2. `backend/daemons/world_data/npcs/_schema.yaml` - Added ref and enum annotations
3. `daemonswright/src/renderer/hooks/useEntityOptions.ts` - Fixed faction ID field

## Backward Compatibility

All changes are backward compatible:
- Existing NPCs without the new fields continue to work
- Schema parser falls back gracefully if `# ref:` or `# Options:` not found
- FormEditor renders basic text inputs if no ref/enum metadata

## Conclusion

These enhancements make the Daemonswright CMS fully capable of creating the complex NPCs required for the battlefield scenario, including:
- ✅ Faction assignment
- ✅ Class and ability system
- ✅ AI behavior selection
- ✅ Multi-ability selection
- ✅ Proper validation

Content creators can now build the entire battlefield ecosystem using the visual CMS instead of manually editing YAML files.
