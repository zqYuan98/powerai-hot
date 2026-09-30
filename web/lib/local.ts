/**
 * 只存在访客自己浏览器里的状态：本机收藏、更新日志已读。
 * localStorage 在隐私模式或被禁用时会抛错，读写都兜底，页面照常可用。
 */
import { useMemo, useSyncExternalStore } from "react";

import changelog from "@/content/changelog.json";

const STARS = "pa_stars";
const CHANGELOG_SEEN = "pa_changelog_seen";
const MAX_STARS = 500;
const listeners = new Set<() => void>();

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // 存不了就只在本次页面内生效
  }
  listeners.forEach((l) => l());
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  window.addEventListener("storage", cb); // 其他标签页的改动
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
}

function useLocal(key: string): string | null {
  return useSyncExternalStore(
    subscribe,
    () => read(key),
    () => null,
  );
}

function parseIds(raw: string | null): number[] {
  try {
    const v: unknown = JSON.parse(raw ?? "[]");
    return Array.isArray(v) ? v.filter((x): x is number => Number.isInteger(x)) : [];
  } catch {
    return [];
  }
}

/** 本机收藏的条目 id，最近收藏的在前。 */
export function useLocalStars(): number[] {
  const raw = useLocal(STARS);
  return useMemo(() => parseIds(raw), [raw]);
}

export function toggleLocalStar(id: number): void {
  const ids = parseIds(read(STARS));
  const next = ids.includes(id) ? ids.filter((x) => x !== id) : [id, ...ids].slice(0, MAX_STARS);
  write(STARS, JSON.stringify(next));
}

export function clearLocalStars(): void {
  write(STARS, "[]");
}

/** 有没有没看过的更新日志（导航上显示小红点）。首屏渲染时按「已看过」处理，避免闪烁。 */
export function useChangelogUnseen(): boolean {
  const seen = useSyncExternalStore(
    subscribe,
    () => read(CHANGELOG_SEEN) ?? "",
    () => changelog.latestVersion,
  );
  return seen < changelog.latestVersion;
}

export function markChangelogSeen(): void {
  if ((read(CHANGELOG_SEEN) ?? "") < changelog.latestVersion) write(CHANGELOG_SEEN, changelog.latestVersion);
}
