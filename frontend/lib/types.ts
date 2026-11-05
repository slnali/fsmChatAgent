// Mirrors the backend contracts (REST endpoints + SSE events).

export type ToolCall = { id: string; sql: string; purpose: string };

export type ToolResult = {
  id: string;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
  error?: string | null;
};

export type RuleProposal = {
  name: string;
  where_clause: string;
  rationale: string;
  matched_count: number;
  labelled_count?: number;
  fraud_count: number;
  fraud_rate: number | null;
};

export type StreamEvent =
  | { event: "text_delta"; data: { text: string } }
  | { event: "tool_call"; data: ToolCall }
  | { event: "tool_result"; data: ToolResult }
  | { event: "rule_proposal"; data: RuleProposal }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: { message_id: number | null } };

export type SavedRule = {
  id: number;
  chat_id: string;
  name: string;
  where_clause: string;
  rationale: string;
  matched_count: number;
  fraud_count: number;
  fraud_rate: number | null;
  created_at: string;
};

type StoredToolCall = { id: string; name: string; args: Record<string, unknown> };

export type StoredMessage =
  | { id: number; role: "user"; content: { text: string } }
  | { id: number; role: "assistant"; content: { text: string; tool_calls: StoredToolCall[] } }
  | {
      id: number;
      role: "tool";
      content: { tool_call_id: string; name: string; result: Record<string, unknown> };
    };

export type Chat = {
  id: string;
  title: string | null;
  messages: StoredMessage[];
  rules: SavedRule[];
};

/** One query the agent ran: shown collapsed, on demand. */
export type QueryStep = ToolCall & { result?: ToolResult };

export type Turn = {
  id: string;
  question: string;
  markdown: string; // the agent's answer text only
  queries: QueryStep[];
  proposals: RuleProposal[];
  streaming: boolean;
};
