"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, SourceRow } from "../../lib/api";
import ReportForm from "./ReportForm";

function SourceSubmissionList() {
  const [submissions, setSubmissions] = useState<SourceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const mountedRef = useRef(true);
  const requestEpochRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestEpochRef.current += 1;
    };
  }, []);

  const load = useCallback(async () => {
    if (!mountedRef.current) return;
    const requestEpoch = ++requestEpochRef.current;
    setLoading(true);
    setError(false);
    try {
      const rows = await api.listSourceSubmissions();
      if (!mountedRef.current || requestEpochRef.current !== requestEpoch) return;
      setSubmissions(rows);
    } catch {
      if (!mountedRef.current || requestEpochRef.current !== requestEpoch) return;
      setError(true);
    } finally {
      if (mountedRef.current && requestEpochRef.current === requestEpoch) setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (loading) return <div role="status" style={{ padding: "20px 0", fontSize: 13, color: "#828EA3" }}>Loading submitted sources…</div>;
  if (error) return (
    <div role="alert" style={{ marginTop: 24, borderRadius: 12, padding: "14px 16px", color: "#FCA5A5", background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.28)", fontSize: 13 }}>
      <div>Source submissions could not be loaded. Please try again.</div>
      <button type="button" onClick={() => void load()} style={{ marginTop: 10, border: "1px solid rgba(248,113,113,0.35)", borderRadius: 8, background: "transparent", color: "#FCA5A5", padding: "6px 10px", cursor: "pointer" }}>Try again</button>
    </div>
  );
  if (!submissions.length) return <div style={{ marginTop: 24, padding: "16px 0", color: "#828EA3", fontSize: 13 }}>No source submissions yet.</div>;

  return (
    <section style={{ marginTop: 28 }}>
      <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700, color: "#DCE3EF" }}>Submitted sources</h3>
      <ul role="list" aria-label="Submitted sources" style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 10 }}>
        {submissions.map((source) => (
          <li key={source.id} style={{ borderRadius: 12, padding: "13px 15px", background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.14)" }}>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12 }}>
              <strong style={{ color: "#E6EBF4", fontSize: 13.5 }}>{source.name}</strong>
              <span style={{ color: "#FCD34D", fontSize: 12 }}>{source.status || "pending"}</span>
            </div>
            <a href={source.url} target="_blank" rel="noreferrer" style={{ display: "block", marginTop: 6, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#9FD0FF", fontSize: 12, fontFamily: "'JetBrains Mono', monospace" }}>{source.url}</a>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function ReportModule({ onSubmitReport }: { onSubmitReport?: () => void } = {}) {
  const [newSubmission, setNewSubmission] = useState<SourceRow | null>(null);
  const handleSubmitted = (submission: SourceRow) => {
    setNewSubmission(submission);
    onSubmitReport?.();
  };

  return (
    <div style={{ flex: 1, minWidth: 0, overflow: "auto", padding: "32px 40px", position: "relative", zIndex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div style={{ width: "100%", maxWidth: 640 }}>
        <h2 style={{ margin: "0 0 4px", fontSize: 24, fontWeight: 900, letterSpacing: "-0.02em", color: "#F4F7FB" }}>信源提报</h2>
        <p style={{ margin: "0 0 24px", fontSize: 13, color: "#828EA3" }}>推荐优质信源，经内部审核后纳入采集池</p>
        <ReportForm reasonHeight={88} onSubmitted={handleSubmitted} />
        <SourceSubmissionList key={newSubmission?.id ?? "submissions"} />
      </div>
    </div>
  );
}
