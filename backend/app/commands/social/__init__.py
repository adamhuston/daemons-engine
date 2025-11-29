"""
Social commands - Groups, Tells, Follows, Yells, Clans, Factions
"""

from .group import register_group_commands
from .tell import register_tell_commands
from .follow import register_follow_commands
from .yell import register_yell_commands
from .clan import register_clan_commands
from .faction import register_faction_commands

__all__ = [
    "register_group_commands",
    "register_tell_commands",
    "register_follow_commands",
    "register_yell_commands",
    "register_clan_commands",
    "register_faction_commands",
]
