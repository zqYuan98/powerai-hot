import { expect, type Page, test } from "@playwright/test";

async function noHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "页面不应出现横向滚动").toBeLessThanOrEqual(1);
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: `test-results/shots/${test.info().project.name}-${name}.png`, fullPage: true });
}

test("精选 → 详情：商机字段、另有 N 家、评分", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "精选" })).toBeVisible();
  await expect(page.getByText("今天").first()).toBeVisible();
  const card = page.getByRole("article").filter({ hasText: "无人机智能巡检服务招标" });
  await expect(card).toContainText("1,280.5 万元");
  await expect(card).toContainText("另有 1 家信源报道");
  await noHorizontalOverflow(page);
  await shot(page, "feed");

  await card.getByRole("link", { name: /无人机智能巡检服务招标/ }).click();
  await expect(page).toHaveURL(/\/items\/\d+/);
  await expect(page.getByText("商机信息")).toBeVisible();
  await expect(page.getByText("DEMO-2026-0931")).toBeVisible();
  await expect(page.getByText("AI 评分")).toBeVisible();
  await noHorizontalOverflow(page);
  await shot(page, "detail");
});

test("商机看板：筛选与跟进状态持久化", async ({ page }) => {
  await page.goto("/leads?min_voltage_kv=220&sort=amount");
  await expect(page.getByText(/结构化线索 · 共 3 条/)).toBeVisible();
  await expect(page.getByText("12 亿元").filter({ visible: true }).first()).toBeVisible();
  await noHorizontalOverflow(page);
  await shot(page, "leads");

  const saved = (status: string) =>
    page.waitForResponse((r) => r.url().includes("/api/leads/") && r.request().method() === "PATCH" && r.ok()).then(
      async (r) => expect((await r.json()).follow_status).toBe(status),
    );
  await Promise.all([saved("following"), page.getByLabel("跟进状态").filter({ visible: true }).first().selectOption("following")]);
  await page.reload();
  await expect(page.getByLabel("跟进状态").filter({ visible: true }).first()).toHaveValue("following");
  // 还原，保证可重复运行
  await Promise.all([saved("new"), page.getByLabel("跟进状态").filter({ visible: true }).first().selectOption("new")]);
});

test("热点、事件时间线与日报", async ({ page }) => {
  await page.goto("/hot");
  await page.getByRole("link", { name: /无人机智能巡检服务招标/ }).first().click();
  await expect(page.getByText("AI 综述")).toBeVisible();
  await expect(page.getByText(/尚未披露：/)).toBeVisible();
  await noHorizontalOverflow(page);

  await page.goto("/daily");
  await expect(page.getByText("（本期完）")).toBeVisible();
  await expect(page.getByRole("heading", { name: "商机速递" })).toBeVisible();
  await noHorizontalOverflow(page);
  await shot(page, "daily");
});

test("设置页与搜索", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "信源" })).toBeVisible();
  await expect(page.getByText("南方电网供应链").first()).toBeVisible();
  await noHorizontalOverflow(page);
  await shot(page, "settings");

  await page.goto("/search?q=变电站");
  await expect(page.getByText(/条结果/)).toBeVisible();
  await expect(page.getByRole("article").first()).toBeVisible();
});

test("移动端底部导航", async ({ page, isMobile }) => {
  test.skip(!isMobile, "仅移动端");
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "底部导航" });
  await expect(nav).toBeVisible();
  await nav.getByRole("link", { name: "商机" }).click();
  await expect(page).toHaveURL(/\/leads/);
  await nav.getByRole("button", { name: "更多" }).click();
  await page.getByRole("dialog", { name: "更多" }).getByRole("link", { name: "热点" }).click();
  await expect(page).toHaveURL(/\/hot/);
  await expect(page.getByRole("dialog", { name: "更多" })).toBeHidden();
});
