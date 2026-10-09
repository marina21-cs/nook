"""Bounded, ephemeral chat guidance backed by deterministic saved-item recall."""

import asyncio
import re
import time
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, field_validator

from app.chat_context import Context
from app.contracts import ApiUUID, Contract, Query, Recall, RecallResult
from app.errors import AppError

router = APIRouter(prefix="/api/chat")

ChatKind = Literal["greeting", "help", "memory", "unknown", "clarify", "unsupported", "generated"]


class Chat(Contract):
    query: Query
    request_id: ApiUUID
    context_id: ApiUUID | None = None

    @field_validator("query")
    @classmethod
    def query_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 4096:
            raise ValueError("Query exceeds the byte limit")
        return value


class ResetChat(Contract):
    request_id: ApiUUID
    context_id: ApiUUID


class ChatResult(BaseModel):
    kind: ChatKind
    request_id: str
    generation: int
    recall: RecallResult | None = None
    reply_text: str | None = None
    general_conversation_available: bool = False
    inference_used: bool = False
    persisted: Literal[False] = False
    context_id: str | None = None
    context_expires_in_seconds: int | None = None
    reply_authority: Literal["bounded_guidance", "saved_records", "generated_unverified"] = (
        "bounded_guidance"
    )


_GREETING = re.compile(r"(?:hey|hi|hello|kamusta|kumusta)(?:,? nook)?[.!?]{0,3}")
_HELP = {
    "help",
    "help me",
    "what can you do",
    "how can you help",
    "how do i use nook",
}
_THANKS = {"thanks", "thank you", "salamat"}
# Only whole phrases or anchored question/instruction forms are classified here.
# This runs after recall so confirmed personal names and aliases still take priority.
_GENERAL_QUESTION = re.compile(
    r"(?:"
    r"(?:what|who) (?:is|are|was|were|does|do|can|should) .+|"
    r"what's .+|who's .+|"
    r"why .+|how (?:is|are|do|does|did|can|could|should|to) .+|"
    r"(?:can|could|would) you (?:write|explain|translate|generate|summarize|tell) .+|"
    r"(?:write|explain|translate|generate|summarize) .+|"
    r"tell me (?:a joke(?: about .+)?|a story(?: about .+)?|about .+)"
    r")[.!?]{0,3}"
)
_HELP_REPLY = (
    "I can help you find your saved belongings. Ask an item's name, or try "
    "'Where are my keys?' Use Remember to save an item and its last recorded location. "
    "General conversation isn't supported yet."
)
_UNSUPPORTED_REPLY = (
    "I can help you find saved belongings and their last recorded locations. "
    "General questions aren't supported yet. Try an item's saved name, "
    "or use Remember to save it first."
)

# Conservative syntax guards, not a semantic personal-intent classifier. Unknown
# novel/implicit personal wording may reach generation; every generated result is
# labeled unverified and no generated text can enter the saved-records channel.
_PERSONAL = re.compile(
    r"\b(?:my|mine|our|saved|belongings|remembered|recorded)\b|"
    r"^(?:where\b|nasaan\b|nasan\b|saan\s+ko\b)",
    re.IGNORECASE,
)
_ITEM_PRONOUN = re.compile(
    r"(?:(?:and|then)\s+)?(?:where\s+(?:is|are|was|were)\s+(?:it|they|that|them)|"
    r"what\s+about\s+(?:it|them)|its\s+(?:location|last\s+recorded\s+location))\s*[.!?]{0,3}"
)


def _normalized(query: str) -> str:
    return " ".join(query.casefold().split())


def _small_reply(query: str) -> tuple[ChatKind, str] | None:
    if _GREETING.fullmatch(query):
        return "greeting", (
            "Hi! I'm Nook. I can help you find your saved belongings. "
            "Try 'Where are my keys?' or use Remember to save an item."
        )
    phrase = re.sub(r"[.!?]{1,3}$", "", query)
    if phrase in _HELP:
        return "help", _HELP_REPLY
    if phrase in _THANKS:
        return "greeting", "You're welcome! Ask me about a saved item whenever you need it."
    return None


def _memory_result(memory: RecallResult, enabled: bool, query: str) -> ChatResult:
    kind: ChatKind = "memory" if memory.kind == "found" else memory.kind
    reply = None
    if memory.kind == "clarify":
        reply = "Several saved items match. Choose the item you mean."
    elif memory.kind == "unknown":
        if memory.items:
            reply = "I found the saved item, but its recorded location is unknown."
        elif not enabled and (
            memory.reason == "unsupported_query" or _GENERAL_QUESTION.fullmatch(query)
        ):
            kind, reply = "unsupported", _UNSUPPORTED_REPLY
        else:
            reply = "I don't have a saved match. Try the item's saved name or alias, or use Remember to save it first."
    return ChatResult(
        kind=kind,
        request_id=memory.request_id,
        generation=memory.generation,
        recall=memory,
        reply_text=reply,
        general_conversation_available=enabled,
        reply_authority="saved_records",
    )


async def _turn(
    body: Chat, state, cancelled: asyncio.Event, generation: int, context: Context | None
) -> ChatResult:
    query = _normalized(body.query)
    enabled = state.settings.chat_enabled
    small = _small_reply(query)
    # Preserve the disabled greeting fallback without a provider or recall call.
    if small is not None and not enabled:
        return ChatResult(
            kind=small[0],
            request_id=str(body.request_id),
            generation=generation,
            reply_text=small[1],
        )
    raw = await state.recall.recall(
        Recall(query=body.query, request_id=body.request_id, use_inference=False),
        cancelled,
        generation,
    )
    memory = RecallResult.model_validate(raw)
    # A complete confirmed name/alias, including greeting/question shaped names,
    # takes precedence over small talk, pronouns and generated conversation.
    if memory.items:
        return _memory_result(memory, enabled, query)
    if enabled and _ITEM_PRONOUN.fullmatch(query):
        if context is not None and context.subject is not None:
            try:
                item = await asyncio.to_thread(state.repo.get, context.subject)
            except AppError as exc:
                if exc.status != 404:
                    raise
            else:
                memory = RecallResult.model_validate(
                    {
                        **memory.model_dump(),
                        "kind": "found" if item["location"] is not None else "unknown",
                        "reason": "last_recorded_evidence"
                        if item["location"] is not None
                        else "location_unknown",
                        "items": [item],
                        "total": 1,
                    }
                )
                return _memory_result(memory, enabled, query)
        return ChatResult(
            kind="clarify",
            request_id=str(body.request_id),
            generation=generation,
            reply_text="Which saved item do you mean? Ask its saved name or alias.",
            general_conversation_available=True,
        )
    if small is not None and small[0] == "help":
        text = small[1]
        if small[0] == "help":
            text = "I can find saved belongings or offer generated, unverified general conversation. Use Remember and confirm to save an item. Recent conversation expires after five minutes."
        return ChatResult(
            kind=small[0],
            request_id=str(body.request_id),
            generation=generation,
            reply_text=text,
            general_conversation_available=enabled,
        )
    if not enabled or _PERSONAL.search(query):
        return _memory_result(memory, enabled, query)
    assert context is not None
    if not context.history and small is None and not _GENERAL_QUESTION.fullmatch(query):
        # A bare unknown label remains a lookup until an explicit general prompt
        # establishes conversation. This is conservative syntax, not semantics.
        return _memory_result(memory, enabled, query)
    reply = await state.chat_provider.generate(
        state.chat_contexts.messages(context, body.query), cancelled
    )
    return ChatResult(
        kind="generated",
        request_id=str(body.request_id),
        generation=generation,
        reply_text="Generated, unverified: " + reply,
        general_conversation_available=True,
        inference_used=True,
        reply_authority="generated_unverified",
    )


@router.post("", response_model=ChatResult)
async def chat(body: Chat, request: Request) -> ChatResult:
    state = request.app.state
    owner = request.state.session_owner
    async with state.requests.begin(str(body.request_id), owner=owner) as cancelled:
        generation = await asyncio.to_thread(state.repo.generation)
        context = None
        if state.settings.chat_enabled:
            context = state.chat_contexts.obtain(
                owner, str(body.context_id) if body.context_id else None, generation
            )
        elif body.context_id is not None:
            raise AppError(409, "chat_context_unavailable", "General conversation is disabled.")
        if context is not None and context.busy.locked():
            raise AppError(
                409, "chat_context_busy", "A turn in this conversation is already active."
            )

        async def run() -> ChatResult:
            result = await _turn(body, state, cancelled, generation, context)

            def publish() -> None:
                # Generation check and context commit share the database writer lock.
                with state.repo.db.lock, state.repo.db.connect() as conn:
                    if cancelled.is_set():
                        raise AppError(
                            409, "request_cancelled", "Chat cancelled; its result was discarded."
                        )
                    if state.repo.db.generation(conn) != generation:
                        state.chat_contexts.clear()
                        raise AppError(
                            409, "stale_request", "Collection changed. Retry with a new request ID."
                        )
                    if context is not None:
                        with state.chat_contexts.lock:
                            state.chat_contexts.validate(context, cancelled)
                            if result.kind == "generated":
                                assert result.reply_text is not None
                                context.subject = None
                                state.chat_contexts.remember(
                                    context,
                                    body.query,
                                    result.reply_text.removeprefix("Generated, unverified: "),
                                )
                            elif result.recall is not None:
                                context.subject = (
                                    result.recall.items[0].id
                                    if result.recall.total == 1 and result.recall.items
                                    else None
                                )
                            result.context_id = context.id
                            result.context_expires_in_seconds = max(
                                0, int(context.expires - time.monotonic())
                            )

            try:
                await asyncio.to_thread(publish)
                if cancelled.is_set():
                    raise AppError(
                        409, "request_cancelled", "Chat cancelled; its result was discarded."
                    )
                if context is not None:
                    state.chat_contexts.validate(context, cancelled)
            except BaseException:
                if context is not None:
                    with state.chat_contexts.lock:
                        state.chat_contexts._drop(context)
                raise
            return result

        if context is None:
            return await run()
        async with context.busy:
            context.active = cancelled
            try:
                state.chat_contexts.validate(context, cancelled)
                return await run()
            except asyncio.CancelledError:
                with state.chat_contexts.lock:
                    state.chat_contexts._drop(context)
                raise
            finally:
                context.active = None
                if cancelled.is_set():
                    with state.chat_contexts.lock:
                        state.chat_contexts._drop(context)


@router.delete("")
async def reset_chat(body: ResetChat, request: Request) -> dict:
    state = request.app.state
    owner = request.state.session_owner
    async with state.requests.begin(str(body.request_id), owner=owner):
        state.chat_contexts.reset(owner, str(body.context_id))
    return {"reset": True, "persisted": False}
