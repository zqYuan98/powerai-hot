import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import EmployeeSidebar from "./EmployeeSidebar";
import AdminSidebar from "./AdminSidebar";

vi.mock("../WorkspaceIdentity", () => ({ default: () => <div data-testid="identity" /> }));

describe("shell navigation semantics", () => {
  it("exposes employee navigation and marks the active page", () => {
    render(<EmployeeSidebar module="feed" go={() => {}} notifCount={null} />);
    expect(screen.getByRole("navigation", { name: /employee|workspace/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /情报流/ })).toHaveAttribute("aria-current", "page");
  });

  it("exposes admin navigation and marks the active page", () => {
    render(<AdminSidebar module="overview" go={() => {}} />);
    expect(screen.getByRole("navigation", { name: /admin/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /管理概览/ })).toHaveAttribute("aria-current", "page");
  });

  it("hides the workspace return link for a single-admin deployment", () => {
    render(<AdminSidebar module="overview" go={() => {}} singleAdmin />);
    expect(screen.queryByRole("link", { name: "返回工作区" })).not.toBeInTheDocument();
  });
});
