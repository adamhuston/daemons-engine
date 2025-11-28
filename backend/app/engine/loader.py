# backend/app/engine/loader.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Room, Player, Area, ItemTemplate, ItemInstance, PlayerInventory
from .world import (
    World, WorldRoom, WorldPlayer, WorldArea, WorldTime, ItemTemplate as WorldItemTemplate,
    WorldItem, PlayerInventory as WorldPlayerInventory, RoomId, PlayerId, AreaId, ItemId,
    ItemTemplateId, DEFAULT_TIME_PHASES
)


async def load_world(session: AsyncSession) -> World:
    """
    Build the in-memory World from the database.

    Called once at startup (in main.py), but can be reused for reloads/tests.
    """
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

        rooms[r.id] = WorldRoom(
            id=r.id,
            name=r.name,
            description=r.description,
            room_type=r.room_type,
            exits=exits,
            on_enter_effect=r.on_enter_effect,
            on_exit_effect=r.on_exit_effect,
        )

    # ----- Load players -----
    player_result = await session.execute(select(Player))
    player_models = player_result.scalars().all()

    players: dict[PlayerId, WorldPlayer] = {}

    for p in player_models:
        players[p.id] = WorldPlayer(
            id=p.id,
            name=p.name,
            room_id=p.current_room_id,
            on_move_effect=p.data.get("on_move_effect"),
            character_class=p.character_class,
            level=p.level,
            experience=p.experience,
            strength=p.strength,
            dexterity=p.dexterity,
            intelligence=p.intelligence,
            vitality=p.vitality,
            max_health=p.max_health,
            current_health=p.current_health,
            armor_class=p.armor_class,
            max_energy=p.max_energy,
            current_energy=p.current_energy,
        )

    # ----- Place players into rooms -----
    for player in players.values():
        room = rooms.get(player.room_id)
        if room:
            room.players.add(player.id)

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
        )

    # ----- Load item instances (Phase 3) -----
    instance_result = await session.execute(select(ItemInstance))
    instance_models = instance_result.scalars().all()

    items: dict[ItemId, WorldItem] = {}

    for i in instance_models:
        items[i.id] = WorldItem(
            id=i.id,
            template_id=i.template_id,
            room_id=i.room_id,
            player_id=i.player_id,
            container_id=i.container_id,
            quantity=i.quantity,
            current_durability=i.current_durability,
            equipped_slot=i.equipped_slot,
            instance_data=i.instance_data,
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

    # ----- Link inventories to players (Phase 3) -----
    for player in players.values():
        if player.id in player_inventories:
            player.inventory_meta = player_inventories[player.id]

    return World(
        rooms=rooms, 
        players=players, 
        areas=areas,
        item_templates=item_templates,
        items=items,
        player_inventories=player_inventories,
    )
