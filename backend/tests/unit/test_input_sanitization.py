"""
Unit tests for Input Sanitization Module (Phase 16.5).

Tests command sanitization, player name validation, and chat text sanitization.
"""


from daemons.input_sanitization import (
    SanitizationConfig,
    get_sanitization_stats,
    is_safe_string,
    limit_combining_marks,
    normalize_confusables,
    normalize_unicode,
    remove_bidi_overrides,
    remove_control_characters,
    remove_invisible_characters,
    sanitization_config,
    sanitize_chat_text,
    sanitize_command,
    sanitize_player_name,
)

# =============================================================================
# Test Control Character Removal
# =============================================================================


class TestControlCharacterRemoval:
    """Tests for control character filtering."""

    def test_removes_null_byte(self):
        """Test that null bytes are removed."""
        result = remove_control_characters("hello\x00world")
        assert result == "helloworld"

    def test_removes_bell_character(self):
        """Test that bell character is removed."""
        result = remove_control_characters("alert\x07here")
        assert result == "alerthere"

    def test_preserves_newline(self):
        """Test that newlines are preserved."""
        result = remove_control_characters("line1\nline2")
        assert result == "line1\nline2"

    def test_preserves_tab(self):
        """Test that tabs are preserved."""
        result = remove_control_characters("col1\tcol2")
        assert result == "col1\tcol2"

    def test_preserves_carriage_return(self):
        """Test that carriage returns are preserved."""
        result = remove_control_characters("line1\r\nline2")
        assert result == "line1\r\nline2"

    def test_removes_escape_sequence(self):
        """Test that escape character is removed."""
        result = remove_control_characters("text\x1b[31mred")
        assert result == "text[31mred"

    def test_removes_c1_controls(self):
        """Test that C1 control characters (0x80-0x9F) are removed."""
        result = remove_control_characters("test\x80\x9fend")
        assert result == "testend"


# =============================================================================
# Test Bidi Override Removal
# =============================================================================


class TestBidiOverrideRemoval:
    """Tests for bidirectional text override removal."""

    def test_removes_rtl_override(self):
        """Test that RTL override is removed."""
        result = remove_bidi_overrides("hello\u202Eworld")
        assert result == "helloworld"

    def test_removes_ltr_override(self):
        """Test that LTR override is removed."""
        result = remove_bidi_overrides("hello\u202Dworld")
        assert result == "helloworld"

    def test_removes_all_bidi_chars(self):
        """Test that all bidi override characters are removed."""
        bidi_chars = "\u202A\u202B\u202C\u202D\u202E\u2066\u2067\u2068\u2069"
        result = remove_bidi_overrides(f"test{bidi_chars}end")
        assert result == "testend"

    def test_preserves_regular_text(self):
        """Test that regular text is unchanged."""
        result = remove_bidi_overrides("Hello, world!")
        assert result == "Hello, world!"


# =============================================================================
# Test Invisible Character Removal
# =============================================================================


class TestInvisibleCharacterRemoval:
    """Tests for zero-width and invisible character removal."""

    def test_removes_zero_width_space(self):
        """Test that zero-width space is removed."""
        result = remove_invisible_characters("hello\u200Bworld")
        assert result == "helloworld"

    def test_removes_zero_width_joiner(self):
        """Test that zero-width joiner is removed."""
        result = remove_invisible_characters("a\u200Db")
        assert result == "ab"

    def test_removes_bom(self):
        """Test that BOM is removed."""
        result = remove_invisible_characters("\uFEFFtext")
        assert result == "text"

    def test_removes_soft_hyphen(self):
        """Test that soft hyphen is removed."""
        result = remove_invisible_characters("hyphen\u00ADated")
        assert result == "hyphenated"


# =============================================================================
# Test Confusable Character Normalization
# =============================================================================


class TestConfusableNormalization:
    """Tests for homoglyph/confusable character normalization."""

    def test_cyrillic_a_normalized(self):
        """Test that Cyrillic 'a' is normalized to ASCII."""
        result = normalize_confusables("\u0430dmin")  # Cyrillic small a
        assert result == "admin"

    def test_greek_alpha_normalized(self):
        """Test that Greek alpha is normalized to ASCII."""
        result = normalize_confusables("\u03B1pple")  # Greek small alpha
        assert result == "apple"

    def test_fullwidth_ascii_normalized(self):
        """Test that fullwidth ASCII is normalized."""
        result = normalize_confusables("\uFF21\uFF42\uFF43")  # Fullwidth ABC
        assert result == "Abc"

    def test_mixed_confusables(self):
        """Test multiple confusable characters together."""
        # "Admin" with Cyrillic A and o
        result = normalize_confusables("\u0410dmin\u043E")
        assert result == "Admino"

    def test_preserves_normal_text(self):
        """Test that normal ASCII is unchanged."""
        result = normalize_confusables("NormalText123")
        assert result == "NormalText123"


# =============================================================================
# Test Combining Mark Limiting
# =============================================================================


class TestCombiningMarkLimiting:
    """Tests for Zalgo text / combining mark limiting."""

    def test_allows_normal_diacritics(self):
        """Test that normal diacritical marks are preserved."""
        # café with combining acute accent - the mark should be preserved
        text = "cafe\u0301"
        result = limit_combining_marks(text)
        # Should keep the combining mark (only limits, doesn't remove single marks)
        assert "\u0301" in result or "é" in result  # Either combining or precomposed

    def test_limits_excessive_marks(self):
        """Test that excessive combining marks are limited."""
        # 10 combining acute accents
        zalgo = "a" + "\u0301" * 10
        result = limit_combining_marks(zalgo, max_consecutive=3)
        # Should have 'a' plus 3 marks
        assert len(result) == 4

    def test_resets_count_for_base_chars(self):
        """Test that count resets between base characters."""
        # 2 marks on 'a', then 'b', then 2 more marks
        text = "a\u0301\u0302b\u0303\u0304"
        result = limit_combining_marks(text, max_consecutive=2)
        assert result == text  # All should pass

    def test_zalgo_text_limited(self):
        """Test that Zalgo-style text is properly limited."""
        # Simulated Zalgo: letter with many stacking marks
        zalgo = "H" + "\u0300\u0301\u0302\u0303\u0304\u0305\u0306\u0307\u0308"
        result = limit_combining_marks(zalgo, max_consecutive=3)
        # Should be 'H' + 3 marks = 4 characters
        assert len(result) == 4


# =============================================================================
# Test Command Sanitization
# =============================================================================


class TestCommandSanitization:
    """Tests for command input sanitization."""

    def test_normal_command_unchanged(self):
        """Test that normal commands pass through unchanged."""
        result, modified = sanitize_command("look north")
        assert result == "look north"
        assert modified is False

    def test_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        result, modified = sanitize_command("  look  ")
        assert result == "look"
        assert modified is True

    def test_collapses_multiple_spaces(self):
        """Test that multiple spaces are collapsed."""
        result, modified = sanitize_command("say    hello    world")
        assert result == "say hello world"
        assert modified is True

    def test_truncates_long_commands(self):
        """Test that commands exceeding max length are truncated."""
        config = SanitizationConfig()
        config.max_command_length = 20
        result, modified = sanitize_command("a" * 100, config)
        assert len(result) == 20
        assert modified is True

    def test_removes_control_characters(self):
        """Test that control characters are removed."""
        result, modified = sanitize_command("look\x00north")
        assert result == "looknorth"
        assert modified is True

    def test_removes_bidi_overrides(self):
        """Test that bidi overrides are removed."""
        result, modified = sanitize_command("say \u202Ehello")
        assert result == "say hello"
        assert modified is True

    def test_removes_invisible_chars(self):
        """Test that invisible characters are removed."""
        result, modified = sanitize_command("attack\u200Bgoblin")
        assert result == "attackgoblin"
        assert modified is True

    def test_handles_none_input(self):
        """Test handling of None input."""
        result, modified = sanitize_command(None)
        assert result == ""
        assert modified is True

    def test_handles_non_string(self):
        """Test handling of non-string input."""
        result, modified = sanitize_command(123)
        assert result == ""
        assert modified is True

    def test_empty_string(self):
        """Test handling of empty string."""
        result, modified = sanitize_command("")
        assert result == ""
        # Empty string stripping counts as modification
        assert modified is False

    def test_normalizes_unicode_whitespace(self):
        """Test that Unicode whitespace is normalized."""
        result, modified = sanitize_command("say\u00A0hello")  # No-break space
        assert result == "say hello"
        assert modified is True


# =============================================================================
# Test Player Name Sanitization
# =============================================================================


class TestPlayerNameSanitization:
    """Tests for player/character name validation."""

    def test_valid_simple_name(self):
        """Test that simple valid names pass."""
        result, valid, error = sanitize_player_name("Knight")
        assert result == "Knight"
        assert valid is True
        assert error is None

    def test_valid_name_with_space(self):
        """Test that names with spaces are valid."""
        result, valid, error = sanitize_player_name("Dark Knight")
        assert result == "Dark Knight"
        assert valid is True

    def test_valid_name_with_hyphen(self):
        """Test that hyphenated names are valid."""
        result, valid, error = sanitize_player_name("Mary-Jane")
        assert result == "Mary-Jane"
        assert valid is True

    def test_valid_name_with_apostrophe(self):
        """Test that names with apostrophes are valid."""
        result, valid, error = sanitize_player_name("O'Brien")
        assert result == "O'Brien"
        assert valid is True

    def test_too_short(self):
        """Test that names that are too short fail."""
        result, valid, error = sanitize_player_name("A")
        assert valid is False
        assert "at least" in error

    def test_too_long(self):
        """Test that names that are too long fail."""
        result, valid, error = sanitize_player_name("A" * 30)
        assert valid is False
        assert "at most" in error

    def test_invalid_characters(self):
        """Test that names with invalid characters fail."""
        result, valid, error = sanitize_player_name("Player@123")
        assert valid is False
        assert "letters" in error.lower()

    def test_starts_with_number(self):
        """Test that names starting with numbers fail."""
        result, valid, error = sanitize_player_name("123Player")
        assert valid is False
        assert "start with a letter" in error

    def test_starts_with_special(self):
        """Test that names starting with special chars fail."""
        result, valid, error = sanitize_player_name("-Knight")
        assert valid is False

    def test_consecutive_special_chars(self):
        """Test that consecutive special characters fail."""
        result, valid, error = sanitize_player_name("Name--Here")
        assert valid is False
        assert "consecutive" in error

    def test_confusables_normalized(self):
        """Test that confusable characters are normalized."""
        # Using Cyrillic 'a' instead of ASCII 'a'
        result, valid, error = sanitize_player_name("Knigh\u0442")  # Cyrillic 't'
        # After normalization, should be valid ASCII
        assert "t" in result or not valid  # Either normalized or rejected

    def test_removes_invisible_chars(self):
        """Test that invisible characters are removed from names."""
        result, valid, error = sanitize_player_name("Kni\u200Bght")  # Zero-width space
        assert result == "Knight"
        assert valid is True

    def test_handles_none(self):
        """Test handling of None input."""
        result, valid, error = sanitize_player_name(None)
        assert valid is False
        assert "string" in error.lower()


# =============================================================================
# Test Chat Text Sanitization
# =============================================================================


class TestChatTextSanitization:
    """Tests for chat/say text sanitization."""

    def test_normal_text_unchanged(self):
        """Test that normal chat text passes through."""
        result, modified = sanitize_chat_text("Hello, how are you?")
        assert result == "Hello, how are you?"
        assert modified is False

    def test_allows_punctuation(self):
        """Test that punctuation is allowed."""
        result, modified = sanitize_chat_text("Wow! That's amazing... isn't it?")
        assert result == "Wow! That's amazing... isn't it?"
        assert modified is False

    def test_truncates_long_text(self):
        """Test that text exceeding max length is truncated."""
        config = SanitizationConfig()
        config.max_chat_length = 50
        result, modified = sanitize_chat_text("a" * 100, config)
        assert len(result) == 50
        assert modified is True

    def test_removes_bidi_overrides(self):
        """Test that bidi overrides are removed from chat."""
        result, modified = sanitize_chat_text("Hello \u202Eworld")
        assert "\u202E" not in result
        assert modified is True

    def test_removes_invisible_chars(self):
        """Test that invisible characters are removed."""
        result, modified = sanitize_chat_text("Hello\u200Bworld")
        assert result == "Helloworld"
        assert modified is True

    def test_limits_combining_marks(self):
        """Test that excessive combining marks are limited."""
        # Zalgo-style text
        zalgo = "H" + "\u0300" * 10
        result, modified = sanitize_chat_text(zalgo)
        # Should be limited
        assert len(result) < len(zalgo)
        assert modified is True

    def test_handles_emoji(self):
        """Test that emoji are preserved (they're not invisible/control chars)."""
        result, modified = sanitize_chat_text("Hello 👋 world!")
        assert "👋" in result

    def test_handles_non_string(self):
        """Test handling of non-string input."""
        result, modified = sanitize_chat_text(None)
        assert result == ""
        assert modified is True


# =============================================================================
# Test Utility Functions
# =============================================================================


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_is_safe_string_clean(self):
        """Test that clean strings are marked safe."""
        is_safe, reason = is_safe_string("Hello, world!")
        assert is_safe is True
        assert reason is None

    def test_is_safe_string_control_chars(self):
        """Test that control characters are detected."""
        is_safe, reason = is_safe_string("Hello\x00world")
        assert is_safe is False
        assert "control" in reason.lower()

    def test_is_safe_string_bidi(self):
        """Test that bidi overrides are detected."""
        is_safe, reason = is_safe_string("Hello\u202Eworld")
        assert is_safe is False
        assert "bidirectional" in reason.lower()

    def test_is_safe_string_invisible(self):
        """Test that invisible characters are detected."""
        is_safe, reason = is_safe_string("Hello\u200Bworld")
        assert is_safe is False
        assert "invisible" in reason.lower()

    def test_is_safe_string_zalgo(self):
        """Test that Zalgo text is detected."""
        zalgo = "H" + "\u0300" * 10
        is_safe, reason = is_safe_string(zalgo)
        assert is_safe is False
        assert "combining" in reason.lower()

    def test_get_sanitization_stats(self):
        """Test that sanitization stats are accurate."""
        text = "He\x00llo\u200B\u202Ewo\u0300\u0301rld"
        stats = get_sanitization_stats(text)

        assert stats["original_length"] > 0
        assert stats["control_chars"] == 1  # \x00
        assert stats["invisible_chars"] == 1  # \u200B
        assert stats["bidi_overrides"] == 1  # \u202E
        assert stats["combining_marks"] == 2  # \u0300, \u0301

    def test_normalize_unicode(self):
        """Test Unicode normalization."""
        # Composed vs decomposed forms
        composed = "é"  # Single character
        decomposed = "é"  # e + combining acute

        result1 = normalize_unicode(composed)
        result2 = normalize_unicode(decomposed)

        # Both should normalize to the same form
        assert result1 == result2


# =============================================================================
# Test Global Config
# =============================================================================


class TestGlobalConfig:
    """Tests for global configuration."""

    def test_config_has_defaults(self):
        """Test that default config values are set."""
        assert sanitization_config.max_command_length == 500
        assert sanitization_config.min_name_length == 2
        assert sanitization_config.max_name_length == 24
        assert sanitization_config.max_chat_length == 1000

    def test_custom_config(self):
        """Test using custom config."""
        config = SanitizationConfig()
        config.max_command_length = 100

        result, _ = sanitize_command("a" * 200, config)
        assert len(result) == 100
