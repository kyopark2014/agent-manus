import type { AppConfig, Task } from "../types";
import type { CreateTaskDefaults } from "./appDataService";

export const MAX_TASK_TITLE_LENGTH = 50;

export function sortTasks(tasks: Task[]): Task[] {
  return [...tasks].sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
  });
}

export function titleFromPrompt(prompt: string): string {
  return prompt.trim().slice(0, MAX_TASK_TITLE_LENGTH) || "New task";
}

export function buildNewTaskDefaults(
  config: AppConfig,
  activeTask: Task | null,
): CreateTaskDefaults {
  // Skill/MCP defaults come from per-user settings.json via /api/config
  // (default_skills / default_mcp_servers), not from the active task.
  return {
    model_name: activeTask?.model_name ?? config.default_model,
    skills: config.default_skills ?? [],
    mcp_servers: config.default_mcp_servers ?? [],
    guardrail_enabled: activeTask?.guardrail_enabled ?? false,
    memory_enabled: activeTask?.memory_enabled ?? true,
    llm_gateway_enabled: activeTask?.llm_gateway_enabled ?? false,
  };
}

export function buildFallbackTaskDefaults(config: AppConfig): CreateTaskDefaults {
  return {
    model_name: config.default_model,
    skills: config.default_skills,
    mcp_servers: config.default_mcp_servers,
    memory_enabled: true,
    llm_gateway_enabled: false,
  };
}

export function applyTaskTitleFromPrompt(
  tasks: Task[],
  taskId: string,
  prompt: string,
): Task[] {
  return sortTasks(
    tasks.map((task) =>
      task.id === taskId && (task.title === "New task" || !task.title)
        ? {
            ...task,
            title: titleFromPrompt(prompt),
            updated_at: new Date().toISOString(),
          }
        : task,
    ),
  );
}
