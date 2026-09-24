import { test, expect } from "@playwright/test";
import { createHmac } from "node:crypto";

const workspaceToken = process.env.E2E_WORKSPACE_TOKEN || "e2e-workspace-token-0123456789";
const adminToken = process.env.E2E_ADMIN_TOKEN || "e2e-admin-token-0123456789";
const sessionSecret = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";

async function installWorkspaceSession(context: import("@playwright/test").BrowserContext) {
  const now = Math.floor(Date.now() / 1000);
  const payload = Buffer.from(JSON.stringify({ v: 1, role: "workspace", iat: now, exp: now + 3600 })).toString("base64url");
  const signature = createHmac("sha256", Buffer.from(sessionSecret, "base64url")).update(payload).digest("base64url");
  await context.addCookies([{
    name: "powerai_session", value: `${payload}.${signature}`,
    domain: "127.0.0.1", path: "/", httpOnly: true, secure: false, sameSite: "Strict",
  }]);
}

async function unlockWorkspace(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.locator("#access-token").fill(workspaceToken);
  await page.getByRole("button", { name: "Unlock" }).click();
  await expect(page.getByRole("navigation")).toBeVisible();
}

test("employee feed searches, paginates and preserves the loaded list after detail", async ({ page }) => {
  await unlockWorkspace(page);
  const search = page.getByRole("searchbox", { name: "搜索情报" });
  await search.fill("唯一检索目标");
  await search.press("Enter");
  await expect(page.getByText("唯一检索目标情报")).toBeVisible();

  await page.getByRole("button", { name: /搜索：唯一检索目标/ }).click();
  await page.getByRole("button", { name: /加载更多/ }).click();
  const detailTitle = page.getByText("E2E 分页情报 35", { exact: true });
  await expect(detailTitle).toBeVisible();
  await detailTitle.click();
  await expect(page).toHaveURL(/\/items\/\d+$/);
  await page.getByRole("link", { name: "返回情报信息流" }).click();
  await expect(page.getByText("E2E 分页情报 35", { exact: true })).toBeVisible();
});

test("tampered workspace session relocks the employee portal", async ({ page, context }) => {
  await unlockWorkspace(page);
  const refresh = page.getByRole("button", { name: /最新入库/ });
  await expect(refresh).toBeVisible();
  const session = (await context.cookies()).find((cookie) => cookie.name === "powerai_session");
  expect(session).toBeTruthy();
  await context.addCookies([{ ...session!, value: "tampered" }]);

  await refresh.click();

  await expect(page.getByRole("heading", { name: "Unlock workspace" })).toBeVisible();
  await expect(page.getByText(/Your session has expired/)).toBeVisible();
});

test("employee portal exposes business modules and real knowledge", async ({ page }) => {
  await page.goto("/");
  await page.locator("#access-token").fill(workspaceToken);
  await page.getByRole("button", { name: "Unlock" }).click();
  await expect(page.getByRole("navigation")).toBeVisible();
  await expect(page.getByRole("navigation").locator("button")).toHaveCount(6);
  await expect(page.getByRole("navigation").getByText(/流水线|来源管理|管理后台|系统设置/)).toHaveCount(0);
  await page.getByRole("navigation").locator("button").nth(3).click();
  await expect(page.getByRole("heading", { name: /业务知识/ })).toBeVisible();
  await page.getByPlaceholder(/搜索/).fill("E基建");
  await expect(page.getByRole("heading", { name: /E基建/ })).toBeVisible();
  await expect(page.getByText(/陈算法|Chen Algorithm/)).toHaveCount(0);
});

test("workspace cannot enter admin, admin can", async ({ page }) => {
  await page.goto("/admin");
  await page.locator("#access-token").fill(workspaceToken);
  await page.getByRole("button", { name: "Unlock" }).click();
  await expect(page.locator("p[role=alert]")).toContainText("Invalid access token");
  await page.locator("#access-token").fill(adminToken);
  await page.getByRole("button", { name: "Unlock" }).click();
  await expect(page.getByRole("navigation")).toBeVisible();
  await expect(page.getByRole("navigation").locator("button")).toHaveCount(4);
  await page.getByRole("navigation").locator("button").nth(3).click();
  await expect(page.getByRole("heading", { name: /内容运营/ })).toBeVisible();
  await page.getByRole("button", { name: "立即生成日报" }).click();
  await expect(page.getByText(/已提交日报生成任务/)).toBeVisible();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByRole("heading", { name: "Admin access required" })).toBeVisible();
});

test("employee can submit a pending source", async ({ page, context }) => {
  await installWorkspaceSession(context);
  await page.goto("/");
  await expect(page.getByRole("navigation")).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: /信源推荐/ }).click();
  await page.locator("#source-name").fill("E2E 来源");
  await page.locator("#source-url").fill("https://93.184.216.34/e2e-source");
  await page.locator("#source-reason").fill("E2E 验证");
  await page.getByRole("button", { name: "Submit source" }).click();
  await expect(page.getByText("Submission received")).toBeVisible();
});
