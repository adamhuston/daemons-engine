# backend/app/engine/systems/persistence.py
"""
StateTracker - Dirty tracking and persistence for world state.

Phase 6: Handles tracking which entities have been modified and need saving.
Supports both periodic saves (60s interval) and immediate critical saves.

Entity Types Tracked:
- players: Player stats, inventory, quest progress
- rooms: Room flags, dynamic exits, dynamic descriptions
- npcs: NPC position, health (for persistent NPCs only)
- items: Ground items with decay timers
- triggers: Fire counts for permanent triggers
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Set

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from .context import GameContext


# Entity type constants
ENTITY_PLAYER = "player"
ENTITY_ROOM = "room"
ENTITY_NPC = "npc"
ENTITY_ITEM = "item"
ENTITY_TRIGGER = "trigger"


@dataclass
class DirtyState:
    """Tracks which entities have been modified since last save."""

    players: Set[str] = field(default_factory=set)
    rooms: Set[str] = field(default_factory=set)
    npcs: Set[str] = field(default_factory=set)
    items: Set[str] = field(default_factory=set)
    triggers: Set[str] = field(default_factory=set)  # "scope:scope_id:trigger_id"

    def clear(self) -> None:
        """Clear all dirty flags after a successful save."""
        self.players.clear()
        self.rooms.clear()
        self.npcs.clear()
        self.items.clear()
        self.triggers.clear()

    def has_dirty_entities(self) -> bool:
        """Check if there are any dirty entities to save."""
        return bool(
            self.players or self.rooms or self.npcs or self.items or self.triggers
        )

    def summary(self) -> str:
        """Return a summary of dirty entity counts."""
        parts = []
        if self.players:
            parts.append(f"{len(self.players)} players")
        if self.rooms:
            parts.append(f"{len(self.rooms)} rooms")
        if self.npcs:
            parts.append(f"{len(self.npcs)} npcs")
        if self.items:
            parts.append(f"{len(self.items)} items")
        if self.triggers:
            parts.append(f"{len(self.triggers)} triggers")
        return ", ".join(parts) if parts else "nothing"


class StateTracker:
    """
    Tracks modified entities and handles persistence to database.

    Usage:
        tracker = StateTracker(ctx, db_session_factory)

        # Mark entity as dirty (will be saved in next periodic save)
        tracker.mark_dirty(ENTITY_PLAYER, player_id)

        # Mark entity as dirty with critical flag (saves immediately)
        await tracker.mark_dirty(ENTITY_PLAYER, player_id, critical=True)

        # Periodic save (called by TimeEventManager)
        await tracker.save_all_dirty()
    """

    # Save interval in seconds
    SAVE_INTERVAL = 60.0

    def __init__(
        self, ctx: "GameContext", db_session_factory: Callable[[], "AsyncSession"]
    ) -> None:
        self.ctx = ctx
        self.db_session_factory = db_session_factory
        self._dirty = DirtyState()
        self._last_save_time = time.time()
        self._save_event_id: str | None = None

    # ---------- Dirty Marking ----------

    async def mark_dirty(
        self, entity_type: str, entity_id: str, critical: bool = False
    ) -> None:
        """
        Mark an entity as needing to be saved.

        Args:
            entity_type: One of ENTITY_PLAYER, ENTITY_ROOM, etc.
            entity_id: The unique identifier for the entity
            critical: If True, save immediately instead of waiting for periodic save
        """
        # Add to dirty set
        dirty_set = self._get_dirty_set(entity_type)
        if dirty_set is not None:
            dirty_set.add(entity_id)

        # Critical saves happen immediately
        if critical:
            await self._save_entity(entity_type, entity_id)
            dirty_set.discard(entity_id)  # Remove from dirty since we just saved

    def mark_dirty_sync(self, entity_type: str, entity_id: str) -> None:
        """
        Synchronous version of mark_dirty for use in non-async contexts.

        Note: This cannot trigger critical saves. Use mark_dirty() for critical saves.
        """
        dirty_set = self._get_dirty_set(entity_type)
        if dirty_set is not None:
            dirty_set.add(entity_id)

    def _get_dirty_set(self, entity_type: str) -> Set[str] | None:
        """Get the dirty set for a given entity type."""
        if entity_type == ENTITY_PLAYER:
            return self._dirty.players
        elif entity_type == ENTITY_ROOM:
            return self._dirty.rooms
        elif entity_type == ENTITY_NPC:
            return self._dirty.npcs
        elif entity_type == ENTITY_ITEM:
            return self._dirty.items
        elif entity_type == ENTITY_TRIGGER:
            return self._dirty.triggers
        else:
            print(f"[StateTracker] Unknown entity type: {entity_type}")
            return None

    # ---------- Save Operations ----------

    async def save_all_dirty(self) -> int:
        """
        Save all dirty entities to database.

        Called periodically by TimeEventManager.

        Returns:
            Number of entities saved
        """
        if not self._dirty.has_dirty_entities():
            return 0

        saved_count = 0
        print(f"[StateTracker] Saving dirty entities: {self._dirty.summary()}")

        async with self.db_session_factory() as session:
            # Save players
            for player_id in list(self._dirty.players):
                try:
                    await self._save_player(session, player_id)
                    saved_count += 1
                except Exception as e:
                    print(f"[StateTracker] Error saving player {player_id}: {e}")

            # Save rooms
            for room_id in list(self._dirty.rooms):
                try:
                    await self._save_room(session, room_id)
                    saved_count += 1
                except Exception as e:
                    print(f"[StateTracker] Error saving room {room_id}: {e}")

            # Save NPCs
            for npc_id in list(self._dirty.npcs):
                try:
                    await self._save_npc(session, npc_id)
                    saved_count += 1
                except Exception as e:
                    print(f"[StateTracker] Error saving npc {npc_id}: {e}")

            # Save items
            for item_id in list(self._dirty.items):
                try:
                    await self._save_item(session, item_id)
                    saved_count += 1
                except Exception as e:
                    print(f"[StateTracker] Error saving item {item_id}: {e}")

            # Save triggers
            for trigger_key in list(self._dirty.triggers):
                try:
                    await self._save_trigger(session, trigger_key)
                    saved_count += 1
                except Exception as e:
                    print(f"[StateTracker] Error saving trigger {trigger_key}: {e}")

            await session.commit()

        # Clear dirty flags after successful save
        self._dirty.clear()
        self._last_save_time = time.time()

        print(f"[StateTracker] Saved {saved_count} entities")
        return saved_count

    async def _save_entity(self, entity_type: str, entity_id: str) -> None:
        """Save a single entity immediately (for critical saves)."""
        async with self.db_session_factory() as session:
            if entity_type == ENTITY_PLAYER:
                await self._save_player(session, entity_id)
            elif entity_type == ENTITY_ROOM:
                await self._save_room(session, entity_id)
            elif entity_type == ENTITY_NPC:
                await self._save_npc(session, entity_id)
            elif entity_type == ENTITY_ITEM:
                await self._save_item(session, entity_id)
            elif entity_type == ENTITY_TRIGGER:
                await self._save_trigger(session, entity_id)
            await session.commit()
            print(f"[StateTracker] Critical save: {entity_type} {entity_id}")

    # ---------- Entity-Specific Save Logic ----------

    async def _save_player(self, session: "AsyncSession", player_id: str) -> None:
        """
        Save player state to database.

        Reuses existing save_player_stats logic from WorldEngine.
        """
        # Delegate to engine's save method which already handles all player fields
        if self.ctx.engine:
            await self.ctx.engine.save_player_stats(player_id)

    async def _save_room(self, session: "AsyncSession", room_id: str) -> None:
        """
        Save room runtime state (flags, dynamic exits) to database.

        Note: Requires room_state table from Phase 6.2 migration.
        """
        from sqlalchemy import text

        room = self.ctx.world.rooms.get(room_id)
        if not room:
            return

        # Check if room_state table exists (graceful degradation)
        try:
            await session.execute(
                text(
                    """
                INSERT INTO room_state (room_id, room_flags, dynamic_exits, dynamic_description, updated_at)
                VALUES (:room_id, :room_flags, :dynamic_exits, :dynamic_description, :updated_at)
                ON CONFLICT (room_id) DO UPDATE SET
                    room_flags = :room_flags,
                    dynamic_exits = :dynamic_exits,
                    dynamic_description = :dynamic_description,
                    updated_at = :updated_at
            """
                ),
                {
                    "room_id": room_id,
                    "room_flags": str(room.room_flags) if room.room_flags else "{}",
                    "dynamic_exits": (
                        str(room.dynamic_exits)
                        if hasattr(room, "dynamic_exits")
                        else "{}"
                    ),
                    "dynamic_description": getattr(room, "dynamic_description", None),
                    "updated_at": time.time(),
                },
            )
        except Exception as e:
            # Table doesn't exist yet - skip gracefully
            print(f"[StateTracker] room_state table not available: {e}")

    async def _save_npc(self, session: "AsyncSession", npc_id: str) -> None:
        """
        Save NPC runtime state for persistent NPCs.

        Note: Requires npc_state table from Phase 6.2 migration.
        """
        from sqlalchemy import text

        npc = self.ctx.world.npcs.get(npc_id)
        if not npc:
            return

        # Only save if NPC template has persist_state=True
        template = self.ctx.world.npc_templates.get(npc.template_id)
        if not template or not getattr(template, "persist_state", False):
            return

        try:
            await session.execute(
                text(
                    """
                INSERT INTO npc_state (instance_id, template_id, current_room_id, current_hp, is_alive, updated_at)
                VALUES (:instance_id, :template_id, :current_room_id, :current_hp, :is_alive, :updated_at)
                ON CONFLICT (instance_id) DO UPDATE SET
                    current_room_id = :current_room_id,
                    current_hp = :current_hp,
                    is_alive = :is_alive,
                    updated_at = :updated_at
            """
                ),
                {
                    "instance_id": npc_id,
                    "template_id": npc.template_id,
                    "current_room_id": npc.current_room_id,
                    "current_hp": npc.current_hp,
                    "is_alive": npc.is_alive,
                    "updated_at": time.time(),
                },
            )
        except Exception as e:
            print(f"[StateTracker] npc_state table not available: {e}")

    async def restore_persistent_npcs(self) -> int:
        """
        Restore persistent NPC states from database.

        Updates NPC positions and health for NPCs with persist_state=True.
        Called during world load.

        Returns number of NPCs restored.
        """
        from sqlalchemy import text

        restored_count = 0

        try:
            async with self.db_session_factory() as session:
                result = await session.execute(text("SELECT * FROM npc_state"))
                rows = result.fetchall()
        except Exception as e:
            print(f"[StateTracker] npc_state table not available: {e}")
            return 0

        for row in rows:
            npc_id = row.instance_id
            npc = self.ctx.world.npcs.get(npc_id)

            if not npc:
                # NPC doesn't exist in world anymore
                continue

            # Verify NPC template has persist_state=True
            template = self.ctx.world.npc_templates.get(npc.template_id)
            if not template or not getattr(template, "persist_state", False):
                continue

            # Restore NPC state
            npc.current_room_id = row.current_room_id
            npc.room_id = row.current_room_id
            npc.current_hp = row.current_hp
            npc.is_alive = row.is_alive

            # Update room's entity set if needed
            for room_id, room in self.ctx.world.rooms.items():
                if npc_id in room.entities:
                    if room_id != row.current_room_id:
                        room.entities.remove(npc_id)
                    break

            new_room = self.ctx.world.rooms.get(row.current_room_id)
            if new_room and npc_id not in new_room.entities:
                new_room.entities.add(npc_id)

            restored_count += 1

        if restored_count > 0:
            print(f"[StateTracker] Restored {restored_count} persistent NPC states")

        return restored_count

    async def _save_item(self, session: "AsyncSession", item_id: str) -> None:
        """
        Save ground item with decay tracking.

        Note: Uses existing item_instances table with new columns from Phase 6.2.
        """
        from sqlalchemy import text

        item = self.ctx.world.items.get(item_id)
        if not item:
            return

        # Only track ground items (not in inventory)
        if item.player_id:
            return

        try:
            await session.execute(
                text(
                    """
                UPDATE item_instances
                SET room_id = :room_id,
                    dropped_at = :dropped_at,
                    decay_minutes = :decay_minutes
                WHERE id = :item_id
            """
                ),
                {
                    "item_id": item_id,
                    "room_id": item.room_id,
                    "dropped_at": getattr(item, "dropped_at", None),
                    "decay_minutes": getattr(item, "decay_minutes", 60),
                },
            )
        except Exception as e:
            print(f"[StateTracker] Error saving item {item_id}: {e}")

    async def _save_trigger(self, session: "AsyncSession", trigger_key: str) -> None:
        """
        Save permanent trigger fire count.

        trigger_key format: "scope:scope_id:trigger_id"

        Note: Requires trigger_state table from Phase 6.2 migration.
        """
        from sqlalchemy import text

        try:
            parts = trigger_key.split(":", 2)
            if len(parts) != 3:
                print(f"[StateTracker] Invalid trigger key: {trigger_key}")
                return

            scope, scope_id, trigger_id = parts

            # Get trigger fire count from the appropriate location
            fire_count = 0
            if scope == "room":
                room = self.ctx.world.rooms.get(scope_id)
                if room and hasattr(room, "trigger_states"):
                    state = room.trigger_states.get(trigger_id)
                    if state:
                        fire_count = state.fire_count
            elif scope == "area":
                area = self.ctx.world.areas.get(scope_id)
                if area and hasattr(area, "trigger_states"):
                    state = area.trigger_states.get(trigger_id)
                    if state:
                        fire_count = state.fire_count

            await session.execute(
                text(
                    """
                INSERT INTO trigger_state (trigger_id, scope, scope_id, fire_count, last_fired_at)
                VALUES (:trigger_id, :scope, :scope_id, :fire_count, :last_fired_at)
                ON CONFLICT (trigger_id, scope, scope_id) DO UPDATE SET
                    fire_count = :fire_count,
                    last_fired_at = :last_fired_at
            """
                ),
                {
                    "trigger_id": trigger_id,
                    "scope": scope,
                    "scope_id": scope_id,
                    "fire_count": fire_count,
                    "last_fired_at": time.time(),
                },
            )
        except Exception as e:
            print(f"[StateTracker] trigger_state table not available: {e}")

    # ---------- Item Decay System ----------

    # Item decay interval (5 minutes)
    DECAY_CHECK_INTERVAL = 300.0

    # Default item decay time (1 hour)
    DEFAULT_DECAY_TIME = 3600.0

    def schedule_item_decay(self) -> None:
        """
        Schedule periodic item decay checks.

        Removes ground items that have been on the ground for too long.
        """
        if not self.ctx.time_manager:
            print(
                "[StateTracker] TimeEventManager not available, cannot schedule item decay"
            )
            return

        async def decay_callback():
            await self.process_item_decay()

        self._decay_event_id = self.ctx.time_manager.schedule(
            delay_seconds=self.DECAY_CHECK_INTERVAL,
            callback=decay_callback,
            recurring=True,
            event_id="persistence_item_decay",
        )
        print(
            f"[StateTracker] Scheduled item decay check every {self.DECAY_CHECK_INTERVAL}s"
        )

    async def process_item_decay(self) -> int:
        """
        Remove items that have been on the ground too long.

        Returns number of items removed.
        """
        now = time.time()
        removed_count = 0
        items_to_remove = []

        # Find items that should decay
        for item_id, item in self.ctx.world.items.items():
            # Only process ground items
            if not item.room_id or item.player_id:
                continue

            # Check if item has decay time set
            dropped_at = getattr(item, "dropped_at", None)
            if dropped_at is None:
                continue

            # Calculate decay threshold
            template = self.ctx.world.item_templates.get(item.template_id)
            decay_time = self.DEFAULT_DECAY_TIME
            if template and hasattr(template, "decay_minutes"):
                decay_time = template.decay_minutes * 60

            if now - dropped_at >= decay_time:
                items_to_remove.append((item_id, item.room_id))

        # Remove decayed items
        for item_id, room_id in items_to_remove:
            item = self.ctx.world.items.get(item_id)
            if not item:
                continue

            room = self.ctx.world.rooms.get(room_id)
            if room:
                room.items.discard(item_id)

            del self.ctx.world.items[item_id]
            removed_count += 1

            # Also remove from database
            async with self.db_session_factory() as session:
                from sqlalchemy import text

                await session.execute(
                    text("DELETE FROM item_instances WHERE id = :item_id"),
                    {"item_id": item_id},
                )
                await session.commit()

        if removed_count > 0:
            print(f"[StateTracker] Decayed {removed_count} ground items")

        return removed_count

    # ---------- Scheduling ----------

    def schedule_periodic_save(self) -> None:
        """
        Schedule periodic save using TimeEventManager.

        Called during WorldEngine startup.
        """
        if not self.ctx.time_manager:
            print(
                "[StateTracker] TimeEventManager not available, cannot schedule periodic saves"
            )
            return

        async def periodic_save_callback():
            await self.save_all_dirty()

        self._save_event_id = self.ctx.time_manager.schedule(
            delay_seconds=self.SAVE_INTERVAL,
            callback=periodic_save_callback,
            recurring=True,
            event_id="persistence_periodic_save",
        )
        print(f"[StateTracker] Scheduled periodic save every {self.SAVE_INTERVAL}s")

        # Also schedule item decay
        self.schedule_item_decay()

    def stop_periodic_save(self) -> None:
        """Cancel the periodic save event."""
        if self._save_event_id and self.ctx.time_manager:
            self.ctx.time_manager.cancel(self._save_event_id)
            self._save_event_id = None

        # Also cancel decay check
        if (
            hasattr(self, "_decay_event_id")
            and self._decay_event_id
            and self.ctx.time_manager
        ):
            self.ctx.time_manager.cancel(self._decay_event_id)
            self._decay_event_id = None

    # ---------- Shutdown ----------

    async def shutdown(self) -> None:
        """
        Save all state before shutdown.

        Called during graceful server shutdown.
        """
        print("[StateTracker] Shutdown: saving all dirty state...")
        self.stop_periodic_save()
        await self.save_all_dirty()
        print("[StateTracker] Shutdown complete")
