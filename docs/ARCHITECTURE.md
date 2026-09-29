# 架构

## 总览

```
信源注册表(sources.yaml → DB)
        │
   worker 进程（单实例：PostgreSQL advisory lock）
   ├─ 调度器（APScheduler）只负责往队列放任务
   └─ 3 个消费者从 jobs 表认领任务（FOR UPDATE SKIP LOCKED，心跳 + 超时重排）
        ├─ collect   抓取列表页 → upsert items（url_hash 去重，first/last_seen）→ source_runs
        ├─ process   正文回捞 → 规则预筛 → LLM① 批量初筛 → LLM② 精读 → grounding
        │            → 打分/精选 → embedding → 事件归并 → 订阅推送
        ├─ heat / story_digests / digest / deadline_reminders / maintenance / backup
        ▼
PostgreSQL 16（pgvector + pg_trgm）
        ▲
   api 进程（FastAPI，只读为主；写操作一律入队）
        ▲
   web（Next.js 16 SSR）◄── Caddy（/api → api，其余 → web，自动 HTTPS）
```

## 目录

```
server/app/
  config.py        部署配置（环境变量）
  db.py            异步引擎；schema 只由 Alembic 管理
  models/          表定义与枚举（频道/阶段/业务线等存英文代码）
  schemas/dto.py   API 契约，前端类型由它的 OpenAPI 生成
  api/             路由：items leads stories digests settings
  collectors/      采集：base 契约、html_list 配置驱动采集器、rss、fulltext、http（限速+编码）
  pipeline/        rules → analyze(LLM) → grounding → scoring → stories → notify；tuning 为可调参数
  llm/             OpenAI 兼容客户端（JSON 模式 + 校验 + 用量记账）与 prompts/*.md
  digest/          日报/周报
  worker/          队列、任务处理器、进程入口
  seed/            sources.yaml 与同步逻辑
  cli.py           运维命令
web/
  app/             页面（全部服务端渲染，状态都在 URL 里）
  components/      feed / leads / settings / layout / ui
  lib/             api.server（SSR 取数）、api.client（浏览器写操作）、format、api-types（生成）
```

## 关键设计决定

**商机优先的打分。** 五个维度（电力基建相关度、商机价值、确定性、时效、影响面）由模型按区间锚定打 0–10 分，
总分由代码合成：`加权平均 × 10 × 信源档位系数`，「包装大于实质」再乘惩罚系数。
权重、档位系数、各档精选门槛、业务画像都存在 `app_settings`，设置页修改后下一条立即生效（有测试保证）。
旧版的问题是精选口径被研究主线关键词计数劫持，纯电力招标几乎进不了精选。

**不静默降级。** 模型调用失败的条目标记 `failed`：超时/429/5xx 自动重试；401/400（Key 失效、模型名下线）
直接挂起，不再重试，也绝不用关键词规则分冒充模型分。修好配置后在设置页一键重试。
旧版 2026-07 因 `deepseek-chat` 下线静默降级了 19 小时。

**grounding 用代码做。** 模型抽取的项目名、业主、编号、中标人、金额、电压、截止日必须在原文中找得到
（金额允许 元/万元/亿元 换算），找不到就置空并记入 `dropped_fields`，详情页显示「无法在原文核实」。

**事件归并先硬后软。** 招标编号 → 规范化项目名 → 模型 event_key → pgvector 近邻（7 天，余弦 ≥ 0.86）→
标题二字组 Jaccard（3 天，≥ 0.6）。归并在全局 advisory lock 下串行，避免并发各建一个事件。
主稿按信源档位 → 分数选举，信息流只展示主稿并提示「另有 N 家信源报道」。

**热度与质量分离。** 热度 = 各独立来源最近一次报道的 `0.5^(小时/24)` 之和 × 10，只衡量讨论度。

**信息流按「发现时间」排序。** 很多列表页只给到日期，发现时间更精确，也能反映平台比别人早发现多少。
游标分页 `(first_seen_at, id)`，部分索引覆盖精选流与频道流。

**API 进程不跑后台任务。** 「立即采集」「生成日报」等写操作只入队；同一 `dedupe_key` 的任务在排队/执行中时不会重复入队。

## 数据表

| 表 | 用途 |
|---|---|
| sources / source_runs | 信源定义与每次采集的审计（传输/解析状态、抓取数、新增数、耗时） |
| items | 条目：原文、状态、频道、摘要/理由/动作、五维分、精选、事件、向量、收藏/已读/笔记 |
| leads | 商机结构化字段（1:1 items）+ 个人跟进状态 |
| stories | 事件：key、综述、来源数、热度 |
| watch_rules / notifications | 订阅规则与推送记录（唯一约束保证不重复推送） |
| digests | 日报/周报（版块引用条目 id） |
| jobs | 持久任务队列 |
| llm_calls | 每次模型调用的真实 token、费用、耗时、错误 |
| app_settings | 业务画像与打分参数 |
| gold_labels / eval_runs | 精选校准：人工标注「该选/不该选」与每次评测的指标、门槛扫描、逐条结果 |
