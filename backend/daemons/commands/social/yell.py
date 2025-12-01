"""
Yell command for Phase 10.1

Commands:
- yell <message> - Broadcast to current and adjacent rooms
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...engine.systems.context import GameContext

Event = dict[str, Any]


class YellCommand:
    """Handler for yell command."""

    def __init__(self, ctx: "GameContext"):
        self.ctx = ctx

    def handle_yell(self, player_id: str, player_name: str, args: str) -> list[Event]:
        """Broadcast a message to current room and adjacent rooms."""
        if not args.strip():
            return [self.ctx.msg_to_player(player_id, "**Usage:** yell <message>")]

        message = args.strip()
        player = self.ctx.world.players[player_id]

        # Check if dead
        if not player.is_alive():
            return [self.ctx.msg_to_player(player_id, "The dead cannot yell.")]

        room_id = player.room_id
        room = self.ctx.world.rooms.get(room_id)

        if not room:
            return [self.ctx.msg_to_player(player_id, "Error: Current room not found.")]

        # Collect room IDs: current room + all adjacent rooms
        room_ids_to_notify = {room_id}

        # Add adjacent rooms from exits
        for direction, adjacent_room_id in room.exits.items():
            if adjacent_room_id:
                room_ids_to_notify.add(adjacent_room_id)

        events = []

        # Create yell events for each room
        for rid in room_ids_to_notify:
            if rid == room_id:
                # Current room: show it's from this player
                msg = f"{player_name} yells: {message}"
            else:
                # Adjacent rooms: show it's from nearby
                msg = f"You hear {player_name} yelling from nearby: {message}"

            event = self.ctx.msg_to_room(
                rid,
                msg,
                exclude=(
                    {player_id} if rid == room_id else set()
                ),  # Don't send to yeller in their own room
            )
            events.append(event)

        # Send feedback to yeller
        events.insert(0, self.ctx.msg_to_player(player_id, f"You yell: {message}"))

        return events


def register_yell_commands(router) -> None:
    """Register yell command with the command router."""

    def cmd_yell(engine, player_id: str, args: str) -> list[Event]:
        """Handle 'yell' command."""
        player = engine.ctx.world.players.get(player_id)
        if not player:
            return []

        handler = YellCommand(engine.ctx)
        return handler.handle_yell(player_id, player.name, args)

    # Register with router
    router.register(
        names=["yell"],
        category="social",
        description="Broadcast a message to current and adjacent rooms",
        usage="yell <message>",
    )(cmd_yell)
