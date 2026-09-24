"use client";
import React from "react";
import WorkspaceCollection from "./WorkspaceCollection";

/**
 * 知识中心。
 *
 * 2026-07-25 起只保留「工作空间收藏」：原来的「业务知识」与「关系探索」两个页签
 * 依赖 knowledge_items / knowledge_relations，生产库里这两张表始终为 0 行
 * （seed 的 2 条都没进去），是空壳；相关后端接口与模型已一并移除。
 */
export default function KnowledgeCenterModule() {
  return (
    <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <WorkspaceCollection />
      </div>
    </div>
  );
}
