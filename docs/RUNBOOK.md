# 运维手册

## 首次部署（腾讯云服务器）

前提：已安装 Docker 与 Docker Compose v2；有域名时把 A 记录指向服务器并放行 80/443。

```bash
git clone <仓库> powerai && cd powerai/deploy
cp .env.example .env && vi .env        # 填口令、密钥、数据库密码、LLM Key、域名
bash deploy.sh                         # 构建 → 迁移 → 同步信源 → 启动 → 健康检查
```

浏览器打开 `https://<域名>`，用 `APP_PASSWORD` 登录。worker 启动后 1 分钟内开始第一轮采集。

更新版本：`git pull && bash deploy/deploy.sh`（迁移可重复执行）。

## 日常检查

「设置 → 信源与流水线」：

- 信源状态为「连续失败」：展开看运行记录里的 HTTP 状态与错误。站点改版就改 `sources.yaml` 里的正则或列表页，WAF 拦截就试 HTTP 入口或调整请求头。连续失败的信源会自动退避（最多 8 倍间隔）。
- 「失败待处理」不为 0：到「模型用量 → 最近错误」看原因。`HTTP 401/402/400 配置/额度故障` 需要修 Key、余额或模型名，修好后点「重试失败条目」。
- 精选太多/太少：到「画像与打分」调各档门槛；某类内容总被高估/低估，先改业务画像的措辞。

## 常用命令

```bash
cd deploy
docker compose logs -f worker                          # 采集/处理日志
docker compose exec api python -m app.cli collect nea   # 立即采集某信源并处理
docker compose exec api python -m app.cli process       # 处理所有待处理/可重试条目
docker compose exec api python -m app.cli digest daily  # 立即生成今天的日报
docker compose exec api python -m app.cli backup        # 立即备份
docker compose exec api python -m app.cli reindex       # 补算向量并重建事件归并（首次配置 Embedding 后）
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
