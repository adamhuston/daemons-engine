"""
Faction chat command for faction-wide communication

Commands:
- fchan <message> - Broadcast message to all faction members
- fc <message> - Alias for fchan
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...engine.systems.context import GameContext

Event = dict[str, Any]


class FactionChatCommand:
    """Handler for faction chat commands."""

    def __init__(self, ctx: "GameContext"):
        self.ctx = ctx

    def handle_fchan(self, player_id: str, player_name: str, args: str) -> list[Event]:
        """Broadcast a message to all online faction members."""
        if not args.strip():
            return [
                self.ctx.msg_to_player(
                    player_id, "**Usage:** fchan <message> (or 'fc <message>')"
                )
            ]

        message = args.strip()
        player = self.ctx.world.players.get(player_id)

        if not player:
            return [self.ctx.msg_to_player(player_id, "Error: Player not found.")]

        # Check if player is dead
        if not player.is_alive():
            return [
                self.ctx.msg_to_player(
                    player_id, "The dead cannot use faction chat."
                )
            ]

        # Check if player belongs to a faction
        if not player.faction_id:
            return [
                self.ctx.msg_to_player(
                    player_id,
                    "You are not a member of any faction. Join a faction to use faction chat.",
                )
            ]

        # Get faction info for formatting
        faction_info = None
        if self.ctx.faction_system:
            faction_info = self.ctx.faction_system.get_faction(player.faction_id)

        faction_name = faction_info.name if faction_info else player.faction_id
        faction_color = faction_info.color if faction_info else "#FFFFFF"

        # Find all online players in the same faction
        faction_members = []
        for pid, p in self.ctx.world.players.items():
            # Check if player is online (has active listener)
            if self.ctx.has_listener(pid) and p.faction_id == player.faction_id:
                faction_members.append(pid)

        if not faction_members:
            return [
                self.ctx.msg_to_player(
                    player_id,
                    f"No other [{faction_name}] members are currently online.",
                )
            ]

        events = []

        # Format: [Faction Name] PlayerName: message
        formatted_message = f"[{faction_name}] {player_name}: {message}"

        # Send to all faction members
        for member_id in faction_members:
            if member_id == player_id:
                # Echo to sender with "You say" format
                sender_message = f"[{faction_name}] You: {message}"
                events.append(
                    self.ctx.msg_to_player(
                        player_id,
                        sender_message,
                        payload={"type": "fchan", "color": faction_color},
                    )
                )
            else:
                # Send to other faction members
                events.append(
                    self.ctx.msg_to_player(
                        member_id,
                        formatted_message,
                        payload={"type": "fchan", "color": faction_color},
                    )
                )

        return events


def register_faction_chat_commands(router) -> None:
    """Register faction chat commands with the command router."""

    def cmd_fchan(engine, player_id: str, args: str) -> list[Event]:
        """Handle 'fchan' command."""
        player = engine.ctx.world.players.get(player_id)
        if not player:
            return []

        handler = FactionChatCommand(engine.ctx)
        return handler.handle_fchan(player_id, player.name, args)

    def cmd_fc(engine, player_id: str, args: str) -> list[Event]:
        """Handle 'fc' command (alias for fchan)."""
        return cmd_fchan(engine, player_id, args)

    # Register both commands
    router.register(
        names=["fchan"],
        description="Broadcast message to all faction members",
        usage="fchan <message>",
        category="social",
    )(cmd_fchan)

    router.register(
        names=["fc"],
        description="Broadcast message to all faction members (alias for fchan)",
        usage="fc <message>",
        category="social",
    )(cmd_fc)
