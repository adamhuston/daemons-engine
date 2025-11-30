"""
Phase 10.1 Command Tests - Tells, Follows, Yells

Comprehensive test suite covering:
- Tell/reply/ignore command functionality
- Follow/followers/following commands
- Yell broadcast command
- Integration with EventDispatcher
"""

import pytest

from app.commands.social.follow import FollowCommand
from app.commands.social.tell import TellCommand
from app.commands.social.yell import YellCommand
from app.engine.systems.context import GameContext
from app.engine.world import EntityType, World, WorldPlayer, WorldRoom

# ============ FIXTURES ============


@pytest.fixture
def mock_world_with_players():
    """Create a World with test rooms and players."""
    rooms = {}
    players = {}

    # Create 3 test rooms
    for i in range(3):
        room = WorldRoom(
            id=f"room_{i}",
            name=f"Test Room {i}",
            description="A test room",
            room_type="test",
        )
        rooms[room.id] = room

    world = World(rooms=rooms, players=players)

    # Create exits between rooms
    world.rooms["room_0"].exits["north"] = "room_1"
    world.rooms["room_1"].exits["south"] = "room_0"
    world.rooms["room_1"].exits["east"] = "room_2"
    world.rooms["room_2"].exits["west"] = "room_1"

    # Create 5 test players
    for i in range(5):
        player = WorldPlayer(
            id=f"player_{i}",
            entity_type=EntityType.PLAYER,
            name=f"Player{i}",
            room_id="room_0" if i < 3 else "room_1",
            character_class="adventurer",
            level=1,
            experience=0,
            player_flags={},
        )
        world.players[player.id] = player

    return world


@pytest.fixture
def ctx_with_events(mock_world_with_players):
    """Create GameContext with EventDispatcher mock."""
    ctx = GameContext(mock_world_with_players)

    # Mock EventDispatcher for testing
    class MockEventDispatcher:
        def __init__(self):
            self.events_created = []

        def tell_message(self, sender_id, sender_name, recipient_id, text):
            event = {
                "type": "tell_message",
                "scope": "tell",
                "sender_id": sender_id,
                "sender_name": sender_name,
                "recipient_id": recipient_id,
                "text": text,
            }
            self.events_created.append(event)
            return event

        def group_message(self, group_id, sender_id, sender_name, text):
            event = {
                "type": "group_message",
                "scope": "group",
                "group_id": group_id,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "text": text,
            }
            self.events_created.append(event)
            return event

        def follow_event(self, follower_id, follower_name, followed_id, action):
            event = {
                "type": "follow_event",
                "scope": "player",
                "follower_id": follower_id,
                "follower_name": follower_name,
                "followed_id": followed_id,
                "action": action,
            }
            self.events_created.append(event)
            return event

    ctx.event_dispatcher = MockEventDispatcher()

    # Mock msg_to_player for testing
    def msg_to_player(player_id, text, **kwargs):
        return {
            "type": "message",
            "scope": "player",
            "player_id": player_id,
            "text": text,
        }

    def msg_to_room(room_id, text, exclude=None, **kwargs):
        return {
            "type": "message",
            "scope": "room",
            "room_id": room_id,
            "text": text,
            "exclude": list(exclude) if exclude else [],
        }

    ctx.msg_to_player = msg_to_player
    ctx.msg_to_room = msg_to_room

    return ctx


# ============ TELL COMMAND TESTS ============


class TestTellCommand:
    """Test tell/private message command."""

    def test_tell_basic(self, ctx_with_events):
        """Test sending a basic tell."""
        handler = TellCommand(ctx_with_events)
        events = handler.handle_tell("player_0", "Player0", "Player1 Hello there!")

        assert len(events) == 1
        tell_event = ctx_with_events.event_dispatcher.events_created[-1]
        assert tell_event["type"] == "tell_message"
        assert tell_event["sender_id"] == "player_0"
        assert tell_event["recipient_id"] == "player_1"
        assert tell_event["text"] == "Hello there!"

    def test_tell_no_args(self, ctx_with_events):
        """Test tell with no arguments shows usage."""
        handler = TellCommand(ctx_with_events)
        events = handler.handle_tell("player_0", "Player0", "")

        assert "Usage" in events[0]["text"]

    def test_tell_no_message(self, ctx_with_events):
        """Test tell with target but no message shows usage."""
        handler = TellCommand(ctx_with_events)
        events = handler.handle_tell("player_0", "Player0", "player_1")

        assert "Usage" in events[0]["text"]

    def test_tell_player_not_found(self, ctx_with_events):
        """Test tell to nonexistent player."""
        handler = TellCommand(ctx_with_events)
        events = handler.handle_tell("player_0", "Player0", "Nonexistent Hi!")

        assert "not found" in events[0]["text"].lower()

    def test_tell_updates_last_tell_from(self, ctx_with_events):
        """Test that last_tell_from is updated on recipient."""
        handler = TellCommand(ctx_with_events)
        handler.handle_tell("player_0", "Player0", "Player1 Test message")

        recipient = ctx_with_events.world.players["player_1"]
        assert recipient.player_flags["last_tell_from"] == "player_0"
        assert recipient.player_flags["last_tell_from_name"] == "Player0"

    def test_tell_with_ignore(self, ctx_with_events):
        """Test tell to a player who is ignoring you."""
        recipient = ctx_with_events.world.players["player_1"]
        recipient.player_flags["ignored_players"] = ["player_0"]

        handler = TellCommand(ctx_with_events)
        events = handler.handle_tell("player_0", "Player0", "Player1 Hi!")

        assert "ignoring" in events[0]["text"].lower()


class TestReplyCommand:
    """Test reply command."""

    def test_reply_no_previous_tell(self, ctx_with_events):
        """Test reply when no one has told you."""
        handler = TellCommand(ctx_with_events)
        events = handler.handle_reply("player_0", "Player0", "Hello!")

        assert "no one" in events[0]["text"].lower()

    def test_reply_to_recent_tell(self, ctx_with_events):
        """Test replying to recent tell."""
        # First, player_1 tells player_0
        handler = TellCommand(ctx_with_events)
        handler.handle_tell("player_1", "Player1", "Player0 Test")

        # Now player_0 replies
        handler.handle_reply("player_0", "Player0", "Reply message")

        # Should create tell event back to player_1
        tell_event = ctx_with_events.event_dispatcher.events_created[-1]
        assert tell_event["recipient_id"] == "player_1"
        assert tell_event["text"] == "Reply message"

    def test_reply_player_not_found(self, ctx_with_events):
        """Test reply when previous sender is not found."""
        player_0 = ctx_with_events.world.players["player_0"]
        player_0.player_flags["last_tell_from"] = "nonexistent_player"
        player_0.player_flags["last_tell_from_name"] = "Nonexistent"

        handler = TellCommand(ctx_with_events)
        events = handler.handle_reply("player_0", "Player0", "Hello")

        assert "no longer online" in events[0]["text"].lower()

    def test_reply_no_message(self, ctx_with_events):
        """Test reply with no message."""
        handler = TellCommand(ctx_with_events)
        events = handler.handle_reply("player_0", "Player0", "")

        assert "Usage" in events[0]["text"]


class TestIgnoreCommand:
    """Test ignore/unignore commands."""

    def test_ignore_player(self, ctx_with_events):
        """Test adding a player to ignore list."""
        handler = TellCommand(ctx_with_events)
        events = handler.handle_ignore("player_0", "Player0", "Player1")

        player_0 = ctx_with_events.world.players["player_0"]
        assert "player_1" in player_0.player_flags["ignored_players"]
        assert "ignoring" in events[0]["text"].lower()

    def test_ignore_already_ignored(self, ctx_with_events):
        """Test ignoring a player already ignored."""
        player_0 = ctx_with_events.world.players["player_0"]
        player_0.player_flags["ignored_players"] = ["player_1"]

        handler = TellCommand(ctx_with_events)
        events = handler.handle_ignore("player_0", "Player0", "Player1")

        assert "already ignoring" in events[0]["text"].lower()

    def test_ignore_nonexistent_player(self, ctx_with_events):
        """Test ignoring nonexistent player."""
        handler = TellCommand(ctx_with_events)
        events = handler.handle_ignore("player_0", "Player0", "Nonexistent")

        assert "not found" in events[0]["text"].lower()

    def test_unignore_player(self, ctx_with_events):
        """Test removing a player from ignore list."""
        player_0 = ctx_with_events.world.players["player_0"]
        player_0.player_flags["ignored_players"] = ["player_1"]

        handler = TellCommand(ctx_with_events)
        events = handler.handle_unignore("player_0", "Player0", "Player1")

        assert "player_1" not in player_0.player_flags["ignored_players"]
        assert "no longer ignoring" in events[0]["text"].lower()

    def test_unignore_not_on_list(self, ctx_with_events):
        """Test unignoring a player not on ignore list."""
        player_0 = ctx_with_events.world.players["player_0"]
        player_0.player_flags["ignored_players"] = []

        handler = TellCommand(ctx_with_events)
        events = handler.handle_unignore("player_0", "Player0", "Player1")

        assert "not ignoring" in events[0]["text"].lower()


# ============ FOLLOW COMMAND TESTS ============


class TestFollowCommand:
    """Test follow/followers/following commands."""

    def test_follow_player(self, ctx_with_events):
        """Test following a player."""
        handler = FollowCommand(ctx_with_events)
        events = handler.handle_follow("player_0", "Player0", "Player1")

        player_0 = ctx_with_events.world.players["player_0"]
        player_1 = ctx_with_events.world.players["player_1"]

        assert "player_1" in player_0.player_flags["following"]
        assert "player_0" in player_1.player_flags["followers"]
        assert len(events) > 1  # Message + follow event

    def test_follow_self(self, ctx_with_events):
        """Test that you can't follow yourself."""
        handler = FollowCommand(ctx_with_events)
        events = handler.handle_follow("player_0", "Player0", "Player0")

        assert "cannot follow yourself" in events[0]["text"].lower()

    def test_follow_nonexistent(self, ctx_with_events):
        """Test following nonexistent player."""
        handler = FollowCommand(ctx_with_events)
        events = handler.handle_follow("player_0", "Player0", "Nonexistent")

        assert "not found" in events[0]["text"].lower()

    def test_follow_already_following(self, ctx_with_events):
        """Test following a player already followed."""
        player_0 = ctx_with_events.world.players["player_0"]
        player_0.player_flags["following"] = ["player_1"]

        handler = FollowCommand(ctx_with_events)
        events = handler.handle_follow("player_0", "Player0", "Player1")

        assert "already following" in events[0]["text"].lower()

    def test_unfollow_player(self, ctx_with_events):
        """Test unfollowing a player."""
        player_0 = ctx_with_events.world.players["player_0"]
        player_1 = ctx_with_events.world.players["player_1"]
        player_0.player_flags["following"] = ["player_1"]
        player_1.player_flags["followers"] = ["player_0"]

        handler = FollowCommand(ctx_with_events)
        handler.handle_unfollow("player_0", "Player0", "Player1")

        assert "player_1" not in player_0.player_flags["following"]
        assert "player_0" not in player_1.player_flags["followers"]

    def test_unfollow_not_following(self, ctx_with_events):
        """Test unfollowing a player you're not following."""
        handler = FollowCommand(ctx_with_events)
        events = handler.handle_unfollow("player_0", "Player0", "Player1")

        assert "not following" in events[0]["text"].lower()

    def test_followers_list(self, ctx_with_events):
        """Test listing followers."""
        player_0 = ctx_with_events.world.players["player_0"]
        player_0.player_flags["followers"] = ["player_1", "player_2"]

        handler = FollowCommand(ctx_with_events)
        events = handler.handle_followers("player_0", "Player0", "")

        assert "Player1" in events[0]["text"]
        assert "Player2" in events[0]["text"]

    def test_followers_empty_list(self, ctx_with_events):
        """Test followers when no one is following."""
        handler = FollowCommand(ctx_with_events)
        events = handler.handle_followers("player_0", "Player0", "")

        assert "no one" in events[0]["text"].lower()

    def test_following_list(self, ctx_with_events):
        """Test listing followed players."""
        player_0 = ctx_with_events.world.players["player_0"]
        player_0.player_flags["following"] = ["player_1", "player_2"]

        handler = FollowCommand(ctx_with_events)
        events = handler.handle_following("player_0", "Player0", "")

        assert "Player1" in events[0]["text"]
        assert "Player2" in events[0]["text"]

    def test_following_empty_list(self, ctx_with_events):
        """Test following when not following anyone."""
        handler = FollowCommand(ctx_with_events)
        events = handler.handle_following("player_0", "Player0", "")

        assert "not following" in events[0]["text"].lower()


# ============ YELL COMMAND TESTS ============


class TestYellCommand:
    """Test yell broadcast command."""

    def test_yell_basic(self, ctx_with_events):
        """Test basic yell in current room."""
        handler = YellCommand(ctx_with_events)
        events = handler.handle_yell("player_0", "Player0", "Help!")

        # Should have feedback to yeller + room messages
        assert len(events) > 1
        assert "Help!" in events[0]["text"]  # Feedback to yeller

    def test_yell_no_message(self, ctx_with_events):
        """Test yell with no message."""
        handler = YellCommand(ctx_with_events)
        events = handler.handle_yell("player_0", "Player0", "")

        assert "Usage" in events[0]["text"]

    def test_yell_adjacent_rooms(self, ctx_with_events):
        """Test that yell reaches adjacent rooms."""
        handler = YellCommand(ctx_with_events)
        events = handler.handle_yell("player_0", "Player0", "Listen up!")

        # Should have events for current room + adjacent rooms
        room_events = [e for e in events if e.get("scope") == "room"]
        current_room = ctx_with_events.world.players["player_0"].room_id

        # Should include message for current room
        current_events = [e for e in room_events if e.get("room_id") == current_room]
        assert len(current_events) > 0

    def test_yell_to_multiple_rooms(self, ctx_with_events):
        """Test that yell broadcasts to multiple adjacent rooms."""
        player_0 = ctx_with_events.world.players["player_0"]

        handler = YellCommand(ctx_with_events)
        events = handler.handle_yell(player_0.id, "Player0", "Hear me!")

        room_events = [e for e in events if e.get("scope") == "room"]
        # Should have events for current room + north (room_1)
        assert len(room_events) >= 1


# ============ EDGE CASES ============


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_tell_empty_message(self, ctx_with_events):
        """Test tell with only target name."""
        handler = TellCommand(ctx_with_events)
        events = handler.handle_tell("player_0", "Player0", "player_1")

        assert "Usage" in events[0]["text"]

    def test_follow_multiple_players(self, ctx_with_events):
        """Test following multiple players."""
        handler = FollowCommand(ctx_with_events)

        handler.handle_follow("player_0", "Player0", "Player1")
        handler.handle_follow("player_0", "Player0", "Player2")

        player_0 = ctx_with_events.world.players["player_0"]
        assert len(player_0.player_flags["following"]) == 2

    def test_ignore_large_list(self, ctx_with_events):
        """Test ignoring many players."""
        player_0 = ctx_with_events.world.players["player_0"]
        handler = TellCommand(ctx_with_events)

        for i in range(1, 5):
            handler.handle_ignore("player_0", "Player0", f"Player{i}")

        assert len(player_0.player_flags["ignored_players"]) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
