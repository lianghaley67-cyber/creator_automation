<script>
import { useStudioContext } from "./useStudioContext.js";

export default {
  name: "RealtimeInfoPage",
  setup() {
    return useStudioContext("RealtimeInfoPage");
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

        <!-- 预设主题 Chips -->
        <div class="preset-topics-row" v-if="presetTopics.length">
          <span class="preset-topics-label">快速选题：</span>
          <button
            v-for="topic in presetTopics"
            :key="topic.id"
            class="topic-chip"
            :class="{ active: trendSearchQuery === topic.query }"
            @click="trendSearchQuery = topic.query; refreshAiTrends(true)"
          >{{ topic.label }}</button>
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
              <button class="btn secondary small" :disabled="busy.trendDistribution" @click="prepareTrendDistribution(false, 'all', item)">
                {{ busy.trendDistribution ? "生成中..." : "用这条生成" }}
              </button>
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
              <strong>选择内容 Skill</strong>
              <span class="meta">
                已选：{{ selectedWechatSkillName }} · {{ selectedXhsSkillName }}
              </span>
              <button class="btn secondary small">{{ skillSelectorVisible ? '收起' : '展开选择' }}</button>
            </div>
            <div class="skill-selected-summary">
              <span>公众号：{{ selectedWechatSkillName }}</span>
              <span>小红书：{{ selectedXhsSkillName }}</span>
            </div>
            <div v-if="skillSelectorVisible" class="skill-selector-body">
              <!-- 公众号 Skill -->
              <div class="skill-channel-group">
                <h4>公众号文章 Skill</h4>
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
                <h4>小红书笔记 Skill</h4>
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
          </div>

          <!-- 生成和发布按钮 -->
          <div class="publish-buttons trend-publish-actions">
            <button class="btn accent small" :disabled="busy.trendDistribution" @click="prepareTrendDistribution(false, 'wechat')">
              {{ busy.trendDistribution ? "生成中..." : "生成文案 → 推公众号草稿" }}
            </button>
            <button class="btn primary small" :disabled="busy.trendDistribution" @click="prepareTrendDistribution(false, 'xiaohongshu')">
              {{ busy.trendDistribution ? "生成中..." : "生成文案 → 小红书素材包" }}
            </button>
          </div>
          <div v-if="trendDistributionDraft" class="publish-card trend-distribution-card">
            <div class="publish-card-head">
              <strong>实时资讯分发</strong>
              <span>{{ trendDistributionDraft.xiaohongshu?.recommendation_reason }}</span>
            </div>
            <p class="meta">
              公众号 Skill：{{ trendDistributionDraft.wechat?.skill_id }}
              · 小红书 Skill：{{ trendDistributionDraft.xiaohongshu?.skill_id }}
              · 图文 Skill：{{ trendDistributionDraft.xiaohongshu?.image_skill_id }}
            </p>
            <div class="channel-tabs">
              <button
                type="button"
                class="channel-tab"
                :class="{ active: trendDistributionView === 'xiaohongshu' }"
                @click="trendDistributionView = 'xiaohongshu'"
              >小红书图文</button>
              <button
                type="button"
                class="channel-tab"
                :class="{ active: trendDistributionView === 'wechat' }"
                @click="trendDistributionView = 'wechat'"
              >公众号文章</button>
            </div>

            <div v-if="trendDistributionView === 'xiaohongshu'" class="channel-preview-pane">
              <label class="field">
                <span>小红书推荐标题</span>
                <input readonly :value="trendDistributionDraft.xiaohongshu?.title" />
              </label>
              <div v-if="trendDistributionDraft.xiaohongshu?.card_urls?.length" class="xiaohongshu-card-preview">
                <a
                  v-for="(cardUrl, cardIndex) in trendDistributionDraft.xiaohongshu.card_urls"
                  :key="cardUrl"
                  :href="mediaUrl(cardUrl)"
                  target="_blank"
                >
                  <img :src="mediaUrl(cardUrl)" :alt="`实时新闻小红书图文第 ${cardIndex + 1} 页`" />
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
                <button
                  class="btn accent small"
                  :disabled="busy.xiaohongshuDirectPublish === String(trendDistributionDraft.id) || trendDistributionDraft.xiaohongshu?.status === 'published'"
                  @click="directPublishXiaohongshu(trendDistributionDraft, applyTrendDistributionResult)"
                >{{ busy.xiaohongshuDirectPublish === String(trendDistributionDraft.id) ? "发布中..." : "直接发布到小红书" }}</button>
                <label class="upload-audio-label">
                  {{ busy.wechatCover ? "上传封面中..." : (wechatEntry?.cover_configured ? "更换公众号封面" : "上传公众号封面") }}
                  <input type="file" accept="image/*" :disabled="busy.wechatCover" @change="uploadWechatCover" />
                </label>
                <button
                  class="btn accent small"
                  :disabled="busy.wechatDraft === String(trendDistributionDraft.id)"
                  @click="createTrendWechatDraft"
                >
                  {{
                    busy.wechatDraft === String(trendDistributionDraft.id)
                      ? "发送中..."
                      : "发送到公众号草稿箱"
                  }}
                </button>
                <a class="btn secondary small" :href="mediaUrl(trendDistributionDraft.wechat?.article_html_url)" target="_blank">预览公众号文章</a>
                <button class="btn secondary small" @click="copyText(trendDistributionDraft.xiaohongshu?.title, '小红书标题已复制。')">复制标题</button>
                <button class="btn secondary small" @click="copyText(trendDistributionDraft.xiaohongshu?.body, '小红书正文已复制。')">复制正文</button>
                <a class="btn secondary small" :href="mediaUrl(trendDistributionDraft.xiaohongshu?.package_url)" download>下载备用图文包</a>
              </div>
            </div>

            <div v-else class="channel-preview-pane">
              <label class="field">
                <span>公众号文章标题</span>
                <input readonly :value="trendDistributionDraft.wechat?.title || trendDistributionDraft.xiaohongshu?.title" />
              </label>
              <div class="wechat-preview-box">
                <strong>先预览，再进草稿箱</strong>
                <p>公众号文章会使用独立的公众号 Skill，不会直接照搬小红书正文。检查标题、开头、段落和结尾后，再发送到公众号草稿箱。</p>
              </div>
              <div class="publish-buttons primary-flow-actions">
                <label class="upload-audio-label">
                  {{ busy.wechatCover ? "上传中..." : (wechatEntry?.cover_configured ? "更换公众号封面" : "上传公众号封面") }}
                  <input type="file" accept="image/*" :disabled="busy.wechatCover" @change="uploadWechatCover" />
                </label>
                <a class="btn secondary small" :href="mediaUrl(trendDistributionDraft.wechat?.article_html_url)" target="_blank">预览公众号文章</a>
                <button
                  class="btn accent small"
                  :disabled="busy.wechatDraft === String(trendDistributionDraft.id)"
                  @click="createTrendWechatDraft"
                >
                  {{
                    busy.wechatDraft === String(trendDistributionDraft.id)
                      ? "发送中..."
                      : "发送到公众号草稿箱"
                  }}
                </button>
              </div>
            </div>
            <p v-if="wechatDraftErrors[trendDistributionDraft.id]" class="error-text">
              {{ wechatDraftErrors[trendDistributionDraft.id] }}
            </p>
            <div class="xiaohongshu-progress">
              <strong>小红书状态：{{ xiaohongshuStatusLabel(trendDistributionDraft) }}</strong>
              <template v-if="['publishing', 'failed'].includes(trendDistributionDraft.xiaohongshu?.status)">
                <input
                  v-model="xiaohongshuPublishUrls[trendDistributionDraft.id]"
                  placeholder="发布后，把小红书笔记链接粘贴到这里"
                />
                <button
                  class="btn accent small"
                  :disabled="busy.xiaohongshu === String(trendDistributionDraft.id)"
                  @click="finishXiaohongshuPublishing(trendDistributionDraft, applyTrendDistributionResult)"
                >标记已发布</button>
                <button
                  v-if="trendDistributionDraft.xiaohongshu?.status !== 'published'"
                  class="btn secondary small"
                  :disabled="busy.xiaohongshu === String(trendDistributionDraft.id)"
                  @click="failXiaohongshuPublishing(trendDistributionDraft, applyTrendDistributionResult)"
                >记录失败</button>
              </template>
              <a
                v-if="trendDistributionDraft.xiaohongshu?.published_note_url"
                :href="trendDistributionDraft.xiaohongshu.published_note_url"
                target="_blank"
                rel="noreferrer"
              >查看已发布笔记</a>
            </div>
            <p v-if="trendDistributionDraft.wechat?.verified" class="meta">
              公众号草稿已由微信读取核验 · AppID {{ trendDistributionDraft.wechat?.app_id_masked }}
              · 草稿ID {{ trendDistributionDraft.wechat?.draft_media_id }}
            </p>
            <ol>
              <li v-for="step in trendDistributionDraft.xiaohongshu?.publish_steps || []" :key="step">{{ step }}</li>
            </ol>
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
