"""Ability test specific fixtures."""

from dataclasses import dataclass
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, Mock

import pytest

from app.engine.systems.abilities import AbilityExecutor
from app.engine.systems.classes import ClassSystem
from app.engine.systems.combat import CombatSystem
from app.engine.systems.effects import EffectSystem
from app.engine.systems.events import EventDispatcher
from app.engine.systems.time_manager import TimeEventManager
from app.engine.world import (CharacterSheet, EntityType, ResourcePool,
                              WorldArea, WorldNpc, WorldPlayer, WorldRoom)
from tests.fixtures.players import PlayerBuilder

# ============================================================================
# Legacy Player Fixtures (kept for backward compatibility)
# ============================================================================


@pytest.fixture
def warrior_player():
    """Create a warrior player for ability testing."""
    return PlayerBuilder().as_warrior().with_level(10).build()


@pytest.fixture
def mage_player():
    """Create a mage player for ability testing."""
    return PlayerBuilder().as_mage().with_level(10).build()


@pytest.fixture
def rogue_player():
    """Create a rogue player for ability testing."""
    return PlayerBuilder().as_rogue().with_level(10).build()


@pytest.fixture
def cleric_player():
    """Create a cleric player for ability testing."""
    return PlayerBuilder().as_cleric().with_level(10).build()


# ============================================================================
# Character Sheet Fixtures (for detailed ability testing)
# ============================================================================


@pytest.fixture
def warrior_sheet():
    """Level 5 warrior with rage pool and warrior abilities"""
    return CharacterSheet(
        class_id="warrior",
        level=5,
        experience=0,
        learned_abilities={"melee_attack", "power_attack", "whirlwind_attack", "rally"},
        resource_pools={
            "rage": ResourcePool(
                resource_id="rage", current=50, max=100, regen_per_second=0.0
            )
        },
    )


@pytest.fixture
def mage_sheet():
    """Level 5 mage with mana pool and mage abilities"""
    return CharacterSheet(
        class_id="mage",
        level=5,
        experience=0,
        learned_abilities={
            "fireball",
            "frostbolt",
            "mana_regen",
            "inferno",
            "arcane_missiles",
        },
        resource_pools={
            "mana": ResourcePool(
                resource_id="mana", current=100, max=150, regen_per_second=5.0
            )
        },
    )


@pytest.fixture
def rogue_sheet():
    """Level 5 rogue with energy pool and rogue abilities"""
    return CharacterSheet(
        class_id="rogue",
        level=5,
        experience=0,
        learned_abilities={"backstab", "evasion", "shadow_clone", "melee_attack"},
        resource_pools={
            "energy": ResourcePool(
                resource_id="energy", current=80, max=100, regen_per_second=10.0
            )
        },
    )


@pytest.fixture
def low_level_sheet():
    """Level 1 character with minimal abilities (for level requirement tests)"""
    return CharacterSheet(
        class_id="warrior",
        level=1,
        experience=0,
        learned_abilities={"melee_attack"},
        resource_pools={
            "rage": ResourcePool(
                resource_id="rage", current=0, max=100, regen_per_second=0.0
            )
        },
    )


@pytest.fixture
def empty_resources_sheet():
    """Character with no resources (for resource validation tests)"""
    return CharacterSheet(
        class_id="mage",
        level=5,
        experience=0,
        learned_abilities={"fireball"},
        resource_pools={
            "mana": ResourcePool(
                resource_id="mana",
                current=0,  # Empty mana pool
                max=150,
                regen_per_second=5.0,
            )
        },
    )


# ============================================================================
# World Entity Fixtures
# ============================================================================


@pytest.fixture
def mock_warrior(warrior_sheet):
    """WorldPlayer with warrior character sheet"""
    return WorldPlayer(
        id="test_warrior",
        name="TestWarrior",
        room_id="test_room",
        entity_type=EntityType.PLAYER,
        current_health=100,
        max_health=100,
        strength=15,
        dexterity=10,
        intelligence=8,
        vitality=12,
        character_sheet=warrior_sheet,
    )


@pytest.fixture
def mock_mage(mage_sheet):
    """WorldPlayer with mage character sheet"""
    return WorldPlayer(
        id="test_mage",
        name="TestMage",
        room_id="test_room",
        entity_type=EntityType.PLAYER,
        current_health=80,
        max_health=80,
        strength=8,
        dexterity=10,
        intelligence=16,
        vitality=10,
        character_sheet=mage_sheet,
    )


@pytest.fixture
def mock_rogue(rogue_sheet):
    """WorldPlayer with rogue character sheet"""
    return WorldPlayer(
        id="test_rogue",
        name="TestRogue",
        room_id="test_room",
        entity_type=EntityType.PLAYER,
        current_health=90,
        max_health=90,
        strength=10,
        dexterity=16,
        intelligence=10,
        vitality=10,
        character_sheet=rogue_sheet,
    )


@pytest.fixture
def mock_enemy_npc():
    """WorldNpc enemy target for ability testing"""
    return WorldNpc(
        id="test_goblin",
        name="TestGoblin",
        room_id="test_room",
        template_id="goblin_scout",
        entity_type=EntityType.NPC,
        current_health=50,
        max_health=50,
        strength=8,
        dexterity=12,
        intelligence=6,
        vitality=10,
    )


@pytest.fixture
def mock_ally_player():
    """WorldPlayer ally for healing/buff ability testing"""
    return WorldPlayer(
        id="test_ally",
        name="TestAlly",
        room_id="test_room",
        entity_type=EntityType.PLAYER,
        current_health=50,
        max_health=100,
        strength=10,
        dexterity=10,
        intelligence=10,
        vitality=10,
    )


@pytest.fixture
def mock_room_with_entities(mock_warrior, mock_enemy_npc, mock_ally_player):
    """WorldRoom with multiple entities for AOE and multi-target testing"""
    room = WorldRoom(
        id="test_room",
        area_id="test_area",
        name="Test Combat Arena",
        description="A test room for combat abilities.",
        exits={},
        entities={mock_warrior.id, mock_enemy_npc.id, mock_ally_player.id},
    )
    return room


@pytest.fixture
def mock_area():
    """WorldArea for room context"""
    return WorldArea(
        area_id="test_area",
        name="Test Area",
        description="A test area",
        entry_point="test_room",
        recommended_level=5,
        time_scale=1.0,
    )


# ============================================================================
# System Fixtures
# ============================================================================


@pytest.fixture
def mock_combat_system(mock_game_context):
    """Mock CombatSystem for damage calculation"""
    return Mock(spec=CombatSystem)


@pytest.fixture
def mock_effect_system(mock_game_context):
    """Mock EffectSystem for buff/debuff application"""
    return Mock(spec=EffectSystem)


@pytest.fixture
def mock_event_dispatcher(mock_game_context):
    """Mock EventDispatcher for event testing"""
    return Mock(spec=EventDispatcher)


@pytest.fixture
def mock_time_manager(mock_game_context):
    """Mock TimeEventManager for cooldown testing"""
    return Mock(spec=TimeEventManager)


@pytest.fixture
def ability_executor(
    mock_combat_system, mock_effect_system, mock_event_dispatcher, mock_time_manager
):
    """Configured AbilityExecutor instance"""
    # Create mock GameContext with necessary systems
    mock_context = Mock()
    mock_context.combat_system = mock_combat_system
    mock_context.effect_system = mock_effect_system
    mock_context.event_dispatcher = mock_event_dispatcher
    mock_context.time_manager = mock_time_manager

    # Create mock ClassSystem
    mock_class_system = Mock(spec=ClassSystem)
    mock_context.class_system = mock_class_system

    # Create AbilityExecutor
    executor = AbilityExecutor(context=mock_context)
    executor.class_system = mock_class_system  # Make class_system accessible for tests

    return executor


# ============================================================================
# Behavior Context Helpers
# ============================================================================


@dataclass
class BehaviorTestContext:
    """Helper for creating BehaviorContext for behavior function testing"""

    caster: WorldPlayer
    target: Optional[Any]
    ability_template: Dict[str, Any]
    combat_system: CombatSystem
    effect_system: EffectSystem
    time_manager: TimeEventManager
    room: Optional[WorldRoom] = None
    area: Optional[WorldArea] = None

    def to_dict(self):
        """Convert to kwargs dict for behavior function calls"""
        return {
            "caster": self.caster,
            "target": self.target,
            "ability_template": self.ability_template,
            "combat_system": self.combat_system,
            "effect_system": self.effect_system,
            "time_manager": self.time_manager,
            "room": self.room,
            "area": self.area,
        }


@pytest.fixture
def behavior_context_factory(
    mock_combat_system,
    mock_effect_system,
    mock_time_manager,
    mock_room_with_entities,
    mock_area,
):
    """Factory for creating BehaviorTestContext instances"""

    def _create_context(caster, target, ability_template):
        return BehaviorTestContext(
            caster=caster,
            target=target,
            ability_template=ability_template,
            combat_system=mock_combat_system,
            effect_system=mock_effect_system,
            time_manager=mock_time_manager,
            room=mock_room_with_entities,
            area=mock_area,
        )

    return _create_context


# ============================================================================
# Cooldown/GCD Helpers
# ============================================================================


@pytest.fixture
def cooldown_helper():
    """Helper functions for cooldown testing"""

    class CooldownHelper:
        @staticmethod
        def set_cooldown(
            player: WorldPlayer, ability_id: str, remaining_seconds: float
        ):
            """Set a cooldown that expires in N seconds"""
            import time

            if not hasattr(player, "ability_cooldowns"):
                player.ability_cooldowns = {}
            player.ability_cooldowns[ability_id] = time.time() + remaining_seconds

        @staticmethod
        def set_gcd(player: WorldPlayer, category: str, remaining_seconds: float):
            """Set a GCD that expires in N seconds"""
            import time

            if not hasattr(player, "gcd_timers"):
                player.gcd_timers = {}
            player.gcd_timers[category] = time.time() + remaining_seconds

        @staticmethod
        def clear_all_cooldowns(player: WorldPlayer):
            """Clear all cooldowns for clean test state"""
            if hasattr(player, "ability_cooldowns"):
                player.ability_cooldowns.clear()
            if hasattr(player, "gcd_timers"):
                player.gcd_timers.clear()

    return CooldownHelper()


@pytest.fixture
def mock_game_context():
    """Create a properly mocked GameContext for ability executor tests"""
    mock_context = Mock()
    mock_context.class_system = Mock()

    # Mock class template with proper gcd_config dict
    mock_class_template = Mock()
    mock_class_template.gcd_config = {"combat": 1.5, "utility": 1.0}
    mock_context.class_system.get_class.return_value = mock_class_template

    mock_context.event_dispatcher = Mock()
    mock_context.event_dispatcher.dispatch = AsyncMock(return_value=None)

    # Mock world with empty player/npc dicts
    mock_context.world = Mock()
    mock_context.world.players = {}
    mock_context.world.npcs = {}

    # Mock combat_system
    mock_context.combat_system = Mock()

    # Mock engine (optional)
    mock_context.engine = None

    return mock_context
