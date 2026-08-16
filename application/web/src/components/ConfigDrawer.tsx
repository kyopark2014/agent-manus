import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

interface Props {
  title: string;
  options: string[];
  selected: string[];
  anchorEl: HTMLElement | null;
  mode?: "multi" | "single";
  onChange: (next: string[]) => void;
  onClose: () => void;
}

const MENU_GAP = 8;
const MENU_MAX_HEIGHT = 320;

export function ConfigDrawer({
  title,
  options,
  selected,
  anchorEl,
  mode = "multi",
  onChange,
  onClose,
}: Props) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{
    left: number;
    top: number;
    width: number;
    maxHeight: number;
  } | null>(null);

  function toggle(option: string) {
    if (mode === "single") {
      onChange([option]);
      onClose();
      return;
    }
    if (selected.includes(option)) {
      onChange(selected.filter((s) => s !== option));
    } else {
      onChange([...selected, option]);
    }
  }

  function updatePosition() {
    if (!anchorEl) return;
    const rect = anchorEl.getBoundingClientRect();
    const width = Math.max(rect.width, 240);
    const left = Math.min(
      Math.max(8, rect.left),
      window.innerWidth - width - 8,
    );
    const top = rect.top - MENU_GAP;
    const maxHeight = Math.min(MENU_MAX_HEIGHT, Math.max(120, top - 8));
    setPosition({ left, top, width, maxHeight });
  }

  useLayoutEffect(() => {
    updatePosition();
  }, [anchorEl, options.length]);

  useEffect(() => {
    if (!anchorEl) return;

    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);

    function onPointerDown(e: MouseEvent) {
      const target = e.target as Node;
      if (menuRef.current?.contains(target)) return;
      if (anchorEl?.contains(target)) return;
      onClose();
    }

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }

    document.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
      document.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [anchorEl, onClose]);

  if (!position) return null;

  return createPortal(
    <div
      ref={menuRef}
      className="config-popover"
      role="dialog"
      aria-label={title}
      style={{
        left: position.left,
        top: position.top,
        width: position.width,
        maxHeight: position.maxHeight,
      }}
    >
      <div className="config-popover-header">{title}</div>
      <div className="config-popover-list">
        {options.length === 0 ? (
          <div className="config-popover-empty">선택할 항목이 없습니다.</div>
        ) : (
          options.map((option) => {
            const isSelected = selected.includes(option);
            if (mode === "single") {
              return (
                <button
                  key={option}
                  type="button"
                  className={`config-popover-item config-popover-choice${isSelected ? " is-selected" : ""}`}
                  role="menuitemradio"
                  aria-checked={isSelected}
                  onClick={() => toggle(option)}
                >
                  <span>{option}</span>
                  {isSelected && <span className="config-popover-check" aria-hidden="true">✓</span>}
                </button>
              );
            }
            return (
              <label key={option} className="config-popover-item">
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => toggle(option)}
                />
                <span>{option}</span>
              </label>
            );
          })
        )}
      </div>
    </div>,
    document.body,
  );
}
