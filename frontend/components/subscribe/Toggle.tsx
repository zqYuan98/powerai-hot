"use client";
import React from "react";

export default function Toggle({
  on, onColor, onToggle,
}: {
  on: boolean; onColor: string; onToggle: () => void;
}) {
  return (
    <div
      onClick={onToggle}
      style={{ width: 42, height: 24, borderRadius: 14, flexShrink: 0, cursor: "pointer", background: on ? onColor : "rgba(148,163,184,0.18)", position: "relative", transition: "background .2s" }}
    >
      <span style={{ position: "absolute", top: 3, left: on ? 21 : 3, width: 18, height: 18, borderRadius: "50%", background: on ? "#fff" : "#8B97AD", boxShadow: on ? "0 2px 6px rgba(0,0,0,0.4)" : "none", transition: "left .2s" }} />
    </div>
  );
}
