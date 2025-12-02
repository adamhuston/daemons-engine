# backend/daemons/input_sanitization.py
"""
Input Sanitization Module - Phase 16.5

This module provides security-focused input sanitization for:
- Command input: Prevents exploits and crashes from malformed input
- Player names: Ensures names are safe and cannot impersonate or exploit
- Chat text: Removes dangerous Unicode that could disrupt display

Goals:
- Prevent server crashes from malformed Unicode or control characters
- Block Unicode exploits (RTL override, homoglyphs, zero-width chars)
- Enforce reasonable length limits
- NOT a content filter (profanity, etc.) - that's a game design choice

All functions return sanitized strings that are safe for processing.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class SanitizationConfig:
    """Configuration for input sanitization limits."""

    # Command limits
    max_command_length: int = 500

    # Player name limits
    min_name_length: int = 2
    max_name_length: int = 24

    # Chat message limits
    max_chat_length: int = 1000


# Global config instance
sanitization_config = SanitizationConfig()


# =============================================================================
# Dangerous Unicode Characters
# =============================================================================

# Control characters that should NEVER appear in user input
# Includes C0 controls (0x00-0x1F) except safe whitespace, and C1 controls (0x80-0x9F)
CONTROL_CHAR_PATTERN = re.compile(
    r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]'
)

# Bidirectional override characters that can disrupt text display
# These can make text appear to read backwards or hide content
BIDI_OVERRIDE_CHARS = {
    '\u202A',  # LEFT-TO-RIGHT EMBEDDING
    '\u202B',  # RIGHT-TO-LEFT EMBEDDING
    '\u202C',  # POP DIRECTIONAL FORMATTING
    '\u202D',  # LEFT-TO-RIGHT OVERRIDE
    '\u202E',  # RIGHT-TO-LEFT OVERRIDE
    '\u2066',  # LEFT-TO-RIGHT ISOLATE
    '\u2067',  # RIGHT-TO-LEFT ISOLATE
    '\u2068',  # FIRST STRONG ISOLATE
    '\u2069',  # POP DIRECTIONAL ISOLATE
}

# Zero-width and invisible characters that can hide content or break parsing
INVISIBLE_CHARS = {
    '\u200B',  # ZERO WIDTH SPACE
    '\u200C',  # ZERO WIDTH NON-JOINER
    '\u200D',  # ZERO WIDTH JOINER
    '\u200E',  # LEFT-TO-RIGHT MARK
    '\u200F',  # RIGHT-TO-LEFT MARK
    '\u2060',  # WORD JOINER
    '\u2061',  # FUNCTION APPLICATION
    '\u2062',  # INVISIBLE TIMES
    '\u2063',  # INVISIBLE SEPARATOR
    '\u2064',  # INVISIBLE PLUS
    '\uFEFF',  # ZERO WIDTH NO-BREAK SPACE (BOM)
    '\u00AD',  # SOFT HYPHEN
}

# Combining characters that can stack and create visual exploits
# We limit the number of consecutive combining marks
MAX_COMBINING_MARKS = 3

# Characters that look like ASCII but aren't (confusables/homoglyphs)
# This is a subset of the most common attack vectors
CONFUSABLE_MAP = {
    # Cyrillic lookalikes
    '\u0430': 'a',  # Cyrillic small a
    '\u0435': 'e',  # Cyrillic small ie
    '\u043E': 'o',  # Cyrillic small o
    '\u0440': 'p',  # Cyrillic small er
    '\u0441': 'c',  # Cyrillic small es
    '\u0443': 'y',  # Cyrillic small u
    '\u0445': 'x',  # Cyrillic small ha
    '\u0410': 'A',  # Cyrillic capital A
    '\u0412': 'B',  # Cyrillic capital Ve
    '\u0415': 'E',  # Cyrillic capital Ie
    '\u041A': 'K',  # Cyrillic capital Ka
    '\u041C': 'M',  # Cyrillic capital Em
    '\u041D': 'H',  # Cyrillic capital En
    '\u041E': 'O',  # Cyrillic capital O
    '\u0420': 'P',  # Cyrillic capital Er
    '\u0421': 'C',  # Cyrillic capital Es
    '\u0422': 'T',  # Cyrillic capital Te
    '\u0425': 'X',  # Cyrillic capital Ha
    # Greek lookalikes
    '\u03B1': 'a',  # Greek small alpha
    '\u03B5': 'e',  # Greek small epsilon
    '\u03BF': 'o',  # Greek small omicron
    '\u0391': 'A',  # Greek capital alpha
    '\u0392': 'B',  # Greek capital beta
    '\u0395': 'E',  # Greek capital epsilon
    '\u0397': 'H',  # Greek capital eta
    '\u039A': 'K',  # Greek capital kappa
    '\u039C': 'M',  # Greek capital mu
    '\u039D': 'N',  # Greek capital nu
    '\u039F': 'O',  # Greek capital omicron
    '\u03A1': 'P',  # Greek capital rho
    '\u03A4': 'T',  # Greek capital tau
    '\u03A7': 'X',  # Greek capital chi
    # Fullwidth ASCII (used in CJK contexts)
    '\uFF21': 'A', '\uFF22': 'B', '\uFF23': 'C', '\uFF24': 'D', '\uFF25': 'E',
    '\uFF26': 'F', '\uFF27': 'G', '\uFF28': 'H', '\uFF29': 'I', '\uFF2A': 'J',
    '\uFF2B': 'K', '\uFF2C': 'L', '\uFF2D': 'M', '\uFF2E': 'N', '\uFF2F': 'O',
    '\uFF30': 'P', '\uFF31': 'Q', '\uFF32': 'R', '\uFF33': 'S', '\uFF34': 'T',
    '\uFF35': 'U', '\uFF36': 'V', '\uFF37': 'W', '\uFF38': 'X', '\uFF39': 'Y',
    '\uFF3A': 'Z',
    '\uFF41': 'a', '\uFF42': 'b', '\uFF43': 'c', '\uFF44': 'd', '\uFF45': 'e',
    '\uFF46': 'f', '\uFF47': 'g', '\uFF48': 'h', '\uFF49': 'i', '\uFF4A': 'j',
    '\uFF4B': 'k', '\uFF4C': 'l', '\uFF4D': 'm', '\uFF4E': 'n', '\uFF4F': 'o',
    '\uFF50': 'p', '\uFF51': 'q', '\uFF52': 'r', '\uFF53': 's', '\uFF54': 't',
    '\uFF55': 'u', '\uFF56': 'v', '\uFF57': 'w', '\uFF58': 'x', '\uFF59': 'y',
    '\uFF5A': 'z',
    '\uFF10': '0', '\uFF11': '1', '\uFF12': '2', '\uFF13': '3', '\uFF14': '4',
    '\uFF15': '5', '\uFF16': '6', '\uFF17': '7', '\uFF18': '8', '\uFF19': '9',
}


# =============================================================================
# Core Sanitization Functions
# =============================================================================

def remove_control_characters(text: str) -> str:
    """Remove dangerous control characters while preserving safe whitespace."""
    return CONTROL_CHAR_PATTERN.sub('', text)


def remove_bidi_overrides(text: str) -> str:
    """Remove bidirectional text override characters."""
    return ''.join(c for c in text if c not in BIDI_OVERRIDE_CHARS)


def remove_invisible_characters(text: str) -> str:
    """Remove zero-width and invisible characters."""
    return ''.join(c for c in text if c not in INVISIBLE_CHARS)


def normalize_confusables(text: str) -> str:
    """Replace common confusable characters with their ASCII equivalents."""
    return ''.join(CONFUSABLE_MAP.get(c, c) for c in text)


def limit_combining_marks(text: str, max_consecutive: int = MAX_COMBINING_MARKS) -> str:
    """
    Limit consecutive combining marks to prevent stacking exploits.

    Zalgo text and similar attacks use many combining marks to create
    visual disruption.
    """
    result = []
    combining_count = 0

    for char in text:
        if unicodedata.category(char).startswith('M'):  # Mark category
            combining_count += 1
            if combining_count <= max_consecutive:
                result.append(char)
        else:
            combining_count = 0
            result.append(char)

    return ''.join(result)


def normalize_unicode(text: str) -> str:
    """
    Normalize Unicode to NFC form.

    This combines characters where possible and provides consistent
    representation, preventing some comparison attacks.
    """
    return unicodedata.normalize('NFC', text)


def normalize_whitespace(text: str) -> str:
    """
    Normalize various Unicode whitespace characters to regular spaces.

    Prevents exploits using unusual whitespace characters.
    """
    # Unicode whitespace characters
    whitespace_chars = {
        '\u00A0',  # NO-BREAK SPACE
        '\u1680',  # OGHAM SPACE MARK
        '\u2000',  # EN QUAD
        '\u2001',  # EM QUAD
        '\u2002',  # EN SPACE
        '\u2003',  # EM SPACE
        '\u2004',  # THREE-PER-EM SPACE
        '\u2005',  # FOUR-PER-EM SPACE
        '\u2006',  # SIX-PER-EM SPACE
        '\u2007',  # FIGURE SPACE
        '\u2008',  # PUNCTUATION SPACE
        '\u2009',  # THIN SPACE
        '\u200A',  # HAIR SPACE
        '\u202F',  # NARROW NO-BREAK SPACE
        '\u205F',  # MEDIUM MATHEMATICAL SPACE
        '\u3000',  # IDEOGRAPHIC SPACE
    }

    return ''.join(' ' if c in whitespace_chars else c for c in text)


# =============================================================================
# High-Level Sanitization Functions
# =============================================================================

def sanitize_command(command: str, config: SanitizationConfig = None) -> tuple[str, bool]:
    """
    Sanitize a command input string.

    Args:
        command: Raw command string from user
        config: Optional configuration (uses global config if not provided)

    Returns:
        (sanitized_command, was_modified)
        - sanitized_command: Safe string for processing
        - was_modified: True if any sanitization was applied
    """
    if config is None:
        config = sanitization_config

    original = command

    # Handle None or non-string input
    if not isinstance(command, str):
        return "", True

    # Truncate to max length first
    if len(command) > config.max_command_length:
        command = command[:config.max_command_length]

    # Apply sanitization pipeline
    command = normalize_unicode(command)
    command = remove_control_characters(command)
    command = remove_bidi_overrides(command)
    command = remove_invisible_characters(command)
    command = normalize_whitespace(command)
    command = limit_combining_marks(command)

    # Strip leading/trailing whitespace
    command = command.strip()

    # Collapse multiple spaces to single space
    command = re.sub(r' +', ' ', command)

    was_modified = command != original

    if was_modified:
        logger.debug(f"Command sanitized: {original!r} -> {command!r}")

    return command, was_modified


def sanitize_player_name(name: str, config: SanitizationConfig = None) -> tuple[str, bool, str | None]:
    """
    Sanitize and validate a player/character name.

    Names are more restrictive than commands because they're used for
    identification and could be used for impersonation attacks.

    Args:
        name: Raw name input
        config: Optional configuration

    Returns:
        (sanitized_name, is_valid, error_message)
        - sanitized_name: The sanitized name (may be empty if invalid)
        - is_valid: True if the name passes all validation
        - error_message: Description of validation failure, or None if valid
    """
    if config is None:
        config = sanitization_config

    original = name

    # Handle None or non-string input
    if not isinstance(name, str):
        return "", False, "Name must be a string"

    # Normalize and clean
    name = normalize_unicode(name)
    name = remove_control_characters(name)
    name = remove_bidi_overrides(name)
    name = remove_invisible_characters(name)
    name = normalize_confusables(name)  # Important for names to prevent impersonation
    name = limit_combining_marks(name, max_consecutive=1)  # Stricter for names
    name = name.strip()

    # Length validation
    if len(name) < config.min_name_length:
        return name, False, f"Name must be at least {config.min_name_length} characters"

    if len(name) > config.max_name_length:
        return name[:config.max_name_length], False, f"Name must be at most {config.max_name_length} characters"

    # Character validation: alphanumeric, spaces, hyphens, apostrophes
    # This allows names like "John", "Mary-Jane", "O'Brien", "Dark Knight"
    allowed_pattern = re.compile(r"^[a-zA-Z0-9 '\-]+$")
    if not allowed_pattern.match(name):
        return name, False, "Name can only contain letters, numbers, spaces, hyphens, and apostrophes"

    # No leading/trailing spaces or hyphens
    if name.startswith((' ', '-', "'")) or name.endswith((' ', '-', "'")):
        return name, False, "Name cannot start or end with spaces or special characters"

    # No consecutive special characters
    if re.search(r"['\- ]{2,}", name):
        return name, False, "Name cannot have consecutive special characters"

    # Must start with a letter
    if not name[0].isalpha():
        return name, False, "Name must start with a letter"

    was_modified = name != original

    if was_modified:
        logger.debug(f"Player name sanitized: {original!r} -> {name!r}")

    return name, True, None


def sanitize_chat_text(text: str, config: SanitizationConfig = None) -> tuple[str, bool]:
    """
    Sanitize chat/say text for safe display.

    More permissive than command sanitization since it's meant for
    creative expression, but still blocks exploits.

    Args:
        text: Raw chat text
        config: Optional configuration

    Returns:
        (sanitized_text, was_modified)
    """
    if config is None:
        config = sanitization_config

    original = text

    # Handle None or non-string input
    if not isinstance(text, str):
        return "", True

    # Truncate to max length
    if len(text) > config.max_chat_length:
        text = text[:config.max_chat_length]

    # Apply sanitization - less aggressive than names
    text = normalize_unicode(text)
    text = remove_control_characters(text)
    text = remove_bidi_overrides(text)
    text = remove_invisible_characters(text)
    text = normalize_whitespace(text)
    text = limit_combining_marks(text)  # Default limit

    # Strip leading/trailing whitespace
    text = text.strip()

    was_modified = text != original

    if was_modified:
        logger.debug(f"Chat text sanitized: {original!r} -> {text!r}")

    return text, was_modified


# =============================================================================
# Utility Functions
# =============================================================================

def is_safe_string(text: str) -> tuple[bool, str | None]:
    """
    Check if a string is safe without modifying it.

    Returns:
        (is_safe, reason) - reason describes why it's not safe, or None
    """
    if not isinstance(text, str):
        return False, "Input is not a string"

    # Check for control characters
    if CONTROL_CHAR_PATTERN.search(text):
        return False, "Contains control characters"

    # Check for bidi overrides
    if any(c in BIDI_OVERRIDE_CHARS for c in text):
        return False, "Contains bidirectional override characters"

    # Check for invisible characters
    if any(c in INVISIBLE_CHARS for c in text):
        return False, "Contains invisible characters"

    # Check for excessive combining marks
    combining_count = 0
    for char in text:
        if unicodedata.category(char).startswith('M'):
            combining_count += 1
            if combining_count > MAX_COMBINING_MARKS:
                return False, "Contains excessive combining marks (possible Zalgo text)"
        else:
            combining_count = 0

    return True, None


def get_sanitization_stats(text: str) -> dict:
    """
    Get statistics about what would be sanitized in a string.

    Useful for logging and debugging.
    """
    stats = {
        "original_length": len(text),
        "control_chars": len(CONTROL_CHAR_PATTERN.findall(text)),
        "bidi_overrides": sum(1 for c in text if c in BIDI_OVERRIDE_CHARS),
        "invisible_chars": sum(1 for c in text if c in INVISIBLE_CHARS),
        "confusable_chars": sum(1 for c in text if c in CONFUSABLE_MAP),
        "combining_marks": sum(1 for c in text if unicodedata.category(c).startswith('M')),
    }

    return stats
