import type { SavedRule } from "@/lib/types";

import { formatRate } from "./RuleProposalCard";

export function RulesPanel({ rules }: { rules: SavedRule[] }) {
  return (
    <aside className="hidden w-80 shrink-0 overflow-y-auto border-l border-border bg-muted/40 p-4 lg:block">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Rules in this chat
      </h2>
      {rules.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No rules yet. Explore the data, validate a hypothesis, then create a rule from a proposal.
        </p>
      ) : (
        <ul className="space-y-3">
          {rules.map((rule) => (
            <li key={rule.id} className="rounded-md border border-border bg-background p-3 text-sm">
              <p className="font-medium">{rule.name}</p>
              <code className="mt-1 block break-words font-mono text-xs text-muted-foreground">
                {rule.where_clause}
              </code>
              <p className="mt-2 text-xs">
                {rule.matched_count.toLocaleString("en-US")} matched · {formatRate(rule.fraud_rate)} fraud
              </p>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
