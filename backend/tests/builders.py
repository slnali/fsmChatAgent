"""Shared test builders: a scripted chat model and SSE helpers."""

import json
import re
from collections.abc import Iterator
from typing import Any

import psycopg
from fastapi.testclient import TestClient
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field

from fsm_ai.agent.tools import PROPOSE_RULE, RUN_SQL


class ScriptedChatModel(BaseChatModel):
    """Replays scripted AI replies in order and records what the model was sent."""

    replies: list[AIMessage]
    received: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":  # type: ignore[override]
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next_reply(messages))])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        reply = self._next_reply(messages)
        for token in re.split(r"(\s)", str(reply.content)):
            if token:
                yield ChatGenerationChunk(message=AIMessageChunk(content=token))
        yield ChatGenerationChunk(
            message=AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {
                        "id": call["id"],
                        "name": call["name"],
                        "args": json.dumps(call["args"]),
                        "index": index,
                        "type": "tool_call_chunk",
                    }
                    for index, call in enumerate(reply.tool_calls)
                ],
                usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
            )
        )

    def _next_reply(self, messages: list[BaseMessage]) -> AIMessage:
        self.received.append(list(messages))
        return self.replies.pop(0)


def text_reply(text: str) -> AIMessage:
    return AIMessage(content=text)


def run_sql_reply(
    sql: str, purpose: str = "Check the data", call_id: str = "call_sql"
) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"id": call_id, "name": RUN_SQL, "args": {"sql": sql, "purpose": purpose}}],
    )


def propose_rule_reply(
    where_clause: str, name: str = "Italy", rationale: str = "Fraud concentrates in Italy"
) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "id": "call_rule",
                "name": PROPOSE_RULE,
                "args": {"name": name, "where_clause": where_clause, "rationale": rationale},
            }
        ],
    )


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in re.split(r"\r?\n\r?\n", body.strip()):
        fields = dict(line.split(": ", 1) for line in re.split(r"\r?\n", block) if ": " in line)
        if "event" in fields:
            events.append((fields["event"], json.loads(fields.get("data", "{}"))))
    return events


def send_message(
    client: TestClient, chat_id: str, content: str
) -> list[tuple[str, dict[str, Any]]]:
    response = client.post(f"/chats/{chat_id}/messages", json={"content": content})
    assert response.status_code == 200, response.text
    return parse_sse(response.text)


def event_names(events: list[tuple[str, dict[str, Any]]]) -> list[str]:
    """Event names with consecutive text_delta events collapsed into one."""
    names: list[str] = []
    for name, _ in events:
        if not (name == "text_delta" and names and names[-1] == "text_delta"):
            names.append(name)
    return names


def events_named(events: list[tuple[str, dict[str, Any]]], name: str) -> list[dict[str, Any]]:
    return [data for event, data in events if event == name]


DATA_TABLES = [
    "users",
    "mcc_codes",
    "merchants",
    "merchant_locations",
    "cards",
    "fraud_labels",
    "transactions",
]


def data_row_counts(owner_url: str) -> dict[str, int]:
    with psycopg.connect(owner_url) as conn:
        counts: dict[str, int] = {}
        for table in DATA_TABLES:
            row = conn.execute(f"SELECT COUNT(*) FROM data.{table}".encode()).fetchone()
            counts[table] = row[0] if row else 0
        return counts
