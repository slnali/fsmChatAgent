"""Converts stored chat_messages rows to LangChain messages (the Claude API is stateless)."""

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage


def to_langchain_messages(rows: list[dict[str, Any]]) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for row in rows:
        content = row["content"]
        if row["role"] == "user":
            messages.append(HumanMessage(content=content["text"]))
        elif row["role"] == "assistant":
            messages.append(
                AIMessage(
                    content=content.get("text", ""),
                    tool_calls=[
                        {"id": call["id"], "name": call["name"], "args": call["args"]}
                        for call in content.get("tool_calls", [])
                    ],
                )
            )
        else:
            messages.append(
                ToolMessage(
                    content=json.dumps(content["result"], default=str),
                    tool_call_id=content["tool_call_id"],
                )
            )
    return messages
