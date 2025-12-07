#!/usr/bin/env python3
"""
Migration Script: Convert List-Based Ability YAML Files to Individual Files

This script converts the legacy format where ability YAML files contain a list
of abilities under an "abilities:" key into the new format where each ability
is its own YAML file.

Old format (warrior.yaml):
    abilities:
      - ability_id: whirlwind
        name: "Whirlwind Attack"
        ...
      - ability_id: shield_bash
        name: "Shield Bash"
        ...

New format (warrior/whirlwind.yaml):
    ability_id: whirlwind
    name: "Whirlwind Attack"
    ...

Usage:
    python migrate_abilities.py [--dry-run]

Options:
    --dry-run    Show what would be done without making changes
"""

import os
import sys
from pathlib import Path

import yaml


def migrate_abilities(abilities_dir: Path, dry_run: bool = False) -> None:
    """
    Migrate list-based ability YAML files to individual ability files.
    
    Args:
        abilities_dir: Path to the abilities directory
        dry_run: If True, only print what would be done
    """
    if not abilities_dir.exists():
        print(f"Error: Abilities directory does not exist: {abilities_dir}")
        sys.exit(1)
    
    # Track files to process
    files_to_migrate = []
    files_to_skip = []
    
    for yaml_file in sorted(abilities_dir.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            files_to_skip.append(yaml_file.name)
            continue
            
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        
        if not data:
            files_to_skip.append(yaml_file.name)
            continue
            
        # Check if this is list format
        if "abilities" in data and isinstance(data.get("abilities"), list):
            files_to_migrate.append(yaml_file)
        elif "ability_id" in data:
            # Already individual format
            files_to_skip.append(f"{yaml_file.name} (already individual)")
        else:
            files_to_skip.append(f"{yaml_file.name} (unknown format)")
    
    print(f"\n{'=' * 60}")
    print("Ability YAML Migration Script")
    print(f"{'=' * 60}")
    print(f"\nDirectory: {abilities_dir}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"\nFiles to migrate: {len(files_to_migrate)}")
    print(f"Files to skip: {len(files_to_skip)}")
    
    if files_to_skip:
        print(f"\nSkipping:")
        for f in files_to_skip:
            print(f"  - {f}")
    
    if not files_to_migrate:
        print("\nNo files to migrate!")
        return
    
    print(f"\n{'=' * 60}")
    print("Migration Plan")
    print(f"{'=' * 60}")
    
    for yaml_file in files_to_migrate:
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        
        ability_list = data.get("abilities", [])
        
        # Determine the category from filename (e.g., "warrior" from "warrior.yaml")
        category = yaml_file.stem
        category_dir = abilities_dir / category
        
        print(f"\n{yaml_file.name} -> {category}/ directory:")
        print(f"  Contains {len(ability_list)} abilities")
        
        for ability in ability_list:
            ability_id = ability.get("ability_id", "unknown")
            new_file = category_dir / f"{ability_id}.yaml"
            print(f"    -> {category}/{ability_id}.yaml")
        
        if not dry_run:
            # Create category directory
            category_dir.mkdir(exist_ok=True)
            print(f"  Created directory: {category_dir}")
            
            # Write individual ability files
            for ability in ability_list:
                ability_id = ability.get("ability_id", "unknown")
                new_file = category_dir / f"{ability_id}.yaml"
                
                # Add a comment header
                header = f"# {ability.get('name', ability_id)} Ability\n"
                if "description" in ability:
                    header += f"# {ability['description']}\n"
                header += "\n"
                
                yaml_content = yaml.dump(ability, default_flow_style=False, sort_keys=False, allow_unicode=True)
                
                with open(new_file, "w") as f:
                    f.write(header)
                    f.write(yaml_content)
                
                print(f"  Created: {new_file.name}")
            
            # Rename original file to .bak
            backup_file = yaml_file.with_suffix(".yaml.bak")
            yaml_file.rename(backup_file)
            print(f"  Backed up original to: {backup_file.name}")
    
    print(f"\n{'=' * 60}")
    if dry_run:
        print("DRY RUN complete. No changes made.")
        print("Run without --dry-run to apply changes.")
    else:
        print("Migration complete!")
        print("\nOriginal files have been renamed to .yaml.bak")
        print("You can delete them after verifying the migration worked.")
    print(f"{'=' * 60}\n")


def main():
    # Parse arguments
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    
    # Find abilities directory
    script_dir = Path(__file__).parent
    
    # Check common locations
    possible_paths = [
        script_dir / "backend" / "daemons" / "world_data" / "abilities",
        script_dir / "daemons" / "world_data" / "abilities",
        script_dir.parent / "backend" / "daemons" / "world_data" / "abilities",
        Path("backend/daemons/world_data/abilities"),
    ]
    
    abilities_dir = None
    for path in possible_paths:
        if path.exists():
            abilities_dir = path.resolve()
            break
    
    if not abilities_dir:
        print("Error: Could not find abilities directory.")
        print("Run this script from the project root or specify the path.")
        sys.exit(1)
    
    migrate_abilities(abilities_dir, dry_run)


if __name__ == "__main__":
    main()
