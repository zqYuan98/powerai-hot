import React from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ReportForm from "./ReportForm";
import ReportModule from "./ReportModule";
import { ApiError, type SourceRow } from "../../lib/api";

const mocks = vi.hoisted(() => ({
  submitSourceSubmission: vi.fn(),
  listSourceSubmissions: vi.fn(),
}));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      submitSourceSubmission: mocks.submitSourceSubmission,
      listSourceSubmissions: mocks.listSourceSubmissions,
    },
  };
});

const validValues = {
  name: "Grid AI updates",
  url: "https://example.com/ai",
  reason: "Useful source for the team",
};

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function fillForm() {
  fireEvent.change(screen.getByLabelText(/source name/i), { target: { value: validValues.name } });
  fireEvent.change(screen.getByLabelText(/^url/i), { target: { value: validValues.url } });
  fireEvent.change(screen.getByLabelText(/recommendation reason|reason/i), { target: { value: validValues.reason } });
}

describe("ReportForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.submitSourceSubmission.mockResolvedValue({
      id: 1,
      name: validValues.name,
      url: validValues.url,
      type: "网站",
      reason: validValues.reason,
      status: "寰呭鏍?",
    });
    mocks.listSourceSubmissions.mockResolvedValue([]);
  });

  it("renders editable accessible name, URL, type, and reason fields empty", () => {
    render(<ReportForm />);

    expect(screen.getByLabelText(/source name/i)).toHaveValue("");
    expect(screen.getByLabelText(/^url/i)).toHaveValue("");
    expect(screen.getByLabelText(/source type/i)).toHaveValue("网站");
    expect(screen.getByLabelText(/recommendation reason|reason/i)).toHaveValue("");
    expect(screen.queryByText(/电子商务|sgcc/i)).not.toBeInTheDocument();
  });

  it("rejects required and whitespace-only values without requesting", () => {
    render(<ReportForm />);

    fireEvent.change(screen.getByLabelText(/source name/i), { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: /submit source/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/name.*required|enter.*name/i);
    expect(mocks.submitSourceSubmission).not.toHaveBeenCalled();
  });

  it("disables submit while submitting and ignores duplicate clicks", async () => {
    let resolveRequest: (value: unknown) => void = () => {};
    mocks.submitSourceSubmission.mockReturnValue(new Promise((resolve) => { resolveRequest = resolve; }));
    render(<ReportForm />);
    fillForm();

    const submit = screen.getByRole("button", { name: /submit source/i });
    fireEvent.click(submit);
    fireEvent.click(submit);

    expect(submit).toBeDisabled();
    expect(mocks.submitSourceSubmission).toHaveBeenCalledTimes(1);
    resolveRequest({ id: 2, name: validValues.name, url: validValues.url, type: "网站", status: "寰呭鏍?" });
    await waitFor(() => expect(submit).not.toBeDisabled());
  });

  it("shows the returned pending record and clears fields only after success", async () => {
    render(<ReportForm />);
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: /submit source/i }));

    await waitFor(() => expect(screen.getByText(validValues.name)).toBeInTheDocument());
    expect(screen.getByText(/寰呭鏍?|pending/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/source name/i)).toHaveValue("");
    expect(screen.getByLabelText(/^url/i)).toHaveValue("");
    expect(screen.getByLabelText(/recommendation reason|reason/i)).toHaveValue("");
    expect(mocks.submitSourceSubmission).toHaveBeenCalledWith({
      name: validValues.name,
      url: validValues.url,
      type: "网站",
      reason: validValues.reason,
    });
  });

  it.each([
    [400, { detail: "URL is not allowed" }, /400|not allowed|invalid/i],
    [409, { detail: "source already exists" }, /409|already exists|duplicate/i],
    [422, { detail: "invalid payload" }, /422|invalid|validation/i],
  ])("shows a truthful %s response error and preserves input", async (status, body, message) => {
    mocks.submitSourceSubmission.mockRejectedValue(new ApiError(status, "/sources/submissions", body));
    render(<ReportForm />);
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: /submit source/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(message));
    expect(screen.getByLabelText(/source name/i)).toHaveValue(validValues.name);
    expect(screen.getByLabelText(/^url/i)).toHaveValue(validValues.url);
    expect(screen.getByLabelText(/recommendation reason|reason/i)).toHaveValue(validValues.reason);
  });

  it("shows a network error and preserves input", async () => {
    mocks.submitSourceSubmission.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<ReportForm />);
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: /submit source/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/network|connect|try again/i));
    expect(screen.getByLabelText(/source name/i)).toHaveValue(validValues.name);
  });

  it("ignores a late POST success after the form unmounts", async () => {
    const pending = deferred<{ id: number; name: string; url: string; type: string; status: string }>();
    mocks.submitSourceSubmission.mockReturnValue(pending.promise);
    const onSubmitted = vi.fn();
    const view = render(<ReportForm onSubmitted={onSubmitted} />);
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: /submit source/i }));
    view.unmount();

    await act(async () => {
      pending.resolve({ id: 9, name: "Late source", url: "https://late.example", type: "RSS", status: "待审核" });
      await pending.promise;
    });
    expect(onSubmitted).not.toHaveBeenCalled();
  });

  it("does not surface a late POST failure after the form unmounts", async () => {
    const pending = deferred<never>();
    mocks.submitSourceSubmission.mockReturnValue(pending.promise);
    const view = render(<ReportForm />);
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: /submit source/i }));
    view.unmount();

    await act(async () => {
      pending.reject(new TypeError("offline"));
      await pending.promise.catch(() => undefined);
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("ReportModule", () => {
  type TestSubmissionRows = Array<Omit<SourceRow, "status"> & { status: string }>;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads and renders newest-first pending submissions", async () => {
    mocks.listSourceSubmissions.mockResolvedValue([
      { id: 2, name: "Newest source", url: "https://new.example", type: "RSS", status: "寰呭鏍?", created_at: "2026-07-10T10:00:00Z" },
      { id: 1, name: "Older source", url: "https://old.example", type: "网站", status: "寰呭鏍?", created_at: "2026-07-09T10:00:00Z" },
    ]);
    render(<ReportModule />);

    const list = await screen.findByRole("list", { name: /submitted sources/i });
    const names = within(list).getAllByRole("listitem").map((item) => item.textContent ?? "");
    expect(names[0]).toContain("Newest source");
    expect(names[1]).toContain("Older source");
    expect(within(list).getAllByText(/寰呭鏍?|pending/i)).toHaveLength(2);
  });

  it("renders an explicit list error state", async () => {
    mocks.listSourceSubmissions.mockRejectedValue(new Error("offline"));
    render(<ReportModule />);

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/submissions.*load|try again/i));
  });

  it("keeps the newest StrictMode list response when an older request resolves late", async () => {
    const first = deferred<TestSubmissionRows>();
    const second = deferred<TestSubmissionRows>();
    mocks.listSourceSubmissions.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    render(<React.StrictMode><ReportModule /></React.StrictMode>);
    await waitFor(() => expect(mocks.listSourceSubmissions).toHaveBeenCalledTimes(2));

    await act(async () => {
      second.resolve([{ id: 2, name: "Newest response", url: "https://new.example", type: "RSS", status: "待审核" }]);
      await second.promise;
    });
    expect(await screen.findByText("Newest response")).toBeInTheDocument();

    await act(async () => {
      first.resolve([{ id: 1, name: "Stale response", url: "https://stale.example", type: "RSS", status: "待审核" }]);
      await first.promise;
    });
    await waitFor(() => expect(screen.queryByText("Stale response")).not.toBeInTheDocument());
  });

  it("does not update an unmounted list when its request resolves", async () => {
    const pending = deferred<TestSubmissionRows>();
    mocks.listSourceSubmissions.mockReturnValue(pending.promise);
    const view = render(<ReportModule />);
    view.unmount();

    await act(async () => {
      pending.resolve([{ id: 3, name: "Unmounted response", url: "https://gone.example", type: "RSS", status: "待审核" }]);
      await pending.promise;
    });
    expect(screen.queryByText("Unmounted response")).not.toBeInTheDocument();
  });
});
