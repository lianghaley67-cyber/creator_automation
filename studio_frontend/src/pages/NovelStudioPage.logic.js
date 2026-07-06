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
