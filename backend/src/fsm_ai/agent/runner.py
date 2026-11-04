"""The agent loop: stream the model's reply, run its tool calls, repeat until it answers."""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage, SystemMessage, ToolMessage

from fsm_ai.agent.events import AgentEvent, StreamEvent, TurnFinished
from fsm_ai.agent.history import to_langchain_messages
from fsm_ai.agent.tools import RUN_SQL, TOOL_SPECS, AgentTools
from fsm_ai.context.system_prompt import PROMPT_VERSION
from fsm_ai.persistence.messages import NewMessage

logger = logging.getLogger(__name__)


class AgentRunner(Protocol):
    def run_turn(self, history: Sequence[dict[str, Any]]) -> AsyncIterator[AgentEvent]:
        """Runs one turn for the stored history (ending with the new user message)."""
        ...


class LangChainAgentRunner:
    def __init__(
        self,
        llm: BaseChatModel,
        tools: AgentTools,
        system_prompt: str,
        model_name: str,
        max_steps: int = 12,
    ) -> None:
        self._llm = llm.bind_tools(TOOL_SPECS)
        self._tools = tools
        self._system_prompt = system_prompt
        self._model_name = model_name
        self._max_steps = max_steps

    async def run_turn(self, history: Sequence[dict[str, Any]]) -> AsyncIterator[AgentEvent]:
        messages: list[BaseMessage] = [
            SystemMessage(content=self._system_prompt),
            *to_langchain_messages(list(history)),
        ]
        new_messages: list[NewMessage] = []
        try:
            for _ in range(self._max_steps):
                started = time.monotonic()
                reply: AIMessageChunk | None = None
                async for chunk in self._llm.astream(messages):
                    assert isinstance(chunk, AIMessageChunk)
                    if chunk.text:
                        yield StreamEvent("text_delta", {"text": chunk.text})
                    reply = chunk if reply is None else reply + chunk
                if reply is None:
                    raise RuntimeError("The model returned an empty response.")

                assistant = self._assistant_message(reply, started)
                new_messages.append(assistant)
                messages.extend(to_langchain_messages([_as_row(assistant)]))
                if not reply.tool_calls:
                    break

                for call in reply.tool_calls:
                    call_id, name, args = str(call["id"]), call["name"], call["args"]
                    if name == RUN_SQL:
                        yield StreamEvent(
                            "tool_call",
                            {
                                "id": call_id,
                                "sql": args.get("sql", ""),
                                "purpose": args.get("purpose", ""),
                            },
                        )
                    outcome = await asyncio.to_thread(self._tools.execute, call_id, name, args)
                    for event in outcome.events:
                        yield event
                    new_messages.append(
                        NewMessage(
                            role="tool",
                            content={
                                "tool_call_id": call_id,
                                "name": name,
                                "result": outcome.result,
                            },
                        )
                    )
                    messages.append(
                        ToolMessage(
                            content=json.dumps(outcome.result, default=str), tool_call_id=call_id
                        )
                    )
            else:
                yield StreamEvent(
                    "error",
                    {"message": f"Stopped after {self._max_steps} steps without an answer."},
                )
        except Exception as error:  # surface any model/tool failure to the FSM, keep the audit
            logger.exception("Agent turn failed")
            yield StreamEvent("error", {"message": f"The agent failed: {error}"})

        yield TurnFinished(messages=new_messages)

    def _assistant_message(self, reply: AIMessageChunk, started: float) -> NewMessage:
        usage = reply.usage_metadata or {}
        return NewMessage(
            role="assistant",
            content={
                "text": reply.text,
                "tool_calls": [
                    {"id": call["id"], "name": call["name"], "args": call["args"]}
                    for call in reply.tool_calls
                ],
            },
            metadata={
                "model": self._model_name,
                "prompt_version": PROMPT_VERSION,
                "latency_ms": round((time.monotonic() - started) * 1000),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            },
        )


def _as_row(message: NewMessage) -> dict[str, Any]:
    return {"role": message.role, "content": message.content}
