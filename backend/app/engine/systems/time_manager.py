# backend/app/engine/systems/time_manager.py
"""
TimeEventManager - Handles scheduled events and time-based callbacks.

Provides:
- Priority queue-based event scheduling
- Recurring events with automatic rescheduling
- Event cancellation by ID
- Efficient sleep-based loop (not busy-polling)

Extracted from WorldEngine for modularity.
"""

from __future__ import annotations
import asyncio
import heapq
import time
import uuid
from typing import TYPE_CHECKING, Callable, Awaitable, Dict, List

if TYPE_CHECKING:
    from .context import GameContext
    from ..world import TimeEvent


class TimeEventManager:
    """
    Manages scheduled time events using a priority queue.
    
    Features:
    - O(log n) insertion and removal via heapq
    - Dynamic sleep duration (not busy-polling)
    - Recurring events with automatic rescheduling
    - Event cancellation by ID
    
    Usage:
        time_mgr = TimeEventManager(ctx)
        await time_mgr.start()
        
        event_id = time_mgr.schedule(5.0, my_callback)
        time_mgr.cancel(event_id)
        
        await time_mgr.stop()
    """
    
    def __init__(self, ctx: "GameContext") -> None:
        self.ctx = ctx
        
        # Min-heap priority queue of TimeEvent objects
        self._events: List["TimeEvent"] = []
        
        # Fast lookup by event_id for cancellation
        self._event_ids: Dict[str, "TimeEvent"] = {}
        
        # Background task running the event loop
        self._loop_task: asyncio.Task | None = None
    
    # ---------- Lifecycle ----------
    
    async def start(self) -> None:
        """
        Start the time event processing loop.
        Should be called once during engine startup.
        """
        if self._loop_task is not None:
            print("[TimeManager] Already running")
            return
        
        self._loop_task = asyncio.create_task(self._run_loop())
        print("[TimeManager] Started")
    
    async def stop(self) -> None:
        """
        Stop the time event processing loop.
        Should be called during engine shutdown.
        """
        if self._loop_task is None:
            return
        
        self._loop_task.cancel()
        try:
            await self._loop_task
        except asyncio.CancelledError:
            pass
        
        self._loop_task = None
        print("[TimeManager] Stopped")
    
    @property
    def is_running(self) -> bool:
        """Check if the time system is running."""
        return self._loop_task is not None
    
    # ---------- Event Scheduling ----------
    
    def schedule(
        self,
        delay_seconds: float,
        callback: Callable[[], Awaitable[None]],
        event_id: str | None = None,
        recurring: bool = False,
    ) -> str:
        """
        Schedule a time event to execute after a delay.
        
        Args:
            delay_seconds: How long to wait before executing
            callback: Async function to call when event fires
            event_id: Optional unique ID (auto-generated if None)
            recurring: If True, reschedule with same delay after execution
        
        Returns:
            The event_id (for cancellation)
        """
        # Import here to avoid circular imports
        from ..world import TimeEvent
        
        if event_id is None:
            event_id = str(uuid.uuid4())
        
        execute_at = time.time() + delay_seconds
        event = TimeEvent(
            execute_at=execute_at,
            callback=callback,
            event_id=event_id,
            recurring=recurring,
            interval=delay_seconds if recurring else 0.0,
        )
        
        heapq.heappush(self._events, event)
        self._event_ids[event_id] = event
        
        print(f"[TimeManager] Scheduled event {event_id} for {delay_seconds:.2f}s (recurring={recurring})")
        return event_id
    
    def cancel(self, event_id: str) -> bool:
        """
        Cancel a scheduled time event.
        
        Args:
            event_id: The ID of the event to cancel
        
        Returns:
            True if event was found and cancelled, False otherwise
        """
        event = self._event_ids.pop(event_id, None)
        if event is None:
            return False
        
        # Mark as non-recurring so it won't reschedule
        event.recurring = False
        
        # We can't efficiently remove from heap, but it will be skipped
        # when popped since it's no longer in _event_ids
        print(f"[TimeManager] Cancelled event {event_id}")
        return True
    
    def has_event(self, event_id: str) -> bool:
        """Check if an event is scheduled."""
        return event_id in self._event_ids
    
    @property
    def pending_count(self) -> int:
        """Number of events currently scheduled."""
        return len(self._event_ids)
    
    # ---------- Internal Loop ----------
    
    async def _run_loop(self) -> None:
        """
        Core time event processing loop.
        
        Continuously checks for due events and executes them.
        Sleeps dynamically based on next event time to minimize CPU usage.
        """
        print("[TimeManager] Loop started")
        
        while True:
            now = time.time()
            
            # Execute all due events
            while self._events and self._events[0].execute_at <= now:
                event = heapq.heappop(self._events)
                
                # Skip if cancelled (removed from _event_ids but still in heap)
                if event.event_id not in self._event_ids:
                    continue
                
                # Remove from ID lookup
                self._event_ids.pop(event.event_id, None)
                
                try:
                    await event.callback()
                    # Only log non-combat events to reduce spam
                    if not event.event_id.startswith("combat_"):
                        print(f"[TimeManager] Executed event {event.event_id}")
                except Exception as e:
                    print(f"[TimeManager] Error executing event {event.event_id}: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Reschedule if recurring
                if event.recurring and event.interval > 0:
                    event.execute_at = time.time() + event.interval
                    heapq.heappush(self._events, event)
                    self._event_ids[event.event_id] = event
                    print(f"[TimeManager] Rescheduled recurring event {event.event_id} for {event.interval:.2f}s")
            
            # Calculate sleep duration until next event
            if self._events:
                next_event_time = self._events[0].execute_at
                sleep_duration = min(1.0, max(0.01, next_event_time - time.time()))
            else:
                # No events scheduled, check every second
                sleep_duration = 1.0
            
            await asyncio.sleep(sleep_duration)
