import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { formatBrandTitle } from "../formatBrandTitle";
import { useTheme } from "../hooks/useTheme";
import type { Theme } from "../theme";
import type { AppConfig, Task } from "../types";
import { ConfigDrawer } from "./ConfigDrawer";
import { KnowledgeGraphModal } from "./KnowledgeGraphModal";
import { LlmGatewayModal } from "./LlmGatewayModal";
import { TaskListItem } from "./TaskListItem";
import {
  AppearanceIcon,
  ChevronIcon,
  DashboardIcon,
  GuardrailIcon,
  KnowledgeGraphIcon,
  LlmGatewayIcon,
  LogoutIcon,
  McpIcon,
  MemoryIcon,
  ModelIcon,
  NewTaskIcon,
  SettingsIcon,
  SkillIcon,
  CloseIcon,
} from "./SidebarIcons";

type DrawerKind = "skill" | "mcp" | "model" | "appearance" | null;

const LLM_GATEWAY_NOT_CONFIGURED =
  "LLM Gateway가 설정되어 있지 않아 활성화할 수 없습니다. 관리자에게 설정을 요청하세요.";

const THEME_OPTIONS = ["Light", "Dark"] as const;

function themeToLabel(theme: Theme): string {
  return theme === "light" ? "Light" : "Dark";
}

function labelToTheme(label: string): Theme {
  return label === "Light" ? "light" : "dark";
}

interface Props {
  userId: string;
  tasks: Task[];
  activeTask: Task | null;
  config: AppConfig | null;
  drawer: DrawerKind;
  open: boolean;
  onClose: () => void;
  onNewTask: () => void;
  onSelectTask: (id: string) => void;
  onOpenDrawer: (kind: DrawerKind) => void;
  onCloseDrawer: () => void;
  onPatchTask: (taskId: string, patch: Partial<Task>) => void | Promise<void>;
  onDeleteTask: (taskId: string) => void;
  onLogout: () => void;
  knowledgeGraphEnabled?: boolean;
  onPatchKnowledgeGraphEnabled?: (enabled: boolean) => void | Promise<void>;
  onOpenDashboard?: () => void;
  onRefreshConfig?: () => Promise<AppConfig | void> | AppConfig | void;
}

export function Sidebar({
  userId,
  tasks,
  activeTask,
  config,
  drawer,
  open,
  onClose,
  onNewTask,
  onSelectTask,
  onOpenDrawer,
  onCloseDrawer,
  onPatchTask,
  onDeleteTask,
  onLogout,
  knowledgeGraphEnabled = true,
  onPatchKnowledgeGraphEnabled,
  onOpenDashboard,
  onRefreshConfig,
}: Props) {
  const skillBtnRef = useRef<HTMLButtonElement>(null);
  const mcpBtnRef = useRef<HTMLButtonElement>(null);
  const modelBtnRef = useRef<HTMLButtonElement>(null);
  const appearanceBtnRef = useRef<HTMLButtonElement>(null);
  const settingsSectionRef = useRef<HTMLDivElement>(null);
  const [llmGatewayOpen, setLlmGatewayOpen] = useState(false);
  const [knowledgeGraphOpen, setKnowledgeGraphOpen] = useState(false);
  const [settingsExpanded, setSettingsExpanded] = useState(false);
  const { theme, setTheme } = useTheme();
  const skills = activeTask?.skills ?? config?.default_skills ?? [];
  const mcpServers = activeTask?.mcp_servers ?? config?.default_mcp_servers ?? [];
  const modelName = activeTask?.model_name ?? config?.default_model ?? "";
  const brandTitle = formatBrandTitle(config?.projectName ?? "agent", userId);
  const pinnedTasks = tasks.filter((task) => task.pinned);
  const regularTasks = tasks.filter((task) => !task.pinned);
  const llmGatewayEnabled = activeTask?.llm_gateway_enabled ?? false;
  const gatewayModels = config?.gateway_models ?? [];
  const modelOptions =
    llmGatewayEnabled && gatewayModels.length > 0 ? gatewayModels : (config?.models ?? []);

  function collapseSettings() {
    setSettingsExpanded(false);
    setLlmGatewayOpen(false);
    onCloseDrawer();
  }

  useEffect(() => {
    if (!activeTask || !llmGatewayEnabled || gatewayModels.length === 0) return;
    if (gatewayModels.includes(modelName)) return;
    const next =
      config?.default_gateway_model && gatewayModels.includes(config.default_gateway_model)
        ? config.default_gateway_model
        : gatewayModels[0];
    onPatchTask(activeTask.id, { model_name: next });
  }, [
    activeTask,
    llmGatewayEnabled,
    gatewayModels,
    modelName,
    config?.default_gateway_model,
    onPatchTask,
  ]);

  useEffect(() => {
    if (!settingsExpanded) return;

    function onPointerDown(e: MouseEvent) {
      const target = e.target;
      if (!(target instanceof Element)) return;
      if (settingsSectionRef.current?.contains(target)) return;
      if (target.closest(".config-popover")) return;
      if (target.closest(".modal-overlay, .llm-gateway-modal, .knowledge-graph-modal")) return;
      collapseSettings();
    }

    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [settingsExpanded, onCloseDrawer]);

  function renderTask(task: Task, hidePinBadge = false) {
    return (
      <TaskListItem
        key={task.id}
        task={task}
        active={activeTask?.id === task.id}
        hidePinBadge={hidePinBadge}
        onSelect={() => {
          collapseSettings();
          onSelectTask(task.id);
        }}
        onDelete={() => onDeleteTask(task.id)}
        onRename={(title) => onPatchTask(task.id, { title })}
        onTogglePin={() => onPatchTask(task.id, { pinned: !task.pinned })}
      />
    );
  }

  function toggleDrawer(kind: Exclude<DrawerKind, null>) {
    onOpenDrawer(drawer === kind ? null : kind);
  }

  function handleSettingApplied() {
    collapseSettings();
  }

  function handleDrawerClose() {
    onCloseDrawer();
    setSettingsExpanded(false);
  }

  return (
    <>
      <aside className={`sidebar${open ? " sidebar-panel-open" : ""}`}>
        <div className="sidebar-header">
          <div className="brand-row">
            <button
              type="button"
              className={`brand brand-graph-btn${knowledgeGraphEnabled ? "" : " is-disabled"}`}
              title={
                knowledgeGraphEnabled
                  ? "Knowledge Graph 보기"
                  : "Knowledge Graph가 꺼져 있습니다"
              }
              aria-label={
                knowledgeGraphEnabled
                  ? `${brandTitle} Knowledge Graph 보기`
                  : brandTitle
              }
              aria-disabled={!knowledgeGraphEnabled}
              onClick={() => {
                if (!knowledgeGraphEnabled) return;
                collapseSettings();
                setKnowledgeGraphOpen(true);
              }}
            >
              {brandTitle}
            </button>
            <div className="sidebar-header-actions">
              <button
                type="button"
                className="sidebar-close-btn"
                aria-label="메뉴 닫기"
                onClick={onClose}
              >
                <CloseIcon className="sidebar-icon" />
              </button>
              <button
                type="button"
                className="brand-logout-btn"
                aria-label="나가기"
                title="나가기"
                onClick={onLogout}
              >
                <LogoutIcon className="sidebar-icon" />
              </button>
            </div>
          </div>
        </div>

        <button
          type="button"
          className="sidebar-menu-btn"
          onClick={() => {
            collapseSettings();
            onNewTask();
          }}
        >
          <NewTaskIcon className="sidebar-icon" />
          <span>New task</span>
        </button>

        {config?.is_admin && onOpenDashboard && (
          <button
            type="button"
            className="sidebar-menu-btn"
            onClick={() => {
              collapseSettings();
              onOpenDashboard();
            }}
          >
            <DashboardIcon className="sidebar-icon" />
            <span>Dashboard</span>
          </button>
        )}

        <div className="task-list">
          {pinnedTasks.length > 0 && (
            <div className="task-list-section">
              <div className="section-label">Pinned</div>
              {pinnedTasks.map((task) => renderTask(task, true))}
            </div>
          )}
          {regularTasks.length > 0 && (
            <div className="task-list-section">
              {pinnedTasks.length > 0 && <div className="section-label">Tasks</div>}
              {regularTasks.map((task) => renderTask(task))}
            </div>
          )}
        </div>

        <button
          ref={modelBtnRef}
          type="button"
          className={`sidebar-menu-btn${drawer === "model" ? " is-active" : ""}`}
          aria-expanded={drawer === "model"}
          aria-haspopup="dialog"
          title={modelName || "Model"}
          disabled={!activeTask}
          onClick={() => {
            setSettingsExpanded(false);
            setLlmGatewayOpen(false);
            if (drawer === "model") {
              onCloseDrawer();
            } else {
              onOpenDrawer("model");
            }
          }}
        >
          <ModelIcon className="sidebar-icon" />
          <span>{modelName || "Model"}</span>
        </button>

        <div
          ref={settingsSectionRef}
          className={`sidebar-section${settingsExpanded ? " is-expanded" : ""}`}
        >
          <button
            type="button"
            className="section-toggle"
            aria-expanded={settingsExpanded}
            onClick={() => {
              if (settingsExpanded) {
                collapseSettings();
                return;
              }
              onCloseDrawer();
              setSettingsExpanded(true);
            }}
          >
            <SettingsIcon className="sidebar-icon" />
            <span>Settings</span>
            <ChevronIcon className="section-chevron" />
          </button>
          {settingsExpanded && (
            <div className="sidebar-section-body">
              <button
                ref={skillBtnRef}
                type="button"
                className={`sidebar-menu-btn${drawer === "skill" ? " is-active" : ""}`}
                aria-expanded={drawer === "skill"}
                aria-haspopup="dialog"
                onClick={() => toggleDrawer("skill")}
                disabled={!activeTask}
              >
                <SkillIcon className="sidebar-icon" />
                <span>Skill ({skills.length})</span>
              </button>
              <button
                ref={mcpBtnRef}
                type="button"
                className={`sidebar-menu-btn${drawer === "mcp" ? " is-active" : ""}`}
                aria-expanded={drawer === "mcp"}
                aria-haspopup="dialog"
                onClick={() => toggleDrawer("mcp")}
                disabled={!activeTask}
              >
                <McpIcon className="sidebar-icon" />
                <span>MCP ({mcpServers.length})</span>
              </button>
              <label className="sidebar-menu-btn settings-toggle">
                <GuardrailIcon className="sidebar-icon" />
                <span>Guardrail</span>
                <input
                  type="checkbox"
                  checked={activeTask?.guardrail_enabled ?? false}
                  disabled={!activeTask}
                  onChange={(e) => {
                    if (!activeTask) return;
                    onPatchTask(activeTask.id, {
                      guardrail_enabled: e.target.checked,
                    });
                    handleSettingApplied();
                  }}
                />
              </label>
              <label className="sidebar-menu-btn settings-toggle">
                <MemoryIcon className="sidebar-icon" />
                <span>Memory</span>
                <input
                  type="checkbox"
                  checked={activeTask?.memory_enabled ?? true}
                  disabled={!activeTask}
                  onChange={(e) => {
                    if (!activeTask) return;
                    onPatchTask(activeTask.id, {
                      memory_enabled: e.target.checked,
                    });
                    handleSettingApplied();
                  }}
                />
              </label>
              <label className="sidebar-menu-btn settings-toggle">
                <KnowledgeGraphIcon className="sidebar-icon" />
                <span>Knowledge Graph</span>
                <input
                  type="checkbox"
                  checked={knowledgeGraphEnabled}
                  onChange={(e) => {
                    const enabled = e.target.checked;
                    void (async () => {
                      try {
                        await onPatchKnowledgeGraphEnabled?.(enabled);
                      } finally {
                        handleSettingApplied();
                      }
                    })();
                  }}
                />
              </label>
              <button
                type="button"
                className={`sidebar-menu-btn${llmGatewayOpen ? " is-active" : ""}`}
                disabled={!activeTask}
                onClick={() => setLlmGatewayOpen(true)}
              >
                <LlmGatewayIcon className="sidebar-icon" />
                <span>
                  LLM Gateway{llmGatewayEnabled ? " (On)" : ""}
                </span>
              </button>
              <button
                ref={appearanceBtnRef}
                type="button"
                className={`sidebar-menu-btn${drawer === "appearance" ? " is-active" : ""}`}
                aria-expanded={drawer === "appearance"}
                aria-haspopup="dialog"
                onClick={() => toggleDrawer("appearance")}
              >
                <AppearanceIcon className="sidebar-icon" />
                <span>Appearance ({themeToLabel(theme)})</span>
              </button>
            </div>
          )}
        </div>
      </aside>

      {drawer === "skill" && config && activeTask && (
        <ConfigDrawer
          title="Skill"
          options={config.skills}
          selected={skills}
          anchorEl={skillBtnRef.current}
          onChange={(next) => activeTask && onPatchTask(activeTask.id, { skills: next })}
          onClose={handleDrawerClose}
        />
      )}
      {drawer === "mcp" && config && activeTask && (
        <ConfigDrawer
          title="MCP"
          options={config.mcp_servers}
          selected={mcpServers}
          anchorEl={mcpBtnRef.current}
          onChange={(next) => activeTask && onPatchTask(activeTask.id, { mcp_servers: next })}
          onClose={handleDrawerClose}
        />
      )}
      {drawer === "model" && config && activeTask && (
        <ConfigDrawer
          title={llmGatewayEnabled ? "Model (LLM Gateway)" : "Model"}
          options={modelOptions}
          selected={modelName ? [modelName] : []}
          mode="single"
          anchorEl={modelBtnRef.current}
          onChange={(next) =>
            activeTask && next[0] && onPatchTask(activeTask.id, { model_name: next[0] })
          }
          onClose={onCloseDrawer}
        />
      )}
      {drawer === "appearance" && (
        <ConfigDrawer
          title="Appearance"
          options={[...THEME_OPTIONS]}
          selected={[themeToLabel(theme)]}
          mode="single"
          anchorEl={appearanceBtnRef.current}
          onChange={(next) => {
            if (next[0]) setTheme(labelToTheme(next[0]));
          }}
          onClose={handleDrawerClose}
        />
      )}

      {knowledgeGraphOpen && knowledgeGraphEnabled && (
        <KnowledgeGraphModal
          userId={userId}
          title={brandTitle}
          onClose={() => setKnowledgeGraphOpen(false)}
        />
      )}

      {llmGatewayOpen && activeTask && (
        <LlmGatewayModal
          enabled={llmGatewayEnabled}
          isAdmin={Boolean(config?.is_admin)}
          gatewayConfigured={Boolean(config?.llm_gateway_configured)}
          onConfirmEnable={async (uiModels) => {
            const refreshed = await onRefreshConfig?.();
            const gatewayStatus = await api.getLlmGateway();
            const configured = Boolean(
              gatewayStatus.configured ||
                (refreshed &&
                  "llm_gateway_configured" in refreshed &&
                  refreshed.llm_gateway_configured),
            );
            if (!configured) {
              throw new Error(LLM_GATEWAY_NOT_CONFIGURED);
            }
            const gatewayList =
              uiModels && uiModels.length > 0
                ? uiModels
                : refreshed && "gateway_models" in refreshed
                  ? (refreshed.gateway_models ?? [])
                  : (config?.gateway_models ?? []);
            const defaultGw =
              refreshed && "default_gateway_model" in refreshed
                ? refreshed.default_gateway_model
                : config?.default_gateway_model;
            const patch: Partial<Task> = { llm_gateway_enabled: true };
            if (gatewayList.length > 0 && !gatewayList.includes(modelName)) {
              patch.model_name =
                defaultGw && gatewayList.includes(defaultGw)
                  ? defaultGw
                  : gatewayList[0];
            }
            await onPatchTask(activeTask.id, patch);
          }}
          onDisable={() =>
            onPatchTask(activeTask.id, { llm_gateway_enabled: false })
          }
          onClose={() => {
            setLlmGatewayOpen(false);
            setSettingsExpanded(false);
            onCloseDrawer();
          }}
        />
      )}
    </>
  );
}
