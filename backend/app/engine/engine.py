# backend/app/engine/engine.py
import asyncio
import time
import uuid
import logging
from typing import Dict, List, Any, Callable, Awaitable, Optional

from .world import (
    World, WorldRoom, Direction, PlayerId, RoomId, AreaId, get_room_emoji, 
    TimeEvent, Effect, EntityType, EntityId, WorldEntity, WorldPlayer, WorldNpc,
    WorldArea,
    Targetable, TargetableType, WorldItem, ItemId,
    CombatPhase, CombatState, CombatResult, WeaponStats,
    get_xp_for_next_level, LEVEL_UP_STAT_GAINS, ResourcePool
)
from .behaviors import (
    BehaviorContext, BehaviorResult, get_behavior_instances
)
from .systems import GameContext, TimeEventManager, EventDispatcher, CombatSystem, EffectSystem, CommandRouter, TriggerSystem, TriggerContext, QuestSystem, StateTracker, ENTITY_PLAYER, ENTITY_ROOM, ENTITY_NPC, ENTITY_ITEM, ENTITY_TRIGGER
from .systems.classes import ClassSystem
from .systems.abilities import AbilityExecutor
from .systems.group_system import GroupSystem
from .systems.clan_system import ClanSystem
from .systems.faction_system import FactionSystem



Event = dict[str, Any]

# Module logger for persistence and debug info
logger = logging.getLogger(__name__)


class WorldEngine:
    """
    Core game engine.

    - Holds a reference to the in-memory World.
    - Consumes commands from players via an asyncio.Queue.
    - Produces events destined for players via per-player queues.
    - Supports per-player messages and room broadcasts.
    - Persists player stats to database on disconnect (and optionally periodically).
    
    Uses modular systems for specific domains:
    - GameContext: Shared state and cross-system communication
    - TimeEventManager: Scheduled events and timers
    - EventDispatcher: Event creation and routing
    """

    def __init__(
        self,
        world: World,
        db_session_factory: Callable[[], Awaitable[Any]] | None = None
    ) -> None:
        self.world = world
        self._db_session_factory = db_session_factory

        # Queue of (player_id, command_text)
        self._command_queue: asyncio.Queue[tuple[PlayerId, str]] = asyncio.Queue()

        # Command history (for ! repeat command)
        self._last_commands: Dict[PlayerId, str] = {}
        
        # Initialize game context and systems
        self.ctx = GameContext(world)
        self.ctx.engine = self  # Set engine reference for systems to trigger hooks
        self.time_manager = TimeEventManager(self.ctx)
        self.ctx.time_manager = self.time_manager
        self.event_dispatcher = EventDispatcher(self.ctx)
        self.ctx.event_dispatcher = self.event_dispatcher
        self.combat_system = CombatSystem(self.ctx)
        self.ctx.combat_system = self.combat_system
        self.effect_system = EffectSystem(self.ctx)
        self.ctx.effect_system = self.effect_system
        self.trigger_system = TriggerSystem(self.ctx)
        self.ctx.trigger_system = self.trigger_system
        self.quest_system = QuestSystem(self.ctx)
        self.ctx.quest_system = self.quest_system
        
        # Phase 10.1: Social systems (groups, tells, follows)
        self.group_system = GroupSystem()
        self.ctx.group_system = self.group_system
        
        # Phase 10.2: Clan system (persistent player organizations)
        self.clan_system = ClanSystem(db_session_factory)
        self.ctx.clan_system = self.clan_system
        
        # Phase 10.3: Faction system (NPC factions with reputation)
        self.faction_system = FactionSystem(db_session_factory)
        self.ctx.faction_system = self.faction_system
        
        # Phase 9: Character classes and abilities system
        self.class_system = ClassSystem(self.ctx)
        self.ctx.class_system = self.class_system
        self.ability_executor = AbilityExecutor(self.ctx)
        self.ctx.ability_executor = self.ability_executor
        
        # Phase 11: Lighting and vision system
        from app.engine.systems.lighting import LightingSystem
        self.lighting_system = LightingSystem(world, self.time_manager)
        self.ctx.lighting_system = self.lighting_system
        
        # Phase 6: State persistence tracker
        if db_session_factory:
            self.state_tracker = StateTracker(self.ctx, db_session_factory)
            self.ctx.state_tracker = self.state_tracker
        else:
            self.state_tracker = None
        
        self.command_router = CommandRouter(self)
        
        # Backward compatibility: reference listeners from context
        self._listeners = self.ctx._listeners
        
        # Register all command handlers
        self._register_command_handlers()

    def _register_command_handlers(self) -> None:
        """
        Register all game command handlers with the router.
        
        This is called once during engine initialization to set up the
        command dispatch system with decorated command handlers.
        """
        # Movement commands - register each direction separately so the handler knows which one was used
        directions = {
            "n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down",
            "north": "north", "south": "south", "east": "east", "west": "west", "up": "up", "down": "down"
        }
        for cmd_name, direction in directions.items():
            # Create a closure to capture the direction for each handler
            def make_move_handler(dir_name):
                def handler(engine: Any, player_id: PlayerId, args: str) -> List[Event]:
                    return self._move_player(player_id, dir_name)
                return handler
            
            self.command_router.register_handler(
                primary_name=direction,
                handler=make_move_handler(direction),
                names=[cmd_name],
                category="movement",
                description=f"Move {direction}",
                usage=""
            )
        
        # Look commands
        self.command_router.register_handler(
            primary_name="look",
            handler=self._handle_look_command,
            names=["look", "l"],
            category="view",
            description="Examine your surroundings or a specific entity",
            usage="[target_name]"
        )
        
        # Stats command
        self.command_router.register_handler(
            primary_name="stats",
            handler=self._show_stats_handler,
            names=["stats", "sheet", "status"],
            category="character",
            description="View your character stats",
            usage=""
        )
        
        # Sleep/Wake commands for regeneration
        self.command_router.register_handler(
            primary_name="sleep",
            handler=self._sleep_handler,
            names=["sleep", "rest"],
            category="character",
            description="Sleep to regenerate HP and resources faster",
            usage=""
        )
        
        self.command_router.register_handler(
            primary_name="wake",
            handler=self._wake_handler,
            names=["wake", "awaken", "stand"],
            category="character",
            description="Wake up from sleeping",
            usage=""
        )
        
        # Say command
        self.command_router.register_handler(
            primary_name="say",
            handler=self._say_handler,
            names=["say"],
            category="social",
            description="Speak to others in the room",
            usage="<message>"
        )
        
        # Emotes
        self.command_router.register_handler(
            primary_name="emote",
            handler=self._emote_handler,
            names=["smile", "nod", "laugh", "cringe", "smirk", "frown", "wink", "lookaround"],
            category="social",
            description="Show an emote",
            usage=""
        )
        
        # Inventory
        self.command_router.register_handler(
            primary_name="inventory",
            handler=self._inventory_handler,
            names=["inventory", "inv", "i"],
            category="inventory",
            description="View your inventory",
            usage=""
        )
        
        # Get/Take commands
        self.command_router.register_handler(
            primary_name="get",
            handler=self._get_handler,
            names=["get", "take", "pickup"],
            category="inventory",
            description="Pick up an item",
            usage="<item_name> [from <container>]"
        )
        
        # Drop command
        self.command_router.register_handler(
            primary_name="drop",
            handler=self._drop_handler,
            names=["drop"],
            category="inventory",
            description="Drop an item",
            usage="<item_name>"
        )
        
        # Equip commands
        self.command_router.register_handler(
            primary_name="equip",
            handler=self._equip_handler,
            names=["equip", "wear", "wield"],
            category="inventory",
            description="Equip an item",
            usage="<item_name>"
        )
        
        # Unequip commands
        self.command_router.register_handler(
            primary_name="unequip",
            handler=self._unequip_handler,
            names=["unequip", "remove"],
            category="inventory",
            description="Unequip an item",
            usage="<item_name>"
        )
        
        # Use/Consume commands
        self.command_router.register_handler(
            primary_name="use",
            handler=self._use_handler,
            names=["use", "consume", "drink"],
            category="inventory",
            description="Use a consumable item",
            usage="<item_name>"
        )
        
        # Combat commands
        self.command_router.register_handler(
            primary_name="attack",
            handler=self._attack_handler,
            names=["attack", "kill", "fight", "hit"],
            category="combat",
            description="Attack a target",
            usage="<target_name>"
        )
        
        # Stop combat/Flee
        self.command_router.register_handler(
            primary_name="stop",
            handler=self._stop_combat_handler,
            names=["stop", "disengage"],
            category="combat",
            description="Stop attacking",
            usage=""
        )
        
        self.command_router.register_handler(
            primary_name="flee",
            handler=self._flee_handler,
            names=["flee"],
            category="combat",
            description="Attempt to flee from combat",
            usage=""
        )
        
        # Combat status
        self.command_router.register_handler(
            primary_name="combat",
            handler=self._show_combat_status_handler,
            names=["combat", "cs"],
            category="combat",
            description="Show combat status",
            usage=""
        )
        
        # Effects
        self.command_router.register_handler(
            primary_name="effects",
            handler=self._show_effects_handler,
            names=["effects"],
            category="character",
            description="Show active effects",
            usage=""
        )
        
        # Admin commands
        self.command_router.register_handler(
            primary_name="heal",
            handler=self._heal_handler,
            names=["heal"],
            category="admin",
            description="[Admin] Heal a target",
            usage="<target_name>"
        )
        
        self.command_router.register_handler(
            primary_name="hurt",
            handler=self._hurt_handler,
            names=["hurt"],
            category="admin",
            description="[Admin] Hurt a target",
            usage="<target_name>"
        )
        
        # Quest commands (Phase X)
        self.command_router.register_handler(
            primary_name="journal",
            handler=self._journal_handler,
            names=["journal", "quests", "j"],
            category="quest",
            description="View your quest journal",
            usage=""
        )
        
        self.command_router.register_handler(
            primary_name="quest",
            handler=self._quest_handler,
            names=["quest"],
            category="quest",
            description="View details of a specific quest",
            usage="<quest_name>"
        )
        
        self.command_router.register_handler(
            primary_name="abandon",
            handler=self._abandon_handler,
            names=["abandon"],
            category="quest",
            description="Abandon a quest",
            usage="<quest_name>"
        )
        
        # Dialogue commands (Phase X.2)
        self.command_router.register_handler(
            primary_name="talk",
            handler=self._talk_handler,
            names=["talk", "speak"],
            category="social",
            description="Talk to an NPC",
            usage="<npc_name>"
        )
        
        # Phase 8: Admin commands
        self.command_router.register_handler(
            primary_name="who",
            handler=self._who_handler,
            names=["who", "online"],
            category="admin",
            description="[Mod] List online players",
            usage=""
        )
        
        self.command_router.register_handler(
            primary_name="where",
            handler=self._where_handler,
            names=["where", "locate"],
            category="admin",
            description="[Mod] Find a player's location",
            usage="<player_name>"
        )
        
        self.command_router.register_handler(
            primary_name="goto",
            handler=self._goto_handler,
            names=["goto", "tp"],
            category="admin",
            description="[GM] Teleport to a room or player",
            usage="<room_id|player_name>"
        )
        
        self.command_router.register_handler(
            primary_name="summon",
            handler=self._summon_handler,
            names=["summon"],
            category="admin",
            description="[GM] Summon a player to your location",
            usage="<player_name>"
        )
        
        self.command_router.register_handler(
            primary_name="spawn",
            handler=self._spawn_handler,
            names=["spawn"],
            category="admin",
            description="[GM] Spawn an NPC or item",
            usage="npc|item <template_id>"
        )
        
        self.command_router.register_handler(
            primary_name="despawn",
            handler=self._despawn_handler,
            names=["despawn"],
            category="admin",
            description="[GM] Despawn an NPC",
            usage="<npc_name>"
        )
        
        self.command_router.register_handler(
            primary_name="give",
            handler=self._give_handler,
            names=["give"],
            category="admin",
            description="[GM] Give an item to a player",
            usage="<player_name> <item_template>"
        )
        
        self.command_router.register_handler(
            primary_name="lightlevel",
            handler=self._lightlevel_handler,
            names=["lightlevel", "ll"],
            category="admin",
            description="[GM] Check light level in current room",
            usage=""
        )
        
        self.command_router.register_handler(
            primary_name="inspect",
            handler=self._inspect_handler,
            names=["inspect", "examine"],
            category="admin",
            description="[GM] Get detailed info on a target",
            usage="<target_name>"
        )
        
        self.command_router.register_handler(
            primary_name="broadcast",
            handler=self._broadcast_handler,
            names=["broadcast", "announce"],
            category="admin",
            description="[Admin] Broadcast message to all players",
            usage="<message>"
        )
        
        self.command_router.register_handler(
            primary_name="kick",
            handler=self._kick_command_handler,
            names=["kick"],
            category="admin",
            description="[Mod] Kick a player from the game",
            usage="<player_name> [reason]"
        )
        
        self.command_router.register_handler(
            primary_name="mute",
            handler=self._mute_handler,
            names=["mute"],
            category="admin",
            description="[Mod] Mute a player",
            usage="<player_name>"
        )
        
        self.command_router.register_handler(
            primary_name="unmute",
            handler=self._unmute_handler,
            names=["unmute"],
            category="admin",
            description="[Mod] Unmute a player",
            usage="<player_name>"
        )
        
        self.command_router.register_handler(
            primary_name="warn",
            handler=self._warn_handler,
            names=["warn"],
            category="admin",
            description="[Mod] Warn a player",
            usage="<player_name> <reason>"
        )
        
        self.command_router.register_handler(
            primary_name="revive",
            handler=self._revive_handler,
            names=["revive"],
            category="admin",
            description="[GM] Revive a dead player",
            usage="<player_name>"
        )
        
        self.command_router.register_handler(
            primary_name="invis",
            handler=self._invis_handler,
            names=["invis", "invisible"],
            category="admin",
            description="[Mod] Make a player invisible",
            usage="[player_name]"
        )
        
        self.command_router.register_handler(
            primary_name="visible",
            handler=self._visible_handler,
            names=["visible", "vis"],
            category="admin",
            description="[Mod] Make a player visible",
            usage="[player_name]"
        )
        
        self.command_router.register_handler(
            primary_name="reload",
            handler=self._reload_handler,
            names=["reload"],
            category="admin",
            description="[Admin] Reload game content from YAML",
            usage="[content_type]"
        )
        
        self.command_router.register_handler(
            primary_name="ban",
            handler=self._ban_command_handler,
            names=["ban"],
            category="admin",
            description="[Admin] Ban a player account",
            usage="<player_name> <reason>"
        )
        
        self.command_router.register_handler(
            primary_name="unban",
            handler=self._unban_command_handler,
            names=["unban"],
            category="admin",
            description="[Admin] Unban a player account",
            usage="<player_name>"
        )
        
        self.command_router.register_handler(
            primary_name="setstat",
            handler=self._setstat_handler,
            names=["setstat"],
            category="admin",
            description="[GM] Set a player's stat",
            usage="<player_name> <stat> <value>"
        )
        
        # Phase 9: Ability commands
        self.command_router.register_handler(
            primary_name="cast",
            handler=self._cast_handler,
            names=["cast", "c"],
            category="abilities",
            description="Cast an ability",
            usage="<ability_name> [target_name]"
        )
        
        self.command_router.register_handler(
            primary_name="abilities",
            handler=self._abilities_handler,
            names=["abilities", "skills", "ab"],
            category="abilities",
            description="View your learned abilities",
            usage=""
        )
        
        self.command_router.register_handler(
            primary_name="resources",
            handler=self._resources_handler,
            names=["resources", "mana", "energy", "rage"],
            category="character",
            description="View your character resources",
            usage=""
        )
        
        # Phase 10.1: Social commands (groups, tells, follows, yells)
        from app.commands.social import (
            register_group_commands,
            register_tell_commands,
            register_follow_commands,
            register_yell_commands,
            register_clan_commands,
            register_faction_commands,
        )
        register_group_commands(self.command_router)
        register_tell_commands(self.command_router)
        register_follow_commands(self.command_router)
        register_yell_commands(self.command_router)
        register_clan_commands(self.command_router)
        register_faction_commands(self.command_router)
        
        # Quit command - graceful disconnect
        self.command_router.register_handler(
            primary_name="quit",
            handler=self._quit_handler,
            names=["quit", "logout", "exit"],
            category="system",
            description="Disconnect and return to character selection",
            usage=""
        )

    # ---------- Command wrapper adapters (convert CommandRouter signature) ----------

    def _show_stats_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for stats command."""
        return self._show_stats(player_id)

    def _sleep_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Handler for sleep command - enter sleeping state for faster regeneration."""
        return self._sleep(player_id)
    
    def _wake_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Handler for wake command - exit sleeping state."""
        return self._wake(player_id)

    def _say_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for say command."""
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Say what?")]
        return self._say(player_id, args)

    def _emote_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for emote commands."""
        return self._emote(player_id, args)

    def _inventory_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for inventory command."""
        return self._inventory(player_id)

    def _get_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for get/take command."""
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Get what?")]
        return self._handle_get_command(player_id, args)

    def _drop_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for drop command."""
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Drop what?")]
        return self._drop(player_id, args)

    def _equip_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for equip command."""
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Equip what?")]
        return self._equip(player_id, args)

    def _unequip_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for unequip command."""
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Unequip what?")]
        return self._unequip(player_id, args)

    def _use_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for use/consume command."""
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Use what?")]
        return self._use(player_id, args)

    async def _attack_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for attack command."""
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Attack whom?")]
        return await self._attack(player_id, args)

    def _stop_combat_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for stop combat command."""
        return self._stop_combat(player_id, flee=False)

    def _flee_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for flee command."""
        return self._stop_combat(player_id, flee=True)

    def _show_combat_status_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for combat status command."""
        return self._show_combat_status(player_id)

    def _show_effects_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for effects command."""
        return self._show_effects(player_id)

    # Phase 9: Ability command handlers
    
    async def _cast_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for cast ability command."""
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Cast which ability?")]
        return await self._cast_ability(player_id, args)
    
    def _abilities_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for abilities/skills command. Use 'list' to show locked abilities."""
        show_locked = args.strip().lower() == "list"
        return self._show_abilities(player_id, show_locked=show_locked)
    
    def _resources_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for resources command."""
        return self._show_resources(player_id)

    def _heal_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for heal command. Requires GAME_MASTER role."""
        # Permission check
        if not self._check_permission(player_id, "MODIFY_STATS"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Heal whom?")]
        return self._heal(player_id, args)

    def _hurt_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Adapter for hurt command. Requires GAME_MASTER role."""
        # Permission check
        if not self._check_permission(player_id, "MODIFY_STATS"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Hurt whom?")]
        return self._hurt(player_id, args)

    # ---------- Phase 8: Admin command handlers ----------

    def _lightlevel_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[GM] Check the light level in the current room and show contributing sources."""
        if not self._check_permission(player_id, "TELEPORT"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        player = self.world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "Player not found.")]
        
        room = self.world.rooms.get(player.room_id)
        if not room:
            return [self._msg_to_player(player_id, "You are not in a valid room.")]
        
        # Get comprehensive light information
        import time
        current_time = time.time()
        light_level = self.lighting_system.calculate_room_light(room, current_time)
        visibility = self.lighting_system.get_visibility_level(light_level)
        room_state = self.lighting_system.room_light_states.get(room.room_id)
        
        area = self.world.areas.get(room.area_id) if room.area_id else None
        
        # Build detailed light report
        lines = [f"🔦 Light Level Analysis: {room.name}"]
        lines.append("=" * 50)
        lines.append(f"Light Level: {light_level}/100")
        lines.append(f"Visibility: {visibility.name} ({visibility.value})")
        lines.append("")
        
        if room_state:
            lines.append("Contributing Light Sources:")
            lines.append("-" * 50)
            
            # Calculate base ambient light
            if area:
                from .systems.lighting import AMBIENT_LIGHTING_VALUES
                ambient_str = getattr(area, "ambient_lighting", "normal")
                ambient = AMBIENT_LIGHTING_VALUES.get(ambient_str, 60)
                biome_name = area.biome
                lines.append(f"  Ambient ({biome_name}): +{ambient}")
            else:
                lines.append(f"  Ambient (no area): +60")
            
            # Time of day modifier
            if area and hasattr(area, 'area_time'):
                from .systems.lighting import TIME_IMMUNE_BIOMES
                if area.biome not in TIME_IMMUNE_BIOMES:
                    time_modifier = self.lighting_system._calculate_time_modifier(area, current_time)
                    if time_modifier != 0:
                        time_period = area.area_time.get_time_period() if hasattr(area.area_time, 'get_time_period') else "unknown"
                        sign = "+" if time_modifier > 0 else ""
                        lines.append(f"  Time of Day ({time_period}): {sign}{time_modifier}")
            
            # Active light/darkness sources
            if room_state.active_light_sources:
                light_count = sum(1 for s in room_state.active_light_sources.values() if s.intensity > 0)
                dark_count = sum(1 for s in room_state.active_light_sources.values() if s.intensity < 0)
                
                if light_count > 0:
                    lines.append(f"  Active Light Sources: {light_count}")
                    for source_id, source in room_state.active_light_sources.items():
                        if source.intensity > 0:
                            source_type = source.source_type.replace('_', ' ').title()
                            import datetime
                            expires_str = datetime.datetime.fromtimestamp(source.expires_at).strftime("%H:%M:%S") if source.expires_at else "permanent"
                            lines.append(f"    - {source_type} '{source_id}': +{source.intensity} (expires: {expires_str})")
                
                if dark_count > 0:
                    lines.append(f"  Darkness Effects: {dark_count}")
                    for source_id, source in room_state.active_light_sources.items():
                        if source.intensity < 0:
                            source_type = source.source_type.replace('_', ' ').title()
                            import datetime
                            expires_str = datetime.datetime.fromtimestamp(source.expires_at).strftime("%H:%M:%S") if source.expires_at else "permanent"
                            lines.append(f"    - {source_type} '{source_id}': {source.intensity} (expires: {expires_str})")
        else:
            lines.append("Light state not initialized for this room.")
        
        lines.append("=" * 50)
        
        # Visibility implications
        if visibility == VisibilityLevel.NONE:
            lines.append("⚫ Pitch black - Cannot see anything")
        elif visibility == VisibilityLevel.MINIMAL:
            lines.append("🌑 Minimal - Can only sense presence of things")
        elif visibility == VisibilityLevel.PARTIAL:
            lines.append("🌘 Partial - Can see basic details")
        elif visibility == VisibilityLevel.NORMAL:
            lines.append("🌕 Normal - Full visibility")
        elif visibility == VisibilityLevel.ENHANCED:
            lines.append("✨ Enhanced - Perfect clarity")
        
        return [self._msg_to_player(player_id, "\n".join(lines))]

    def _who_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[Mod] List all online players with their locations."""
        if not self._check_permission(player_id, "KICK_PLAYER"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        online_players = [p for p in self.world.players.values() if p.is_connected]
        
        if not online_players:
            return [self._msg_to_player(player_id, "No players online.")]
        
        lines = ["📋 Online Players:"]
        lines.append("-" * 40)
        for p in sorted(online_players, key=lambda x: x.name):
            room = self.world.rooms.get(p.room_id)
            room_name = room.name if room else "Unknown"
            hp_pct = int((p.current_health / p.max_health) * 100) if p.max_health > 0 else 0
            lines.append(f"  {p.name} (Lv{p.level}) - {room_name} [{hp_pct}% HP]")
        lines.append("-" * 40)
        lines.append(f"Total: {len(online_players)} player(s)")
        
        return [self._msg_to_player(player_id, "\n".join(lines))]

    def _where_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[Mod] Find a player's location."""
        if not self._check_permission(player_id, "KICK_PLAYER"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Where is whom? Usage: where <player_name>")]
        
        target_name = args.strip().lower()
        target = None
        for p in self.world.players.values():
            if p.name.lower() == target_name or p.name.lower().startswith(target_name):
                target = p
                break
        
        if not target:
            return [self._msg_to_player(player_id, f"Player '{args.strip()}' not found.")]
        
        room = self.world.rooms.get(target.room_id)
        area = self.world.areas.get(room.area_id) if room and room.area_id else None
        
        location = room.name if room else "Unknown"
        if area:
            location = f"{room.name} ({area.name})"
        
        status = "online" if target.is_connected else "offline (stasis)"
        
        return [self._msg_to_player(player_id, f"📍 {target.name}: {location} [{status}]")]

    def _goto_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[GM] Teleport to a room or player."""
        if not self._check_permission(player_id, "TELEPORT"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Go to where? Usage: goto <room_id|player_name>")]
        
        target = args.strip()
        player = self.world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form.")]
        
        # First check if it's a room ID
        if target in self.world.rooms:
            target_room = self.world.rooms[target]
        else:
            # Try to find a player with that name
            target_player = None
            for p in self.world.players.values():
                if p.name.lower() == target.lower() or p.name.lower().startswith(target.lower()):
                    target_player = p
                    break
            
            if target_player:
                target_room = self.world.rooms.get(target_player.room_id)
                if not target_room:
                    return [self._msg_to_player(player_id, f"Could not find {target_player.name}'s location.")]
            else:
                return [self._msg_to_player(player_id, f"Room or player '{target}' not found.")]
        
        # Move player
        old_room = self.world.rooms.get(player.room_id)
        if old_room:
            old_room.players.discard(player.id)
        
        player.room_id = target_room.id
        target_room.players.add(player.id)
        
        # Show room description
        room_desc = self._format_room_description(target_room, player_id)
        return [self._msg_to_player(player_id, f"You teleport to {target_room.name}.\n\n{room_desc}")]

    def _summon_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[GM] Summon a player to your location."""
        if not self._check_permission(player_id, "TELEPORT"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Summon whom? Usage: summon <player_name>")]
        
        player = self.world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form.")]
        
        target_name = args.strip().lower()
        target = None
        for p in self.world.players.values():
            if p.id != player_id and (p.name.lower() == target_name or p.name.lower().startswith(target_name)):
                target = p
                break
        
        if not target:
            return [self._msg_to_player(player_id, f"Player '{args.strip()}' not found.")]
        
        target_room = self.world.rooms.get(player.room_id)
        if not target_room:
            return [self._msg_to_player(player_id, "You are not in a valid room.")]
        
        # Move target player
        old_room = self.world.rooms.get(target.room_id)
        if old_room:
            old_room.players.discard(target.id)
        
        target.room_id = target_room.id
        target_room.players.add(target.id)
        
        events = [self._msg_to_player(player_id, f"You summon {target.name} to your location.")]
        
        # Notify the summoned player
        if target.id in self._listeners:
            room_desc = self._format_room_description(target_room, target.id)
            events.append({
                "type": "message",
                "scope": "player",
                "player_id": target.id,
                "text": f"You have been summoned by {player.name}.\n\n{room_desc}"
            })
        
        return events

    def _spawn_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[GM] Spawn an NPC or item in the current room."""
        if not self._check_permission(player_id, "SPAWN_NPC"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Spawn what? Usage: spawn npc|item <template_id>")]
        
        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            return [self._msg_to_player(player_id, "Usage: spawn npc|item <template_id>")]
        
        spawn_type = parts[0].lower()
        template_id = parts[1].strip()
        
        player = self.world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form.")]
        
        if spawn_type == "npc":
            template = self.world.npc_templates.get(template_id)
            if not template:
                return [self._msg_to_player(player_id, f"NPC template '{template_id}' not found.")]
            
            # Use async spawn
            import asyncio
            async def do_spawn():
                npc = await self._spawn_npc(template, player.room_id)
                return npc
            
            # Schedule the spawn (can't await directly in sync handler)
            # For now, just create the NPC synchronously
            import uuid
            npc_id = str(uuid.uuid4())
            from .world import WorldNpc
            npc = WorldNpc(
                id=npc_id,
                template_id=template.id,
                name=template.name,
                room_id=player.room_id,
                spawn_room_id=player.room_id,
                max_health=template.max_health,
                current_health=template.max_health,
                level=template.level,
                keywords=template.keywords.copy() if template.keywords else [],
                behaviors=template.behaviors.copy() if template.behaviors else []
            )
            self.world.npcs[npc_id] = npc
            
            return [self._msg_to_player(player_id, f"Spawned {template.name} ({npc_id[:8]}...)")]
        
        elif spawn_type == "item":
            template = self.world.item_templates.get(template_id)
            if not template:
                return [self._msg_to_player(player_id, f"Item template '{template_id}' not found.")]
            
            import uuid
            from .world import WorldItem
            item_id = str(uuid.uuid4())
            item = WorldItem(
                id=item_id,
                template_id=template.id,
                name=template.name,
                description=template.description,
                room_id=player.room_id,
                player_id=None,
                container_id=None,
                quantity=1,
                keywords=template.keywords.copy() if template.keywords else []
            )
            self.world.items[item_id] = item
            
            return [self._msg_to_player(player_id, f"Spawned {template.name} on the ground.")]
        
        else:
            return [self._msg_to_player(player_id, "Usage: spawn npc|item <template_id>")]

    def _despawn_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[GM] Despawn an NPC in the current room."""
        if not self._check_permission(player_id, "SPAWN_NPC"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Despawn whom? Usage: despawn <npc_name>")]
        
        player = self.world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form.")]
        
        target_name = args.strip().lower()
        npc_id = self._find_npc_in_room(player.room_id, target_name)
        
        if not npc_id:
            return [self._msg_to_player(player_id, f"No NPC named '{args.strip()}' in this room.")]
        
        npc = self.world.npcs.get(npc_id)
        npc_name = npc.name if npc else "Unknown"
        
        del self.world.npcs[npc_id]
        
        return [self._msg_to_player(player_id, f"{npc_name} vanishes in a puff of smoke.")]

    def _give_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[GM] Give an item to a player."""
        if not self._check_permission(player_id, "SPAWN_ITEM"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Give what to whom? Usage: give <player_name> <item_template>")]
        
        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            return [self._msg_to_player(player_id, "Usage: give <player_name> <item_template>")]
        
        target_name = parts[0].lower()
        template_id = parts[1].strip()
        
        # Find target player
        target = None
        for p in self.world.players.values():
            if p.name.lower() == target_name or p.name.lower().startswith(target_name):
                target = p
                break
        
        if not target:
            return [self._msg_to_player(player_id, f"Player '{parts[0]}' not found.")]
        
        # Find item template
        template = self.world.item_templates.get(template_id)
        if not template:
            return [self._msg_to_player(player_id, f"Item template '{template_id}' not found.")]
        
        # Create item in player's inventory
        import uuid
        from .world import WorldItem
        item_id = str(uuid.uuid4())
        item = WorldItem(
            id=item_id,
            template_id=template.id,
            name=template.name,
            description=template.description,
            room_id=None,
            player_id=target.id,
            container_id=None,
            quantity=1,
            keywords=template.keywords.copy() if template.keywords else []
        )
        self.world.items[item_id] = item
        
        events = [self._msg_to_player(player_id, f"Gave {template.name} to {target.name}.")]
        
        # Notify recipient
        if target.id in self._listeners:
            events.append({
                "type": "message",
                "scope": "player",
                "player_id": target.id,
                "text": f"You received {template.name} from a mysterious force."
            })
        
        return events

    def _inspect_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[GM] Get detailed info on a target (player, NPC, or item)."""
        if not self._check_permission(player_id, "MODIFY_STATS"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Inspect what? Usage: inspect <target_name>")]
        
        target_name = args.strip().lower()
        player = self.world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form.")]
        
        # Try to find a player
        for p in self.world.players.values():
            if p.name.lower() == target_name or p.name.lower().startswith(target_name):
                lines = [f"📋 Player: {p.name}"]
                lines.append("-" * 40)
                lines.append(f"  ID: {p.id}")
                lines.append(f"  Level: {p.level} ({p.experience} XP)")
                lines.append(f"  Class: {p.character_class}")
                lines.append(f"  Health: {p.current_health}/{p.max_health}")
                lines.append(f"  Energy: {p.current_energy}/{p.max_energy}")
                lines.append(f"  Room: {p.room_id}")
                lines.append(f"  Connected: {p.is_connected}")
                lines.append(f"  Stats: STR {p.strength}, DEX {p.dexterity}, INT {p.intelligence}, VIT {p.vitality}")
                lines.append(f"  Active Effects: {len(p.active_effects)}")
                return [self._msg_to_player(player_id, "\n".join(lines))]
        
        # Try to find an NPC in room
        npc_id = self._find_npc_in_room(player.room_id, target_name)
        if npc_id:
            npc = self.world.npcs.get(npc_id)
            if npc:
                lines = [f"📋 NPC: {npc.name}"]
                lines.append("-" * 40)
                lines.append(f"  ID: {npc.id}")
                lines.append(f"  Template: {npc.template_id}")
                lines.append(f"  Level: {npc.level}")
                lines.append(f"  Health: {npc.current_health}/{npc.max_health}")
                lines.append(f"  Room: {npc.room_id}")
                lines.append(f"  Spawn Room: {npc.spawn_room_id}")
                lines.append(f"  Behaviors: {', '.join(npc.behaviors) if npc.behaviors else 'None'}")
                return [self._msg_to_player(player_id, "\n".join(lines))]
        
        # Try to find an item in room or inventory
        for item in self.world.items.values():
            if item.room_id == player.room_id or item.player_id == player_id:
                if item.name.lower() == target_name or item.name.lower().startswith(target_name):
                    lines = [f"📋 Item: {item.name}"]
                    lines.append("-" * 40)
                    lines.append(f"  ID: {item.id}")
                    lines.append(f"  Template: {item.template_id}")
                    lines.append(f"  Quantity: {item.quantity}")
                    lines.append(f"  Room: {item.room_id or 'N/A'}")
                    lines.append(f"  Owner: {item.player_id or 'N/A'}")
                    lines.append(f"  Container: {item.container_id or 'N/A'}")
                    return [self._msg_to_player(player_id, "\n".join(lines))]
        
        return [self._msg_to_player(player_id, f"Could not find '{args.strip()}' to inspect.")]

    def _broadcast_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[Admin] Broadcast a message to all connected players."""
        if not self._check_permission(player_id, "SERVER_COMMANDS"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Broadcast what? Usage: broadcast <message>")]
        
        player = self.world.players.get(player_id)
        sender_name = player.name if player else "SYSTEM"
        
        message = f"📢 [{sender_name}]: {args.strip()}"
        
        events = []
        for p in self.world.players.values():
            if p.is_connected and p.id in self._listeners:
                events.append({
                    "type": "message",
                    "scope": "player",
                    "player_id": p.id,
                    "text": message
                })
        
        events.append(self._msg_to_player(player_id, f"Broadcast sent to {len(events)-1} player(s)."))
        return events

    def _kick_command_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[Mod] Kick a player from the game."""
        if not self._check_permission(player_id, "KICK_PLAYER"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Kick whom? Usage: kick <player_name> [reason]")]
        
        parts = args.strip().split(maxsplit=1)
        target_name = parts[0].lower()
        reason = parts[1] if len(parts) > 1 else "Kicked by administrator"
        
        # Find target player
        target = None
        for p in self.world.players.values():
            if p.name.lower() == target_name or p.name.lower().startswith(target_name):
                target = p
                break
        
        if not target:
            return [self._msg_to_player(player_id, f"Player '{parts[0]}' not found.")]
        
        if target.id == player_id:
            return [self._msg_to_player(player_id, "You cannot kick yourself.")]
        
        if not target.is_connected:
            return [self._msg_to_player(player_id, f"{target.name} is not connected.")]
        
        # Kick the player
        target.is_connected = False
        
        events = [self._msg_to_player(player_id, f"Kicked {target.name}: {reason}")]
        
        # Notify the kicked player
        if target.id in self._listeners:
            events.append({
                "type": "kicked",
                "scope": "player",
                "player_id": target.id,
                "text": f"You have been kicked: {reason}"
            })
        
        # Broadcast to room
        room = self.world.rooms.get(target.room_id)
        if room:
            for p_id in room.players:
                if p_id != target.id:
                    events.append(self._msg_to_player(p_id, f"{target.name} has been kicked from the game."))
        
        return events

    def _mute_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[Mod] Mute a player (prevent speaking)."""
        if not self._check_permission(player_id, "KICK_PLAYER"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Mute whom? Usage: mute <player_name>")]
        
        target_name = args.strip().lower()
        target = None
        for p in self.world.players.values():
            if p.name.lower() == target_name or p.name.lower().startswith(target_name):
                target = p
                break
        
        if not target:
            return [self._msg_to_player(player_id, f"Player '{args.strip()}' not found.")]
        
        # Set mute flag
        if not target.data:
            target.data = {}
        target.data['muted'] = True
        
        events = [self._msg_to_player(player_id, f"Muted {target.name}.")]
        
        if target.id in self._listeners:
            events.append(self._msg_to_player(target.id, "You have been muted and cannot speak."))
        
        return events

    def _unmute_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[Mod] Unmute a player."""
        if not self._check_permission(player_id, "KICK_PLAYER"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Unmute whom? Usage: unmute <player_name>")]
        
        target_name = args.strip().lower()
        target = None
        for p in self.world.players.values():
            if p.name.lower() == target_name or p.name.lower().startswith(target_name):
                target = p
                break
        
        if not target:
            return [self._msg_to_player(player_id, f"Player '{args.strip()}' not found.")]
        
        # Clear mute flag
        if target.data:
            target.data.pop('muted', None)
        
        events = [self._msg_to_player(player_id, f"Unmuted {target.name}.")]
        
        if target.id in self._listeners:
            events.append(self._msg_to_player(target.id, "You have been unmuted."))
        
        return events

    def _warn_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[Mod] Warn a player."""
        if not self._check_permission(player_id, "KICK_PLAYER"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Warn whom? Usage: warn <player_name> <reason>")]
        
        parts = args.strip().split(maxsplit=1)
        target_name = parts[0].lower()
        reason = parts[1] if len(parts) > 1 else "Behavior violation"
        
        target = None
        for p in self.world.players.values():
            if p.name.lower() == target_name or p.name.lower().startswith(target_name):
                target = p
                break
        
        if not target:
            return [self._msg_to_player(player_id, f"Player '{parts[0]}' not found.")]
        
        # Track warnings
        if not target.data:
            target.data = {}
        warn_count = target.data.get('warn_count', 0) + 1
        target.data['warn_count'] = warn_count
        
        events = [self._msg_to_player(player_id, f"Warned {target.name} ({warn_count} warning(s)): {reason}")]
        
        if target.id in self._listeners:
            events.append(self._msg_to_player(target.id, f"⚠️ WARNING from admin: {reason}"))
        
        return events

    def _revive_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[GM] Revive a dead player."""
        if not self._check_permission(player_id, "MODIFY_STATS"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Revive whom? Usage: revive <player_name>")]
        
        target_name = args.strip().lower()
        target = None
        for p in self.world.players.values():
            if p.name.lower() == target_name or p.name.lower().startswith(target_name):
                target = p
                break
        
        if not target:
            return [self._msg_to_player(player_id, f"Player '{args.strip()}' not found.")]
        
        if target.is_alive():
            return [self._msg_to_player(player_id, f"{target.name} is already alive.")]
        
        # Revive the player
        target.current_health = target.max_health
        target.current_energy = target.max_energy
        target.is_connected = True
        
        events = [self._msg_to_player(player_id, f"Revived {target.name}.")]
        
        if target.id in self._listeners:
            events.append(self._msg_to_player(target.id, "You have been revived by divine intervention!"))
            events.append({
                "type": "stat_update",
                "scope": "player",
                "player_id": target.id,
                "payload": {"health": target.max_health, "max_health": target.max_health}
            })
        
        # Notify room
        room = self.world.rooms.get(target.room_id)
        if room:
            for p_id in room.players:
                if p_id != target.id:
                    events.append(self._msg_to_player(p_id, f"✨ {target.name} has been revived!"))
        
        return events

    def _invis_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[Mod] Make a player invisible (admin mode)."""
        if not self._check_permission(player_id, "KICK_PLAYER"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        # If no args, apply to self
        target = None
        if args and args.strip():
            target_name = args.strip().lower()
            for p in self.world.players.values():
                if p.name.lower() == target_name or p.name.lower().startswith(target_name):
                    target = p
                    break
            if not target:
                return [self._msg_to_player(player_id, f"Player '{args.strip()}' not found.")]
        else:
            target = self.world.players.get(player_id)
        
        if not target:
            return [self._msg_to_player(player_id, "Invalid target.")]
        
        # Set invisibility flag
        if not target.data:
            target.data = {}
        target.data['invisible'] = True
        
        events = []
        if target.id == player_id:
            events.append(self._msg_to_player(player_id, "You fade from view."))
        else:
            events.append(self._msg_to_player(player_id, f"{target.name} has been made invisible."))
            if target.id in self._listeners:
                events.append(self._msg_to_player(target.id, "You have been made invisible."))
        
        return events

    def _visible_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[Mod] Make a player visible (remove invisibility)."""
        if not self._check_permission(player_id, "KICK_PLAYER"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        # If no args, apply to self
        target = None
        if args and args.strip():
            target_name = args.strip().lower()
            for p in self.world.players.values():
                if p.name.lower() == target_name or p.name.lower().startswith(target_name):
                    target = p
                    break
            if not target:
                return [self._msg_to_player(player_id, f"Player '{args.strip()}' not found.")]
        else:
            target = self.world.players.get(player_id)
        
        if not target:
            return [self._msg_to_player(player_id, "Invalid target.")]
        
        # Clear invisibility flag
        if target.data:
            target.data.pop('invisible', None)
        
        events = []
        if target.id == player_id:
            events.append(self._msg_to_player(player_id, "You become visible."))
        else:
            events.append(self._msg_to_player(player_id, f"{target.name} has been made visible."))
            if target.id in self._listeners:
                events.append(self._msg_to_player(target.id, "You have been made visible."))
        
        return events

    def _reload_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[Admin] Reload game content from YAML files."""
        if not self._check_permission(player_id, "SERVER_COMMANDS"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        content_type = args.strip().lower() if args and args.strip() else "all"
        
        # Valid content types
        valid_types = ["all", "abilities", "items", "npcs", "rooms", "areas", "classes"]
        
        if content_type not in valid_types:
            return [self._msg_to_player(player_id, f"Invalid content type. Valid: {', '.join(valid_types)}")]
        
        # Attempt to reload content
        try:
            if hasattr(self, 'content_reloader'):
                result = self.content_reloader.reload(content_type)
                events = [self._msg_to_player(player_id, f"Reloaded {content_type}: {result}")]
            else:
                events = [self._msg_to_player(player_id, "Content reload system not available.")]
        except Exception as e:
            events = [self._msg_to_player(player_id, f"Reload failed: {str(e)}")]
        
        return events

    def _ban_command_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[Admin] Ban a player account."""
        if not self._check_permission(player_id, "MANAGE_ACCOUNTS"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            return [self._msg_to_player(player_id, "Usage: ban <player_name> <reason>")]
        
        target_name = parts[0]
        ban_reason = parts[1]
        
        # Find target player
        target = self._find_player_by_name(target_name)
        if not target:
            return [self._msg_to_player(player_id, f"Player '{target_name}' not found.")]
        
        # Get admin player
        admin_player = self.world.players.get(player_id)
        if not admin_player:
            return [self._msg_to_player(player_id, "Admin player not found.")]
        
        # Ban the account
        target.is_connected = False
        
        # Mark account as banned in player.data (for in-game tracking)
        if not target.data:
            target.data = {}
        target.data['banned'] = True
        target.data['ban_reason'] = ban_reason
        target.data['banned_by'] = admin_player.name
        
        events = [
            self._msg_to_player(player_id, f"🚫 Banned {target.name} for: {ban_reason}"),
            self._msg_to_room(target.room_id, f"⚠️ {target.name} has been banned from the game.")
        ]
        
        # Notify target if still connected
        if target.id in self._listeners:
            events.append(self._msg_to_player(target.id, f"You have been banned: {ban_reason}"))
        
        return events

    def _unban_command_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[Admin] Unban a player account."""
        if not self._check_permission(player_id, "MANAGE_ACCOUNTS"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        target_name = args.strip()
        if not target_name:
            return [self._msg_to_player(player_id, "Usage: unban <player_name>")]
        
        # Find target player (by name in world)
        target = self._find_player_by_name(target_name)
        if not target:
            # Player not currently online, but we can still unban them by finding via database
            # For now, we'll just note that offline unbanning requires the REST API
            return [self._msg_to_player(player_id, f"Player '{target_name}' not found online. Use REST API for offline unbanning.")]
        
        # Unban the account
        if not target.data:
            target.data = {}
        
        old_reason = target.data.get('ban_reason', 'Unknown')
        target.data.pop('banned', None)
        target.data.pop('ban_reason', None)
        target.data.pop('banned_by', None)
        
        # Get admin player
        admin_player = self.world.players.get(player_id)
        if not admin_player:
            return [self._msg_to_player(player_id, "Admin player not found.")]
        
        events = [
            self._msg_to_player(player_id, f"✅ Unbanned {target.name} (was banned for: {old_reason})"),
            self._msg_to_room(target.room_id, f"✅ {target.name} has been unbanned.")
        ]
        
        if target.id in self._listeners:
            events.append(self._msg_to_player(target.id, "You have been unbanned!"))
        
        return events

    def _setstat_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """[GM] Set a player's stat to a specific value."""
        if not self._check_permission(player_id, "MODIFY_STATS"):
            return [self._msg_to_player(player_id, "You don't have permission to use this command.")]
        
        parts = args.strip().split()
        if len(parts) < 3:
            return [self._msg_to_player(player_id, "Usage: setstat <player_name> <stat> <value>")]
        
        target_name = parts[0]
        stat_name = parts[1].lower()
        
        try:
            stat_value = int(parts[2])
        except ValueError:
            return [self._msg_to_player(player_id, "Value must be a number.")]
        
        # Find target player
        target = self._find_player_by_name(target_name)
        if not target:
            return [self._msg_to_player(player_id, f"Player '{target_name}' not found.")]
        
        # Valid stats that can be modified
        valid_stats = {
            "hp": "current_health",
            "health": "current_health",
            "max_hp": "max_health",
            "max_health": "max_health",
            "mana": "current_energy",
            "energy": "current_energy",
            "max_mana": "max_energy",
            "max_energy": "max_energy",
            "level": "level",
            "armor": "armor_class",
            "armor_class": "armor_class",
            "strength": "strength",
            "str": "strength",
            "dexterity": "dexterity",
            "dex": "dexterity",
            "intelligence": "intelligence",
            "int": "intelligence",
            "vitality": "vitality",
            "vit": "vitality",
            "experience": "experience",
            "xp": "experience",
        }
        
        if stat_name not in valid_stats:
            valid_names = ", ".join(sorted(set(valid_stats.keys())))
            return [self._msg_to_player(player_id, f"Unknown stat: {stat_name}. Valid: {valid_names}")]
        
        attr_name = valid_stats[stat_name]
        
        # Validate value ranges for certain stats
        if "max_" in attr_name and stat_value < 1:
            return [self._msg_to_player(player_id, f"{stat_name} must be at least 1.")]
        
        if "current_" in attr_name or attr_name == "armor_class":
            max_attr = attr_name.replace("current_", "max_")
            max_value = getattr(target, max_attr, 100)
            if stat_value < 0:
                stat_value = 0
            elif stat_value > max_value:
                stat_value = max_value
                return [self._msg_to_player(player_id, f"Capped {stat_name} at {max_value}.")]
        
        # Set the stat
        old_value = getattr(target, attr_name)
        setattr(target, attr_name, stat_value)
        
        # Format stat name for display
        display_stat = stat_name.replace("_", " ").title()
        
        events = [
            self._msg_to_player(player_id, f"✓ Set {target.name}'s {display_stat} from {old_value} to {stat_value}"),
        ]
        
        # Notify target if online
        if target.id in self._listeners:
            events.append(self._msg_to_player(target.id, f"[Admin] Your {display_stat} has been set to {stat_value}."))
        
        return events

    def _quit_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Handle quit command - sends disconnect signal to client."""
        player = self.world.players.get(player_id)
        player_name = player.name if player else "Unknown"
        
        # Send farewell message and special quit event
        return [
            self._msg_to_player(player_id, "\nYou feel the world fade away as you enter a state of stasis...\nFarewell, brave adventurer. May your return be swift.\n"),
            {
                "type": "quit",
                "scope": "player",
                "player_id": player_id,
                "text": "Disconnecting..."
            }
        ]

    # ---------- Quest command handlers (Phase X) ----------

    def _journal_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Show the player's quest journal."""
        return self.quest_system.get_quest_log(player_id)

    def _quest_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Show details of a specific quest."""
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Which quest? Usage: quest <quest_name>")]
        return self.quest_system.get_quest_details(player_id, args.strip())

    def _abandon_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Abandon a quest."""
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Abandon which quest? Usage: abandon <quest_name>")]
        return self.quest_system.abandon_quest(player_id, args.strip())

    def _talk_handler(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """Talk to an NPC to start dialogue."""
        if not args or not args.strip():
            return [self._msg_to_player(player_id, "Talk to whom? Usage: talk <npc_name>")]
        
        player = self.world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form.")]
        
        # Find NPC in room
        npc_id = self._find_npc_in_room(player.room_id, args.strip())
        if not npc_id:
            return [self._msg_to_player(player_id, f"You don't see '{args.strip()}' here.")]
        
        npc = self.world.npcs.get(npc_id)
        if not npc:
            return [self._msg_to_player(player_id, "That NPC seems to have vanished.")]
        
        # Start dialogue
        return self.quest_system.start_dialogue(player_id, npc_id, npc.template_id)

    # ---------- Permission checking (Phase 7) ----------

    def _check_permission(self, player_id: PlayerId, permission_name: str) -> bool:
        """
        Check if a player has a specific permission.
        
        Checks against the auth_info stored in the context (set during WebSocket handling)
        or falls back to checking the player's linked account.
        
        Args:
            player_id: The player to check permissions for
            permission_name: Name of the permission (e.g., "MODIFY_STATS")
            
        Returns:
            True if the player has the permission, False otherwise
        """
        # Import here to avoid circular imports
        from .systems.auth import Permission, ROLE_PERMISSIONS, UserRole
        
        # First check if we have auth_info in context (from authenticated WebSocket)
        if hasattr(self.ctx, 'auth_info') and self.ctx.auth_info:
            role_str = self.ctx.auth_info.get('role', 'player')
            try:
                user_role = UserRole(role_str)
            except ValueError:
                user_role = UserRole.PLAYER
            
            # Check if the role has the permission
            try:
                perm = Permission(permission_name.lower())
            except ValueError:
                # Try with the exact name
                perm_map = {p.name.upper(): p for p in Permission}
                perm = perm_map.get(permission_name.upper())
                if not perm:
                    return False
            
            role_perms = ROLE_PERMISSIONS.get(user_role, set())
            return perm in role_perms
        
        # For legacy connections without auth, deny admin commands
        # (Or you could allow for testing by returning True here)
        return False

    # ---------- Time event system (delegates to TimeEventManager) ----------

    async def start_time_system(self) -> None:
        """
        Start the time event processing loop.
        Should be called once during engine startup.
        """
        await self.time_manager.start()
        
        # Schedule world time advancement (every 30 seconds = 1 game hour)
        self._schedule_time_advancement()
        
        # Schedule NPC housekeeping tick (respawns, etc.) - every 30 seconds
        self._schedule_npc_housekeeping_tick()
        
        # Schedule passive regeneration tick for players
        self._schedule_regeneration_tick()
        
        # Initialize per-NPC behavior timers
        self._init_npc_behaviors()
        
        # Initialize room and area trigger timers
        self.trigger_system.initialize_all_timers()
        
        # Phase 6: Start periodic state saves
        if self.state_tracker:
            self.state_tracker.schedule_periodic_save()
        
        # Phase 10.1: Schedule periodic cleanup of stale groups
        self._schedule_stale_group_cleanup()
    
    def _schedule_stale_group_cleanup(self) -> None:
        """Schedule recurring cleanup of stale groups (inactive 30+ minutes)."""
        async def cleanup_stale_groups():
            """Callback to clean up stale groups and reschedule."""
            disbanded = self.group_system.clean_stale_groups()
            if disbanded:
                logger.info(f"Disbanded {len(disbanded)} stale groups")
            # Reschedule for next cleanup
            self._schedule_stale_group_cleanup()
        
        # Schedule cleanup every 5 minutes
        interval = 5 * 60
        self.schedule_event(
            delay_seconds=interval,
            callback=cleanup_stale_groups,
            event_id="stale_group_cleanup"
        )
    
    def _schedule_time_advancement(self) -> None:
        """
        Schedule recurring time advancement event.
        Advances time in each area independently based on area-specific time_scale.
        """
        from .world import game_hours_to_real_seconds
        
        async def advance_world_time():
            """Callback to advance time in all areas and reschedule."""
            # Track if time period changed for any area (for lighting recalculation)
            time_periods_before = {}
            for area in self.world.areas.values():
                time_periods_before[area.id] = area.area_time.get_time_of_day(area.time_scale)
            
            # Advance each area's time independently
            for area in self.world.areas.values():
                area.area_time.advance(
                    real_seconds_elapsed=30.0,  # 30 seconds have elapsed
                    time_scale=area.time_scale  # Use area-specific time scale
                )
                
                time_str = area.area_time.format_full(area.time_scale)
                scale_note = f" (scale: {area.time_scale:.1f}x)" if area.time_scale != 1.0 else ""
                print(f"[WorldTime] {area.name}: {time_str}{scale_note}")
            
            # Also advance global world time (for areas without specific areas)
            self.world.world_time.advance(
                real_seconds_elapsed=30.0,
                time_scale=1.0  # Global time runs at normal speed
            )
            
            # Phase 11: Check if time period changed for any area
            time_period_changed = False
            for area in self.world.areas.values():
                new_period = area.area_time.get_time_of_day(area.time_scale)
                old_period = time_periods_before.get(area.id)
                if old_period and new_period != old_period:
                    time_period_changed = True
                    print(f"[Lighting] Time period changed in {area.name}: {old_period} → {new_period}")
            
            # If time period changed, recalculate all room lighting
            if time_period_changed:
                self.lighting_system.recalculate_all_rooms()
            
            # Reschedule for next hour
            self._schedule_time_advancement()
        
        # Schedule 30 seconds from now
        interval = game_hours_to_real_seconds(1.0)  # 30 seconds
        self.schedule_event(
            delay_seconds=interval,
            callback=advance_world_time,
            event_id="world_time_tick"
        )
    
    def _schedule_npc_housekeeping_tick(self) -> None:
        """
        Schedule recurring NPC housekeeping tick (every 30 seconds).
        Handles: respawn checks, cleanup, area-wide NPC events.
        Individual NPC behaviors (idle, wander) use per-NPC timers.
        """
        async def npc_housekeeping_tick():
            """Process housekeeping for all NPCs."""
            current_time = time.time()
            
            # Check for NPC respawns
            for npc_id, npc in list(self.world.npcs.items()):
                if npc.is_alive():
                    continue
                
                # Resolve respawn time: NPC override > area default > 300s fallback
                respawn_time = self._get_npc_respawn_time(npc)
                
                # -1 means never respawn
                if respawn_time < 0:
                    continue
                
                # Check if respawn time has elapsed
                if npc.last_killed_at and current_time - npc.last_killed_at >= respawn_time:
                    # Respawn the NPC
                    template = self.world.npc_templates.get(npc.template_id)
                    if template:
                        npc.current_health = template.max_health
                        npc.last_killed_at = None
                        npc.room_id = npc.spawn_room_id
                        npc.target_id = None
                        
                        # Add back to room
                        spawn_room = self.world.rooms.get(npc.spawn_room_id)
                        if spawn_room:
                            spawn_room.entities.add(npc_id)
                            
                            # Announce respawn
                            npc_name = npc.instance_data.get("name_override", npc.name)
                            await self._dispatch_events([
                                self._msg_to_room(
                                    spawn_room.id,
                                    f"{npc_name} appears.",
                                )
                            ])
                            
                            # Start behavior timers for respawned NPC
                            self._schedule_npc_idle(npc_id)
                            self._schedule_npc_wander(npc_id)
            
            # Reschedule housekeeping
            self._schedule_npc_housekeeping_tick()
        
        # Housekeeping every 30 seconds
        self.schedule_event(
            delay_seconds=30.0,
            callback=npc_housekeeping_tick,
            event_id="npc_housekeeping_tick"
        )
    
    def _schedule_regeneration_tick(self) -> None:
        """
        Schedule recurring regeneration tick for all online players and NPCs.
        Handles passive HP and resource regeneration based on player state (awake/sleeping).
        NPCs always use the awake regeneration rate.
        """
        async def regeneration_tick():
            """Process HP and resource regeneration for all online players and living NPCs."""
            from .systems import d20
            import time
            
            current_time = time.time()
            events = []
            
            # Process player regeneration
            for player_id, player in list(self.world.players.items()):
                if not player.is_connected or not player.is_alive():
                    continue
                
                # Calculate time since last regen tick
                time_delta = current_time - player.last_regen_tick
                player.last_regen_tick = current_time
                
                # Determine regen rates based on sleeping state
                if player.is_sleeping:
                    hp_regen_rate = d20.HEALTH_REGEN_SLEEPING
                    resource_regen_rate = d20.RESOURCE_REGEN_SLEEPING
                else:
                    hp_regen_rate = d20.HEALTH_REGEN_AWAKE
                    resource_regen_rate = d20.RESOURCE_REGEN_AWAKE
                
                # Regenerate HP
                if player.current_health < player.max_health:
                    hp_gained = int(hp_regen_rate * time_delta)
                    if hp_gained > 0:
                        old_hp = player.current_health
                        player.current_health = min(player.max_health, player.current_health + hp_gained)
                        
                        # Send stat update to player
                        events.append({
                            "type": "stat_update",
                            "scope": "player",
                            "player_id": player_id,
                            "payload": {
                                "health": player.current_health,
                                "max_health": player.max_health,
                            }
                        })
                
                # Regenerate resources
                if player.character_sheet:
                    resources_updated = {}
                    for resource_id, pool in player.character_sheet.resource_pools.items():
                        if pool.current < pool.max:
                            resource_gained = int(pool.max * resource_regen_rate * time_delta)
                            if resource_gained > 0:
                                pool.current = min(pool.max, pool.current + resource_gained)
                                resources_updated[resource_id] = {
                                    "current": pool.current,
                                    "max": pool.max,
                                    "percent": (pool.current / pool.max * 100) if pool.max > 0 else 0
                                }
                    
                    # Send resource update if any resources changed
                    if resources_updated:
                        events.append({
                            "type": "resource_update",
                            "scope": "player",
                            "player_id": player_id,
                            "payload": resources_updated
                        })
            
            # Process NPC regeneration (always use awake rate)
            for npc_id, npc in list(self.world.npcs.items()):
                if not npc.is_alive():
                    continue
                
                # Initialize last_regen_tick if not set (for existing NPCs)
                if not hasattr(npc, 'last_regen_tick'):
                    npc.last_regen_tick = current_time
                
                # Calculate time since last regen tick
                time_delta = current_time - npc.last_regen_tick
                npc.last_regen_tick = current_time
                
                # Regenerate HP using awake rate
                if npc.current_health < npc.max_health:
                    hp_gained = int(d20.HEALTH_REGEN_AWAKE * time_delta)
                    if hp_gained > 0:
                        npc.current_health = min(npc.max_health, npc.current_health + hp_gained)
                        # NPCs don't get UI updates, regeneration happens silently
            
            # Dispatch all regen events
            if events:
                await self._dispatch_events(events)
            
            # Reschedule next regen tick
            self._schedule_regeneration_tick()
        
        # Regen tick every few seconds (defined in d20 module)
        from .systems import d20
        self.schedule_event(
            delay_seconds=d20.REGEN_TICK_INTERVAL,
            callback=regeneration_tick,
            event_id="regeneration_tick"
        )
    
    def _get_npc_respawn_time(self, npc: WorldNpc) -> int:
        """
        Resolve the respawn time for an NPC.
        
        Resolution order:
        1. NPC respawn_time_override (if set)
        2. Area default_respawn_time (if NPC's spawn room is in an area)
        3. Hardcoded fallback of 300 seconds
        
        Returns:
            Respawn time in seconds. -1 means never respawn.
        """
        # If NPC has an override, use it
        if npc.respawn_time_override is not None:
            return npc.respawn_time_override
        
        # Try to get the area for this NPC's spawn room
        spawn_room = self.world.rooms.get(npc.spawn_room_id)
        if spawn_room and spawn_room.area_id:
            area = self.world.areas.get(spawn_room.area_id)
            if area:
                return area.default_respawn_time
        
        # Fallback to hardcoded default
        return 300
    
    def _init_npc_behaviors(self) -> None:
        """
        Initialize per-NPC behavior timers for all living NPCs.
        Called once on engine startup after world is loaded.
        """
        for npc_id, npc in self.world.npcs.items():
            if npc.is_alive():
                self._schedule_npc_idle(npc_id)
                self._schedule_npc_wander(npc_id)
    
    def _schedule_npc_idle(self, npc_id: str) -> None:
        """
        Schedule the next idle behavior check for a specific NPC.
        Uses behavior scripts to determine idle messages.
        """
        import random
        
        npc = self.world.npcs.get(npc_id)
        if not npc or not npc.is_alive():
            return
        
        template = self.world.npc_templates.get(npc.template_id)
        if not template:
            return
        
        # Get idle timing from resolved behavior config
        config = template.resolved_behavior
        if not config.get("idle_enabled", True):
            return
        
        async def npc_idle_callback():
            """Run idle behavior hooks, then reschedule."""
            npc = self.world.npcs.get(npc_id)
            if not npc or not npc.is_alive():
                return
            
            # Run the on_idle_tick hook for all behaviors
            await self._run_behavior_hook(npc_id, "on_idle_tick")
            
            # Reschedule next idle check
            self._schedule_npc_idle(npc_id)
        
        # Cancel any existing idle timer for this NPC
        if npc.idle_event_id:
            self.cancel_event(npc.idle_event_id)
        
        # Get timing from config (with defaults)
        min_delay = config.get("idle_interval_min", 15.0)
        max_delay = config.get("idle_interval_max", 45.0)
        delay = random.uniform(min_delay, max_delay)
        
        event_id = f"npc_idle_{npc_id}_{time.time()}"
        npc.idle_event_id = event_id
        
        self.schedule_event(
            delay_seconds=delay,
            callback=npc_idle_callback,
            event_id=event_id
        )
    
    def _schedule_npc_wander(self, npc_id: str) -> None:
        """
        Schedule the next wander behavior check for a specific NPC.
        Uses behavior scripts to determine movement.
        """
        import random
        
        npc = self.world.npcs.get(npc_id)
        if not npc or not npc.is_alive():
            return
        
        template = self.world.npc_templates.get(npc.template_id)
        if not template:
            return
        
        # Get wander timing from resolved behavior config
        config = template.resolved_behavior
        wander_enabled = config.get("wander_enabled", False)
        
        if not wander_enabled:
            print(f"[NPC] {npc.name} wander NOT enabled (config={config})")
            return
        
        print(f"[NPC] Scheduling wander for {npc.name} (behaviors={template.behaviors})")
        
        async def npc_wander_callback():
            """Run wander behavior hooks, then reschedule."""
            npc = self.world.npcs.get(npc_id)
            if not npc or not npc.is_alive():
                return
            
            # Run the on_wander_tick hook for all behaviors
            result = await self._run_behavior_hook(npc_id, "on_wander_tick")
            if result and result.handled:
                print(f"[NPC] {npc.name} wander tick handled: move_to={result.move_to}")
            
            # Reschedule next wander check
            self._schedule_npc_wander(npc_id)
        
        # Cancel any existing wander timer for this NPC
        if npc.wander_event_id:
            self.cancel_event(npc.wander_event_id)
        
        # Get timing from config (with defaults)
        min_delay = config.get("wander_interval_min", 30.0)
        max_delay = config.get("wander_interval_max", 90.0)
        delay = random.uniform(min_delay, max_delay)
        
        event_id = f"npc_wander_{npc_id}_{time.time()}"
        npc.wander_event_id = event_id
        
        self.schedule_event(
            delay_seconds=delay,
            callback=npc_wander_callback,
            event_id=event_id
        )
    
    def _cancel_npc_timers(self, npc_id: str) -> None:
        """
        Cancel all behavior timers for an NPC (called on death/despawn).
        """
        npc = self.world.npcs.get(npc_id)
        if not npc:
            return
        
        if npc.idle_event_id:
            self.cancel_event(npc.idle_event_id)
            npc.idle_event_id = None
        
        if npc.wander_event_id:
            self.cancel_event(npc.wander_event_id)
            npc.wander_event_id = None

    # ---------- Player Respawn System ----------

    def schedule_player_respawn(
        self, 
        player_id: PlayerId, 
        countdown_seconds: int = 10
    ) -> None:
        """
        Schedule a player respawn with countdown.
        
        Sends respawn_countdown events to the player every second,
        then respawns them at their area's entry point.
        
        Args:
            player_id: The player who died
            countdown_seconds: Seconds before respawn (default 10)
        """
        import random
        
        player = self.world.players.get(player_id)
        if not player:
            return
        
        # Record death time
        player.death_time = time.time()
        
        # Get respawn location (area entry point)
        area = self._get_player_area(player)
        if not area or not area.entry_points:
            print(f"[Respawn] No entry points for player {player.name}, using current room")
            respawn_room_id = player.room_id
        else:
            # Pick random entry point
            respawn_room_id = random.choice(list(area.entry_points))
        
        respawn_room = self.world.rooms.get(respawn_room_id)
        area_name = area.name if area else "Unknown"
        
        # Schedule countdown events
        for i in range(countdown_seconds, 0, -1):
            delay = countdown_seconds - i
            event_id = f"respawn_countdown_{player_id}_{i}"
            
            # Create closure with captured value
            seconds_remaining = i
            async def send_countdown(secs=seconds_remaining, area=area_name):
                # Different messages based on countdown progress
                if secs == 10:
                    msg = f"💀 Your flesh failed you, but your spirit is not yet defeated... ({secs}s)"
                elif secs >= 7:
                    msg = f"Darkness surrounds you... ({secs}s)"
                elif secs >= 4:
                    msg = f"A distant light calls to you... ({secs}s)"
                elif secs >= 2:
                    msg = f"You feel yourself being pulled back... ({secs}s)"
                else:
                    msg = f"Reality snaps back into focus... ({secs}s)"
                
                await self._dispatch_events([
                    {
                        "type": "message",
                        "scope": "player",
                        "player_id": player_id,
                        "text": msg
                    },
                    {
                        "type": "respawn_countdown",
                        "scope": "player",
                        "player_id": player_id,
                        "payload": {
                            "seconds_remaining": secs,
                            "respawn_location": area
                        }
                    }
                ])
            
            self.schedule_event(
                delay_seconds=delay,
                callback=send_countdown,
                event_id=event_id
            )
        
        # Schedule the actual respawn
        respawn_event_id = f"respawn_{player_id}_{time.time()}"
        player.respawn_event_id = respawn_event_id
        
        async def do_respawn():
            await self._execute_player_respawn(player_id, respawn_room_id)
        
        self.schedule_event(
            delay_seconds=countdown_seconds,
            callback=do_respawn,
            event_id=respawn_event_id
        )
        
        print(f"[Respawn] Scheduled respawn for {player.name} in {countdown_seconds}s at {respawn_room_id}")

    async def _execute_player_respawn(
        self, 
        player_id: PlayerId, 
        respawn_room_id: RoomId
    ) -> None:
        """
        Execute the actual player respawn.
        
        - Restores health
        - Clears combat state
        - Moves to respawn room
        - Sends confirmation message
        """
        player = self.world.players.get(player_id)
        if not player:
            return
        
        old_room_id = player.room_id
        old_room = self.world.rooms.get(old_room_id)
        new_room = self.world.rooms.get(respawn_room_id)
        
        if not new_room:
            print(f"[Respawn] ERROR: Respawn room {respawn_room_id} not found")
            return
        
        # Restore player state
        player.current_health = player.max_health
        player.death_time = None
        player.respawn_event_id = None
        
        # Clear combat state using the proper method
        player.combat.clear_combat()
        
        print(f"[Respawn DEBUG] Executing respawn for {player.name}")
        
        # Move player to respawn room
        if old_room:
            old_room.entities.discard(player_id)
        new_room.entities.add(player_id)
        player.room_id = respawn_room_id
        
        # Send respawn confirmation and look at new room
        events: List[Event] = []
        
        resurrection_msg = {
            "type": "message",
            "scope": "player",
            "player_id": player_id,
            "text": "**Sensation floods into you.** Every nerve prickles with fresh sensitivity as your spirit and your body are restored."
        }
        events.append(resurrection_msg)
        print(f"[Respawn DEBUG] Queued resurrection message for {player_id}")
        
        # Show the new room
        look_events = self._look(player_id)
        events.extend(look_events)
        
        # Update player stats
        events.append({
            "type": "stat_update",
            "scope": "player",
            "player_id": player_id,
            "payload": {
                "health": player.current_health,
                "max_health": player.max_health,
            }
        })
        
        # Announce arrival to other players in the room
        if old_room_id != respawn_room_id:
            # Player moved to a different room
            events.append({
                "type": "message",
                "scope": "room",
                "room_id": respawn_room_id,
                "exclude": [player_id],
                "text": f"{player.name} materializes in a shimmer of light."
            })
        else:
            # Player respawned in the same room they died in
            events.append({
                "type": "message",
                "scope": "room",
                "room_id": respawn_room_id,
                "exclude": [player_id],
                "text": f"{player.name}'s body glows with ethereal light as life returns to them."
            })
        
        await self._dispatch_events(events)
        print(f"[Respawn DEBUG] Dispatched {len(events)} events for {player.name}")
        print(f"[Respawn] {player.name} respawned at {respawn_room_id}")

    def _get_player_area(self, player: WorldPlayer) -> WorldArea | None:
        """Get the area a player is currently in."""
        room = self.world.rooms.get(player.room_id)
        if not room:
            return None
        return self.world.areas.get(room.area_id)

    def cancel_player_respawn(self, player_id: PlayerId) -> None:
        """
        Cancel a scheduled player respawn (e.g., if they disconnect).
        """
        player = self.world.players.get(player_id)
        if not player:
            return
        
        if player.respawn_event_id:
            self.cancel_event(player.respawn_event_id)
            player.respawn_event_id = None
        
        # Also cancel any countdown events
        for i in range(10, 0, -1):
            event_id = f"respawn_countdown_{player_id}_{i}"
            self.cancel_event(event_id)
    
    def _get_npc_behavior_context(self, npc_id: str) -> BehaviorContext | None:
        """
        Create a BehaviorContext for the given NPC.
        Returns None if NPC doesn't exist or is dead.
        """
        npc = self.world.npcs.get(npc_id)
        if not npc or not npc.is_alive():
            return None
        
        template = self.world.npc_templates.get(npc.template_id)
        if not template:
            return None
        
        return BehaviorContext(
            npc=npc,
            world=self.world,
            template=template,
            config=template.resolved_behavior,
            broadcast=lambda room_id, msg: None  # We handle messages via BehaviorResult
        )
    
    async def _run_behavior_hook(
        self, 
        npc_id: str, 
        hook_name: str, 
        *args, 
        **kwargs
    ) -> BehaviorResult | None:
        """
        Run a specific behavior hook for an NPC.
        
        Executes all behaviors in priority order. Stops if a behavior returns
        handled=True (for most hooks).
        
        Returns the first result with handled=True, or the last result.
        """
        npc = self.world.npcs.get(npc_id)
        if not npc or not npc.is_alive():
            return None
        
        template = self.world.npc_templates.get(npc.template_id)
        if not template:
            return None
        
        ctx = self._get_npc_behavior_context(npc_id)
        if not ctx:
            return None
        
        # Get behavior instances for this NPC
        behaviors = get_behavior_instances(template.behaviors)
        print(f"[Behavior] Running {hook_name} for {npc.name} with {len(behaviors)} behaviors: {[b.name for b in behaviors]}")
        
        last_result: BehaviorResult | None = None
        for behavior in behaviors:
            hook = getattr(behavior, hook_name, None)
            if hook is None:
                continue
            
            try:
                result = await hook(ctx, *args, **kwargs)
                if result and result.handled:
                    # Process the result
                    await self._process_behavior_result(npc_id, result)
                    return result
                last_result = result
            except Exception as e:
                print(f"[Behavior] Error in {behavior.name}.{hook_name}: {e}")
        
        return last_result
    
    async def _process_behavior_result(self, npc_id: str, result: BehaviorResult) -> None:
        """
        Process a BehaviorResult - handle movement, messages, attacks, etc.
        """
        npc = self.world.npcs.get(npc_id)
        if not npc:
            return
        
        events: list[Event] = []
        
        # Handle messages
        if result.message:
            events.append(self._msg_to_room(npc.room_id, result.message))
        
        # Handle movement
        if result.move_to:
            # Don't allow NPCs to leave while engaged in combat
            if npc.combat.is_in_combat():
                # NPC is engaged in combat; skip movement
                pass
            else:
                old_room = self.world.rooms.get(npc.room_id)
                new_room = self.world.rooms.get(result.move_to)
                
                if old_room and new_room:
                    # Update room tracking
                    old_room.entities.discard(npc_id)
                    npc.room_id = result.move_to
                    new_room.entities.add(npc_id)
                    
                    # Announce arrival if we have a direction
                    if result.move_direction:
                        opposite = {
                            "north": "south", "south": "north",
                            "east": "west", "west": "east",
                            "up": "down", "down": "up"
                        }
                        from_dir = opposite.get(result.move_direction, "somewhere")
                        # Use "from above/below" for vertical movement
                        if from_dir == "up":
                            arrival_msg = f"{npc.name} arrives from above."
                        elif from_dir == "down":
                            arrival_msg = f"{npc.name} arrives from below."
                        else:
                            arrival_msg = f"{npc.name} arrives from the {from_dir}."
                        events.append(self._msg_to_room(result.move_to, arrival_msg))
        
        # Dispatch all events
        if events:
            await self._dispatch_events(events)
    
    async def stop_time_system(self) -> None:
        """Stop the time event processing loop. Delegates to TimeEventManager."""
        # Phase 6: Save all dirty state before stopping
        if self.state_tracker:
            await self.state_tracker.shutdown()
        await self.time_manager.stop()
    
    def schedule_event(
        self,
        delay_seconds: float,
        callback: Callable[[], Awaitable[None]],
        event_id: str | None = None,
        recurring: bool = False,
    ) -> str:
        """Schedule a time event. Delegates to TimeEventManager."""
        return self.time_manager.schedule(delay_seconds, callback, event_id, recurring)
    
    def cancel_event(self, event_id: str) -> bool:
        """Cancel a scheduled time event. Delegates to TimeEventManager."""
        return self.time_manager.cancel(event_id)

    # ---------- Unified Entity System Helpers ----------

    def _get_players_in_room(self, room_id: RoomId) -> List[WorldPlayer]:
        """Get all players in a room (from unified entities set)."""
        room = self.world.rooms.get(room_id)
        if not room:
            return []
        
        players = []
        for entity_id in room.entities:
            if entity_id in self.world.players:
                players.append(self.world.players[entity_id])
        return players
    
    def _get_npcs_in_room(self, room_id: RoomId) -> List[WorldNpc]:
        """Get all NPCs in a room (from unified entities set)."""
        room = self.world.rooms.get(room_id)
        if not room:
            return []
        
        npcs = []
        for entity_id in room.entities:
            if entity_id in self.world.npcs:
                npcs.append(self.world.npcs[entity_id])
        return npcs
    
    def _get_player_ids_in_room(self, room_id: RoomId) -> set[PlayerId]:
        """Get IDs of all players in a room."""
        room = self.world.rooms.get(room_id)
        if not room:
            return set()
        return {eid for eid in room.entities if eid in self.world.players}
    
    def _find_entity_in_room(
        self, 
        room_id: RoomId, 
        search_term: str,
        include_players: bool = True,
        include_npcs: bool = True,
    ) -> tuple[EntityId | None, EntityType | None]:
        """
        Find an entity in a room by name or keyword.
        
        Returns:
            Tuple of (entity_id, entity_type) or (None, None) if not found.
        """
        room = self.world.rooms.get(room_id)
        if not room:
            return None, None
        
        search_lower = search_term.lower()
        
        for entity_id in room.entities:
            # Check players
            if include_players and entity_id in self.world.players:
                player = self.world.players[entity_id]
                if player.name.lower() == search_lower or search_lower in player.name.lower():
                    return entity_id, EntityType.PLAYER
            
            # Check NPCs
            if include_npcs and entity_id in self.world.npcs:
                npc = self.world.npcs[entity_id]
                template = self.world.npc_templates.get(npc.template_id)
                if not template or not npc.is_alive():
                    continue
                
                # Check instance name override
                npc_name = npc.instance_data.get("name_override", npc.name)
                
                # Exact or partial match on name
                if npc_name.lower() == search_lower or search_lower in npc_name.lower():
                    return entity_id, EntityType.NPC
                
                # Keyword match
                for keyword in template.keywords:
                    if search_lower == keyword.lower() or search_lower in keyword.lower():
                        return entity_id, EntityType.NPC
        
        return None, None
    
    def _find_targetable_in_room(
        self, 
        room_id: RoomId, 
        search_term: str,
        include_players: bool = True,
        include_npcs: bool = True,
        include_items: bool = True,
    ) -> tuple[Targetable | None, TargetableType | None]:
        """
        Find any targetable object in a room by name or keyword.
        
        Searches through entities (players, NPCs) and items in priority order.
        This provides a unified targeting interface for commands.
        
        Args:
            room_id: The room to search in
            search_term: Name or keyword to search for
            include_players: Whether to search players
            include_npcs: Whether to search NPCs
            include_items: Whether to search items
        
        Returns:
            Tuple of (targetable_object, targetable_type) or (None, None) if not found.
        """
        room = self.world.rooms.get(room_id)
        if not room:
            return None, None
        
        search_lower = search_term.lower()
        
        # Search entities first (players and NPCs)
        for entity_id in room.entities:
            # Check players
            if include_players and entity_id in self.world.players:
                player = self.world.players[entity_id]
                if player.matches_keyword(search_term):
                    return player, TargetableType.PLAYER
            
            # Check NPCs
            if include_npcs and entity_id in self.world.npcs:
                npc = self.world.npcs[entity_id]
                if not npc.is_alive():
                    continue
                if npc.matches_keyword(search_term):
                    return npc, TargetableType.NPC
        
        # Search items in the room
        if include_items:
            for item_id in room.items:
                item = self.world.items.get(item_id)
                if item and item.matches_keyword(search_term):
                    return item, TargetableType.ITEM
        
        return None, None
    
    def _find_item_in_room(
        self, 
        room_id: RoomId, 
        search_term: str,
    ) -> WorldItem | None:
        """
        Find an item in a room by name or keyword.
        
        Args:
            room_id: The room to search in
            search_term: Name or keyword to search for
        
        Returns:
            The matching WorldItem or None if not found.
        """
        room = self.world.rooms.get(room_id)
        if not room:
            return None
        
        for item_id in room.items:
            item = self.world.items.get(item_id)
            if item and item.matches_keyword(search_term):
                return item
        
        return None
    
    def _find_item_in_inventory(
        self, 
        player_id: PlayerId, 
        search_term: str,
    ) -> WorldItem | None:
        """
        Find an item in a player's inventory by name or keyword.
        
        Args:
            player_id: The player whose inventory to search
            search_term: Name or keyword to search for
        
        Returns:
            The matching WorldItem or None if not found.
        """
        player = self.world.players.get(player_id)
        if not player:
            return None
        
        for item_id in player.inventory_items:
            item = self.world.items.get(item_id)
            if item and item.matches_keyword(search_term):
                return item
        
        return None

    # ---------- Player connection management ----------

    async def register_player(self, player_id: PlayerId) -> asyncio.Queue[Event]:
        """
        Called when a player opens a WebSocket connection.

        Returns a queue; the WebSocket sender task will read events from this queue.
        """
        q: asyncio.Queue[Event] = asyncio.Queue()
        self._listeners[player_id] = q
        
        # Check if player is coming out of stasis
        if player_id in self.world.players:
            player = self.world.players[player_id]
            was_in_stasis = not player.is_connected
            player.is_connected = True
            
            # Send initial stat update event to populate client UI
            stat_event = self._stat_update_to_player(player_id, {
                "current_health": player.current_health,
                "max_health": player.max_health,
            })
            await self._dispatch_events([stat_event])
            
            # Send initial room description
            look_events = self._look(player_id)
            await self._dispatch_events(look_events)
            
            # Phase 6: Restore effects from database (with offline tick calculation)
            if was_in_stasis and self._db_session_factory and self.effect_system:
                try:
                    async with self._db_session_factory() as session:
                        effect_events = await self.effect_system.restore_player_effects(
                            session, player_id
                        )
                        if effect_events:
                            await self._dispatch_events(effect_events)
                except Exception as e:
                    print(f"[Phase6] Error restoring effects for {player_id}: {e}")
            
            # Phase 9i: Restore character resources with offline regen
            if was_in_stasis and self._db_session_factory:
                try:
                    async with self._db_session_factory() as session:
                        from sqlalchemy import select
                        from ..models import Player as DBPlayer
                        
                        stmt = select(DBPlayer).where(DBPlayer.id == player_id)
                        result = await session.execute(stmt)
                        db_player = result.scalar_one_or_none()
                        
                        if db_player and db_player.data:
                            # Restore resources and apply offline regen
                            self._restore_player_resources(player, db_player.data)
                            
                            # Emit resource update events to notify client
                            if player.character_sheet:
                                resources_payload = {}
                                for rid in player.character_sheet.resource_pools.keys():
                                    pool = player.character_sheet.resource_pools[rid]
                                    resources_payload[rid] = {
                                        "current": pool.current,
                                        "max": pool.max,
                                        "percent": (pool.current / pool.max * 100) if pool.max > 0 else 0
                                    }
                                if resources_payload:
                                    resource_event = self.event_dispatcher.resource_update(
                                        player_id, resources_payload
                                    )
                                    await self._dispatch_events([resource_event])
                except Exception as e:
                    logger.error(f"[Phase9i] Error restoring resources for {player_id}: {e}", exc_info=True)
            
            # Broadcast awakening message if coming out of stasis
            if was_in_stasis:
                room = self.world.rooms.get(player.room_id)
                
                # Message to the player themselves
                awakening_self_msg = (
                    "The prismatic stasis shatters around you like glass. "
                    "You gasp as awareness floods back into your form."
                )
                self_event = self._msg_to_player(player_id, awakening_self_msg)
                await self._dispatch_events([self_event])
                
                # Broadcast to others in the room
                room_player_ids = self._get_player_ids_in_room(room.id) if room else set()
                if room and len(room_player_ids) > 1:
                    awaken_msg = (
                        f"The prismatic light around {player.name} shatters like glass. "
                        f"They gasp and return to awareness, freed from stasis."
                    )
                    room_event = self._msg_to_room(
                        room.id,
                        awaken_msg,
                        exclude={player_id}
                    )
                    await self._dispatch_events([room_event])
        
        return q

    def unregister_player(self, player_id: PlayerId) -> None:
        """
        Called when a player's WebSocket disconnects.
        """
        self._listeners.pop(player_id, None)
    
    async def save_player_stats(self, player_id: PlayerId) -> None:
        """
        Persist current WorldPlayer stats and inventory to the database.
        
        This is called on disconnect, and can also be called periodically
        (once tick system is implemented in Phase 2) or on key events.
        """
        if self._db_session_factory is None:
            return  # No DB session factory configured
        
        player = self.world.players.get(player_id)
        if not player:
            return  # Player not found in world
        
        # Import here to avoid circular dependency
        from sqlalchemy import select, update
        from ..models import Player as DBPlayer, PlayerInventory as DBPlayerInventory, ItemInstance as DBItemInstance
        
        # Serialize quest progress to JSON-compatible format
        quest_progress_data = {}
        for quest_id, progress in player.quest_progress.items():
            # Handle both QuestProgress objects and raw dicts
            if hasattr(progress, 'status'):
                quest_progress_data[quest_id] = {
                    'status': progress.status.value,
                    'objective_progress': progress.objective_progress,
                    'accepted_at': progress.accepted_at,
                    'completed_at': progress.completed_at,
                    'turned_in_at': progress.turned_in_at,
                    'completion_count': progress.completion_count,
                    'last_completed_at': progress.last_completed_at,
                }
            else:
                # Already a dict
                quest_progress_data[quest_id] = progress
        
        async with self._db_session_factory() as session:
            # Serialize character sheet resources to JSON-compatible format (Phase 9i)
            resources_data = {}
            if player.character_sheet and player.character_sheet.resource_pools:
                for resource_id, pool in player.character_sheet.resource_pools.items():
                    resources_data[resource_id] = {
                        "current": pool.current,
                        "max": pool.max,
                        "last_regen_tick": getattr(pool, "last_regen_tick", time.time()),
                    }
            
            # Serialize character sheet abilities to JSON-compatible format (Phase 9i)
            learned_abilities_list = []
            if player.character_sheet:
                learned_abilities_list = list(player.character_sheet.learned_abilities)
            
            # Update player stats in database (including quest data and character sheet)
            player_stmt = (
                update(DBPlayer)
                .where(DBPlayer.id == player_id)
                .values(
                    current_health=player.current_health,
                    current_energy=player.current_energy,
                    level=player.level,
                    experience=player.experience,
                    current_room_id=player.room_id,
                    # Quest system (Phase X)
                    player_flags=player.player_flags,
                    quest_progress=quest_progress_data,
                    completed_quests=list(player.completed_quests),
                    # Phase 9: Character sheet persistence
                    data=self._serialize_player_data(player, resources_data, learned_abilities_list),
                )
            )
            await session.execute(player_stmt)
            
            # Update player inventory metadata (Phase 3)
            if player.inventory_meta:
                inventory_stmt = (
                    update(DBPlayerInventory)
                    .where(DBPlayerInventory.player_id == player_id)
                    .values(
                        max_weight=player.inventory_meta.max_weight,
                        max_slots=player.inventory_meta.max_slots,
                        current_weight=player.inventory_meta.current_weight,
                        current_slots=player.inventory_meta.current_slots,
                    )
                )
                await session.execute(inventory_stmt)
            
            # Update all items owned by this player (Phase 3)
            for item_id in player.inventory_items:
                if item_id in self.world.items:
                    item = self.world.items[item_id]
                    item_stmt = (
                        update(DBItemInstance)
                        .where(DBItemInstance.id == item_id)
                        .values(
                            player_id=player_id,
                            room_id=None,
                            container_id=item.container_id,
                            quantity=item.quantity,
                            current_durability=item.current_durability,
                            equipped_slot=item.equipped_slot,
                            instance_data=item.instance_data,
                        )
                    )
                    await session.execute(item_stmt)
            
            await session.commit()
            print(f"[Persistence] Saved stats, inventory, and quest progress for player {player.name} (ID: {player_id})")
    
    def _serialize_player_data(
        self,
        player: WorldPlayer,
        resources_data: dict,
        learned_abilities_list: list
    ) -> dict:
        """
        Serialize player data including character sheet for JSON storage.
        
        Args:
            player: The WorldPlayer instance
            resources_data: Serialized resource pools
            learned_abilities_list: List of learned ability IDs
        
        Returns:
            Dictionary ready for JSON serialization
        """
        data = {}
        
        # Store character sheet data
        if player.character_sheet:
            data["class_id"] = player.character_sheet.class_id
            data["learned_abilities"] = learned_abilities_list
            data["resource_pools"] = resources_data
            if player.character_sheet.ability_loadout:
                # Serialize ability slots
                loadout = []
                for slot in player.character_sheet.ability_loadout:
                    loadout.append({
                        "slot_id": slot.slot_id,
                        "ability_id": slot.ability_id,
                        "last_used_at": slot.last_used_at,
                        "learned_at": slot.learned_at,
                    })
                data["ability_loadout"] = loadout
        
        return data
    
    def _restore_player_resources(self, player: WorldPlayer, player_data: dict) -> None:
        """
        Restore player resources from persisted data and apply offline regen.
        
        Args:
            player: The WorldPlayer to restore
            player_data: The data dict from database
        """
        if not player.character_sheet:
            return  # No character sheet
        
        class_id = player_data.get("class_id")
        if not class_id:
            return  # No class data
        
        # Get class template for resource definitions
        class_template = self.class_system.get_class(class_id)
        if not class_template:
            logger.warning(f"Could not find class template for {class_id}")
            return
        
        # Restore resources with offline regen
        now = time.time()
        saved_resources = player_data.get("resource_pools", {})
        
        for resource_id, resource_def in (class_template.resources or {}).items():
            saved = saved_resources.get(resource_id, {})
            
            # Get last regen time (when player disconnected)
            last_regen_tick = saved.get("last_regen_tick", now)
            time_offline = max(0, now - last_regen_tick)
            
            # Calculate offline regen
            # Use regen_rate from resource definition
            regen_per_second = resource_def.regen_rate if hasattr(resource_def, 'regen_rate') else 0.1
            regen_amount = int(time_offline * regen_per_second)
            
            # Restore or create resource pool
            max_amount = resource_def.max_amount if hasattr(resource_def, 'max_amount') else 100
            
            if resource_id in player.character_sheet.resource_pools:
                pool = player.character_sheet.resource_pools[resource_id]
                # Restore saved current value
                pool.current = saved.get("current", pool.max)
                # Apply offline regen
                pool.current = min(pool.max, pool.current + regen_amount)
            else:
                # Create new pool
                pool = ResourcePool(
                    resource_id=resource_id,
                    current=min(max_amount, saved.get("current", max_amount) + regen_amount),
                    max=max_amount,
                    regen_per_second=regen_per_second
                )
                player.character_sheet.resource_pools[resource_id] = pool
            
            if regen_amount > 0:
                logger.info(
                    f"{player.name} regenerated {regen_amount} {resource_id} "
                    f"during {time_offline:.1f}s offline"
                )
    
    async def player_disconnect(self, player_id: PlayerId) -> None:
        """
        Handle a player disconnect by putting them in stasis and broadcasting a message.
        Should be called before unregister_player.
        """
        # Save player stats to database before disconnect
        await self.save_player_stats(player_id)
        
        # Phase 6: Save player effects for offline tick calculation
        if self._db_session_factory and self.effect_system:
            try:
                async with self._db_session_factory() as session:
                    await self.effect_system.save_player_effects(session, player_id)
                    await session.commit()
            except Exception as e:
                print(f"[Phase6] Error saving effects on disconnect for {player_id}: {e}")
        
        if player_id in self.world.players:
            player = self.world.players[player_id]
            player.is_connected = False  # Put in stasis
            
            room = self.world.rooms.get(player.room_id)
            room_player_ids = self._get_player_ids_in_room(room.id) if room else set()
            
            if room and len(room_player_ids) > 1:
                # Create stasis event for others in the room
                stasis_msg = (
                    f"A bright flash of light engulfs {player.name}. "
                    f"Their form flickers and freezes, suddenly suspended in a prismatic stasis."
                )
                event = self._msg_to_room(
                    room.id,
                    stasis_msg,
                    exclude={player_id}
                )
                await self._dispatch_events([event])

    # ---------- Command submission / main loop ----------

    async def submit_command(self, player_id: PlayerId, command: str) -> None:
        """
        Called by the WebSocket receiver when a command comes in from the client.
        """
        await self._command_queue.put((player_id, command))

    async def game_loop(self) -> None:
        """
        Main engine loop.

        Simple version: process commands one-by-one, no global tick yet.
        You can later extend this to also run NPC AI / timed events.
        """
        while True:
            player_id, command = await self._command_queue.get()
            print(f"WorldEngine: got command from {player_id}: {command!r}")
            events = await self.handle_command(player_id, command)
            print(f"WorldEngine: generated: {events!r}")
            await self._dispatch_events(events)

    # ---------- Command handling ----------

    async def handle_command(self, player_id: PlayerId, command: str) -> List[Event]:
        """
        Parse a raw command string and return logical events.
        
        Uses the CommandRouter to dispatch to appropriate handlers.
        """
        raw = command.strip()
        if not raw:
            return []

        # Handle repeat command "!"
        if raw == "!":
            last_cmd = self._last_commands.get(player_id)
            if not last_cmd:
                return [self._msg_to_player(player_id, "No previous command to repeat.")]
            # Don't store "!" itself, use the previous command
            raw = last_cmd
        else:
            # Store command for future repeat (but not "!")
            self._last_commands[player_id] = raw

        # Replace "self" keyword with player's own name
        player = self.world.players.get(player_id)
        if player:
            # Use word boundaries to avoid replacing "self" in words like "yourself" or "selfish"
            import re
            raw = re.sub(r'\bself\b', player.name, raw, flags=re.IGNORECASE)

        # Dispatch to command router
        return await self.command_router.dispatch(player_id, raw)

    # ---------- Helper: event constructors ----------

    def _get_equipped_weapon_name(self, entity_id: EntityId) -> str:
        """Get the name of the equipped weapon for an entity, or 'fists' if unarmed."""
        entity = self.world.players.get(entity_id) or self.world.npcs.get(entity_id)
        if not entity:
            return "fists"
        
        if "weapon" in entity.equipped_items:
            weapon_template_id = entity.equipped_items["weapon"]
            weapon_template = self.world.item_templates.get(weapon_template_id)
            if weapon_template:
                return weapon_template.name
        
        return "fists"

    def _msg_to_player(
        self,
        player_id: PlayerId,
        text: str,
        *,
        payload: dict | None = None,
    ) -> Event:
        """Create a per-player message event. Delegates to EventDispatcher."""
        return self.event_dispatcher.msg_to_player(player_id, text, payload=payload)

    def _stat_update_to_player(
        self,
        player_id: PlayerId,
        stats: dict,
    ) -> Event:
        """Create a stat_update event. Delegates to EventDispatcher."""
        return self.event_dispatcher.stat_update(player_id, stats)
    
    def _emit_stat_update(self, player_id: PlayerId) -> List[Event]:
        """Helper function to emit stat update for a player. Delegates to EventDispatcher."""
        return self.event_dispatcher.emit_stat_update(player_id)

    def _msg_to_room(
        self,
        room_id: RoomId,
        text: str,
        *,
        exclude: set[PlayerId] | None = None,
        payload: dict | None = None,
    ) -> Event:
        """Create a room-broadcast message event. Delegates to EventDispatcher."""
        return self.event_dispatcher.msg_to_room(room_id, text, exclude=exclude, payload=payload)

    # ---------- Concrete command handlers ----------

    def _format_room_entities(
        self,
        room: WorldRoom,
        exclude_player_id: PlayerId,
    ) -> list[str]:
        """
        Format the list of all entities in a room (players and NPCs).
        Returns a list of formatted strings to append to room description.
        """
        lines: list[str] = []
        world = self.world
        
        # Get all entities from the room
        players_connected = []
        players_stasis = []
        npcs_by_type: dict[str, list[str]] = {
            "hostile": [],
            "neutral": [],
            "friendly": [],
            "merchant": [],
        }
        
        for entity_id in room.entities:
            # Check if it's a player
            if entity_id in world.players:
                player = world.players[entity_id]
                if entity_id == exclude_player_id:
                    continue
                if player.is_connected:
                    players_connected.append(player.name)
                else:
                    players_stasis.append(player.name)
            
            # Check if it's an NPC
            elif entity_id in world.npcs:
                npc = world.npcs[entity_id]
                if not npc.is_alive():
                    continue
                template = world.npc_templates.get(npc.template_id)
                if not template:
                    continue
                npc_name = npc.instance_data.get("name_override", npc.name)
                npc_type = template.npc_type
                if npc_type in npcs_by_type:
                    npcs_by_type[npc_type].append(npc_name)
        
        # Format connected players
        if players_connected:
            lines.append("")
            for name in players_connected:
                lines.append(f"{name} is here.")
        
        # Format players in stasis
        if players_stasis:
            lines.append("")
            for name in players_stasis:
                lines.append(f"(Stasis) The flickering form of {name} is here, suspended in prismatic stasis.")
        
        # Format NPCs (no disposition indicator in room listing)
        any_npcs = any(npcs for npcs in npcs_by_type.values())
        if any_npcs:
            lines.append("")
            for npc_type, npc_names in npcs_by_type.items():
                for name in npc_names:
                    lines.append(f"{name} is here.")
        
        return lines
    
    # Keep old name as alias for compatibility during refactoring
    def _format_room_occupants(
        self,
        room: WorldRoom,
        exclude_player_id: PlayerId,
    ) -> list[str]:
        """Deprecated: Use _format_room_entities instead."""
        return self._format_room_entities(room, exclude_player_id)

    def _format_container_contents(self, container_id: str, template: Any) -> list[str]:
        """
        Format the contents of a container for display.
        Uses the container_contents index for O(1) lookup.
        
        Args:
            container_id: The container item's ID
            template: The container's ItemTemplate
        
        Returns:
            List of formatted lines describing the container contents
        """
        from .world import ItemTemplate
        
        world = self.world
        lines: list[str] = [""]
        container_items: list[str] = []
        
        # Use container index for O(1) lookup
        for other_item_id in world.get_container_contents(container_id):
            other_item = world.items.get(other_item_id)
            if other_item:
                other_template = world.item_templates.get(other_item.template_id)
                if other_template:
                    quantity_str = f" x{other_item.quantity}" if other_item.quantity > 1 else ""
                    container_items.append(f"  {other_template.name}{quantity_str}")
        
        if container_items:
            lines.append(f"**Contents of {template.name}:**")
            lines.extend(container_items)
            
            # Show container capacity if available
            if template.container_capacity:
                if template.container_type == "weight_based":
                    container_weight = world.get_container_weight(container_id)
                    lines.append(f"  Weight: {container_weight:.1f}/{template.container_capacity:.1f} kg")
                else:
                    # Slot-based container
                    item_count = len(container_items)
                    lines.append(f"  Slots: {item_count}/{template.container_capacity}")
        else:
            lines.append(f"**{template.name} is empty.**")
        
        return lines

    def _move_player(self, player_id: PlayerId, direction: Direction) -> List[Event]:
        events: List[Event] = []
        world = self.world

        if player_id not in world.players:
            return [
                self._msg_to_player(
                    player_id,
                    "You feel incorporeal. (Player not found in world)",
                )
            ]

        player = world.players[player_id]
        
        # Check if dead
        if not player.is_alive():
            return [self._msg_to_player(player_id, "You can't move while dead.")]
        
        # Check if sleeping
        sleeping_check = self._check_sleeping(player_id)
        if sleeping_check:
            return sleeping_check
        current_room = world.rooms.get(player.room_id)

        if current_room is None:
            return [
                self._msg_to_player(
                    player_id,
                    "You are lost in the void. (Room not found)",
                )
            ]

        # Use effective exits (includes dynamic exits from triggers)
        effective_exits = current_room.get_effective_exits()
        if direction not in effective_exits:
            return [
                self._msg_to_player(player_id, "You can't go that way."),
            ]

        new_room_id = effective_exits[direction]
        new_room = world.rooms.get(new_room_id)
        if new_room is None:
            return [
                self._msg_to_player(
                    player_id,
                    "The way blurs and collapses. (Destination room missing)",
                )
            ]

        old_room_id = current_room.id

        # Prevent leaving while engaged in combat; player must attempt to flee
        if player.combat.is_in_combat():
            return [
                self._msg_to_player(
                    player_id,
                    "You are engaged in combat and cannot leave. Try 'flee' to escape."
                )
            ]

        # Fire on_exit triggers for the old room (before leaving)
        exit_trigger_ctx = TriggerContext(
            player_id=player_id,
            room_id=old_room_id,
            world=self.world,
            event_type="on_exit",
            direction=direction,
        )
        trigger_events = self.trigger_system.fire_event(old_room_id, "on_exit", exit_trigger_ctx)
        events.extend(trigger_events)

        # Check for area transition and fire area triggers
        old_area_id = current_room.area_id
        new_area_id = new_room.area_id
        
        if old_area_id != new_area_id:
            # Fire on_area_exit for the old area
            if old_area_id:
                area_exit_ctx = TriggerContext(
                    player_id=player_id,
                    room_id=old_room_id,
                    world=self.world,
                    event_type="on_area_exit",
                    direction=direction,
                )
                area_events = self.trigger_system.fire_area_event(old_area_id, "on_area_exit", area_exit_ctx)
                events.extend(area_events)
            
            # Fire on_area_enter for the new area
            if new_area_id:
                area_enter_ctx = TriggerContext(
                    player_id=player_id,
                    room_id=new_room_id,
                    world=self.world,
                    event_type="on_area_enter",
                    direction=direction,
                )
                area_events = self.trigger_system.fire_area_event(new_area_id, "on_area_enter", area_enter_ctx)
                events.extend(area_events)

        # Update occupancy (unified entity tracking)
        current_room.entities.discard(player_id)
        new_room.entities.add(player_id)
        player.room_id = new_room_id

        # Build movement message with effects
        description_lines = [f"You move {direction}."]
        
        # Trigger exit effect from old room
        if current_room.on_exit_effect:
            description_lines.append(current_room.on_exit_effect)
        
        # Trigger player movement effect
        if player.on_move_effect:
            description_lines.append(player.on_move_effect)
        
        # Show new room (use effective description for trigger overrides)
        room_emoji = get_room_emoji(new_room.room_type, new_room.room_type_emoji)
        description_lines.extend([
            "",
            f"**{room_emoji} {new_room.name}**",
            new_room.get_effective_description()
        ])
        
        # Trigger enter effect for new room
        if new_room.on_enter_effect:
            description_lines.append("")
            description_lines.append(new_room.on_enter_effect)
        
        # List other players in the new room
        description_lines.extend(self._format_room_occupants(new_room, player_id))
        
        # Show items in new room (Phase 3)
        if new_room.items:
            items_here = []
            for item_id in new_room.items:
                item = self.world.items[item_id]
                template = self.world.item_templates[item.template_id]
                quantity_str = f" x{item.quantity}" if item.quantity > 1 else ""
                items_here.append(f"  {template.name}{quantity_str}")
            
            description_lines.append("")
            description_lines.append("Items here:")
            description_lines.extend(items_here)
        
        # Add exits to the room description (use effective exits)
        effective_exits = new_room.get_effective_exits()
        if effective_exits:
            exits = list(effective_exits.keys())
            description_lines.append("")
            description_lines.append(f"Exits: {', '.join(exits)}")
        
        events.append(
            self._msg_to_player(
                player_id,
                "\n".join(description_lines),
            )
        )

        # Broadcast to players still in the old room (they see you leave)
        old_room_players = self._get_player_ids_in_room(old_room_id)
        if old_room_players:
            events.append(
                self._msg_to_room(
                    old_room_id,
                    f"{player.name} leaves.",
                )
            )

        # Broadcast to players in the new room (they see you enter)
        new_room_players = self._get_player_ids_in_room(new_room_id)
        if len(new_room_players) > 1:  # More than just the moving player
            # Calculate the direction they arrived from (opposite of movement)
            opposite = {
                "north": "south", "south": "north",
                "east": "west", "west": "east",
                "up": "down", "down": "up"
            }
            from_dir = opposite.get(direction, "somewhere")
            # Use "from above/below" for vertical movement
            if from_dir == "up":
                arrival_msg = f"{player.name} arrives from above."
            elif from_dir == "down":
                arrival_msg = f"{player.name} arrives from below."
            else:
                arrival_msg = f"{player.name} arrives from the {from_dir}."
            events.append(
                self._msg_to_room(
                    new_room_id,
                    arrival_msg,
                    exclude={player_id},
                )
            )

        # Trigger on_player_enter for NPCs in the new room (aggressive NPCs attack)
        asyncio.create_task(self._trigger_npc_player_enter(new_room_id, player_id))

        # Fire on_enter triggers for the new room (after arrival)
        enter_trigger_ctx = TriggerContext(
            player_id=player_id,
            room_id=new_room_id,
            world=self.world,
            event_type="on_enter",
            direction=direction,
        )
        trigger_events = self.trigger_system.fire_event(new_room_id, "on_enter", enter_trigger_ctx)
        events.extend(trigger_events)
        
        # Hook: Quest system VISIT objective tracking
        if self.quest_system:
            quest_events = self.quest_system.on_room_entered(player_id, new_room_id)
            events.extend(quest_events)

        return events

    def _handle_look_command(self, engine: Any, player_id: PlayerId, args: str) -> List[Event]:
        """
        Unified look command handler for CommandRouter.
        
        Signature matches CommandRouter's expected handler signature: (engine, player_id, args)
        Delegates to existing look methods: _look() or _look_at_target()
        """
        if args and args.strip():
            # Look at a specific target
            return self._look_at_target(player_id, args.strip())
        else:
            # Look at room
            return self._look(player_id)

    def _look(self, player_id: PlayerId) -> List[Event]:
        import time
        world = self.world

        if player_id not in world.players:
            return [
                self._msg_to_player(
                    player_id,
                    "You have no form here. (Player not found)",
                )
            ]

        player = world.players[player_id]
        
        # Check if sleeping
        sleeping_check = self._check_sleeping(player_id)
        if sleeping_check:
            return sleeping_check
        room = world.rooms.get(player.room_id)

        if room is None:
            return [
                self._msg_to_player(
                    player_id,
                    "There is only darkness. (Room not found)",
                )
            ]

        # Phase 11: Check light level for visibility
        current_time = time.time()
        light_level = self.lighting_system.calculate_room_light(room, current_time)
        visibility = self.lighting_system.get_visibility_level(light_level)
        
        # If pitch black, show darkness message
        from app.engine.systems.lighting import VisibilityLevel
        if visibility == VisibilityLevel.NONE:
            return [self._msg_to_player(
                player_id,
                "It is pitch black. You can't see anything.\n"
                "You might need a light source to see your surroundings."
            )]
        
        room_emoji = get_room_emoji(room.room_type, room.room_type_emoji)
        
        # Get description based on light level
        description = self.lighting_system.get_visible_description(room, light_level)
        lines: list[str] = [f"**{room_emoji} {room.name}**", description]

        # List all entities (players and NPCs) in the same room
        # Filter by visibility
        if visibility != VisibilityLevel.MINIMAL:  # Can see entities in dim+ light
            lines.extend(self._format_room_entities(room, player_id))
        elif visibility == VisibilityLevel.MINIMAL:
            # In minimal light, show only that entities are present
            entity_count = len([e for e in room.entities if e != player_id])
            if entity_count > 0:
                lines.append(f"\nYou sense {entity_count} other presence(s) nearby.")

        # Show items in room (Phase 3) - only if light is sufficient
        if room.items and self.lighting_system.can_see_item_details(light_level):
            items_here = []
            for item_id in room.items:
                item = world.items[item_id]
                template = world.item_templates[item.template_id]
                quantity_str = f" x{item.quantity}" if item.quantity > 1 else ""
                items_here.append(f"  {template.name}{quantity_str}")
            
            lines.append("")
            lines.append("Items here:")
            lines.extend(items_here)
        elif room.items and visibility == VisibilityLevel.MINIMAL:
            lines.append("\nYou can barely make out some objects on the ground.")

        # List available exits (use effective exits for trigger overrides)
        # Always show exits unless pitch black (already handled above)
        effective_exits = room.get_effective_exits()
        if effective_exits:
            exits = list(effective_exits.keys())
            lines.append("")
            lines.append(f"Exits: {', '.join(exits)}")

        return [self._msg_to_player(player_id, "\n".join(lines))]

    def _look_at_item(self, player_id: PlayerId, item_name: str) -> List[Event]:
        """Examine an item in detail, showing description and container contents."""
        from .inventory import find_item_by_name, find_item_in_room
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        room = world.rooms[player.room_id]
        
        # First check player's inventory and equipped items
        found_item_id = find_item_by_name(world, player_id, item_name, "both")
        
        # If not found in inventory, check room
        if not found_item_id:
            found_item_id = find_item_in_room(world, room.id, item_name)
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't see '{item_name}' anywhere.")]
        
        item = world.items[found_item_id]
        template = world.item_templates[item.template_id]
        
        # Build detailed description
        lines = [f"**{template.name}**"]
        lines.append(template.description)
        
        # Add flavor text if available
        if template.flavor_text:
            lines.append("")
            lines.append(template.flavor_text)
        
        # Show item properties
        lines.append("")
        properties = []
        
        # Item type and rarity
        type_str = template.item_type.title()
        if template.item_subtype:
            type_str += f" ({template.item_subtype})"
        if template.rarity != "common":
            type_str += f" - {template.rarity.title()}"
        properties.append(f"Type: {type_str}")
        
        # Weight
        total_weight = template.weight * item.quantity
        if item.quantity > 1:
            properties.append(f"Weight: {total_weight:.1f} kg ({template.weight:.1f} kg each)")
        else:
            properties.append(f"Weight: {total_weight:.1f} kg")
        
        # Durability
        if template.has_durability and item.current_durability is not None:
            properties.append(f"Durability: {item.current_durability}/{template.max_durability}")
        
        # Equipment slot
        if template.equipment_slot:
            slot_name = template.equipment_slot.replace("_", " ").title()
            properties.append(f"Equipment Slot: {slot_name}")
        
        # Stat modifiers
        if template.stat_modifiers:
            stat_strs = []
            for stat, value in template.stat_modifiers.items():
                sign = "+" if value >= 0 else ""
                stat_display = stat.replace("_", " ").title()
                stat_strs.append(f"{sign}{value} {stat_display}")
            properties.append(f"Effects: {', '.join(stat_strs)}")
        
        # Value
        if template.value > 0:
            total_value = template.value * item.quantity
            if item.quantity > 1:
                properties.append(f"Value: {total_value} gold ({template.value} each)")
            else:
                properties.append(f"Value: {total_value} gold")
        
        # Stackable info
        if template.max_stack_size > 1:
            properties.append(f"Quantity: {item.quantity}/{template.max_stack_size}")
        elif item.quantity > 1:
            properties.append(f"Quantity: {item.quantity}")
        
        lines.extend(f"  {prop}" for prop in properties)
        
        # Show equipped status
        if item.is_equipped():
            lines.append("")
            lines.append("  [Currently Equipped]")
        
        # Container contents
        if template.is_container:
            lines.extend(self._format_container_contents(found_item_id, template))
        
        return [self._msg_to_player(player_id, "\n".join(lines))]

    def _find_npc_in_room(self, room_id: RoomId, search_term: str) -> str | None:
        """
        Find an NPC in a room by name or keyword.
        Returns the NPC ID if found, None otherwise.
        
        Note: This is a convenience wrapper around _find_entity_in_room.
        """
        entity_id, entity_type = self._find_entity_in_room(
            room_id, search_term, 
            include_players=False, 
            include_npcs=True
        )
        return entity_id if entity_type == EntityType.NPC else None

    def _look_at_target(self, player_id: PlayerId, target_name: str) -> List[Event]:
        """
        Examine any targetable object (player, NPC, or item) using unified targeting.
        
        Uses the Targetable protocol to find and describe targets uniformly.
        """
        import time
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        room = world.rooms.get(player.room_id)
        if not room:
            return [self._msg_to_player(player_id, "You are nowhere. (Room not found)")]
        
        # Phase 11: Check if there's enough light to inspect targets
        current_time = time.time()
        light_level = self.lighting_system.calculate_room_light(room, current_time)
        if not self.lighting_system.can_inspect_target(light_level):
            return [self._msg_to_player(
                player_id,
                "It's too dark to see details. You need more light to examine things closely."
            )]
        
        # Use unified targeting to find the target
        target, target_type = self._find_targetable_in_room(
            room.id, target_name,
            include_players=True,
            include_npcs=True,
            include_items=True
        )
        
        # Also check player's inventory for items
        if not target:
            inv_item = self._find_item_in_inventory(player_id, target_name)
            if inv_item:
                target = inv_item
                target_type = TargetableType.ITEM
        
        if not target:
            return [self._msg_to_player(player_id, f"You don't see '{target_name}' here.")]
        
        # Dispatch to appropriate detailed look method based on type
        if target_type == TargetableType.PLAYER:
            return self._look_at_player(player_id, target)
        elif target_type == TargetableType.NPC:
            return self._look_at_npc_detail(player_id, target)
        elif target_type == TargetableType.ITEM:
            return self._look_at_item_detail(player_id, target)
        
        return [self._msg_to_player(player_id, f"You don't see '{target_name}' here.")]
    
    def _look_at_player(self, player_id: PlayerId, target: WorldPlayer) -> List[Event]:
        """Examine another player in detail."""
        lines = [f"**{target.name}**"]
        lines.append(f"A level {target.level} {target.character_class}.")
        
        # Show health status (descriptive, not exact numbers)
        health_percent = (target.current_health / target.max_health) * 100
        if health_percent >= 100:
            health_status = "appears uninjured"
        elif health_percent >= 75:
            health_status = "has minor injuries"
        elif health_percent >= 50:
            health_status = "is moderately wounded"
        elif health_percent >= 25:
            health_status = "is heavily wounded"
        else:
            health_status = "is near death"
        
        lines.append(f"Condition: {target.name} {health_status}.")
        
        # Show connection status
        if not target.is_connected:
            lines.append("")
            lines.append("*They appear to be in a trance-like stasis.*")
        
        return [self._msg_to_player(player_id, "\n".join(lines))]
    
    def _look_at_npc_detail(self, player_id: PlayerId, npc: WorldNpc) -> List[Event]:
        """Examine an NPC in detail (internal implementation)."""
        world = self.world
        template = world.npc_templates.get(npc.template_id)
        
        if not template:
            return [self._msg_to_player(player_id, f"You see {npc.name}, but something seems off...")]
        
        # Use instance name override if available
        display_name = npc.instance_data.get("name_override", template.name)
        
        # Build detailed description
        lines = [f"**{display_name}**"]
        lines.append(template.description)
        
        # Show type indicator
        lines.append("")
        type_indicators = {
            "hostile": "🔴 Hostile",
            "neutral": "🟡 Neutral",
            "friendly": "🟢 Friendly",
            "merchant": "🛒 Merchant",
        }
        type_str = type_indicators.get(template.npc_type, template.npc_type.title())
        lines.append(f"Disposition: {type_str}")
        
        # Show level
        lines.append(f"Level: {template.level}")
        
        # Show health status (descriptive, not exact numbers)
        health_percent = (npc.current_health / template.max_health) * 100
        if health_percent >= 100:
            health_status = "appears uninjured"
        elif health_percent >= 75:
            health_status = "has minor injuries"
        elif health_percent >= 50:
            health_status = "is moderately wounded"
        elif health_percent >= 25:
            health_status = "is heavily wounded"
        else:
            health_status = "is near death"
        
        lines.append(f"Condition: {display_name} {health_status}.")
        
        # Show instance-specific data like guard messages
        if "guard_message" in npc.instance_data:
            lines.append("")
            lines.append(npc.instance_data["guard_message"])
        
        return [self._msg_to_player(player_id, "\n".join(lines))]
    
    def _look_at_item_detail(self, player_id: PlayerId, item: WorldItem) -> List[Event]:
        """Examine an item in detail (internal implementation)."""
        world = self.world
        template = world.item_templates.get(item.template_id)
        
        if not template:
            return [self._msg_to_player(player_id, f"You see {item.name}, but something seems off...")]
        
        # Build detailed description
        lines = [f"**{template.name}**"]
        lines.append(template.description)
        
        # Add flavor text if available
        if template.flavor_text:
            lines.append("")
            lines.append(template.flavor_text)
        
        # Show item properties
        lines.append("")
        properties = []
        
        # Item type and rarity
        type_str = template.item_type.title()
        if template.item_subtype:
            type_str += f" ({template.item_subtype})"
        if template.rarity != "common":
            type_str += f" - {template.rarity.title()}"
        properties.append(f"Type: {type_str}")
        
        # Weight
        total_weight = template.weight * item.quantity
        if item.quantity > 1:
            properties.append(f"Weight: {total_weight:.1f} kg ({template.weight:.1f} kg each)")
        else:
            properties.append(f"Weight: {total_weight:.1f} kg")
        
        # Durability
        if template.has_durability and item.current_durability is not None:
            properties.append(f"Durability: {item.current_durability}/{template.max_durability}")
        
        # Equipment slot
        if template.equipment_slot:
            slot_name = template.equipment_slot.replace("_", " ").title()
            properties.append(f"Equipment Slot: {slot_name}")
        
        # Stat modifiers
        if template.stat_modifiers:
            stat_strs = []
            for stat, value in template.stat_modifiers.items():
                sign = "+" if value >= 0 else ""
                stat_display = stat.replace("_", " ").title()
                stat_strs.append(f"{sign}{value} {stat_display}")
            properties.append(f"Effects: {', '.join(stat_strs)}")
        
        # Value
        if template.value > 0:
            total_value = template.value * item.quantity
            if item.quantity > 1:
                properties.append(f"Value: {total_value} gold ({template.value} each)")
            else:
                properties.append(f"Value: {total_value} gold")
        
        # Stackable info
        if template.max_stack_size > 1:
            properties.append(f"Quantity: {item.quantity}/{template.max_stack_size}")
        elif item.quantity > 1:
            properties.append(f"Quantity: {item.quantity}")
        
        lines.extend(f"  {prop}" for prop in properties)
        
        # Show equipped status
        if item.is_equipped():
            lines.append("")
            lines.append("  [Currently Equipped]")
        
        # Container contents
        if template.is_container:
            lines.extend(self._format_container_contents(item.id, template))
        
        return [self._msg_to_player(player_id, "\n".join(lines))]

    def _look_at_npc(self, player_id: PlayerId, npc_name: str) -> List[Event] | None:
        """
        Examine an NPC in detail.
        Returns None if no NPC found (so caller can try looking at items).
        """
        world = self.world
        
        if player_id not in world.players:
            return None
        
        player = world.players[player_id]
        room = world.rooms.get(player.room_id)
        if not room:
            return None
        
        # Find NPC in current room
        npc_id = self._find_npc_in_room(room.id, npc_name)
        if not npc_id:
            return None  # No NPC found, let caller try items
        
        npc = world.npcs[npc_id]
        template = world.npc_templates[npc.template_id]
        
        # Use instance name override if available
        display_name = npc.instance_data.get("name_override", template.name)
        
        # Build detailed description
        lines = [f"**{display_name}**"]
        lines.append(template.description)
        
        # Show type indicator
        lines.append("")
        type_indicators = {
            "hostile": "🔴 Hostile",
            "neutral": "🟡 Neutral",
            "friendly": "🟢 Friendly",
            "merchant": "🛒 Merchant",
        }
        type_str = type_indicators.get(template.npc_type, template.npc_type.title())
        lines.append(f"Disposition: {type_str}")
        
        # Show level
        lines.append(f"Level: {template.level}")
        
        # Show health status (descriptive, not exact numbers)
        health_percent = (npc.current_health / template.max_health) * 100
        if health_percent >= 100:
            health_status = "appears uninjured"
        elif health_percent >= 75:
            health_status = "has minor injuries"
        elif health_percent >= 50:
            health_status = "is moderately wounded"
        elif health_percent >= 25:
            health_status = "is heavily wounded"
        else:
            health_status = "is near death"
        
        lines.append(f"Condition: {display_name} {health_status}.")
        
        # Show instance-specific data like guard messages
        if "guard_message" in npc.instance_data:
            lines.append("")
            lines.append(npc.instance_data["guard_message"])
        
        return [self._msg_to_player(player_id, "\n".join(lines))]

    def _show_stats(self, player_id: PlayerId) -> List[Event]:
        """
        Display player's current stats.
        """
        world = self.world

        if player_id not in world.players:
            return [
                self._msg_to_player(
                    player_id,
                    "You have no form. (Player not found)",
                )
            ]

        player = world.players[player_id]

        # Calculate effective armor class (with buffs)
        effective_ac = player.get_effective_armor_class()
        ac_display = f"Armor Class: {effective_ac}"
        if effective_ac != player.armor_class:
            ac_display += f" ({player.armor_class} base)"

        lines: list[str] = [
            f"═══ Character Sheet: {player.name} ═══",
            "",
            f"Class: {player.character_class.title()}",
            f"Level: {player.level}",
            f"Experience: {player.experience} XP",
            "",
            "═══ Base Attributes ═══",
            f"Strength:     {player.strength}",
            f"Dexterity:    {player.dexterity}",
            f"Intelligence: {player.intelligence}",
            f"Vitality:     {player.vitality}",
            "",
            "═══ Combat Stats ═══",
            f"Health: {player.current_health}/{player.max_health}",
            f"Energy: {player.current_energy}/{player.max_energy}",
            ac_display,
        ]
        
        # Show active effects count if any
        if player.active_effects:
            lines.append("")
            lines.append(f"Active Effects: {len(player.active_effects)} (use 'effects' to view)")

        return [self._msg_to_player(player_id, "\n".join(lines))]

    def _sleep(self, player_id: PlayerId) -> List[Event]:
        """
        Enter sleeping state for faster HP and resource regeneration.
        Cannot sleep while in combat.
        """
        import time
        
        player = self.world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form.")]
        
        # Check if already sleeping
        if player.is_sleeping:
            return [self._msg_to_player(player_id, "You're already sleeping.")]
        
        # Check if in combat
        if player.is_in_combat():
            return [self._msg_to_player(
                player_id,
                "You can't sleep while in combat!"
            )]
        
        # Enter sleeping state
        player.is_sleeping = True
        player.sleep_start_time = time.time()
        
        events: List[Event] = []
        
        # Message to player
        events.append(self._msg_to_player(
            player_id,
            "You lie down and close your eyes, drifting into a restful sleep..."
        ))
        
        # Message to room
        room = self.world.rooms.get(player.room_id)
        if room:
            events.append(self._msg_to_room(
                room.id,
                f"{player.name} lies down and falls asleep.",
                exclude={player_id}
            ))
        
        return events
    
    def _check_sleeping(self, player_id: PlayerId) -> List[Event] | None:
        """
        Check if a player is sleeping and return a wake reminder message if so.
        
        Returns:
            List with wake reminder message if player is sleeping, None otherwise
        """
        player = self.world.players.get(player_id)
        if player and player.is_sleeping:
            return [self._msg_to_player(
                player_id,
                "You can't do that while sleeping. Use 'wake' to wake up."
            )]
        return None
    
    def _wake(self, player_id: PlayerId) -> List[Event]:
        """
        Exit sleeping state and return to normal regeneration.
        """
        import time
        
        player = self.world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form.")]
        
        # Check if not sleeping
        if not player.is_sleeping:
            return [self._msg_to_player(player_id, "You're not sleeping.")]
        
        # Calculate how long they slept
        sleep_duration = time.time() - (player.sleep_start_time or time.time())
        
        # Exit sleeping state
        player.is_sleeping = False
        player.sleep_start_time = None
        
        events: List[Event] = []
        
        # Message to player with sleep duration
        minutes = int(sleep_duration // 60)
        seconds = int(sleep_duration % 60)
        duration_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        
        events.append(self._msg_to_player(
            player_id,
            f"You awaken feeling refreshed. (Slept for {duration_str})"
        ))
        
        # Message to room
        room = self.world.rooms.get(player.room_id)
        if room:
            events.append(self._msg_to_room(
                room.id,
                f"{player.name} awakens.",
                exclude={player_id}
            ))
        
        return events

    def _say(self, player_id: PlayerId, text: str) -> List[Event]:
        """
        Player speaks; everyone in the same room hears it.
        """
        world = self.world

        if player_id not in world.players:
            return [
                self._msg_to_player(
                    player_id,
                    "No one hears you. (Player not found)",
                )
            ]

        player = world.players[player_id]
        
        # Check if dead
        if not player.is_alive():
            return [self._msg_to_player(player_id, "The dead cannot speak.")]
        
        room = world.rooms.get(player.room_id)

        if room is None:
            return [
                self._msg_to_player(
                    player_id,
                    "Your words vanish into nothing. (Room not found)",
                )
            ]

        events: List[Event] = []

        # Feedback to speaker
        events.append(self._msg_to_player(player_id, f'You say: "{text}"'))

        # Broadcast to everyone else in the room
        room_player_ids = self._get_player_ids_in_room(room.id)
        if room_player_ids:
            events.append(
                self._msg_to_room(
                    room.id,
                    f'{player.name} says: "{text}"',
                    exclude={player_id},
                )
            )

        return events

    def _emote(self, player_id: PlayerId, emote: str) -> List[Event]:
        """
        Player performs an emote; everyone in the same room sees the third-person version.
        """
        world = self.world

        if player_id not in world.players:
            return [
                self._msg_to_player(
                    player_id,
                    "No one perceives you. (Player not found)",
                )
            ]

        player = world.players[player_id]
        
        # Check if dead
        if not player.is_alive():
            return [self._msg_to_player(player_id, "The dead cannot emote.")]
        
        room = world.rooms.get(player.room_id)

        if room is None:
            return [
                self._msg_to_player(
                    player_id,
                    "Your gesture fades into the void. (Room not found)",
                )
            ]

        # Define first-person and third-person messages for each emote
        emote_map = {
            "smile": ("😊 You smile.", f"😊 {player.name} smiles."),
            "nod": ("🙂‍↕️ You nod.", f"🙂‍↕️ {player.name} nods."),
            "laugh": ("😄 You laugh.", f"😄 {player.name} laughs."),
            "cringe": ("😖 You cringe.", f"😖 {player.name} cringes."),
            "smirk": ("😏 You smirk.", f"😏 {player.name} smirks."),
            "frown": ("🙁 You frown.", f"🙁 {player.name} frowns."),
            "wink": ("😉 You wink.", f"😉 {player.name} winks."),
            "lookaround": ("👀 You look around.", f"👀 {player.name} looks around."),
        }

        first_person, third_person = emote_map.get(emote, ("You do something.", f"{player.name} does something."))

        events: List[Event] = []

        # Feedback to the player
        events.append(self._msg_to_player(player_id, first_person))

        # Broadcast to everyone else in the room
        room_player_ids = self._get_player_ids_in_room(room.id)
        if len(room_player_ids) > 1:
            events.append(
                self._msg_to_room(
                    room.id,
                    third_person,
                    exclude={player_id},
                )
            )

        return events

    def _heal(self, player_id: PlayerId, target_name: str) -> List[Event]:
        """
        Heal an entity by name (admin/debug command).
        Uses Targetable protocol for unified player/NPC targeting.
        """
        world = self.world
        events: List[Event] = []
        
        player = world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        room = world.rooms.get(player.room_id)
        if not room:
            return [self._msg_to_player(player_id, "You are nowhere. (Room not found)")]

        # Use unified targeting to find target entity
        target, target_type = self._find_targetable_in_room(
            room.id, target_name,
            include_players=True,
            include_npcs=True,
            include_items=False
        )
        
        if not target or target_type == TargetableType.ITEM:
            return [self._msg_to_player(player_id, f"'{target_name}' not found.")]
        
        # Get entity reference
        entity: WorldEntity
        if target_type == TargetableType.PLAYER:
            entity = world.players[target.id]
        else:
            entity = world.npcs[target.id]
        
        # Heal for 20 HP (or up to max)
        heal_amount = 20
        old_health = entity.current_health
        entity.current_health = min(entity.current_health + heal_amount, entity.max_health)
        actual_heal = entity.current_health - old_health
        
        # Send stat_update to target (only for players)
        if target_type == TargetableType.PLAYER:
            events.append(self._stat_update_to_player(
                target.id,
                {
                    "current_health": entity.current_health,
                    "max_health": entity.max_health,
                }
            ))
            
            # Send message to target player
            events.append(self._msg_to_player(
                target.id,
                f"*A warm glow surrounds you.* You are healed for {actual_heal} HP."
            ))
        
        # Send confirmation to healer
        if target_type == TargetableType.PLAYER and player_id != target.id:
            events.append(self._msg_to_player(
                player_id,
                f"You heal {entity.name} for {actual_heal} HP."
            ))
        elif target_type == TargetableType.NPC:
            events.append(self._msg_to_player(
                player_id,
                f"You heal {entity.name} for {actual_heal} HP."
            ))
        
        # Broadcast to others in the room
        room_player_ids = self._get_player_ids_in_room(room.id)
        if len(room_player_ids) > 1:
            healer_name = player.name
            exclude_set = {player_id}
            if target_type == TargetableType.PLAYER:
                exclude_set.add(target.id)
            
            if target_type == TargetableType.PLAYER and player_id == target.id:
                room_msg = f"*A warm glow surrounds {entity.name}.*"
            else:
                room_msg = f"*{healer_name} channels healing energy into {entity.name}.*"
            events.append(self._msg_to_room(room.id, room_msg, exclude=exclude_set))
        
        return events

    def _hurt(self, player_id: PlayerId, target_name: str) -> List[Event]:
        """
        Hurt an entity by name (admin/debug command).
        Uses Targetable protocol for unified player/NPC targeting.
        """
        world = self.world
        events: List[Event] = []
        
        player = world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        room = world.rooms.get(player.room_id)
        if not room:
            return [self._msg_to_player(player_id, "You are nowhere. (Room not found)")]

        # Use unified targeting to find target entity
        target, target_type = self._find_targetable_in_room(
            room.id, target_name,
            include_players=True,
            include_npcs=True,
            include_items=False
        )
        
        if not target or target_type == TargetableType.ITEM:
            return [self._msg_to_player(player_id, f"'{target_name}' not found.")]
        
        # Get entity reference
        entity: WorldEntity
        if target_type == TargetableType.PLAYER:
            entity = world.players[target.id]
        else:
            entity = world.npcs[target.id]
        
        # Damage for 15 HP (but not below 1)
        damage_amount = 15
        old_health = entity.current_health
        entity.current_health = max(entity.current_health - damage_amount, 1)
        actual_damage = old_health - entity.current_health
        
        # Send stat_update to target (only for players)
        if target_type == TargetableType.PLAYER:
            events.append(self._stat_update_to_player(
                target.id,
                {
                    "current_health": entity.current_health,
                    "max_health": entity.max_health,
                }
            ))
            
            # Send message to target player
            events.append(self._msg_to_player(
                target.id,
                f"*A dark force strikes you!* You take {actual_damage} damage."
            ))
        
        # Send confirmation to attacker
        if target_type == TargetableType.PLAYER and player_id != target.id:
            events.append(self._msg_to_player(
                player_id,
                f"You hurt {entity.name} for {actual_damage} damage."
            ))
        elif target_type == TargetableType.NPC:
            events.append(self._msg_to_player(
                player_id,
                f"You hurt {entity.name} for {actual_damage} damage."
            ))
        
        # Broadcast to others in the room
        room_player_ids = self._get_player_ids_in_room(room.id)
        if len(room_player_ids) > 1:
            attacker_name = player.name
            exclude_set = {player_id}
            if target_type == TargetableType.PLAYER:
                exclude_set.add(target.id)
            
            if target_type == TargetableType.PLAYER and player_id == target.id:
                room_msg = f"*Dark energy lashes at {entity.name}!*"
            else:
                room_msg = f"*{attacker_name} strikes {entity.name} with dark energy!*"
            events.append(self._msg_to_room(room.id, room_msg, exclude=exclude_set))
        
        return events

    # =========================================================================
    # Real-Time Combat System (delegates to CombatSystem)
    # =========================================================================
    
    async def _attack(self, player_id: PlayerId, target_name: str) -> List[Event]:
        """Initiate an attack. Delegates to CombatSystem."""
        return await self.combat_system.start_attack(player_id, target_name)
    
    def _roll_and_drop_loot(self, drop_table: list, room_id: RoomId, npc_name: str) -> List[Event]:
        """Roll and drop loot. Delegates to CombatSystem."""
        return self.combat_system.roll_and_drop_loot(drop_table, room_id, npc_name)
    
    async def _handle_death(self, victim_id: EntityId, killer_id: EntityId) -> List[Event]:
        """Handle entity death. Delegates to CombatSystem and handles NPC cleanup."""
        events = await self.combat_system.handle_death(victim_id, killer_id)
        
        # Handle NPC behavior cleanup
        if victim_id in self.world.npcs:
            self._cancel_npc_timers(victim_id)
        
        return events
    
    def _stop_combat(self, player_id: PlayerId, flee: bool = False) -> List[Event]:
        """Stop combat or attempt to flee. Delegates to CombatSystem."""
        return self.combat_system.stop_combat(player_id, flee)
    
    def _show_combat_status(self, player_id: PlayerId) -> List[Event]:
        """Show current combat status. Delegates to CombatSystem."""
        return self.combat_system.show_combat_status(player_id)
    
    async def _trigger_npc_player_enter(self, room_id: str, player_id: str) -> None:
        """Trigger on_player_enter for all NPCs in a room when a player enters."""
        room = self.world.rooms.get(room_id)
        if not room:
            return
        
        player = self.world.players.get(player_id)
        if not player:
            return
        
        for entity_id in list(room.entities):
            if entity_id not in self.world.npcs:
                continue
            
            npc = self.world.npcs[entity_id]
            if not npc.is_alive():
                continue
            
            result = await self._run_behavior_hook(entity_id, "on_player_enter", player_id)
            
            # Handle attack_target (aggressive NPCs)
            if result and result.attack_target:
                # Use the combat system to initiate NPC attack by entity ids
                events = self.combat_system.start_attack_entity(entity_id, player_id)
                
                # Announce the attack message from behavior
                if result.message:
                    events.append(self._msg_to_room(room_id, result.message))
                
                # Dispatch events
                if events:
                    await self._dispatch_events(events)
    
    async def _trigger_npc_combat_start(self, npc_id: str, attacker_id: str) -> None:
        """Trigger on_combat_start behavior hooks for an NPC."""
        result = await self._run_behavior_hook(npc_id, "on_combat_start", attacker_id)
        
        # If NPC behavior wants to retaliate, start their attack
        if result and result.attack_target:
            # Use returned attack_target if provided, otherwise fall back to attacker_id
            target_id = result.attack_target or attacker_id
            target_entity = self.world.players.get(target_id) or self.world.npcs.get(target_id)
            if target_entity:
                events = self.combat_system.start_attack_entity(npc_id, target_id)
                if events:
                    await self._dispatch_events(events)
    
    async def _trigger_npc_damaged(self, npc_id: str, attacker_id: str, damage: int) -> None:
        """Trigger on_damaged behavior hooks for an NPC."""
        result = await self._run_behavior_hook(npc_id, "on_damaged", attacker_id, damage)
        
        npc = self.world.npcs.get(npc_id)
        if not npc or not npc.is_alive():
            return
        
        # Handle flee result
        if result and result.flee and result.move_to:
            # NPC flees - cancel combat and move
            npc.combat.clear_combat()
            old_room = self.world.rooms.get(npc.room_id)
            new_room = self.world.rooms.get(result.move_to)
            
            if old_room and new_room:
                old_room.entities.discard(npc_id)
                npc.room_id = result.move_to
                new_room.entities.add(npc_id)
        
        # Handle call for help
        if result and result.call_for_help:
            # Alert nearby allies
            await self._npc_call_for_help(npc_id, attacker_id)
        
        # Handle retaliation: delegate to CombatSystem so swings/scheduling work
        if result and result.attack_target and not npc.combat.is_in_combat():
            # result.attack_target is an entity id; resolve to a name for the combat API
            target_entity = self.world.players.get(result.attack_target) or self.world.npcs.get(result.attack_target)
            if target_entity:
                events = self.combat_system.start_attack_entity(npc_id, target_entity.id)
                if events:
                    # include any behavior message already queued
                    await self._dispatch_events(events)
    
    async def _npc_call_for_help(self, caller_id: str, enemy_id: str) -> None:
        """Have nearby NPCs of same type join combat."""
        caller = self.world.npcs.get(caller_id)
        if not caller:
            return
        
        room = self.world.rooms.get(caller.room_id)
        if not room:
            return
        
        caller_template = self.world.npc_templates.get(caller.template_id)
        
        # Find allies in the same room
        for entity_id in list(room.entities):
            if entity_id == caller_id or entity_id not in self.world.npcs:
                continue
            
            ally = self.world.npcs[entity_id]
            if not ally.is_alive() or ally.combat.is_in_combat():
                continue
            
            # Check if same faction/type (simplified - same template type)
            ally_template = self.world.npc_templates.get(ally.template_id)
            if ally_template and caller_template:
                if ally_template.npc_type == caller_template.npc_type:
                    # Ally joins the fight via CombatSystem
                    ally.combat.add_threat(enemy_id, 50.0)
                    events = self.combat_system.start_attack_entity(entity_id, enemy_id)
                    # Announce arrival and any combat events
                    join_msg = self._msg_to_room(room.id, f"{ally.name} joins the fight!")
                    to_dispatch = [join_msg]
                    if events:
                        to_dispatch.extend(events)
                    await self._dispatch_events(to_dispatch)

    def _test_timer(self, player_id: PlayerId, delay: float) -> List[Event]:
        """
        Test command to demonstrate time event system.
        Schedules a message to be sent after a delay.
        """
        world = self.world
        player = world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "Player not found.")]
        
        # Get player's area for time scale info
        room = world.rooms.get(player.room_id)
        area = None
        time_scale = 1.0
        area_name = "global time"
        
        if room and room.area_id and room.area_id in world.areas:
            area = world.areas[room.area_id]
            time_scale = area.time_scale
            area_name = area.name
        
        # Calculate in-game time that will pass
        from .world import real_seconds_to_game_minutes
        game_minutes = real_seconds_to_game_minutes(delay) * time_scale
        
        # Create callback that will send a message when timer fires
        async def timer_callback():
            event = self._msg_to_player(
                player_id,
                f"⏰ Timer expired! {delay} seconds have passed."
            )
            await self._dispatch_events([event])
        
        # Schedule the event
        event_id = self.schedule_event(delay, timer_callback)
        
        # Build response message
        scale_note = f" at {time_scale:.1f}x timescale" if time_scale != 1.0 else ""
        message = f"⏱️ Timer set for {delay} seconds ({game_minutes:.1f} in-game minutes in {area_name}{scale_note})"
        
        return [self._msg_to_player(player_id, message)]

    def _bless(self, player_id: PlayerId, target_name: str) -> List[Event]:
        """
        Apply a temporary armor class buff to an entity. Delegates to EffectSystem.
        """
        world = self.world
        events: List[Event] = []
        
        player = world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        room = world.rooms.get(player.room_id)
        if not room:
            return [self._msg_to_player(player_id, "You are nowhere. (Room not found)")]

        # Use unified targeting to find target entity
        target, target_type = self._find_targetable_in_room(
            room.id, target_name,
            include_players=True,
            include_npcs=True,
            include_items=False
        )
        
        if not target or target_type == TargetableType.ITEM:
            return [self._msg_to_player(player_id, f"'{target_name}' not found.")]
        
        # Get entity reference
        entity: WorldEntity
        if target_type == TargetableType.PLAYER:
            entity = world.players[target.id]
        else:
            entity = world.npcs[target.id]
        
        # Apply blessing via EffectSystem
        effect_events = self.effect_system.apply_blessing(target.id, bonus=5, duration=30.0)
        events.extend(effect_events)
        
        # Send confirmation to caster
        if target_type == TargetableType.PLAYER and player_id != target.id:
            events.append(self._msg_to_player(
                player_id,
                f"You bless {entity.name} with divine protection."
            ))
        elif target_type == TargetableType.NPC:
            events.append(self._msg_to_player(
                player_id,
                f"You bless {entity.name} with divine protection."
            ))
        
        # Broadcast to others in the room
        room_player_ids = self._get_player_ids_in_room(room.id)
        if len(room_player_ids) > 1:
            caster_name = player.name
            exclude_set = {player_id}
            if target_type == TargetableType.PLAYER:
                exclude_set.add(target.id)
            
            if target_type == TargetableType.PLAYER and player_id == target.id:
                room_msg = f"*Divine light surrounds {entity.name}!*"
            else:
                room_msg = f"*{caster_name} blesses {entity.name} with divine light!*"
            events.append(self._msg_to_room(room.id, room_msg, exclude=exclude_set))
        
        return events

    def _poison(self, player_id: PlayerId, target_name: str) -> List[Event]:
        """
        Apply a damage-over-time poison effect to an entity. Delegates to EffectSystem.
        """
        world = self.world
        events: List[Event] = []
        
        player = world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        room = world.rooms.get(player.room_id)
        if not room:
            return [self._msg_to_player(player_id, "You are nowhere. (Room not found)")]

        # Use unified targeting to find target entity
        target, target_type = self._find_targetable_in_room(
            room.id, target_name,
            include_players=True,
            include_npcs=True,
            include_items=False
        )
        
        if not target or target_type == TargetableType.ITEM:
            return [self._msg_to_player(player_id, f"'{target_name}' not found.")]
        
        # Get entity reference
        entity: WorldEntity
        if target_type == TargetableType.PLAYER:
            entity = world.players[target.id]
        else:
            entity = world.npcs[target.id]
        
        # Apply poison via EffectSystem
        effect_events = self.effect_system.apply_poison(target.id, damage_per_tick=5, tick_interval=3.0, duration=15.0)
        events.extend(effect_events)
        
        # Send confirmation to poisoner
        if target_type == TargetableType.PLAYER and player_id != target.id:
            events.append(self._msg_to_player(
                player_id,
                f"You poison {entity.name} with toxic energy."
            ))
        elif target_type == TargetableType.NPC:
            events.append(self._msg_to_player(
                player_id,
                f"You poison {entity.name} with toxic energy."
            ))
        
        # Broadcast to others in the room
        room_player_ids = self._get_player_ids_in_room(room.id)
        if len(room_player_ids) > 1:
            poisoner_name = player.name
            exclude_set = {player_id}
            if target_type == TargetableType.PLAYER:
                exclude_set.add(target.id)
            
            if target_type == TargetableType.PLAYER and player_id == target.id:
                room_msg = f"🤢 *Vile toxins course through {entity.name}!*"
            else:
                room_msg = f"🤢 *{poisoner_name} poisons {entity.name} with toxic energy!*"
            events.append(self._msg_to_room(room.id, room_msg, exclude=exclude_set))
        
        return events

    def _time(self, player_id: PlayerId) -> List[Event]:
        """
        Display the current time for the player's area.
        Usage: time
        """
        world = self.world
        
        # Get player's current area to use area-specific time and flavor text
        player = world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "Player not found.")]
        
        room = world.rooms.get(player.room_id)
        if not room:
            return [self._msg_to_player(player_id, "Room not found.")]
        
        # Use area-specific time if in an area, otherwise global time
        if room.area_id and room.area_id in world.areas:
            area = world.areas[room.area_id]
            time_info = area.area_time.format_full(area.time_scale)
            phase = area.area_time.get_time_of_day(area.time_scale)
            flavor_text = area.time_phases.get(phase, "")
            
            # Build message with area context
            message_parts = [time_info]
            if area.name:
                message_parts.append(f"*{area.name}*")
            if flavor_text:
                message_parts.append("")
                message_parts.append(flavor_text)
            
            # Add ambient sound if present
            if area.ambient_sound:
                message_parts.append("")
                message_parts.append(f"*{area.ambient_sound}*")
            
            # Note if time flows differently here
            if area.time_scale != 1.0:
                message_parts.append("")
                if area.time_scale > 1.0:
                    message_parts.append(f"*Time flows {area.time_scale:.1f}x faster here.*")
                else:
                    message_parts.append(f"🐌 *Time flows {area.time_scale:.1f}x slower here.*")
            
            message = "\n".join(message_parts)
        else:
            # Use global world time for rooms not in an area
            time_info = world.world_time.format_full()
            phase = world.world_time.get_time_of_day()
            from .world import DEFAULT_TIME_PHASES
            flavor_text = DEFAULT_TIME_PHASES.get(phase, "")
            message = f"{time_info}\n\n{flavor_text}"
        
        return [self._msg_to_player(player_id, message)]

    def _show_effects(self, player_id: PlayerId) -> List[Event]:
        """
        Display active effects on the player. Delegates to EffectSystem.
        """
        world = self.world

        if player_id not in world.players:
            return [
                self._msg_to_player(
                    player_id,
                    "You have no form. (Player not found)",
                )
            ]

        # Use EffectSystem to get formatted effects summary
        summary = self.effect_system.get_effect_summary(player_id)
        return [self._msg_to_player(player_id, summary)]

    # ---------- Event dispatch ----------

    async def _dispatch_events(self, events: List[Event]) -> None:
        """Route events to players. Delegates to EventDispatcher."""
        await self.event_dispatcher.dispatch(events)

    # ---------- Inventory system commands (Phase 3) ----------

    def _inventory(self, player_id: PlayerId) -> List[Event]:
        """Show player inventory."""
        from .inventory import calculate_inventory_weight
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        # Check if sleeping
        sleeping_check = self._check_sleeping(player_id)
        if sleeping_check:
            return sleeping_check
        
        player = world.players[player_id]
        inventory = player.inventory_meta
        
        if not inventory:
            return [self._msg_to_player(player_id, "You have no inventory.")]
        
        if not player.inventory_items:
            return [self._msg_to_player(player_id, "Your inventory is empty.")]
        
        # Group items by template (for stacking display)
        items_display = []
        for item_id in player.inventory_items:
            item = world.items[item_id]
            template = world.item_templates[item.template_id]
            
            equipped_marker = " [equipped]" if item.is_equipped() else ""
            quantity_str = f" x{item.quantity}" if item.quantity > 1 else ""
            
            items_display.append(f"  {template.name}{quantity_str}{equipped_marker}")
        
        weight = calculate_inventory_weight(world, player_id)
        
        lines = [
            "=== Inventory ===",
            *items_display,
            "",
            f"Weight: {weight:.1f}/{inventory.max_weight:.1f} kg",
            f"Slots: {inventory.current_slots}/{inventory.max_slots}"
        ]
        
        return [self._msg_to_player(player_id, "\n".join(lines))]

    def _get(self, player_id: PlayerId, item_name: str) -> List[Event]:
        """Pick up item from room (one at a time for stacks)."""
        from .inventory import add_item_to_inventory, InventoryFullError, find_item_in_room
        import uuid
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        
        # Check if dead
        if not player.is_alive():
            return [self._msg_to_player(player_id, "You can't pick up items while dead.")]
        
        # Check if sleeping
        sleeping_check = self._check_sleeping(player_id)
        if sleeping_check:
            return sleeping_check
        
        room = world.rooms[player.room_id]
        
        # Find item in room by name
        found_item_id = find_item_in_room(world, room.id, item_name)
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't see '{item_name}' here.")]
        
        item = world.items[found_item_id]
        template = world.item_templates[item.template_id]
        
        # Check quest item / no pickup flags
        if template.flags.get("no_pickup"):
            return [self._msg_to_player(player_id, f"You cannot pick up {template.name}.")]
        
        # Handle stacked items - only pick up one at a time
        if item.quantity > 1:
            # Reduce stack on ground
            item.quantity -= 1
            
            # Create a new item instance for the one we're picking up
            from .world import WorldItem
            new_item_id = str(uuid.uuid4())
            new_item = WorldItem(
                id=new_item_id,
                template_id=item.template_id,
                room_id=None,
                player_id=player_id,
                container_id=None,
                quantity=1,
                current_durability=item.current_durability,
                equipped_slot=None,
                instance_data=dict(item.instance_data)
            )
            world.items[new_item_id] = new_item
            
            # Try to add to inventory (will stack with existing if possible)
            try:
                add_item_to_inventory(world, player_id, new_item_id)
                
                events = [
                    self._msg_to_player(player_id, f"You pick up {template.name}."),
                    self._msg_to_room(room.id, f"{player.name} picks up {template.name}.", exclude={player_id})
                ]
                
                # Hook: Quest system COLLECT objective tracking
                if self.quest_system:
                    quest_events = self.quest_system.on_item_acquired(player_id, item.template_id, 1)
                    events.extend(quest_events)
                
                return events
                
            except InventoryFullError as e:
                # Revert: add back to ground stack and remove new item
                item.quantity += 1
                del world.items[new_item_id]
                return [self._msg_to_player(player_id, str(e))]
        else:
            # Single item - just move it
            try:
                room.items.remove(found_item_id)
                add_item_to_inventory(world, player_id, found_item_id)
                
                events = [
                    self._msg_to_player(player_id, f"You pick up {template.name}."),
                    self._msg_to_room(room.id, f"{player.name} picks up {template.name}.", exclude={player_id})
                ]
                
                # Hook: Quest system COLLECT objective tracking
                if self.quest_system:
                    quest_events = self.quest_system.on_item_acquired(player_id, item.template_id, 1)
                    events.extend(quest_events)
                
                return events
                
            except InventoryFullError as e:
                # Return item to room
                room.items.add(found_item_id)
                item.room_id = room.id
                return [self._msg_to_player(player_id, str(e))]

    def _get_from_container(self, player_id: PlayerId, item_name: str, container_name: str) -> List[Event]:
        """Get an item from a container."""
        from .inventory import find_item_by_name, add_item_to_inventory, InventoryFullError
        import uuid
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        
        # Find the container (in inventory or room)
        container_id = find_item_by_name(world, player_id, container_name, "both")
        
        if not container_id:
            # Check room for container
            from .inventory import find_item_in_room
            room = world.rooms[player.room_id]
            container_id = find_item_in_room(world, room.id, container_name)
        
        if not container_id:
            return [self._msg_to_player(player_id, f"You don't see '{container_name}' anywhere.")]
        
        container = world.items[container_id]
        container_template = world.item_templates[container.template_id]
        
        if not container_template.is_container:
            return [self._msg_to_player(player_id, f"{container_template.name} is not a container.")]
        
        # Find the item inside the container using index + keyword matching
        from .inventory import _matches_item_name
        item_name_lower = item_name.lower()
        found_item_id = None
        
        # Use container index for O(1) lookup of container contents
        container_item_ids = world.get_container_contents(container_id)
        
        # Exact match first
        for other_id in container_item_ids:
            other_item = world.items.get(other_id)
            if other_item:
                other_template = world.item_templates[other_item.template_id]
                if _matches_item_name(other_template, item_name_lower, exact=True):
                    found_item_id = other_id
                    break
        
        # Partial match if no exact match
        if not found_item_id:
            for other_id in container_item_ids:
                other_item = world.items.get(other_id)
                if other_item:
                    other_template = world.item_templates[other_item.template_id]
                    if _matches_item_name(other_template, item_name_lower, exact=False):
                        found_item_id = other_id
                        break
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't see '{item_name}' in {container_template.name}.")]
        
        item = world.items[found_item_id]
        template = world.item_templates[item.template_id]
        
        # Handle stacks - take one at a time
        if item.quantity > 1:
            item.quantity -= 1
            
            from .world import WorldItem
            new_item_id = str(uuid.uuid4())
            new_item = WorldItem(
                id=new_item_id,
                template_id=item.template_id,
                room_id=None,
                player_id=player_id,
                container_id=None,
                quantity=1,
                current_durability=item.current_durability,
                equipped_slot=None,
                instance_data=dict(item.instance_data)
            )
            world.items[new_item_id] = new_item
            
            try:
                add_item_to_inventory(world, player_id, new_item_id)
                return [self._msg_to_player(player_id, f"You take {template.name} from {container_template.name}.")]
            except InventoryFullError as e:
                item.quantity += 1
                del world.items[new_item_id]
                return [self._msg_to_player(player_id, str(e))]
        else:
            # Single item - move it using index helper
            world.remove_item_from_container(found_item_id)
            try:
                add_item_to_inventory(world, player_id, found_item_id)
                return [self._msg_to_player(player_id, f"You take {template.name} from {container_template.name}.")]
            except InventoryFullError as e:
                # Restore to container on failure
                world.add_item_to_container(found_item_id, container_id)
                return [self._msg_to_player(player_id, str(e))]

    def _put_in_container(self, player_id: PlayerId, item_name: str, container_name: str) -> List[Event]:
        """Put an item into a container."""
        from .inventory import find_item_by_name, remove_item_from_inventory, InventoryError
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        
        # Find the item in inventory
        item_id = find_item_by_name(world, player_id, item_name, "inventory")
        
        if not item_id:
            return [self._msg_to_player(player_id, f"You don't have '{item_name}'.")]
        
        item = world.items[item_id]
        template = world.item_templates[item.template_id]
        
        # Can't put equipped items in containers
        if item.is_equipped():
            return [self._msg_to_player(player_id, f"Unequip {template.name} first.")]
        
        # Find the container (in inventory or room)
        container_id = find_item_by_name(world, player_id, container_name, "both")
        
        if not container_id:
            # Check room for container
            from .inventory import find_item_in_room
            room = world.rooms[player.room_id]
            container_id = find_item_in_room(world, room.id, container_name)
        
        if not container_id:
            return [self._msg_to_player(player_id, f"You don't see '{container_name}' anywhere.")]
        
        # Can't put item in itself
        if container_id == item_id:
            return [self._msg_to_player(player_id, "You can't put something inside itself.")]
        
        container = world.items[container_id]
        container_template = world.item_templates[container.template_id]
        
        if not container_template.is_container:
            return [self._msg_to_player(player_id, f"{container_template.name} is not a container.")]
        
        # Prevent putting containers inside other containers
        if template.is_container:
            return [self._msg_to_player(player_id, f"You can't put {template.name} inside another container.")]
        
        # Check container capacity using index helpers
        if container_template.container_capacity:
            current_count = world.get_container_slot_count(container_id)
            current_weight = world.get_container_weight(container_id)
            
            if container_template.container_type == "weight_based":
                new_weight = current_weight + (template.weight * item.quantity)
                if new_weight > container_template.container_capacity:
                    return [self._msg_to_player(player_id, f"{container_template.name} is too full. ({current_weight:.1f}/{container_template.container_capacity:.1f} kg)")]
            else:
                # Slot-based
                if current_count >= container_template.container_capacity:
                    return [self._msg_to_player(player_id, f"{container_template.name} is full. ({current_count}/{container_template.container_capacity} slots)")]
        
        # Remove from inventory and put in container using index helper
        try:
            player.inventory_items.remove(item_id)
            item.player_id = None
            world.add_item_to_container(item_id, container_id)
            
            # Update inventory metadata
            if player.inventory_meta:
                from .inventory import calculate_inventory_weight
                player.inventory_meta.current_weight = calculate_inventory_weight(world, player_id)
                player.inventory_meta.current_slots = len(player.inventory_items)
            
            return [self._msg_to_player(player_id, f"You put {template.name} in {container_template.name}.")]
            
        except KeyError:
            return [self._msg_to_player(player_id, f"Failed to put {template.name} in {container_template.name}.")]

    def _drop(self, player_id: PlayerId, item_name: str) -> List[Event]:
        """Drop item from inventory."""
        from .inventory import remove_item_from_inventory, InventoryError, find_item_by_name
        import time as time_module
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        # Check if sleeping
        sleeping_check = self._check_sleeping(player_id)
        if sleeping_check:
            return sleeping_check
        
        player = world.players[player_id]
        room = world.rooms[player.room_id]
        
        # Find item in inventory
        found_item_id = find_item_by_name(world, player_id, item_name, "inventory")
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't have '{item_name}'.")]
        
        item = world.items[found_item_id]
        template = world.item_templates[item.template_id]
        
        # Check no-drop flag
        if template.flags.get("no_drop"):
            return [self._msg_to_player(player_id, f"You cannot drop {template.name}.")]
        
        try:
            remove_item_from_inventory(world, player_id, found_item_id)
            item.room_id = room.id
            item.dropped_at = time_module.time()  # Phase 6: Track drop time for decay
            room.items.add(found_item_id)
            
            # Broadcast to room
            return [
                self._msg_to_player(player_id, f"You drop {template.name}."),
                self._msg_to_room(room.id, f"{player.name} drops {template.name}.", exclude={player_id})
            ]
            
        except InventoryError as e:
            return [self._msg_to_player(player_id, str(e))]

    def _equip(self, player_id: PlayerId, item_name: str) -> List[Event]:
        """Equip item."""
        from .inventory import equip_item, InventoryError, find_item_by_name
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        # Check if sleeping
        sleeping_check = self._check_sleeping(player_id)
        if sleeping_check:
            return sleeping_check
        
        player = world.players[player_id]
        
        # Find item in inventory
        found_item_id = find_item_by_name(world, player_id, item_name, "inventory")
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't have '{item_name}'.")]
        
        template = world.item_templates[world.items[found_item_id].template_id]
        
        try:
            previously_equipped = equip_item(world, player_id, found_item_id)
            
            messages = [f"You equip {template.name}."]
            
            if previously_equipped:
                prev_template = world.item_templates[world.items[previously_equipped].template_id]
                messages.append(f"You unequip {prev_template.name}.")
                
                # Phase 11: Remove light source if previously equipped item provided light
                if prev_template.provides_light:
                    self.lighting_system.remove_light_source(
                        room_id=player.room_id,
                        source_id=f"item_{previously_equipped}"
                    )
            
            # Phase 11: Add light source if item provides light
            if template.provides_light and template.light_intensity > 0:
                import time
                expires_at = None
                if template.light_duration:
                    expires_at = time.time() + template.light_duration
                
                self.lighting_system.update_light_source(
                    room_id=player.room_id,
                    source_id=f"item_{found_item_id}",
                    source_type="item",
                    intensity=template.light_intensity,
                    expires_at=expires_at
                )
                
                if template.light_duration:
                    messages.append(f"{template.name} begins to glow brightly!")
                else:
                    messages.append(f"{template.name} illuminates the area.")
            
            # Emit stat update event (reuse existing pattern from effect system)
            events = [self._msg_to_player(player_id, "\n".join(messages))]
            events.extend(self._emit_stat_update(player_id))
            
            return events
            
        except InventoryError as e:
            return [self._msg_to_player(player_id, str(e))]

    def _unequip(self, player_id: PlayerId, item_name: str) -> List[Event]:
        """Unequip item."""
        from .inventory import unequip_item, InventoryError, find_item_by_name
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        # Check if sleeping
        sleeping_check = self._check_sleeping(player_id)
        if sleeping_check:
            return sleeping_check
        
        player = world.players[player_id]
        
        # Find equipped item
        found_item_id = find_item_by_name(world, player_id, item_name, "equipped")
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't have '{item_name}' equipped.")]
        
        template = world.item_templates[world.items[found_item_id].template_id]
        
        try:
            unequip_item(world, player_id, found_item_id)
            
            messages = [f"You unequip {template.name}."]
            
            # Phase 11: Remove light source if item provided light
            if template.provides_light:
                self.lighting_system.remove_light_source(
                    room_id=player.room_id,
                    source_id=f"item_{found_item_id}"
                )
                messages.append(f"{template.name}'s light fades.")
            
            # Emit stat update event
            events = [self._msg_to_player(player_id, "\n".join(messages))]
            events.extend(self._emit_stat_update(player_id))
            
            return events
            
        except InventoryError as e:
            return [self._msg_to_player(player_id, str(e))]

    def _use(self, player_id: PlayerId, item_name: str) -> List[Event]:
        """Use/consume item. Delegates to EffectSystem for effect handling."""
        from .inventory import find_item_by_name, remove_item_from_inventory
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        # Check if sleeping
        sleeping_check = self._check_sleeping(player_id)
        if sleeping_check:
            return sleeping_check
        
        player = world.players[player_id]
        
        # Find item in inventory
        found_item_id = find_item_by_name(world, player_id, item_name, "inventory")
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't have '{item_name}'.")]
        
        item = world.items[found_item_id]
        template = world.item_templates[item.template_id]
        
        if not template.is_consumable:
            return [self._msg_to_player(player_id, f"You can't consume {template.name}.")]
        
        events = []
        
        # Apply consume effect via EffectSystem
        if template.consume_effect:
            effect_data = template.consume_effect
            
            # Apply instant healing if hot/magnitude specified
            if effect_data.get("magnitude", 0) > 0 and effect_data.get("effect_type") == "hot":
                old_health = player.current_health
                player.current_health = min(
                    player.max_health,
                    player.current_health + effect_data["magnitude"]
                )
                healed = player.current_health - old_health
                if healed > 0:
                    events.append(self._msg_to_player(player_id, f"You heal for {healed} health."))
            
            # Apply ongoing effect if duration > 0 or stat modifiers
            duration = effect_data.get("duration", 0.0)
            stat_mods = effect_data.get("stat_modifiers", {})
            if stat_mods or duration > 0:
                self.effect_system.apply_effect(
                    player_id,
                    effect_data.get("name", "Consumable Effect"),
                    effect_data.get("effect_type", "buff"),
                    duration=duration,
                    stat_modifiers=stat_mods,
                    magnitude=effect_data.get("magnitude", 0),
                    interval=effect_data.get("interval", 0.0),
                )
        
        # Reduce quantity or remove item
        if item.quantity > 1:
            item.quantity -= 1
        else:
            remove_item_from_inventory(world, player_id, found_item_id)
            del world.items[found_item_id]
        
        events.insert(0, self._msg_to_player(player_id, f"You consume {template.name}."))
        events.extend(self._emit_stat_update(player_id))
        
        return events

    def _give(self, player_id: PlayerId, item_name: str, target_name: str) -> List[Event]:
        """Give an item from your inventory to another entity (player or NPC)."""
        from .inventory import find_item_by_name, add_item_to_inventory, InventoryFullError, calculate_inventory_weight
        
        world = self.world
        
        if player_id not in world.players:
            return [self._msg_to_player(player_id, "You have no form. (Player not found)")]
        
        player = world.players[player_id]
        
        # Check if dead
        if not player.is_alive():
            return [self._msg_to_player(player_id, "You can't give items while dead.")]
        
        room = world.rooms[player.room_id]
        
        # Find the item in giver's inventory
        found_item_id = find_item_by_name(world, player_id, item_name, "inventory")
        
        if not found_item_id:
            return [self._msg_to_player(player_id, f"You don't have '{item_name}'.")]
        
        item = world.items[found_item_id]
        template = world.item_templates[item.template_id]
        
        # Can't give equipped items
        if item.is_equipped():
            return [self._msg_to_player(player_id, f"Unequip {template.name} first.")]
        
        # Use unified targeting to find the target entity (player or NPC)
        target, target_type = self._find_targetable_in_room(
            room.id, target_name,
            include_players=True,
            include_npcs=True,
            include_items=False  # Can't give items to items
        )
        
        if not target:
            return [self._msg_to_player(player_id, f"You don't see '{target_name}' here.")]
        
        # Don't give to self
        if target_type == TargetableType.PLAYER and target.id == player_id:
            return [self._msg_to_player(player_id, "You can't give items to yourself.")]
        
        # Handle giving to a player
        if target_type == TargetableType.PLAYER:
            target_player = world.players[target.id]
            
            # Check if target is connected
            if not target_player.is_connected:
                return [self._msg_to_player(player_id, f"{target_player.name} is in stasis and cannot receive items.")]
            
            # Remove from giver's inventory
            player.inventory_items.remove(found_item_id)
            item.player_id = None
            
            # Update giver's inventory metadata
            if player.inventory_meta:
                player.inventory_meta.current_weight = calculate_inventory_weight(world, player_id)
                player.inventory_meta.current_slots = len(player.inventory_items)
            
            # Try to add to target's inventory
            try:
                add_item_to_inventory(world, target.id, found_item_id)
                
                return [
                    self._msg_to_player(player_id, f"You give {template.name} to {target_player.name}."),
                    self._msg_to_player(target.id, f"{player.name} gives you {template.name}."),
                    self._msg_to_room(room.id, f"{player.name} gives {template.name} to {target_player.name}.", exclude={player_id, target.id})
                ]
                
            except InventoryFullError as e:
                # Revert: give item back to giver
                item.player_id = player_id
                player.inventory_items.add(found_item_id)
                if player.inventory_meta:
                    player.inventory_meta.current_weight = calculate_inventory_weight(world, player_id)
                    player.inventory_meta.current_slots = len(player.inventory_items)
                
                return [self._msg_to_player(player_id, f"{target_player.name}'s inventory is full.")]
        
        # Handle giving to an NPC
        elif target_type == TargetableType.NPC:
            npc = world.npcs[target.id]
            npc_template = world.npc_templates.get(npc.template_id)
            display_name = npc.instance_data.get("name_override", npc.name) if npc.instance_data else npc.name
            
            # Remove from giver's inventory  
            player.inventory_items.remove(found_item_id)
            item.player_id = None
            
            # Update giver's inventory metadata
            if player.inventory_meta:
                player.inventory_meta.current_weight = calculate_inventory_weight(world, player_id)
                player.inventory_meta.current_slots = len(player.inventory_items)
            
            # Add to NPC's inventory (NPCs have unlimited inventory for now)
            npc.inventory_items.add(found_item_id)
            
            # Generate NPC response based on type
            npc_response = ""
            if npc_template:
                if npc_template.npc_type == "merchant":
                    npc_response = f'\n{display_name} says "Hmm, interesting. I\'ll take a look at this."'
                elif npc_template.npc_type == "friendly":
                    npc_response = f'\n{display_name} accepts your gift graciously.'
                elif npc_template.npc_type == "hostile":
                    npc_response = f'\n{display_name} snatches the item from your hand.'
                else:
                    npc_response = f'\n{display_name} takes the item.'
            
            return [
                self._msg_to_player(player_id, f"You give {template.name} to {display_name}.{npc_response}"),
                self._msg_to_room(room.id, f"{player.name} gives {template.name} to {display_name}.", exclude={player_id})
            ]
        
        return [self._msg_to_player(player_id, f"You can't give items to that.")]

    # ========== Phase 9: Ability Commands ==========
    
    async def _cast_ability(self, player_id: PlayerId, args: str) -> List[Event]:
        """
        Cast an ability.
        
        Args:
            player_id: The caster
            args: "ability_name [target_name]"
            
        Returns:
            List of events
        """
        events: List[Event] = []
        player = self.world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form.")]
        
        # Check if dead
        if not player.is_alive():
            return [self._msg_to_player(player_id, "You can't use abilities while dead.")]
        
        # Check if sleeping
        sleeping_check = self._check_sleeping(player_id)
        if sleeping_check:
            return sleeping_check
        
        # Parse ability name and optional target
        parts = args.split(maxsplit=1)
        ability_id = parts[0].lower()
        target_name = parts[1] if len(parts) > 1 else ""
        
        # Get ability template
        ability = self.class_system.get_ability(ability_id)
        if not ability:
            return [self._msg_to_player(player_id, f"Unknown ability: {ability_id}")]
        
        # Resolve target if needed
        target_entity = None
        if target_name:
            # Find target in the player's room
            target_entity, target_type = self._find_targetable_in_room(
                player.room_id,
                target_name,
                include_players=True,
                include_npcs=True,
                include_items=False  # Abilities typically target entities, not items
            )
            if not target_entity:
                return [self._msg_to_player(player_id, f"'{target_name}' not found.")]
        
        # Execute ability via AbilityExecutor (now properly async)
        result = await self._execute_ability(player_id, ability_id, target_entity)
        
        if result.success:
            events.append(self._msg_to_player(player_id, result.message))
            
            # Notify room of ability cast
            room = self.world.rooms.get(player.room_id)
            if room:
                events.append(self._msg_to_room(
                    room.id,
                    f"{player.name} casts {ability.name}!",
                    exclude={player_id}
                ))
            
            # Notify targets
            for target_id in result.targets_hit:
                if target_id != player_id:
                    events.append(self._msg_to_player(
                        target_id,
                        f"{player.name} casts {ability.name} on you!"
                    ))
        else:
            events.append(self._msg_to_player(
                player_id,
                f"Cannot cast {ability_id}: {result.error}"
            ))
        
        return events
    
    async def _execute_ability(
        self,
        player_id: PlayerId,
        ability_id: str,
        target_entity: Optional[WorldEntity] = None
    ) -> Any:
        """
        Execute an ability asynchronously.
        
        Args:
            player_id: The caster
            ability_id: The ability to cast
            target_entity: Optional target
            
        Returns:
            AbilityExecutionResult from ability_executor.execute_ability()
        """
        player = self.world.players.get(player_id)
        if not player:
            from app.engine.systems.abilities import AbilityExecutionResult
            return AbilityExecutionResult(
                success=False,
                ability_id=ability_id,
                caster_id=player_id,
                message="",
                error="Player not found"
            )
        
        # Execute ability via AbilityExecutor (properly async now)
        try:
            result = await self.ability_executor.execute_ability(
                player,
                ability_id,
                target_entity=target_entity
            )
            return result
        except Exception as e:
            from app.engine.systems.abilities import AbilityExecutionResult
            import logging
            logging.error(f"Error executing ability: {e}", exc_info=True)
            return AbilityExecutionResult(
                success=False,
                ability_id=ability_id,
                caster_id=player_id,
                message="",
                error=f"Ability execution error: {str(e)}"
            )
    
    def _show_abilities(self, player_id: PlayerId, show_locked: bool = False) -> List[Event]:
        """
        Show the player's learned abilities that are available at their current level.
        
        Args:
            player_id: The player
            show_locked: If True, also show abilities locked by level requirements
            
        Returns:
            List of events
        """
        player = self.world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form.")]
        
        if not player.has_character_sheet():
            return [self._msg_to_player(
                player_id,
                "You haven't chosen a class yet."
            )]
        
        learned = player.get_learned_abilities()
        if not learned:
            return [self._msg_to_player(
                player_id,
                "You haven't learned any abilities yet."
            )]
        
        # Filter abilities by player's current level
        player_level = player.level
        available_abilities = []
        locked_abilities = []
        
        for ability_id in learned:
            ability = self.class_system.get_ability(ability_id)
            if not ability:
                continue
            
            if ability.required_level <= player_level:
                available_abilities.append((ability_id, ability))
            else:
                locked_abilities.append((ability_id, ability))
        
        if not available_abilities:
            return [self._msg_to_player(
                player_id,
                "You haven't unlocked any abilities at your current level yet."
            )]
        
        lines = ["═══ Your Abilities ═══"]
        lines.append(f"Level {player_level}")
        lines.append("")
        
        # Sort by required level, then by name
        available_abilities.sort(key=lambda x: (x[1].required_level, x[1].name))
        
        for ability_id, ability in available_abilities:
            # Get cooldown status
            cooldown = self.ability_executor.get_ability_cooldown(player_id, ability_id)
            cooldown_str = f" [CD: {cooldown:.1f}s]" if cooldown > 0 else ""
            
            # Show required level
            level_str = f" (Lvl {ability.required_level})" if ability.required_level > 1 else ""
            
            # Indicate if it's a spell (requires 'cast') or skill (direct use)
            usage_hint = f" [Use: cast {ability_id}]" if ability.ability_category == "magic" else f" [Use: {ability_id}]"
            
            lines.append(f"{ability.name}{level_str}{cooldown_str}")
            lines.append(f"  {ability.description}{usage_hint}")
            
            # Show costs if any
            if ability.costs:
                costs_str = ", ".join(f"{k}: {v}" for k, v in ability.costs.items())
                lines.append(f"  Cost: {costs_str}")
            
            lines.append("")
        
        # Show locked abilities only if requested
        if show_locked and locked_abilities:
            lines.append("─── Locked Abilities ───")
            lines.append("")
            locked_abilities.sort(key=lambda x: (x[1].required_level, x[1].name))
            
            for ability_id, ability in locked_abilities:
                lines.append(f"🔒 {ability.name} (Requires Level {ability.required_level})")
                lines.append(f"  {ability.description}")
                lines.append("")
        
        # Add helpful hint if there are locked abilities but they're not shown
        if not show_locked and locked_abilities:
            lines.append(f"💡 You have {len(locked_abilities)} locked ability{'ies' if len(locked_abilities) != 1 else 'y'}. Use 'abilities list' to see all.")
        
        return [self._msg_to_player(player_id, "\n".join(lines))]
    
    def _show_resources(self, player_id: PlayerId) -> List[Event]:
        """
        Show the player's character resources (mana, rage, energy, etc).
        
        Args:
            player_id: The player
            
        Returns:
            List of events
        """
        player = self.world.players.get(player_id)
        if not player:
            return [self._msg_to_player(player_id, "You have no form.")]
        
        if not player.has_character_sheet():
            return [self._msg_to_player(
                player_id,
                "You haven't chosen a class yet."
            )]
        
        pools = player.character_sheet.resource_pools
        if not pools:
            return [self._msg_to_player(
                player_id,
                "You have no active resources."
            )]
        
        lines = ["═══ Your Resources ═══"]
        lines.append("")
        
        for resource_id, pool in sorted(pools.items()):
            pct = int((pool.current / pool.max) * 100) if pool.max > 0 else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            lines.append(f"{pool.resource_id.title()}: {pool.current}/{pool.max} [{bar}] {pct}%")
        
        lines.append("")
        
        return [self._msg_to_player(player_id, "\n".join(lines))]