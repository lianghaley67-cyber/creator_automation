<script>
import { useStudioContext } from "./useStudioContext.js";

export default {
  name: "OverviewPage",
  setup() {
    return useStudioContext("OverviewPage");
  }
};
</script>

<template>
      <section v-if="activeTab === 'overview'" class="dashboard">
        <section class="landing-hero">
          <div class="landing-copy">
            <span class="version-pill">v2.0 · 个人成长系统全新升级</span>
            <h1>一个人的 <span>AI 成长工作台</span></h1>
            <p>AI 洞察 · 软件开发 · 职场成长 · 内容创作。实时抓取行业资讯，素材一键生成文案与视频，股票决策辅助已接入工作台。</p>
            <div class="landing-actions">
              <button class="btn accent" type="button" @click="openStudioModule('materials', 'script-panel')">开始今日创作</button>
              <button class="btn secondary" type="button" @click="openStudioModule('trends', 'trends-panel')">查看演示</button>
            </div>
            <div class="hero-stats">
              <strong>120+<small>每日信源</small></strong>
              <strong>8 种<small>文案模板</small></strong>
              <strong>60s<small>素材→视频</small></strong>
            </div>
          </div>
          <div class="hero-console" aria-label="工作台实时预览">
            <div class="console-bar">
              <span></span><span></span><span></span>
              <small>studio.inspwk.site</small>
            </div>
            <div class="signal-list">
              <div><span>实时信息流</span></div>
              <p><strong>GPT-5 多模态能力更新</strong><small>2 分钟前</small></p>
              <p><strong>TanStack Start 1.0 正式发布</strong><small>14 分钟前</small></p>
              <p><strong>远程办公薪酬白皮书 2026</strong><small>32 分钟前</small></p>
            </div>
            <div class="console-grid">
              <div class="mini-widget">
                <strong>文案生成</strong>
                <div class="progress-track"><div class="progress-fill" style="width: 75%"></div></div>
                <small>视频号口播 · 生成中 75%</small>
              </div>
              <div class="mini-widget">
                <strong>股票分析</strong>
                <div class="bar-chart" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div>
                <small>实时等待</small>
              </div>
            </div>
          </div>
        </section>

        <section class="core-section">
          <span class="dashboard-kicker">CORE MODULES</span>
          <h2>三大模块 · 一条成长闭环</h2>
          <p>从信息输入到内容产出，再到决策辅助。每一步都为个人创作者与独立开发者量身打造。</p>
          <div class="core-grid">
            <button
              v-for="module in coreModules"
              :key="module.key"
              class="core-card"
              type="button"
              @click="openStudioModule(module.tab, module.target)"
            >
              <span class="module-icon" :data-icon="module.icon" aria-hidden="true"></span>
              <em :class="{ warm: module.status === '开发中' }">{{ module.status }}</em>
              <small>{{ module.number }} · {{ module.key === "capture" ? "实时洞察" : module.key === "create" ? "创作引擎" : "决策助手" }}</small>
              <strong>{{ module.title }}</strong>
              <p>{{ module.desc }}</p>
              <ul>
                <li v-for="item in module.bullets" :key="item">{{ item }}</li>
              </ul>
              <span class="module-link">{{ module.action }}</span>
            </button>
          </div>
        </section>

        <section class="workflow-section">
          <div class="dashboard-hero">
            <div>
              <span class="dashboard-kicker">DAILY WORKFLOW</span>
              <h2>每天 30 分钟 · 完成一条优质内容</h2>
            </div>
            <span class="coverage-pill">自动化覆盖 80% 流程</span>
          </div>

          <div class="workflow-grid" aria-label="每日工作流">
            <button
              v-for="card in workflowCards"
              :key="card.key"
              class="workflow-card"
              type="button"
              @click="openStudioModule(card.tab, card.target)"
            >
              <span class="module-icon" :data-icon="card.icon" aria-hidden="true"></span>
              <span class="module-number">{{ card.number }}</span>
              <strong>{{ card.title }}</strong>
              <small>{{ card.desc }}</small>
            </button>
          </div>
        </section>

        <div class="metric-grid">
          <button
            v-for="stat in studioStats"
            :key="stat.label"
            class="metric-card"
            type="button"
            @click="openStudioModule('trends', 'trends-panel')"
          >
            <span class="module-icon compact" :data-icon="stat.icon" aria-hidden="true"></span>
            <strong>{{ stat.value }}</strong>
            <small>{{ stat.label }}</small>
          </button>
        </div>

        <section class="launch-panel">
          <h2>今天的灵感，<span>让 AI 帮你落地</span></h2>
          <p>一个工作台，覆盖洞察、创作、决策。专为持续输出的个人成长者打造。</p>
          <div class="launch-actions">
            <button class="btn accent" type="button" @click="openStudioModule('materials', 'script-panel')">免费开始使用</button>
            <button class="btn secondary" type="button" @click="openStudioModule('trends', 'questions-panel')">预约 1v1 咨询</button>
          </div>
        </section>
      </section>
</template>
