"use client";

import { useEffect, useRef } from "react";
import { Toaster, useToasterStore, type ToastType } from "react-hot-toast";
import { playNoticeSound, unlockNoticeAudio } from "../../lib/noticeSound";

const toastOptions = {
  duration: 3600,
  style: {
    border: "1px solid var(--border)",
    borderRadius: "12px",
    boxShadow: "var(--shadow-md)",
    color: "var(--text-primary)",
    fontSize: "14px",
    fontWeight: 500,
    padding: "12px 14px",
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
