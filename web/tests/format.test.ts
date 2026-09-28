import { describe, expect, it } from "vitest";

import { dayKey, dayLabel, deadlineInfo, formatAmount, groupByDay, relativeTime } from "@/lib/format";

const NOW = new Date("2026-09-28T04:00:00Z"); // 北京时间 12:00

describe("format", () => {
  it("按北京时间切日", () => {
    expect(dayKey("2026-09-27T16:30:00Z")).toBe("2026-09-28");
    expect(dayKey("2026-09-27T15:59:00Z")).toBe("2026-09-27");
  });

  it("日期分组标题", () => {
    expect(dayLabel("2026-09-28", NOW)).toBe("今天");
    expect(dayLabel("2026-09-27", NOW)).toBe("昨天");
    expect(dayLabel("2026-09-25", NOW)).toMatch(/^9月25日 周五$/);
  });

  it("金额换算", () => {
    expect(formatAmount("1280.5")).toBe("1,280.5 万元");
    expect(formatAmount(25000)).toBe("2.5 亿元");
    expect(formatAmount(null)).toBeNull();
  });

  it("截止倒计时分级", () => {
    expect(deadlineInfo("2026-09-28T10:00:00Z", NOW)).toEqual({ text: "6 小时后截止", level: "urgent" });
    expect(deadlineInfo("2026-10-03T04:00:00Z", NOW)?.level).toBe("soon");
    expect(deadlineInfo("2026-09-01T00:00:00Z", NOW)?.level).toBe("past");
    expect(deadlineInfo(null, NOW)).toBeNull();
  });

  it("相对时间", () => {
    expect(relativeTime("2026-09-28T03:30:00Z", NOW)).toBe("30 分钟前");
    expect(relativeTime("2026-09-27T04:00:00Z", NOW)).toBe("1 天前");
  });

  it("按天分组保持顺序", () => {
    const groups = groupByDay([
      { first_seen_at: "2026-09-28T03:00:00Z" },
      { first_seen_at: "2026-09-28T01:00:00Z" },
      { first_seen_at: "2026-09-27T03:00:00Z" },
    ]);
    expect(groups.map((g) => [g.key, g.items.length])).toEqual([
      ["2026-09-28", 2],
      ["2026-09-27", 1],
    ]);
  });
});
