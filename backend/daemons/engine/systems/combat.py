# backend/app/engine/systems/combat.py
"""
CombatSystem - Handles attack execution, damage calculation, and death.

Provides:
- Attack initiation and swing scheduling
- Damage calculation with crits and armor
- Loot dropping and level-up integration
- Flee with dex-based difficulty checks
- Death handling and respawn scheduling

Extracted from WorldEngine for modularity.
"""

from __future__ import annotations

import random
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..world import EntityId, PlayerId, RoomId, WeaponStats, WorldEntity
    from .context import GameContext


# Type alias for events
Event = dict[str, Any]


@dataclass
class CombatConfig:
    """
    Configuration for combat mechanics.

    Note: Critical hits are determined by D20 mechanics (natural 20),
    not by percentage chance. The fields below are legacy and unused.
    """

    crit_chance: float = 0.10  # LEGACY: Not used (D20 uses natural 20)
    crit_multiplier: float = 1.5  # LEGACY: Not used (D20 doubles dice damage)
    recovery_time: float = 0.5  # Recovery time between auto-attack swings


class CombatSystem:
    """
    Manages all combat-related operations.

    Features:
    - Real-time combat with windups and swings
    - Damage calculation with strength bonus and armor reduction
    - Critical hit chance and multiplier
    - Loot dropping with configurable drop tables
    - Flee mechanic with dex-based difficulty scaling
    - Level-up integration

    Usage:
        combat = CombatSystem(ctx, config=CombatConfig())
        events = combat.start_attack(player_id, target_name)
        events = combat.attempt_flee(player_id)
    """

    def __init__(self, ctx: GameContext, config: CombatConfig | None = None) -> None:
        self.ctx = ctx
        self.config = config or CombatConfig()

    # ---------- Combat Initiation ----------

    async def start_attack(self, player_id: PlayerId, target_name: str) -> list[Event]:
        """
        Initiate an attack against a target.
        Starts the swing timer based on weapon speed.

        Args:
            player_id: The attacker
            target_name: Name/keyword of target to find in room

        Returns:
            List of events describing the attack start
        """
        world = self.ctx.world
        events: list[Event] = []

        player = world.players.get(player_id)
        if not player:
            return [self.ctx.msg_to_player(player_id, "You have no form.")]

        if not player.is_alive():
            return [self.ctx.msg_to_player(player_id, "You can't attack while dead.")]

        room = world.rooms.get(player.room_id)
        if not room:
            return [self.ctx.msg_to_player(player_id, "You are nowhere.")]

        # Check if already in combat with this target
        if player.combat.is_in_combat():
            current_target = player.combat.target_id
            if current_target:
                current_target_entity = world.players.get(
                    current_target
                ) or world.npcs.get(current_target)
                if current_target_entity:
                    return [
                        self.ctx.msg_to_player(
                            player_id,
                            f"You're already attacking {current_target_entity.name}! Use 'stop' to disengage first.",
                        )
                    ]

        # Find target - use engine's find method via _engine reference if available
        # For now, we'll use a simplified version here
        target = self._find_target(player_id, target_name)
        if not target:
            return [self.ctx.msg_to_player(player_id, f"'{target_name}' not found.")]

        # Can't attack yourself
        if target.id == player_id:
            return [self.ctx.msg_to_player(player_id, "You can't attack yourself!")]

        # Check if target is alive
        if not target.is_alive():
            return [
                self.ctx.msg_to_player(player_id, f"{target.name} is already dead.")
            ]

        # Start the attack
        player.start_attack(target.id, world.item_templates)

        # Schedule the swing completion
        weapon = player.combat.current_weapon
        self._schedule_swing_completion(player_id, target.id, weapon)

        # Generate attack message
        swing_time = weapon.swing_speed
        weapon_name = self._get_equipped_weapon_name(player_id)

        events.append(
            self.ctx.msg_to_player(
                player_id,
                f"You begin attacking {target.name} with your {weapon_name}... ({swing_time:.1f}s)",
            )
        )

        # Notify target
        if target.id in world.players:
            events.append(
                self.ctx.msg_to_player(target.id, f"{player.name} attacks you!")
            )

        # Broadcast to room
        events.append(
            self.ctx.msg_to_room(
                room.id,
                f"{player.name} attacks {target.name}!",
                exclude={player_id, target.id},
            )
        )

        # Add threat for NPCs and trigger combat start behavior
        if target.id in world.npcs:
            target.combat.add_threat(player_id, 100.0)
            # Trigger NPC retaliation behavior if engine callback is available
            if hasattr(self.ctx, "engine") and hasattr(
                self.ctx.engine, "_trigger_npc_combat_start"
            ):
                await self.ctx.engine._trigger_npc_combat_start(target.id, player_id)

        return events

    def start_attack_entity(
        self, attacker_id: EntityId, target_id: EntityId
    ) -> list[Event]:
        """
        Initiate an attack where both attacker and target are known entity IDs.
        This supports NPC-initiated attacks so they follow the same scheduling
        and messaging as player-initiated attacks.
        """
        world = self.ctx.world
        events: list[Event] = []

        attacker = world.players.get(attacker_id) or world.npcs.get(attacker_id)
        if not attacker:
            # If attacker not found, nothing to do
            return []

        if not attacker.is_alive():
            if attacker_id in world.players:
                return [
                    self.ctx.msg_to_player(attacker_id, "You can't attack while dead.")
                ]
            return []

        room = world.rooms.get(attacker.room_id)
        if not room:
            if attacker_id in world.players:
                return [self.ctx.msg_to_player(attacker_id, "You are nowhere.")]
            return []

        # Wake up sleeping attacker
        if attacker_id in world.players and attacker.is_sleeping:
            attacker.is_sleeping = False
            attacker.sleep_start_time = None
            events.append(
                self.ctx.msg_to_player(
                    attacker_id, "You wake up as you prepare to fight!"
                )
            )

        # Check if already in combat
        if attacker.combat.is_in_combat():
            current_target = attacker.combat.target_id
            if current_target:
                current_target_entity = world.players.get(
                    current_target
                ) or world.npcs.get(current_target)
                if current_target_entity and attacker_id in world.players:
                    return [
                        self.ctx.msg_to_player(
                            attacker_id,
                            f"You're already attacking {current_target_entity.name}! Use 'stop' to disengage first.",
                        )
                    ]

        target = world.players.get(target_id) or world.npcs.get(target_id)
        if not target:
            if attacker_id in world.players:
                return [
                    self.ctx.msg_to_player(attacker_id, "Your target cannot be found.")
                ]
            return []

        if target.id == attacker_id:
            if attacker_id in world.players:
                return [
                    self.ctx.msg_to_player(attacker_id, "You can't attack yourself!")
                ]
            return []

        if not target.is_alive():
            if attacker_id in world.players:
                return [
                    self.ctx.msg_to_player(
                        attacker_id, f"{target.name} is already dead."
                    )
                ]
            return []

        # Wake up sleeping target
        if target_id in world.players and target.is_sleeping:
            target.is_sleeping = False
            target.sleep_start_time = None
            events.append(
                self.ctx.msg_to_player(
                    target_id, "You wake with a start as you're attacked!"
                )
            )
            events.append(
                self.ctx.msg_to_room(
                    room.id, f"{target.name} jolts awake!", exclude={target_id}
                )
            )

        # Start the attack on the entity
        attacker.start_attack(target.id, world.item_templates)

        # Schedule the swing completion
        weapon = attacker.combat.current_weapon
        self._schedule_swing_completion(attacker_id, target.id, weapon)

        # Messaging
        swing_time = weapon.swing_speed
        weapon_name = self._get_equipped_weapon_name(attacker_id)

        if attacker_id in world.players:
            events.append(
                self.ctx.msg_to_player(
                    attacker_id,
                    f"You begin attacking {target.name} with your {weapon_name}... ({swing_time:.1f}s)",
                )
            )

        # Notify target if player
        if target.id in world.players:
            events.append(
                self.ctx.msg_to_player(target.id, f"{attacker.name} attacks you!")
            )

        # Room broadcast
        events.append(
            self.ctx.msg_to_room(
                room.id,
                f"{attacker.name} attacks {target.name}!",
                exclude={attacker_id, target_id},
            )
        )

        # Add threat for NPC targets
        if target.id in world.npcs:
            target.combat.add_threat(attacker_id, 100.0)

        return events

    def stop_combat(self, player_id: PlayerId, flee: bool = False) -> list[Event]:
        """
        Stop attacking or attempt to flee from combat.

        Args:
            player_id: The player disengaging
            flee: If True, attempt a dex-based flee instead of just stopping

        Returns:
            List of events describing the disengage/flee
        """
        world = self.ctx.world

        player = world.players.get(player_id)
        if not player:
            return [self.ctx.msg_to_player(player_id, "You have no form.")]

        if not player.combat.is_in_combat():
            return [self.ctx.msg_to_player(player_id, "You're not in combat.")]

        target_id = player.combat.target_id
        target = None
        if target_id:
            target = world.players.get(target_id) or world.npcs.get(target_id)

        events: list[Event] = []

        if flee:
            # Flee uses D20 Dexterity ability check
            # DC = 15 - (10 * missing_health_percent) - easier when injured
            # Roll: d20 + dexterity modifier
            health_percent = (
                player.current_health / player.max_health
                if player.max_health > 0
                else 1.0
            )
            missing_percent = 1.0 - health_percent
            flee_dc = max(5, 15 - int(10 * missing_percent))

            roll = random.randint(1, 20)
            dex_mod = player.get_ability_modifier(player.get_effective_dexterity())
            total = roll + dex_mod

            if total >= flee_dc:
                # Flee successful - find a random exit and move
                room = world.rooms.get(player.room_id)
                if room and room.exits:
                    direction = random.choice(list(room.exits.keys()))
                    exit_target = room.exits[direction]

                    # Cancel scheduled combat events
                    if player.combat.swing_event_id:
                        self.ctx.time_manager.cancel(player.combat.swing_event_id)

                    # Clear combat state
                    player.combat.clear_combat()

                    # Remove player from old room
                    room.entities.discard(player_id)

                    # Move player to new room
                    new_room = world.rooms.get(exit_target)
                    if new_room:
                        player.room_id = new_room.id
                        new_room.entities.add(player_id)

                        events.append(
                            self.ctx.msg_to_room(
                                room.id, f"{player.name} flees {direction}!"
                            )
                        )
                        events.append(
                            self.ctx.msg_to_player(
                                player_id,
                                f"You flee {direction}! (rolled {roll}+{dex_mod}={total} vs DC {flee_dc})",
                            )
                        )
                    else:
                        events.append(
                            self.ctx.msg_to_player(
                                player_id, "You try to flee but the exit leads nowhere!"
                            )
                        )
                else:
                    events.append(
                        self.ctx.msg_to_player(player_id, "There's nowhere to flee!")
                    )
            else:
                # Flee failed - stay in combat
                events.append(
                    self.ctx.msg_to_player(
                        player_id,
                        f"You fail to escape! (rolled {roll}+{dex_mod}={total} vs DC {flee_dc})",
                    )
                )
        else:
            # Regular disengage
            if player.combat.swing_event_id:
                self.ctx.time_manager.cancel(player.combat.swing_event_id)

            player.combat.clear_combat()

            if target:
                events.append(
                    self.ctx.msg_to_player(
                        player_id, f"You stop attacking {target.name}."
                    )
                )
            else:
                events.append(
                    self.ctx.msg_to_player(player_id, "You disengage from combat.")
                )

        return events

    def show_combat_status(self, player_id: PlayerId) -> list[Event]:
        """
        Show detailed combat status.

        Args:
            player_id: The player checking status

        Returns:
            List of events with combat information
        """
        world = self.ctx.world

        player = world.players.get(player_id)
        if not player:
            return [self.ctx.msg_to_player(player_id, "You have no form.")]

        combat = player.combat

        if not combat.is_in_combat():
            return [self.ctx.msg_to_player(player_id, "You are not in combat.")]

        target = None
        if combat.target_id:
            target = world.players.get(combat.target_id) or world.npcs.get(
                combat.target_id
            )

        target_name = target.name if target else "unknown"
        target_health = ""
        if target:
            health_pct = (target.current_health / target.max_health) * 100
            target_health = f" ({health_pct:.0f}% health)"

        phase_name = combat.phase.value
        progress = combat.get_phase_progress() * 100
        remaining = combat.get_phase_remaining()

        weapon = combat.current_weapon

        lines = [
            "**Combat Status**",
            f"Target: {target_name}{target_health}",
            f"Phase: {phase_name} ({progress:.0f}% - {remaining:.1f}s remaining)",
            f"Weapon: {weapon.damage_min}-{weapon.damage_max} damage, {weapon.swing_speed:.1f}s speed",
            f"Auto-attack: {'ON' if combat.auto_attack else 'OFF'}",
        ]

        return [self.ctx.msg_to_player(player_id, "\n".join(lines))]

    # ---------- Damage and Scheduling ----------

    def _schedule_swing_completion(
        self, attacker_id: EntityId, target_id: EntityId, weapon: WeaponStats
    ) -> None:
        """Schedule the completion of a swing (windup phase)."""

        async def swing_complete_callback():
            """Called when windup completes - transition to swing phase."""
            world = self.ctx.world
            attacker = world.players.get(attacker_id) or world.npcs.get(attacker_id)
            target = world.players.get(target_id) or world.npcs.get(target_id)

            if not attacker or not target or not attacker.is_alive():
                if attacker:
                    attacker.combat.clear_combat()
                return

            # Check positions
            if attacker.room_id != target.room_id:
                attacker.combat.clear_combat()
                if attacker_id in world.players:
                    await self.ctx.dispatch_events(
                        [
                            self.ctx.msg_to_player(
                                attacker_id, "Your target is no longer here."
                            )
                        ]
                    )
                return

            if not target.is_alive():
                attacker.combat.clear_combat()
                if attacker_id in world.players:
                    await self.ctx.dispatch_events(
                        [
                            self.ctx.msg_to_player(
                                attacker_id, f"{target.name} is already dead!"
                            )
                        ]
                    )
                return

            # Transition to swing and schedule damage
            from ..world import CombatPhase

            attacker.combat.start_phase(CombatPhase.SWING, weapon.swing_time)
            self._schedule_damage_application(attacker_id, target_id, weapon)

        event_id = f"combat_windup_{attacker_id}_{time.time()}"
        attacker = self.ctx.world.players.get(attacker_id) or self.ctx.world.npcs.get(
            attacker_id
        )
        if attacker:
            attacker.combat.swing_event_id = event_id

        self.ctx.time_manager.schedule(
            weapon.windup_time, swing_complete_callback, event_id=event_id
        )

    def _schedule_damage_application(
        self, attacker_id: EntityId, target_id: EntityId, weapon: WeaponStats
    ) -> None:
        """Schedule damage application during swing phase."""

        async def damage_callback():
            """Apply damage and handle combat continuation."""
            from ..world import CombatPhase, CombatResult

            world = self.ctx.world
            attacker = world.players.get(attacker_id) or world.npcs.get(attacker_id)
            target = world.players.get(target_id) or world.npcs.get(target_id)

            if not attacker or not target or not attacker.is_alive():
                if attacker:
                    attacker.combat.clear_combat()
                return

            # Validate target still alive and in same room
            if attacker.room_id != target.room_id or not target.is_alive():
                attacker.combat.clear_combat()
                return

            # ========== D20 ATTACK ROLL ==========
            # Use centralized d20 module for attack mechanics
            from . import d20

            attack_bonus = attacker.get_melee_attack_bonus()
            target_ac = target.get_effective_armor_class()

            # Make attack roll using centralized mechanics
            is_hit, attack_roll, attack_total, is_crit = d20.make_attack_roll(
                attack_bonus, target_ac
            )

            # If attack misses
            if not is_hit:
                events: list[Event] = []

                # Attacker message
                if attacker_id in world.players:
                    events.append(
                        self.ctx.msg_to_player(
                            attacker_id,
                            f"You swing at {target.name} but miss! (rolled {attack_roll}+{attack_bonus}={attack_total} vs AC {target_ac})",
                        )
                    )

                # Target message
                if target_id in world.players:
                    events.append(
                        self.ctx.msg_to_player(
                            target_id, f"{attacker.name} swings at you but misses!"
                        )
                    )

                # Room broadcast
                room = world.rooms.get(attacker.room_id)
                if room:
                    events.append(
                        self.ctx.msg_to_room(
                            room.id,
                            f"{attacker.name} swings at {target.name} but misses!",
                            exclude={attacker_id, target_id},
                        )
                    )

                # Continue auto-attack if enabled
                if attacker.combat.auto_attack and attacker.is_alive():
                    attacker.combat.start_phase(
                        CombatPhase.RECOVERY, self.config.recovery_time
                    )
                    self._schedule_next_swing(attacker_id, target_id, weapon)
                else:
                    attacker.combat.clear_combat()

                await self.ctx.dispatch_events(events)
                return

            # ========== ATTACK HIT - CALCULATE DAMAGE ==========
            # Base weapon damage
            damage = random.randint(weapon.damage_min, weapon.damage_max)

            # Add strength modifier to damage
            str_mod = attacker.get_ability_modifier(attacker.get_effective_strength())
            damage = max(1, damage + str_mod)

            # Critical hits use centralized mechanics
            if is_crit:
                damage = d20.calculate_critical_damage(damage, str_mod)

            # Apply damage
            target.current_health = max(0, target.current_health - damage)

            print(
                f"[Combat DEBUG] Attack roll: {attack_roll}+{attack_bonus}={attack_total} vs AC {target_ac} - HIT! Damage: {damage}"
            )

            # Build result
            CombatResult(
                success=True,
                damage_dealt=damage,
                damage_type=weapon.damage_type,
                was_critical=is_crit,
                attacker_id=attacker_id,
                defender_id=target_id,
            )

            # Generate events
            events: list[Event] = []
            crit_text = " **CRITICAL HIT!**" if is_crit else ""

            # Attacker message with attack roll info
            if attacker_id in world.players:
                roll_info = (
                    f" (rolled {attack_roll}+{attack_bonus}={attack_total} vs AC {target_ac})"
                    if not is_crit
                    else " (natural 20!)"
                )
                events.append(
                    self.ctx.msg_to_player(
                        attacker_id,
                        f"You hit {target.name} for {damage} damage!{crit_text}{roll_info}",
                    )
                )

            # Target message and health update
            if target_id in world.players:
                events.append(
                    self.ctx.msg_to_player(
                        target_id,
                        f"{attacker.name} hits you for {damage} damage!{crit_text}",
                    )
                )
                events.extend(self.ctx.event_dispatcher.emit_stat_update(target_id))

            # Room broadcast
            room = world.rooms.get(attacker.room_id)
            if room:
                events.append(
                    self.ctx.msg_to_room(
                        room.id,
                        f"{attacker.name} hits {target.name}!{crit_text}",
                        exclude={attacker_id, target_id},
                    )
                )

            # Check for death
            if not target.is_alive():
                print(
                    f"[Combat DEBUG] Target {target.name} is dead, calling handle_death"
                )
                events.extend(await self.handle_death(target_id, attacker_id))
                attacker.combat.clear_combat()
            else:
                # If the target is a player, make them automatically retaliate
                if target_id in world.players:
                    # Only auto-retaliate if the player is not already in combat
                    # (if they're fighting something else, let them handle it manually)
                    if not target.combat.is_in_combat():
                        try:
                            retaliation_events = self.start_attack_entity(
                                target_id, attacker_id
                            )
                            if retaliation_events:
                                await self.ctx.dispatch_events(retaliation_events)
                        except Exception:
                            # Don't let retaliation errors break the combat flow
                            pass
                # If the target is an NPC, trigger engine hooks so behaviors can respond
                elif target_id in world.npcs and self.ctx.engine:
                    await self.ctx.engine._trigger_npc_combat_start(
                        target_id, attacker_id
                    )

                # Continue auto-attack if enabled for the attacker
                if attacker.combat.auto_attack and attacker.is_alive():
                    attacker.combat.start_phase(
                        CombatPhase.RECOVERY, self.config.recovery_time
                    )
                    self._schedule_next_swing(attacker_id, target_id, weapon)
                else:
                    attacker.combat.clear_combat()

            await self.ctx.dispatch_events(events)

        event_id = f"combat_damage_{attacker_id}_{time.time()}"
        self.ctx.time_manager.schedule(
            weapon.swing_time, damage_callback, event_id=event_id
        )

    def _schedule_next_swing(
        self, attacker_id: EntityId, target_id: EntityId, weapon: WeaponStats
    ) -> None:
        """Schedule the next swing in auto-attack sequence."""

        async def next_swing_callback():
            """Start next attack."""
            world = self.ctx.world
            attacker = world.players.get(attacker_id) or world.npcs.get(attacker_id)
            target = world.players.get(target_id) or world.npcs.get(target_id)

            if not attacker or not attacker.is_alive():
                return

            if (
                not target
                or not target.is_alive()
                or attacker.room_id != target.room_id
            ):
                attacker.combat.clear_combat()
                if attacker_id in world.players:
                    await self.ctx.dispatch_events(
                        [self.ctx.msg_to_player(attacker_id, "Combat ended.")]
                    )
                return

            # Phase 14.3: For NPCs with abilities, trigger on_combat_action hook
            # This gives behaviors a chance to use abilities instead of basic attacks
            if attacker_id in world.npcs and self.ctx.engine:
                npc = world.npcs[attacker_id]
                if npc.has_character_sheet():
                    # Trigger ability behavior hook
                    result = await self.ctx.engine._run_behavior_hook(
                        attacker_id, "on_combat_action", target_id
                    )
                    # If behavior cast an ability, skip this basic attack cycle
                    # The ability execution handles its own timing
                    if result and result.handled and result.cast_ability:
                        # Reschedule next swing after ability cooldown
                        # For now, use same recovery time as basic attack
                        self.ctx.time_manager.schedule(
                            self.config.recovery_time
                            * 1.5,  # Slightly longer for abilities
                            next_swing_callback,
                            event_id=f"combat_recovery_{attacker_id}_{time.time()}",
                        )
                        return

            # Start next swing (basic attack)
            attacker.start_attack(target_id, world.item_templates)
            self._schedule_swing_completion(attacker_id, target_id, weapon)

        self.ctx.time_manager.schedule(
            self.config.recovery_time,
            next_swing_callback,
            event_id=f"combat_recovery_{attacker_id}_{time.time()}",
        )

    # ---------- Death and Loot ----------

    def roll_and_drop_loot(
        self, drop_table: list, room_id: RoomId, npc_name: str
    ) -> list[Event]:
        """
        Roll loot from a drop table and create items in the room.

        Args:
            drop_table: List of {"template_id": str, "chance": float, "quantity": int|[min,max]}
            room_id: Room to drop items into
            npc_name: Name of the NPC for broadcast messages

        Returns:
            List of events for loot drop messages
        """
        from ..world import WorldItem

        events: list[Event] = []
        world = self.ctx.world
        room = world.rooms.get(room_id)
        if not room:
            return events

        for drop in drop_table:
            template_id = drop.get("template_id")
            chance = drop.get("chance", 1.0)
            quantity_spec = drop.get("quantity", 1)

            # Roll for drop chance
            if random.random() > chance:
                continue

            # Determine quantity
            if isinstance(quantity_spec, list) and len(quantity_spec) == 2:
                quantity = random.randint(quantity_spec[0], quantity_spec[1])
            else:
                quantity = int(quantity_spec)

            if quantity <= 0:
                continue

            # Get template
            template = world.item_templates.get(template_id)
            if not template:
                continue

            # Create item instance
            item_id = f"loot_{uuid.uuid4().hex[:12]}"
            item = WorldItem(
                id=item_id,
                template_id=template_id,
                name=template.name,
                keywords=list(template.keywords),
                room_id=room_id,
                quantity=quantity,
                current_durability=(
                    template.max_durability if template.has_durability else None
                ),
                _description=template.description,
            )

            # Add to world and room
            world.items[item_id] = item
            room.items.add(item_id)

            # Broadcast drop message
            quantity_str = f" x{quantity}" if quantity > 1 else ""
            events.append(
                self.ctx.msg_to_room(
                    room_id, f"💎 {npc_name} drops {template.name}{quantity_str}."
                )
            )

        return events

    async def handle_death(
        self, victim_id: EntityId, killer_id: EntityId
    ) -> list[Event]:
        """
        Handle entity death - loot drops, XP, level-ups.

        Args:
            victim_id: The entity that died
            killer_id: The entity that killed victim

        Returns:
            List of events describing death and consequences
        """

        events: list[Event] = []
        world = self.ctx.world

        victim = world.players.get(victim_id) or world.npcs.get(victim_id)
        killer = world.players.get(killer_id) or world.npcs.get(killer_id)

        if not victim:
            return events

        victim_name = victim.name
        killer_name = killer.name if killer else "unknown forces"

        # Death message to room
        room = world.rooms.get(victim.room_id)
        if room:
            events.append(
                self.ctx.msg_to_room(
                    room.id, f"💀 {victim_name} has been slain by {killer_name}!"
                )
            )

        # If victim was an NPC, trigger respawn and loot
        if victim_id in world.npcs:
            npc = world.npcs[victim_id]

            # Remove from room
            if room:
                room.entities.discard(victim_id)

            # Record death time for respawn
            npc.last_killed_at = time.time()

            # Get template for loot and XP
            template = world.npc_templates.get(npc.template_id)

            # Drop loot to room floor
            if template and template.drop_table and room:
                loot_events = self.roll_and_drop_loot(
                    template.drop_table, room.id, victim_name
                )
                events.extend(loot_events)

            # Award XP to killer if it's a player
            if killer_id in world.players and template:
                xp_reward = template.experience_reward
                killer_player = world.players[killer_id]
                killer_player.experience += xp_reward
                events.append(
                    self.ctx.msg_to_player(
                        killer_id, f"You gain {xp_reward} experience!"
                    )
                )

                # Hook: Quest system KILL objective tracking
                if self.ctx.quest_system:
                    quest_events = self.ctx.quest_system.on_npc_killed(
                        killer_id, npc.template_id
                    )
                    events.extend(quest_events)

                # Check for level-up
                level_ups = killer_player.check_level_up()
                for level_data in level_ups:
                    new_level = level_data["new_level"]
                    gains = level_data["stat_gains"]

                    # Build stat gain message
                    gain_parts = []
                    if gains.get("max_health"):
                        gain_parts.append(f"+{gains['max_health']} HP")
                    if gains.get("max_energy"):
                        gain_parts.append(f"+{gains['max_energy']} Energy")
                    if gains.get("strength"):
                        gain_parts.append(f"+{gains['strength']} STR")
                    if gains.get("dexterity"):
                        gain_parts.append(f"+{gains['dexterity']} DEX")
                    if gains.get("intelligence"):
                        gain_parts.append(f"+{gains['intelligence']} INT")
                    if gains.get("vitality"):
                        gain_parts.append(f"+{gains['vitality']} VIT")

                    gains_str = ", ".join(gain_parts)
                    events.append(
                        self.ctx.msg_to_player(
                            killer_id,
                            f"🎉 **LEVEL UP!** You reached level {new_level}! ({gains_str})",
                        )
                    )

        # If victim was a player, handle death state
        if victim_id in world.players:
            print(f"[Combat DEBUG] Player {victim_id} death handling triggered")
            player = world.players[victim_id]

            # Remove player from room (they're dead)
            if room:
                room.entities.discard(victim_id)

            # Clear combat state using the proper method
            player.combat.clear_combat()

            # Cancel any pending attack timer
            if player.combat.swing_event_id:
                self.ctx.time_manager.cancel(player.combat.swing_event_id)
                player.combat.swing_event_id = None

            events.append(
                self.ctx.msg_to_player(
                    victim_id,
                    f"☠️ **You have been slain by {killer_name}!**\n\n"
                    "Your vision fades to black as your spirit separates from your body...\n"
                    "Respawning in 10 seconds.",
                )
            )

            # Schedule respawn countdown via engine
            if self.ctx.engine:
                self.ctx.engine.schedule_player_respawn(victim_id, countdown_seconds=10)

            # Phase 6: Critical save on player death
            if self.ctx.state_tracker:
                from .persistence import ENTITY_PLAYER

                await_coro = self.ctx.state_tracker.mark_dirty(
                    ENTITY_PLAYER, victim_id, critical=True
                )
                # Since we're in sync context, schedule the async critical save
                import asyncio

                asyncio.create_task(await_coro)

        return events

    # ---------- Helpers ----------

    def _get_equipped_weapon_name(self, entity_id: EntityId) -> str:
        """Get the name of the equipped weapon, or 'fists'."""
        world = self.ctx.world
        entity = world.players.get(entity_id) or world.npcs.get(entity_id)
        if not entity:
            return "fists"

        if "weapon" in entity.equipped_items:
            weapon_template_id = entity.equipped_items["weapon"]
            weapon_template = world.item_templates.get(weapon_template_id)
            if weapon_template:
                return weapon_template.name

        return "fists"

    def _find_target(self, player_id: PlayerId, target_name: str) -> WorldEntity | None:
        """
        Simple target finding by name in current room.

        Supports numbered targeting: "2.goblin" will find the second goblin.
        """
        world = self.ctx.world
        player = world.players.get(player_id)
        if not player:
            return None

        room = world.rooms.get(player.room_id)
        if not room:
            return None

        # Parse numbered targeting
        target_index = 1
        actual_search = target_name
        if "." in target_name:
            parts = target_name.split(".", 1)
            if len(parts) == 2 and parts[0].isdigit():
                target_num = int(parts[0])
                if target_num >= 1:
                    target_index = target_num
                    actual_search = parts[1]

        search_lower = actual_search.lower()
        matches_found = 0

        for entity_id in room.entities:
            # Check players
            if entity_id in world.players:
                target = world.players[entity_id]
                if (
                    target.name.lower() == search_lower
                    or search_lower in target.name.lower()
                ):
                    matches_found += 1
                    if matches_found == target_index:
                        return target

            # Check NPCs
            if entity_id in world.npcs:
                target = world.npcs[entity_id]
                if not target.is_alive():
                    continue

                template = world.npc_templates.get(target.template_id)
                if not template:
                    continue

                npc_name = target.instance_data.get("name_override", target.name)
                if npc_name.lower() == search_lower or search_lower in npc_name.lower():
                    matches_found += 1
                    if matches_found == target_index:
                        return target
                    continue

                for keyword in template.keywords:
                    if search_lower == keyword.lower():
                        matches_found += 1
                        if matches_found == target_index:
                            return target
                        break

        return None
