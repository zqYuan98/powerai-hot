# 运维手册

## 首次部署（腾讯云服务器）

前提：已安装 Docker 与 Docker Compose v2；有域名时把 A 记录指向服务器并放行 80/443。

```bash
git clone <仓库> powerai && cd powerai/deploy
cp .env.example .env && vi .env        # 填口令、密钥、数据库密码、LLM Key、域名
bash deploy.sh                         # 构建 → 迁移 → 同步信源 → 启动 → 健康检查
```

浏览器打开 `https://<域名>` 即可浏览（前台匿名可读）。后台在 `https://<域名>/settings`，导航里没有入口，访问时会跳到登录页，用 `APP_PASSWORD` 登录。worker 启动后 1 分钟内开始第一轮采集。

公开上线前确认 `.env` 里：`PUBLIC_BASE_URL` 改成真实域名（RSS、REST API、llms.txt 里的链接都用它）；国内服务器绑定域名时填 `SITE_ICP`（页脚展示备案号）；想收到访客反馈提醒就配 `FEISHU_WEBHOOK_URL`。

## 公开访问与后台

- 访客能看：精选、商机、热点、日报、全部、搜索、事件、条目详情，以及「更多」里的 Agent 接入、关于、更新日志、反馈。
- 只有管理员能看、能改：后台（`/settings`）、笔记、商机跟进状态与备注、被淘汰/失败的条目、手动生成日报。访客看到的数据里不带这些字段（后端过滤，不只是前端隐藏）。
- 访客的收藏只存在各自浏览器里；管理员的收藏仍存服务器。
- 限频（按 IP，API 进程内计数）：访客搜索每分钟 20 次，反馈每 10 分钟 5 条。
- 给 Agent 的公开接口：`/api/mcp`（MCP）、`/api/v1/*`（REST，定义在 `/api/v1/openapi.json`）、`/feed.xml` 与 `/feed/*`（RSS）、`/llms.txt`。允许跨域，匿名只读。
- 访客反馈在「后台 → 访客反馈」处理；配置了飞书时由 worker 推送提醒。
- 知识库（导航「知识」）：管理员登录后，页面顶部多一个收录框，下方是「待处理 / 失败 / 未通过 / 重复 / 已隐藏」队列。抓取失败的（公众号风控、纯图片文章）不会自动重试，粘贴正文重新提交即可。接入自动订阅见 docs/SOURCES.md「知识库信源」。
- 更新日志写在 `web/content/changelog.json`：新条目加在最前面，并把 `latestVersion` 改成它的日期时间，访客导航上会出现小红点。

更新版本：`git pull && bash deploy/deploy.sh`（迁移可重复执行）。

## 日常检查

「后台 → 信源与流水线」：

- 信源状态为「连续失败」：展开看运行记录里的 HTTP 状态与错误。站点改版就改 `sources.yaml` 里的正则或列表页，WAF 拦截就试 HTTP 入口或调整请求头。连续失败的信源会自动退避（最多 8 倍间隔）。
- 「失败待处理」不为 0：到「模型用量 → 最近错误」看原因。`HTTP 401/402/400 配置/额度故障` 需要修 Key、余额或模型名，修好后点「重试失败条目」。
- 精选太多/太少：先到「精选校准」看评测里判错的是哪一类，再改评分标准或业务画像；整体偏松偏紧且判错的条目分数都贴着门槛时，才去「画像与打分」调门槛。

## 精选校准

「后台 → 精选校准」：

1. **标注**：逐条判断「该不该进精选」（快捷键 1 该选 / 2 不该选 / 3 两可 / S 跳过）。页面只给原文，不显示 AI 的分数和摘要，避免被系统判断带偏。抽样偏向差一点入选、差一点落选的难例；`item_id` 能被 5 整除的自动进留出集。建议先标 150 条左右。
2. **基线**：评测方式选「线上已有判断」，不花钱，得到查准率、查全率、按层/档位/频道的判错分布、门槛扫描和判错清单。
3. **改一版再比**：改提示词（`server/app/llm/prompts/`）或打分参数后，选「用当前提示词和参数重跑」，在同一批样本上对比。调提示词只看开发集，定稿前再跑一次留出集。重跑不写回条目，花费记在「模型用量」的「评测·」任务下。

有标注的条目不会被维护任务清掉正文；标注随数据库一起备份。

## 常用命令

```bash
cd deploy
docker compose logs -f worker                          # 采集/处理日志
docker compose exec api python -m app.cli collect nea   # 立即采集某信源并处理
docker compose exec api python -m app.cli process       # 处理所有待处理/可重试条目
docker compose exec api python -m app.cli digest daily  # 立即生成今天的日报
docker compose exec api python -m app.cli backup        # 立即备份
docker compose exec api python -m app.cli reindex       # 补算向量并重建事件归并（首次配置 Embedding 后）
docker compose exec api python -m app.cli eval --split all          # 按人工标注评测线上判断（不花钱）
docker compose exec api python -m app.cli eval --rerun --label 说明  # 用当前提示词重跑开发集（调模型）
docker compose exec db psql -U powerai                  # 数据库
```

## 定时任务（worker 内置，北京时间）

| 任务 | 频率 |
|---|---|
| 调度采集（按各信源间隔，失败退避） | 每分钟检查 |
| 重试失败/滞留条目 | 每 15 分钟 |
| 热度重算、事件综述 | 每 30 分钟 |
| 队列维护（恢复心跳超时任务、清理旧任务） | 每 10 分钟 |
| 日报 / 周报 | 每天 08:00 / 周一 08:30 |
| 截止提醒 | 09:05、16:05 |
| 数据库备份 | 03:30，保留 14 天 |

## 备份与恢复

见 [deploy/backup-restore.md](../deploy/backup-restore.md)。

## 本地开发

```bash
docker compose -f deploy/compose.dev.yml up -d          # 只起数据库
cd server && cp .env.example .env
uv sync && uv run alembic upgrade head && uv run python -m app.cli seed
uv run uvicorn app.main:app --reload --port 8000        # API（http://127.0.0.1:8000/api/docs）
uv run python -m app.worker.main                        # worker（另开终端）
cd ../web && npm install && npm run dev                 # 前端 http://127.0.0.1:3000
```

没有 Docker 时，测试会用 `pgserver` 自动拉起临时 PostgreSQL，`uv run pytest` 即可。

## 质量门禁

```bash
cd server && uv run ruff check app tests && uv run mypy app && uv run pytest
cd web && npm run lint && npm run typecheck && npm test && npm run build
# E2E：用 tests/e2e_seed.py 灌一个名字含 e2e 的测试库，起 API + Web 后
E2E_BASE_URL=http://127.0.0.1:3000 npx playwright test
```

后端改了 API 契约后执行 `cd web && npm run gen:api` 重新生成前端类型。
