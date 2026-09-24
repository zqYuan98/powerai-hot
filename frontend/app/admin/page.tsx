"use client";

import React from "react";

import { AccessGate } from "../../components/auth/AccessGate";
import { SessionProvider, useSession } from "../../components/auth/SessionProvider";
import AdminApp from "../../components/shells/AdminApp";

function AdminEntry() {
  const { mode } = useSession();
  if (mode === "public_admin") return <AdminApp />;
  return <AccessGate scope="admin"><AdminApp /></AccessGate>;
}

export default function AdminPage() {
  return <SessionProvider><AdminEntry /></SessionProvider>;
}
