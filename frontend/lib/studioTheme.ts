export type StudioTheme = "dark" | "light";
export const THEME_STORAGE_KEY = "clipforge.studio.theme";
export const THEME_EVENT = "clipforge:theme-change";

export function resolveStudioTheme(preference: string | null, prefersDark: boolean): StudioTheme {
  return preference === "light" || preference === "dark" ? preference : prefersDark ? "dark" : "light";
}

// Runs in <head> before the first paint, including when storage is unavailable.
export const THEME_BOOTSTRAP = `(function(){var p=null;try{p=localStorage.getItem('${THEME_STORAGE_KEY}')}catch(e){}var d=matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.dataset.theme=p==='light'||p==='dark'?p:d?'dark':'light'})()`;
