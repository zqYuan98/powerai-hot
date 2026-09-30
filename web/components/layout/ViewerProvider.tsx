"use client";

import { createContext, type ReactNode, useContext } from "react";

const AdminContext = createContext(false);

/** 把「是否管理员」交给客户端组件（收藏按钮、导航）。真正的权限在后端校验。 */
export function ViewerProvider({ admin, children }: { admin: boolean; children: ReactNode }) {
  return <AdminContext.Provider value={admin}>{children}</AdminContext.Provider>;
}

export function useIsAdmin(): boolean {
  return useContext(AdminContext);
}
