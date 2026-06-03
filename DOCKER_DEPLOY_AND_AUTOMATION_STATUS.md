# Docker 部署与自动化流水线状态

更新时间：2026-06-03

## 一、当前已经完成到哪一步

目前已经完成：

1. AI 实时信息抓取
   - 支持默认抓取最新 AI 信息。
   - 支持在页面输入主题后按要求抓取。
   - 支持 Tavily/RSS 等来源。

2. NotebookLM 导入包
   - 可以从抓取结果生成 Markdown 导入包。
   - 可以生成原始网页链接清单。
   - 可以归档到 Obsidian。

3. 文案生成
   - 可以读取 `D:\obsMD\Obsidian\vault\CreatorStudioSkills\文案生成Skill.md`。
   - 可以生成喜马拉雅播客标题、简介、标签、口播稿。
   - 可以同步生成视频号真人口播标题、话题、正文。
   - 可以在人工审核后，根据修改意见二次修稿。

4. 微信素材
   - 可以接收微信文字素材。
   - 可以接收微信语音素材。
   - 如果微信不返回 Recognition，可以走本地 Whisper 兜底转写。
   - 已做简体中文统一转换。

5. 半自动发布辅助
   - `automation/notebooklm_ximalaya_pipeline.py` 可以打开 Studio、NotebookLM、喜马拉雅。
   - 可以辅助清空 NotebookLM 旧来源、导入新链接、生成/下载音频。
   - 可以辅助填写喜马拉雅发布信息。

## 二、还没有完全自动化的部分

这些步骤仍建议人工确认：

1. NotebookLM 删除旧来源
   - 原因：避免误删 notebook 或误删错来源。

2. NotebookLM 生成音频
   - 原因：NotebookLM 网页控件经常变化，且可能需要登录确认。

3. 喜马拉雅最终发布
   - 原因：涉及账号发布动作，建议你人工审核后点击发布。

4. 视频号最终发布
   - 目前已生成视频号口播文案，但还没有接入微信视频号/发布助手的自动上传。

## 三、你现在需要做什么

你需要准备并确认：

1. 服务器 `.env` 配置完整
   - Tavily Key
   - Gemini 或 MiniMax Key
   - DeepSeek Key
   - 微信测试号 Token/AppID/AppSecret
   - Obsidian/Gitee Token

2. NotebookLM 和喜马拉雅账号登录
   - 首次运行自动化脚本时，会打开浏览器。
   - 你需要手动登录 Google/NotebookLM 和喜马拉雅。
   - 登录状态会保存在本地浏览器 profile 中。

3. 每次发布前人工审核
   - 检查标题、简介、标签、口播稿。
   - 确认音频内容没有错。

## 四、Docker Compose 部署

服务器目录：

```bash
cd /home/ubuntu/creator_automation
```

拉取最新代码：

```bash
git pull origin master
```

确认 `.env` 存在：

```bash
ls -la .env
```

首次启动或重新构建：

```bash
docker compose up -d --build
```

查看状态：

```bash
docker compose ps
docker compose logs -f creator-studio
```

验证服务：

```bash
curl http://127.0.0.1/api/health
```

浏览器访问：

```text
http://43.156.8.162/
```

## 五、如果服务器 80 端口被占用

如果之前的 nginx/systemd 服务还占用 80，可以先停掉旧服务：

```bash
sudo systemctl stop creator-studio || true
sudo systemctl stop nginx || true
```

也可以不占用 80，改用 8000 端口：

```bash
CREATOR_STUDIO_HOST_PORT=8000 docker compose up -d --build
```

访问：

```text
http://43.156.8.162:8000/
```

微信回调地址也要对应改成：

```text
http://43.156.8.162:8000/api/integrations/wechat/callback
```

## 六、运行 NotebookLM + 喜马拉雅流水线

本地 Windows 推荐运行：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
python automation\notebooklm_ximalaya_pipeline.py
```

只生成审核单、不打开浏览器：

```powershell
python automation\notebooklm_ximalaya_pipeline.py --no-browser
```

按指定主题抓取：

```powershell
python automation\notebooklm_ximalaya_pipeline.py --query "AI 对普通职场妈妈和内容创作者的影响"
```

输出文件在：

```text
studio_runtime\notebooklm_ximalaya\
```

里面会包含：

- NotebookLM 原始链接
- 喜马拉雅发布内容
- 视频号口播文案
- 下载的 NotebookLM 音频

## 七、下一阶段建议

下一步建议优先做：

1. 在页面上增加“一键生成多平台发布包”按钮。
2. 把喜马拉雅和视频号文案展示到页面里，而不是只放 Markdown 审核单。
3. 增加“已审核/待发布/已发布”状态。
4. 后续再接入视频号发布助手或喜马拉雅接口能力。
