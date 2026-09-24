"use client";

import React from "react";

import { Bolt } from "../icons";
import WorkspaceIdentity from "../WorkspaceIdentity";
import { employeeNavItems, type EmployeeModuleKey } from "./navConfig";

const ACCENTS = {
  blue: { bg: "linear-gradient(90deg, rgba(59,158,255,0.16), rgba(59,158,255,0.04))", bd: "rgba(59,158,255,0.22)", fg: "#EAF2FF", dot: "#34E0D8" },
  cyan: { bg: "linear-gradient(90deg, rgba(52,224,216,0.16), rgba(52,224,216,0.04))", bd: "rgba(52,224,216,0.22)", fg: "#EAF7F6", dot: "#34E0D8" },
  violet: { bg: "linear-gradient(90deg, rgba(167,139,250,0.16), rgba(167,139,250,0.04))", bd: "rgba(167,139,250,0.22)", fg: "#F0EAFF", dot: "#A78BFA" },
} as const;

export default function EmployeeSidebar({
  module,
  go,
  notifCount,
}: {
  module: EmployeeModuleKey;
  go: (module: EmployeeModuleKey) => void;
  notifCount: number | null;
}) {
  return (
    <aside style={{ width: 232, flexShrink: 0, background: "linear-gradient(180deg, #0C111C, #090C14)", borderRight: "1px solid rgba(148,163,184,0.10)", display: "flex", flexDirection: "column", padding: "22px 16px", position: "relative", zIndex: 5 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 11, padding: "4px 6px 22px" }}>
        <div style={{ width: 38, height: 38, borderRadius: 11, background: "linear-gradient(145deg, #3B9EFF, #1E6FE0)", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 8px 22px -6px rgba(59,158,255,0.7), inset 0 1px 0 rgba(255,255,255,0.25)" }}><Bolt size={20} /></div>
        <div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 16, letterSpacing: "-0.02em", lineHeight: 1, color: "#F2F5FA" }}>电力AI<span style={{ color: "#34E0D8" }}>-hot</span></div>
          <div style={{ fontSize: 10, color: "#5E6A82", marginTop: 4, letterSpacing: "0.04em" }}>POWER AI INTELLIGENCE</div>
        </div>
      </div>

      <nav aria-label="Employee workspace navigation">
        <div style={{ fontSize: 10, fontWeight: 700, color: "#485066", letterSpacing: "0.12em", padding: "6px 10px 8px" }}>工作区导航</div>
        {employeeNavItems.map((item) => {
        const active = module === item.key;
        const accent = ACCENTS[item.accent];
        const Icon = item.icon;
        return (
          <button key={item.key} type="button" onClick={() => go(item.key)} aria-current={active ? "page" : undefined} style={{ display: "flex", alignItems: "center", gap: 12, width: "100%", padding: "11px 12px", borderRadius: 11, marginBottom: 4, textDecoration: "none", cursor: "pointer", textAlign: "left", background: active ? accent.bg : "transparent", border: active ? `1px solid ${accent.bd}` : "1px solid transparent", color: active ? accent.fg : "#94A0B5", boxShadow: active ? "inset 0 1px 0 rgba(255,255,255,0.06)" : undefined }}>
            <Icon size={18} color="currentColor" />
            <span style={{ fontSize: 14, fontWeight: 500 }}>{item.label}</span>
            {item.key === "sub" && notifCount !== null && notifCount > 0 ? <span style={{ marginLeft: "auto", fontFamily: "'JetBrains Mono', monospace", fontSize: 10, fontWeight: 700, color: "#0A0E17", background: "#34E0D8", padding: "2px 6px", borderRadius: 6 }}>{notifCount}</span> : active ? <span style={{ marginLeft: "auto", width: 6, height: 6, borderRadius: "50%", background: accent.dot, boxShadow: `0 0 8px ${accent.dot}` }} /> : null}
          </button>
        );
        })}
      </nav>

      <div style={{ marginTop: "auto" }}>
        <WorkspaceIdentity />
      </div>
    </aside>
  );
}
