# Creator Studio 使用文档

## 1. 当前系统状态

这套本地系统已经可以正常使用，当前运行地址如下：

- 前端页面：`http://127.0.0.1:4173`
- 后端接口：`http://127.0.0.1:8000`
- 后端健康检查：`http://127.0.0.1:8000/api/health`

当前已经完成：

- `Vue3 + FastAPI` 前后端联通
- 上传个人口播视频并自动分析
- 蒸馏个人表达风格和内容结构
- 手动输入主题或文案生成新视频
- 定时批量生成任务
- 本地 `SadTalker` 数字人引擎安装完成
- 本地样例视频已经成功跑通

样例视频输出位置：

- `C:\Users\HP\Documents\Playground\creator_automation\runtime_logs\sadtalker_smoke\03342f36-bfbf-45ca-a38a-9fc6144fa92d\full_body_1##bus_chinese_full.mp4`

## 2. 日常启动方式

如果服务没有运行，可以分别启动后端和前端。

后端：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
powershell -ExecutionPolicy Bypass -File .\run_creator_studio_backend.ps1
```

前端开发页：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
powershell -ExecutionPolicy Bypass -File .\run_creator_studio_frontend.ps1
```

如果开发页端口异常，也可以直接使用预览页：

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation\studio_frontend
npm run build
npm run preview -- --host 127.0.0.1 --port 4173
```

## 3. 页面使用流程

推荐按照下面顺序使用。

### 第一步：上传你的历史口播视频

在前端页面的上传区域：

- 选择你的个人口播视频
- 如果你已经有文案，可以把文案一起填入
- 点击上传

系统会自动做这些事情：

- 提取视频基本信息
- 尝试转写语音
- 分析镜头、停顿、节奏、问句比例、CTA 风格
- 更新你的数字人格画像

### 第二步：检查数字人格画像

上传完成后，页面会更新你的画像信息，包括：

- 常用开场方式
- 常用收尾和 CTA
- 语言节奏
- 停顿风格
- 表达情绪倾向
- 镜头和构图偏好

如果你觉得结果不够像你，可以继续上传更多你的历史视频，让画像更稳定。

### 第三步：生成新内容

在生成区域你有两种常用方式：

1. 输入主题，让系统自动写文案再生成视频
2. 直接输入你自己的文案，让系统按文案生成视频

建议：

- 想快速批量产出时，输入主题
- 想严格控制内容时，直接输入文案

## 4. SadTalker 数字人使用方法

当前 `SadTalker` 已经安装完成，并且后端已经接好了调用链。

页面里的 `SadTalker 引擎` 建议这样配置：

- `Enable SadTalker`：开启
- `repo_dir`：
  `C:\Users\HP\Documents\Playground\creator_automation\tools\digital_human\SadTalker`
- `python_exe`：
  `C:\Users\HP\Documents\Playground\creator_automation\tools\digital_human\envs\sadtalker\python.exe`
- `checkpoint_dir`：
  `C:\Users\HP\Documents\Playground\creator_automation\tools\digital_human\SadTalker\checkpoints`

你现在最需要补的是：

- `source_image`

这里请换成你自己的头像图，建议：

- 正脸
- 单人
- 光线稳定
- 背景尽量干净
- 分辨率不要太低

推荐图片要求：

- `png` 或 `jpg`
- 五官清晰
- 头部不要被遮挡
- 尽量不要侧脸

生成时的推荐设置：

- `render_mode`：`SadTalker`
- `tts_provider`：先用 `pyttsx3` 或已有可用语音
- `avatar_preprocess`：`full`
- `avatar_still_mode`：开启
- `avatar_size`：先用 `256` 或 `512`
- `avatar_use_cpu`：当前建议开启

说明：

- 现在这套环境已经能跑通 `SadTalker`
- 当前默认按 CPU 模式更稳
- 速度会比 GPU 慢，但成功率更高

## 5. 定时自动生成

页面中可以直接创建定时任务。

建议配置：

- 工作日先跑一轮
- 先固定一个时段，例如早上 `08:30`
- 先准备多个主题池
- 先用统一头像和统一视频模板

推荐工作流：

1. 准备 10 到 30 个主题
2. 配置一个固定生成时间
3. 每天自动生成文案和视频
4. 你只负责筛选和发布

## 6. 你自己的使用建议

如果你想做“更像你本人”的效果，建议你准备三类素材：

1. 你的高质量正脸头像
2. 你的 10 到 30 条真实口播视频
3. 你常用的表达句式和文案风格

优先顺序建议：

1. 先把头像和数字人生成链路稳定下来
2. 再持续补历史视频，让人格画像更像你
3. 最后再细化情绪强度、镜头语言和话术模板

## 7. 常见问题

### 页面打不开

先检查：

- 后端是否在 `8000`
- 前端是否在 `4173` 或 `5173`

可以手动访问：

- `http://127.0.0.1:8000/api/health`
- `http://127.0.0.1:4173`

### SadTalker 状态显示不完整

先确认：

- `repo_dir` 存在
- `python_exe` 存在
- `checkpoint_dir` 存在
- 头像图路径有效

### 视频生成慢

这是正常现象，尤其在 CPU 模式下更明显。

优化方式：

- 先用 `256` 尺寸测试
- 先用较短文案
- 确认头像图干净、正脸、单人

### 生成结果不像本人

优先检查：

- 头像图是否足够清晰
- 文案语气是否像你
- 历史视频样本是否太少

## 8. 关键文件位置

主要入口文件：

- 后端入口：`C:\Users\HP\Documents\Playground\creator_automation\studio_backend\app.py`
- SadTalker 适配：`C:\Users\HP\Documents\Playground\creator_automation\studio_backend\avatar.py`
- SadTalker runner：`C:\Users\HP\Documents\Playground\creator_automation\studio_backend\sadtalker_runner.py`
- 前端页面：`C:\Users\HP\Documents\Playground\creator_automation\studio_frontend\src\App.vue`

启动脚本：

- `C:\Users\HP\Documents\Playground\creator_automation\run_creator_studio_backend.ps1`
- `C:\Users\HP\Documents\Playground\creator_automation\run_creator_studio_frontend.ps1`

## 9. 下一步建议

你接下来最值得做的事情只有两件：

1. 在页面里把 `source_image` 换成你自己的真人头像
2. 上传你自己的口播视频继续蒸馏你的数字人格

做完这两步，这套系统就会从“样例可跑”进入“可用于你本人”的阶段。
