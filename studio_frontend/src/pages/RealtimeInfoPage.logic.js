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

export const CONTENT_WORKFLOW_STEPS = [
  {
    id: "fetch",
    label: "抓取资讯",
    helper: "输入主题，拿到今天能转内容的信息。"
  },
  {
    id: "summarize",
    label: "AI 总结",
    helper: "先把资讯翻译成普通人听得懂的重点。"
  },
  {
    id: "direction",
    label: "写方向",
    helper: "补一句你的受众、观点或想服务的人。"
  },
  {
    id: "skills",
    label: "选 Skill",
    helper: "公众号、小红书分开选写法。"
  },
  {
    id: "draft",
    label: "生成预览",
    helper: "先看文案和素材包，再决定发布。"
  },
  {
    id: "review",
    label: "可选审稿",
    helper: "检查是否空泛、是否有操作细节。"
  },
  {
    id: "publish",
    label: "进草稿箱",
    helper: "公众号进草稿箱，小红书保留人工审核。"
  }
];

export const WORKFLOW_REVIEW_OPTIONS = [
  {
    id: "jianghushuo",
    label: "姜胡说审稿",
    description: "看开头有没有真实场景、结尾有没有具体互动。"
  },
  {
    id: "plain_reader",
    label: "小白可读性",
    description: "检查一个完全不了解工具的人能不能跟着做。"
  },
  {
    id: "fact_boundary",
    label: "事实边界",
    description: "检查官方链接、价格、权限、风险是否说清楚。"
  }
];

export function buildContentWorkflowState({
  isRefreshing,
  hasTrends,
  hasSummary,
  hasDirection,
  hasWechatSkill,
  hasXhsSkill,
  hasDistributionDraft,
  hasWechatPreview,
  wechatDraftVerified,
  hasReviewResult
}) {
  const done = new Set();
  if (hasTrends) done.add("fetch");
  if (hasSummary) done.add("summarize");
  if (hasDirection) done.add("direction");
  if (hasWechatSkill && hasXhsSkill) done.add("skills");
  if (hasDistributionDraft) done.add("draft");
  if (hasReviewResult) done.add("review");
  if (wechatDraftVerified) done.add("publish");

  let activeStepId = "fetch";
  let nextAction = "输入主题后点“按要求抓取”，先拿到今天可用的 AI 信息。";
  let nextButtonLabel = "按要求抓取";

  if (isRefreshing) {
    activeStepId = "fetch";
    nextAction = "正在抓取新资讯，抓完后会自动高亮结果。";
    nextButtonLabel = "抓取中";
  } else if (!hasTrends) {
    activeStepId = "fetch";
  } else if (!hasSummary) {
    activeStepId = "summarize";
    nextAction = "先点“生成 AI 摘要”，别急着写稿，先判断这批资讯值不值得转成内容。";
    nextButtonLabel = "生成 AI 摘要";
  } else if (!hasDirection) {
    activeStepId = "direction";
    nextAction = "写一句你的内容方向：想讲给谁听、你自己的判断是什么、希望读者看完能做什么。";
    nextButtonLabel = "填写内容方向";
  } else if (!hasWechatSkill || !hasXhsSkill) {
    activeStepId = "skills";
    nextAction = "确认公众号和小红书各自用哪套 Skill。两个平台不要共用一套话术。";
    nextButtonLabel = "选择 Skill";
  } else if (!hasDistributionDraft) {
    activeStepId = "draft";
    nextAction = "现在可以点“生成文案”，先生成公众号文章和小红书素材包预览。";
    nextButtonLabel = "生成文案";
  } else if (!hasReviewResult) {
    activeStepId = "review";
    nextAction = "建议先跑一次可选审稿：检查是否有真实场景、具体步骤、官方链接和风险边界。";
    nextButtonLabel = "运行审稿";
  } else if (!wechatDraftVerified) {
    activeStepId = "publish";
    nextAction = hasWechatPreview
      ? "最后检查预览和封面，确认无误后发送到公众号草稿箱；小红书只保留人工审核后发布。"
      : "先打开公众号预览，确认排版后再发送到草稿箱。";
    nextButtonLabel = "发送到公众号草稿箱";
  } else {
    activeStepId = "publish";
    nextAction = "公众号草稿箱已经写入成功。接下来你只需要在公众号后台审核发布。";
    nextButtonLabel = "已完成";
  }

  const steps = CONTENT_WORKFLOW_STEPS.map((step) => ({
    ...step,
    status: done.has(step.id) ? "done" : step.id === activeStepId ? "active" : "pending"
  }));

  return {
    activeStepId,
    nextAction,
    nextButtonLabel,
    steps
  };
}

export function reviewDistributionDraft(draft, reviewSkill = "jianghushuo") {
  const wechatTitle = String(draft?.wechat?.title || draft?.title || "");
  const wechatMarkdown = String(draft?.wechat?.markdown || draft?.wechat?.article_markdown || "");
  const wechatHtmlUrl = String(draft?.wechat?.article_html_url || "");
  const xhsBody = String(draft?.xiaohongshu?.body || "");
  const merged = `${wechatTitle}\n${wechatMarkdown}\n${xhsBody}`;
  const hasPersonalAngle = /我|我的|职场|宝妈|妈妈|普通人|新手|小白/.test(merged);
  const hasActionSteps = /第一步|第二步|第[一二三四五六七八九十]步|步骤|打开|点击|复制|下载|安装|配置|测试/.test(merged);
  const hasFactBoundary = /官方|链接|来源|需要核验|权限|隐私|价格|费用|风险|限制/.test(merged);
  const hasScreenshotPlan = /截图|配图|封面|图文|素材包/.test(merged) || Array.isArray(draft?.xiaohongshu?.card_urls);
  const hasInteraction = /你有没有|你可以|欢迎|留言|评论|如果你/.test(merged);
  const hasPreview = Boolean(wechatHtmlUrl);
  const checks = [
    {
      label: "有真实读者场景",
      passed: hasPersonalAngle,
      tip: "开头最好出现“我/普通人/职场宝妈/新手”的具体处境，不要只介绍工具。"
    },
    {
      label: "有可照做步骤",
      passed: hasActionSteps,
      tip: "需要写清打开哪里、点哪里、输入什么、如何判断成功。"
    },
    {
      label: "有事实边界",
      passed: hasFactBoundary,
      tip: "官方链接、价格、权限、数据上传风险不确定时要提醒核验。"
    },
    {
      label: "有配图或截图计划",
      passed: hasScreenshotPlan,
      tip: "公众号长文最好保留截图清单和配图实操版，小红书用素材包。"
    },
    {
      label: "有互动收口",
      passed: hasInteraction,
      tip: "结尾只留一个具体问题，方便读者回复。"
    },
    {
      label: "可预览",
      passed: hasPreview,
      tip: "发布前必须先打开公众号预览看排版。"
    }
  ];
  const failed = checks.filter((item) => !item.passed);
  const label = WORKFLOW_REVIEW_OPTIONS.find((item) => item.id === reviewSkill)?.label || "审稿";
  return {
    label,
    passed: failed.length === 0,
    verdict: failed.length === 0
      ? "这版可以进入发布前人工检查。"
      : `这版还差 ${failed.length} 个点，建议先补齐再发。`,
    checks,
    suggestions: failed.map((item) => item.tip).slice(0, 4)
  };
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
