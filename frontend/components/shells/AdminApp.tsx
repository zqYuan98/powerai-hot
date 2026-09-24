"use client";

import React, { useRef, useState } from "react";

import AdminSidebar from "../navigation/AdminSidebar";
import MobileNav from "../navigation/MobileNav";
import { adminNavItems } from "../navigation/navConfig";
import { useIsMobile } from "../../lib/useViewport";
import AdminModule from "../admin/AdminModule";
import PipelineModule from "../pipeline/PipelineModule";
import SourcesModule from "../sources/SourcesModule";
import ContentOperationsModule from "../admin/ContentOperationsModule";
import Toast from "../Toast";
import type { AdminModuleKey } from "../navigation/navConfig";

export default function AdminApp() {
  const isMobile = useIsMobile();
  const [module, setModule] = useState<AdminModuleKey>("overview");
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (message: string) => {
    setToast(message);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2400);
  };

  return (
    <div style={{ height: "100vh", ...(isMobile ? {} : { minWidth: 1180 }), display: "flex", flexDirection: isMobile ? "column" : "row", background: "#0A0C12", backgroundImage: "radial-gradient(900px 500px at 12% -8%, rgba(167,139,250,0.10), transparent 60%), radial-gradient(800px 520px at 98% 4%, rgba(59,158,255,0.08), transparent 60%)", fontFamily: "'Noto Sans SC', sans-serif", color: "#E6EBF4", overflow: "hidden", position: "relative" }}>
      {!isMobile && <AdminSidebar module={module} go={setModule} />}
      <div style={{ flex: 1, minWidth: 0, minHeight: 0, display: "flex", overflow: "hidden" }}>
        {module === "overview" && <AdminModule onToast={showToast} />}
        {module === "pipeline" && <PipelineModule />}
        {module === "sources" && <SourcesModule onToast={showToast} />}
        {module === "content" && <ContentOperationsModule />}
      </div>
      {isMobile && <MobileNav items={adminNavItems} active={module} go={setModule} />}
      <Toast message={toast} />
    </div>
  );
}
