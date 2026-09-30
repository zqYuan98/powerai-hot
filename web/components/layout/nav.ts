import { BookOpen, Bookmark, CalendarDays, Flame, History, Info, Layers, MessageSquare, Newspaper, Plug, Settings, Target } from "lucide-react";

export const NAV = [
  { href: "/", label: "精选", icon: Newspaper },
  { href: "/leads", label: "商机", icon: Target },
  { href: "/hot", label: "热点", icon: Flame },
  { href: "/daily", label: "日报", icon: CalendarDays },
  { href: "/knowledge", label: "知识", icon: BookOpen },
  { href: "/all", label: "全部", icon: Layers },
  { href: "/starred", label: "收藏", icon: Bookmark },
] as const;

/** 「更多」菜单；changelog 项在有新日志时带小红点。 */
export const MORE_LINKS = [
  { href: "/agent", label: "Agent 接入", icon: Plug, changelog: false },
  { href: "/about", label: "关于", icon: Info, changelog: false },
  { href: "/changelog", label: "更新日志", icon: History, changelog: true },
  { href: "/feedback", label: "反馈", icon: MessageSquare, changelog: false },
] as const;

/** 后台入口只对已登录的管理员显示；访客直接访问 /settings 会被带到登录页。 */
export const ADMIN_LINK = { href: "/settings", label: "后台", icon: Settings, changelog: false } as const;

export function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/" || pathname.startsWith("/items");
  if (href === "/hot" && pathname.startsWith("/stories")) return true;
  return pathname === href || pathname.startsWith(`${href}/`);
}
