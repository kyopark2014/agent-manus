const SIDEBAR_W_KEY = "agent-manus:sidebar-w";

export const SIDEBAR_W_DEFAULT = 260;
export const SIDEBAR_W_MIN = 200;
export const SIDEBAR_W_MAX = 480;

export function getSidebarWidth(): number {
  try {
    const n = Number(localStorage.getItem(SIDEBAR_W_KEY));
    if (Number.isFinite(n) && n >= SIDEBAR_W_MIN && n <= SIDEBAR_W_MAX) {
      return Math.round(n);
    }
  } catch {
    /* ignore */
  }
  return SIDEBAR_W_DEFAULT;
}

export function setSidebarWidth(width: number): void {
  const clamped = clampSidebarWidth(width);
  try {
    localStorage.setItem(SIDEBAR_W_KEY, String(clamped));
  } catch {
    /* ignore */
  }
}

export function clampSidebarWidth(width: number): number {
  return Math.min(SIDEBAR_W_MAX, Math.max(SIDEBAR_W_MIN, Math.round(width)));
}
