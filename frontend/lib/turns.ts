// Builds chat turns from live SSE events, and from stored messages after a refresh.
// Both paths go through applyEvent, so a rehydrated chat looks exactly like the live one.
import type { RuleProposal, StoredMessage, StreamEvent, ToolResult, Turn } from "./types";

export function newTurn(question: string, id: string, streaming = true): Turn {
  return { id, question, markdown: "", queries: [], proposals: [], streaming };
}

export function applyEvent(turn: Turn, { event, data }: StreamEvent): Turn {
  switch (event) {
    case "text_delta":
      return { ...turn, markdown: turn.markdown + data.text };
    case "tool_call":
      // Text from separate agent steps becomes separate paragraphs.
      return {
        ...turn,
        markdown: turn.markdown && !turn.markdown.endsWith("\n") ? `${turn.markdown}\n\n` : turn.markdown,
        queries: [...turn.queries, data],
      };
    case "tool_result":
      return {
        ...turn,
        queries: turn.queries.map((query) => (query.id === data.id ? { ...query, result: data } : query)),
      };
    case "rule_proposal":
      return { ...turn, proposals: [...turn.proposals, data] };
    case "error":
      return { ...turn, markdown: `${turn.markdown}\n\n> **Error:** ${data.message}\n\n` };
    case "done":
      return { ...turn, streaming: false };
  }
}

export function turnsFromMessages(messages: StoredMessage[]): Turn[] {
  const turns: Turn[] = [];
  const pendingCalls = new Map<string, { sql: string; purpose: string }>();
  const apply = (event: StreamEvent) => {
    const last = turns.at(-1);
    if (last) turns[turns.length - 1] = applyEvent(last, event);
  };

  for (const message of messages) {
    if (message.role === "user") {
      turns.push(newTurn(message.content.text, `m${message.id}`, false));
    } else if (message.role === "assistant") {
      if (message.content.text) apply({ event: "text_delta", data: { text: message.content.text } });
      for (const call of message.content.tool_calls) {
        pendingCalls.set(call.id, {
          sql: String(call.args.sql ?? ""),
          purpose: String(call.args.purpose ?? ""),
        });
      }
    } else {
      const { tool_call_id: id, name, result } = message.content;
      if (name === "run_sql") {
        const call = pendingCalls.get(id) ?? { sql: "", purpose: "" };
        apply({ event: "tool_call", data: { id, ...call } });
        apply({ event: "tool_result", data: { id, ...(result as Omit<ToolResult, "id">) } });
      } else if (name === "propose_rule" && !result.error) {
        apply({ event: "rule_proposal", data: result as unknown as RuleProposal });
      }
    }
  }
  return turns;
}
