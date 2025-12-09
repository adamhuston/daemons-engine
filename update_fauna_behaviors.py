#!/usr/bin/env python3
"""
Update fauna YAML files to add appropriate behaviors based on diet:
- herbivore: add 'grazes'
- carnivore: add 'hunts' 
- omnivore: add both 'grazes' and 'hunts'
- prey animals (with predator_tags): add 'flees_predators'
"""

import os
import re
from pathlib import Path

FAUNA_DIR = Path("backend/daemons/world_data/npcs/fauna")

def get_diet(content: str) -> str:
    """Extract diet from YAML content."""
    match = re.search(r'diet:\s*(\w+)', content)
    return match.group(1) if match else None

def has_predator_tags(content: str) -> bool:
    """Check if fauna has predator_tags (meaning it's prey)."""
    match = re.search(r'predator_tags:\s*\[([^\]]+)\]', content)
    if match:
        tags = match.group(1).strip()
        return bool(tags)  # Non-empty predator_tags
    return False

def get_current_behaviors(content: str) -> list[str]:
    """Extract current behavior list from YAML."""
    # Find behavior section
    match = re.search(r'^behavior:\s*\n((?:  - .+\n)*)', content, re.MULTILINE)
    if not match:
        return []
    
    behavior_section = match.group(1)
    behaviors = re.findall(r'  - (\w+)', behavior_section)
    return behaviors

def update_behaviors(content: str, diet: str, has_predators: bool) -> str:
    """Update behavior list based on diet."""
    current = get_current_behaviors(content)
    needed = []
    
    # Determine needed behaviors based on diet
    if diet == 'herbivore':
        if 'grazes' not in current:
            needed.append('grazes')
    elif diet == 'carnivore':
        if 'hunts' not in current:
            needed.append('hunts')
    elif diet == 'omnivore':
        if 'grazes' not in current:
            needed.append('grazes')
        if 'hunts' not in current:
            needed.append('hunts')
    
    # Prey animals should flee
    if has_predators and 'flees_predators' not in current:
        needed.append('flees_predators')
    
    if not needed:
        return content, []
    
    # Find behavior section and insert new behaviors
    # Insert after "behavior:" line
    match = re.search(r'^(behavior:\s*\n)', content, re.MULTILINE)
    if not match:
        return content, []
    
    insert_point = match.end()
    new_lines = ''.join(f'  - {b}\n' for b in needed)
    
    new_content = content[:insert_point] + new_lines + content[insert_point:]
    return new_content, needed

def main():
    print("Updating fauna behaviors...\n")
    
    updated_files = []
    
    for yaml_file in sorted(FAUNA_DIR.glob("*.yaml")):
        with open(yaml_file, 'r') as f:
            content = f.read()
        
        diet = get_diet(content)
        has_predators = has_predator_tags(content)
        
        if not diet:
            print(f"SKIP {yaml_file.name}: no diet found")
            continue
        
        new_content, added = update_behaviors(content, diet, has_predators)
        
        if added:
            with open(yaml_file, 'w') as f:
                f.write(new_content)
            print(f"UPDATED {yaml_file.name} ({diet}): added {added}")
            updated_files.append((yaml_file.name, diet, added))
        else:
            print(f"OK {yaml_file.name} ({diet}): already has correct behaviors")
    
    print(f"\n=== Summary ===")
    print(f"Updated {len(updated_files)} files")
    for name, diet, added in updated_files:
        print(f"  {name}: +{added}")

if __name__ == "__main__":
    main()
