"""
CommandRouter: Decorator-based command routing system for game commands.

Provides:
- @command() decorator for handler registration
- Unified command dispatch with alias support
- Argument parsing patterns (simple, target, separators)
- Command metadata and help system
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .context import GameContext
    from ..world import PlayerId

# Type alias for event
Event = Dict[str, Any]
CommandHandler = Callable[..., List[Event]]  # (engine, player_id, args)


@dataclass
class CommandMeta:
    """Metadata for a registered command."""
    name: str  # Primary command name
    names: List[str]  # All primary names
    aliases: Dict[str, List[str]]  # Map of name -> alias list
    handler: CommandHandler  # The actual handler function
    category: str  # Command category (movement, combat, inventory, etc)
    description: str  # Human-readable description
    usage: str  # Usage string (e.g., "attack <target>")
    arg_pattern: Optional[str] = None  # Argument parsing pattern


class CommandRouter:
    """
    Routes player commands to handlers using a decorator-based registration system.
    
    Supports:
    - Multiple names and aliases for commands
    - Automatic argument parsing
    - Simple, target-based, and separator-based arguments
    - Command categorization and help
    """
    
    def __init__(self, engine: Any) -> None:
        """
        Initialize command router.
        
        Args:
            engine: The WorldEngine instance (for access to handler methods)
        """
        self.engine = engine
        self.commands: Dict[str, CommandMeta] = {}  # name -> meta
        self.categories: Dict[str, List[str]] = {}  # category -> [command names]
    
    def register(
        self,
        names: List[str],
        aliases: Optional[Dict[str, List[str]]] = None,
        category: str = "misc",
        description: str = "",
        usage: str = "",
        arg_pattern: Optional[str] = None,
    ) -> Callable:
        """
        Decorator to register a command handler.
        
        Can be used as:
        @router.register(names=["attack", "kill"], ...)
        def handle_attack(self, player_id, args):
            ...
        
        Or called directly:
        router.register_handler("attack", handler_func, names=["attack", "kill"], ...)
        
        Args:
            names: List of primary command names
            aliases: Dict mapping names to their aliases
            category: Command category for organization
            description: Human-readable description
            usage: Usage/help text
            arg_pattern: How to parse arguments
                - None: no arguments
                - "single": single required argument
                - "optional": single optional argument
                - "rest": all remaining text as single argument
                - "target_name": extract target name (for commands like "attack foo")
        
        Returns:
            Decorator function
        """
        def decorator(handler: CommandHandler) -> CommandHandler:
            self.register_handler(
                primary_name=names[0],
                handler=handler,
                names=names,
                aliases=aliases,
                category=category,
                description=description,
                usage=usage,
                arg_pattern=arg_pattern,
            )
            return handler
        
        return decorator
    
    def register_handler(
        self,
        primary_name: str,
        handler: CommandHandler,
        names: Optional[List[str]] = None,
        aliases: Optional[Dict[str, List[str]]] = None,
        category: str = "misc",
        description: str = "",
        usage: str = "",
        arg_pattern: Optional[str] = None,
    ) -> None:
        """
        Register a command handler directly (without decorator).
        
        Args:
            primary_name: Primary command name
            handler: Handler function
            names: List of command name variants (defaults to [primary_name])
            aliases: Dict of aliases
            category: Command category
            description: Description text
            usage: Usage text
            arg_pattern: Argument parsing pattern
        """
        if names is None:
            names = [primary_name]
        
        # Register all names and aliases
        for name in names:
            meta = CommandMeta(
                name=primary_name,
                names=names,
                aliases=aliases or {},
                handler=handler,
                category=category,
                description=description,
                usage=usage,
                arg_pattern=arg_pattern,
            )
            self.commands[name] = meta
        
        # Register aliases
        if aliases:
            for primary, alias_list in aliases.items():
                for alias in alias_list:
                    meta = CommandMeta(
                        name=primary,
                        names=names,
                        aliases=aliases,
                        handler=handler,
                        category=category,
                        description=description,
                        usage=usage,
                        arg_pattern=arg_pattern,
                    )
                    self.commands[alias] = meta
        
        # Track category
        if category not in self.categories:
            self.categories[category] = []
        if primary_name not in self.categories[category]:
            self.categories[category].append(primary_name)
    
    async def dispatch(self, player_id: str, raw_command: str) -> List['Event']:
        """
        Parse and dispatch a command to its handler.
        
        Args:
            player_id: The player executing the command
            raw_command: Raw command string (e.g., "attack goblin")
        
        Returns:
            List of events to send to players
        """
        raw = raw_command.strip()
        if not raw:
            return []
        
        # Check if player is in dialogue mode (Phase X.2)
        player = self.engine.world.players.get(player_id)
        if player and player.active_dialogue:
            return self._handle_dialogue_input(player_id, raw)
        
        # Split into command and arguments
        parts = raw.split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Look up command
        if cmd_name not in self.commands:
            # Check room triggers before returning unknown command
            trigger_events = self._check_room_triggers(player_id, raw_command)
            if trigger_events:
                return trigger_events
            
            return [self.engine._msg_to_player(
                player_id,
                "You mutter something unintelligible. (Unknown command)"
            )]
        
        meta = self.commands[cmd_name]
        
        # Call handler with arguments (await if it's a coroutine)
        try:
            result = meta.handler(self.engine, player_id, args)
            # Check if the handler is async (returns a coroutine)
            if hasattr(result, '__await__'):
                return await result
            return result
        except Exception as e:
            # Log error and return generic message
            print(f"[CommandError] {cmd_name}: {e}")
            return [self.engine._msg_to_player(
                player_id,
                "Something went wrong executing that command."
            )]
    
    def _check_room_triggers(self, player_id: str, raw_command: str) -> List['Event']:
        """
        Check if the player's room has a trigger that matches the command.
        
        Args:
            player_id: The player executing the command
            raw_command: The raw command string
            
        Returns:
            List of events if a trigger matched, empty list otherwise
        """
        # Get player's current room
        player = self.engine.world.players.get(player_id)
        if not player:
            return []
        
        room_id = player.room_id
        
        # Check if trigger system exists
        if not hasattr(self.engine, 'trigger_system'):
            return []
        
        # Import TriggerContext here to avoid circular import
        from .triggers import TriggerContext
        
        trigger_ctx = TriggerContext(
            player_id=player_id,
            room_id=room_id,
            world=self.engine.world,
            event_type="on_command",
            raw_command=raw_command,
        )
        
        return self.engine.trigger_system.fire_command(room_id, raw_command, trigger_ctx)
    
    def get_help(self, category: Optional[str] = None) -> str:
        """
        Get help text for commands.
        
        Args:
            category: Specific category to list, or None for all
        
        Returns:
            Formatted help text
        """
        lines = ["═══ Available Commands ═══", ""]
        
        cats = [category] if category else sorted(self.categories.keys())
        
        for cat in cats:
            if cat not in self.categories:
                continue
            
            lines.append(f"**{cat.title()}**:")
            
            seen = set()
            for cmd_name in sorted(self.categories[cat]):
                if cmd_name in seen:
                    continue
                seen.add(cmd_name)
                
                meta = self.commands[cmd_name]
                usage = f"{cmd_name} {meta.usage}" if meta.usage else cmd_name
                
                aliases_str = ""
                if meta.aliases and cmd_name in meta.aliases:
                    aliases_str = f" (aliases: {', '.join(meta.aliases[cmd_name])})"
                
                lines.append(f"  {usage}{aliases_str}")
                if meta.description:
                    lines.append(f"    {meta.description}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _handle_dialogue_input(self, player_id: str, raw: str) -> List['Event']:
        """
        Handle input when player is in dialogue mode.
        
        Args:
            player_id: The player in dialogue
            raw: Raw input string
        
        Returns:
            List of events
        """
        raw_lower = raw.lower().strip()
        
        # Exit commands
        if raw_lower in ("bye", "farewell", "leave", "exit", "goodbye"):
            return self.engine.quest_system.end_dialogue(player_id)
        
        # Number selection (1, 2, 3, etc.)
        if raw.isdigit():
            option_num = int(raw)
            return self.engine.quest_system.select_option(player_id, option_num)
        
        # Invalid input while in dialogue
        return [self.engine._msg_to_player(
            player_id,
            "You're in a conversation. Enter a number (1, 2, 3...) to respond, or 'bye' to leave."
        )]
