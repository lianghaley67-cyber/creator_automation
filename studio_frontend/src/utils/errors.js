export function normalizeErrorMessage(error, fallback = "请求失败。") {
  if (!error) return fallback;
  if (typeof error === "string") return error || fallback;
  if (error instanceof Error) {
    if (/504 Gateway Time-out|504 Gateway Timeout/i.test(error.message || "")) {
      return "服务器这次处理超时了，请稍后重试。页面和已有数据不会丢失。";
    }
    if (/502 Bad Gateway/i.test(error.message || "")) {
      return "服务器正在重启或暂时不可用，请等待几秒后重试。";
    }
    if (/failed to fetch/i.test(error.message || "")) {
      return "后端没连上：请确认后台服务已启动，或者刷新页面后重试。";
    }
    return error.message || fallback;
  }
  return String(error || fallback);
}
