# 电力基建情报站

面向电力基建的**商机优先**情报系统：自动采集电网公司、政府与招标平台的一手信息，用大模型精读、打分、抽取商机字段，
帮你更早发现与「智能运检 / AI 视觉」「输变电工程施工 / EPC」相关的招标、项目核准、规划与政策。

## 能做什么

- **精选**：按天分组的信息流。每条都有中文短标题、60–120 字摘要、推荐理由、建议动作、AI 评分；同一事件多家报道自动合并为「另有 N 家信源报道」。
- **商机看板**：从招标/中标/核准/规划中抽取项目名、业主、金额、电压等级、阶段、截止时间、编号；按省份、阶段、业务线、金额、电压筛选；截止倒计时；记录跟进状态与备注。抽取字段必须能在原文中核实，否则不显示。
- **热点**：48 小时内被最多独立信源报道的事件，点进去是项目/事件时间线与 AI 综述（含「尚未披露」的关键信息）。
- **日报 / 周报**：每天 08:00、每周一 08:30 自动出刊，报纸式版面：看点、头条、商机速递、政策规划、电网与市场。
- **订阅推送**：关键词/省份/金额/电压规则命中时推送飞书；关注中的商机截止前 3 天提醒。
- **设置**：信源健康（成功率、新增、精选比、运行记录）、业务画像与打分权重（实时生效）、模型调用量与费用、任务队列。

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.12、FastAPI（async）、SQLAlchemy 2 + asyncpg、Alembic、uv |
| 数据库 | PostgreSQL 16 + pgvector（事件归并、语义搜索）+ pg_trgm（关键词搜索） |
| 后台任务 | 单个 worker 进程：APScheduler 定时入队 + PostgreSQL 持久队列（SKIP LOCKED） |
| 模型 | 任意 OpenAI 兼容端点，默认 DeepSeek：flash 关闭推理做初筛与精读（约 3 秒/条），v4-pro 低强度推理写日报与事件综述；Embedding 默认硅基流动 BGE-M3 |
| 前端 | Next.js 16 App Router（SSR）、React 19、Tailwind CSS 4、类型由后端 OpenAPI 生成 |
| 部署 | Docker Compose：db / api / worker / web / caddy（自动 HTTPS） |

## 快速开始

生产部署：

```bash
cd deploy && cp .env.example .env   # 填写口令、密钥、LLM Key、域名
bash deploy.sh
```

本地开发、日常运维与质量门禁见 [docs/RUNBOOK.md](docs/RUNBOOK.md)。

## 文档

- [架构与关键设计决定](docs/ARCHITECTURE.md)
- [信源登记、新增方法与实测记录](docs/SOURCES.md)
- [运维手册](docs/RUNBOOK.md)

## 目录

```
server/   后端、采集、分析管线、worker（Python）
web/      前端（Next.js）
deploy/   Compose、Caddyfile、部署脚本、环境变量模板
docs/     架构、信源、运维文档
```
