"""
Group commands for Phase 10.1

Commands:
- group create <name> - Create a new group
- group invite <player_name> - Invite player to group
- group join <group_id> - Join an existing group (if invited)
- group leave - Leave current group
- group members - List group members
- group info - Show group info
- group rename <new_name> - Rename group (leader only)
- group disband - Disband group (leader only)
"""

from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from ...engine.systems.context import GameContext

Event = Dict[str, Any]


class GroupCommand:
    """Handler for group-related commands."""

    def __init__(self, ctx: "GameContext"):
        self.ctx = ctx

    def handle_create(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Create a new group."""
        if not args.strip():
            return [self.ctx.msg_to_player(player_id, "**Usage:** group create <name>")]

        group_name = args.strip()
        group_system = self.ctx.group_system

        # Check if already in a group
        if player_id in group_system.player_to_group:
            return [
                self.ctx.msg_to_player(
                    player_id, "You are already in a group. Leave it first."
                )
            ]

        try:
            group = group_system.create_group(group_name, player_id)
            return [
                self.ctx.msg_to_player(
                    player_id,
                    f"You created group '{group.name}' (ID: {group.group_id})",
                )
            ]
        except ValueError as e:
            return [self.ctx.msg_to_player(player_id, f"Error: {str(e)}")]

    def handle_invite(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Invite a player to the group."""
        if not args.strip():
            return [
                self.ctx.msg_to_player(
                    player_id, "**Usage:** group invite <player_name>"
                )
            ]

        target_name = args.strip()
        group_system = self.ctx.group_system

        # Check if inviter is in a group
        group = group_system.get_player_group(player_id)
        if not group:
            return [self.ctx.msg_to_player(player_id, "You are not in a group.")]

        # Check if inviter is group leader
        if group.leader_id != player_id:
            return [
                self.ctx.msg_to_player(
                    player_id, "Only the group leader can invite players."
                )
            ]

        # Find target player by name
        target_id = None
        for pid, p in self.ctx.world.players.items():
            if p.name == target_name:
                target_id = pid
                break

        if not target_id:
            return [
                self.ctx.msg_to_player(player_id, f"Player '{target_name}' not found.")
            ]

        try:
            group_system.invite_player(group.group_id, target_id)

            events = [
                self.ctx.msg_to_player(
                    player_id, f"You invited {target_name} to the group."
                ),
                self.ctx.msg_to_player(
                    target_id,
                    f"{player_name} invited you to join '{group.name}'. Use 'group join {group.group_id}' to accept.",
                ),
            ]
            return events
        except ValueError as e:
            return [self.ctx.msg_to_player(player_id, f"Error: {str(e)}")]

    def handle_leave(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Leave the current group."""
        group_system = self.ctx.group_system

        group = group_system.get_player_group(player_id)
        if not group:
            return [self.ctx.msg_to_player(player_id, "You are not in a group.")]

        group_id = group_system.remove_player(player_id)

        events = [
            self.ctx.msg_to_player(player_id, f"You left the group '{group.name}'.")
        ]

        # Notify remaining members if group still exists
        if group_id and group_id in group_system.groups:
            group_system.groups[group_id]
            room_event = self.ctx.event_dispatcher.group_message(
                group_id, player_id, player_name, f"{player_name} left the group."
            )
            events.append(room_event)

        return events

    def handle_members(
        self, player_id: str, player_name: str, args: str
    ) -> List[Event]:
        """List group members."""
        group_system = self.ctx.group_system

        group = group_system.get_player_group(player_id)
        if not group:
            return [self.ctx.msg_to_player(player_id, "You are not in a group.")]

        member_names = []
        for mid in group.members:
            member = self.ctx.world.players.get(mid)
            if member:
                member_names.append(
                    f"  {member.name}" + (" (leader)" if mid == group.leader_id else "")
                )

        text = f"**Group '{group.name}' Members:**\n" + "\n".join(member_names)
        return [self.ctx.msg_to_player(player_id, text)]

    def handle_info(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Show group information."""
        group_system = self.ctx.group_system

        group = group_system.get_player_group(player_id)
        if not group:
            return [self.ctx.msg_to_player(player_id, "You are not in a group.")]

        leader = self.ctx.world.players.get(group.leader_id)
        leader_name = leader.name if leader else "Unknown"

        text = (
            f"**Group: {group.name}**\n"
            f"ID: {group.group_id}\n"
            f"Leader: {leader_name}\n"
            f"Members: {group.member_count()}\n"
        )
        return [self.ctx.msg_to_player(player_id, text)]

    def handle_rename(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Rename the group (leader only)."""
        if not args.strip():
            return [
                self.ctx.msg_to_player(player_id, "**Usage:** group rename <new_name>")
            ]

        group_system = self.ctx.group_system

        group = group_system.get_player_group(player_id)
        if not group:
            return [self.ctx.msg_to_player(player_id, "You are not in a group.")]

        if group.leader_id != player_id:
            return [
                self.ctx.msg_to_player(
                    player_id, "Only the group leader can rename the group."
                )
            ]

        new_name = args.strip()
        old_name = group.name

        try:
            group_system.rename_group(group.group_id, new_name)
            return [
                self.ctx.msg_to_player(
                    player_id, f"Renamed group from '{old_name}' to '{new_name}'."
                )
            ]
        except ValueError as e:
            return [self.ctx.msg_to_player(player_id, f"Error: {str(e)}")]

    def handle_disband(
        self, player_id: str, player_name: str, args: str
    ) -> List[Event]:
        """Disband the group (leader only)."""
        group_system = self.ctx.group_system

        group = group_system.get_player_group(player_id)
        if not group:
            return [self.ctx.msg_to_player(player_id, "You are not in a group.")]

        if group.leader_id != player_id:
            return [
                self.ctx.msg_to_player(
                    player_id, "Only the group leader can disband the group."
                )
            ]

        group_name = group.name
        members = list(group.members)

        group_system.disband_group(group.group_id)

        events = []
        for mid in members:
            events.append(
                self.ctx.msg_to_player(
                    mid, f"Group '{group_name}' was disbanded by {player_name}."
                )
            )

        return events


def register_group_commands(router) -> None:
    """Register all group commands with the command router."""

    def cmd_group(engine, player_id: str, args: str) -> List[Event]:
        """Handle 'group' command and subcommands."""
        player = engine.ctx.world.players.get(player_id)
        if not player:
            return []

        handler = GroupCommand(engine.ctx)

        # Parse subcommand
        parts = args.strip().split(maxsplit=1)
        if not parts:
            return [
                engine.ctx.msg_to_player(
                    player_id,
                    (
                        "**Group Commands:**\n"
                        "  group create <name>\n"
                        "  group invite <player>\n"
                        "  group members\n"
                        "  group info\n"
                        "  group rename <name>\n"
                        "  group leave\n"
                        "  group disband"
                    ),
                )
            ]

        subcommand = parts[0].lower()
        subargs = parts[1] if len(parts) > 1 else ""

        if subcommand == "create":
            return handler.handle_create(player_id, player.name, subargs)
        elif subcommand == "invite":
            return handler.handle_invite(player_id, player.name, subargs)
        elif subcommand == "leave":
            return handler.handle_leave(player_id, player.name, subargs)
        elif subcommand == "members":
            return handler.handle_members(player_id, player.name, subargs)
        elif subcommand == "info":
            return handler.handle_info(player_id, player.name, subargs)
        elif subcommand == "rename":
            return handler.handle_rename(player_id, player.name, subargs)
        elif subcommand == "disband":
            return handler.handle_disband(player_id, player.name, subargs)
        else:
            return [
                engine.ctx.msg_to_player(
                    player_id, f"Unknown group subcommand: {subcommand}"
                )
            ]

    # Register with router
    router.register(
        names=["group"],
        category="social",
        description="Manage player groups",
        usage="group <create|invite|leave|members|info|rename|disband>",
    )(cmd_group)
