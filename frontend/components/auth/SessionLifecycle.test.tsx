import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AccessGate } from "./AccessGate";
import { SessionProvider, useSession } from "./SessionProvider";
import { api } from "../../lib/api";

const workspaceSession = {
  authenticated: true,
  role: "workspace" as const,
  mode: "shared",
  workspace: { name: "PowerAI", subtitle: "Workspace" },
};

describe("session lifecycle", () => {
  beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
  afterEach(() => vi.unstubAllGlobals());

  it("relocks protected content when a non-auth API call returns 401", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input) => {
      if (String(input).endsWith("/auth/session")) return Promise.resolve(new Response(JSON.stringify(workspaceSession), { status: 200 }));
      return Promise.resolve(new Response("expired", { status: 401 }));
    });

    function SessionDetails() {
      const { workspace, role, mode } = useSession();
      return <div data-testid="session-details">{workspace?.name}|{workspace?.subtitle}|{role}|{mode}</div>;
    }
    render(<SessionProvider><SessionDetails /><AccessGate scope="workspace"><div data-testid="protected">Protected</div></AccessGate></SessionProvider>);
    expect(await screen.findByTestId("protected")).toBeInTheDocument();
    expect(screen.getByTestId("session-details")).toHaveTextContent("PowerAI|Workspace|workspace|shared");
    expect(window.localStorage.getItem("access_token")).toBeNull();
    expect(window.sessionStorage.getItem("access_token")).toBeNull();

    let transportError: unknown;
    await act(async () => {
      try { await api.listArticles(); } catch (error) { transportError = error; }
    });
    expect(transportError).toMatchObject({ status: 401 });
    await waitFor(() => expect(screen.queryByTestId("protected")).not.toBeInTheDocument());
    expect(await screen.findByText(/session has expired/i)).toBeInTheDocument();
  });

  it("unmounts protected content before a hanging logout request resolves", async () => {
    const fetchMock = vi.mocked(fetch);
    let resolveDelete!: (response: Response) => void;
    const pendingDelete = new Promise<Response>((resolve) => { resolveDelete = resolve; });
    fetchMock.mockImplementation((input, init) => {
      if (String(input).endsWith("/auth/session") && (init?.method ?? "GET") === "DELETE") return pendingDelete;
      return Promise.resolve(new Response(JSON.stringify(workspaceSession), { status: 200 }));
    });

    render(<SessionProvider><AccessGate scope="workspace"><div data-testid="protected">Protected</div></AccessGate></SessionProvider>);
    expect(await screen.findByTestId("protected")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /log out|logout/i }));
    await waitFor(() => expect(screen.queryByTestId("protected")).not.toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/session", expect.objectContaining({ method: "DELETE" }));

    resolveDelete(new Response(null, { status: 204 }));
  });

  it("ignores a stale 401 after logout and a successful new session", async () => {
    const fetchMock = vi.mocked(fetch);
    let resolveStale!: (response: Response) => void;
    const staleRequest = new Promise<Response>((resolve) => { resolveStale = resolve; });
    fetchMock.mockImplementation((input, init) => {
      const path = String(input);
      if (path.endsWith("/auth/session") && (init?.method ?? "GET") === "DELETE") return Promise.resolve(new Response(null, { status: 204 }));
      if (path.endsWith("/auth/session") && init?.method === "POST") return Promise.resolve(new Response(JSON.stringify(workspaceSession), { status: 200 }));
      if (path.endsWith("/auth/session")) return Promise.resolve(new Response(JSON.stringify(workspaceSession), { status: 200 }));
      return staleRequest;
    });

    render(<SessionProvider><AccessGate scope="workspace"><div data-testid="protected">Protected</div></AccessGate></SessionProvider>);
    expect(await screen.findByTestId("protected")).toBeInTheDocument();

    const staleApiCall = api.listArticles();
    const staleError = staleApiCall.catch((error) => error);
    fireEvent.click(screen.getByRole("button", { name: /log out|logout/i }));
    await waitFor(() => expect(screen.queryByTestId("protected")).not.toBeInTheDocument());
    fireEvent.change(screen.getByLabelText(/access token|token/i), { target: { value: "fresh-token" } });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));
    expect(await screen.findByTestId("protected")).toBeInTheDocument();

    await act(async () => { resolveStale(new Response("expired", { status: 401 })); });
    await expect(staleError).resolves.toMatchObject({ status: 401 });
    expect(screen.getByTestId("protected")).toBeInTheDocument();
  });
});
