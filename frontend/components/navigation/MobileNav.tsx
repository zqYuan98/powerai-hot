"use client";

import React from "react";

import type { NavigationItem } from "./navConfig";

/** 移动端底部导航：小屏替代固定侧栏，点击目标 ≥44px，键盘可操作。 */
export default function MobileNav<Key extends string>({
  items,
  active,
  go,
  badges,
}: {
  items: NavigationItem<Key>[];
  active: Key;
  go: (key: Key) => void;
  badges?: Partial<Record<Key, number | null>>;
}) {
  return (
    <nav
      aria-label="移动端主导航"
      style={{
        flexShrink: 0,
        display: "flex",
        background: "linear-gradient(180deg, #0C111C, #090C14)",
        borderTop: "1px solid rgba(148,163,184,0.14)",
        paddingBottom: "env(safe-area-inset-bottom)",
        overflowX: "auto",
        position: "relative",
        zIndex: 20,
      }}
    >
      {items.map((item) => {
        const on = active === item.key;
        const Icon = item.icon;
        const badge = badges?.[item.key];
        return (
          <button
            key={item.key}
            type="button"
            onClick={() => go(item.key)}
            aria-current={on ? "page" : undefined}
            style={{
              flex: "1 0 62px",
              minHeight: 56,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 3,
              padding: "7px 4px",
              background: "transparent",
              border: 0,
              borderTop: on ? "2px solid #34E0D8" : "2px solid transparent",
              color: on ? "#EAF7F6" : "#828EA3",
              cursor: "pointer",
              position: "relative",
            }}
          >
            <Icon size={18} color="currentColor" />
            <span style={{ fontSize: 10.5, fontWeight: on ? 700 : 500, whiteSpace: "nowrap" }}>{item.label}</span>
            {badge != null && badge > 0 && (
              <span style={{ position: "absolute", top: 5, right: "50%", transform: "translateX(18px)", fontFamily: "'JetBrains Mono', monospace", fontSize: 9, fontWeight: 700, color: "#0A0E17", background: "#34E0D8", padding: "1px 5px", borderRadius: 6 }}>{badge}</span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
