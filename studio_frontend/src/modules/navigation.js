export const workflowCards = [
  {
    key: "capture",
    number: "01",
    title: "抓取",
    desc: "120+ 信息源 · 15 分钟刷新",
    icon: "feed",
    tab: "trends",
    target: "trends-panel"
  },
  {
    key: "input",
    number: "02",
    title: "输入",
    desc: "语音 / 文字 / 文档上传",
    icon: "mic",
    tab: "materials",
    target: "wechat-inbox"
  },
  {
    key: "interview",
    number: "03",
    title: "追问",
    desc: "AI 访谈式深挖观点",
    icon: "ask",
    tab: "trends",
    target: "questions-panel"
  },
  {
    key: "generate",
    number: "04",
    title: "生成",
    desc: "多 Skill 文案 + 视频",
    icon: "wand",
    tab: "materials",
    target: "script-panel"
  },
  {
    key: "publish",
    number: "05",
    title: "发布",
    desc: "归档 Obsidian · 半自动分发",
    icon: "upload",
    tab: "materials",
    target: "jobs-panel"
  }
];

export const coreModules = [
  {
    key: "capture",
    number: "01",
    title: "实时信息获取",
    desc: "聚合 AI、软件开发、内容创作、职场成长四大赛道的多源资讯，自动去重、打标、生成普通人能理解的关键词图谱。",
    icon: "live",
    status: "已上线",
    action: "进入模块",
    tab: "trends",
    target: "trends-panel",
    bullets: ["RSS / API / 微信公众号 多源抓取", "AI 自动分类 · 关键词去重", "一键转访谈式追问"]
  },
  {
    key: "create",
    number: "02",
    title: "素材上传 · 生成文案视频",
    desc: "支持文字、微信语音、文档导入。AI 按 Skill 模板生成视频号口播、播客脚本、学习拉链文章，并自动渲染短视频。",
    icon: "doc",
    status: "已上线",
    action: "进入模块",
    tab: "materials",
    target: "script-panel",
    bullets: ["微信语音 → 转写 → 润色", "多模板 Skill 切换", "TTS + 模板视频自动渲染"]
  },
  {
    key: "analysis",
    number: "03",
    title: "股票分析",
    desc: "基于实时行情、技术指标、市场温度与个人持仓，输出复盘卡片、风险提示和下一步观察动作。",
    icon: "stock",
    status: "已上线",
    action: "进入模块",
    tab: "stocks",
    target: "stock-panel",
    bullets: ["A/HK/US 行情分析", "个人持仓与预警", "AI 辅助复盘报告"]
  }
];

export const sidebarModules = [
  { key: "trends", label: "实时信息获取", icon: "01", tab: "trends", target: "trends-panel" },
  { key: "materials", label: "素材生成视频", icon: "02", tab: "materials", target: "wechat-inbox" },
  { key: "stocks", label: "股票分析", icon: "03", tab: "stocks", target: "stock-panel" }
];

export function modulePageMeta(tab) {
  const meta = {
    trends: {
      kicker: "REALTIME INTELLIGENCE",
      title: "实时信息获取",
      desc: "抓取 AI、软件开发、职场成长与内容创作资讯，自动去重、分类并生成可追问选题。"
    },
    materials: {
      kicker: "CONTENT ENGINE",
      title: "素材上传 · 生成文案视频",
      desc: "把微信语音、文字、文档和真实经历，串成文案审核、视频生成与发布归档工作流。"
    },
    stocks: {
      kicker: "DECISION ASSISTANT",
      title: "股票分析",
      desc: "沉淀行情、舆情、个人持仓与复盘卡片，为后续决策辅助模块预留完整入口。"
    }
  };
  return meta[tab] || meta.trends;
}
