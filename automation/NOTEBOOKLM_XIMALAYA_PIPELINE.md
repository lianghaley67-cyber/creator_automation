# NotebookLM 到喜马拉雅半自动发布流水线

这个脚本用于把 Creator Digital Studio 的最新 AI 抓取结果导入 NotebookLM，再辅助生成音频并发布到喜马拉雅。

脚本位置：

```text
automation/notebooklm_ximalaya_pipeline.py
```

## 已支持流程

1. 从 Creator Digital Studio 生成最新 NotebookLM 导入包。
2. 自动获取 Markdown 导入链接和原始网页链接清单。
3. 读取 `D:\obsMD\Obsidian\vault\CreatorStudioSkills\文案生成Skill.md`。
4. 调用现有文案生成接口，按 Skill 规则生成喜马拉雅标题、简介、标签、口播文案。
5. 同时按同一个 Skill 生成视频号真人出镜口播文案。
6. 生成一份人工审核单，里面同时包含喜马拉雅和视频号两套内容。
7. 打开 NotebookLM，辅助你清空旧来源、重新导入最新网页链接。
8. 等待你生成并下载 NotebookLM 音频，脚本捕获下载文件。
9. 打开喜马拉雅投稿页，辅助复制标题、标签、简介，并提示你手动上传音频。

## 为什么不是全自动发布

NotebookLM 和喜马拉雅都可能有登录、验证码、页面 UI 改版、最终发布确认等情况。

所以脚本设计为半自动：

- 可以自动生成链接和文案。
- 可以自动打开网页、复制内容、捕获下载。
- 清空 NotebookLM 来源、最终发布喜马拉雅，需要人工确认。

这样更稳定，也避免误删资料或误发布。

## 本地安装依赖

第一次运行需要安装 Playwright：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
python -m pip install playwright
python -m playwright install chromium
```

## 推荐运行命令

默认抓取最新 AI 信息：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
python automation\notebooklm_ximalaya_pipeline.py
```

按指定主题抓取：

```powershell
python automation\notebooklm_ximalaya_pipeline.py --query "AI 对普通职场妈妈和内容创作者的影响"
```

只生成 NotebookLM 链接和喜马拉雅审核单，不打开浏览器：

```powershell
python automation\notebooklm_ximalaya_pipeline.py --no-browser
```

## 可配置项

可以通过命令参数或 `.env` 配置：

```env
CREATOR_STUDIO_URL=http://43.156.8.162/
NOTEBOOKLM_URL=https://notebooklm.google.com/notebook/8a28b3eb-d0f4-44a2-a57b-3d9b437a8f37
XIMALAYA_UPLOAD_URL=https://www.ximalaya.com/anchor-center/upload
XIMALAYA_COPY_SKILL_PATH=D:/obsMD/Obsidian/vault/CreatorStudioSkills/文案生成Skill.md
NOTEBOOKLM_AUDIO_DOWNLOAD_TIMEOUT=1800
```

## 人工审核点

脚本会在这些位置暂停：

1. 文案审核：你可以补充修改意见，脚本会再次调用文案模型修稿。
2. NotebookLM 来源清理：你手动删除旧网页来源，避免误删 notebook。
3. NotebookLM 音频生成：你手动点击生成和下载。
4. 喜马拉雅发布：你手动上传音频并确认发布。
5. 视频号发布：审核单里会同步提供视频号标题、话题和口播正文，后续可复制到视频号发布助手。

## 输出文件

审核单和下载音频会放在：

```text
studio_runtime/notebooklm_ximalaya/
```

审核单包含：

- NotebookLM Markdown 导入包链接
- 原始网页链接清单
- 喜马拉雅标题
- 喜马拉雅标签
- 喜马拉雅简介
- 口播文案
- 视频号标题
- 视频号话题
- 视频号真人出镜口播文案
