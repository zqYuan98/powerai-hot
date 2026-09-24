import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AccessGate } from "./AccessGate";
import { SessionProvider } from "./SessionProvider";
import { api } from "../../lib/api";

vi.mock("../../lib/api", () => ({
  api: {
    getSession: vi.fn(),
    createSession: vi.fn(),
    deleteSession: vi.fn(),
  },
  advanceAuthEpoch: vi.fn(),
  getAuthEpoch: vi.fn(() => 0),
  subscribeUnauthorized: vi.fn(() => () => {}),
}));

const mockedApi = vi.mocked(api);
const workspaceSession = { authenticated: true, role: "workspace" as const, mode: "shared", workspace: { name: "PowerAI", subtitle: "Workspace" } };
const adminSession = { ...workspaceSession, role: "admin" as const };
const anonymousSession = { authenticated: false, role: null, mode: "shared", workspace: { name: "PowerAI", subtitle: "Workspace" } };

function renderGate(scope: "workspace" | "admin" = "workspace") {
  return render(
    <SessionProvider>
      <AccessGate scope={scope}><div data-testid="protected">Protected content</div></AccessGate>
    </SessionProvider>,
  );
}

describe("AccessGate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.getSession.mockResolvedValue(anonymousSession);
    mockedApi.createSession.mockResolvedValue(workspaceSession);
    mockedApi.deleteSession.mockResolvedValue(undefined);
  });

  it("does not mount children while locked and offers an unlock form", async () => {
    renderGate();
    await screen.findByRole("button", { name: /unlock/i });
    expect(screen.queryByTestId("protected")).not.toBeInTheDocument();
  });

  it.each([
    [401, /invalid|incorrect|denied/i],
    [429, /too many|rate/i],
    [503, /unavailable|configuration|service/i],
  ])("shows a clear message for HTTP %s unlock errors", async (status, message) => {
    mockedApi.createSession.mockRejectedValue(Object.assign(new Error("failed"), { status }));
    renderGate();
    await screen.findByRole("button", { name: /unlock/i });
    fireEvent.change(screen.getByLabelText(/access token|token/i), { target: { value: "bad" } });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));
    expect(await screen.findByText(message)).toBeInTheDocument();
  });

  it("shows a network error state", async () => {
    mockedApi.createSession.mockRejectedValue(new TypeError("Failed to fetch"));
    renderGate();
    await screen.findByRole("button", { name: /unlock/i });
    fireEvent.change(screen.getByLabelText(/access token|token/i), { target: { value: "bad" } });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));
    expect(await screen.findByText(/network|connection/i)).toBeInTheDocument();
  });

  it("mounts children after a valid workspace session", async () => {
    mockedApi.createSession.mockResolvedValue(workspaceSession);
    renderGate();
    await screen.findByRole("button", { name: /unlock/i });
    fireEvent.change(screen.getByLabelText(/access token|token/i), { target: { value: "valid" } });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));
    expect(await screen.findByTestId("protected")).toBeInTheDocument();
  });

  it("does not allow a workspace session to satisfy admin scope", async () => {
    mockedApi.getSession.mockResolvedValue(workspaceSession);
    renderGate("admin");
    expect(await screen.findByRole("button", { name: /unlock/i })).toBeInTheDocument();
    expect(screen.queryByTestId("protected")).not.toBeInTheDocument();
  });

  it("allows an admin session and logout clears protected content", async () => {
    mockedApi.getSession.mockResolvedValue(adminSession);
    renderGate("admin");
    expect(await screen.findByTestId("protected")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /log out|logout/i }));
    await waitFor(() => expect(screen.queryByTestId("protected")).not.toBeInTheDocument());
  });

  it("keeps the logout control in an overlay without adding shell layout height", async () => {
    mockedApi.getSession.mockResolvedValue(workspaceSession);
    renderGate();
    const logout = await screen.findByRole("button", { name: /log out|logout/i });
    expect(logout.parentElement).toHaveClass("fixed");
  });

  it("shows session expiry when an authenticated fetch returns 401", async () => {
    mockedApi.getSession.mockRejectedValue(Object.assign(new Error("expired"), { status: 401 }));
    renderGate();
    expect(await screen.findByText(/session has expired/i)).toBeInTheDocument();
  });
});
