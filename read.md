# creator_automation 执行命令说明

## 1. 进入项目目录

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
```

## 2. 配置 API Key（当前终端会话）

```powershell
$env:OPENAI_API_KEY="你的OpenAIKey"
```

## 3. 每日内容生产

```powershell
powershell -ExecutionPolicy Bypass -File .\run_daily.ps1
```

按栏目生成：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_daily.ps1 -Series anti_anxiety
powershell -ExecutionPolicy Bypass -File .\run_daily.ps1 -Series self_rescue
powershell -ExecutionPolicy Bypass -File .\run_daily.ps1 -Series self_media
```

仅模拟模式（不实际调用生成）：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_daily.ps1 -Mock
```

额度不足自动降级为 mock：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_daily.ps1 -MockOnQuota
```

## 4. 周报生成

```powershell
powershell -ExecutionPolicy Bypass -File .\run_weekly.ps1 -Days 7
```

## 5. 视频号日更监控

```powershell
powershell -ExecutionPolicy Bypass -File .\run_videohao_daily.ps1 -InputCsv .\data\videohao_posts.csv -Days 3 -MockOnQuota
```

## 6. 视频号登录采集 + 日更

```powershell
powershell -ExecutionPolicy Bypass -File .\run_videohao_login_daily.ps1 -InputCsv .\data\videohao_posts.csv -Days 3 -MockOnQuota
```

## 7. 定时任务（可选）

每日 08:30：

```powershell
schtasks /Create /SC DAILY /TN "CreatorDailyContent" /TR "powershell -ExecutionPolicy Bypass -File C:\Users\HP\Documents\Playground\creator_automation\run_daily.ps1" /ST 08:30
```

每周一 09:00：

```powershell
schtasks /Create /SC WEEKLY /D MON /TN "CreatorWeeklyReport" /TR "powershell -ExecutionPolicy Bypass -File C:\Users\HP\Documents\Playground\creator_automation\run_weekly.ps1" /ST 09:00
```

## 8. 仓库忽略说明

`outputs/` 与 `reports/` 目录下的生成内容已通过 `.gitignore` 忽略，仅保留 `.gitkeep` 占位文件。
