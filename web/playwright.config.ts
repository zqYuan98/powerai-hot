import { defineConfig, devices } from "@playwright/test";

/**
 * E2E 针对「已启动的 API + Web」运行，数据来自 server/tests/e2e_seed.py 写入的测试库：
 *   E2E_BASE_URL=http://127.0.0.1:3011 npx playwright test
 */
export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000",
    locale: "zh-CN",
    timezoneId: "Asia/Shanghai",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } } },
    { name: "mobile", use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } } },
  ],
});
