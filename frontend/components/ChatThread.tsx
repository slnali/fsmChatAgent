"use client";

import { useEffect, useRef } from "react";
import { Streamdown } from "streamdown";

import type { SavedRule, Turn } from "@/lib/types";

import { QueryDetails } from "./QueryDetails";
import { RuleProposalCard } from "./RuleProposalCard";

export const SAMPLE_QUESTIONS = [
  "What is the fraud rate by transaction type?",
  "Where in the world is fraud happening? Compare US and foreign merchant locations.",
  "How many fraudulent transactions were there each month?",
  "Which merchant categories have the most fraud?",
];

type Props = {
  chatId: string;
  turns: Turn[];
  onAsk: (question: string) => void;
  onRuleSaved: (rule: SavedRule) => void;
};

export function ChatThread({ chatId, turns, onAsk, onRuleSaved }: Props) {
  const end = useRef<HTMLDivElement>(null);
  const lastMarkdown = turns.at(-1)?.markdown;

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [turns.length, lastMarkdown]);

  if (turns.length === 0) {
    return (
      <div className="mx-auto flex max-w-2xl flex-1 flex-col justify-center gap-4 p-6">
        <h2 className="text-xl font-semibold">What would you like to investigate?</h2>
        <p className="text-sm text-muted-foreground">
          Ask in plain English. Every query the agent runs is shown with its results, and you decide
          which proposed rules to create.
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          {SAMPLE_QUESTIONS.map((question) => (
            <button
              key={question}
              type="button"
              onClick={() => onAsk(question)}
              className="rounded-md border border-border p-3 text-left text-sm hover:bg-muted"
            >
              {question}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-6 p-6">
        {turns.map((turn) => (
          <article key={turn.id} className="space-y-3">
            <p className="ml-auto w-fit max-w-[80%] rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground">
              {turn.question}
            </p>
            <div className="text-sm">
              <Streamdown isAnimating={turn.streaming} parseIncompleteMarkdown>
                {turn.markdown || (turn.streaming ? "_Thinking…_" : "")}
              </Streamdown>
              <QueryDetails queries={turn.queries} streaming={turn.streaming} />
              {turn.proposals.map((proposal, index) => (
                <RuleProposalCard
                  key={`${turn.id}-${index}`}
                  chatId={chatId}
                  proposal={proposal}
                  onSaved={onRuleSaved}
                />
              ))}
            </div>
          </article>
        ))}
        <div ref={end} />
      </div>
    </div>
  );
}
