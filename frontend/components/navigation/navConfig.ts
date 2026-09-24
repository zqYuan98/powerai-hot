import type { ComponentType } from "react";

import { Bell, Book, Doc, Feed, Gear, Globe, Link, Sort, Spark } from "../icons";

export type NavigationAccess = "workspace" | "admin";
export type EmployeeModuleKey = "feed" | "digest" | "research" | "knowledge" | "sub" | "report";
export type AdminModuleKey = "overview" | "pipeline" | "sources" | "content";

export interface NavigationItem<Key extends string = string> {
  key: Key;
  label: string;
  access: NavigationAccess;
  accent: "blue" | "cyan" | "violet";
  icon: ComponentType<any>;
}

export const employeeNavItems: NavigationItem<EmployeeModuleKey>[] = [
  { key: "feed", label: "情报流", access: "workspace", accent: "blue", icon: Feed },
  { key: "digest", label: "今日精选", access: "workspace", accent: "cyan", icon: Spark },
  { key: "research", label: "研究报告", access: "workspace", accent: "blue", icon: Doc },
  // 业务知识库与关系图谱已移除（生产库长期 0 行），此入口现在只剩「工作空间收藏」，
  // 沿用「知识中心」会误导使用者以为还有知识库
  { key: "knowledge", label: "我的收藏", access: "workspace", accent: "violet", icon: Book },
  { key: "sub", label: "推送订阅", access: "workspace", accent: "blue", icon: Bell },
  { key: "report", label: "信源推荐", access: "workspace", accent: "cyan", icon: Globe },
];

export const adminNavItems: NavigationItem<AdminModuleKey>[] = [
  { key: "overview", label: "管理概览", access: "admin", accent: "violet", icon: Gear },
  { key: "pipeline", label: "流水线", access: "admin", accent: "cyan", icon: Sort },
  { key: "sources", label: "信源管理", access: "admin", accent: "blue", icon: Link },
  { key: "content", label: "内容运营", access: "admin", accent: "cyan", icon: Doc },
];
