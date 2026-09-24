# 电力 AI-hot

面向电力基建与能源行业的 AI 情报聚合、研究和知识沉淀平台。产品参考 [AI HOT](https://aihot.virxact.com/) 的阅读型信息流，将多信源采集、规则预筛、模型评分、事件聚类、日报、收藏、知识卡片和研报串成一条可回溯的研究工作流。

> 当前状态：已基于 main 完成同源会话/访问矩阵、单调度器、文章分页、真实搜索、前端依赖安全整改和移动端适配（≤768px 底部导航 + 抽屉需求池）。后端、前端单测、浏览器 E2E 与生产构建均有自动验证；公开部署仍需配置 TLS 与正式数据库凭据。详细证据见 [AI HOT 参考研究与项目全面自检](docs/AIHOT_REFERENCE_AND_PROJECT_AUDIT.md)。

## 已实现能力

前端目前包含 11 个业务入口：

- 情报信息流：8 个频道、服务端游标分页、真实搜索、时间/精选/噪声/标签/排序筛选、入库时间线、动态热点、已读置灰和需求池。
- 情报详情：站内富文本全文阅读（RSS/公众号全文经白名单消毒）、一键导出 Markdown、原文外链。
- 今日精选：按日期生成事件聚类后的零 LLM 日报。
- 我的知识库：收藏、AI 知识卡片、卡片重试和编辑。
- 研报：周报与主题研报生成、状态跟踪和阅读。
- 业务知识库、知识关系图谱：承接内部业务知识。
- 推送订阅、信源提报：关键词订阅、飞书推送和信源登记。
- 流水线、信源管理、管理后台：运行状态、评分配置、采集和任务观测。

真实采集器已覆盖北极星电力网、RSS、arXiv 和 Hugging Face Papers；国网新闻、南网新闻、国家能源局和政府采购采集器仍是待接入骨架。DeepSeek 分析链路已实现（默认），另支持任意 OpenAI 兼容的自定义模型端点（`CUSTOM_API_URL` / `CUSTOM_API_KEY` / `CUSTOM_MODEL`）。

## 架构

```text
外部信源
  └─ collector（BJX / RSS / arXiv / HF Papers）
       └─ ingest：规范化、URL 去重、入库
            └─ analyzer：预筛 → 评分 → 富化 → 向量/卡片
                 └─ services：聚类、日报、收藏、研报、推送
                      ├─ FastAPI API
                      ├─ APScheduler（默认 Compose 单实例）
                      └─ Next.js 15 前端
```

| 层级 | 技术 |
|---|---|
| 前端 | Next.js 15 App Router、React 18、TypeScript、Tailwind |
| 后端 | FastAPI、Python 3.11、SQLAlchemy 2 |
| 数据库 | 本地 SQLite；生产建议 PostgreSQL 16 |
| 异步/调度 | 默认 APScheduler；Celery 代码仅作为未来可选方案 |
| 采集 | HTTP、BeautifulSoup、RSS、arXiv/HF 公共数据源 |
| AI | DeepSeek（默认）；可切换 OpenAI 兼容自定义模型端点；Embedding 接口 |
| 部署 | Docker Compose、Nginx |

## 目录

```text
powerai-hot/
├─ backend/
│  ├─ api/          FastAPI 路由与 DTO
│  ├─ analyzer/     预筛、评分、富化、向量、知识卡片
│  ├─ collector/    信源采集器
│  ├─ core/         配置、鉴权、安全和运行时工具
│  ├─ models/       SQLAlchemy 模型、初始化和轻量迁移
│  ├─ scheduler/    APScheduler/Celery 任务与监控
│  ├─ services/     入库、聚类、日报、卡片和研报服务
│  └─ tests/        后端测试
├─ frontend/
│  ├─ app/          App Router 页面
│  ├─ components/   业务模块与通用组件
│  └─ lib/          API 客户端、类型和数据钩子
├─ docs/            当前架构、自检与优化文档
├─ scripts/         本地启动脚本
├─ docker-compose.yml
└─ nginx.conf
```

## 本地启动

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-backend.ps1
# 新终端
powershell -ExecutionPolicy Bypass -File scripts\run-frontend.ps1
```

访问：

- 前端：<http://127.0.0.1:3010>
- 后端 API：<http://127.0.0.1:8010>
- 本地调试文档：<http://127.0.0.1:8010/docs>

手动启动和端口说明见 [启动说明](启动说明.md)。首次执行 `python -m models.seed` 只建立基础信源、知识库参考和订阅关键词，不再灌入演示情报。

## 验证

```powershell
cd backend
python -m pytest -q

cd ..\frontend
npm.cmd ci
npm.cmd run lint
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npm.cmd exec playwright test
npm.cmd audit --audit-level=moderate
```

当前基线为后端 303 项测试、前端 82 项单元/组件测试和 5 条门户 E2E；Next 15 生产构建通过，`npm audit --audit-level=moderate` 为 0。ESLint 已可非交互执行，仍报告 6 条既有 warning，不阻断构建。

## 部署提醒

浏览器只使用同源 HttpOnly 会话；不要把任何密钥放入 `NEXT_PUBLIC_*`。公网部署前仍必须阅读 [部署指南](DEPLOY.md)，配置 HTTPS/HSTS、独立数据库凭据、备份和网关限流，并在有 Docker 的环境运行 `scripts/verify-compose.ps1`。
