# backend/app/engine/inventory.py

from .world import ItemId, PlayerId, World, WorldItem


class InventoryError(Exception):
    """Base exception for inventory operations."""

    pass


class InventoryFullError(InventoryError):
    """Raised when inventory is at capacity."""

    pass


class ItemNotFoundError(InventoryError):
    """Raised when item is not found."""

    pass


def calculate_inventory_weight(world: World, player_id: PlayerId) -> float:
    """Calculate total weight of player's inventory."""
    player = world.players[player_id]
    total_weight = 0.0

    for item_id in player.inventory_items:
        item = world.items[item_id]
        template = world.item_templates[item.template_id]
        total_weight += template.weight * item.quantity

    return total_weight


def can_add_item(
    world: World, player_id: PlayerId, template_id: str, quantity: int = 1
) -> tuple[bool, str]:
    """
    Check if player can add item to inventory.

    Returns: (can_add: bool, reason: str)
    """
    player = world.players[player_id]
    inventory = player.inventory_meta
    template = world.item_templates[template_id]

    if not inventory:
        # Auto-initialize inventory if missing (for legacy/test players)
        from .world import PlayerInventory

        player.inventory_meta = PlayerInventory(
            player_id=player_id,
            max_weight=100.0,
            max_slots=20,
            current_weight=0.0,
            current_slots=0,
        )
        inventory = player.inventory_meta

    # Check weight
    new_weight = calculate_inventory_weight(world, player_id) + (
        template.weight * quantity
    )
    if new_weight > inventory.max_weight:
        return False, f"Too heavy! ({new_weight:.1f}/{inventory.max_weight:.1f} kg)"

    # Check slots (if not stackable)
    if template.max_stack_size == 1:
        if inventory.current_slots >= inventory.max_slots:
            return (
                False,
                f"Inventory full! ({inventory.current_slots}/{inventory.max_slots} slots)",
            )

    return True, ""


def add_item_to_inventory(world: World, player_id: PlayerId, item_id: ItemId) -> None:
    """
    Add item to player inventory. Handles stacking automatically.

    Raises InventoryFullError if inventory is at capacity.
    """
    player = world.players[player_id]
    item = world.items[item_id]
    template = world.item_templates[item.template_id]

    # Check capacity
    can_add, reason = can_add_item(world, player_id, item.template_id, item.quantity)
    if not can_add:
        raise InventoryFullError(reason)

    # Try to stack with existing item
    if template.max_stack_size > 1:
        for existing_id in player.inventory_items:
            existing = world.items[existing_id]
            if item.can_stack_with(existing, template):
                # Stack items
                existing.quantity += item.quantity
                # Remove the duplicate item instance
                del world.items[item_id]
                return

    # Add as new item
    item.player_id = player_id
    item.room_id = None
    player.inventory_items.add(item_id)

    # Update inventory metadata
    if player.inventory_meta:
        player.inventory_meta.current_weight = calculate_inventory_weight(
            world, player_id
        )
        player.inventory_meta.current_slots = len(player.inventory_items)


def remove_item_from_inventory(
    world: World, player_id: PlayerId, item_id: ItemId
) -> WorldItem:
    """
    Remove item from player inventory.

    Raises ItemNotFoundError if item is not in inventory.
    """
    player = world.players[player_id]

    if item_id not in player.inventory_items:
        raise ItemNotFoundError(f"Item {item_id} not in inventory")

    item = world.items[item_id]

    # Can't drop equipped items
    if item.is_equipped():
        raise InventoryError("Cannot drop equipped item. Unequip first.")

    player.inventory_items.remove(item_id)
    item.player_id = None

    # Update inventory metadata
    if player.inventory_meta:
        player.inventory_meta.current_weight = calculate_inventory_weight(
            world, player_id
        )
        player.inventory_meta.current_slots = len(player.inventory_items)

    return item


def equip_item(world: World, player_id: PlayerId, item_id: ItemId) -> ItemId | None:
    """
    Equip an item. Returns ID of item that was unequipped (if any).

    Raises InventoryError if item cannot be equipped.
    """
    player = world.players[player_id]
    item = world.items[item_id]
    template = world.item_templates[item.template_id]

    # Check if item can be equipped
    if template.equipment_slot is None:
        raise InventoryError(f"{template.name} cannot be equipped")

    # Check if item is in inventory
    if item_id not in player.inventory_items:
        raise InventoryError("Item must be in inventory to equip")

    slot = template.equipment_slot
    previously_equipped = player.equipped_items.get(slot)

    # Unequip existing item in slot
    if previously_equipped:
        prev_item = world.items[previously_equipped]
        prev_item.equipped_slot = None

    # Equip new item
    item.equipped_slot = slot
    player.equipped_items[slot] = item_id

    # Apply stat modifiers (integrate with effect system)
    _apply_equipment_stats(world, player_id, item_id)

    return previously_equipped


def unequip_item(world: World, player_id: PlayerId, item_id: ItemId) -> None:
    """
    Unequip an item.

    Raises InventoryError if item is not equipped.
    """
    player = world.players[player_id]
    item = world.items[item_id]

    if not item.is_equipped():
        raise InventoryError("Item is not equipped")

    slot = item.equipped_slot
    if player.equipped_items.get(slot) != item_id:
        raise InventoryError("Item is not equipped in expected slot")

    # Remove from equipped
    item.equipped_slot = None
    del player.equipped_items[slot]

    # Remove stat modifiers
    _remove_equipment_stats(world, player_id, item_id)


def _apply_equipment_stats(world: World, player_id: PlayerId, item_id: ItemId) -> None:
    """Apply equipment stat modifiers as an effect."""
    import time

    from .world import Effect

    player = world.players[player_id]
    item = world.items[item_id]
    template = world.item_templates[item.template_id]

    if not template.stat_modifiers:
        return

    # Create permanent effect for equipment stats
    effect = Effect(
        effect_id=f"equipment_{item_id}",
        name=f"{template.name} (equipped)",
        effect_type="buff",
        stat_modifiers=template.stat_modifiers,
        duration=float("inf"),  # Permanent while equipped
        applied_at=time.time(),
    )

    player.apply_effect(effect)


def _remove_equipment_stats(world: World, player_id: PlayerId, item_id: ItemId) -> None:
    """Remove equipment stat modifiers effect."""
    player = world.players[player_id]
    player.remove_effect(f"equipment_{item_id}")


def find_item_by_name(
    world: World, player_id: PlayerId, item_name: str, location: str = "inventory"
) -> ItemId | None:
    """
    Find an item by name or keyword in player inventory or equipped items.
    Uses WorldItem.matches_keyword() for consistent targeting behavior.
    Prioritizes exact matches over partial matches.

    Supports numbered targeting: "2.potion" will find the second potion.

    Args:
        world: Game world
        player_id: Player ID
        item_name: Name or keyword to search for (case insensitive, supports "N.keyword" syntax)
        location: "inventory", "equipped", or "both"

    Returns:
        Item ID if found, None otherwise
    """
    player = world.players[player_id]

    # Parse numbered targeting
    target_index = 1
    actual_search = item_name
    if "." in item_name:
        parts = item_name.split(".", 1)
        if len(parts) == 2 and parts[0].isdigit():
            target_num = int(parts[0])
            if target_num >= 1:
                target_index = target_num
                actual_search = parts[1]

    matches_found = 0

    # First try exact match in inventory
    if location in ("inventory", "both"):
        for item_id in player.inventory_items:
            item = world.items[item_id]
            if item.matches_keyword(actual_search, match_mode="exact"):
                matches_found += 1
                if matches_found == target_index:
                    return item_id

    # First try exact match in equipped items
    if location in ("equipped", "both"):
        for item_id in player.equipped_items.values():
            item = world.items[item_id]
            if item.matches_keyword(actual_search, match_mode="exact"):
                matches_found += 1
                if matches_found == target_index:
                    return item_id

    # Reset counter for startswith matches
    matches_found = 0

    # If no exact match, try startswith match in inventory
    if location in ("inventory", "both"):
        for item_id in player.inventory_items:
            item = world.items[item_id]
            if item.matches_keyword(actual_search, match_mode="startswith"):
                matches_found += 1
                if matches_found == target_index:
                    return item_id

    # If no exact match, try startswith match in equipped items
    if location in ("equipped", "both"):
        for item_id in player.equipped_items.values():
            item = world.items[item_id]
            if item.matches_keyword(actual_search, match_mode="startswith"):
                matches_found += 1
                if matches_found == target_index:
                    return item_id

    return None


def find_item_in_room(world: World, room_id: str, item_name: str) -> ItemId | None:
    """
    Find an item by name or keyword in a room.
    Uses WorldItem.matches_keyword() for consistent targeting behavior.
    Prioritizes exact matches over partial matches.

    Supports numbered targeting: "2.potion" will find the second potion.

    Args:
        world: Game world
        room_id: Room ID
        item_name: Name or keyword to search for (case insensitive, supports "N.keyword" syntax)

    Returns:
        Item ID if found, None otherwise
    """
    room = world.rooms[room_id]

    # Parse numbered targeting
    target_index = 1
    actual_search = item_name
    if "." in item_name:
        parts = item_name.split(".", 1)
        if len(parts) == 2 and parts[0].isdigit():
            target_num = int(parts[0])
            if target_num >= 1:
                target_index = target_num
                actual_search = parts[1]

    matches_found = 0

    # First try exact match
    for item_id in room.items:
        item = world.items[item_id]
        if item.matches_keyword(actual_search, match_mode="exact"):
            matches_found += 1
            if matches_found == target_index:
                return item_id

    # Reset counter for startswith matches
    matches_found = 0

    # If no exact match, try startswith match
    for item_id in room.items:
        item = world.items[item_id]
        if item.matches_keyword(actual_search, match_mode="startswith"):
            matches_found += 1
            if matches_found == target_index:
                return item_id

    return None
