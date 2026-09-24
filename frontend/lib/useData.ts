"use client";
import { useCallback, useEffect, useRef, useState } from "react";

export type DataSource = "backend" | "mock" | "loading";

/**
 * 先尝试后端，失败则回退到本地 mock。返回数据 + 当前数据来源标识 + 手动刷新函数，
 * 便于在 UI 上标注「演示数据 / 实时数据」。
 *
 * opts.refreshMs：静默轮询间隔——信息流这类"感觉不更新"的页面用它保持新鲜；
 * 页面不可见（切到别的浏览器标签）时跳过请求，避免后台空转。
 * 刷新失败时保留现有数据，不把整页打回空态。
 */
export function useData<T>(
  fetcher: () => Promise<T>,
  fallback: T,
  opts?: { refreshMs?: number },
): [T, DataSource, () => void] {
  const [data, setData] = useState<T>(fallback);
  const [source, setSource] = useState<DataSource>("loading");
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const load = useCallback((initial: boolean) => {
    fetcherRef.current()
      .then((res) => {
        setData(res);
        setSource("backend");
      })
      .catch(() => {
        // 仅首次失败才回退 fallback（通常是 []）；后续刷新失败保留旧数据
        if (initial) {
          setData(fallback);
          setSource("mock");
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load(true);
    if (!opts?.refreshMs) return;
    const timer = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
      load(false);
    }, opts.refreshMs);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const reload = useCallback(() => load(false), [load]);
  return [data, source, reload];
}
