"use client";

import { useEffect, useRef } from "react";
import { Toaster, useToasterStore, type ToastType } from "react-hot-toast";
import { playNoticeSound, unlockNoticeAudio } from "../../lib/noticeSound";

const toastOptions = {
  duration: 3600,
  style: {
    border: "1px solid var(--border)",
    borderRadius: "12px",
    background: "var(--panel)",
    boxShadow: "var(--shadow-md)",
    color: "var(--text-primary)",
    fontSize: "14px",
    fontWeight: 700,
    lineHeight: 1.45,
    maxWidth: "min(520px, calc(100vw - 32px))",
    padding: "13px 15px",
  },
  success: {
    iconTheme: {
      primary: "var(--success)",
      secondary: "var(--panel)",
    },
    style: {
      borderColor: "var(--success-border)",
      color: "var(--text-primary)",
    },
  },
  error: {
    iconTheme: {
      primary: "var(--danger)",
      secondary: "var(--panel)",
    },
    style: {
      borderColor: "var(--danger-border)",
      color: "var(--text-primary)",
    },
  },
  loading: {
    iconTheme: {
      primary: "var(--primary)",
      secondary: "var(--panel)",
    },
    style: {
      borderColor: "var(--border-strong)",
      color: "var(--text-primary)",
    },
  },
};

const audibleTypes = new Set<ToastType>(["success", "error", "loading", "blank", "custom"]);

export function AudioNoticeToaster() {
  const { toasts } = useToasterStore();
  const playedToastStates = useRef(new Set<string>());

  useEffect(() => {
    const unlock = () => unlockNoticeAudio();

    window.addEventListener("pointerdown", unlock, { passive: true });
    window.addEventListener("keydown", unlock);
    return () => {
      window.removeEventListener("pointerdown", unlock);
      window.removeEventListener("keydown", unlock);
    };
  }, []);

  useEffect(() => {
    const activeKeys = new Set<string>();

    toasts.forEach((item) => {
      if (!item.visible || item.dismissed || !audibleTypes.has(item.type)) return;

      const key = `${item.id}:${item.type}:${item.createdAt}`;
      activeKeys.add(key);
      if (playedToastStates.current.has(key)) return;

      playedToastStates.current.add(key);
      playNoticeSound(item.type);
    });

    playedToastStates.current.forEach((key) => {
      if (!activeKeys.has(key)) {
        playedToastStates.current.delete(key);
      }
    });
  }, [toasts]);

  return <Toaster position="top-center" gutter={12} toastOptions={toastOptions} />;
}
