<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";

const configuredApiBase = (import.meta.env.VITE_API_BASE || "").trim().replace(/\/$/, "");
const browserApiBase = window.location.origin && window.location.protocol.startsWith("http")
  ? window.location.origin.replace(/\/$/, "")
  : "";
const apiCandidates = Array.from(
  new Set(
    [
      configuredApiBase,
      browserApiBase,
      "http://127.0.0.1:8000",
      "http://localhost:8000",
      "http://127.0.0.1:8011",
      "http://localhost:8011"
    ].filter(Boolean)
  )
);

const brandName = "灵感工坊 AI Studio";
const brandTagline = "AI 洞察 · 软件开发 · 职场成长 · 内容创作";
const brandIconDataUrl = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='18' fill='%2300D5E8'/%3E%3Cpath d='M32 12v40M20 20c7.5 0 12 4.5 12 12M44 20c-7.5 0-12 4.5-12 12M20 44c7.5 0 12-4.5 12-12M44 44c-7.5 0-12-4.5-12-12' fill='none' stroke='%2306111C' stroke-width='4' stroke-linecap='round'/%3E%3Cpath d='M18 32h28' fill='none' stroke='%2306111C' stroke-width='4' stroke-linecap='round'/%3E%3C/svg%3E";
if (typeof document !== "undefined") {
  document.title = brandName;
  document.querySelectorAll("link[rel~='icon']").forEach((link) => link.remove());
  const icon = document.createElement("link");
  icon.rel = "icon";
  icon.type = "image/svg+xml";
  icon.href = brandIconDataUrl;
  document.head.appendChild(icon);
}

const activeApiBase = ref(configuredApiBase || browserApiBase || "http://127.0.0.1:8000");
const notice = ref("");
const errorMessage = ref("");
const jobs = ref([]);
const wechatMaterials = ref([]);
const wechatCallbackEvents = ref([]);
const wechatEntry = ref(null);
const wechatQrImageUrl = computed(() => {
  const entry = wechatEntry.value || {};
  return entry.qr_proxy_url || entry.qr_image_url || "";
});
const selectedWechatMaterialId = ref("");
const aiTrends = ref([]);
const notebookLmPackage = ref(null);
const trendSearchQuery = ref("");
const deletingJobId = ref("");
const previewStoryboard = ref([]);
const hardRules = ref([]);
const quality = ref(null);
const activeTab = ref("overview"); // overview | trends | materials | stocks
const trendQuestions = ref([]);
const trendScripts = ref({});
const generatingTrendScript = ref(false);
const selectedTrendQuestion = ref("");
const trendInterviewAnswer = ref("");
const trendInterviewTurns = ref([]);
const trendFollowups = ref([]);
const trendInterviewRecording = ref(false);
const trendInterviewVoiceNote = ref("");
let trendInterviewRecorder = null;
let trendInterviewChunks = [];
let trendInterviewStream = null;
let trendInterviewCancelRecording = false;
const canRecordTrendVoice = computed(() => (
  typeof window !== "undefined"
  && window.isSecureContext
  && Boolean(navigator.mediaDevices?.getUserMedia)
  && typeof MediaRecorder !== "undefined"
));
const referenceStyleContract = ref(null);
const visualPipeline = ref(null);
const scriptAi = ref(null);
const draftScript = ref("");
const deepseekReview = ref(null);
const finalReview = ref(null);
const humanReviewNotes = ref("");
const referenceImageUrl = ref("");
const maodouVoiceUrl = ref("");
const peanutVoiceUrl = ref("");
const publishDrafts = reactive({});
const stockWatchlist = ref([]);
const stockAnalysis = ref(null);
const stockSearchResults = ref([]);
const stockMarket = ref(null);
const stockHistory = ref([]);
const stockSkills = ref([]);
const stockSkillResult = ref(null);
const stockSkillRuns = ref([]);
const selectedStockSkill = ref("single_stock_diagnosis");
const stockForm = reactive({
  symbol: "AAPL",
  market: "US",
  name: "",
  cost: "",
  shares: "",
  alert_high: "",
  alert_low: "",
  notes: ""
});
const stockQuestion = ref("请从趋势、量能、风险和适合我的观察动作分析这只股票。");

const voicePresets = [
  { label: "温暖真人女声（推荐）", value: "zh-CN-XiaoxiaoNeural" },
  { label: "沉稳知识型女声", value: "zh-CN-XiaoyiNeural" },
  { label: "轻快口语女声", value: "zh-CN-XiaoyiNeural" },
  { label: "理性导师男声", value: "zh-CN-YunxiNeural" }
];

const busy = reactive({
  connect: false,
  refresh: false,
  refreshWechat: false,
  clearWechatDiagnostics: false,
  refreshTrends: false,
  trendInterview: false,
  trendVoice: false,
  notebooklm: false,
  archive: "",
  cleanup: false,
  uploadReference: false,
  uploadVoice: false,
  previewScript: false,
  reviseScript: false,
  generate: false,
  publish: "",
  stockRefresh: false,
  stockSearch: false,
  stockSave: false,
  stockAnalyze: false,
  stockMarket: false,
  stockHistory: false,
  stockSkills: false,
  stockSkillRun: false
});

const kidsForm = reactive({
  topic: "今天送娃迟到被老板点名，心里很憋屈",
  content_mode: "working_mom",
  script_provider: "gemini_minimax",
  learning_goal: "把真实经历转成高共情、可落地的 AI 提效方案",
  seconds: 45,
  prompt_hint: "提炼职场妈妈痛点，给出一个能拍成视频号爆款的观点",
  custom_script: "",
  reference_image_path: "",
  maodou_voice_reference_path: "",
  peanut_voice_reference_path: "",
  edge_voice: "zh-CN-XiaoxiaoNeural",
  animation_style: "videohao_real_person",
  use_my_real_voice: true,
  video_provider: "zhipu_qingying"
});

function setNotice(message) {
  notice.value = message || "";
  errorMessage.value = "";
}

function setError(message) {
  errorMessage.value = message || "发生未知错误。";
}

function normalizeErrorMessage(error, fallback = "请求失败。") {
  if (!error) return fallback;
  if (typeof error === "string") return error || fallback;
  if (error instanceof Error) return error.message || fallback;
  return String(error || fallback);
}

async function pingApi(base) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 2500);
  try {
    const response = await fetch(`${base}/api/health`, { signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) throw new Error("Health endpoint did not return JSON.");
    const payload = await response.json();
    if (payload?.status !== "ok") throw new Error("Health endpoint returned an invalid payload.");
    return true;
  } finally {
    window.clearTimeout(timer);
  }
}

async function resolveApiBase() {
  busy.connect = true;
  try {
    for (const candidate of [activeApiBase.value, ...apiCandidates]) {
      if (!candidate) continue;
      try {
        await pingApi(candidate);
        activeApiBase.value = candidate;
        return candidate;
      } catch {
        // Try the next local API.
      }
    }
    throw new Error("后端未连接，请先启动 8000 端口服务。");
  } finally {
    busy.connect = false;
  }
}

async function requestApi(path, options = {}, timeoutMs = 20000) {
  const base = await resolveApiBase();
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${base}${path}`, { ...options, signal: controller.signal });
    if (!response.ok) {
      let message = "请求失败";
      const text = await response.text();
      try {
        const payload = text ? JSON.parse(text) : null;
        message = payload.detail || payload.error || JSON.stringify(payload);
      } catch {
        if (text) message = text;
      }
      throw new Error(message);
    }
    if (response.status === 204) return null;
    return response.json();
  } catch (error) {
    if (error?.name === "AbortError") throw new Error("请求超时，请检查后端服务。");
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

function mediaUrl(path) {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  return `${activeApiBase.value}${path}`;
}

function kidsPayload() {
  return {
    topic: kidsForm.topic,
    content_mode: kidsForm.content_mode,
    script_provider: kidsForm.script_provider,
    learning_goal: kidsForm.learning_goal,
    seconds: Number(kidsForm.seconds || 45),
    prompt_hint: kidsForm.prompt_hint,
    custom_script: String(kidsForm.custom_script || "").trim(),
    uploaded_image_path: kidsForm.reference_image_path,
    reference_image_path: kidsForm.reference_image_path,
    maodou_voice_reference_path: kidsForm.maodou_voice_reference_path,
    peanut_voice_reference_path: kidsForm.peanut_voice_reference_path,
    auto_generate_image: false,
    edge_voice: kidsForm.edge_voice,
    animation_style: kidsForm.animation_style,
    use_my_real_voice: Boolean(kidsForm.use_my_real_voice),
    video_provider: kidsForm.video_provider
  };
}

function applyScriptResult(result) {
  kidsForm.custom_script = result.script || "";
  previewStoryboard.value = Array.isArray(result.storyboard) ? result.storyboard : [];
  hardRules.value = Array.isArray(result.hard_rules) ? result.hard_rules : [];
  quality.value = result.quality || null;
  referenceStyleContract.value = result.reference_style_contract || null;
  visualPipeline.value = result.visual_pipeline || null;
  scriptAi.value = result.script_ai || null;
  if (result.script_ai?.review) deepseekReview.value = result.script_ai.review;
  if (result.script_ai?.final_review) finalReview.value = result.script_ai.final_review;
}

function applyWechatMaterial(material) {
  if (!material) return;
  kidsForm.topic = material.text || kidsForm.topic;
  kidsForm.content_mode = material.content_mode || kidsForm.content_mode;
  kidsForm.script_provider = material.script_provider || kidsForm.script_provider;
  kidsForm.custom_script = material.script || "";
  previewStoryboard.value = Array.isArray(material.storyboard) ? material.storyboard : [];
  quality.value = material.quality || null;
  scriptAi.value = material.script_ai || null;
  deepseekReview.value = material.script_ai?.review || null;
  finalReview.value = material.script_ai?.final_review || null;
  draftScript.value = material.script || "";
  setNotice(material.script ? "已载入微信素材生成的文案。" : "已载入微信素材，文案还在生成或生成失败。");
}

async function generateWechatMaterial(material, mode) {
  if (!material?.id) return;
  const isInterview = mode === "interview";
  busy.previewScript = true;
  try {
    const result = await requestApi(
      `/api/integrations/wechat/materials/${material.id}/generate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({
          content_mode: kidsForm.content_mode,
          script_provider: kidsForm.script_provider,
          learning_goal: kidsForm.learning_goal,
          prompt_hint: isInterview ? "生成嘉宾A/嘉宾B访谈脚本，保留情绪标签和互动钩子。" : "生成真人出镜口播脚本，突出3秒钩子、3个方法和评论互动。",
          animation_style: isInterview ? "notebooklm_duo_interview" : "videohao_real_person",
          use_my_real_voice: !isInterview || kidsForm.use_my_real_voice,
          seconds: kidsForm.seconds
        })
      },
      240000
    );
    await refreshWechatMaterials();
    applyWechatMaterial(result);
  } catch (error) {
    setError(normalizeErrorMessage(error, "微信素材生成文案失败。"));
  } finally {
    busy.previewScript = false;
  }
}

function reviewLines(review) {
  const value = review || {};
  const issues = Array.isArray(value.issues) ? value.issues : [];
  const fixes = Array.isArray(value.fix_instructions) ? value.fix_instructions : [];
  return [...issues, ...fixes].filter(Boolean);
}

async function uploadReferenceImage(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  busy.uploadReference = true;
  try {
    const formData = new FormData();
    formData.append("file", file);
    const result = await requestApi(
      "/api/kids/upload-image",
      {
        method: "POST",
        body: formData
      },
      120000
    );
    kidsForm.reference_image_path = result.path || "";
    referenceImageUrl.value = result.url ? mediaUrl(result.url) : "";
    setNotice("人物/角色参考图已上传，后续生成会把它作为视觉参考。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "角色模板图上传失败。"));
  } finally {
    busy.uploadReference = false;
    if (event?.target) event.target.value = "";
  }
}

async function uploadCharacterVoice(role, event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  busy.uploadVoice = true;
  try {
    const formData = new FormData();
    formData.append("role", role);
    formData.append("file", file);
    const result = await requestApi(
      "/api/kids/upload-voice",
      {
        method: "POST",
        body: formData
      },
      180000
    );
    if (role === "maodou") {
      kidsForm.maodou_voice_reference_path = result.path || "";
      maodouVoiceUrl.value = result.url ? mediaUrl(result.url) : "";
      setNotice("嘉宾A参考声音已提取，访谈模式下会优先用于嘉宾A台词。");
    } else {
      kidsForm.peanut_voice_reference_path = result.path || "";
      peanutVoiceUrl.value = result.url ? mediaUrl(result.url) : "";
      setNotice("嘉宾B参考声音已提取，访谈模式下会优先用于嘉宾B台词。");
    }
  } catch (error) {
    setError(normalizeErrorMessage(error, "角色声音提取失败。"));
  } finally {
    busy.uploadVoice = false;
    if (event?.target) event.target.value = "";
  }
}

function clearCharacterVoice(role) {
  if (role === "maodou") {
    kidsForm.maodou_voice_reference_path = "";
    maodouVoiceUrl.value = "";
    setNotice("已清除嘉宾A参考声音。");
  } else {
    kidsForm.peanut_voice_reference_path = "";
    peanutVoiceUrl.value = "";
    setNotice("已清除嘉宾B参考声音。");
  }
}

function clearReferenceImage() {
  kidsForm.reference_image_path = "";
  referenceImageUrl.value = "";
  setNotice("已清除人物/角色参考图，本次将由智谱清影根据文案原创生成画面。");
}

async function previewKidsScript() {
  busy.previewScript = true;
  try {
    const result = await requestApi("/api/kids/preview-script", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify(kidsPayload())
    });
    applyScriptResult(result);
    setNotice(result.script_source?.startsWith("third_party_ai") ? "已通过第三方 AI 生成 IP 文案、质量检查和多场景分镜。" : "已生成本地规则文案、质量检查和多场景分镜。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "文案预览失败。"));
  } finally {
    busy.previewScript = false;
  }
}

async function generateKidsVideo() {
  busy.generate = true;
  setNotice(
    kidsForm.video_provider === "zhipu_qingying"
      ? "正在提交智谱清影参考图生成任务..."
      : kidsForm.video_provider === "kling"
        ? "正在提交可灵 API 参考图生成任务..."
        : "正在提交本地低保真预览任务..."
  );
  try {
    await requestApi(
      "/api/kids/generate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify(kidsPayload())
      },
      300000
    );
    setNotice("任务已提交，视频生成中。");
    await refreshJobs();
  } catch (error) {
    setError(normalizeErrorMessage(error, "生成任务提交失败。"));
  } finally {
    busy.generate = false;
  }
}

async function clearHumanData() {
  busy.cleanup = true;
  try {
    const result = await requestApi("/api/maintenance/clear-human-data", { method: "POST" });
    setNotice(`已清理真人蒸馏数据：作业 ${result.removed_jobs || 0}，上传 ${result.removed_uploads || 0}。`);
    await refreshJobs();
  } catch (error) {
    setError(normalizeErrorMessage(error, "清理失败。"));
  } finally {
    busy.cleanup = false;
  }
}

async function deleteHistoryJob(jobId) {
  if (!jobId) return;
  deletingJobId.value = String(jobId);
  try {
    await requestApi(`/api/jobs/${jobId}`, { method: "DELETE" });
    setNotice("历史记录已删除。");
    await refreshJobs();
  } catch (error) {
    setError(normalizeErrorMessage(error, "删除失败。"));
  } finally {
    if (deletingJobId.value === String(jobId)) deletingJobId.value = "";
  }
}

async function copyText(text, successMessage = "已复制。") {
  const value = String(text || "");
  if (!value) return;
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = value;
      textarea.setAttribute("readonly", "readonly");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    }
    setNotice(successMessage);
  } catch (error) {
    setError(normalizeErrorMessage(error, "复制失败，请手动选择文本复制。"));
  }
}

async function generateDraftAndReview() {
  busy.previewScript = true;
  draftScript.value = "";
  deepseekReview.value = null;
  finalReview.value = null;
  try {
    const result = await requestApi(
      "/api/kids/draft-review",
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify(kidsPayload())
      },
      240000
    );
    applyScriptResult(result);
    draftScript.value = result.script || "";
    setNotice(result.script_source?.startsWith("third_party_ai") ? "初稿已生成，DeepSeek 审核意见已展示，可补充意见后再二次修改。" : "AI 审核链路未跑通，已回退本地文案。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "生成初稿与审核失败。"));
  } finally {
    busy.previewScript = false;
  }
}

async function reviseWithReview() {
  const sourceDraft = draftScript.value || kidsForm.custom_script;
  if (!sourceDraft.trim()) {
    setError("请先生成初稿，再进行二次修改。");
    return;
  }
  busy.reviseScript = true;
  try {
    const result = await requestApi(
      "/api/kids/revise-script",
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({
          ...kidsPayload(),
          draft_script: sourceDraft,
          review: deepseekReview.value || {},
          human_feedback: humanReviewNotes.value
        })
      },
      240000
    );
    applyScriptResult(result);
    setNotice("已根据 DeepSeek 审核意见和你的补充意见完成二次修改，并完成终稿复审。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "二次修改失败。"));
  } finally {
    busy.reviseScript = false;
  }
}

async function prepareDouyinPublish(job) {
  if (!job?.id) return;
  busy.publish = String(job.id);
  try {
    const result = await requestApi(
      `/api/jobs/${job.id}/publish/douyin-assistant`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({})
      },
      30000
    );
    publishDrafts[job.id] = result;
    setNotice("发布助手已准备好：先复制标题/话题，再打开抖音投稿页上传视频。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "发布助手准备失败。"));
  } finally {
    if (busy.publish === String(job.id)) busy.publish = "";
  }
}

function openDouyinCreator(draft) {
  const url = draft?.creator_url || "https://creator.douyin.com/";
  window.open(url, "_blank", "noopener,noreferrer");
}

async function refreshJobs() {
  busy.refresh = true;
  try {
    const data = await requestApi("/api/jobs");
    jobs.value = Array.isArray(data) ? data : [];
  } catch (error) {
    setError(normalizeErrorMessage(error, "刷新任务失败。"));
  } finally {
    busy.refresh = false;
  }
}

async function refreshWechatMaterials() {
  busy.refreshWechat = true;
  try {
    const [data, events, entry] = await Promise.all([
      requestApi("/api/integrations/wechat/materials"),
      requestApi("/api/integrations/wechat/callback-events").catch(() => []),
      requestApi("/api/integrations/wechat/entry").catch(() => null)
    ]);
    wechatMaterials.value = Array.isArray(data) ? data : [];
    wechatCallbackEvents.value = Array.isArray(events) ? events : [];
    if (entry) wechatEntry.value = entry;
    if (!wechatMaterials.value.some((item) => item.id === selectedWechatMaterialId.value)) {
      selectedWechatMaterialId.value = wechatMaterials.value[0]?.id || "";
    }
  } catch (error) {
    setError(normalizeErrorMessage(error, "刷新微信素材失败。"));
  } finally {
    busy.refreshWechat = false;
  }
}

async function clearWechatMaterials() {
  if (!window.confirm("确定清空所有微信旧素材吗？已生成的文案记录也会从收件箱移除。")) return;
  busy.refreshWechat = true;
  try {
    const result = await requestApi("/api/integrations/wechat/materials", { method: "DELETE" });
    wechatMaterials.value = [];
    selectedWechatMaterialId.value = "";
    setNotice(`已清理微信旧素材 ${result.removed || 0} 条。`);
  } catch (error) {
    setError(normalizeErrorMessage(error, "清理微信素材失败。"));
  } finally {
    busy.refreshWechat = false;
  }
}

async function clearWechatDiagnostics() {
  if (!window.confirm("确定清空微信回调诊断记录吗？这不会删除微信素材。")) return;
  busy.clearWechatDiagnostics = true;
  try {
    const result = await requestApi("/api/integrations/wechat/callback-events", { method: "DELETE" });
    wechatCallbackEvents.value = [];
    setNotice(`已清理微信回调诊断 ${result.removed || 0} 条。`);
  } catch (error) {
    setError(normalizeErrorMessage(error, "清理微信回调诊断失败。"));
  } finally {
    busy.clearWechatDiagnostics = false;
  }
}

async function deleteWechatMaterial(material) {
  if (!material?.id) return;
  if (!window.confirm("确定删除这一条微信素材吗？")) return;
  busy.refreshWechat = true;
  try {
    await requestApi(`/api/integrations/wechat/materials/${material.id}`, { method: "DELETE" });
    wechatMaterials.value = wechatMaterials.value.filter((item) => item.id !== material.id);
    if (selectedWechatMaterialId.value === material.id) {
      selectedWechatMaterialId.value = wechatMaterials.value[0]?.id || "";
    }
    setNotice("已删除这一条微信素材。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "删除微信素材失败。"));
  } finally {
    busy.refreshWechat = false;
  }
}

async function refreshAiTrends(force = false) {
  busy.refreshTrends = true;
  try {
    const query = trendSearchQuery.value.trim();
    const data = force
      ? await requestApi(
          "/api/ai-trends/refresh",
          {
            method: "POST",
            headers: { "Content-Type": "application/json; charset=utf-8" },
            body: JSON.stringify({ query })
          },
          90000
        )
      : await requestApi("/api/ai-trends");
    aiTrends.value = Array.isArray(data) ? data : [data];
    // 自动生成6个问题
    if (aiTrends.value.length > 0) {
      generateTrendQuestions(aiTrends.value[0]);
    }
    setNotice(force ? (query ? `已按"${query}"抓取 AI 资讯。` : "AI 最新资讯已刷新。") : notice.value);
  } catch (error) {
    setError(normalizeErrorMessage(error, "刷新 AI 资讯失败。"));
  } finally {
    busy.refreshTrends = false;
  }
}

function generateTrendQuestions(trend) {
  if (!trend) return;
  if (Array.isArray(trend.suggested_questions) && trend.suggested_questions.length) {
    trendQuestions.value = trend.suggested_questions.slice(0, 6);
    return;
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
  trendQuestions.value = [
    `从「${pickTitle(0)}」看，AI 正在解决普通人生活工作里的哪个具体问题？`,
    `如果把今天的资讯落到${focus}，最值得普通人立刻尝试的一个动作是什么？`,
    `「${pickTitle(1)}」可能带来哪些机会和风险，哪些地方必须保留人的判断？`,
    "这些 AI 工具是不是完全准确？普通人怎么判断接口数据、模型输出和真实经验的边界？",
    "如果用访谈方式深挖：这条资讯最触动我的一个焦虑、期待或真实经历是什么？",
    `怎么把「${pickTitle(2)}」转成一条有钩子、有观点、有行动建议的视频号口播文案？`
  ];
}

function startTrendInterview(question) {
  selectedTrendQuestion.value = question;
  trendInterviewAnswer.value = "";
  trendFollowups.value = [];
  trendInterviewTurns.value = [
    {
      role: "system",
      text: "先不用急着写稿，我们像访谈一样把这个问题问清楚：它和你的生活、工作、学习有什么真实关系？"
    },
    { role: "question", text: question }
  ];
}

async function continueTrendInterview(question = selectedTrendQuestion.value) {
  if (!question) {
    setError("请先选择一个想继续探讨的问题。");
    return;
  }
  busy.trendInterview = true;
  try {
    const answer = trendInterviewAnswer.value.trim();
    const depth = trendInterviewTurns.value.filter((turn) => turn.role === "answer").length + 1;
    const result = await requestApi("/api/ai-trends/interview/followups", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ question, answer, depth })
    }, 60000);
    if (answer) {
      trendInterviewTurns.value.push({ role: "answer", text: answer });
    }
    const followups = Array.isArray(result.followups) ? result.followups : [];
    trendFollowups.value = followups;
    trendInterviewTurns.value.push({
      role: "question",
      text: followups[0] || "这个问题继续往下看，你最想确认的边界是什么？"
    });
    trendInterviewAnswer.value = "";
    setNotice("已生成下一轮访谈追问。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "生成访谈追问失败。"));
  } finally {
    busy.trendInterview = false;
  }
}

function chooseFollowupQuestion(question) {
  selectedTrendQuestion.value = question;
  trendInterviewTurns.value.push({ role: "question", text: question });
  trendFollowups.value = [];
  trendInterviewAnswer.value = "";
}

async function transcribeTrendInterviewAudioBlob(blob, filename = "interview_voice.webm") {
  if (!blob || blob.size <= 0) {
    setError("没有录到有效语音，请重新录制。");
    return;
  }
  busy.trendVoice = true;
  trendInterviewVoiceNote.value = "正在转写语音...";
  try {
    const form = new FormData();
    form.append("file", blob, filename);
    const result = await requestApi("/api/ai-trends/interview/transcribe", {
      method: "POST",
      body: form
    }, 120000);
    if (result.transcript) {
      trendInterviewAnswer.value = [trendInterviewAnswer.value.trim(), result.transcript].filter(Boolean).join("\n");
      trendInterviewVoiceNote.value = `语音已转成文字：${result.note || "完成"}`;
      setNotice("语音已填入访谈回答框。");
    } else {
      trendInterviewVoiceNote.value = result.note || "语音已上传，但没有识别到文字。";
      setError(trendInterviewVoiceNote.value);
    }
  } catch (error) {
    trendInterviewVoiceNote.value = normalizeErrorMessage(error, "语音转写失败。");
    setError(trendInterviewVoiceNote.value);
  } finally {
    busy.trendVoice = false;
  }
}

async function startTrendVoiceRecording() {
  if (!canRecordTrendVoice.value) {
    const reason = window.isSecureContext
      ? "当前浏览器不支持直接录音。"
      : "当前页面是公网 http，浏览器会禁止麦克风录音。";
    trendInterviewVoiceNote.value = `${reason}请改用“上传音频转文字”，或通过微信语音发送素材。`;
    setError(trendInterviewVoiceNote.value);
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    trendInterviewStream = stream;
    trendInterviewCancelRecording = false;
    trendInterviewChunks = [];
    trendInterviewRecorder = new MediaRecorder(stream);
    trendInterviewRecorder.ondataavailable = (event) => {
      if (event.data?.size > 0) trendInterviewChunks.push(event.data);
    };
    trendInterviewRecorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      trendInterviewStream = null;
      if (trendInterviewCancelRecording) {
        trendInterviewRecorder = null;
        trendInterviewRecording.value = false;
        trendInterviewVoiceNote.value = "录音已取消。";
        trendInterviewCancelRecording = false;
        return;
      }
      const blob = new Blob(trendInterviewChunks, { type: trendInterviewRecorder?.mimeType || "audio/webm" });
      trendInterviewRecorder = null;
      trendInterviewRecording.value = false;
      await transcribeTrendInterviewAudioBlob(blob);
    };
    trendInterviewRecorder.start();
    trendInterviewRecording.value = true;
    trendInterviewVoiceNote.value = "正在录音，说完后点击“停止并转写”。";
  } catch (error) {
    setError(normalizeErrorMessage(error, "无法启动录音。服务器页面如果是 http 公网地址，浏览器可能会禁止麦克风，请改用上传音频。"));
  }
}

function stopTrendVoiceRecording() {
  if (trendInterviewRecorder && trendInterviewRecorder.state !== "inactive") {
    trendInterviewVoiceNote.value = "录音结束，正在准备转写...";
    trendInterviewRecorder.stop();
  }
}

function cancelTrendVoiceRecording() {
  trendInterviewCancelRecording = true;
  if (trendInterviewRecorder && trendInterviewRecorder.state !== "inactive") {
    trendInterviewRecorder.stop();
  } else if (trendInterviewStream) {
    trendInterviewStream.getTracks().forEach((track) => track.stop());
    trendInterviewStream = null;
    trendInterviewRecording.value = false;
    trendInterviewVoiceNote.value = "录音已取消。";
  }
}

async function uploadTrendInterviewVoice(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  await transcribeTrendInterviewAudioBlob(file, file.name || "interview_voice.webm");
  event.target.value = "";
}

async function generateScriptFromTrend(question, trend) {
  if (!trend) {
    setError("请先获取 AI 最新资讯");
    return;
  }
  generatingTrendScript.value = true;
  try {
    const result = await requestApi("/api/kids/preview-script", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({
        topic: question,
        content_mode: "ai_growth",
        script_provider: "gemini_minimax",
        learning_goal: `结合最新 AI 资讯：${trend.title}，回答普通学习者关心的问题：${question}`,
        seconds: 45,
        prompt_hint: `必须基于接口抓取到的 AI 最新资讯回答：${trend.summary}。要明确提醒：AI 输出来自模型和数据接口，不等于人的价值判断，也不保证完全准确；请同时讲清机会、风险和普通人可以立刻做的小行动。`,
        custom_script: "",
        auto_generate_image: false,
        edge_voice: kidsForm.edge_voice,
        animation_style: "videohao_real_person",
        use_my_real_voice: kidsForm.use_my_real_voice,
        video_provider: kidsForm.video_provider
      })
    }, 90000);
    trendScripts.value[question] = result;
    setNotice(`已生成关于"${question}"的文案`);
  } catch (error) {
    setError(normalizeErrorMessage(error, "生成文案失败"));
  } finally {
    generatingTrendScript.value = false;
  }
}

async function createNotebookLmPackage() {
  busy.notebooklm = true;
  try {
    const result = await requestApi("/api/ai-trends/notebooklm-package", { method: "POST" }, 60000);
    notebookLmPackage.value = result.package || null;
    setNotice("NotebookLM 导入包已生成，并已归档到 Obsidian。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "生成 NotebookLM 导入包失败。"));
  } finally {
    busy.notebooklm = false;
  }
}

async function copyNotebookLmSourceLinks() {
  const links = Array.isArray(notebookLmPackage.value?.source_urls) ? notebookLmPackage.value.source_urls : [];
  if (!links.length) {
    setError("当前 NotebookLM 导入包里还没有原始链接清单。");
    return;
  }
  try {
    await navigator.clipboard.writeText(links.join("\n"));
    setNotice(`已复制 ${links.length} 条原始资讯链接，可粘贴到 NotebookLM 的网站来源里。`);
  } catch {
    setError("复制失败，可以打开原始链接清单后手动复制。");
  }
}

async function archiveWechatMaterial(material) {
  if (!material?.id) return;
  busy.archive = String(material.id);
  try {
    const result = await requestApi(`/api/integrations/wechat/materials/${material.id}/archive`, { method: "POST" }, 60000);
    await refreshWechatMaterials();
    const statusText = result.archive?.status === "archived" ? "已归档到 Obsidian Gitee 仓库。" : "已先归档到服务器本地，配置 GITEE_ACCESS_TOKEN 后可写入 Obsidian 仓库。";
    setNotice(statusText);
  } catch (error) {
    setError(normalizeErrorMessage(error, "归档到 Obsidian 失败。"));
  } finally {
    if (busy.archive === String(material.id)) busy.archive = "";
  }
}

async function archiveCurrentScript() {
  const body = String(kidsForm.custom_script || "").trim();
  if (!body) {
    setError("当前没有可归档的文案。");
    return;
  }
  busy.archive = "current";
  try {
    const result = await requestApi(
      "/api/archive/obsidian",
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({ title: kidsForm.topic || "Creator Studio 文案", body })
      },
      60000
    );
    setNotice(result.archive?.status === "archived" ? "当前文案已归档到 Obsidian Gitee 仓库。" : "当前文案已先归档到服务器本地。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "当前文案归档失败。"));
  } finally {
    if (busy.archive === "current") busy.archive = "";
  }
}

async function refreshStockWatchlist() {
  busy.stockRefresh = true;
  try {
    const result = await requestApi("/api/stocks/watchlist", {}, 30000);
    stockWatchlist.value = Array.isArray(result.items) ? result.items : [];
  } catch (error) {
    setError(normalizeErrorMessage(error, "刷新股票自选失败。"));
  } finally {
    busy.stockRefresh = false;
  }
}

async function refreshStockMarket() {
  busy.stockMarket = true;
  try {
    stockMarket.value = await requestApi("/api/stocks/market", {}, 45000);
  } catch (error) {
    setError(normalizeErrorMessage(error, "刷新市场概览失败。"));
  } finally {
    busy.stockMarket = false;
  }
}

async function refreshStockHistory(symbol = "") {
  busy.stockHistory = true;
  try {
    const query = symbol ? `?symbol=${encodeURIComponent(symbol)}` : "";
    const result = await requestApi(`/api/stocks/analysis-history${query}`, {}, 30000);
    stockHistory.value = Array.isArray(result.items) ? result.items : [];
  } catch (error) {
    setError(normalizeErrorMessage(error, "刷新分析历史失败。"));
  } finally {
    busy.stockHistory = false;
  }
}

async function refreshStockSkills() {
  busy.stockSkills = true;
  try {
    const [skills, runs] = await Promise.all([
      requestApi("/api/stocks/skills", {}, 30000),
      requestApi("/api/stocks/skill-runs", {}, 30000)
    ]);
    stockSkills.value = Array.isArray(skills.items) ? skills.items : [];
    stockSkillRuns.value = Array.isArray(runs.items) ? runs.items : [];
    if (!stockSkills.value.some((item) => item.id === selectedStockSkill.value)) {
      selectedStockSkill.value = stockSkills.value[0]?.id || "single_stock_diagnosis";
    }
  } catch (error) {
    setError(normalizeErrorMessage(error, "刷新股票 Skill 失败。"));
  } finally {
    busy.stockSkills = false;
  }
}

async function searchStockSymbols() {
  const query = stockForm.symbol.trim();
  if (!query) return;
  busy.stockSearch = true;
  try {
    const result = await requestApi(`/api/stocks/search?q=${encodeURIComponent(query)}`, {}, 30000);
    stockSearchResults.value = Array.isArray(result.items) ? result.items : [];
  } catch (error) {
    setError(normalizeErrorMessage(error, "搜索股票失败。"));
  } finally {
    busy.stockSearch = false;
  }
}

function chooseStockSearchResult(item) {
  if (!item?.symbol) return;
  stockForm.symbol = item.symbol;
  stockForm.name = item.name || item.symbol;
  stockForm.market = item.market || stockForm.market;
  stockSearchResults.value = [];
}

async function saveStockToWatchlist() {
  if (!stockForm.symbol.trim()) {
    setError("请先输入股票代码。");
    return;
  }
  busy.stockSave = true;
  try {
    await requestApi("/api/stocks/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify(stockForm)
    }, 30000);
    setNotice("已加入股票自选。");
    await refreshStockWatchlist();
  } catch (error) {
    setError(normalizeErrorMessage(error, "保存股票自选失败。"));
  } finally {
    busy.stockSave = false;
  }
}

async function deleteStockFromWatchlist(symbol) {
  if (!symbol) return;
  try {
    await requestApi(`/api/stocks/watchlist/${encodeURIComponent(symbol)}`, { method: "DELETE" }, 30000);
    setNotice("已移除自选股票。");
    await refreshStockWatchlist();
  } catch (error) {
    setError(normalizeErrorMessage(error, "移除股票失败。"));
  }
}

async function analyzeStock(symbol = stockForm.symbol) {
  const value = String(symbol || "").trim();
  if (!value) {
    setError("请先输入或选择股票代码。");
    return;
  }
  busy.stockAnalyze = true;
  try {
    const result = await requestApi("/api/stocks/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ symbol: value, question: stockQuestion.value })
    }, 45000);
    stockAnalysis.value = result;
    stockForm.symbol = result.quote?.symbol || value;
    stockForm.name = result.quote?.name || stockForm.name;
    setNotice("股票分析已生成。");
    await refreshStockHistory(result.quote?.symbol || value);
    await nextTick();
    document.querySelector(".stock-analysis-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setError(normalizeErrorMessage(error, "股票分析失败。"));
  } finally {
    busy.stockAnalyze = false;
  }
}

async function runStockSkill(skillId = selectedStockSkill.value, symbol = stockForm.symbol) {
  const selected = String(skillId || "").trim();
  if (!selected) {
    setError("请先选择一个股票 Skill。");
    return;
  }
  const needsSymbol = !["watchlist_review", "condition_screening"].includes(selected);
  const value = String(symbol || "").trim();
  if (needsSymbol && !value) {
    setError("这个 Skill 需要先输入股票代码。");
    return;
  }
  busy.stockSkillRun = true;
  try {
    const result = await requestApi("/api/stocks/skills/run", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({
        skill_id: selected,
        symbol: value,
        question: stockQuestion.value,
        latest_analysis: stockAnalysis.value || null
      })
    }, 90000);
    stockSkillResult.value = result;
    if (result.analysis) stockAnalysis.value = result.analysis;
    if (result.symbol) stockForm.symbol = result.symbol;
    setNotice("股票 Skill 已运行。");
    await refreshStockSkills();
    await nextTick();
    document.querySelector(".stock-skill-result")?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setError(normalizeErrorMessage(error, "股票 Skill 运行失败。"));
  } finally {
    busy.stockSkillRun = false;
  }
}

function stockSkillName(skillId) {
  return stockSkills.value.find((item) => item.id === skillId)?.name || skillId || "Stock Skill";
}

function formatStockNumber(value, digits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return number.toFixed(digits);
}

function stockChangeClass(value) {
  const number = Number(value);
  if (number > 0) return "up";
  if (number < 0) return "down";
  return "";
}

function stockKlinePoints(points = []) {
  const values = (Array.isArray(points) ? points : []).slice(-42).map((item) => Number(item.close)).filter(Number.isFinite);
  if (!values.length) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = 320;
  const height = 88;
  const span = max - min || 1;
  return values.map((value, index) => {
    const x = values.length === 1 ? width : (index / (values.length - 1)) * width;
    const y = height - ((value - min) / span) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

function jobProgress(job) {
  const raw = Number(job?.progress_percent);
  if (Number.isFinite(raw)) return Math.min(100, Math.max(0, Math.round(raw)));
  return job?.status === "completed" ? 100 : 0;
}

const kidsJobs = computed(() => jobs.value.filter((job) => String(job?.request?.project_mode || "") === "kids_cartoon"));
const runningKidsJobs = computed(() => kidsJobs.value.filter((job) => ["queued", "running"].includes(job.status)));
const completedKidsJobs = computed(() => kidsJobs.value.filter((job) => job.status === "completed"));
const failedKidsJobs = computed(() => kidsJobs.value.filter((job) => job.status === "failed"));
const latestWechatMaterial = computed(() => wechatMaterials.value[0] || null);
const selectedWechatMaterial = computed(() => (
  wechatMaterials.value.find((item) => item.id === selectedWechatMaterialId.value) || latestWechatMaterial.value
));
const latestWechatCallbackEvent = computed(() => wechatCallbackEvents.value[0] || null);
const workflowCards = [
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
const coreModules = [
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
const studioStats = computed(() => [
  { value: `${Math.max(aiTrends.value[0]?.items?.length || 0, 120)}+`, label: "实时信息源", icon: "globe" },
  { value: "60s", label: "素材到成片", icon: "flash" },
  { value: "8 类", label: "内容 Skill 模板", icon: "chart" },
  { value: "3x", label: "周更产能提升", icon: "trend" }
]);
const sidebarModules = [
  { key: "trends", label: "实时信息获取", icon: "01", tab: "trends", target: "trends-panel" },
  { key: "materials", label: "素材生成视频", icon: "02", tab: "materials", target: "wechat-inbox" },
  { key: "stocks", label: "股票分析", icon: "03", tab: "stocks", target: "stock-panel" }
];
const modulePageMeta = computed(() => {
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
  return meta[activeTab.value] || meta.trends;
});

function openStudioModule(tab, targetId = "") {
  activeTab.value = tab;
  if (!targetId) return;
  nextTick(() => {
    const target = document.getElementById(targetId);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

let pollTimer = null;
onMounted(async () => {
  await refreshJobs();
  await refreshWechatMaterials();
  await refreshAiTrends();
  await refreshStockWatchlist();
  await refreshStockMarket();
  await refreshStockHistory();
  await refreshStockSkills();
  pollTimer = window.setInterval(() => {
    if (runningKidsJobs.value.length) refreshJobs();
  }, 3000);
});

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer);
  if (trendInterviewRecorder && trendInterviewRecorder.state !== "inactive") {
    trendInterviewRecorder.stop();
  }
});
</script>

<template>
  <div class="studio-page" :class="{ 'module-mode': activeTab !== 'overview' }">
    <aside v-if="activeTab !== 'overview'" class="studio-sidebar" aria-label="功能模块侧边栏">
      <button class="sidebar-brand" type="button" @click="activeTab = 'overview'">
        <img class="brand-logo-img" src="/favicon.svg?v=2" alt="" aria-hidden="true" />
        <span>
          <strong>灵感工坊</strong>
          <small>AI STUDIO</small>
        </span>
      </button>
      <nav class="sidebar-nav">
        <button
          v-for="item in sidebarModules"
          :key="item.key"
          type="button"
          :class="{ active: activeTab === item.tab }"
          @click="openStudioModule(item.tab, item.target)"
        >
          <span>{{ item.icon }}</span>
          <strong>{{ item.label }}</strong>
        </button>
      </nav>
      <div class="sidebar-footer">后续模块可继续扩展</div>
    </aside>

    <header class="studio-header">
      <button class="brand-mini" type="button" @click="activeTab = 'overview'">
        <img class="brand-logo-img" src="/favicon.svg?v=2" alt="" aria-hidden="true" />
        <span>
          <strong>灵感工坊</strong>
          <small>AI STUDIO</small>
        </span>
      </button>
      <div class="header-actions">
        <span>登录</span>
        <button class="btn accent header-cta" type="button" @click="openStudioModule('materials', 'script-panel')">进入工作台</button>
      </div>
    </header>

    <main class="app-shell">
      <section v-if="activeTab === 'overview'" class="dashboard">
        <section class="landing-hero">
          <div class="landing-copy">
            <span class="version-pill">v2.0 · 个人成长系统全新升级</span>
            <h1>一个人的 <span>AI 成长工作台</span></h1>
            <p>AI 洞察 · 软件开发 · 职场成长 · 内容创作。实时抓取行业资讯，素材一键生成文案与视频，股票决策辅助已接入工作台。</p>
            <div class="landing-actions">
              <button class="btn accent" type="button" @click="openStudioModule('materials', 'script-panel')">开始今日创作</button>
              <button class="btn secondary" type="button" @click="openStudioModule('trends', 'trends-panel')">查看演示</button>
            </div>
            <div class="hero-stats">
              <strong>120+<small>每日信源</small></strong>
              <strong>8 种<small>文案模板</small></strong>
              <strong>60s<small>素材→视频</small></strong>
            </div>
          </div>
          <div class="hero-console" aria-label="工作台实时预览">
            <div class="console-bar">
              <span></span><span></span><span></span>
              <small>studio.inspwk.site</small>
            </div>
            <div class="signal-list">
              <div><span>实时信息流</span></div>
              <p><strong>GPT-5 多模态能力更新</strong><small>2 分钟前</small></p>
              <p><strong>TanStack Start 1.0 正式发布</strong><small>14 分钟前</small></p>
              <p><strong>远程办公薪酬白皮书 2026</strong><small>32 分钟前</small></p>
            </div>
            <div class="console-grid">
              <div class="mini-widget">
                <strong>文案生成</strong>
                <div class="progress-track"><div class="progress-fill" style="width: 75%"></div></div>
                <small>视频号口播 · 生成中 75%</small>
              </div>
              <div class="mini-widget">
                <strong>股票分析</strong>
                <div class="bar-chart" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div>
                <small>实时等待</small>
              </div>
            </div>
          </div>
        </section>

        <section class="core-section">
          <span class="dashboard-kicker">CORE MODULES</span>
          <h2>三大模块 · 一条成长闭环</h2>
          <p>从信息输入到内容产出，再到决策辅助。每一步都为个人创作者与独立开发者量身打造。</p>
          <div class="core-grid">
            <button
              v-for="module in coreModules"
              :key="module.key"
              class="core-card"
              type="button"
              @click="openStudioModule(module.tab, module.target)"
            >
              <span class="module-icon" :data-icon="module.icon" aria-hidden="true"></span>
              <em :class="{ warm: module.status === '开发中' }">{{ module.status }}</em>
              <small>{{ module.number }} · {{ module.key === "capture" ? "实时洞察" : module.key === "create" ? "创作引擎" : "决策助手" }}</small>
              <strong>{{ module.title }}</strong>
              <p>{{ module.desc }}</p>
              <ul>
                <li v-for="item in module.bullets" :key="item">{{ item }}</li>
              </ul>
              <span class="module-link">{{ module.action }}</span>
            </button>
          </div>
        </section>

        <section class="workflow-section">
          <div class="dashboard-hero">
            <div>
              <span class="dashboard-kicker">DAILY WORKFLOW</span>
              <h2>每天 30 分钟 · 完成一条优质内容</h2>
            </div>
            <span class="coverage-pill">自动化覆盖 80% 流程</span>
          </div>

          <div class="workflow-grid" aria-label="每日工作流">
            <button
              v-for="card in workflowCards"
              :key="card.key"
              class="workflow-card"
              type="button"
              @click="openStudioModule(card.tab, card.target)"
            >
              <span class="module-icon" :data-icon="card.icon" aria-hidden="true"></span>
              <span class="module-number">{{ card.number }}</span>
              <strong>{{ card.title }}</strong>
              <small>{{ card.desc }}</small>
            </button>
          </div>
        </section>

        <div class="metric-grid">
          <button
            v-for="stat in studioStats"
            :key="stat.label"
            class="metric-card"
            type="button"
            @click="openStudioModule('trends', 'trends-panel')"
          >
            <span class="module-icon compact" :data-icon="stat.icon" aria-hidden="true"></span>
            <strong>{{ stat.value }}</strong>
            <small>{{ stat.label }}</small>
          </button>
        </div>

        <section class="launch-panel">
          <h2>今天的灵感，<span>让 AI 帮你落地</span></h2>
          <p>一个工作台，覆盖洞察、创作、决策。专为持续输出的个人成长者打造。</p>
          <div class="launch-actions">
            <button class="btn accent" type="button" @click="openStudioModule('materials', 'script-panel')">免费开始使用</button>
            <button class="btn secondary" type="button" @click="openStudioModule('trends', 'questions-panel')">预约 1v1 咨询</button>
          </div>
        </section>
      </section>

      <section v-if="activeTab !== 'overview'" class="module-hero">
        <div>
          <span class="dashboard-kicker">{{ modulePageMeta.kicker }}</span>
          <h1>{{ modulePageMeta.title }}</h1>
          <p>{{ modulePageMeta.desc }}</p>
        </div>
        <div v-if="activeTab !== 'stocks'" class="hero-actions">
          <button class="btn primary" :disabled="busy.previewScript" @click="generateDraftAndReview">
            {{ busy.previewScript ? "生成中..." : "初稿 + DeepSeek 审核" }}
          </button>
          <button class="btn accent" :disabled="busy.generate" @click="generateKidsVideo">
            {{ busy.generate ? "提交中..." : "生成视频" }}
          </button>
        </div>
      </section>

      <div v-if="activeTab !== 'overview'" class="tabs">
        <button class="tab-btn" :class="{ active: activeTab === 'trends' }" @click="openStudioModule('trends', 'trends-panel')">
          实时信息获取
        </button>
        <button class="tab-btn" :class="{ active: activeTab === 'materials' }" @click="openStudioModule('materials', 'wechat-inbox')">
          素材上传 · 生成文案视频
        </button>
        <button class="tab-btn" :class="{ active: activeTab === 'stocks' }" @click="openStudioModule('stocks', 'stock-panel')">
          股票分析
        </button>
      </div>

      <section v-if="activeTab === 'materials'" class="panel wechat-entry-card sticky-wechat-entry">
      <div class="wechat-qr-box" :class="{ empty: !wechatQrImageUrl }">
        <img v-if="wechatQrImageUrl" :src="wechatQrImageUrl" :alt="`${wechatEntry?.account_name || '微信素材入口'}二维码`" />
        <span v-else>二维码未配置</span>
      </div>
      <div class="wechat-entry-copy">
        <strong>扫码用微信语音提供素材</strong>
        <p>关注 {{ wechatEntry?.account_name || "微信测试号/公众号" }} 后，直接按住说话：今天发生了什么、你的感想、剪辑心得。页面点击“刷新微信素材”即可加载。</p>
        <p v-if="wechatEntry?.voice_fallback_enabled" class="meta">
          兜底转写：{{ wechatEntry.voice_fallback_configured ? "已配置 AppID/AppSecret，微信不返回识别文本时会尝试下载语音转写。" : "未配置 AppID/AppSecret，只能依赖微信 Recognition 识别文本。" }}
        </p>
        <p class="meta">回调地址：{{ wechatEntry?.callback_url || "/api/integrations/wechat/callback" }}</p>
        <p v-if="!wechatQrImageUrl" class="error-text">请在 .env 配置 WECHAT_QR_IMAGE_URL 为微信测试号/公众号二维码图片地址，然后重启后端。</p>
      </div>
      </section>

      <div v-if="notice" class="notice">{{ notice }}</div>
      <div v-if="errorMessage" class="notice danger">{{ errorMessage }}</div>

    <!-- 实时信息 Tab -->
    <div v-if="activeTab === 'trends'">
      <section id="trends-panel" class="panel">
        <div class="panel-header">
          <h2>AI 最新实时信息</h2>
          <div class="top-actions">
            <button class="btn secondary" :disabled="busy.refreshTrends" @click="refreshAiTrends(false)">刷新列表</button>
            <button class="btn accent" :disabled="busy.refreshTrends" @click="refreshAiTrends(true)">
              {{ busy.refreshTrends ? "抓取中..." : "立即抓取" }}
            </button>
            <button class="btn primary" :disabled="busy.notebooklm" @click="createNotebookLmPackage">
              {{ busy.notebooklm ? "生成中..." : "生成 NotebookLM 导入包" }}
            </button>
          </div>
        </div>
        <div class="meta">这里展示的是 Tavily/RSS 等接口抓取到的资讯，不是系统自己的主观看法；生成文案时会提醒 AI 输出仍需要人来判断。</div>
        <div class="trend-search-box">
          <label for="trend-search-query">按你的要求获取信息</label>
          <div class="trend-search-row">
            <input
              id="trend-search-query"
              v-model="trendSearchQuery"
              type="text"
              placeholder="例如：AI 对普通职场妈妈的影响、NotebookLM 播客生成、AI 视频工具最新进展"
              @keydown.enter.prevent="refreshAiTrends(true)"
            />
            <button class="btn primary" :disabled="busy.refreshTrends" @click="refreshAiTrends(true)">
              {{ busy.refreshTrends ? "抓取中..." : "按要求抓取" }}
            </button>
          </div>
          <span>不填写时，默认获取最新 AI 实时信息；填写后，会优先根据这个主题检索。</span>
        </div>
        <div v-if="!aiTrends.length" class="meta">暂无 AI 日报。系统会每天自动抓取，也可以点击“立即抓取”。</div>
        <div v-else class="trend-card">
          <div class="script-preview-head">
            <strong>{{ aiTrends[0].title }}</strong>
            <span>{{ aiTrends[0].created_at }}</span>
          </div>
          <p>{{ aiTrends[0].summary }}</p>
          <ul>
            <li v-for="item in (aiTrends[0].items || []).slice(0, 8)" :key="item.url || item.title">
              <a v-if="item.url" :href="item.url" target="_blank" rel="noreferrer">{{ item.title }}</a>
              <strong v-else>{{ item.title }}</strong>
              <span>{{ item.summary }}</span>
            </li>
          </ul>
          <div class="trend-angles">
            <strong>可转化选题角度</strong>
            <span v-for="angle in aiTrends[0].angles || []" :key="angle">{{ angle }}</span>
          </div>
          <div v-if="notebookLmPackage" class="notebooklm-box">
            <strong>NotebookLM 导入包</strong>
            <span>Markdown 包适合整体导入；原始链接清单适合让 NotebookLM 分别读取每篇资讯网页。</span>
            <div class="notebooklm-actions">
              <a :href="mediaUrl(notebookLmPackage.url)" target="_blank" rel="noreferrer">{{ notebookLmPackage.title || "打开导入包" }}</a>
              <a v-if="notebookLmPackage.source_links_url" :href="mediaUrl(notebookLmPackage.source_links_url)" target="_blank" rel="noreferrer">打开原始链接清单</a>
              <button class="btn secondary small" type="button" @click="copyNotebookLmSourceLinks">复制全部原始链接</button>
            </div>
          </div>
        </div>
      </section>

      <section v-if="aiTrends.length > 0" id="questions-panel" class="panel">
        <div class="panel-header">
          <h2>基于今天资讯生成的 6 个追问</h2>
          <span class="eyebrow">参考访谈式深挖：从事实、影响、边界、情绪和行动建议生成口播文案</span>
        </div>
        <div class="questions-grid">
          <button
            v-for="(question, index) in trendQuestions"
            :key="index"
            class="question-card"
            :class="{ selected: selectedTrendQuestion === question }"
            type="button"
            @click="startTrendInterview(question)"
          >
            <div class="question-header">
              <span class="question-number">{{ index + 1 }}</span>
              <h3>{{ question }}</h3>
            </div>
            <div class="question-footer">
              <span>{{ selectedTrendQuestion === question ? "正在探讨" : "点击进入访谈" }}</span>
              <span v-if="trendScripts[question]">已生成文案</span>
            </div>
          </button>
        </div>
        <div v-if="selectedTrendQuestion" class="interview-panel">
          <div class="script-preview-head">
            <strong>访谈式深挖</strong>
            <span>像 ainterview 一样：先回答，再追问，再沉淀成文案</span>
          </div>
          <div class="interview-thread">
            <div
              v-for="(turn, index) in trendInterviewTurns"
              :key="`${turn.role}-${index}`"
              class="interview-turn"
              :class="turn.role"
            >
              <span>{{ turn.role === "answer" ? "我的回答" : turn.role === "system" ? "访谈引导" : "追问" }}</span>
              <p>{{ turn.text }}</p>
            </div>
          </div>
          <textarea
            v-model="trendInterviewAnswer"
            class="interview-input"
            placeholder="写下你的真实想法：它和你的工作、生活、软件开发经历、自媒体计划有什么关系？"
          />
          <div class="voice-input-row">
            <button
              v-if="!trendInterviewRecording"
              class="btn secondary"
              type="button"
              :disabled="busy.trendVoice || !canRecordTrendVoice"
              @click="startTrendVoiceRecording"
            >
              {{ canRecordTrendVoice ? "语音回答" : "网页录音不可用" }}
            </button>
            <button
              v-else
              class="btn accent"
              type="button"
              :disabled="busy.trendVoice"
              @click="stopTrendVoiceRecording"
            >
              停止并转写
            </button>
            <button
              v-if="trendInterviewRecording"
              class="btn secondary"
              type="button"
              :disabled="busy.trendVoice"
              @click="cancelTrendVoiceRecording"
            >
              取消录音
            </button>
            <label class="upload-audio-label">
              上传音频转文字
              <input type="file" accept="audio/*,video/mp4" :disabled="busy.trendVoice" @change="uploadTrendInterviewVoice" />
            </label>
            <span v-if="trendInterviewVoiceNote" class="meta">{{ trendInterviewVoiceNote }}</span>
            <span v-else-if="!canRecordTrendVoice" class="meta">公网 HTTP 页面通常无法直接调用麦克风，可先用手机录音后上传。</span>
          </div>
          <div class="top-actions">
            <button class="btn primary" :disabled="busy.trendInterview" @click="continueTrendInterview()">
              {{ busy.trendInterview ? "追问中..." : "继续追问" }}
            </button>
            <button class="btn accent" :disabled="generatingTrendScript" @click="generateScriptFromTrend(selectedTrendQuestion, aiTrends[0])">
              基于当前问题生成文案
            </button>
          </div>
          <div v-if="trendFollowups.length" class="followup-list">
            <strong>也可以选择一个方向继续问</strong>
            <button
              v-for="followup in trendFollowups"
              :key="followup"
              class="followup-btn"
              type="button"
              @click="chooseFollowupQuestion(followup)"
            >
              {{ followup }}
            </button>
          </div>
          <div v-if="trendScripts[selectedTrendQuestion]" class="script-preview-card interview-script">
            <div class="script-preview-head">
              <strong>已生成文案</strong>
              <button class="btn secondary small inline" @click="copyText(trendScripts[selectedTrendQuestion].script, '文案已复制')">复制</button>
            </div>
            <pre>{{ trendScripts[selectedTrendQuestion].script }}</pre>
            <div v-if="trendScripts[selectedTrendQuestion].quality" class="quality" :class="{ pass: trendScripts[selectedTrendQuestion].quality.passed }">
              <strong>{{ trendScripts[selectedTrendQuestion].quality.profile_label }} · {{ trendScripts[selectedTrendQuestion].quality.passed ? "通过基础检查" : "需要优化" }}</strong>
              <span>{{ trendScripts[selectedTrendQuestion].quality.line_count }} 段 · {{ trendScripts[selectedTrendQuestion].quality.char_count }} 字</span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- 素材与生成 Tab -->
    <div v-if="activeTab === 'materials'">
      <section id="wechat-inbox" class="panel">
      <div class="panel-header">
        <h2>微信素材收件箱</h2>
        <div class="top-actions">
          <button class="btn secondary" :disabled="busy.refreshWechat" @click="refreshWechatMaterials">
            {{ busy.refreshWechat ? "刷新中..." : "刷新微信素材" }}
          </button>
          <button class="btn secondary" :disabled="busy.refreshWechat" @click="clearWechatMaterials">
            全部清除
          </button>
          <button v-if="latestWechatMaterial" class="btn accent" type="button" @click="applyWechatMaterial(latestWechatMaterial)">
            载入最新文案
          </button>
        </div>
      </div>
      <div class="meta">微信发新消息后，点击“刷新微信素材”加载；页面不会自动轮询刷新。</div>
      <div v-if="!wechatMaterials.length" class="meta">
        还没有收到微信素材。你可以在微信测试号里发一句真实经历。
        <span v-if="latestWechatCallbackEvent">
          最近一次微信回调：{{ latestWechatCallbackEvent.created_at }} / {{ latestWechatCallbackEvent.msg_type }} / {{ latestWechatCallbackEvent.action }}，{{ latestWechatCallbackEvent.reason }}
        </span>
      </div>
      <div v-else class="wechat-mailbox">
        <div class="mail-list" aria-label="微信素材列表">
          <button
            v-for="item in wechatMaterials.slice(0, 30)"
            :key="item.id"
            class="mail-row"
            :class="{
              selected: selectedWechatMaterial?.id === item.id,
              ready: item.script,
              failed: item.status === 'preview_failed'
            }"
            type="button"
            @click="selectedWechatMaterialId = item.id"
          >
            <span class="mail-status">{{ item.status === "preview_generated" ? "已生成文案" : item.status === "preview_failed" ? "生成失败" : "已收到素材" }}</span>
            <span class="mail-time">{{ item.created_at }}</span>
            <span class="mail-summary">{{ item.text }}</span>
          </button>
        </div>
        <div v-if="selectedWechatMaterial" class="mail-detail" :class="{ ready: selectedWechatMaterial.script, failed: selectedWechatMaterial.status === 'preview_failed' }">
          <div class="script-preview-head">
            <strong>{{ selectedWechatMaterial.status === "preview_generated" ? "已生成文案" : selectedWechatMaterial.status === "preview_failed" ? "生成失败" : "已收到素材" }}</strong>
            <span>{{ selectedWechatMaterial.created_at }}</span>
          </div>
          <p>{{ selectedWechatMaterial.text }}</p>
          <p v-if="selectedWechatMaterial.error" class="error-text">{{ selectedWechatMaterial.error }}</p>
          <div v-if="selectedWechatMaterial.script" class="generated-copy">
            <strong>已生成文案</strong>
            <pre>{{ selectedWechatMaterial.script }}</pre>
          </div>
          <div class="material-actions">
            <button class="btn primary small" type="button" :disabled="busy.previewScript" @click="generateWechatMaterial(selectedWechatMaterial, 'real_person')">真人口播生成</button>
            <button class="btn primary small" type="button" :disabled="busy.previewScript" @click="generateWechatMaterial(selectedWechatMaterial, 'interview')">嘉宾访谈生成</button>
            <button class="btn secondary small" type="button" @click="applyWechatMaterial(selectedWechatMaterial)">
              {{ selectedWechatMaterial.script ? "载入到编辑区" : "载入素材" }}
            </button>
            <button v-if="selectedWechatMaterial.script" class="btn secondary small" type="button" :disabled="busy.archive === String(selectedWechatMaterial.id)" @click="archiveWechatMaterial(selectedWechatMaterial)">
              {{ busy.archive === String(selectedWechatMaterial.id) ? "归档中..." : "归档 Obsidian" }}
            </button>
            <button class="btn secondary small danger-action" type="button" :disabled="busy.refreshWechat" @click="deleteWechatMaterial(selectedWechatMaterial)">删除本条</button>
          </div>
        </div>
      </div>
      <div v-if="wechatCallbackEvents.length" class="callback-diagnostics">
        <div class="script-preview-head">
          <strong>最近微信回调诊断</strong>
          <div class="diagnostics-head-actions">
            <span>用于判断消息是否真的进入后端</span>
            <button class="btn secondary small danger-action" type="button" :disabled="busy.clearWechatDiagnostics" @click="clearWechatDiagnostics">
              {{ busy.clearWechatDiagnostics ? "清理中..." : "清空诊断" }}
            </button>
          </div>
        </div>
        <div class="callback-list">
          <div v-for="event in wechatCallbackEvents.slice(0, 8)" :key="event.id" class="callback-row" :class="event.action">
            <span class="callback-time">{{ event.created_at }}</span>
            <span class="callback-type">{{ event.msg_type }}{{ event.event ? `/${event.event}` : "" }}</span>
            <span class="callback-action">{{ event.action }}</span>
            <span class="callback-reason">{{ event.reason }}</span>
            <span class="callback-preview">{{ event.content_preview || "无文本内容" }}</span>
          </div>
        </div>
      </div>
    </section>

    <section id="input-panel" class="panel">
      <div class="panel-header">
        <h2>1. IP 选题与内容模式</h2>
        <span class="eyebrow">高认知 · 强共情 · 有温度</span>
      </div>
      <div class="field-grid">
        <label class="field">
          <span>内容支柱</span>
          <select v-model="kidsForm.content_mode">
            <option value="working_mom">职场妈妈痛点解决</option>
            <option value="creator_tips">短视频/剪辑提效</option>
            <option value="ai_growth">AI 学习与职业重塑</option>
          </select>
        </label>
        <label class="field">
          <span>文案生成</span>
          <select v-model="kidsForm.script_provider">
            <option value="gemini_minimax">Gemini 初稿 → DeepSeek 审核 → Gemini 修复 → DeepSeek 复审</option>
            <option value="minimax_plan">MiniMax Token Plan 初稿 → DeepSeek 审核 → MiniMax 修复</option>
            <option value="zhipu">智谱初稿（备用）</option>
            <option value="local">本地规则兜底</option>
          </select>
        </label>
        <label class="field">
          <span>时长（秒）</span>
          <input v-model.number="kidsForm.seconds" type="number" min="30" max="60" />
        </label>
        <label class="field wide">
          <span>输入今天的憋屈/剪辑心得</span>
          <input v-model="kidsForm.topic" placeholder="例如：今天送娃迟到被老板点名，心里很憋屈" />
        </label>
        <label class="field wide">
          <span>本条内容要解决的问题</span>
          <input v-model="kidsForm.learning_goal" placeholder="例如：把职场妈妈的情绪困境转成一个可执行的 AI 提效方案" />
        </label>
        <label class="field wide">
          <span>爆款角度/补充提示</span>
          <input v-model="kidsForm.prompt_hint" placeholder="例如：开头要有痛点暴击，结尾引导评论区分享同款经历" />
        </label>
        <label class="field">
          <span>真人/角色声音</span>
          <select v-model="kidsForm.edge_voice">
            <option v-for="voice in voicePresets" :key="voice.label" :value="voice.value">{{ voice.label }}</option>
          </select>
        </label>
        <label class="field">
          <span>嘉宾A参考声音</span>
          <input type="file" accept="audio/*,video/*" :disabled="busy.uploadVoice" @change="uploadCharacterVoice('maodou', $event)" />
        </label>
        <label class="field">
          <span>嘉宾B参考声音</span>
          <input type="file" accept="audio/*,video/*" :disabled="busy.uploadVoice" @change="uploadCharacterVoice('peanut', $event)" />
        </label>
        <div class="reference-card voice-card" :class="{ ready: kidsForm.maodou_voice_reference_path }">
          <div>
            <strong>{{ kidsForm.maodou_voice_reference_path ? "嘉宾A声音已提取" : "未录入嘉宾A声音" }}</strong>
            <p>上传嘉宾A的录音或视频，系统会提取前 30 秒作为访谈语气参考。</p>
            <audio v-if="maodouVoiceUrl" :src="maodouVoiceUrl" controls preload="metadata"></audio>
            <button v-if="kidsForm.maodou_voice_reference_path" class="btn secondary small" type="button" @click="clearCharacterVoice('maodou')">清除嘉宾A声音</button>
          </div>
        </div>
        <div class="reference-card voice-card" :class="{ ready: kidsForm.peanut_voice_reference_path }">
          <div>
            <strong>{{ kidsForm.peanut_voice_reference_path ? "嘉宾B声音已提取" : "未录入嘉宾B声音" }}</strong>
            <p>上传嘉宾B的录音或视频，系统会提取前 30 秒作为访谈语气参考。</p>
            <audio v-if="peanutVoiceUrl" :src="peanutVoiceUrl" controls preload="metadata"></audio>
            <button v-if="kidsForm.peanut_voice_reference_path" class="btn secondary small" type="button" @click="clearCharacterVoice('peanut')">清除嘉宾B声音</button>
          </div>
        </div>
        <label class="field">
          <span>一键切换成片模式</span>
          <select v-model="kidsForm.animation_style">
            <option value="videohao_real_person">真人出镜口播</option>
            <option value="notebooklm_duo_interview">嘉宾A / 嘉宾B访谈</option>
            <option value="cartoon_3d_duo_cinematic">3D 双角色访谈</option>
          </select>
        </label>
        <label class="field">
          <span>视频生成引擎</span>
          <select v-model="kidsForm.video_provider">
            <option value="zhipu_qingying">智谱清影 CogVideoX-3</option>
            <option value="kling">可灵 API（备用）</option>
            <option value="local_preview">本地预览（低保真）</option>
          </select>
        </label>
        <label class="field switch-field">
          <span>一键启用：我的真人声音蒸馏</span>
          <input v-model="kidsForm.use_my_real_voice" type="checkbox" />
        </label>
        <label class="field wide">
          <span>人物/角色参考图</span>
          <input type="file" accept="image/png,image/jpeg,image/webp" :disabled="busy.uploadReference" @change="uploadReferenceImage" />
        </label>
        <div class="reference-card wide" :class="{ ready: kidsForm.reference_image_path }">
          <img v-if="referenceImageUrl" :src="referenceImageUrl" alt="人物/角色参考图" />
          <div>
            <strong>{{ kidsForm.reference_image_path ? "模板图已锁定" : "未上传模板图" }}</strong>
            <p>{{ kidsForm.reference_image_path ? "生成任务会把这张图作为人物或角色视觉参考。" : "不上传模板图时，智谱清影会根据文案原创生成匹配职场妈妈 IP 的视频画面。" }}</p>
            <button v-if="kidsForm.reference_image_path" class="btn secondary small" type="button" @click="clearReferenceImage">清除模板图，改用文案原创</button>
          </div>
        </div>
      </div>
    </section>

    <section id="script-panel" class="panel">
      <div class="panel-header">
        <h2>2. 文案与质量检查</h2>
        <span class="eyebrow">黄金钩子 · 情绪价值 · 可落地方法</span>
      </div>
      <label class="field script-field">
        <span>可编辑文案</span>
        <textarea v-model="kidsForm.custom_script" placeholder="可以先点“生成文案预览”，也可以直接输入视频号口播稿或嘉宾访谈稿，例如：[0-3秒钩子] 如果你也在公司洗手间崩溃过，请听我说..." />
      </label>

      <div v-if="kidsForm.custom_script" class="script-preview-card">
        <div class="script-preview-head">
          <strong>当前生成文案</strong>
          <div class="top-actions">
            <button class="btn secondary small inline" type="button" @click="copyText(kidsForm.custom_script, '文案已复制。')">复制文案</button>
            <button class="btn secondary small inline" type="button" :disabled="busy.archive === 'current'" @click="archiveCurrentScript">
              {{ busy.archive === "current" ? "归档中..." : "归档 Obsidian" }}
            </button>
          </div>
        </div>
        <pre>{{ kidsForm.custom_script }}</pre>
      </div>

      <div v-if="deepseekReview" class="review-card">
        <div class="script-preview-head">
          <strong>DeepSeek 审核意见</strong>
          <span>分数：{{ deepseekReview.score ?? "未返回" }}</span>
        </div>
        <p v-if="deepseekReview.strongest_line">最强句：{{ deepseekReview.strongest_line }}</p>
        <p v-if="deepseekReview.weakest_line">最弱句：{{ deepseekReview.weakest_line }}</p>
        <ul>
          <li v-for="item in reviewLines(deepseekReview)" :key="item">{{ item }}</li>
        </ul>
        <label class="field">
          <span>人工补充审核意见</span>
          <textarea class="review-notes" v-model="humanReviewNotes" placeholder="例如：语气再像我本人一点，减少夸张网感；结尾要引导评论区说出今天最崩溃的一件事。" />
        </label>
        <button class="btn accent" :disabled="busy.reviseScript" @click="reviseWithReview">
          {{ busy.reviseScript ? "修改中..." : "根据审核意见二次修改" }}
        </button>
      </div>

      <div v-if="finalReview" class="review-card final-review">
        <div class="script-preview-head">
          <strong>DeepSeek 终稿复审</strong>
          <span>分数：{{ finalReview.score ?? "未返回" }}</span>
        </div>
        <ul>
          <li v-for="item in reviewLines(finalReview)" :key="item">{{ item }}</li>
        </ul>
      </div>

      <div v-if="quality" class="quality" :class="{ pass: quality.passed }">
        <strong>{{ quality.profile_label }} · {{ quality.passed ? "通过基础检查" : "需要优化" }}</strong>
        <span>{{ quality.line_count }} 段 · {{ quality.char_count }} 字 · 互动点 {{ quality.interaction_count }}</span>
        <p v-if="!quality.issues?.length">文案包含痛点钩子、真实经历、方法输出和评论区互动。</p>
        <p v-for="issue in quality.issues" :key="issue">{{ issue }}</p>
      </div>

      <div v-if="referenceStyleContract" class="quality reference-lock" :class="{ pass: kidsForm.reference_image_path }">
        <strong>{{ kidsForm.reference_image_path ? "角色参考图已进入生成任务" : "智谱清影将按文案原创角色" }}</strong>
        <span>{{ referenceStyleContract.fidelity_target }} · {{ visualPipeline?.current_local_renderer || "preview_fallback_only" }}</span>
        <p>{{ kidsForm.reference_image_path ? "当前任务会携带 reference_image / character_reference_image 字段。" : "当前任务不会携带默认图片或基础视频，会让智谱清影根据文案生成原创拟人化毛豆和花生。" }}</p>
      </div>

      <div v-if="previewStoryboard.length" class="storyboard">
        <div class="storyboard-head">分镜预览：{{ previewStoryboard.length }} 段</div>
        <div v-for="shot in previewStoryboard" :key="shot.index" class="shot-row">
          <span>{{ shot.index }}</span>
          <strong>{{ shot.scene_key }}</strong>
          <em>{{ shot.learning_step }}</em>
          <p>{{ shot.line }}</p>
        </div>
      </div>

      <div v-if="hardRules.length" class="rules">{{ hardRules.join(" | ") }}</div>
    </section>

    <section id="jobs-panel" class="panel">
      <div class="panel-header">
        <h2>3. 任务与预览</h2>
        <div class="top-actions">
          <button class="btn secondary" :disabled="busy.refresh || busy.connect" @click="refreshJobs">刷新任务</button>
          <button class="btn secondary" :disabled="busy.cleanup" @click="clearHumanData">
            {{ busy.cleanup ? "清理中..." : "清理真人数据" }}
          </button>
        </div>
      </div>

      <div v-if="runningKidsJobs.length" class="stack">
        <div v-for="job in runningKidsJobs.slice(0, 6)" :key="job.id" class="job-card">
          <div class="job-title">{{ job.request?.title || job.request?.topic || job.id }}</div>
          <div class="meta">{{ job.progress_message || job.progress_stage || job.status }}</div>
          <div class="progress-track"><div class="progress-fill" :style="{ width: `${jobProgress(job)}%` }"></div></div>
        </div>
      </div>
      <div v-else class="meta">当前没有进行中的任务。</div>

      <div v-if="failedKidsJobs.length" class="jobs-grid failed-jobs">
        <div v-for="job in failedKidsJobs.slice(0, 4)" :key="job.id" class="job-card failed">
          <div class="job-title">{{ job.request?.title || job.request?.topic || job.id }}</div>
          <div class="meta">{{ job.created_at }} / {{ job.progress_stage || job.status }}</div>
          <p class="error-text">{{ job.error || job.progress_message || "任务失败" }}</p>
          <button class="btn secondary small" :disabled="deletingJobId === String(job.id)" @click="deleteHistoryJob(job.id)">
            {{ deletingJobId === String(job.id) ? "删除中..." : "删除记录" }}
          </button>
        </div>
      </div>

      <div class="jobs-grid">
        <div v-for="job in completedKidsJobs.slice(0, 8)" :key="job.id" class="job-card">
          <div class="job-title">{{ job.request?.title || job.request?.topic || job.id }}</div>
          <div class="meta">
            {{ job.created_at }} · {{ job.summary?.duration_seconds || 0 }}s · {{ job.summary?.tts_provider || "edge" }}
          </div>
          <div v-if="job.artifacts" class="links">
            <a v-if="job.artifacts.script_url" :href="mediaUrl(job.artifacts.script_url)" target="_blank">脚本</a>
            <a v-if="job.artifacts.audio_url" :href="mediaUrl(job.artifacts.audio_url)" target="_blank">音频</a>
            <a v-if="job.artifacts.video_url" :href="mediaUrl(job.artifacts.video_url)" target="_blank">打开视频</a>
          </div>
          <video v-if="job.artifacts?.video_url" class="video-preview" :src="mediaUrl(job.artifacts.video_url)" controls preload="metadata"></video>
          <div class="publish-actions">
            <button class="btn accent small" :disabled="busy.publish === String(job.id)" @click="prepareDouyinPublish(job)">
              {{ busy.publish === String(job.id) ? "准备中..." : "发布助手" }}
            </button>
          </div>
          <div v-if="publishDrafts[job.id]" class="publish-card">
            <div class="publish-card-head">
              <strong>抖音发布助手</strong>
              <span>最后一步需要你手动点发布</span>
            </div>
            <label class="field">
              <span>标题 + 话题</span>
              <textarea class="caption-box" readonly :value="publishDrafts[job.id].caption"></textarea>
            </label>
            <label class="field">
              <span>本地视频文件路径</span>
              <input readonly :value="publishDrafts[job.id].video_file_path" />
            </label>
            <div class="publish-buttons">
              <button class="btn secondary small" @click="copyText(publishDrafts[job.id].caption, '标题和话题已复制。')">复制标题话题</button>
              <button class="btn secondary small" @click="copyText(publishDrafts[job.id].video_file_path, '视频路径已复制。')">复制视频路径</button>
              <button class="btn accent small" @click="openDouyinCreator(publishDrafts[job.id])">打开抖音投稿页</button>
            </div>
            <ol>
              <li v-for="step in publishDrafts[job.id].steps" :key="step">{{ step }}</li>
            </ol>
          </div>
          <button class="btn secondary small" :disabled="deletingJobId === String(job.id)" @click="deleteHistoryJob(job.id)">
            {{ deletingJobId === String(job.id) ? "删除中..." : "删除记录" }}
          </button>
        </div>
      </div>
    </section>
    </div>

    <div v-if="activeTab === 'stocks'">
      <section id="stock-panel" class="panel stock-module">
        <div class="panel-header">
          <h2>股票分析</h2>
          <span class="eyebrow">行情 · 技术指标 · 持仓 · 预警 · 复盘</span>
        </div>
        <div class="stock-workbench">
          <div class="stock-control-panel">
            <div class="field-grid">
              <label class="field">
                <span>股票代码 / 名称</span>
                <input v-model="stockForm.symbol" placeholder="AAPL / 00700 / 600519" @keyup.enter="searchStockSymbols" />
              </label>
              <label class="field">
                <span>市场</span>
                <select v-model="stockForm.market">
                  <option value="US">美股</option>
                  <option value="HK">港股</option>
                  <option value="CN">A股</option>
                </select>
              </label>
              <label class="field">
                <span>显示名称</span>
                <input v-model="stockForm.name" placeholder="可选" />
              </label>
              <label class="field">
                <span>成本价</span>
                <input v-model="stockForm.cost" inputmode="decimal" placeholder="可选" />
              </label>
              <label class="field">
                <span>持仓数量</span>
                <input v-model="stockForm.shares" inputmode="decimal" placeholder="可选" />
              </label>
              <label class="field">
                <span>上方预警</span>
                <input v-model="stockForm.alert_high" inputmode="decimal" placeholder="突破提醒" />
              </label>
              <label class="field">
                <span>下方预警</span>
                <input v-model="stockForm.alert_low" inputmode="decimal" placeholder="止损提醒" />
              </label>
              <label class="field">
                <span>关注理由</span>
                <input v-model="stockForm.notes" placeholder="财报、行业、策略..." />
              </label>
            </div>
            <textarea v-model="stockQuestion" class="stock-question" rows="3"></textarea>
            <div class="stock-actions">
              <button class="btn secondary" type="button" :disabled="busy.stockSearch" @click="searchStockSymbols">
                {{ busy.stockSearch ? "搜索中..." : "搜索标的" }}
              </button>
              <button class="btn secondary" type="button" :disabled="busy.stockSave" @click="saveStockToWatchlist">
                {{ busy.stockSave ? "保存中..." : "加入/更新自选" }}
              </button>
              <button class="btn accent" type="button" :disabled="busy.stockAnalyze" @click="analyzeStock()">
                {{ busy.stockAnalyze ? "分析中..." : "生成 AI 辅助分析" }}
              </button>
            </div>
            <div v-if="stockSearchResults.length" class="stock-search-results">
              <button v-for="item in stockSearchResults" :key="item.symbol" type="button" @click="chooseStockSearchResult(item)">
                <strong>{{ item.symbol }}</strong>
                <span>{{ item.name }} · {{ item.exchange || item.market }}</span>
              </button>
            </div>
          </div>

          <div class="stock-market-card">
            <div class="stock-section-head">
              <strong>全球市场温度</strong>
              <button class="btn secondary small" type="button" :disabled="busy.stockMarket" @click="refreshStockMarket">
                {{ busy.stockMarket ? "刷新中" : "刷新" }}
              </button>
            </div>
            <div class="market-mood">
              <span>{{ stockMarket?.mood || "待刷新" }}</span>
              <strong :class="stockChangeClass(stockMarket?.average_change)">{{ formatStockNumber(stockMarket?.average_change) }}%</strong>
            </div>
            <div class="market-index-list">
              <div v-for="item in stockMarket?.items || []" :key="item.symbol" class="market-index-row">
                <span>{{ item.name }}</span>
                <strong>{{ item.price || "--" }}</strong>
                <em :class="stockChangeClass(item.change_percent)">{{ formatStockNumber(item.change_percent) }}%</em>
              </div>
            </div>
          </div>
        </div>

        <section class="stock-skill-panel">
          <div class="stock-section-head">
            <strong>Stock Skills</strong>
            <button class="btn secondary small" type="button" :disabled="busy.stockSkills" @click="refreshStockSkills">
              {{ busy.stockSkills ? "刷新中" : "刷新 Skills" }}
            </button>
          </div>
          <div class="stock-skill-grid">
            <button
              v-for="skill in stockSkills"
              :key="skill.id"
              type="button"
              class="stock-skill-card"
              :class="{ active: selectedStockSkill === skill.id }"
              @click="selectedStockSkill = skill.id"
            >
              <strong>{{ skill.name }}</strong>
              <span>{{ skill.description }}</span>
            </button>
          </div>
          <div class="stock-actions">
            <button class="btn accent" type="button" :disabled="busy.stockSkillRun" @click="runStockSkill()">
              {{ busy.stockSkillRun ? "运行中..." : `运行 ${stockSkillName(selectedStockSkill)}` }}
            </button>
            <button class="btn secondary" type="button" :disabled="busy.stockSkillRun" @click="runStockSkill('watchlist_review', '')">
              自选股一键复盘
            </button>
            <button class="btn secondary" type="button" :disabled="busy.stockSkillRun" @click="runStockSkill('condition_screening', '')">
              按问题筛选自选
            </button>
          </div>
          <div v-if="stockSkillResult" class="stock-skill-result">
            <div class="stock-score-line">
              <span>{{ stockSkillResult.title }}</span>
              <em>{{ stockSkillName(stockSkillResult.skill_id) }}</em>
            </div>
            <div v-if="stockSkillResult.cards?.length" class="indicator-grid">
              <span v-for="card in stockSkillResult.cards" :key="card.title">
                {{ card.title }}
                <strong>{{ card.value }}</strong>
                <small>{{ card.note }}</small>
              </span>
            </div>
            <pre class="stock-report">{{ stockSkillResult.report }}</pre>
            <small>{{ stockSkillResult.disclaimer }}</small>
          </div>
        </section>

        <div class="stock-dashboard-grid">
          <section class="stock-list-panel">
            <div class="stock-section-head">
              <strong>自选与持仓</strong>
              <button class="btn secondary small" type="button" :disabled="busy.stockRefresh" @click="refreshStockWatchlist">
                {{ busy.stockRefresh ? "刷新中" : "刷新行情" }}
              </button>
            </div>
            <div v-if="!stockWatchlist.length" class="stock-empty">还没有自选股，先搜索代码并加入。</div>
            <article v-for="item in stockWatchlist" :key="item.symbol" class="stock-watch-card">
              <div class="stock-watch-main">
                <div>
                  <strong>{{ item.name || item.symbol }}</strong>
                  <span>{{ item.symbol }} · {{ item.quote?.market || item.market }}</span>
                </div>
                <div class="stock-price">
                  <strong>{{ item.quote?.price ?? "--" }}</strong>
                  <em :class="stockChangeClass(item.quote?.change_percent)">{{ formatStockNumber(item.quote?.change_percent) }}%</em>
                </div>
              </div>
              <div class="stock-mini-meta">
                <span>成本 {{ item.cost || "--" }}</span>
                <span>数量 {{ item.shares || "--" }}</span>
                <span>市值 {{ item.position?.market_value ?? "--" }}</span>
                <span :class="stockChangeClass(item.position?.profit_percent)">盈亏 {{ formatStockNumber(item.position?.profit_percent) }}%</span>
              </div>
              <div v-if="item.position?.alerts?.length" class="stock-alerts">
                <span v-for="alert in item.position.alerts" :key="alert">{{ alert }}</span>
              </div>
              <p v-if="item.notes">{{ item.notes }}</p>
              <div class="stock-row-actions">
                <button class="btn secondary small" type="button" @click="analyzeStock(item.symbol)">分析</button>
                <button class="btn secondary small danger-action" type="button" @click="deleteStockFromWatchlist(item.symbol)">移除</button>
              </div>
            </article>
          </section>

          <section class="stock-analysis-panel">
            <div class="stock-section-head">
              <strong>AI 辅助分析报告</strong>
              <button class="btn secondary small" type="button" :disabled="!stockAnalysis?.report" @click="copyText(stockAnalysis?.report, '股票分析报告已复制。')">复制报告</button>
            </div>
            <div v-if="!stockAnalysis" class="stock-empty">输入股票代码后生成分析，会展示趋势、指标、风险、机会和预警线。</div>
            <div v-else class="stock-analysis-result">
              <div class="stock-score-line">
                <span>{{ stockAnalysis.quote?.name }} · {{ stockAnalysis.quote?.symbol }}</span>
                <strong>{{ stockAnalysis.score }}/100</strong>
                <em>{{ stockAnalysis.stance }}</em>
              </div>
              <div v-if="stockAnalysis.conclusion" class="stock-clear-conclusion">
                <strong>明确结论：{{ stockAnalysis.conclusion.label }}</strong>
                <p>{{ stockAnalysis.conclusion.summary }}</p>
                <span>{{ stockAnalysis.conclusion.action }}</span>
              </div>
              <div v-if="stockAnalysis.upside_targets?.length" class="stock-target-grid">
                <div v-for="item in stockAnalysis.upside_targets" :key="item.label">
                  <span>{{ item.label }}</span>
                  <strong>{{ item.target_price }}</strong>
                  <em>约 {{ item.upside_percent }}%</em>
                  <small>{{ item.basis }}</small>
                </div>
              </div>
              <svg class="stock-sparkline" viewBox="0 0 320 88" preserveAspectRatio="none" aria-hidden="true">
                <polyline :points="stockKlinePoints(stockAnalysis.kline)" fill="none" stroke="#00d5e8" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" />
              </svg>
              <div class="indicator-grid">
                <span>趋势 <strong>{{ stockAnalysis.indicators?.trend }}</strong></span>
                <span>RSI <strong>{{ stockAnalysis.indicators?.rsi14 ?? "--" }}</strong></span>
                <span>MACD <strong>{{ stockAnalysis.indicators?.macd?.signal }}</strong></span>
                <span>BOLL <strong>{{ stockAnalysis.indicators?.boll?.position }}</strong></span>
                <span>5日收益 <strong>{{ stockAnalysis.indicators?.return5 ?? "--" }}%</strong></span>
                <span>20日波动 <strong>{{ stockAnalysis.indicators?.volatility20 ?? "--" }}%</strong></span>
              </div>
              <div class="stock-signal-columns">
                <div>
                  <strong>机会</strong>
                  <p v-for="item in stockAnalysis.opportunities" :key="item">{{ item }}</p>
                </div>
                <div>
                  <strong>风险</strong>
                  <p v-for="item in stockAnalysis.risks" :key="item">{{ item }}</p>
                </div>
              </div>
              <div class="stock-signal-columns">
                <div>
                  <strong>预警线</strong>
                  <p v-for="item in stockAnalysis.alerts" :key="item.label">{{ item.label }}：{{ item.price || item.percent + '%' }}</p>
                </div>
                <div>
                  <strong>持仓动作</strong>
                  <p v-for="item in stockAnalysis.position_plan" :key="item.title">{{ item.title }}：{{ item.text }}</p>
                </div>
              </div>
              <pre class="stock-report">{{ stockAnalysis.report }}</pre>
              <small>{{ stockAnalysis.disclaimer }}</small>
            </div>
          </section>
        </div>

        <section class="stock-history-panel">
          <div class="stock-section-head">
            <strong>分析历史</strong>
            <button class="btn secondary small" type="button" :disabled="busy.stockHistory" @click="refreshStockHistory">
              {{ busy.stockHistory ? "刷新中" : "查看全部" }}
            </button>
          </div>
          <div v-if="!stockHistory.length" class="stock-empty">暂无历史报告。</div>
          <div v-else class="stock-history-list">
            <button v-for="item in stockHistory" :key="item.id" type="button" @click="stockAnalysis = { ...stockAnalysis, report: item.report, score: item.score, stance: item.stance, quote: { symbol: item.symbol, name: item.name } }">
              <span>{{ item.created_at }}</span>
              <strong>{{ item.name }} · {{ item.symbol }}</strong>
              <em>{{ item.score }}/100 · {{ item.stance }}</em>
            </button>
          </div>
        </section>

        <section class="stock-history-panel">
          <div class="stock-section-head">
            <strong>Stock Skill 运行历史</strong>
            <button class="btn secondary small" type="button" :disabled="busy.stockSkills" @click="refreshStockSkills">
              {{ busy.stockSkills ? "刷新中" : "刷新" }}
            </button>
          </div>
          <div v-if="!stockSkillRuns.length" class="stock-empty">暂无 Skill 运行记录。</div>
          <div v-else class="stock-history-list">
            <button v-for="item in stockSkillRuns" :key="item.id" type="button" @click="stockSkillResult = item">
              <span>{{ item.created_at }}</span>
              <strong>{{ item.title }}</strong>
              <em>{{ stockSkillName(item.skill_id) }} · {{ item.symbol || "自选股" }}</em>
            </button>
          </div>
        </section>
      </section>
    </div>

    <button v-if="activeTab === 'materials'" class="floating-generate" :disabled="busy.generate" @click="generateKidsVideo">
      {{ busy.generate ? "提交中..." : "生成视频" }}
    </button>
      <footer class="studio-footer">
        <span><img class="brand-logo-img small" src="/favicon.svg?v=2" alt="" aria-hidden="true" /> 灵感工坊 AI Studio · inspwk.site</span>
        <span>© 2026 · AI 洞察 · 软件开发 · 职场成长 · 内容创作</span>
      </footer>
    </main>
  </div>
</template>

<style scoped>
* {
  box-sizing: border-box;
}

.studio-page {
  min-height: 100vh;
  background: #06111c;
  color: #f7fbff;
}

.studio-page.module-mode {
  padding-left: 220px;
}

.studio-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 30;
  display: grid;
  grid-template-rows: auto 1fr auto;
  width: 220px;
  padding: 18px 14px;
  border-right: 1px solid rgba(142, 171, 205, 0.16);
  background: #081522;
}

.sidebar-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  border: 0;
  background: transparent;
  color: #f7fbff;
  text-align: left;
  cursor: pointer;
}

.sidebar-brand strong {
  display: block;
  font-size: 15px;
}

.sidebar-brand small {
  color: #9fb5ce;
  font-size: 10px;
}

.sidebar-nav {
  display: grid;
  align-content: start;
  gap: 8px;
  margin-top: 26px;
}

.sidebar-nav button {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  border: 1px solid transparent;
  border-radius: 10px;
  padding: 0 10px;
  background: transparent;
  color: #a9bfda;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s ease, background 0.18s ease, color 0.18s ease;
}

.sidebar-nav button:hover,
.sidebar-nav button.active {
  border-color: rgba(0, 213, 232, 0.28);
  background: rgba(0, 213, 232, 0.1);
  color: #f7fbff;
}

.sidebar-nav span {
  display: inline-grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(0, 213, 232, 0.14);
  color: #00d5e8;
  font-size: 11px;
  font-weight: 900;
}

.sidebar-nav strong {
  font-size: 14px;
}

.sidebar-footer {
  color: #6f859f;
  font-size: 12px;
}

.studio-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 20px;
  min-height: 72px;
  padding: 0 24px;
  border-bottom: 1px solid rgba(142, 171, 205, 0.16);
  background: rgba(9, 21, 34, 0.95);
  backdrop-filter: blur(18px);
}

.brand-mini,
.studio-nav button {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
}

.brand-mini {
  display: inline-flex;
  align-items: center;
  justify-self: start;
  gap: 12px;
  padding: 0;
  text-align: left;
}

.brand-mini strong {
  display: block;
  font-size: 16px;
}

.brand-mini small,
.studio-footer,
.module-hero p,
.dashboard-hero p {
  color: #9fb5ce;
}

.brand-mark {
  display: inline-grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: #00d5e8;
  color: #06111c;
  font-size: 13px;
  font-weight: 900;
}

.brand-mark.small {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  font-size: 10px;
}

.brand-logo-img {
  display: block;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  flex: 0 0 auto;
}

.brand-logo-img.small {
  width: 22px;
  height: 22px;
  border-radius: 6px;
}

.studio-nav {
  display: inline-flex;
  align-items: center;
  gap: 26px;
}

.studio-nav button {
  color: #9fb5ce;
  font-size: 14px;
  transition: color 0.18s ease;
}

.studio-nav button:hover,
.studio-nav button.active {
  color: #f7fbff;
}

.header-actions {
  display: inline-flex;
  align-items: center;
  justify-self: end;
  gap: 16px;
  color: #d9e7f7;
  font-size: 14px;
}

.header-cta {
  min-height: 36px;
  padding: 0 18px;
}

.dashboard {
  display: grid;
  gap: 0;
}

.dashboard-hero {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 24px;
  min-height: 150px;
  padding: 28px 0 48px;
}

.dashboard-kicker {
  display: block;
  margin-bottom: 12px;
  color: #00d5e8;
  font-size: 13px;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.dashboard h1,
.module-hero h1 {
  margin: 0;
  color: #fff;
  font-size: clamp(32px, 5vw, 42px);
  line-height: 1.14;
}

.coverage-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #b7cbe1;
  font-size: 14px;
  white-space: nowrap;
}

.coverage-pill::before {
  content: "";
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-radius: 999px;
}

.workflow-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 16px;
  padding-bottom: 92px;
}

.workflow-card,
.metric-card,
.launch-panel,
.module-hero,
.panel {
  border: 1px solid rgba(142, 171, 205, 0.18);
  background: #0d1b2a;
}

.workflow-card,
.metric-card {
  position: relative;
  display: grid;
  align-content: start;
  min-height: 142px;
  border-radius: 14px;
  padding: 20px;
  color: #f7fbff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s ease, background 0.18s ease, transform 0.18s ease;
}

.workflow-card:hover,
.metric-card:hover {
  transform: translateY(-2px);
  border-color: rgba(0, 213, 232, 0.46);
  background: #102235;
}

.module-icon {
  display: inline-grid;
  place-items: center;
  width: 40px;
  height: 40px;
  margin-bottom: 18px;
  border-radius: 12px;
  background: rgba(0, 213, 232, 0.16);
  color: #00d5e8;
}

.module-icon::before {
  content: attr(data-icon);
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
}

.module-icon.compact {
  width: 36px;
  height: 36px;
  margin-bottom: 16px;
}

.module-icon.compact::before {
  font-size: 10px;
}

.module-number {
  position: absolute;
  top: 32px;
  right: 18px;
  color: #9fd9ff;
  font-size: 13px;
}

.workflow-card strong {
  margin-bottom: 6px;
  font-size: 18px;
}

.workflow-card small,
.metric-card small {
  color: #aed0ef;
  line-height: 1.45;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  padding: 80px 0;
  border-top: 1px solid rgba(142, 171, 205, 0.16);
  border-bottom: 1px solid rgba(142, 171, 205, 0.16);
}

.metric-card {
  min-height: 162px;
}

.metric-card strong {
  font-size: 32px;
  line-height: 1;
}

.launch-panel {
  width: min(980px, 100%);
  margin: 96px auto;
  padding: 48px 28px;
  border-radius: 24px;
  text-align: center;
  background:
    linear-gradient(120deg, rgba(0, 213, 232, 0.08), transparent 46%),
    #0b1b2a;
}

.launch-panel h2 {
  margin: 0;
  color: #fff;
  font-size: clamp(28px, 4vw, 38px);
}

.launch-panel h2 span {
  color: #00d5e8;
}

.launch-panel p {
  margin-top: 18px;
  color: #b7cbe1;
}

.launch-actions {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 32px;
}

.module-hero {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 24px;
  min-height: 210px;
  padding: 30px;
  border-radius: 18px;
  background:
    linear-gradient(120deg, rgba(0, 213, 232, 0.1), transparent 50%),
    #0b1b2a;
}

.studio-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 34px 0 0;
  border-top: 1px solid rgba(142, 171, 205, 0.16);
  font-size: 14px;
}

.studio-footer span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 4px;
}

.tab-btn {
  flex: 1;
  border: 1px solid rgba(142, 171, 205, 0.2);
  border-radius: 8px;
  padding: 12px 20px;
  font-size: 15px;
  font-weight: 700;
  background: #0d1b2a;
  color: #a9bfda;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  background: #102235;
}

.tab-btn.active {
  background: rgba(0, 213, 232, 0.12);
  color: #fff;
  border-color: rgba(0, 213, 232, 0.46);
  box-shadow: none;
}

.questions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.question-card {
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  padding: 16px;
  background: #fdfdff;
  color: #1f3045;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.18s ease, background 0.18s ease, box-shadow 0.18s ease;
}

.question-card:hover {
  border-color: #8db8ff;
  background: #f6faff;
  box-shadow: 0 8px 18px rgba(36, 107, 254, 0.08);
}

.question-card.selected {
  border-color: #246bfe;
  background: #f0f6ff;
}

.question-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.question-number {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: #246bfe;
  color: white;
  font-weight: 800;
  border-radius: 50%;
  font-size: 14px;
}

.question-card h3 {
  font-size: 15px;
  margin: 0;
  color: #1f3045;
  line-height: 1.4;
}

.question-footer {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.question-footer span {
  border-radius: 999px;
  background: #eef5ff;
  color: #40546e;
  padding: 4px 8px;
  font-size: 12px;
  font-weight: 800;
}

.interview-panel {
  margin-top: 18px;
  border: 1px solid #b9d6ff;
  border-radius: 8px;
  background: #f7fbff;
  padding: 16px;
}

.interview-thread {
  display: grid;
  gap: 10px;
  margin: 12px 0;
}

.interview-turn {
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  background: white;
  padding: 12px;
}

.interview-turn span {
  display: inline-block;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 800;
  color: #59708c;
}

.interview-turn p {
  margin: 0;
  line-height: 1.7;
}

.interview-turn.answer {
  background: #ecfff6;
  border-color: #a9e7c9;
}

.interview-turn.question {
  background: #fffdf2;
  border-color: #f0df9b;
}

.interview-input {
  width: 100%;
  min-height: 96px;
  resize: vertical;
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  padding: 12px;
  font: inherit;
  line-height: 1.6;
  margin-bottom: 12px;
}

.voice-input-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin: -2px 0 12px;
}

.upload-audio-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  background: #f6f9ff;
  color: #40546e;
  padding: 8px 12px;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
}

.upload-audio-label input {
  display: none;
}

.followup-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.followup-btn {
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  background: white;
  color: #1f3045;
  text-align: left;
  padding: 10px 12px;
  cursor: pointer;
}

.followup-btn:hover {
  border-color: #246bfe;
  background: #f0f6ff;
}

.interview-script {
  margin-top: 14px;
}

.app-shell {
  width: min(1180px, 100% - 28px);
  margin: 20px auto 44px;
  display: grid;
  gap: 16px;
  color: #17253a;
}

.hero,
.panel {
  border: 1px solid rgba(120, 144, 177, 0.22);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.09);
  backdrop-filter: blur(18px);
}

.hero {
  position: relative;
  overflow: hidden;
  min-height: 250px;
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 24px;
  padding: 30px;
  background:
    radial-gradient(circle at 14% 20%, rgba(34, 197, 94, 0.28), transparent 24%),
    radial-gradient(circle at 78% 8%, rgba(56, 189, 248, 0.34), transparent 30%),
    linear-gradient(135deg, #0b1220 0%, #12243a 46%, #173a47 100%);
  color: #f8fbff;
}

.hero::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(rgba(255, 255, 255, 0.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.055) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: linear-gradient(90deg, rgba(0, 0, 0, 0.88), transparent 82%);
}

.hero::after {
  content: "";
  position: absolute;
  right: -80px;
  top: -110px;
  width: 320px;
  height: 320px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(249, 115, 22, 0.24), transparent 64%);
  pointer-events: none;
}

.brand-block {
  position: relative;
  z-index: 1;
  min-width: 0;
}

.brand-lockup {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-logo {
  width: 72px;
  height: 72px;
  flex: 0 0 auto;
  border: 1px solid rgba(255, 255, 255, 0.34);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 20px 44px rgba(0, 0, 0, 0.24);
  padding: 8px;
}

.brand-logo svg {
  display: block;
  width: 100%;
  height: 100%;
}

.panel {
  padding: 18px;
}

.panel-header,
.top-actions,
.hero-actions,
.links {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-actions {
  position: relative;
  z-index: 1;
}

.panel-header {
  justify-content: space-between;
  margin-bottom: 12px;
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  margin-top: 8px;
  font-size: clamp(28px, 4vw, 48px);
  line-height: 1.08;
  letter-spacing: 0;
}

h2 {
  font-size: 18px;
}

p,
.meta,
.eyebrow,
.rules {
  color: #5f7088;
}

.hero p,
.hero .meta,
.hero .eyebrow {
  color: rgba(226, 236, 249, 0.82);
}

.hero h1 {
  color: #f8fbff;
  text-shadow: 0 18px 46px rgba(0, 0, 0, 0.32);
}

.eyebrow {
  font-size: 12px;
  font-weight: 700;
}

.meta {
  margin-top: 8px;
  font-size: 13px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.field {
  display: grid;
  gap: 6px;
}

.field span {
  font-size: 13px;
  color: #40546e;
}

.wide {
  grid-column: 1 / -1;
}

input,
select,
textarea {
  width: 100%;
  border: 1px solid #ccd9ea;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  color: #1f3045;
  background: rgba(255, 255, 255, 0.92);
}

textarea {
  min-height: 190px;
  resize: vertical;
}

.script-field {
  margin-top: 8px;
}

.btn {
  border: 0;
  border-radius: 8px;
  padding: 10px 14px;
  font-weight: 800;
  cursor: pointer;
  transition: transform 0.16s ease, box-shadow 0.16s ease, background 0.16s ease;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.primary {
  background: linear-gradient(135deg, #246bfe, #0ea5e9);
  color: #fff;
  box-shadow: 0 10px 22px rgba(36, 107, 254, 0.24);
}

.accent {
  background: linear-gradient(135deg, #ff7a3d, #f59e0b);
  color: #fff;
  box-shadow: 0 10px 22px rgba(249, 115, 22, 0.22);
}

.secondary {
  background: #edf4fb;
  color: #203a5b;
  border: 1px solid rgba(116, 139, 171, 0.18);
}

.small {
  margin-top: 10px;
  padding: 8px 10px;
}

.inline {
  margin-top: 0;
}

.notice {
  border-radius: 8px;
  padding: 12px 14px;
  background: #ebf8f1;
  color: #175b34;
  border: 1px solid #bce8ce;
}

.danger {
  background: #fff1f1;
  color: #8e2525;
  border-color: #f2c2c2;
}

.quality {
  display: grid;
  gap: 5px;
  margin-top: 12px;
  border: 1px solid #f0c9a2;
  border-radius: 8px;
  padding: 12px;
  background: #fff8ee;
}

.quality.pass {
  border-color: #bce8ce;
  background: #effaf4;
}

.quality span {
  color: #5f7088;
  font-size: 13px;
}

.reference-card {
  display: grid;
  grid-template-columns: 92px 1fr;
  gap: 12px;
  align-items: center;
  border: 1px dashed #d3b28a;
  border-radius: 8px;
  padding: 12px;
  background: #fff8ee;
}

.reference-card.ready {
  border-color: #8bd3a9;
  background: #effaf4;
}

.script-preview-card,
.review-card {
  display: grid;
  gap: 10px;
  margin-top: 12px;
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  padding: 12px;
  background: #fbfdff;
}

.review-card {
  border-color: #c9d7ff;
  background: #f6f8ff;
}

.final-review {
  border-color: #bce8ce;
  background: #effaf4;
}

.script-preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.script-preview-head span {
  color: #5f7088;
  font-size: 13px;
}

.script-preview-card pre {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: inherit;
  line-height: 1.75;
  color: #1f3045;
}

.review-card ul {
  margin: 0;
  padding-left: 20px;
  color: #1f3045;
  line-height: 1.6;
}

.review-notes {
  min-height: 92px;
}

.switch-field {
  align-content: start;
}

.switch-field input[type="checkbox"] {
  width: 22px;
  height: 22px;
  padding: 0;
  accent-color: #246bfe;
}

.voice-card {
  grid-template-columns: 1fr;
}

.voice-card audio {
  display: block;
  width: 100%;
  margin: 8px 0;
}

.reference-card img {
  width: 92px;
  height: 92px;
  border-radius: 8px;
  object-fit: cover;
  background: #e6edf7;
}

.reference-card strong {
  display: block;
  margin-bottom: 4px;
}

.reference-card p,
.reference-lock p {
  margin: 0;
  color: #5f7088;
}

.wechat-entry-card {
  display: grid;
  grid-template-columns: 128px minmax(0, 1fr);
  gap: 14px;
  align-items: center;
  margin-top: 12px;
  padding: 12px;
  border: 1px solid #bce8ce;
  border-radius: 8px;
  background: #effaf4;
}

.wechat-qr-box {
  display: grid;
  place-items: center;
  width: 128px;
  aspect-ratio: 1;
  border: 1px solid #cddcf4;
  border-radius: 8px;
  background: #ffffff;
  overflow: hidden;
}

.wechat-qr-box.empty {
  border-style: dashed;
  color: #6a7890;
  font-size: 13px;
  font-weight: 800;
}

.wechat-qr-box img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.wechat-entry-copy {
  display: grid;
  gap: 6px;
}

.wechat-entry-copy p {
  margin: 0;
  color: #40546d;
  line-height: 1.6;
}

.wechat-mailbox {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.35fr);
  gap: 12px;
  min-height: 360px;
}

.mail-list {
  display: grid;
  align-content: start;
  max-height: 520px;
  overflow: auto;
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  background: #fbfdff;
}

.mail-row {
  display: grid;
  grid-template-columns: 86px 1fr;
  gap: 5px 10px;
  width: 100%;
  border: 0;
  border-bottom: 1px solid #e6edf7;
  padding: 11px 12px;
  color: #1f3045;
  text-align: left;
  background: transparent;
  cursor: pointer;
}

.mail-row:last-child {
  border-bottom: 0;
}

.mail-row:hover,
.mail-row.selected {
  background: #eef5ff;
}

.mail-row.ready {
  border-left: 3px solid #30b46c;
}

.mail-row.failed {
  border-left: 3px solid #d65f2b;
}

.mail-status {
  font-weight: 900;
}

.mail-time {
  justify-self: end;
  color: #5f7088;
  font-size: 12px;
}

.mail-summary {
  grid-column: 1 / -1;
  overflow: hidden;
  color: #40546d;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mail-detail {
  display: grid;
  align-content: start;
  gap: 12px;
  min-width: 0;
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  padding: 14px;
  background: #fbfdff;
}

.mail-detail.ready {
  border-color: #bce8ce;
  background: #effaf4;
}

.mail-detail.failed {
  border-color: #f0b8a8;
  background: #fff8f5;
}

.mail-detail p {
  margin: 0;
  color: #1f3045;
  line-height: 1.7;
  white-space: pre-wrap;
}

.callback-diagnostics {
  display: grid;
  gap: 10px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #e0e8f4;
}

.callback-list {
  display: grid;
  overflow: hidden;
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  background: #fbfdff;
}

.diagnostics-head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: flex-end;
}

.callback-row {
  display: grid;
  grid-template-columns: 150px 90px 118px minmax(160px, 1fr);
  gap: 8px;
  align-items: center;
  padding: 9px 10px;
  border-bottom: 1px solid #e6edf7;
  color: #40546d;
}

.callback-row:last-child {
  border-bottom: 0;
}

.callback-row.queued_material {
  background: #effaf4;
}

.callback-row.ignored {
  background: #fffaf0;
}

.callback-row.rejected {
  background: #fff1f1;
}

.callback-time,
.callback-type,
.callback-action {
  font-size: 12px;
  font-weight: 800;
}

.callback-action {
  color: #1f3045;
}

.callback-reason,
.callback-preview {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.callback-preview {
  grid-column: 1 / -1;
  color: #5f7088;
}

.generated-copy {
  display: grid;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.72);
}

.generated-copy pre {
  margin: 0;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font: inherit;
  color: #1f3045;
}

.material-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-start;
}

.danger-action {
  color: #9c3726;
}

.notebooklm-box {
  display: grid;
  gap: 6px;
  padding: 10px;
  border: 1px solid #cddcf4;
  border-radius: 8px;
  background: #f6f9ff;
}

.notebooklm-box span {
  color: #5f7088;
}

.notebooklm-box a {
  color: #246bfe;
  font-weight: 800;
}

.notebooklm-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.trend-search-box {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  background: #f8fbff;
}

.trend-search-box label {
  font-weight: 800;
  color: #20324a;
}

.trend-search-box span {
  color: #6a7890;
  line-height: 1.5;
}

.trend-search-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}

.trend-search-row input {
  width: 100%;
  min-width: 0;
  border: 1px solid #cfdced;
  border-radius: 8px;
  padding: 11px 12px;
  font: inherit;
  color: #20324a;
  background: #ffffff;
}

.trend-search-row input:focus {
  outline: 2px solid rgba(36, 107, 254, 0.18);
  border-color: #7aa3ff;
}

.trend-card {
  display: grid;
  gap: 12px;
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  padding: 12px;
  background: #fbfdff;
}

.trend-card p {
  margin: 0;
  color: #5f7088;
}

.trend-card ul {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.trend-card li {
  display: grid;
  gap: 3px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e6edf7;
}

.trend-card li:last-child {
  border-bottom: 0;
}

.trend-card a {
  color: #246bfe;
  font-weight: 800;
}

.trend-card li span,
.trend-angles span {
  color: #5f7088;
  line-height: 1.5;
}

.trend-angles {
  display: grid;
  gap: 6px;
  padding: 10px;
  border-radius: 8px;
  background: #fff8ee;
}

.storyboard {
  margin-top: 14px;
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  overflow: hidden;
}

.storyboard-head,
.shot-row {
  display: grid;
  grid-template-columns: 42px 150px 120px 1fr;
  gap: 10px;
  align-items: center;
  padding: 9px 12px;
  border-bottom: 1px solid #e6edf7;
}

.storyboard-head {
  display: block;
  font-weight: 800;
  background: #f4f7fb;
}

.shot-row:last-child {
  border-bottom: 0;
}

.shot-row em {
  font-style: normal;
  color: #d65f2b;
}

.rules {
  margin-top: 12px;
  font-size: 12px;
  line-height: 1.6;
}

.stack {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
}

.jobs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.job-card {
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  padding: 12px;
  background: #fbfdff;
}

.job-card.failed {
  border-color: #f0b8a8;
  background: #fff8f5;
}

.failed-jobs {
  margin-bottom: 12px;
}

.error-text {
  color: #9c3726;
  font-size: 13px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.job-title {
  font-weight: 800;
}

.progress-track {
  height: 8px;
  margin-top: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: #d9e3f2;
}

.progress-fill {
  height: 100%;
  background: #246bfe;
}

.links {
  margin-top: 10px;
}

.links a {
  color: #246bfe;
  font-weight: 800;
}

.video-preview {
  width: 100%;
  margin-top: 10px;
  border-radius: 8px;
  background: #101820;
}

.publish-actions {
  display: flex;
  justify-content: flex-start;
}

.publish-card {
  display: grid;
  gap: 10px;
  margin-top: 10px;
  border: 1px solid #ffd0a8;
  border-radius: 8px;
  padding: 12px;
  background: #fff8ee;
}

.publish-card-head,
.publish-buttons {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: space-between;
}

.publish-card-head span,
.publish-card ol {
  color: #6b5b4a;
  font-size: 13px;
}

.caption-box {
  min-height: 82px;
}

.publish-card ol {
  margin: 0;
  padding-left: 18px;
  line-height: 1.55;
}

.floating-generate {
  position: fixed;
  right: 18px;
  bottom: 18px;
  border: 0;
  border-radius: 999px;
  padding: 14px 18px;
  font-weight: 900;
  color: #fff;
  background: #ff7a3d;
  box-shadow: 0 12px 28px rgba(255, 122, 61, 0.32);
}

.studio-page .app-shell {
  width: 100%;
  padding-top: 0;
}

.studio-page {
  padding-left: 0;
}

.studio-page.module-mode {
  padding-left: 220px;
}

.studio-header {
  min-height: 52px;
  padding: 0 32px;
  grid-template-columns: 1fr auto;
}

.brand-mark {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  font-size: 10px;
}

.brand-logo-img {
  width: 28px;
  height: 28px;
  border-radius: 8px;
}

.brand-mini strong {
  font-size: 14px;
}

.brand-mini small {
  font-size: 10px;
}

.header-cta {
  min-height: 32px;
  padding: 0 16px;
}

.landing-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(420px, 0.92fr);
  align-items: center;
  gap: 72px;
  min-height: 480px;
  padding: 44px 32px;
  border-bottom: 1px solid rgba(142, 171, 205, 0.14);
  background-image:
    linear-gradient(rgba(0, 213, 232, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 213, 232, 0.05) 1px, transparent 1px);
  background-size: 36px 36px;
}

.version-pill {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  margin-bottom: 28px;
  padding: 0 12px;
  border: 1px solid rgba(0, 213, 232, 0.24);
  border-radius: 999px;
  background: rgba(0, 213, 232, 0.08);
  color: #c6f8ff;
  font-size: 12px;
}

.landing-copy h1 {
  max-width: 600px;
  margin: 0;
  color: #fff;
  font-size: clamp(42px, 5vw, 62px);
  line-height: 1.08;
}

.landing-copy h1 span {
  color: #00d5e8;
}

.landing-copy p {
  max-width: 720px;
  margin: 22px 0 0;
  color: #a9bfda;
  font-size: 18px;
  line-height: 1.7;
}

.landing-actions,
.hero-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 28px;
}

.hero-stats {
  gap: 46px;
  margin-top: 42px;
}

.hero-stats strong {
  display: grid;
  gap: 8px;
  color: #fff;
  font-size: 26px;
}

.hero-stats small {
  color: #a9bfda;
  font-size: 13px;
  font-weight: 500;
}

.hero-console {
  display: grid;
  gap: 14px;
  width: min(560px, 100%);
  justify-self: end;
  padding: 18px;
  border: 1px solid rgba(142, 171, 205, 0.22);
  border-radius: 18px;
  background: #0d1b2a;
  box-shadow: 0 0 60px rgba(0, 213, 232, 0.12);
}

.console-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #8ba1bb;
  font-size: 12px;
}

.console-bar span {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #ff7a3d;
}

.console-bar span:nth-child(2) {
  background: #00d5e8;
}

.console-bar span:nth-child(3) {
  background: #38c172;
}

.console-bar small {
  margin-left: 12px;
}

.signal-list,
.mini-widget {
  border: 1px solid rgba(142, 171, 205, 0.18);
  border-radius: 14px;
  background: rgba(9, 21, 34, 0.78);
}

.signal-list {
  display: grid;
  gap: 12px;
  padding: 16px;
}

.signal-list div,
.signal-list p {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin: 0;
}

.signal-list div span {
  color: #dcecff;
  font-weight: 800;
}

.signal-list strong {
  color: #dcecff;
  font-size: 13px;
}

.signal-list small,
.mini-widget small {
  color: #8ba1bb;
  font-size: 12px;
}

.console-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.mini-widget {
  display: grid;
  gap: 12px;
  padding: 16px;
}

.mini-widget strong {
  color: #e9f5ff;
}

.bar-chart {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  align-items: end;
  gap: 6px;
  height: 42px;
}

.bar-chart span {
  border-radius: 8px 8px 4px 4px;
  background: #12b9cd;
}

.bar-chart span:nth-child(1) { height: 34%; }
.bar-chart span:nth-child(2) { height: 56%; }
.bar-chart span:nth-child(3) { height: 42%; }
.bar-chart span:nth-child(4) { height: 68%; }
.bar-chart span:nth-child(5) { height: 52%; }
.bar-chart span:nth-child(6) { height: 82%; }
.bar-chart span:nth-child(7) { height: 66%; }

.core-section,
.workflow-section,
.metric-grid,
.launch-panel {
  margin-top: 0;
}

.core-section {
  padding: 76px 32px 78px;
  border-bottom: 1px solid rgba(142, 171, 205, 0.14);
}

.core-section h2,
.workflow-section h2 {
  margin: 0;
  color: #fff;
  font-size: clamp(30px, 4vw, 42px);
  line-height: 1.18;
}

.core-section > p {
  max-width: 760px;
  margin: 14px 0 0;
  color: #a9bfda;
  line-height: 1.7;
}

.core-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
  margin-top: 44px;
}

.core-card {
  position: relative;
  display: grid;
  min-height: 320px;
  padding: 28px;
  border: 1px solid rgba(142, 171, 205, 0.2);
  border-radius: 14px;
  background: #0d1b2a;
  color: #f7fbff;
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.core-card:hover {
  transform: translateY(-3px);
  border-color: rgba(0, 213, 232, 0.5);
  background: #102235;
}

.core-card em {
  position: absolute;
  top: 30px;
  right: 28px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.12);
  color: #40d990;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.core-card em.warm {
  background: rgba(255, 122, 61, 0.14);
  color: #ff9b68;
}

.core-card > small {
  margin-top: 8px;
  color: #8ba1bb;
}

.core-card > strong {
  margin-top: 10px;
  font-size: 24px;
}

.core-card p {
  min-height: 72px;
  margin: 12px 0 0;
  color: #a9bfda;
  line-height: 1.7;
}

.core-card ul {
  display: grid;
  gap: 10px;
  margin: 24px 0 0;
  padding: 20px 0 0;
  border-top: 1px solid rgba(142, 171, 205, 0.14);
  color: #d8ebff;
  list-style: none;
}

.core-card li::before {
  content: "";
  display: inline-block;
  width: 5px;
  height: 5px;
  margin-right: 10px;
  border-radius: 999px;
  background: #00d5e8;
  vertical-align: middle;
}

.module-link {
  align-self: end;
  margin-top: 28px;
  color: #00d5e8;
  font-weight: 800;
}

.workflow-section {
  padding: 76px 32px 72px;
  border-bottom: 1px solid rgba(142, 171, 205, 0.14);
}

.workflow-section .dashboard-hero {
  min-height: auto;
  padding: 0 0 42px;
}

.workflow-section .workflow-grid {
  padding-bottom: 0;
}

.metric-grid {
  padding: 70px 32px;
}

.launch-panel {
  margin: 78px auto;
}

.studio-page .panel,
.studio-page .job-card,
.studio-page .question-card,
.studio-page .trend-card,
.studio-page .script-preview-card,
.studio-page .review-card,
.studio-page .interview-panel,
.studio-page .interview-turn,
.studio-page .mail-list,
.studio-page .mail-detail,
.studio-page .reference-card,
.studio-page .wechat-entry-card,
.studio-page .trend-search-box,
.studio-page .notebooklm-box,
.studio-page .callback-list,
.studio-page .publish-card,
.studio-page .quality {
  border-color: rgba(142, 171, 205, 0.18);
  background: #0d1b2a;
  color: #f7fbff;
  box-shadow: none;
}

.studio-page p,
.studio-page .meta,
.studio-page .field span,
.studio-page .trend-card p,
.studio-page .trend-card li span,
.studio-page .trend-angles span,
.studio-page .mail-detail p,
.studio-page .reference-card p,
.studio-page .review-card p,
.studio-page .quality span,
.studio-page .quality p,
.studio-page .publish-card-head span,
.studio-page .publish-card ol {
  color: #a9bfda;
}

.studio-page input,
.studio-page select,
.studio-page textarea,
.studio-page .interview-input,
.studio-page .trend-search-row input {
  border-color: rgba(142, 171, 205, 0.22);
  background: #091522;
  color: #f7fbff;
}

.studio-page input::placeholder,
.studio-page textarea::placeholder {
  color: #6f859f;
}

.studio-page .secondary {
  border: 1px solid rgba(142, 171, 205, 0.22);
  background: rgba(142, 171, 205, 0.08);
  color: #dcecff;
}

.studio-page .primary {
  background: #00aeca;
  color: #06111c;
  box-shadow: none;
}

.studio-page .accent {
  background: #ff7a3d;
  color: #06111c;
  box-shadow: none;
}

.studio-page .eyebrow,
.studio-page .question-footer span,
.studio-page .upload-audio-label {
  border-color: rgba(0, 213, 232, 0.18);
  background: rgba(0, 213, 232, 0.1);
  color: #bdf7ff;
}

.studio-page .question-card h3,
.studio-page .script-preview-card pre,
.studio-page .generated-copy pre,
.studio-page .job-title,
.studio-page .panel-header h2,
.studio-page .trend-card a,
.studio-page .links a {
  color: #f7fbff;
}

.studio-page .question-number,
.studio-page .progress-fill {
  background: #00d5e8;
  color: #06111c;
}

.studio-page .mail-row {
  border-bottom-color: rgba(142, 171, 205, 0.14);
  color: #dcecff;
}

.studio-page .mail-row:hover,
.studio-page .mail-row.selected {
  background: rgba(0, 213, 232, 0.08);
}

.studio-page .notice {
  border: 1px solid rgba(0, 213, 232, 0.18);
  background: rgba(0, 213, 232, 0.1);
  color: #bdf7ff;
}

.studio-page .notice.danger,
.studio-page .error-text,
.studio-page .danger-action {
  color: #ff9b68;
}

.module-hero,
.tabs,
.studio-page > .app-shell > div:not(.dashboard),
.studio-page > .app-shell > .panel {
  width: min(1320px, calc(100vw - 40px));
  margin-left: auto;
  margin-right: auto;
}

.module-hero {
  margin-top: 28px;
}

.stock-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
  margin-top: 20px;
}

.stock-feature-card,
.stock-placeholder {
  border: 1px solid rgba(142, 171, 205, 0.18);
  border-radius: 14px;
  background: rgba(9, 21, 34, 0.64);
  padding: 22px;
}

.stock-feature-card {
  display: grid;
  align-content: start;
  min-height: 190px;
}

.stock-feature-card strong,
.stock-placeholder strong {
  color: #f7fbff;
  font-size: 18px;
}

.stock-feature-card p,
.stock-placeholder p {
  margin-top: 12px;
  color: #a9bfda;
  line-height: 1.7;
}

.stock-placeholder {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.stock-workbench,
.stock-dashboard-grid {
  display: grid;
  gap: 18px;
  margin-top: 18px;
}

.stock-workbench {
  grid-template-columns: minmax(0, 1.55fr) minmax(300px, 0.8fr);
}

.stock-dashboard-grid {
  grid-template-columns: minmax(300px, 0.92fr) minmax(0, 1.35fr);
}

.stock-control-panel,
.stock-market-card,
.stock-list-panel,
.stock-analysis-panel,
.stock-history-panel,
.stock-skill-panel {
  border: 1px solid rgba(142, 171, 205, 0.18);
  border-radius: 8px;
  background: rgba(9, 21, 34, 0.64);
  padding: 16px;
}

.stock-question {
  width: 100%;
  margin-top: 12px;
}

.stock-actions,
.stock-row-actions,
.stock-section-head {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}

.stock-actions {
  justify-content: flex-start;
  margin-top: 12px;
}

.stock-search-results,
.market-index-list,
.stock-history-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.stock-search-results button,
.stock-history-list button {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 4px 12px;
  width: 100%;
  border: 1px solid rgba(142, 171, 205, 0.18);
  border-radius: 8px;
  padding: 10px;
  color: #dcecff;
  text-align: left;
  background: rgba(142, 171, 205, 0.08);
  cursor: pointer;
}

.stock-search-results button span,
.stock-history-list button span,
.stock-history-list button em {
  color: #a9bfda;
  font-size: 12px;
  font-style: normal;
}

.stock-history-list button strong {
  color: #f7fbff;
}

.market-mood {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-top: 12px;
  padding: 14px;
  border-radius: 8px;
  background: rgba(0, 213, 232, 0.08);
}

.market-mood span {
  color: #bdf7ff;
  font-weight: 800;
}

.market-mood strong {
  font-size: 28px;
}

.market-index-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 10px;
  align-items: center;
  padding: 9px 0;
  border-bottom: 1px solid rgba(142, 171, 205, 0.12);
}

.market-index-row:last-child {
  border-bottom: 0;
}

.market-index-row span,
.market-index-row em {
  color: #a9bfda;
  font-style: normal;
}

.stock-empty {
  margin-top: 12px;
  border: 1px dashed rgba(142, 171, 205, 0.24);
  border-radius: 8px;
  padding: 16px;
  color: #a9bfda;
  background: rgba(142, 171, 205, 0.05);
}

.stock-watch-card {
  display: grid;
  gap: 10px;
  margin-top: 12px;
  border: 1px solid rgba(142, 171, 205, 0.16);
  border-radius: 8px;
  padding: 12px;
  background: rgba(13, 27, 42, 0.78);
}

.stock-watch-main,
.stock-mini-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}

.stock-watch-main strong,
.stock-section-head strong {
  color: #f7fbff;
}

.stock-watch-main span,
.stock-mini-meta span,
.stock-watch-card p,
.stock-analysis-result small {
  color: #a9bfda;
}

.stock-price {
  display: grid;
  gap: 2px;
  justify-items: end;
}

.stock-price em,
.market-index-row em,
.stock-mini-meta .up,
.stock-mini-meta .down,
.market-mood .up,
.market-mood .down {
  font-style: normal;
  font-weight: 900;
}

.up {
  color: #ff7a3d !important;
}

.down {
  color: #40d990 !important;
}

.stock-alerts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.stock-alerts span {
  border-radius: 999px;
  padding: 4px 8px;
  color: #ffcfb7;
  background: rgba(255, 122, 61, 0.12);
  font-size: 12px;
  font-weight: 800;
}

.stock-analysis-result {
  display: grid;
  gap: 14px;
  margin-top: 12px;
}

.stock-score-line {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.stock-score-line span {
  color: #a9bfda;
}

.stock-score-line strong {
  color: #00d5e8;
  font-size: 28px;
}

.stock-score-line em {
  border-radius: 999px;
  padding: 5px 10px;
  color: #06111c;
  background: #00d5e8;
  font-style: normal;
  font-weight: 900;
}

.stock-clear-conclusion {
  display: grid;
  gap: 8px;
  border: 1px solid rgba(0, 213, 232, 0.22);
  border-radius: 8px;
  padding: 14px;
  background: rgba(0, 213, 232, 0.09);
}

.stock-clear-conclusion strong {
  color: #f7fbff;
  font-size: 18px;
}

.stock-clear-conclusion p {
  margin: 0;
  color: #dcecff;
  line-height: 1.6;
}

.stock-clear-conclusion span {
  color: #bdf7ff;
  font-weight: 800;
}

.stock-target-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.stock-target-grid div {
  display: grid;
  gap: 6px;
  border: 1px solid rgba(255, 122, 61, 0.24);
  border-radius: 8px;
  padding: 12px;
  background: rgba(255, 122, 61, 0.08);
}

.stock-target-grid span,
.stock-target-grid small {
  color: #a9bfda;
}

.stock-target-grid strong {
  color: #ffb088;
  font-size: 26px;
}

.stock-target-grid em {
  color: #ff7a3d;
  font-style: normal;
  font-weight: 900;
}

.stock-sparkline {
  width: 100%;
  height: 96px;
  border-radius: 8px;
  padding: 8px;
  background: rgba(0, 213, 232, 0.06);
}

.indicator-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.indicator-grid span {
  display: grid;
  gap: 4px;
  border: 1px solid rgba(142, 171, 205, 0.16);
  border-radius: 8px;
  padding: 10px;
  color: #a9bfda;
  background: rgba(142, 171, 205, 0.06);
}

.indicator-grid strong {
  color: #f7fbff;
}

.stock-signal-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.stock-signal-columns > div {
  border: 1px solid rgba(142, 171, 205, 0.16);
  border-radius: 8px;
  padding: 12px;
  background: rgba(142, 171, 205, 0.05);
}

.stock-signal-columns p {
  margin: 8px 0 0;
  color: #a9bfda;
  line-height: 1.55;
}

.stock-report {
  max-height: 360px;
  overflow: auto;
  margin: 0;
  border: 1px solid rgba(142, 171, 205, 0.16);
  border-radius: 8px;
  padding: 12px;
  color: #dcecff;
  white-space: pre-wrap;
  word-break: break-word;
  background: #091522;
}

.stock-history-panel {
  margin-top: 18px;
}

.stock-skill-panel {
  display: grid;
  gap: 14px;
  margin-top: 18px;
}

.stock-skill-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.stock-skill-card {
  display: grid;
  gap: 8px;
  min-height: 116px;
  border: 1px solid rgba(142, 171, 205, 0.18);
  border-radius: 8px;
  padding: 12px;
  color: #dcecff;
  text-align: left;
  background: rgba(142, 171, 205, 0.06);
  cursor: pointer;
}

.stock-skill-card:hover,
.stock-skill-card.active {
  border-color: rgba(0, 213, 232, 0.48);
  background: rgba(0, 213, 232, 0.1);
}

.stock-skill-card strong {
  color: #f7fbff;
}

.stock-skill-card span,
.stock-skill-result small,
.indicator-grid small {
  color: #a9bfda;
  line-height: 1.5;
}

.stock-skill-result {
  display: grid;
  gap: 12px;
}

@media (max-width: 760px) {
  .studio-page {
    padding-left: 0;
    padding-top: 0;
  }

  .studio-page.module-mode {
    padding-left: 0;
    padding-top: 72px;
  }

  .studio-sidebar {
    inset: 0 0 auto 0;
    grid-template-columns: auto 1fr;
    grid-template-rows: 1fr;
    align-items: center;
    width: auto;
    height: 72px;
    padding: 10px 12px;
    border-right: 0;
    border-bottom: 1px solid rgba(142, 171, 205, 0.16);
  }

  .sidebar-brand {
    width: auto;
    min-width: 124px;
  }

  .sidebar-nav {
    display: flex;
    overflow-x: auto;
    gap: 8px;
    margin-top: 0;
    padding-bottom: 2px;
  }

  .sidebar-nav button {
    flex: 0 0 auto;
    min-height: 40px;
    padding: 0 10px;
  }

  .sidebar-footer {
    display: none;
  }

  .studio-header {
    grid-template-columns: 1fr;
    gap: 12px;
    padding: 14px 16px;
    position: static;
  }

  .studio-nav,
  .header-actions {
    justify-self: start;
  }

  .landing-hero,
  .core-grid,
  .workflow-grid,
  .metric-grid,
  .stock-grid,
  .stock-workbench,
  .stock-dashboard-grid,
  .stock-signal-columns,
  .indicator-grid,
  .stock-target-grid,
  .stock-skill-grid,
  .console-grid {
    grid-template-columns: 1fr;
  }

  .landing-hero {
    min-height: auto;
    gap: 32px;
    padding: 48px 0;
  }

  .hero-console {
    min-width: 0;
  }

  .dashboard-hero,
  .module-hero,
  .studio-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .core-section,
  .workflow-section {
    padding: 56px 0;
  }

  .core-card {
    min-height: auto;
  }

  .hero {
    align-items: start;
    flex-direction: column;
  }

  .field-grid,
  .wechat-mailbox,
  .wechat-entry-card,
  .storyboard-head,
  .shot-row {
    grid-template-columns: 1fr;
  }

  .floating-generate {
    right: 12px;
    bottom: 12px;
  }
}
</style>
