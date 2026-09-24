import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { adminNavItems, employeeNavItems } from "./navConfig";
import WorkspaceIdentity from "../WorkspaceIdentity";

vi.mock("../auth/SessionProvider", () => ({
  useSession: () => ({
    workspace: { name: "能源情报中心", subtitle: "华东共享工作区" },
    role: "admin",
    mode: "shared",
  }),
}));

describe("navigation configuration", () => {
  it("exposes the six employee destinations", () => {
    expect(employeeNavItems.map((item) => item.key)).toEqual([
      "feed",
      "digest",
      "research",
      "knowledge",
      "sub",
      "report",
    ]);
  });

  it("exposes the four admin destinations", () => {
    expect(adminNavItems.map((item) => item.key)).toEqual([
      "overview",
      "pipeline",
      "sources",
      "content",
    ]);
  });

  it("keeps admin language out of employee labels", () => {
    const labels = employeeNavItems.map((item) => item.label).join(" ");
    expect(labels).not.toMatch(/流水线|信源管理|管理后台|系统脉搏/);
  });
});

describe("workspace identity", () => {
  it("renders session workspace metadata rather than a fake individual", () => {
    render(React.createElement(WorkspaceIdentity));

    expect(screen.getByText("能源情报中心")).toBeInTheDocument();
    expect(screen.getByText("华东共享工作区")).toBeInTheDocument();
    expect(screen.getByText(/admin/i)).toBeInTheDocument();
    expect(screen.getByText(/shared/i)).toBeInTheDocument();
    expect(screen.queryByText("陈算法")).not.toBeInTheDocument();
  });
});
