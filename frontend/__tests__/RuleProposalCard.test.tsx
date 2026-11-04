import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RuleProposalCard } from "@/components/RuleProposalCard";

const proposal = {
  name: "Italy merchants",
  where_clause: "t.merchant_location_id IN (SELECT id FROM data.merchant_locations WHERE state = 'Italy')",
  rationale: "85% of Italian labelled transactions are fraud",
  matched_count: 2431,
  fraud_count: 1360,
  fraud_rate: 0.851,
};

function mockFetch(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("RuleProposalCard", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows the rule and its metrics", () => {
    render(<RuleProposalCard chatId="chat-1" proposal={proposal} onSaved={() => {}} />);

    expect(screen.getByText(/WHERE t.merchant_location_id/)).toBeInTheDocument();
    expect(screen.getByText("2,431")).toBeInTheDocument();
    expect(screen.getByText("85.10%")).toBeInTheDocument();
  });

  it("posts the rule and reports it saved", async () => {
    const saved = { id: 1, chat_id: "chat-1", ...proposal, created_at: "2026-11-04" };
    const fetchMock = mockFetch(new Response(JSON.stringify(saved), { status: 201 }));
    const onSaved = vi.fn();
    render(<RuleProposalCard chatId="chat-1" proposal={proposal} onSaved={onSaved} />);

    await userEvent.click(screen.getByRole("button", { name: "Create rule" }));

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/rules$/);
    expect(JSON.parse(init.body)).toEqual({
      chat_id: "chat-1",
      name: proposal.name,
      where_clause: proposal.where_clause,
      rationale: proposal.rationale,
    });
    expect(await screen.findByRole("button", { name: "Rule created" })).toBeDisabled();
    expect(onSaved).toHaveBeenCalledWith(saved);
  });

  it("shows the backend's error when the rule is rejected", async () => {
    mockFetch(new Response(JSON.stringify({ detail: "Invalid rule: bad clause" }), { status: 422 }));
    render(<RuleProposalCard chatId="chat-1" proposal={proposal} onSaved={() => {}} />);

    await userEvent.click(screen.getByRole("button", { name: "Create rule" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid rule: bad clause");
  });
});
