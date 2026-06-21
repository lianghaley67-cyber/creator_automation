<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, provide, reactive, ref } from "vue";
import { coreModules, modulePageMeta as getModulePageMeta, sidebarModules, workflowCards } from "./modules/navigation.js";
import {
  jobProgress,
  reviewLines,
  xiaohongshuNextStep,
  xiaohongshuStatusLabel,
} from "./pages/MaterialStudioPage.logic.js";
import MaterialStudioPage from "./pages/MaterialStudioPage.vue";
import OverviewPage from "./pages/OverviewPage.vue";
import {
  WORKFLOW_REVIEW_OPTIONS,
  buildContentWorkflowState,
  buildTrendNextAction,
  buildTrendQuestions,
  reviewDistributionDraft,
} from "./pages/RealtimeInfoPage.logic.js";
import RealtimeInfoPage from "./pages/RealtimeInfoPage.vue";
import {
  formatStockNumber,
  stockChangeClass,
  stockDecisionGuide as buildStockDecisionGuide,
  stockKlinePoints,
  stockReadableReport as buildStockReadableReport,
} from "./pages/StockAnalysisPage.logic.js";
import StockAnalysisPage from "./pages/StockAnalysisPage.vue";
import { normalizeErrorMessage } from "./utils/errors.js";

const configuredApiBase = (import.meta.env.VITE_API_BASE || "").trim().replace(/\/$/, "");
const browserApiBase = window.location.origin && window.location.protocol.startsWith("http")
  ? window.location.origin.replace(/\/$/, "")
  : "";
const isLocalBrowser = ["127.0.0.1", "localhost", "::1"].includes(window.location.hostname);
const apiCandidates = Array.from(
  new Set(
    [
      configuredApiBase,
      browserApiBase,
      ...(isLocalBrowser
        ? [
            "http://127.0.0.1:8000",
            "http://127.0.0.1:8011",
            "http://localhost:8000",
            "http://localhost:8011"
          ]
        : [])
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
  const directUrl = String(entry.qr_image_url || "");
  if (directUrl.startsWith("https://") || directUrl.startsWith("/")) return directUrl;
  return entry.qr_proxy_url || directUrl || "";
});
const selectedWechatMaterialId = ref("");
const aiTrends = ref([]);
const notebookLmPackage = ref(null);
const trendSearchQuery = ref("");
const materialTextInput = ref("");
const materialVoiceNote = ref("");
const materialRecording = ref(false);
let materialRecorder = null;
let materialRecorderChunks = [];
let materialRecorderStream = null;
const deletingJobId = ref("");
const previewStoryboard = ref([]);
const hardRules = ref([]);
const quality = ref(null);
const activeTab = ref("overview"); // overview | trends | materials | stocks
const trendQuestions = ref([]);
const trendScripts = ref({});
const trendDistributionDraft = ref(null);
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
let trendHighlightTimer = null;

// ===== 新增：AI摘要 + 讨论 + Skill选择 =====
const presetTopics = ref([]);
const trendAiSummary = ref(null); // AI摘要结果
const trendChatMessages = ref([]); // [{role, content}]
const trendChatInput = ref("");
const trendContentDirection = ref("");
const trendSelectedReviewSkill = ref("jianghushuo");
const trendWorkflowReview = ref(null);
const channelSkillsList = ref([]); // 全量 skill 列表
const selectedWechatSkill = ref(""); // 用户选择的公众号 skill
const selectedXhsSkill = ref(""); // 用户选择的小红书 skill
const wechatSkillManuallySelected = ref(false);
const xhsSkillManuallySelected = ref(false);
const skillSelectorVisible = ref(false); // 是否展开 skill 选择面板
const trendDiscussionOpen = ref(false); // 多轮讨论是否展开
const trendFreshHighlight = ref(false); // 资讯刷新后的短暂高亮
const trendDistributionView = ref("xiaohongshu"); // xiaohongshu | wechat
const busy_trendSummarize = ref(false);
const busy_trendChat = ref(false);
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
const distributionDrafts = reactive({});
const materialDistributionDrafts = reactive({});
const distributionTasks = ref([]);
const jobsLoaded = ref(false);
const wechatMaterialsLoaded = ref(false);
const distributionTasksLoaded = ref(false);
const xiaohongshuPublishUrls = reactive({});
const xiaohongshuServerSession = ref(null);
const xiaohongshuPhone = ref("");
const xiaohongshuSmsCode = ref("");
const xiaohongshuDragStart = ref(null);
const xiaohongshuDragLine = ref(null);
let xiaohongshuFrameTimer = null;
const wechatDraftErrors = reactive({});
const audioPreviews = reactive({});
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
  risk_level: "balanced",
  holding_period: "swing",
  max_position_percent: "20",
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
  trendDistribution: false,
  materialIntake: false,
  materialVoice: false,
  notebooklm: false,
  archive: "",
  cleanup: false,
  uploadReference: false,
  uploadVoice: false,
  previewScript: false,
  reviseScript: false,
  generate: false,
  publish: "",
  audio: "",
  distribution: "",
  xiaohongshu: "",
  xiaohongshuSession: false,
  xiaohongshuSms: false,
  xiaohongshuVerify: false,
  xiaohongshuDrag: false,
  xiaohongshuDirectPublish: "",
  wechatDraft: "",
  wechatCover: false,
  stockRefresh: false,
  stockSearch: false,
  stockSave: false,
  stockAnalyze: false,
  stockMarket: false,
  stockHistory: false,
  stockSkills: false,
  stockSkillRun: false,
  trendSummarize: false,
  trendChat: false,
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

async function pingApi(base) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 6000);
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

let verifiedApiBase = "";
let apiResolutionPromise = null;

async function resolveApiBase() {
  if (verifiedApiBase) return verifiedApiBase;
  if (apiResolutionPromise) return apiResolutionPromise;
  busy.connect = true;
  apiResolutionPromise = (async () => {
    for (const candidate of [activeApiBase.value, ...apiCandidates]) {
      if (!candidate) continue;
      try {
        await pingApi(candidate);
        activeApiBase.value = candidate;
        verifiedApiBase = candidate;
        return candidate;
      } catch {
        // Try the next API candidate.
      }
    }
    throw new Error(
      isLocalBrowser
        ? "本地后端未连接，请确认 8000 端口服务已启动。"
        : "线上服务暂时不可用，请刷新页面；如果仍失败，请检查服务器容器和 Nginx。"
    );
  })();
  try {
    return await apiResolutionPromise;
  } finally {
    apiResolutionPromise = null;
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
        if (response.status === 504) {
          message = "服务器这次处理超时了，请稍后重试。页面和已有数据不会丢失。";
        } else if (response.status === 502) {
          message = "服务器正在重启或暂时不可用，请等待几秒后重试。";
        } else if (text && !/<html[\s>]/i.test(text)) {
          message = text;
        } else {
          message = `服务器请求失败（HTTP ${response.status}）。`;
        }
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

async function acceptCreatedMaterial(material, successMessage) {
  await refreshWechatMaterials();
  if (material?.id) selectedWechatMaterialId.value = material.id;
  materialTextInput.value = "";
  setNotice(successMessage);
}

async function submitTextMaterial() {
  const text = materialTextInput.value.trim();
  if (!text) {
    setError("请先输入一段文字素材。");
    return;
  }
  busy.materialIntake = true;
  try {
    const result = await requestApi(
      "/api/materials/text",
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({
          text,
          source_type: "web_text",
          content_mode: kidsForm.content_mode,
          script_provider: kidsForm.script_provider,
          auto_preview: true
        })
      },
      240000
    );
    await acceptCreatedMaterial(result.material, "文字素材已进入收件箱，并开始生成文案。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "文字素材提交失败。"));
  } finally {
    busy.materialIntake = false;
  }
}

async function uploadMaterialAudioFile(file, sourceType = "web_audio") {
  if (!file) return;
  busy.materialVoice = true;
  materialVoiceNote.value = "正在上传并转成文字...";
  try {
    const form = new FormData();
    form.append("file", file, file.name || "material.webm");
    form.append("content_mode", kidsForm.content_mode);
    form.append("script_provider", kidsForm.script_provider);
    form.append("source_type", sourceType);
    const result = await requestApi("/api/materials/audio", { method: "POST", body: form }, 240000);
    materialVoiceNote.value = result.transcribe_note || "语音已转成文字。";
    await acceptCreatedMaterial(result.material, "语音素材已转成文字并进入收件箱。");
  } catch (error) {
    materialVoiceNote.value = "";
    setError(normalizeErrorMessage(error, "语音素材处理失败。"));
  } finally {
    busy.materialVoice = false;
  }
}

async function uploadMaterialAudio(event) {
  const file = event?.target?.files?.[0];
  await uploadMaterialAudioFile(file, "web_audio_upload");
  if (event?.target) event.target.value = "";
}

async function startMaterialRecording() {
  try {
    materialRecorderStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    materialRecorderChunks = [];
    materialRecorder = new MediaRecorder(materialRecorderStream);
    materialRecorder.ondataavailable = (event) => {
      if (event.data?.size) materialRecorderChunks.push(event.data);
    };
    materialRecorder.onstop = async () => {
      const blob = new Blob(materialRecorderChunks, { type: materialRecorder?.mimeType || "audio/webm" });
      materialRecorderStream?.getTracks().forEach((track) => track.stop());
      materialRecorderStream = null;
      materialRecording.value = false;
      const file = new File([blob], "web_recording.webm", { type: blob.type || "audio/webm" });
      await uploadMaterialAudioFile(file, "web_microphone");
    };
    materialRecorder.start();
    materialRecording.value = true;
    materialVoiceNote.value = "正在录音，讲完后点击“停止并提交”。";
  } catch (error) {
    setError(normalizeErrorMessage(error, "无法使用麦克风，请检查浏览器权限或改用音频上传。"));
  }
}

function stopMaterialRecording() {
  if (materialRecorder?.state === "recording") materialRecorder.stop();
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
    jobsLoaded.value = true;
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
    wechatMaterialsLoaded.value = true;
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
    // 重置 AI 摘要和讨论（新的资讯进来后需重新生成）
    if (force) {
      trendAiSummary.value = null;
      trendChatMessages.value = [];
      trendDistributionDraft.value = null;
      trendWorkflowReview.value = null;
    }
    // 自动生成6个问题
    if (aiTrends.value.length > 0) {
      generateTrendQuestions(aiTrends.value[0]);
      trendFreshHighlight.value = true;
      if (trendHighlightTimer) window.clearTimeout(trendHighlightTimer);
      trendHighlightTimer = window.setTimeout(() => {
        trendFreshHighlight.value = false;
      }, 1800);
    }
    setNotice(force ? (query ? `已按"${query}"抓取 AI 资讯。` : "AI 最新资讯已刷新。") : notice.value);
  } catch (error) {
    setError(normalizeErrorMessage(error, "刷新 AI 资讯失败。"));
  } finally {
    busy.refreshTrends = false;
  }
}

function generateTrendQuestions(trend) {
  trendQuestions.value = buildTrendQuestions(trend);
}

async function refreshDistributionTasks() {
  try {
    const result = await requestApi("/api/distribution/tasks?limit=20");
    distributionTasks.value = Array.isArray(result?.items) ? result.items : [];
    distributionTasksLoaded.value = true;
  } catch (error) {
    setError(normalizeErrorMessage(error, "刷新平台草稿箱失败。"));
  }
}

async function prepareTrendDistribution(preferGeneratedScript = false, destination = "all", sourceItem = null) {
  const trend = aiTrends.value[0];
  if (!trend?.id) {
    setError("请先获取实时资讯。");
    return;
  }
  const itemTitle = String(sourceItem?.title || "").trim();
  const itemSummary = String(sourceItem?.summary || "").trim();
  const itemUrl = String(sourceItem?.url || "").trim();
  const generated = selectedTrendQuestion.value
    ? trendScripts.value[selectedTrendQuestion.value]
    : null;
  const itemScript = sourceItem
    ? [itemTitle, itemSummary, itemUrl ? `官方/原文链接：${itemUrl}` : ""].filter(Boolean).join("\n\n")
    : "";
  const baseScript = sourceItem ? itemScript : (preferGeneratedScript ? String(generated?.script || "").trim() : "");
  const direction = trendContentDirection.value.trim();
  const script = [
    direction
      ? `【我的内容方向】\n${direction}\n\n请生成内容时优先服务这个方向：用大白话讲清楚，适合对 AI 感兴趣的普通人和知识成长女性阅读；少空话，多给真实判断、操作步骤、官方链接、风险边界和可复用方法。`
      : "",
    baseScript,
  ].filter(Boolean).join("\n\n");
  if (preferGeneratedScript && !baseScript) {
    setError("请先基于追问生成文案，再推荐到小红书。");
    return;
  }
  if (sourceItem) {
    trendDistributionView.value = destination === "wechat" ? "wechat" : "xiaohongshu";
  }
  busy.trendDistribution = true;
  try {
    const result = await requestApi(
      `/api/ai-trends/${trend.id}/distribution`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({
          script,
          question: sourceItem ? itemTitle : (preferGeneratedScript ? selectedTrendQuestion.value : ""),
          title: sourceItem ? itemTitle : (preferGeneratedScript ? selectedTrendQuestion.value : trend.title || ""),
          wechat_skill_id: selectedWechatSkill.value || "",
          xiaohongshu_skill_id: selectedXhsSkill.value || "",
          hashtags: trendAiSummary.value?.suggested_hashtags || [],
        })
      },
      30000
    );
    trendDistributionDraft.value = result;
    trendWorkflowReview.value = null;
    setNotice(
      sourceItem
        ? `已用「${itemTitle || "这条资讯"}」生成公众号和小红书发布包。`
        : destination === "xiaohongshu"
        ? "已生成小红书推荐方案：标题、封面短句、正文、话题和发布步骤都准备好了。"
        : "实时资讯已整理成公众号文章和小红书发布包。"
    );
  } catch (error) {
    setError(normalizeErrorMessage(error, "实时资讯分发准备失败。"));
  } finally {
    busy.trendDistribution = false;
  }
}

async function createTrendWechatDraft() {
  await submitWechatDraftTask(trendDistributionDraft.value, (result) => {
    trendDistributionDraft.value = result;
  });
}

function applyTrendDistributionResult(result) {
  trendDistributionDraft.value = result;
}

function applyJobDistributionResult(jobId, result) {
  distributionDrafts[jobId] = result;
}

function applySavedDistributionTask(result) {
  const index = distributionTasks.value.findIndex((item) => item.id === result?.id);
  if (index >= 0) {
    distributionTasks.value[index] = result;
  } else if (result) {
    distributionTasks.value.unshift(result);
  }
}

async function generateJobAudio(job) {
  const text = String(job?.script_text || job?.request?.custom_script || job?.request?.topic || "").trim();
  if (!text) {
    setError("这个任务没有可转成音频的文案。");
    return;
  }
  busy.audio = String(job.id);
  try {
    const result = await requestApi(
      "/api/audio/generate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({
          text,
          provider: "edge",
          voice: job?.request?.edge_voice || kidsForm.edge_voice
        })
      },
      180000
    );
    audioPreviews[job.id] = result;
    setNotice(`音频生成成功，使用 ${result.provider}，时长 ${result.duration_seconds || 0} 秒。`);
  } catch (error) {
    setError(normalizeErrorMessage(error, "音频生成失败。"));
  } finally {
    if (busy.audio === String(job.id)) busy.audio = "";
  }
}

async function prepareDistribution(job) {
  if (!job?.id) return;
  busy.distribution = String(job.id);
  try {
    const result = await requestApi(
      `/api/jobs/${job.id}/distribution`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({})
      },
      30000
    );
    distributionDrafts[job.id] = result;
    setNotice("分发包已生成：公众号文章、小红书标题正文和素材路径都已准备好。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "准备分发包失败。"));
  } finally {
    if (busy.distribution === String(job.id)) busy.distribution = "";
  }
}

async function createWechatDraft(job) {
  const task = distributionDrafts[job?.id];
  await submitWechatDraftTask(task, (result) => {
    distributionDrafts[job.id] = result;
  });
}

async function submitWechatDraftTask(task, applyResult) {
  if (!task?.id) return;
  if (!wechatEntry.value?.cover_configured) {
    wechatDraftErrors[task.id] = "请先点击“上传公众号封面”。微信规定草稿必须带封面，上传成功后才能发送。";
    setError(wechatDraftErrors[task.id]);
    return;
  }
  busy.wechatDraft = String(task.id);
  wechatDraftErrors[task.id] = "";
  try {
    const result = await requestApi(
      `/api/distribution/tasks/${task.id}/wechat-draft`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({ publish_now: false })
      },
      60000
    );
    applyResult(result);
    const accountHint = result.wechat?.app_id_masked || wechatEntry.value?.app_id_masked || "当前配置账号";
    const verifiedTitle = result.wechat?.verified_title || result.title || "";
    setNotice(`微信已核验草稿：${verifiedTitle}。发送账号 AppID：${accountHint}，请登录这个 AppID 对应的公众号查看。`);
  } catch (error) {
    const message = normalizeErrorMessage(error, "公众号草稿创建失败。");
    wechatDraftErrors[task.id] = message;
    setError(message);
  } finally {
    busy.wechatDraft = "";
  }
}

async function prepareMaterialDistribution(material) {
  if (!material?.id || !material?.script) return;
  busy.distribution = String(material.id);
  try {
    const result = await requestApi(
      `/api/integrations/wechat/materials/${material.id}/distribution`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({})
      },
      30000
    );
    materialDistributionDrafts[material.id] = result;
    setNotice("公众号文章已准备好。首次使用请上传封面，然后发送到草稿箱。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "准备公众号文章失败。"));
  } finally {
    if (busy.distribution === String(material.id)) busy.distribution = "";
  }
}

async function createMaterialWechatDraft(material) {
  const task = materialDistributionDrafts[material?.id];
  await submitWechatDraftTask(task, (result) => {
    materialDistributionDrafts[material.id] = result;
  });
}

function applyMaterialDistributionResult(materialId, result) {
  materialDistributionDrafts[materialId] = result;
}

async function uploadWechatCover(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  busy.wechatCover = true;
  try {
    const form = new FormData();
    form.append("file", file);
    await requestApi(
      "/api/integrations/wechat/cover",
      { method: "POST", body: form },
      90000
    );
    const entry = await requestApi("/api/integrations/wechat/entry");
    if (entry) wechatEntry.value = entry;
    setNotice("公众号封面已上传并保存，以后创建草稿会自动使用它。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "公众号封面上传失败。"));
  } finally {
    busy.wechatCover = false;
    if (event?.target) event.target.value = "";
  }
}

async function updateXiaohongshuStatus(task, status, applyResult, noteUrl = "") {
  if (!task?.id) return;
  busy.xiaohongshu = String(task.id);
  try {
    const result = await requestApi(
      `/api/distribution/tasks/${task.id}/xiaohongshu/status`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({
          status,
          note_url: noteUrl,
          notes: status === "failed" ? "人工发布未完成，等待重新处理。" : ""
        })
      },
      30000
    );
    applyResult(result);
    return result;
  } catch (error) {
    setError(normalizeErrorMessage(error, "更新小红书发布状态失败。"));
    return null;
  } finally {
    busy.xiaohongshu = "";
  }
}

async function refreshXiaohongshuServerSession() {
  busy.xiaohongshuSession = true;
  try {
    const result = await requestApi(
      "/api/integrations/xiaohongshu/session",
      { method: "POST" },
      90000
    );
    xiaohongshuServerSession.value = result;
    setNotice(result.message || "小红书服务器登录状态已刷新。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "检查小红书服务器登录状态失败。"));
  } finally {
    busy.xiaohongshuSession = false;
  }
}

async function refreshXiaohongshuFrame(silent = true) {
  if (
    busy.xiaohongshuDrag ||
    busy.xiaohongshuSms ||
    busy.xiaohongshuVerify ||
    xiaohongshuServerSession.value?.logged_in
  ) return;
  try {
    const result = await requestApi(
      "/api/integrations/xiaohongshu/frame",
      { method: "POST" },
      15000
    );
    xiaohongshuServerSession.value = result;
  } catch (error) {
    if (!silent) {
      setError(normalizeErrorMessage(error, "刷新服务器登录画面失败。"));
    }
  }
}

function toggleXiaohongshuRemote(event) {
  if (xiaohongshuFrameTimer) {
    window.clearInterval(xiaohongshuFrameTimer);
    xiaohongshuFrameTimer = null;
  }
  if (!event.currentTarget.open) return;
  refreshXiaohongshuFrame(false);
  xiaohongshuFrameTimer = window.setInterval(() => {
    refreshXiaohongshuFrame(true);
  }, 1500);
}

async function sendXiaohongshuSms() {
  const phone = xiaohongshuPhone.value.replace(/\D/g, "");
  if (phone.length !== 11) {
    setError("请输入 11 位手机号。");
    return;
  }
  if (xiaohongshuFrameTimer) {
    window.clearInterval(xiaohongshuFrameTimer);
    xiaohongshuFrameTimer = null;
  }
  busy.xiaohongshuSms = true;
  try {
    const result = await requestApi(
      "/api/integrations/xiaohongshu/send-sms",
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({ phone })
      },
      90000
    );
    xiaohongshuServerSession.value = result;
    setNotice(result.message || "验证码请求已提交。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "发送小红书验证码失败。"));
    await refreshXiaohongshuServerSession();
  } finally {
    busy.xiaohongshuSms = false;
  }
}

async function verifyXiaohongshuSms() {
  const phone = xiaohongshuPhone.value.replace(/\D/g, "");
  const code = xiaohongshuSmsCode.value.replace(/\D/g, "");
  if (phone.length !== 11 || code.length < 4) {
    setError("请填写手机号和短信验证码。");
    return;
  }
  if (xiaohongshuFrameTimer) {
    window.clearInterval(xiaohongshuFrameTimer);
    xiaohongshuFrameTimer = null;
  }
  busy.xiaohongshuVerify = true;
  try {
    const result = await requestApi(
      "/api/integrations/xiaohongshu/verify-sms",
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({ phone, code })
      },
      90000
    );
    xiaohongshuServerSession.value = result;
    if (result.logged_in) {
      xiaohongshuSmsCode.value = "";
      setNotice(result.message || "小红书服务器登录成功。");
    } else {
      setError(result.message || "小红书登录没有完成，请重新获取验证码。");
    }
  } catch (error) {
    setError(normalizeErrorMessage(error, "小红书验证码登录失败。"));
    await refreshXiaohongshuServerSession();
  } finally {
    busy.xiaohongshuVerify = false;
  }
}

function xiaohongshuImagePoint(event) {
  const image = event.currentTarget;
  const rect = image.getBoundingClientRect();
  const viewportWidth = Number(xiaohongshuServerSession.value?.viewport_width || image.naturalWidth || 1440);
  const viewportHeight = Number(xiaohongshuServerSession.value?.viewport_height || image.naturalHeight || 1000);
  return {
    x: Math.max(0, Math.min(viewportWidth, ((event.clientX - rect.left) / rect.width) * viewportWidth)),
    y: Math.max(0, Math.min(viewportHeight, ((event.clientY - rect.top) / rect.height) * viewportHeight)),
    displayX: event.clientX - rect.left,
    displayY: event.clientY - rect.top
  };
}

function startXiaohongshuDrag(event) {
  if (busy.xiaohongshuDrag || !xiaohongshuServerSession.value?.challenge_visible) {
    setError("当前没有检测到滑块，请不要拖动画面，直接使用新验证码登录。");
    return;
  }
  event.currentTarget.setPointerCapture?.(event.pointerId);
  const point = xiaohongshuImagePoint(event);
  xiaohongshuDragStart.value = point;
  xiaohongshuDragLine.value = {
    x1: point.displayX,
    y1: point.displayY,
    x2: point.displayX,
    y2: point.displayY
  };
}

function moveXiaohongshuDrag(event) {
  if (!xiaohongshuDragStart.value || busy.xiaohongshuDrag) return;
  const point = xiaohongshuImagePoint(event);
  xiaohongshuDragLine.value = {
    ...xiaohongshuDragLine.value,
    x2: point.displayX,
    y2: point.displayY
  };
}

async function finishXiaohongshuDrag(event) {
  const start = xiaohongshuDragStart.value;
  if (!start || busy.xiaohongshuDrag) return;
  const end = xiaohongshuImagePoint(event);
  xiaohongshuDragStart.value = null;
  xiaohongshuDragLine.value = null;
  busy.xiaohongshuDrag = true;
  try {
    const result = await requestApi(
      "/api/integrations/xiaohongshu/drag",
      {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({
          start_x: start.x,
          start_y: start.y,
          end_x: end.x,
          end_y: end.y
        })
      },
      30000
    );
    xiaohongshuServerSession.value = result;
    setNotice(result.message || "服务器已执行滑块拖动。");
  } catch (error) {
    setError(normalizeErrorMessage(error, "服务器滑块拖动失败。"));
    await refreshXiaohongshuServerSession();
  } finally {
    busy.xiaohongshuDrag = false;
  }
}

function cancelXiaohongshuDrag() {
  xiaohongshuDragStart.value = null;
  xiaohongshuDragLine.value = null;
}

function xiaohongshuPublishToken() {
  const saved = window.sessionStorage.getItem("xiaohongshu_publish_token") || "";
  if (saved) return saved;
  const entered = window.prompt("请输入服务器的小红书发布密钥。当前浏览器关闭后会自动清除。");
  const token = String(entered || "").trim();
  if (token) window.sessionStorage.setItem("xiaohongshu_publish_token", token);
  return token;
}

async function directPublishXiaohongshu(task, applyResult) {
  if (!task?.id) return;
  const title = String(task?.xiaohongshu?.title || task?.title || "").trim();
  if (!window.confirm(`确认正式发布到小红书？\n\n标题：${title}\n\n发布后用户将能看到这篇内容。小红书可能识别第三方自动化，近期账号已有过预警；如果你仍要自动发布，请点确认。`)) return;
  const token = xiaohongshuPublishToken();
  if (!token) {
    setError("没有输入发布密钥，本次没有发布。");
    return;
  }
  busy.xiaohongshuDirectPublish = String(task.id);
  try {
    let result = await requestApi(
      `/api/distribution/tasks/${task.id}/xiaohongshu/direct-publish`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "X-Publish-Token": token
        },
        body: JSON.stringify({
          confirm_title: title,
          confirm_publish: true
        })
      },
      20000
    );
    applyResult(result);
    setNotice("服务器正在正式发布到小红书，请稍等，页面会自动更新结果。");
    const deadline = Date.now() + 8 * 60 * 1000;
    while (Date.now() < deadline) {
      await new Promise((resolve) => window.setTimeout(resolve, 3000));
      const payload = await requestApi("/api/distribution/tasks", {}, 20000);
      result = (payload.items || []).find((item) => String(item.id) === String(task.id));
      if (!result) throw new Error("没有找到正在发布的小红书任务。");
      applyResult(result);
      const status = result?.xiaohongshu?.status;
      if (status === "published") {
        await refreshDistributionTasks();
        setNotice(result?.xiaohongshu?.message || "小红书已确认发布成功。");
        return;
      }
      if (["failed", "login_required"].includes(status)) {
        throw new Error(result?.xiaohongshu?.save_error || "小红书发布失败，请查看服务器结果截图。");
      }
    }
    throw new Error("小红书发布超过 8 分钟仍未完成，请查看服务器结果截图。");
  } catch (error) {
    if (String(error?.message || "").includes("密钥")) {
      window.sessionStorage.removeItem("xiaohongshu_publish_token");
    }
    setError(normalizeErrorMessage(error, "直接发布到小红书失败。"));
    await refreshDistributionTasks();
  } finally {
    busy.xiaohongshuDirectPublish = "";
  }
}

async function finishXiaohongshuPublishing(task, applyResult) {
  const noteUrl = String(xiaohongshuPublishUrls[task?.id] || "").trim();
  if (!noteUrl) {
    setError("请先粘贴发布后的小红书笔记链接。");
    return;
  }
  const result = await updateXiaohongshuStatus(task, "published", applyResult, noteUrl);
  if (result) setNotice("小红书笔记已标记为发布完成，链接已保存，后续可以继续做数据复盘。");
}

async function failXiaohongshuPublishing(task, applyResult) {
  const result = await updateXiaohongshuStatus(task, "failed", applyResult);
  if (result) setNotice("已记录为发布失败，你可以修改内容后重新开始。");
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
      body: JSON.stringify({ ...stockForm, symbol: value, question: stockQuestion.value })
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
  const needsSymbol = !["watchlist_review", "condition_screening", "personal_strategy_plan"].includes(selected);
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

function stockDecisionGuide(analysis) {
  return buildStockDecisionGuide(analysis, stockQuestion.value);
}

function stockReadableReport(analysis) {
  return buildStockReadableReport(analysis, stockQuestion.value);
}

const kidsJobs = computed(() => jobs.value.filter((job) => String(job?.request?.project_mode || "") === "kids_cartoon"));
const runningKidsJobs = computed(() => kidsJobs.value.filter((job) => ["queued", "running"].includes(job.status)));
const completedKidsJobs = computed(() => kidsJobs.value.filter((job) => job.status === "completed"));
const failedKidsJobs = computed(() => kidsJobs.value.filter((job) => job.status === "failed"));
const latestWechatMaterial = computed(() => wechatMaterials.value[0] || null);
const selectedWechatMaterial = computed(() => (
  wechatMaterials.value.find((item) => item.id === selectedWechatMaterialId.value) || latestWechatMaterial.value
));
const xiaohongshuSystemDrafts = computed(() => (
  distributionTasks.value.filter((item) => (
    [
      "draft_saved",
      "platform_draft_saving",
      "platform_draft_saved",
      "platform_draft_failed",
      "login_required",
      "publishing",
      "published",
      "failed"
    ].includes(item?.xiaohongshu?.status)
  ))
));
const latestWechatCallbackEvent = computed(() => wechatCallbackEvents.value[0] || null);
const studioStats = computed(() => [
  { value: `${Math.max(aiTrends.value[0]?.items?.length || 0, 120)}+`, label: "实时信息源", icon: "globe" },
  { value: "60s", label: "素材到成片", icon: "flash" },
  { value: "8 类", label: "内容 Skill 模板", icon: "chart" },
  { value: "3x", label: "周更产能提升", icon: "trend" }
]);
const modulePageMeta = computed(() => getModulePageMeta(activeTab.value));

const selectedWechatSkillName = computed(() => (
  channelSkillsList.value.find((skill) => skill.id === selectedWechatSkill.value)?.name || "默认公众号 Skill"
));
const selectedXhsSkillName = computed(() => (
  channelSkillsList.value.find((skill) => skill.id === selectedXhsSkill.value)?.name || "默认小红书 Skill"
));
const contentWorkflow = computed(() => buildContentWorkflowState({
  isRefreshing: busy.refreshTrends,
  hasTrends: aiTrends.value.length > 0,
  hasSummary: Boolean(trendAiSummary.value && !trendAiSummary.value.error),
  hasDirection: Boolean(trendContentDirection.value.trim()),
  hasWechatSkill: Boolean(selectedWechatSkill.value),
  hasXhsSkill: Boolean(selectedXhsSkill.value),
  hasDistributionDraft: Boolean(trendDistributionDraft.value),
  hasWechatPreview: Boolean(trendDistributionDraft.value?.wechat?.article_html_url),
  wechatDraftVerified: Boolean(trendDistributionDraft.value?.wechat?.verified),
  hasReviewResult: Boolean(trendWorkflowReview.value),
}));
const trendNextAction = computed(() => {
  return contentWorkflow.value?.nextAction || buildTrendNextAction({
    isRefreshing: busy.refreshTrends,
    hasTrends: aiTrends.value.length > 0,
    hasSummary: Boolean(trendAiSummary.value),
    isSkillSelectorVisible: skillSelectorVisible.value,
    hasDistributionDraft: Boolean(trendDistributionDraft.value)
  });
});

function runTrendWorkflowReview() {
  if (!trendDistributionDraft.value) {
    setError("请先生成公众号和小红书文案，再运行审稿。");
    return;
  }
  trendWorkflowReview.value = reviewDistributionDraft(
    trendDistributionDraft.value,
    trendSelectedReviewSkill.value
  );
  setNotice(trendWorkflowReview.value.passed ? "审稿通过，可以进入发布前预览。" : "审稿完成，建议先补齐提示中的缺口。");
}

function openStudioModule(tab, targetId = "") {
  activeTab.value = tab;
  if (tab === "trends" && !aiTrends.value.length && !busy.refreshTrends) {
    refreshAiTrends();
  }
  if (tab === "materials" && !wechatMaterialsLoaded.value && !busy.refreshWechat) {
    refreshWechatMaterials();
  }
  if (tab === "materials" && !distributionTasksLoaded.value) {
    refreshDistributionTasks();
  }
  if (tab === "stocks" && !stockMarket.value && !busy.stockMarket) {
    Promise.allSettled([
      refreshStockWatchlist(),
      refreshStockMarket(),
      refreshStockHistory(),
      refreshStockSkills()
    ]);
  }
  if (!targetId) return;
  nextTick(() => {
    const target = document.getElementById(targetId);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

async function loadPresetTopicsAndSkills() {
  try {
    const [topicsData, skillsData] = await Promise.allSettled([
      requestApi("/api/ai-trends/preset-topics"),
      requestApi("/api/channel-skills"),
    ]);
    if (topicsData.status === "fulfilled" && Array.isArray(topicsData.value?.items)) {
      presetTopics.value = topicsData.value.items;
    }
    if (skillsData.status === "fulfilled" && Array.isArray(skillsData.value?.items)) {
      channelSkillsList.value = skillsData.value.items;
    }
  } catch (_) { /* ignore */ }
}

const uploadSkillModal = ref({
  visible: false,
  channel: "wechat",
  name: "",
  description: "",
  tags: "",
  file: null,
  uploading: false,
  error: "",
});

function openUploadSkill(channel) {
  uploadSkillModal.value = { visible: true, channel, name: "", description: "", tags: "", file: null, uploading: false, error: "" };
}

async function submitUploadSkill() {
  const m = uploadSkillModal.value;
  if (!m.name.trim()) { m.error = "请填写 Skill 名称"; return; }
  if (!m.file) { m.error = "请选择 .md 文件"; return; }
  m.uploading = true;
  m.error = "";
  try {
    const fd = new FormData();
    fd.append("file", m.file);
    fd.append("name", m.name.trim());
    fd.append("channel", m.channel);
    fd.append("description", m.description.trim());
    fd.append("persona_tags", JSON.stringify(m.tags.split(",").map(t => t.trim()).filter(Boolean)));
    const base = verifiedApiBase.value || configuredApiBase.value || "";
    const res = await fetch(`${base}/api/channel-skills/upload`, { method: "POST", body: fd });
    if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || res.statusText); }
    uploadSkillModal.value.visible = false;
    await loadPresetTopicsAndSkills();
  } catch (err) {
    m.error = err.message || "上传失败";
  } finally {
    m.uploading = false;
  }
}

async function deleteSkill(skillId, skillName) {
  if (!confirm(`确认删除 Skill「${skillName}」？`)) return;
  try {
    const base = verifiedApiBase.value || configuredApiBase.value || "";
    await fetch(`${base}/api/channel-skills/${encodeURIComponent(skillId)}`, { method: "DELETE" });
    await loadPresetTopicsAndSkills();
  } catch (err) {
    setError(`删除失败：${err.message}`);
  }
}

async function generateTrendAiSummary() {
  if (!aiTrends.value.length) return;
  busy.trendSummarize = true;
  trendAiSummary.value = null;
  try {
    const trend = aiTrends.value[0];
    const result = await requestApi("/api/ai-trends/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ trend_id: trend.id || "" }),
    }, 60000);
    trendAiSummary.value = result?.summary || null;
    // 自动预填推荐 Skill
    if (!wechatSkillManuallySelected.value && trendAiSummary.value?.suggested_wechat_skill) {
      selectedWechatSkill.value = trendAiSummary.value.suggested_wechat_skill;
    }
    if (!xhsSkillManuallySelected.value && trendAiSummary.value?.suggested_xhs_skill) {
      selectedXhsSkill.value = trendAiSummary.value.suggested_xhs_skill;
    }
    skillSelectorVisible.value = true;
    trendDiscussionOpen.value = true;
  } catch (err) {
    setError(normalizeErrorMessage(err, "AI 摘要生成失败，请检查 OPENAI_API_KEY 是否已配置。"));
  } finally {
    busy.trendSummarize = false;
  }
}

async function sendTrendChat() {
  const userMsg = trendChatInput.value.trim();
  if (!userMsg) return;
  trendChatMessages.value.push({ role: "user", content: userMsg });
  trendChatInput.value = "";
  busy.trendChat = true;
  const trend = aiTrends.value[0];
  const trendContext = trendAiSummary.value
    ? `今日摘要：${trendAiSummary.value.one_sentence || ""}\n关键点：${(trendAiSummary.value.key_points || []).join("；")}`
    : (trend?.summary || "");
  try {
    const result = await requestApi("/api/ai-trends/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({
        messages: trendChatMessages.value,
        trend_context: trendContext,
        query: trend?.query || "",
      }),
    }, 60000);
    trendChatMessages.value.push({ role: "assistant", content: result.response || "" });
  } catch (err) {
    trendChatMessages.value.push({ role: "assistant", content: `[错误] ${normalizeErrorMessage(err, "对话失败")}` });
  } finally {
    busy.trendChat = false;
  }
}

const studioContext = {
  acceptCreatedMaterial,
  activeApiBase,
  activeTab,
  aiTrends,
  analyzeStock,
  apiCandidates,
  apiResolutionPromise,
  applyJobDistributionResult,
  applyMaterialDistributionResult,
  applySavedDistributionTask,
  applyScriptResult,
  applyTrendDistributionResult,
  applyWechatMaterial,
  archiveCurrentScript,
  archiveWechatMaterial,
  audioPreviews,
  brandIconDataUrl,
  brandName,
  brandTagline,
  browserApiBase,
  busy,
  busy_trendChat,
  busy_trendSummarize,
  canRecordTrendVoice,
  cancelTrendVoiceRecording,
  cancelXiaohongshuDrag,
  channelSkillsList,
  chooseFollowupQuestion,
  chooseStockSearchResult,
  clearCharacterVoice,
  clearHumanData,
  clearReferenceImage,
  clearWechatDiagnostics,
  clearWechatMaterials,
  completedKidsJobs,
  configuredApiBase,
  contentWorkflow,
  continueTrendInterview,
  copyNotebookLmSourceLinks,
  copyText,
  coreModules,
  createMaterialWechatDraft,
  createNotebookLmPackage,
  createTrendWechatDraft,
  createWechatDraft,
  deepseekReview,
  deleteHistoryJob,
  deleteSkill,
  deleteStockFromWatchlist,
  deleteWechatMaterial,
  openUploadSkill,
  submitUploadSkill,
  uploadSkillModal,
  deletingJobId,
  directPublishXiaohongshu,
  distributionDrafts,
  distributionTasks,
  distributionTasksLoaded,
  draftScript,
  errorMessage,
  failXiaohongshuPublishing,
  failedKidsJobs,
  finalReview,
  finishXiaohongshuDrag,
  finishXiaohongshuPublishing,
  formatStockNumber,
  generateDraftAndReview,
  generateJobAudio,
  generateKidsVideo,
  generateScriptFromTrend,
  generateTrendAiSummary,
  generateTrendQuestions,
  generateWechatMaterial,
  generatingTrendScript,
  hardRules,
  humanReviewNotes,
  isLocalBrowser,
  jobProgress,
  jobs,
  jobsLoaded,
  kidsForm,
  kidsJobs,
  kidsPayload,
  latestWechatCallbackEvent,
  latestWechatMaterial,
  loadPresetTopicsAndSkills,
  maodouVoiceUrl,
  materialDistributionDrafts,
  materialRecorder,
  materialRecorderChunks,
  materialRecorderStream,
  materialRecording,
  materialTextInput,
  materialVoiceNote,
  mediaUrl,
  modulePageMeta,
  moveXiaohongshuDrag,
  notebookLmPackage,
  notice,
  openDouyinCreator,
  openStudioModule,
  peanutVoiceUrl,
  pingApi,
  prepareDistribution,
  prepareDouyinPublish,
  prepareMaterialDistribution,
  prepareTrendDistribution,
  presetTopics,
  previewKidsScript,
  previewStoryboard,
  publishDrafts,
  quality,
  referenceImageUrl,
  referenceStyleContract,
  refreshAiTrends,
  refreshDistributionTasks,
  refreshJobs,
  refreshStockHistory,
  refreshStockMarket,
  refreshStockSkills,
  refreshStockWatchlist,
  refreshWechatMaterials,
  refreshXiaohongshuFrame,
  refreshXiaohongshuServerSession,
  requestApi,
  resolveApiBase,
  reviewLines,
  reviseWithReview,
  runTrendWorkflowReview,
  runStockSkill,
  runningKidsJobs,
  saveStockToWatchlist,
  scriptAi,
  searchStockSymbols,
  selectedStockSkill,
  selectedTrendQuestion,
  selectedWechatMaterial,
  selectedWechatMaterialId,
  selectedWechatSkill,
  selectedWechatSkillName,
  selectedXhsSkill,
  selectedXhsSkillName,
  sendTrendChat,
  sendXiaohongshuSms,
  setError,
  setNotice,
  sidebarModules,
  skillSelectorVisible,
  startMaterialRecording,
  startTrendInterview,
  startTrendVoiceRecording,
  startXiaohongshuDrag,
  stockAnalysis,
  stockChangeClass,
  stockDecisionGuide,
  stockForm,
  stockHistory,
  stockKlinePoints,
  stockMarket,
  stockQuestion,
  stockReadableReport,
  stockSearchResults,
  stockSkillName,
  stockSkillResult,
  stockSkillRuns,
  stockSkills,
  stockWatchlist,
  stopMaterialRecording,
  stopTrendVoiceRecording,
  studioStats,
  submitTextMaterial,
  submitWechatDraftTask,
  toggleXiaohongshuRemote,
  transcribeTrendInterviewAudioBlob,
  trendAiSummary,
  trendChatInput,
  trendChatMessages,
  trendContentDirection,
  trendDiscussionOpen,
  trendDistributionDraft,
  trendDistributionView,
  trendFollowups,
  trendFreshHighlight,
  trendHighlightTimer,
  trendInterviewAnswer,
  trendInterviewCancelRecording,
  trendInterviewChunks,
  trendInterviewRecorder,
  trendInterviewRecording,
  trendInterviewStream,
  trendInterviewTurns,
  trendInterviewVoiceNote,
  trendNextAction,
  trendQuestions,
  trendSelectedReviewSkill,
  trendScripts,
  trendSearchQuery,
  trendWorkflowReview,
  updateXiaohongshuStatus,
  uploadCharacterVoice,
  uploadMaterialAudio,
  uploadMaterialAudioFile,
  uploadReferenceImage,
  uploadTrendInterviewVoice,
  uploadWechatCover,
  verifiedApiBase,
  verifyXiaohongshuSms,
  visualPipeline,
  voicePresets,
  wechatCallbackEvents,
  wechatDraftErrors,
  wechatEntry,
  wechatMaterials,
  wechatMaterialsLoaded,
  wechatQrImageUrl,
  wechatSkillManuallySelected,
  WORKFLOW_REVIEW_OPTIONS,
  workflowCards,
  xhsSkillManuallySelected,
  xiaohongshuDragLine,
  xiaohongshuDragStart,
  xiaohongshuFrameTimer,
  xiaohongshuImagePoint,
  xiaohongshuNextStep,
  xiaohongshuPhone,
  xiaohongshuPublishToken,
  xiaohongshuPublishUrls,
  xiaohongshuServerSession,
  xiaohongshuSmsCode,
  xiaohongshuStatusLabel,
  xiaohongshuSystemDrafts,
};
provide("studioContext", studioContext);

let pollTimer = null;
onMounted(async () => {
  await loadPresetTopicsAndSkills();
  if (activeTab.value === "trends") {
    await refreshAiTrends();
  } else if (activeTab.value === "materials") {
    await Promise.allSettled([
      refreshWechatMaterials(),
      refreshDistributionTasks(),
    ]);
  } else if (activeTab.value !== "overview") {
    await refreshJobs();
  }
  pollTimer = window.setInterval(() => {
    if (jobsLoaded.value && runningKidsJobs.value.length) refreshJobs();
    if (
      distributionTasksLoaded.value &&
      distributionTasks.value.some(
        (item) => item?.xiaohongshu?.status === "platform_draft_saving"
      )
    ) {
      refreshDistributionTasks();
    }
  }, 3000);
});

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer);
  if (trendHighlightTimer) window.clearTimeout(trendHighlightTimer);
  if (trendInterviewRecorder && trendInterviewRecorder.state !== "inactive") {
    trendInterviewRecorder.stop();
  }
  if (materialRecorder && materialRecorder.state !== "inactive") {
    materialRecorder.stop();
  }
  materialRecorderStream?.getTracks().forEach((track) => track.stop());
});
</script>

<template>
  <div class="studio-page" :class="{ 'module-mode': activeTab !== 'overview' }">
    <aside v-if="activeTab !== 'overview'" class="studio-sidebar" aria-label="功能模块侧边栏">
      <button class="sidebar-brand" type="button" @click="activeTab = 'overview'">
        <img class="brand-logo-img" :src="brandIconDataUrl" alt="" aria-hidden="true" />
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
        <img class="brand-logo-img" :src="brandIconDataUrl" alt="" aria-hidden="true" />
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
      <OverviewPage v-if="activeTab === 'overview'" />

      <section v-if="activeTab !== 'overview'" class="module-hero">
        <div>
          <span class="dashboard-kicker">{{ modulePageMeta.kicker }}</span>
          <h1>{{ modulePageMeta.title }}</h1>
          <p>{{ modulePageMeta.desc }}</p>
        </div>
        <div v-if="activeTab === 'materials'" class="hero-actions">
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

      <div v-if="notice" class="notice">{{ notice }}</div>
      <div v-if="errorMessage" class="notice danger">{{ errorMessage }}</div>

    <RealtimeInfoPage v-if="activeTab === 'trends'" />

    <MaterialStudioPage v-if="activeTab === 'materials'" />

    <StockAnalysisPage v-if="activeTab === 'stocks'" />
      <footer class="studio-footer">
        <span><img class="brand-logo-img small" :src="brandIconDataUrl" alt="" aria-hidden="true" /> 灵感工坊 AI Studio · inspwk.site</span>
        <span>© 2026 · AI 洞察 · 软件开发 · 职场成长 · 内容创作</span>
      </footer>
    </main>
  </div>
</template>

<style>
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

.xiaohongshu-login-preview {
  display: block;
  width: min(100%, 960px);
  max-height: 640px;
  object-fit: contain;
  margin-top: 14px;
  border: 1px solid #263b50;
  background: #ffffff;
}

.xiaohongshu-remote-frame {
  position: relative;
  width: min(100%, 960px);
  margin-top: 14px;
  user-select: none;
}

.xiaohongshu-login-preview.interactive {
  width: 100%;
  height: auto;
  max-height: none;
  margin-top: 0;
  cursor: default;
  touch-action: none;
  user-select: none;
  -webkit-user-drag: none;
}

.xiaohongshu-remote-frame.interactive .xiaohongshu-login-preview {
  cursor: crosshair;
}

.xiaohongshu-remote-frame.busy .xiaohongshu-login-preview {
  opacity: 0.55;
  cursor: wait;
}

.xiaohongshu-drag-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  overflow: visible;
}

.xiaohongshu-drag-overlay line {
  stroke: #ff7139;
  stroke-width: 5;
  stroke-linecap: round;
}

.xiaohongshu-drag-overlay circle {
  fill: #00cfe8;
  stroke: #ffffff;
  stroke-width: 2;
}

.xiaohongshu-remote-loading {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  padding: 12px 16px;
  border-radius: 6px;
  background: #081521;
  color: #ffffff;
  font-weight: 800;
  pointer-events: none;
}

.xiaohongshu-sms-login {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) auto minmax(180px, 0.7fr) auto;
  align-items: end;
  gap: 12px;
  margin-top: 14px;
}

.success-text {
  color: #2bd99f;
  font-weight: 800;
}

@media (max-width: 900px) {
  .xiaohongshu-sms-login {
    grid-template-columns: 1fr;
    align-items: stretch;
  }
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

.trend-flow-hint {
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(0, 213, 232, 0.28);
  border-radius: 8px;
  background: rgba(0, 213, 232, 0.08);
  color: #dcecff;
  font-size: 13px;
  font-weight: 800;
}

.trend-card.fresh {
  border-color: #00d5e8;
  box-shadow: 0 0 0 2px rgba(0, 213, 232, 0.16);
}

.trend-loading-strip {
  padding: 8px 10px;
  border-radius: 7px;
  background: rgba(0, 213, 232, 0.12);
  color: #00d5e8;
  font-size: 12px;
  font-weight: 800;
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

.trend-card li.trend-news-item {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 12px;
}

.trend-news-main {
  display: grid;
  gap: 4px;
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

.trend-chat-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  border: 0;
  background: transparent;
  color: inherit;
  padding: 0;
  text-align: left;
  cursor: pointer;
}

.trend-chat-toggle span {
  display: grid;
  gap: 4px;
}

.trend-chat-toggle small {
  color: #5f7088;
  font-size: 12px;
}

.trend-chat-inner {
  margin-top: 12px;
}

.skill-selected-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid rgba(142, 171, 205, 0.18);
  background: rgba(0, 213, 232, 0.04);
}

.skill-selected-summary span {
  padding: 4px 9px;
  border-radius: 999px;
  background: rgba(0, 213, 232, 0.12);
  color: #00d5e8;
  font-size: 12px;
  font-weight: 800;
}

.skill-card.selected {
  border-color: #00d5e8;
  background: rgba(0, 213, 232, 0.12);
  box-shadow: inset 0 0 0 1px rgba(0, 213, 232, 0.35);
}

.skill-channel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.skill-channel-head h4 {
  margin: 0;
}

.btn-upload-skill {
  background: transparent;
  border: 1px dashed rgba(0, 213, 232, 0.45);
  border-radius: 8px;
  color: #00d5e8;
  font-size: 12px;
  font-weight: 700;
  padding: 5px 12px;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-upload-skill:hover {
  background: rgba(0, 213, 232, 0.1);
}

.skill-delete-btn {
  margin-left: auto;
  background: transparent;
  border: none;
  color: rgba(169, 191, 218, 0.5);
  font-size: 13px;
  cursor: pointer;
  padding: 0 2px;
  line-height: 1;
  flex-shrink: 0;
  transition: color 0.15s;
}

.skill-delete-btn:hover {
  color: #ff6b6b;
}

.skill-upload-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(6, 17, 28, 0.72);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.skill-upload-modal {
  background: #0d1f33;
  border: 1px solid rgba(142, 171, 205, 0.2);
  border-radius: 14px;
  width: 440px;
  max-width: 92vw;
  overflow: hidden;
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(142, 171, 205, 0.15);
}

.modal-close {
  background: transparent;
  border: none;
  color: #a9bfda;
  font-size: 16px;
  cursor: pointer;
  padding: 2px 6px;
}

.modal-body {
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.modal-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 13px;
  color: #a9bfda;
}

.modal-field input[type="text"],
.modal-field input[type="file"] {
  background: rgba(142, 171, 205, 0.07);
  border: 1px solid rgba(142, 171, 205, 0.2);
  border-radius: 7px;
  color: #e2eaf4;
  font-size: 13px;
  padding: 7px 10px;
}

.modal-error {
  color: #ff6b6b;
  font-size: 12px;
  margin: 0;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 14px 20px;
  border-top: 1px solid rgba(142, 171, 205, 0.15);
}

.channel-tabs {
  display: inline-flex;
  gap: 6px;
  padding: 4px;
  border: 1px solid rgba(142, 171, 205, 0.18);
  border-radius: 10px;
  background: rgba(142, 171, 205, 0.08);
}

.channel-tab {
  border: 0;
  border-radius: 8px;
  padding: 8px 14px;
  background: transparent;
  color: #a9bfda;
  font-weight: 900;
  cursor: pointer;
}

.channel-tab.active {
  background: #00d5e8;
  color: #06111c;
}

.channel-preview-pane {
  display: grid;
  gap: 12px;
}

.wechat-preview-box {
  display: grid;
  gap: 6px;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(142, 171, 205, 0.18);
  background: rgba(142, 171, 205, 0.08);
}

.wechat-preview-box p {
  margin: 0;
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

.primary-flow-actions {
  justify-content: flex-start;
  padding: 8px 0;
}

.next-step-card {
  display: grid;
  gap: 6px;
  border: 1px solid rgba(0, 213, 232, 0.28);
  border-radius: 8px;
  padding: 10px 12px;
  background: rgba(0, 213, 232, 0.08);
}

.next-step-card strong {
  color: #0a5a66;
}

.next-step-card p {
  margin: 0;
  color: #5b6d7f;
  font-size: 13px;
  line-height: 1.5;
}

.secondary-actions {
  border-top: 1px solid rgba(138, 164, 190, 0.22);
  padding-top: 8px;
}

.secondary-actions summary {
  cursor: pointer;
  color: #647890;
  font-size: 13px;
  font-weight: 800;
}

.secondary-actions .publish-buttons {
  justify-content: flex-start;
  margin-top: 8px;
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

.xiaohongshu-progress {
  display: grid;
  grid-template-columns: minmax(160px, auto) minmax(240px, 1fr) auto auto;
  gap: 8px;
  align-items: center;
  padding-top: 10px;
  border-top: 1px solid #ead5bf;
}

.xiaohongshu-progress input {
  min-width: 0;
}

.xiaohongshu-progress a {
  color: #246bfe;
  font-weight: 800;
}

.material-intake-grid,
.channel-pipeline-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
  gap: 14px;
}

.material-text-field textarea {
  min-height: 132px;
}

.material-intake-actions,
.channel-pipeline {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
}

.channel-pipeline {
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.55);
}

.mail-source {
  color: #00a6b5;
  font-size: 11px;
  font-weight: 800;
}

.xiaohongshu-card-preview {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 8px;
}

.xiaohongshu-card-preview a {
  display: block;
  aspect-ratio: 3 / 4;
  overflow: hidden;
  border: 1px solid #d7e2f1;
  border-radius: 6px;
  background: #fff;
}

.xiaohongshu-card-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.draft-list {
  display: grid;
  gap: 12px;
  margin-top: 14px;
}

.draft-list .publish-card {
  margin: 0;
}

.draft-list .publish-card > p {
  color: var(--muted);
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.xiaohongshu-result-preview {
  display: block;
  overflow: hidden;
  width: min(100%, 960px);
  max-height: 520px;
  border: 1px solid #d7e2f1;
  border-radius: 6px;
  background: #fff;
}

.xiaohongshu-result-preview img {
  display: block;
  width: 100%;
  height: auto;
  object-fit: contain;
}

@media (max-width: 860px) {
  .xiaohongshu-progress,
  .material-intake-grid,
  .channel-pipeline-grid {
    grid-template-columns: 1fr;
  }
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

.studio-page .next-step-card {
  border-color: rgba(0, 213, 232, 0.34);
  background: rgba(0, 213, 232, 0.1);
}

.studio-page .next-step-card strong {
  color: #d9fbff;
}

.studio-page .next-step-card p,
.studio-page .secondary-actions summary {
  color: #a9bfda;
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

.stock-plain-answer {
  display: grid;
  gap: 8px;
  border: 1px solid rgba(255, 122, 61, 0.28);
  border-radius: 8px;
  padding: 14px;
  background: rgba(255, 122, 61, 0.09);
}

.stock-plain-answer strong {
  color: #fff4ed;
  font-size: 18px;
}

.stock-plain-answer p {
  margin: 0;
  color: #ffd9c6;
  line-height: 1.6;
}

.stock-plain-answer span {
  color: #ffb088;
  font-weight: 900;
}

.stock-plain-answer small {
  color: #a9bfda;
  line-height: 1.5;
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
