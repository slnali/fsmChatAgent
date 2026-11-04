// Turns agent events into Markdown for Streamdown. Pure functions, easy to test.
import type { ToolCall, ToolResult } from "./types";

export function sqlToMarkdown({ sql, purpose }: Pick<ToolCall, "sql" | "purpose">): string {
  return `\n\n*${purpose.trim() || "Query"}*\n\n\`\`\`sql\n${sql.trim()}\n\`\`\`\n\n`;
}

export function resultToMarkdown(
  result: Pick<ToolResult, "columns" | "rows" | "truncated" | "error">,
): string {
  if (result.error) {
    return `> **Query error:** ${singleLine(result.error)}\n\n`;
  }
  if (result.rows.length === 0) {
    return "_No rows returned._\n\n";
  }

  const header = `| ${result.columns.map(escapeCell).join(" | ")} |`;
  const divider = `| ${result.columns.map(() => "---").join(" | ")} |`;
  const body = result.rows.map((row) => `| ${row.map(formatCell).join(" | ")} |`);
  let markdown = [header, divider, ...body].join("\n") + "\n\n";

  if (result.truncated) {
    markdown += `_Showing the first ${result.rows.length} rows._\n\n`;
  }
  const chart = toMermaidChart(result.columns, result.rows);
  if (chart) {
    markdown += `\`\`\`mermaid\n${chart}\n\`\`\`\n\n`;
  }
  return markdown;
}

/**
 * A Mermaid xychart for "label + number" results:
 * date-like labels -> line chart, other labels -> bar chart, anything else -> null.
 */
export function toMermaidChart(columns: string[], rows: unknown[][]): string | null {
  if (columns.length < 2 || rows.length < 2) return null;

  const valueIndex = pickValueColumn(columns, rows);
  if (valueIndex === null) return null;

  const labels = rows.map((row) => labelOf(row[0]));
  const isTimeSeries = rows.every((row) => isDateLike(row[0]));
  const xLabels = isTimeSeries ? shortenDates(labels) : labels;
  const values = rows.map((row) => Number(row[valueIndex] ?? 0));

  return [
    "xychart-beta",
    `    title "${quote(columns[valueIndex])} by ${quote(columns[0])}"`,
    `    x-axis [${xLabels.map((label) => `"${quote(label)}"`).join(", ")}]`,
    `    y-axis "${quote(columns[valueIndex])}"`,
    `    ${isTimeSeries ? "line" : "bar"} [${values.join(", ")}]`,
  ].join("\n");
}

/** Prefer a rate/percentage column; otherwise the first numeric column after the label. */
function pickValueColumn(columns: string[], rows: unknown[][]): number | null {
  const numeric = columns
    .map((_, index) => index)
    .filter((index) => index > 0 && rows.every((row) => isNumber(row[index]) || row[index] === null))
    .filter((index) => rows.some((row) => isNumber(row[index])));
  if (numeric.length === 0) return null;
  return numeric.find((index) => /rate|pct|percent|share/i.test(columns[index])) ?? numeric[0];
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isDateLike(value: unknown): boolean {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}/.test(value);
}

function shortenDates(labels: string[]): string[] {
  const days = labels.map((label) => label.slice(0, 10));
  const monthly = days.every((day) => day.endsWith("-01"));
  return monthly ? days.map((day) => day.slice(0, 7)) : days;
}

function labelOf(value: unknown): string {
  return value === null || value === undefined ? "(none)" : String(value);
}

function quote(text: string): string {
  return text.replace(/"/g, "'");
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return value.toLocaleString("en-US", { maximumFractionDigits: 6 });
  return escapeCell(String(value));
}

function escapeCell(text: string): string {
  return singleLine(text).replace(/\|/g, "\\|");
}

function singleLine(text: string): string {
  return text.replace(/\r?\n/g, " ");
}
