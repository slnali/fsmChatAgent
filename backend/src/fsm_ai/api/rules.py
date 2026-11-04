import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from fsm_ai.api.dependencies import get_services
from fsm_ai.data_access.readonly_executor import RuleEvaluationError
from fsm_ai.persistence.rules import NewRule
from fsm_ai.services import Services

router = APIRouter(prefix="/rules", tags=["rules"])
ServicesDep = Annotated[Services, Depends(get_services)]


class CreateRule(BaseModel):
    chat_id: UUID
    name: str = Field(min_length=1, max_length=200)
    where_clause: str = Field(min_length=1, max_length=4000)
    rationale: str = ""


@router.post("", status_code=201)
async def create_rule(body: CreateRule, services: ServicesDep) -> dict[str, Any]:
    """The FSM saves a rule. It is re-validated and re-measured here, never trusted as sent."""
    if await asyncio.to_thread(services.chats.get, body.chat_id) is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    try:
        metrics = await asyncio.to_thread(services.executor.evaluate_rule, body.where_clause)
    except RuleEvaluationError as error:
        raise HTTPException(status_code=422, detail=f"Invalid rule: {error}") from error

    return await asyncio.to_thread(
        services.rules.add,
        NewRule(
            chat_id=body.chat_id,
            name=body.name,
            where_clause=body.where_clause,
            rationale=body.rationale,
            matched_count=metrics.matched_count,
            fraud_count=metrics.fraud_count,
            fraud_rate=metrics.fraud_rate,
        ),
    )
