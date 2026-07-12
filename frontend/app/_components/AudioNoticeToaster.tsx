"use client";

import { useEffect, useRef } from "react";
import { Toaster, useToasterStore, type ToastType } from "react-hot-toast";
import { playNoticeSound, unlockNoticeAudio } from "../../lib/noticeSound";

const toastOptions = {
  duration: 3600,
  style: {
    border: "1px solid var(--border)",
    borderRadius: "12px",
    background: "rgba(4, 18, 14, 0.96)",
    boxShadow: "var(--shadow-md)",
    color: "#ECFDF5",
    fontSize: "14px",
    fontWeight: 700,
    lineHeight: 1.45,
    maxWidth: "min(520px, calc(100vw - 32px))",
    padding: "13px 15px",
  },
  success: {
    iconTheme: {
      primary: "#4ADE80",
      secondary: "#03130E",
    },
    style: {
      borderColor: "rgba(74, 222, 128, 0.38)",
      color: "#ECFDF5",
    },
  },
  error: {
    iconTheme: {
      primary: "#FB7185",
      secondary: "#03130E",
    },
    style: {
      borderColor: "rgba(251, 113, 133, 0.42)",
      color: "#FFE4E6",
    },
  },
  loading: {
    iconTheme: {
      primary: "#5EEAD4",
      secondary: "#03130E",
    },
    style: {
      borderColor: "rgba(94, 234, 212, 0.35)",
      color: "#CCFBF1",
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
