"""
Faction commands for Phase 10.3

Commands:
- faction list - List all factions
- faction info <name> - Show faction info and your standing
- faction join <name> - Join a faction
- faction leave <name> - Leave a faction
- faction standing - Show your standings with all factions
"""

from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from ...engine.systems.context import GameContext

Event = Dict[str, Any]


class FactionCommand:
    """Handler for faction-related commands."""

    def __init__(self, ctx: "GameContext"):
        self.ctx = ctx

    def handle_list(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """List all joinable factions."""
        faction_system = self.ctx.faction_system

        factions = faction_system.list_factions(player_joinable_only=True)

        if not factions:
            return [self.ctx.msg_to_player(player_id, "No factions available to join.")]

        faction_list = "**Available Factions:**\n"
        for faction in factions:
            faction_list += f"  • {faction.name} {faction.emblem}\n"
            faction_list += f"    Requires Level {faction.require_level}\n"
            if faction.description:
                faction_list += f"    {faction.description}\n"

        return [self.ctx.msg_to_player(player_id, faction_list)]

    def handle_info(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Show detailed faction info and player's standing."""
        if not args.strip():
            return [self.ctx.msg_to_player(player_id, "**Usage:** faction info <name>")]

        faction_name = args.strip()
        faction_system = self.ctx.faction_system

        faction = faction_system.get_faction_by_name(faction_name)
        if not faction:
            return [
                self.ctx.msg_to_player(
                    player_id, f"Faction '{faction_name}' not found."
                )
            ]

        # Get player's standing
        standing = faction_system.get_standing(player_id, faction.faction_id)

        info_text = f"**{faction.name}** {faction.emblem}\n" f"Color: {faction.color}\n"

        if faction.description:
            info_text += f"Description: {faction.description}\n"

        info_text += (
            f"Requires Level: {faction.require_level}\n"
            f"\n**Your Standing:**\n"
            f"Reputation: {faction_system.format_standing(standing.standing)}\n"
            f"Alignment: {faction_system.get_tier_emoji(standing.tier)} {standing.tier.title()}\n"
        )

        return [self.ctx.msg_to_player(player_id, info_text)]

    def handle_join(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Join a faction."""
        if not args.strip():
            return [self.ctx.msg_to_player(player_id, "**Usage:** faction join <name>")]

        faction_name = args.strip()
        faction_system = self.ctx.faction_system
        player = self.ctx.world.players[player_id]

        faction = faction_system.get_faction_by_name(faction_name)
        if not faction:
            return [
                self.ctx.msg_to_player(
                    player_id, f"Faction '{faction_name}' not found."
                )
            ]

        if not faction.player_joinable:
            return [
                self.ctx.msg_to_player(
                    player_id, f"You cannot join '{faction.name}' (NPC-only faction)."
                )
            ]

        if player.level < faction.require_level:
            return [
                self.ctx.msg_to_player(
                    player_id,
                    f"You must be level {faction.require_level} to join '{faction.name}'. You are level {player.level}.",
                )
            ]

        # Check if already member
        standing = faction_system.get_standing(player_id, faction.faction_id)
        if standing.joined_at is not None:
            return [
                self.ctx.msg_to_player(
                    player_id, f"You are already a member of '{faction.name}'."
                )
            ]

        try:
            import asyncio

            asyncio.run(faction_system.join_faction(player_id, faction.faction_id))

            # Update joined_at timestamp
            import time

            standing.joined_at = time.time()

            return [
                self.ctx.msg_to_player(
                    player_id,
                    f"You have joined '{faction.name}'! {faction.emblem}\n"
                    f"You begin as a neutral member.",
                )
            ]
        except ValueError as e:
            return [self.ctx.msg_to_player(player_id, f"Error: {str(e)}")]

    def handle_leave(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Leave a faction."""
        if not args.strip():
            return [
                self.ctx.msg_to_player(player_id, "**Usage:** faction leave <name>")
            ]

        faction_name = args.strip()
        faction_system = self.ctx.faction_system

        faction = faction_system.get_faction_by_name(faction_name)
        if not faction:
            return [
                self.ctx.msg_to_player(
                    player_id, f"Faction '{faction_name}' not found."
                )
            ]

        standing = faction_system.get_standing(player_id, faction.faction_id)
        if standing.joined_at is None:
            return [
                self.ctx.msg_to_player(
                    player_id, f"You are not a member of '{faction.name}'."
                )
            ]

        try:
            import asyncio

            asyncio.run(faction_system.leave_faction(player_id, faction.faction_id))

            # Clear joined_at but keep standing for rejoining
            standing.joined_at = None

            return [
                self.ctx.msg_to_player(player_id, f"You have left '{faction.name}'.")
            ]
        except ValueError as e:
            return [self.ctx.msg_to_player(player_id, f"Error: {str(e)}")]

    def handle_standing(
        self, player_id: str, player_name: str, args: str
    ) -> List[Event]:
        """Show player's standing with all factions."""
        faction_system = self.ctx.faction_system

        standings = faction_system.get_player_standings(player_id)

        if not standings:
            return [
                self.ctx.msg_to_player(
                    player_id, "You have not joined any factions yet."
                )
            ]

        standing_text = "**Your Faction Standing:**\n"
        for faction_id, standing in standings.items():
            faction = faction_system.get_faction(faction_id)
            if faction:
                emoji = faction_system.get_tier_emoji(standing.tier)
                standing_text += (
                    f"  {emoji} {faction.name}: {faction_system.format_standing(standing.standing)} "
                    f"({standing.tier.title()})\n"
                )

        return [self.ctx.msg_to_player(player_id, standing_text)]


def register_faction_commands(router) -> None:
    """Register all faction commands with the command router."""

    def cmd_faction(engine, player_id: str, args: str) -> List[Event]:
        """Handle 'faction' command with subcommands."""
        player = engine.ctx.world.players.get(player_id)
        if not player:
            return []

        handler = FactionCommand(engine.ctx)

        # Parse subcommand
        parts = args.split(" ", 1) if args else []
        subcommand = parts[0].lower() if parts else "list"
        subargs = parts[1] if len(parts) > 1 else ""

        if subcommand == "list":
            return handler.handle_list(player_id, player.name, subargs)
        elif subcommand == "info":
            return handler.handle_info(player_id, player.name, subargs)
        elif subcommand == "join":
            return handler.handle_join(player_id, player.name, subargs)
        elif subcommand == "leave":
            return handler.handle_leave(player_id, player.name, subargs)
        elif subcommand == "standing":
            return handler.handle_standing(player_id, player.name, subargs)
        else:
            return [
                engine.ctx.msg_to_player(
                    player_id,
                    f"Unknown faction subcommand: {subcommand}. Use: list|info|join|leave|standing",
                )
            ]

    # Register with router
    router.register(
        names=["faction"],
        category="social",
        description="Manage faction standings and memberships",
        usage="faction <list|info|join|leave|standing>",
    )(cmd_faction)
