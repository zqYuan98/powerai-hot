import { defineConfig, devices } from "@playwright/test";

const workspaceToken = process.env.E2E_WORKSPACE_TOKEN || "e2e-workspace-token-0123456789";
const adminToken = process.env.E2E_ADMIN_TOKEN || "e2e-admin-token-0123456789";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:3011", trace: "retain-on-failure", ...devices["Desktop Chrome"] },
  webServer: [
    {
      command: "python tests/e2e_seed.py && python -m uvicorn main:app --host 127.0.0.1 --port 8011",
      cwd: "../backend",
      port: 8011,
      reuseExistingServer: false,
      env: {
        WORKSPACE_TOKEN: workspaceToken,
        ADMIN_TOKEN: adminToken,
        SESSION_SECRET: "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        APP_ORIGIN: "http://127.0.0.1:3011",
        SESSION_COOKIE_SECURE: "false",
        AUTO_CRAWL_ENABLED: "false",
        DEEPSEEK_API_KEY: "",
        ANTHROPIC_API_KEY: "",
        EMBEDDING_API_KEY: "",
        DATABASE_URL: "sqlite:///./.e2e/powerai-e2e.db",
      },
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3011",
      cwd: ".",
      port: 3011,
      reuseExistingServer: false,
      env: { BACKEND_URL: "http://127.0.0.1:8011" },
    },
  ],
  metadata: { workspaceToken, adminToken },
});
