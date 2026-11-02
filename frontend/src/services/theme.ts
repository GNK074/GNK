import type { Theme } from "../store/session";
const key = "gnk:theme";
export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(key, theme);
  } catch {
    /* Storage can be disabled. */
  }
}
export function initializeTheme() {
  let theme: Theme = "carbon_black";
  try {
    const saved = localStorage.getItem(key);
    if (saved === "light" || saved === "royal_blue") theme = saved;
  } catch {
    /* Use default. */
  }
  applyTheme(theme);
}
