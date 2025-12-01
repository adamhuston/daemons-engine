# backend/app/engine/behaviors/idle.py
"""Idle behavior scripts - control NPC chatter and ambient messages."""
import random

from .base import BehaviorContext, BehaviorResult, BehaviorScript, behavior


@behavior(
    name="talkative",
    description="NPC frequently says idle messages",
    priority=100,
    defaults={
        "idle_enabled": True,
        "idle_chance": 0.4,
        "idle_interval_min": 10.0,
        "idle_interval_max": 30.0,
    },
)
class Talkative(BehaviorScript):
    async def on_idle_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        if not ctx.config.get("idle_enabled", True):
            return BehaviorResult.nothing()

        chance = ctx.config.get("idle_chance", 0.4)
        if random.random() > chance:
            return BehaviorResult.nothing()

        # Get idle messages from template
        messages = ctx.template.idle_messages if ctx.template else []
        if not messages:
            return BehaviorResult.nothing()

        message = random.choice(messages)
        return BehaviorResult.handled(message=message)


@behavior(
    name="chatty",
    description="NPC occasionally says idle messages",
    priority=100,
    defaults={
        "idle_enabled": True,
        "idle_chance": 0.3,
        "idle_interval_min": 15.0,
        "idle_interval_max": 45.0,
    },
)
class Chatty(BehaviorScript):
    async def on_idle_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        if not ctx.config.get("idle_enabled", True):
            return BehaviorResult.nothing()

        chance = ctx.config.get("idle_chance", 0.3)
        if random.random() > chance:
            return BehaviorResult.nothing()

        messages = ctx.template.idle_messages if ctx.template else []
        if not messages:
            return BehaviorResult.nothing()

        message = random.choice(messages)
        return BehaviorResult.handled(message=message)


@behavior(
    name="quiet",
    description="NPC rarely says idle messages",
    priority=100,
    defaults={
        "idle_enabled": True,
        "idle_chance": 0.15,
        "idle_interval_min": 30.0,
        "idle_interval_max": 90.0,
    },
)
class Quiet(BehaviorScript):
    async def on_idle_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        if not ctx.config.get("idle_enabled", True):
            return BehaviorResult.nothing()

        chance = ctx.config.get("idle_chance", 0.15)
        if random.random() > chance:
            return BehaviorResult.nothing()

        messages = ctx.template.idle_messages if ctx.template else []
        if not messages:
            return BehaviorResult.nothing()

        message = random.choice(messages)
        return BehaviorResult.handled(message=message)


@behavior(
    name="silent",
    description="NPC never says idle messages",
    priority=50,  # Higher priority to suppress other idle behaviors
    defaults={
        "idle_enabled": False,
        "idle_chance": 0.0,
    },
)
class Silent(BehaviorScript):
    async def on_idle_tick(self, ctx: BehaviorContext) -> BehaviorResult:
        # Explicitly handled - we say nothing
        return BehaviorResult.handled()
