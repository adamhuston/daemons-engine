"""
Tests for NPC Ability System (Phase 14 - Entity Abilities)

Tests cover:
- NPC ability casting with character_sheet
- NPC resource consumption (mana, cooldowns)
- NPC cooldown tracking (separate from players)
- entity_type field in ability events
- Room broadcasts for NPC abilities
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.engine.systems.abilities import AbilityExecutor
from app.engine.systems.events import EventDispatcher
from tests.abilities.builders import (AbilityTemplateBuilder,
                                      CharacterSheetBuilder, WorldNpcBuilder)
from tests.fixtures.ability_samples import SAMPLE_FIREBALL

# ============================================================================
# NPC Ability Casting Tests
# ============================================================================


@pytest.mark.asyncio
async def test_npc_can_cast_with_character_sheet(
    mock_npc_caster, mock_enemy_npc, mock_game_context
):
    """NPC with character_sheet should be able to cast learned abilities"""
    # NPC mage has fireball in learned_abilities
    mock_behavior = AsyncMock(
        return_value=Mock(
            success=True,
            damage_dealt=25,
            targets_hit=["test_goblin"],
            effects_applied=[],
            message="Fireball hits for 25 damage",
        )
    )

    mock_game_context.class_system.get_ability.return_value = SAMPLE_FIREBALL
    mock_game_context.class_system.get_behavior.return_value = mock_behavior

    executor = AbilityExecutor(context=mock_game_context)

    with patch.object(executor, "_resolve_targets", return_value=[mock_enemy_npc]):
        result = await executor.execute_ability(
            caster=mock_npc_caster, ability_id="fireball", target_id="TestGoblin"
        )

    assert result.success
    assert result.damage_dealt == 25


@pytest.mark.asyncio
async def test_npc_without_character_sheet_cannot_cast(
    mock_enemy_npc, mock_game_context
):
    """NPC without character_sheet should fail ability validation"""
    # mock_enemy_npc has no character_sheet
    mock_game_context.class_system.get_ability.return_value = SAMPLE_FIREBALL

    executor = AbilityExecutor(context=mock_game_context)

    result = await executor.execute_ability(
        caster=mock_enemy_npc, ability_id="fireball", target_id=None
    )

    assert not result.success
    # Without character_sheet, the error is "choose a class first"
    assert "class" in result.error.lower() or "cannot" in result.error.lower()


@pytest.mark.asyncio
async def test_npc_ability_not_learned(mock_npc_caster, mock_game_context):
    """NPC should fail when trying to cast unlearned ability"""
    unknown_ability = AbilityTemplateBuilder().with_id("unknown_spell").build()

    mock_game_context.class_system.get_ability.return_value = unknown_ability

    executor = AbilityExecutor(context=mock_game_context)

    result = await executor.execute_ability(
        caster=mock_npc_caster, ability_id="unknown_spell", target_id=None
    )

    assert not result.success
    assert "learned" in result.error.lower() or "unknown" in result.error.lower()


# ============================================================================
# NPC Resource Consumption Tests
# ============================================================================


@pytest.mark.asyncio
async def test_npc_mana_consumed_on_cast(
    npc_mage_sheet, mock_enemy_npc, mock_game_context
):
    """NPC should consume mana when casting spells"""
    # Create NPC with 100 mana
    npc = (
        WorldNpcBuilder()
        .with_name("ManaTest")
        .with_character_sheet(npc_mage_sheet)
        .build()
    )
    initial_mana = npc.character_sheet.resource_pools["mana"].current

    mock_behavior = AsyncMock(
        return_value=Mock(
            success=True,
            damage_dealt=20,
            targets_hit=["test_goblin"],
            effects_applied=[],
            message="Hit",
        )
    )

    mock_game_context.class_system.get_ability.return_value = SAMPLE_FIREBALL
    mock_game_context.class_system.get_behavior.return_value = mock_behavior

    executor = AbilityExecutor(context=mock_game_context)

    with patch.object(executor, "_resolve_targets", return_value=[mock_enemy_npc]):
        result = await executor.execute_ability(
            caster=npc, ability_id="fireball", target_id="TestGoblin"
        )

    assert result.success
    # Fireball costs 80 mana (from SAMPLE_FIREBALL)
    expected_mana = initial_mana - 80
    assert npc.character_sheet.resource_pools["mana"].current == expected_mana


@pytest.mark.asyncio
async def test_npc_insufficient_mana(npc_mage_sheet, mock_game_context):
    """NPC should fail when mana is insufficient"""
    # Set mana to 10 (fireball costs 80)
    npc_mage_sheet.resource_pools["mana"].current = 10

    npc = (
        WorldNpcBuilder()
        .with_name("LowMana")
        .with_character_sheet(npc_mage_sheet)
        .build()
    )

    mock_game_context.class_system.get_ability.return_value = SAMPLE_FIREBALL

    executor = AbilityExecutor(context=mock_game_context)

    result = await executor.execute_ability(
        caster=npc, ability_id="fireball", target_id=None
    )

    assert not result.success
    assert "mana" in result.error.lower() or "resource" in result.error.lower()


# ============================================================================
# NPC Cooldown Tests
# ============================================================================


@pytest.mark.asyncio
async def test_npc_cooldown_tracking(
    mock_npc_caster, mock_enemy_npc, mock_game_context
):
    """NPC cooldowns should be tracked separately"""
    mock_behavior = AsyncMock(
        return_value=Mock(
            success=True,
            damage_dealt=25,
            targets_hit=["test_goblin"],
            effects_applied=[],
            message="Hit",
        )
    )

    mock_game_context.class_system.get_ability.return_value = SAMPLE_FIREBALL
    mock_game_context.class_system.get_behavior.return_value = mock_behavior

    executor = AbilityExecutor(context=mock_game_context)

    # First cast should succeed
    with patch.object(executor, "_resolve_targets", return_value=[mock_enemy_npc]):
        result1 = await executor.execute_ability(
            caster=mock_npc_caster, ability_id="fireball", target_id="TestGoblin"
        )

    assert result1.success

    # Restore mana to test cooldown specifically (not resource limitation)
    mock_npc_caster.character_sheet.resource_pools["mana"].current = 150

    # Second cast immediately should fail (on cooldown)
    result2 = await executor.execute_ability(
        caster=mock_npc_caster, ability_id="fireball", target_id="TestGoblin"
    )

    assert not result2.success
    assert "cooldown" in result2.error.lower()


@pytest.mark.asyncio
async def test_npc_and_player_cooldowns_separate(
    mock_npc_caster, mock_mage, mock_enemy_npc, mock_game_context
):
    """NPC and player cooldowns should be tracked independently"""
    mock_behavior = AsyncMock(
        return_value=Mock(
            success=True,
            damage_dealt=25,
            targets_hit=["test_goblin"],
            effects_applied=[],
            message="Hit",
        )
    )

    mock_game_context.class_system.get_ability.return_value = SAMPLE_FIREBALL
    mock_game_context.class_system.get_behavior.return_value = mock_behavior

    executor = AbilityExecutor(context=mock_game_context)

    # NPC casts fireball - triggers cooldown for NPC
    with patch.object(executor, "_resolve_targets", return_value=[mock_enemy_npc]):
        npc_result = await executor.execute_ability(
            caster=mock_npc_caster, ability_id="fireball", target_id="TestGoblin"
        )

    assert npc_result.success

    # Player casts fireball - should NOT be on cooldown (different entity)
    with patch.object(executor, "_resolve_targets", return_value=[mock_enemy_npc]):
        player_result = await executor.execute_ability(
            caster=mock_mage, ability_id="fireball", target_id="TestGoblin"
        )

    # Player should succeed (their cooldown is separate from NPC's)
    assert player_result.success


# ============================================================================
# Entity Type Event Tests
# ============================================================================


def test_ability_cast_event_npc_entity_type(mock_game_context):
    """ability_cast event should include entity_type='npc' for NPCs"""
    dispatcher = EventDispatcher(mock_game_context)
    event = dispatcher.ability_cast(
        caster_id="npc_123",
        ability_id="fireball",
        ability_name="Fireball",
        target_ids=["player_1"],
        entity_type="npc",
    )

    assert event["type"] == "ability_cast"
    assert event["caster_id"] == "npc_123"
    assert event["entity_type"] == "npc"


def test_ability_cast_event_player_entity_type(mock_game_context):
    """ability_cast event should include entity_type='player' for players (default)"""
    dispatcher = EventDispatcher(mock_game_context)
    event = dispatcher.ability_cast(
        caster_id="player_123",
        ability_id="fireball",
        ability_name="Fireball",
        target_ids=["npc_1"],
    )

    assert event["type"] == "ability_cast"
    assert event["entity_type"] == "player"


def test_ability_cast_complete_event_npc_entity_type(mock_game_context):
    """ability_cast_complete event should include entity_type='npc' for NPCs"""
    dispatcher = EventDispatcher(mock_game_context)
    event = dispatcher.ability_cast_complete(
        caster_id="npc_123",
        ability_id="fireball",
        ability_name="Fireball",
        success=True,
        message="Hit for 50 damage",
        damage_dealt=50,
        entity_type="npc",
    )

    assert event["type"] == "ability_cast_complete"
    assert event["player_id"] == "npc_123"  # Uses player_id key in event
    assert event["entity_type"] == "npc"


def test_ability_error_event_structure(mock_game_context):
    """ability_error event should have correct structure"""
    dispatcher = EventDispatcher(mock_game_context)
    event = dispatcher.ability_error(
        player_id="npc_123",
        ability_id="fireball",
        ability_name="Fireball",
        error_message="Not enough mana",
    )

    assert event["type"] == "ability_error"
    assert event["player_id"] == "npc_123"
    assert event["ability_id"] == "fireball"
    assert event["error"] == "Not enough mana"


# ============================================================================
# NPC Builder Tests
# ============================================================================


def test_world_npc_builder_with_character_sheet():
    """WorldNpcBuilder should support character_sheet"""
    sheet = (
        CharacterSheetBuilder()
        .with_class("mage")
        .with_level(5)
        .with_learned_abilities({"fireball", "frostbolt"})
        .with_mana_pool(100, 150)
        .build()
    )

    npc = (
        WorldNpcBuilder()
        .with_id("test_npc")
        .with_name("Test Mage")
        .with_template("mage_template")
        .with_character_sheet(sheet)
        .build()
    )

    assert npc.id == "test_npc"
    assert npc.name == "Test Mage"
    assert npc.character_sheet is not None
    assert npc.character_sheet.class_id == "mage"
    assert "fireball" in npc.character_sheet.learned_abilities


def test_world_npc_builder_without_character_sheet():
    """WorldNpcBuilder should work without character_sheet (default enemy)"""
    npc = (
        WorldNpcBuilder()
        .with_id("basic_npc")
        .with_name("Goblin")
        .with_health(50, 50)
        .build()
    )

    assert npc.id == "basic_npc"
    assert npc.name == "Goblin"
    assert npc.character_sheet is None


# ============================================================================
# Integration Tests (NPC in Combat Context)
# ============================================================================


@pytest.mark.asyncio
async def test_npc_can_target_player(mock_npc_caster, mock_warrior, mock_game_context):
    """NPC should be able to target players with abilities"""
    mock_behavior = AsyncMock(
        return_value=Mock(
            success=True,
            damage_dealt=30,
            targets_hit=[mock_warrior.id],
            effects_applied=[],
            message="Fireball hits TestWarrior for 30 damage",
        )
    )

    mock_game_context.class_system.get_ability.return_value = SAMPLE_FIREBALL
    mock_game_context.class_system.get_behavior.return_value = mock_behavior

    executor = AbilityExecutor(context=mock_game_context)

    with patch.object(executor, "_resolve_targets", return_value=[mock_warrior]):
        result = await executor.execute_ability(
            caster=mock_npc_caster, ability_id="fireball", target_id="TestWarrior"
        )

    assert result.success
    assert mock_warrior.id in result.targets_hit


@pytest.mark.asyncio
async def test_npc_gcd_applied_after_cast(
    mock_npc_caster, mock_enemy_npc, mock_game_context
):
    """NPC should have GCD applied after successful cast"""
    mock_behavior = AsyncMock(
        return_value=Mock(
            success=True,
            damage_dealt=25,
            targets_hit=["test_goblin"],
            effects_applied=[],
            message="Hit",
        )
    )

    mock_game_context.class_system.get_ability.return_value = SAMPLE_FIREBALL
    mock_game_context.class_system.get_behavior.return_value = mock_behavior

    executor = AbilityExecutor(context=mock_game_context)

    with patch.object(executor, "_resolve_targets", return_value=[mock_enemy_npc]):
        result = await executor.execute_ability(
            caster=mock_npc_caster, ability_id="fireball", target_id="TestGoblin"
        )

    assert result.success

    # Check GCD is set for the NPC
    assert mock_npc_caster.id in executor.gcd_state


@pytest.mark.asyncio
async def test_multiple_npcs_independent_cooldowns(
    npc_mage_sheet, mock_enemy_npc, mock_game_context
):
    """Multiple NPCs should have independent cooldown tracking"""
    # Create two NPCs
    npc1 = (
        WorldNpcBuilder()
        .with_id("npc1")
        .with_name("Cultist A")
        .with_character_sheet(npc_mage_sheet)
        .build()
    )

    # Create fresh sheet for second NPC
    sheet2 = (
        CharacterSheetBuilder()
        .with_class("mage")
        .with_level(5)
        .with_learned_abilities({"fireball"})
        .with_mana_pool(100, 150)
        .build()
    )
    npc2 = (
        WorldNpcBuilder()
        .with_id("npc2")
        .with_name("Cultist B")
        .with_character_sheet(sheet2)
        .build()
    )

    mock_behavior = AsyncMock(
        return_value=Mock(
            success=True,
            damage_dealt=25,
            targets_hit=["test_goblin"],
            effects_applied=[],
            message="Hit",
        )
    )

    mock_game_context.class_system.get_ability.return_value = SAMPLE_FIREBALL
    mock_game_context.class_system.get_behavior.return_value = mock_behavior

    executor = AbilityExecutor(context=mock_game_context)

    # NPC1 casts fireball
    with patch.object(executor, "_resolve_targets", return_value=[mock_enemy_npc]):
        result1 = await executor.execute_ability(
            caster=npc1, ability_id="fireball", target_id="TestGoblin"
        )
    assert result1.success

    # NPC2 should still be able to cast (different entity)
    with patch.object(executor, "_resolve_targets", return_value=[mock_enemy_npc]):
        result2 = await executor.execute_ability(
            caster=npc2, ability_id="fireball", target_id="TestGoblin"
        )
    assert result2.success

    # Restore NPC1 mana to test cooldown specifically (not resource limitation)
    npc1.character_sheet.resource_pools["mana"].current = 150

    # NPC1 should be on cooldown
    result3 = await executor.execute_ability(
        caster=npc1, ability_id="fireball", target_id="TestGoblin"
    )
    assert not result3.success
    assert "cooldown" in result3.error.lower()
