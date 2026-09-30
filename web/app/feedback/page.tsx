import type { Metadata } from "next";

import { FeedbackForm } from "@/components/FeedbackForm";
import { AsideCard, ReadingLayout } from "@/components/ui";

export const metadata: Metadata = {
  title: "反馈",
  description: "告诉我们哪里可以做得更好：内容、信源、功能、接入问题，或来源方的更正与下架请求。",
  robots: { index: false },
};

const TIPS = ["出问题的页面或条目链接", "你看到了什么、原本想做什么", "想加的信源，附上网址"];

export default async function FeedbackPage({ searchParams }: { searchParams: Promise<{ from?: string }> }) {
  const from = (await searchParams).from;
  return (
    <ReadingLayout
      aside={
        <>
          <AsideCard title="写清楚这几点，处理更快">
            <ol className="space-y-2">
              {TIPS.map((t, i) => (
                <li key={t} className="flex gap-2.5 text-[13px] leading-relaxed text-muted">
                  <span className="mt-px font-mono text-[11px] font-bold text-accent">{String(i + 1).padStart(2, "0")}</span>
                  {t}
                </li>
              ))}
            </ol>
          </AsideCard>
          <AsideCard title="来源方">
            <p className="text-[13px] leading-relaxed text-muted">
              如果你是信息来源方，希望更正、下架或调整展示方式，写明对应的条目链接和诉求即可。
            </p>
          </AsideCard>
        </>
      }
    >
      <h1 className="text-xl font-semibold tracking-tight text-ink">说说你的想法</h1>
      <p className="mt-1 text-sm text-muted">发现问题、想要的功能、想加的信源、看不顺的地方，都可以告诉我们，每一条都会看。</p>
      <FeedbackForm from={from?.startsWith("/") && !from.startsWith("//") ? from : undefined} />
    </ReadingLayout>
  );
}
