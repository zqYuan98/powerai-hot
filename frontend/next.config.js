/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // 把 /api/* 代理到后端。默认直连本地后端，无需设置环境变量；
    // 需要改地址时再用 BACKEND_URL 覆盖。
    const api = process.env.BACKEND_URL || "http://127.0.0.1:8010";
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};
module.exports = nextConfig;
