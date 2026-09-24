"use client";

import { useEffect, useState } from "react";

export const MOBILE_QUERY = "(max-width: 768px)";

/** 视口 ≤768px 视为移动端。SSR 首帧按桌面渲染，挂载后立即校正。 */
export function useIsMobile(): boolean {
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    // jsdom（vitest）与极老旧浏览器无 matchMedia：保持桌面布局
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(MOBILE_QUERY);
    const update = () => setMobile(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return mobile;
}
