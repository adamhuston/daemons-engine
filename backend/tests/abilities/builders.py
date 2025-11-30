"""
Builder pattern utilities for ability testing.

These builders provide fluent APIs for creating test data structures
with sensible defaults and easy customization.
"""

from typing import Any, Optional

from app.engine.systems.abilities import AbilityTemplate
from app.engine.world import (CharacterSheet, EntityType, ResourcePool,
                              WorldNpc, WorldPlayer)


class AbilityTemplateBuilder:
    """
    Fluent builder for ability templates.

    Example:
        ability = (AbilityTemplateBuilder()
                   .with_id("fireball")
                   .with_damage(20, 30)
                   .with_mana_cost(50)
                   .with_cooldown(5.0)
                   .build())
    """

    def __init__(self):
        self._template = {
            "id": "test_ability",
            "name": "Test Ability",
            "description": "A test ability",
            "cooldown": 0.0,
            "gcd_category": "combat",
            "resource_cost": {"type": "none"},
            "behavior": "melee_attack",
            "target_type": "enemy",
            "level_requirement": 1,
        }

    def with_id(self, ability_id: str) -> "AbilityTemplateBuilder":
        self._template["id"] = ability_id
        return self

    def with_name(self, name: str) -> "AbilityTemplateBuilder":
        self._template["name"] = name
        return self

    def with_behavior(self, behavior: str) -> "AbilityTemplateBuilder":
        self._template["behavior"] = behavior
        return self

    def with_target_type(self, target_type: str) -> "AbilityTemplateBuilder":
        """Target types: self, enemy, ally, room, aoe_enemies"""
        self._template["target_type"] = target_type
        return self

    def with_damage(self, min_damage: int, max_damage: int) -> "AbilityTemplateBuilder":
        self._template["damage_min"] = min_damage
        self._template["damage_max"] = max_damage
        return self

    def with_scaling(self, stat: str, factor: float) -> "AbilityTemplateBuilder":
        """Stat: strength, dexterity, intelligence, wisdom"""
        self._template["scaling_stat"] = stat
        self._template["scaling_factor"] = factor
        return self

    def with_mana_cost(self, amount: int) -> "AbilityTemplateBuilder":
        self._template["resource_cost"] = {"type": "mana", "amount": amount}
        return self

    def with_rage_cost(self, amount: int) -> "AbilityTemplateBuilder":
        self._template["resource_cost"] = {"type": "rage", "amount": amount}
        return self

    def with_energy_cost(self, amount: int) -> "AbilityTemplateBuilder":
        self._template["resource_cost"] = {"type": "energy", "amount": amount}
        return self

    def with_no_cost(self) -> "AbilityTemplateBuilder":
        self._template["resource_cost"] = {"type": "none"}
        return self

    def with_cooldown(self, seconds: float) -> "AbilityTemplateBuilder":
        self._template["cooldown"] = seconds
        return self

    def with_gcd_category(self, category: str) -> "AbilityTemplateBuilder":
        """Categories: combat, utility, none"""
        self._template["gcd_category"] = category
        return self

    def with_level_requirement(self, level: int) -> "AbilityTemplateBuilder":
        self._template["level_requirement"] = level
        return self

    def with_field(self, key: str, value: Any) -> "AbilityTemplateBuilder":
        """Set arbitrary field for custom ability properties"""
        self._template[key] = value
        return self

    def build(self) -> AbilityTemplate:
        """Build the AbilityTemplate object from the dict"""
        # Map builder dict fields to AbilityTemplate fields
        template_dict = self._template.copy()

        # Handle field name mappings
        if "level_requirement" in template_dict:
            template_dict["required_level"] = template_dict.pop("level_requirement")

        # Handle behavior field (builder uses "behavior", dataclass uses "behavior_id")
        if "behavior" in template_dict:
            behavior_id = template_dict.pop("behavior")
            template_dict["behavior_id"] = behavior_id
            # Convert single behavior_id to behaviors list for executor compatibility
            template_dict["behaviors"] = [behavior_id]

        # Handle resource cost conversion
        resource_cost = template_dict.pop("resource_cost", {"type": "none"})
        costs = {}
        if resource_cost["type"] != "none":
            costs[resource_cost["type"]] = resource_cost["amount"]
        template_dict["costs"] = costs

        # Move non-standard fields to metadata
        metadata = template_dict.get("metadata", {})
        non_standard_fields = [
            "damage_min",
            "damage_max",
            "scaling_stat",
            "scaling_factor",
        ]
        for field_name in non_standard_fields:
            if field_name in template_dict:
                metadata[field_name] = template_dict.pop(field_name)
        if metadata:
            template_dict["metadata"] = metadata

        # Ensure required fields have defaults
        template_dict.setdefault("ability_id", template_dict.get("id", "test_ability"))
        template_dict.setdefault("ability_type", "active")
        template_dict.setdefault("ability_category", "melee")

        # Remove 'id' if present (use ability_id instead)
        template_dict.pop("id", None)

        return AbilityTemplate(**template_dict)


class CharacterSheetBuilder:
    """
    Fluent builder for CharacterSheet instances.

    Example:
        sheet = (CharacterSheetBuilder()
                 .with_class("warrior")
                 .with_level(5)
                 .with_rage_pool(50, 100)
                 .with_learned_abilities(["melee_attack", "power_attack"])
                 .build())
    """

    def __init__(self):
        self._class_id = "warrior"
        self._level = 1
        self._experience = 0
        self._learned_abilities = set()
        self._resource_pools = {}

    def with_class(self, class_id: str) -> "CharacterSheetBuilder":
        self._class_id = class_id
        return self

    def with_level(self, level: int) -> "CharacterSheetBuilder":
        self._level = level
        return self

    def with_experience(self, xp: int) -> "CharacterSheetBuilder":
        self._experience = xp
        return self

    def with_learned_abilities(self, abilities: list[str]) -> "CharacterSheetBuilder":
        self._learned_abilities = set(abilities)
        return self

    def with_mana_pool(
        self, current: int, maximum: int, regen_rate: int = 5
    ) -> "CharacterSheetBuilder":
        self._resource_pools["mana"] = ResourcePool(
            resource_id="mana",
            current=current,
            max=maximum,
            regen_per_second=float(regen_rate),
        )
        return self

    def with_rage_pool(self, current: int, maximum: int) -> "CharacterSheetBuilder":
        self._resource_pools["rage"] = ResourcePool(
            resource_id="rage", current=current, max=maximum, regen_per_second=0.0
        )
        return self

    def with_energy_pool(
        self, current: int, maximum: int, regen_rate: int = 10
    ) -> "CharacterSheetBuilder":
        self._resource_pools["energy"] = ResourcePool(
            resource_id="energy",
            current=current,
            max=maximum,
            regen_per_second=float(regen_rate),
        )
        return self

    def build(self) -> CharacterSheet:
        return CharacterSheet(
            class_id=self._class_id,
            level=self._level,
            experience=self._experience,
            learned_abilities=self._learned_abilities,
            resource_pools=self._resource_pools,
        )


class WorldPlayerBuilder:
    """
    Fluent builder for WorldPlayer instances.

    Example:
        player = (WorldPlayerBuilder()
                  .with_name("TestWarrior")
                  .with_stats(strength=15, constitution=12)
                  .with_character_sheet(warrior_sheet)
                  .build())
    """

    def __init__(self):
        self._id = "test_player"
        self._name = "TestPlayer"
        self._room_id = "test_room"
        self._current_health = 100
        self._max_health = 100
        self._strength = 10
        self._dexterity = 10
        self._intelligence = 10
        self._vitality = 10
        self._character_sheet: Optional[CharacterSheet] = None

    def with_id(self, player_id: str) -> "WorldPlayerBuilder":
        self._id = player_id
        return self

    def with_name(self, name: str) -> "WorldPlayerBuilder":
        self._name = name
        return self

    def with_room(self, room_id: str) -> "WorldPlayerBuilder":
        self._room_id = room_id
        return self

    def with_health(self, current: int, maximum: int) -> "WorldPlayerBuilder":
        self._current_health = current
        self._max_health = maximum
        return self

    def with_stats(
        self,
        strength: int = 10,
        dexterity: int = 10,
        intelligence: int = 10,
        vitality: int = 10,
    ) -> "WorldPlayerBuilder":
        self._strength = strength
        self._dexterity = dexterity
        self._intelligence = intelligence
        self._vitality = vitality
        return self

    def with_character_sheet(self, sheet: CharacterSheet) -> "WorldPlayerBuilder":
        self._character_sheet = sheet
        return self

    def build(self) -> WorldPlayer:
        return WorldPlayer(
            id=self._id,
            name=self._name,
            room_id=self._room_id,
            entity_type=EntityType.PLAYER,
            current_health=self._current_health,
            max_health=self._max_health,
            strength=self._strength,
            dexterity=self._dexterity,
            intelligence=self._intelligence,
            vitality=self._vitality,
            character_sheet=self._character_sheet,
        )


class WorldNpcBuilder:
    """
    Fluent builder for WorldNpc instances.

    Example:
        goblin = (WorldNpcBuilder()
                  .with_name("TestGoblin")
                  .with_template("goblin_scout")
                  .with_health(50, 50)
                  .with_stats(strength=8, dexterity=12)
                  .build())
    """

    def __init__(self):
        self._id = "test_npc"
        self._name = "TestNPC"
        self._room_id = "test_room"
        self._template_id = "test_template"
        self._current_health = 50
        self._max_health = 50
        self._strength = 10
        self._dexterity = 10
        self._intelligence = 10
        self._vitality = 10

    def with_id(self, entity_id: str) -> "WorldNpcBuilder":
        self._id = entity_id
        return self

    def with_name(self, name: str) -> "WorldNpcBuilder":
        self._name = name
        return self

    def with_template(self, template_id: str) -> "WorldNpcBuilder":
        self._template_id = template_id
        return self

    def with_room(self, room_id: str) -> "WorldNpcBuilder":
        self._room_id = room_id
        return self

    def with_health(self, current: int, maximum: int) -> "WorldNpcBuilder":
        self._current_health = current
        self._max_health = maximum
        return self

    def with_stats(
        self,
        strength: int = 10,
        dexterity: int = 10,
        intelligence: int = 10,
        vitality: int = 10,
    ) -> "WorldNpcBuilder":
        self._strength = strength
        self._dexterity = dexterity
        self._intelligence = intelligence
        self._vitality = vitality
        return self

    def build(self) -> WorldNpc:
        return WorldNpc(
            id=self._id,
            name=self._name,
            room_id=self._room_id,
            template_id=self._template_id,
            entity_type=EntityType.NPC,
            current_health=self._current_health,
            max_health=self._max_health,
            strength=self._strength,
            dexterity=self._dexterity,
            intelligence=self._intelligence,
            vitality=self._vitality,
        )
