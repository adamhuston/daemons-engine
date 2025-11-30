"""
Follow commands for Phase 10.1

Commands:
- follow <player_name> - Start following a player
- unfollow <player_name> - Stop following a player
- followers - List players following you
- following - List players you are following
"""

from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from ...engine.systems.context import GameContext

Event = Dict[str, Any]


class FollowCommand:
    """Handler for follow-related commands."""

    def __init__(self, ctx: "GameContext"):
        self.ctx = ctx

    def handle_follow(self, player_id: str, player_name: str, args: str) -> List[Event]:
        """Start following another player."""
        if not args.strip():
            return [
                self.ctx.msg_to_player(player_id, "**Usage:** follow <player_name>")
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

        if target_id == player_id:
            return [self.ctx.msg_to_player(player_id, "You cannot follow yourself.")]

        player = self.ctx.world.players[player_id]
        if not player.player_flags:
            player.player_flags = {}

        # Check if already following
        following_list = player.player_flags.get("following", [])
        if target_id in following_list:
            return [
                self.ctx.msg_to_player(
                    player_id,
                    f"You are already following {self.ctx.world.players[target_id].name}.",
                )
            ]

        # Add to following list
        following_list.append(target_id)
        player.player_flags["following"] = following_list

        # Add to target's followers list
        target = self.ctx.world.players[target_id]
        if not target.player_flags:
            target.player_flags = {}

        followers_list = target.player_flags.get("followers", [])
        if player_id not in followers_list:
            followers_list.append(player_id)
            target.player_flags["followers"] = followers_list

        # Create follow event
        follow_event = self.ctx.event_dispatcher.follow_event(
            follower_id=player_id,
            follower_name=player_name,
            followed_id=target_id,
            action="started_following",
        )

        return [
            self.ctx.msg_to_player(
                player_id,
                f"You are now following {self.ctx.world.players[target_id].name}.",
            ),
            follow_event,
        ]

    def handle_unfollow(
        self, player_id: str, player_name: str, args: str
    ) -> List[Event]:
        """Stop following another player."""
        if not args.strip():
            return [
                self.ctx.msg_to_player(player_id, "**Usage:** unfollow <player_name>")
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

        # Remove from following list
        following_list = player.player_flags.get("following", [])
        if target_id not in following_list:
            return [
                self.ctx.msg_to_player(
                    player_id,
                    f"You are not following {self.ctx.world.players[target_id].name}.",
                )
            ]

        following_list.remove(target_id)
        player.player_flags["following"] = following_list

        # Remove from target's followers list
        target = self.ctx.world.players[target_id]
        if target.player_flags:
            followers_list = target.player_flags.get("followers", [])
            if player_id in followers_list:
                followers_list.remove(player_id)
                target.player_flags["followers"] = followers_list

        return [
            self.ctx.msg_to_player(
                player_id,
                f"You stopped following {self.ctx.world.players[target_id].name}.",
            )
        ]

    def handle_followers(
        self, player_id: str, player_name: str, args: str
    ) -> List[Event]:
        """List players following you."""
        player = self.ctx.world.players[player_id]
        followers_list = (
            player.player_flags.get("followers", []) if player.player_flags else []
        )

        if not followers_list:
            return [self.ctx.msg_to_player(player_id, "No one is following you.")]

        follower_names = []
        for fid in followers_list:
            follower = self.ctx.world.players.get(fid)
            if follower:
                follower_names.append(f"  {follower.name}")

        text = f"**Players Following You ({len(follower_names)}):**\n" + "\n".join(
            follower_names
        )
        return [self.ctx.msg_to_player(player_id, text)]

    def handle_following(
        self, player_id: str, player_name: str, args: str
    ) -> List[Event]:
        """List players you are following."""
        player = self.ctx.world.players[player_id]
        following_list = (
            player.player_flags.get("following", []) if player.player_flags else []
        )

        if not following_list:
            return [self.ctx.msg_to_player(player_id, "You are not following anyone.")]

        following_names = []
        for fid in following_list:
            followed = self.ctx.world.players.get(fid)
            if followed:
                following_names.append(f"  {followed.name}")

        text = f"**Players You Are Following ({len(following_names)}):**\n" + "\n".join(
            following_names
        )
        return [self.ctx.msg_to_player(player_id, text)]


def register_follow_commands(router) -> None:
    """Register all follow commands with the command router."""

    def cmd_follow(engine, player_id: str, args: str) -> List[Event]:
        """Handle 'follow' command."""
        player = engine.ctx.world.players.get(player_id)
        if not player:
            return []

        handler = FollowCommand(engine.ctx)
        return handler.handle_follow(player_id, player.name, args)

    def cmd_unfollow(engine, player_id: str, args: str) -> List[Event]:
        """Handle 'unfollow' command."""
        player = engine.ctx.world.players.get(player_id)
        if not player:
            return []

        handler = FollowCommand(engine.ctx)
        return handler.handle_unfollow(player_id, player.name, args)

    def cmd_followers(engine, player_id: str, args: str) -> List[Event]:
        """Handle 'followers' command."""
        player = engine.ctx.world.players.get(player_id)
        if not player:
            return []

        handler = FollowCommand(engine.ctx)
        return handler.handle_followers(player_id, player.name, args)

    def cmd_following(engine, player_id: str, args: str) -> List[Event]:
        """Handle 'following' command."""
        player = engine.ctx.world.players.get(player_id)
        if not player:
            return []

        handler = FollowCommand(engine.ctx)
        return handler.handle_following(player_id, player.name, args)

    # Register with router
    router.register(
        names=["follow"],
        category="social",
        description="Follow a player (auto-move to their room on movement)",
        usage="follow <player_name>",
    )(cmd_follow)

    router.register(
        names=["unfollow"],
        category="social",
        description="Stop following a player",
        usage="unfollow <player_name>",
    )(cmd_unfollow)

    router.register(
        names=["followers"],
        category="social",
        description="List players following you",
        usage="followers",
    )(cmd_followers)

    router.register(
        names=["following"],
        category="social",
        description="List players you are following",
        usage="following",
    )(cmd_following)
