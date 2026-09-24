# E-AI 腾讯云生产可靠性重构设计

**状态：** 待独立评审  
**目标环境：** 腾讯云轻量服务器 `tencent-lighthouse`，Ubuntu 24.04，4 vCPU / 3.6 GiB RAM / 40 GiB 系统盘  
**目标：** 不推倒现有产品，替换供给与运行层，使平台在腾讯云无人值守运行；即使 AI 模型不可用，原始内容仍持续入库，并且每次运行都有可审计证据。

## 1. 用户结果

部署完成后用户获得：

1. 一个 HTTPS 可访问的 E-AI 平台；
2. AI 热点自动更新，不依赖 Windows、WSL 或浏览器进程；
3. 每条新内容具有真实来源关系、标准发布时间和原文链接；
4. 主模型失败时自动降级，不能导致内容供给归零；
5. 管理端能查看任务运行、各信源状态、抓取/入库/精选/降级统计；
6. RSS 与健康接口独立于主页面可用；
7. 可回滚到部署前版本，数据库与环境变量不进入 Git。

## 2. 本期边界

### 必须完成

- 独立采集 CLI，Web 进程不再承载定时调度；
- `job_runs` 和 `source_runs` 持久运行账本；
- 原始记录先提交，再执行 AI 分析；
- `source_id`、`published_at`、`ingested_at`、`processing_status`、`scored_by` 数据契约；
- 区分正常零条、传输失败、Schema 错误和解析失败；
- 主模型、备用兼容模型、规则回退三档；
- AIHOT、ai-news-aggregator、官方 RSS/GitHub Releases 等稳定供给；
- RSS、运行状态 API、每日摘要生成；
- PostgreSQL、Docker Compose、Caddy HTTPS、systemd timer；
- 旧 SQLite 数据迁移到 PostgreSQL；
- 自动重启、资源限制、备份、日志轮转、部署/回滚脚本；
- 完整测试、故障注入和生产验收。

### 本期不做

- 大规模前端改版；
- 知识图谱重写；
- 全量 embedding 回填；
- 商机雷达；
- 四个尚为空骨架的复杂电力网站爬虫；
- 自建微信公众号桥；
- Redis/Celery。

## 3. 生产拓扑

```text
Internet 80/443
       |
   host Caddy (TLS)
       |
127.0.0.1:8080
       |
 container nginx
   |           |
frontend     backend
                |
            PostgreSQL

systemd timers
   -> docker compose run --rm backend python -m jobs.ingest --group news
   -> docker compose run --rm backend python -m jobs.ingest --group papers
   -> docker compose run --rm backend python -m jobs.digest
```

- Caddy 是唯一公网入口；应用容器端口仅绑定回环地址。
- PostgreSQL 不发布主机端口。
- Redis/Celery 删除，避免在 3.6 GiB 主机增加无必要常驻组件。
- 定时命令使用 `flock` 防止重叠。
- Compose 服务均设置 `restart: unless-stopped`、健康检查、日志轮转和合理内存限制。

## 4. 数据模型

### `job_runs`

- `id`
- `run_key`，唯一，格式 `<job>:<时间窗>`
- `job_name`
- `started_at` / `finished_at`
- `status`: `running | ok | degraded | failed | skipped`
- `fetched` / `inserted` / `selected`
- `model_count` / `fallback_model_count` / `rule_count`
- `source_failures`
- `error_summary`
- `metadata_json`

### `source_runs`

- `id` / `job_run_id` / `source_id`
- `attempted_at` / `finished_at` / `duration_ms`
- `transport_status`: `ok | timeout | http_error | network_error`
- `parse_status`: `ok | empty | schema_error | parse_error`
- `fetched_count`
- `newest_item_at`
- `error_summary`

### `articles` 新增/修正

- `source_id`：新入库记录必须非空；
- `published_at`：UTC aware datetime；
- `ingested_at`：UTC aware datetime；
- `processing_status`: `pending | processed | degraded | failed`；
- `scored_by`: `primary_model | fallback_model | rule | unscored`；
- 保留 `crawled_at` 兼容历史接口；
- `url_hash` 唯一约束继续作为内容幂等键。

旧记录允许缺少 `source_id/published_at`；迁移脚本尽力按域名匹配来源，无法可靠推断时保持空值并生成迁移统计，不伪造数据。

## 5. 原始优先流程

```text
fetch
 -> validate transport/content-type/schema
 -> normalize canonical URL/source/published_at
 -> insert Article(processing_status=pending, scored_by=unscored)
 -> commit raw batch
 -> process pending items
 -> update enrichment/score/provenance
 -> commit each item or bounded batch
```

约束：

- 模型调用发生在原始提交之后；
- 任一模型异常不能回滚原始内容；
- 下轮任务会继续处理 `pending/degraded`；
- 单个来源失败不影响其他来源；
- 单条分析失败不影响整批。

## 6. AI 降级

1. 主模型：现有 DeepSeek；
2. 备用模型：现有 OpenAI 兼容 `CustomAnalyzer`，仅在完整配置时启用；
3. 规则档：确定性关键词/来源/类型评分。

必须满足：

- 超时、429、5xx 最多 3 次指数退避；
- 格式错误视为本次模型失败；
- `scored_by` 写入文章和任务统计；
- 规则档使用独立阈值或保证其理论分数范围可越过对应阈值；
- UI/API 明示降级来源；
- 缺 Key、主模型断网、非法 JSON 情况下，原始供给仍成功且至少产生可浏览内容。

## 7. 信源策略

首批：

- AIHOT 公共 API：精选与最近内容，保留其 attribution；
- ai-news-aggregator `latest-24h.json`：作为广覆盖聚合源；
- 现有 RSS / arXiv / Hugging Face；
- GitHub Releases RSS：PaddleOCR、MinerU、Ultralytics、MMDetection、vLLM、ComfyUI、TensorRT-LLM、QwenLM 等；
- 官方博客 RSS。

每个采集器返回结构化结果，而不是仅返回 `[]`。内容去重按规范化 URL hash；跨 URL 重复继续交由现有聚类处理。

外部聚合源不得成为唯一供给；任何单一聚合源故障时，官方源仍可独立产生内容。

## 8. 调度与状态

- news：每 2 小时；
- papers：每天 06:10（Asia/Shanghai）；
- digest：每天 08:00；
- backup：每天 03:30；
- health watchdog：每 15 分钟检查最新成功任务、最新文章和 Compose 健康。

`run_key` 由 job + 确定性时间窗生成；相同窗口重复执行只允许一条有效运行记录。异常退出留下 `running` 时，后续 watchdog 标记为 `failed/stale`。

## 9. 对外接口

- `/health`：进程与数据库连通；
- `/api/system/status`：最新任务、数据新鲜度、降级比、失败信源；管理权限；
- `/api/rss.xml`：只输出公开来源的精选内容，不包含私人笔记、收藏和内部字段；
- 现有前端继续使用现有鉴权。

## 10. 迁移、部署与回滚

- 部署目录：`/opt/e-ai`；
- 生产数据：Docker named volumes；
- secrets：`/opt/e-ai/secrets/backend.env`，root/部署用户可读，不进入 Git；
- 旧 SQLite 只读传输到迁移目录；
- 先建 PostgreSQL schema，再运行可重复、按主键/唯一键跳过的导入；
- 导入后核对各表计数、文章最新时间和关键关系；
- 首次上线前备份旧 SQLite；上线后 `pg_dump` 每日压缩保留 7 天；
- 每次发布保留前一版 release 目录和数据库备份；
- 回滚脚本恢复前一 Compose release；若涉及破坏性 schema 变更，先恢复对应备份。

## 11. 安全

- 公网仅 22/80/443；
- PostgreSQL、backend、frontend 不直接公网暴露；
- 生产 secrets 只通过受限 env 文件注入；
- 日志不得打印 token、Cookie、模型 Key 或数据库密码；
- Caddy 自动 HTTPS；HTTP 重定向 HTTPS；
- 管理和 workspace token 使用随机高熵值；
- RSS 仅包含原本公开内容；
- 部署前扫描 Git diff 的明文凭据、危险 shell、SQL 拼接和不安全反序列化。

## 12. 客观验收标准

### 代码与本地

1. 新行为均有先失败后通过的自动化测试；
2. 后端全量 pytest 通过；
3. 前端单测、lint、typecheck、build 通过；
4. Compose config 有效，所有服务健康；
5. 无新明文 secret；
6. 独立 Codex 会话终验完整 diff。

### 数据与故障

1. 新入库文章 `source_id` 完整率 100%；
2. 可提供发布时间的信源，`published_at` 完整率不低于 95%；
3. 同一 URL 重跑不重复；
4. 相同时间窗重复 job 不产生重复有效运行；
5. 模型 Key 为空、429/5xx/超时、非法 JSON 时原始内容仍入库；
6. 正常零条、传输失败、Schema 错误、解析失败在 `source_runs` 中可区分；
7. 旧 SQLite 文章数迁移后不减少，除非有明确、可审计的重复冲突统计。

### 生产

1. HTTPS 页面可从外部访问，HTTP 自动跳转；
2. `/health`、前端、鉴权登录、文章列表、详情、RSS 可用；
3. 手动触发 news job 后 `job_runs` 和 `source_runs` 有记录，并有新内容；
4. 停掉 Web 容器时独立采集仍能运行；
5. 杀死容器后自动恢复；
6. 主模型故障注入不导致断供；
7. 数据库备份文件实际生成并可读取目录清单；
8. 至少完成一次部署后回滚演练（不破坏生产数据）；
9. 进入连续 7 天观察期：每天有新内容、无缺失预期任务；如用户在观察期开始前查看结果，应明确显示当前累计运行天数，而不得伪称已完成 7 天。

## 13. 实施角色

- Claude：现有方案的独立架构反驳已经完成；本设计再做冻结评审；
- Codex 会话 A：严格 TDD 实施与自测；
- Codex 会话 B：独立终验，不共享会话；
- Hermes：基线、证据核验、腾讯云部署、故障注入、回滚和最终验收。
