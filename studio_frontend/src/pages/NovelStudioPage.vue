<script>
import { computed, nextTick, reactive, ref, onMounted, watch } from "vue";
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
    const rejectedChapter = ref(null);
    const storyArchive = ref(null);
    const books = ref([]);
    const currentBookId = ref("");
    const selectedBookId = currentBookId;
    const plannerBookId = ref("");
    const editingBookId = ref("");
    const plannerPanel = ref(null);
    const plannerExpanded = ref(false);
    const loading = reactive({
      workflow: false,
      diagnosis: false,
      blueprint: false,
      saveBlueprint: false,
      createStory: false,
      books: false,
      deleteBook: "",
      regenerateChapter: "",
      deleteChapter: "",
      saveChapter: "",
      brief: false,
      chapter: false,
      storyUnitExtract: false,
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
        enabled: false,
        source_type: "个人",
        source_type_custom: "",
        adaptation_level: "中",
        risk_control: "人物、地点、时间线和关键事件均虚构化，不影射具体个人，保留现实情绪但避免复刻真实案件。",
      },
      core_design: {
        爽点设计: "弱势处境中靠智慧破局，阶段性获得尊重、资源和同盟",
        情绪曲线: "压抑开局 -> 发现机会 -> 小胜释放 -> 新危机牵引",
        读者画像: "喜欢强情绪、快节奏、女性成长和关系拉扯的连载读者",
        平台标签: "番茄,女频,成长,逆袭,强钩子",
      },
      chapter_count: 500,
      phase_count: 5,
      story_mainline: "",
      volume_plans: [],
      story_units: [],
    });
    const blueprint = ref(null);
    const blueprintPromise = ref("");
    const chapterNote = ref("");
    const chapterPlanDraft = ref("");
    const chapterPlanDraftNumber = ref(0);
    const editingChapterKey = ref("");
    const editingChapterDraft = ref("");
    const storyUnitImportText = ref("");
    const savedChapterAiKey = localStorage.getItem("novelChapterAiKey") || "";
    const selectedChapterAiKey = ref(savedChapterAiKey.includes(":") ? savedChapterAiKey : "qwen:qwen3.7-plus");
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
    const chapterAiOptions = [
      { key: "qwen:qwen3.7-plus", provider: "qwen", model: "qwen3.7-plus", label: "通义千问 qwen3.7-plus（优先）" },
      { key: "qwen:qwen-plus-2025-07-28", provider: "qwen", model: "qwen-plus-2025-07-28", label: "通义千问 qwen-plus-2025-07-28" },
      { key: "qwen:qwen-max", provider: "qwen", model: "qwen-max", label: "通义千问 qwen-max" },
      { key: "deepseek:deepseek-chat", provider: "deepseek", model: "deepseek-chat", label: "DeepSeek Chat" },
      { key: "deepseek:deepseek-v4-flash:thinking", provider: "deepseek", model: "deepseek-v4-flash", thinking: true, reasoningEffort: "high", label: "DeepSeek V4 Flash · 思维模式" },
      { key: "deepseek:deepseek-v4-pro:thinking", provider: "deepseek", model: "deepseek-v4-pro", thinking: true, reasoningEffort: "max", label: "DeepSeek V4 Pro · 思维模式" },
      { key: "deepseek:deepseek-v4-flash", provider: "deepseek", model: "deepseek-v4-flash", label: "DeepSeek V4 Flash · 非思维" },
      { key: "openai:gpt-4o-mini", provider: "openai", model: "gpt-4o-mini", label: "OpenAI gpt-4o-mini" },
    ];
    const selectedChapterAi = computed(() => chapterAiOptions.find((item) => item.key === selectedChapterAiKey.value) || chapterAiOptions[0]);
    const storyNextAction = computed(() => nextStoryAction({
      hasStory: Boolean(ctx.selectedStoryId.value),
      hasDiagnosis: Boolean(diagnosis.value),
      hasBrief: Boolean(chapterBrief.value),
    }));
    const novelOsModules = computed(() => novelOsModuleStatus({ blueprint: blueprint.value, diagnosis: diagnosis.value, chapterBrief: chapterBrief.value }));
    const planPreview = computed(() => novelOsPlanPreview(blueprint.value?.hundred_chapter_plan || [], 12));
    const commandMetrics = computed(() => commandCenterMetrics({
      book: selectedBook.value,
      archive: storyArchive.value,
      latestChapter: latestBookChapter.value,
      diagnosis: diagnosis.value,
      chapterBrief: chapterBrief.value,
      blueprint: blueprint.value,
    }));
    const aiTeam = computed(() => aiTeamStatus({
      hasBlueprint: Boolean(blueprint.value),
      hasStory: Boolean(currentBookId.value),
      hasBrief: Boolean(chapterBrief.value),
      generating: loading.chapter,
    }));
    const selectedBook = computed(() => books.value.find((book) => book.id === selectedBookId.value) || null);
    const latestBookChapter = computed(() => {
      const chapters = Array.isArray(storyArchive.value?.chapters) ? storyArchive.value.chapters : [];
      return [...chapters].sort((a, b) => Number(b.chapter_number || 0) - Number(a.chapter_number || 0))[0] || null;
    });
    const sortedBookChapters = computed(() => {
      const chapters = Array.isArray(storyArchive.value?.chapters) ? storyArchive.value.chapters : [];
      return [...chapters].sort((a, b) => Number(a.chapter_number || 0) - Number(b.chapter_number || 0));
    });
    const nextChapterNumber = computed(() => (sortedBookChapters.value.at(-1)?.chapter_number || 0) + 1);
    const currentBookFanqieTargetKey = computed(() => currentBookId.value ? `book:${currentBookId.value}` : "");
    const selectedFanqieTargetId = computed({
      get() {
        const key = currentBookFanqieTargetKey.value;
        if (!key) return "";
        const saved = ctx.fanqie.chapterTarget?.[key];
        if (saved) return saved;
        const bookTitle = String(selectedBook.value?.title || "").trim();
        const matched = (ctx.fanqie.works || []).find((work) => {
          const workName = String(work.work_name || "").trim();
          return bookTitle && (workName.includes(bookTitle) || bookTitle.includes(workName));
        });
        return matched?.id || ctx.fanqie.works?.[0]?.id || "";
      },
      set(value) {
        const key = currentBookFanqieTargetKey.value;
        if (!key) return;
        ctx.fanqie.chapterTarget[key] = value;
        localStorage.setItem("fanqieChapterTarget", JSON.stringify(ctx.fanqie.chapterTarget || {}));
      },
    });
    const projectCards = computed(() => (books.value || []).map((book) => ({
      ...book,
      name: book.title,
      production_status: book.plot_outline?.length ? "策划完成" : "创意阶段",
      last_chapter_number: book.chapter_count || 0,
      quality_score: book.quality_score || book.commercial_analysis?.score || "--",
    })));

    function formatBookDetail(value) {
      if (value === null || value === undefined || value === "") return "暂无";
      if (Array.isArray(value) || typeof value === "object") {
        return JSON.stringify(value, null, 2);
      }
      return String(value);
    }

    function chapterDisplayContent(chapter) {
      const title = String(chapter?.title || `第${chapter?.chapter_number || ""}章`).trim();
      const content = String(chapter?.content || chapter?.content_markdown || "").trim();
      if (!title) return content;
      return content.startsWith(title) ? content : `${title}\n\n${content}`.trim();
    }

    function chapterEditKey(chapter) {
      return String(chapter?.id || chapter?.chapter_number || "");
    }

    function startEditChapter(chapter) {
      editingChapterKey.value = chapterEditKey(chapter);
      editingChapterDraft.value = chapterDisplayContent(chapter);
    }

    function cancelEditChapter() {
      editingChapterKey.value = "";
      editingChapterDraft.value = "";
    }

    function genericChapterPlanEvent(event) {
      const text = String(event || "");
      const genericTokens = [
        "开局危机", "人物困境", "世界规则", "第一目标", "目标", "本章", "剧情", "章节",
        "推进主线", "制造冲突", "新信息", "读者", "写作", "手法", "节奏", "前慢后快",
        "结尾留钩子", "埋伏笔", "无法解释", "具体事件", "更大的问题", "主角第一次接触",
        "修行世界", "引入危险", "异常事件", "外部压力逼近", "内部选择尚未统一",
      ];
      if (!text.trim()) return true;
      if (genericTokens.some((token) => text.includes(token))) return true;
      return /^开启[【《]/.test(text) || /^用一次/.test(text) || /^一个暂时解释不了/.test(text);
    }

    function concreteChapterPlanEvent(index, title, storyName) {
      const cleanTitle = String(title || `第${nextChapterNumber.value}章`).replace(/^第\s*\d+\s*章[：:、\s]*/, "").trim() || "新的线索";
      const name = storyName || selectedBook.value?.title || "这本书";
      const events = [
        `她沿着「${cleanTitle}」这条线索去找第一个经手人，第一次看见${name}里隐藏的异常痕迹。`,
        "对方拒绝说明真相，却把一个会带来危险的东西塞到她手里，逼她立刻离开现场。",
        "她刚走出门，那个东西在无人触碰的情况下自己变了位置，指向下一处未知地点。",
        "有人在暗处抢先抹掉线索，她必须当场决定追人还是保住手里的证物。",
        "她以为暂时脱身时，证物上多出一个不属于任何人的名字。",
      ];
      return events[Math.min(index, events.length - 1)];
    }

    function formatChapterPlanDraft(brief) {
      const plan = brief?.chapterPlan || {};
      const title = plan.title || plan.chapter_title || plan.name || brief?.title_hint || `第${brief?.chapter_number || nextChapterNumber.value}章`;
      const storyName = selectedBook.value?.title || brief?.story_name || "这本书";
      const events = Array.isArray(plan.event_plan) ? plan.event_plan : [];
      if (events.length) {
        return events.map((item, index) => {
          const rawEvent = typeof item === "string" ? item : item?.event || item?.content || item?.summary || "";
          const event = genericChapterPlanEvent(rawEvent)
            ? concreteChapterPlanEvent(index, title, storyName)
            : rawEvent;
          const advances = typeof item === "object" ? item.advances_mainline || "是" : "是";
          const conflict = typeof item === "object" ? item.creates_conflict || "否" : "否";
          const info = typeof item === "object" ? item.new_information || "是" : "是";
          return `事件${index + 1}：${event}（推进主线：${advances}；制造冲突：${conflict}；新信息：${info}）`;
        }).join("\n");
      }
      const coreEvent = plan.core_event || plan.main_event || plan.unit_event || plan.chapter_goal || plan.goal || plan.summary || "";
      const conflict = plan.conflict || plan.plot_conflict || plan.core_conflict || plan.stage_conflict || "";
      const suspense = plan.suspense || plan.hook || plan.ending_hook || plan.cliffhanger || plan.foreshadowing || "";
      const lines = [
        coreEvent ? `事件1：${genericChapterPlanEvent(coreEvent) ? concreteChapterPlanEvent(0, title, storyName) : coreEvent}（推进主线：是；制造冲突：否；新信息：是）` : "",
        conflict ? `事件2：${genericChapterPlanEvent(conflict) ? concreteChapterPlanEvent(1, title, storyName) : conflict}（推进主线：否；制造冲突：是；新信息：是）` : "",
        suspense ? `事件3：${genericChapterPlanEvent(suspense) ? concreteChapterPlanEvent(2, title, storyName) : suspense}（推进主线：是；制造冲突：是；新信息：是）` : "",
      ].filter(Boolean);
      if (lines.length) return lines.join("\n");
      if (!Object.keys(plan).length) return "";
      return [
        `事件1：${concreteChapterPlanEvent(0, title, storyName)}（推进主线：是；制造冲突：否；新信息：是）`,
        `事件2：${concreteChapterPlanEvent(1, title, storyName)}（推进主线：是；制造冲突：是；新信息：是）`,
        `事件3：${concreteChapterPlanEvent(2, title, storyName)}（推进主线：是；制造冲突：是；新信息：是）`,
      ].join("\n");
    }

    function chapterPlanNumber(plan, index) {
      const raw = plan?.chapter ?? plan?.chapter_number ?? plan?.node ?? plan?.index ?? plan?.order ?? plan?.seq;
      const number = Number(raw);
      return Number.isFinite(number) && number > 0 ? number : index + 1;
    }

    function chapterPlanTitle(plan) {
      return String(plan?.title || plan?.chapter_title || plan?.name || plan?.chapter_goal || plan?.goal || "").trim();
    }

    function chapterPlanList() {
      const bookPlans = Array.isArray(selectedBook.value?.plot_outline) ? selectedBook.value.plot_outline : [];
      const archivePlans = Array.isArray(storyArchive.value?.plot?.chapterPlans) ? storyArchive.value.plot.chapterPlans : [];
      const blueprintPlans = Array.isArray(blueprint.value?.hundred_chapter_plan) ? blueprint.value.hundred_chapter_plan : [];
      return bookPlans.length ? bookPlans : (archivePlans.length ? archivePlans : blueprintPlans);
    }

    function planForNextChapter() {
      const target = Number(nextChapterNumber.value || 1);
      const plans = chapterPlanList();
      return plans.find((item, index) => chapterPlanNumber(item, index) === target)
        || plans[Math.max(0, target - 1)]
        || {};
    }

    const activeChapterBrief = computed(() => {
      const targetNumber = Number(nextChapterNumber.value || 1);
      const briefNumber = Number(chapterBrief.value?.chapter_number || 0);
      return briefNumber === targetNumber ? chapterBrief.value : null;
    });

    function clearStaleChapterBrief() {
      if (!chapterBrief.value) return false;
      const targetNumber = Number(nextChapterNumber.value || 1);
      const briefNumber = Number(chapterBrief.value.chapter_number || 0);
      if (briefNumber === targetNumber) return false;
      chapterBrief.value = null;
      chapterPlanDraftNumber.value = 0;
      return true;
    }

    const dailyChapterEcho = computed(() => {
      const plan = planForNextChapter();
      const brief = activeChapterBrief.value;
      const title = brief?.title_hint || chapterPlanTitle(plan) || `第${nextChapterNumber.value}章`;
      return {
        chapterNumber: brief?.chapter_number || nextChapterNumber.value,
        title,
        hasPlan: Boolean(chapterPlanDraft.value.trim() || Object.keys(plan || {}).length),
      };
    });

    function refreshChapterPlanDraftFromBook({ force = false } = {}) {
      const targetNumber = Number(nextChapterNumber.value || 1);
      const briefWasStale = clearStaleChapterBrief();
      const brief = activeChapterBrief.value;
      if (brief) {
        chapterPlanDraft.value = formatChapterPlanDraft(brief);
        chapterPlanDraftNumber.value = Number(brief.chapter_number || targetNumber);
        return;
      }
      const plan = planForNextChapter();
      const draftBelongsToTarget = Number(chapterPlanDraftNumber.value || 0) === targetNumber;
      if (plan && Object.keys(plan).length && (force || briefWasStale || !draftBelongsToTarget || !chapterPlanDraft.value.trim())) {
        chapterPlanDraft.value = formatChapterPlanDraft({
          chapterPlan: plan,
          chapter_number: targetNumber,
        });
        chapterPlanDraftNumber.value = targetNumber;
      } else if (force || briefWasStale || !draftBelongsToTarget || !chapterPlanDraft.value.trim()) {
        chapterPlanDraft.value = "";
        chapterPlanDraftNumber.value = targetNumber;
      }
    }

    async function advanceToNextChapterPlan() {
      chapterBrief.value = null;
      rejectedChapter.value = null;
      chapterPlanDraft.value = "";
      chapterPlanDraftNumber.value = 0;
      await nextTick();
      refreshChapterPlanDraftFromBook({ force: true });
    }

    async function loadNextChapterBrief({ silent = false } = {}) {
      if (!currentBookId.value || loading.brief) return null;
      loading.brief = true;
      try {
        const brief = await ctx.requestApi(`/books/${encodeURIComponent(currentBookId.value)}/chapter-brief`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_note: chapterNote.value }),
        }, 15000);
        chapterBrief.value = brief;
        rejectedChapter.value = null;
        chapterPlanDraft.value = formatChapterPlanDraft(brief);
        chapterPlanDraftNumber.value = Number(brief.chapter_number || nextChapterNumber.value || 1);
        if (!silent) {
          ctx.setNotice(`第 ${brief.chapter_number} 章 Brief 已生成。Brief 只是计划，请点击“生成正文”继续写章节。`);
        }
        return brief;
      } catch (err) {
        if (!silent) ctx.setError(`章节 Brief 生成失败：${err.message}`);
        return null;
      } finally {
        loading.brief = false;
      }
    }

    function parseChapterPlanDraft() {
      return String(chapterPlanDraft.value || "")
        .split(/\n+/)
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line, index) => {
          const event = line
            .replace(/^事件\s*\d+\s*[：:]\s*/, "")
            .replace(/（推进主线[：:].*$/, "")
            .trim();
          const advances = /推进主线[：:]\s*是/.test(line) ? "是" : (/推进主线[：:]\s*否/.test(line) ? "否" : (index === 1 ? "否" : "是"));
          const conflict = /制造冲突[：:]\s*是/.test(line) ? "是" : (/制造冲突[：:]\s*否/.test(line) ? "否" : (index >= 1 ? "是" : "否"));
          const info = /新信息[：:]\s*否/.test(line) ? "否" : "是";
          const tags = [
            advances === "是" ? "推进主线" : "",
            conflict === "是" ? "冲突" : "",
            index === 2 ? "伏笔" : "",
          ].filter(Boolean);
          return { event, tags, advances_mainline: advances, creates_conflict: conflict, new_information: info };
        })
        .filter((item) => item.event);
    }

    function buildLocalChapterBrief(plan = planForNextChapter()) {
      const title = chapterPlanTitle(plan) || `第${nextChapterNumber.value}章`;
      const eventPlan = parseChapterPlanDraft();
      const fallbackEvents = eventPlan.length ? eventPlan : [
        { event: concreteChapterPlanEvent(0, title, selectedBook.value?.title), tags: ["推进主线"], advances_mainline: "是", creates_conflict: "否", new_information: "是" },
        { event: concreteChapterPlanEvent(1, title, selectedBook.value?.title), tags: ["冲突"], advances_mainline: "是", creates_conflict: "是", new_information: "是" },
        { event: concreteChapterPlanEvent(2, title, selectedBook.value?.title), tags: ["伏笔"], advances_mainline: "是", creates_conflict: "是", new_information: "是" },
      ];
      return {
        bookId: currentBookId.value,
        story_name: selectedBook.value?.title || "",
        chapter_number: nextChapterNumber.value,
        title_hint: title,
        must_do: [
          "按上方剧情计划写具体故事情节，不输出写作说明。",
          "开头直接进入当前场景，用动作、对话和可观察细节推进。",
          "每3段必须出现新动作、新冲突或新线索，禁止复述旧章节。",
          "都市现实类必须符合平台和职业常识：外卖/快递先线上记录、电话、拍照、平台留言、物业或报警，不能收现金或擅自进屋。",
        ],
        do_not_do: [
          "不要写本章目标、推进主线、制造冲突、埋伏笔等元话语。",
          "不要生成空正文、摘要、JSON或结构说明。",
          "不要重复上一章完整场景或旧对白。",
          "不要让外卖员收现金、找零、无人回应却进屋，或让角色跳过平台/物业/报警等现实流程。",
        ],
        chapterPlan: {
          ...(plan || {}),
          event_plan: fallbackEvents,
          scene_beats: fallbackEvents.map((item) => item.event),
        },
      };
    }

    function syncEditedChapterPlan() {
      clearStaleChapterBrief();
      const eventPlan = parseChapterPlanDraft();
      if (!eventPlan.length) return;
      if (!chapterBrief.value) {
        chapterBrief.value = buildLocalChapterBrief();
      }
      chapterBrief.value = {
        ...chapterBrief.value,
        must_do: chapterBrief.value.must_do?.length ? chapterBrief.value.must_do : buildLocalChapterBrief().must_do,
        do_not_do: chapterBrief.value.do_not_do?.length ? chapterBrief.value.do_not_do : buildLocalChapterBrief().do_not_do,
        chapterPlan: {
          ...(chapterBrief.value.chapterPlan || {}),
          event_plan: eventPlan,
          scene_beats: eventPlan.map((item) => item.event),
        },
      };
    }

    function bookDetailSections(book) {
      return [
        {
          label: "基础信息",
          value: {
            id: book.id,
            title: book.title,
            genre: book.genre,
            hook: book.hook,
            created_at: book.created_at,
          },
        },
        { label: "核心设计", value: book.core_design || {} },
        { label: "真实事件改编策略", value: book.real_event_strategy || {} },
        { label: "长篇结构设计", value: book.long_form_plan || {} },
        { label: "世界观设定", value: book.world_setting || {} },
        { label: "人物生命系统", value: book.characters || [] },
        { label: "章节规划", value: book.plot_outline || [] },
        { label: "商业分析", value: book.commercial_analysis || {} },
      ];
    }

    function normalizeStoryGenre(raw) {
      const value = String(raw || "").trim();
      if (["romance_fantasy", "fantasy", "fantasy_upgrade", "xianxia", "romance", "modern_romance"].includes(value)) return value;
      if (["urban", "urban_news_adaptation", "transmigration", "female_lead_ancient", "eastern_mysticism", "sci_fi"].includes(value)) return value;
      if (["言情玄幻", "言情玄幻连载", "玄幻言情"].includes(value)) return "romance_fantasy";
      if (["修仙", "修仙升级", "仙侠"].includes(value)) return "xianxia";
      if (["玄幻升级"].includes(value)) return "fantasy_upgrade";
      if (["现代言情", "现代言情连载"].includes(value)) return "modern_romance";
      if (["都市", "都市连载"].includes(value)) return "urban";
      if (["都市现实新闻改编", "都市现实新闻改编连载", "现实新闻改编"].includes(value)) return "urban_news_adaptation";
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
        urban_news_adaptation: ["都市", "现实", "新闻", "urban", "modern_romance", "ai_writing_workshop"],
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
        urban_news_adaptation: ["wechat_modern_romance_serial_v1", "wechat_ai_writing_workshop_v1"],
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
        if (currentBookId.value && !books.value.some((book) => book.id === currentBookId.value)) {
          currentBookId.value = "";
          storyArchive.value = null;
        }
      } catch (err) {
        ctx.setError(`小说列表加载失败：${err.message}`);
      } finally {
        loading.books = false;
      }
    }

    function freshBookId() {
      return window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    function chapterRangeForPhase(total = 500, count = 5, index = 0) {
      const safeTotal = Math.max(1, Number(total) || 500);
      const safeCount = Math.max(1, Number(count) || 5);
      const start = Math.floor(index * safeTotal / safeCount) + 1;
      const end = Math.floor((index + 1) * safeTotal / safeCount);
      return `${start}-${Math.max(start, end)}`;
    }

    function normalizeVolumeCount(value) {
      return Math.max(1, Math.min(50, Math.floor(Number(value) || 5)));
    }

    function makeEmptyVolumePlan(index = 0) {
      return {
        volume_name: `第${index + 1}卷`,
        chapter_range: chapterRangeForPhase(blueprintForm.chapter_count, blueprintForm.phase_count, index),
        theme: "",
        stage_goal: "",
        core_conflict: "",
        protagonist_growth: "",
        ending_result: "",
        ending_hook: "",
      };
    }

    function makeEmptyStoryUnit() {
      return {
        start_chapter: "",
        end_chapter: "",
        unit_name: "",
        main_event: "",
        stage_conflict: "",
        payoff_emotion: "",
        foreshadowing: "",
        payoff: "",
      };
    }

    function syncVolumePlanCount({ redistributeRanges = true } = {}) {
      const count = normalizeVolumeCount(blueprintForm.phase_count);
      blueprintForm.phase_count = count;
      while (blueprintForm.volume_plans.length < count) {
        blueprintForm.volume_plans.push(makeEmptyVolumePlan(blueprintForm.volume_plans.length));
      }
      if (blueprintForm.volume_plans.length > count) {
        blueprintForm.volume_plans.splice(count);
      }
      blueprintForm.volume_plans.forEach((plan, index) => {
        if (!plan.volume_name) plan.volume_name = `第${index + 1}卷`;
        if (redistributeRanges || !plan.chapter_range) {
          plan.chapter_range = chapterRangeForPhase(blueprintForm.chapter_count, count, index);
        }
      });
    }

    function ensureLongPlanDefaults() {
      if (!blueprintForm.story_mainline) {
        blueprintForm.story_mainline = "一个普通人穿过现实压力和关系考验，最终夺回人生主动权并帮助身边人一起重新开始。";
      }
      syncVolumePlanCount({ redistributeRanges: false });
      if (!blueprintForm.story_units.length) {
        blueprintForm.story_units.push({
          ...makeEmptyStoryUnit(),
          start_chapter: 1,
          end_chapter: 20,
          unit_name: "开局危机",
          main_event: "用一次具体事件把人物困境、世界规则和第一目标推到台前。",
          stage_conflict: "外部压力逼近，内部选择尚未统一。",
          payoff_emotion: "压抑后的第一次行动感。",
          foreshadowing: "一个暂时解释不了的细节指向更大的问题。",
          payoff: "回收开篇危机，同时打开下一阶段入口。",
        });
      }
    }

    function addStoryUnit() {
      blueprintForm.story_units.push(makeEmptyStoryUnit());
    }

    function removeStoryUnit(index) {
      blueprintForm.story_units.splice(index, 1);
      if (!blueprintForm.story_units.length) addStoryUnit();
    }

    function parseChapterRangeText(value, fallbackStart = 1, fallbackEnd = 20) {
      const text = String(value || "").replace(/[－—~到]/g, "-");
      const match = text.match(/(\d+)\s*-\s*(\d+)/);
      if (match) {
        const start = Math.max(1, Number(match[1]) || fallbackStart);
        const end = Math.max(start, Number(match[2]) || fallbackEnd);
        return [start, end];
      }
      return [fallbackStart, fallbackEnd];
    }

    function normalizeStoryUnitFromAi(raw, index = 0) {
      const unit = raw && typeof raw === "object" ? raw : {};
      const fallbackVolume = blueprintForm.volume_plans[index] || blueprintForm.volume_plans[0] || {};
      const [rangeStart, rangeEnd] = parseChapterRangeText(fallbackVolume.chapter_range, index * 20 + 1, index * 20 + 20);
      const start = Number(unit.start_chapter || unit.start || unit.begin || rangeStart) || rangeStart;
      const end = Number(unit.end_chapter || unit.end || unit.finish || rangeEnd) || rangeEnd;
      return {
        ...makeEmptyStoryUnit(),
        start_chapter: Math.max(1, start),
        end_chapter: Math.max(Math.max(1, start), end),
        unit_name: String(unit.unit_name || unit.name || unit.title || fallbackVolume.volume_name || `故事单元 ${index + 1}`).trim(),
        main_event: String(unit.main_event || unit.event || unit.major_event || unit.summary || "").trim(),
        stage_conflict: String(unit.stage_conflict || unit.conflict || unit.obstacle || "").trim(),
        payoff_emotion: String(unit.payoff_emotion || unit.emotion || unit爽点 || unit.payoff_point || "").trim(),
        foreshadowing: String(unit.foreshadowing || unit.foreshadow || unit.hook || unit伏笔 || "").trim(),
        payoff: String(unit.payoff || unit.result || unit回收点 || unit.resolution || "").trim(),
      };
    }

    function parseStoryUnitsJson(text) {
      const raw = String(text || "").trim();
      const jsonBlock = raw.match(/```(?:json)?\s*([\s\S]*?)```/i)?.[1] || raw;
      const arrayText = jsonBlock.match(/\[[\s\S]*\]/)?.[0] || "";
      if (!arrayText) return [];
      try {
        const parsed = JSON.parse(arrayText);
        return Array.isArray(parsed) ? parsed : [];
      } catch (error) {
        return [];
      }
    }

    function localStoryUnitFromText(text) {
      const lines = String(text || "")
        .split(/\n+/)
        .map((line) => line.trim())
        .filter(Boolean);
      const joined = lines.join(" ");
      if (!joined) return [];
      const [start, end] = parseChapterRangeText(joined, 1, 20);
      const nameLine = lines.find((line) => /单元|小主线|卷名|故事/.test(line)) || lines[0] || "故事单元";
      const eventLine = lines.find((line) => /主要事件|事件|发生|讲/.test(line)) || lines[1] || joined.slice(0, 80);
      const conflictLine = lines.find((line) => /冲突|阻碍|压力|危机|矛盾/.test(line)) || "";
      const payoffLine = lines.find((line) => /爽点|情绪|释放|反击|成长/.test(line)) || "";
      const hookLine = lines.find((line) => /伏笔|钩子|悬念|反转|发现/.test(line)) || "";
      const resultLine = lines.find((line) => /回收|结果|解决|收束|兑现/.test(line)) || "";
      return [normalizeStoryUnitFromAi({
        start_chapter: start,
        end_chapter: end,
        unit_name: nameLine.replace(/^(故事单元|小主线名称|卷名|标题)\s*[：:]\s*/, "").slice(0, 40),
        main_event: eventLine.replace(/^(主要事件|事件)\s*[：:]\s*/, ""),
        stage_conflict: conflictLine.replace(/^(阶段冲突|冲突)\s*[：:]\s*/, ""),
        payoff_emotion: payoffLine.replace(/^(爽点\/情绪点|爽点|情绪点)\s*[：:]\s*/, ""),
        foreshadowing: hookLine.replace(/^(伏笔|钩子|悬念)\s*[：:]\s*/, ""),
        payoff: resultLine.replace(/^(回收点|结果|收束)\s*[：:]\s*/, ""),
      })];
    }

    async function fillStoryUnitsFromConversation() {
      const source = storyUnitImportText.value.trim();
      if (!source) {
        ctx.setError("请先粘贴 AI 沟通结果或截图 OCR 后的文字。");
        return;
      }
      loading.storyUnitExtract = true;
      try {
        const prompt = [
          "请从下面的小说讨论记录中提取故事单元规划，只返回 JSON 数组，不要解释。",
          "数组每项字段必须是：start_chapter, end_chapter, unit_name, main_event, stage_conflict, payoff_emotion, foreshadowing, payoff。",
          "如果内容里没有明确章节范围，请根据当前卷规划推断；都市现实新闻改编保持一卷一个故事，玄幻修仙保持一个小副本/事件一个单元。",
          `小说名称：${blueprintForm.title || selectedBook.value?.title || "未命名小说"}`,
          `类型：${blueprintForm.genre}`,
          `卷规划：${JSON.stringify(blueprintForm.volume_plans || [])}`,
          "讨论记录：",
          source,
        ].join("\n");
        const result = await ctx.requestApi("/api/ai-chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            provider: selectedChapterAi.value.provider,
            model: selectedChapterAi.value.model,
            thinking: Boolean(selectedChapterAi.value.thinking),
            reasoning_effort: selectedChapterAi.value.reasoningEffort || "",
            context: "把小说沟通记录结构化成故事单元规划，严格返回 JSON。",
            messages: [{ role: "user", content: prompt }],
          }),
        }, 120000);
        let units = parseStoryUnitsJson(result?.response || "");
        if (!units.length) units = localStoryUnitFromText(source);
        const normalized = units.map((unit, index) => normalizeStoryUnitFromAi(unit, index)).filter((unit) => unit.unit_name || unit.main_event);
        if (!normalized.length) {
          ctx.setError("没有识别到可填入的故事单元，请补充章节范围、主要事件或冲突。");
          return;
        }
        blueprintForm.story_units = normalized;
        ctx.setNotice(`已从沟通结果填入 ${normalized.length} 个故事单元。`);
      } catch (error) {
        const fallback = localStoryUnitFromText(source);
        if (fallback.length) {
          blueprintForm.story_units = fallback;
          ctx.setNotice("AI 提取失败，已使用本地规则填入 1 个故事单元。");
        } else {
          ctx.setError(`故事单元提取失败：${error.message}`);
        }
      } finally {
        loading.storyUnitExtract = false;
      }
    }

    function normalizedLongFormPlan() {
      syncVolumePlanCount({ redistributeRanges: false });
      const volume_plans = blueprintForm.volume_plans.map((plan, index) => ({
        volume_name: String(plan.volume_name || `第${index + 1}卷`).trim(),
        chapter_range: String(plan.chapter_range || chapterRangeForPhase(blueprintForm.chapter_count, blueprintForm.phase_count, index)).trim(),
        theme: String(plan.theme || "").trim(),
        stage_goal: String(plan.stage_goal || "").trim(),
        core_conflict: String(plan.core_conflict || "").trim(),
        protagonist_growth: String(plan.protagonist_growth || "").trim(),
        ending_result: String(plan.ending_result || "").trim(),
        ending_hook: String(plan.ending_hook || "").trim(),
      }));
      const story_units = blueprintForm.story_units
        .map((unit) => ({
          start_chapter: Number(unit.start_chapter) || "",
          end_chapter: Number(unit.end_chapter) || "",
          unit_name: String(unit.unit_name || "").trim(),
          main_event: String(unit.main_event || "").trim(),
          stage_conflict: String(unit.stage_conflict || "").trim(),
          payoff_emotion: String(unit.payoff_emotion || "").trim(),
          foreshadowing: String(unit.foreshadowing || "").trim(),
          payoff: String(unit.payoff || "").trim(),
        }))
        .filter((unit) => unit.unit_name || unit.main_event || unit.start_chapter || unit.end_chapter);
      return {
        total_chapters: Math.max(1, Number(blueprintForm.chapter_count) || 500),
        story_mainline: String(blueprintForm.story_mainline || "").trim(),
        phase_count: normalizeVolumeCount(blueprintForm.phase_count),
        volume_plans,
        story_units,
      };
    }

    function resetBlueprintForm() {
      blueprintForm.title = "";
      blueprintForm.genre = "romance_fantasy";
      blueprintForm.idea = "";
      blueprintForm.audience = "喜欢言情玄幻、强剧情和关系拉扯的女性读者";
      blueprintForm.tone = "有画面感，情绪克制但有张力，章末留钩子";
      blueprintForm.market_positioning = "平台连载型强情绪故事，优先追读、完读和章节钩子";
      blueprintForm.reader_pain = "现实压力下渴望被理解、被看见，并看到主角一步步夺回主动权";
      blueprintForm.emotional_core = "压抑处境中的选择、成长、希望和关系确认";
      blueprintForm.worldview_seed = "";
      blueprintForm.protagonist_seed = "";
      blueprintForm.real_event_strategy = {
        enabled: false,
        source_type: "个人",
        source_type_custom: "",
        adaptation_level: "中",
        risk_control: "人物、地点、时间线和关键事件均虚构化，不影射具体个人，保留现实情绪但避免复刻真实案件。",
      };
      blueprintForm.core_design = {
        爽点设计: "弱势处境中靠智慧破局，阶段性获得尊重、资源和同盟",
        情绪曲线: "压抑开局 -> 发现机会 -> 小胜释放 -> 新危机牵引",
        读者画像: "喜欢强情绪、快节奏、女性成长和关系拉扯的连载读者",
        平台标签: "番茄,女频,成长,逆袭,强钩子",
      };
      blueprintForm.chapter_count = 500;
      blueprintForm.phase_count = 5;
      blueprintForm.story_mainline = "";
      blueprintForm.volume_plans = [];
      blueprintForm.story_units = [];
      ensureLongPlanDefaults();
      blueprint.value = null;
      blueprintPromise.value = "";
    }

    async function scrollToPlanner() {
      plannerExpanded.value = true;
      await nextTick();
      plannerPanel.value?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    }

    function startCreateBook() {
      editingBookId.value = "";
      plannerExpanded.value = true;
      resetBookScopedMemory("");
      resetBlueprintForm();
      scrollToPlanner();
      ctx.setNotice("请先填写开书策划表单，再生成蓝图。");
    }

    function normalizedRealEventStrategy() {
      const strategy = { ...blueprintForm.real_event_strategy };
      const custom = String(strategy.source_type_custom || "").trim();
      if (!strategy.enabled) {
        return {
          enabled: false,
          source_type: strategy.source_type === "__custom__" ? custom : strategy.source_type,
          source_type_custom: custom,
          adaptation_level: "",
          risk_control: "",
        };
      }
      return {
        ...strategy,
        enabled: Boolean(strategy.enabled),
        source_type: strategy.source_type === "__custom__" ? custom : strategy.source_type,
      };
    }

    function collectBookBlueprintInput() {
      const longFormPlan = normalizedLongFormPlan();
      const existingBookId = editingBookId.value || plannerBookId.value;
      return {
        bookId: existingBookId || freshBookId(),
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
        chapter_count: longFormPlan.total_chapters,
        phase_count: longFormPlan.phase_count,
        story_mainline: longFormPlan.story_mainline,
        volume_plans: longFormPlan.volume_plans,
        story_units: longFormPlan.story_units,
        long_form_plan: longFormPlan,
        real_event_strategy: normalizedRealEventStrategy(),
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

    function coreValue(core, cnKey, legacyKey, fallback = "") {
      return core?.[cnKey] || core?.[legacyKey] || fallback;
    }

    function bookToBlueprint(book) {
      if (book?.blueprint?.book_profile) return book.blueprint;
      return {
        book_profile: {
          title: book?.title || blueprintForm.title,
          genre: book?.genre || blueprintForm.genre,
          one_sentence: book?.hook || blueprintForm.idea,
          promise: coreValue(book?.core_design, "爽点设计", "satisfaction_design", blueprintPromise.value),
        },
        topic_center: {
          direction: book?.genre || blueprintForm.genre,
          market_positioning: coreValue(book?.core_design, "平台标签", "commercial_tags", blueprintForm.market_positioning),
          audience_profile: coreValue(book?.core_design, "读者画像", "reader_profile", blueprintForm.audience),
          emotion_value: coreValue(book?.core_design, "情绪曲线", "emotion_curve", blueprintForm.emotional_core),
          commercial_potential: coreValue(book?.core_design, "爽点设计", "satisfaction_design", ""),
        },
        world_bible: book?.world_setting || {},
        long_form_plan: book?.long_form_plan || {},
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
      resetBlueprintForm();
      plannerBookId.value = book.id || "";
      const sourceType = String(book.real_event_strategy?.source_type || "个人");
      const sourcePresets = ["新闻", "历史", "个人"];
      blueprintForm.title = book.title || "";
      blueprintForm.genre = normalizeStoryGenre(book.genre);
      blueprintForm.idea = book.hook || "";
      blueprintForm.chapter_count = Number(book.chapter_count || book.long_form_plan?.total_chapters || book.plot_outline?.length || 500);
      blueprintForm.phase_count = Number(book.long_form_plan?.phase_count || book.phase_count || 5);
      blueprintForm.story_mainline = book.long_form_plan?.story_mainline || book.story_mainline || "";
      blueprintForm.volume_plans = Array.isArray(book.long_form_plan?.volume_plans) ? book.long_form_plan.volume_plans.map((item) => ({ ...makeEmptyVolumePlan(), ...item })) : [];
      blueprintForm.story_units = Array.isArray(book.long_form_plan?.story_units) ? book.long_form_plan.story_units.map((item) => ({ ...makeEmptyStoryUnit(), ...item })) : [];
      ensureLongPlanDefaults();
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
        source_type: sourcePresets.includes(sourceType) ? sourceType : "__custom__",
        source_type_custom: sourcePresets.includes(sourceType) ? "" : sourceType,
      };
      blueprint.value = bookToBlueprint(book);
      blueprintPromise.value = coreValue(book.core_design, "爽点设计", "satisfaction_design", blueprint.value?.book_profile?.promise || "");
    }

    function resetBookScopedMemory(bookId) {
      currentBookId.value = bookId || "";
      plannerBookId.value = bookId || "";
      ctx.selectedStoryId.value = "";
      diagnosis.value = null;
      chapterBrief.value = null;
      rejectedChapter.value = null;
      chapterPlanDraft.value = "";
      chapterPlanDraftNumber.value = 0;
      storyArchive.value = null;
    }

    async function getStoryArchive(bookId = currentBookId.value) {
      if (!bookId) return null;
      const archive = await ctx.requestApi(`/books/${encodeURIComponent(bookId)}/archive`, {}, 10000);
      if (bookId === currentBookId.value) {
        storyArchive.value = archive;
        refreshChapterPlanDraftFromBook();
      }
      return archive;
    }

    async function updateStoryArchive(bookId = currentBookId.value, archive = storyArchive.value) {
      if (!bookId || !archive) return null;
      storyArchive.value = await ctx.requestApi(`/books/${encodeURIComponent(bookId)}/archive`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(archive),
      }, 10000);
      return storyArchive.value;
    }

    async function createBookBlueprint() {
      if (loading.blueprint) return;
      plannerExpanded.value = true;
      const input = collectBookBlueprintInput();
      if (!input.title || !input.hook) {
        ctx.setError("请先填写书名和一句话想法。");
        return;
      }
      const targetBookId = editingBookId.value || plannerBookId.value;
      const isUpdatingExistingBook = Boolean(targetBookId);
      if (!isUpdatingExistingBook) resetBookScopedMemory(input.bookId);
      loading.blueprint = true;
      try {
        const generated = await generateBlueprint(input);
        const savePath = isUpdatingExistingBook ? `/books/${encodeURIComponent(targetBookId)}` : "/books";
        const saved = await ctx.requestApi(savePath, {
          method: isUpdatingExistingBook ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...generated,
            core_design: generated.core_design || input.core_design,
            real_event_strategy: generated.real_event_strategy || input.real_event_strategy,
            long_form_plan: generated.long_form_plan || input.long_form_plan,
            volume_plans: generated.volume_plans || input.volume_plans,
            story_units: generated.story_units || input.story_units,
          }),
        }, 15000);
        blueprint.value = bookToBlueprint(saved);
        blueprintPromise.value = coreValue(saved.core_design, "爽点设计", "satisfaction_design", blueprint.value?.book_profile?.promise || "");
        currentBookId.value = saved.id;
        plannerBookId.value = saved.id;
        editingBookId.value = "";
        storyDraft.name = saved.title || input.title;
        storyDraft.genre = normalizeStoryGenre(saved.genre || input.genre);
        await loadBooks();
        await getStoryArchive(saved.id);
        ctx.setNotice(isUpdatingExistingBook ? `《${saved.title || input.title}》蓝图已更新。` : "小说创建成功，开书蓝图已写入数据库。");
        editingBookId.value = "";
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
      resetBookScopedMemory(book.id);
      editingBookId.value = "";
      plannerExpanded.value = false;
      fillFormFromBook(book);
      refreshChapterPlanDraftFromBook();
      getStoryArchive(book.id).catch((err) => ctx.setError(`故事档案读取失败：${err.message}`));
      ctx.setNotice(`已载入「${book.title}」，可以继续生成章节 Brief 或编辑蓝图。`);
    }

    function editBook(book) {
      resetBookScopedMemory(book.id);
      editingBookId.value = book.id;
      fillFormFromBook(book);
      getStoryArchive(book.id).catch((err) => ctx.setError(`故事档案读取失败：${err.message}`));
      scrollToPlanner();
      ctx.setNotice("已进入编辑状态，可在开书策划表单中修改并保存。");
    }

    async function deleteBook(book) {
      if (!book?.id) return;
      if (!window.confirm(`确定删除《${book.title || "未命名小说"}》吗？此操作会从数据库移除该小说项目。`)) return;
      loading.deleteBook = book.id;
      try {
        const deletingPlannerBook = plannerBookId.value === book.id;
        await ctx.requestApi(`/books/${encodeURIComponent(book.id)}`, { method: "DELETE" }, 10000);
        if (currentBookId.value === book.id) resetBookScopedMemory("");
        if (deletingPlannerBook) {
          plannerBookId.value = "";
          resetBlueprintForm();
        }
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
      if (!currentBookId.value) {
        ctx.setError("请先选择或创建一本小说。");
        return;
      }
      await loadNextChapterBrief();
    }

    async function generateChapterFromBrief() {
      if (!currentBookId.value) {
        ctx.setError("请先选择或创建一本小说。");
        return;
      }
      loading.chapter = true;
      try {
        localStorage.setItem("novelChapterAiKey", selectedChapterAi.value.key);
        syncEditedChapterPlan();
        if (!chapterBrief.value) {
          chapterBrief.value = buildLocalChapterBrief();
        }
        const result = await ctx.requestApi(`/books/${encodeURIComponent(currentBookId.value)}/chapters/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            brief: chapterBrief.value,
            user_note: chapterNote.value,
            ai_provider: selectedChapterAi.value.provider,
            ai_model: selectedChapterAi.value.model,
            ai_thinking: Boolean(selectedChapterAi.value.thinking),
            ai_reasoning_effort: selectedChapterAi.value.reasoningEffort || "",
            allow_local_fallback: false,
            wechat_skill_id: selectedNovelSkillId.value || "wechat_ai_writing_workshop_v1",
          }),
        }, 300000);
        const chNum = result?.chapter?.chapter_number;
        rejectedChapter.value = null;
        const review = result?.quality;
        await getStoryArchive(currentBookId.value);
        await advanceToNextChapterPlan();
        await loadNextChapterBrief({ silent: true });
        if (chNum && review && Number(review.score || 0) < 60) {
          ctx.setError(`第 ${chNum} 章已保存，但商业智能评分偏低；已切换到第 ${nextChapterNumber.value} 章剧情计划。`);
        } else if (chNum) {
          ctx.setNotice(`第 ${chNum} 章已生成并保存，已切换到第 ${nextChapterNumber.value} 章剧情计划。`);
        } else {
          ctx.setNotice(`章节已生成，已切换到第 ${nextChapterNumber.value} 章剧情计划。`);
        }
      } catch (err) {
        const detail = err?.payload?.detail;
        const failedChapter = detail?.chapter;
        if (failedChapter) {
          rejectedChapter.value = failedChapter;
          const issues = Array.isArray(detail.issues) ? detail.issues.join("；") : err.message;
          ctx.setError(`章节已生成草稿，但未通过质量门槛，未保存：${issues}`);
        } else {
          rejectedChapter.value = null;
          ctx.setError(`章节生成失败：${err.message}`);
        }
      } finally {
        loading.chapter = false;
      }
    }

    async function regenerateBookChapter(chapter) {
      if (!currentBookId.value || !chapter?.chapter_number) {
        ctx.setError("请先选择一本小说和要重生成的章节。");
        return;
      }
      const chapterNumber = Number(chapter.chapter_number);
      loading.regenerateChapter = String(chapterNumber);
      try {
        localStorage.setItem("novelChapterAiKey", selectedChapterAi.value.key);
        const plan = chapter.chapterPlan || (selectedBook.value?.plot_outline || []).find((item) => Number(item.chapter) === chapterNumber) || {};
        const originalExcerpt = String(chapter.content || chapter.content_markdown || "").slice(0, 260);
        const result = await ctx.requestApi(`/books/${encodeURIComponent(currentBookId.value)}/chapters/${chapterNumber}/regenerate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            brief: {
              bookId: currentBookId.value,
              story_name: selectedBook.value?.title,
              chapter_number: chapterNumber,
              chapterPlan: plan,
              regenerate_seed: Date.now(),
              user_note: `${chapterNote.value || ""}\n不合规范，按小说世界模拟器规则重写：直接入场、动作对话推进、不要说明腔。必须避开原文开头和原事件节奏，原文片段：${originalExcerpt}`.trim(),
            },
            user_note: chapterNote.value,
            ai_provider: selectedChapterAi.value.provider,
            ai_model: selectedChapterAi.value.model,
            ai_thinking: Boolean(selectedChapterAi.value.thinking),
            ai_reasoning_effort: selectedChapterAi.value.reasoningEffort || "",
            allow_local_fallback: false,
          }),
        }, 300000);
        const score = result?.quality?.score || result?.chapter?.quality?.score || "--";
        ctx.setNotice(`第 ${chapterNumber} 章已重新生成，质量评分 ${score}。`);
        await getStoryArchive(currentBookId.value);
      } catch (err) {
        ctx.setError(`章节重生成失败：${err.message}`);
      } finally {
        loading.regenerateChapter = "";
      }
    }

    async function saveEditedChapter(chapter) {
      if (!currentBookId.value || !chapter?.chapter_number) {
        ctx.setError("请先选择一本小说和要修改的章节。");
        return;
      }
      const chapterNumber = Number(chapter.chapter_number);
      const editKey = chapterEditKey(chapter);
      const content = editingChapterDraft.value.trim();
      if (!content) {
        ctx.setError("章节正文不能为空。");
        return;
      }
      loading.saveChapter = editKey;
      try {
        await ctx.requestApi(`/books/${encodeURIComponent(currentBookId.value)}/chapters/${chapterNumber}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
        }, 30000);
        cancelEditChapter();
        await getStoryArchive(currentBookId.value);
        ctx.setNotice(`第 ${chapterNumber} 章正文已保存。`);
      } catch (err) {
        ctx.setError(`保存章节失败：${err.message}`);
      } finally {
        loading.saveChapter = "";
      }
    }

    async function deleteBookChapter(chapter) {
      if (!currentBookId.value || !chapter?.chapter_number) {
        ctx.setError("请先选择一本小说和要删除的章节。");
        return;
      }
      const chapterNumber = Number(chapter.chapter_number);
      if (!confirm(`确认删除第 ${chapterNumber} 章吗？此操作不会删除小说项目。`)) return;
      loading.deleteChapter = String(chapterNumber);
      try {
        await ctx.requestApi(`/books/${encodeURIComponent(currentBookId.value)}/chapters/${chapterNumber}`, {
          method: "DELETE",
        }, 15000);
        ctx.setNotice(`第 ${chapterNumber} 章已删除。`);
        await getStoryArchive(currentBookId.value);
      } catch (err) {
        ctx.setError(`章节删除失败：${err.message}`);
      } finally {
        loading.deleteChapter = "";
      }
    }

    async function runOneClickProduction() {
      if (!blueprint.value) {
        await createBookBlueprint();
      }
      if (currentBookId.value && !chapterBrief.value) {
        await createChapterBrief();
      }
    }

    function syncBlueprintTitleFromStory() {
      return null;
    }

    onMounted(async () => {
      await Promise.allSettled([loadWorkflow(), loadBooks(), ctx.loadStories(), ctx.fanqieLoadSettings(), ctx.loadPresetTopicsAndSkills()]);
      ensureNovelSkillSelected();
    });

    watch(
      () => blueprintForm.genre,
      () => syncSkillWithGenre({ force: true }),
    );

    watch(
      () => [blueprintForm.phase_count, blueprintForm.chapter_count],
      () => syncVolumePlanCount(),
    );

    watch(
      () => [currentBookId.value, selectedBook.value?.id, sortedBookChapters.value.length],
      async () => {
        const force = Number(chapterPlanDraftNumber.value || 0) !== Number(nextChapterNumber.value || 1);
        refreshChapterPlanDraftFromBook({ force });
        if (currentBookId.value && force && !loading.brief) {
          await loadNextChapterBrief({ silent: true });
        }
      },
    );

    ensureLongPlanDefaults();

    return {
      ...ctx,
      workflow,
      diagnosis,
      chapterBrief,
      activeChapterBrief,
      rejectedChapter,
      storyArchive,
      books,
      currentBookId,
      selectedBookId,
      selectedBook,
      plannerBookId,
      latestBookChapter,
      sortedBookChapters,
      selectedFanqieTargetId,
      editingBookId,
      plannerPanel,
      plannerExpanded,
      loading,
      blueprintForm,
      blueprint,
      blueprintPromise,
      chapterNote,
      chapterPlanDraft,
      editingChapterKey,
      editingChapterDraft,
      selectedChapterAiKey,
      chapterAiOptions,
      selectedChapterAi,
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
      dailyChapterEcho,
      projectCards,
      formatBookDetail,
      chapterDisplayContent,
      bookDetailSections,
      addStoryUnit,
      removeStoryUnit,
      storyUnitImportText,
      fillStoryUnitsFromConversation,
      storyProductionStatus,
      uploadNovelSkill,
      startCreateBook,
      loadBooks,
      generateBlueprint,
      createBookBlueprint,
      getStoryArchive,
      updateStoryArchive,
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
      syncEditedChapterPlan,
      regenerateBookChapter,
      deleteBookChapter,
      runOneClickProduction,
      storyMetricClass,
      formatStoryStep,
      storyScoreLabel,
      novelOsPlanPreview,
      chapterEditKey,
      startEditChapter,
      cancelEditChapter,
      saveEditedChapter,
    };
  }
};
</script>

<template>
  <div v-if="activeTab === 'novels'" class="novel-page">
    <section class="panel novel-wizard-panel novel-product-hero">
      <div>
        <span>SERIAL FICTION OPS</span>
        <h2>AI小说创作向导</h2>
        <p>先输入创意，再由AI团队完成市场分析、小说DNA、团队配置和章节生产。</p>
      </div>
      <div class="novel-mode-switch">
        <button type="button" :class="{ active: userMode === 'novice' }" @click="userMode = 'novice'">新手模式</button>
        <button type="button" :class="{ active: userMode === 'professional' }" @click="userMode = 'professional'">专业模式</button>
      </div>
      <div class="novel-wizard-steps">
        <article :class="{ done: blueprintForm.idea }"><span>01</span><strong>输入创意</strong><p>类型、一句话故事、喜欢方向、目标读者。</p></article>
        <article :class="{ done: blueprint?.topic_center }"><span>02</span><strong>AI总编分析</strong><p>市场定位、商业潜力、核心卖点和风险。</p></article>
        <article :class="{ done: blueprint?.world_bible }"><span>03</span><strong>小说DNA</strong><p>主题、世界规则、人物方向、核心冲突。</p></article>
        <article :class="{ done: selectedNovelSkillId }"><span>04</span><strong>配置AI团队</strong><p>总编、市场、世界观、人物、剧情、作者、审核。</p></article>
        <article :class="{ done: chapterBrief }"><span>05</span><strong>章节生产</strong><p>Brief、正文、节奏检测、逻辑审核、平台审核。</p></article>
      </div>
    </section>

    <section class="panel novel-project-center">
      <div class="panel-header">
        <div>
          <h2>我的小说</h2>
          <div class="meta">管理项目进度，选择一本书进入生产。</div>
        </div>
        <button class="btn accent" :disabled="loading.blueprint" @click="startCreateBook">
          + 创建小说
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
          <div v-if="selectedBookId === book.id" class="novel-selected-badge">当前选中</div>
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
          <details class="novel-book-details" @click.stop>
            <summary>开书资料 · 点击展开</summary>
            <div class="novel-book-detail-grid">
              <article v-for="section in bookDetailSections(book)" :key="section.label">
                <strong>{{ section.label }}</strong>
                <pre>{{ formatBookDetail(section.value) }}</pre>
              </article>
            </div>
          </details>
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
          <strong>{{ selectedBook?.title || blueprintForm.title || "未创建" }}</strong>
          <p>{{ commandMetrics.currentTask }}</p>
        </div>
        <div class="novel-dashboard-grid">
          <span>章节 <strong>{{ commandMetrics.completed }}/{{ commandMetrics.planned }}</strong></span>
          <span>质量评分 <strong>{{ commandMetrics.qualityScore }}</strong></span>
          <span>读者兴趣 <strong>{{ commandMetrics.readerInterest }}</strong></span>
          <span>风险 <strong>{{ commandMetrics.risk }}</strong></span>
        </div>
      </div>
      <div v-if="currentBookId" class="novel-daily-echo">
        <div class="novel-daily-echo-head">
          <div>
            <span>每日章节生产回显</span>
            <strong>第 {{ dailyChapterEcho.chapterNumber }} 章 · {{ dailyChapterEcho.title }}</strong>
          </div>
          <button class="btn secondary small" :disabled="loading.brief" @click="createChapterBrief">
            {{ loading.brief ? "生成中..." : "生成/刷新 Brief" }}
          </button>
        </div>
        <textarea
          v-model="chapterPlanDraft"
          rows="4"
          placeholder="选中小说后，这里会回显下一章剧情计划；不符合预期可以直接修改后再生成正文。"
        ></textarea>
        <div class="novel-daily-echo-actions">
          <span>{{ dailyChapterEcho.hasPlan ? "已载入下一章计划，可手动调整。" : "当前小说还没有可用章节规划，请先生成或刷新 Brief。" }}</span>
          <button class="btn accent small" :disabled="loading.chapter || !selectedNovelSkillId" @click="generateChapterFromBrief">
            {{ loading.chapter ? "生成中..." : "按此计划生成正文" }}
          </button>
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
          <div class="meta">小说基础规范会自动叠加。这里选的是题材写法：玄幻修仙、东方玄学、都市现实新闻改编等。</div>
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

    <section ref="plannerPanel" class="panel novel-planner-panel">
      <div class="panel-header">
        <div>
          <h2>1. 开书策划</h2>
          <div class="meta">
            {{ editingBookId ? "正在编辑当前小说，修改后会更新这本书的蓝图。" : "先手动填写创意和定位，再生成开书蓝图。" }}
          </div>
        </div>
        <div class="panel-actions">
          <button class="btn secondary" type="button" @click="plannerExpanded = !plannerExpanded">
            {{ plannerExpanded ? "收起开书策划" : "展开开书策划" }}
          </button>
          <button v-if="plannerExpanded" class="btn accent" :disabled="loading.blueprint" @click="createBookBlueprint">
            {{ loading.blueprint ? "生成中..." : (editingBookId || plannerBookId) ? "更新当前书蓝图" : "生成开书蓝图" }}
          </button>
        </div>
      </div>
      <div v-show="plannerExpanded" class="novel-form-grid">
        <label class="field">
          <span>书名</span>
          <input v-model="blueprintForm.title" :placeholder="selectedStoryName || '例：烬月灯'" />
        </label>
        <label class="field">
          <span>类型</span>
          <select v-model="blueprintForm.genre">
            <option value="romance_fantasy">言情玄幻</option>
            <option value="urban">都市</option>
            <option value="urban_news_adaptation">都市现实新闻改编</option>
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
          <select v-model="blueprintForm.real_event_strategy.enabled">
            <option :value="false">否，完全虚构</option>
            <option :value="true">是，需要改编</option>
          </select>
        </label>
        <label class="field">
          <span>事件来源</span>
          <select v-model="blueprintForm.real_event_strategy.source_type">
            <option value="新闻">新闻</option>
            <option value="历史">历史</option>
            <option value="个人">个人经历</option>
            <option value="__custom__">自定义来源</option>
          </select>
        </label>
        <label v-if="blueprintForm.real_event_strategy.source_type === '__custom__'" class="field">
          <span>自定义来源</span>
          <input
            v-model="blueprintForm.real_event_strategy.source_type_custom"
            placeholder="例：社区见闻 / 行业案例 / 身边人物 / 公开访谈"
          />
        </label>
        <label v-if="blueprintForm.real_event_strategy.enabled" class="field">
          <span>改编程度</span>
          <select v-model="blueprintForm.real_event_strategy.adaptation_level">
            <option value="低">低：保留大框架</option>
            <option value="中">中：重组人物与事件</option>
            <option value="高">高：只保留情绪内核</option>
          </select>
        </label>
        <label class="field">
          <span>商业标签</span>
          <input v-model="blueprintForm.core_design.平台标签" placeholder="例：番茄,女频,逆袭,强钩子" />
        </label>
        <label v-if="blueprintForm.real_event_strategy.enabled" class="field wide">
          <span>风险规避策略</span>
          <textarea v-model="blueprintForm.real_event_strategy.risk_control" rows="2" placeholder="例：人物地点虚构化，不复刻真实案件细节。"></textarea>
        </label>
        <label class="field wide">
          <span>爽点设计</span>
          <textarea v-model="blueprintForm.core_design.爽点设计" rows="2" placeholder="例：主角靠智慧破局，每3章一次阶段性小胜。"></textarea>
        </label>
        <label class="field">
          <span>情绪曲线</span>
          <input v-model="blueprintForm.core_design.情绪曲线" placeholder="例：压抑 -> 破局 -> 爽感释放 -> 新悬念" />
        </label>
        <label class="field">
          <span>读者画像</span>
          <input v-model="blueprintForm.core_design.读者画像" placeholder="例：高压现实中需要成长代偿的女频读者" />
        </label>
        <label class="field">
          <span>世界观种子</span>
          <input v-model="blueprintForm.worldview_seed" placeholder="时间背景、社会体系或力量规则" />
        </label>
        <label class="field">
          <span>主角生命种子</span>
          <input v-model="blueprintForm.protagonist_seed" placeholder="背景、缺陷、心理矛盾或成长方向" />
        </label>
        <div class="long-plan-editor wide">
          <div class="long-plan-header">
            <div>
              <strong>长篇结构设计</strong>
              <span>先确定总章节数和分卷数量，再按卷填写主题、目标、冲突和卷末钩子。</span>
            </div>
          </div>
          <div class="novel-form-grid nested">
            <label class="field">
              <span>总章节数</span>
              <input v-model.number="blueprintForm.chapter_count" inputmode="numeric" placeholder="500" />
            </label>
            <label class="field">
              <span>分为多少卷</span>
              <input v-model.number="blueprintForm.phase_count" inputmode="numeric" min="1" placeholder="5" />
            </label>
            <label class="field wide">
              <span>全书主线</span>
              <input v-model="blueprintForm.story_mainline" placeholder="一句话写清楚最终目标：例如，林小满从普通打工人一步步完成自救，并带动身边人重新开始。" />
            </label>
          </div>
          <details class="long-plan-block" open>
            <summary>
              <strong>阶段/卷规划</strong>
              <span>系统会根据“分为多少卷”生成对应卷数，并按总章节数自动分配章节范围。</span>
            </summary>
            <div class="volume-plan-list">
              <article v-for="(volume, index) in blueprintForm.volume_plans" :key="`volume-${index}`" class="volume-plan-card">
                <div class="volume-plan-title">
                  <strong>第 {{ index + 1 }} 卷</strong>
                  <input v-model="volume.volume_name" placeholder="卷名" />
                  <input v-model="volume.chapter_range" placeholder="章节范围：1-100" />
                </div>
                <div class="novel-form-grid nested">
                  <label class="field">
                    <span>卷主题</span>
                    <input v-model="volume.theme" placeholder="例：凡人入局 / 宗门修炼 / 城市自救" />
                  </label>
                  <label class="field">
                    <span>阶段目标</span>
                    <input v-model="volume.stage_goal" placeholder="这一卷必须完成的明确目标" />
                  </label>
                  <label class="field">
                    <span>核心冲突</span>
                    <input v-model="volume.core_conflict" placeholder="外部阻力 + 内在选择" />
                  </label>
                  <label class="field">
                    <span>人物成长</span>
                    <input v-model="volume.protagonist_growth" placeholder="角色从什么状态变成什么状态" />
                  </label>
                  <label class="field">
                    <span>卷末结果</span>
                    <input v-model="volume.ending_result" placeholder="本卷问题如何阶段性收束" />
                  </label>
                  <label class="field">
                    <span>卷末钩子</span>
                    <input v-model="volume.ending_hook" placeholder="引向下一卷的更大问题" />
                  </label>
                </div>
              </article>
            </div>
          </details>
          <details class="long-plan-block" open>
            <summary>
              <strong>故事单元规划</strong>
              <span>每几个章节一个小主线，生成章节时会优先按对应单元推进。</span>
            </summary>
            <div class="story-unit-import-box">
              <label class="field">
                <span>从 AI 沟通结果提取故事单元</span>
                <textarea
                  v-model="storyUnitImportText"
                  rows="4"
                  placeholder="把你和全局 AI、DeepSeek、通义千问或其他 AI 的沟通结果粘贴到这里；截图内容请先用 OCR/复制文字后粘贴。"
                ></textarea>
              </label>
              <div class="novel-actions compact">
                <button
                  type="button"
                  class="btn secondary small"
                  :disabled="loading.storyUnitExtract || !storyUnitImportText.trim()"
                  @click="fillStoryUnitsFromConversation"
                >
                  {{ loading.storyUnitExtract ? "提取中..." : "AI提取并填入故事单元" }}
                </button>
                <button type="button" class="btn secondary small" :disabled="!storyUnitImportText" @click="storyUnitImportText = ''">清空文本</button>
              </div>
            </div>
            <div class="story-unit-list">
              <article v-for="(unit, index) in blueprintForm.story_units" :key="`unit-${index}`" class="story-unit-card">
                <div class="story-unit-title">
                  <strong>故事单元 {{ index + 1 }}</strong>
                  <button type="button" class="btn secondary small danger" @click="removeStoryUnit(index)">删除</button>
                </div>
                <div class="novel-form-grid nested">
                  <label class="field">
                    <span>起始章</span>
                    <input v-model.number="unit.start_chapter" inputmode="numeric" placeholder="1" />
                  </label>
                  <label class="field">
                    <span>结束章</span>
                    <input v-model.number="unit.end_chapter" inputmode="numeric" placeholder="20" />
                  </label>
                  <label class="field">
                    <span>小主线名称</span>
                    <input v-model="unit.unit_name" placeholder="例：村庄危机 / 第一份订单 / 旧案重启" />
                  </label>
                  <label class="field">
                    <span>主要事件</span>
                    <input v-model="unit.main_event" placeholder="这组章节连续推进的主要事件" />
                  </label>
                  <label class="field">
                    <span>阶段冲突</span>
                    <input v-model="unit.stage_conflict" placeholder="这一小主线的核心阻碍" />
                  </label>
                  <label class="field">
                    <span>爽点/情绪点</span>
                    <input v-model="unit.payoff_emotion" placeholder="读者在这里获得什么释放" />
                  </label>
                  <label class="field">
                    <span>伏笔</span>
                    <input v-model="unit.foreshadowing" placeholder="埋下但暂不解释的信息" />
                  </label>
                  <label class="field">
                    <span>回收点</span>
                    <input v-model="unit.payoff" placeholder="预计如何回收或兑现" />
                  </label>
                </div>
              </article>
            </div>
            <button type="button" class="btn secondary small" @click="addStoryUnit">+ 添加故事单元</button>
          </details>
        </div>
      </div>
      <div v-if="blueprint" class="blueprint-card">
        <strong>{{ blueprint.book_profile.title }} · {{ blueprint.book_profile.genre }}</strong>
        <p>{{ blueprint.book_profile.one_sentence }}</p>
        <details class="novel-os-section novel-system-capabilities">
          <summary>
            <strong>系统默认能力与生成结果</strong>
            <span>选题、世界观、人物、100章规划、Skill、Memory 和商业智能默认自动参与；需要查看或人工微调时展开。</span>
          </summary>
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
        <div v-if="blueprint.long_form_plan" class="novel-os-section">
          <div class="novel-section-title">长篇结构设计</div>
          <div class="novel-insight-grid">
            <span>
              总章节数
              <strong>{{ blueprint.long_form_plan.total_chapters || blueprint.volume_plan?.planned_chapters }}</strong>
            </span>
            <span>
              分卷数量
              <strong>{{ blueprint.long_form_plan.phase_count || 5 }}</strong>
            </span>
            <span class="wide">
              全书主线
              <strong>{{ blueprint.long_form_plan.story_mainline || blueprint.book_profile.one_sentence }}</strong>
            </span>
          </div>
          <div class="long-plan-readonly-grid">
            <article v-for="volume in blueprint.long_form_plan.volume_plans || []" :key="volume.volume_name">
              <strong>{{ volume.volume_name }} · {{ volume.chapter_range }}</strong>
              <p>{{ volume.theme || "卷主题待细化" }}</p>
              <span>目标：{{ volume.stage_goal || "待补充" }}</span>
              <span>冲突：{{ volume.core_conflict || "待补充" }}</span>
              <span>卷末：{{ volume.ending_result || "待补充" }} / {{ volume.ending_hook || "待补充" }}</span>
            </article>
          </div>
          <div class="long-plan-readonly-grid compact">
            <article v-for="unit in blueprint.long_form_plan.story_units || []" :key="`${unit.start_chapter}-${unit.end_chapter}-${unit.unit_name}`">
              <strong>{{ unit.start_chapter }}-{{ unit.end_chapter }}章 · {{ unit.unit_name }}</strong>
              <p>{{ unit.main_event }}</p>
              <span>{{ unit.stage_conflict }}</span>
              <span>{{ unit.payoff_emotion }}</span>
            </article>
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
        </details>
        <label class="field wide blueprint-promise-field">
          <span>故事承诺（会写入故事档案，后面每章都按它校准）</span>
          <textarea
            v-model="blueprintPromise"
            rows="3"
            placeholder="例：女主每一卷都要在爱情、命运和自我选择之间付出代价，并逐步夺回主动权。"
          ></textarea>
        </label>
        <details v-if="userMode === 'professional'" class="blueprint-debug-details">
          <summary>专业调试资料：旧版校准问题与开篇预览</summary>
          <div class="blueprint-questions">
            <span v-for="q in blueprint.questions" :key="q">{{ q }}</span>
          </div>
          <div class="chapter-outline">
            <div v-for="item in blueprint.chapter_outline" :key="item.chapter">
              <b>第 {{ item.chapter }} 章</b>
              <span>{{ item.goal }}</span>
            </div>
          </div>
        </details>
        <div class="novel-actions compact">
          <button class="btn primary small" :disabled="!currentBookId" @click="getStoryArchive()">
            刷新当前书档案
          </button>
          <button class="btn secondary small" :disabled="!currentBookId" @click="createChapterBrief">生成章节计划 Brief</button>
        </div>
      </div>
    </section>

    <section class="panel novel-story-panel">
      <div class="panel-header">
        <div>
          <h2>2. 故事档案与诊断</h2>
          <div class="meta">这里看“这本书能不能继续写”，不是单纯看文笔。</div>
        </div>
        <button class="btn secondary" :disabled="!currentBookId" @click="getStoryArchive">刷新档案</button>
      </div>

      <div class="story-selector-block novel-selector">
        <div class="story-selector-row">
          <select class="story-select" v-model="currentBookId" @change="selectedBook && continueBook(selectedBook)">
            <option value="">选择小说项目</option>
            <option v-for="book in books" :key="book.id" :value="book.id">
              {{ book.title }} · 规划 {{ book.plot_outline?.length || 0 }} 章
            </option>
          </select>
          <button class="btn secondary small" :disabled="!currentBookId" @click="getStoryArchive">读取档案</button>
          <button class="btn primary small" :disabled="!currentBookId || loading.brief" @click="createChapterBrief">
            {{ loading.brief ? "生成中..." : "按100章规划生成Brief" }}
          </button>
        </div>
        <div v-if="storyArchive" class="diagnosis-card">
          <div class="diagnosis-score">
            <strong>{{ storyArchive.chapters?.length || 0 }}/{{ selectedBook?.plot_outline?.length || 100 }}</strong>
            <span>bookId：{{ currentBookId }}</span>
            <em>{{ storyArchive.title }} · {{ storyArchive.plot?.chapterPlans?.length || 0 }} 条章节规划</em>
          </div>
          <div class="next-actions">
            <b>当前档案只读取这本书的数据</b>
            <span>世界观：{{ storyArchive.world?.time_background || "待生成" }}</span>
            <span>人物数：{{ storyArchive.characters?.length || 0 }}</span>
            <span>时间线事件：{{ storyArchive.timeline?.length || 0 }}</span>
            <span>已生成章节：{{ storyArchive.chapters?.length || 0 }}</span>
          </div>
        </div>
      </div>

      <div v-if="userMode === 'professional' && diagnosis" class="diagnosis-card">
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
        <button class="btn primary" :disabled="!currentBookId || loading.brief" @click="createChapterBrief">
          {{ loading.brief ? "生成中..." : "生成章节计划 Brief" }}
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
      <label v-if="currentBookId" class="field chapter-plan-editor">
        <span>剧情计划（可手动修改，不符合就先改这里）</span>
        <textarea
          v-model="chapterPlanDraft"
          rows="5"
          placeholder="事件1：新事件（推进主线：是；制造冲突：否；新信息：是）"
        ></textarea>
      </label>
      <div v-if="activeChapterBrief" class="brief-card">
        <strong>{{ activeChapterBrief.story_name }} · 第 {{ activeChapterBrief.chapter_number }} 章</strong>
        <p>{{ activeChapterBrief.title_hint }}</p>
        <div class="brief-columns">
          <div>
            <b>必须做到</b>
            <span v-for="item in activeChapterBrief.must_do" :key="item">{{ item }}</span>
          </div>
          <div>
            <b>不要踩坑</b>
            <span v-for="item in activeChapterBrief.do_not_do" :key="item">{{ item }}</span>
          </div>
        </div>
      </div>
      <div class="novel-actions">
        <label class="chapter-ai-select">
          <span>本次生成 AI</span>
          <select v-model="selectedChapterAiKey" :disabled="loading.chapter">
            <option v-for="item in chapterAiOptions" :key="item.key" :value="item.key">{{ item.label }}</option>
          </select>
        </label>
        <button class="btn accent" :disabled="loading.chapter || !currentBookId || !selectedNovelSkillId" @click="generateChapterFromBrief">
          {{ loading.chapter ? "生成中..." : "生成正文" }}
        </button>
        <button class="btn secondary" :disabled="loading.chapter || !currentBookId" @click="createChapterBrief">重新生成</button>
        <button class="btn secondary" :disabled="!currentBookId" @click="getStoryArchive()">刷新档案</button>
        <button v-if="storyArchive?.chapters?.length" class="btn secondary" @click="getStoryArchive()">查看已生成 {{ storyArchive.chapters.length }} 章</button>
      </div>
      <div v-if="rejectedChapter" class="brief-card chapter-output-card rejected-chapter-card">
        <strong>已生成草稿，但未通过质量门槛</strong>
        <p>这份正文没有保存到章节列表。请根据审核提示调整剧情计划后重新生成。</p>
        <div v-if="rejectedChapter.editorial_review?.issues?.length" class="chapter-review-issues">
          <strong>审核提示</strong>
          <span v-for="issue in rejectedChapter.editorial_review.issues" :key="issue">{{ issue }}</span>
        </div>
        <div v-if="rejectedChapter.chapter_self_check?.issues?.length" class="chapter-review-issues">
          <strong>自检提示</strong>
          <span v-for="issue in rejectedChapter.chapter_self_check.issues" :key="issue">{{ issue }}</span>
        </div>
        <div v-if="rejectedChapter.generation_source === 'local_fallback' || rejectedChapter.local_generation_warning?.enabled" class="chapter-local-warning">
          <strong>本地生成提示</strong>
          <span>{{ rejectedChapter.local_generation_warning?.message || "本章由本地规则兜底生成，仅供检查剧情连贯性。" }}</span>
          <em>{{ rejectedChapter.local_generation_warning?.quality_gate || "系统已执行水文、重复和剧情推进检查；不满意请重新生成。" }}</em>
        </div>
        <div v-else-if="rejectedChapter.generation_source === 'online_ai'" class="chapter-ai-source">
          <strong>在线AI生成</strong>
          <span>{{ rejectedChapter.online_ai?.provider || "online" }} · {{ rejectedChapter.online_ai?.model || "model" }}</span>
        </div>
        <pre>{{ chapterDisplayContent(rejectedChapter) }}</pre>
      </div>
      <div v-if="sortedBookChapters.length" class="brief-card chapter-output-card">
        <strong>已生成章节</strong>
        <p>默认合并收起，点击任意章节展开查看完整正文。</p>
        <div class="chapter-push-row chapter-push-global">
          <label>
            <span>当前小说推送目标</span>
            <select v-model="selectedFanqieTargetId">
              <option value="">选择番茄作品</option>
              <option v-for="work in fanqie.works" :key="work.id" :value="work.id">
                {{ work.work_name }} · {{ work.book_id }}
              </option>
            </select>
          </label>
          <span v-if="!fanqie.works.length" class="chapter-push-hint">先在下方录入番茄 Book ID 和书名。</span>
          <span v-else class="chapter-push-hint">选一次后，本小说所有章节默认使用这个推送目标。</span>
        </div>
        <details v-for="chapter in sortedBookChapters" :key="chapter.id || chapter.chapter_number" class="chapter-collapse-item">
          <summary>
            <span>{{ chapter.title || `第 ${chapter.chapter_number} 章` }}</span>
            <em>
              质量 {{ chapter.quality?.score || "--" }} ·
              沉浸感 {{ chapter.quality?.editor_immersion_score || "--" }} ·
              审核 {{ chapter.editorial_review?.pass ? "通过" : "需复核" }}
            </em>
          </summary>
          <div class="chapter-manage-row">
            <span
              class="chapter-review-pill"
              :class="{ warning: !chapter.editorial_review?.pass || Number(chapter.quality?.score || 0) < 80 }"
            >
              {{ chapter.editorial_review?.pass && Number(chapter.quality?.score || 0) >= 80 ? "符合规范" : "不合规范，建议重新生成" }}
            </span>
            <button
              v-if="editingChapterKey !== chapterEditKey(chapter)"
              class="btn secondary small"
              :disabled="loading.regenerateChapter === String(chapter.chapter_number) || loading.deleteChapter === String(chapter.chapter_number)"
              @click="startEditChapter(chapter)"
            >
              编辑正文
            </button>
            <button
              v-if="editingChapterKey === chapterEditKey(chapter)"
              class="btn accent small"
              :disabled="loading.saveChapter === chapterEditKey(chapter) || !editingChapterDraft.trim()"
              @click="saveEditedChapter(chapter)"
            >
              {{ loading.saveChapter === chapterEditKey(chapter) ? "保存中..." : "保存修改" }}
            </button>
            <button
              v-if="editingChapterKey === chapterEditKey(chapter)"
              class="btn secondary small"
              :disabled="loading.saveChapter === chapterEditKey(chapter)"
              @click="cancelEditChapter"
            >
              取消
            </button>
            <button
              class="btn secondary small"
              :disabled="loading.regenerateChapter === String(chapter.chapter_number) || loading.deleteChapter === String(chapter.chapter_number)"
              @click="regenerateBookChapter(chapter)"
            >
              {{ loading.regenerateChapter === String(chapter.chapter_number) ? "重生成中..." : "重新生成" }}
            </button>
            <button
              class="btn secondary small danger"
              :disabled="loading.deleteChapter === String(chapter.chapter_number) || loading.regenerateChapter === String(chapter.chapter_number)"
              @click="deleteBookChapter(chapter)"
            >
              {{ loading.deleteChapter === String(chapter.chapter_number) ? "删除中..." : "删除" }}
            </button>
            <button
              class="btn accent small"
              :disabled="!fanqie.works.length || fanqie.pushingChapter === fanqieChapterKey(chapter)"
              @click="fanqiePushChapter(chapter, fanqie.works.find((work) => work.id === selectedFanqieTargetId))"
            >
              {{ fanqie.pushingChapter === fanqieChapterKey(chapter) ? "推送中..." : "推送到草稿箱" }}
            </button>
          </div>
          <div v-if="fanqie.pushResult[fanqieChapterKey(chapter)]" class="chapter-push-row compact-result">
            <span v-if="!fanqie.works.length" class="chapter-push-hint">先在下方录入番茄 Book ID 和书名。</span>
            <span
              v-else
              class="chapter-push-hint"
              :class="{ err: !fanqie.pushResult[fanqieChapterKey(chapter)].ok }"
            >
              {{ fanqie.pushResult[fanqieChapterKey(chapter)].message || fanqie.pushResult[fanqieChapterKey(chapter)].error }}
            </span>
          </div>
          <div v-if="chapter.editorial_review?.issues?.length" class="chapter-review-issues">
            <strong>审核提示</strong>
            <span v-for="issue in chapter.editorial_review.issues" :key="issue">{{ issue }}</span>
          </div>
          <div v-if="chapter.generation_source === 'local_fallback' || chapter.local_generation_warning?.enabled" class="chapter-local-warning">
            <strong>本地生成提示</strong>
            <span>{{ chapter.local_generation_warning?.message || "本章由本地规则兜底生成，仅供检查剧情连贯性。" }}</span>
            <em>{{ chapter.local_generation_warning?.quality_gate || "系统已执行水文、重复和剧情推进检查；不满意请重新生成。" }}</em>
          </div>
          <div v-else-if="chapter.generation_source === 'online_ai'" class="chapter-ai-source">
            <strong>在线AI生成</strong>
            <span>{{ chapter.online_ai?.provider || "online" }} · {{ chapter.online_ai?.model || "model" }}</span>
          </div>
          <textarea
            v-if="editingChapterKey === chapterEditKey(chapter)"
            v-model="editingChapterDraft"
            class="chapter-edit-textarea"
            rows="22"
            placeholder="在这里修改章节正文，保存后会更新到章节列表和后续推送内容。"
          ></textarea>
          <pre v-else>{{ chapterDisplayContent(chapter) }}</pre>
        </details>
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
        <div class="fanqie-work-manager">
          <div class="fanqie-work-form">
            <label class="fanqie-field">
              <span>番茄书名</span>
              <input v-model="fanqie.workDraft.work_name" placeholder="例：人间重启" />
            </label>
            <label class="fanqie-field">
              <span>Book ID</span>
              <input v-model="fanqie.workDraft.book_id" placeholder="从番茄章节管理 URL 获取" />
            </label>
            <button class="btn accent small" @click="fanqieSaveWorkTarget">
              {{ fanqie.workDraft.id ? "保存映射" : "添加作品" }}
            </button>
            <button v-if="fanqie.workDraft.id" class="btn secondary small" @click="fanqieResetWorkDraft">取消编辑</button>
          </div>
          <div v-if="fanqie.works.length" class="fanqie-work-list">
            <div v-for="work in fanqie.works" :key="work.id" class="fanqie-work-item">
              <strong>{{ work.work_name }}</strong>
              <code>{{ work.book_id }}</code>
              <button class="btn secondary small" @click="fanqieEditWorkTarget(work)">编辑</button>
              <button class="btn secondary small" @click="fanqieDeleteWorkTarget(work.id)">删除</button>
            </div>
          </div>
          <p v-else class="fanqie-msg">还没有番茄作品映射。录入后，每一章都可以选择具体 Book ID 推送到对应草稿箱。</p>
        </div>
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
