# backend/app/engine/loader.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Room, Player, Area, ItemTemplate, ItemInstance, PlayerInventory, NpcTemplate, NpcInstance, RoomType
from .world import (
    World, WorldRoom, WorldPlayer, WorldArea, WorldTime, ItemTemplate as WorldItemTemplate,
    WorldItem, PlayerInventory as WorldPlayerInventory, RoomId, PlayerId, AreaId, ItemId,
    ItemTemplateId, DEFAULT_TIME_PHASES, NpcTemplate as WorldNpcTemplate, WorldNpc, NpcId,
    NpcTemplateId, EntityType, resolve_behaviors, set_room_type_emojis, DEFAULT_ROOM_TYPE_EMOJIS
)


async def load_room_types(session: AsyncSession) -> dict[str, str]:
    """
    Load room type emojis from the database.
    
    Returns a dict mapping room type names to their emojis.
    Also ensures all default room types exist in the database.
    """
    # First, ensure all default room types exist in DB
    existing_result = await session.execute(select(RoomType))
    existing_types = {rt.name: rt for rt in existing_result.scalars().all()}
    
    # Add any missing default room types
    for name, emoji in DEFAULT_ROOM_TYPE_EMOJIS.items():
        if name not in existing_types:
            new_type = RoomType(name=name, emoji=emoji)
            session.add(new_type)
            existing_types[name] = new_type
    
    # Build the emoji mapping BEFORE commit (objects expire after commit)
    result = {rt.name: rt.emoji for rt in existing_types.values()}
    
    await session.commit()
    
    return result


async def load_world(session: AsyncSession) -> World:
    """
    Build the in-memory World from the database.

    Called once at startup (in main.py), but can be reused for reloads/tests.
    """
    # ----- Load room types -----
    room_type_emojis = await load_room_types(session)
    set_room_type_emojis(room_type_emojis)
    
    # ----- Load rooms -----
    room_result = await session.execute(select(Room))
    room_models = room_result.scalars().all()

    rooms: dict[RoomId, WorldRoom] = {}

    for r in room_models:
        exits: dict[str, str] = {}
        for d in ("north", "south", "east", "west", "up", "down"):
            dest_id = getattr(r, f"{d}_id")
            if dest_id:
                exits[d] = dest_id
        
        # Check if this room uses a new room type not in the database yet
        if r.room_type not in room_type_emojis:
            # Add new room type with default emoji
            new_type = RoomType(name=r.room_type, emoji="❓")
            session.add(new_type)
            room_type_emojis[r.room_type] = "❓"
            await session.commit()

        rooms[r.id] = WorldRoom(
            id=r.id,
            name=r.name,
            description=r.description,
            room_type=r.room_type,
            room_type_emoji=getattr(r, 'room_type_emoji', None),
            exits=exits,
            area_id=r.area_id,
            on_enter_effect=r.on_enter_effect,
            on_exit_effect=r.on_exit_effect,
        )
    
    # Update the global emoji cache with any new types discovered
    set_room_type_emojis(room_type_emojis)

    # ----- Load players -----
    player_result = await session.execute(select(Player))
    player_models = player_result.scalars().all()

    players: dict[PlayerId, WorldPlayer] = {}

    for p in player_models:
        # Load quest progress from DB (stored as dict of dicts)
        quest_progress_data = p.quest_progress if hasattr(p, 'quest_progress') and p.quest_progress else {}
        completed_quests_data = p.completed_quests if hasattr(p, 'completed_quests') and p.completed_quests else []
        player_flags_data = p.player_flags if hasattr(p, 'player_flags') and p.player_flags else {}
        
        players[p.id] = WorldPlayer(
            id=p.id,
            entity_type=EntityType.PLAYER,
            name=p.name,
            room_id=p.current_room_id,
            level=p.level,
            max_health=p.max_health,
            current_health=p.current_health,
            armor_class=p.armor_class,
            strength=p.strength,
            dexterity=p.dexterity,
            intelligence=p.intelligence,
            on_move_effect=p.data.get("on_move_effect"),
            character_class=p.character_class,
            experience=p.experience,
            vitality=p.vitality,
            max_energy=p.max_energy,
            current_energy=p.current_energy,
            # Quest system (Phase X)
            quest_progress=quest_progress_data,
            completed_quests=set(completed_quests_data),
            player_flags=player_flags_data,
        )

    # ----- Place players into rooms (unified entity tracking) -----
    for player in players.values():
        room = rooms.get(player.room_id)
        if room:
            room.entities.add(player.id)

    # ----- Load areas from database -----
    area_result = await session.execute(select(Area))
    area_models = area_result.scalars().all()

    areas: dict[AreaId, WorldArea] = {}

    for a in area_models:
        # Create WorldTime for this area
        area_time = WorldTime(
            day=a.starting_day,
            hour=a.starting_hour,
            minute=a.starting_minute,
        )
        
        # Get time phases, fall back to defaults if not specified
        time_phases = a.time_phases if a.time_phases else DEFAULT_TIME_PHASES
        
        # Get entry points
        entry_points = set(a.entry_points) if a.entry_points else set()
        
        areas[a.id] = WorldArea(
            id=a.id,
            name=a.name,
            description=a.description,
            area_time=area_time,
            time_scale=a.time_scale,
            biome=a.biome,
            climate=a.climate,
            ambient_lighting=a.ambient_lighting,
            weather_profile=a.weather_profile,
            danger_level=a.danger_level,
            magic_intensity=a.magic_intensity,
            ambient_sound=a.ambient_sound,
            default_respawn_time=a.default_respawn_time,
            time_phases=time_phases,
            entry_points=entry_points,
        )

    # ----- Link rooms to areas -----
    for room in rooms.values():
        if room.area_id and room.area_id in areas:
            area = areas[room.area_id]
            area.room_ids.add(room.id)

    # ----- Load item templates (Phase 3) -----
    template_result = await session.execute(select(ItemTemplate))
    template_models = template_result.scalars().all()

    item_templates: dict[ItemTemplateId, WorldItemTemplate] = {}

    for t in template_models:
        item_templates[t.id] = WorldItemTemplate(
            id=t.id,
            name=t.name,
            description=t.description,
            item_type=t.item_type,
            item_subtype=t.item_subtype,
            equipment_slot=t.equipment_slot,
            stat_modifiers=t.stat_modifiers,
            weight=t.weight,
            max_stack_size=t.max_stack_size,
            has_durability=bool(t.has_durability),  # Convert SQLite int to bool
            max_durability=t.max_durability,
            is_container=bool(t.is_container),
            container_capacity=t.container_capacity,
            container_type=t.container_type,
            is_consumable=bool(t.is_consumable),
            consume_effect=t.consume_effect,
            flavor_text=t.flavor_text,
            rarity=t.rarity,
            value=t.value,
            flags=t.flags,
            keywords=t.keywords or [],
            # Weapon stats
            damage_min=t.damage_min,
            damage_max=t.damage_max,
            attack_speed=t.attack_speed,
            damage_type=t.damage_type,
        )

    # ----- Load item instances (Phase 3) -----
    instance_result = await session.execute(select(ItemInstance))
    instance_models = instance_result.scalars().all()

    items: dict[ItemId, WorldItem] = {}

    for i in instance_models:
        # Get the template to cache name/keywords/description
        template = item_templates.get(i.template_id)
        items[i.id] = WorldItem(
            id=i.id,
            template_id=i.template_id,
            name=template.name if template else "",
            keywords=list(template.keywords) if template else [],
            room_id=i.room_id,
            player_id=i.player_id,
            container_id=i.container_id,
            quantity=i.quantity,
            current_durability=i.current_durability,
            equipped_slot=i.equipped_slot,
            instance_data=i.instance_data,
            _description=template.description if template else "",
        )

    # ----- Load player inventories (Phase 3) -----
    inventory_result = await session.execute(select(PlayerInventory))
    inventory_models = inventory_result.scalars().all()

    player_inventories: dict[PlayerId, WorldPlayerInventory] = {}

    for inv in inventory_models:
        player_inventories[inv.player_id] = WorldPlayerInventory(
            player_id=inv.player_id,
            max_weight=inv.max_weight,
            max_slots=inv.max_slots,
            current_weight=inv.current_weight,
            current_slots=inv.current_slots,
        )

    # ----- Link items to locations (Phase 3) -----
    for item in items.values():
        if item.room_id and item.room_id in rooms:
            rooms[item.room_id].items.add(item.id)
        elif item.player_id and item.player_id in players:
            players[item.player_id].inventory_items.add(item.id)
            if item.equipped_slot:
                players[item.player_id].equipped_items[item.equipped_slot] = item.id
    
    # ----- Build container contents index (Phase 3) -----
    container_contents: dict[str, set[str]] = {}
    for item in items.values():
        if item.container_id:
            if item.container_id not in container_contents:
                container_contents[item.container_id] = set()
            container_contents[item.container_id].add(item.id)

    # ----- Link inventories to players (Phase 3) -----
    for player in players.values():
        if player.id in player_inventories:
            player.inventory_meta = player_inventories[player.id]

    # ----- Load NPC templates (Phase 4) -----
    npc_template_result = await session.execute(select(NpcTemplate))
    npc_template_models = npc_template_result.scalars().all()

    npc_templates: dict[NpcTemplateId, WorldNpcTemplate] = {}

    for t in npc_template_models:
        # Handle behavior field - can be list of tags (new) or legacy dict
        raw_behavior = t.behavior or {}
        if isinstance(raw_behavior, list):
            # New format: list of behavior tags like ["wanders_sometimes", "aggressive"]
            behavior_tags = raw_behavior
            resolved = resolve_behaviors(behavior_tags)
        else:
            # Legacy format: raw dict - use as-is, no tags
            behavior_tags = []
            resolved = raw_behavior
        
        npc_templates[t.id] = WorldNpcTemplate(
            id=t.id,
            name=t.name,
            description=t.description,
            npc_type=t.npc_type,
            level=t.level,
            max_health=t.max_health,
            armor_class=t.armor_class,
            strength=t.strength,
            dexterity=t.dexterity,
            intelligence=t.intelligence,
            attack_damage_min=t.attack_damage_min,
            attack_damage_max=t.attack_damage_max,
            attack_speed=t.attack_speed,
            experience_reward=t.experience_reward,
            behaviors=behavior_tags,
            resolved_behavior=resolved,
            drop_table=t.loot_table or [],  # DB field is loot_table, runtime uses drop_table
            idle_messages=t.idle_messages or [],
            keywords=t.keywords or [],
            persist_state=t.persist_state if hasattr(t, 'persist_state') else False,
        )

    # ----- Load NPC instances (Phase 4) -----
    npc_instance_result = await session.execute(select(NpcInstance))
    npc_instance_models = npc_instance_result.scalars().all()

    npcs: dict[NpcId, WorldNpc] = {}

    for n in npc_instance_models:
        # Get template to populate NPC stats
        template = npc_templates.get(n.template_id)
        if not template:
            continue
        
        # Use instance name override or template name
        npc_name = (n.instance_data or {}).get("name_override", template.name)
        
        npcs[n.id] = WorldNpc(
            id=n.id,
            entity_type=EntityType.NPC,
            name=npc_name,
            room_id=n.room_id,
            # Keywords from template for targeting
            keywords=list(template.keywords),
            # Core stats from template
            level=template.level,
            max_health=template.max_health,
            current_health=n.current_health,
            armor_class=template.armor_class,
            strength=template.strength,
            dexterity=template.dexterity,
            intelligence=template.intelligence,
            # Combat properties from template
            base_attack_damage_min=template.attack_damage_min,
            base_attack_damage_max=template.attack_damage_max,
            base_attack_speed=template.attack_speed,
            experience_reward=template.experience_reward,
            # NPC-specific fields
            template_id=n.template_id,
            spawn_room_id=n.spawn_room_id,
            respawn_time_override=n.respawn_time,  # NULL means use area default
            last_killed_at=n.last_killed_at,
            instance_data=n.instance_data or {},
        )

    # ----- Link NPCs to rooms (unified entity tracking) -----
    for npc in npcs.values():
        if npc.is_alive() and npc.room_id in rooms:
            rooms[npc.room_id].entities.add(npc.id)

    return World(
        rooms=rooms, 
        players=players, 
        areas=areas,
        item_templates=item_templates,
        items=items,
        player_inventories=player_inventories,
        npc_templates=npc_templates,
        npcs=npcs,
        container_contents=container_contents,
    )


def load_triggers_from_yaml(world: World, world_data_dir: str | None = None) -> None:
    """
    Load room and area triggers from YAML files into the world.
    
    This function is called after load_world() to populate triggers
    from the YAML definitions into the WorldRoom and WorldArea objects.
    
    Args:
        world: The loaded World object
        world_data_dir: Optional path to world_data directory. If not provided,
                       defaults to backend/world_data
    """
    from pathlib import Path
    import yaml
    from .systems.triggers import RoomTrigger, TriggerCondition, TriggerAction
    
    if world_data_dir is None:
        # Default: backend/world_data relative to this file
        world_data_dir = Path(__file__).parent.parent.parent / "world_data"
    else:
        world_data_dir = Path(world_data_dir)
    
    rooms_loaded = 0
    areas_loaded = 0
    
    # ----- Load room triggers -----
    rooms_dir = world_data_dir / "rooms"
    if rooms_dir.exists():
        yaml_files = list(rooms_dir.glob("**/*.yaml"))
        for yaml_file in yaml_files:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                room_data = yaml.safe_load(f)
            
            if not room_data:
                continue
                
            room_id = room_data.get('id')
            triggers_data = room_data.get('triggers', [])
            
            if not room_id or not triggers_data:
                continue
            
            room = world.rooms.get(room_id)
            if not room:
                continue
            
            # Parse each trigger
            for trigger_dict in triggers_data:
                trigger = _parse_trigger(trigger_dict)
                if trigger:
                    room.triggers.append(trigger)
                    rooms_loaded += 1
    
    # ----- Load area triggers -----
    areas_dir = world_data_dir / "areas"
    if areas_dir.exists():
        yaml_files = list(areas_dir.glob("**/*.yaml"))
        for yaml_file in yaml_files:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                area_data = yaml.safe_load(f)
            
            if not area_data:
                continue
                
            area_id = area_data.get('id')
            triggers_data = area_data.get('triggers', [])
            
            # Also load area metadata
            if area_id and area_id in world.areas:
                area = world.areas[area_id]
                # Load optional metadata
                if 'recommended_level' in area_data:
                    area.recommended_level = area_data['recommended_level']
                if 'theme' in area_data:
                    area.theme = area_data['theme']
                if 'area_flags' in area_data:
                    area.area_flags = area_data['area_flags']
            
            if not area_id or not triggers_data:
                continue
            
            area = world.areas.get(area_id)
            if not area:
                continue
            
            # Parse each trigger
            for trigger_dict in triggers_data:
                trigger = _parse_trigger(trigger_dict)
                if trigger:
                    area.triggers.append(trigger)
                    areas_loaded += 1
    
    if rooms_loaded > 0 or areas_loaded > 0:
        print(f"Loaded triggers: {rooms_loaded} room triggers, {areas_loaded} area triggers")


def _parse_trigger(trigger_dict: dict):
    """
    Parse a trigger dictionary from YAML into a RoomTrigger object.
    
    Expected format:
        id: unique_trigger_id
        name: Human-readable name
        event_type: on_enter | on_exit | on_command | on_timer | on_area_enter | on_area_exit
        command_pattern: "pattern*"  # For on_command triggers
        interval_seconds: 60         # For on_timer triggers
        conditions:
          - type: flag_set
            flag: some_flag
            expected: true
          - type: has_item
            template_id: item_123
        actions:
          - type: message_player
            message: "You see something"
          - type: set_flag
            flag: some_flag
            value: true
        cooldown: 30
        max_fires: 1
        enabled: true
    
    Returns:
        RoomTrigger or None if parsing fails.
    """
    from .systems.triggers import RoomTrigger, TriggerCondition, TriggerAction
    
    if not isinstance(trigger_dict, dict):
        return None
    
    trigger_id = trigger_dict.get('id')
    # Support both 'event' and 'event_type' for YAML flexibility
    event_type = trigger_dict.get('event') or trigger_dict.get('event_type')
    
    if not trigger_id or not event_type:
        print(f"Warning: Trigger missing id or event: {trigger_dict}")
        return None
    
    # Parse conditions
    conditions: list[TriggerCondition] = []
    for cond_dict in trigger_dict.get('conditions', []):
        if isinstance(cond_dict, dict):
            cond_type = cond_dict.pop('type', None)
            if cond_type:
                conditions.append(TriggerCondition(
                    type=cond_type,
                    params=cond_dict.copy()
                ))
                # Restore type for potential re-use
                cond_dict['type'] = cond_type
    
    # Parse actions
    actions: list[TriggerAction] = []
    for action_dict in trigger_dict.get('actions', []):
        if isinstance(action_dict, dict):
            action_type = action_dict.pop('type', None)
            if action_type:
                actions.append(TriggerAction(
                    type=action_type,
                    params=action_dict.copy()
                ))
                # Restore type for potential re-use
                action_dict['type'] = action_type
    
    # Support both 'timer_interval' and 'interval_seconds' for YAML flexibility
    timer_interval = trigger_dict.get('timer_interval') or trigger_dict.get('interval_seconds')
    
    return RoomTrigger(
        id=trigger_id,
        event=event_type,
        conditions=conditions,
        actions=actions,
        command_pattern=trigger_dict.get('command_pattern'),
        timer_interval=timer_interval,
        timer_initial_delay=trigger_dict.get('timer_initial_delay', 0.0),
        cooldown=trigger_dict.get('cooldown', 0.0),
        max_fires=trigger_dict.get('max_fires', -1),
        enabled=trigger_dict.get('enabled', True),
    )


def load_quests_into_system(quest_system, world_data_dir: str | None = None) -> int:
    """
    Load quest templates from YAML files into the QuestSystem.
    
    Args:
        quest_system: The QuestSystem instance to register quests with
        world_data_dir: Optional path to world_data directory
        
    Returns:
        Number of quests loaded
    """
    from pathlib import Path
    import yaml
    from .systems.quests import (
        QuestTemplate, QuestObjective, QuestReward, ObjectiveType
    )
    
    if world_data_dir is None:
        world_data_dir = Path(__file__).parent.parent.parent / "world_data"
    else:
        world_data_dir = Path(world_data_dir)
    
    quests_dir = world_data_dir / "quests"
    loaded = 0
    
    if not quests_dir.exists():
        print(f"Quests directory not found: {quests_dir}")
        return 0
    
    yaml_files = list(quests_dir.glob("**/*.yaml"))
    for yaml_file in yaml_files:
        # Skip README files
        if yaml_file.stem.lower() == 'readme':
            continue
            
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                quest_data = yaml.safe_load(f)
            
            if not quest_data or 'id' not in quest_data:
                continue
            
            # Parse objectives
            objectives = []
            for obj_data in quest_data.get('objectives', []):
                try:
                    obj_type = ObjectiveType(obj_data.get('type', 'visit'))
                except ValueError:
                    obj_type = ObjectiveType.VISIT
                    
                objectives.append(QuestObjective(
                    id=obj_data.get('id', ''),
                    type=obj_type,
                    description=obj_data.get('description', ''),
                    target_template_id=obj_data.get('target_template_id'),
                    target_room_id=obj_data.get('target_room_id'),
                    target_npc_name=obj_data.get('target_npc_name'),
                    required_count=obj_data.get('required_count', 1),
                    command_pattern=obj_data.get('command_pattern'),
                    hidden=obj_data.get('hidden', False),
                    optional=obj_data.get('optional', False),
                ))
            
            # Parse rewards
            rewards_data = quest_data.get('rewards', {})
            rewards = QuestReward(
                experience=rewards_data.get('experience', 0),
                items=[tuple(item) for item in rewards_data.get('items', [])],
                effects=rewards_data.get('effects', []),
                flags=rewards_data.get('flags', {}),
                currency=rewards_data.get('currency', 0),
                reputation=rewards_data.get('reputation', {}),
            )
            
            # Create template
            template = QuestTemplate(
                id=quest_data['id'],
                name=quest_data.get('name', quest_data['id']),
                description=quest_data.get('description', ''),
                giver_npc_template=quest_data.get('giver_npc_template'),
                giver_room_id=quest_data.get('giver_room_id'),
                prerequisites=quest_data.get('prerequisites', []),
                level_requirement=quest_data.get('level_requirement', 1),
                required_items=quest_data.get('required_items', []),
                required_flags=quest_data.get('required_flags', {}),
                objectives=objectives,
                turn_in_npc_template=quest_data.get('turn_in_npc_template'),
                turn_in_room_id=quest_data.get('turn_in_room_id'),
                auto_complete=quest_data.get('auto_complete', False),
                rewards=rewards,
                category=quest_data.get('category', 'main'),
                repeatable=quest_data.get('repeatable', False),
                cooldown_hours=quest_data.get('cooldown_hours', 0),
                time_limit_minutes=quest_data.get('time_limit_minutes'),
                accept_dialogue=quest_data.get('accept_dialogue', 'Quest accepted.'),
                progress_dialogue=quest_data.get('progress_dialogue', 'Still working on it?'),
                complete_dialogue=quest_data.get('complete_dialogue', 'Well done!'),
                on_accept_actions=quest_data.get('on_accept_actions', []),
                on_complete_actions=quest_data.get('on_complete_actions', []),
                on_turn_in_actions=quest_data.get('on_turn_in_actions', []),
            )
            
            quest_system.register_quest(template)
            print(f"Loaded quest: {template.name} ({template.id})")
            loaded += 1
            
        except Exception as e:
            print(f"Error loading quest from {yaml_file}: {e}")
    
    print(f"Loaded {loaded} quests into QuestSystem")
    return loaded


def load_dialogues_into_system(quest_system, world_data_dir: str | None = None) -> int:
    """
    Load NPC dialogue trees from YAML files into the QuestSystem.
    
    Args:
        quest_system: The QuestSystem instance to register dialogues with
        world_data_dir: Optional path to world_data directory
        
    Returns:
        Number of dialogue trees loaded
    """
    from pathlib import Path
    import yaml
    from .systems.quests import (
        DialogueTree, DialogueNode, DialogueOption, 
        DialogueCondition, DialogueAction, DialogueEntryOverride
    )
    
    if world_data_dir is None:
        world_data_dir = Path(__file__).parent.parent.parent / "world_data"
    else:
        world_data_dir = Path(world_data_dir)
    
    dialogues_dir = world_data_dir / "dialogues"
    loaded = 0
    
    if not dialogues_dir.exists():
        print(f"Dialogues directory not found: {dialogues_dir}")
        return 0
    
    yaml_files = list(dialogues_dir.glob("**/*.yaml"))
    for yaml_file in yaml_files:
        # Skip README files
        if yaml_file.stem.lower() == 'readme':
            continue
            
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                dialogue_data = yaml.safe_load(f)
            
            if not dialogue_data or 'npc_template_id' not in dialogue_data:
                continue
            
            npc_template_id = dialogue_data['npc_template_id']
            
            # Parse nodes
            nodes = {}
            for node_id, node_data in dialogue_data.get('nodes', {}).items():
                # Parse node conditions
                node_conditions = []
                for cond_data in node_data.get('conditions', []):
                    node_conditions.append(DialogueCondition(
                        type=cond_data.get('type', ''),
                        params=cond_data.get('params', {}),
                        negate=cond_data.get('negate', False),
                    ))
                
                # Parse node actions
                node_actions = []
                for action_data in node_data.get('actions', []):
                    node_actions.append(DialogueAction(
                        type=action_data.get('type', ''),
                        params=action_data.get('params', {}),
                    ))
                
                # Parse options
                options = []
                for opt_data in node_data.get('options', []):
                    # Parse option conditions
                    opt_conditions = []
                    for cond_data in opt_data.get('conditions', []):
                        opt_conditions.append(DialogueCondition(
                            type=cond_data.get('type', ''),
                            params=cond_data.get('params', {}),
                            negate=cond_data.get('negate', False),
                        ))
                    
                    # Parse option actions
                    opt_actions = []
                    for action_data in opt_data.get('actions', []):
                        opt_actions.append(DialogueAction(
                            type=action_data.get('type', ''),
                            params=action_data.get('params', {}),
                        ))
                    
                    options.append(DialogueOption(
                        text=opt_data.get('text', ''),
                        next_node=opt_data.get('next_node'),
                        conditions=opt_conditions,
                        actions=opt_actions,
                        accept_quest=opt_data.get('accept_quest'),
                        turn_in_quest=opt_data.get('turn_in_quest'),
                        hidden_if_unavailable=opt_data.get('hidden_if_unavailable', True),
                    ))
                
                nodes[node_id] = DialogueNode(
                    id=node_id,
                    text=node_data.get('text', ''),
                    options=options,
                    conditions=node_conditions,
                    actions=node_actions,
                )
            
            # Parse entry overrides
            entry_overrides = []
            for override_data in dialogue_data.get('entry_overrides', []):
                conditions = []
                for cond_data in override_data.get('conditions', []):
                    conditions.append(DialogueCondition(
                        type=cond_data.get('type', ''),
                        params=cond_data.get('params', {}),
                        negate=cond_data.get('negate', False),
                    ))
                entry_overrides.append(DialogueEntryOverride(
                    conditions=conditions,
                    node_id=override_data.get('node_id', ''),
                ))
            
            # Create dialogue tree
            tree = DialogueTree(
                npc_template_id=npc_template_id,
                nodes=nodes,
                entry_node=dialogue_data.get('entry_node', 'greet'),
                entry_overrides=entry_overrides,
            )
            
            quest_system.register_dialogue(tree)
            print(f"Loaded dialogue for: {npc_template_id}")
            loaded += 1
            
        except Exception as e:
            print(f"Error loading dialogue from {yaml_file}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"Loaded {loaded} dialogues into QuestSystem")
    return loaded


def load_quest_chains_into_system(quest_system, world_data_dir: str | None = None) -> int:
    """
    Load quest chains from YAML files into the QuestSystem.
    
    Phase X.4: Quest chains link multiple quests into a storyline
    with bonus rewards on completion.
    
    Args:
        quest_system: The QuestSystem instance to register chains with
        world_data_dir: Optional path to world_data directory
        
    Returns:
        Number of chains loaded
    """
    from pathlib import Path
    import yaml
    from .systems.quests import QuestChain, QuestReward
    
    if world_data_dir is None:
        world_data_dir = Path(__file__).parent.parent.parent / "world_data"
    else:
        world_data_dir = Path(world_data_dir)
    
    chains_dir = world_data_dir / "quest_chains"
    loaded = 0
    
    if not chains_dir.exists():
        print(f"Quest chains directory not found: {chains_dir}")
        return 0
    
    yaml_files = list(chains_dir.glob("**/*.yaml"))
    for yaml_file in yaml_files:
        # Skip README files
        if yaml_file.stem.lower() == 'readme':
            continue
            
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                chain_data = yaml.safe_load(f)
            
            if not chain_data or 'id' not in chain_data:
                continue
            
            # Parse chain rewards
            rewards_data = chain_data.get('chain_rewards', {})
            chain_rewards = QuestReward(
                experience=rewards_data.get('experience', 0),
                items=[tuple(item) for item in rewards_data.get('items', [])],
                flags=rewards_data.get('flags', {}),
                currency=rewards_data.get('currency', 0),
            )
            
            # Create chain
            chain = QuestChain(
                id=chain_data['id'],
                name=chain_data.get('name', chain_data['id']),
                description=chain_data.get('description', ''),
                quest_ids=chain_data.get('quest_ids', []),
                unlock_requirements=chain_data.get('unlock_requirements', []),
                chain_rewards=chain_rewards,
                completion_flags=chain_data.get('completion_flags', {}),
            )
            
            quest_system.register_chain(chain)
            print(f"Loaded quest chain: {chain.name} ({chain.id})")
            loaded += 1
            
        except Exception as e:
            print(f"Error loading quest chain from {yaml_file}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"Loaded {loaded} quest chains into QuestSystem")
    return loaded


def restore_player_quest_progress(quest_system, player) -> None:
    """
    Restore a player's quest progress from their saved data.
    
    This converts the stored dict format back into QuestProgress objects
    in the player's quest_progress dict.
    
    Args:
        quest_system: The QuestSystem instance
        player: The WorldPlayer to restore progress for
    """
    from .systems.quests import QuestProgress, QuestStatus
    
    if not player.quest_progress:
        return
    
    restored = {}
    for quest_id, progress_data in player.quest_progress.items():
        if isinstance(progress_data, dict):
            try:
                status_str = progress_data.get('status', 'in_progress')
                status = QuestStatus(status_str)
            except ValueError:
                status = QuestStatus.IN_PROGRESS
            
            restored[quest_id] = QuestProgress(
                quest_id=quest_id,
                status=status,
                objective_progress=progress_data.get('objective_progress', {}),
                accepted_at=progress_data.get('accepted_at'),
                completed_at=progress_data.get('completed_at'),
                turned_in_at=progress_data.get('turned_in_at'),
                completion_count=progress_data.get('completion_count', 0),
                last_completed_at=progress_data.get('last_completed_at'),
            )
    
    player.quest_progress = restored
