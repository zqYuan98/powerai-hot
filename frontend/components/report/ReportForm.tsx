"use client";

import React, { useEffect, useRef, useState } from "react";
import { ApiError, api, SourceRow } from "../../lib/api";
import { SourceType } from "../../lib/types";
import { Send } from "../icons";

const LABEL: React.CSSProperties = { display: "block", fontSize: 12, fontWeight: 600, color: "#9AA6BC", marginBottom: 7 };
const FIELD: React.CSSProperties = { width: "100%", boxSizing: "border-box", padding: "11px 13px", borderRadius: 10, background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.16)", fontSize: 13.5, color: "#DCE3EF", marginBottom: 16, outline: "none" };
const ERROR_FIELD: React.CSSProperties = { borderColor: "rgba(248,113,113,0.8)" };
const INITIAL_VALUES = { name: "", url: "", type: "网站" as SourceType, reason: "" };
const SOURCE_TYPES: SourceType[] = ["网站", "公众号", "RSS"];

type FormValues = typeof INITIAL_VALUES;
type FieldErrors = Partial<Record<keyof FormValues, string>>;

function getErrorDetail(body: unknown): string | undefined {
  if (typeof body === "string" && body.trim()) return body;
  if (!body || typeof body !== "object") return undefined;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item && typeof item === "object" && typeof (item as { msg?: unknown }).msg === "string" ? (item as { msg: string }).msg : ""))
      .filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  return undefined;
}

function formatSubmitError(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = getErrorDetail(error.body);
    if (error.status === 409) return `Source already exists (409)${detail ? `: ${detail}` : "."}`;
    if (error.status === 422) return `Submission validation failed (422)${detail ? `: ${detail}` : "."}`;
    if (error.status >= 400 && error.status < 500) return `Submission rejected (${error.status})${detail ? `: ${detail}` : "."}`;
    return `Source service error (${error.status})${detail ? `: ${detail}` : "."}`;
  }
  return "Unable to reach the source service. Please try again.";
}

export default function ReportForm({
  reasonHeight = 74,
  onSubmitted,
}: {
  reasonHeight?: number;
  onSubmitted?: (record: SourceRow) => void;
}) {
  const [values, setValues] = useState<FormValues>(INITIAL_VALUES);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState<SourceRow | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const mountedRef = useRef(true);
  const lifecycleEpochRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      lifecycleEpochRef.current += 1;
    };
  }, []);

  const update = <K extends keyof FormValues>(field: K, value: FormValues[K]) => {
    setValues((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
    setSubmitError(null);
  };

  const validate = (): FieldErrors => {
    const next: FieldErrors = {};
    if (!values.name.trim()) next.name = "Source name is required.";
    if (!values.url.trim()) next.url = "URL is required.";
    if (!values.reason.trim()) next.reason = "Recommendation reason is required.";
    return next;
  };

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;
    const nextErrors = validate();
    setFieldErrors(nextErrors);
    setSubmitError(null);
    if (Object.keys(nextErrors).length) return;

    const requestEpoch = lifecycleEpochRef.current;
    setSubmitting(true);
    try {
      const record = await api.submitSourceSubmission({
        name: values.name.trim(),
        url: values.url.trim(),
        type: values.type,
        reason: values.reason.trim(),
      });
      if (!mountedRef.current || lifecycleEpochRef.current !== requestEpoch) return;
      setSubmitted(record);
      setValues(INITIAL_VALUES);
      setFieldErrors({});
      onSubmitted?.(record);
    } catch (error) {
      if (!mountedRef.current || lifecycleEpochRef.current !== requestEpoch) return;
      setSubmitError(formatSubmitError(error));
    } finally {
      if (mountedRef.current && lifecycleEpochRef.current === requestEpoch) setSubmitting(false);
    }
  };

  const fieldStyle = (field: keyof FormValues): React.CSSProperties => ({
    ...FIELD,
    ...(fieldErrors[field] ? ERROR_FIELD : {}),
  });
  const validationSummary = Object.values(fieldErrors).filter(Boolean).join(" ");

  return (
    <form onSubmit={submit} noValidate style={{ background: "linear-gradient(180deg, rgba(20,27,42,0.7), rgba(15,20,32,0.5))", border: "1px solid rgba(148,163,184,0.14)", borderRadius: 16, padding: 20 }}>
      {(submitError || validationSummary) && <div role="alert" style={{ marginBottom: 16, borderRadius: 10, padding: "10px 12px", color: "#FCA5A5", background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.28)", fontSize: 13 }}>{submitError || validationSummary}</div>}

      <label htmlFor="source-name" style={LABEL}>Source name</label>
      <input id="source-name" name="name" value={values.name} onChange={(event) => update("name", event.target.value)} style={fieldStyle("name")} aria-invalid={!!fieldErrors.name} aria-describedby={fieldErrors.name ? "source-name-error" : undefined} autoComplete="off" />
      {fieldErrors.name && <div id="source-name-error" style={{ marginTop: -10, marginBottom: 12, fontSize: 12, color: "#FCA5A5" }}>{fieldErrors.name}</div>}

      <label htmlFor="source-url" style={LABEL}>URL</label>
      <input id="source-url" name="url" type="url" value={values.url} onChange={(event) => update("url", event.target.value)} style={fieldStyle("url")} aria-invalid={!!fieldErrors.url} aria-describedby={fieldErrors.url ? "source-url-error" : undefined} autoComplete="off" />
      {fieldErrors.url && <div id="source-url-error" style={{ marginTop: -10, marginBottom: 12, fontSize: 12, color: "#FCA5A5" }}>{fieldErrors.url}</div>}

      <label htmlFor="source-type" style={LABEL}>Source type</label>
      <select id="source-type" name="type" value={values.type} onChange={(event) => update("type", event.target.value as SourceType)} style={{ ...fieldStyle("type"), cursor: "pointer" }}>
        {SOURCE_TYPES.map((sourceType) => <option key={sourceType} value={sourceType}>{sourceType}</option>)}
      </select>

      <label htmlFor="source-reason" style={LABEL}>Recommendation reason</label>
      <textarea id="source-reason" name="reason" value={values.reason} onChange={(event) => update("reason", event.target.value)} style={{ ...fieldStyle("reason"), fontSize: 13, lineHeight: 1.6, height: reasonHeight, resize: "vertical" }} aria-invalid={!!fieldErrors.reason} aria-describedby={fieldErrors.reason ? "source-reason-error" : undefined} />
      {fieldErrors.reason && <div id="source-reason-error" style={{ marginTop: -10, marginBottom: 12, fontSize: 12, color: "#FCA5A5" }}>{fieldErrors.reason}</div>}

      <button type="submit" disabled={submitting} style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, fontSize: 14, fontWeight: 700, color: submitting ? "#6B7280" : "#0A0E17", background: submitting ? "rgba(148,163,184,0.22)" : "linear-gradient(145deg, #34E0D8, #1FB6C9)", border: "none", padding: "12px 0", borderRadius: 11, cursor: submitting ? "not-allowed" : "pointer", boxShadow: submitting ? "none" : "0 8px 22px -8px rgba(52,224,216,0.6)" }}>
        <Send />{submitting ? "Submitting…" : "Submit source"}
      </button>

      <div aria-live="polite" role={submitted ? "status" : undefined} style={{ minHeight: submitted ? 22 : 0, marginTop: submitted ? 16 : 0 }}>
        {submitted && <div style={{ borderRadius: 10, padding: "11px 13px", background: "rgba(52,224,216,0.08)", border: "1px solid rgba(52,224,216,0.22)", fontSize: 13, color: "#B7F7F1" }}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>Submission received</div>
          <div data-testid="submitted-record"><strong>{submitted.name}</strong><span style={{ marginLeft: 8, color: "#9AA6BC" }}>{submitted.status || "pending"}</span></div>
        </div>}
      </div>
    </form>
  );
}
