"use client";
import React from "react";
import { Check } from "./icons";

export default function Toast({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div style={{ position: "fixed", bottom: 30, left: "50%", transform: "translateX(-50%)", zIndex: 50, display: "flex", alignItems: "center", gap: 10, background: "linear-gradient(145deg, #16203A, #0E1626)", border: "1px solid rgba(52,224,216,0.4)", borderRadius: 12, padding: "13px 20px", boxShadow: "0 20px 50px -15px rgba(0,0,0,0.8), 0 0 0 1px rgba(52,224,216,0.1)", animation: "pToast 0.3s ease" }}>
      <div style={{ width: 22, height: 22, borderRadius: "50%", background: "linear-gradient(145deg,#34E0D8,#1FB6C9)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Check size={13} color="#0A0E17" sw={3} />
      </div>
      <span style={{ fontSize: 13.5, fontWeight: 500, color: "#EAF2FF" }}>{message}</span>
    </div>
  );
}
