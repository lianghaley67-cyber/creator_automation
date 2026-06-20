export function buildTrendQuestions(trend) {
  if (!trend) return [];
  if (Array.isArray(trend.suggested_questions) && trend.suggested_questions.length) {
    return trend.suggested_questions.slice(0, 6);
  }

  const items = Array.isArray(trend.items) ? trend.items : [];
  const pickTitle = (index, fallback) => {
    const title = (items[index]?.title || trend.title || fallback || "今天的 AI 资讯").trim();
    return title.length > 28 ? `${title.slice(0, 27)}…` : title;
  };
  const focusText = `${trend.query || ""} ${trend.summary || ""} ${items.map((item) => item.title || "").join(" ")}`.toLowerCase();
  const focus = focusText.includes("video") || focusText.includes("creator") || focusText.includes("短视频")
    ? "短视频创作和内容生产"
    : focusText.includes("work") || focusText.includes("效率") || focusText.includes("职场")
      ? "普通人的工作效率和时间管理"
      : "普通人的生活、工作和学习方式";

  return [
    `从「${pickTitle(0)}」看，AI 正在解决普通人生活工作里的哪个具体问题？`,
    `如果把今天的资讯落到${focus}，最值得普通人立刻尝试的一个动作是什么？`,
    `「${pickTitle(1)}」可能带来哪些机会和风险，哪些地方必须保留人的判断？`,
    "这些 AI 工具是不是完全准确？普通人怎么判断接口数据、模型输出和真实经验的边界？",
    "如果用访谈方式深挖：这条资讯最触动我的一个焦虑、期待或真实经历是什么？",
    `怎么把「${pickTitle(2)}」转成一条有钩子、有观点、有行动建议的视频号口播文案？`
  ];
}

export function buildTrendNextAction({
  isRefreshing,
  hasTrends,
  hasSummary,
  isSkillSelectorVisible,
  hasDistributionDraft
}) {
  if (isRefreshing) return "正在抓取新资讯，抓完后会高亮本次结果。";
  if (!hasTrends) return "下一步：先点“立即抓取”，获取今天可转成内容的 AI 资讯。";
  if (!hasSummary) return "下一步：点右上角“生成 AI 摘要”，先让 AI 把资讯翻译成普通人能用的重点。";
  if (!isSkillSelectorVisible) return "下一步：展开 Skill，确认公众号和小红书分别用哪套写法。";
  if (!hasDistributionDraft) return "下一步：读完摘要后，点“生成发布包”，或在某条资讯右侧点“用这条生成”。";
  return "下一步：切换公众号/小红书预览，检查内容后再进入发布。";
}
