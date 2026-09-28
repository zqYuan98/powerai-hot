"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

type Theme = "system" | "light" | "dark";
const NEXT: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };
const LABEL: Record<Theme, string> = { system: "跟随系统", light: "浅色", dark: "深色" };

function read(): Theme {
  const v = document.documentElement.getAttribute("data-theme");
  return v === "light" || v === "dark" ? v : "system";
}

function subscribe(cb: () => void) {
  const obs = new MutationObserver(cb);
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => obs.disconnect();
}

/** 三态主题：跟随系统 → 浅色 → 深色。偏好存本机，首屏由 layout 里的内联脚本恢复。 */
export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, read, () => "system" as Theme);

  function apply(next: Theme) {
    if (next === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("theme", next);
    } catch {}
  }

  const Icon = theme === "dark" ? Moon : theme === "light" ? Sun : Monitor;
  return (
    <button
      type="button"
      onClick={() => apply(NEXT[theme])}
      className="flex size-9 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-ink"
      title={`主题：${LABEL[theme]}`}
      aria-label={`切换主题（当前：${LABEL[theme]}）`}
    >
      <Icon className="size-4" aria-hidden />
    </button>
  );
}
