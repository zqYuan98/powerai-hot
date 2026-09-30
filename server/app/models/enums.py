"""领域枚举。库里存英文代码，展示名由前端/提示词映射，改文案不需要迁移数据。"""
from __future__ import annotations

from enum import StrEnum


class Channel(StrEnum):
    TENDER = "tender"        # 招标（含采购、询价、资格预审）
    AWARD = "award"          # 中标/成交/候选人公示
    PROJECT = "project"      # 项目核准/可研/开工/投运
    PLANNING = "planning"    # 规划（十五五、电网规划、投资计划）
    POLICY = "policy"        # 政策法规
    MARKET = "market"        # 电力市场/电价/交易
    COMPANY = "company"      # 电网与央企动态
    TECH = "tech"            # 技术与 AI 前沿
    INDUSTRY = "industry"    # 其他行业资讯


CHANNEL_LABELS: dict[str, str] = {
    Channel.TENDER: "招标",
    Channel.AWARD: "中标",
    Channel.PROJECT: "项目",
    Channel.PLANNING: "规划",
    Channel.POLICY: "政策",
    Channel.MARKET: "市场",
    Channel.COMPANY: "企业",
    Channel.TECH: "技术",
    Channel.INDUSTRY: "行业",
}

# 这些频道的条目会抽取结构化商机字段
LEAD_CHANNELS = frozenset({Channel.TENDER, Channel.AWARD, Channel.PROJECT, Channel.PLANNING})


class Tier(StrEnum):
    T1 = "T1"      # 官方一手：政府、电网公司、招标平台
    T1_5 = "T1_5"  # 专业媒体：行业报刊、北极星
    T2 = "T2"      # 综合媒体、自媒体、聚合


class SourceKind(StrEnum):
    HTML_LIST = "html_list"  # 列表页 + 链接正则（配置驱动）
    RSS = "rss"
    CUSTOM = "custom"        # 需要专门代码的站点（接口/SPA）


class ItemStatus(StrEnum):
    NEW = "new"                  # 刚入库，待处理
    SCREENED_OUT = "screened_out"  # 预筛判定无关（原因见 status_reason）
    ANALYZED = "analyzed"
    FAILED = "failed"            # 模型失败，可重试


class Stage(StrEnum):
    PLANNING = "planning"      # 规划
    APPROVAL = "approval"      # 核准/备案
    FEASIBILITY = "feasibility"  # 可研/设计
    TENDERING = "tendering"    # 招标中
    AWARDED = "awarded"        # 已中标
    CONSTRUCTION = "construction"  # 开工/在建
    OPERATION = "operation"    # 投运
    UNKNOWN = "unknown"


class BizLine(StrEnum):
    INSPECTION_AI = "inspection_ai"  # 智能运检 / AI 视觉
    GRID_EPC = "grid_epc"            # 输变电工程施工 / EPC
    OTHER = "other"


class FollowStatus(StrEnum):
    NEW = "new"
    WATCHING = "watching"
    FOLLOWING = "following"
    IGNORED = "ignored"
    CLOSED = "closed"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class DigestKind(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"


# ---------- 知识库 ----------

class KnowledgeDomain(StrEnum):
    TRANSMISSION = "transmission"    # 输电线路
    SUBSTATION = "substation"        # 变电站（一次/二次）
    DISTRIBUTION = "distribution"    # 配电网
    CIVIL = "civil"                  # 土建与基础
    COMMISSIONING = "commissioning"  # 调试试验
    INSPECTION = "inspection"        # 智能运检（无人机、在线监测、AI 视觉）
    RENEWABLE = "renewable"          # 新能源与储能并网
    GENERAL = "general"              # 综合 / 其他


class KnowledgeType(StrEnum):
    PRINCIPLE = "principle"        # 原理科普
    CONSTRUCTION = "construction"  # 施工工艺 / 工法
    STANDARD = "standard"          # 标准规范解读
    DESIGN = "design"              # 设计方案 / 典型案例
    SAFETY = "safety"              # 安全与事故案例
    COST = "cost"                  # 造价与定额
    BIDDING = "bidding"            # 招投标实务
    MANAGEMENT = "management"      # 项目管理
    TECH = "tech"                  # 新技术新装备


DOMAIN_LABELS: dict[str, str] = {
    KnowledgeDomain.TRANSMISSION: "输电线路",
    KnowledgeDomain.SUBSTATION: "变电站",
    KnowledgeDomain.DISTRIBUTION: "配电网",
    KnowledgeDomain.CIVIL: "土建与基础",
    KnowledgeDomain.COMMISSIONING: "调试试验",
    KnowledgeDomain.INSPECTION: "智能运检",
    KnowledgeDomain.RENEWABLE: "新能源与储能",
    KnowledgeDomain.GENERAL: "综合",
}

KTYPE_LABELS: dict[str, str] = {
    KnowledgeType.PRINCIPLE: "原理科普",
    KnowledgeType.CONSTRUCTION: "施工工艺",
    KnowledgeType.STANDARD: "标准规范",
    KnowledgeType.DESIGN: "设计方案",
    KnowledgeType.SAFETY: "安全与事故",
    KnowledgeType.COST: "造价定额",
    KnowledgeType.BIDDING: "招投标实务",
    KnowledgeType.MANAGEMENT: "项目管理",
    KnowledgeType.TECH: "新技术装备",
}


class ArticleStatus(StrEnum):
    NEW = "new"              # 待抓取 / 待分析
    ANALYZED = "analyzed"    # 已做成知识卡片，对外展示
    REJECTED = "rejected"    # 质量不够、营销软文或不是电力专业知识
    DUPLICATE = "duplicate"  # 与已收录文章重复（多为公众号转载）
    HIDDEN = "hidden"        # 管理员手动隐藏
    FAILED = "failed"        # 抓取或模型失败，可重试
