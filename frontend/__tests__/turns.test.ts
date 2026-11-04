import { describe, expect, it } from "vitest";

import { applyEvent, newTurn, turnsFromMessages } from "@/lib/turns";
import type { StoredMessage, StreamEvent } from "@/lib/types";

const proposal = {
  name: "Italy",
  where_clause: "t.x = 1",
  rationale: "r",
  matched_count: 10,
  fraud_count: 8,
  fraud_rate: 0.8,
};

describe("turnsFromMessages", () => {
  it("rebuilds the same turn the live stream produced", () => {
    const live: StreamEvent[] = [
      { event: "text_delta", data: { text: "Checking." } },
      { event: "tool_call", data: { id: "c1", sql: "SELECT 1", purpose: "p" } },
      {
        event: "tool_result",
        data: { id: "c1", columns: ["a"], rows: [[1]], row_count: 1, truncated: false, error: null },
      },
      { event: "rule_proposal", data: proposal },
      { event: "text_delta", data: { text: "Done." } },
      { event: "done", data: { message_id: 5 } },
    ];
    const liveTurn = live.reduce(applyEvent, newTurn("Q?", "x"));

    const stored: StoredMessage[] = [
      { id: 1, role: "user", content: { text: "Q?" } },
      {
        id: 2,
        role: "assistant",
        content: {
          text: "Checking.",
          tool_calls: [{ id: "c1", name: "run_sql", args: { sql: "SELECT 1", purpose: "p" } }],
        },
      },
      {
        id: 3,
        role: "tool",
        content: {
          tool_call_id: "c1",
          name: "run_sql",
          result: { columns: ["a"], rows: [[1]], row_count: 1, truncated: false, error: null },
        },
      },
      {
        id: 4,
        role: "assistant",
        content: { text: "", tool_calls: [{ id: "c2", name: "propose_rule", args: {} }] },
      },
      { id: 5, role: "tool", content: { tool_call_id: "c2", name: "propose_rule", result: proposal } },
      { id: 6, role: "assistant", content: { text: "Done.", tool_calls: [] } },
    ];
    const [rehydrated] = turnsFromMessages(stored);

    expect(rehydrated.markdown).toBe("Checking.\n\nDone.");
    expect(rehydrated.markdown).toBe(liveTurn.markdown);
    expect(rehydrated.queries).toEqual(liveTurn.queries);
    expect(rehydrated.queries[0].result?.rows).toEqual([[1]]);
    expect(rehydrated.proposals).toEqual(liveTurn.proposals);
    expect(rehydrated.streaming).toBe(false);
  });
});
