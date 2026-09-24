"""初始化数据：只建「真实信源登记 + 知识库参考 + 订阅关键词」。

不再灌入任何演示情报/演示需求 —— 情报全部由真实采集（北极星等）产生。
运行：python -m models.seed
"""
from models.database import SessionLocal, init_db
from models import schema

# 真实信源登记（tier: T1 官方一手 / T1.5 官方社媒 / T2 媒体KOL —— 进入评分权重）。
# arXiv / Hugging Face Papers 为内置采集器，登记仅用于健康监控与分级展示。
SOURCES = [
    # —— 电力行业 ——
    dict(name="北极星电力网", url="https://shupeidian.bjx.com.cn", type="网站", status="已采纳", tier="T2"),
    dict(name="国家能源局", url="https://www.nea.gov.cn", type="网站", status="已采纳", tier="T1"),
    dict(name="国家电网", url="http://www.nc.sgcc.com.cn", type="网站", status="已采纳", tier="T1"),
    dict(name="南方电网", url="https://www.csg.cn", type="网站", status="已采纳", tier="T1"),
    dict(name="中国政府采购网", url="https://www.ccgp.gov.cn", type="网站", status="已采纳", tier="T1"),
    dict(name="南方电网供应链", url="https://www.bidding.csg.cn", type="网站", status="已采纳", tier="T1"),
    dict(name="GitHub Trending", url="https://github.com/wenbochang888/github-trending-spider",
         type="网站", status="已采纳", tier="T2"),
    # —— 论文（内置采集器）——
    dict(name="arXiv", url="https://arxiv.org", type="网站", status="已采纳", tier="T1"),
    dict(name="Hugging Face Papers", url="https://huggingface.co/papers", type="网站", status="已采纳", tier="T1"),
    # —— 大模型动态（RSS）——
    dict(name="OpenAI Blog", url="https://openai.com/news/rss.xml", type="RSS", status="已采纳", tier="T1"),
    dict(name="Hugging Face Blog", url="https://huggingface.co/blog/feed.xml", type="RSS",
         status="待审核", tier="T1", reason="国内服务器当前连接超时，保留登记但不进入定时采集。"),
    dict(name="机器之心", url="https://www.jiqizhixin.com/rss", type="RSS", status="待审核", tier="T2",
         reason="该地址当前返回 HTML 而非 RSS，等待官方恢复后再启用。"),
    dict(name="MIT Technology Review AI",
         url="https://www.technologyreview.com/topic/artificial-intelligence/feed/",
         type="RSS", status="已采纳", tier="T1.5"),
    dict(name="NVIDIA Blog", url="https://blogs.nvidia.com/feed/",
         type="RSS", status="已采纳", tier="T1"),
    dict(name="IT之家", url="https://www.ithome.com/rss/",
         type="RSS", status="已停用", tier="T2",
         reason="2026-07-26 停用：161 条中 80% 判噪音、零精选。"),
    dict(name="Anthropic News", url="https://cdn.jsdelivr.net/gh/Olshansk/rss-feeds@main/feeds/feed_anthropic_news.xml",
         type="RSS", status="已停用", tier="T1",
         reason="2026-07-26 停用：45% 噪音、零精选；纯厂商动态，与电力方向无交叉。"),
    # —— AI 公众号（经公开 wechat2rss 桥接；借鉴 SuYxh/ai-news-aggregator 信源清单，
    #     URL 已于 2026-07-08 逐一验证可用。第三方桥有失效风险，挂了会在「信源管理」亮红）——
    dict(name="量子位", url="https://decemberpei.cyou/rssbox/wechat-liangziwei.xml",
         type="公众号", status="已停用", tier="T2",
         reason="2026-07-26 停用：40% 噪音、零精选。"),
    dict(name="新智元公众号", url="https://decemberpei.cyou/rssbox/wechat-xinzhiyuan.xml",
         type="公众号", status="已采纳", tier="T2"),
    dict(name="PaperWeekly", url="https://decemberpei.cyou/rssbox/wechat-paperweekly.xml",
         type="公众号", status="已采纳", tier="T2",
         reason="AI 论文解读，补充 arXiv/HF 之外的中文学术视角。"),
    dict(name="计算机视觉life", url="https://decemberpei.cyou/rssbox/wechat-jisuanjishijuelife.xml",
         type="公众号", status="已停用", tier="T2",
         reason="2026-07-26 停用：83% 噪音、零精选。"),
    dict(name="AI前线", url="https://decemberpei.cyou/rssbox/wechat-aiqianxian.xml",
         type="公众号", status="已停用", tier="T2",
         reason="2026-07-26 停用：40% 噪音、零精选。"),
    dict(name="DeepTech深科技", url="https://decemberpei.cyou/rssbox/wechat-shenkeji.xml",
         type="公众号", status="已停用", tier="T2",
         reason="2026-07-26 停用：58% 噪音、零精选。"),
    dict(name="甲子光年", url="https://decemberpei.cyou/rssbox/wechat-jiaziguangnian.xml",
         type="公众号", status="已采纳", tier="T2",
         reason="科技产业深度报道，AI 落地与产业分析。"),
    dict(name="海外独角兽", url="https://decemberpei.cyou/rssbox/wechat-haiwaidujiaoshou.xml",
         type="公众号", status="已采纳", tier="T2",
         reason="海外 AI 创业与投资动向。"),
    dict(name="夕小瑶科技说", url="https://decemberpei.cyou/rssbox/wechat-xixiaoyaokejishuo.xml",
         type="公众号", status="已采纳", tier="T2",
         reason="AI/NLP 技术博主，模型实测与解读。"),
    dict(name="AI能见未来", url="", type="公众号", status="待审核", tier="T2",
         reason="微信公众号。请用 wechat2rss / RSSHub 等 RSS 桥获取其 RSS 地址，"
                "在「信源管理」里填入 URL 并启用即可被自动监控。"),
    # —— 泛技术（噪音偏多，默认待审核，需要时再启用）——
    dict(name="InfoQ 中文", url="https://www.infoq.cn/feed", type="RSS", status="待审核", tier="T2",
         reason="泛技术媒体，AI 内容占比有限，启用会消耗单轮采集预算——按需开。"),
]

# 知识库参考条目（真实系统说明，可在后台继续维护扩充）。
# 默认订阅关键词（公司业务方向）。
KEYWORDS = ["布控球", "无人机巡检", "变电站AI", "特高压", "边缘计算"]

RESEARCH_THREADS = [
    {"name": "文档理解与 OCR", "description": "版面分析、表格/公式识别、文档解析（MinerU/PaddleOCR/Surya 类）、文档多模态", "keywords": ["OCR", "文档理解", "版面分析", "表格识别", "公式识别", "MinerU", "PaddleOCR", "Surya"], "weight": 1.0},
    {"name": "目标检测与缺陷识别", "description": "检测新范式、小目标、少样本/异常检测、工业质检", "keywords": ["目标检测", "缺陷识别", "小目标", "少样本", "异常检测", "工业质检"], "weight": 1.0},
    {"name": "多模态大模型", "description": "VLM、grounding、视频理解、多模态数据与评测", "keywords": ["VLM", "grounding", "视频理解", "多模态", "评测"], "weight": 0.9},
    {"name": "边缘部署与模型压缩", "description": "量化/蒸馏/剪枝、TensorRT/RKNN/昇腾、端侧推理", "keywords": ["量化", "蒸馏", "剪枝", "TensorRT", "RKNN", "昇腾", "端侧推理"], "weight": 0.8},
    {"name": "大模型与 Agent 通识", "description": "前沿模型发布、Agent 工程、训练/推理基础设施", "keywords": ["大模型", "LLM", "Agent", "训练", "推理", "基础设施"], "weight": 0.6},
    {"name": "AI × 电力场景", "description": "视觉/OCR/大模型在电网基建/巡检/安监的落地", "keywords": ["电力", "电网", "巡检", "安监", "视觉", "OCR", "大模型"], "weight": 1.0},
]


def seed_research_threads(db) -> None:
    existing = {row.name_key for row in db.query(schema.ResearchThread).all()}
    db.add_all(
        schema.ResearchThread(
            **item,
            name_key=schema.normalize_thread_name(item["name"]),
            status="active",
        )
        for item in RESEARCH_THREADS
        if schema.normalize_thread_name(item["name"]) not in existing
    )
    db.flush()


def _source_values(values: dict) -> dict:
    """Add canonical normalized keys to every seeded source row."""
    row = dict(values)
    row["name_key"] = schema.normalize_source_name(row.get("name")) or None
    row["url_key"] = schema.normalize_source_url(row.get("url"))
    row.setdefault("submitted_by", "seed")
    return row


def seed_sources(db) -> None:
    """Idempotently register the maintained source catalog.

    Rows created by built-in collectors in older releases were incorrectly
    marked as RSS. Repair only anonymous root-page rows; administrator and
    workspace submissions remain untouched.
    """
    rows = db.query(schema.Source).all()
    for row in rows:
        if (
            row.submitted_by is None
            and row.type == "RSS"
            and row.url
            and not any(marker in row.url.casefold() for marker in ("rss", "feed", ".xml", ".atom"))
        ):
            row.type = "网站"
            row.submitted_by = "builtin"

    by_name = {
        schema.normalize_source_name(row.name): row
        for row in rows
    }
    by_url = {
        schema.normalize_source_url(row.url): row
        for row in rows
        if row.url
    }
    for values in SOURCES:
        seeded = _source_values(values)
        name_key = seeded["name_key"]
        url_key = seeded["url_key"]
        row = by_url.get(url_key) if url_key else None
        row = row or by_name.get(name_key)
        if row is None:
            row = schema.Source(**seeded)
            db.add(row)
            by_name[name_key] = row
            if url_key:
                by_url[url_key] = row
            continue
        if not row.name_key:
            row.name_key = schema.normalize_source_name(row.name) or None
        if row.url and not row.url_key:
            row.url_key = schema.normalize_source_url(row.url)
        if not row.url and seeded.get("url"):
            row.url = seeded["url"]
            row.url_key = url_key
            row.status = seeded["status"]
            row.tier = seeded.get("tier", row.tier)
        elif (
            row.submitted_by == "seed"
            and url_key
            and row.url_key != url_key
            and url_key not in by_url
        ):
            if row.url_key:
                by_url.pop(row.url_key, None)
            row.url = seeded["url"]
            row.url_key = url_key
            by_url[url_key] = row
        if row.url_key == url_key and row.submitted_by is None:
            row.submitted_by = "seed"
    db.flush()


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_sources(db)
        if db.query(schema.Subscription).count() == 0:
            db.add(schema.Subscription(user_id="me", keywords=KEYWORDS))
        seed_research_threads(db)
        db.commit()
        print("Init OK：已建信源登记 + 知识库参考 + 订阅关键词（无演示情报，等待真实采集）")
    finally:
        db.close()


if __name__ == "__main__":
    run()
