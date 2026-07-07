<script>
import { reactive, ref, watch } from "vue";
import { useStudioContext } from "./useStudioContext.js";

export default {
  name: "RealtimeInfoPage",
  setup() {
    const ctx = useStudioContext("RealtimeInfoPage");
    const expandedPlatforms = reactive({ wechat: false, xiaohongshu: false });
    watch(() => ctx.trendDistributionDraft.value?.wechat,      (v) => { if (v) expandedPlatforms.wechat = true; });
    watch(() => ctx.trendDistributionDraft.value?.xiaohongshu, (v) => { if (v) expandedPlatforms.xiaohongshu = true; });

    // 快速选题编辑态
    const topicsEditMode = ref(false);
    const newTopicLabel = ref("");
    const addingTopic = ref(false);

    async function deleteTopic(topic) {
      if (!confirm(`确认删除「${topic.label}」？`)) return;
      try {
        await ctx.requestApi(`/api/ai-trends/preset-topics/${topic.id}`, { method: "DELETE" });
        await ctx.loadPresetTopicsAndSkills();
      } catch (e) {
        ctx.setError("删除失败：" + (e?.message || e));
      }
    }

    async function addTopic() {
      const label = newTopicLabel.value.trim();
      if (!label) { ctx.setError("选题名不能为空"); return; }
      addingTopic.value = true;
      try {
        await ctx.requestApi("/api/ai-trends/preset-topics", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ label, query: label }),
        });
        newTopicLabel.value = "";
        await ctx.loadPresetTopicsAndSkills();
      } catch (e) {
        ctx.setError("添加失败：" + (e?.message || e));
      } finally {
        addingTopic.value = false;
      }
    }

    return { ...ctx, expandedPlatforms, topicsEditMode, newTopicLabel, addingTopic, deleteTopic, addTopic };
  }
};
</script>

<template>
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
            <button class="btn primary" :disabled="busy.trendSummarize || !aiTrends.length" @click="generateTrendAiSummary">
              {{ busy.trendSummarize ? "摘要中..." : (trendAiSummary ? "重做 AI 摘要" : "生成 AI 摘要") }}
            </button>
            <button class="btn primary" :disabled="busy.notebooklm" @click="createNotebookLmPackage">
              {{ busy.notebooklm ? "生成中..." : "生成 NotebookLM 导入包" }}
            </button>
          </div>
        </div>
        <div class="meta">这里展示的是 Tavily/RSS 等接口抓取到的资讯，不是系统自己的主观看法；生成文案时会提醒 AI 输出仍需要人来判断。</div>
        <div class="trend-flow-hint">{{ trendNextAction }}</div>
        <section class="content-workflow-panel" aria-label="内容生成工作流">
          <div class="content-workflow-header">
            <div>
              <strong>今天只看下一步</strong>
              <span>{{ contentWorkflow.nextAction }}</span>
            </div>
            <b>{{ contentWorkflow.nextButtonLabel }}</b>
          </div>
          <div class="content-workflow-steps">
            <div
              v-for="step in contentWorkflow.steps"
              :key="step.id"
              class="workflow-step"
              :class="step.status"
            >
              <span>{{ step.label }}</span>
              <small>{{ step.helper }}</small>
            </div>
          </div>
        </section>

        <!-- 快速选题 Chips -->
        <div class="preset-topics-row">
          <span class="preset-topics-label">快速选题：</span>
          <template v-for="topic in presetTopics" :key="topic.id">
            <span v-if="topicsEditMode" class="topic-chip topic-chip-edit">
              {{ topic.label }}
              <button class="topic-chip-del" @click="deleteTopic(topic)" title="删除">×</button>
            </span>
            <button v-else
              class="topic-chip"
              :class="{ active: trendSearchQuery === topic.query }"
              @click="trendSearchQuery = topic.query; refreshAiTrends(true)"
            >{{ topic.label }}</button>
          </template>
          <button class="topic-chip topic-chip-manage" @click="topicsEditMode = !topicsEditMode">
            {{ topicsEditMode ? '完成' : '管理' }}
          </button>
        </div>
        <!-- 新增选题表单（编辑态） -->
        <div v-if="topicsEditMode" class="preset-topics-add">
          <input v-model="newTopicLabel" class="topics-add-input" placeholder="输入选题名，如：Cursor实战" maxlength="30"
            @keydown.enter.prevent="addTopic" />
          <button class="btn accent small" :disabled="addingTopic" @click="addTopic">
            {{ addingTopic ? '添加中...' : '+ 添加' }}
          </button>
        </div>

        <!-- 自定义搜索 -->
        <div class="trend-search-box">
          <label for="trend-search-query">或自定义主题</label>
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

        <div class="trend-direction-box">
          <label for="trend-content-direction">我的内容方向/思想</label>
          <textarea
            id="trend-content-direction"
            v-model="trendContentDirection"
            rows="4"
            placeholder="例如：写给像我一样想学 AI 但时间很碎的职场宝妈；希望读者看完知道这个工具能解决什么问题、适合谁、第一步怎么试、哪里需要谨慎。"
          ></textarea>
          <span>这段会进入公众号和小红书生成上下文。写得越具体，文案越不容易空泛。</span>
        </div>

        <div v-if="!aiTrends.length" class="meta">暂无 AI 日报。系统会每天自动抓取，也可以点击"立即抓取"。</div>
        <div v-else class="trend-card" :class="{ fresh: trendFreshHighlight }">
          <div v-if="busy.refreshTrends" class="trend-loading-strip">正在刷新资讯，完成后会自动更新这里。</div>
          <div class="script-preview-head">
            <strong>{{ aiTrends[0].title }}</strong>
            <span>{{ aiTrends[0].created_at }}</span>
          </div>
          <p>{{ aiTrends[0].summary }}</p>
          <ul>
            <li v-for="item in (aiTrends[0].items || []).slice(0, 8)" :key="item.url || item.title" class="trend-news-item">
              <div class="trend-news-main">
                <a v-if="item.url" :href="item.url" target="_blank" rel="noreferrer">{{ item.title }}</a>
                <strong v-else>{{ item.title }}</strong>
                <span>{{ item.summary }}</span>
              </div>
              <div class="trend-item-actions">
                <button class="btn secondary small" :disabled="busy.trendDistWechat" @click="prepareTrendDistribution(false, 'wechat', item)">
                  {{ busy.trendDistWechat ? "..." : "→ 公众号" }}
                </button>
                <button class="btn secondary small" :disabled="busy.trendDistXhs" @click="prepareTrendDistribution(false, 'xiaohongshu', item)">
                  {{ busy.trendDistXhs ? "..." : "→ 小红书" }}
                </button>
              </div>
            </li>
          </ul>
          <div class="trend-angles">
            <strong>可转化选题角度</strong>
            <span v-for="angle in aiTrends[0].angles || []" :key="angle">{{ angle }}</span>
          </div>

          <!-- AI 摘要区块 -->
          <div class="trend-ai-summary-block">
            <div class="trend-ai-summary-head">
              <strong>AI 智能摘要</strong>
              <span class="meta">先把资讯翻译成“普通人能怎么用”。</span>
            </div>
            <div v-if="trendAiSummary && !trendAiSummary.error" class="trend-ai-summary-content">
              <p class="summary-one-sentence">{{ trendAiSummary.one_sentence }}</p>
              <ul class="summary-key-points">
                <li v-for="point in trendAiSummary.key_points || []" :key="point">{{ point }}</li>
              </ul>
              <p class="summary-plain">{{ trendAiSummary.plain_explanation }}</p>
              <div class="summary-angles" v-if="trendAiSummary.content_angles?.length">
                <strong>适合转成内容的角度：</strong>
                <span v-for="angle in trendAiSummary.content_angles" :key="angle" class="angle-chip">{{ angle }}</span>
              </div>
              <div v-if="trendAiSummary.skill_reason" class="summary-skill-hint">
                <span>推荐 Skill：{{ trendAiSummary.skill_reason }}</span>
              </div>
            </div>
            <div v-if="trendAiSummary?.error" class="notice danger small-notice">{{ trendAiSummary.error }}</div>
          </div>

          <!-- 多轮讨论区 -->
          <div class="trend-chat-block" v-if="trendAiSummary && !trendAiSummary.error">
            <button class="trend-chat-toggle" type="button" @click="trendDiscussionOpen = !trendDiscussionOpen">
              <span>
                <strong>多轮讨论：把资讯变成你的选题判断</strong>
                <small>先问清“这条对我的用户有什么用”，再生成文案。</small>
              </span>
              <b>{{ trendDiscussionOpen ? "收起" : "展开" }}</b>
            </button>
            <div v-if="trendDiscussionOpen" class="trend-chat-inner">
              <div class="trend-chat-messages" v-if="trendChatMessages.length">
                <div
                  v-for="(msg, idx) in trendChatMessages"
                  :key="idx"
                  class="chat-message"
                  :class="msg.role"
                >
                  <span class="chat-role">{{ msg.role === 'user' ? '我' : 'AI顾问' }}</span>
                  <p class="chat-content" style="white-space: pre-wrap;">{{ msg.content }}</p>
                </div>
              </div>
              <div class="trend-chat-input-row">
                <textarea
                  v-model="trendChatInput"
                  class="trend-chat-input"
                  placeholder="问问这条资讯对我的受众意味着什么？我该用哪个角度？普通人怎么理解？..."
                  rows="3"
                  @keydown.ctrl.enter.prevent="sendTrendChat"
                ></textarea>
                <button class="btn primary" :disabled="busy.trendChat || !trendChatInput.trim()" @click="sendTrendChat">
                  {{ busy.trendChat ? "思考中..." : "发送（Ctrl+Enter）" }}
                </button>
                <button v-if="trendChatMessages.length" class="btn secondary small" @click="trendChatMessages = []">清空对话</button>
              </div>
            </div>
          </div>

          <!-- Skill 选择器 -->
          <div class="skill-selector-block">
            <div class="skill-selector-head" @click="skillSelectorVisible = !skillSelectorVisible">
              <strong>内容 Skill &amp; 平台分发</strong>
              <span class="meta">选技能 → 生成 → 推送</span>
              <button class="btn secondary small">{{ skillSelectorVisible ? '收起 Skill 卡片' : '展开 Skill 卡片' }}</button>
            </div>

            <!-- 平台分发手风琴：选 Skill → 展开 → 生成 → 推送 -->
            <div class="platform-generate-bar">
              <!-- 公众号 -->
              <div class="pgb-section" :class="{ 'pgb-expanded': expandedPlatforms.wechat }">
                <div class="pgb-row pgb-row-toggle" @click="expandedPlatforms.wechat = !expandedPlatforms.wechat">
                  <span class="pgb-label">公众号</span>
                  <select class="pgb-skill-pick" v-model="selectedWechatSkill" @change="wechatSkillManuallySelected = true" @click.stop>
                    <option value="">— 选 Skill —</option>
                    <option v-for="s in channelSkillsList.filter(s => s.channel === 'wechat')" :key="s.id" :value="s.id">{{ s.name }}</option>
                  </select>
                  <button class="btn accent small" :disabled="busy.trendDistWechat || !selectedWechatSkill" @click.stop="prepareTrendDistribution(false, 'wechat')">
                    {{ busy.trendDistWechat ? '生成中...' : '生成文案' }}
                  </button>
                  <span v-if="trendDistributionDraft?.wechat" class="pgb-done">✓ 已生成</span>
                  <span class="pgb-chevron">{{ expandedPlatforms.wechat ? '▲' : '▼' }}</span>
                </div>
                <div v-if="expandedPlatforms.wechat" class="pgb-detail">
                  <div v-if="trendDistributionDraft?.wechat" class="channel-preview-pane">
                    <label class="field">
                      <span>公众号文章标题</span>
                      <input readonly :value="trendDistributionDraft.wechat?.title" />
                    </label>
                    <div class="publish-buttons primary-flow-actions">
                      <button class="cover-gen-btn" @click="openCoverModal">
                        ✦ {{ wechatEntry?.cover_configured ? "更换封面" : "生成封面" }}
                      </button>
                      <a class="btn secondary small" :href="mediaUrl(trendDistributionDraft.wechat?.article_html_url)" target="_blank">预览公众号文章</a>
                      <button class="btn accent small"
                        :disabled="busy.wechatDraft === String(trendDistributionDraft.id)"
                        @click="createTrendWechatDraft">
                        {{ busy.wechatDraft === String(trendDistributionDraft.id) ? "发送中..." : "发送到公众号草稿箱" }}
                      </button>
                    </div>
                    <p v-if="wechatDraftErrors[trendDistributionDraft.id]" class="error-text">{{ wechatDraftErrors[trendDistributionDraft.id] }}</p>
                    <p v-if="trendDistributionDraft.wechat?.verified" class="meta">
                      公众号草稿已核验 · AppID {{ trendDistributionDraft.wechat?.app_id_masked }} · 草稿ID {{ trendDistributionDraft.wechat?.draft_media_id }}
                    </p>
                  </div>
                  <div v-else class="pgb-empty-hint">点击「生成文案」生成公众号文章</div>
                </div>
              </div>

              <!-- 小红书 -->
              <div class="pgb-section" :class="{ 'pgb-expanded': expandedPlatforms.xiaohongshu }">
                <div class="pgb-row pgb-row-toggle" @click="expandedPlatforms.xiaohongshu = !expandedPlatforms.xiaohongshu">
                  <span class="pgb-label">小红书</span>
                  <select class="pgb-skill-pick" v-model="selectedXhsSkill" @change="xhsSkillManuallySelected = true" @click.stop>
                    <option value="">— 选 Skill —</option>
                    <option v-for="s in channelSkillsList.filter(s => s.channel === 'xiaohongshu')" :key="s.id" :value="s.id">{{ s.name }}</option>
                  </select>
                  <button class="btn primary small" :disabled="busy.trendDistXhs || !selectedXhsSkill" @click.stop="prepareTrendDistribution(false, 'xiaohongshu')">
                    {{ busy.trendDistXhs ? '生成中...' : '生成文案' }}
                  </button>
                  <span v-if="trendDistributionDraft?.xiaohongshu" class="pgb-done">✓ 已生成</span>
                  <span class="pgb-chevron">{{ expandedPlatforms.xiaohongshu ? '▲' : '▼' }}</span>
                </div>
                <div v-if="expandedPlatforms.xiaohongshu" class="pgb-detail">
                  <div v-if="trendDistributionDraft?.xiaohongshu" class="channel-preview-pane">
                    <label class="field">
                      <span>小红书推荐标题</span>
                      <input readonly :value="trendDistributionDraft.xiaohongshu?.title" />
                    </label>
                    <div v-if="trendDistributionDraft.xiaohongshu?.card_urls?.length" class="xiaohongshu-card-preview">
                      <a v-for="(cardUrl, cardIndex) in trendDistributionDraft.xiaohongshu.card_urls" :key="cardUrl" :href="mediaUrl(cardUrl)" target="_blank">
                        <img :src="mediaUrl(cardUrl)" :alt="`小红书图文第 ${cardIndex + 1} 页`" />
                      </a>
                    </div>
                    <label class="field">
                      <span>封面短句</span>
                      <input readonly :value="trendDistributionDraft.xiaohongshu?.cover_text" />
                    </label>
                    <label class="field">
                      <span>小红书正文与话题</span>
                      <textarea class="caption-box" readonly :value="trendDistributionDraft.xiaohongshu?.body"></textarea>
                    </label>
                    <div class="next-step-card">
                      <strong>小红书下一步：{{ xiaohongshuNextStep(trendDistributionDraft).title }}</strong>
                      <p>{{ xiaohongshuNextStep(trendDistributionDraft).body }}</p>
                    </div>
                    <div class="publish-buttons primary-flow-actions">
                      <button class="btn accent small"
                        :disabled="busy.xiaohongshuDirectPublish === String(trendDistributionDraft.id) || trendDistributionDraft.xiaohongshu?.status === 'published'"
                        @click="directPublishXiaohongshu(trendDistributionDraft, applyTrendDistributionResult)"
                      >{{ busy.xiaohongshuDirectPublish === String(trendDistributionDraft.id) ? "发布中..." : "直接发布到小红书" }}</button>
                      <button class="btn secondary small" @click="copyText(trendDistributionDraft.xiaohongshu?.title, '小红书标题已复制。')">复制标题</button>
                      <button class="btn secondary small" @click="copyText(trendDistributionDraft.xiaohongshu?.body, '小红书正文已复制。')">复制正文</button>
                      <a class="btn secondary small" :href="mediaUrl(trendDistributionDraft.xiaohongshu?.package_url)" download>下载图文包</a>
                    </div>
                    <div class="xiaohongshu-progress">
                      <strong>小红书状态：{{ xiaohongshuStatusLabel(trendDistributionDraft) }}</strong>
                      <template v-if="['publishing', 'failed'].includes(trendDistributionDraft.xiaohongshu?.status)">
                        <input v-model="xiaohongshuPublishUrls[trendDistributionDraft.id]" placeholder="发布后，把小红书笔记链接粘贴到这里" />
                        <button class="btn accent small" :disabled="busy.xiaohongshu === String(trendDistributionDraft.id)" @click="finishXiaohongshuPublishing(trendDistributionDraft, applyTrendDistributionResult)">标记已发布</button>
                        <button v-if="trendDistributionDraft.xiaohongshu?.status !== 'published'" class="btn secondary small" :disabled="busy.xiaohongshu === String(trendDistributionDraft.id)" @click="failXiaohongshuPublishing(trendDistributionDraft, applyTrendDistributionResult)">记录失败</button>
                      </template>
                      <a v-if="trendDistributionDraft.xiaohongshu?.published_note_url" :href="trendDistributionDraft.xiaohongshu.published_note_url" target="_blank" rel="noreferrer">查看已发布笔记</a>
                    </div>
                    <ol>
                      <li v-for="step in trendDistributionDraft.xiaohongshu?.publish_steps || []" :key="step">{{ step }}</li>
                    </ol>
                  </div>
                  <div v-else class="pgb-empty-hint">点击「生成文案」生成小红书图文</div>
                </div>
              </div>

            </div>
            <div v-if="skillSelectorVisible" class="skill-selector-body">
              <!-- 公众号 Skill -->
              <div class="skill-channel-group">
                <div class="skill-channel-head">
                  <h4>公众号文章 Skill</h4>
                  <button class="btn-upload-skill" @click.stop="openUploadSkill('wechat')">+ 上传 Skill</button>
                </div>
                <div class="skill-cards-row">
                  <div
                    v-for="skill in channelSkillsList.filter(s => s.channel === 'wechat')"
                    :key="skill.id"
                    class="skill-card"
                    :class="{ selected: selectedWechatSkill === skill.id }"
                    :title="`${skill.name}：${skill.description || '点击选择这套写法'}`"
                    @click="selectedWechatSkill = skill.id; wechatSkillManuallySelected = true"
                  >
                    <div class="skill-card-header">
                      <strong>{{ skill.name }}</strong>
                      <span v-if="selectedWechatSkill === skill.id" class="skill-selected-badge">✓ 已选</span>
                      <button
                        class="skill-delete-btn"
                        title="删除此 Skill"
                        @click.stop="deleteSkill(skill.id, skill.name)"
                      >✕</button>
                    </div>
                    <p class="skill-desc">{{ skill.description }}</p>
                    <div class="skill-tags">
                      <span v-for="tag in skill.persona_tags || []" :key="tag" class="skill-tag">{{ tag }}</span>
                    </div>
                    <div v-if="skill.example" class="skill-example">
                      <div class="skill-example-label">示例标题</div>
                      <div class="skill-example-title">{{ skill.example.title }}</div>
                      <div v-if="skill.example.summary" class="skill-example-summary">{{ skill.example.summary }}</div>
                    </div>
                  </div>
                </div>
              </div>
              <!-- 小红书 Skill -->
              <div class="skill-channel-group">
                <div class="skill-channel-head">
                  <h4>小红书笔记 Skill</h4>
                  <button class="btn-upload-skill" @click.stop="openUploadSkill('xiaohongshu')">+ 上传 Skill</button>
                </div>
                <div class="skill-cards-row">
                  <div
                    v-for="skill in channelSkillsList.filter(s => s.channel === 'xiaohongshu')"
                    :key="skill.id"
                    class="skill-card"
                    :class="{ selected: selectedXhsSkill === skill.id }"
                    :title="`${skill.name}：${skill.description || '点击选择这套写法'}`"
                    @click="selectedXhsSkill = skill.id; xhsSkillManuallySelected = true"
                  >
                    <div class="skill-card-header">
                      <strong>{{ skill.name }}</strong>
                      <span v-if="selectedXhsSkill === skill.id" class="skill-selected-badge">✓ 已选</span>
                      <button
                        class="skill-delete-btn"
                        title="删除此 Skill"
                        @click.stop="deleteSkill(skill.id, skill.name)"
                      >✕</button>
                    </div>
                    <p class="skill-desc">{{ skill.description }}</p>
                    <div class="skill-tags">
                      <span v-for="tag in skill.persona_tags || []" :key="tag" class="skill-tag">{{ tag }}</span>
                    </div>
                    <div v-if="skill.example" class="skill-example">
                      <div class="skill-example-label">示例标题</div>
                      <div class="skill-example-title">{{ skill.example.title }}</div>
                      <div v-if="skill.example.body" class="skill-example-body">{{ skill.example.body?.slice(0, 120) }}...</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 上传 Skill 弹窗 -->
            <div v-if="uploadSkillModal.visible" class="skill-upload-modal-overlay" @click.self="uploadSkillModal.visible = false">
              <div class="skill-upload-modal">
                <div class="modal-head">
                  <strong>上传新 Skill（{{ uploadSkillModal.channel === 'wechat' ? '公众号' : '小红书' }}）</strong>
                  <button class="modal-close" @click="uploadSkillModal.visible = false">✕</button>
                </div>
                <div class="modal-body">
                  <label class="modal-field">
                    <span>Skill 名称</span>
                    <input v-model="uploadSkillModal.name" type="text" placeholder="例：情感共鸣类" />
                  </label>
                  <label class="modal-field">
                    <span>描述（一句话）</span>
                    <input v-model="uploadSkillModal.description" type="text" placeholder="例：从普通人视角解读AI对生活的影响" />
                  </label>
                  <label class="modal-field">
                    <span>标签（逗号分隔）</span>
                    <input v-model="uploadSkillModal.tags" type="text" placeholder="例：情感,普通人,AI影响" />
                  </label>
                  <label class="modal-field">
                    <span>选择 .md 文件</span>
                    <input type="file" accept=".md" @change="uploadSkillModal.file = $event.target.files[0]" />
                  </label>
                  <p v-if="uploadSkillModal.error" class="modal-error">{{ uploadSkillModal.error }}</p>
                </div>
                <div class="modal-footer">
                  <button class="btn secondary small" @click="uploadSkillModal.visible = false">取消</button>
                  <button class="btn accent small" :disabled="uploadSkillModal.uploading" @click="submitUploadSkill">
                    {{ uploadSkillModal.uploading ? '上传中...' : '确认上传' }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- 封面生成弹窗 -->
          <div v-if="coverModal.visible" class="cover-modal-overlay" @click.self="coverModal.visible = false">
            <div class="cover-modal">
              <div class="cover-modal-head">
                <strong>生成公众号封面</strong>
                <button class="modal-close" @click="coverModal.visible = false">✕</button>
              </div>
              <div class="cover-modal-body">
                <div style="display:flex;gap:10px;align-items:center">
                  <button class="btn accent small" :disabled="coverModal.generating" @click="generateCoverImages">
                    {{ coverModal.generating ? "生成中..." : (coverModal.images.length ? "重新生成" : "生成 4 张封面") }}
                  </button>
                  <span class="cover-modal-hint">根据文章标题和正文生成，选用后自动上传到微信</span>
                </div>
                <div v-if="coverModal.error" class="error-text">{{ coverModal.error }}</div>
                <div v-if="coverModal.generating" class="meta">正在生成封面。默认会先生成稳定可用的本地封面；如已配置外部图片模型，最长约 2 分钟。</div>
                <div v-if="coverModal.images.length" class="cover-images-grid">
                  <div v-for="imgUrl in coverModal.images" :key="imgUrl" class="cover-image-item">
                    <img :src="mediaUrl(imgUrl)" alt="封面预览" />
                    <button
                      class="cover-image-use"
                      :disabled="coverModal.usingUrl === imgUrl"
                      @click="useGeneratedCover(imgUrl)"
                    >{{ coverModal.usingUrl === imgUrl ? "上传中..." : "选用" }}</button>
                  </div>
                </div>
                <div class="cover-modal-divider">或上传自己的图片</div>
                <div class="cover-modal-upload">
                  <label class="upload-audio-label">
                    {{ busy.wechatCover ? "上传中..." : "选择本地图片" }}
                    <input type="file" accept="image/*" :disabled="busy.wechatCover" @change="uploadWechatCover" />
                  </label>
                  <span class="cover-modal-hint">JPG / PNG，建议 900×383px</span>
                </div>
              </div>
            </div>
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
              <div class="top-actions">
                <button class="btn secondary small inline" @click="copyText(trendScripts[selectedTrendQuestion].script, '文案已复制')">复制</button>
                <button class="btn accent small inline" :disabled="busy.trendDistribution" @click="prepareTrendDistribution(true, 'wechat')">这篇推公众号</button>
                <button class="btn primary small inline" :disabled="busy.trendDistribution" @click="prepareTrendDistribution(true, 'xiaohongshu')">推荐到小红书</button>
              </div>
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
</template>
