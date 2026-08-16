import { useEffect, useRef, useState } from "react";
import type { Task } from "../types";

interface Props {
  task: Task;
  active: boolean;
  hidePinBadge?: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRename: (title: string) => void;
  onTogglePin: () => void;
}

export function TaskListItem({
  task,
  active,
  hidePinBadge = false,
  onSelect,
  onDelete,
  onRename,
  onTogglePin,
}: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(task.title);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setRenameValue(task.title);
  }, [task.title]);

  useEffect(() => {
    if (!menuOpen) return;
    function onDocClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [menuOpen]);

  function submitRename() {
    const title = renameValue.trim();
    if (title && title !== task.title) {
      onRename(title);
    }
    setRenaming(false);
  }

  if (renaming) {
    return (
      <div className={`task-row ${active ? "active" : ""}`}>
        <input
          className="task-rename-input"
          value={renameValue}
          onChange={(e) => setRenameValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submitRename();
            if (e.key === "Escape") {
              setRenaming(false);
              setRenameValue(task.title);
            }
          }}
          onBlur={submitRename}
          autoFocus
        />
      </div>
    );
  }

  return (
    <div className={`task-row ${active ? "active" : ""}`}>
      <button type="button" className="task-item" onClick={onSelect} title={task.title}>
        {task.pinned && !hidePinBadge && (
          <svg className="task-pin-icon" viewBox="0 0 16 16" aria-hidden="true">
            <path
              fill="currentColor"
              d="M9.5 1.5 8 0 6.5 1.5v3L3 7v1h10V7L9.5 4.5v-3ZM4 9v5l4-2 4 2V9H4Z"
            />
          </svg>
        )}
        <span className="task-item-label">{task.title}</span>
      </button>
      <div className="task-actions">
        <button
          type="button"
          className="task-action-btn"
          aria-label="Delete task"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        >
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <path
              fill="currentColor"
              d="M5 2V1h6v1h4v2H1V2h4ZM3 6h1v8H2V6h1Zm3 0h1v8H6V6Zm4 0h1v8h-1V6ZM3 16h10V6H3v10Z"
            />
          </svg>
        </button>
        <div className="task-menu-wrap" ref={menuRef}>
          <button
            type="button"
            className="task-action-btn"
            aria-label="Task options"
            onClick={(e) => {
              e.stopPropagation();
              setMenuOpen((open) => !open);
            }}
          >
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <circle fill="currentColor" cx="8" cy="3" r="1.5" />
              <circle fill="currentColor" cx="8" cy="8" r="1.5" />
              <circle fill="currentColor" cx="8" cy="13" r="1.5" />
            </svg>
          </button>
          {menuOpen && (
            <div className="task-menu" role="menu">
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  setRenaming(true);
                  setRenameValue(task.title);
                }}
              >
                <svg viewBox="0 0 16 16" aria-hidden="true">
                  <path
                    fill="currentColor"
                    d="m11.7 2.3 1 1-8.4 8.4-1.3.3.3-1.3 8.4-8.4ZM12 1 15 4 5.5 13.5l-3 .8.8-3L12 1Z"
                  />
                </svg>
                Rename
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  onTogglePin();
                }}
              >
                <svg viewBox="0 0 16 16" aria-hidden="true">
                  <path
                    fill="currentColor"
                    d="M9.5 1.5 8 0 6.5 1.5v3L3 7v1h10V7L9.5 4.5v-3ZM4 9v5l4-2 4 2V9H4Z"
                  />
                </svg>
                {task.pinned ? "Unpin" : "Pin"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
