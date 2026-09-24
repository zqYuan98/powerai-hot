/** 已读状态：仅当前浏览器（localStorage），容量 1000 FIFO；SSR/隐私模式安全降级。 */
export const READ_KEY = "pai:read:v1";
const CAP = 1000;

function load(): number[] {
  try {
    const raw = typeof localStorage === "undefined" ? null : localStorage.getItem(READ_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr.filter((n) => typeof n === "number") : [];
  } catch {
    return [];
  }
}

export function getReadIds(): Set<number> {
  return new Set(load());
}

export function markRead(id: number): Set<number> {
  const arr = load().filter((existing) => existing !== id);
  arr.push(id);
  const trimmed = arr.slice(-CAP);
  try {
    localStorage.setItem(READ_KEY, JSON.stringify(trimmed));
  } catch {
    /* 隐私模式配额满等：静默降级 */
  }
  return new Set(trimmed);
}
