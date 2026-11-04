import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { QueryDetails, queriesToMarkdown } from "@/components/QueryDetails";

const query = {
  id: "c1",
  sql: "SELECT 1",
  purpose: "Count things",
  result: { id: "c1", columns: ["n"], rows: [[1]], row_count: 1, truncated: false, error: null },
};

describe("QueryDetails", () => {
  it("is collapsed by default and says how many queries ran", () => {
    render(<QueryDetails queries={[query, { ...query, id: "c2" }]} streaming={false} />);

    const toggle = screen.getByRole("button", { name: /Show 2 queries and results/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("expands on click", async () => {
    render(<QueryDetails queries={[query]} streaming={false} />);

    await userEvent.click(screen.getByRole("button", { name: /Show 1 query/ }));

    expect(screen.getByRole("button", { name: /Hide 1 query/ })).toHaveAttribute("aria-expanded", "true");
  });

  it("renders nothing when no queries ran", () => {
    const { container } = render(<QueryDetails queries={[]} streaming={false} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("puts each query's SQL before its result", () => {
    const markdown = queriesToMarkdown([query]);

    expect(markdown.indexOf("```sql")).toBeLessThan(markdown.indexOf("| n |"));
  });
});
