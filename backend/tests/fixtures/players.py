"""
Player factory and builder fixtures.

Provides convenient builders for creating test players with various configurations.
"""

from daemons.engine.world import WorldPlayer


class PlayerBuilder:
    """
    Builder pattern for creating test WorldPlayer instances.

    Usage:
        player = PlayerBuilder().with_name("Alice").with_level(10).as_warrior().build()
    """

    def __init__(self):
        self.data = {
            "id": "test_player",
            "name": "TestPlayer",
            "room_id": "room_center",
            "character_class": "adventurer",
            "level": 1,
            "xp": 0,
            "hp": 100,
            "max_hp": 100,
            "mp": 50,
            "max_mp": 50,
            "strength": 10,
            "dexterity": 10,
            "intelligence": 10,
            "vitality": 10,
            "constitution": 10,
            "wisdom": 10,
            "charisma": 10,
        }

    def with_id(self, player_id: str) -> "PlayerBuilder":
        """Set player ID."""
        self.data["id"] = player_id
        return self

    def with_name(self, name: str) -> "PlayerBuilder":
        """Set player name."""
        self.data["name"] = name
        return self

    def in_room(self, room_id: str) -> "PlayerBuilder":
        """Set player's current room."""
        self.data["room_id"] = room_id
        return self

    def with_level(self, level: int) -> "PlayerBuilder":
        """Set player level and scale HP/MP accordingly."""
        self.data["level"] = level
        self.data["max_hp"] = level * 100
        self.data["hp"] = level * 100
        self.data["max_mp"] = level * 50
        self.data["mp"] = level * 50
        self.data["xp"] = (level - 1) * 1000
        return self

    def with_hp(self, hp: int, max_hp: int | None = None) -> "PlayerBuilder":
        """Set player HP."""
        self.data["hp"] = hp
        if max_hp is not None:
            self.data["max_hp"] = max_hp
        return self

    def with_mp(self, mp: int, max_mp: int | None = None) -> "PlayerBuilder":
        """Set player MP."""
        self.data["mp"] = mp
        if max_mp is not None:
            self.data["max_mp"] = max_mp
        return self

    def with_stats(self, **stats) -> "PlayerBuilder":
        """Set player stats (str, dex, int, vit, con, wis, cha)."""
        stat_mapping = {
            "str": "strength",
            "dex": "dexterity",
            "int": "intelligence",
            "vit": "vitality",
            "con": "constitution",
            "wis": "wisdom",
            "cha": "charisma",
        }

        for short_name, value in stats.items():
            full_name = stat_mapping.get(short_name, short_name)
            if full_name in self.data:
                self.data[full_name] = value

        return self

    def as_warrior(self) -> "PlayerBuilder":
        """Configure as warrior (high STR, CON)."""
        self.data["character_class"] = "warrior"
        self.data["strength"] = 15
        self.data["constitution"] = 14
        self.data["dexterity"] = 8
        self.data["intelligence"] = 6
        return self

    def as_mage(self) -> "PlayerBuilder":
        """Configure as mage (high INT, WIS)."""
        self.data["character_class"] = "mage"
        self.data["intelligence"] = 15
        self.data["wisdom"] = 14
        self.data["strength"] = 6
        self.data["constitution"] = 8
        return self

    def as_rogue(self) -> "PlayerBuilder":
        """Configure as rogue (high DEX, CHA)."""
        self.data["character_class"] = "rogue"
        self.data["dexterity"] = 15
        self.data["charisma"] = 12
        self.data["strength"] = 8
        self.data["constitution"] = 10
        return self

    def as_cleric(self) -> "PlayerBuilder":
        """Configure as cleric (high WIS, CON)."""
        self.data["character_class"] = "cleric"
        self.data["wisdom"] = 15
        self.data["constitution"] = 12
        self.data["intelligence"] = 10
        self.data["strength"] = 8
        return self

    def damaged(self, damage: int) -> "PlayerBuilder":
        """Reduce HP by specified amount."""
        self.data["hp"] = max(0, self.data["hp"] - damage)
        return self

    def at_low_hp(self) -> "PlayerBuilder":
        """Set HP to 25% of max."""
        self.data["hp"] = self.data["max_hp"] // 4
        return self

    def at_full_health(self) -> "PlayerBuilder":
        """Set HP to max."""
        self.data["hp"] = self.data["max_hp"]
        return self

    def build(self) -> WorldPlayer:
        """Build and return the WorldPlayer instance."""
        return WorldPlayer(**self.data)


def create_test_party(
    size: int = 3, start_room: str = "room_center"
) -> list[WorldPlayer]:
    """
    Create a party of test players.

    Args:
        size: Number of players in party
        start_room: Room ID where party starts

    Returns:
        List of WorldPlayer instances
    """
    classes = ["warrior", "mage", "rogue", "cleric"]
    party = []

    for i in range(size):
        builder = PlayerBuilder()
        builder.with_id(f"player_{i}")
        builder.with_name(f"Player{i}")
        builder.in_room(start_room)

        # Assign class based on index
        class_type = classes[i % len(classes)]
        if class_type == "warrior":
            builder.as_warrior()
        elif class_type == "mage":
            builder.as_mage()
        elif class_type == "rogue":
            builder.as_rogue()
        elif class_type == "cleric":
            builder.as_cleric()

        party.append(builder.build())

    return party
