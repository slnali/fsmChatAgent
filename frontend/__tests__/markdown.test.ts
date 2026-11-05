import { describe, expect, it } from "vitest";

import { resultToMarkdown, sqlToMarkdown, toMermaidChart } from "@/lib/markdown";

const result = (columns: string[], rows: unknown[][], extra = {}) => ({
  columns,
  rows,
  truncated: false,
  error: null,
  ...extra,
});

describe("sqlToMarkdown", () => {
  it("shows the purpose then a sql fence", () => {
    expect(sqlToMarkdown({ sql: "SELECT 1", purpose: "Count" })).toBe(
      "\n\n*Count*\n\n```sql\nSELECT\n  1\n```\n\n",
    );
  });

  it("formats single-line SQL across lines so it is readable", () => {
    const markdown = sqlToMarkdown({
      sql: "SELECT t.transaction_type, COUNT(*) AS n FROM data.transactions t GROUP BY 1",
      purpose: "Count by type",
    });

    expect(markdown).toContain(
      "SELECT\n  t.transaction_type,\n  COUNT(*) AS n\nFROM\n  data.transactions t\nGROUP BY\n  1",
    );
  });

  it("shows the SQL unchanged when it cannot be formatted", () => {
    expect(sqlToMarkdown({ sql: "SELECT (((", purpose: "" })).toContain("```sql\nSELECT (((\n```");
  });
});

describe("resultToMarkdown", () => {
  it("builds a GFM table", () => {
    const markdown = resultToMarkdown(result(["type", "n"], [["Chip", 1200]]));

    expect(markdown).toContain("| type | n |\n| --- | --- |\n| Chip | 1,200 |");
  });

  it("escapes pipes and newlines in cells", () => {
    const markdown = resultToMarkdown(result(["name"], [["a|b\nc"]]));

    expect(markdown).toContain("| a\\|b c |");
  });

  it("adds a truncation note", () => {
    const markdown = resultToMarkdown(result(["id"], [[1], [2]], { truncated: true }));

    expect(markdown).toContain("_Showing the first 2 rows._");
  });

  it("shows an error callout instead of a table", () => {
    const markdown = resultToMarkdown(result([], [], { error: "column x does not exist" }));

    expect(markdown).toBe("> **Query error:** column x does not exist\n\n");
  });
});

describe("toMermaidChart", () => {
  it("draws a line chart for a date series, shortening month starts", () => {
    const chart = toMermaidChart(
      ["month", "fraud_count"],
      [
        ["2019-01-01T00:00:00", 129],
        ["2019-02-01T00:00:00", 113],
      ],
    );

    expect(chart).toContain('x-axis ["2019-01", "2019-02"]');
    expect(chart).toContain("line [129, 113]");
  });

  it("draws a bar chart for categories and prefers a rate column", () => {
    const chart = toMermaidChart(
      ["transaction_type", "labelled", "fraud_rate_pct"],
      [
        ["Chip", 551905, 0.224],
        ["Swipe", 131632, 0.093],
      ],
    );

    expect(chart).toContain('x-axis ["Chip", "Swipe"]');
    expect(chart).toContain("bar [0.224, 0.093]");
  });

  it("returns null when there is nothing to chart", () => {
    expect(toMermaidChart(["count"], [[1159966]])).toBeNull();
    expect(toMermaidChart(["a", "b"], [["x", "y"], ["z", "w"]])).toBeNull();
    expect(toMermaidChart(["a", "n"], [["x", 1]])).toBeNull();
  });
});
