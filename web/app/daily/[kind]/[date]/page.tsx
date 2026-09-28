import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DigestView } from "@/components/DigestView";
import { api } from "@/lib/api.server";
import type { DigestDetail } from "@/lib/types";

type Props = { params: Promise<{ kind: string; date: string }> };

async function load(params: Props["params"]): Promise<DigestDetail> {
  const { kind, date } = await params;
  if (!["daily", "weekly"].includes(kind) || !/^\d{4}-\d{2}-\d{2}$/.test(date)) notFound();
  return api<DigestDetail>(`/digests/${kind}/${date}`);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  return { title: (await load(params)).title };
}

export default async function DigestPage({ params }: Props) {
  return <DigestView d={await load(params)} />;
}
