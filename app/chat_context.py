"""Bounded RAM-only server-owned context. No saved records enter model history."""

import asyncio
import threading
import time
from dataclasses import dataclass, field
from uuid import uuid4

from app.errors import AppError
from app.local_chat import PROMPT_BYTES, SYSTEM

CONTEXT_TTL = 300
MAX_CONTEXTS = 32
MAX_TURNS = 3
HISTORY_BYTES = 6000


@dataclass
class Context:
    id: str
    owner: str
    generation: int
    expires: float
    history: list[tuple[str, str]] = field(default_factory=list)
    subject: str | None = None  # Authoritative item ID, never a generated subject.
    valid: bool = True
    busy: asyncio.Lock = field(default_factory=asyncio.Lock)
    active: asyncio.Event | None = None


class ChatContexts:
    def __init__(self) -> None:
        self.contexts: dict[str, Context] = {}
        self.lock = threading.RLock()
        self.loop = asyncio.get_running_loop()

    def _drop(self, context: Context) -> None:
        context.valid = False
        context.history.clear()
        context.subject = None
        self.contexts.pop(context.id, None)
        if context.active is not None:
            self.loop.call_soon_threadsafe(context.active.set)

    def clear(self) -> None:
        # Called by generation changes under the existing database lock, possibly
        # from a repository worker thread. Publication checks the same lock order.
        with self.lock:
            for context in list(self.contexts.values()):
                self._drop(context)

    def prune(self) -> None:
        with self.lock:
            for context in list(self.contexts.values()):
                if context.expires <= time.monotonic():
                    self._drop(context)

    async def expire(self) -> None:
        while True:
            await asyncio.sleep(1)
            self.prune()

    def obtain(self, owner: str, context_id: str | None, generation: int) -> Context:
        with self.lock:
            self.prune()
            if context_id is not None:
                context = self.contexts.get(context_id)
                if context is None or context.owner != owner or context.generation != generation:
                    raise AppError(
                        409,
                        "chat_context_unavailable",
                        "Context expired or changed. Start a new conversation.",
                    )
                return context
            # One context per authenticated session prevents unlimited abandoned
            # conversations from one cookie. New chat explicitly replaces the old.
            for old in list(self.contexts.values()):
                if old.owner == owner:
                    self._drop(old)
            if len(self.contexts) >= MAX_CONTEXTS:
                raise AppError(
                    503, "chat_context_busy", "Too many recent conversations. Retry later."
                )
            context = Context(str(uuid4()), owner, generation, time.monotonic() + CONTEXT_TTL)
            self.contexts[context.id] = context
            return context

    def reset(self, owner: str, context_id: str) -> None:
        with self.lock:
            self.prune()
            context = self.contexts.get(context_id)
            if context is None or context.owner != owner:
                raise AppError(409, "chat_context_unavailable", "Context is unavailable.")
            self._drop(context)

    def validate(self, context: Context, cancelled: asyncio.Event) -> None:
        with self.lock:
            if cancelled.is_set():
                raise AppError(
                    409, "request_cancelled", "Chat cancelled; its result was discarded."
                )
            if not context.valid or context.expires <= time.monotonic():
                self._drop(context)
                raise AppError(
                    409,
                    "chat_context_unavailable",
                    "Context expired or changed. Start a new conversation.",
                )

    def messages(self, context: Context, query: str) -> list[dict[str, str]]:
        with self.lock:
            # Keep complete recent pairs. Never truncate a system message or splice
            # an incomplete assistant/user turn. Current query is always retained.
            history = list(context.history[-MAX_TURNS * 2 :])
            budget = PROMPT_BYTES - len(SYSTEM.encode("utf-8")) - len(query.encode("utf-8"))
            while history and sum(len(text.encode("utf-8")) for _, text in history) > budget:
                del history[:2]
            return [{"role": role, "content": text} for role, text in history] + [
                {"role": "user", "content": query}
            ]

    def remember(self, context: Context, query: str, reply: str) -> None:
        with self.lock:
            context.history.extend((("user", query), ("assistant", reply)))
            while (
                len(context.history) > MAX_TURNS * 2
                or sum(len(text.encode("utf-8")) for _, text in context.history) > HISTORY_BYTES
            ):
                del context.history[:2]
