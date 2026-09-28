"use client";

import { useState } from "react";

import { Button } from "@/components/ui";
import { send } from "@/lib/api.client";

/** 笔记：条目笔记走 /items，商机跟进备注走 /leads。 */
export function NoteEditor({
  endpoint,
  field,
  initial,
  placeholder,
}: {
  endpoint: string;
  field: "note" | "follow_note";
  initial: string | null;
  placeholder: string;
}) {
  const [text, setText] = useState(initial ?? "");
  const [saved, setSaved] = useState(initial ?? "");
  const [state, setState] = useState<"idle" | "saving" | "error">("idle");

  async function save() {
    setState("saving");
    try {
      await send(endpoint, { method: "PATCH", body: { [field]: text } });
      setSaved(text);
      setState("idle");
    } catch {
      setState("error");
    }
  }

  return (
    <div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        rows={3}
        className="w-full resize-y rounded-md border border-line bg-surface p-2.5 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none"
      />
      <div className="mt-1.5 flex items-center justify-end gap-2">
        {state === "error" ? <span className="text-xs text-danger">保存失败</span> : null}
        {text !== saved ? <span className="text-xs text-muted">未保存</span> : null}
        <Button onClick={save} disabled={state === "saving" || text === saved} className="h-8">
          {state === "saving" ? "保存中…" : "保存"}
        </Button>
      </div>
    </div>
  );
}
