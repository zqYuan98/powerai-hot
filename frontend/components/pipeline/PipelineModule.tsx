"use client";
import React, { useEffect, useState } from "react";
import { api, PipelineStatus } from "../../lib/api";
import { useIsMobile } from "../../lib/useViewport";
import { Bolt } from "../icons";
import AxisMonitorPanel from "../admin/AxisMonitorPanel";

// ============ 流水线全景 ============
// 上半部「系统脉搏」：轮询 /admin/pipeline 展示流水线此刻的真实运行状态——
// 采集是否在跑、上轮结果、24h 入库节奏、信源健康、补打分积压、日报新鲜度。
// 下半部为静态步骤说明：向非工程师同事解释一条情报从抓取到上页面的完整链路，
// 所有步骤、规则、代码位置都对应后端真实实现（backend/services/ingest.py 为主线）。

const MONO = "'JetBrains Mono', monospace";
const DISPLAY = "'Space Grotesk', sans-serif";

type Role = "collect" | "ai" | "code" | "decision" | "db" | "push";

const ROLES: Record<Role, { label: string; color: string }> = {
  collect: { label: "抓取", color: "#3B9EFF" },
  ai: { label: "AI 干活", color: "#FCD34D" },
  code: { label: "代码干活", color: "#4ADE80" },
  decision: { label: "决策点", color: "#FB7185" },
  db: { label: "存数据库", color: "#A78BFA" },
  push: { label: "推送", color: "#94A0B5" },
};

interface Step {
  id: string;
  no: number;
  name: string;       // 左列卡片短名
  title: string;      // 右侧详情大标题
  role: Role;
  oneLiner: string;   // 高亮框一句话概括
  who: string;        // 谁在干这件事
  cost: string;       // 花多少钱
  input: string;      // 它要什么数据
  output: string;     // 它产出什么
  codePath: string;   // 代码在哪（真实文件路径）
  rules: string[];    // 规则与判断
  notes: string[];    // 背景说明
}

const STEPS: Step[] = [
  {
    id: "collect", no: 1, name: "多源抓取", title: "多源抓取", role: "collect",
    oneLiner: "定时器（资讯每小时、论文每天早 6 点）或管理后台的「立即采集」唤醒采集器，把各个源头的最新内容抓回来。",
    who: "采集器代码：北极星电力网、arXiv、HuggingFace 论文榜三个内置采集器，加上信源管理里已「采纳」的 RSS / 公众号源",
    cost: "免费（纯网络抓取，不调用 AI 模型）",
    input: "各信息源的网页 / RSS 列表",
    output: "一批原始条目：标题、正文、链接、来源、频道初值",
    codePath: "backend/services/ingest.py · backend/collector/ · backend/scheduler/monitor.py",
    rules: [
      "默认调度：资讯类源每小时抓一轮（间隔可配置），论文类源每天 06:00 抓一轮；管理后台「立即采集」走的是同一条管线，不是另一套逻辑",
      "每轮开始前把源的顺序随机打乱，配合单轮上限，避免排前面的源每次占满名额、后面的源饿死",
      "单轮最多处理 40 条新内容（max_total=40），到上限就停、剩余留给下一轮——曾因源太多一次挤爆过服务器",
      "某个源抓取失败只记一笔健康状态（last_status=error），不影响其他源继续抓",
    ],
    notes: [
      "每个源带一个可信度等级 tier（T1 官方 / T1.5 / T2 自媒体），第 6 步算总分时会乘上对应系数",
      "新源要先在「信源管理」里被采纳，才会参与抓取",
    ],
  },
  {
    id: "dedup", no: 2, name: "查重跳过", title: "查重跳过", role: "code",
    oneLiner: "用链接指纹查一下这条是不是已经抓过，抓过的直接跳过——一分模型钱都不花。",
    who: "纯代码：数据库查询 + 本轮内存去重",
    cost: "免费",
    input: "由链接算出的指纹 url_hash",
    output: "全新条目继续往下走；重复条目计入 skipped 直接跳过",
    codePath: "backend/services/ingest.py",
    rules: [
      "先查本轮已见过的指纹（内存集合），再查数据库里有没有同指纹的旧文章",
      "去重排在所有 AI 步骤之前——重复内容不会触发任何一次模型调用",
    ],
    notes: [
      "定时采集和手动采集可能同时在跑、互相看不到对方未提交的行；就算这里都没查到，第 10 步入库时还有数据库唯一约束兜底",
    ],
  },
  {
    id: "prefilter", no: 3, name: "便宜模型预筛", title: "便宜模型预筛 + 频道分类", role: "ai",
    oneLiner: "一个便宜的小模型快速回答两件事：这条跟「电力 / AI」有关吗？该放进哪个频道？",
    who: "便宜档 AI 模型（全链路的成本闸门）；模型不可用时退化为关键词规则",
    cost: "花一点点模型钱：只喂标题 + 正文前 200 字，输出限 80 个 token，是全链路最便宜的 AI 调用",
    input: "标题 + 正文前 200 字",
    output: "{ relevant 是否相关, domain 领域, channel 频道 }",
    codePath: "backend/analyzer/prefilter.py",
    rules: [
      "「相不相关」只在这一步判一次，后面的贵模型不再重复决策——挡掉无关内容就省下了它们的评分和翻译钱",
      "频道分类也在这一步定：招标 / 政策 / 规划这类标题有确定性关键词的，由代码规则直接定频道，优先级高于模型（模型爱把招标政策笼统归成行业动态）",
      "提示词明确要求：拿不准一律判相关——误杀会让内容从精选里永远消失，误放还有后面的精细评分把关",
      "没配 API Key 或模型输出不合法时，退化成纯关键词规则（电力词表 + AI 词表）",
    ],
    notes: [
      "这一步的设计原则：分类这种一次性判断交给便宜模型 + 代码规则，别浪费贵模型的调用",
    ],
  },
  {
    id: "gate", no: 4, name: "是否进入评分", title: "决策点：是否进入评分", role: "decision",
    oneLiner: "预筛说「无关」的在这里被打回——但不会消失，会带着原因入库，在信息流「噪音」视图随时可以回溯。",
    who: "纯代码：按预筛结果分流",
    cost: "免费",
    input: "预筛结果 { relevant, domain, channel }",
    output: "通过 → 同时启动评分链和富化链两条任务；打回 → 记录 noise_reason 后直接入库",
    codePath: "backend/services/ingest.py",
    rules: [
      "被打回的条目不评分、不翻译，模型钱到此为止；但原文照常入库，noise_reason 记成「预筛判定无关（xx）」",
      "在信息流页面切到「噪音」视图，能看到所有被打回的内容和打回原因——预筛误杀了可以人工发现",
      "通过的条目同时甩出两个并行任务（ThreadPoolExecutor）：评分链 + 富化链，互不等待",
      "预筛本身失败（比如网络超时）的条目也照常入库，标记 scored=false，下一轮可以重试",
    ],
    notes: [
      "「打回的不删、可回溯」是刻意设计：闸门再便宜也会误判，留底才能持续校准它",
    ],
  },
  {
    id: "score", no: 5, name: "AI 六维评分", title: "AI 六维评分（评分链 1/3）", role: "ai",
    oneLiner: "较强的 AI 模型给内容打 6 个维度的分（各 0-100）+ 一句话推荐理由——只打维度分，不打总分。",
    who: "较强档 AI 模型，按「电力基建集成商算法负责人」的用户画像做评审",
    cost: "花模型钱：全链路最贵的调用之一，输入含正文前 600 字",
    input: "标题 + 正文前 600 字",
    output: "定位两维：AI 相关 / 行业相关；质量四维：一手性 / 工程实用 / 影响力 / 内容深度，外加一句话推荐理由",
    codePath: "backend/analyzer/scorer.py",
    rules: [
      "模型只出维度分：不打总分、不做翻译摘要、不做分类——评判和生成分离，打分更客观",
      "两组维度正交：定位管「对不对口」，质量管「好不好」——「非常对口但写得一般」和「写得很好但不相关」必须能分开表达",
      "按内容讲的是什么打分，不按文档体裁打分：「变电站智能传感终端采购」买的就是 AI，AI 相关要给高分；同为招标的「常年法律顾问采购」才该给低分",
      "采样温度 0.1，尽量让同一篇内容多次打分结果稳定",
      "模型失败时退化为关键词规则，但结果打上 fallback 标记、不参与精选——降级可以，冒充正品不行",
    ],
    notes: [
      "项目核心原则：「模型只打维度分，合成与决策用代码」——总分怎么算、精不精选，模型说了不算",
      "体裁陷阱是实测踩出来的：模型最初看到「招标」二字就把 AI 相关打到 15 分，而这恰恰是全库最有价值的一类交叉情报",
    ],
  },
  {
    id: "quality", no: 6, name: "代码合成质量分与双轴", title: "代码合成质量分与双轴（评分链 2/3）", role: "code",
    oneLiner: "两条公式：质量总分 = 加权维度均值 × 信源系数 × 类型系数；交叉分 = √(AI 相关 × 行业相关)。零 AI 参与。",
    who: "纯代码函数 compute_quality / compute_cross_score / classify_axis",
    cost: "免费",
    input: "六维分 + 信源等级 tier + 内容类型 kind + 管理后台的权重配置",
    output: "质量总分 relevance_score、交叉分 cross_score、轴标签 axis（交叉 / AI / 行业 / 弱）",
    codePath: "backend/analyzer/scoring.py",
    rules: [
      "默认权重：AI 相关 20、行业相关 20、一手性 20、工程实用 20、影响力 10、深度 10",
      "默认信源系数：T1 官方 ×1.0，T1.5 ×0.92，T2 ×0.85——同样的内容，官方源分更高",
      "交叉分用几何平均而不是算术平均：任一轴为 0 则交叉分为 0，偏科拿不到分",
      "交叉分不乘信源系数：它衡量的是内容属性（落不落在交叉区），与信源权威性无关，权威性已经体现在质量分里",
      "两轴都达到单轴高分线才算「交叉」；只有一轴高就是「AI」或「行业」，都不高是「弱」",
      "权重、系数、阈值都能在管理后台改；改完可对全库已存的维度分瞬间重算，不用重新花模型钱",
    ],
    notes: [
      "这就是「合成用代码」的落点：调权重是免费的代码运算，模型打过的维度分永远可以复用",
      "T1.5/T2 系数曾是 0.85/0.7，实测导致 T2 内容加权后封顶 59 分、永远够不到 60 的精选线——分级本该影响排序，不该变成一票否决",
    ],
  },
  {
    id: "curate", no: 7, name: "精选判定", title: "精选判定（评分链 3/3）", role: "decision",
    oneLiner: "精选走两条通道的并集：质量够高，或者足够对口且不算垃圾——都是可配置的死规则，不是模型拍脑袋。",
    who: "纯代码函数 is_curated / is_cross_pick，由 evaluate 汇总",
    cost: "免费",
    input: "质量总分 + 交叉分 + 轴标签 + 所属频道 + 阈值配置",
    output: "curated 精选与否、cross_pick 交叉精选与否、hot 热门与否",
    codePath: "backend/analyzer/scoring.py",
    rules: [
      "质量通道：总分过本频道阈值线（默认 60）即精选——不同频道可以松紧不同",
      "交叉通道：轴为「交叉」且 cross_score ≥ 交叉精选线（默认 50）且 quality ≥ 交叉质量下限（默认 35）",
      "两条通道取并集，任一条满足即入选",
      "交叉质量下限刻意低于频道阈值：招标/政策类交叉内容的实用性与深度天然偏低（正文就是一纸公告），沿用 60 会把最对口的情报全部挡在外面",
      "总分 ≥ hot_score（默认 80 分）另外标记为热门 hot",
      "没精选的内容不删，仍在「全部」视图里，只是不进精选流",
    ],
    notes: [
      "把决策交给可配置的代码阈值而不是模型：「今天为什么精选了这条」永远可以复现、可以解释",
      "第二条通道是产品定位的落点：单一阈值下，越符合「AI × 电力」定位的内容越进不了精选——实测行业轴 243 条只有 3 条过线",
    ],
  },
  {
    id: "enrich", no: 8, name: "摘要/标签/机构/标题翻译", title: "富化翻译（富化链）", role: "ai",
    oneLiner: "评分的同时，另一个 AI 任务在给内容做「编辑加工」：中文摘要、标签、机构名、英文标题翻译。",
    who: "AI 模型（与评分同档），只做内容整理，不做评价打分",
    cost: "花模型钱：与评分链同时进行，所以不增加等待时间",
    input: "标题 + 正文前 600 字",
    output: "不超过 100 字的中文摘要、2-4 个标签、来源机构名、中文标题译文（原文是中文则留空）",
    codePath: "backend/analyzer/enricher.py",
    rules: [
      "与评分链完全并行：任何一条失败都不拖累另一条——评分挂了摘要照出，摘要挂了分照打",
      "富化失败时保留原文透传，页面上照样能看到这条内容",
    ],
    notes: [
      "把「评判」和「生成」拆成两个提示词，比一个大提示词又打分又翻译更稳定、更好排查问题",
    ],
  },
  {
    id: "cluster", no: 9, name: "事件聚类", title: "事件聚类", role: "code",
    oneLiner: "把 48 小时内讲同一件事的报道归成一簇，官方源自动当「主条」，页面上不重复刷屏。",
    who: "纯代码余弦相似计算 + 一个便宜的向量模型（BGE-M3）出 embedding",
    cost: "很便宜：向量模型按字符计费，远低于评分 / 富化的调用",
    input: "「标题 + 摘要」拼成的文本 → 向量；近 48 小时内所有带向量的文章",
    output: "cluster_id 簇编号 + 簇内主条标记 is_cluster_main",
    codePath: "backend/services/clustering.py · backend/analyzer/embedder.py",
    rules: [
      "与近 48 小时窗口内的文章逐个算余弦相似度，最高相似 ≥ 0.82（可配置）就并入那一簇，否则自成一簇",
      "主条选举：信源等级高者优先（T1 > T1.5 > T2），同级比质量分，再同就比谁先入库",
      "向量获取失败、或没配 embedding Key：直接自成一簇，链路不断",
    ],
    notes: [
      "聚类发生在文章先落库之后——归簇需要文章编号，也需要能查到库里近两天的邻居",
    ],
  },
  {
    id: "persist", no: 10, name: "写入数据库", title: "写入数据库（逐条提交）", role: "db",
    oneLiner: "每处理完一条就立刻提交一条，绝不整批攒着——已经花了模型钱的成果，一条都不能丢。",
    who: "SQLAlchemy + 数据库（本地 SQLite，可换 PostgreSQL）",
    cost: "免费",
    input: "带全字段的文章对象：评分、摘要、频道、簇号……",
    output: "数据库里的一行文章记录",
    codePath: "backend/services/ingest.py",
    rules: [
      "实际有两次提交：两条链一汇合先提交拿到文章编号（聚类要用），聚类归完簇再提交一次",
      "撞了唯一约束（并发任务先插入了同一条）只回滚跳过这一条，前面已入库的不受影响",
      "数据库锁超时也只跳过当前条，不中断整批采集",
    ],
    notes: [
      "定时采集和手动采集可能并发运行、互相看不到对方未提交的行——逐条提交 + 唯一约束兜底，就是为这种并发准备的",
    ],
  },
  {
    id: "notify", no: 11, name: "命中订阅推飞书", title: "命中订阅推飞书", role: "push",
    oneLiner: "精选内容如果标题命中了你的订阅关键词，一条消息直接推到飞书群。",
    who: "纯代码调用飞书群机器人 webhook",
    cost: "免费",
    input: "精选文章 + 订阅关键词列表",
    output: "飞书群里一条消息：「【精选命中】标题 + 推荐理由 + 链接」",
    codePath: "backend/services/ingest.py（_notify_keyword_hit）",
    rules: [
      "两个条件都满足才推：这条是精选 + 标题里包含至少一个订阅关键词",
      "没配置 webhook 就静默跳过；推送失败只记日志，绝不影响采集",
    ],
    notes: [
      "推送用中文标题（有译文优先用译文），点开链接直达原文",
    ],
  },
];

const TOTAL = STEPS.length;
const byId = (id: string): Step => STEPS.find((s) => s.id === id) ?? STEPS[0];

// 布局分组按 id 引用而非数组下标——插入/重排步骤时只需改这里，不会悄悄画错流程图
const TRUNK = ["collect", "dedup", "prefilter", "gate"].map(byId);       // 主干 1-4
const SCORE_CHAIN = ["score", "quality", "curate"].map(byId);            // 评分链（与富化并行）
const ENRICH_STEP = byId("enrich");                                      // 富化翻译（与评分链并行）
const TAIL = ["cluster", "persist", "notify"].map(byId);                 // 汇合后 9-11

// ---------- 小部件 ----------

function RolePill({ role, size = 10.5 }: { role: Role; size?: number }) {
  const r = ROLES[role];
  return (
    <span style={{
      fontSize: size, fontWeight: 600, whiteSpace: "nowrap", flexShrink: 0,
      color: r.color, background: `${r.color}1A`, border: `1px solid ${r.color}40`,
      padding: "2px 8px", borderRadius: 20,
    }}>{r.label}</span>
  );
}

function Arrow() {
  return (
    <div style={{ textAlign: "center", color: "#5E6A82", fontSize: 13, lineHeight: 1, padding: "3px 0" }}>↓</div>
  );
}

function Capsule({ text, color }: { text: string; color: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "center", padding: "4px 0" }}>
      <span style={{
        fontSize: 11, fontWeight: 500, color, textAlign: "center", lineHeight: 1.6,
        background: `${color}12`, border: `1px dashed ${color}45`,
        padding: "5px 14px", borderRadius: 999,
      }}>{text}</span>
    </div>
  );
}

function StepCard({ step, selected, onSelect }: { step: Step; selected: boolean; onSelect: (id: string) => void }) {
  const c = ROLES[step.role].color;
  return (
    <div
      onClick={() => onSelect(step.id)}
      style={{
        display: "flex", alignItems: "center", gap: 10, padding: "10px 12px",
        borderRadius: 11, cursor: "pointer", userSelect: "none",
        background: selected ? `${c}14` : "rgba(148,163,184,0.05)",
        border: `1px solid ${selected ? `${c}70` : "rgba(148,163,184,0.12)"}`,
        boxShadow: selected ? `0 0 14px ${c}22` : "none",
        transition: "border-color .15s, background .15s, box-shadow .15s",
      }}
    >
      <span style={{
        width: 24, height: 24, borderRadius: 8, flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: MONO, fontSize: 11.5, fontWeight: 700,
        color: c, background: `${c}18`, border: `1px solid ${c}35`,
      }}>{step.no}</span>
      <span style={{
        flex: 1, minWidth: 0, fontSize: 13, lineHeight: 1.4,
        fontWeight: selected ? 700 : 500,
        color: selected ? "#F2F5FA" : "#C6CFDD",
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
      }}>{step.name}</span>
      <RolePill role={step.role} />
    </div>
  );
}

function Field({ label, value, mono, valueColor }: { label: string; value: string; mono?: boolean; valueColor?: string }) {
  return (
    <div style={{
      background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.10)",
      borderRadius: 11, padding: "11px 13px",
    }}>
      <div style={{ fontSize: 10.5, fontWeight: 600, color: "#5E6A82", letterSpacing: 1, marginBottom: 6 }}>{label}</div>
      <div style={{
        fontSize: mono ? 12 : 12.5, lineHeight: 1.65,
        color: valueColor ?? "#C6CFDD",
        fontFamily: mono ? MONO : undefined,
        wordBreak: "break-word",
      }}>{value}</div>
    </div>
  );
}

function BulletList({ title, items, dotColor }: { title: string; items: string[]; dotColor: string }) {
  return (
    <div>
      <div style={{ fontSize: 12, fontWeight: 700, color: "#94A0B5", marginBottom: 9, letterSpacing: 0.5 }}>{title}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        {items.map((t, i) => (
          <div key={i} style={{ display: "flex", gap: 9, alignItems: "flex-start" }}>
            <span style={{ width: 5, height: 5, borderRadius: "50%", background: dotColor, marginTop: 7, flexShrink: 0 }} />
            <span style={{ fontSize: 12.5, lineHeight: 1.7, color: "#B7C0D2" }}>{t}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------- 系统脉搏（实时仪表盘） ----------

function pToMs(iso?: string | null): number | undefined {
  if (!iso) return undefined;
  const d = new Date(/Z$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + "Z");
  return isNaN(d.getTime()) ? undefined : d.getTime();
}
function pHhmm(ms?: number): string {
  if (!ms) return "—";
  const d = new Date(ms);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
}
function pAgo(ms?: number): string {
  if (!ms) return "—";
  const diff = Date.now() - ms;
  if (diff < 6e4) return "刚刚";
  if (diff < 36e5) return `${Math.floor(diff / 6e4)} 分钟前`;
  if (diff < 864e5) return `${Math.floor(diff / 36e5)} 小时前`;
  return `${Math.floor(diff / 864e5)} 天前`;
}

function PulseCard({ label, value, sub, color }: { label: string; value: React.ReactNode; sub?: React.ReactNode; color: string }) {
  return (
    <div style={{
      flex: "1 1 150px", minWidth: 140, padding: "12px 14px", borderRadius: 12,
      background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.12)",
    }}>
      <div style={{ fontSize: 10.5, color: "#5E6A82", marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 800, color, fontFamily: MONO, lineHeight: 1.25 }}>{value}</div>
      {sub && <div style={{ fontSize: 10.5, color: "#5E6A82", marginTop: 5, lineHeight: 1.6 }}>{sub}</div>}
    </div>
  );
}

function PulseBoard() {
  const [st, setSt] = useState<PipelineStatus | null>(null);
  const [down, setDown] = useState(false);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      let crawling = false;
      try {
        const s = await api.pipelineStatus();
        if (!alive) return;
        setSt(s);
        setDown(false);
        crawling = s.manual_crawl?.status === "running";
      } catch {
        if (!alive) return;
        setDown(true);
      }
      timer = setTimeout(tick, crawling ? 4000 : 10000);
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, []);

  if (down) {
    return (
      <div style={{
        margin: "14px 28px 0", padding: "12px 16px", borderRadius: 11,
        background: "rgba(251,113,133,0.08)", border: "1px solid rgba(251,113,133,0.28)",
        fontSize: 12.5, color: "#FDA4AF",
      }}>
        后端未连接——无法读取流水线实时状态。请确认 FastAPI 服务已启动（默认 8010 端口）。
      </div>
    );
  }
  if (!st) return <div style={{ margin: "14px 28px 0", fontSize: 12, color: "#5E6A82" }}>正在读取系统状态…</div>;

  const m = st.monitor;
  const lr = m.last_run;
  const mc = st.manual_crawl;
  const crawling = mc?.status === "running";
  const runSecs = crawling && mc.started_at
    ? Math.max(0, Math.floor((Date.now() - (pToMs(mc.started_at) ?? Date.now())) / 1000)) : 0;
  const lastRunMs = lr?.at ? new Date(lr.at).getTime() : undefined; // monitor.at 是本地时间 isoformat
  const anyIssue = st.sources.error > 0 || st.sources.blocked.length > 0;

  return (
    <div style={{ padding: "14px 28px 4px", borderBottom: "1px solid rgba(148,163,184,0.10)", flexShrink: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span style={{
          width: 8, height: 8, borderRadius: "50%",
          background: crawling ? "#FCD34D" : "#4ADE80",
          boxShadow: `0 0 8px ${crawling ? "#FCD34D" : "#4ADE80"}`,
        }} />
        <span style={{ fontSize: 14, fontWeight: 800, color: "#F2F5FA" }}>系统脉搏</span>
        <span style={{ fontSize: 11, color: "#5E6A82" }}>流水线此刻的真实运行状态 · 10 秒自动刷新</span>
      </div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
        <PulseCard
          label="自动采集调度" color={m.enabled ? "#34E0D8" : "#FB7185"}
          value={m.enabled ? `每 ${m.interval_hours} 小时` : "已关闭"}
          sub={m.enabled ? `下次资讯 ${pHhmm(pToMs(m.next_runs?.crawl))} · 论文 ${pHhmm(pToMs(m.next_runs?.papers))}` : "AUTO_CRAWL_ENABLED=false"}
        />
        <PulseCard
          label="上轮自动采集" color="#9FD0FF"
          value={lr ? (lr.error ? "失败" : `+${lr.inserted ?? 0} 条`) : "本次启动后未跑"}
          sub={lr ? (lr.error
            ? <span style={{ color: "#FDA4AF" }}>{String(lr.error).slice(0, 60)}</span>
            : `${pAgo(lastRunMs)} · 抓 ${lr.fetched ?? 0} · 精选 ${lr.curated ?? 0} · 补打分 ${lr.rescored ?? 0}`) : "等待首轮（启动后 ~15s）"}
        />
        <PulseCard
          label="手动采集" color={crawling ? "#FCD34D" : "#C4CDDD"}
          value={crawling ? `进行中 ${runSecs}s` : mc?.status === "done" ? "上轮已完成" : mc?.status === "error" ? "上轮失败" : "空闲"}
          sub={crawling ? "可离开本页，进度不会丢" : mc?.stats ? `新增 ${mc.stats.inserted} · 精选 ${mc.stats.curated}` : "管理后台可发起「立即采集」"}
        />
        <PulseCard
          label="24h 入库" color="#B79CFF"
          value={`${st.articles.added_24h} 条`}
          sub={`精选 ${st.articles.curated_24h} · 噪音 ${st.articles.noise_24h} · 最新 ${pAgo(pToMs(st.articles.last_crawled_at))}`}
        />
        <PulseCard
          label="补打分积压" color={st.articles.unscored_backlog > 0 ? "#FCD34D" : "#4ADE80"}
          value={`${st.articles.unscored_backlog} 条`}
          sub={st.articles.unscored_backlog > 0 ? "评分曾失败的存量，每轮采集自动补几条" : "无积压"}
        />
        <PulseCard
          label="信源健康" color={st.sources.error > 0 ? "#FB7185" : "#4ADE80"}
          value={`${st.sources.ok} 正常`}
          sub={`异常 ${st.sources.error} · 从未抓取 ${st.sources.never} · 不参与 ${st.sources.blocked.length}`}
        />
        <PulseCard
          label="最新日报" color="#8EE6E0"
          value={st.digest ? `${st.digest.total} 条` : "尚未生成"}
          sub={st.digest ? `${st.digest.title.split("· ")[1] ?? st.digest.title} · 生成于 ${pHhmm(pToMs(st.digest.created_at))}` : "每日 07:00 自动生成，缺失时启动后自动补"}
        />
      </div>
      {anyIssue && (
        <div style={{
          marginBottom: 10, padding: "10px 14px", borderRadius: 11,
          background: "rgba(251,146,60,0.06)", border: "1px solid rgba(251,146,60,0.25)",
          fontSize: 11.5, lineHeight: 1.8, color: "#C4CDDD",
        }}>
          {st.sources.errors.map((e) => (
            <div key={e.name}><span style={{ color: "#FB7185", fontWeight: 700 }}>抓取失败</span> {e.name} — <span style={{ fontFamily: MONO, color: "#94A0B5" }}>{e.error || "未知错误"}</span></div>
          ))}
          {st.sources.blocked.map((b) => (
            <div key={b.name}><span style={{ color: "#FB923C", fontWeight: 700 }}>未参与抓取</span> {b.name} — {b.reason}</div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------- 主组件 ----------

export default function PipelineModule() {
  const isMobile = useIsMobile();
  const [selectedId, setSelectedId] = useState<string>("gate"); // 默认选中「是否进入评分」决策点
  const sel = byId(selectedId);
  const selColor = ROLES[sel.role].color;
  const costFree = sel.cost.startsWith("免费");

  const forkHeaderStyle: React.CSSProperties = {
    fontFamily: MONO, fontSize: 10, letterSpacing: 1, color: "#94A0B5",
    textAlign: "center", marginBottom: 8, whiteSpace: "nowrap",
    overflow: "hidden", textOverflow: "ellipsis",
  };
  const forkBoxStyle: React.CSSProperties = {
    flex: 1, minWidth: 0, border: "1px dashed rgba(148,163,184,0.20)",
    borderRadius: 12, padding: "10px 8px", background: "rgba(148,163,184,0.03)",
    display: "flex", flexDirection: "column",
  };

  return (
    <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {/* 页头 */}
      <div style={{ padding: "22px 28px 16px", borderBottom: "1px solid rgba(148,163,184,0.10)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{
            width: 34, height: 34, borderRadius: 10, flexShrink: 0,
            background: "linear-gradient(145deg, rgba(59,158,255,0.25), rgba(52,224,216,0.15))",
            border: "1px solid rgba(59,158,255,0.35)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}><Bolt size={18} fill="#3B9EFF" /></span>
          <h1 style={{ fontFamily: DISPLAY, fontSize: 23, fontWeight: 700, color: "#F2F5FA", margin: 0 }}>流水线全景</h1>
        </div>
        <p style={{ margin: "10px 0 0", fontSize: 13, lineHeight: 1.75, color: "#94A0B5", maxWidth: 860 }}>
          上方是系统<b style={{ color: "#C4CDDD" }}>此刻的真实运行状态</b>；下方解释一条情报从被抓取到出现在你眼前的
          <span style={{ fontFamily: MONO, color: "#34E0D8" }}> {TOTAL} </span>个步骤。
          第 5-7 步「评分链」和第 8 步「富化翻译链」同时跑、不互相等待。点击任意节点看细节。
          具体数值（单轮上限、阈值、权重等）为代码默认值，实际以管理后台配置为准。
        </p>
        {/* 图例行 */}
        <div style={{ display: "flex", alignItems: "center", gap: 18, marginTop: 13, flexWrap: "wrap" }}>
          {(Object.keys(ROLES) as Role[]).map((r) => (
            <span key={r} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: ROLES[r].color, boxShadow: `0 0 8px ${ROLES[r].color}66` }} />
              <span style={{ fontSize: 11.5, color: "#94A0B5" }}>{ROLES[r].label}</span>
            </span>
          ))}
        </div>
      </div>

      {/* 系统脉搏：实时运行状态 */}
      <PulseBoard />

      {/* 双列主体（移动端上下堆叠） */}
      <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: isMobile ? "column" : "row", overflow: isMobile ? "auto" : "hidden" }}>
        {/* 左列：步骤图 */}
        <section style={{
          ...(isMobile
            ? { width: "100%", borderBottom: "1px solid rgba(148,163,184,0.10)" }
            : { width: "40%", minWidth: 330, maxWidth: 540, overflowY: "auto" as const, borderRight: "1px solid rgba(148,163,184,0.10)" }),
          flexShrink: 0,
          padding: isMobile ? "16px 14px 24px" : "18px 20px 40px 28px",
        }}>
          {/* 1-4 单列 */}
          {TRUNK.map((s, i) => (
            <React.Fragment key={s.id}>
              {i > 0 && <Arrow />}
              <StepCard step={s} selected={selectedId === s.id} onSelect={setSelectedId} />
            </React.Fragment>
          ))}

          {/* 分叉说明胶囊（上） */}
          <Arrow />
          <Capsule text="通过 → 同时启动评分链和富化链两条任务" color="#34E0D8" />

          {/* 并行分叉区 */}
          <div style={{ display: "flex", gap: 8, alignItems: "stretch", marginTop: 4 }}>
            {/* 左：评分链 串行三步 */}
            <div style={{ ...forkBoxStyle, flex: 1.15 }}>
              <div style={forkHeaderStyle}>评分链 · 串行三步</div>
              {SCORE_CHAIN.map((s, i) => (
                <React.Fragment key={s.id}>
                  {i > 0 && <Arrow />}
                  <StepCard step={s} selected={selectedId === s.id} onSelect={setSelectedId} />
                </React.Fragment>
              ))}
            </div>
            {/* 右：富化翻译 单步 */}
            <div style={forkBoxStyle}>
              <div style={forkHeaderStyle}>富化翻译 · 单步</div>
              <StepCard step={ENRICH_STEP} selected={selectedId === ENRICH_STEP.id} onSelect={setSelectedId} />
              <div style={{
                marginTop: 10, fontSize: 11, lineHeight: 1.65, color: "#5E6A82",
                textAlign: "center", padding: "0 4px",
              }}>与左边的评分链并行执行，任一条失败不拖累另一条</div>
            </div>
          </div>

          {/* 汇合说明胶囊（下） */}
          <Capsule text="两条都完成 → 写入数据库" color="#A78BFA" />

          {/* 9-11 单列 */}
          {TAIL.map((s, i) => (
            <React.Fragment key={s.id}>
              {i > 0 && <Arrow />}
              <StepCard step={s} selected={selectedId === s.id} onSelect={setSelectedId} />
            </React.Fragment>
          ))}
        </section>

        {/* 右列：详情面板 */}
        <section style={{ flex: 1, minWidth: 0, overflowY: isMobile ? "visible" : "auto", padding: isMobile ? "18px 14px 40px" : "22px 30px 48px" }}>
          {/* 头部：第 N 步 + 角色标签 */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
            <span style={{ fontFamily: MONO, fontSize: 11, color: "#5E6A82", letterSpacing: 1 }}>
              第 {sel.no} 步 / 共 {TOTAL} 步
            </span>
            <RolePill role={sel.role} size={11.5} />
          </div>
          <h2 style={{
            fontFamily: DISPLAY, fontSize: 24, fontWeight: 700, color: "#F2F5FA",
            margin: "10px 0 16px", lineHeight: 1.35,
          }}>{sel.title}</h2>

          {/* 一句话概括高亮框 */}
          <div style={{
            background: `${selColor}10`,
            border: `1px solid ${selColor}30`, borderLeft: `3px solid ${selColor}`,
            borderRadius: 11, padding: "13px 16px",
            fontSize: 13.5, lineHeight: 1.75, color: "#E6EBF4", marginBottom: 18,
          }}>{sel.oneLiner}</div>

          {/* 分栏字段 */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
            <Field label="谁在干这件事" value={sel.who} />
            <Field label="花多少钱" value={sel.cost} valueColor={costFree ? "#4ADE80" : "#FCD34D"} />
            <Field label="它要什么数据" value={sel.input} />
            <Field label="它产出什么" value={sel.output} />
          </div>
          <div style={{ marginBottom: 22 }}>
            <Field label="代码在哪" value={sel.codePath} mono valueColor="#9FD0FF" />
          </div>

          {/* 规则与背景 */}
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <BulletList title="规则与判断" items={sel.rules} dotColor={selColor} />
            <BulletList title="背景说明" items={sel.notes} dotColor="#5E6A82" />
          </div>
        </section>
      </div>
      <div style={{ padding: "0 24px 24px" }}>
        <AxisMonitorPanel />
      </div>
    </main>
  );
}
