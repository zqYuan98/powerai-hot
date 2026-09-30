"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Card, Field, inputClass } from "@/components/ui";
import { send } from "@/lib/api.client";
import type { KnowledgeSubmitAck } from "@/lib/types";

/** 管理员收录：粘贴公众号或网页链接；抓不到正文时展开「粘贴正文」一起提交。 */
export function SubmitForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [note, setNote] = useState("");
  const [paste, setPaste] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [state, setState] = useState<{ kind: "idle" | "sending" | "ok" | "error"; text?: string; id?: number }>({
    kind: "idle",
  });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setState({ kind: "sending" });
    try {
      const ack = await send<KnowledgeSubmitAck>("/knowledge", {
        body: { url, note: note || null, title: title || null, content: paste && content ? content : null },
      });
      setState({
        kind: "ok",
        id: ack.id,
        text: ack.existed
          ? content
            ? "这篇之前收录过，已用粘贴的正文重新处理。"
            : "这篇之前已经收录过。"
          : "已加入处理队列，通常半分钟内出卡片（在「待处理」里能看到进度）。",
      });
      setUrl("");
      setNote("");
      setTitle("");
      setContent("");
      setPaste(false);
      router.refresh();
    } catch (err) {
      setState({ kind: "error", text: err instanceof Error ? err.message : "收录失败" });
    }
  }

  return (
    <Card className="mb-5 p-4">
      <form onSubmit={submit} className="space-y-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <Field label="收录文章（公众号或网页链接）" className="flex-1">
            <input
              type="url"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://mp.weixin.qq.com/s/…"
              className={inputClass}
            />
          </Field>
          <Field label="收录备注（仅自己可见，选填）" className="sm:w-64">
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="为什么收、给哪个项目用" className={inputClass} />
          </Field>
          <Button type="submit" variant="primary" disabled={state.kind === "sending" || !url}>
            <Plus className="size-4" aria-hidden />
            {state.kind === "sending" ? "收录中…" : "收录"}
          </Button>
        </div>
        {paste ? (
          <div className="grid gap-2">
            <Field label="标题（选填，不填取正文第一行）">
              <input value={title} onChange={(e) => setTitle(e.target.value)} className={inputClass} />
            </Field>
            <Field label="正文">
              <textarea
                rows={6}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="在微信里打开文章 → 全选复制正文粘贴到这里"
                className="w-full resize-y rounded-md border border-line bg-surface p-2.5 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none"
              />
            </Field>
          </div>
        ) : (
          <button type="button" onClick={() => setPaste(true)} className="text-xs text-accent hover:underline">
            公众号打不开或抓不到正文？粘贴正文一起提交
          </button>
        )}
        {state.kind === "ok" ? (
          <p className="text-sm text-ok">
            {state.text}{" "}
            <Link href={`/knowledge/${state.id}`} className="underline">
              查看
            </Link>
          </p>
        ) : null}
        {state.kind === "error" ? <p className="text-sm text-danger">{state.text}</p> : null}
      </form>
    </Card>
  );
}
