"""Turns an agent turn into SSE events, persisting the turn's messages before `done`."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fsm_ai.agent.events import StreamEvent, TurnFinished
from fsm_ai.services import Services


def sse(name: str, data: dict[str, Any]) -> dict[str, str]:
    return {"event": name, "data": json.dumps(data, default=str)}


async def stream_turn(
    services: Services, chat_id: UUID, history: list[dict[str, Any]]
) -> AsyncIterator[dict[str, str]]:
    async for event in services.agent.run_turn(history):
        if isinstance(event, StreamEvent):
            yield sse(event.name, event.data)
        elif isinstance(event, TurnFinished):
            message_id = None
            if event.messages:
                ids = await asyncio.to_thread(services.messages.add_many, chat_id, event.messages)
                message_id = ids[-1]
            yield sse("done", {"message_id": message_id})
