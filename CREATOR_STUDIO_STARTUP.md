# Creator Studio 本地启动说明

这份文档用于在 Windows PowerShell 本地启动 3-6 岁儿童科普/早教动画短视频生成工具。

## 1. 环境要求

- Windows 10/11
- Python 3.10+，当前脚本默认优先使用 `Python312`
- Node.js 18+ 和 npm
- FFmpeg，可放入系统 `PATH`，也可放入项目的 `tools/ffmpeg/` 目录
- 智谱 API Key，用于智谱文案生成和清影 CogVideoX-3 视频生成

## 2. 安装依赖

在项目根目录执行：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
powershell -ExecutionPolicy Bypass -File .\setup_creator_studio.ps1
```

如果需要更完整的本地媒体/语音能力，可以安装可选依赖：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_creator_studio.ps1 -WithOptionalMedia
```

## 3. 配置密钥

复制示例配置：

```powershell
Copy-Item .\.env.example .\.env
```

然后编辑 `.env`，至少填写：

```env
ZHIPUAI_API_KEY=你的智谱Key
ZHIPU_VIDEO_MODEL=cogvideox-3
SCRIPT_AI_PROVIDER=zhipu
SCRIPT_AI_MODEL=glm-4-flash
```

说明：

- `.env` 已被 `.gitignore` 忽略，不会提交到仓库。
- `ZHIPUAI_API_KEY` 同时用于文案生成和智谱清影视频生成。
- 如果后续切换 OpenAI、ElevenLabs、可灵或 DashScope，再填写 `.env.example` 中对应字段即可。

## 4. 启动后端

开发模式：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
powershell -ExecutionPolicy Bypass -File .\run_creator_studio_backend.ps1 -Reload
```

普通模式：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
powershell -ExecutionPolicy Bypass -File .\run_creator_studio_backend.ps1
```

后端默认地址：

```text
http://127.0.0.1:8000
```

健康检查：

```powershell
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=10).read().decode())"
```

正常返回：

```json
{"status":"ok"}
```

## 5. 启动前端

开发模式，推荐本地使用：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
powershell -ExecutionPolicy Bypass -File .\run_creator_studio_frontend.ps1 -Dev
```

前端默认地址：

```text
http://127.0.0.1:5173/index.html
```

生产预览模式：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
powershell -ExecutionPolicy Bypass -File .\run_creator_studio_frontend.ps1
```

## 6. 一次性启动检查

前后端都启动后，可以执行：

```powershell
@'
import urllib.request
for url in [
    "http://127.0.0.1:8000/api/health",
    "http://127.0.0.1:8000/api/dashboard",
    "http://127.0.0.1:5173/index.html",
]:
    with urllib.request.urlopen(url, timeout=10) as r:
        print(url, r.status)
'@ | python -
```

三个地址都返回 `200`，说明本地可以启动。

## 7. 常见问题

### 个人号如何发布到抖音

个人新号通常无法直接使用抖音开放平台 API 代发视频。当前项目提供的是发布助手：

```text
生成视频 -> 预览 -> 发布助手 -> 复制标题/话题和视频路径 -> 打开抖音投稿页 -> 手动确认发布
```

如果抖音投稿页地址后续变化，可以在 `.env` 中调整：

```env
DOUYIN_CREATOR_UPLOAD_URL=https://creator.douyin.com/creator-micro/content/post/video
```

### 端口被旧进程占用

查看端口：

```powershell
Get-NetTCPConnection -LocalPort 8000,5173 -State Listen -ErrorAction SilentlyContinue | Select-Object LocalPort,OwningProcess
```

结束旧进程：

```powershell
Stop-Process -Id 进程ID -Force
```

### 后端 `/api/health` 返回 404

通常是 8000 端口上跑的不是当前项目的后端。结束旧进程后重新执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_creator_studio_backend.ps1
```

### 视频生成失败或长时间等待

检查 `.env` 中是否设置了：

```env
ZHIPUAI_API_KEY=
ZHIPU_VIDEO_MODEL=cogvideox-3
```

清影视频生成是异步任务，高峰期可能等待较久。后端默认等待时间由 `ZHIPU_VIDEO_TIMEOUT_SEC` 控制。

### 视频没有声音或声音不自然

默认会优先使用 Edge TTS。如果上传了毛豆/花生参考声音，后端会尝试按角色生成/转换音色。若在线 TTS 返回 403，通常是网络或服务限制，需要换网络环境或改用已配置的第三方 TTS。

## 8. 本次本地验证记录

最近一次检查结果：

```text
http://127.0.0.1:8000/api/health 200
http://127.0.0.1:8000/api/dashboard 200
http://127.0.0.1:5173/index.html 200
```

同时已执行：

```powershell
python -m py_compile .\studio_backend\app.py .\studio_backend\generation.py .\studio_backend\kids_mode.py .\studio_backend\zhipu_provider.py .\studio_backend\script_ai.py
npm run build
```
