"""
Build LLM context files from documentation.

Generates:
- llm_context_index.md: High-level overview with file map (always attach this)
- llm_context_architecture.md: Core systems deep dive
- llm_context_protocol.md: WebSocket/HTTP protocol reference
- llm_context_content.md: YAML content authoring guide

Usage:
    python docs/build_docs/build_context.py

For your own game, run from your project root to include your customizations.
"""

from datetime import datetime
from pathlib import Path


def find_project_root() -> Path:
    """Find the project root by looking for key markers."""
    current = Path.cwd()

    # Walk up looking for docs/ or world_data/
    for parent in [current] + list(current.parents):
        if (parent / "docs").is_dir() or (parent / "world_data").is_dir():
            return parent

    return current


def gather_docs(docs_dir: Path) -> dict[str, str]:
    """Gather all markdown files from docs directory."""
    docs = {}

    if not docs_dir.exists():
        return docs

    for md_file in docs_dir.rglob("*.md"):
        # Skip build_docs output files
        if "build_docs" in str(md_file) and md_file.name.startswith("llm_context"):
            continue

        rel_path = md_file.relative_to(docs_dir)
        try:
            docs[str(rel_path)] = md_file.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Warning: Could not read {md_file}: {e}")

    return docs


def gather_yaml_examples(world_data_dir: Path, max_per_type: int = 2) -> dict[str, list[str]]:
    """Gather example YAML files from world_data directory."""
    examples = {}

    if not world_data_dir.exists():
        return examples

    for subdir in world_data_dir.iterdir():
        if subdir.is_dir():
            yaml_files = list(subdir.glob("*.yaml")) + list(subdir.glob("*.yml"))
            examples[subdir.name] = []

            for yaml_file in yaml_files[:max_per_type]:
                try:
                    content = yaml_file.read_text(encoding="utf-8")
                    examples[subdir.name].append({
                        "name": yaml_file.name,
                        "content": content
                    })
                except Exception as e:
                    print(f"Warning: Could not read {yaml_file}: {e}")

    return examples


def build_index(docs: dict[str, str], yaml_examples: dict[str, list]) -> str:
    """Build the main index context file."""
    lines = [
        "# Daemons Engine - LLM Context Index",
        "",
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "This file provides an overview of the Daemons Engine codebase.",
        "Attach this to your AI assistant for general questions about the project.",
        "For specific tasks, also attach the relevant domain-specific context file.",
        "",
        "## Quick Reference",
        "",
        "| Context File | Use When |",
        "|--------------|----------|",
        "| `llm_context_index.md` | General questions, orientation |",
        "| `llm_context_architecture.md` | Working on engine internals |",
        "| `llm_context_protocol.md` | Building clients, WebSocket work |",
        "| `llm_context_content.md` | Creating YAML content (rooms, NPCs, items) |",
        "",
        "## Project Structure",
        "",
        "```",
        "daemons-engine/",
        "├── backend/daemons/          # Engine source code",
        "│   ├── engine/               # Core game engine",
        "│   │   ├── systems/          # Modular game systems",
        "│   │   ├── world.py          # Runtime world model",
        "│   │   └── engine.py         # WorldEngine orchestrator",
        "│   ├── models.py             # SQLAlchemy database models",
        "│   ├── routes/               # HTTP API endpoints",
        "│   └── main.py               # FastAPI application",
        "├── docs/                     # Documentation",
        "├── world_data/               # YAML game content",
        "└── tests/                    # Test suite",
        "```",
        "",
        "## Documentation Files",
        "",
    ]

    for doc_path in sorted(docs.keys()):
        # Extract first heading as title
        content = docs[doc_path]
        title = doc_path
        for line in content.split("\n"):
            if line.startswith("# "):
                title = line[2:].strip()
                break

        lines.append(f"- **`docs/{doc_path}`**: {title}")

    if yaml_examples:
        lines.extend([
            "",
            "## Content Directories",
            "",
        ])
        for content_type, examples in sorted(yaml_examples.items()):
            count = len(examples)
            lines.append(f"- **`world_data/{content_type}/`**: {count} example(s) available")

    lines.extend([
        "",
        "## Key Concepts",
        "",
        "- **Room-based world**: Rooms connected by directional exits (north, south, etc.)",
        "- **Real-time multiplayer**: WebSocket-based event-driven architecture",
        "- **YAML content**: All game content defined in human-readable YAML files",
        "- **Modular systems**: Combat, quests, effects, etc. are separate composable systems",
        "- **Template/Instance pattern**: Templates define prototypes, instances are runtime copies",
        "",
    ])

    return "\n".join(lines)


def build_architecture_context(docs: dict[str, str]) -> str:
    """Build architecture-focused context file."""
    lines = [
        "# Daemons Engine - Architecture Context",
        "",
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "Attach this file when working on engine internals, adding systems, or debugging.",
        "",
    ]

    # Include ARCHITECTURE.md content if available
    arch_content = docs.get("ARCHITECTURE.md", "")
    if arch_content:
        lines.append(arch_content)

    # Include operations content if available
    ops_content = docs.get("OPERATIONS.md", "")
    if ops_content:
        lines.extend([
            "",
            "---",
            "",
            ops_content
        ])

    return "\n".join(lines)


def build_protocol_context(docs: dict[str, str]) -> str:
    """Build protocol-focused context file."""
    lines = [
        "# Daemons Engine - Protocol Context",
        "",
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "Attach this file when building clients, working on WebSocket communication,",
        "or implementing the game protocol.",
        "",
    ]

    # Include protocol.md content if available
    protocol_content = docs.get("protocol.md", "")
    if protocol_content:
        lines.append(protocol_content)

    return "\n".join(lines)


def build_content_context(yaml_examples: dict[str, list]) -> str:
    """Build content authoring context file."""
    lines = [
        "# Daemons Engine - Content Authoring Context",
        "",
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "Attach this file when creating or editing YAML game content.",
        "",
        "## Content Types",
        "",
    ]

    for content_type in sorted(yaml_examples.keys()):
        lines.append(f"- `world_data/{content_type}/`")

    lines.extend([
        "",
        "## Example Files",
        "",
    ])

    for content_type, examples in sorted(yaml_examples.items()):
        if not examples:
            continue

        lines.extend([
            f"### {content_type.title()}",
            "",
        ])

        for example in examples:
            lines.extend([
                f"**`{example['name']}`**:",
                "",
                "```yaml",
                example["content"].strip(),
                "```",
                "",
            ])

    lines.extend([
        "## Common Patterns",
        "",
        "### IDs",
        "- Use snake_case for all IDs",
        "- Prefix with type: `room_`, `npc_`, `item_`, `quest_`",
        "- Example: `room_tavern_main`, `npc_barkeeper`, `item_rusty_sword`",
        "",
        "### References",
        "- Reference other entities by ID",
        "- Rooms reference other rooms in `exits`",
        "- NPCs reference `spawn_room` and `drop_table` items",
        "- Quests reference NPCs, items, and rooms",
        "",
        "### Keywords",
        "- Define `keywords` for player interaction",
        "- Players can `look <keyword>` or `examine <keyword>`",
        "- Example: `keywords: [sword, rusty, blade]`",
        "",
    ])

    return "\n".join(lines)


def main():
    """Generate all LLM context files."""
    root = find_project_root()
    docs_dir = root / "docs"
    world_data_dir = root / "world_data"
    output_dir = docs_dir / "build_docs"

    print(f"Project root: {root}")
    print(f"Docs directory: {docs_dir}")
    print(f"World data directory: {world_data_dir}")
    print(f"Output directory: {output_dir}")
    print()

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Gather source material
    docs = gather_docs(docs_dir)
    print(f"Found {len(docs)} documentation files")

    yaml_examples = gather_yaml_examples(world_data_dir)
    total_examples = sum(len(v) for v in yaml_examples.values())
    print(f"Found {total_examples} YAML examples across {len(yaml_examples)} content types")
    print()

    # Build context files
    context_files = {
        "llm_context_index.md": build_index(docs, yaml_examples),
        "llm_context_architecture.md": build_architecture_context(docs),
        "llm_context_protocol.md": build_protocol_context(docs),
        "llm_context_content.md": build_content_context(yaml_examples),
    }

    # Write output files
    for filename, content in context_files.items():
        output_path = output_dir / filename
        output_path.write_text(content, encoding="utf-8")
        size_kb = len(content) / 1024
        print(f"Generated: {filename} ({size_kb:.1f} KB)")

    print()
    print("Done! Context files are ready in docs/build_docs/")
    print()
    print("Usage:")
    print("  - Always attach llm_context_index.md for general questions")
    print("  - Add domain-specific files as needed for your task")


if __name__ == "__main__":
    main()
