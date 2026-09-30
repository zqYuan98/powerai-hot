"use client";

import { useEffect } from "react";

import { markChangelogSeen } from "@/lib/local";

/** 打开更新日志即视为已读，导航上的小红点随之消失。 */
export function MarkChangelogSeen() {
  useEffect(() => markChangelogSeen(), []);
  return null;
}
