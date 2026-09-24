"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { advanceAuthEpoch, api, getAuthEpoch, subscribeUnauthorized } from "../../lib/api";
import { anonymousSession, SessionState, toSessionState } from "../../lib/session";

interface SessionContextValue {
  session: SessionState;
  authenticated: boolean;
  role: SessionState["role"];
  mode: SessionState["mode"];
  workspace: SessionState["workspace"];
  error?: string;
  loading: boolean;
  refresh: () => Promise<SessionState>;
  unlock: (scope: "workspace" | "admin", token: string) => Promise<SessionState>;
  logout: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | null>(null);

function errorMessage(error: unknown, operation: "refresh" | "unlock"): string {
  const status = (error as { status?: number } | null)?.status;
  const message = error instanceof Error ? error.message.toLowerCase() : "";
  if (status === 401) return operation === "refresh" ? "Your session has expired. Unlock again to continue." : "Invalid access token.";
  if (message.includes("invalid") || message.includes("access code") || message.includes("unauthor")) return "Invalid access token.";
  if (status === 429) return "Too many unlock attempts. Try again later.";
  if (message.includes("rate") || message.includes("too many")) return "Too many unlock attempts. Try again later.";
  if (status === 503) return "Authentication service unavailable. Try again later.";
  if (message.includes("unavailable") || message.includes("service")) return "Authentication service unavailable. Try again later.";
  return "Network error. Check your connection and try again.";
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionState>(anonymousSession);
  const [loading, setLoading] = useState(true);
  const sessionRef = useRef(session);

  useEffect(() => { sessionRef.current = session; }, [session]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const next = toSessionState(await api.getSession());
      if (next.authenticated) advanceAuthEpoch();
      sessionRef.current = next;
      setSession(next);
      return next;
    } catch (error) {
      const failed = { ...anonymousSession, error: errorMessage(error, "refresh") };
      sessionRef.current = failed;
      setSession(failed);
      return failed;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const unsubscribe = subscribeUnauthorized((eventEpoch) => {
      if (eventEpoch !== getAuthEpoch() || !sessionRef.current.authenticated) return;
      advanceAuthEpoch();
      const expired = { ...anonymousSession, error: "Your session has expired. Unlock again to continue." };
      sessionRef.current = expired;
      setSession(expired);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const unlock = useCallback(async (scope: "workspace" | "admin", token: string) => {
    setLoading(true);
    try {
      const next = toSessionState(await api.createSession(scope, token));
      if (next.authenticated) advanceAuthEpoch();
      sessionRef.current = next;
      setSession(next);
      return next;
    } catch (error) {
      const failed = { ...session, error: errorMessage(error, "unlock") };
      sessionRef.current = failed;
      setSession(failed);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [session]);

  const logout = useCallback(async () => {
    advanceAuthEpoch();
    const loggedOut = { ...anonymousSession, workspace: sessionRef.current.workspace };
    sessionRef.current = loggedOut;
    setSession(loggedOut);
    setLoading(false);
    try {
      await api.deleteSession();
    } catch { /* local lock state is already cleared; server cleanup is best effort */ }
  }, []);

  const value = useMemo(() => ({
    session,
    authenticated: session.authenticated,
    role: session.role,
    mode: session.mode,
    workspace: session.workspace,
    error: session.error,
    loading,
    refresh,
    unlock,
    logout,
  }), [session, loading, refresh, unlock, logout]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside SessionProvider");
  return context;
}
