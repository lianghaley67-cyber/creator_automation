export function reviewLines(review) {
  const value = review || {};
  const issues = Array.isArray(value.issues) ? value.issues : [];
  const fixes = Array.isArray(value.fix_instructions) ? value.fix_instructions : [];
  return [...issues, ...fixes].filter(Boolean);
}

export function jobProgress(job) {
  const raw = Number(job?.progress_percent);
  if (Number.isFinite(raw)) return Math.min(100, Math.max(0, Math.round(raw)));
  return job?.status === "completed" ? 100 : 0;
}

export function xiaohongshuStatusLabel(draft) {
  const status = draft?.xiaohongshu?.status;
  if (status === "draft_saved") return "已准备好，等待自动发布";
  if (status === "platform_draft_saved") return "已准备好，建议直接发布或下载备用包";
  if (status === "platform_draft_saving") return "正在处理，请稍等";
  if (status === "platform_draft_failed") return "旧草稿流程失败，请改用直接发布或下载备用包";
  if (status === "login_required") return "小红书登录已失效";
  if (status === "publishing") return "发布中，等待你确认";
  if (status === "published") return "已发布";
  if (status === "failed") return "发布失败，可重新尝试";
  return "待发布";
}

export function xiaohongshuNextStep(draft) {
  const status = draft?.xiaohongshu?.status;
  if (status === "published") {
    return {
      title: "小红书已发布，下一步看数据",
      body: "这篇已经发出去了。现在不用重复发布，后面看浏览、点赞、收藏和评论，再决定是否复盘成下一篇。"
    };
  }
  if (status === "publishing") {
    return {
      title: "正在自动发布，先等结果",
      body: "服务器正在处理，不要重复点击。等页面状态变成已发布或失败后，再决定下一步。"
    };
  }
  if (status === "login_required") {
    return {
      title: "先恢复小红书服务器登录",
      body: "服务器小红书登录过期了。先到下方登录区检查登录状态，再回来点自动发布。"
    };
  }
  if (status === "failed") {
    return {
      title: "发布失败，先看失败原因",
      body: "先看下方错误或服务器截图。如果是登录、验证码、风控问题，先处理登录；如果是内容问题，改标题或正文后再发。"
    };
  }
  if (status === "platform_draft_failed") {
    return {
      title: "改用自动发布",
      body: "旧草稿保存流程不稳定，当前页面已收口为直接发布。先确认标题、正文和图卡，再点“直接发布到小红书”。"
    };
  }
  return {
    title: "确认内容后，点自动发布",
    body: "标题、正文和图卡已经准备好。你要省事就点自动发布；如果担心账号风控，就下载图文包手动发。"
  };
}
