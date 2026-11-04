import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse

from fsm_ai.api.dependencies import get_services
from fsm_ai.api.sse import stream_turn
from fsm_ai.persistence.messages import NewMessage
from fsm_ai.services import Services

router = APIRouter(prefix="/chats", tags=["chats"])
ServicesDep = Annotated[Services, Depends(get_services)]


class SendMessage(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


@router.post("", status_code=201)
def create_chat(services: ServicesDep) -> dict[str, UUID]:
    return {"id": services.chats.create()}


@router.get("/{chat_id}")
def get_chat(chat_id: UUID, services: ServicesDep) -> dict[str, Any]:
    chat = services.chats.get(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {
        "id": chat["id"],
        "title": chat["title"],
        "messages": services.messages.list_for_chat(chat_id),
        "rules": services.rules.list_for_chat(chat_id),
    }


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: UUID, body: SendMessage, services: ServicesDep
) -> EventSourceResponse:
    if await asyncio.to_thread(services.chats.get, chat_id) is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    await asyncio.to_thread(
        services.messages.add, chat_id, NewMessage(role="user", content={"text": body.content})
    )
    await asyncio.to_thread(services.chats.set_title_if_missing, chat_id, body.content)
    history = await asyncio.to_thread(services.messages.list_for_chat, chat_id)
    return EventSourceResponse(stream_turn(services, chat_id, history))
