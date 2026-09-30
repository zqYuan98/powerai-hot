"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button, Card, Field, inputClass } from "@/components/ui";
import { send } from "@/lib/api.client";
import type { FeedbackAck } from "@/lib/types";

const MAX_TEXT = 2000;
const DRAFT_KEY = "pa_feedback_draft";

type Draft = { content: string; contact: string };

function loadDraft(): Draft | null {
  try {
    const d: unknown = JSON.parse(localStorage.getItem(DRAFT_KEY) ?? "null");
    if (d && typeof d === "object") {
      const { content, contact } = d as Partial<Draft>;
      return { content: String(content ?? ""), contact: String(contact ?? "") };
    }
  } catch {}
  return null;
}

function saveDraft(d: Draft | null): void {
  try {
    if (d && (d.content || d.contact)) localStorage.setItem(DRAFT_KEY, JSON.stringify(d));
    else localStorage.removeItem(DRAFT_KEY);
  } catch {}
}

/** 反馈表单：草稿自动存本机，网络失败不丢；来源页面取 ?from= 或站内 referrer。 */
export function FeedbackForm({ from }: { from?: string }) {
  const [draft, setDraft] = useState<Draft>({ content: "", contact: "" });
  const [pageUrl, setPageUrl] = useState(from ?? "");
  const [state, setState] = useState<{ kind: "idle" | "sending" | "done" | "error"; message?: string; id?: number }>({
    kind: "idle",
  });

  useEffect(() => {
    const saved = loadDraft();
    // 恢复草稿与来源页只能在客户端做（localStorage、document.referrer）
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (saved) setDraft(saved);
    if (!from && document.referrer.startsWith(location.origin)) {
      const ref = new URL(document.referrer);
      if (ref.pathname !== "/feedback") setPageUrl(ref.pathname + ref.search);
    }
  }, [from]);

  useEffect(() => {
    const t = setTimeout(() => saveDraft(draft), 400);
    return () => clearTimeout(t);
  }, [draft]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (draft.content.trim().length < 2) return setState({ kind: "error", message: "请写下反馈内容。" });
    setState({ kind: "sending" });
    try {
      const ack = await send<FeedbackAck>("/site/feedback", {
        body: { content: draft.content, contact: draft.contact || null, page_url: pageUrl || null },
      });
      saveDraft(null);
      setDraft({ content: "", contact: "" });
      setState({ kind: "done", id: ack.id });
    } catch (err) {
      setState({ kind: "error", message: `${err instanceof Error ? err.message : "提交失败"}。草稿已保存在本机，稍后再试。` });
    }
  }

  if (state.kind === "done") {
    return (
      <Card className="mt-6 px-6 py-12 text-center">
        <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-accent text-white">
          <Check className="size-6" aria-hidden />
        </div>
        <h2 className="mt-5 text-lg font-semibold text-ink">收到了，谢谢你</h2>
        <p className="mt-1.5 text-sm text-muted">
          反馈编号 <span className="font-mono font-semibold text-ink">#{state.id}</span>，需要回复时会引用这个编号。
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <Link href="/" className="flex h-9 items-center rounded-md bg-ink px-4 text-sm font-medium text-bg hover:opacity-90">
            回到精选
          </Link>
          <Button onClick={() => setState({ kind: "idle" })}>再写一条</Button>
        </div>
      </Card>
    );
  }

  const canSend = draft.content.trim().length >= 2 && state.kind !== "sending";
  return (
    <form onSubmit={submit} className="mt-6">
      <Card className="space-y-4 p-4 sm:p-5">
        <Field label="想说点什么？">
          <div className="relative">
            <textarea
              required
              rows={8}
              maxLength={MAX_TEXT}
              value={draft.content}
              onChange={(e) => setDraft({ ...draft, content: e.target.value })}
              placeholder="例如：希望增加某省电力公司的招标公告；某条商机的截止时间和原文不一致……"
              className="block w-full resize-y rounded-md border border-line bg-surface px-3 pt-2.5 pb-7 text-sm leading-relaxed text-ink placeholder:text-muted focus:border-accent focus:outline-none"
            />
            <span className="pointer-events-none absolute right-3 bottom-2 font-mono text-[11px] text-muted">
              {draft.content.length} / {MAX_TEXT}
            </span>
          </div>
        </Field>
        <Field label="联系方式（选填，邮箱或微信，需要回复时用）">
          <input
            value={draft.contact}
            maxLength={200}
            onChange={(e) => setDraft({ ...draft, contact: e.target.value })}
            className={inputClass}
            autoComplete="email"
          />
        </Field>
        {pageUrl ? (
          <p className="text-xs text-muted">
            来自页面：<span className="font-mono">{pageUrl}</span>{" "}
            <button type="button" onClick={() => setPageUrl("")} className="text-accent hover:underline">
              不附带
            </button>
          </p>
        ) : null}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
          <p className="text-xs text-muted">请不要填写密码、token 等敏感信息。</p>
          <Button type="submit" variant="primary" disabled={!canSend}>
            {state.kind === "sending" ? "提交中…" : "提交反馈"}
          </Button>
        </div>
        {state.kind === "error" ? <p className="text-sm text-danger">{state.message}</p> : null}
      </Card>
    </form>
  );
}
