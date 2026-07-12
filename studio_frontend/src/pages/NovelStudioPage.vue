<script>
import { computed, reactive, ref, onMounted, watch } from "vue";
import { useStudioContext } from "./useStudioContext.js";
import {
  nextStoryAction,
  storyMetricClass,
  storyScoreLabel,
  formatStoryStep,
  novelOsModuleStatus,
  novelOsPlanPreview,
  storyProductionStatus,
  commandCenterMetrics,
  aiTeamStatus,
} from "./NovelStudioPage.logic.js";

export default {
  name: "NovelStudioPage",
  setup() {
    const ctx = useStudioContext("NovelStudioPage");
    const workflow = ref(null);
    const diagnosis = ref(null);
    const chapterBrief = ref(null);
    const books = ref([]);
    const selectedBookId = ref("");
    const editingBookId = ref("");
    const loading = reactive({
      workflow: false,
      diagnosis: false,
      blueprint: false,
      saveBlueprint: false,
      createStory: false,
      books: false,
      deleteBook: "",
      brief: false,
      chapter: false,
    });
    const blueprintForm = reactive({
      title: "",
      genre: "romance_fantasy",
      idea: "",
      audience: "喜欢言情玄幻、强剧情和关系拉扯的女性读者",
      tone: "有画面感，情绪克制但有张力，章末留钩子",
      market_positioning: "平台连载型强情绪故事，优先追读、完读和章节钩子",
      reader_pain: "现实压力下渴望被理解、被看见，并看到主角一步步夺回主动权",
      emotional_core: "压抑处境中的选择、成长、希望和关系确认",
      worldview_seed: "",
      protagonist_seed: "",
      real_event_strategy: {
        based_on_real_event: false,
        event_source: "news",
        adaptation_level: "medium",
        risk_avoidance: "人物、地点、时间线和关键事件均虚构化，不影射具体个人，保留现实情绪但避免复刻真实案件。",
      },
      core_design: {
        satisfaction_design: "弱势处境中靠智慧破局，阶段性获得尊重、资源和同盟",
        emotion_curve: "压抑开局 -> 发现机会 -> 小胜释放 -> 新危机牵引",
        reader_profile: "喜欢强情绪、快节奏、女性成长和关系拉扯的连载读者",
        commercial_tags: "番茄,女频,成长,逆袭,强钩子",
      },
      chapter_count: 100,
      first_volume_count: 10,
    });
    const blueprint = ref(null);
    const blueprintPromise = ref("");
    const chapterNote = ref("");
    const selectedNovelSkillId = ref("");
    const userMode = ref("novice");
    const storyDraft = reactive({
      visible: false,
      name: "",
      genre: "romance_fantasy",
      error: "",
    });

    const selectedStoryName = computed(() => ctx.selectedStory.value?.name || "");
    const novelSkills = computed(() => (
      ctx.channelSkillsList.value || []
    ).filter((skill) => skill.channel === "wechat" && skill.content_kind === "fiction_serial"));
    const selectedNovelSkill = computed(() => novelSkills.value.find((skill) => skill.id === selectedNovelSkillId.value) || null);
    const storyNextAction = computed(() => nextStoryAction({
      hasStory: Boolean(ctx.selectedStoryId.value),
      hasDiagnosis: Boolean(diagnosis.value),
      hasBrief: Boolean(chapterBrief.value),
    }));
    const novelOsModules = computed(() => novelOsModuleStatus({ blueprint: blueprint.value, diagnosis: diagnosis.value, chapterBrief: chapterBrief.value }));
    const planPreview = computed(() => novelOsPlanPreview(blueprint.value?.hundred_chapter_plan || [], 12));
    const commandMetrics = computed(() => commandCenterMetrics({
      story: ctx.selectedStory.value,
      diagnosis: diagnosis.value,
      chapterBrief: chapterBrief.value,
      blueprint: blueprint.value,
    }));
    const aiTeam = computed(() => aiTeamStatus({
      hasBlueprint: Boolean(blueprint.value),
      hasStory: Boolean(ctx.selectedStoryId.value),
      hasBrief: Boolean(chapterBrief.value),
      generating: loading.chapter,
    }));
    const selectedBook = computed(() => books.value.find((book) => book.id === selectedBookId.value) || null);
    const projectCards = computed(() => (books.value || []).map((book) => ({
      ...book,
      name: book.title,
      production_status: book.plot_outline?.length ? "策划完成" : "创意阶段",
      last_chapter_number: book.chapter_count || 0,
      quality_score: book.quality_score || "--",
    })));

    function normalizeStoryGenre(raw) {
      const value = String(raw || "").trim();
      if (["romance_fantasy", "fantasy", "fantasy_upgrade", "xianxia", "romance", "modern_romance"].includes(value)) return value;
      if (["urban", "transmigration", "female_lead_ancient", "eastern_mysticism", "sci_fi"].includes(value)) return value;
      if (["言情玄幻", "言情玄幻连载", "玄幻言情"].includes(value)) return "romance_fantasy";
      if (["修仙", "修仙升级", "仙侠"].includes(value)) return "xianxia";
      if (["玄幻升级"].includes(value)) return "fantasy_upgrade";
      if (["现代言情", "现代言情连载"].includes(value)) return "modern_romance";
      if (["都市", "都市连载"].includes(value)) return "urban";
      if (["穿越", "穿越连载"].includes(value)) return "transmigration";
      if (["古装大女主"].includes(value)) return "female_lead_ancient";
      if (["东方玄学"].includes(value)) return "eastern_mysticism";
      if (["科幻", "科幻连载"].includes(value)) return "sci_fi";
      return "romance_fantasy";
    }

    function skillMatchesGenre(skill, genre) {
      const haystack = `${skill.id || ""} ${skill.name || ""} ${(skill.persona_tags || []).join(" ")}`;
      const matchers = {
        romance_fantasy: ["言情玄幻", "romance_fantasy", "ai_writing_workshop"],
        xianxia: ["修仙", "仙侠", "xianxia", "cultivation"],
        fantasy_upgrade: ["玄幻升级", "fantasy_upgrade"],
        fantasy: ["玄幻升级", "玄幻", "fantasy_upgrade", "fantasy"],
        romance: ["现代言情", "言情", "modern_romance"],
        modern_romance: ["现代言情", "modern_romance"],
        urban: ["都市", "urban", "modern_romance"],
        transmigration: ["穿越", "transmigration", "fantasy_upgrade"],
        female_lead_ancient: ["古装大女主", "女主", "言情", "romance_fantasy"],
        eastern_mysticism: ["东方玄学", "玄学", "悬疑", "xianxia"],
        sci_fi: ["科幻", "sci_fi", "fantasy_upgrade"],
      };
      return (matchers[genre] || []).some((needle) => haystack.includes(needle));
    }

    function syncSkillWithGenre({ force = false } = {}) {
      const genre = normalizeStoryGenre(blueprintForm.genre);
      if (!force && selectedNovelSkillId.value && novelSkills.value.some((skill) => skill.id === selectedNovelSkillId.value)) return;
      const preferredIds = {
        romance_fantasy: ["wechat_ai_writing_workshop_v1"],
        xianxia: ["wechat_xianxia_cultivation_serial_v1"],
        fantasy_upgrade: ["wechat_fantasy_upgrade_serial_v1"],
        fantasy: ["wechat_fantasy_upgrade_serial_v1", "wechat_ai_writing_workshop_v1"],
        romance: ["wechat_modern_romance_serial_v1", "wechat_ai_writing_workshop_v1"],
        modern_romance: ["wechat_modern_romance_serial_v1"],
        urban: ["wechat_modern_romance_serial_v1", "wechat_ai_writing_workshop_v1"],
        transmigration: ["wechat_fantasy_upgrade_serial_v1", "wechat_ai_writing_workshop_v1"],
        female_lead_ancient: ["wechat_ai_writing_workshop_v1"],
        eastern_mysticism: ["wechat_xianxia_cultivation_serial_v1", "wechat_ai_writing_workshop_v1"],
        sci_fi: ["wechat_fantasy_upgrade_serial_v1", "wechat_ai_writing_workshop_v1"],
      };
      const preferred = (preferredIds[genre] || [])
        .map((id) => novelSkills.value.find((skill) => skill.id === id))
        .find(Boolean);
      const matched = preferred || novelSkills.value.find((skill) => skillMatchesGenre(skill, genre));
      selectedNovelSkillId.value = matched?.id || novelSkills.value[0]?.id || "";
    }

    function ensureNovelSkillSelected() {
      if (selectedNovelSkillId.value && novelSkills.value.some((skill) => skill.id === selectedNovelSkillId.value)) return;
      syncSkillWithGenre({ force: true });
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

    async function loadBooks() {
      loading.books = true;
      try {
        const result = await ctx.requestApi("/books", {}, 10000);
        books.value = Array.isArray(result?.items) ? result.items : [];
        if (!selectedBookId.value && books.value[0]) {
          selectedBookId.value = books.value[0].id;
        }
      } catch (err) {
        ctx.setError(`小说列表加载失败：${err.message}`);
      } finally {
        loading.books = false;
      }
    }

    function collectBookBlueprintInput() {
      return {
        title: blueprintForm.title.trim(),
        genre: normalizeStoryGenre(blueprintForm.genre),
        hook: blueprintForm.idea.trim(),
        idea: blueprintForm.idea.trim(),
        audience: blueprintForm.audience,
        tone: blueprintForm.tone,
        market_positioning: blueprintForm.market_positioning,
        reader_pain: blueprintForm.reader_pain,
        emotional_core: blueprintForm.emotional_core,
        worldview_seed: blueprintForm.worldview_seed,
        protagonist_seed: blueprintForm.protagonist_seed,
        chapter_count: blueprintForm.chapter_count,
        first_volume_count: blueprintForm.first_volume_count,
        real_event_strategy: {
          ...blueprintForm.real_event_strategy,
          based_on_real_event: Boolean(blueprintForm.real_event_strategy.based_on_real_event),
        },
        core_design: { ...blueprintForm.core_design },
      };
    }

    async function generateBlueprint(input) {
      return await ctx.requestApi("/api/ai/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }, 30000);
    }

    function bookToBlueprint(book) {
      if (book?.blueprint?.book_profile) return book.blueprint;
      return {
        book_profile: {
          title: book?.title || blueprintForm.title,
          genre: book?.genre || blueprintForm.genre,
          one_sentence: book?.hook || blueprintForm.idea,
          promise: book?.core_design?.satisfaction_design || blueprintPromise.value,
        },
        topic_center: {
          direction: book?.genre || blueprintForm.genre,
          market_positioning: book?.core_design?.commercial_tags || blueprintForm.market_positioning,
          audience_profile: book?.core_design?.reader_profile || blueprintForm.audience,
          emotion_value: book?.core_design?.emotion_curve || blueprintForm.emotional_core,
          commercial_potential: book?.core_design?.satisfaction_design || "",
        },
        world_bible: book?.world_setting || {},
        character_life_system: {
          protagonist: Array.isArray(book?.characters) ? book.characters[0] : null,
          supporting_cast: Array.isArray(book?.characters) ? book.characters.slice(1) : [],
        },
        chapter_outline: Array.isArray(book?.plot_outline) ? book.plot_outline : [],
        hundred_chapter_plan: Array.isArray(book?.plot_outline) ? book.plot_outline : [],
      };
    }

    function fillFormFromBook(book) {
      if (!book) return;
      blueprintForm.title = book.title || "";
      blueprintForm.genre = normalizeStoryGenre(book.genre);
      blueprintForm.idea = book.hook || "";
      blueprintForm.worldview_seed = book.world_setting?.time_background || book.world_setting?.power_system || "";
      const protagonist = Array.isArray(book.characters) ? book.characters[0] : null;
      blueprintForm.protagonist_seed = protagonist?.name || protagonist?.background || "";
      blueprintForm.core_design = {
        ...blueprintForm.core_design,
        ...(book.core_design || {}),
      };
      blueprintForm.real_event_strategy = {
        ...blueprintForm.real_event_strategy,
        ...(book.real_event_strategy || {}),
      };
      blueprint.value = bookToBlueprint(book);
      blueprintPromise.value = book.core_design?.satisfaction_design || blueprint.value?.book_profile?.promise || "";
    }

    async function createBookBlueprint() {
      if (loading.blueprint) return;
      const input = collectBookBlueprintInput();
      if (!input.title || !input.hook) {
        ctx.setError("请先填写书名和一句话想法。");
        return;
      }
      loading.blueprint = true;
      try {
        const generated = await generateBlueprint(input);
        const saved = await ctx.requestApi("/books", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...generated,
            core_design: generated.core_design || input.core_design,
            real_event_strategy: generated.real_event_strategy || input.real_event_strategy,
          }),
        }, 15000);
        blueprint.value = bookToBlueprint(saved);
        blueprintPromise.value = saved.core_design?.satisfaction_design || blueprint.value?.book_profile?.promise || "";
        selectedBookId.value = saved.id;
        editingBookId.value = "";
        storyDraft.name = saved.title || input.title;
        storyDraft.genre = normalizeStoryGenre(saved.genre || input.genre);
        await loadBooks();
        ctx.setNotice("小说创建成功，开书蓝图已写入数据库。");
      } catch (err) {
        ctx.setError(`开书蓝图生成失败：${err.message}`);
      } finally {
        loading.blueprint = false;
      }
    }

    async function createBlueprint() {
      return createBookBlueprint();
    }

    function continueBook(book) {
      selectedBookId.value = book.id;
      fillFormFromBook(book);
      ctx.setNotice(`已载入「${book.title}」，可以继续生成章节 Brief 或编辑蓝图。`);
    }

    function editBook(book) {
      selectedBookId.value = book.id;
      editingBookId.value = book.id;
      fillFormFromBook(book);
      ctx.setNotice("已进入编辑状态，修改后可重新生成并保存新蓝图。");
    }

    async function deleteBook(book) {
      if (!book?.id) return;
      if (!window.confirm(`确定删除《${book.title || "未命名小说"}》吗？此操作会从数据库移除该小说项目。`)) return;
      loading.deleteBook = book.id;
      try {
        await ctx.requestApi(`/books/${encodeURIComponent(book.id)}`, { method: "DELETE" }, 10000);
        if (selectedBookId.value === book.id) selectedBookId.value = "";
        await loadBooks();
        ctx.setNotice("小说已删除。");
      } catch (err) {
        ctx.setError(`删除小说失败：${err.message}`);
      } finally {
        loading.deleteBook = "";
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

    async function runOneClickProduction() {
      if (!blueprint.value) {
        await createBlueprint();
      }
      if (!ctx.selectedStoryId.value) {
        storyDraft.name = storyDraft.name || blueprint.value?.book_profile?.title || blueprintForm.title || "未命名小说";
        storyDraft.genre = normalizeStoryGenre(storyDraft.genre || blueprintForm.genre);
        await saveBlueprintToStory();
      }
      if (ctx.selectedStoryId.value && !diagnosis.value) {
        await diagnoseStory();
      }
      if (ctx.selectedStoryId.value && !chapterBrief.value) {
        await createChapterBrief();
      }
    }

    function syncBlueprintTitleFromStory() {
      if (!blueprintForm.title && selectedStoryName.value) blueprintForm.title = selectedStoryName.value;
    }

    onMounted(async () => {
      await Promise.allSettled([loadWorkflow(), loadBooks(), ctx.loadStories(), ctx.fanqieLoadSettings(), ctx.loadPresetTopicsAndSkills()]);
      ensureNovelSkillSelected();
      syncBlueprintTitleFromStory();
    });

    watch(
      () => blueprintForm.genre,
      () => syncSkillWithGenre({ force: true }),
    );

    return {
      ...ctx,
      workflow,
      diagnosis,
      chapterBrief,
      books,
      selectedBookId,
      selectedBook,
      editingBookId,
      loading,
      blueprintForm,
      blueprint,
      blueprintPromise,
      chapterNote,
      selectedNovelSkillId,
      userMode,
      storyDraft,
      novelSkills,
      selectedNovelSkill,
      selectedStoryName,
      storyNextAction,
      novelOsModules,
      planPreview,
      commandMetrics,
      aiTeam,
      projectCards,
      storyProductionStatus,
      uploadNovelSkill,
      loadBooks,
      generateBlueprint,
      createBookBlueprint,
      continueBook,
      editBook,
      deleteBook,
      ensureNovelSkillSelected,
      openStoryDraft,
      createStoryInline,
      saveBlueprintToStory,
      loadWorkflow,
      createBlueprint,
      diagnoseStory,
      createChapterBrief,
      generateChapterFromBrief,
      runOneClickProduction,
      storyMetricClass,
      formatStoryStep,
      storyScoreLabel,
      novelOsPlanPreview,
    };
  }
};
</script>

<template>
  <div v-if="activeTab === 'novels'" class="novel-page">
    <section class="panel novel-product-hero">
      <div>
        <span>SERIAL FICTION OPS</span>
        <h2>AI小说生产工作台</h2>
        <p>输入一个想法，AI总编带领团队完成策划、设定、人物、章节、审核和发布。</p>
      </div>
      <div class="novel-mode-switch">
        <button type="button" :class="{ active: userMode === 'novice' }" @click="userMode = 'novice'">新手模式</button>
        <button type="button" :class="{ active: userMode === 'professional' }" @click="userMode = 'professional'">专业模式</button>
      </div>
    </section>

    <section class="panel novel-project-center">
      <div class="panel-header">
        <div>
          <h2>我的小说</h2>
          <div class="meta">管理项目进度，选择一本书进入生产。</div>
        </div>
        <button class="btn accent" :disabled="loading.blueprint" @click="createBookBlueprint">
          {{ loading.blueprint ? "创建中..." : "+ 创建小说" }}
        </button>
      </div>
      <div v-if="loading.books" class="novel-empty">正在读取小说项目...</div>
      <div v-else-if="!projectCards.length" class="novel-empty">还没有小说项目。先输入创意，或点击创建小说。</div>
      <div v-else class="novel-project-grid">
        <article
          v-for="book in projectCards"
          :key="book.id"
          class="novel-project-card"
          :class="{ active: selectedBookId === book.id }"
          @click="continueBook(book)"
        >
          <div>
            <strong>{{ book.title }}</strong>
            <span>{{ book.genre || "未分类" }} · {{ book.production_status }}</span>
          </div>
          <div class="novel-project-meta">
            <span>规划 {{ book.plot_outline?.length || 0 }} 节点</span>
            <span>质量 {{ book.quality_score }}</span>
          </div>
          <div class="novel-actions compact">
            <button class="btn secondary small" @click.stop="continueBook(book)">继续写</button>
            <button class="btn secondary small" @click.stop="editBook(book)">编辑</button>
            <button class="btn secondary small danger" :disabled="loading.deleteBook === book.id" @click.stop="deleteBook(book)">
              {{ loading.deleteBook === book.id ? "删除中" : "删除" }}
            </button>
          </div>
        </article>
      </div>
    </section>

    <section class="panel novel-command-center">
      <div class="panel-header">
        <div>
          <h2>小说生产驾驶舱</h2>
          <div class="meta">当前任务、质量、风险和AI团队状态集中在这里。</div>
        </div>
        <button class="btn accent" :disabled="loading.blueprint || loading.createStory || loading.diagnosis || loading.brief" @click="runOneClickProduction">
          {{ loading.blueprint || loading.createStory || loading.diagnosis || loading.brief ? "生产中..." : "开始AI小说生产" }}
        </button>
      </div>
      <div class="novel-command-main">
        <div class="novel-current-book">
          <span>当前小说</span>
          <strong>{{ selectedBook?.title || selectedStory?.name || blueprintForm.title || "未创建" }}</strong>
          <p>{{ commandMetrics.currentTask }}</p>
        </div>
        <div class="novel-dashboard-grid">
          <span>章节 <strong>{{ commandMetrics.completed }}/{{ commandMetrics.planned }}</strong></span>
          <span>质量评分 <strong>{{ commandMetrics.qualityScore }}</strong></span>
          <span>读者兴趣 <strong>{{ commandMetrics.readerInterest }}</strong></span>
          <span>风险 <strong>{{ commandMetrics.risk }}</strong></span>
        </div>
      </div>
      <div class="novel-team-status">
        <article v-for="member in aiTeam" :key="member.role">
          <strong>{{ member.role }}</strong>
          <span>{{ member.duty }}</span>
          <em>{{ member.status }}</em>
        </article>
      </div>
    </section>

    <section class="panel novel-wizard-panel">
      <div class="panel-header">
        <div>
          <h2>AI小说创作向导</h2>
          <div class="meta">按步骤把一个创意变成可持续生产的小说项目。</div>
        </div>
      </div>
      <div class="novel-wizard-steps">
        <article :class="{ done: blueprintForm.idea }"><span>01</span><strong>输入创意</strong><p>类型、一句话故事、喜欢方向、目标读者。</p></article>
        <article :class="{ done: blueprint?.topic_center }"><span>02</span><strong>AI总编分析</strong><p>市场定位、商业潜力、核心卖点和风险。</p></article>
        <article :class="{ done: blueprint?.world_bible }"><span>03</span><strong>小说DNA</strong><p>主题、世界规则、人物方向、核心冲突。</p></article>
        <article :class="{ done: selectedNovelSkillId }"><span>04</span><strong>配置AI团队</strong><p>总编、市场、世界观、人物、剧情、作者、审核。</p></article>
        <article :class="{ done: chapterBrief }"><span>05</span><strong>章节生产</strong><p>Brief、正文、节奏检测、逻辑审核、平台审核。</p></article>
      </div>
    </section>

    <details class="panel novel-workflow-panel novel-advanced-panel" :open="userMode === 'professional'">
      <summary>
        <strong>专业模式：系统架构与AI团队配置</strong>
        <span>Skill、Memory、商业智能、总编工作流等高级配置</span>
      </summary>
      <div class="panel-header">
        <div>
          <h2>Novel OS 2.0 · AI小说工业化生产系统</h2>
          <div class="meta">用总编、策划、剧情、人物、文字和审核编辑的协作方式，长期生产中文网文。</div>
        </div>
        <button class="btn secondary" :disabled="loading.workflow" @click="loadWorkflow">
          {{ loading.workflow ? "加载中..." : "刷新流程" }}
        </button>
      </div>
      <div class="novel-next-action">{{ storyNextAction }}</div>
      <div v-if="workflow?.charter" class="novel-charter-card">
        <div>
          <span>最高使命</span>
          <strong>{{ workflow.charter.mission }}</strong>
          <p>{{ workflow.charter.creative_belief }}</p>
        </div>
        <div class="novel-quality-tags">
          <span v-for="target in workflow.charter.quality_targets" :key="target">{{ target }}</span>
        </div>
      </div>
      <div class="novel-os-command">
        <div v-for="module in novelOsModules" :key="module.key" class="novel-os-module">
          <span>{{ module.label }}</span>
          <strong>{{ module.status }}</strong>
          <p>{{ module.note }}</p>
        </div>
      </div>
      <div v-if="workflow?.steps?.length" class="novel-step-grid">
        <div v-for="(step, index) in workflow.steps" :key="step.key" class="novel-step">
          <span>{{ String(index + 1).padStart(2, "0") }}</span>
          <strong>{{ step.label }}</strong>
          <p>{{ step.desc }}</p>
        </div>
      </div>
      <div v-if="workflow?.agents?.length" class="novel-agent-grid">
        <article v-for="agent in workflow.agents" :key="agent.role">
          <strong>{{ agent.role }}</strong>
          <p>{{ agent.job }}</p>
        </article>
      </div>
      <div v-if="workflow?.skills?.length" class="novel-professional-skill-grid">
        <article v-for="skill in workflow.skills" :key="skill.id">
          <span>{{ skill.id }}</span>
          <strong>{{ skill.name }}</strong>
          <p>{{ skill.output }}</p>
        </article>
      </div>
      <div v-if="workflow?.skill_plugin_architecture" class="novel-plugin-architecture">
        <div>
          <div class="novel-section-title">{{ workflow.skill_plugin_architecture.name }}</div>
          <p>{{ workflow.skill_plugin_architecture.description }}</p>
          <small>{{ workflow.skill_plugin_architecture.collaboration_rule }}</small>
        </div>
        <div class="novel-plugin-tags">
          <span v-for="capability in workflow.skill_plugin_architecture.capabilities" :key="capability">{{ capability }}</span>
        </div>
      </div>
      <div v-if="workflow?.skill_calling_rules?.length" class="novel-call-rule-grid">
        <article v-for="rule in workflow.skill_calling_rules" :key="rule.stage">
          <strong>{{ rule.stage }}</strong>
          <span>{{ rule.skills.join(" / ") }}</span>
          <p>{{ rule.handoff }}</p>
        </article>
      </div>
      <div v-if="workflow?.skill_collaboration_flow?.length" class="novel-collaboration-flow">
        <span v-for="step in workflow.skill_collaboration_flow" :key="step">{{ step }}</span>
      </div>
      <div v-if="workflow?.master_workflow" class="novel-master-workflow">
        <div class="novel-section-title">{{ workflow.master_workflow.name }} 工作流程</div>
        <p>{{ workflow.master_workflow.positioning }}</p>
        <div class="novel-master-stage-grid">
          <article v-for="stage in workflow.master_workflow.stages" :key="stage.key">
            <span>{{ stage.title }}</span>
            <strong>{{ stage.goal }}</strong>
            <small>Skill：{{ stage.skills.join(" / ") }}</small>
          </article>
        </div>
      </div>
      <div v-if="workflow?.novel_memory_engine" class="novel-memory-engine">
        <div class="novel-section-title">{{ workflow.novel_memory_engine.name }}</div>
        <p>{{ workflow.novel_memory_engine.positioning }}</p>
        <strong>{{ workflow.novel_memory_engine.core_rule }}</strong>
        <div class="novel-memory-layer-grid">
          <article v-for="layer in workflow.novel_memory_engine.memory_layers" :key="layer.key">
            <span>{{ layer.name }}</span>
            <strong>{{ layer.purpose }}</strong>
            <small>{{ layer.fields.join(" / ") }}</small>
          </article>
        </div>
      </div>
      <div v-if="workflow?.commercial_intelligence" class="novel-commercial-panel">
        <div class="novel-section-title">{{ workflow.commercial_intelligence.name }}</div>
        <p>{{ workflow.commercial_intelligence.positioning }}</p>
        <div class="novel-commercial-agent-grid">
          <article v-for="agent in workflow.commercial_intelligence.agents" :key="agent.id">
            <span>{{ agent.id }}</span>
            <strong>{{ agent.name }}</strong>
            <p>{{ agent.responsibility }}</p>
          </article>
        </div>
        <div class="novel-analytics-preview">
          <span>完成章节：{{ workflow.commercial_intelligence.analytics_dashboard.example.completed_chapters }}</span>
          <span>质量评分：{{ workflow.commercial_intelligence.analytics_dashboard.example.quality_score }}</span>
          <span>读者兴趣：{{ workflow.commercial_intelligence.analytics_dashboard.example.reader_interest }}</span>
          <span>风险：{{ workflow.commercial_intelligence.analytics_dashboard.example.risk }}</span>
          <strong>{{ workflow.commercial_intelligence.analytics_dashboard.example.current_issue }}</strong>
          <em>{{ workflow.commercial_intelligence.analytics_dashboard.example.suggestion }}</em>
        </div>
      </div>
    </details>

    <section v-if="userMode === 'professional'" class="panel novel-skill-panel">
      <div class="panel-header">
        <div>
          <h2>0. 小说 Skill</h2>
          <div class="meta">小说基础规范会自动叠加。这里选的是题材写法：言情玄幻、修仙升级、玄幻升级或现代言情。</div>
        </div>
        <div class="novel-actions compact">
          <button class="btn secondary small" @click="loadPresetTopicsAndSkills().then(ensureNovelSkillSelected)">刷新 Skill</button>
          <button class="btn-upload-skill" @click="uploadNovelSkill">+ 上传小说 Skill</button>
        </div>
      </div>
      <div v-if="!novelSkills.length" class="novel-empty">
        还没有小说 Skill。可以先上传一个 .md 文件，或使用默认的小说类型 Skill。
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
        <button class="btn accent" :disabled="loading.blueprint" @click="createBookBlueprint">
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
            <option value="urban">都市</option>
            <option value="xianxia">修仙升级</option>
            <option value="fantasy_upgrade">玄幻升级</option>
            <option value="fantasy">玄幻</option>
            <option value="transmigration">穿越</option>
            <option value="female_lead_ancient">古装大女主</option>
            <option value="eastern_mysticism">东方玄学</option>
            <option value="sci_fi">科幻</option>
            <option value="romance">言情</option>
            <option value="modern_romance">现代言情</option>
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
        <label class="field">
          <span>市场定位</span>
          <input v-model="blueprintForm.market_positioning" placeholder="例：番茄强情绪女频，追读优先" />
        </label>
        <label class="field">
          <span>读者压力/痛点</span>
          <input v-model="blueprintForm.reader_pain" placeholder="例：就业焦虑、家庭压力、未来不确定" />
        </label>
        <label class="field wide">
          <span>核心情绪价值</span>
          <textarea v-model="blueprintForm.emotional_core" rows="2" placeholder="例：被误解后仍然成长，靠智慧和同盟夺回主动权。"></textarea>
        </label>
        <label class="field">
          <span>是否基于真实事件</span>
          <select v-model="blueprintForm.real_event_strategy.based_on_real_event">
            <option :value="false">否，完全虚构</option>
            <option :value="true">是，需要改编</option>
          </select>
        </label>
        <label class="field">
          <span>事件来源</span>
          <select v-model="blueprintForm.real_event_strategy.event_source">
            <option value="news">新闻</option>
            <option value="history">历史</option>
            <option value="personal">个人经历</option>
          </select>
        </label>
        <label class="field">
          <span>改编程度</span>
          <select v-model="blueprintForm.real_event_strategy.adaptation_level">
            <option value="low">低：保留大框架</option>
            <option value="medium">中：重组人物与事件</option>
            <option value="high">高：只保留情绪内核</option>
          </select>
        </label>
        <label class="field">
          <span>商业标签</span>
          <input v-model="blueprintForm.core_design.commercial_tags" placeholder="例：番茄,女频,逆袭,强钩子" />
        </label>
        <label class="field wide">
          <span>风险规避策略</span>
          <textarea v-model="blueprintForm.real_event_strategy.risk_avoidance" rows="2" placeholder="例：人物地点虚构化，不复刻真实案件细节。"></textarea>
        </label>
        <label class="field wide">
          <span>爽点设计</span>
          <textarea v-model="blueprintForm.core_design.satisfaction_design" rows="2" placeholder="例：主角靠智慧破局，每3章一次阶段性小胜。"></textarea>
        </label>
        <label class="field">
          <span>情绪曲线</span>
          <input v-model="blueprintForm.core_design.emotion_curve" placeholder="例：压抑 -> 破局 -> 爽感释放 -> 新悬念" />
        </label>
        <label class="field">
          <span>读者画像</span>
          <input v-model="blueprintForm.core_design.reader_profile" placeholder="例：高压现实中需要成长代偿的女频读者" />
        </label>
        <label class="field">
          <span>世界观种子</span>
          <input v-model="blueprintForm.worldview_seed" placeholder="时间背景、社会体系或力量规则" />
        </label>
        <label class="field">
          <span>主角生命种子</span>
          <input v-model="blueprintForm.protagonist_seed" placeholder="背景、缺陷、心理矛盾或成长方向" />
        </label>
        <label class="field">
          <span>规划章节数</span>
          <input v-model.number="blueprintForm.chapter_count" inputmode="numeric" placeholder="100" />
        </label>
        <label class="field">
          <span>第一卷章数</span>
          <input v-model.number="blueprintForm.first_volume_count" inputmode="numeric" placeholder="20" />
        </label>
      </div>
      <div v-if="blueprint" class="blueprint-card">
        <strong>{{ blueprint.book_profile.title }} · {{ blueprint.book_profile.genre }}</strong>
        <p>{{ blueprint.book_profile.one_sentence }}</p>
        <div v-if="blueprint.chief_editor_charter" class="novel-os-section">
          <div class="novel-section-title">超级总编创作宪章</div>
          <div class="novel-principle-grid">
            <article v-for="principle in blueprint.chief_editor_charter.principles" :key="principle.title">
              <strong>{{ principle.title }}</strong>
              <p>{{ principle.rule }}</p>
              <span>{{ principle.checklist.join(" · ") }}</span>
            </article>
          </div>
        </div>
        <div v-if="blueprint.topic_center" class="novel-os-section">
          <div class="novel-section-title">小说选题中心</div>
          <div class="novel-insight-grid">
            <span>
              小说方向
              <strong>{{ blueprint.topic_center.direction }}</strong>
            </span>
            <span>
              市场定位
              <strong>{{ blueprint.topic_center.market_positioning }}</strong>
            </span>
            <span>
              用户画像
              <strong>{{ blueprint.topic_center.audience_profile }}</strong>
            </span>
            <span>
              情绪价值
              <strong>{{ blueprint.topic_center.emotion_value }}</strong>
            </span>
          </div>
        </div>
        <div v-if="blueprint.social_emotion_database?.length" class="novel-os-section">
          <div class="novel-section-title">社会情绪数据库</div>
          <div class="novel-emotion-grid">
            <article v-for="item in blueprint.social_emotion_database.slice(0, 6)" :key="item.key">
              <strong>{{ item.label }}</strong>
              <p>{{ item.pain }}</p>
              <span>{{ item.positive_resolution }}</span>
            </article>
          </div>
        </div>
        <div v-if="blueprint.world_bible" class="novel-os-section">
          <div class="novel-section-title">世界观设计模块</div>
          <div class="novel-insight-grid">
            <span>
              时间背景
              <strong>{{ blueprint.world_bible.time_background }}</strong>
            </span>
            <span>
              社会体系
              <strong>{{ blueprint.world_bible.society_system }}</strong>
            </span>
            <span>
              规则体系
              <strong>{{ blueprint.world_bible.rule_system }}</strong>
            </span>
            <span>
              力量体系
              <strong>{{ blueprint.world_bible.power_system }}</strong>
            </span>
          </div>
        </div>
        <div v-if="blueprint.character_life_system?.length" class="novel-os-section">
          <div class="novel-section-title">人物生命系统</div>
          <div class="novel-character-grid">
            <article v-for="character in blueprint.character_life_system" :key="character.name">
              <strong>{{ character.name }} · {{ character.role }}</strong>
              <p>{{ character.background }}</p>
              <span>心理矛盾：{{ character.inner_conflict }}</span>
              <span>成长路线：{{ character.growth_route }}</span>
            </article>
          </div>
        </div>
        <div v-if="planPreview.length" class="novel-os-section">
          <div class="novel-section-title">100章节规划系统</div>
          <div class="novel-plan-table">
            <div class="novel-plan-head">
              <span>章</span>
              <span>目标</span>
              <span>冲突</span>
              <span>悬念</span>
            </div>
            <div v-for="item in planPreview" :key="item.chapter" class="novel-plan-row">
              <span>V{{ item.volume }} · {{ item.chapter }}</span>
              <strong>{{ item.chapter_goal }}</strong>
              <em>{{ item.plot_conflict }}</em>
              <small>{{ item.hook }}</small>
            </div>
          </div>
        </div>
        <div v-if="blueprint.professional_skills?.length" class="novel-os-section">
          <div class="novel-section-title">专业 Skill 调度</div>
          <div class="novel-professional-skill-grid compact">
            <article v-for="skill in blueprint.professional_skills" :key="skill.id">
              <span>{{ skill.id }}</span>
              <strong>{{ skill.name }}</strong>
              <p>{{ skill.output }}</p>
            </article>
          </div>
        </div>
        <div v-if="blueprint.skill_plugins?.length" class="novel-os-section">
          <div class="novel-section-title">AI小说生产团队 Skill插件体系</div>
          <div class="novel-plugin-grid">
            <article v-for="plugin in blueprint.skill_plugins" :key="plugin.skill_id">
              <div>
                <span>{{ plugin.skill_id }} · v{{ plugin.version }}</span>
                <strong>{{ plugin.skill_name }}</strong>
                <em>{{ plugin.enabled_status ? "启用" : "关闭" }} · 优先级 {{ plugin.priority }}</em>
              </div>
              <p>{{ plugin.description }}</p>
              <small>触发：{{ plugin.trigger_condition }}</small>
              <small>评价：{{ plugin.evaluation_rule }}</small>
            </article>
          </div>
        </div>
        <div v-if="blueprint.skill_calling_rules?.length" class="novel-os-section">
          <div class="novel-section-title">Skill调用规则与质量评价</div>
          <div class="novel-call-rule-grid compact">
            <article v-for="rule in blueprint.skill_calling_rules" :key="rule.stage">
              <strong>{{ rule.stage }}</strong>
              <span>{{ rule.skills.join(" / ") }}</span>
              <p>{{ rule.handoff }}</p>
            </article>
          </div>
          <div class="novel-editor-rule">{{ blueprint.skill_plugin_architecture?.retry_rule }}</div>
        </div>
        <div v-if="blueprint.master_chief_editor_workflow" class="novel-os-section">
          <div class="novel-section-title">总编评分机制</div>
          <div class="novel-score-rubric">
            <article v-for="item in blueprint.master_chief_editor_workflow.chapter_score_rubric" :key="item.key">
              <span>{{ item.points }}分</span>
              <strong>{{ item.label }}</strong>
              <p>{{ item.pass_rule }}</p>
            </article>
          </div>
          <div class="novel-editor-rule">{{ blueprint.master_chief_editor_workflow.optimization_rule }}</div>
        </div>
        <div v-if="blueprint.novel_memory_engine" class="novel-os-section">
          <div class="novel-section-title">Novel Memory Engine 长期记忆引擎</div>
          <div class="novel-memory-layer-grid compact">
            <article v-for="layer in blueprint.novel_memory_engine.memory_layers" :key="layer.key">
              <span>{{ layer.name }}</span>
              <strong>{{ layer.purpose }}</strong>
              <small>{{ layer.read_rule }}</small>
            </article>
          </div>
          <div class="novel-memory-manager-grid">
            <article v-for="manager in blueprint.novel_memory_engine.managers" :key="manager.name">
              <strong>{{ manager.name }}</strong>
              <p>{{ manager.responsibility }}</p>
              <span>{{ manager.example_guard || manager.example_state || manager.output }}</span>
            </article>
          </div>
          <div class="novel-context-package">
            <strong>Chapter Context Package</strong>
            <p>{{ blueprint.novel_memory_engine.chapter_context_package.description }}</p>
            <span v-for="field in blueprint.novel_memory_engine.chapter_context_package.fields" :key="field">{{ field }}</span>
          </div>
          <div class="novel-memory-flow">
            <span v-for="step in blueprint.novel_memory_engine.update_pipeline" :key="step">{{ step }}</span>
          </div>
          <div class="novel-db-table-grid">
            <article v-for="table in blueprint.novel_memory_engine.database_tables" :key="table.name">
              <strong>{{ table.name }}</strong>
              <p>{{ table.purpose }}</p>
              <small>{{ table.fields.join(" · ") }}</small>
            </article>
          </div>
        </div>
        <div v-if="blueprint.commercial_intelligence" class="novel-os-section">
          <div class="novel-section-title">小说商业智能与自动优化系统</div>
          <div class="novel-commercial-dimension-grid">
            <article v-for="dimension in blueprint.commercial_intelligence.bestseller_analysis_dimensions" :key="dimension.key">
              <span>{{ dimension.name }}</span>
              <strong>{{ dimension.output }}</strong>
              <p>{{ (dimension.extract || dimension.categories || []).join(" / ") }}</p>
            </article>
          </div>
          <div class="novel-reader-grid">
            <article v-for="reader in blueprint.commercial_intelligence.reader_personas" :key="reader.id">
              <strong>{{ reader.name }} · {{ reader.profile }}</strong>
              <span>{{ reader.focus.join(" / ") }}</span>
            </article>
          </div>
          <div class="novel-score-rubric">
            <article v-for="item in blueprint.commercial_intelligence.novel_quality_score.dimensions" :key="item.key">
              <span>{{ item.points }}分</span>
              <strong>{{ item.label }}</strong>
              <p>{{ blueprint.commercial_intelligence.novel_quality_score.low_score_action }}</p>
            </article>
          </div>
          <div class="novel-memory-flow">
            <span v-for="step in blueprint.commercial_intelligence.feedback_loop" :key="step">{{ step }}</span>
          </div>
          <div class="novel-pattern-grid">
            <article v-for="pattern in blueprint.commercial_intelligence.story_pattern_database" :key="pattern.name">
              <span>{{ pattern.type }}</span>
              <strong>{{ pattern.name }}</strong>
              <p>{{ pattern.usage }}</p>
            </article>
          </div>
          <div class="novel-db-table-grid">
            <article v-for="table in blueprint.commercial_intelligence.database_tables" :key="table.name">
              <strong>{{ table.name }}</strong>
              <p>{{ table.purpose }}</p>
              <small>{{ table.fields.join(" · ") }}</small>
            </article>
          </div>
        </div>
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
            <option value="urban">都市</option>
            <option value="xianxia">修仙升级</option>
            <option value="fantasy_upgrade">玄幻升级</option>
            <option value="fantasy">玄幻</option>
            <option value="transmigration">穿越</option>
            <option value="female_lead_ancient">古装大女主</option>
            <option value="eastern_mysticism">东方玄学</option>
            <option value="sci_fi">科幻</option>
            <option value="romance">言情</option>
            <option value="modern_romance">现代言情</option>
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
          <h2>Chapter Studio · 每日章节生产</h2>
          <div class="meta">先确认章节目标，再生成正文，并进入节奏、逻辑和平台安全审核。</div>
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
        <button class="btn secondary" :disabled="loading.chapter || !selectedStoryId" @click="createChapterBrief">重新生成</button>
        <button class="btn secondary" :disabled="!selectedStory" @click="openStoryManage(selectedStory)">AI优化/人工修改</button>
        <button v-if="selectedStory" class="btn secondary" @click="openStoryManage(selectedStory)">查看/推送章节</button>
      </div>
    </section>

    <section class="panel fanqie-panel standalone">
      <div class="fanqie-panel-head" @click="fanqieLoadSettings(); fanqie.loginVisible = !fanqie.loginVisible">
        <span class="fanqie-logo">Publishing Center · 番茄小说发布中心</span>
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
        <div class="novel-publish-checklist">
          <span>章节格式转换</span>
          <span>标题优化</span>
          <span>简介/标签建议</span>
          <span>低俗与违规风险</span>
          <span>逻辑与完整度</span>
        </div>
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
