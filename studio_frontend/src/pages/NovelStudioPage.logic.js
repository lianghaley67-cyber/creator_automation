export function storyMetricClass(metric) {
  if (!metric) return "";
  if (metric.severity === "high" && metric.count > 0) return "danger";
  if (metric.count > 0) return "warn";
  return "ok";
}

export function storyScoreLabel(score) {
  if (score >= 80) return "基本可用";
  if (score >= 60) return "需要收束";
  return "建议重构";
}

export function formatStoryStep(step, index) {
  return `${index + 1}. ${step?.label || ""}：${step?.desc || ""}`;
}

export function nextStoryAction({ hasStory, hasDiagnosis, hasBrief }) {
  if (!hasStory) return "先新建一本书，别急着写章节。";
  if (!hasDiagnosis) return "先诊断当前故事，看看是否跑偏或有平台风险。";
  if (!hasBrief) return "生成下一章 Brief，确认目标、冲突和禁忌后再写。";
  return "可以生成下一章，写完后再审核并推送番茄。";
}

export function novelOsModuleStatus({ blueprint, diagnosis, chapterBrief }) {
  return [
    {
      key: "topic",
      label: "选题中心",
      status: blueprint?.topic_center ? "已生成" : "待生成",
      note: blueprint?.topic_center?.market_positioning || "方向、市场、读者、情绪价值和商业潜力。",
    },
    {
      key: "emotion",
      label: "社会情绪库",
      status: blueprint?.social_emotion_database?.length ? `${blueprint.social_emotion_database.length} 项` : "待绑定",
      note: "就业、家庭、婚恋、成长、孤独、未来焦虑。",
    },
    {
      key: "world",
      label: "世界观",
      status: blueprint?.world_bible ? "已成型" : "待设计",
      note: blueprint?.world_bible?.time_background || "时间背景、社会体系、规则体系、力量体系。",
    },
    {
      key: "characters",
      label: "人物生命",
      status: blueprint?.character_life_system?.length ? `${blueprint.character_life_system.length} 人` : "待建立",
      note: "背景、性格、缺陷、心理矛盾、成长路线。",
    },
    {
      key: "plan",
      label: "100章规划",
      status: blueprint?.hundred_chapter_plan?.length ? `${blueprint.hundred_chapter_plan.length} 章` : "待拆解",
      note: "卷规划、章节目标、冲突、爽点、情绪点、悬念点。",
    },
    {
      key: "review",
      label: "总编审核",
      status: diagnosis ? `${diagnosis.score}/100` : "待审核",
      note: diagnosis?.level || "剧情逻辑、人物行为、节奏、重复和主题一致性。",
    },
    {
      key: "brief",
      label: "章节生产",
      status: chapterBrief ? `第 ${chapterBrief.chapter_number} 章` : "待 Brief",
      note: chapterBrief?.title_hint || "开篇入冲突、推动剧情、人物成长、结尾留钩子。",
    },
    {
      key: "safety",
      label: "番茄安全",
      status: diagnosis?.hard_issues?.length ? "需复核" : "待检测",
      note: "低俗、暗示、猎奇、违法美化和负面价值观优化。",
    },
  ];
}

export function novelOsPlanPreview(plan = [], limit = 12) {
  return (Array.isArray(plan) ? plan : []).slice(0, limit);
}
