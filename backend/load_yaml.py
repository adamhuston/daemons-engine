"""Load all world data from YAML into database."""

import asyncio
import random
import time
import uuid
from pathlib import Path

import yaml
from sqlalchemy import select

from daemons.db import AsyncSessionLocal
from daemons.models import (
    Area,
    FloraInstance,
    ItemInstance,
    ItemTemplate,
    NpcInstance,
    NpcTemplate,
    Room,
)


async def load_data():
    world_data_dir = Path(__file__).parent / "daemons" / "world_data"

    async with AsyncSessionLocal() as session:
        # ===== Load Areas =====
        areas_dir = world_data_dir / "areas"
        if areas_dir.exists():
            yaml_files = list(areas_dir.glob("**/*.yaml"))
            loaded = 0
            for yaml_file in yaml_files:
                # Skip schema files
                if yaml_file.name.startswith("_"):
                    continue
                with open(yaml_file, encoding="utf-8") as f:
                    area_data = yaml.safe_load(f)

                existing = await session.execute(
                    select(Area).where(Area.id == area_data["id"])
                )
                if existing.scalars().first():
                    continue

                print(f"Loading area: {area_data['name']}")
                area = Area(
                    id=area_data["id"],
                    name=area_data["name"],
                    description=area_data.get("description", ""),
                    time_scale=area_data.get("time_scale", 1.0),
                    biome=area_data.get("biome", "mystical"),
                    climate=area_data.get("climate", "temperate"),
                    ambient_lighting=area_data.get("ambient_lighting", "dim"),
                    weather_profile=area_data.get("weather_profile"),
                    danger_level=area_data.get("danger_level", 1),
                    magic_intensity=area_data.get("magic_intensity", "moderate"),
                    ambient_sound=area_data.get("ambient_sound"),
                    default_respawn_time=area_data.get("default_respawn_time", 300),
                    time_phases=area_data.get("time_phases"),
                    entry_points=area_data.get("entry_points", []),
                    starting_day=area_data.get("starting_day", 1),
                    starting_hour=area_data.get("starting_hour", 0),
                    starting_minute=area_data.get("starting_minute", 0),
                )
                session.add(area)
                loaded += 1
            await session.commit()
            print(f"Loaded {loaded} areas")

        # ===== Load Rooms =====
        rooms_dir = world_data_dir / "rooms"
        if rooms_dir.exists():
            yaml_files = list(rooms_dir.glob("**/*.yaml"))
            loaded = 0
            for yaml_file in yaml_files:
                # Skip schema files
                if yaml_file.name.startswith("_"):
                    continue
                with open(yaml_file, encoding="utf-8") as f:
                    room_data = yaml.safe_load(f)

                existing = await session.execute(
                    select(Room).where(Room.id == room_data["id"])
                )
                if existing.scalars().first():
                    continue

                print(f"Loading room: {room_data['name']} ({room_data['id']})")
                exits = room_data.get("exits", {})
                room = Room(
                    id=room_data["id"],
                    name=room_data["name"],
                    description=room_data["description"],
                    room_type=room_data.get("room_type", "ethereal"),
                    area_id=room_data.get("area_id"),
                    north_id=exits.get("north"),
                    south_id=exits.get("south"),
                    east_id=exits.get("east"),
                    west_id=exits.get("west"),
                    up_id=exits.get("up"),
                    down_id=exits.get("down"),
                    on_enter_effect=room_data.get("on_enter_effect"),
                    on_exit_effect=room_data.get("on_exit_effect"),
                )
                session.add(room)
                loaded += 1
            await session.commit()
            print(f"Loaded {loaded} rooms")

        # ===== Load Item Templates =====
        items_dir = world_data_dir / "items"
        if items_dir.exists():
            yaml_files = list(items_dir.glob("**/*.yaml"))
            loaded = 0
            for yaml_file in yaml_files:
                # Skip schema files
                if yaml_file.name.startswith("_"):
                    continue
                with open(yaml_file, encoding="utf-8") as f:
                    item_data = yaml.safe_load(f)

                existing = await session.execute(
                    select(ItemTemplate).where(ItemTemplate.id == item_data["id"])
                )
                if existing.scalars().first():
                    continue

                print(f"Loading item template: {item_data['name']}")
                template = ItemTemplate(
                    id=item_data["id"],
                    name=item_data["name"],
                    description=item_data.get("description", ""),
                    item_type=item_data.get("item_type", "misc"),
                    item_subtype=item_data.get("item_subtype"),
                    equipment_slot=item_data.get("equipment_slot"),
                    stat_modifiers=item_data.get("stat_modifiers", {}),
                    weight=item_data.get("weight", 0.0),
                    max_stack_size=item_data.get("max_stack_size", 1),
                    has_durability=item_data.get("has_durability", False),
                    max_durability=item_data.get("max_durability"),
                    is_container=item_data.get("is_container", False),
                    container_capacity=item_data.get("container_capacity"),
                    container_type=item_data.get("container_type"),
                    is_consumable=item_data.get("is_consumable", False),
                    consume_effect=item_data.get("consume_effect"),
                    # Weapon combat stats
                    damage_min=item_data.get("damage_min", 0),
                    damage_max=item_data.get("damage_max", 0),
                    attack_speed=item_data.get("attack_speed", 2.0),
                    damage_type=item_data.get("damage_type", "physical"),
                    # Phase 11: Light source properties
                    provides_light=item_data.get("provides_light", False),
                    light_intensity=item_data.get("light_intensity", 0),
                    light_duration=item_data.get("light_duration"),
                    # Phase 14: Ability system support (magic items)
                    class_id=item_data.get("class_id"),
                    default_abilities=item_data.get("default_abilities", []),
                    ability_loadout=item_data.get("ability_loadout", []),
                    # Phase 14+: Combat stats (destructible items)
                    max_health=item_data.get("max_health"),
                    base_armor_class=item_data.get("base_armor_class", 10),
                    resistances=item_data.get("resistances", {}),
                    # Flavor and metadata
                    flavor_text=item_data.get("flavor_text"),
                    rarity=item_data.get("rarity", "common"),
                    value=item_data.get("value", 0),
                    flags=item_data.get("flags", {}),
                    keywords=item_data.get("keywords", []),
                )
                session.add(template)
                loaded += 1
            await session.commit()
            print(f"Loaded {loaded} item templates")

        # ===== Load Item Instances =====
        item_instances_dir = world_data_dir / "item_instances"
        if item_instances_dir.exists():
            yaml_files = list(item_instances_dir.glob("**/*.yaml"))
            loaded = 0
            for yaml_file in yaml_files:
                # Skip schema files
                if yaml_file.name.startswith("_"):
                    continue
                with open(yaml_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                # Determine room_id from file path (e.g., ethereal/room_1_1_1.yaml)
                room_id = yaml_file.stem  # e.g., "room_1_1_1"

                items = data.get("items", [])
                for item_data in items:
                    instance_id = str(uuid.uuid4())
                    print(
                        f"Loading item instance: {item_data['template_id']} in {room_id}"
                    )
                    instance = ItemInstance(
                        id=instance_id,
                        template_id=item_data["template_id"],
                        room_id=room_id if room_id != "starting_items" else None,
                        player_id=None,
                        container_id=None,
                        quantity=item_data.get("quantity", 1),
                        current_durability=item_data.get("current_durability"),
                        equipped_slot=None,
                        instance_data=item_data.get("instance_data", {}),
                    )
                    session.add(instance)
                    loaded += 1
            await session.commit()
            print(f"Loaded {loaded} item instances")

        # ===== Load NPC Templates =====
        npcs_dir = world_data_dir / "npcs"
        if npcs_dir.exists():
            yaml_files = list(npcs_dir.glob("**/*.yaml"))
            loaded = 0
            for yaml_file in yaml_files:
                # Skip schema files
                if yaml_file.name.startswith("_"):
                    continue
                with open(yaml_file, encoding="utf-8") as f:
                    npc_data = yaml.safe_load(f)

                existing_result = await session.execute(
                    select(NpcTemplate).where(NpcTemplate.id == npc_data["id"])
                )
                existing = existing_result.scalars().first()

                behavior = npc_data.get("behavior", {})

                if existing:
                    # Update existing template with new data
                    existing.name = npc_data["name"]
                    existing.description = npc_data.get("description", "")
                    existing.npc_type = npc_data.get("npc_type", "neutral")
                    existing.level = npc_data.get("level", 1)
                    existing.max_health = npc_data.get("max_health", 10)
                    existing.armor_class = npc_data.get("armor_class", 10)
                    existing.strength = npc_data.get("strength", 10)
                    existing.dexterity = npc_data.get("dexterity", 10)
                    existing.intelligence = npc_data.get("intelligence", 10)
                    existing.attack_damage_min = npc_data.get("attack_damage_min", 1)
                    existing.attack_damage_max = npc_data.get("attack_damage_max", 4)
                    existing.attack_speed = npc_data.get("attack_speed", 1.0)
                    existing.experience_reward = npc_data.get("experience_reward", 10)
                    existing.behavior = behavior
                    existing.idle_messages = npc_data.get("idle_messages", [])
                    existing.keywords = npc_data.get("keywords", [])
                    existing.loot_table = npc_data.get("loot_table", [])
                    # Phase 17.5: Fauna properties
                    existing.is_fauna = npc_data.get("is_fauna", False)
                    existing.fauna_data = npc_data.get("fauna_data", {})
                    print(f"Updating NPC template: {npc_data['name']}")
                else:
                    print(f"Loading NPC template: {npc_data['name']}")
                    template = NpcTemplate(
                        id=npc_data["id"],
                        name=npc_data["name"],
                        description=npc_data.get("description", ""),
                        npc_type=npc_data.get("npc_type", "neutral"),
                        level=npc_data.get("level", 1),
                        max_health=npc_data.get("max_health", 10),
                        armor_class=npc_data.get("armor_class", 10),
                        strength=npc_data.get("strength", 10),
                        dexterity=npc_data.get("dexterity", 10),
                        intelligence=npc_data.get("intelligence", 10),
                        attack_damage_min=npc_data.get("attack_damage_min", 1),
                        attack_damage_max=npc_data.get("attack_damage_max", 4),
                        attack_speed=npc_data.get("attack_speed", 1.0),
                        experience_reward=npc_data.get("experience_reward", 10),
                        behavior=behavior,
                        idle_messages=npc_data.get("idle_messages", []),
                        keywords=npc_data.get("keywords", []),
                        loot_table=npc_data.get("loot_table", []),
                        # Phase 17.5: Fauna properties
                        is_fauna=npc_data.get("is_fauna", False),
                        fauna_data=npc_data.get("fauna_data", {}),
                    )
                    session.add(template)
                loaded += 1
            await session.commit()
            print(f"Loaded {loaded} NPC templates")

        # ===== Load NPC Spawns =====
        npc_spawns_dir = world_data_dir / "npc_spawns"
        if npc_spawns_dir.exists():
            yaml_files = list(npc_spawns_dir.glob("**/*.yaml"))
            loaded = 0
            for yaml_file in yaml_files:
                # Skip schema files
                if yaml_file.name.startswith("_"):
                    continue
                with open(yaml_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if not data:
                    continue

                spawns = data.get("spawns", []) or []
                for spawn in spawns:
                    instance_id = str(uuid.uuid4())
                    room_id = spawn["room_id"]

                    # Get template to set current_health if not specified
                    template_result = await session.execute(
                        select(NpcTemplate).where(
                            NpcTemplate.id == spawn["template_id"]
                        )
                    )
                    template = template_result.scalars().first()
                    current_health = spawn.get("current_health") or (
                        template.max_health if template else 50
                    )

                    print(f"Loading NPC spawn: {spawn['template_id']} in {room_id}")
                    instance = NpcInstance(
                        id=instance_id,
                        template_id=spawn["template_id"],
                        room_id=room_id,
                        spawn_room_id=room_id,  # Spawn in same room they're placed
                        current_health=current_health,
                        is_alive=True,
                        respawn_time=spawn.get(
                            "respawn_time"
                        ),  # None = use area default, -1 = no respawn
                        instance_data=spawn.get("instance_data", {}),
                    )
                    session.add(instance)
                    loaded += 1
            await session.commit()
            print(f"Loaded {loaded} NPC spawns")

        # ===== Load Biome Definitions =====
        biomes_dir = world_data_dir / "biomes"
        biome_defs = {}
        if biomes_dir.exists():
            yaml_files = list(biomes_dir.glob("**/*.yaml"))
            for yaml_file in yaml_files:
                if yaml_file.name.startswith("_"):
                    continue
                with open(yaml_file, encoding="utf-8") as f:
                    biome_data = yaml.safe_load(f)
                if biome_data and "biome_id" in biome_data:
                    biome_defs[biome_data["biome_id"]] = biome_data

        # ===== Load Flora Templates =====
        flora_dir = world_data_dir / "flora"
        flora_templates = {}
        if flora_dir.exists():
            yaml_files = list(flora_dir.glob("**/*.yaml"))
            for yaml_file in yaml_files:
                if yaml_file.name.startswith("_"):
                    continue
                with open(yaml_file, encoding="utf-8") as f:
                    flora_data = yaml.safe_load(f)
                if flora_data and "id" in flora_data:
                    flora_templates[flora_data["id"]] = flora_data

        # ===== Load Fauna (NPC) Templates =====
        npcs_dir = world_data_dir / "npcs"
        fauna_templates = {}
        if npcs_dir.exists():
            yaml_files = list(npcs_dir.glob("**/*.yaml"))
            for yaml_file in yaml_files:
                if yaml_file.name.startswith("_"):
                    continue
                with open(yaml_file, encoding="utf-8") as f:
                    npc_data = yaml.safe_load(f)
                # Only include fauna NPCs
                if npc_data and npc_data.get("is_fauna"):
                    fauna_templates[npc_data["id"]] = npc_data

        # ===== Seed Initial Flora and Fauna by Biome =====
        # Get all rooms and areas
        rooms_result = await session.execute(select(Room))
        rooms = rooms_result.scalars().all()
        
        areas_result = await session.execute(select(Area))
        areas_by_id = {a.id: a for a in areas_result.scalars().all()}
        
        flora_loaded = 0
        fauna_loaded = 0
        
        for room in rooms:
            area = areas_by_id.get(room.area_id)
            if not area:
                continue
                
            # Get biome definition
            biome = biome_defs.get(area.biome, {})
            
            # Build compatibility tags from biome
            biome_flora_tags = set(biome.get("flora_tags", []))
            biome_fauna_tags = set(biome.get("fauna_tags", []))
            biome_tags = set(biome.get("tags", []))
            
            # Fallback: use biome name as tag if no specific tags
            if not biome_flora_tags:
                biome_flora_tags = biome_tags | {area.biome} if area.biome else set()
            if not biome_fauna_tags:
                biome_fauna_tags = biome_tags | {area.biome} if area.biome else set()
            
            # ----- Seed Flora -----
            if flora_templates and biome_flora_tags:
                # Check if room already has flora
                existing_flora = await session.execute(
                    select(FloraInstance).where(FloraInstance.room_id == room.id)
                )
                if not existing_flora.scalars().first():
                    # Find compatible flora templates
                    compatible = []
                    for template_id, template in flora_templates.items():
                        template_tags = set(template.get("biome_tags", []))
                        if not template_tags or template_tags & biome_flora_tags:
                            rarity = template.get("rarity", "common")
                            weight = {"common": 1.0, "uncommon": 0.5, "rare": 0.2, "very_rare": 0.05}.get(rarity, 1.0)
                            compatible.append((template_id, template, weight))
                    
                    if compatible:
                        # Spawn 1-3 flora types per room
                        num_to_spawn = random.randint(1, min(3, len(compatible)))
                        templates_to_spawn = random.choices(
                            compatible,
                            weights=[c[2] for c in compatible],
                            k=num_to_spawn
                        )
                        
                        for template_id, template, _ in templates_to_spawn:
                            cluster_size = template.get("cluster_size", [1, 3])
                            quantity = random.randint(cluster_size[0], cluster_size[1])
                            
                            flora_instance = FloraInstance(
                                template_id=template_id,
                                room_id=room.id,
                                quantity=quantity,
                                spawned_at=time.time(),
                                is_permanent=True,
                                is_depleted=False,
                            )
                            session.add(flora_instance)
                            flora_loaded += 1
            
            # ----- Seed Fauna -----
            if fauna_templates and biome_fauna_tags:
                # Check if room already has fauna
                existing_fauna = await session.execute(
                    select(NpcInstance).where(NpcInstance.room_id == room.id)
                )
                if not existing_fauna.scalars().first():
                    # Find compatible fauna templates
                    compatible = []
                    for template_id, template in fauna_templates.items():
                        fauna_data = template.get("fauna_data", {})
                        template_tags = set(fauna_data.get("biome_tags", []))
                        if not template_tags or template_tags & biome_fauna_tags:
                            # Weight by level (lower level = more common)
                            level = template.get("level", 1)
                            weight = 1.0 / (level * 0.5 + 0.5)
                            compatible.append((template_id, template, weight))
                    
                    if compatible:
                        # 50% chance to spawn fauna in room (not every room needs fauna)
                        if random.random() < 0.5:
                            # Spawn 1-2 fauna types per room
                            num_to_spawn = random.randint(1, min(2, len(compatible)))
                            templates_to_spawn = random.choices(
                                compatible,
                                weights=[c[2] for c in compatible],
                                k=num_to_spawn
                            )
                            
                            for template_id, template, _ in templates_to_spawn:
                                # Get max health from template
                                max_health = template.get("max_health", 50)
                                
                                instance_id = str(uuid.uuid4())
                                npc_instance = NpcInstance(
                                    id=instance_id,
                                    template_id=template_id,
                                    room_id=room.id,
                                    spawn_room_id=room.id,
                                    current_health=max_health,
                                    is_alive=True,
                                    respawn_time=300,  # 5 minute respawn
                                    instance_data={},
                                )
                                session.add(npc_instance)
                                fauna_loaded += 1
        
        await session.commit()
        if flora_loaded > 0:
            print(f"Seeded {flora_loaded} flora instances based on biomes")
        if fauna_loaded > 0:
            print(f"Seeded {fauna_loaded} fauna instances based on biomes")

        print("\n✅ All world data loaded!")


if __name__ == "__main__":
    asyncio.run(load_data())
