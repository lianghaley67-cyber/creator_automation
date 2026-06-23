# CLAUDE.md — 灵感工坊 AI Studio 项目上下文

> 本文件帮助 AI 开发助手快速理解项目背景、架构约定和开发规则，**每次开发前必读**。

---

## 一、项目定位

**灵感工坊 AI Studio** 是一个自媒体内容创作自动化工具，服务于个人 IP：

- **IP 定位**：独立女性 / 职场宝妈 / 软件开发者 / AI 学习开发者 / 自媒体博主
- **目标用户**：和作者处境相似的女性，职场 + 家庭 + 自我成长三线并行，碎片时间学 AI
- **4 大内容支柱**：
  1. 工具安装使用教程（开发者视角拆解）
  2. AI 学习心得（真实过程、踩坑、成长）
  3. AI 使用教程（职场提效、自媒体效率）
  4. AI 辅助创作（情感/玄幻连载小说，方法 + 片段展示）
- **写作声音**：第一人称"我"；有真实情绪；不写鸡汤；每篇有具体场景、可操作步骤、真实踩坑

---

## 二、技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 Composition API（`<script>` Options + `setup()`），Vite 4，纯 CSS（无 Tailwind/UI 库）|
| 后端 | Python 3.12，FastAPI，SQLite（`studio_runtime/studio.db`）|
| 部署 | Docker（单容器），Nginx 反向代理，腾讯云 Ubuntu |
| 版本控制 | Git，双远端：`origin`(Gitee) 和 `github`(GitHub)，**每次 push 两个都要推** |

---

## 三、目录结构

```
creator_automation/
├── studio_frontend/src/
│   ├── App.vue              # 全局状态中心，所有业务逻辑和 API 调用
│   ├── styles.css           # 全局样式，无 CSS module
│   ├── main.js
│   └── pages/
│       ├── useStudioContext.js      # inject("studioContext") 封装
│       ├── RealtimeInfoPage.vue     # 实时资讯 + 平台分发主页面
│       ├── RealtimeInfoPage.logic.js
│       ├── MaterialStudioPage.vue
│       ├── StockAnalysisPage.vue
│       └── OverviewPage.vue
├── studio_backend/
│   ├── app.py               # FastAPI 路由入口（所有 /api/* 路由）
│   ├── channel_skills.py    # Skill 定义 + 预设选题 PRESET_TOPICS
│   ├── ai_trends.py         # 实时资讯抓取（Tavily）
│   ├── publishing.py        # 微信/小红书推送
│   ├── story_db.py          # 番茄小说故事档案 DB 操作
│   ├── novel_platforms/
│   │   └── fanqie.py        # 番茄小说登录/推章
│   └── ...
├── creator_skills/          # Skill Markdown 文件（写法规则）
│   ├── wechat/06_wechat_article.md
│   ├── xiaohongshu/07_xiaohongshu_note.md
│   └── shared/
├── studio_runtime/          # 运行时数据（Docker volume 挂载，不进 git）
│   ├── studio.db            # SQLite 主数据库
│   ├── ai_trends/           # 每日资讯 JSON 缓存
│   └── outputs/             # 生成文件
├── docker-compose.yml
└── Dockerfile
```

---

## 四、前端核心约定

### 状态管理模式

- **所有全局状态和 API 函数** 定义在 `App.vue` 的 `setup()` 中
- 通过 `provide("studioContext", studioContext)` 注入到所有子页面
- 子页面通过 `useStudioContext()` 拿到全部上下文（`...ctx` spread 展开）

```js
// 子页面标准写法
import { useStudioContext } from "./useStudioContext.js";
export default {
  setup() {
    const ctx = useStudioContext("PageName");
    // 本页私有状态写这里
    return { ...ctx, localState };
  }
};
```

- **不要**在子页面直接 fetch API，统一用 `ctx.requestApi()`
- **不要**创建独立的 Pinia/Vuex store

### Vue Import 规则

- Vue 3 Composition API 函数（`ref`, `reactive`, `watch`, `computed` 等）**必须显式 import**
- `App.vue` 第 2 行是 import 语句，新增功能用到新函数时记得加

### 平台分发手风琴（RealtimeInfoPage）

```
platform-generate-bar
├── pgb-section (番茄小说) — 始终可见，不受 isWritingWorkshopMode 控制
├── pgb-section (公众号)   — 始终可见
└── pgb-section (小红书)   — 始终可见
```

- 番茄小说：故事选择 + 新建故事 + 生成下一章 + 查看章节，都在 `pgb-row` 主行（不能折叠隐藏）
- 微信/小红书：Skill 下拉 + 生成文案按钮 + 展开详情（推送、预览、状态）

### 关键变量

| 变量 | 说明 |
|---|---|
| `selectedStoryId` | 当前选中的番茄故事 ID，localStorage 持久化 |
| `trendDistributionDraft` | 当前资讯的分发草稿（含 `wechat` / `xiaohongshu` 子对象）|
| `expandedPlatforms` | 各平台手风琴展开状态（RealtimeInfoPage 本地状态）|
| `busy.*` | 各操作的 loading 状态对象 |
| `presetTopics` | 快速选题列表，来自 `/api/ai-trends/preset-topics` |

### 分发合并逻辑（防止跨平台污染）

```js
// 严格按 channel 只更新对应平台字段
if (!channel || channel === "wechat")      { if (result.wechat)      _merged.wechat      = result.wechat; }
if (!channel || channel === "xiaohongshu") { if (result.xiaohongshu) _merged.xiaohongshu = result.xiaohongshu; }
```

- 分发按钮**不传** `story_id`（始终 `""`），章节生成专用 `generateNextChapter()` 才传

---

## 五、后端核心约定

### API 路由前缀

所有接口在 `/api/` 下，主文件 `studio_backend/app.py`。

### 关键接口

```
GET  /api/ai-trends                        # 获取资讯列表
POST /api/ai-trends/refresh                # 抓取新资讯
POST /api/ai-trends/{id}/distribution      # 生成公众号/小红书内容
GET  /api/ai-trends/preset-topics          # 快速选题列表
POST /api/ai-trends/preset-topics          # 新增选题 {label, query}
DEL  /api/ai-trends/preset-topics/{id}     # 删除选题
GET  /api/stories                          # 番茄故事列表
POST /api/stories                          # 新建故事
GET  /api/stories/{id}/chapters            # 章节列表
POST /api/novel/fanqie/push-chapter        # 推章到番茄小说
GET  /api/channel-skills                   # Skill 列表
POST /api/channel-skills/upload            # 上传 Skill
```

### Skill 系统

- Skill 文件放 `creator_skills/` 目录下，Markdown 格式
- 内置 Skill 定义在 `channel_skills.py` 的 `CHANNEL_SKILLS` 字典
- 用户上传的 Skill 存 `creator_skills/user_skills.json`
- 快速选题用户自定义存 `creator_skills/user_topics.json`（有则覆盖内置）

### distribution 接口的 target_channel

```python
# target_channel 决定生成哪个平台的内容
# "wechat" → 只生成公众号；"xiaohongshu" → 只生成小红书
# 不传或 "" → 两个都生成（旧行为，现在避免使用）
```

---

## 六、部署流程

### 线上部署（腾讯云，43.156.8.162）

```bash
# 拉代码
git pull origin main

# 重新构建并启动
docker compose build creator-studio && docker compose up -d --force-recreate creator-studio

# 查看日志
docker logs creator-studio -f
```

### 本地开发

```powershell
# 后端（PowerShell）
cd studio_backend
uvicorn app:app --reload --port 8000

# 前端（PowerShell）
cd studio_frontend
npm run dev   # http://127.0.0.1:5173
```

### Git Push 规则

**每次 push 必须推两个远端：**

```bash
git push origin main
git push github main
```

---

## 七、开发规则（AI 助手必读）

1. **不改架构**：不要引入新的状态管理库、UI 组件库、CSS 框架
2. **不加无用代码**：不写 TODO 注释、不加超出需求的功能、不写无用 error handler
3. **改前端必读当前文件**：Edit 前先 Read，避免用错旧快照
4. **Vue import 检查**：每次在 App.vue 加 `watch`/`computed` 等，先确认 import 行包含它
5. **双平台推送**：每次 commit 后 `git push origin main && git push github main`
6. **子页面不直接 fetch**：所有 API 调用走 `ctx.requestApi()`，新 API 函数在 App.vue 里定义后加入 studioContext
7. **样式写 styles.css**：不写 `<style scoped>`，全局 CSS 文件统一管理
8. **番茄小说行始终显示**：不能加 `v-if="isWritingWorkshopMode"` 到番茄区域

---

## 八、近期迭代记录（最新在前）

| 时间 | 变更 |
|---|---|
| 2026-06-23 | 快速选题支持增删，持久化到 user_topics.json |
| 2026-06-23 | 快速选题内容重写，贴合 IP 定位 4 大支柱；chip 字色对比度修复 |
| 2026-06-23 | 番茄小说行去除 isWritingWorkshopMode 限制，始终显示 |
| 2026-06-23 | 修复 watch 未 import 导致白屏 ReferenceError |
| 2026-06-23 | 平台分发手风琴重构：番茄置顶，公众号/小红书独立行，按平台生成不互串 |
| 2026-06-23 | 修复微信生成同时触发小红书的 merge 逻辑 bug |
| 2026-06-23 | 番茄小说故事选择默认选第一个，localStorage 持久化 |
