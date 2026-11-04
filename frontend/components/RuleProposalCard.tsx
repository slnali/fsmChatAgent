"use client";

import { useState } from "react";

import { createRule } from "@/lib/api";
import type { RuleProposal, SavedRule } from "@/lib/types";

type Props = { chatId: string; proposal: RuleProposal; onSaved: (rule: SavedRule) => void };
type Status = { state: "idle" | "saving" | "saved" } | { state: "error"; message: string };

export function formatRate(rate: number | null): string {
  return rate === null ? "n/a" : `${(rate * 100).toFixed(2)}%`;
}

export function RuleProposalCard({ chatId, proposal, onSaved }: Props) {
  const [status, setStatus] = useState<Status>({ state: "idle" });

  const save = async () => {
    setStatus({ state: "saving" });
    try {
      const rule = await createRule({
        chat_id: chatId,
        name: proposal.name,
        where_clause: proposal.where_clause,
        rationale: proposal.rationale,
      });
      setStatus({ state: "saved" });
      onSaved(rule);
    } catch (error) {
      setStatus({ state: "error", message: (error as Error).message });
    }
  };

  return (
    <section
      aria-label={`Rule proposal: ${proposal.name}`}
      className="my-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm dark:border-amber-700 dark:bg-amber-950/40"
    >
      <div className="mb-2 flex items-center justify-between gap-3">
        <h3 className="font-semibold">Proposed rule: {proposal.name}</h3>
        <span className="text-xs uppercase tracking-wide text-muted-foreground">not saved yet</span>
      </div>
      <pre className="mb-3 overflow-x-auto rounded bg-background p-2 font-mono text-xs">
        WHERE {proposal.where_clause}
      </pre>
      <dl className="mb-3 grid grid-cols-3 gap-2">
        <Metric label="Matched transactions" value={proposal.matched_count.toLocaleString("en-US")} />
        <Metric label="Fraud (labelled)" value={proposal.fraud_count.toLocaleString("en-US")} />
        <Metric label="Fraud rate" value={formatRate(proposal.fraud_rate)} />
      </dl>
      {proposal.rationale && <p className="mb-3 text-muted-foreground">{proposal.rationale}</p>}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={status.state === "saving" || status.state === "saved"}
          className="rounded-md bg-primary px-3 py-1.5 font-medium text-primary-foreground disabled:opacity-50"
        >
          {status.state === "saved" ? "Rule created" : status.state === "saving" ? "Saving…" : "Create rule"}
        </button>
        {status.state === "error" && (
          <span role="alert" className="text-red-600">
            {status.message}
          </span>
        )}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-background p-2">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-mono text-base font-semibold">{value}</dd>
    </div>
  );
}
