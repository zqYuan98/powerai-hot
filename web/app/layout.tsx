import "./globals.css";

import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { MobileNav } from "@/components/layout/MobileNav";
import { TopNav } from "@/components/layout/TopNav";

export const metadata: Metadata = {
  title: { default: "电力基建情报站", template: "%s · 电力基建情报站" },
  description: "电力基建商机、政策与行业动态的每日情报",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f5f1" },
    { media: "(prefers-color-scheme: dark)", color: "#111317" },
  ],
};

// 在首帧前恢复主题，避免闪烁
const THEME_SCRIPT = `try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
        >
          跳到正文
        </a>
        <TopNav />
        <main id="main" className="mx-auto max-w-6xl px-4 pt-5 pb-[calc(5rem+env(safe-area-inset-bottom))] md:pb-12">
          {children}
        </main>
        <MobileNav />
      </body>
    </html>
  );
}
