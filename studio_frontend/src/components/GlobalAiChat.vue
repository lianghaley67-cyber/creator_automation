<script>
import { computed, ref } from "vue";
import { useStudioContext } from "../pages/useStudioContext.js";
import { normalizeErrorMessage } from "../utils/errors.js";

function readSavedPosition() {
  try {
    const parsed = JSON.parse(localStorage.getItem("globalAiChatPosition") || "null");
    if (parsed && Number.isFinite(parsed.left) && Number.isFinite(parsed.top)) return parsed;
  } catch (error) {
    // Ignore broken localStorage values and fall back to the default corner.
  }
  return null;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

export default {
  name: "GlobalAiChat",
  setup() {
    const ctx = useStudioContext("GlobalAiChat");
    const open = ref(false);
    const savedPosition = readSavedPosition();
    const position = ref(savedPosition || { left: window.innerWidth - 174, top: window.innerHeight - 82 });
    const dragState = ref(null);
    const suppressNextClick = ref(false);
    const savedAiKey = localStorage.getItem("globalAiChatProvider") || "";
    const provider = ref(savedAiKey.includes(":") ? savedAiKey : "qwen:qwen3.7-plus");
    const input = ref("");
    const sending = ref(false);
    const messages = ref([
      {
        role: "assistant",
        content: "我是你的剧情讨论助手。可以把章节计划、上一章结尾或卡住的剧情发给我，我会优先帮你找新事件、新冲突和去重问题。",
      },
    ]);
    const providers = [
      { value: "qwen:qwen3.7-plus", provider: "qwen", model: "qwen3.7-plus", label: "通义千问 qwen3.7-plus" },
      { value: "qwen:qwen-plus-2025-07-28", provider: "qwen", model: "qwen-plus-2025-07-28", label: "通义千问 qwen-plus-2025-07-28" },
      { value: "qwen:qwen-max", provider: "qwen", model: "qwen-max", label: "通义千问 qwen-max" },
      { value: "deepseek:deepseek-chat", provider: "deepseek", model: "deepseek-chat", label: "DeepSeek Chat" },
      { value: "deepseek:deepseek-v4-flash:thinking", provider: "deepseek", model: "deepseek-v4-flash", thinking: true, reasoningEffort: "high", label: "DeepSeek V4 Flash · 思维模式" },
      { value: "deepseek:deepseek-v4-pro:thinking", provider: "deepseek", model: "deepseek-v4-pro", thinking: true, reasoningEffort: "max", label: "DeepSeek V4 Pro · 思维模式" },
      { value: "deepseek:deepseek-v4-flash", provider: "deepseek", model: "deepseek-v4-flash", label: "DeepSeek V4 Flash · 非思维" },
      { value: "openai:gpt-4o-mini", provider: "openai", model: "gpt-4o-mini", label: "OpenAI gpt-4o-mini" },
      { value: "local:local-plot-consultant", provider: "local", model: "local-plot-consultant", label: "本地建议" },
    ];
    const selectedAi = computed(() => providers.find((item) => item.value === provider.value) || providers[0]);
    const contextText = computed(() => {
      const page = ctx.activeTab?.value || "overview";
      const title = ctx.modulePageMeta?.value?.title || "灵感工坊";
      return `当前页面：${title}（${page}）。用户可能正在讨论小说章节、内容生产或运营策略。`;
    });
    const chatPositionStyle = computed(() => ({
      left: `${position.value.left}px`,
      top: `${position.value.top}px`,
    }));

    function clampPosition(left, top) {
      const safeWidth = 174;
      const safeHeight = 60;
      return {
        left: clamp(left, 8, Math.max(8, window.innerWidth - safeWidth)),
        top: clamp(top, 8, Math.max(8, window.innerHeight - safeHeight)),
      };
    }

    function savePosition(nextPosition) {
      localStorage.setItem("globalAiChatPosition", JSON.stringify(nextPosition));
    }

    function startDrag(event) {
      if (event.button !== undefined && event.button !== 0) return;
      const pointer = event.currentTarget;
      pointer?.setPointerCapture?.(event.pointerId);
      dragState.value = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        startLeft: position.value.left,
        startTop: position.value.top,
        moved: false,
      };
    }

    function moveDrag(event) {
      const state = dragState.value;
      if (!state || state.pointerId !== event.pointerId) return;
      const dx = event.clientX - state.startX;
      const dy = event.clientY - state.startY;
      if (Math.abs(dx) + Math.abs(dy) > 4) state.moved = true;
      position.value = clampPosition(state.startLeft + dx, state.startTop + dy);
    }

    function stopDrag(event) {
      const state = dragState.value;
      if (!state || state.pointerId !== event.pointerId) return;
      event.currentTarget?.releasePointerCapture?.(event.pointerId);
      dragState.value = null;
      if (state.moved) suppressNextClick.value = true;
      savePosition(position.value);
    }

    function toggleOpen() {
      if (suppressNextClick.value) {
        suppressNextClick.value = false;
        return;
      }
      open.value = !open.value;
      position.value = clampPosition(position.value.left, position.value.top);
      savePosition(position.value);
    }

    async function send() {
      const text = input.value.trim();
      if (!text || sending.value) return;
      messages.value.push({ role: "user", content: text });
      input.value = "";
      sending.value = true;
      localStorage.setItem("globalAiChatProvider", provider.value);
      try {
        const result = await ctx.requestApi("/api/ai-chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            provider: selectedAi.value.provider,
            model: selectedAi.value.model,
            thinking: Boolean(selectedAi.value.thinking),
            reasoning_effort: selectedAi.value.reasoningEffort || "",
            messages: messages.value.filter((item) => item.role !== "system"),
            context: contextText.value,
          }),
        }, 70000);
        messages.value.push({
          role: "assistant",
          content: result?.response || "这次没有拿到有效回复，可以换个模型或再问一次。",
          meta: result?.fallback ? "本地兜底" : `${result?.provider || provider.value} · ${result?.model || ""}`,
        });
      } catch (error) {
        messages.value.push({ role: "assistant", content: normalizeErrorMessage(error, "AI 聊天失败。"), meta: "请求失败" });
      } finally {
        sending.value = false;
      }
    }

    function clearChat() {
      messages.value = [
        {
          role: "assistant",
          content: "已清空。你可以继续把章节计划、人物动机或卡住的桥段发给我。",
        },
      ];
    }

    return {
      open,
      provider,
      providers,
      selectedAi,
      input,
      sending,
      messages,
      chatPositionStyle,
      send,
      clearChat,
      startDrag,
      moveDrag,
      stopDrag,
      toggleOpen,
    };
  },
};
</script>

<template>
  <aside class="global-ai-chat" :class="{ open }" :style="chatPositionStyle">
    <button
      class="global-ai-chat-tab"
      type="button"
      @pointerdown="startDrag"
      @pointermove="moveDrag"
      @pointerup="stopDrag"
      @pointercancel="stopDrag"
      @click="toggleOpen"
    >
      <span>AI</span>
      <strong>剧情沟通</strong>
    </button>
    <div v-if="open" class="global-ai-chat-panel">
      <header class="global-ai-chat-head">
        <div>
          <strong>AI 聊天工具</strong>
          <span>默认 qwen3.7-plus，可切换模型</span>
        </div>
        <button type="button" @click="open = false">×</button>
      </header>
      <div class="global-ai-chat-tools">
        <select v-model="provider">
          <option v-for="item in providers" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
        <button type="button" @click="clearChat">清空</button>
      </div>
      <div class="global-ai-chat-messages">
        <article v-for="(message, index) in messages" :key="index" :class="['global-ai-message', message.role]">
          <small>{{ message.role === "user" ? "我" : "AI" }}<em v-if="message.meta"> · {{ message.meta }}</em></small>
          <p>{{ message.content }}</p>
        </article>
      </div>
      <form class="global-ai-chat-input" @submit.prevent="send">
        <textarea
          v-model="input"
          rows="3"
          placeholder="例：帮我看第2章计划是否重复上一章，下一场冲突怎么升级？"
          @keydown.ctrl.enter.prevent="send"
        ></textarea>
        <button type="submit" :disabled="sending || !input.trim()">{{ sending ? "发送中..." : "发送" }}</button>
      </form>
    </div>
  </aside>
</template>
