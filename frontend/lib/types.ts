export type Channel =
  | "行业动态" | "国网规划" | "招标公告" | "AI洞察" | "政策法规"
  | "前沿论文" | "大模型动态" | "落地案例";
export type Kind = "资讯" | "论文" | "案例";

export interface PaperMeta {
  authors?: string[];
  arxivId?: string;
  pdfUrl?: string;
  hfUrl?: string;
  titleZh?: string;
}
export type Priority = "高" | "中" | "低";
export type SourceType = "网站" | "公众号" | "RSS";

export interface Article {
  id: number;
  title: string;
  summary: string;
  tags: string[];
  channel: Channel;
  org?: string;
  hot?: boolean;
  deadlineDays?: number | null;
  sourceDomain?: string;
  url?: string;
  publishedLabel?: string;
  viewCount?: number;
  /** AI 精选机制 */
  relevanceScore?: number;
  recommendReason?: string;
  curated?: boolean;
  kind?: Kind;
  meta?: PaperMeta;
  /** 详情页站内全文（服务端已白名单消毒）；列表接口不返回，故通常为 undefined */
  contentHtml?: string | null;
  clusterId?: string;
  primaryThreadId?: number | null;
  threadAffinity?: Record<string, number>;
  relatedCount?: number;
  scored?: boolean;
  processingStatus?: string;
  scoredBy?: "primary_model" | "fallback_model" | "rule" | "unscored" | string;
  noiseReason?: string | null;
  /** 时间窗筛选用：源侧发布时间，缺失时退回入库时间（毫秒时间戳，UTC 解析后） */
  timeMs?: number;
  /** 入库时间（毫秒）：新入库徽标与"最新入库"统计用，与发布时间无关 */
  crawledMs?: number;
  /** 由 timeMs 算出的相对时间（"2 小时前"），比源侧五花八门的 published_label 口径统一 */
  timeLabel?: string;
  /** 信源分级 T1 官方 / T1.5 / T2 自媒体——来源可信度透明化 */
  tier?: string;
  /** 双轴：√(AI 相关度 × 电力相关度)，衡量是否落在交叉区 */
  crossScore?: number;
  /** 双轴分类：交叉 | AI | 行业 | 弱 */
  axis?: "交叉" | "AI" | "行业" | "弱";
  /** accent colour for the left bar + theme: blue | green | amber | violet */
  accent?: "blue" | "green" | "amber" | "violet";
}

export interface GraphNode {
  id: string;
  label: string;
  sub: string;
  kind: "部门" | "系统" | "场景";
  x: number;
  y: number;
}

export interface SourceReport {
  id: number;
  name: string;
  domain: string;
  type: SourceType;
  status: "已采纳" | "待审核" | "未通过";
}
