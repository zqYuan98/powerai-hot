import { beforeEach, describe, expect, it } from "vitest";
import { getReadIds, markRead, READ_KEY } from "./readStore";

describe("readStore", () => {
  beforeEach(() => localStorage.clear());

  it("marks and reads back ids", () => {
    markRead(1); markRead(2);
    expect(getReadIds().has(1)).toBe(true);
    expect(getReadIds().has(2)).toBe(true);
    expect(getReadIds().has(3)).toBe(false);
  });

  it("dedupes and survives corrupt json", () => {
    markRead(1); markRead(1);
    expect(JSON.parse(localStorage.getItem(READ_KEY)!)).toHaveLength(1);
    localStorage.setItem(READ_KEY, "{corrupt");
    expect(getReadIds().size).toBe(0);
  });

  it("evicts oldest beyond capacity", () => {
    for (let i = 0; i < 1005; i++) markRead(i);
    const ids = getReadIds();
    expect(ids.size).toBe(1000);
    expect(ids.has(0)).toBe(false);
    expect(ids.has(1004)).toBe(true);
  });
});
