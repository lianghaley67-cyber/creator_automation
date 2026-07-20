<script>
import { computed, ref } from "vue";
import { useStudioContext } from "../pages/useStudioContext.js";
import { normalizeErrorMessage } from "../utils/errors.js";

export default {
  name: "GlobalAiChat",
  setup() {
    const ctx = useStudioContext("GlobalAiChat");
    const open = ref(false);
    const provider = ref(localStorage.getItem("globalAiChatProvider") || "deepseek");
    const input = ref("");
    const sending = ref(false);
    const messages = ref([
      {
        role: "assistant",
        content: "我是你的剧情讨论助手。可以把章节计划、上一章结尾或卡住的剧情发给我，我会优先帮你找新事件、新冲突和去重问题。",
      },
    ]);
    const providers = [
      { value: "deepseek", label: "DeepSeek" },
      { value: "openai", label: "OpenAI" },
      { value: "qwen", label: "通义千问" },
      { value: "zhipu", label: "智谱 GLM" },
      { value: "local", label: "本地建议" },
    ];
    const contextText = computed(() => {
      const page = ctx.activeTab?.value || "overview";
      const title = ctx.modulePageMeta?.value?.title || "灵感工坊";
      return `当前页面：${title}（${page}）。用户可能正在讨论小说章节、内容生产或运营策略。`;
    });

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
            provider: provider.value,
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

    return { open, provider, providers, input, sending, messages, send, clearChat };
  },
};
</script>

<template>
  <aside class="global-ai-chat" :class="{ open }">
    <button class="global-ai-chat-tab" type="button" @click="open = !open">
      <span>AI</span>
      <strong>剧情沟通</strong>
    </button>
    <div v-if="open" class="global-ai-chat-panel">
      <header class="global-ai-chat-head">
        <div>
          <strong>AI 聊天工具</strong>
          <span>默认 DeepSeek，可切换模型</span>
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
