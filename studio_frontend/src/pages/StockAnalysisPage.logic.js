export function formatStockNumber(value, digits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return number.toFixed(digits);
}

export function stockChangeClass(value) {
  const number = Number(value);
  if (number > 0) return "up";
  if (number < 0) return "down";
  return "";
}

export function stockKlinePoints(points = []) {
  const values = (Array.isArray(points) ? points : []).slice(-42).map((item) => Number(item.close)).filter(Number.isFinite);
  if (!values.length) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = 320;
  const height = 88;
  const span = max - min || 1;
  return values.map((value, index) => {
    const x = values.length === 1 ? width : (index / (values.length - 1)) * width;
    const y = height - ((value - min) / span) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

export function stockDecisionGuide(analysis, question = "") {
  const plain = analysis?.plain_answer || null;
  if (plain?.headline || plain?.action) return plain;
  const score = Number(analysis?.score);
  const indicators = analysis?.indicators || {};
  const quote = analysis?.quote || {};
  const price = quote.price ?? indicators.latest ?? "--";
  const support = indicators.support ?? indicators.low20 ?? "--";
  const resistance = indicators.resistance ?? indicators.high20 ?? "--";
  const ma20 = indicators.ma20 ?? "--";
  const trend = indicators.trend || analysis?.stance || "趋势不明确";
  const rsi = Number(indicators.rsi14);
  const volatility = Number(indicators.volatility20);
  const changePercent = Number(quote.change_percent);
  const risks = Array.isArray(analysis?.risks) ? analysis.risks : [];
  const asksPosition = /减仓|加仓|仓位|补仓|持有|卖|买/.test(String(question || ""));
  const asksRange = /最高|最低|目标|到多少|预测|空间/.test(String(question || ""));
  let headline = "结论：中性偏弱，先等信号";
  let action = `下一步：不建议加仓；已有仓位看 MA20（${ma20}）和20日低点 ${support}，守不住就减仓。`;
  let invalidation = `价格区间：短线先看 ${support} 到 ${resistance}；突破 ${resistance} 才有继续上看的理由。`;

  if ((Number.isFinite(score) && score < 40) || trend === "空头排列") {
    headline = "结论：偏弱，先防守，不要补仓";
    action = `仓位建议：减仓或只留小观察仓。不要加仓。防守线看 ${support}，站回 MA20（${ma20}）之前不考虑加仓。`;
    invalidation = `价格区间：短线先看 ${support} 到 ${resistance}；只有站回 MA20（${ma20}）并突破 ${resistance}，才算转强。`;
  } else if (Number.isFinite(volatility) && volatility >= 45) {
    headline = "结论：波动太大，仓位要轻";
    action = `仓位建议：只适合轻仓。已有仓位可减到让你睡得着的位置；想加仓也等站稳 MA20（${ma20}）后再分批。`;
    invalidation = `价格区间：短线先看 ${support} 到 ${resistance}；跌破 ${support} 继续偏弱。`;
  } else if (Number.isFinite(rsi) && rsi <= 30 && (!Number.isFinite(score) || score < 55)) {
    headline = "结论：可能反弹，但不是加仓信号";
    action = `仓位建议：不是加仓点。RSI 低只说明可能反弹，先看 ${support} 是否止跌，突破 ${resistance} 才能提高仓位。`;
    invalidation = `价格区间：反弹上沿先看 ${resistance}，跌破 ${support} 就是反弹失败。`;
  } else if (Number.isFinite(score) && score >= 70 && ["多头排列", "短线强于中期"].includes(trend)) {
    headline = "结论：趋势偏强，持有比追高更合适";
    action = `仓位建议：已有仓位可以持有；不建议追高满仓。突破 ${resistance} 后可小幅加，跌破 MA20（${ma20}）就减。`;
    invalidation = `价格区间：下方看 MA20（${ma20}），上方先看 ${resistance}。`;
  } else if (Number.isFinite(score) && score < 40) {
    headline = "结论：偏弱，先别补仓";
  } else if (Number.isFinite(changePercent) && changePercent <= -3) {
    headline = "结论：今天偏弱，不要急着加仓";
    action = `仓位建议：不加仓。已有仓位先看 ${support}，跌破就减；反弹到 MA20（${ma20}）附近量不够也别追。`;
  } else if (Number.isFinite(score) && score >= 55) {
    headline = "结论：略有转好，但还不能重仓";
    action = `仓位建议：可以观察，不适合重仓。若站稳 MA20（${ma20}）且突破 ${resistance}，再考虑小仓加；跌破 ${support} 就减。`;
  }

  if (asksPosition && !action.includes("仓位建议")) {
    action = `仓位建议：先不加仓，已有仓位可继续观察。上方看 ${resistance}，下方看 ${support}；方向没出来前不要扩大仓位。`;
  }
  if (asksRange && !invalidation.includes("价格区间")) {
    invalidation = `价格区间：短线先看 ${support} 到 ${resistance}；MA20（${ma20}）是中间分水岭。`;
  }

  const notes = [`现在价格大约 ${price}，趋势是「${trend}」。`];
  if (Number.isFinite(rsi) && rsi <= 30) notes.push("RSI 很低，可能有反弹，但这不等于反转。");
  if (Number.isFinite(rsi) && rsi >= 75) notes.push("RSI 偏热，短线要防回落。");
  if (Number.isFinite(volatility) && volatility >= 45) notes.push("波动很大，仓位要比平时更轻。");
  if (risks[0]) notes.push(`最大的风险：${risks[0]}`);
  return {
    headline,
    summary: notes.join(""),
    action,
    invalidation
  };
}

export function stockReadableReport(analysis, question = "") {
  if (!analysis) return "";
  const guide = stockDecisionGuide(analysis, question);
  const report = String(analysis.report || "");
  if (report.includes("大白话") || report.includes("下一步：")) return report;
  return [
    `## 大白话：${guide.headline}`,
    "",
    `- ${guide.summary}`,
    `- ${guide.action}`,
    `- ${guide.invalidation}`,
    "",
    report
  ].join("\n").trim();
}
