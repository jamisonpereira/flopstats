"use client";

import { useEffect } from "react";

/** y confirm · n reject · 1–4 type · j/k next/previous. Buttons opt in with data-key. */
export default function Shortcuts() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.metaKey || e.ctrlKey || e.altKey || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) return;
      const el = document.querySelector<HTMLElement>(`[data-key="${e.key}"]`);
      if (!el) return;
      e.preventDefault();
      if (el instanceof HTMLButtonElement && el.form) el.form.requestSubmit(el);
      else el.click();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return null;
}
