export type Theme = "light" | "dark";

export const THEME_STORAGE_KEY = "agent-skills-theme";

export function getStoredTheme(): Theme {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY);
    if (value === "light" || value === "dark") return value;
  } catch {
    // ignore storage access errors
  }
  return "dark";
}

export function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // ignore storage access errors
  }
}

export function initTheme() {
  applyTheme(getStoredTheme());
}
