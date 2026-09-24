"use client";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, type CardOut } from "../../lib/api";

function CollectionCard({ card, onSaved }: { card: CardOut; onSaved: () => void }) {
  const [draft, setDraft] = useState(card.note ?? "");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  const cardRef = useRef(card);
  useEffect(() => () => { mounted.current = false; }, []);
  useEffect(() => {
    cardRef.current = card;
    setDraft(card.note ?? "");
  }, [card]);
  const title = card.article?.title_zh || card.article?.title || `#${card.article_id}`;
  const save = async () => {
    setSaving(true); setError(null);
    try { await api.patchCard(cardRef.current.id, { note: draft }); if (!mounted.current) return; setSaving(false); setEditing(false); onSaved(); }
    catch { if (!mounted.current) return; setSaving(false); setError("笔记保存失败，请稍后重试"); }
  };
  return <article style={{ border: "1px solid rgba(148,163,184,.16)", borderRadius: 12, padding: 16, marginBottom: 12, color: "#CBD5E1" }}>
    <div style={{ color: "#F2F5FA", fontWeight: 700 }}>{title}</div>
    {card.problem && <p>问题：{card.problem}</p>}
    {editing ? <div>
      <textarea aria-label={`笔记：${title}`} value={draft} onChange={e => { setDraft(e.target.value); setError(null); }} rows={3} style={{ width: "100%", padding: 8 }} />
      {error && <div role="alert" style={{ color: "#FCA5A5" }}>{error}</div>}
      <button type="button" disabled={saving} onClick={save}>{saving ? "保存中…" : "保存"}</button>
      <button type="button" onClick={() => { setDraft(card.note ?? ""); setError(null); setEditing(false); }}>取消</button>
    </div> : <button type="button" onClick={() => setEditing(true)} style={{ display: "block", marginTop: 10, width: "100%", textAlign: "left", color: card.note ? "#A9D8D3" : "#8290A8", background: "transparent", border: "1px dashed rgba(52,224,216,.25)", padding: 9 }}>
      {card.note || "点击添加个人笔记"}
    </button>}
  </article>;
}

export default function WorkspaceCollection() {
  const [cards, setCards] = useState<CardOut[]>([]); const [error, setError] = useState<string | null>(null); const [loaded, setLoaded] = useState(false); const generation = useRef(0);
  const load = useCallback(async () => { const g = ++generation.current; try { const rows = await api.listCards(); if (g !== generation.current) return; setCards(rows); setError(null); setLoaded(true); } catch { if (g !== generation.current) return; setError("收藏加载失败，请稍后重试"); setLoaded(true); } }, []);
  useEffect(() => {
    void load();
    const cleanupGeneration = generation.current;
    return () => {
      if (generation.current === cleanupGeneration) generation.current += 1;
    };
  }, [load]);
  return <main style={{ flex: 1, padding: 24, overflow: "auto" }}><h2 style={{ color: "#F2F5FA" }}>工作空间收藏</h2>
    {error && <div role="alert" style={{ color: "#FCA5A5" }}>{error} <button type="button" onClick={load}>重新加载</button></div>}
    {!error && loaded && cards.length === 0 && <p style={{ color: "#828EA3" }}>还没有收藏内容。去情报信息流收藏一条知识卡片吧。</p>}
    {cards.map(card => <CollectionCard key={card.id} card={card} onSaved={load} />)}
  </main>;
}
