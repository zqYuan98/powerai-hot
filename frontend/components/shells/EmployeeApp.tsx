"use client";

import React, { useEffect, useRef, useState } from "react";

import EmployeeSidebar from "../navigation/EmployeeSidebar";
import MobileNav from "../navigation/MobileNav";
import { employeeNavItems } from "../navigation/navConfig";
import { useIsMobile } from "../../lib/useViewport";
import FeedModule from "../feed/FeedModule";
import DigestModule from "../digest/DigestModule";
import ResearchModule from "../research/ResearchModule";
import KnowledgeCenterModule from "../knowledge/KnowledgeCenterModule";
import SubscribeModule, { type Sub } from "../subscribe/SubscribeModule";
import ReportModule from "../report/ReportModule";
import Toast from "../Toast";
import { api } from "../../lib/api";
import type { Article } from "../../lib/types";
import type { EmployeeModuleKey } from "../navigation/navConfig";

export default function EmployeeApp() {
  const isMobile = useIsMobile();
  const [module, setModule] = useState<EmployeeModuleKey>("feed");
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [sub, setSub] = useState<Sub | null>(null);
  const subRef = useRef<Sub | null>(null);
  const [subDown, setSubDown] = useState(false);
  const [favIds, setFavIds] = useState<Record<number, boolean>>({});

  const showToast = (message: string) => {
    setToast(message);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2400);
  };

  const applySub = (next: Sub | null) => {
    subRef.current = next;
    setSub(next);
  };

  useEffect(() => {
    api.getSubscription().then((value) => applySub({
      keywords: value.keywords ?? [],
      notify_in_app: !!value.notify_in_app,
      notify_bid_deadline: !!value.notify_bid_deadline,
      notify_email_digest: !!value.notify_email_digest,
    })).catch(() => setSubDown(true));
  }, []);

  useEffect(() => {
    api.listFavorites().then((ids) => {
      const next: Record<number, boolean> = {};
      ids.forEach((id) => { next[id] = true; });
      setFavIds(next);
    }).catch(() => {});
  }, []);

  const saveSub = async (make: (current: Sub) => Partial<Sub>) => {
    const current = subRef.current;
    if (!current) return;
    const patch = make(current);
    if (Object.keys(patch).length === 0) return;
    applySub({ ...current, ...patch });
    try {
      await api.updateSubscription(patch);
    } catch {
      applySub(current);
      showToast("保存失败：后端未连接或无写入权限");
    }
  };

  const toggleFav = async (article: Article) => {
    const on = !favIds[article.id];
    setFavIds((current) => ({ ...current, [article.id]: on }));
    try {
      if (on) {
        await api.addFavorite(article.id);
        showToast("已收藏，知识卡片生成中");
      } else {
        await api.removeFavorite(article.id);
        showToast("已取消收藏（卡片一并移除）");
      }
    } catch {
      setFavIds((current) => ({ ...current, [article.id]: !on }));
    }
  };

  const submitReport = () => showToast("提交已提交，等待内部审核");

  return (
    <div style={{ height: "100vh", ...(isMobile ? {} : { minWidth: 1180 }), display: "flex", flexDirection: isMobile ? "column" : "row", background: "#0A0C12", backgroundImage: "radial-gradient(900px 500px at 12% -8%, rgba(59,158,255,0.10), transparent 60%), radial-gradient(800px 520px at 98% 4%, rgba(167,139,250,0.10), transparent 60%)", fontFamily: "'Noto Sans SC', sans-serif", color: "#E6EBF4", overflow: "hidden", position: "relative" }}>
      {!isMobile && <EmployeeSidebar module={module} go={setModule} notifCount={sub ? sub.keywords.length : null} />}
      <div style={{ flex: 1, minWidth: 0, minHeight: 0, display: "flex", overflow: "hidden" }}>
        {module === "feed" && <FeedModule onGoSub={() => setModule("sub")} favIds={favIds} onToggleFav={toggleFav} subKeywords={sub?.keywords ?? []} />}
        {module === "digest" && <DigestModule favIds={favIds} onToggleFav={toggleFav} />}
        {module === "research" && <ResearchModule />}
        {module === "knowledge" && <KnowledgeCenterModule />}
        {module === "sub" && <SubscribeModule sub={sub} subDown={subDown} onSave={saveSub} />}
        {module === "report" && <ReportModule onSubmitReport={submitReport} />}
      </div>
      {isMobile && <MobileNav items={employeeNavItems} active={module} go={setModule} badges={{ sub: sub ? sub.keywords.length : null }} />}
      <Toast message={toast} />
    </div>
  );
}
