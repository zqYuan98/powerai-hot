import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // /api 代理见 app/api/[...path]/route.ts（运行时读取 BACKEND_URL）
};

export default config;
