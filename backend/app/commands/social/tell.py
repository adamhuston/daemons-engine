"""
Tell/private message commands for Phase 10.1

Commands:
- tell <player_name> <message> - Send private message
- reply <message> - Reply to last sender
- ignore <player_name> - Ignore a player's tells
- unignore <player_name> - Stop ignoring a player
"""

from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from ...engine.systems.context import GameContext

Event = Dict[str, Any]


class TellCommand:
    """Handler for tell/private message commands."""

    def __init__(self, ctx: "GameContext"):
        self.ctx = ctx

    def handle_tell(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Send a private message to another player."""
        if not args.strip():
            return [
                self.ctx.msg_to_player(
                    player_id, "**Usage:** tell <player_name> <message>"
                )
            ]

        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            return [
                self.ctx.msg_to_player(
                    player_id, "**Usage:** tell <player_name> <message>"
                )
            ]

        target_name = parts[0]
        message = parts[1]

        # Check if sender is dead
        sender = self.ctx.world.players.get(player_id)
        if sender and not sender.is_alive():
            return [self.ctx.msg_to_player(player_id, "The dead cannot send tells.")]

        # Find target player
        target_id = None
        for pid, p in self.ctx.world.players.items():
            if p.name.lower() == target_name.lower():
                target_id = pid
                break

        if not target_id:
            return [
                self.ctx.msg_to_player(player_id, f"Player '{target_name}' not found.")
            ]

        # Check if target is ignoring sender
        target = self.ctx.world.players[target_id]
        target_flags = target.player_flags or {}
        ignored_list = target_flags.get("ignored_players", [])

        if player_id in ignored_list:
            return [
                self.ctx.msg_to_player(
                    player_id, f"{target.name} is ignoring your tells."
                )
            ]

        # Create tell event
        tell_event = self.ctx.event_dispatcher.tell_message(
            sender_id=player_id,
            sender_name=player_name,
            recipient_id=target_id,
            text=message,
        )

        # Update last_tell_from for reply command
        if not target.player_flags:
            target.player_flags = {}
        target.player_flags["last_tell_from"] = player_id
        target.player_flags["last_tell_from_name"] = player_name

        return [tell_event]

    def handle_reply(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Reply to the last player who sent you a tell."""
        if not args.strip():
            return [self.ctx.msg_to_player(player_id, "**Usage:** reply <message>")]

        player = self.ctx.world.players[player_id]

        # Check if sender is dead
        if not player.is_alive():
            return [self.ctx.msg_to_player(player_id, "The dead cannot send tells.")]

        if not player.player_flags or "last_tell_from" not in player.player_flags:
            return [
                self.ctx.msg_to_player(
                    player_id, "No one has told you anything recently."
                )
            ]

        target_id = player.player_flags["last_tell_from"]
        target_name = player.player_flags.get("last_tell_from_name", "Unknown")

        # Check if target still exists
        if target_id not in self.ctx.world.players:
            return [
                self.ctx.msg_to_player(
                    player_id, f"Player '{target_name}' is no longer online."
                )
            ]

        target = self.ctx.world.players[target_id]

        # Check if target is ignoring sender
        target_flags = target.player_flags or {}
        ignored_list = target_flags.get("ignored_players", [])

        if player_id in ignored_list:
            return [
                self.ctx.msg_to_player(
                    player_id, f"{target.name} is ignoring your tells."
                )
            ]

        message = args.strip()

        # Create tell event
        tell_event = self.ctx.event_dispatcher.tell_message(
            sender_id=player_id,
            sender_name=player_name,
            recipient_id=target_id,
            text=message,
        )

        # Update target's last_tell_from for their reply
        if not target.player_flags:
            target.player_flags = {}
        target.player_flags["last_tell_from"] = player_id
        target.player_flags["last_tell_from_name"] = player_name

        return [tell_event]

    def handle_ignore(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Add a player to the ignore list."""
        if not args.strip():
            return [
                self.ctx.msg_to_player(player_id, "**Usage:** ignore <player_name>")
            ]

        target_name = args.strip()

        # Find target player
        target_id = None
        for pid, p in self.ctx.world.players.items():
            if p.name.lower() == target_name.lower():
                target_id = pid
                break

        if not target_id:
            return [
                self.ctx.msg_to_player(player_id, f"Player '{target_name}' not found.")
            ]

        player = self.ctx.world.players[player_id]
        if not player.player_flags:
            player.player_flags = {}

        ignored_list = player.player_flags.get("ignored_players", [])
        if target_id in ignored_list:
            return [
                self.ctx.msg_to_player(
                    player_id, f"You are already ignoring {target_name}."
                )
            ]

        ignored_list.append(target_id)
        player.player_flags["ignored_players"] = ignored_list

        return [
            self.ctx.msg_to_player(player_id, f"You are now ignoring {target_name}.")
        ]

    def handle_unignore(
        self, player_id: str, player_name: str, args: str
    ) -> List[Event]:
        """Remove a player from the ignore list."""
        if not args.strip():
            return [
                self.ctx.msg_to_player(player_id, "**Usage:** unignore <player_name>")
            ]

        target_name = args.strip()

        # Find target player
        target_id = None
        for pid, p in self.ctx.world.players.items():
            if p.name.lower() == target_name.lower():
                target_id = pid
                break

        if not target_id:
            return [
                self.ctx.msg_to_player(player_id, f"Player '{target_name}' not found.")
            ]

        player = self.ctx.world.players[player_id]
        if not player.player_flags:
            player.player_flags = {}

        ignored_list = player.player_flags.get("ignored_players", [])
        if target_id not in ignored_list:
            return [
                self.ctx.msg_to_player(
                    player_id, f"You are not ignoring {target_name}."
                )
            ]

        ignored_list.remove(target_id)
        player.player_flags["ignored_players"] = ignored_list

        return [
            self.ctx.msg_to_player(
                player_id, f"You are no longer ignoring {target_name}."
            )
        ]


def register_tell_commands(router) -> None:
    """Register all tell commands with the command router."""

    def cmd_tell(engine, player_id: str, args: str) -> List[Event]:
        """Handle 'tell' command."""
        player = engine.ctx.world.players.get(player_id)
        if not player:
            return []

        handler = TellCommand(engine.ctx)
        return handler.handle_tell(player_id, player.name, args)

    def cmd_reply(engine, player_id: str, args: str) -> List[Event]:
        """Handle 'reply' command."""
        player = engine.ctx.world.players.get(player_id)
        if not player:
            return []

        handler = TellCommand(engine.ctx)
        return handler.handle_reply(player_id, player.name, args)

    def cmd_ignore(engine, player_id: str, args: str) -> List[Event]:
        """Handle 'ignore' command."""
        player = engine.ctx.world.players.get(player_id)
        if not player:
            return []

        handler = TellCommand(engine.ctx)
        return handler.handle_ignore(player_id, player.name, args)

    def cmd_unignore(engine, player_id: str, args: str) -> List[Event]:
        """Handle 'unignore' command."""
        player = engine.ctx.world.players.get(player_id)
        if not player:
            return []

        handler = TellCommand(engine.ctx)
        return handler.handle_unignore(player_id, player.name, args)

    # Register with router
    router.register(
        names=["tell", "t"],
        category="social",
        description="Send a private message to a player",
        usage="tell <player_name> <message>",
    )(cmd_tell)

    router.register(
        names=["reply", "r"],
        category="social",
        description="Reply to the last player who sent you a tell",
        usage="reply <message>",
    )(cmd_reply)

    router.register(
        names=["ignore"],
        category="social",
        description="Ignore tells from a player",
        usage="ignore <player_name>",
    )(cmd_ignore)

    router.register(
        names=["unignore"],
        category="social",
        description="Stop ignoring tells from a player",
        usage="unignore <player_name>",
    )(cmd_unignore)
