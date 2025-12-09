# backend/app/engine/behaviors/fauna.py
"""
Fauna-specific behavior scripts for grazing, hunting, and predator avoidance.

These behaviors integrate with the existing NPC AI system and are triggered
on the standard idle/wander tick timers. Fauna NPCs should include these
behaviors in their template's behavior list.

Example NPC template:
    behaviors: ["grazes", "flees_predators", "wanders_sometimes"]
"""
import random

from .base import BehaviorContext, BehaviorResult, BehaviorScript, behavior


# =============================================================================
# Grazing Behavior (Herbivores)
# =============================================================================


@behavior(
    name="grazes",
    description="Herbivore grazes on flora when hungry, reducing hunger",
    priority=30,  # Run before wandering
    defaults={
        "graze_hunger_threshold": 50,  # Start grazing when hunger > this
        "graze_hunger_reduction": 30,  # How much hunger is reduced
        "graze_chance": 0.6,  # Chance to find food
        "idle_enabled": True,
        "idle_interval_min": 10.0,
        "idle_interval_max": 30.0,
    },
)
class Grazes(BehaviorScript):
    """Herbivore grazing behavior."""

    async def on_idle_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        """Check hunger and graze if needed."""
        npc = ctx.npc

        # Get hunger (fauna-specific attribute)
        hunger = getattr(npc, "hunger", None)
        if hunger is None:
            return BehaviorResult.nothing()

        threshold = ctx.config.get("graze_hunger_threshold", 50)
        if hunger <= threshold:
            # Not hungry enough to graze
            return BehaviorResult.nothing()

        # Try to graze
        graze_chance = ctx.config.get("graze_chance", 0.6)
        if random.random() > graze_chance:
            # Couldn't find food, maybe wander to find some
            return BehaviorResult.nothing()

        # Successfully grazed!
        reduction = ctx.config.get("graze_hunger_reduction", 30)
        new_hunger = max(0, hunger - reduction)
        npc.hunger = new_hunger

        return BehaviorResult.was_handled(
            message=f"The {npc.name} grazes contentedly."
        )


# =============================================================================
# Hunting Behavior (Carnivores/Omnivores)
# =============================================================================


@behavior(
    name="hunts",
    description="Carnivore hunts prey when hungry",
    priority=25,  # Run before grazing and wandering
    defaults={
        "hunt_hunger_threshold": 70,  # Start hunting when hunger > this
        "hunt_success_chance": 0.4,  # Chance to catch prey
        "idle_enabled": True,
        "idle_interval_min": 15.0,
        "idle_interval_max": 45.0,
    },
)
class Hunts(BehaviorScript):
    """Carnivore/omnivore hunting behavior."""

    async def on_idle_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        """Check hunger and hunt if needed."""
        npc = ctx.npc

        # Get hunger (fauna-specific attribute)
        hunger = getattr(npc, "hunger", None)
        if hunger is None:
            return BehaviorResult.nothing()

        threshold = ctx.config.get("hunt_hunger_threshold", 70)
        if hunger <= threshold:
            # Not hungry enough to hunt
            return BehaviorResult.nothing()

        # Look for prey in the room
        prey = self._find_prey_in_room(ctx)
        if not prey:
            # No prey found, maybe wander to find some
            return BehaviorResult.nothing()

        # Try to catch prey
        success_chance = ctx.config.get("hunt_success_chance", 0.4)
        if random.random() > success_chance:
            # Prey escaped
            prey_name = prey.name if hasattr(prey, "name") else "prey"
            return BehaviorResult.was_handled(
                message=f"The {npc.name} lunges at the {prey_name} but misses!"
            )

        # Successful hunt!
        prey_name = prey.name if hasattr(prey, "name") else "prey"
        npc.hunger = 0  # Fully fed

        # Mark prey as dead (abstract death for fauna)
        prey.current_health = 0
        if hasattr(prey, "is_dead"):
            prey.is_dead = True

        # Remove prey from room
        room = ctx.get_room()
        if room:
            room.entities.discard(prey.id)

        return BehaviorResult.was_handled(
            message=f"The {npc.name} catches and devours the {prey_name}!"
        )

    def _find_prey_in_room(self, ctx: BehaviorContext) -> object | None:
        """Find potential prey in the room."""
        npc = ctx.npc
        room = ctx.get_room()
        if not room:
            return None

        # Get fauna system from context
        fauna_system = ctx.fauna_system
        if fauna_system is None:
            return None

        # Get this predator's prey tags
        predator_props = fauna_system.get_fauna_properties(npc.template_id)
        if not predator_props or not predator_props.prey_tags:
            return None

        # Find prey in room
        for entity_id in list(room.entities):
            if entity_id == npc.id:
                continue

            prey_npc = ctx.world.npcs.get(entity_id)
            if not prey_npc or not prey_npc.is_alive():
                continue

            prey_props = fauna_system.get_fauna_properties(prey_npc.template_id)
            if not prey_props:
                continue

            # Check if prey matches predator's prey tags
            if any(tag in prey_props.fauna_tags for tag in predator_props.prey_tags):
                return prey_npc

        return None


# =============================================================================
# Flee from Predators Behavior
# =============================================================================


@behavior(
    name="flees_predators",
    description="Flees when predators are nearby",
    priority=10,  # Run first - survival instinct
    defaults={
        "flee_chance": 0.8,  # High chance to flee
    },
)
class FleesPredators(BehaviorScript):
    """Prey animal flees from predators."""

    async def on_idle_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        """Check for predators and flee if found."""
        npc = ctx.npc

        # Get fauna system
        fauna_system = ctx.fauna_system
        if fauna_system is None:
            return BehaviorResult.nothing()

        # Check for predators in room
        predators = self._find_predators_in_room(ctx, fauna_system)
        if not predators:
            return BehaviorResult.nothing()

        # Decide to flee
        flee_chance = ctx.config.get("flee_chance", 0.8)
        if random.random() > flee_chance:
            # Frozen with fear or didn't notice
            return BehaviorResult.nothing()

        # Flee to a random exit
        exit_info = ctx.get_random_exit()
        if not exit_info:
            # Trapped!
            return BehaviorResult.was_handled(
                message=f"The {npc.name} looks around frantically!"
            )

        direction, dest_room = exit_info
        predator = predators[0]
        predator_name = predator.name if hasattr(predator, "name") else "predator"

        return BehaviorResult.move(
            direction=direction,
            room_id=dest_room,
            message=f"The {npc.name} flees {direction} from the {predator_name}!",
        )

    def _find_predators_in_room(self, ctx: BehaviorContext, fauna_system) -> list:
        """Find predators that hunt this creature."""
        npc = ctx.npc
        room = ctx.get_room()
        if not room:
            return []

        # Get this prey's predator tags
        prey_props = fauna_system.get_fauna_properties(npc.template_id)
        if not prey_props or not prey_props.predator_tags:
            return []

        predators = []
        for entity_id in list(room.entities):
            if entity_id == npc.id:
                continue

            pred_npc = ctx.world.npcs.get(entity_id)
            if not pred_npc or not pred_npc.is_alive():
                continue

            pred_props = fauna_system.get_fauna_properties(pred_npc.template_id)
            if not pred_props:
                continue

            # Check if this NPC is a predator of our prey
            if any(tag in pred_props.fauna_tags for tag in prey_props.predator_tags):
                predators.append(pred_npc)

        return predators


# =============================================================================
# Territorial Behavior
# =============================================================================


@behavior(
    name="territorial",
    description="Defends territory aggressively against intruders",
    priority=20,
    defaults={
        "aggro_chance": 0.5,  # Chance to attack intruders
    },
)
class Territorial(BehaviorScript):
    """Territorial creature attacks intruders."""

    async def on_idle_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        """Check for intruders and potentially attack."""
        npc = ctx.npc

        # Get fauna system
        fauna_system = ctx.fauna_system
        if fauna_system is None:
            return BehaviorResult.nothing()

        # Check if this creature is territorial
        fauna_props = fauna_system.get_fauna_properties(npc.template_id)
        if not fauna_props or not fauna_props.territorial:
            return BehaviorResult.nothing()

        # Look for players in room (intruders)
        players_in_room = ctx.get_players_in_room()
        if not players_in_room:
            return BehaviorResult.nothing()

        # Decide to become aggressive
        aggro_chance = ctx.config.get("aggro_chance", 0.5)
        if random.random() > aggro_chance:
            return BehaviorResult.nothing()

        # Growl/warn (actual attack handled by combat system)
        return BehaviorResult.was_handled(
            message=f"The {npc.name} growls menacingly at you!"
        )
