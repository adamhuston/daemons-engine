"""Load all world data from YAML into database."""
import asyncio
from pathlib import Path
import yaml
from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.models import Room, Area, ItemTemplate, ItemInstance, NpcTemplate, NpcInstance
import uuid

async def load_data():
    world_data_dir = Path(__file__).parent / 'world_data'
    
    async with AsyncSessionLocal() as session:
        # ===== Load Areas =====
        areas_dir = world_data_dir / 'areas'
        if areas_dir.exists():
            yaml_files = list(areas_dir.glob('**/*.yaml'))
            loaded = 0
            for yaml_file in yaml_files:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    area_data = yaml.safe_load(f)
                
                existing = await session.execute(
                    select(Area).where(Area.id == area_data['id'])
                )
                if existing.scalars().first():
                    continue
                
                print(f"Loading area: {area_data['name']}")
                area = Area(
                    id=area_data['id'],
                    name=area_data['name'],
                    description=area_data.get('description', ''),
                    time_scale=area_data.get('time_scale', 1.0),
                    biome=area_data.get('biome', 'mystical'),
                    climate=area_data.get('climate', 'temperate'),
                    ambient_lighting=area_data.get('ambient_lighting', 'dim'),
                    weather_profile=area_data.get('weather_profile'),
                    danger_level=area_data.get('danger_level', 1),
                    magic_intensity=area_data.get('magic_intensity', 'moderate'),
                    ambient_sound=area_data.get('ambient_sound'),
                    default_respawn_time=area_data.get('default_respawn_time', 300),
                    time_phases=area_data.get('time_phases'),
                    entry_points=area_data.get('entry_points', []),
                    starting_day=area_data.get('starting_day', 1),
                    starting_hour=area_data.get('starting_hour', 0),
                    starting_minute=area_data.get('starting_minute', 0),
                )
                session.add(area)
                loaded += 1
            await session.commit()
            print(f"Loaded {loaded} areas")
        
        # ===== Load Rooms =====
        rooms_dir = world_data_dir / 'rooms'
        if rooms_dir.exists():
            yaml_files = list(rooms_dir.glob('**/*.yaml'))
            loaded = 0
            for yaml_file in yaml_files:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    room_data = yaml.safe_load(f)
                
                existing = await session.execute(
                    select(Room).where(Room.id == room_data['id'])
                )
                if existing.scalars().first():
                    continue
                
                print(f"Loading room: {room_data['name']} ({room_data['id']})")
                exits = room_data.get('exits', {})
                room = Room(
                    id=room_data['id'],
                    name=room_data['name'],
                    description=room_data['description'],
                    room_type=room_data.get('room_type', 'ethereal'),
                    area_id=room_data.get('area_id'),
                    north_id=exits.get('north'),
                    south_id=exits.get('south'),
                    east_id=exits.get('east'),
                    west_id=exits.get('west'),
                    up_id=exits.get('up'),
                    down_id=exits.get('down'),
                    on_enter_effect=room_data.get('on_enter_effect'),
                    on_exit_effect=room_data.get('on_exit_effect'),
                )
                session.add(room)
                loaded += 1
            await session.commit()
            print(f"Loaded {loaded} rooms")
        
        # ===== Load Item Templates =====
        items_dir = world_data_dir / 'items'
        if items_dir.exists():
            yaml_files = list(items_dir.glob('**/*.yaml'))
            loaded = 0
            for yaml_file in yaml_files:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    item_data = yaml.safe_load(f)
                
                existing = await session.execute(
                    select(ItemTemplate).where(ItemTemplate.id == item_data['id'])
                )
                if existing.scalars().first():
                    continue
                
                print(f"Loading item template: {item_data['name']}")
                template = ItemTemplate(
                    id=item_data['id'],
                    name=item_data['name'],
                    description=item_data.get('description', ''),
                    item_type=item_data.get('item_type', 'misc'),
                    item_subtype=item_data.get('item_subtype'),
                    equipment_slot=item_data.get('equipment_slot'),
                    stat_modifiers=item_data.get('stat_modifiers', {}),
                    weight=item_data.get('weight', 0.0),
                    max_stack_size=item_data.get('max_stack_size', 1),
                    has_durability=item_data.get('has_durability', False),
                    max_durability=item_data.get('max_durability'),
                    is_container=item_data.get('is_container', False),
                    container_capacity=item_data.get('container_capacity'),
                    container_type=item_data.get('container_type'),
                    is_consumable=item_data.get('is_consumable', False),
                    consume_effect=item_data.get('consume_effect'),
                    # Weapon combat stats
                    damage_min=item_data.get('damage_min', 0),
                    damage_max=item_data.get('damage_max', 0),
                    attack_speed=item_data.get('attack_speed', 2.0),
                    damage_type=item_data.get('damage_type', 'physical'),
                    # Flavor and metadata
                    flavor_text=item_data.get('flavor_text'),
                    rarity=item_data.get('rarity', 'common'),
                    value=item_data.get('value', 0),
                    flags=item_data.get('flags', {}),
                    keywords=item_data.get('keywords', []),
                )
                session.add(template)
                loaded += 1
            await session.commit()
            print(f"Loaded {loaded} item templates")
        
        # ===== Load Item Instances =====
        item_instances_dir = world_data_dir / 'item_instances'
        if item_instances_dir.exists():
            yaml_files = list(item_instances_dir.glob('**/*.yaml'))
            loaded = 0
            for yaml_file in yaml_files:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                
                # Determine room_id from file path (e.g., ethereal/room_1_1_1.yaml)
                room_id = yaml_file.stem  # e.g., "room_1_1_1"
                
                items = data.get('items', [])
                for item_data in items:
                    instance_id = str(uuid.uuid4())
                    print(f"Loading item instance: {item_data['template_id']} in {room_id}")
                    instance = ItemInstance(
                        id=instance_id,
                        template_id=item_data['template_id'],
                        room_id=room_id if room_id != 'starting_items' else None,
                        player_id=None,
                        container_id=None,
                        quantity=item_data.get('quantity', 1),
                        current_durability=item_data.get('current_durability'),
                        equipped_slot=None,
                        instance_data=item_data.get('instance_data', {}),
                    )
                    session.add(instance)
                    loaded += 1
            await session.commit()
            print(f"Loaded {loaded} item instances")
        
        # ===== Load NPC Templates =====
        npcs_dir = world_data_dir / 'npcs'
        if npcs_dir.exists():
            yaml_files = list(npcs_dir.glob('**/*.yaml'))
            loaded = 0
            for yaml_file in yaml_files:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    npc_data = yaml.safe_load(f)
                
                existing_result = await session.execute(
                    select(NpcTemplate).where(NpcTemplate.id == npc_data['id'])
                )
                existing = existing_result.scalars().first()
                
                behavior = npc_data.get('behavior', {})
                
                if existing:
                    # Update existing template with new data
                    existing.name = npc_data['name']
                    existing.description = npc_data.get('description', '')
                    existing.npc_type = npc_data.get('npc_type', 'neutral')
                    existing.level = npc_data.get('level', 1)
                    existing.max_health = npc_data.get('max_health', 10)
                    existing.armor_class = npc_data.get('armor_class', 10)
                    existing.strength = npc_data.get('strength', 10)
                    existing.dexterity = npc_data.get('dexterity', 10)
                    existing.intelligence = npc_data.get('intelligence', 10)
                    existing.attack_damage_min = npc_data.get('attack_damage_min', 1)
                    existing.attack_damage_max = npc_data.get('attack_damage_max', 4)
                    existing.attack_speed = npc_data.get('attack_speed', 1.0)
                    existing.experience_reward = npc_data.get('experience_reward', 10)
                    existing.behavior = behavior
                    existing.idle_messages = npc_data.get('idle_messages', [])
                    existing.keywords = npc_data.get('keywords', [])
                    existing.loot_table = npc_data.get('loot_table', [])
                    print(f"Updating NPC template: {npc_data['name']}")
                else:
                    print(f"Loading NPC template: {npc_data['name']}")
                    template = NpcTemplate(
                        id=npc_data['id'],
                        name=npc_data['name'],
                        description=npc_data.get('description', ''),
                        npc_type=npc_data.get('npc_type', 'neutral'),
                        level=npc_data.get('level', 1),
                        max_health=npc_data.get('max_health', 10),
                        armor_class=npc_data.get('armor_class', 10),
                        strength=npc_data.get('strength', 10),
                        dexterity=npc_data.get('dexterity', 10),
                        intelligence=npc_data.get('intelligence', 10),
                        attack_damage_min=npc_data.get('attack_damage_min', 1),
                        attack_damage_max=npc_data.get('attack_damage_max', 4),
                        attack_speed=npc_data.get('attack_speed', 1.0),
                        experience_reward=npc_data.get('experience_reward', 10),
                        behavior=behavior,
                        idle_messages=npc_data.get('idle_messages', []),
                        keywords=npc_data.get('keywords', []),
                        loot_table=npc_data.get('loot_table', []),
                    )
                    session.add(template)
                loaded += 1
            await session.commit()
            print(f"Loaded {loaded} NPC templates")
        
        # ===== Load NPC Spawns =====
        npc_spawns_dir = world_data_dir / 'npc_spawns'
        if npc_spawns_dir.exists():
            yaml_files = list(npc_spawns_dir.glob('**/*.yaml'))
            loaded = 0
            for yaml_file in yaml_files:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                
                spawns = data.get('spawns', [])
                for spawn in spawns:
                    instance_id = str(uuid.uuid4())
                    room_id = spawn['room_id']
                    
                    # Get template to set current_health if not specified
                    template_result = await session.execute(
                        select(NpcTemplate).where(NpcTemplate.id == spawn['template_id'])
                    )
                    template = template_result.scalars().first()
                    current_health = spawn.get('current_health') or (template.max_health if template else 50)
                    
                    print(f"Loading NPC spawn: {spawn['template_id']} in {room_id}")
                    instance = NpcInstance(
                        id=instance_id,
                        template_id=spawn['template_id'],
                        room_id=room_id,
                        spawn_room_id=room_id,  # Spawn in same room they're placed
                        current_health=current_health,
                        is_alive=True,
                        respawn_time=spawn.get('respawn_time'),  # None = use area default, -1 = no respawn
                        instance_data=spawn.get('instance_data', {}),
                    )
                    session.add(instance)
                    loaded += 1
            await session.commit()
            print(f"Loaded {loaded} NPC spawns")
        
        print("\n✅ All world data loaded!")

if __name__ == "__main__":
    asyncio.run(load_data())
