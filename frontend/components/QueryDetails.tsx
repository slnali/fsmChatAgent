"use client";

import { code } from "@streamdown/code";
import { mermaid } from "@streamdown/mermaid";
import { useState } from "react";
import { Streamdown } from "streamdown";

import { resultToMarkdown, sqlToMarkdown } from "@/lib/markdown";
import type { QueryStep } from "@/lib/types";

const plugins = { code, mermaid };

export function queriesToMarkdown(queries: QueryStep[]): string {
  return queries
    .map((query) => sqlToMarkdown(query) + (query.result ? resultToMarkdown(query.result) : ""))
    .join("\n\n---\n\n");
}

/** The agent's working (SQL, result tables, charts), collapsed until the FSM wants to dig in. */
export function QueryDetails({ queries, streaming }: { queries: QueryStep[]; streaming: boolean }) {
  const [open, setOpen] = useState(false);
  if (queries.length === 0) return null;

  const running = streaming && queries.some((query) => !query.result);
  const label = `${queries.length} ${queries.length === 1 ? "query" : "queries"}`;

  return (
    <div className="mt-2 text-xs">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
      >
        {open ? "▾" : "▸"} {open ? "Hide" : "Show"} {label} and results
        {running && ` · running: ${queries.at(-1)?.purpose}`}
      </button>
      {open && (
        <div className="mt-2 rounded-md border border-border bg-muted/30 p-3 text-sm">
          <Streamdown
            plugins={plugins}
            isAnimating={streaming}
            parseIncompleteMarkdown
            controls={{ table: true, code: true, mermaid: { fullscreen: true } }}
          >
            {queriesToMarkdown(queries)}
          </Streamdown>
        </div>
      )}
    </div>
  );
}
