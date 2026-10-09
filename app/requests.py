import asyncio
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.errors import AppError


class RequestRegistry:
    def __init__(self) -> None:
        self.active: dict[str, tuple[asyncio.Event, str | None]] = {}
        self.finished: deque[str] = deque(maxlen=1024)
        self.owners: dict[str, str] = {}

    def _finish(self, request_id: str, owner: str | None = None) -> None:
        if len(self.finished) == self.finished.maxlen:
            self.owners.pop(self.finished[0], None)
        self.finished.append(request_id)
        if owner is not None:
            self.owners[request_id] = owner

    @asynccontextmanager
    async def begin(
        self, request_id: str, target: str | None = None, owner: str | None = None
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
        if owner is not None:
            self.owners[request_id] = owner
        try:
            yield stop
        finally:
            self.active.pop(request_id, None)
            self._finish(request_id, owner)

    def cancel(self, request_id: str, owner: str | None = None) -> dict:
        if request_id in self.owners and self.owners[request_id] != owner:
            raise AppError(404, "request_unavailable", "Request is unavailable in this session.")
        entry = self.active.get(request_id)
        if entry:
            entry[0].set()
            return {"cancelled": True, "request_id": request_id}
        if request_id not in self.finished:
            self._finish(request_id, owner)  # Handles Stop racing just before the request starts.
        return {"cancelled": True, "request_id": request_id, "active": False}

    def cancel_target(self, target: str | None = None) -> None:
        for stop, capture in self.active.values():
            if target is None or capture == target:
                stop.set()
