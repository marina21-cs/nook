import asyncio
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.errors import AppError


class RequestRegistry:
    def __init__(self) -> None:
        self.active: dict[str, tuple[asyncio.Event, str | None]] = {}
        self.finished: deque[str] = deque(maxlen=1024)

    @asynccontextmanager
    async def begin(
        self, request_id: str, target: str | None = None
    ) -> AsyncIterator[asyncio.Event]:
        if request_id in self.active or request_id in self.finished:
            raise AppError(
                409, "request_id_reused", "Use a new UUID for each search or photo check."
            )
        if len(self.active) >= 4:
            raise AppError(
                503, "request_busy", "Too many active inference requests. Retry shortly."
            )
        stop = asyncio.Event()
        self.active[request_id] = (stop, target)
        try:
            yield stop
        finally:
            self.active.pop(request_id, None)
            self.finished.append(request_id)

    def cancel(self, request_id: str) -> dict:
        entry = self.active.get(request_id)
        if entry:
            entry[0].set()
            return {"cancelled": True, "request_id": request_id}
        if request_id not in self.finished:
            self.finished.append(request_id)  # Handles Stop racing just before the request starts.
        return {"cancelled": True, "request_id": request_id, "active": False}

    def cancel_target(self, target: str | None = None) -> None:
        for stop, capture in self.active.values():
            if target is None or capture == target:
                stop.set()
