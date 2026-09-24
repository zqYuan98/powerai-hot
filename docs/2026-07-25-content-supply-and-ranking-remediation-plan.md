# 内容供给与推荐质量整改规划

日期：2026-07-25
问题陈述：产品定位「四不像」——本意是「AI 资讯 × 电力行业背景」，实际行业背景侧的内容和需求池近乎空白，推荐质量与筛查不可用。
参考对象：SuYxh/ai-news-aggregator、zenitlab/ai-hot-radar、wenbochang888/github-trending-spider、aihot.virxact.com

---

## 0-bis. 生产实测修订（2026-07-25，接入 124.220.207.16 后）

本文第 1–4 节的初版结论是**仅凭代码和信源探测**推出的。接入生产库（547 篇真实文章）后，有三条被证伪或需要大幅修正，以下修订**优先于**下文原始表述：

### 修订 A：头号根因不是信源，是评分模型已死

`job_runs` 显示 **2026-07-24 16:00 之后每一轮 `model_count` 都是 0**，状态全部 `degraded`。原因：DeepSeek 于 2026-07 下线 `deepseek-chat`，接口只接受 `deepseek-v4-pro` / `deepseek-v4-flash`，旧模型名返回 **HTTP 400**。而 `services/ingest.py` 用裸 `except Exception` 吞掉异常静默退化到规则打分 —— **静默降级持续约 19 小时**，运维界面无任何提示。

规则打分固定给出 base ≈ 43，低于任何 tier 的入选门槛 → 这段时间入库的内容**全部无法进入精选**。「推荐内容质量不行」的直接原因在这里，不在信源。

**已修复**（详见第 7 节）。

### 修订 B：「无正文导致评分低」不成立

原文 R1 断言正文缺失是内容质量的最大单点。真实数据不支持：

| 分组 | n | relevance | firsthand | utility | impact | depth |
|---|---|---|---|---|---|---|
| 有正文 | 191 | 44 | 74 | 40 | 50 | 49 |
| 无正文 | 223 | 48 | 74 | 40 | 53 | 46 |

五维几乎无差异。模型在只有标题时照样给分。正文回捞仍值得做（模型的 `reason` 里会明说「仅为招标标题，缺少技术细节」，`depth` 确实被压到 30），但它主要改善的是**摘要可读性和需求抽取的上下文**，不是评分。

**因此：正文回捞从「P1 最高优先级」降级为「P2 中等优先级」，不再是前置依赖。**

### 修订 C：T1.5 的零精选与 tier 系数无关

真实数据下按 tier 反推（仅统计模型正常打分的条目）：

| tier | n | 平均 base | 最高 base | 系数 1.00 可通过 | 0.85 | 0.70（原值） |
|---|---|---|---|---|---|---|
| T1 | 148 | 50 | 91 | 47 | 36 | 16 |
| T1.5 | 39 | 30 | **59** | **0** | 0 | 0 |
| T2 | 84 | 41 | 82 | 14 | 6 | **0** |

- **T2**：tier 系数确实是一票否决 —— 原值 0.7 下通过数为 0，0.85 下 6 条。**修正有效**。
- **T1.5**：最高 base 仅 59，低于阈值 60，**即使系数拉到 1.0 也是 0 条**。这是信源内容质量问题，不是系数问题。T1.5 全是 TopHub / TechURLs / NewsNow / 微信公众号 这类热榜聚合源 —— 也就是说，**照搬 ai-news-aggregator 的热榜广度打法，引入的是低价值内容**。这一条直接影响下文 P1-C 的取舍。

### 修订 D：其他实测确认项

- `requirements = 0`、`knowledge_items = 0` —— 需求池与行业知识库在生产环境**完全空白**，连 seed 的 2 条都没进去。原文 R4/R5 确认。
- 北极星 `last_status = ok`，但招标子站实际已死。原文 R6 确认（**挂了显示绿**）。
- IT之家 54 条中 40 条噪音（74%），`avg_score = 7`；甲子光年 `avg_score = 1`；计算机视觉life `avg_score = 4`。这些源是纯噪音泵。
- 表现最好的是 GitHub Releases 系列：PaddleOCR `avg 78 / 10 条全精选`、MinerU `55 / 7 条`、ultralytics `42 / 4 条`。**这是全库信噪比最高的信源类型，值得重点扩容。**
- **156 条规则打分的文章没有任何重新评分机制**（`rescore_pending` 只捞 `scored=False` 的，规则打分的 `scored=True`）。模型故障期间的内容会永久带着错误分数沉底。

---

## 0. 结论先行

「没有好的源」只是表象之一。实测下来，电力侧站点大部分是活的、可抓的，真正的问题是四层叠加：

1. **供给层**：电力采集器全部只抓标题、不抓正文；招标子站已挂但被静默吞掉。
2. **评分层**：单极 AI 画像 + T2 系数惩罚，使电力内容在数学上进不了精选。
3. **产物层**：需求池没有生产者、行业知识库只有 2 条种子，「行业背景」是空壳。
4. **结构层**：8 个频道只有 3 个有供给，产品结构承诺了电力、供给全是 AI。

四个参考项目**没有一个覆盖电力行业**，行业侧必须自建。参考的价值在于：信源广度策略（#1）、事件主条选择（#2）、职业定向摘要（#3）、产品形态收敛（#4）。

---

## 1. 实测证据

### 1.1 采集器实跑（2026-07-25）

| 采集器 | transport/parse | 条数 | 备注 |
|---|---|---|---|
| AI HOT | ok/ok | 10 | 正常 |
| ai-news-aggregator | ok/ok | 10 | 正常 |
| GitHub Trending 快照 | ok/ok | 4 | 正常 |
| 北极星电力网 | —（裸 list） | **0** | 不返回 CollectorResult |
| 国家能源局 | ok/parse_error | **0** | 本机缺 bs4 |
| 国家电网 | ok/parse_error | **0** | 本机缺 bs4 |
| 南方电网 | ok/parse_error | **0** | 本机缺 bs4 |
| 中国政府采购网 | ok/parse_error | **0** | 本机缺 bs4 |
| 南方电网供应链 | ok/parse_error | **0** | 本机缺 bs4 |

### 1.2 站点直连可达性（绕开采集器，验证「源本身好不好」）

| 站点 | HTTP | 可抓文章链接数 | 判定 |
|---|---|---|---|
| `shupeidian.bjx.com.cn/` | 200 | 112 | 好 |
| `www.bjx.com.cn/` | 200 | 442 个 `<a>` | 好，比子站更富 |
| `zhaobiao.bjx.com.cn/` | **SSL 握手失败 / HTTP 502** | 0 | **已挂** |
| `www.nea.gov.cn/` | 200 | 21 | 可用但只抓首页，量太小 |
| `www.nea.gov.cn/policy/index.htm` | **404** | 0 | 栏目页路径已变 |
| `nc.sgcc.com.cn/zxzx/gsxw/` | 200 | 17 | 量小，且是分部级党建/人事稿 |
| `www.csg.cn/` | 200 | 187 个 `<a>` | 好 |
| `www.ccgp.gov.cn/` | 200 | 278 个 `<a>` | 好 |
| `www.cec.org.cn/`（中电联） | 200 | 24 个 `<a>` | 疑似 JS 渲染，需二次确认 |
| `ecp.sgcc.com.cn/`（国网电商） | 200 | **0 个 `<a>`**，3.5KB | SPA，需走接口或 Playwright |
| `www.chinapower.com.cn/` | SSL 握手失败 | 0 | 与 zhaobiao 同类问题 |
| `paper.people.com.cn/zgnyb/`（中国能源报） | 403 | 0 | 需 Referer/UA 调整 |

**结论：电力信源不是「没有」，是「接得不对 + 挂了没人知道」。**

### 1.3 本地库状态

`backend/powerai_hot.db`：`articles=0`、`knowledge_items=0`、`requirements=0`、`sources=27`、`research_threads=6`。

---

## 2. 根因分析

### R1 —— 电力采集器全部只抓标题，无正文

`nea.py:61`、`sgcc_news.py:76`、`southern_grid.py:60`、`gov_procurement.py:80`、`csg_bidding.py:63`、`bjx.py:65` 构造 `RawArticle` 时**均未传 `content=`**。`services/ingest.py` 也没有任何正文回捞环节（全文只有一处 `content_html` 消毒，用于 RSS 已带的富文本）。

后果链：正文为空 → `analyzer/scorer.py:51` 的 `body` 只有标题 → `depth`/`utility` 无判据 → 打分偏低；`analyzer/enricher.py:26` 同样只见标题 → `summary` 退化成标题复读 → 卡片没有信息量。

`bjx.py` 顶部注释自认「一期按标题三角洲做采集，正文抓取留作后续增强（见 TODO）」—— 这个 TODO 从未兑现，且被复制到了后来所有电力采集器。

### R2 —— T2 信源在数学上进不了精选

`analyzer/scoring.py:23` `compute_quality = 加权均值 × tier_coeff × kind_coeff`，`tier_coeff = {T1:1.0, T1.5:0.85, T2:0.7}`，`channel_thresholds` 全部 60。

反推入选门槛（加权均值需达到）：

| tier | 需要的五维加权均值 |
|---|---|
| T1 | ≥ 60.0 |
| T1.5 | ≥ 70.6 |
| **T2** | **≥ 85.7** |

电力侧唯一有量的信源北极星是 T2（`seed.py:13`），所有公众号源也是 T2。等于精选池被结构性限定为「官方政策稿 + arXiv/HF 论文 + OpenAI/NVIDIA/Anthropic 官方博客」。这解释了为什么「推荐内容质量不行」——不是选得差，是候选集被砍到只剩一类。

### R3 —— 评分画像单极

`analyzer/scorer.py:22` 的 SYSTEM 只描述一个人设：「电力基建集成商的算法负责人，技术方向为视觉/OCR/多模态」。`relevance` 是五维中权重最高的（30/100）。

一篇《省级电力现货市场结算实施细则》对这个画像的 relevance 必然低分，但它恰恰是「行业背景」的核心内容。**行业背景内容是被评分器主动筛掉的，不是没采到。**

`services/threads.py:26` 的关键词亲和同理：`keyword_affinity` 用 `min(100, 25 + 25*len(hits))`，一篇纯政策文命中 0 个技术词 → thread_score = 0 → `learn_score` 只剩 0.5 权重之外的部分。

### R4 —— 需求池没有生产者

`api/requirements.py` 全文 51 行，只有 list/stats/create/delete。全仓库除 `api/dto.py` 和 `models/schema.py` 外，**没有任何代码创建 `Requirement`**。`components/feed/RequirementPool.tsx` 是个纯展示侧栏。

需求池是这个产品区别于普通 AI 资讯站的唯一支点，但它是纯手工的，所以永远是空的。

### R5 —— 行业知识库是空壳

`models/seed.py:76` 只有 2 条 `KNOWLEDGE_ITEMS`（E基建2.0、PMS2.0），9 条 `RELATIONS`。本地库 `knowledge_items=0`。「知识关系图谱」在 2 个节点上无法成图。

### R6 —— 采集器契约不统一，故障静默

`collector/base.py:97` `BaseCollector.fetch` 签名声明返回 `list[RawArticle]`，但除 `bjx.py` 外所有采集器已改返回 `CollectorResult`。`bjx.py:44` 仍返回裸 list，且：

- `bjx.py:48` ImportError → `return []`
- `bjx.py:56` `except Exception: continue`（吞掉招标子站的 SSL 失败）

于是 `_record_health` 记到的是「ok，0 条」。**招标子站挂了，信源管理是绿的。**

### R7 —— 频道结构与供给不匹配

`core/constants.py` 定义 8 频道：行业动态、国网规划、招标公告、AI洞察、政策法规、前沿论文、大模型动态、落地案例。

实际有稳定供给的只有后 3 个（全部来自 AI 侧聚合器/arXiv/HF）。前 5 个依赖电力采集器，而电力采集器全部 0 产出或只有标题。**产品结构承诺了电力，供给全是 AI —— 这就是「四不像」的直接来源。**

---

## 3. 四个参考的定位：抄什么、不抄什么

> 关键前提：四个参考项目**全部是纯 AI 资讯站，没有一个覆盖电力行业**。行业侧无参考可抄，必须自建。

### 3.1 SuYxh/ai-news-aggregator —— 抄「信源广度策略」

它的价值不在算法（`filters/ai-related.ts` 只是关键词表 + 正则），而在**聚合器的聚合器**打法：

- 14 个热榜聚合站：AI今日热榜、TechURLs、NewsNow、TopHub、Buzzing、Info Flow、Zeli、AI HubToday、AIbase、BestBlogs、WaytoAGI、YouTube、新智元、微信公众号
- `feeds/follow.example.opml` + 52 个公众号 + 70+ RSS
- GitHub Actions 每 2 小时跑一次，产物是纯静态 JSON

**现状问题**：我们只接了它的成品 `latest-24h.json`（`collector/aggregator.py`），等于只拿了它 1/80 的能力，而且受制于它的过滤口径和 24h 窗口。

**该抄**：
- 直接接 TopHub / NewsNow / AIbase / BestBlogs / WaytoAGI 等热榜站（它的 `src/fetchers/*.ts` 每个文件就是一个站的抓法）
- OPML 作为 RSS 源的管理格式，替代现在硬编码在 `seed.py` 的 27 条
- `config.ts` 的 `tophubAllowKeywords` / `tophubBlockKeywords` 白黑名单双列表结构（我们现在只有 `NOISE_KW` 黑名单）
- `rss.replacements` / `skipPrefixes` 机制：把失效的第三方桥（我们大量依赖 `decemberpei.cyou`）集中声明、可替换

**不该抄**：
- `dedupe.ts` 的 `randomPick`（同 key 随机选一条）—— 我们已有事件聚类，比它强
- 它的翻译链（Google 翻译）—— 我们有 enricher

### 3.2 zenitlab/ai-hot-radar —— 只剩「事件主条」没抄

它的两段式（轻模型预筛 → 五维评分 + tier 加成 + 阈值）**我们已经完整实现了**，`prefilter.py` / `scorer.py` / `scoring.py` 就是它。

**还没抄的**：「按权威性挑主条 —— OpenAI Blog 优先于 V2EX 转发」。我们的 `services/clustering.py` 做了聚类，但没有在簇内按 tier + firsthand 选代表条，也没有在卡片上呈现「另有 N 家信源同时报道」。

### 3.3 wenbochang888/github-trending-spider —— 抄「职业定向摘要」

6 源（GitHub Trending 日/周、Hacker News、TLDR AI、OpenAI、Anthropic、InfoQ AI），每日 3 次（07:50/15:50/23:50），产物统一 JSON + Redis 3 天缓存 + RSS。

**该抄**：它用 GPT-4o 生成的中文摘要是**面向后端工程师视角改写的**，不是通用摘要。我们的 `enricher.py` SYSTEM 是通用的「提炼实质信息」。

**现状问题**：我们接的是 `frontier.py` → `gdufe888.top/api/sources/github-daily/latest` 单一快照接口，只拿到 GitHub Trending 一路，且实测只有 4 条。它的 HN / TLDR AI / InfoQ AI 三路我们完全没用。

### 3.4 aihot.virxact.com —— 抄「产品形态收敛」

它的信息架构只有 5 个内容入口：**精选 / 全部 AI 动态 / AI 日报 / 主题 / 收藏**（外加 Agent 接入、About、Changelog）。

卡片字段固定：`时间 · 来源` + `热度分` + 标题 + 2–3 句摘要 + 彩色标签 + **推荐理由** + **「另有 21 家信源同时报道」**。首屏有「热点 TOP 4」，下方按日期分组。

**对比现状**：我们是 6 个员工入口（情报信息流/今日精选/研究报告/知识中心/推送订阅/信源推荐）+ 4 个管理入口。入口比它多，但**卡片信息密度比它低**（缺多源计数、推荐理由展示位不突出）。

**该抄**：卡片字段清单、日期分组、热点 TOP N 首屏、以及「精选 vs 全部」的二元主视图（而不是 8 个平级频道 tab）。

---

## 4. 整改规划

### 定位重设（做任何改动前先定这一条）

现在的隐含定位是「AI 资讯站 + 一点行业背景」，所以怎么调都是四不像。建议改成：

> **以电力业务问题为轴的 AI 情报站。**
> 双轴打分：**AI 技术轴 × 电力场景轴**。
> - 两轴都高 → **精选**（这才是产品的独有价值）
> - 只有 AI 轴高 → **技术背景流**（可读，但不占精选位）
> - 只有电力轴高 → **行业底噪 / 事件线**（进「行业动态」时间线，不进精选流）
>
> 产品的最终产物不是「今天有哪些 AI 新闻」，而是**需求池**：从情报里自动抽出「我们能做什么、该准备什么」。

这条定下来，下面每一阶段的取舍才有依据。

---

### P0 —— 止血：让故障可见、让供给恢复（1–2 天）

目标：不新增功能，先让现有的电力供给真的跑起来、坏了能看见。

| # | 动作 | 文件 | 验收 |
|---|---|---|---|
| P0-1 | `BjxCollector.fetch` 改为返回 `CollectorResult`，去掉 `except Exception: continue` 的全吞，逐子站记录失败原因 | `collector/bjx.py:44-79` | 招标子站 502 时信源管理亮红 |
| P0-2 | `BaseCollector.fetch` 签名与文档字符串改为 `-> CollectorResult`，统一契约 | `collector/base.py:97` | 无采集器返回裸 list |
| P0-3 | 把 `bs4` / `lxml` 加入部署校验，缺依赖时 watchdog 告警而非静默 `parse_error` | `requirements.txt`、`jobs/watchdog.py` | 缺包时首页有明确提示 |
| P0-4 | 修复 `zhaobiao.bjx.com.cn`：改用 `www.bjx.com.cn` 主站（实测 442 链接）+ 招标关键词路由，或对该子站降级 HTTP + 放宽 SSL 校验并记录降级原因 | `collector/bjx.py:26-33` | 招标公告频道有非零供给 |
| P0-5 | `nea.py` 从只抓首页改为抓栏目页列表（首页只有 21 条，且 `/policy/index.htm` 已 404，需重新定位栏目路径） | `collector/nea.py:15` | 单轮 ≥ 30 条 |
| P0-6 | `sgcc_news.py` 的 `published_at` 现在用 `datetime(year, month, 1)` 伪造日期（`sgcc_news.py:75`），改为抓详情页真实日期或标记为不可信 | `collector/sgcc_news.py:75` | 时间线不再出现整月堆在 1 号 |

**P0 完成的标志**：跑一轮全量采集，电力侧 6 个采集器每个都有明确的 ok/失败原因，且至少 3 个有非零产出。

---

### P1 —— 供给：电力信源重建 + 正文回捞（3–5 天）

#### P1-A 正文回捞（这是内容质量的最大单点）

新增 `collector/fulltext.py`：对 `content` 为空的条目，按域名走白名单规则回捞正文，接入 `services/ingest.py` 在 prefilter 之后、scorer 之前。

- 白名单起步：`bjx.com.cn`、`nea.gov.cn`、`csg.cn`、`ccgp.gov.cn`、`sgcc.com.cn`
- 复用已有的 `core/htmlsanitize.sanitize_html`
- 失败不阻断，记 `provenance.fulltext_status`
- 加单站 ≥5min 抓取间隔（设计文档已有此约定）

**预期收益**：scorer/enricher 的输入从「一句标题」变成「标题 + 正文前 600 字」，`depth`/`utility` 才有判据，摘要才不是标题复读。这一项不做，后面所有评分调优都是在噪声上拟合。

#### P1-B 电力信源扩容

按「实测可达性」分三档推进：

**第一档（已验证可抓，优先接）**
- `www.bjx.com.cn` 主站（442 链接，比现在接的 7 个子站更富）
- `www.csg.cn`（187 链接）
- `www.ccgp.gov.cn`（278 链接，已接但需扩栏目）

**第二档（可达但需要额外处理）**
- 中电联 `www.cec.org.cn` —— 200 但只有 24 个 `<a>`，需确认是否 JS 渲染
- 国网电商平台 `ecp.sgcc.com.cn` —— SPA（3.5KB / 0 链接），需找 XHR 接口或上 Playwright；这是招标公告的权威一手源，值得投入
- 中国能源报 `paper.people.com.cn/zgnyb/` —— 403，调 UA/Referer 后重试
- `www.chinapower.com.cn` —— SSL 握手失败，同 zhaobiao 的处理方式

**第三档（待调研，本次未验证）**
- 各省电力交易中心公告（现货市场、结算规则）
- 国网/南网省公司门户（比 `nc.sgcc.com.cn` 分部站量大）
- 电力规划设计总院、中国电科院

> 注：第三档的具体 URL 需实测后再登记，不要直接写进 `seed.py`。`seed.py` 里已经有 3 条「待审核」信源就是因为地址失效（HF Blog 超时、机器之心返回 HTML、AI能见未来无 URL）。

#### P1-C AI 侧广度补齐（借 ai-news-aggregator 打法）

- 把 `collector/aggregator.py` 从「只吃 `latest-24h.json` 成品」升级为「自己接热榜站」：优先 TopHub、NewsNow、AIbase、BestBlogs、WaytoAGI
- 把 `frontier.py` 从单一快照接口扩为 HN / TLDR AI / InfoQ AI 三路（github-trending-spider 的另外三源）
- RSS 源管理从 `seed.py` 硬编码迁到 OPML 文件，支持后台导入
- 第三方微信桥（`decemberpei.cyou`，现有 9 条依赖它）加健康探测 + 备用桥声明，参考 `config.ts` 的 `replacements` 机制

---

### P2 —— 评分：双轴画像 + 分级重校准（3–4 天）

#### P2-A 拆双轴

`analyzer/scorer.py` 的五维保留，但 `relevance` 拆成两维：

- `ai_relevance` —— 与 AI 技术方向（视觉/OCR/多模态/边缘部署）的相关度
- `power_relevance` —— 与电力业务（电网规划、基建、运检、安监、市场交易、招标采购）的相关度

`analyzer/scoring.py` 的合成规则改为：

```
quality      = 加权均值 × tier_coeff × kind_coeff        # 保持不变，用于「全部」流排序
cross_score  = f(ai_relevance, power_relevance)          # 新增，双轴都高才高
is_curated   = cross_score >= 阈值                        # 精选改用 cross_score
```

`f` 建议用几何平均或 `min()`，而非算术平均 —— 算术平均会让「纯 AI 高分」照样入选，等于没改。

对应地，`core/constants.py` 的 8 频道重新归位到三条流：
- **精选**（双轴交叉）
- **AI 技术流**（大模型动态、前沿论文、AI洞察）
- **行业事件流**（行业动态、国网规划、招标公告、政策法规）

「落地案例」应该是精选流里的一个标签，不是平级频道。

#### P2-B 重校准 tier 系数

现在 T2 需要加权均值 85.7 才能入选，是硬性出局。建议：

- `tier_coeff` 收窄到 `{T1: 1.0, T1.5: 0.92, T2: 0.85}`，让分级影响排序而非一票否决
- 或改为**加法** `+bonus` 而非乘法系数（ai-hot-radar 的原话是「tier 加成」，是加法）
- `channel_thresholds` 按流分设：行业事件流阈值应显著低于精选流

改完用 `services/config_store.py` 的全库重算能力验证（这个能力已经有了，`scoring.py:3` 的注释提到过）。

#### P2-C 预筛口径

`analyzer/prefilter.py:14` 的 `POWER_KW` 只有 13 个词，且缺市场化交易类（现货、辅助服务、容量电价、绿电、需求响应、虚拟电厂）、基建类（EPC、可研、初设、竣工）。`AI_KW` 反而更全。补齐 `POWER_KW` 到与 `AI_KW` 同等颗粒度。

同时按 ai-news-aggregator 的做法，把现在的单一黑名单 `NOISE_KW` 扩为**白名单 + 黑名单双表**，尤其是对公众号源。

---

### P3 —— 产物：需求池自动化 + 行业背景落地（5–7 天）

这是把「四不像」变成「有独有价值」的关键阶段。

#### P3-A 需求池生产者

新增 `analyzer/requirement_miner.py` + `services/requirements.py`：

- 输入：`cross_score` 高于阈值的文章 + 业务知识库（部门/系统/场景三元组）
- 输出：需求候选，字段至少含 `title`（一句话「我们可以/需要做什么」）、`priority`、`rationale`、`source_article_id`、`related_system`（关联到 E基建2.0/PMS2.0 这类系统节点）
- 落库到已有的 `schema.Requirement`，`created_by` 标记为 `auto`
- 人工在 `RequirementPool.tsx` 侧栏确认/驳回，形成反馈信号

**这一步是「行业背景」真正发挥作用的地方**：知识库里的系统/场景不是用来展示的，是用来做需求抽取的上下文的。

#### P3-B 行业背景知识库填充

`seed.py` 现在只有 2 条系统 + 9 条关系。要让图谱和需求抽取有意义，至少需要：

- 国网侧主要业务系统（PMS、E基建、ERP、营销2.0/新一代营销、调度D5000、物资供应链等）
- 部门 → 系统 → 场景三层关系
- 每条带 `integration_tip`（现有 schema 已支持，是需求抽取的关键上下文）

建议做成可维护的 YAML/JSON 数据文件而非硬编码在 `seed.py`，配后台编辑入口。

#### P3-C 事件主条与多源计数（补 ai-hot-radar 缺口）

`services/clustering.py` 已有聚类，补两件事：
- 簇内按 `tier` + `firsthand` 选主条（官方稿优先于转载）
- 卡片展示「另有 N 家信源同时报道」（aihot.virxact.com 的做法）

#### P3-D 职业定向摘要（借 github-trending-spider）

`analyzer/enricher.py:12` 的 SYSTEM 增加「面向电力基建集成商算法负责人」的改写视角，摘要要回答「这条对我们的业务意味着什么」，而不是复述原文。

---

### P4 —— 形态：产品结构收敛（2–3 天，可与 P3 并行）

对齐 aihot.virxact.com 的信息架构，把入口从 6 个收到 4 个：

| 现状 | 建议 |
|---|---|
| 情报信息流（8 频道 tab） | **情报流**：精选 / AI 技术 / 行业事件 三视图 + 日期分组 + 热点 TOP 4 首屏 |
| 今日精选 | 并入情报流的「精选」视图；日报保留为流内的日期分组 |
| 研究报告 | 保留 |
| 知识中心 | **知识与需求**：知识库 + 图谱 + 需求池合并（需求池不该只是信息流的侧栏） |
| 推送订阅 | 折进设置 |
| 信源推荐 | 折进管理端「信源管理」 |

卡片字段补齐到 aihot 的密度：`时间 · 来源` + 分数 + 标题 + 摘要 + 标签 + **推荐理由** + **多源计数**。`scorer.py` 已经在产出 `reason` 了，前端要给它固定展示位。

---

## 5. 验收指标

改完之后用这几个数判断是否真的解决了问题，而不是凭感觉：

| 指标 | 现状 | 目标 |
|---|---|---|
| 电力侧采集器非零产出数 | 0 / 6 | ≥ 5 / 6 |
| 电力条目中 `content` 非空占比 | ~0% | ≥ 80% |
| 单日入库条目数（电力 : AI） | 0 : N | 至少 1 : 2 |
| 精选池中双轴交叉条目占比 | 不可测（无此维度） | ≥ 60% |
| 招标公告频道单周条目数 | 0 | ≥ 20 |
| 需求池自动生成条目 / 周 | 0 | ≥ 10，人工确认率 ≥ 40% |
| 知识库系统节点数 | 2 | ≥ 15 |
| 信源健康红灯的准确性 | 挂了显示绿 | 挂了必红 |

---

## 6. 建议的执行顺序与理由

```
P0（止血）→ P1-A（正文回捞）→ P1-B/C（信源扩容）→ P2（双轴评分）→ P3（需求池+知识库）→ P4（形态收敛）
```

**为什么正文回捞必须排在评分调优前面**：现在 scorer 的输入是一句标题，任何评分参数调优都是在噪声上拟合，改完看起来「分数变了」但质量没变。先把输入喂饱，再调权重。

**为什么定位重设要放在最前面**：P2 的双轴合成函数、P4 的入口取舍，都依赖「精选到底选什么」这个答案。这条不定，P2 调完还是会觉得四不像。

---

## 附：本次未验证 / 需要决策的点

1. **数据库现状** —— 本地 `powerai_hot.db` 是空的（articles=0）。线上/Docker 环境的实际数据分布未采样，上面关于「推荐质量」的判断是从代码和信源实测推出的，建议在有真实数据的环境跑一次分布统计（各频道条目数、各 tier 的 quality 分布、精选率）来交叉验证。
2. **tier 系数是改乘法还是改加法** —— 影响面较大（全库重算），建议先在有数据的环境用 `config_store` 的重算能力对比两种方案的精选率。
3. **`ecp.sgcc.com.cn` 是否值得上 Playwright** —— 它是招标公告的权威一手源，但是 SPA，需要评估维护成本。
4. **第三方微信 RSS 桥的长期可靠性** —— 现有 9 条信源依赖 `decemberpei.cyou`，单点风险高。

---

## 7. 本次已实施的修复（2026-07-25）

### 7.1 已在生产生效（通过 backend.env 覆盖 + 容器重建）

| 项 | 内容 |
|---|---|
| DeepSeek 模型名 | `/opt/e-ai/secrets/backend.env` 追加 `DEEPSEEK_PREFILTER_MODEL=deepseek-v4-flash`、`DEEPSEEK_SCORER_MODEL=deepseek-v4-pro`、`DEEPSEEK_WRITER_MODEL=deepseek-v4-pro` |
| 回滚点 | `/opt/e-ai/secrets/backend.env.bak-20260725-modelfix` |
| 容器 | `docker compose -p e-ai up -d backend`（注意：compose 项目名是 `e-ai`，工作目录在 `/opt/e-ai/releases/<ts>/powerai-hot`，直接在 `current/powerai-hot` 下跑会因网段冲突失败） |
| 验证 | 实调 `analyzer.scorer.score()` 返回真实五维分与推荐理由；`process_pending(limit=40)` 结果 `model_count=40, rule_count=0, errors=0` |
| 数据 | 40 条规则打分文章已重新用模型评分；`scored_by=primary_model` 从 271 升至 311 |

### 7.2 代码修改（全部已部署，见 7.4）

| 文件 | 修改 |
|---|---|
| `core/config.py:90-94` | 三个模型名默认值改为 v4 系列，附下线说明 |
| `analyzer/deepseek.py:12` | `MODEL` 改为 `deepseek-v4-pro` |
| `analyzer/scoring.py:15-18` | `tier_coeff` 由 `{T1:1.0, T1.5:0.85, T2:0.7}` 改为 `{T1:1.0, T1.5:0.92, T2:0.85}`，注释记录实测依据 |
| `services/ingest.py` | 新增 `_model_failure_reason()` / `_note_model_failure()`：模型故障写日志（4xx 配置类故障记 ERROR，临时故障记 WARNING），并汇总进 `job_run.error_summary` 与 `metadata_json.model_errors` |
| `collector/bjx.py` | 改返回 `CollectorResult`；逐子站记录失败；招标改用各子站 `/zb/` 栏目替代已下线的 `zhaobiao.bjx.com.cn`；新增发电子站与主站 |
| `collector/base.py:97` | `fetch` 签名与文档改为 `-> CollectorResult`，明确禁止返回裸 list |
| `tests/test_scoring.py`、`tests/test_models_p3.py` | 跟随新配置值 |

**验证**：`python -m pytest -q --ignore=tests/test_ops_config.py` → **375 passed**。
（`test_ops_config.py` 依赖 Unix-only 的 `fcntl`，在 Windows 上无法收集，与本次改动无关。）

**BJX 修复实测**：修复前 0 条 → 修复后 **120 条**，且内容高度对口，例如「南方电网公司2026年数字变电站、数字输电和智能配电系列传感终端以及北斗终端第一批框架招标」。

### 7.3 后续追加的修改（同样已部署）

| 文件 | 修改 |
|---|---|
| `services/ingest.py` | `rescore_pending` 改为同时捞 `scored_by='rule'` 的条目；补打分成功后改写 `scored_by`（原实现只置 `scored=True`，条目会被反复选中、白烧 3 次重试额度） |
| `services/ingest.py` | 停用 `AggregatorCollector`（T1.5 热榜源的唯一产出来源），采集器类保留 |
| `services/ingest.py` | 新增 `trusted_relevance` 元标记：人工挑定信源跳过通用相关性预筛 |
| `services/ingest.py` | GitHub Releases 调用改为 `limit=max(limit,70), per_repo_limit=3` |
| `collector/github_releases.py` | 仓库清单 8 → 23，按六条研究方向分组；去掉「达到 limit 就 break 并取消其余仓库」；跨仓按发布时间排序；`_qualified_title()` 给裸版本号补仓名；产出打 `trusted_relevance` |
| `tests/test_collectors_production.py` | 新增 5 项测试（每仓配额、跨仓时间截断、标题补全、不重复补全、trusted_relevance） |

**验证**：`python -m pytest -q --ignore=tests/test_ops_config.py` → **380 passed**，连续 3 次稳定。
新增的两项分布测试已反向验证：把旧的提前退出逻辑放回去，两项立刻失败。

### 7.4 生产变更记录

| 时间 | 内容 |
|---|---|
| backend.env | 追加三个 `DEEPSEEK_*_MODEL` 覆盖；回滚点 `backend.env.bak-20260725-modelfix` |
| `20260725T103112Z` | 模型名默认值、tier 系数、模型故障可见性、bjx 修复 |
| `20260725T105426Z` | rescore 修复 |
| `20260725T110959Z` | 停用热榜聚合源、GitHub Releases 扩容至 23 仓 |
| `20260725T112417Z` | 标题补仓名 |
| `20260725T113317Z` | trusted_relevance（当前 `current`） |

数据修复：255 条规则/未打分文章全量重跑（`scored_by='rule'` 归零）；7 条热榜源置 `已停用`；
GitHub Releases 52 行补 `trusted_relevance`、26 行补标题、13 行解除误判并重评分。

部署方式：`/opt/e-ai/staging` 从当时运行的 release 复制而来，只覆盖改动文件，
再 `SOURCE_DIR=/opt/e-ai/staging bash powerai-hot/scripts/deploy.sh`。
首次部署前对全仓 207 个文件做过哈希比对，确认无计划外漂移。

**注意**：compose 项目名是 `e-ai`，工作目录在 `/opt/e-ai/releases/<ts>/powerai-hot`。
直接在 `current/powerai-hot` 下跑 `docker compose` 会因网段冲突失败。

### 7.5 仍未做（按优先级）

1. **P2 双轴评分** —— 未做。这是精选池长期偏小的根因：当前单轴画像下，一个 vllm 发布
   对「电力基建 AI」的相关度本来就不高。修订 C 已证明调系数解决不了。
2. **P3 需求池自动化** —— 未做。`requirements` 仍为 0，全仓无任何代码创建 `Requirement`。
3. **P3 行业知识库填充** —— 未做。`knowledge_items` 仍为 0，连 seed 的 2 条都没进生产库。
4. **P2 正文回捞** —— 未做（修订 B 已将其从最高优先级降级）。
5. **P4 产品形态收敛** —— 未做。
6. **高噪音源处理** —— 未做。IT之家 74% 噪音、甲子光年 avg 1、计算机视觉life avg 4，
   本轮只动了 T1.5 热榜源，这几个 T2 噪音源仍在采集。
7. **Hugging Face Papers 长期不可达** —— `[Errno 101] Network is unreachable`，
   早于本次改动即存在，未处理。

### 7.6 已作废的原始判断

- 原 P0-3「把 bs4/lxml 加入部署校验」**前提错误**：二者已在 `requirements.txt`
  第 10、12 行声明，生产容器正常。当时的 `parse_error` 只是我本地环境缺包。
- 原文「规则打分固定给出 base ≈ 43，低于任何 tier 的入选门槛」**错误**：
  `services/ingest.py` 的 `_rule_score` 把五维全部设为同一个值（命中关键词 76，否则 62），
  在 T1 下高于阈值 60。模型故障期间不是精选被饿死，而是**精选被灌入了从未经模型评判的假分条目**。
  这解释了修复后精选数从 39 降到 35：池子变小但变真。
  （`analyzer/scorer.py` 里另有一个 `_rule_based` 才是 ~43 的那套，两者不是同一个回退。）

---

## 8. P2 双轴评分实施（2026-07-25 晚）

### 8.1 设计

原来只有一个 `relevance` 维度，画像是单极的「AI 算法负责人」，纯电力政策/招标内容的
相关度天然低分 —— 行业侧内容是被评分器主动筛掉的。现拆成两个独立维度：

| 概念 | 公式 | 语义 |
|---|---|---|
| `quality` | 六维加权均值 × tier × kind | 内容本身好不好 |
| `cross_score` | **√(ai_relevance × power_relevance)** | 落不落在交叉区 |
| `axis` | 双轴阈值分类 | 交叉 / AI / 行业 / 弱 |

**为什么用几何平均而不是算术平均**：算术平均下「AI 100 + 电力 0」= 50，纯 AI 内容
会被当成半相关塞进精选，等于没改。几何平均下等于 0 —— 只有两轴都不低才可能高。
`test_cross_score_collapses_when_one_axis_is_zero` 锁定这条性质。

**职责分离**：`axis`/`cross_score` 是内容属性，两条评分链路都算；`curated` 沿用各链路
既有门槛（频道阈值或研究方向阈值）。「交叉精选」= `curated AND axis='交叉'`，在查询层
组合，不在评分层硬编码 —— 否则会和 `_apply_thread_score` 形成两套互相打架的精选口径。

权重：`ai_relevance` 20 + `power_relevance` 20 + `firsthand` 20 + `utility` 20
+ `impact` 10 + `depth` 10。两轴合计 40，高于原 `relevance` 的 30。

### 8.2 双轴监控

新增 `GET /api/admin/axis`（管理员鉴权），三个切面 + 一个总指标：

- `by_axis` —— 四轴分布、各轴精选数与均分
- `by_source` —— 每个信源产出哪一轴（判断信源该留该砍）
- `trend` —— 逐日分布（断供预警）
- **`power_supply_ratio`** —— 行业侧供给占比（交叉 + 行业）／总量

`power_supply_ratio` 是本产品的核心风险指标：低于 20% 即说明行业侧内容不足、
正在退化回纯 AI 资讯站。前端在「流水线」页以红/绿卡片呈现，低于阈值直接告警。

前端同步：信息流新增「全部轴 / 交叉 / AI / 行业」筛选；文章卡片显示轴徽标
（交叉用金色高亮，单轴弱标注，「弱」不显示）；`cross_score` 在徽标 tooltip 里。

### 8.3 移除的模块

按业务决定移除「需求池」与「行业知识库」——生产库里 `requirements` 与
`knowledge_items` 长期为 0 行，是空壳：

- 后端：`api/requirements.py`、`api/knowledge.py` 及路由注册、三个 DTO、
  `Requirement`/`KnowledgeItem`/`KnowledgeRelation` 模型、seed 数据、迁移逻辑与相关测试
- 前端：`RequirementPool.tsx`、知识中心的「业务知识」「关系探索」两个页签及其组件、
  `Requirement` 类型与 API 客户端方法、卡片上的「加入需求池」按钮

保留 `KnowledgeCard`（个人 AI 知识卡片）与「工作空间收藏」——那是收藏功能，
与被移除的「行业知识库」不是一回事。

数据库层面保留 `requirements`/`knowledge_items`/`knowledge_relations` 三张孤儿表
（不再有模型与代码引用）。删表是不可逆操作，留着零成本，需要时再单独清理。

### 8.4 顺带修掉的缺陷

**规则分自动进精选**（根因级）。`process_pending` 里原有一段
`elif scored_by == "rule": quality = _rule_curated_score(...); article.curated = True`,
无条件把规则打分的条目标成精选、质量分固定 60。这正是 2026-07-24 模型故障期间
精选池被灌入假分条目的源头（修复后精选 39→35 就是这批被清掉）。

现改为规则分一律 `curated = False`、`hot = False`，等 `rescore_pending` 用模型补回来
再决定。`_rule_curated_score` 随之成为死代码，已删除；只测该死函数的
`test_rule_scoring_can_reach_every_channel_threshold` 一并删除。

三个断言旧行为的可靠性测试已更新为断言新行为（规则分不得进精选）。

**规则回退双轴化**。`analyzer/scorer.py` 的 `_rule_based` 原本只出单个 relevance，
现按 AI/电力两套关键词分别估分，否则模型故障期间所有条目的 `axis` 会塌成「弱」。

### 8.5 验证与部署

- 后端 **378 passed**（新增双轴评分 8 项、信息流轴筛选 3 项、监控接口 2 项、
  规则回退双轴 1 项）
- 前端 typecheck 通过、**81 passed**、lint 0 error（6 条既有 warning）、生产构建通过
- 部署 `20260725T134809Z`；迁移自动补 `cross_score` / `axis` 两列并已确认生效
- 传输前对关键文件做哈希比对，确认 staging 与本地一致

### 8.6 仍未做

- **正文回捞**（修订 B 已降级为 P2 中优先级）
- **产品形态收敛 P4** —— 入口仍是 6 + 4
- **高噪音源处理** —— IT之家 74% 噪音、甲子光年 avg 1 仍在采集
- **Hugging Face Papers** 长期不可达，早于本次改动即存在

---

## 9. 回填过程中发现的两个静默故障（2026-07-25 夜）

第一版回填跑完后，双轴分布显示「两轴几乎完全互斥、交叉区仅 2 条」，我几乎据此
得出「供给里没有 AI×电力 交集」的结论。抽查后发现是**假象**，根因有两个。

### 9.1 推理模型的 token 预算与静默降级

`deepseek-v4-pro` 是推理模型，思维链（`reasoning_content`）与正式回复（`content`）
共用 `max_tokens`。原设 300 太紧，会出现 **HTTP 200 但 `content` 为空字符串**、
内容全在 `reasoning_content` 的情况。于是 `extract_json("")` 失败，
`analyzer/scorer.py` 静默退回关键词规则估分——不抛异常、不记日志。

叠加第二个诱因：回填脚本开了 8 路并发，把接口打到限流，失败同样走静默降级。

**实测污染面：474 条里 274 条（58%）是规则估分**，而规则估分的取值恰好是
`15 + 20 × 关键词命中数` 的阶梯（15/35/55/75/90），且 AI 与电力两组关键词互不相交，
于是产出了「两轴完美互斥」的假分布。

修复：
- `max_tokens` 300 → 800
- `score()` 增加 `fallback` 布尔标记，降级可被调用方识别（此前只能靠 reason 文案反推）
- 回填脚本改为检测 `fallback` 并退避重试，并发降到 4

修复后重跑：**规则回退 274 → 2 条（0.4%）**，交叉区 2 → 19 条，平均交叉分 83。

### 9.2 提示词按文档体裁而非内容主题打分

原提示词写「与 AI 技术无关的内容（纯政策、纯招标、纯人事）应低于 20」。
模型据此按**体裁**判定：看到「招标公告」就压低 AI 轴，完全不看采购的是什么。

实测误判（修复前 → 修复后）：

| 标题 | 修复前 ai | 修复后 ai |
|---|---|---|
| 南网数字变电站、智能配电传感终端框架招标 | 15 | **85** |
| 南网红外监测及机器人管理套装软件采购 | 25 | **80** |

这两条正是本产品最该突出的情报。提示词已改为明确要求「按内容讲的是什么打分，
不要按文档体裁打分」，并给出正反例（智能传感终端采购 AI 轴应 ≥60；
常年法律顾问框架采购才是 <20）。

### 9.3 交叉区直通精选

修复后交叉区 19 条，但只有 3 条能进精选——交叉分 97 的
「国家电网：推进人工智能技术与电网业务深度融合」都被挡在外面。原因是
`curated` 走频道阈值(60)或研究方向阈值，而招标/政策类交叉内容的
`utility`/`depth` 天然低（正文就是一纸公告），加权质量分上不去。

新增 `is_cross_pick()`：交叉分 ≥ `cross_threshold`(50) 且质量 ≥
`cross_quality_floor`(35) 即直通精选，与原有通道取并集。交叉区 19/19 全部入选。

### 9.4 顺带修掉的口径不一致（既有缺陷）

`recompute_all` 无条件用 `compute_quality` 写 `relevance_score`，而 `ingest`
在有激活研究方向时写的是 `learn_score`——**两个公式写同一列**。重算过的文章
与新采集的文章分数不可比，信息流按该列排序会出现不可解释的顺序。此缺陷早于
本次改动存在，被这次全库重算放大后暴露。

`recompute_all` 已改为与 ingest 完全一致（有研究方向走 `_apply_thread_score`，
并同样应用交叉直通），新增回归测试 `test_recompute_matches_ingest_scale_when_threads_active`
锁定两者一致。

### 9.5 最终状态

| 轴 | 条数 | 精选 | 均交叉分 | 均质量 |
|---|---|---|---|---|
| AI | 241 | 28 | 21 | 34 |
| 行业 | 173 | 3 | 29 | 34 |
| **交叉** | **19** | **19** | **83** | 49 |
| 弱 | 99 | 0 | 7 | 17 |

- `power_supply_ratio` = **36.1%**（健康线 20%）
- 规则回退占比 0.4%
- 交叉产出最多的信源：北极星电力网 10、南方电网供应链 6、国家能源局 2、国家电网 1
- 后端 **383 passed**，前端 typecheck + 81 passed
- 生产 `20260725T233902Z`，公网 HTTP 200

---

## 10. 供给侧治理与产品形态收敛（2026-07-26 ~ 27）

### 10.1 高噪音信源治理

先查了一个决定性的问题：**AI 轴的 28 条精选是谁产的**。

答案是全部来自 GitHub Releases（26）与 arXiv（2）。IT之家、量子位、新智元、
DeepTech、AI前线、Anthropic News **一条都没有**。其中 IT之家 单家入库 161 条、
噪音率 80%。

据此按「噪音率 ≥40% 且从未产出精选」停用 7 个源。GitHub Trending 是代码内置
采集器，改数据库状态拦不住，已从 `build_collectors` 摘除。

更重要的是把判据做成常驻指标而不是一次性结论：信源管理页新增
**入库数 / 噪音% / 精选数 / 电力轴数** 四列，噪音 ≥40% 标红。此前只有「抓取状态 ok」，
看不出一个源是不是在白烧模型预算。

**结论有产品含义**：在 AI 这一侧不该跟媒体号拼时效，应直连一手来源（论文、
Release、官方博客）。媒体号的增量价值是「解读」，而本产品的用户不需要二手解读。

### 10.2 Hugging Face Papers

不是源坏了，是国内服务器直连 `huggingface.co` 被墙。改用 `HF_ENDPOINT=https://hf-mirror.com`
后恢复，实测返回 50 篇。错误信息同时改为携带修复提示，而非只甩一行 errno。

### 10.3 正文回捞

新增 `collector/fulltext.py`，接在预筛之后、评分之前。域名白名单制，抓到的内容
还要过两道闸：长度 ≥120 字、不命中反爬页特征词，任一不过即返回 `None` 保持原样。

**原则：宁可没有正文，不可写入脏数据。** 反爬页混进正文库会污染摘要、污染 depth
评分，而且看起来完全正常，没人会去查。

摘要质量的变化最直观：

```
之前：标题复读
之后：南方电网数字电网科技公司公示4月专项采购中标候选人：
      星环科技61.4万元中标数据服务套件，中能拾贝360…
```

**已知限制**：`news.bjx.com.cn` 是 JS 反爬（返回「为了更好的访问体验，请进行验证」），
实测加 Referer、完整浏览器头、先访问列表页拿 cookie 三种均无效。覆盖它需要引入
Playwright，对 3.6 GiB 生产机是笔不小的开销，故本模块不覆盖 bjx。这是有意取舍，
已写入模块文档。

### 10.4 产品形态收敛（P4）

- 「交叉精选」提到首屏：这是整个双轴工作的落点，此前埋在筛选器之后基本不可见
- 新增 `GET /articles/cross-picks` 与 `services/article_feed.py::get_cross_picks()`
- 「知识中心」改名「我的收藏」——行业知识库移除后该标签已名不副实
- 「情报信息流」→「情报流」

### 10.5 顺带修掉的缺陷

- `arxiv.py` / `hf_papers.py` 是最后两个返回裸 list 的采集器（与当初的 BJX 同病：
  失败会被当成「今天没有新内容」），已统一到 `CollectorResult`
- 新增**契约防回归测试**：遍历全部 13 个采集器，签名不返回 `CollectorResult` 即失败

---

## 11. 配置读写口径与陈旧文档（2026-07-28）

起因是 `services/ingest.py` 顶部注释仍写「五维评分」（P2 后实为六维）。顺藤摸出
四个真实缺陷。

### 11.1 前端「管线说明」整页停留在 P2 之前

`PipelineModule.tsx` 是面向用户的「系统如何工作」解释页，内容全是 P2 之前的世界：
权重写「方向相关 30、影响力 15、深度 15」，信源系数写 `T1.5 ×0.85 / T2 ×0.7`
（**正是当初导致 T2 恒零精选的那组值**），双轴一个字未提。已按现状重写第 5/6/7 步。

### 11.2 双轴三个阈值在管理后台够不着

`axis_threshold` / `cross_threshold` / `cross_quality_floor` 后端 `_NUMERIC_RANGE`
早已接受，但前端既不渲染也不提交——P2 最该调的三个参数只能改代码。同时
`DIM_LABEL` 未补 `ai_relevance` / `power_relevance`，两个旋钮走 `?? k` 兜底
裸露成英文键名。均已补齐。

### 11.3 `get_scoring_config` 浅合并 —— 两种静默降级

读端是 `{**DEFAULT_CONFIG, **stored}`（浅合并），写端是嵌套合并，**读写口径不一致**。
以 P2 把 `relevance` 拆成 `ai_relevance` / `power_relevance` 为例，一行 P2 之前
存下的 `dim_weights` 会造成：

| 症状 | 机制 | 后果 |
|---|---|---|
| 缺键不补 | `compute_quality` 按 `weights.items()` 加权，缺键即完全不计入 | 双轴对质量分**彻底失效** |
| 旧键不删 | 废弃的 `relevance` 仍占 30 权重却匹配不到维度值（`_dim` 返回 0），只推高 `total_w` 分母 | 加权均值整体**稀释约 23%** |

两种都不报错、不留痕迹，只是分数悄悄变低。已改为逐键合并 + 丢弃 `DEFAULT_CONFIG`
中已不存在的键。

**生产库 `scoring_config` 无存量行，因此从未被触发**——但只要有人存过一次配置就会中招。

### 11.4 `put_scoring_config` 接受未知子键

顶层键早有 `_ALLOWED_KEYS` 白名单，字典型配置的子键没有。写一个拼错的维度名
返回 200，随后被读取端静默丢弃，调用方毫无察觉——又是同一类「看起来成功了」。
已扩展校验：

```
400 {"detail":"dim_weights 含未知项: ['relevance']"}
```

### 11.5 一个定时炸弹测试与一个误导性字段

- `test_axis_monitor_reports_power_supply_ratio` 写死 `2026-07-20`，`days=7`
  窗口过期后 `trend` 恒为空。改为相对 `now` 的时间基准。
- `window_days` 与 `by_axis` / `by_source` 并排返回，但**实际只约束 `trend`**
  （前两者刻意用全量：「这个源该留该砍」问的是长期结构，短窗口样本不足会让
  判断随机跳动）。已改名 `trend_window_days`，前端在时间切换器旁加「仅影响下方趋势线」。

### 11.6 验证方式

三个新增回归测试**全部做过反证**：临时还原旧实现确认测试失败，再恢复。不是写完
看它绿就算数。后端 395 passed，前端 81 passed，typecheck / lint 0 error / 生产构建通过。
生产 `20260728T015324Z`。

### 11.7 一个意外的正面验证

交叉精选榜首是「南方电网公司党组传达学习贯彻习近平总书记近期重要讲话」，
`cross_score` 97。初看像误判，查维度分后并非如此：

```
ai_relevance 95 | power_relevance 100
理由：南方电网官方明确将打造电力人工智能底座模型"大瓦特"，推动 AI+电网场景规模化
```

标题是纯公文体裁，正文里是具体的 AI 基座模型承诺。**正文回捞（10.3）与
「按内容不按体裁打分」（9.2）两条设计在同一条数据上同时生效**——只看标题的话
这条必然被扔进噪音。

---

## 12. 待优化点（2026-07-28 实测，按价值排序）

数字均取自生产库当日实测，非估算。当前基线：入库 1175，噪音 349（30%），
有效 826，有正文 415（50%），精选 83，规则回退 0 条。

### 12.1 【高】历史条目没有正文回捞作业

回捞只作用于**新入库**条目，没有针对存量的补捞。白名单域名下仍有 **119 条**
可回捞而未回捞：

| 域名 | 缺正文 | 部署后新条目成功率 |
|---|---|---|
| www.bidding.csg.cn | 48 | 38/38 = **100%** |
| www.ccgp.gov.cn | 27 | 20/22 = **91%** |
| www.nea.gov.cn | 18 | 3/3 = 100% |
| www.csg.cn | 14 | 6/6 = 100% |
| www.nc.sgcc.com.cn | 12 | **无新条目，选择器未在生产验证** |

选择器本身是好的（部署后成功率 91–100%），只差一个一次性补捞作业。做完正文
覆盖率从 50% → 约 65%。

### 12.2 【高】北极星电力网 233 条全部标题级，而它是最大交叉源

| 信源 | 入库 | 交叉 | 精选 | 缺正文 |
|---|---|---|---|---|
| 北极星电力网 | 233 | **17** | **18** | **233（100%）** |
| 南方电网供应链 | 90 | 13 | 14 | 48 |

**交叉产出最多的源，正文覆盖率为零。** 这是当前内容质量的最大单点。需要 Playwright，
对 3.6 GiB 主机是真实成本——是引入无头浏览器、还是换用北极星的其他入口，需要决策。

### 12.3 【高】主机磁盘 85%，几次部署后可能撞上 ENOSPC

```
/dev/vda2  40G  32G 使用  5.8G 可用  85%
Docker 镜像      25.78 GB（可回收 8.70 GB）
Docker 构建缓存  11.22 GB（可回收 8.23 GB）
```

每次部署构建 2 个镜像、消耗 1–2 GB。`docker builder prune` 可安全取回 8.2 GB
且不影响回滚；清理镜像会让旧版本回滚时需要重新构建。**cutover 中途 ENOSPC 是
真实的运维风险**，建议在下次部署前处理。

### 12.4 【中】行业轴 292 条只有 4 条精选，质量通道对它基本无效

| 轴 | 条数 | 精选 | 精选率 |
|---|---|---|---|
| AI | 307 | 41 | 13% |
| 行业 | 292 | **4** | **1.4%** |
| 交叉 | 31 | 31 | 100% |
| 弱 | 148 | 0 | 0% |

交叉轴靠 9.3 的直通通道解决了，**行业轴没有对应通道**。需要一个产品判断：
纯行业内容（不含 AI）究竟应不应该进精选？如果答案是「应该」，行业轴需要自己的
低门槛通道；如果是「不应该」，那 292 条纯行业内容的采集成本就该重新评估。
**这是定位问题，不是参数问题。**

### 12.5 【中】「弱」轴 148 条通过了预筛却两轴皆低

占有效条目 18%。这些条目付了强模型的评分费用，却既不 AI 也不行业。说明预筛
口径偏松——`prefilter` 的关键词表与评分模型的判断标准不一致。收紧预筛可直接
省下这部分模型开销。

### 12.6 【中】零产出但仍在采集的信源

中国政府采购网：入库 48 条，**交叉 0、精选 0**，状态仍为「已采纳」。按 10.1
确立的判据（噪音率 + 精选产出）它已达到停用线，但因是 T1 官方源未被自动纳入
上一轮清理。需要人工确认：是源本身无价值，还是抓取的栏目选错了。

### 12.7 【低】`test_ops_config.py` 无法在 Windows 运行，且不在任何 CI 中

该文件 `import fcntl`（POSIX-only），Windows 开发机上直接收集失败；生产镜像不含
pytest（本该如此）。结果是**这个测试当前没有任何地方在跑**。它测的是运维配置
文件锁，与近期改动无关，但属于覆盖盲区。

### 12.8 【低】文档与代码没有同步机制

§11.1 的 `PipelineModule.tsx` 陈旧了整整一个大版本，是靠人肉发现的。面向用户
解释系统行为的页面若与实现漂移，比没有更糟——它会让人按错误的模型去调参。

---

## 13. 后续工作建议

### 第一批：运维止血（0.5 天，无产品风险）

1. **磁盘清理**（12.3）—— 先 `docker builder prune` 取回 8.2 GB，观察后再决定
   是否清理镜像。这是唯一有「下次部署可能失败」时限的项。
2. **历史正文补捞**（12.1）—— 一次性作业扫描白名单域名下 `content` 为空的条目，
   复用现有 `fulltext.fetch_fulltext()`，控制并发（教训见 §9.1：8 路并发触发限流
   导致 58% 静默降级）。补完后对这 119 条重跑 `enricher` 刷新摘要。
   同时验证 `www.nc.sgcc.com.cn` 的选择器——它至今没有生产样本。

### 第二批：一个必须由你拍板的定位问题（12.4）

**纯行业内容（不含 AI）该不该进精选？**

这不是调参能解决的。两条路：

| 选择 | 含义 | 代价 |
|---|---|---|
| 应该进 | 行业轴开专用低门槛通道，产品是「电力资讯 + AI 交叉」 | 精选池被政策/招标稀释，与北极星的差异化变小 |
| 不该进 | 纯行业内容只作为交叉的**候选池**存在，不单独露出 | 292 条的采集成本需重新评估，可能要砍掉部分纯行业源 |

我倾向**第二条**：产品的差异化在交叉带，纯行业内容北极星做得比我们好。但这
直接改变产品边界，应该由你决定。定了之后 12.5、12.6 的处理方式随之确定
（若走第二条，预筛应直接收紧到「必须沾 AI」，弱轴与零产出行业源一并清理）。

### 第三批：北极星正文（12.2，1–2 天，取决于第二批的结论）

如果第二批选了「不该进」，北极星的价值就集中在它产出的 **17 条交叉**上，
那么上 Playwright 只为这一部分内容服务，性价比要重新算。
如果选了「应该进」，233 条标题级内容就是最大短板，Playwright 值得上。

**顺序上必须排在第二批之后**——先定边界再投入，否则可能为一批要砍掉的内容
引入一个常驻浏览器进程。

### 第四批：防漂移（0.5 天）

1. 把 `test_ops_config.py` 纳入一个 Linux CI（或至少在部署前于容器内跑一次
   完整测试，需在镜像里保留 dev 依赖的构建阶段）（12.7）
2. 给 `PipelineModule.tsx` 加一个「说明与实现一致性」测试：从
   `analyzer/scoring.py::DEFAULT_CONFIG` 读取权重与系数，断言说明页文案中的
   数字与之一致（12.8）。这类测试成本很低，但能挡住整整一个版本的漂移。

### 不建议现在做

- **继续扩 AI 侧信源**：10.1 已证明 AI 轴精选 100% 来自一手源，加媒体号只会
  增加噪音与模型开销。
- **调整双轴阈值**：当前交叉轴 31 条 100% 精选、`power_supply_ratio` 41.5%
  （健康线 20%），参数处于健康区间。在 12.4 的定位问题定下来之前调参没有意义。
