<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

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

const activeApiBase = ref(configuredApiBase || browserApiBase || "http://127.0.0.1:8000");
const notice = ref("");
const errorMessage = ref("");
const jobs = ref([]);
const wechatMaterials = ref([]);
const deletingJobId = ref("");
const previewStoryboard = ref([]);
const hardRules = ref([]);
const quality = ref(null);
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
  cleanup: false,
  uploadReference: false,
  uploadVoice: false,
  previewScript: false,
  reviseScript: false,
  generate: false,
  publish: ""
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
      try {
        const payload = await response.json();
        message = payload.detail || payload.error || JSON.stringify(payload);
      } catch {
        const text = await response.text();
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
    const data = await requestApi("/api/integrations/wechat/materials");
    wechatMaterials.value = Array.isArray(data) ? data : [];
  } catch (error) {
    setError(normalizeErrorMessage(error, "刷新微信素材失败。"));
  } finally {
    busy.refreshWechat = false;
  }
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
const pendingWechatMaterials = computed(() => wechatMaterials.value.filter((item) => item.status === "received"));

let pollTimer = null;
onMounted(async () => {
  await refreshJobs();
  await refreshWechatMaterials();
  pollTimer = window.setInterval(() => {
    if (runningKidsJobs.value.length) refreshJobs();
    if (pendingWechatMaterials.value.length) refreshWechatMaterials();
  }, 3000);
});

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer);
});
</script>

<template>
  <div class="app-shell">
    <section class="hero">
      <div>
        <span class="eyebrow">职场妈妈 · AI 提效 · 视频号 IP 工作台</span>
        <h1>职场精英妈妈 AI 视频流水线</h1>
        <p>输入今天的憋屈或剪辑心得，一键切换真人出镜/嘉宾访谈，并保留声音蒸馏与 3D 渲染能力。</p>
        <div class="meta">当前 API：{{ activeApiBase }}</div>
      </div>
      <div class="hero-actions">
        <button class="btn primary" :disabled="busy.previewScript" @click="generateDraftAndReview">
          {{ busy.previewScript ? "生成中..." : "初稿 + DeepSeek 审核" }}
        </button>
        <button class="btn primary" :disabled="busy.previewScript" @click="previewKidsScript">
          {{ busy.previewScript ? "生成中..." : "直接生成终稿" }}
        </button>
        <button class="btn accent" :disabled="busy.generate" @click="generateKidsVideo">
          {{ busy.generate ? "提交中..." : "生成视频" }}
        </button>
      </div>
    </section>

    <div v-if="notice" class="notice">{{ notice }}</div>
    <div v-if="errorMessage" class="notice danger">{{ errorMessage }}</div>

    <section class="panel">
      <div class="panel-header">
        <h2>微信素材收件箱</h2>
        <div class="top-actions">
          <button class="btn secondary" :disabled="busy.refreshWechat" @click="refreshWechatMaterials">
            {{ busy.refreshWechat ? "刷新中..." : "刷新微信素材" }}
          </button>
          <button v-if="latestWechatMaterial" class="btn accent" type="button" @click="applyWechatMaterial(latestWechatMaterial)">
            载入最新文案
          </button>
        </div>
      </div>
      <div v-if="!wechatMaterials.length" class="meta">还没有收到微信素材。你可以在微信测试号里发一句真实经历。</div>
      <div v-else class="wechat-grid">
        <div v-for="item in wechatMaterials.slice(0, 6)" :key="item.id" class="wechat-card" :class="{ ready: item.script, failed: item.status === 'preview_failed' }">
          <div class="script-preview-head">
            <strong>{{ item.status === "preview_generated" ? "已生成文案" : item.status === "preview_failed" ? "生成失败" : "已收到素材" }}</strong>
            <span>{{ item.created_at }}</span>
          </div>
          <p>{{ item.text }}</p>
          <p v-if="item.error" class="error-text">{{ item.error }}</p>
          <button class="btn secondary small" type="button" @click="applyWechatMaterial(item)">
            {{ item.script ? "载入到编辑区" : "载入素材" }}
          </button>
        </div>
      </div>
    </section>

    <section class="panel">
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

    <section class="panel">
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
          <button class="btn secondary small inline" type="button" @click="copyText(kidsForm.custom_script, '文案已复制。')">复制文案</button>
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

    <section class="panel">
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

    <button class="floating-generate" :disabled="busy.generate" @click="generateKidsVideo">
      {{ busy.generate ? "提交中..." : "生成视频" }}
    </button>
  </div>
</template>

<style scoped>
* {
  box-sizing: border-box;
}

.app-shell {
  width: min(1180px, 100% - 24px);
  margin: 18px auto 40px;
  display: grid;
  gap: 14px;
  color: #1f3045;
}

.hero,
.panel {
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(35, 62, 98, 0.08);
}

.hero {
  min-height: 220px;
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 24px;
  padding: 24px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0.9)),
    radial-gradient(circle at 18% 18%, #fff4bf, transparent 28%),
    linear-gradient(145deg, #dff5ff 0%, #cdebd0 55%, #ffe0a8 100%);
}

.panel {
  padding: 16px;
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
  border: 1px solid #cbd7e8;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  color: #1f3045;
  background: #fff;
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
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.primary {
  background: #246bfe;
  color: #fff;
}

.accent {
  background: #ff7a3d;
  color: #fff;
}

.secondary {
  background: #edf3fb;
  color: #24405f;
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

.wechat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.wechat-card {
  border: 1px solid #d7e2f1;
  border-radius: 8px;
  padding: 12px;
  background: #fbfdff;
}

.wechat-card.ready {
  border-color: #bce8ce;
  background: #effaf4;
}

.wechat-card.failed {
  border-color: #f0b8a8;
  background: #fff8f5;
}

.wechat-card p {
  margin: 8px 0 0;
  color: #1f3045;
  line-height: 1.55;
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

@media (max-width: 760px) {
  .hero {
    align-items: start;
    flex-direction: column;
  }

  .field-grid,
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
