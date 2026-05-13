# Creator Digital Studio

这是一个适合个人 PC 使用的本地数字人口播工作台，目标是把你历史视频中的表达风格、镜头偏好和内容结构蒸馏出来，然后支持手动或定时生成新的文案与视频。

## 当前这版已经包含

- `Vue3 + Vite` 前端工作台
- `FastAPI` 本地后端
- 上传口播视频并做自动分析
- 从历史素材蒸馏个人画像
- 手动输入主题或直接输入文案生成新内容
- 免费 `edge-tts` 配音
- 离线 `pyttsx3` 配音后备
- 字幕 + 纯背景或背景图视频合成
- 内置 `SadTalker` 数字人渲染接入口
- 每日定时任务
- 外接数字人驱动命令模板接口

## 快速开始

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
powershell -ExecutionPolicy Bypass -File .\setup_creator_studio.ps1 -WithOptionalMedia
```

安装完成后，开两个终端：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
powershell -ExecutionPolicy Bypass -File .\run_creator_studio_backend.ps1
```

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
powershell -ExecutionPolicy Bypass -File .\run_creator_studio_frontend.ps1
```

打开：

- 前端：[http://127.0.0.1:5173](http://127.0.0.1:5173)
- 后端 API：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## 目录说明

- `studio_backend/`：FastAPI 服务
- `studio_frontend/`：Vue3 页面
- `studio_data/`：上传文件、分析结果、任务产物、定时配置

## 关于“模仿我的表情、生成真人感视频”

当前默认内置的是“文案 + 配音 + 字幕成片”链路，这一部分完全可以本地跑。

如果你希望直接走本地开源数字人驱动，这版已经把 `SadTalker` 做成了正式渲染模式：

1. 打开前端里的 `SadTalker 引擎` 面板
2. 配置 `repo_dir`、`python_exe`、`checkpoint_dir`
3. 在生成区选择 `SadTalker 数字人`
4. 输入头像路径或在引擎里设置默认头像

配套安装脚本在：

- [install_sadtalker_workspace.ps1](C:\Users\HP\Documents\Playground\creator_automation\tools\digital_human\install_sadtalker_workspace.ps1)
- [README.md](C:\Users\HP\Documents\Playground\creator_automation\tools\digital_human\README.md)

如果你要更像“数字人驱动”的效果，比如：

- 用一张头像或源视频驱动嘴型
- 模仿你的表情强度
- 输出更像真人口播的视频

这版已经预留了 `avatar_command_template` 接口，你可以接入免费的开源项目，比如：

- SadTalker
- MuseTalk
- LivePortrait
- EchoMimic

前端里选择 `外接数字人驱动` 后，把你本地驱动脚本命令模板填进去即可。

## 推荐安装顺序

1. 先安装基础依赖，确认上传分析、蒸馏画像、脚本生成、字幕视频都正常。
2. 再安装 `requirements.optional.txt`，打开自动转写和更完整的视频分析。
3. 最后再接入你偏好的本地数字人驱动模型。
