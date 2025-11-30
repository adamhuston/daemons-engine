"""Fix indentation issues in test_clans.py"""
import re

test_file = r"backend\tests\commands\test_clans.py"

with open(test_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Fix indentation for lines following clan creation
fixed_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    fixed_lines.append(line)

    # Check if this is a clan creation line
    if re.match(r"        clan = await clan_system\.create_clan", line):
        # Check next lines for improper indentation (12 spaces instead of 8)
        i += 1
        while (
            i < len(lines)
            and lines[i].startswith("            ")
            and not lines[i].strip().startswith("#")
            and not lines[i].strip().startswith('"""')
        ):
            # Fix indentation: remove 4 spaces
            fixed_line = lines[i][4:]
            fixed_lines.append(fixed_line)
            i += 1
        continue

    i += 1

# Write back
with open(test_file, "w", encoding="utf-8") as f:
    f.writelines(fixed_lines)

print("✅ Fixed indentation issues in test_clans.py")
