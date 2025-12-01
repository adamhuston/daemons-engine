"""Fix all test_social.py issues - player names and missing fields."""

import re

test_file = r"backend\tests\commands\test_social.py"

with open(test_file, encoding="utf-8") as f:
    content = f.read()

# Fix 1: Replace all "player_X" references in command args with "PlayerX"
# Pattern: handle_tell/follow/ignore commands use player names, not IDs
replacements = [
    (r'"player_0 ', '"Player0 '),
    (r'"player_1 ', '"Player1 '),
    (r'"player_2 ', '"Player2 '),
    (r'"player_3 ', '"Player3 '),
    (r'"player_4 ', '"Player4 '),
    (r' player_0"', ' Player0"'),
    (r' player_1"', ' Player1"'),
    (r' player_2"', ' Player2"'),
    (r' player_3"', ' Player3"'),
    (r' player_4"', ' Player4"'),
    # For follow/ignore commands that just have the name
    (
        r'handle_follow\("player_0", "Player0", "player_1"\)',
        'handle_follow("player_0", "Player0", "Player1")',
    ),
    (
        r'handle_follow\("player_0", "Player0", "player_0"\)',
        'handle_follow("player_0", "Player0", "Player0")',
    ),
    (
        r'handle_follow\("player_0", "Player0", "player_2"\)',
        'handle_follow("player_0", "Player0", "Player2")',
    ),
    (
        r'handle_follow\("player_0", "Player0", "player_3"\)',
        'handle_follow("player_0", "Player0", "Player3")',
    ),
    (
        r'handle_ignore\("player_0", "Player0", "player_1"\)',
        'handle_ignore("player_0", "Player0", "Player1")',
    ),
    (
        r'handle_ignore\("player_0", "Player0", "player_2"\)',
        'handle_ignore("player_0", "Player0", "Player2")',
    ),
    (
        r'handle_ignore\("player_0", "Player0", "player_3"\)',
        'handle_ignore("player_0", "Player0", "Player3")',
    ),
    (
        r'handle_ignore\("player_0", "Player0", "player_4"\)',
        'handle_ignore("player_0", "Player0", "Player4")',
    ),
    (
        r'handle_unfollow\("player_0", "Player0", "player_1"\)',
        'handle_unfollow("player_0", "Player0", "Player1")',
    ),
    (
        r'handle_unignore\("player_0", "Player0", "player_1"\)',
        'handle_unignore("player_0", "Player0", "Player1")',
    ),
]

for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)

# Write back
with open(test_file, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Fixed all test_social.py player name issues!")
print("   - Changed 'player_X' to 'PlayerX' in command arguments")
print("   - Player names now match fixture (Player0, Player1, etc.)")
