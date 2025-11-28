"""
EffectSystem: Manages temporary buffs, debuffs, and damage-over-time effects.

Handles:
- Effect application and removal
- Stat modifier application
- Duration tracking and expiration
- Periodic damage/healing (DoT/HoT)
- Event dispatch for effect messages
"""

import uuid
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .context import GameContext
    from ..world import EntityId, WorldEntity, Effect
else:
    # At runtime, we import these to avoid circular dependencies
    pass

# Type alias for events
Event = Dict[str, Any]


@dataclass
class EffectConfig:
    """Tunable effect parameters."""
    default_buff_duration: float = 30.0
    default_debuff_duration: float = 15.0
    default_dot_tick_interval: float = 3.0


class EffectSystem:
    """
    Manages application, tracking, and expiration of temporary effects (buffs/debuffs/DoT).
    
    Uses GameContext for:
    - world: entity access
    - time_manager: effect scheduling
    - event_dispatcher: event routing
    """
    
    def __init__(self, ctx: 'GameContext', config: Optional[EffectConfig] = None):
        self.ctx = ctx
        self.config = config or EffectConfig()
    
    def apply_effect(
        self,
        entity_id: 'EntityId',
        effect_name: str,
        effect_type: str,
        duration: float = 0.0,
        stat_modifiers: Optional[Dict[str, int]] = None,
        magnitude: int = 0,
        interval: float = 0.0,
        caster_id: Optional['EntityId'] = None,
    ) -> Optional[str]:
        """
        Apply an effect to an entity and schedule expiration.
        
        Args:
            entity_id: Target entity ID
            effect_name: Human-readable effect name (e.g., "Blessed", "Poisoned")
            effect_type: Effect category (buff, debuff, dot, hot)
            duration: Total duration in seconds (0 = permanent until removed)
            stat_modifiers: Dict of stat changes (e.g., {"armor_class": 5})
            magnitude: Periodic damage/healing per tick (0 = no periodic effect)
            interval: Seconds between periodic ticks
            caster_id: Optional ID of entity that applied the effect
        
        Returns:
            effect_id of the applied effect, or None if entity not found
        """
        # Import here to avoid circular dependency
        from ..world import Effect
        
        # Find entity
        entity = self._get_entity(entity_id)
        if not entity:
            return None
        
        # Create effect
        effect_id = str(uuid.uuid4())
        effect = Effect(
            effect_id=effect_id,
            name=effect_name,
            effect_type=effect_type,
            stat_modifiers=stat_modifiers or {},
            duration=duration,
            magnitude=magnitude,
            interval=interval,
        )
        
        # Apply effect to entity
        entity.apply_effect(effect)
        
        # Schedule periodic damage/healing if applicable
        if magnitude != 0 and interval > 0:
            periodic_event_id = self.ctx.time_manager.schedule_event(
                delay_seconds=interval,
                callback=self._make_periodic_tick_callback(entity_id, effect_id, magnitude),
                recurring=True,
            )
            effect.periodic_event_id = periodic_event_id
        
        # Schedule effect expiration if duration > 0
        if duration > 0:
            expiration_event_id = self.ctx.time_manager.schedule_event(
                delay_seconds=duration,
                callback=self._make_expiration_callback(entity_id, effect_id, effect_name),
            )
            effect.expiration_event_id = expiration_event_id
        
        return effect_id
    
    def remove_effect(self, entity_id: 'EntityId', effect_id: str) -> Optional['Effect']:
        """
        Remove an effect from an entity and cancel its scheduled events.
        
        Returns:
            The removed effect, or None if not found
        """
        entity = self._get_entity(entity_id)
        if not entity:
            return None
        
        effect = entity.active_effects.get(effect_id)
        if not effect:
            return None
        
        # Cancel periodic damage/healing
        if effect.periodic_event_id:
            self.ctx.time_manager.cancel_event(effect.periodic_event_id)
        
        # Cancel expiration timer
        if effect.expiration_event_id:
            self.ctx.time_manager.cancel_event(effect.expiration_event_id)
        
        # Remove from entity
        entity.remove_effect(effect_id)
        
        return effect
    
    def apply_blessing(
        self,
        target_id: 'EntityId',
        bonus: int = 5,
        duration: float = 30.0,
    ) -> List[Event]:
        """
        Apply a blessing buff (armor class bonus) to a target.
        
        Returns list of events:
        - Stat update for player targets
        - Message to target
        - Confirmation to caster
        - Room broadcast
        """
        events: List[Event] = []
        
        target = self._get_entity(target_id)
        if not target:
            return events
        
        # Apply effect
        effect_id = self.apply_effect(
            target_id,
            "Blessed",
            "buff",
            duration=duration,
            stat_modifiers={"armor_class": bonus},
        )
        
        if not effect_id:
            return events
        
        # Generate events
        if target_id in self.ctx.world.players:
            # Stat update for player
            player = self.ctx.world.players[target_id]
            events.append(self.ctx._stat_update_to_player(
                target_id,
                {"armor_class": player.get_effective_armor_class()}
            ))
            
            # Message to target
            events.append(self.ctx._msg_to_player(
                target_id,
                f"✨ *Divine light surrounds you!* You feel blessed. (+{bonus} Armor Class for {duration:.0f} seconds)"
            ))
        
        return events
    
    def apply_poison(
        self,
        target_id: 'EntityId',
        damage_per_tick: int = 5,
        tick_interval: float = 3.0,
        duration: float = 15.0,
    ) -> List[Event]:
        """
        Apply a poison debuff (damage-over-time) to a target.
        
        Returns list of events:
        - Message to target
        - Confirmation to caster
        - Room broadcast
        """
        events: List[Event] = []
        
        target = self._get_entity(target_id)
        if not target:
            return events
        
        # Apply effect
        effect_id = self.apply_effect(
            target_id,
            "Poisoned",
            "dot",
            duration=duration,
            magnitude=damage_per_tick,
            interval=tick_interval,
        )
        
        if not effect_id:
            return events
        
        # Generate events
        if target_id in self.ctx.world.players:
            events.append(self.ctx._msg_to_player(
                target_id,
                f"🤢 *Vile toxins course through your body!* You are poisoned. ({damage_per_tick} damage every {tick_interval:.1f} seconds for {duration:.1f} seconds)"
            ))
        
        return events
    
    def get_active_effects(self, entity_id: 'EntityId') -> List['Effect']:
        """Get list of all active effects on an entity."""
        entity = self._get_entity(entity_id)
        if not entity:
            return []
        return list(entity.active_effects.values())
    
    def get_effect_summary(self, entity_id: 'EntityId') -> str:
        """Get formatted summary of active effects for display."""
        effects = self.get_active_effects(entity_id)
        
        if not effects:
            return "You have no active effects."
        
        lines = ["═══ Active Effects ═══", ""]
        
        for effect in effects:
            remaining = effect.get_remaining_duration()
            lines.append(f"**{effect.name}** ({effect.effect_type})")
            lines.append(f"  Duration: {remaining:.1f}s remaining")
            
            if effect.stat_modifiers:
                mods = ", ".join(
                    [f"{stat} {value:+d}" for stat, value in effect.stat_modifiers.items()]
                )
                lines.append(f"  Modifiers: {mods}")
            
            if effect.magnitude != 0:
                lines.append(f"  Periodic: {effect.magnitude:+d} HP every {effect.interval:.1f}s")
            
            lines.append("")
        
        return "\n".join(lines)
    
    # =========================================================================
    # Private helpers
    # =========================================================================
    
    def _get_entity(self, entity_id: 'EntityId') -> Optional['WorldEntity']:
        """Get entity by ID from world."""
        return self.ctx.world.players.get(entity_id) or self.ctx.world.npcs.get(entity_id)
    
    def _make_periodic_tick_callback(
        self,
        entity_id: 'EntityId',
        effect_id: str,
        magnitude: int,
    ) -> Callable:
        """
        Factory method that creates a periodic tick callback for an effect.
        
        Returns an async function that can be called by the time manager.
        """
        async def tick_callback():
            entity = self._get_entity(entity_id)
            if not entity or effect_id not in entity.active_effects:
                return
            
            effect = entity.active_effects[effect_id]
            
            # Apply damage or healing
            old_health = entity.current_health
            entity.current_health = max(1, entity.current_health - magnitude)
            actual_change = old_health - entity.current_health
            
            # Generate event for players
            if entity_id in self.ctx.world.players:
                if magnitude > 0:
                    # Damage
                    message = f"🤢 *The poison burns through your veins!* You take {actual_change} poison damage."
                else:
                    # Healing
                    message = f"💚 *Healing energy flows through you!* You heal for {actual_change} health."
                
                await self.ctx.event_dispatcher.dispatch([
                    self.ctx._msg_to_player(entity_id, message)
                ])
                
                # Send stat update
                await self.ctx.event_dispatcher.dispatch([
                    self.ctx._stat_update_to_player(
                        entity_id,
                        {
                            "current_health": entity.current_health,
                            "max_health": entity.max_health,
                        }
                    )
                ])
        
        return tick_callback
    
    def _make_expiration_callback(
        self,
        entity_id: 'EntityId',
        effect_id: str,
        effect_name: str,
    ) -> Callable:
        """
        Factory method that creates an effect expiration callback.
        
        Returns an async function that can be called by the time manager.
        """
        async def expiration_callback():
            entity = self._get_entity(entity_id)
            if not entity:
                return
            
            effect = entity.active_effects.get(effect_id)
            if not effect:
                return
            
            # Cancel periodic effect if active
            if effect.periodic_event_id:
                self.ctx.time_manager.cancel_event(effect.periodic_event_id)
            
            # Remove effect
            entity.remove_effect(effect_id)
            
            # Generate expiration message for players
            if entity_id in self.ctx.world.players:
                if effect.effect_type == "dot":
                    message = f"🧪 The poison has run its course."
                elif effect.effect_type == "hot":
                    message = f"💚 The healing effect fades."
                elif effect.effect_type == "buff":
                    message = f"✨ The {effect_name} fades away."
                else:
                    message = f"{effect_name} wears off."
                
                await self.ctx.event_dispatcher.dispatch([
                    self.ctx._msg_to_player(entity_id, message)
                ])
                
                # Send stat update for buff/debuff effects
                if effect.stat_modifiers:
                    entity = self.ctx.world.players[entity_id]
                    await self.ctx.event_dispatcher.dispatch([
                        self.ctx._stat_update_to_player(
                            entity_id,
                            {"armor_class": entity.get_effective_armor_class()}
                        )
                    ])
        
        return expiration_callback
