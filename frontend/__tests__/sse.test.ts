import { describe, expect, it } from "vitest";

import { parseSseChunk } from "@/lib/sse";

describe("parseSseChunk", () => {
  it("parses a single event", () => {
    const { events, rest } = parseSseChunk('event: text_delta\r\ndata: {"text":"Hi"}\r\n\r\n');

    expect(events).toEqual([{ event: "text_delta", data: { text: "Hi" } }]);
    expect(rest).toBe("");
  });

  it("parses several events in one chunk", () => {
    const chunk =
      'event: tool_call\ndata: {"id":"1","sql":"SELECT 1","purpose":"p"}\n\n' +
      'event: done\ndata: {"message_id":7}\n\n';

    expect(parseSseChunk(chunk).events.map((e) => e.event)).toEqual(["tool_call", "done"]);
  });

  it("keeps an event split across chunks until it is complete", () => {
    const first = parseSseChunk('event: text_delta\ndata: {"te');
    expect(first.events).toEqual([]);

    const second = parseSseChunk(first.rest + 'xt":"lo"}\n\n');
    expect(second.events).toEqual([{ event: "text_delta", data: { text: "lo" } }]);
  });

  it("ignores unknown events and comments", () => {
    const { events } = parseSseChunk(': ping\n\nevent: mystery\ndata: {}\n\n');

    expect(events).toEqual([]);
  });
});
