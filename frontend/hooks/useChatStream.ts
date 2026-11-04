"use client";

import { useCallback, useRef, useState } from "react";

import { sendMessage } from "@/lib/api";
import { parseSseChunk } from "@/lib/sse";
import { applyEvent, newTurn } from "@/lib/turns";
import type { StreamEvent, Turn } from "@/lib/types";

/** Sends a question and streams the agent's turn (POST + ReadableStream, not EventSource). */
export function useChatStream(chatId: string | null) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [streaming, setStreaming] = useState(false);
  const counter = useRef(0);

  const updateLastTurn = useCallback((event: StreamEvent) => {
    setTurns((current) => {
      const last = current.at(-1);
      return last ? [...current.slice(0, -1), applyEvent(last, event)] : current;
    });
  }, []);

  const send = useCallback(
    async (question: string) => {
      if (!chatId || streaming) return;
      setStreaming(true);
      setTurns((current) => [...current, newTurn(question, `live-${counter.current++}`)]);

      try {
        const response = await sendMessage(chatId, question);
        if (!response.ok || !response.body) throw new Error(`Request failed (${response.status})`);

        const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
        let buffer = "";
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          const { events, rest } = parseSseChunk(buffer + value);
          buffer = rest;
          events.forEach(updateLastTurn);
        }
      } catch (error) {
        updateLastTurn({ event: "error", data: { message: (error as Error).message } });
      } finally {
        updateLastTurn({ event: "done", data: { message_id: null } });
        setStreaming(false);
      }
    },
    [chatId, streaming, updateLastTurn],
  );

  return { turns, setTurns, streaming, send };
}
