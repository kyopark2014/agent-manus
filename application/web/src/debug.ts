const PREFIX = "[AgentUI]";

function write(
  level: "log" | "warn" | "error",
  message: string,
  data?: unknown,
) {
  const line = `${PREFIX} ${message}`;
  if (data !== undefined) {
    console[level](line, data);
  } else {
    console[level](line);
  }
}

export const uiLog = (message: string, data?: unknown) => write("log", message, data);
export const uiWarn = (message: string, data?: unknown) => write("warn", message, data);
export const uiError = (message: string, data?: unknown) => write("error", message, data);
