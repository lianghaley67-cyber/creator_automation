<script>
import { computed, reactive, ref, onMounted } from "vue";
import { useStudioContext } from "./useStudioContext.js";
import { nextStoryAction, storyMetricClass, storyScoreLabel, formatStoryStep } from "./NovelStudioPage.logic.js";

export default {
  name: "NovelStudioPage",
  setup() {
    const ctx = useStudioContext("NovelStudioPage");
    const workflow = ref(null);
    const diagnosis = ref(null);
    const chapterBrief = ref(null);
    const loading = reactive({
      workflow: false,
      diagnosis: false,
      blueprint: false,
      saveBlueprint: false,
      createStory: false,
      brief: false,
      chapter: false,
    });
    const blueprintForm = reactive({
      title: "",
      genre: "romance_fantasy",
      idea: "",
      audience: "喜欢言情玄幻、强剧情和关系拉扯的女性读者",
      tone: "有画面感，情绪克制但有张力，章末留钩子",
      chapter_count: 30,
      first_volume_count: 10,
    });
    const blueprint = ref(null);
    const blueprintPromise = ref("");
    const chapterNote = ref("");
    const selectedNovelSkillId = ref("");
    const storyDraft = reactive({
      visible: false,
      name: "",
      genre: "romance_fantasy",
      error: "",
    });

    const selectedStoryName = computed(() => ctx.selectedStory.value?.name || "");
    const novelSkills = computed(() => (
      ctx.channelSkillsList.value || []
    ).filter((skill) => skill.content_kind === "fiction_serial"));
    const selectedNovelSkill = computed(() => novelSkills.value.find((skill) => skill.id === selectedNovelSkillId.value) || null);
    const storyNextAction = computed(() => nextStoryAction({
      hasStory: Boolean(ctx.selectedStoryId.value),
      hasDiagnosis: Boolean(diagnosis.value),
      hasBrief: Boolean(chapterBrief.value),
    }));

    function normalizeStoryGenre(raw) {
      const value = String(raw || "").trim();
      if (["romance_fantasy", "fantasy", "romance"].includes(value)) return value;
      if (["言情玄幻", "言情玄幻连载", "玄幻言情"].includes(value)) return "romance_fantasy";
      return "romance_fantasy";
    }

    function ensureNovelSkillSelected() {
      if (selectedNovelSkillId.value && novelSkills.value.some((skill) => skill.id === selectedNovelSkillId.value)) return;
      selectedNovelSkillId.value =
        novelSkills.value.find((skill) => skill.channel === "wechat")?.id ||
        novelSkills.value[0]?.id ||
        "";
    }

    function uploadNovelSkill() {
      ctx.openUploadSkill("wechat", {
        contentKind: "fiction_serial",
        name: "公众号·自定义连载小说",
        description: "按你的连载小说规则生成章节，包含人物目标、冲突推进、情绪张力和章末悬念。",
        tags: "连载小说,言情,玄幻,故事结构",
      });
    }

    async function loadWorkflow() {
      loading.workflow = true;
      try {
        workflow.value = await ctx.requestApi("/api/stories/workflow", {}, 10000);
      } finally {
        loading.workflow = false;
      }
    }

    async function createBlueprint() {
      loading.blueprint = true;
      try {
        blueprint.value = await ctx.requestApi("/api/stories/planning/blueprint", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(blueprintForm),
        }, 15000);
        blueprintPromise.value = blueprint.value?.book_profile?.promise || "";
        if (!storyDraft.name && blueprint.value?.book_profile?.title) {
          storyDraft.name = blueprint.value.book_profile.title;
        }
        storyDraft.genre = normalizeStoryGenre(blueprint.value?.book_profile?.genre || blueprintForm.genre || storyDraft.genre);
        ctx.setNotice("开书蓝图已生成，先确认方向，再进入章节。");
      } catch (err) {
        ctx.setError(`开书策划失败：${err.message}`);
      } finally {
        loading.blueprint = false;
      }
    }

    function openStoryDraft() {
      storyDraft.visible = true;
      storyDraft.error = "";
      if (!storyDraft.name) {
        storyDraft.name = blueprint.value?.book_profile?.title || blueprintForm.title || "";
      }
      storyDraft.genre = normalizeStoryGenre(blueprint.value?.book_profile?.genre || blueprintForm.genre || storyDraft.genre);
    }

    async function createStoryInline() {
      const name = storyDraft.name.trim();
      if (!name) {
        storyDraft.error = "先填写故事名称。";
        return null;
      }
      loading.createStory = true;
      storyDraft.error = "";
      try {
        const story = await ctx.requestApi("/api/stories", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            genre: normalizeStoryGenre(storyDraft.genre),
            style_notes: blueprintPromise.value || blueprint.value?.book_profile?.promise || "",
          }),
        }, 15000);
        await ctx.loadStories();
        ctx.selectedStoryId.value = story.id;
        storyDraft.visible = false;
        ctx.setNotice(`故事「${story.name || name}」已创建。`);
        return story;
      } catch (err) {
        storyDraft.error = err.message || "创建故事失败";
        return null;
      } finally {
        loading.createStory = false;
      }
    }

    async function saveBlueprintToStory() {
      if (!blueprint.value) {
        ctx.setError("请先生成开书蓝图。");
        return;
      }
      loading.saveBlueprint = true;
      try {
        let storyId = ctx.selectedStoryId.value;
        if (!storyId) {
          storyDraft.name = storyDraft.name || blueprint.value?.book_profile?.title || blueprintForm.title;
          storyDraft.genre = normalizeStoryGenre(storyDraft.genre || blueprint.value?.book_profile?.genre || blueprintForm.genre);
          const story = await createStoryInline();
          storyId = story?.id;
        }
        if (!storyId) {
          ctx.setError("请先选择或创建一个故事档案。");
          return;
        }
        const bookProfile = {
          ...(blueprint.value.book_profile || {}),
          title: blueprint.value?.book_profile?.title || blueprintForm.title,
          genre: blueprint.value?.book_profile?.genre || blueprintForm.genre,
          promise: blueprintPromise.value.trim(),
        };
        await ctx.requestApi(`/api/stories/${storyId}/bible/blueprint`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            book_profile: bookProfile,
            questions: blueprint.value.questions || [],
            chapter_outline: blueprint.value.chapter_outline || [],
          }),
        }, 15000);
        await ctx.loadStories();
        ctx.setNotice("故事承诺和开书蓝图已录入故事档案，下一步可以诊断或生成章节 Brief。");
      } catch (err) {
        ctx.setError(`保存故事承诺失败：${err.message}`);
      } finally {
        loading.saveBlueprint = false;
      }
    }

    async function diagnoseStory() {
      if (!ctx.selectedStoryId.value) {
        ctx.setError("请先选择一个故事。");
        return;
      }
      loading.diagnosis = true;
      try {
        diagnosis.value = await ctx.requestApi(`/api/stories/${ctx.selectedStoryId.value}/diagnose`, {}, 15000);
        ctx.setNotice(`故事诊断完成：${storyScoreLabel(diagnosis.value.score)}。`);
      } catch (err) {
        ctx.setError(`故事诊断失败：${err.message}`);
      } finally {
        loading.diagnosis = false;
      }
    }

    async function createChapterBrief() {
      if (!ctx.selectedStoryId.value) {
        ctx.setError("请先选择一个故事。");
        return;
      }
      loading.brief = true;
      try {
        chapterBrief.value = await ctx.requestApi(`/api/stories/${ctx.selectedStoryId.value}/chapter-brief`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_note: chapterNote.value }),
        }, 15000);
        ctx.setNotice(`第 ${chapterBrief.value.chapter_number} 章 Brief 已生成，确认后再写正文。`);
      } catch (err) {
        ctx.setError(`章节 Brief 生成失败：${err.message}`);
      } finally {
        loading.brief = false;
      }
    }

    async function generateChapterFromBrief() {
      if (!ctx.selectedStoryId.value) {
        ctx.setError("请先选择一个故事。");
        return;
      }
      loading.chapter = true;
      try {
        const result = await ctx.requestApi(`/api/stories/${ctx.selectedStoryId.value}/chapters/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            brief: chapterBrief.value,
            user_note: chapterNote.value,
            wechat_skill_id: selectedNovelSkillId.value || "wechat_ai_writing_workshop_v1",
          }),
        }, 90000);
        const chNum = result?.story_chapter_saved;
        const review = result?.fanqie_review;
        if (chNum && review && !review.pass) {
          const issues = (review.issues || []).join("；");
          ctx.setError(`第 ${chNum} 章已保存，但番茄审核可能不通过：${issues || "请人工复核"}`);
        } else if (chNum) {
          ctx.setNotice(`第 ${chNum} 章已生成并保存，可以去「查看/推送章节」里审核。`);
        } else {
          ctx.setNotice("章节已生成，请在章节管理里查看。");
        }
        await ctx.loadStories();
        if (ctx.selectedStory.value) await ctx.openStoryManage(ctx.selectedStory.value);
      } catch (err) {
        ctx.setError(`章节生成失败：${err.message}`);
      } finally {
        loading.chapter = false;
      }
    }

    function syncBlueprintTitleFromStory() {
      if (!blueprintForm.title && selectedStoryName.value) blueprintForm.title = selectedStoryName.value;
    }

    onMounted(async () => {
      await Promise.allSettled([loadWorkflow(), ctx.loadStories(), ctx.fanqieLoadSettings(), ctx.loadPresetTopicsAndSkills()]);
      ensureNovelSkillSelected();
      syncBlueprintTitleFromStory();
    });

    return {
      ...ctx,
      workflow,
      diagnosis,
      chapterBrief,
      loading,
      blueprintForm,
      blueprint,
      blueprintPromise,
      chapterNote,
      selectedNovelSkillId,
      storyDraft,
      novelSkills,
      selectedNovelSkill,
      selectedStoryName,
      storyNextAction,
      uploadNovelSkill,
      ensureNovelSkillSelected,
      openStoryDraft,
      createStoryInline,
      saveBlueprintToStory,
      loadWorkflow,
      createBlueprint,
      diagnoseStory,
      createChapterBrief,
      generateChapterFromBrief,
      storyMetricClass,
      formatStoryStep,
      storyScoreLabel,
    };
  }
};
</script>

<template>
  <div v-if="activeTab === 'novels'" class="novel-page">
    <section class="panel novel-workflow-panel">
      <div class="panel-header">
        <div>
          <h2>小说工程台</h2>
          <div class="meta">小说单独走一套流程：先定一本书，再定章节脉络，最后逐章生成和审核。</div>
        </div>
        <button class="btn secondary" :disabled="loading.workflow" @click="loadWorkflow">
          {{ loading.workflow ? "加载中..." : "刷新流程" }}
        </button>
      </div>
      <div class="novel-next-action">{{ storyNextAction }}</div>
      <div v-if="workflow?.steps?.length" class="novel-step-grid">
        <div v-for="(step, index) in workflow.steps" :key="step.key" class="novel-step">
          <span>{{ String(index + 1).padStart(2, "0") }}</span>
          <strong>{{ step.label }}</strong>
          <p>{{ step.desc }}</p>
        </div>
      </div>
    </section>

    <section class="panel novel-skill-panel">
      <div class="panel-header">
        <div>
          <h2>0. 小说 Skill</h2>
          <div class="meta">先选这本书要用哪套写法。这里的 Skill 只约束小说，不会套公众号工具测评或小红书知识笔记。</div>
        </div>
        <div class="novel-actions compact">
          <button class="btn secondary small" @click="loadPresetTopicsAndSkills().then(ensureNovelSkillSelected)">刷新 Skill</button>
          <button class="btn-upload-skill" @click="uploadNovelSkill">+ 上传小说 Skill</button>
        </div>
      </div>
      <div v-if="!novelSkills.length" class="novel-empty">
        还没有小说 Skill。可以先上传一个 .md 文件，或保留默认的“公众号·言情玄幻连载”。
      </div>
      <div v-else class="novel-skill-grid">
        <article
          v-for="skill in novelSkills"
          :key="skill.id"
          class="skill-card novel-skill-card"
          :class="{ selected: selectedNovelSkillId === skill.id }"
          @click="selectedNovelSkillId = skill.id"
        >
          <div class="skill-card-header">
            <strong>{{ skill.name }}</strong>
            <span v-if="selectedNovelSkillId === skill.id" class="skill-selected-badge">✓ 已选</span>
            <button
              class="skill-delete-btn"
              :title="skill.builtin ? '隐藏这个内置 Skill' : '删除此 Skill'"
              @click.stop="deleteSkill(skill.id, skill.name).then(ensureNovelSkillSelected)"
            >×</button>
          </div>
          <p class="skill-desc">{{ skill.description }}</p>
          <div class="skill-tags">
            <span v-for="tag in skill.persona_tags || []" :key="tag" class="skill-tag">{{ tag }}</span>
          </div>
          <div v-if="skill.example" class="skill-example">
            <div class="skill-example-label">示例</div>
            <div class="skill-example-title">{{ skill.example.title }}</div>
            <div v-if="skill.example.summary" class="skill-example-summary">{{ skill.example.summary }}</div>
            <div v-else-if="skill.example.body" class="skill-example-summary">{{ skill.example.body.slice(0, 90) }}...</div>
          </div>
        </article>
      </div>
    </section>

    <section class="panel novel-planner-panel">
      <div class="panel-header">
        <div>
          <h2>1. 开书策划</h2>
          <div class="meta">先确认主题框架，避免写到第十章才发现方向错了。</div>
        </div>
        <button class="btn accent" :disabled="loading.blueprint" @click="createBlueprint">
          {{ loading.blueprint ? "生成中..." : "生成开书蓝图" }}
        </button>
      </div>
      <div class="novel-form-grid">
        <label class="field">
          <span>书名</span>
          <input v-model="blueprintForm.title" :placeholder="selectedStoryName || '例：烬月灯'" />
        </label>
        <label class="field">
          <span>类型</span>
          <select v-model="blueprintForm.genre">
            <option value="romance_fantasy">言情玄幻</option>
            <option value="fantasy">玄幻</option>
            <option value="romance">言情</option>
          </select>
        </label>
        <label class="field wide">
          <span>一句话想法</span>
          <textarea v-model="blueprintForm.idea" rows="3" placeholder="例：一个被献祭的少女发现月神灯里困着未来的自己。"></textarea>
        </label>
        <label class="field">
          <span>读者</span>
          <input v-model="blueprintForm.audience" />
        </label>
        <label class="field">
          <span>文风</span>
          <input v-model="blueprintForm.tone" />
        </label>
      </div>
      <div v-if="blueprint" class="blueprint-card">
        <strong>{{ blueprint.book_profile.title }} · {{ blueprint.book_profile.genre }}</strong>
        <p>{{ blueprint.book_profile.one_sentence }}</p>
        <label class="field wide blueprint-promise-field">
          <span>故事承诺（会写入故事档案，后面每章都按它校准）</span>
          <textarea
            v-model="blueprintPromise"
            rows="3"
            placeholder="例：女主每一卷都要在爱情、命运和自我选择之间付出代价，并逐步夺回主动权。"
          ></textarea>
        </label>
        <div class="blueprint-questions">
          <span v-for="q in blueprint.questions" :key="q">{{ q }}</span>
        </div>
        <div class="chapter-outline">
          <div v-for="item in blueprint.chapter_outline" :key="item.chapter">
            <b>第 {{ item.chapter }} 章</b>
            <span>{{ item.goal }}</span>
          </div>
        </div>
        <div class="novel-actions compact">
          <button class="btn primary small" :disabled="loading.saveBlueprint" @click="saveBlueprintToStory">
            {{ loading.saveBlueprint ? "保存中..." : selectedStoryId ? "保存承诺到当前故事" : "创建故事并保存承诺" }}
          </button>
          <button class="btn secondary small" @click="openStoryDraft">新建为另一本文档</button>
        </div>
      </div>
    </section>

    <section class="panel novel-story-panel">
      <div class="panel-header">
        <div>
          <h2>2. 故事档案与诊断</h2>
          <div class="meta">这里看“这本书能不能继续写”，不是单纯看文笔。</div>
        </div>
        <button class="btn secondary" @click="loadStories">刷新故事</button>
      </div>

      <div class="story-selector-block novel-selector">
        <div class="story-selector-row">
          <select class="story-select" v-model="selectedStoryId">
            <option value="">选择故事档案</option>
            <option v-for="s in stories" :key="s.id" :value="s.id">
              {{ s.name }} · 已写 {{ s.last_chapter_number || 0 }} 章
            </option>
          </select>
          <button class="btn secondary small" @click="openStoryDraft">+ 新建故事</button>
          <button v-if="selectedStory" class="btn secondary small" @click="openStoryManage(selectedStory)">查看章节</button>
          <button class="btn primary small" :disabled="!selectedStoryId || loading.diagnosis" @click="diagnoseStory">
            {{ loading.diagnosis ? "诊断中..." : "诊断当前故事" }}
          </button>
        </div>
        <div v-if="storyDraft.visible" class="inline-story-form">
          <label class="field">
            <span>故事名称</span>
            <input v-model="storyDraft.name" placeholder="例：烬月灯" />
          </label>
          <label class="field">
            <span>类型</span>
            <select v-model="storyDraft.genre">
              <option value="romance_fantasy">言情玄幻</option>
              <option value="fantasy">玄幻</option>
              <option value="romance">言情</option>
            </select>
          </label>
          <div class="inline-story-actions">
            <button class="btn accent small" :disabled="loading.createStory" @click="createStoryInline">
              {{ loading.createStory ? "创建中..." : "确认创建" }}
            </button>
            <button class="btn secondary small" @click="storyDraft.visible = false">取消</button>
            <span v-if="storyDraft.error" class="inline-error">{{ storyDraft.error }}</span>
          </div>
        </div>
      </div>

      <div v-if="diagnosis" class="diagnosis-card">
        <div class="diagnosis-score">
          <strong>{{ diagnosis.score }}/100</strong>
          <span>{{ diagnosis.level }}</span>
          <em>{{ diagnosis.chapter_count }} 章 · {{ diagnosis.open_thread_count }} 条未解悬念</em>
        </div>
        <div v-if="diagnosis.hard_issues?.length" class="diagnosis-issues">
          <b>最影响审核/推荐的问题</b>
          <span v-for="issue in diagnosis.hard_issues" :key="issue">{{ issue }}</span>
        </div>
        <div class="metric-grid">
          <div v-for="metric in diagnosis.metrics" :key="metric.key" class="metric-card" :class="storyMetricClass(metric)">
            <strong>{{ metric.label }}</strong>
            <span>{{ metric.count }} 章命中</span>
            <p>{{ metric.suggestion }}</p>
          </div>
        </div>
        <div class="next-actions">
          <b>下一步按这个做</b>
          <span v-for="action in diagnosis.next_actions" :key="action">{{ action }}</span>
        </div>
      </div>
    </section>

    <section class="panel novel-chapter-panel">
      <div class="panel-header">
        <div>
          <h2>3. 本章 Brief → 逐章生成</h2>
          <div class="meta">每章先定目标、冲突、关系变化和禁忌，再用当前小说 Skill 生成下一章。</div>
        </div>
        <button class="btn primary" :disabled="!selectedStoryId || loading.brief" @click="createChapterBrief">
          {{ loading.brief ? "生成中..." : "生成下一章 Brief" }}
        </button>
      </div>
      <div class="novel-current-skill">
        当前写作 Skill：
        <strong>{{ selectedNovelSkill?.name || "未选择" }}</strong>
        <span v-if="selectedNovelSkill">{{ selectedNovelSkill.description }}</span>
      </div>
      <label class="field">
        <span>这一章你的想法（可选）</span>
        <textarea v-model="chapterNote" rows="3" placeholder="例：这一章希望女主第一次意识到男主隐瞒了身份，但不要立刻揭穿。"></textarea>
      </label>
      <div v-if="chapterBrief" class="brief-card">
        <strong>{{ chapterBrief.story_name }} · 第 {{ chapterBrief.chapter_number }} 章</strong>
        <p>{{ chapterBrief.title_hint }}</p>
        <div class="brief-columns">
          <div>
            <b>必须做到</b>
            <span v-for="item in chapterBrief.must_do" :key="item">{{ item }}</span>
          </div>
          <div>
            <b>不要踩坑</b>
            <span v-for="item in chapterBrief.do_not_do" :key="item">{{ item }}</span>
          </div>
        </div>
      </div>
      <div class="novel-actions">
        <button class="btn accent" :disabled="loading.chapter || !selectedStoryId || !selectedNovelSkillId" @click="generateChapterFromBrief">
          {{ loading.chapter ? "生成中..." : "按 Brief 生成下一章" }}
        </button>
        <button v-if="selectedStory" class="btn secondary" @click="openStoryManage(selectedStory)">查看/推送章节</button>
      </div>
    </section>

    <section class="panel fanqie-panel standalone">
      <div class="fanqie-panel-head" @click="fanqieLoadSettings(); fanqie.loginVisible = !fanqie.loginVisible">
        <span class="fanqie-logo">番茄小说发布配置</span>
        <span class="fanqie-status-dot" :class="fanqie.logged_in ? 'online' : 'offline'"></span>
        <span class="fanqie-status-text">{{ fanqie.logged_in ? `已登录：${fanqie.username || '创作者'}` : '未登录' }}</span>
        <span style="margin-left:auto;font-size:11px;color:#6a8aaa;">{{ fanqie.loginVisible ? '收起' : '展开' }}</span>
      </div>
      <div v-if="fanqie.loginVisible" class="fanqie-panel-body">
        <label class="fanqie-field">
          <span>番茄作品名（可留空）</span>
          <input v-model="fanqie.workName" placeholder="和番茄小说创作中心的作品名一致" @blur="fanqieSaveSettings" />
        </label>
        <label class="fanqie-field">
          <span>Book ID（推荐）</span>
          <input v-model="fanqie.bookId" placeholder="从章节管理 URL 获取" @blur="fanqieSaveSettings" />
        </label>
        <div v-if="fanqie.logged_in && !fanqie.showCookieImport" class="fanqie-logged">
          <span class="fanqie-status-dot online" style="display:inline-block;margin-right:6px;"></span>
          <span class="fanqie-status-text">Cookie 有效{{ fanqie.cookieImportedAt ? `，导入于 ${fanqie.cookieImportedAt}` : '' }}</span>
          <button class="btn secondary small" style="margin-left:10px" @click="fanqie.showCookieImport = true; fanqie.message = ''">
            重新导入 Cookie
          </button>
        </div>
        <div v-if="!fanqie.logged_in || fanqie.showCookieImport" class="fanqie-login-area">
          <p class="fanqie-msg">Cookie 授权：打开 fanqienovel.com 后，用 Cookie-Editor 导出 JSON 粘贴到这里。</p>
          <textarea v-model="fanqie.cookieInput" class="fanqie-cookie-input" rows="4" placeholder='[{"name":"...","value":"..."}]'></textarea>
          <button class="btn accent small" :disabled="fanqie.importingCookies || !fanqie.cookieInput?.trim()" @click="fanqieImportCookies">
            {{ fanqie.importingCookies ? '导入中…' : '导入 Cookie 并验证' }}
          </button>
          <p v-if="fanqie.message" class="fanqie-msg" :class="{ err: fanqie.status === 'failed' }">{{ fanqie.message }}</p>
        </div>
      </div>
    </section>

    <div v-if="uploadSkillModal.visible" class="skill-upload-modal-overlay" @click.self="uploadSkillModal.visible = false">
      <div class="skill-upload-modal">
        <div class="modal-head">
          <strong>上传小说 Skill</strong>
          <button class="modal-close" @click="uploadSkillModal.visible = false">✕</button>
        </div>
        <div class="modal-body">
          <label class="modal-field">
            <span>Skill 名称</span>
            <input v-model="uploadSkillModal.name" type="text" placeholder="例：言情玄幻强钩子连载" />
          </label>
          <label class="modal-field">
            <span>描述（一句话）</span>
            <input v-model="uploadSkillModal.description" type="text" placeholder="例：强冲突、强情绪、章末悬念，适合番茄连载。" />
          </label>
          <label class="modal-field">
            <span>标签（逗号分隔）</span>
            <input v-model="uploadSkillModal.tags" type="text" placeholder="例：言情,玄幻,连载,悬念" />
          </label>
          <label class="modal-field">
            <span>选择 .md 文件</span>
            <input type="file" accept=".md" @change="uploadSkillModal.file = $event.target.files[0]" />
          </label>
          <p class="modal-tip">上传后会自动标记为 fiction_serial，只在小说工程台里用于章节生成。</p>
          <p v-if="uploadSkillModal.error" class="modal-error">{{ uploadSkillModal.error }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn secondary small" @click="uploadSkillModal.visible = false">取消</button>
          <button class="btn accent small" :disabled="uploadSkillModal.uploading" @click="submitUploadSkill().then(ensureNovelSkillSelected)">
            {{ uploadSkillModal.uploading ? '上传中...' : '确认上传' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
