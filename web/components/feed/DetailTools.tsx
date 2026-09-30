"use client";

import { Check, Copy, ExternalLink, Share2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui";

/** 一键复制项目编号或原题等文本，带 2 秒成功反馈。 */
export function CopySnippet({ text, label = "复制" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 剪贴板不可用时的静默降级
    }
  }

  return (
    <button
      type="button"
      onClick={onCopy}
      title={label}
      aria-label={label}
      className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-muted transition hover:bg-surface-2 hover:text-ink active:scale-95"
    >
      {copied ? (
        <>
          <Check className="size-3 text-ok" aria-hidden />
          <span className="text-[11px] text-ok">已复制</span>
        </>
      ) : (
        <>
          <Copy className="size-3" aria-hidden />
          <span className="text-[11px]">{label}</span>
        </>
      )}
    </button>
  );
}

/** 详情页顶部快捷操作栏：复制分享链接与查看原文 */
export function DetailHeaderActions({ url, title }: { url: string; title: string }) {
  const [copied, setCopied] = useState(false);

  async function share() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 降级
    }
  }

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="secondary"
        onClick={share}
        className="h-8 px-2.5 text-xs font-normal text-ink-2 hover:text-ink"
        title="复制情报链接"
      >
        {copied ? (
          <>
            <Check className="size-3.5 text-ok" aria-hidden />
            <span>已复制链接</span>
          </>
        ) : (
          <>
            <Share2 className="size-3.5" aria-hidden />
            <span>分享</span>
          </>
        )}
      </Button>

      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line bg-surface px-2.5 text-xs text-ink-2 transition hover:bg-surface-2 hover:text-ink"
      >
        <span>查看原文</span>
        <ExternalLink className="size-3 text-muted" aria-hidden />
      </a>
    </div>
  );
}
