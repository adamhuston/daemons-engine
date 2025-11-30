"""
Clan commands for Phase 10.2

Commands:
- clan create <name> [description] - Create a new clan
- clan invite <player_name> - Invite player to clan (officer+)
- clan join <clan_id> - Join clan if invited
- clan leave - Leave current clan
- clan promote <player_name> - Promote member (leader only)
- clan members - List clan members
- clan info - Show clan info
- clan disband - Disband clan (leader only)
"""

from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from ...engine.systems.context import GameContext

Event = Dict[str, Any]


class ClanCommand:
    """Handler for clan-related commands."""

    def __init__(self, ctx: "GameContext"):
        self.ctx = ctx

    def handle_create(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Create a new clan."""
        if not args.strip():
            return [
                self.ctx.msg_to_player(
                    player_id, "**Usage:** clan create <name> [description]"
                )
            ]

        parts = args.strip().split(" ", 1)
        clan_name = parts[0]
        description = parts[1] if len(parts) > 1 else ""

        clan_system = self.ctx.clan_system

        # Check if player is already in a clan
        if player_id in clan_system.player_to_clan:
            return [
                self.ctx.msg_to_player(
                    player_id, "You are already in a clan. Leave it first."
                )
            ]

        # Check if clan name already exists
        if any(
            clan.name.lower() == clan_name.lower()
            for clan in clan_system.clans.values()
        ):
            return [
                self.ctx.msg_to_player(
                    player_id, f"A clan with the name '{clan_name}' already exists."
                )
            ]

        try:
            import asyncio

            clan_info = asyncio.run(
                clan_system.create_clan(clan_name, player_id, description)
            )

            return [
                self.ctx.msg_to_player(
                    player_id,
                    f"You created clan '{clan_info.name}' (ID: {clan_info.clan_id})",
                )
            ]
        except ValueError as e:
            return [self.ctx.msg_to_player(player_id, f"Error: {str(e)}")]

    def handle_invite(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Invite a player to the clan."""
        if not args.strip():
            return [
                self.ctx.msg_to_player(
                    player_id, "**Usage:** clan invite <player_name>"
                )
            ]

        target_name = args.strip()
        clan_system = self.ctx.clan_system

        # Check if inviter is in a clan
        if player_id not in clan_system.player_to_clan:
            return [self.ctx.msg_to_player(player_id, "You are not in a clan.")]

        clan_id = clan_system.player_to_clan[player_id]
        clan = clan_system.clans[clan_id]

        # Check if inviter has permission to invite
        if not clan_system.can_invite(clan_id, player_id):
            return [
                self.ctx.msg_to_player(
                    player_id,
                    "You do not have permission to invite players to this clan.",
                )
            ]

        # Find target player by name
        target_id = None
        for pid, p in self.ctx.world.players.items():
            if p.name.lower() == target_name.lower():
                target_id = pid
                break

        if not target_id:
            return [
                self.ctx.msg_to_player(player_id, f"Player '{target_name}' not found.")
            ]

        # Check if target is already in a clan
        if target_id in clan_system.player_to_clan:
            return [
                self.ctx.msg_to_player(
                    player_id, f"{target_name} is already in a clan."
                )
            ]

        try:
            import asyncio

            asyncio.run(clan_system.invite_player(clan_id, target_id))

            self.ctx.world.players[target_id]

            events = [
                self.ctx.msg_to_player(
                    player_id, f"You invited {target_name} to clan '{clan.name}'."
                ),
                self.ctx.msg_to_player(
                    target_id,
                    f"{player_name} invited you to join clan '{clan.name}'. Use 'clan join {clan_id}' to accept.",
                ),
            ]
            return events
        except ValueError as e:
            return [self.ctx.msg_to_player(player_id, f"Error: {str(e)}")]

    def handle_join(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Join a clan if invited."""
        if not args.strip():
            return [self.ctx.msg_to_player(player_id, "**Usage:** clan join <clan_id>")]

        try:
            clan_id = int(args.strip())
        except ValueError:
            return [self.ctx.msg_to_player(player_id, "Invalid clan ID.")]

        clan_system = self.ctx.clan_system

        # Check if player is already in a clan
        if player_id in clan_system.player_to_clan:
            return [
                self.ctx.msg_to_player(
                    player_id, "You are already in a clan. Leave it first."
                )
            ]

        # Check if clan exists
        if clan_id not in clan_system.clans:
            return [
                self.ctx.msg_to_player(player_id, f"Clan with ID {clan_id} not found.")
            ]

        clan = clan_system.clans[clan_id]

        # Check if player was invited
        if player_id not in clan.pending_invites:
            return [
                self.ctx.msg_to_player(
                    player_id, f"You were not invited to clan '{clan.name}'."
                )
            ]

        try:
            import asyncio

            asyncio.run(clan_system.invite_player(clan_id, player_id))  # Accept invite

            clan_system.player_to_clan[player_id] = clan_id
            clan.pending_invites.discard(player_id)

            events = [
                self.ctx.msg_to_player(player_id, f"You joined clan '{clan.name}'."),
                self.ctx.event_dispatcher.clan_message(
                    clan_id, player_id, player_name, f"{player_name} joined the clan."
                ),
            ]
            return events
        except ValueError as e:
            return [self.ctx.msg_to_player(player_id, f"Error: {str(e)}")]

    def handle_leave(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Leave the current clan."""
        clan_system = self.ctx.clan_system

        if player_id not in clan_system.player_to_clan:
            return [self.ctx.msg_to_player(player_id, "You are not in a clan.")]

        clan_id = clan_system.player_to_clan[player_id]
        clan = clan_system.clans[clan_id]

        # Check if player is the leader
        if clan.leader_id == player_id:
            return [
                self.ctx.msg_to_player(
                    player_id,
                    "The clan leader cannot leave. Disband the clan or promote another leader.",
                )
            ]

        try:
            import asyncio

            asyncio.run(clan_system.remove_player(clan_id, player_id))

            del clan_system.player_to_clan[player_id]

            events = [
                self.ctx.msg_to_player(player_id, f"You left clan '{clan.name}'."),
                self.ctx.event_dispatcher.clan_message(
                    clan_id, player_id, player_name, f"{player_name} left the clan."
                ),
            ]
            return events
        except ValueError as e:
            return [self.ctx.msg_to_player(player_id, f"Error: {str(e)}")]

    def handle_promote(
        self, player_id: str, player_name: str, args: str
    ) -> List[Event]:
        """Promote a clan member (leader only)."""
        if not args.strip():
            return [
                self.ctx.msg_to_player(
                    player_id, "**Usage:** clan promote <player_name>"
                )
            ]

        target_name = args.strip()
        clan_system = self.ctx.clan_system

        if player_id not in clan_system.player_to_clan:
            return [self.ctx.msg_to_player(player_id, "You are not in a clan.")]

        clan_id = clan_system.player_to_clan[player_id]
        clan = clan_system.clans[clan_id]

        # Check if player is the leader
        if clan.leader_id != player_id:
            return [
                self.ctx.msg_to_player(
                    player_id, "Only the clan leader can promote members."
                )
            ]

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

        # Check if target is in the clan
        if target_id not in clan.members:
            return [
                self.ctx.msg_to_player(player_id, f"{target_name} is not in your clan.")
            ]

        try:
            import asyncio

            asyncio.run(clan_system.promote_player(clan_id, target_id))

            self.ctx.world.players[target_id]

            events = [
                self.ctx.msg_to_player(
                    player_id, f"You promoted {target_name} to officer."
                ),
                self.ctx.msg_to_player(
                    target_id, f"You were promoted to officer in clan '{clan.name}'."
                ),
                self.ctx.event_dispatcher.clan_message(
                    clan_id,
                    player_id,
                    player_name,
                    f"{target_name} was promoted to officer.",
                ),
            ]
            return events
        except ValueError as e:
            return [self.ctx.msg_to_player(player_id, f"Error: {str(e)}")]

    def handle_members(
        self, player_id: str, player_name: str, args: str
    ) -> List[Event]:
        """List clan members."""
        clan_system = self.ctx.clan_system

        if player_id not in clan_system.player_to_clan:
            return [self.ctx.msg_to_player(player_id, "You are not in a clan.")]

        clan_id = clan_system.player_to_clan[player_id]
        clan = clan_system.clans[clan_id]

        members_text = "**Clan Members:**\n"

        # Show leader
        leader = self.ctx.world.players.get(clan.leader_id)
        if leader:
            members_text += f"  {leader.name} (Leader)\n"

        # Show officers and members
        for member_id, rank in clan.members.items():
            if member_id != clan.leader_id:
                member = self.ctx.world.players.get(member_id)
                if member:
                    rank_name = (
                        "Officer"
                        if rank == 3
                        else "Member"
                        if rank == 2
                        else "Initiate"
                    )
                    members_text += f"  {member.name} ({rank_name})\n"

        return [self.ctx.msg_to_player(player_id, members_text)]

    def handle_info(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Show clan info."""
        clan_system = self.ctx.clan_system

        if player_id not in clan_system.player_to_clan:
            return [self.ctx.msg_to_player(player_id, "You are not in a clan.")]

        clan_id = clan_system.player_to_clan[player_id]
        clan = clan_system.clans[clan_id]

        leader = self.ctx.world.players.get(clan.leader_id)
        leader_name = leader.name if leader else "Unknown"

        info_text = (
            f"**Clan Information**\n"
            f"Name: {clan.name}\n"
            f"ID: {clan.clan_id}\n"
            f"Leader: {leader_name}\n"
            f"Members: {len(clan.members)}\n"
            f"Level: {clan.level}\n"
            f"Experience: {clan.experience}\n"
        )

        if clan.description:
            info_text += f"Description: {clan.description}\n"

        return [self.ctx.msg_to_player(player_id, info_text)]

    def handle_disband(
        self, player_id: str, player_name: str, args: str
    ) -> List[Event]:
        """Disband the clan (leader only)."""
        clan_system = self.ctx.clan_system

        if player_id not in clan_system.player_to_clan:
            return [self.ctx.msg_to_player(player_id, "You are not in a clan.")]

        clan_id = clan_system.player_to_clan[player_id]
        clan = clan_system.clans[clan_id]

        # Check if player is the leader
        if clan.leader_id != player_id:
            return [
                self.ctx.msg_to_player(
                    player_id, "Only the clan leader can disband the clan."
                )
            ]

        try:
            import asyncio

            asyncio.run(clan_system.disband_clan(clan_id))

            # Clear all members from clan
            for member_id in list(clan_system.player_to_clan.keys()):
                if clan_system.player_to_clan[member_id] == clan_id:
                    del clan_system.player_to_clan[member_id]
                    if member_id in self.ctx.world.players:
                        self.ctx.msg_to_player(
                            member_id, f"Clan '{clan.name}' has been disbanded."
                        )

            # Remove clan from system
            del clan_system.clans[clan_id]

            return [
                self.ctx.msg_to_player(player_id, f"You disbanded clan '{clan.name}'.")
            ]
        except ValueError as e:
            return [self.ctx.msg_to_player(player_id, f"Error: {str(e)}")]


def register_clan_commands(router) -> None:
    """Register all clan commands with the command router."""

    def cmd_clan(engine, player_id: str, args: str) -> List[Event]:
        """Handle 'clan' command with subcommands."""
        player = engine.ctx.world.players.get(player_id)
        if not player:
            return []

        handler = ClanCommand(engine.ctx)

        # Parse subcommand
        parts = args.split(" ", 1) if args else []
        subcommand = parts[0].lower() if parts else "info"
        subargs = parts[1] if len(parts) > 1 else ""

        if subcommand == "create":
            return handler.handle_create(player_id, player.name, subargs)
        elif subcommand == "invite":
            return handler.handle_invite(player_id, player.name, subargs)
        elif subcommand == "join":
            return handler.handle_join(player_id, player.name, subargs)
        elif subcommand == "leave":
            return handler.handle_leave(player_id, player.name, subargs)
        elif subcommand == "promote":
            return handler.handle_promote(player_id, player.name, subargs)
        elif subcommand == "members":
            return handler.handle_members(player_id, player.name, subargs)
        elif subcommand == "info":
            return handler.handle_info(player_id, player.name, subargs)
        elif subcommand == "disband":
            return handler.handle_disband(player_id, player.name, subargs)
        else:
            return [
                engine.ctx.msg_to_player(
                    player_id,
                    f"Unknown clan subcommand: {subcommand}. Use: create|invite|join|leave|promote|members|info|disband",
                )
            ]

    # Register with router
    router.register(
        names=["clan"],
        category="social",
        description="Manage player clans",
        usage="clan <create|invite|join|leave|promote|members|info|disband>",
    )(cmd_clan)
