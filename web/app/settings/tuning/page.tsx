import type { Metadata } from "next";

import { TuningForm } from "@/components/settings/TuningForm";
import { api } from "@/lib/api.server";
import type { Tuning } from "@/lib/types";

export const metadata: Metadata = { title: "画像与打分" };

export default async function TuningPage() {
  return <TuningForm initial={await api<Tuning>("/tuning")} />;
}
