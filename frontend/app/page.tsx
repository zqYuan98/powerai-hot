"use client";

import React from "react";

import { AccessGate } from "../components/auth/AccessGate";
import { SessionProvider, useSession } from "../components/auth/SessionProvider";
import EmployeeApp from "../components/shells/EmployeeApp";

function HomeApp() {
  const { mode } = useSession();
  if (mode === "public_admin") return <EmployeeApp />;
  return <AccessGate scope="workspace"><EmployeeApp /></AccessGate>;
}

export default function Page() {
  return <SessionProvider><HomeApp /></SessionProvider>;
}
