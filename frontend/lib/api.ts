import type { Chat, SavedRule } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function createChat(): Promise<string> {
  const { id } = await json<{ id: string }>(await fetch(`${API_URL}/chats`, { method: "POST" }));
  return id;
}

export async function getChat(chatId: string): Promise<Chat> {
  return json<Chat>(await fetch(`${API_URL}/chats/${chatId}`));
}

export type NewRule = { chat_id: string; name: string; where_clause: string; rationale: string };

export async function createRule(rule: NewRule): Promise<SavedRule> {
  return json<SavedRule>(
    await fetch(`${API_URL}/rules`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(rule),
    }),
  );
}

export function sendMessage(chatId: string, content: string, signal?: AbortSignal) {
  return fetch(`${API_URL}/chats/${chatId}/messages`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "text/event-stream" },
    body: JSON.stringify({ content }),
    signal,
  });
}
