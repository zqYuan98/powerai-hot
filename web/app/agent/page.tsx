import { ArrowUpRight, ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { CodeBlock, CopyButton } from "@/components/CodeBlock";
import { AsideCard, Card, ReadingLayout, TabLinks } from "@/components/ui";
import { CHANNELS } from "@/lib/format";
import { siteOrigin } from "@/lib/site";

export const metadata: Metadata = {
  title: "Agent 接入",
  description: "让 Agent 直接读电力基建情报：MCP、RSS、REST API v1，匿名只读，不需要 token。",
};

const TABS = [
  { key: "mcp", label: "MCP" },
  { key: "rss", label: "RSS" },
  { key: "api", label: "REST API" },
] as const;
type Tab = (typeof TABS)[number]["key"];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-8">
      <h3 className="mb-2 text-base font-semibold text-ink">{title}</h3>
      <div className="text-sm leading-relaxed text-ink-2">{children}</div>
    </section>
  );
}

function Bullets({ items }: { items: ReactNode[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((it, i) => (
        <li key={i} className="flex gap-2">
          <span className="mt-2 size-1 shrink-0 rounded-full bg-muted" aria-hidden />
          <span>{it}</span>
        </li>
      ))}
    </ul>
  );
}

function Mono({ children }: { children: ReactNode }) {
  return <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[0.9em] text-ink">{children}</code>;
}

function McpTab({ base }: { base: string }) {
  const url = `${base}/api/mcp`;
  return (
    <>
      <h2 className="text-lg font-semibold text-ink">加一个地址，Agent 直接调用七个工具</h2>
      <p className="mt-1.5 text-sm text-muted">
        适合 Claude Code、Codex、Cursor 等支持远程 MCP 的 Agent 与开发工具。标准 Streamable HTTP，匿名只读，不需要
        token；每个工具同时返回可读的文字和结构化数据。
      </p>
      <Card className="mt-5 flex items-center gap-2 px-3 py-2.5">
        <code className="min-w-0 flex-1 truncate font-mono text-[13px] text-ink">{url}</code>
        <CopyButton text={url} label="复制" />
      </Card>
      <CodeBlock title="通用 MCP 配置" code={JSON.stringify({ mcpServers: { powerai: { type: "http", url } } }, null, 2)} />
      <CodeBlock
        title="命令行添加"
        code={`# Claude Code\nclaude mcp add --transport http powerai ${url}\n# Codex\ncodex mcp add powerai --url ${url}`}
      />
      <Section title="连上后应看到这七个工具">
        <Bullets
          items={[
            <>
              <Mono>latest</Mono>：过去 24 小时或最近 7 天的精选 / 全部动态，可按频道筛选
            </>,
            <>
              <Mono>search</Mono>：按项目名、业主、地区或话题搜索全部已精读条目
            </>,
            <>
              <Mono>leads</Mono>：结构化商机，可按阶段、省份、金额、电压等级、是否截止筛选
            </>,
            <>
              <Mono>hot</Mono>：当前热点事件排名
            </>,
            <>
              <Mono>story</Mono>：一个事件的 AI 综述与报道时间线
            </>,
            <>
              <Mono>daily</Mono>：最新或指定日期的日报 / 周报全文
            </>,
            <>
              <Mono>knowledge</Mono>：电力基建知识库，按关键词、专业、类型查知识卡片（要点、适用场景、涉及标准）
            </>,
          ]}
        />
        <p className="mt-3">
          验证一次真实调用：
          <span className="font-medium text-ink">请调用 leads，列出未截止、金额最大的 5 个 220kV 以上商机，并附原文链接。</span>
        </p>
      </Section>
      <Section title="工具边界">
        <Bullets
          items={[
            "列表类工具最多返回 30 条，热点最多 10 个，事件时间线最多最近 50 条；参数越界会明确报错，不会悄悄放宽。",
            <>
              <Mono>story</Mono> 的 story_id 只能来自 hot 或其他工具返回的结果，不要猜。
            </>,
            "搜索每个 IP 每分钟最多 20 次。",
            "标题、摘要和推荐理由由模型根据原文生成，只能当线索；金额、截止时间、资质要求请回原文核对。",
          ]}
        />
      </Section>
    </>
  );
}

function RssTab({ base }: { base: string }) {
  const feeds = [
    ["精选（推荐）", "AI 精读筛出的最新 50 条，保留站内阅读页与原文链接。", "/feed.xml"],
    ["商机", "招标、中标、项目与规划中抽取的结构化商机，最新 50 条，摘要里带金额、电压、截止时间。", "/feed/leads.xml"],
    ["日报", "每天 08:00（北京时间）发布，保留最近 30 期。", "/feed/daily.xml"],
    ["知识库", "最新收录的 50 篇知识卡片：一句话、核心要点、涉及标准与原文链接。", "/feed/knowledge.xml"],
    ["最近 7 天全部", "所有完成精读的动态（含未进精选的），最多 100 条。", "/feed/all.xml"],
  ] as const;
  return (
    <>
      <h2 className="text-lg font-semibold text-ink">复制地址即可订阅</h2>
      <p className="mt-1.5 text-sm text-muted">兼容主流 RSS 2.0 阅读器，以及 n8n、Zapier 这类自动化工具。第一次接入选「精选」。</p>
      <div className="mt-5 space-y-3">
        {feeds.map(([name, desc, path]) => (
          <Card key={path} className="p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="font-semibold text-ink">{name}</span>
              <CopyButton text={`${base}${path}`} label="复制地址" />
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-muted">{desc}</p>
            <code className="mt-2 block truncate font-mono text-xs text-muted">{`${base}${path}`}</code>
          </Card>
        ))}
      </div>
      <Section title="按频道订阅">
        <p>只要精选里的某一类，用 <Mono>{"/feed/channel/{频道}.xml"}</Mono>：</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {CHANNELS.map((c) => (
            <a
              key={c.value}
              href={`/feed/channel/${c.value}.xml`}
              className="rounded-md border border-line bg-surface px-2 py-1 font-mono text-xs text-ink-2 hover:border-accent hover:text-accent"
            >
              {c.label} · {c.value}
            </a>
          ))}
        </div>
      </Section>
      <Section title="给阅读器和 Agent 的约定">
        <Bullets
          items={[
            "支持 ETag 条件请求，未变化时返回 304；建议每 30 分钟或更慢轮询一次。",
            "条目的 link 指向站内阅读页，原文链接在 description 里。",
            "RSS 只给摘要，不转载正文。",
          ]}
        />
      </Section>
    </>
  );
}

function ApiTab({ base }: { base: string }) {
  const endpoints: [string, string][] = [
    ["/api/v1/items", "最近 24 小时 / 7 天的精选或全部动态；支持频道、关键词、游标翻页"],
    ["/api/v1/search", "关键词 + 语义搜索全部已精读条目"],
    ["/api/v1/leads", "结构化商机；支持阶段、省份、业务线、金额、电压、是否截止，按最新 / 截止 / 金额排序"],
    ["/api/v1/hot", "当前热点事件排名"],
    ["/api/v1/stories/{story_id}", "事件详情：AI 综述与报道时间线"],
    ["/api/v1/knowledge", "知识库：按专业、类型、关键词查知识卡片"],
    ["/api/v1/dailies", "日报 / 周报目录"],
    ["/api/v1/dailies/latest", "最新一期"],
    ["/api/v1/dailies/{YYYY-MM-DD}", "指定日期的一期"],
  ];
  return (
    <>
      <h2 className="text-lg font-semibold text-ink">匿名 GET，不需要 token</h2>
      <p className="mt-1.5 text-sm text-muted">
        浏览器跨域、curl 和任意 HTTP 客户端都可以直接用。字段、参数与错误码以{" "}
        <a href="/api/v1/openapi.json" className="text-accent hover:underline">
          OpenAPI 定义
        </a>{" "}
        为准。
      </p>
      <CodeBlock title="第一个请求" code={`curl '${base}/api/v1/items?window=24h&limit=20'`} />
      <div className="overflow-x-auto rounded-lg border border-line bg-surface">
        <table className="w-full min-w-[560px] text-left text-sm">
          <thead className="border-b border-line text-xs text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">方法</th>
              <th className="px-3 py-2 font-medium">路径</th>
              <th className="px-3 py-2 font-medium">说明</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {endpoints.map(([p, d]) => (
              <tr key={p}>
                <td className="px-3 py-2 font-mono text-xs text-ok">GET</td>
                <td className="px-3 py-2 font-mono text-[12.5px] whitespace-nowrap text-ink">{p}</td>
                <td className="px-3 py-2 text-ink-2">{d}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Section title="先知道这几件事">
        <Bullets
          items={[
            <>
              items 不传 <Mono>mode</Mono> 等同 selected（精选）；需要全部动态才用 <Mono>mode=all</Mono>。
            </>,
            <>
              items 用 <Mono>next_cursor</Mono> 翻页，leads 用 <Mono>offset</Mono> 翻页。
            </>,
            "返回摘要、推荐理由、商机字段、站内阅读页（url）与原文链接（source_url），不带正文。",
            "没有推送通道：带 If-None-Match 轮询，未变化时返回 304。",
          ]}
        />
      </Section>
      <Section title="错误与恢复">
        <Bullets
          items={[
            "422：参数不合法，按 OpenAPI 修正，不要自动改成更宽的查询。",
            "404：事件或该期日报不存在。",
            "429：搜索每个 IP 每分钟最多 20 次，遵守 Retry-After，不要并发重试。",
            "5xx：指数退避，并使用上次成功的结果。",
          ]}
        />
      </Section>
    </>
  );
}

export default async function AgentPage({ searchParams }: { searchParams: Promise<{ tab?: string }> }) {
  const raw = (await searchParams).tab;
  const tab: Tab = TABS.some((t) => t.key === raw) ? (raw as Tab) : "mcp";
  const base = await siteOrigin();
  const resources: [string, string, string][] = [
    ["llms.txt", "/llms.txt", "给大模型读的站点说明"],
    ["MCP Server", "/api/mcp", "MCP 客户端的连接地址"],
    ["OpenAPI 定义", "/api/v1/openapi.json", "REST API v1 的完整定义"],
    ["RSS · 精选", "/feed.xml", "最常用的订阅地址"],
  ];

  return (
    <ReadingLayout
      aside={
        <>
          <AsideCard title="接入资源">
            <nav aria-label="接入资源" className="-mx-2 -mb-1">
              {resources.map(([label, href, note]) => (
                <a key={href} href={href} className="group flex items-start gap-2 rounded-md px-2 py-2 hover:bg-surface-2">
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm text-ink-2 group-hover:text-ink">{label}</span>
                    <span className="mt-0.5 block text-xs text-muted">{note}</span>
                  </span>
                  <ArrowUpRight className="mt-1 size-3.5 shrink-0 text-muted" aria-hidden />
                </a>
              ))}
            </nav>
          </AsideCard>
          <AsideCard title="没接上？">
            <p className="text-[13px] leading-relaxed text-muted">把客户端名称、版本和报错写在反馈页，不要附带任何 token 或本地文件。</p>
            <Link href="/feedback?from=/agent" className="mt-2 inline-flex items-center gap-0.5 text-sm font-medium text-accent hover:underline">
              去反馈 <ChevronRight className="size-4" aria-hidden />
            </Link>
          </AsideCard>
        </>
      }
    >
      <h1 className="text-xl font-semibold tracking-tight text-ink">Agent 接入</h1>
      <p className="mt-1 mb-4 text-sm text-muted">让 Agent 直接读这里的电力基建情报。三种方式任选，全部匿名只读。</p>
      <TabLinks active={tab} tabs={TABS.map((t) => ({ key: t.key, label: t.label, href: t.key === "mcp" ? "/agent" : `/agent?tab=${t.key}` }))} />
      {tab === "mcp" ? <McpTab base={base} /> : tab === "rss" ? <RssTab base={base} /> : <ApiTab base={base} />}
    </ReadingLayout>
  );
}
