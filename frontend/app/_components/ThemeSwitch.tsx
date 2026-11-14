"use client";

import { useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";
import { resolveStudioTheme, THEME_EVENT, THEME_STORAGE_KEY, type StudioTheme } from "../../lib/studioTheme";

function storedTheme() {
  try { return localStorage.getItem(THEME_STORAGE_KEY); } catch { return null; }
}

function subscribe(notify: () => void) {
  const media = matchMedia("(prefers-color-scheme: dark)");
  const update = (preference: string | null) => {
    document.documentElement.dataset.theme = resolveStudioTheme(preference, media.matches);
    notify();
  };
  const onSystem = () => {
    const preference = storedTheme();
    if (preference !== "dark" && preference !== "light") update(preference);
  };
  const onStorage = (event: StorageEvent) => {
    if (event.key === THEME_STORAGE_KEY || event.key === null) update(event.newValue);
  };
  media.addEventListener("change", onSystem);
  window.addEventListener("storage", onStorage);
  window.addEventListener(THEME_EVENT, notify);
  return () => {
    media.removeEventListener("change", onSystem);
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(THEME_EVENT, notify);
  };
}

const snapshot = (): StudioTheme => document.documentElement.dataset.theme === "light" ? "light" : "dark";
const serverSnapshot = (): StudioTheme => "dark";

export function ThemeSwitch() {
  const theme = useSyncExternalStore(subscribe, snapshot, serverSnapshot);
  const next = theme === "dark" ? "light" : "dark";
  const label = next === "light" ? "Aktifkan tema terang" : "Aktifkan tema gelap";
  return <button type="button" className="studioThemeToggle" title={label} aria-label={label}
    onClick={() => {
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem(THEME_STORAGE_KEY, next); } catch { /* Keep the control usable without storage. */ }
      window.dispatchEvent(new Event(THEME_EVENT));
    }}>
    {theme === "dark" ? <Sun size={17} strokeWidth={1.7} /> : <Moon size={17} strokeWidth={1.7} />}
  </button>;
}
