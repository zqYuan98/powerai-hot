"use client";

import React, { FormEvent, useEffect, useState } from "react";

import { satisfiesScope } from "../../lib/session";
import { useSession } from "./SessionProvider";

export function AccessGate({ scope = "workspace", children }: { scope?: "workspace" | "admin"; children: React.ReactNode }) {
  const { session, loading, unlock, logout } = useSession();
  const [token, setToken] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    if (session.error) setError(session.error);
  }, [session.error]);

  if (loading && !session.authenticated) {
    return <div role="status" className="p-6 text-sm text-slate-400">Checking access…</div>;
  }

  if (satisfiesScope(session, scope)) {
    return <div data-session-role={session.role} className="contents">
      <div data-session-logout className="fixed right-4 top-3 z-50"><button type="button" onClick={() => void logout()} className="rounded bg-slate-950/80 px-2 py-1 text-xs text-slate-400 shadow hover:text-white">Log out</button></div>
      {children}
    </div>;
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token.trim()) return;
    setSubmitting(true);
    setError(undefined);
    try {
      const next = await unlock(scope, token);
      setToken("");
      if (!satisfiesScope(next, scope)) setError("This access token does not grant the requested scope.");
    } catch (reason) {
      const status = (reason as { status?: number } | null)?.status;
      const message = reason instanceof Error ? reason.message.toLowerCase() : "";
      if (status === 401) setError("Invalid access token.");
      else if (message.includes("invalid") || message.includes("access code") || message.includes("unauthor")) setError("Invalid access token.");
      else if (status === 429) setError("Too many unlock attempts. Try again later.");
      else if (message.includes("rate") || message.includes("too many")) setError("Too many unlock attempts. Try again later.");
      else if (status === 503) setError("Authentication service unavailable. Try again later.");
      else if (message.includes("unavailable") || message.includes("service")) setError("Authentication service unavailable. Try again later.");
      else setError("Network error. Check your connection and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return <section aria-label="Access required" className="mx-auto max-w-md p-6 text-slate-100">
    <h2 className="text-lg font-semibold">{scope === "admin" ? "Admin access required" : "Unlock workspace"}</h2>
    <p className="mt-2 text-sm text-slate-400">Enter the access token to continue. Tokens are sent only to this workspace.</p>
    {error && <p role="alert" className="mt-3 text-sm text-rose-300">{error}</p>}
    <form onSubmit={submit} className="mt-4 flex gap-2">
      <label className="sr-only" htmlFor="access-token">Access token</label>
      <input id="access-token" type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} className="min-w-0 flex-1 rounded border border-slate-700 bg-slate-900 px-3 py-2" />
      <button type="submit" disabled={submitting || !token.trim()} className="rounded bg-cyan-500 px-3 py-2 text-sm font-medium text-slate-950 disabled:opacity-50">{submitting ? "Unlocking…" : "Unlock"}</button>
    </form>
  </section>;
}
