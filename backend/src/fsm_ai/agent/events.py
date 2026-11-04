"""What an agent turn yields: SSE-shaped events for the UI, then the messages to persist."""

from dataclasses import dataclass
from typing import Any, Literal

from fsm_ai.persistence.messages import NewMessage

EventName = Literal["text_delta", "tool_call", "tool_result", "rule_proposal", "error"]


@dataclass(frozen=True)
class StreamEvent:
    name: EventName
    data: dict[str, Any]


@dataclass(frozen=True)
class TurnFinished:
    """Always the last item of a turn: the assistant and tool messages to store."""

    messages: list[NewMessage]


AgentEvent = StreamEvent | TurnFinished
