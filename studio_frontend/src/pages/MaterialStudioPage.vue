<script>
import { useStudioContext } from "./useStudioContext.js";

export default {
  name: "MaterialStudioPage",
  setup() {
    return useStudioContext("MaterialStudioPage");
  }
};
</script>

<template>
      <section v-if="activeTab === 'materials'" class="panel wechat-entry-card sticky-wechat-entry">
      <div class="wechat-qr-box" :class="{ empty: !wechatQrImageUrl }">
        <img v-if="wechatQrImageUrl" :src="wechatQrImageUrl" :alt="`${wechatEntry?.account_name || '微信素材入口'}二维码`" />
        <span v-else>二维码未配置</span>
      </div>
      <div class="wechat-entry-copy">
        <strong>当前微信素材接收账号</strong>
        <p>
          {{ wechatEntry?.receiver_label || "当前 AppID 对应的公众号" }}
          · AppID {{ wechatEntry?.app_id_masked || "未配置" }}
        </p>
        <p>{{ wechatEntry?.receiver_description }}</p>
        <p>关注这个 AppID 对应的真实公众号后，可以发送文字或语音；页面点击"刷新微信素材"即可加载。</p>
        <p v-if="wechatEntry?.voice_fallback_enabled" class="meta">
          兜底转写：{{ wechatEntry.voice_fallback_configured ? "已配置 AppID/AppSecret，微信不返回识别文本时会尝试下载语音转写。" : "未配置 AppID/AppSecret，只能依赖微信 Recognition 识别文本。" }}
        </p>
        <p class="meta">回调地址：{{ wechatEntry?.callback_url || "/api/integrations/wechat/callback" }}</p>
        <p v-if="wechatEntry && !wechatEntry.callback_token_configured" class="error-text">
          微信回调 Token 未配置。请先设置 WECHAT_CALLBACK_TOKEN，并在公众号后台"设置与开发 → 基本配置 → 服务器配置"填写同一个 Token。
        </p>
        <p v-else-if="wechatEntry && !wechatEntry.callback_received" class="error-text">
          服务器还没有收到过微信回调。扫码关注并不会自动上传素材；必须在公众号后台启用服务器配置，URL 使用上面的回调地址，消息加解密方式先选"明文模式"。
        </p>
        <p v-else-if="wechatEntry?.callback_received" class="meta">
          微信回调已接通，服务器已收到 {{ wechatEntry.callback_event_count }} 条回调记录。
        </p>
        <p v-if="!wechatQrImageUrl" class="error-text">当前 AppID 已配置，但二维码未配置。请把同一个公众号的二维码图片地址写入 WECHAT_QR_IMAGE_URL，不能继续使用旧测试号二维码。</p>
      </div>
      </section>

    <!-- 素材与生成 Tab -->
    <div v-if="activeTab === 'materials'">
      <section class="panel material-intake-panel">
        <div class="panel-header">
          <h2>添加素材</h2>
          <span class="eyebrow">网页文字 · 网页录音 · 音频文件 · 微信文字/语音</span>
        </div>
        <div class="material-intake-grid">
          <label class="field material-text-field">
            <span>直接输入文字</span>
            <textarea
              v-model="materialTextInput"
              rows="5"
              placeholder="写下今天发生的事、你的判断、剪辑心得，或者粘贴一段待整理素材。"
            ></textarea>
          </label>
          <div class="material-intake-actions">
            <button class="btn accent" type="button" :disabled="busy.materialIntake" @click="submitTextMaterial">
              {{ busy.materialIntake ? "提交中..." : "提交文字素材" }}
            </button>
            <button
              v-if="!materialRecording"
              class="btn primary"
              type="button"
              :disabled="busy.materialVoice || !canRecordTrendVoice"
              @click="startMaterialRecording"
            >
              {{ canRecordTrendVoice ? "开始语音录入" : "浏览器录音不可用" }}
            </button>
            <button
              v-else
              class="btn accent"
              type="button"
              :disabled="busy.materialVoice"
              @click="stopMaterialRecording"
            >停止并提交</button>
            <label class="upload-audio-label">
              {{ busy.materialVoice ? "处理中..." : "上传音频/视频转文字" }}
              <input type="file" accept="audio/*,video/*" :disabled="busy.materialVoice" @change="uploadMaterialAudio" />
            </label>
            <span v-if="materialVoiceNote" class="meta">{{ materialVoiceNote }}</span>
          </div>
        </div>
        <p class="meta">
          四种入口最终进入同一个素材收件箱，但会保留来源标记。微信入口使用上方显示的真实 AppID 对应公众号。
        </p>
      </section>
      <section id="wechat-inbox" class="panel">
      <div class="panel-header">
        <h2>统一素材收件箱</h2>
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
      <div class="meta">网页提交会立即刷新；微信发新消息后点击"刷新微信素材"。</div>
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
            <span class="mail-source">{{ item.source_type || "unknown" }}</span>
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
            <button
              v-if="selectedWechatMaterial.script"
              class="btn accent small"
              type="button"
              :disabled="busy.distribution === String(selectedWechatMaterial.id)"
              @click="prepareMaterialDistribution(selectedWechatMaterial)"
            >
              {{ busy.distribution === String(selectedWechatMaterial.id) ? "准备中..." : "生成公众号 + 小红书发布包" }}
            </button>
            <button class="btn secondary small danger-action" type="button" :disabled="busy.refreshWechat" @click="deleteWechatMaterial(selectedWechatMaterial)">删除本条</button>
          </div>
          <div v-if="materialDistributionDrafts[selectedWechatMaterial.id]" class="publish-card material-publish-card">
            <div class="publish-card-head">
              <strong>双渠道发布工作台</strong>
              <span>公众号与小红书使用两套独立 Skill 生成</span>
            </div>
            <div class="channel-pipeline-grid">
              <div class="channel-pipeline">
                <strong>微信公众号</strong>
                <span class="meta">Skill：{{ materialDistributionDrafts[selectedWechatMaterial.id].wechat?.skill_id }}</span>
                <label class="field">
                  <span>文章标题</span>
                  <input readonly :value="materialDistributionDrafts[selectedWechatMaterial.id].title" />
                </label>
                <p class="meta">长文章结构：背景、判断、行动建议。不会直接复用小红书正文。</p>
              </div>
              <div class="channel-pipeline">
                <strong>小红书</strong>
                <span class="meta">Skill：{{ materialDistributionDrafts[selectedWechatMaterial.id].xiaohongshu?.skill_id }} + {{ materialDistributionDrafts[selectedWechatMaterial.id].xiaohongshu?.image_skill_id }}</span>
                <label class="field">
                  <span>笔记标题</span>
                  <input readonly :value="materialDistributionDrafts[selectedWechatMaterial.id].xiaohongshu?.title" />
                </label>
                <textarea class="caption-box" readonly :value="materialDistributionDrafts[selectedWechatMaterial.id].xiaohongshu?.body"></textarea>
              </div>
            </div>
            <div v-if="materialDistributionDrafts[selectedWechatMaterial.id].xiaohongshu?.card_urls?.length" class="xiaohongshu-card-preview">
              <a
                v-for="(cardUrl, cardIndex) in materialDistributionDrafts[selectedWechatMaterial.id].xiaohongshu.card_urls"
                :key="cardUrl"
                :href="mediaUrl(cardUrl)"
                target="_blank"
              >
                <img :src="mediaUrl(cardUrl)" :alt="`小红书图文第 ${cardIndex + 1} 页`" />
              </a>
            </div>
            <div class="next-step-card">
              <strong>小红书下一步：{{ xiaohongshuNextStep(materialDistributionDrafts[selectedWechatMaterial.id]).title }}</strong>
              <p>{{ xiaohongshuNextStep(materialDistributionDrafts[selectedWechatMaterial.id]).body }}</p>
            </div>
            <div class="publish-buttons primary-flow-actions">
              <label class="upload-audio-label">
                {{ busy.wechatCover ? "上传封面中..." : (wechatEntry?.cover_configured ? "更换公众号封面" : "先上传公众号封面") }}
                <input type="file" accept="image/*" :disabled="busy.wechatCover" @change="uploadWechatCover" />
              </label>
              <button
                class="btn accent small"
                type="button"
                :disabled="busy.wechatDraft === String(materialDistributionDrafts[selectedWechatMaterial.id].id)"
                @click="createMaterialWechatDraft(selectedWechatMaterial)"
              >
                {{
                  busy.wechatDraft === String(materialDistributionDrafts[selectedWechatMaterial.id].id)
                    ? "发送中..."
                    : "发送到公众号草稿箱"
                }}
              </button>
              <button
                class="btn accent small"
                :disabled="busy.xiaohongshuDirectPublish === String(materialDistributionDrafts[selectedWechatMaterial.id].id) || materialDistributionDrafts[selectedWechatMaterial.id].xiaohongshu?.status === 'published'"
                @click="directPublishXiaohongshu(materialDistributionDrafts[selectedWechatMaterial.id], (result) => applyMaterialDistributionResult(selectedWechatMaterial.id, result))"
              >{{ busy.xiaohongshuDirectPublish === String(materialDistributionDrafts[selectedWechatMaterial.id].id) ? "发布中..." : "直接发布到小红书" }}</button>
            </div>
            <details class="secondary-actions">
              <summary>备用操作：复制、下载、预览</summary>
              <div class="publish-buttons">
                <button class="btn secondary small" @click="copyText(materialDistributionDrafts[selectedWechatMaterial.id].xiaohongshu?.title, '小红书标题已复制。')">复制小红书标题</button>
                <button class="btn secondary small" @click="copyText(materialDistributionDrafts[selectedWechatMaterial.id].xiaohongshu?.body, '小红书正文已复制。')">复制小红书正文</button>
                <a class="btn secondary small" :href="mediaUrl(materialDistributionDrafts[selectedWechatMaterial.id].xiaohongshu?.package_url)" download>下载备用图文包</a>
                <a
                  class="btn secondary small"
                  :href="mediaUrl(materialDistributionDrafts[selectedWechatMaterial.id].wechat?.article_html_url)"
                  target="_blank"
                >预览公众号文章</a>
              </div>
            </details>
            <p v-if="!wechatEntry?.cover_configured" class="error-text">
              当前没有公众号封面。请先上传一张 JPG/PNG 封面，上传成功后发送按钮会自动解锁。
            </p>
            <p v-if="wechatDraftErrors[materialDistributionDrafts[selectedWechatMaterial.id].id]" class="error-text">
              {{ wechatDraftErrors[materialDistributionDrafts[selectedWechatMaterial.id].id] }}
            </p>
            <p class="meta">
              状态：{{ materialDistributionDrafts[selectedWechatMaterial.id].wechat?.status === "draft_created" ? "已进入公众号草稿箱" : "等待发送" }}
              <template v-if="materialDistributionDrafts[selectedWechatMaterial.id].wechat?.verified">
                · 微信已读取核验 · AppID {{ materialDistributionDrafts[selectedWechatMaterial.id].wechat?.app_id_masked }}
                · 草稿ID {{ materialDistributionDrafts[selectedWechatMaterial.id].wechat?.draft_media_id }}
              </template>
            </p>
            <div class="xiaohongshu-progress">
              <strong>小红书状态：{{ xiaohongshuStatusLabel(materialDistributionDrafts[selectedWechatMaterial.id]) }}</strong>
              <template v-if="['publishing', 'failed'].includes(materialDistributionDrafts[selectedWechatMaterial.id].xiaohongshu?.status)">
                <input
                  v-model="xiaohongshuPublishUrls[materialDistributionDrafts[selectedWechatMaterial.id].id]"
                  placeholder="发布后粘贴小红书笔记链接"
                />
                <button
                  class="btn accent small"
                  @click="finishXiaohongshuPublishing(materialDistributionDrafts[selectedWechatMaterial.id], (result) => applyMaterialDistributionResult(selectedWechatMaterial.id, result))"
                >标记已发布</button>
              </template>
            </div>
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

    <section class="panel">
      <div class="panel-header">
        <h2>小红书服务器短信登录</h2>
        <button
          class="btn secondary small"
          type="button"
          :disabled="busy.xiaohongshuSession"
          @click="refreshXiaohongshuServerSession"
        >{{ busy.xiaohongshuSession ? "检查中..." : "检查登录状态" }}</button>
      </div>
      <p class="meta">
        手机号和验证码只用于本次服务器登录，不写入数据库。登录成功后，自动发布入口才可用。
        如果小红书出现风控提醒，建议改用下载图文包后手动发布。
      </p>
      <p v-if="xiaohongshuServerSession?.message" class="meta">{{ xiaohongshuServerSession.message }}</p>
      <div v-if="!xiaohongshuServerSession?.logged_in" class="xiaohongshu-sms-login">
        <label class="field">
          <span>小红书绑定手机号</span>
          <input v-model="xiaohongshuPhone" type="tel" inputmode="numeric" maxlength="11" placeholder="请输入 11 位手机号" />
        </label>
        <button class="btn secondary" type="button" :disabled="busy.xiaohongshuSms" @click="sendXiaohongshuSms">
          {{ busy.xiaohongshuSms ? "发送中..." : "发送验证码" }}
        </button>
        <label class="field">
          <span>短信验证码</span>
          <input v-model="xiaohongshuSmsCode" inputmode="numeric" maxlength="10" placeholder="输入短信验证码" />
        </label>
        <button class="btn primary" type="button" :disabled="busy.xiaohongshuVerify" @click="verifyXiaohongshuSms">
          {{ busy.xiaohongshuVerify ? "登录中..." : "验证码登录" }}
        </button>
      </div>
      <p v-else class="success-text">服务器小红书已登录，可以直接自动发布；发布结果会直接显示在本页面。</p>
      <details
        v-if="xiaohongshuServerSession?.screenshot_url && !xiaohongshuServerSession?.logged_in"
        @toggle="toggleXiaohongshuRemote"
      >
        <summary>打开服务器实时操作画面</summary>
        <p v-if="xiaohongshuServerSession?.challenge_visible" class="warning-text">
          已检测到滑块：从滑块中心按住并拖到缺口位置，松手后等待验证结果。
        </p>
        <p v-else class="meta">
          当前没有滑块，不需要操作下方画面。请重新发送验证码，并在收到后 60 秒内点击一次"验证码登录"。
        </p>
        <div
          class="xiaohongshu-remote-frame"
          :class="{ busy: busy.xiaohongshuDrag, interactive: xiaohongshuServerSession?.challenge_visible }"
        >
          <img
            class="xiaohongshu-login-preview interactive"
            :src="mediaUrl(xiaohongshuServerSession.screenshot_url)"
            alt="可拖动的小红书服务器登录画面"
            draggable="false"
            @pointerdown.prevent="startXiaohongshuDrag"
            @pointermove.prevent="moveXiaohongshuDrag"
            @pointerup.prevent="finishXiaohongshuDrag"
            @pointercancel="cancelXiaohongshuDrag"
          />
          <svg v-if="xiaohongshuDragLine" class="xiaohongshu-drag-overlay">
            <line
              :x1="xiaohongshuDragLine.x1"
              :y1="xiaohongshuDragLine.y1"
              :x2="xiaohongshuDragLine.x2"
              :y2="xiaohongshuDragLine.y2"
            />
            <circle :cx="xiaohongshuDragLine.x1" :cy="xiaohongshuDragLine.y1" r="8" />
          </svg>
          <span v-if="busy.xiaohongshuDrag" class="xiaohongshu-remote-loading">服务器正在拖动并刷新画面...</span>
        </div>
      </details>
    </section>

    <section v-if="xiaohongshuSystemDrafts.length" class="panel">
      <div class="panel-header">
        <h2>小红书系统草稿箱</h2>
        <button class="btn secondary small" type="button" @click="refreshDistributionTasks">刷新草稿</button>
      </div>
      <p class="meta">
        这里展示历史小红书发布包和处理结果。当前主流程只保留自动发布，同时提供下载图文包作为备用。
      </p>
      <div class="draft-list">
        <article v-for="draft in xiaohongshuSystemDrafts" :key="draft.id" class="publish-card">
          <div class="script-preview-head">
            <strong>{{ draft.xiaohongshu?.title || draft.title }}</strong>
            <span>{{ draft.xiaohongshu?.draft_saved_at || draft.updated_at }}</span>
          </div>
          <p>{{ draft.xiaohongshu?.body }}</p>
          <p class="meta">{{ xiaohongshuStatusLabel(draft) }}</p>
          <p v-if="draft.xiaohongshu?.save_error" class="warning-text">
            {{ draft.xiaohongshu.save_error }}
          </p>
          <a
            v-if="draft.xiaohongshu?.result_screenshot_url"
            class="inline-link"
            :href="mediaUrl(draft.xiaohongshu.result_screenshot_url)"
            target="_blank"
            rel="noreferrer"
          >在新窗口查看服务器保存结果</a>
          <a
            v-if="draft.xiaohongshu?.result_screenshot_url"
            class="xiaohongshu-result-preview"
            :href="mediaUrl(draft.xiaohongshu.result_screenshot_url)"
            target="_blank"
            rel="noreferrer"
            title="点击放大服务器草稿箱截图"
          >
            <img
              :src="mediaUrl(draft.xiaohongshu.result_screenshot_url)"
              alt="服务器小红书草稿保存结果"
            />
          </a>
          <div class="next-step-card">
            <strong>小红书下一步：{{ xiaohongshuNextStep(draft).title }}</strong>
            <p>{{ xiaohongshuNextStep(draft).body }}</p>
          </div>
          <div class="publish-buttons primary-flow-actions">
            <button
              class="btn accent small"
              :disabled="busy.xiaohongshuDirectPublish === String(draft.id) || draft.xiaohongshu?.status === 'published'"
              @click="directPublishXiaohongshu(draft, applySavedDistributionTask)"
            >{{ busy.xiaohongshuDirectPublish === String(draft.id) ? "发布中..." : "直接发布到小红书" }}</button>
          </div>
          <details class="secondary-actions">
            <summary>备用操作：复制、下载</summary>
            <div class="publish-buttons">
              <button class="btn secondary small" @click="copyText(draft.xiaohongshu?.body, '小红书正文已复制。')">复制正文</button>
              <a class="btn secondary small" :href="mediaUrl(draft.xiaohongshu?.package_url)" download>下载备用图文包</a>
            </div>
          </details>
        </article>
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
            <button class="btn secondary small" :disabled="busy.audio === String(job.id)" @click="generateJobAudio(job)">
              {{ busy.audio === String(job.id) ? "生成中..." : "补生成音频" }}
            </button>
            <button class="btn accent small" :disabled="busy.distribution === String(job.id)" @click="prepareDistribution(job)">
              {{ busy.distribution === String(job.id) ? "准备中..." : "准备多平台分发" }}
            </button>
            <button class="btn accent small" :disabled="busy.publish === String(job.id)" @click="prepareDouyinPublish(job)">
              {{ busy.publish === String(job.id) ? "准备中..." : "发布助手" }}
            </button>
          </div>
          <audio
            v-if="audioPreviews[job.id]?.audio_url"
            :src="mediaUrl(audioPreviews[job.id].audio_url)"
            controls
            preload="metadata"
          ></audio>
          <div v-if="distributionDrafts[job.id]" class="publish-card">
            <div class="publish-card-head">
              <strong>长期分发工作台</strong>
              <span>公众号自动进草稿，小红书生成稳定发布包</span>
            </div>
            <label class="field">
              <span>小红书标题</span>
              <input readonly :value="distributionDrafts[job.id].xiaohongshu?.title" />
            </label>
            <label class="field">
              <span>小红书正文</span>
              <textarea class="caption-box" readonly :value="distributionDrafts[job.id].xiaohongshu?.body"></textarea>
            </label>
            <div class="next-step-card">
              <strong>小红书下一步：{{ xiaohongshuNextStep(distributionDrafts[job.id]).title }}</strong>
              <p>{{ xiaohongshuNextStep(distributionDrafts[job.id]).body }}</p>
            </div>
            <div class="publish-buttons primary-flow-actions">
              <label class="upload-audio-label">
                {{ busy.wechatCover ? "上传封面中..." : (wechatEntry?.cover_configured ? "更换公众号封面" : "上传公众号封面") }}
                <input type="file" accept="image/*" :disabled="busy.wechatCover" @change="uploadWechatCover" />
              </label>
              <button
                class="btn accent small"
                :disabled="busy.xiaohongshuDirectPublish === String(distributionDrafts[job.id].id) || distributionDrafts[job.id].xiaohongshu?.status === 'published'"
                @click="directPublishXiaohongshu(distributionDrafts[job.id], (result) => applyJobDistributionResult(job.id, result))"
              >{{ busy.xiaohongshuDirectPublish === String(distributionDrafts[job.id].id) ? "发布中..." : "直接发布到小红书" }}</button>
              <button
                class="btn accent small"
                :disabled="busy.wechatDraft === String(distributionDrafts[job.id].id)"
                @click="createWechatDraft(job)"
              >
                {{
                  busy.wechatDraft === String(distributionDrafts[job.id].id)
                    ? "提交中..."
                    : "发送到公众号草稿箱"
                }}
              </button>
            </div>
            <details class="secondary-actions">
              <summary>备用操作：复制、下载</summary>
              <div class="publish-buttons">
                <button
                  class="btn secondary small"
                  @click="copyText(distributionDrafts[job.id].xiaohongshu?.body, '小红书正文已复制。')"
                >复制正文</button>
                <button
                  class="btn secondary small"
                  @click="copyText(distributionDrafts[job.id].xiaohongshu?.title, '小红书标题已复制。')"
                >复制标题</button>
                <a class="btn secondary small" :href="mediaUrl(distributionDrafts[job.id].xiaohongshu?.package_url)" download>下载备用图文包</a>
              </div>
            </details>
            <p v-if="wechatDraftErrors[distributionDrafts[job.id].id]" class="error-text">
              {{ wechatDraftErrors[distributionDrafts[job.id].id] }}
            </p>
            <div class="xiaohongshu-progress">
              <strong>小红书状态：{{ xiaohongshuStatusLabel(distributionDrafts[job.id]) }}</strong>
              <template v-if="['publishing', 'failed'].includes(distributionDrafts[job.id].xiaohongshu?.status)">
                <input
                  v-model="xiaohongshuPublishUrls[distributionDrafts[job.id].id]"
                  placeholder="发布后，把小红书笔记链接粘贴到这里"
                />
                <button
                  class="btn accent small"
                  :disabled="busy.xiaohongshu === String(distributionDrafts[job.id].id)"
                  @click="finishXiaohongshuPublishing(distributionDrafts[job.id], (result) => applyJobDistributionResult(job.id, result))"
                >标记已发布</button>
                <button
                  v-if="distributionDrafts[job.id].xiaohongshu?.status !== 'published'"
                  class="btn secondary small"
                  :disabled="busy.xiaohongshu === String(distributionDrafts[job.id].id)"
                  @click="failXiaohongshuPublishing(distributionDrafts[job.id], (result) => applyJobDistributionResult(job.id, result))"
                >记录失败</button>
              </template>
              <a
                v-if="distributionDrafts[job.id].xiaohongshu?.published_note_url"
                :href="distributionDrafts[job.id].xiaohongshu.published_note_url"
                target="_blank"
                rel="noreferrer"
              >查看已发布笔记</a>
            </div>
            <p class="meta">
              公众号：{{ distributionDrafts[job.id].wechat?.status === "draft_created" ? "草稿已创建" : "等待提交" }}
              <template v-if="distributionDrafts[job.id].wechat?.verified">
                · 微信已核验 · AppID {{ distributionDrafts[job.id].wechat?.app_id_masked }}
              </template>
              · 小红书：{{ xiaohongshuStatusLabel(distributionDrafts[job.id]) }}
            </p>
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

    <button v-if="activeTab === 'materials'" class="floating-generate" :disabled="busy.generate" @click="generateKidsVideo">
      {{ busy.generate ? "提交中..." : "生成视频" }}
    </button>
</template>
