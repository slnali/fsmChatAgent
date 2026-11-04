"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useChatStream } from "@/hooks/useChatStream";
import { createChat, getChat } from "@/lib/api";
import { turnsFromMessages } from "@/lib/turns";
import type { SavedRule } from "@/lib/types";

import { ChatThread } from "./ChatThread";
import { Composer } from "./Composer";
import { RulesPanel } from "./RulesPanel";

/** One chat per URL (?chat=<id>): created when absent, rehydrated from the backend on refresh. */
export function ChatApp() {
  const chatParam = useSearchParams().get("chat");
  const [chatId, setChatId] = useState<string | null>(null);
  const [rules, setRules] = useState<SavedRule[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const { turns, setTurns, streaming, send } = useChatStream(chatId);

  // Which chat has been loaded; stops dev double-effects (and our own URL update) reloading it.
  const loaded = useRef<string | null>(null);

  useEffect(() => {
    const key = chatParam ?? "new";
    if (loaded.current === key) return;
    loaded.current = key;

    const load = async () => {
      try {
        if (chatParam) {
          const chat = await getChat(chatParam);
          setTurns(turnsFromMessages(chat.messages));
          setRules(chat.rules);
          setChatId(chat.id);
        } else {
          const id = await createChat();
          loaded.current = id;
          window.history.replaceState(null, "", `?chat=${id}`);
          setChatId(id);
        }
      } catch (error) {
        setLoadError((error as Error).message);
      }
    };
    load();
  }, [chatParam, setTurns]);

  const startNewChat = () => {
    window.location.assign(window.location.pathname);
  };

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-baseline gap-3">
          <h1 className="text-lg font-bold tracking-tight">
            fsm<span className="text-amber-600">.ai</span>
          </h1>
          <span className="text-xs text-muted-foreground">Fraud data assistant · read-only</span>
        </div>
        <button
          type="button"
          onClick={startNewChat}
          className="rounded-md border border-border px-3 py-1 text-sm hover:bg-muted"
        >
          New chat
        </button>
      </header>
      <div className="flex min-h-0 flex-1">
        <main className="flex min-w-0 flex-1 flex-col">
          {loadError ? (
            <p role="alert" className="m-6 text-sm text-red-600">
              Could not reach the backend: {loadError}
            </p>
          ) : chatId ? (
            <ChatThread
              chatId={chatId}
              turns={turns}
              onAsk={send}
              onRuleSaved={(rule) => setRules((current) => [...current, rule])}
            />
          ) : (
            <p className="m-6 text-sm text-muted-foreground">Loading…</p>
          )}
          <Composer disabled={!chatId || streaming} onSend={send} />
        </main>
        <RulesPanel rules={rules} />
      </div>
    </div>
  );
}
