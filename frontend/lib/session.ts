import type { SessionPayload } from "./api";

export type SessionRole = "workspace" | "admin" | null;
export type AccessScope = "workspace" | "admin";

export interface WorkspaceInfo {
  name: string;
  subtitle: string;
}

export interface SessionState {
  authenticated: boolean;
  role: SessionRole;
  mode: string | null;
  workspace: WorkspaceInfo | null;
  error?: string;
}

export const anonymousSession: SessionState = {
  authenticated: false,
  role: null,
  mode: null,
  workspace: null,
};

export function toSessionState(payload: SessionPayload): SessionState {
  return {
    authenticated: payload.authenticated,
    role: payload.role,
    mode: payload.mode,
    workspace: payload.workspace ?? null,
  };
}

/** Admin sessions include workspace access; workspace sessions do not include admin access. */
export function satisfiesScope(session: Pick<SessionState, "authenticated" | "role">, scope: AccessScope): boolean {
  if (!session.authenticated || session.role === null) return false;
  return scope === "workspace" || session.role === "admin";
}
