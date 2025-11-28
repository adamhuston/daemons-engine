"""
Look Command System: Consolidated view/examine commands with unified formatting.

Consolidates duplicated look logic from:
- _look_at_player
- _look_at_npc_detail  
- _look_at_item_detail

Provides reusable formatters for:
- Health status descriptions
- Type/disposition indicators
- Entity descriptions with properties
"""

from typing import List, Optional, Dict, Any

# Type alias
Event = Dict[str, Any]


def format_health_status(current_health: int, max_health: int) -> str:
    """
    Format a health status description based on percentage.
    
    Returns descriptive status like "appears uninjured", "is heavily wounded", etc.
    """
    if max_health <= 0:
        return "appears to be in stasis"
    
    health_percent = (current_health / max_health) * 100
    
    if health_percent >= 100:
        return "appears uninjured"
    elif health_percent >= 75:
        return "has minor injuries"
    elif health_percent >= 50:
        return "is moderately wounded"
    elif health_percent >= 25:
        return "is heavily wounded"
    else:
        return "is near death"


def format_type_indicator(entity_type: str) -> str:
    """
    Format a type/disposition indicator with emoji.
    
    Supports: hostile, neutral, friendly, merchant, custom
    """
    indicators = {
        "hostile": "🔴 Hostile",
        "neutral": "🟡 Neutral",
        "friendly": "🟢 Friendly",
        "merchant": "🛒 Merchant",
    }
    return indicators.get(entity_type, entity_type.title())


def format_entity_description(
    name: str,
    description: str,
    entity_type: Optional[str] = None,
    level: Optional[int] = None,
    current_health: Optional[int] = None,
    max_health: Optional[int] = None,
    instance_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Format a detailed entity description (player, NPC, or item).
    
    Args:
        name: Entity display name
        description: Base description text
        entity_type: Type indicator (hostile, friendly, etc)
        level: Entity level
        current_health: Current health points
        max_health: Max health points
        instance_data: Instance-specific overrides (like guard_message)
    
    Returns:
        Formatted multi-line description
    """
    lines = [f"**{name}**"]
    lines.append(description)
    
    if entity_type:
        lines.append("")
        lines.append(f"Disposition: {format_type_indicator(entity_type)}")
    
    if level is not None:
        lines.append(f"Level: {level}")
    
    if current_health is not None and max_health is not None:
        health_status = format_health_status(current_health, max_health)
        lines.append(f"Condition: {name} {health_status}.")
    
    # Add instance-specific data
    if instance_data and "guard_message" in instance_data:
        lines.append("")
        lines.append(instance_data["guard_message"])
    
    return "\n".join(lines)


def format_item_properties(
    template: Any,  # ItemTemplate
    item: Any,  # WorldItem
) -> List[str]:
    """
    Format item properties (type, weight, durability, effects, etc).
    
    Returns list of property strings to be indented and joined.
    """
    properties = []
    
    # Item type and rarity
    type_str = template.item_type.title()
    if template.item_subtype:
        type_str += f" ({template.item_subtype})"
    if template.rarity != "common":
        type_str += f" - {template.rarity.title()}"
    properties.append(f"Type: {type_str}")
    
    # Weight
    total_weight = template.weight * item.quantity
    if item.quantity > 1:
        properties.append(f"Weight: {total_weight:.1f} kg ({template.weight:.1f} kg each)")
    else:
        properties.append(f"Weight: {total_weight:.1f} kg")
    
    # Durability
    if template.has_durability and item.current_durability is not None:
        properties.append(f"Durability: {item.current_durability}/{template.max_durability}")
    
    # Equipment slot
    if template.equipment_slot:
        slot_name = template.equipment_slot.replace("_", " ").title()
        properties.append(f"Equipment Slot: {slot_name}")
    
    # Stat modifiers
    if template.stat_modifiers:
        stat_strs = []
        for stat, value in template.stat_modifiers.items():
            sign = "+" if value >= 0 else ""
            stat_display = stat.replace("_", " ").title()
            stat_strs.append(f"{sign}{value} {stat_display}")
        properties.append(f"Effects: {', '.join(stat_strs)}")
    
    # Value
    if template.value > 0:
        total_value = template.value * item.quantity
        if item.quantity > 1:
            properties.append(f"Value: {total_value} gold ({template.value} each)")
        else:
            properties.append(f"Value: {total_value} gold")
    
    # Stackable info
    if template.max_stack_size > 1:
        properties.append(f"Quantity: {item.quantity}/{template.max_stack_size}")
    elif item.quantity > 1:
        properties.append(f"Quantity: {item.quantity}")
    
    return properties
