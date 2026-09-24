import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "电力AI-hot · 电力行业 AI 情报聚合平台",
  description: "面向电力基建行业的 AI 情报聚合与知识管理平台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
