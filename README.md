# 真人口播 + 公众号自动化脚本

这套模板帮你完成 3 件事：

1. `topic_collector.py`：自动抓取热点，生成可用选题池。
2. `content_generator.py`：一键生成 30 秒短视频成片包（标题 + 口播 + 封面 + 配音）。
3. `weekly_report.py`：自动输出每周复盘报告。
4. `videohao_mimic_analyzer.py`：分析视频号历史数据并输出仿写策略（标题库+脚本）。
5. `videohao_daily_monitor.py`：每日统计相关内容，重点关注福饱饱并自动生成新文案。
6. `videohao_login_fetch.py`：网站登录采集（本机登录导出CSV后自动接收并跑日报+文案）。

## 1) 目录说明

```text
creator_automation/
├─ config.json               # 你的正式配置（已创建，可直接改）
├─ config.example.json       # 配置示例
├─ topic_collector.py        # 选题抓取
├─ content_generator.py      # 30秒短视频成片包生成
├─ weekly_report.py          # 周报复盘
├─ run_daily.ps1             # 每日一键运行
├─ run_weekly.ps1            # 每周一键运行
├─ fubaobao6_content_pack.md # 现成文案与标题库
├─ videohao_mimic_analyzer.py # 视频号数据仿写分析
├─ videohao_daily_monitor.py  # 每日监控+自动出稿
├─ run_videohao_daily.ps1     # 每日监控一键运行
├─ videohao_login_fetch.py    # 登录采集+自动跑日报
├─ run_videohao_login_daily.ps1 # 登录采集一键运行
├─ shared.py
├─ data/                     # 自动生成：topics.csv, content_history.csv
├─ outputs/                  # 自动生成：内容包 Markdown
└─ reports/                  # 自动生成：周报 Markdown
```

## 2) 准备环境

1. 安装 Python 3.10+ 并确保命令行可用。
2. 设置 OpenAI API Key（如果你要真实生成，不是 `--mock`）：

```powershell
$env:OPENAI_API_KEY="你的key"
```

如果你希望永久生效（Windows 用户变量）：

```powershell
[System.Environment]::SetEnvironmentVariable("OPENAI_API_KEY","你的key","User")
```

## 3) 先改配置

编辑 `config.json`，重点改这些字段：

1. `account_profile.positioning`：你的账号定位。
2. `account_profile.audience`：目标受众。
3. `account_profile.tone`：你的说话风格。
4. `account_profile.cta`：你的结尾引导动作。
5. `topic_collection.keywords`：你的核心赛道关键词。
6. `network.proxy_url`：代理地址（如 `http://127.0.0.1:7890`，不需要代理就留空）。
7. `network.no_proxy`：可选，不走代理的域名（如 `localhost,127.0.0.1`）。
8. `content_strategy.default_series`：默认栏目（`anti_anxiety/self_rescue/self_media`）。

## 4) 日常运行（建议每天）

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
python .\topic_collector.py
python .\content_generator.py
```

按栏目生成（你现在的三大方向）：

```powershell
python .\content_generator.py --series anti_anxiety
python .\content_generator.py --series self_rescue
python .\content_generator.py --series self_media
```

若你想先测流程，不调用 API：

```powershell
python .\content_generator.py --mock
```

你也可以一键跑：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_daily.ps1
```

如果你需要临时指定代理：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_daily.ps1 -ProxyUrl "http://127.0.0.1:7890"
```

按栏目一键跑：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_daily.ps1 -Series anti_anxiety
```

如果你希望“有额度就真生成，没额度自动降级”为 mock：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_daily.ps1 -MockOnQuota
```

如果当前终端还没刷新 PATH，`python` 仍不可用，可临时指定：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_daily.ps1 -PythonExe "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
```

## 5) 每周复盘（建议每周一次）

先把发布后的真实数据补到 `data/content_history.csv` 里，重点是：

1. `read_count` 阅读数
2. `avg_read_time` 平均阅读时长（秒）
3. `like_count` 点赞
4. `share_count` 转发
5. `lead_count` 私信/加微/成交前动作
6. `completion_rate` 完播/读完率（百分比）

然后运行：

```powershell
python .\weekly_report.py --days 7
```

或一键跑：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_weekly.ps1 -Days 7
```

临时指定代理：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_weekly.ps1 -Days 7 -ProxyUrl "http://127.0.0.1:7890"
```

报告会输出到 `reports/` 目录。

## 6) 视频号数据仿写分析

先把你在视频号助手导出的 CSV 放到：

`C:\Users\HP\Documents\Playground\creator_automation\data\videohao_posts.csv`

可参考模板：

`C:\Users\HP\Documents\Playground\creator_automation\data\videohao_posts_template.csv`

运行：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
python .\videohao_mimic_analyzer.py --input .\data\videohao_posts.csv
```

输出：

- `reports/videohao_mimic_时间戳.md`（包含节奏分析、标题库、30秒脚本）

## 7) 每日监控福饱饱并自动出稿

把视频号导出的最新 CSV 放到：

`C:\Users\HP\Documents\Playground\creator_automation\data\videohao_posts.csv`

运行（推荐）：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
powershell -ExecutionPolicy Bypass -File .\run_videohao_daily.ps1 -InputCsv .\data\videohao_posts.csv -Days 3 -MockOnQuota
```

输出结果：

1. 日报：`reports/videohao_daily_时间戳.md`
2. 分主题文案：`outputs/` 下自动生成 3 条（抗焦虑/自救/自媒体）
3. 直接开录文案：`outputs/ready_30s_时间戳.md`（只保留可直接口播内容）

注意：

脚本默认会拦截模板演示数据（`videohao_posts_template.csv`），防止误把示例当真实数据。
如果你只是测试流程，才使用 `-AllowDemoData`。

## 8) 网站登录采集（不需要把密码给AI）

适合你不想手工复制 CSV 路径时使用。

执行后会自动打开视频号后台，你只要在浏览器里登录并导出 CSV，脚本会自动抓到最新下载文件并继续跑日报+文案：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
powershell -ExecutionPolicy Bypass -File .\run_videohao_login_daily.ps1 -InputCsv .\data\videohao_posts.csv -Days 3 -MockOnQuota
```

可选参数：

1. `-WatchDir`：你的下载目录（默认 `C:\Users\HP\Downloads`）
2. `-TimeoutSec`：等待导出超时时间（默认 900 秒）
3. `-SourceCsv`：直接指定一个 CSV 文件（跳过登录和等待）

## 9) 可选：任务计划自动执行（Windows）

每天 08:30 自动抓题+生成：

```powershell
schtasks /Create /SC DAILY /TN "CreatorDailyContent" /TR "powershell -ExecutionPolicy Bypass -File C:\Users\HP\Documents\Playground\creator_automation\run_daily.ps1" /ST 08:30
```

每周一 09:00 自动复盘：

```powershell
schtasks /Create /SC WEEKLY /D MON /TN "CreatorWeeklyReport" /TR "powershell -ExecutionPolicy Bypass -File C:\Users\HP\Documents\Playground\creator_automation\run_weekly.ps1" /ST 09:00
```

## 10) 常见问题

1. 报 `python` 找不到：说明 Python 还没安装或未加入 PATH。
2. 报 API 鉴权失败：检查 `OPENAI_API_KEY` 是否正确。
3. `topics.csv` 没有新选题：可能 RSS 暂不可用或关键词过窄，建议增加关键词和数据源模板。
4. 报 SSL/连接错误：优先配置 `network.proxy_url` 或用 `-ProxyUrl` 临时指定代理。
5. 登录采集超时：确认导出 CSV 下载到了你设置的 `watch_dir`，或改用 `run_videohao_daily.ps1` 手动指定 CSV。
