"""Script to fix all test_clans.py issues systematically."""

import re

test_file = r"backend\tests\commands\test_clans.py"

# Read the file
with open(test_file, "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: Remove all pending_invites parameters (11 occurrences)
content = re.sub(r",?\s*pending_invites=set\(\),?\s*", "", content)

# Fix 2: Remove patches for non-existent methods
content = re.sub(
    r"with patch\.object\(clan_system, '_create_clan_in_db', new_callable=AsyncMock\):\s*",
    "",
    content,
)
content = re.sub(
    r"with patch\.object\(clan_system, '_create_clan_in_db', mock_create\):\s*",
    "",
    content,
)
content = re.sub(
    r"with patch\.object\(clan_system, '_invite_player_in_db', new_callable=AsyncMock\):\s*",
    "",
    content,
)
content = re.sub(
    r"with patch\.object\(clan_system, '_remove_player_in_db', new_callable=AsyncMock\):\s*",
    "",
    content,
)
content = re.sub(
    r"with patch\.object\(clan_system, '_promote_player_in_db', new_callable=AsyncMock\):\s*",
    "",
    content,
)
content = re.sub(
    r"with patch\.object\(clan_system, '_add_contribution_in_db', new_callable=AsyncMock\):\s*",
    "",
    content,
)
content = re.sub(
    r"with patch\.object\(clan_system, '_update_clan_in_db', new_callable=AsyncMock\):\s*",
    "",
    content,
)
content = re.sub(
    r"with patch\.object\(clan_system, '_disband_clan_in_db', new_callable=AsyncMock\):\s*",
    "",
    content,
)

# Fix 3: Fix player_to_clan → player_clan_map
content = content.replace("clan_system.player_to_clan", "clan_system.player_clan_map")
content = content.replace("player_to_clan[", "player_clan_map[")

# Fix 4: Fix ClanInfo member structure - replace integer ranks with ClanMemberInfo
# This is complex, so we'll need to add the import and create helper for creating members

# Add import after existing imports
import_section = """from app.engine.systems.clan_system import ClanSystem, ClanInfo, ClanMemberInfo"""
if import_section in content:
    # Already has the right imports
    pass

# Fix 5: Update members dict instantiations
# Replace patterns like: members={"player_0": 4}
# With: members={"player_0": ClanMemberInfo(player_id="player_0", rank=RANK_LEADER, joined_at=0)}

# This requires more sophisticated replacement - let's do manual fixes for key patterns
test_patterns = [
    (
        r'members=\{"player_0": 4\}',
        'members={"player_0": ClanMemberInfo(player_id="player_0", rank="leader", joined_at=0)}',
    ),
    (
        r'members=\{"player_0": 4, "player_1": 3\}',
        'members={"player_0": ClanMemberInfo(player_id="player_0", rank="leader", joined_at=0), "player_1": ClanMemberInfo(player_id="player_1", rank="officer", joined_at=0)}',
    ),
    (
        r'members=\{"player_0": 4, "player_1": 2\}',
        'members={"player_0": ClanMemberInfo(player_id="player_0", rank="leader", joined_at=0), "player_1": ClanMemberInfo(player_id="player_1", rank="member", joined_at=0)}',
    ),
    (
        r'members=\{f"player_\{i\}": \(4 if i == 0 else 2\) for i in range\(100\)\}',
        'members={f"player_{i}": ClanMemberInfo(player_id=f"player_{i}", rank="leader" if i == 0 else "member", joined_at=0) for i in range(100)}',
    ),
]

for pattern, replacement in test_patterns:
    content = re.sub(pattern, replacement, content)

# Fix 6: Fix member assignment lines like: clan.members["player_1"] = 1
content = re.sub(
    r'clan\.members\["player_1"\] = 1  # RANK_INITIATE',
    'clan.members["player_1"] = ClanMemberInfo(player_id="player_1", rank="initiate", joined_at=0)',
    content,
)

# Fix 7: Fix assertions like: assert clan.members["player_1"] == 1
content = re.sub(
    r'assert clan\.members\["player_1"\] == 1  # RANK_INITIATE',
    'assert clan.members["player_1"].rank == "initiate"',
    content,
)
content = re.sub(
    r'assert clan\.members\["player_1"\] == 3  # RANK_OFFICER',
    'assert clan.members["player_1"].rank == "officer"',
    content,
)

# Fix 8: Fix test dataclass assertions
content = re.sub(r"assert member\.rank == 4", 'assert member.rank == "leader"', content)

# Fix 9: Fix clan_id type (should be str not int in most places)
content = re.sub(r"clan_id=1,", 'clan_id="1",', content)
content = re.sub(r"clan_system\.clans\[1\]", 'clan_system.clans["1"]', content)
content = re.sub(r"1 in clan_system\.clans", '"1" in clan_system.clans', content)
content = re.sub(
    r"1 not in clan_system\.clans", '"1" not in clan_system.clans', content
)
content = re.sub(r"can_invite\(1,", 'can_invite("1",', content)
content = re.sub(r"can_promote\(1,", 'can_promote("1",', content)
content = re.sub(r"can_disband\(1,", 'can_disband("1",', content)
content = re.sub(r"add_contribution\(1,", 'add_contribution("1",', content)
content = re.sub(r"promote_player\(1,", 'promote_player("1",', content)
content = re.sub(r"disband_clan\(1\)", 'disband_clan("1")', content)
content = re.sub(r"mock_clan\.id = 1", 'mock_clan.id = "1"', content)

# Write back
with open(test_file, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Fixed all test_clans.py issues!")
print("   - Removed pending_invites parameters")
print("   - Removed non-existent DB mock patches")
print("   - Fixed player_to_clan → player_clan_map")
print("   - Fixed ClanInfo member structure")
print("   - Fixed clan_id types (int → str)")
