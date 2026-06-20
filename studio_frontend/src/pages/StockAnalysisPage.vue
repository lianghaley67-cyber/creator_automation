<script>
import { useStudioContext } from "./useStudioContext.js";

export default {
  name: "StockAnalysisPage",
  setup() {
    return useStudioContext("StockAnalysisPage");
  }
};
</script>

<template>
    <div v-if="activeTab === 'stocks'">
      <section id="stock-panel" class="panel stock-module">
        <div class="panel-header">
          <h2>股票分析</h2>
          <span class="eyebrow">行情 · 技术指标 · 持仓 · 预警 · 复盘</span>
        </div>
        <div class="stock-workbench">
          <div class="stock-control-panel">
            <div class="field-grid">
              <label class="field">
                <span>股票代码 / 名称</span>
                <input v-model="stockForm.symbol" placeholder="AAPL / 00700 / 600519" @keyup.enter="searchStockSymbols" />
              </label>
              <label class="field">
                <span>市场</span>
                <select v-model="stockForm.market">
                  <option value="US">美股</option>
                  <option value="HK">港股</option>
                  <option value="CN">A股</option>
                </select>
              </label>
              <label class="field">
                <span>显示名称</span>
                <input v-model="stockForm.name" placeholder="可选" />
              </label>
              <label class="field">
                <span>成本价</span>
                <input v-model="stockForm.cost" inputmode="decimal" placeholder="可选" />
              </label>
              <label class="field">
                <span>持仓数量</span>
                <input v-model="stockForm.shares" inputmode="decimal" placeholder="可选" />
              </label>
              <label class="field">
                <span>上方预警</span>
                <input v-model="stockForm.alert_high" inputmode="decimal" placeholder="突破提醒" />
              </label>
              <label class="field">
                <span>下方预警</span>
                <input v-model="stockForm.alert_low" inputmode="decimal" placeholder="止损提醒" />
              </label>
              <label class="field">
                <span>风险偏好</span>
                <select v-model="stockForm.risk_level">
                  <option value="conservative">保守</option>
                  <option value="balanced">平衡</option>
                  <option value="aggressive">进取</option>
                </select>
              </label>
              <label class="field">
                <span>持有周期</span>
                <select v-model="stockForm.holding_period">
                  <option value="short">短线</option>
                  <option value="swing">波段</option>
                  <option value="long">中长线</option>
                </select>
              </label>
              <label class="field">
                <span>单票仓位上限%</span>
                <input v-model="stockForm.max_position_percent" inputmode="decimal" placeholder="例如 20" />
              </label>
              <label class="field">
                <span>关注理由</span>
                <input v-model="stockForm.notes" placeholder="财报、行业、策略..." />
              </label>
            </div>
            <textarea v-model="stockQuestion" class="stock-question" rows="3"></textarea>
            <div class="stock-actions">
              <button class="btn secondary" type="button" :disabled="busy.stockSearch" @click="searchStockSymbols">
                {{ busy.stockSearch ? "搜索中..." : "搜索标的" }}
              </button>
              <button class="btn secondary" type="button" :disabled="busy.stockSave" @click="saveStockToWatchlist">
                {{ busy.stockSave ? "保存中..." : "加入/更新自选" }}
              </button>
              <button class="btn accent" type="button" :disabled="busy.stockAnalyze" @click="analyzeStock()">
                {{ busy.stockAnalyze ? "分析中..." : "生成 AI 辅助分析" }}
              </button>
            </div>
            <div v-if="stockSearchResults.length" class="stock-search-results">
              <button v-for="item in stockSearchResults" :key="item.symbol" type="button" @click="chooseStockSearchResult(item)">
                <strong>{{ item.symbol }}</strong>
                <span>{{ item.name }} · {{ item.exchange || item.market }}</span>
              </button>
            </div>
          </div>

          <div class="stock-market-card">
            <div class="stock-section-head">
              <strong>全球市场温度</strong>
              <button class="btn secondary small" type="button" :disabled="busy.stockMarket" @click="refreshStockMarket">
                {{ busy.stockMarket ? "刷新中" : "刷新" }}
              </button>
            </div>
            <div class="market-mood">
              <span>{{ stockMarket?.mood || "待刷新" }}</span>
              <strong :class="stockChangeClass(stockMarket?.average_change)">{{ formatStockNumber(stockMarket?.average_change) }}%</strong>
            </div>
            <div class="market-index-list">
              <div v-for="item in stockMarket?.items || []" :key="item.symbol" class="market-index-row">
                <span>{{ item.name }}</span>
                <strong>{{ item.price || "--" }}</strong>
                <em :class="stockChangeClass(item.change_percent)">{{ formatStockNumber(item.change_percent) }}%</em>
              </div>
            </div>
          </div>
        </div>

        <section class="stock-skill-panel">
          <div class="stock-section-head">
            <strong>Stock Skills</strong>
            <button class="btn secondary small" type="button" :disabled="busy.stockSkills" @click="refreshStockSkills">
              {{ busy.stockSkills ? "刷新中" : "刷新 Skills" }}
            </button>
          </div>
          <div class="stock-skill-grid">
            <button
              v-for="skill in stockSkills"
              :key="skill.id"
              type="button"
              class="stock-skill-card"
              :class="{ active: selectedStockSkill === skill.id }"
              @click="selectedStockSkill = skill.id"
            >
              <strong>{{ skill.name }}</strong>
              <span>{{ skill.description }}</span>
            </button>
          </div>
          <div class="stock-actions">
            <button class="btn accent" type="button" :disabled="busy.stockSkillRun" @click="runStockSkill()">
              {{ busy.stockSkillRun ? "运行中..." : `运行 ${stockSkillName(selectedStockSkill)}` }}
            </button>
            <button class="btn secondary" type="button" :disabled="busy.stockSkillRun" @click="runStockSkill('watchlist_review', '')">
              自选股一键复盘
            </button>
            <button class="btn secondary" type="button" :disabled="busy.stockSkillRun" @click="runStockSkill('condition_screening', '')">
              按问题筛选自选
            </button>
            <button class="btn secondary" type="button" :disabled="busy.stockSkillRun" @click="runStockSkill('personal_strategy_plan', '')">
              生成我的交易计划
            </button>
          </div>
          <div v-if="stockSkillResult" class="stock-skill-result">
            <div class="stock-score-line">
              <span>{{ stockSkillResult.title }}</span>
              <em>{{ stockSkillName(stockSkillResult.skill_id) }}</em>
            </div>
            <div v-if="stockSkillResult.cards?.length" class="indicator-grid">
              <span v-for="card in stockSkillResult.cards" :key="card.title">
                {{ card.title }}
                <strong>{{ card.value }}</strong>
                <small>{{ card.note }}</small>
              </span>
            </div>
            <pre class="stock-report">{{ stockSkillResult.report }}</pre>
            <small>{{ stockSkillResult.disclaimer }}</small>
          </div>
        </section>

        <div class="stock-dashboard-grid">
          <section class="stock-list-panel">
            <div class="stock-section-head">
              <strong>自选与持仓</strong>
              <button class="btn secondary small" type="button" :disabled="busy.stockRefresh" @click="refreshStockWatchlist">
                {{ busy.stockRefresh ? "刷新中" : "刷新行情" }}
              </button>
            </div>
            <div v-if="!stockWatchlist.length" class="stock-empty">还没有自选股，先搜索代码并加入。</div>
            <article v-for="item in stockWatchlist" :key="item.symbol" class="stock-watch-card">
              <div class="stock-watch-main">
                <div>
                  <strong>{{ item.name || item.symbol }}</strong>
                  <span>{{ item.symbol }} · {{ item.quote?.market || item.market }}</span>
                </div>
                <div class="stock-price">
                  <strong>{{ item.quote?.price ?? "--" }}</strong>
                  <em :class="stockChangeClass(item.quote?.change_percent)">{{ formatStockNumber(item.quote?.change_percent) }}%</em>
                </div>
              </div>
              <div class="stock-mini-meta">
                <span>成本 {{ item.cost || "--" }}</span>
                <span>数量 {{ item.shares || "--" }}</span>
                <span>市值 {{ item.position?.market_value ?? "--" }}</span>
                <span :class="stockChangeClass(item.position?.profit_percent)">盈亏 {{ formatStockNumber(item.position?.profit_percent) }}%</span>
                <span>风险 {{ item.risk_level === "conservative" ? "保守" : item.risk_level === "aggressive" ? "进取" : "平衡" }}</span>
                <span>周期 {{ item.holding_period === "short" ? "短线" : item.holding_period === "long" ? "中长线" : "波段" }}</span>
                <span>上限 {{ item.max_position_percent || item.position?.max_position_percent || "--" }}%</span>
              </div>
              <div v-if="item.position?.alerts?.length" class="stock-alerts">
                <span v-for="alert in item.position.alerts" :key="alert">{{ alert }}</span>
              </div>
              <p v-if="item.notes">{{ item.notes }}</p>
              <div class="stock-row-actions">
                <button class="btn secondary small" type="button" @click="analyzeStock(item.symbol)">分析</button>
                <button class="btn secondary small" type="button" @click="runStockSkill('personal_strategy_plan', item.symbol)">策略</button>
                <button class="btn secondary small danger-action" type="button" @click="deleteStockFromWatchlist(item.symbol)">移除</button>
              </div>
            </article>
          </section>

          <section class="stock-analysis-panel">
            <div class="stock-section-head">
              <strong>下一步怎么做</strong>
              <button class="btn secondary small" type="button" :disabled="!stockAnalysis?.report" @click="copyText(stockReadableReport(stockAnalysis), '股票分析报告已复制。')">复制报告</button>
            </div>
            <div v-if="!stockAnalysis" class="stock-empty">输入股票代码后生成分析，会先用大白话告诉你下一步该观察、持有、减仓还是先别动。</div>
            <div v-else class="stock-analysis-result">
              <div class="stock-score-line">
                <span>{{ stockAnalysis.quote?.name }} · {{ stockAnalysis.quote?.symbol }}</span>
                <strong>{{ stockAnalysis.score }}/100</strong>
                <em>{{ stockAnalysis.stance }}</em>
              </div>
              <div class="stock-plain-answer">
                <strong>{{ stockDecisionGuide(stockAnalysis).headline }}</strong>
                <p>{{ stockDecisionGuide(stockAnalysis).summary }}</p>
                <span>{{ stockDecisionGuide(stockAnalysis).action }}</span>
                <small>{{ stockDecisionGuide(stockAnalysis).invalidation }}</small>
              </div>
              <div v-if="stockAnalysis.conclusion" class="stock-clear-conclusion">
                <strong>明确结论：{{ stockAnalysis.conclusion.label }}</strong>
                <p>{{ stockAnalysis.conclusion.summary }}</p>
                <span>{{ stockAnalysis.conclusion.action }}</span>
              </div>
              <div v-if="stockAnalysis.upside_targets?.length" class="stock-target-grid">
                <div v-for="item in stockAnalysis.upside_targets" :key="item.label">
                  <span>{{ item.label }}</span>
                  <strong>{{ item.target_price }}</strong>
                  <em>约 {{ item.upside_percent }}%</em>
                  <small>{{ item.basis }}</small>
                </div>
              </div>
              <svg class="stock-sparkline" viewBox="0 0 320 88" preserveAspectRatio="none" aria-hidden="true">
                <polyline :points="stockKlinePoints(stockAnalysis.kline)" fill="none" stroke="#00d5e8" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" />
              </svg>
              <div class="indicator-grid">
                <span>趋势 <strong>{{ stockAnalysis.indicators?.trend }}</strong></span>
                <span>RSI <strong>{{ stockAnalysis.indicators?.rsi14 ?? "--" }}</strong></span>
                <span>MACD <strong>{{ stockAnalysis.indicators?.macd?.signal }}</strong></span>
                <span>BOLL <strong>{{ stockAnalysis.indicators?.boll?.position }}</strong></span>
                <span>5日收益 <strong>{{ stockAnalysis.indicators?.return5 ?? "--" }}%</strong></span>
                <span>20日波动 <strong>{{ stockAnalysis.indicators?.volatility20 ?? "--" }}%</strong></span>
              </div>
              <div class="stock-signal-columns">
                <div>
                  <strong>机会</strong>
                  <p v-for="item in stockAnalysis.opportunities" :key="item">{{ item }}</p>
                </div>
                <div>
                  <strong>风险</strong>
                  <p v-for="item in stockAnalysis.risks" :key="item">{{ item }}</p>
                </div>
              </div>
              <div class="stock-signal-columns">
                <div>
                  <strong>预警线</strong>
                  <p v-for="item in stockAnalysis.alerts" :key="item.label">{{ item.label }}：{{ item.price || item.percent + '%' }}</p>
                </div>
                <div>
                  <strong>持仓动作</strong>
                  <p v-for="item in stockAnalysis.position_plan" :key="item.title">{{ item.title }}：{{ item.text }}</p>
                </div>
              </div>
              <pre class="stock-report">{{ stockReadableReport(stockAnalysis) }}</pre>
              <small>{{ stockAnalysis.disclaimer }}</small>
            </div>
          </section>
        </div>

        <section class="stock-history-panel">
          <div class="stock-section-head">
            <strong>分析历史</strong>
            <button class="btn secondary small" type="button" :disabled="busy.stockHistory" @click="refreshStockHistory">
              {{ busy.stockHistory ? "刷新中" : "查看全部" }}
            </button>
          </div>
          <div v-if="!stockHistory.length" class="stock-empty">暂无历史报告。</div>
          <div v-else class="stock-history-list">
            <button v-for="item in stockHistory" :key="item.id" type="button" @click="stockAnalysis = { ...stockAnalysis, report: item.report, score: item.score, stance: item.stance, quote: { symbol: item.symbol, name: item.name } }">
              <span>{{ item.created_at }}</span>
              <strong>{{ item.name }} · {{ item.symbol }}</strong>
              <em>{{ item.score }}/100 · {{ item.stance }}</em>
            </button>
          </div>
        </section>

        <section class="stock-history-panel">
          <div class="stock-section-head">
            <strong>Stock Skill 运行历史</strong>
            <button class="btn secondary small" type="button" :disabled="busy.stockSkills" @click="refreshStockSkills">
              {{ busy.stockSkills ? "刷新中" : "刷新" }}
            </button>
          </div>
          <div v-if="!stockSkillRuns.length" class="stock-empty">暂无 Skill 运行记录。</div>
          <div v-else class="stock-history-list">
            <button v-for="item in stockSkillRuns" :key="item.id" type="button" @click="stockSkillResult = item">
              <span>{{ item.created_at }}</span>
              <strong>{{ item.title }}</strong>
              <em>{{ stockSkillName(item.skill_id) }} · {{ item.symbol || "自选股" }}</em>
            </button>
          </div>
        </section>
      </section>
    </div>
</template>
