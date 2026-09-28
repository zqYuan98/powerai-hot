# 信源登记与实测记录

信源定义在 [server/app/seed/sources.yaml](../server/app/seed/sources.yaml)，部署时 `python -m app.cli seed` 同步进数据库。
已存在的信源只同步定义（URL、正则、档位等），**不会覆盖设置页里改过的启停与采集间隔**。

## 如何新增一个信源

大多数政府、电网、招标站点是「列表页 + 文章链接」结构，不需要写代码，只加一段配置：

```yaml
- key: example-bidding          # 全局唯一，小写字母/数字/短横线
  name: 某某电子采购平台
  kind: html_list
  url: https://example.com/
  tier: T1                      # T1 官方一手 | T1_5 行业媒体 | T2 综合媒体
  category: tender              # 默认频道；标题规则会进一步纠正（中标/核准等）
  interval_min: 60
  notes: 实测记录、已知限制
  config:
    lists:
      - {url: "https://example.com/zbgg/", channel: tender}
    link_pattern: 'https://example\.com/zbgg/(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})/\d+\.html'
    min_title_len: 10
    title_keywords: []          # 非空时标题须命中任一（综合采购平台用它过滤非电力项目）
    date_from_parent: false     # URL 无日期时，从链接所在行解析日期
    https_upgrade: false
    fulltext_selectors: ["div.article"]   # 详情页正文容器，按优先级
```

验证步骤：

1. 在 `server/tests/test_collectors.py` 加一段真实列表页 HTML 片段的解析测试。
2. `python -m app.cli seed && python -m app.cli collect example-bidding --no-process`，看抓取条数与新增数。
3. 在「设置 → 信源与流水线」观察 24 小时成功率与 7 天新增/精选比，精选比长期为 0 的信源应停用并在 `notes` 写明原因。

需要调用接口或渲染 JS 的站点用 `kind: custom`，在 `app/collectors/` 写实现并用 `@register("key")` 注册。

## 当前信源（2026-09-28 实测）

| key | 名称 | 档位 | 状态 | 备注 |
|---|---|---|---|---|
| bjx-tender | 北极星·招标（输配电/储能/发电 `/zb/`） | T1_5 | ✅ 75 条/轮 | 原 zhaobiao.bjx.com.cn 已下线；详情页 JS 反爬，只有标题 |
| bjx-news | 北极星（政策栏目 + 首页） | T1_5 | ✅ 125 条/轮 | 同上 |
| nea | 国家能源局首页 | T1 | ✅ 30 条/轮 | `/policy/index.htm` 已 404 |
| sgcc-nc | 国家电网华北分部 | T1 | ✅ 34 条/轮 | 主站 JS 风控 412；党建/人事稿偏多，6 小时一次 |
| csg | 南方电网官网 | T1 | ✅ 22 条/轮 | |
| ccgp | 中国政府采购网（中央/地方公开招标） | T1 | ✅ 可达 | **HTTPS 入口被 WAF 返回 403，改走 HTTP**；按电力/运检关键词过滤，非电力项目多时 0 条属正常 |
| csg-bidding | 南方电网供应链 | T1 | ✅ 34 条/轮 | |
| jiazi-wechat | 甲子光年（公众号桥） | T2 | 默认关闭 | 第三方 RSS 桥有失效风险 |
| nvidia-blog | NVIDIA Blog | T1 | 默认关闭 | 边缘推理/视觉硬件动态 |

## 候选信源（待实测后接入）

按商机价值排序：

| 站点 | 已知情况 | 接入思路 |
|---|---|---|
| 国网电子商务平台 `ecp.sgcc.com.cn` | SPA，首页 3.5KB、0 个链接 | **最高价值的一手招标源**。先在浏览器开发者工具里找列表 XHR 接口写 `custom` 采集器；接口带签名再考虑 Playwright（`uv sync --extra browser`） |
| 中国招标投标公共服务平台 | 未验证 | 全国招投标汇总，量大，需关键词过滤 |
| 五大发电集团 / 中国电建 / 中国能建 电子采购平台 | 未验证 | 各选 1–2 个，EPC 与分包机会多 |
| 各省发改委 / 能源局 项目核准公示 | 未验证 | 「核准」早于招标，最能提前发现商机 |
| 中电联 `www.cec.org.cn` | 200，但只有 24 个链接 | 疑似 JS 渲染，需二次确认 |
| 中国能源报 `paper.people.com.cn/zgnyb/` | 403 | 调整 UA/Referer 重试 |
| `www.chinapower.com.cn` | SSL 握手失败 | 试 HTTP 入口（同 ccgp） |
| 各省电力交易中心 | 未验证 | 现货市场、结算规则 → 市场频道 |

## 已放弃的信源（不再迁移）

旧版为「AI × 电力」双轴定位接入的 AI 论文/资讯源，与「电力商机优先」定位不符：
arXiv、Hugging Face Papers（国内长期不可达）、GitHub Releases、aihot、ai-news-aggregator 快照、GitHub Trending 快照。

旧版停用记录（2026-07-26 按噪音率停用）：IT之家 80% 噪音、Anthropic News 45%、量子位 40%、计算机视觉life 83%、AI前线 40%、DeepTech 58%，均零精选。
