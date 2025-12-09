"""
Phase 17.6: Spawn Conditions System

Evaluates environmental conditions for NPC and fauna spawning.

Spawn conditions include:
- Time of day requirements
- Temperature ranges
- Weather conditions
- Season restrictions
- Biome matching
- Light levels
- Population limits
- Flora/fauna dependencies

Design Decisions (see Phase17_implementation.md):
- Single adjustable tick interval for performance tuning
- Extensible condition system for future additions
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from daemons.engine.systems.biome import BiomeSystem
    from daemons.engine.systems.fauna import FaunaSystem
    from daemons.engine.systems.flora import FloraSystem
    from daemons.engine.systems.temperature import TemperatureSystem
    from daemons.engine.systems.time_manager import TimeManager
    from daemons.engine.systems.weather import WeatherSystem
    from daemons.engine.world import World, WorldArea, WorldRoom

logger = logging.getLogger(__name__)


# === Dataclasses ===


@dataclass
class SpawnConditions:
    """
    Parsed spawn conditions from YAML spawn definitions.

    All conditions are optional - only specified conditions are evaluated.
    """

    # Time conditions
    time_of_day: Optional[list[str]] = None  # dawn, day, dusk, night

    # Temperature conditions
    temperature_min: Optional[int] = None
    temperature_max: Optional[int] = None
    temperature_range: Optional[tuple[int, int]] = None

    # Weather conditions
    weather_is: Optional[list[str]] = None  # Must be one of these
    weather_not: Optional[list[str]] = None  # Must not be any of these
    weather_intensity_min: Optional[float] = None
    weather_intensity_max: Optional[float] = None

    # Season conditions
    season_is: Optional[list[str]] = None  # spring, summer, fall, winter
    season_not: Optional[list[str]] = None

    # Biome conditions
    biome_is: Optional[list[str]] = None  # Must be one of these biome types
    biome_match: bool = False  # NPC's biome_tags must match room's biome

    # Light conditions
    light_level_min: Optional[int] = None  # 0-100
    light_level_max: Optional[int] = None

    # Population conditions
    max_in_area: Optional[int] = None  # Cap for this template in area
    max_in_room: Optional[int] = None  # Cap for this template in room

    # Dependency conditions
    requires_flora: Optional[list[str]] = None  # Flora must be present
    requires_fauna: Optional[list[str]] = None  # Fauna (prey) must be present
    excludes_fauna: Optional[list[str]] = None  # Fauna (predators) must not be present

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpawnConditions":
        """Parse spawn conditions from YAML data."""
        if not data:
            return cls()

        # Handle temperature range
        temp_range = None
        if "temperature_range" in data and isinstance(data["temperature_range"], list):
            temp_range = tuple(data["temperature_range"][:2])
        elif data.get("temperature_min") or data.get("temperature_max"):
            temp_range = (
                data.get("temperature_min", -100),
                data.get("temperature_max", 200),
            )

        return cls(
            time_of_day=data.get("time_of_day"),
            temperature_min=data.get("temperature_min"),
            temperature_max=data.get("temperature_max"),
            temperature_range=temp_range,
            weather_is=data.get("weather_is"),
            weather_not=data.get("weather_not"),
            weather_intensity_min=data.get("weather_intensity_min"),
            weather_intensity_max=data.get("weather_intensity_max"),
            season_is=data.get("season_is"),
            season_not=data.get("season_not"),
            biome_is=data.get("biome_is"),
            biome_match=data.get("biome_match", False),
            light_level_min=data.get("light_level_min"),
            light_level_max=data.get("light_level_max"),
            max_in_area=data.get("max_in_area"),
            max_in_room=data.get("max_in_room"),
            requires_flora=data.get("requires_flora"),
            requires_fauna=data.get("requires_fauna"),
            excludes_fauna=data.get("excludes_fauna"),
        )

    def has_conditions(self) -> bool:
        """Check if any conditions are specified."""
        return any(
            [
                self.time_of_day,
                self.temperature_range,
                self.weather_is,
                self.weather_not,
                self.season_is,
                self.season_not,
                self.biome_is,
                self.biome_match,
                self.light_level_min is not None,
                self.light_level_max is not None,
                self.max_in_area is not None,
                self.max_in_room is not None,
                self.requires_flora,
                self.requires_fauna,
                self.excludes_fauna,
            ]
        )


@dataclass
class EvaluationResult:
    """Result of condition evaluation."""

    can_spawn: bool
    failed_conditions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_allowed(self) -> bool:
        """Alias for can_spawn for clarity."""
        return self.can_spawn


# === Spawn Condition Evaluator ===


class SpawnConditionEvaluator:
    """
    Evaluates spawn conditions against current environment.

    Integrates with all environmental systems to determine
    if spawn conditions are met.
    """

    def __init__(
        self,
        world: "World",
        time_manager: Optional["TimeManager"] = None,
        temperature_system: Optional["TemperatureSystem"] = None,
        weather_system: Optional["WeatherSystem"] = None,
        biome_system: Optional["BiomeSystem"] = None,
        flora_system: Optional["FloraSystem"] = None,
        fauna_system: Optional["FaunaSystem"] = None,
    ):
        self.world = world
        self.time_manager = time_manager
        self.temperature_system = temperature_system
        self.weather_system = weather_system
        self.biome_system = biome_system
        self.flora_system = flora_system
        self.fauna_system = fauna_system

        logger.info("SpawnConditionEvaluator initialized")

    async def evaluate(
        self,
        conditions: SpawnConditions,
        room_id: str,
        area_id: str,
        template_id: str,
        session: "AsyncSession",
    ) -> EvaluationResult:
        """
        Evaluate all spawn conditions for a potential spawn.

        Args:
            conditions: The spawn conditions to evaluate
            room_id: Room where spawn would occur
            area_id: Area containing the room
            template_id: NPC template being spawned
            session: Database session

        Returns:
            EvaluationResult with spawn eligibility and any failed conditions
        """
        failed: list[str] = []
        warnings: list[str] = []

        room = self.world.rooms.get(room_id)
        if not room:
            return EvaluationResult(
                can_spawn=False,
                failed_conditions=["room_not_found"],
            )

        # If no conditions, allow spawn
        if not conditions.has_conditions():
            return EvaluationResult(can_spawn=True)

        # Evaluate each condition type
        failed.extend(self._check_time_conditions(conditions, area_id))
        failed.extend(self._check_temperature_conditions(conditions, room_id, area_id))
        failed.extend(self._check_weather_conditions(conditions, area_id))
        failed.extend(self._check_season_conditions(conditions, area_id))
        failed.extend(self._check_biome_conditions(conditions, area_id, template_id))
        failed.extend(self._check_light_conditions(conditions, room_id, area_id))
        failed.extend(
            await self._check_population_conditions(
                conditions, room_id, area_id, template_id, session
            )
        )
        failed.extend(
            await self._check_dependency_conditions(
                conditions, room_id, session
            )
        )

        return EvaluationResult(
            can_spawn=len(failed) == 0,
            failed_conditions=failed,
            warnings=warnings,
        )

    def _check_time_conditions(
        self, conditions: SpawnConditions, area_id: str
    ) -> list[str]:
        """Check time of day conditions."""
        failed = []

        if not conditions.time_of_day:
            return failed

        if not self.time_manager:
            return failed  # Can't check, allow spawn

        hour = self.time_manager.get_hour()
        current_time = self._get_time_period(hour)

        if current_time not in conditions.time_of_day:
            failed.append(
                f"time_of_day: current={current_time}, required={conditions.time_of_day}"
            )

        return failed

    def _get_time_period(self, hour: int) -> str:
        """Convert hour to time period name."""
        if 5 <= hour < 7:
            return "dawn"
        elif 7 <= hour < 17:
            return "day"
        elif 17 <= hour < 20:
            return "dusk"
        else:
            return "night"

    def _check_temperature_conditions(
        self, conditions: SpawnConditions, room_id: str, area_id: str
    ) -> list[str]:
        """Check temperature conditions."""
        failed = []

        if not conditions.temperature_range:
            return failed

        if not self.temperature_system:
            return failed  # Can't check, allow spawn

        room = self.world.rooms.get(room_id)
        if not room:
            return failed

        temp = self.temperature_system.calculate_room_temperature(room, area_id)
        min_t, max_t = conditions.temperature_range

        if not (min_t <= temp.effective_temperature <= max_t):
            failed.append(
                f"temperature: current={temp.effective_temperature}°F, "
                f"required=[{min_t}, {max_t}]"
            )

        return failed

    def _check_weather_conditions(
        self, conditions: SpawnConditions, area_id: str
    ) -> list[str]:
        """Check weather conditions."""
        failed = []

        if not conditions.weather_is and not conditions.weather_not:
            return failed

        if not self.weather_system:
            return failed  # Can't check, allow spawn

        weather = self.weather_system.get_current_weather(area_id)
        if not weather:
            return failed

        weather_type = getattr(weather, "weather_type", None)
        if not weather_type:
            return failed

        current = weather_type.value if hasattr(weather_type, "value") else str(weather_type)

        if conditions.weather_is and current not in conditions.weather_is:
            failed.append(
                f"weather_is: current={current}, required={conditions.weather_is}"
            )

        if conditions.weather_not and current in conditions.weather_not:
            failed.append(
                f"weather_not: current={current} in excluded list {conditions.weather_not}"
            )

        # Check intensity
        intensity = getattr(weather, "intensity", None)
        if intensity is not None:
            if (
                conditions.weather_intensity_min is not None
                and intensity < conditions.weather_intensity_min
            ):
                failed.append(
                    f"weather_intensity_min: current={intensity}, "
                    f"required>={conditions.weather_intensity_min}"
                )
            if (
                conditions.weather_intensity_max is not None
                and intensity > conditions.weather_intensity_max
            ):
                failed.append(
                    f"weather_intensity_max: current={intensity}, "
                    f"required<={conditions.weather_intensity_max}"
                )

        return failed

    def _check_season_conditions(
        self, conditions: SpawnConditions, area_id: str
    ) -> list[str]:
        """Check season conditions."""
        failed = []

        if not conditions.season_is and not conditions.season_not:
            return failed

        if not self.biome_system:
            return failed  # Can't check, allow spawn

        season = self.biome_system.get_season(area_id)
        if not season:
            return failed

        current = season.value if hasattr(season, "value") else str(season)

        if conditions.season_is and current not in conditions.season_is:
            failed.append(
                f"season_is: current={current}, required={conditions.season_is}"
            )

        if conditions.season_not and current in conditions.season_not:
            failed.append(
                f"season_not: current={current} in excluded list {conditions.season_not}"
            )

        return failed

    def _check_biome_conditions(
        self, conditions: SpawnConditions, area_id: str, template_id: str
    ) -> list[str]:
        """Check biome conditions."""
        failed = []

        if not conditions.biome_is and not conditions.biome_match:
            return failed

        if not self.biome_system:
            return failed  # Can't check, allow spawn

        biome = self.biome_system.get_biome_for_area(area_id)
        if not biome:
            return failed

        biome_type = getattr(biome, "biome_type", None)
        biome_id = biome_type.value if hasattr(biome_type, "value") else str(biome_type)

        # Check explicit biome list
        if conditions.biome_is and biome_id not in conditions.biome_is:
            failed.append(
                f"biome_is: current={biome_id}, required={conditions.biome_is}"
            )

        # Check biome match for fauna
        if conditions.biome_match and self.fauna_system:
            fauna = self.fauna_system.get_fauna_properties(template_id)
            if fauna and fauna.biome_tags:
                biome_fauna_tags = getattr(biome, "fauna_tags", [])
                if not any(tag in biome_fauna_tags for tag in fauna.biome_tags):
                    failed.append(
                        f"biome_match: fauna tags {fauna.biome_tags} "
                        f"not compatible with biome tags {biome_fauna_tags}"
                    )

        return failed

    def _check_light_conditions(
        self, conditions: SpawnConditions, room_id: str, area_id: str
    ) -> list[str]:
        """Check light level conditions."""
        failed = []

        if conditions.light_level_min is None and conditions.light_level_max is None:
            return failed

        # Light level is derived from time and weather
        # Default to 50 (mid-range) if can't determine
        light_level = self._calculate_light_level(room_id, area_id)

        if (
            conditions.light_level_min is not None
            and light_level < conditions.light_level_min
        ):
            failed.append(
                f"light_level_min: current={light_level}, "
                f"required>={conditions.light_level_min}"
            )

        if (
            conditions.light_level_max is not None
            and light_level > conditions.light_level_max
        ):
            failed.append(
                f"light_level_max: current={light_level}, "
                f"required<={conditions.light_level_max}"
            )

        return failed

    def _calculate_light_level(self, room_id: str, area_id: str) -> int:
        """
        Calculate current light level (0-100).

        Based on time of day and weather conditions.
        """
        base_light = 50

        # Adjust for time of day
        if self.time_manager:
            hour = self.time_manager.get_hour()
            if 6 <= hour <= 18:
                # Daylight curve peaking at noon
                base_light = 80 + 20 * (1 - abs(hour - 12) / 6)
            else:
                # Night time
                base_light = 10

        # Adjust for weather
        if self.weather_system:
            weather = self.weather_system.get_current_weather(area_id)
            if weather:
                weather_type = getattr(weather, "weather_type", None)
                if weather_type:
                    weather_value = (
                        weather_type.value
                        if hasattr(weather_type, "value")
                        else str(weather_type)
                    )
                    if weather_value in ["overcast", "storm", "fog"]:
                        base_light = int(base_light * 0.6)
                    elif weather_value == "cloudy":
                        base_light = int(base_light * 0.8)

        # Check room for indoor override
        room = self.world.rooms.get(room_id)
        if room:
            room_type = getattr(room, "room_type", "outdoor")
            if room_type in ["indoor", "underground", "cave"]:
                base_light = 20  # Artificial/ambient light

        return max(0, min(100, base_light))

    async def _check_population_conditions(
        self,
        conditions: SpawnConditions,
        room_id: str,
        area_id: str,
        template_id: str,
        session: "AsyncSession",
    ) -> list[str]:
        """Check population limit conditions."""
        failed = []

        room = self.world.rooms.get(room_id)
        if not room:
            return failed

        # Check room population
        if conditions.max_in_room is not None:
            count = self._count_in_room(template_id, room)
            if count >= conditions.max_in_room:
                failed.append(
                    f"max_in_room: current={count}, max={conditions.max_in_room}"
                )

        # Check area population
        if conditions.max_in_area is not None:
            count = self._count_in_area(template_id, area_id)
            if count >= conditions.max_in_area:
                failed.append(
                    f"max_in_area: current={count}, max={conditions.max_in_area}"
                )

        return failed

    def _count_in_room(self, template_id: str, room: "WorldRoom") -> int:
        """Count NPCs of template in room."""
        count = 0
        npc_ids = getattr(room, "npc_ids", [])

        for npc_id in npc_ids:
            npc = self.world.npcs.get(npc_id)
            if npc and npc.template_id == template_id:
                count += 1

        return count

    def _count_in_area(self, template_id: str, area_id: str) -> int:
        """Count NPCs of template in area."""
        count = 0

        for npc in self.world.npcs.values():
            room = self.world.rooms.get(npc.room_id)
            if room and getattr(room, "area_id", None) == area_id:
                if npc.template_id == template_id:
                    count += 1

        return count

    async def _check_dependency_conditions(
        self,
        conditions: SpawnConditions,
        room_id: str,
        session: "AsyncSession",
    ) -> list[str]:
        """Check flora/fauna dependency conditions."""
        failed = []

        room = self.world.rooms.get(room_id)
        if not room:
            return failed

        # Check required flora
        if conditions.requires_flora and self.flora_system:
            room_flora = await self.flora_system.get_room_flora(room, session)
            flora_ids = {f.template_id for f in room_flora}
            missing = set(conditions.requires_flora) - flora_ids
            if missing:
                failed.append(f"requires_flora: missing {missing}")

        # Check required fauna (prey)
        if conditions.requires_fauna:
            npc_ids = getattr(room, "npc_ids", [])
            room_templates = set()
            for npc_id in npc_ids:
                npc = self.world.npcs.get(npc_id)
                if npc:
                    room_templates.add(npc.template_id)

            missing = set(conditions.requires_fauna) - room_templates
            if missing:
                failed.append(f"requires_fauna: missing {missing}")

        # Check excluded fauna (predators)
        if conditions.excludes_fauna:
            npc_ids = getattr(room, "npc_ids", [])
            room_templates = set()
            for npc_id in npc_ids:
                npc = self.world.npcs.get(npc_id)
                if npc:
                    room_templates.add(npc.template_id)

            present = set(conditions.excludes_fauna) & room_templates
            if present:
                failed.append(f"excludes_fauna: {present} present in room")

        return failed

    # === Batch Evaluation ===

    async def evaluate_all_spawns(
        self,
        spawn_definitions: list[dict[str, Any]],
        area_id: str,
        session: "AsyncSession",
    ) -> dict[str, EvaluationResult]:
        """
        Evaluate conditions for multiple spawn definitions.

        Returns dict mapping template_id to evaluation result.
        """
        results = {}

        for spawn_def in spawn_definitions:
            template_id = spawn_def.get("template_id")
            room_id = spawn_def.get("room_id")
            conditions_data = spawn_def.get("spawn_conditions", {})

            if not template_id or not room_id:
                continue

            conditions = SpawnConditions.from_dict(conditions_data)
            result = await self.evaluate(
                conditions, room_id, area_id, template_id, session
            )

            # Use composite key for multiple spawns of same template
            key = f"{template_id}@{room_id}"
            results[key] = result

        return results
