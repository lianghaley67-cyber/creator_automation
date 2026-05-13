<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

const configuredApiBase = (import.meta.env.VITE_API_BASE || "").trim().replace(/\/$/, "");
const apiCandidates = Array.from(
  new Set(
    [
      configuredApiBase,
      "http://127.0.0.1:8000",
      "http://localhost:8000",
      "http://127.0.0.1:8011",
      "http://localhost:8011"
    ].filter(Boolean)
  )
);

const activeApiBase = ref(configuredApiBase || "http://127.0.0.1:8000");
const notice = ref("");
const errorMessage = ref("");
const jobs = ref([]);
const deletingJobId = ref("");
const previewStoryboard = ref([]);
const hardRules = ref([]);
const quality = ref(null);
const referenceStyleContract = ref(null);
const visualPipeline = ref(null);
const referenceImageUrl = ref("");
const maodouVoiceUrl = ref("");
const peanutVoiceUrl = ref("");

const voicePresets = [
  { label: "轻快软萌童声（推荐）", value: "zh-CN-XiaoyiNeural" },
  { label: "活泼男孩中文声", value: "zh-CN-YunxiNeural" },
  { label: "温柔姐姐中文声", value: "zh-CN-XiaoxiaoNeural" }
];

const busy = reactive({
  connect: false,
  refresh: false,
  cleanup: false,
  uploadReference: false,
  uploadVoice: false,
  previewScript: false,
  generate: false
});

const kidsForm = reactive({
  topic: "为什么小种子会发芽",
  content_mode: "science",
  script_provider: "zhipu",
  learning_goal: "认识种子发芽需要水、阳光和耐心",
  seconds: 45,
  prompt_hint: "请你找一找小芽在哪里，再数一数叶子",
  custom_script: "",
  reference_image_path: "",
  maodou_voice_reference_path: "",
  peanut_voice_reference_path: "",
  edge_voice: "zh-CN-XiaoyiNeural",
  animation_style: "cartoon_3d_duo_cinematic",
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
    video_provider: kidsForm.video_provider
  };
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
    setNotice("角色模板图已上传，后续生成会把它作为毛豆和花生的参考图。");
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
      setNotice("毛豆参考声音已提取，后续会优先用于毛豆台词。");
    } else {
      kidsForm.peanut_voice_reference_path = result.path || "";
      peanutVoiceUrl.value = result.url ? mediaUrl(result.url) : "";
      setNotice("花生参考声音已提取，后续会优先用于花生台词。");
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
    setNotice("已清除毛豆参考声音。");
  } else {
    kidsForm.peanut_voice_reference_path = "";
    peanutVoiceUrl.value = "";
    setNotice("已清除花生参考声音。");
  }
}

function clearReferenceImage() {
  kidsForm.reference_image_path = "";
  referenceImageUrl.value = "";
  setNotice("已清除角色模板图，本次将由智谱清影根据文案原创生成毛豆和花生形象。");
}

async function previewKidsScript() {
  busy.previewScript = true;
  try {
    const result = await requestApi("/api/kids/preview-script", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify(kidsPayload())
    });
    kidsForm.custom_script = result.script || "";
    previewStoryboard.value = Array.isArray(result.storyboard) ? result.storyboard : [];
    hardRules.value = Array.isArray(result.hard_rules) ? result.hard_rules : [];
    quality.value = result.quality || null;
    referenceStyleContract.value = result.reference_style_contract || null;
    visualPipeline.value = result.visual_pipeline || null;
    setNotice(result.script_source?.startsWith("third_party_ai") ? "已通过第三方 AI 生成文案、质量检查和多场景分镜。" : "已生成本地规则文案、质量检查和多场景分镜。");
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

function jobProgress(job) {
  const raw = Number(job?.progress_percent);
  if (Number.isFinite(raw)) return Math.min(100, Math.max(0, Math.round(raw)));
  return job?.status === "completed" ? 100 : 0;
}

const kidsJobs = computed(() => jobs.value.filter((job) => String(job?.request?.project_mode || "") === "kids_cartoon"));
const runningKidsJobs = computed(() => kidsJobs.value.filter((job) => ["queued", "running"].includes(job.status)));
const completedKidsJobs = computed(() => kidsJobs.value.filter((job) => job.status === "completed"));
const failedKidsJobs = computed(() => kidsJobs.value.filter((job) => job.status === "failed"));

let pollTimer = null;
onMounted(async () => {
  await refreshJobs();
  pollTimer = window.setInterval(() => {
    if (runningKidsJobs.value.length) refreshJobs();
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
        <span class="eyebrow">3-6 岁 · 科普与益智早教动画</span>
        <h1>毛豆和花生 3D 早教短视频生成</h1>
        <p>围绕一个知识点生成第一人称短句、互动提问、学习步骤和可爱 3D 多场景分镜。</p>
        <div class="meta">当前 API：{{ activeApiBase }}</div>
      </div>
      <div class="hero-actions">
        <button class="btn primary" :disabled="busy.previewScript" @click="previewKidsScript">
          {{ busy.previewScript ? "生成中..." : "生成文案预览" }}
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
        <h2>1. 学习设计</h2>
        <span class="eyebrow">只讲一个知识点</span>
      </div>
      <div class="field-grid">
        <label class="field">
          <span>内容类型</span>
          <select v-model="kidsForm.content_mode">
            <option value="science">科普动画</option>
            <option value="early_learning">益智早教</option>
          </select>
        </label>
        <label class="field">
          <span>文案生成</span>
          <select v-model="kidsForm.script_provider">
            <option value="zhipu">第三方 AI（智谱）</option>
            <option value="local">本地规则兜底</option>
          </select>
        </label>
        <label class="field">
          <span>时长（秒）</span>
          <input v-model.number="kidsForm.seconds" type="number" min="30" max="60" />
        </label>
        <label class="field wide">
          <span>主题</span>
          <input v-model="kidsForm.topic" placeholder="例如：为什么小种子会发芽" />
        </label>
        <label class="field wide">
          <span>学习目标</span>
          <input v-model="kidsForm.learning_goal" placeholder="例如：认识种子发芽需要水、阳光和耐心" />
        </label>
        <label class="field wide">
          <span>互动提示</span>
          <input v-model="kidsForm.prompt_hint" placeholder="例如：请你找一找小芽在哪里，再数一数叶子" />
        </label>
        <label class="field">
          <span>中文童声</span>
          <select v-model="kidsForm.edge_voice">
            <option v-for="voice in voicePresets" :key="voice.label" :value="voice.value">{{ voice.label }}</option>
          </select>
        </label>
        <label class="field">
          <span>毛豆参考声音</span>
          <input type="file" accept="audio/*,video/*" :disabled="busy.uploadVoice" @change="uploadCharacterVoice('maodou', $event)" />
        </label>
        <label class="field">
          <span>花生参考声音</span>
          <input type="file" accept="audio/*,video/*" :disabled="busy.uploadVoice" @change="uploadCharacterVoice('peanut', $event)" />
        </label>
        <div class="reference-card voice-card" :class="{ ready: kidsForm.maodou_voice_reference_path }">
          <div>
            <strong>{{ kidsForm.maodou_voice_reference_path ? "毛豆声音已提取" : "未录入毛豆声音" }}</strong>
            <p>上传毛豆的录音或视频，系统会提取前 30 秒作为毛豆语气参考。</p>
            <audio v-if="maodouVoiceUrl" :src="maodouVoiceUrl" controls preload="metadata"></audio>
            <button v-if="kidsForm.maodou_voice_reference_path" class="btn secondary small" type="button" @click="clearCharacterVoice('maodou')">清除毛豆声音</button>
          </div>
        </div>
        <div class="reference-card voice-card" :class="{ ready: kidsForm.peanut_voice_reference_path }">
          <div>
            <strong>{{ kidsForm.peanut_voice_reference_path ? "花生声音已提取" : "未录入花生声音" }}</strong>
            <p>上传花生的录音或视频，系统会提取前 30 秒作为花生语气参考。</p>
            <audio v-if="peanutVoiceUrl" :src="peanutVoiceUrl" controls preload="metadata"></audio>
            <button v-if="kidsForm.peanut_voice_reference_path" class="btn secondary small" type="button" @click="clearCharacterVoice('peanut')">清除花生声音</button>
          </div>
        </div>
        <label class="field">
          <span>动画风格</span>
          <select v-model="kidsForm.animation_style">
            <option value="cartoon_3d_duo_cinematic">3D 双角色剧情（推荐）</option>
            <option value="cartoon_3d">3D 通用动画</option>
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
        <label class="field wide">
          <span>角色模板图</span>
          <input type="file" accept="image/png,image/jpeg,image/webp" :disabled="busy.uploadReference" @change="uploadReferenceImage" />
        </label>
        <div class="reference-card wide" :class="{ ready: kidsForm.reference_image_path }">
          <img v-if="referenceImageUrl" :src="referenceImageUrl" alt="角色模板图" />
          <div>
            <strong>{{ kidsForm.reference_image_path ? "模板图已锁定" : "未上传模板图" }}</strong>
            <p>{{ kidsForm.reference_image_path ? "生成任务会把这张图作为毛豆和花生的角色参考。" : "不上传模板图时，智谱清影会根据文案原创生成适合3岁小朋友的毛豆和花生形象。" }}</p>
            <button v-if="kidsForm.reference_image_path" class="btn secondary small" type="button" @click="clearReferenceImage">清除模板图，改用文案原创</button>
          </div>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h2>2. 文案与质量检查</h2>
        <span class="eyebrow">第一人称 · 短句 · 复习</span>
      </div>
      <label class="field script-field">
        <span>可编辑文案</span>
        <textarea v-model="kidsForm.custom_script" placeholder="可以先点“生成文案预览”，也可以直接输入第一人称短句，例如：我们今天认识小种子。我先观察，再想一想。" />
      </label>

      <div v-if="quality" class="quality" :class="{ pass: quality.passed }">
        <strong>{{ quality.profile_label }} · {{ quality.passed ? "通过基础检查" : "需要优化" }}</strong>
        <span>{{ quality.line_count }} 段 · {{ quality.char_count }} 字 · 互动点 {{ quality.interaction_count }}</span>
        <p v-if="!quality.issues?.length">文案包含第一人称表达、学习目标、互动引导和结尾复习。</p>
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
