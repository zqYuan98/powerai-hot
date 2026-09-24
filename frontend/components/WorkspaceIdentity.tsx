"use client";

import React from "react";

import { useSession } from "./auth/SessionProvider";

export default function WorkspaceIdentity() {
  const { workspace, role, mode } = useSession();
  const name = workspace?.name || "PowerAI 工作区";
  const subtitle = workspace?.subtitle || "共享工作区";
  const roleLabel = role === "admin" ? "admin" : role === "workspace" ? "workspace" : "访客";
  const modeLabel = mode || "未指定模式";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 11,
        padding: 10,
        borderRadius: 12,
        background: "rgba(148,163,184,0.05)",
        border: "1px solid rgba(148,163,184,0.08)",
      }}
      data-workspace-identity
    >
      <div
        style={{
          width: 34,
          height: 34,
          borderRadius: 10,
          background: "linear-gradient(145deg, #3B9EFF, #1FB6C9)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontWeight: 800,
          fontSize: 13,
          color: "#0A0E17",
        }}
      >
        {name.slice(0, 1)}
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 650, color: "#DCE3EF", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {name}
        </div>
        <div style={{ fontSize: 10, color: "#7D8AA1", marginTop: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {subtitle}
        </div>
        <div style={{ fontSize: 9, color: "#5E6A82", marginTop: 3, letterSpacing: "0.04em" }}>
          {roleLabel} · {modeLabel}
        </div>
      </div>
    </div>
  );
}
