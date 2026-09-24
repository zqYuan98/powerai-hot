import React from "react";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SubscribeModule from "./SubscribeModule";
import { api } from "../../lib/api";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      listArticles: vi.fn(),
      subscriptionHits: vi.fn(),
      listSources: vi.fn(),
    },
  };
});

const mockedApi = vi.mocked(api);

describe("SubscribeModule", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.subscriptionHits.mockImplementation(() => new Promise(() => {}));
    mockedApi.listSources.mockResolvedValue([]);
  });

  it("does not render the duplicate source-report panel", () => {
    render(
      <SubscribeModule
        sub={{ keywords: [], notify_in_app: false, notify_bid_deadline: false, notify_email_digest: false }}
        subDown={false}
        onSave={() => {}}
      />,
    );

    expect(screen.queryByText("信源报告")).not.toBeInTheDocument();
    expect(screen.queryByText("我的报告")).not.toBeInTheDocument();
  });

  it("loads bounded subscription hits and never requests the full feed", async () => {
    render(
      <SubscribeModule
        sub={{ keywords: ["储能"], notify_in_app: false, notify_bid_deadline: false, notify_email_digest: false }}
        subDown={false}
        onSave={() => {}}
      />,
    );

    expect(mockedApi.subscriptionHits).toHaveBeenCalledWith(3);
    expect(mockedApi.listArticles).not.toHaveBeenCalled();
    expect(mockedApi.listSources).not.toHaveBeenCalled();
  });
});
