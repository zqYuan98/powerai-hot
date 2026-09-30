import { ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { AsideCard, Card, ReadingLayout } from "@/components/ui";
import { api } from "@/lib/api.server";
import { relativeTime } from "@/lib/format";
import type { Meta } from "@/lib/types";

export const metadata: Metadata = {
  title: "关于",
  description: "电力基建情报站是什么、每天怎么工作、怎么看这里的内容。",
};

const STEPS: [string, string][] = [
  ["采集", "按各自的节奏抓取政府部门、电网公司、招标采购平台和行业媒体的公开信息，只保留标题、链接和公开正文。"],
  ["初筛", "规则先拦掉明显无关的（食堂采购、物业保洁、过旧的公告），再由模型判断是否与电力基建相关。"],
  ["精读打分", "模型通读原文，写中文短标题、摘要和推荐理由，从相关度、商机价值、确定性、时效、影响面五个维度打分，高分进入精选。"],
  ["商机抽取与核验", "招标、中标、项目、规划类信息抽取项目、业主、金额、电压等级、编号、截止时间，每个字段都回原文逐字核对，核对不上的直接丢弃。"],
  ["事件归并", "同一个项目或同一件事的多家报道归到一起，按独立信源数和时间衰减排出热点。"],
  ["日报", "每天 08:00（北京时间）汇总前 24 小时的精选，每周一出周报。"],
  ["知识库", "另一条线：从公众号和专业网站收录讲原理、工艺、规范、方案的好文章，提炼成知识卡片，按专业和类型归档，并和相关商机互相关联。"],
];

const NEXT: [href: string, label: string, note: string][] = [
  ["/agent", "Agent 接入", "用 MCP、RSS 或 API 读这里的数据"],
  ["/changelog", "更新日志", "最近改了什么"],
  ["/feedback?from=/about", "反馈", "想要的信源、看不顺的地方"],
];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="mb-3 text-base font-semibold text-ink">{title}</h2>
      <div className="space-y-2 text-sm leading-relaxed text-ink-2">{children}</div>
    </section>
  );
}

export default async function AboutPage() {
  const meta = await api<Meta>("/meta");
  const today = meta.channels.reduce((n, c) => n + c.today, 0);
  const stats = [
    { label: "在跟踪的信源", value: `${meta.sources_enabled} 个` },
    { label: "今日精选", value: `${today} 条` },
    { label: "最近一次采集", value: meta.last_collect_at ? relativeTime(meta.last_collect_at) : "—" },
  ];

  return (
    <ReadingLayout
      aside={
        <>
          <AsideCard title="接着看">
            <nav className="-mx-2 -mb-1">
              {NEXT.map(([href, label, note]) => (
                <Link key={href} href={href} className="group flex items-center gap-2 rounded-md px-2 py-2 hover:bg-surface-2">
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm text-ink-2 group-hover:text-ink">{label}</span>
                    <span className="mt-0.5 block text-xs text-muted">{note}</span>
                  </span>
                  <ChevronRight className="size-4 text-muted" aria-hidden />
                </Link>
              ))}
            </nav>
          </AsideCard>
        </>
      }
    >
      <h1 className="text-xl font-semibold tracking-tight text-ink">关于电力基建情报站</h1>
      <p className="mt-3 leading-relaxed text-ink-2">
        一个替你每天翻招标平台、电网公司官网和行业媒体的情报站。重点关注输变电工程（EPC、施工）和智能运检（无人机巡检、AI
        视觉、在线监测）相关的商机，同时覆盖规划、政策、电力市场和行业动态。
      </p>

      <div className="mt-5 grid grid-cols-3 gap-3">
        {stats.map((s) => (
          <Card key={s.label} className="p-3">
            <div className="text-lg font-semibold text-ink tabular-nums">{s.value}</div>
            <div className="text-xs text-muted">{s.label}</div>
          </Card>
        ))}
      </div>

      <Section title="每天怎么工作">
        <ol className="space-y-3">
          {STEPS.map(([name, desc], i) => (
            <li key={name} className="flex gap-3">
              <span className="mt-0.5 font-mono text-xs font-semibold text-accent tabular-nums">{String(i + 1).padStart(2, "0")}</span>
              <span>
                <span className="font-medium text-ink">{name}</span>　{desc}
              </span>
            </li>
          ))}
        </ol>
      </Section>

      <Section title="怎么看这里的内容">
        <p>
          <span className="font-medium text-ink">以原文为准。</span>
          标题、摘要、推荐理由都是模型根据原文写的，方便快速浏览；金额、截止时间、资质要求这类要拿去做决定的信息，请点「查看原文」核对。
        </p>
        <p>
          <span className="font-medium text-ink">「原文未披露」和「已丢弃」不一样。</span>
          前者是公告里本来就没写，后者是模型抽出了内容、但在原文里找不到依据，所以没有展示。宁可空着，也不编。
        </p>
        <p>
          <span className="font-medium text-ink">信源分三档。</span>
          官方一手（政府、电网公司、招标平台）、专业媒体、综合媒体。同一件事有多家报道时，优先展示一手来源。
        </p>
        <p>
          <span className="font-medium text-ink">评分是相对的。</span>
          0–100 分衡量的是「对电力基建从业者值不值得看」，不代表项目本身好坏。
        </p>
      </Section>

      <Section title="隐私">
        <p>浏览不需要账号。收藏只保存在你自己的浏览器里，服务器看不到。</p>
        <p>提交反馈时会记录你填写的内容、自愿留下的联系方式、来源页面和 IP，只用于处理反馈和防止滥用。</p>
      </Section>
    </ReadingLayout>
  );
}
