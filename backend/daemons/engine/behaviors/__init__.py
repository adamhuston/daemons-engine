# backend/app/engine/behaviors/__init__.py
"""
Dynamic behavior script loading system.

Behavior scripts are modular AI routines that can be dropped into this directory
and automatically loaded at runtime. Each script defines executable hooks that
get called at specific points in the game loop.

To create a new behavior:
1. Create a new .py file in this directory
2. Import from .base: behavior, BehaviorScript, BehaviorContext, BehaviorResult
3. Use the @behavior decorator to register your behavior class
4. Implement the hooks you need (on_idle_tick, on_wander_tick, on_damaged, etc.)

Example:
    from .base import behavior, BehaviorScript, BehaviorContext, BehaviorResult

    @behavior(
        name="my_custom_behavior",
        description="Does something cool",
        defaults={"my_setting": True}
    )
    class MyCustomBehavior(BehaviorScript):
        async def on_idle_tick(self, ctx: BehaviorContext) -> BehaviorResult:
            if ctx.config.get("my_setting"):
                return BehaviorResult.handled(message="Something cool happens!")
            return BehaviorResult.nothing()
"""
import importlib
import pkgutil
from pathlib import Path
from typing import Any

# Import base classes first (they set up the registry)
from .base import (
    _BEHAVIOR_REGISTRY,
    BehaviorContext,
    BehaviorResult,
    BehaviorScript,
    get_behavior_defaults,
    get_behavior_instance,
)


def _load_behavior_scripts() -> None:
    """
    Dynamically load all behavior script modules from this package.

    Each module should use the @behavior decorator to register its behavior classes.
    """
    package_dir = Path(__file__).parent

    for module_info in pkgutil.iter_modules([str(package_dir)]):
        # Skip private modules and base
        if module_info.name.startswith("_") or module_info.name == "base":
            continue

        try:
            importlib.import_module(f".{module_info.name}", package=__name__)
        except Exception as e:
            print(f"[Behavior] Error loading {module_info.name}: {e}")


def resolve_behaviors(behavior_names: list[str]) -> dict[str, Any]:
    """
    Resolve a list of behavior names into a merged configuration dict.

    This merges the defaults from all specified behaviors, with later
    behaviors overriding earlier ones for conflicting keys.
    """
    return get_behavior_defaults(behavior_names)


def get_behavior_instances(behavior_names: list[str]) -> list[BehaviorScript]:
    """
    Get instances of all specified behaviors, sorted by priority.

    Lower priority values run first.
    """
    instances = []
    for name in behavior_names:
        instance = get_behavior_instance(name)
        if instance:
            instances.append(instance)
        else:
            print(f"[Behavior] Warning: Unknown behavior '{name}'")

    # Sort by priority (lower = runs first)
    instances.sort(key=lambda b: b.priority)
    return instances


def get_all_tags() -> list[str]:
    """Return a list of all available behavior tag names."""
    return sorted(_BEHAVIOR_REGISTRY.keys())


# For backwards compatibility with world.py imports
BEHAVIOR_SCRIPTS = _BEHAVIOR_REGISTRY
DEFAULT_BEHAVIOR: dict[str, Any] = {
    # Wandering
    "wander_enabled": False,
    "wander_chance": 0.1,
    "wander_interval_min": 30.0,
    "wander_interval_max": 90.0,
    # Idle/chatter
    "idle_enabled": True,
    "idle_chance": 0.3,
    "idle_interval_min": 15.0,
    "idle_interval_max": 45.0,
    # Combat/aggro
    "aggro_on_sight": False,
    "attacks_first": False,
    "attacks_if_attacked": True,
    # Flee
    "flees_at_health_percent": 0,
    # Social
    "calls_for_help": False,
    # Special
    "is_merchant": False,
    "attacks_hostiles_on_sight": False,
    "returns_to_spawn": False,
}


# Load all behavior scripts on import
_load_behavior_scripts()

# Export public API
__all__ = [
    "BehaviorContext",
    "BehaviorResult",
    "BehaviorScript",
    "get_behavior_instances",
    "get_behavior_instance",
    "get_behavior_defaults",
    "resolve_behaviors",
    "get_all_tags",
    "BEHAVIOR_SCRIPTS",
    "DEFAULT_BEHAVIOR",
]
