"use client";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, CardOut } from "../../lib/api";
import { Book } from "../icons";

const CATS = ["全部", "视觉/OCR", "大模型", "电力AI应用", "其他"];
const CARD_CATS = CATS.filter((c) => c !== "全部");

const STATUS_STYLE: Record<string, [string, string]> = {
  完成: ["#6EE7B7", "rgba(52,211,153,0.12)"],
  生成中: ["#FCD34D", "rgba(251,191,36,0.12)"],
  失败: ["#FCA5A5", "rgba(251,113,133,0.12)"],
};

function Field({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
      <span style={{ flexShrink: 0, fontSize: 11, fontWeight: 700, color: "#8EA0C0", background: "rgba(148,163,184,0.10)", padding: "3px 8px", borderRadius: 6, marginTop: 1 }}>{label}</span>
      <span style={{ fontSize: 13, lineHeight: 1.7, color: "#C4CDDD" }}>{value}</span>
    </div>
  );
}

function CardItem({ card, onChanged }: { card: CardOut; onChanged: () => void }) {
  const [note, setNote] = useState(card.note ?? "");
  const [editing, setEditing] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savingCat, setSavingCat] = useState(false);
  const [catError, setCatError] = useState<string | null>(null);
  const mounted = useRef(true);
  const [fg, bg] = STATUS_STYLE[card.status] ?? STATUS_STYLE["生成中"];
  const title = card.article?.title_zh || card.article?.title || `#${card.article_id}`;

  useEffect(() => () => { mounted.current = false; }, []);

  const changeCategory = async (next: string) => {
    if (next === card.category) return;
    setSavingCat(true);
    try {
      await api.patchCard(card.id, { category: next });
      if (!mounted.current) return;
      setCatError(null);
      onChanged();
    } catch {
      if (!mounted.current) return;
      setCatError("分类修改失败，请稍后重试");
    } finally {
      if (mounted.current) setSavingCat(false);
    }
  };

  const saveNote = async () => {
    try {
      await api.patchCard(card.id, { note });
      if (!mounted.current) return;
      setSaveError(null);
      setEditing(false);
      onChanged();
    } catch {
      if (!mounted.current) return;
      setSaveError("笔记保存失败，请稍后重试");
    }
  };

  return (
    <div style={{ background: "linear-gradient(180deg, rgba(20,27,42,0.9), rgba(15,20,32,0.9))", border: "1px solid rgba(148,163,184,0.12)", borderRadius: 14, padding: "18px 20px", display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <select
          value={card.category}
          onChange={(e) => changeCategory(e.target.value)}
          disabled={savingCat}
          title="修改卡片分类"
          aria-label="卡片分类"
          style={{ fontSize: 11, fontWeight: 700, color: "#B79CFF", background: "rgba(167,139,250,0.14)", border: "1px solid rgba(167,139,250,0.3)", padding: "3px 6px", borderRadius: 7, cursor: savingCat ? "wait" : "pointer", appearance: "auto" }}
        >
          {(CARD_CATS.includes(card.category) ? CARD_CATS : [card.category, ...CARD_CATS]).map((c) => (
            <option key={c} value={c} style={{ color: "#0A0E17" }}>{c}</option>
          ))}
        </select>
        {catError && <span style={{ fontSize: 11, color: "#FCA5A5" }}>{catError}</span>}
        <span style={{ fontSize: 11, fontWeight: 700, color: fg, background: bg, padding: "3px 9px", borderRadius: 7 }}>{card.status}</span>
        {card.status === "失败" && (
          <span style={{ fontSize: 11, fontWeight: 600, color: "#FCD34D", background: "rgba(251,191,36,0.12)", border: "1px solid rgba(251,191,36,0.22)", padding: "3px 10px", borderRadius: 7 }}>
            等待管理员处理
          </span>
        )}
        {card.article?.url && (
          <a href={card.article.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}
            style={{ marginLeft: "auto", fontSize: 12, color: "#9FD0FF", textDecoration: "none" }}>原文 ↗</a>
        )}
      </div>
      <div style={{ fontSize: 15.5, fontWeight: 700, color: "#F2F5FA", lineHeight: 1.45 }}>{title}</div>
      <Field label="问题" value={card.problem} />
      <Field label="方法" value={card.method} />
      <Field label="结论" value={card.conclusion} />
      <Field label="电力关联" value={card.power_relevance} />
      {editing ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <textarea value={note} onChange={(e) => { setNote(e.target.value); setSaveError(null); }} rows={3}
            style={{ width: "100%", resize: "vertical", fontSize: 13, lineHeight: 1.6, color: "#E6EBF4", background: "rgba(148,163,184,0.06)", border: "1px solid rgba(52,224,216,0.3)", borderRadius: 9, padding: "9px 12px", fontFamily: "inherit" }} />
          {saveError && <div style={{ color: "#FCA5A5", fontSize: 12 }}>{saveError}</div>}
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={saveNote} style={{ fontSize: 12, fontWeight: 600, color: "#0A0E17", background: "linear-gradient(145deg,#34E0D8,#1FB6C9)", border: "none", padding: "6px 14px", borderRadius: 8, cursor: "pointer" }}>保存</button>
            <button onClick={() => { setEditing(false); setNote(card.note ?? ""); }} style={{ fontSize: 12, color: "#94A0B5", background: "transparent", border: "1px solid rgba(148,163,184,0.2)", padding: "6px 14px", borderRadius: 8, cursor: "pointer" }}>取消</button>
          </div>
        </div>
      ) : (
        <div onClick={() => setEditing(true)} style={{ cursor: "text", fontSize: 12.5, lineHeight: 1.6, color: card.note ? "#A9D8D3" : "#5E6A82", background: "rgba(52,224,216,0.04)", border: "1px dashed rgba(52,224,216,0.2)", borderRadius: 9, padding: "8px 12px" }}>
          {card.note || "点击添加个人笔记…"}
        </div>
      )}
    </div>
  );
}

export default function LibraryModule() {
  const [cat, setCat] = useState("全部");
  const [q, setQ] = useState("");
  const queryRef = useRef("");
  const [cards, setCards] = useState<CardOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [listLoaded, setListLoaded] = useState(false);
  const loadGeneration = useRef(0);

  useEffect(() => {
    loadGeneration.current += 1;
    return () => { loadGeneration.current += 1; };
  }, []);

  const load = useCallback(async () => {
    const generation = ++loadGeneration.current;
    try {
      const rows = await api.listCards(cat === "全部" ? undefined : cat, queryRef.current || undefined);
      if (generation !== loadGeneration.current) return;
      setCards(rows);
      setError(null);
      setListLoaded(true);
    } catch {
      if (generation !== loadGeneration.current) return;
      setCards([]);
      setError("知识库加载失败，请稍后重试");
      setListLoaded(true);
    }
  }, [cat]);

  useEffect(() => { void load(); }, [load]);

  return (
    <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", position: "relative", zIndex: 1 }}>
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 14, padding: "18px 26px", borderBottom: "1px solid rgba(148,163,184,0.10)", flexShrink: 0 }}>
        <Book />
        <span style={{ fontSize: 17, fontWeight: 700, color: "#F2F5FA" }}>我的知识库</span>
        <span style={{ fontSize: 12, color: "#6B7689" }}>收藏自动生成结构化卡片 · 可搜索 · 可补笔记</span>
        <input value={q} onChange={(e) => { queryRef.current = e.target.value; setQ(e.target.value); }} onKeyDown={(e) => e.key === "Enter" && void load()}
          placeholder="搜索标题/问题/方法/结论/笔记，回车检索"
          style={{ marginLeft: "auto", flex: "1 1 220px", maxWidth: 300, fontSize: 13, color: "#E6EBF4", background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.14)", borderRadius: 10, padding: "9px 14px" }} />
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, padding: "12px 26px 0", flexShrink: 0 }}>
        {CATS.map((c) => {
          const on = cat === c;
          return (
            <span key={c} onClick={() => setCat(c)}
              style={{ fontSize: 13, fontWeight: on ? 700 : 500, cursor: "pointer", padding: "7px 14px", borderRadius: 9, color: on ? "#0A0E17" : "#94A0B5", background: on ? "linear-gradient(145deg,#34E0D8,#1FB6C9)" : "rgba(148,163,184,0.08)" }}>
              {c}
            </span>
          );
        })}
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: "16px 26px 26px", display: "flex", flexDirection: "column", gap: 14 }}>
        {cards.map((c) => <CardItem key={c.id} card={c} onChanged={load} />)}
        {error && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "#5E6A82", gap: 12, textAlign: "center", padding: "80px 0" }}>
            <Book />
            <div style={{ fontSize: 15, color: "#FCA5A5" }}>{error}</div>
            <button type="button" onClick={load} style={{ fontSize: 12, color: "#9FD0FF", background: "rgba(59,158,255,0.12)", border: "1px solid rgba(59,158,255,0.22)", padding: "7px 14px", borderRadius: 8, cursor: "pointer" }}>重试加载</button>
          </div>
        )}
        {!error && listLoaded && cards.length === 0 && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "#5E6A82", gap: 12, textAlign: "center", padding: "80px 0" }}>
            <Book />
            <div style={{ fontSize: 15, color: "#828EA3" }}>知识库还是空的</div>
            <div style={{ fontSize: 12.5, lineHeight: 1.7 }}>在信息流或今日精选里点 ⭐ 收藏，AI 会自动生成知识卡片沉淀到这里。</div>
          </div>
        )}
      </div>
    </main>
  );
}
