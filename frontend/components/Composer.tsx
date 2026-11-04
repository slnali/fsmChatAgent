"use client";

import { useState } from "react";

type Props = { disabled: boolean; onSend: (question: string) => void };

export function Composer({ disabled, onSend }: Props) {
  const [text, setText] = useState("");

  const submit = () => {
    const question = text.trim();
    if (!question || disabled) return;
    onSend(question);
    setText("");
  };

  return (
    <form
      className="flex gap-2 border-t border-border bg-background p-3"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <textarea
        aria-label="Ask a question"
        className="min-h-11 flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
        placeholder="Ask about the transaction data… (Enter to send, Shift+Enter for a new line)"
        rows={2}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground disabled:opacity-40"
      >
        {disabled ? "Thinking…" : "Send"}
      </button>
    </form>
  );
}
