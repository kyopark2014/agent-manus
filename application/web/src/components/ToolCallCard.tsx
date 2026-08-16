import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ToolEvent } from "../types";

interface Props {
  event: ToolEvent;
}

function formatToolInput(input: unknown): string {
  if (input === undefined || input === null) {
    return "(매개변수 없음)";
  }
  if (typeof input === "object" && !Array.isArray(input)) {
    const keys = Object.keys(input as Record<string, unknown>);
    if (keys.length === 0) {
      return "(매개변수 없음 — 기본값 사용)";
    }
  }
  return JSON.stringify(input, null, 2);
}

/** Make tool result / info payloads readable across multiple lines. */
function formatToolPayload(data: string | undefined): string {
  if (!data) return "";

  try {
    const parsed = JSON.parse(data) as unknown;
    if (Array.isArray(parsed)) {
      const texts = parsed
        .filter(
          (block): block is { type: string; text: string } =>
            !!block &&
            typeof block === "object" &&
            (block as { type?: unknown }).type === "text" &&
            typeof (block as { text?: unknown }).text === "string",
        )
        .map((block) => block.text);
      if (texts.length > 0) {
        return texts.join("\n\n");
      }
    }
    return JSON.stringify(parsed, null, 2);
  } catch {
    // Python-style repr often embeds literal \n / \t escape sequences.
    return data.replace(/\\n/g, "\n").replace(/\\t/g, "\t");
  }
}

/** Strip optional [status] prefix and normalize whitespace for display. */
function formatStatusPayload(data: string | undefined): string {
  if (!data) return "";
  let text = data.replace(/\\n/g, "\n").trim();
  if (text.startsWith("[status]")) {
    text = text.slice("[status]".length).trim();
  }
  return text;
}

export function ToolCallCard({ event }: Props) {
  if (event.type === "plan") {
    return (
      <details className="tool-card plan-card" open>
        <summary>Plan</summary>
        <div className="plan-card-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {event.data ?? ""}
          </ReactMarkdown>
        </div>
      </details>
    );
  }
  if (event.type === "tool") {
    return (
      <details className="tool-card" open>
        <summary>Tool: {event.tool}</summary>
        <pre>{formatToolInput(event.input)}</pre>
      </details>
    );
  }
  if (event.type === "tool_result") {
    const resultLabel = event.tool ? `Tool result: ${event.tool}` : "Tool result";
    return (
      <details className="tool-card">
        <summary>{resultLabel}</summary>
        <pre>{formatToolPayload(event.data)}</pre>
      </details>
    );
  }
  // status + info: same Info notification card
  const infoData =
    event.type === "status" ? formatStatusPayload(event.data) : event.data;
  return (
    <details className="tool-card">
      <summary>
        Info
        {infoData
          ? `: ${infoData.replace(/\s+/g, " ").trim().slice(0, 120)}${
              infoData.replace(/\s+/g, " ").trim().length > 120 ? "…" : ""
            }`
          : ""}
      </summary>
      <pre>{formatToolPayload(infoData)}</pre>
    </details>
  );
}
