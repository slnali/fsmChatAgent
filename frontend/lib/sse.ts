import type { StreamEvent } from "./types";

const KNOWN_EVENTS = new Set([
  "text_delta",
  "tool_call",
  "tool_result",
  "rule_proposal",
  "error",
  "done",
]);

/** Parses complete SSE events out of a buffer; returns the incomplete remainder. */
export function parseSseChunk(buffer: string): { events: StreamEvent[]; rest: string } {
  const blocks = buffer.split(/\r?\n\r?\n/);
  const rest = blocks.pop() ?? "";
  const events: StreamEvent[] = [];

  for (const block of blocks) {
    let name = "";
    const data: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("event:")) name = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
    }
    if (KNOWN_EVENTS.has(name) && data.length > 0) {
      events.push({ event: name, data: JSON.parse(data.join("\n")) } as StreamEvent);
    }
  }
  return { events, rest };
}
