from __future__ import annotations

import re
from typing import Any

from .stocks import analyze_stock


STOCK_SKILLS: list[dict[str, Any]] = [
    {
        "id": "single_stock_diagnosis",
        "name": "个股诊断",
        "description": "从趋势、量能、技术指标、支撑压力、风险机会生成个股复盘卡。",
        "inputs": ["symbol", "question"],
    },
    {
        "id": "watchlist_review",
        "name": "自选股复盘",
        "description": "结合自选股行情、成本、仓位和预警线，输出今天最该关注的标的。",
        "inputs": ["watchlist"],
    },
    {
        "id": "condition_screening",
        "name": "条件选股",
        "description": "在已有自选股内按自然语言条件筛选，例如强趋势、超卖、低波动、突破。",
        "inputs": ["watchlist", "question"],
    },
    {
        "id": "financial_checklist",
        "name": "财报解读清单",
        "description": "生成财报/估值/现金流核验清单，避免在没有真实财报数据时误判。",
        "inputs": ["symbol", "question"],
    },
    {
        "id": "news_risk_scan",
        "name": "公告新闻风险扫描",
        "description": "基于价格异动生成公告、新闻、财报、行业政策的核验路径。",
        "inputs": ["symbol", "question"],
    },
    {
        "id": "money_flow_sentiment",
        "name": "资金情绪推断",
        "description": "用价格、成交量、波动和市场温度做资金情绪的本地推断。",
        "inputs": ["symbol", "question"],
    },
    {
        "id": "followup_qa",
        "name": "多轮追问",
        "description": "基于最近一次分析继续回答用户追问，保留数据边界和风险提示。",
        "inputs": ["symbol", "question", "latest_analysis"],
    },
]


def list_stock_skills() -> list[dict[str, Any]]:
    return [dict(item) for item in STOCK_SKILLS]


def run_stock_skill(
    skill_id: str,
    *,
    symbol: str = "",
    question: str = "",
    watchlist: list[dict[str, Any]] | None = None,
    latest_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = str(skill_id or "").strip()
    if normalized == "single_stock_diagnosis":
        return _single_stock_diagnosis(symbol, question)
    if normalized == "watchlist_review":
        return _watchlist_review(watchlist or [])
    if normalized == "condition_screening":
        return _condition_screening(watchlist or [], question)
    if normalized == "financial_checklist":
        return _financial_checklist(symbol, question)
    if normalized == "news_risk_scan":
        return _news_risk_scan(symbol, question)
    if normalized == "money_flow_sentiment":
        return _money_flow_sentiment(symbol, question)
    if normalized == "followup_qa":
        return _followup_qa(symbol, question, latest_analysis)
    raise ValueError(f"unknown stock skill: {skill_id}")


def _single_stock_diagnosis(symbol: str, question: str) -> dict[str, Any]:
    analysis = analyze_stock(symbol, question=question)
    return _skill_result(
        "single_stock_diagnosis",
        analysis["quote"]["symbol"],
        "个股诊断已完成",
        analysis["report"],
        analysis=analysis,
        cards=[
            {"title": "评分", "value": f"{analysis['score']}/100", "note": analysis["stance"]},
            {"title": "趋势", "value": analysis["indicators"].get("trend"), "note": "均线结构"},
            {"title": "情绪", "value": analysis["sentiment"].get("label"), "note": analysis["sentiment"].get("note")},
        ],
    )


def _watchlist_review(watchlist: list[dict[str, Any]]) -> dict[str, Any]:
    if not watchlist:
        return _skill_result("watchlist_review", "", "自选股为空", "请先添加自选股，再运行自选股复盘。", cards=[])
    rows = []
    alert_rows = []
    for item in watchlist:
        quote = item.get("quote") or {}
        position = item.get("position") or {}
        if not quote:
            continue
        score = _watch_score(item)
        alerts = position.get("alerts") if isinstance(position.get("alerts"), list) else []
        row = {
            "symbol": item.get("symbol"),
            "name": item.get("name") or quote.get("name") or item.get("symbol"),
            "change_percent": quote.get("change_percent"),
            "profit_percent": position.get("profit_percent"),
            "alerts": alerts,
            "score": score,
        }
        rows.append(row)
        if alerts:
            alert_rows.append(row)
    rows.sort(key=lambda item: item["score"], reverse=True)
    lines = ["## 自选股复盘", ""]
    for row in rows[:8]:
        lines.append(
            f"- {row['name']}（{row['symbol']}）：涨跌幅 {row.get('change_percent')}%，"
            f"持仓盈亏 {row.get('profit_percent') if row.get('profit_percent') is not None else '--'}%，"
            f"关注优先级 {row['score']}/100。"
        )
    if alert_rows:
        lines.extend(["", "### 需要立刻检查的预警"])
        for row in alert_rows:
            lines.append(f"- {row['name']}：{'；'.join(row['alerts'])}")
    lines.extend(_risk_footer())
    return _skill_result(
        "watchlist_review",
        "",
        "自选股复盘已完成",
        "\n".join(lines),
        cards=[{"title": item["name"], "value": f"{item['score']}/100", "note": f"{item.get('change_percent')}%"} for item in rows[:4]],
        items=rows,
    )


def _condition_screening(watchlist: list[dict[str, Any]], question: str) -> dict[str, Any]:
    if not watchlist:
        return _skill_result("condition_screening", "", "暂无可筛选股票", "当前只在自选股范围内筛选。请先加入自选股。", cards=[])
    query = str(question or "").strip()
    rules = _screening_rules(query)
    matches = []
    for item in watchlist:
        quote = item.get("quote") or {}
        if not quote:
            continue
        cp = _num(quote.get("change_percent")) or 0
        position = item.get("position") or {}
        pp = _num(position.get("profit_percent"))
        ok = True
        if rules["strong"] and cp < 1:
            ok = False
        if rules["weak"] and cp > -1:
            ok = False
        if rules["alert"] and not position.get("alerts"):
            ok = False
        if rules["profit"] and (pp is None or pp <= 0):
            ok = False
        if rules["loss"] and (pp is None or pp >= 0):
            ok = False
        if ok:
            matches.append({"symbol": item.get("symbol"), "name": item.get("name") or quote.get("name"), "change_percent": cp, "profit_percent": pp})
    lines = [f"## 条件选股：{query or '默认强弱筛选'}", "", "筛选范围：当前自选股。"]
    if matches:
        lines.append("")
        for item in matches[:12]:
            lines.append(f"- {item['name']}（{item['symbol']}）：涨跌幅 {item['change_percent']}%，持仓盈亏 {item['profit_percent'] if item['profit_percent'] is not None else '--'}%。")
    else:
        lines.extend(["", "- 当前自选股中没有匹配项，可以放宽条件或先扩充观察池。"])
    lines.extend(_risk_footer())
    return _skill_result("condition_screening", "", "条件筛选已完成", "\n".join(lines), items=matches)


def _financial_checklist(symbol: str, question: str) -> dict[str, Any]:
    analysis = analyze_stock(symbol, question=question)
    quote = analysis["quote"]
    lines = [
        f"## {quote.get('name')}（{quote.get('symbol')}）财报解读清单",
        "",
        "当前版本尚未接入真实财报数据库，所以这里输出核验清单，不伪造财务结论。",
        "",
        "### 必查项目",
        "- 收入增速：同比、环比、是否靠一次性项目拉动。",
        "- 利润质量：毛利率、净利率、费用率是否改善。",
        "- 现金流：经营现金流是否跟利润同向。",
        "- 资产负债：有息负债、短债压力、商誉和存货风险。",
        "- 估值位置：PE/PB/PS 与自身历史和同行相比是否极端。",
        "",
        "### 和当前行情结合",
        f"- 技术面状态：{analysis['indicators'].get('trend')}，评分 {analysis['score']}/100。",
        f"- 如果财报确认增长修复，可关注 {analysis['indicators'].get('resistance')} 附近突破质量。",
        f"- 如果财报低于预期，优先检查 {analysis['indicators'].get('support')} 附近防守是否失效。",
        *_risk_footer(),
    ]
    return _skill_result("financial_checklist", quote.get("symbol"), "财报核验清单已生成", "\n".join(lines), analysis=analysis)


def _news_risk_scan(symbol: str, question: str) -> dict[str, Any]:
    analysis = analyze_stock(symbol, question=question)
    quote = analysis["quote"]
    risks = list(analysis.get("risks") or [])
    lines = [
        f"## {quote.get('name')}（{quote.get('symbol')}）公告新闻风险扫描",
        "",
        "当前版本尚未接入公告/新闻全文数据，因此先基于行情异动给出核验路径。",
        "",
        "### 需要核验",
        "- 公司公告：业绩预告、减持、回购、诉讼、重组、分红。",
        "- 行业政策：监管、补贴、价格管制、出口限制。",
        "- 财报日期：临近财报期时，波动可能提前放大。",
        "- 研报/评级：是否出现集中上调或下调。",
        "",
        "### 由行情触发的风险提示",
        *[f"- {item}" for item in risks],
        *_risk_footer(),
    ]
    return _skill_result("news_risk_scan", quote.get("symbol"), "风险扫描路径已生成", "\n".join(lines), analysis=analysis)


def _money_flow_sentiment(symbol: str, question: str) -> dict[str, Any]:
    analysis = analyze_stock(symbol, question=question)
    quote = analysis["quote"]
    indicators = analysis["indicators"]
    lines = [
        f"## {quote.get('name')}（{quote.get('symbol')}）资金情绪推断",
        "",
        "当前资金情绪由价格、成交量、波动率和趋势规则推断；不等同于真实主力资金流数据。",
        "",
        f"- 情绪标签：{analysis['sentiment'].get('label')}，分数 {analysis['sentiment'].get('score')}/100。",
        f"- 量能比：{indicators.get('volume_ratio')}，20日波动率：{indicators.get('volatility20')}%。",
        f"- 市场上下文：{analysis['market_context'].get('regime')}。",
        f"- MACD：{(indicators.get('macd') or {}).get('signal')}，KDJ：{(indicators.get('kdj') or {}).get('signal')}。",
        "",
        "### 下一步",
        "- 若放量上涨且突破压力位，再核验新闻/财报是否同步支持。",
        "- 若放量下跌，先排查公告、行业政策和大盘系统性风险。",
        *_risk_footer(),
    ]
    return _skill_result("money_flow_sentiment", quote.get("symbol"), "资金情绪推断已完成", "\n".join(lines), analysis=analysis)


def _followup_qa(symbol: str, question: str, latest_analysis: dict[str, Any] | None) -> dict[str, Any]:
    analysis = latest_analysis if isinstance(latest_analysis, dict) and latest_analysis.get("quote") else analyze_stock(symbol, question=question)
    quote = analysis.get("quote") or {}
    indicators = analysis.get("indicators") or {}
    lines = [
        f"## 追问：{question or '继续分析'}",
        "",
        f"基于最近一次 {quote.get('name')}（{quote.get('symbol')}）分析：",
        f"- 评分：{analysis.get('score')}/100，结论：{analysis.get('stance')}",
        f"- 趋势：{indicators.get('trend')}，支撑/压力：{indicators.get('support')} / {indicators.get('resistance')}",
        "",
        "### 回答",
        _answer_followup(question, analysis),
        *_risk_footer(),
    ]
    return _skill_result("followup_qa", quote.get("symbol"), "追问回答已生成", "\n".join(lines), analysis=analysis)


def _answer_followup(question: str, analysis: dict[str, Any]) -> str:
    text = str(question or "")
    if re.search(r"止损|防守|跌破|风险", text):
        return "优先看 20 日低点、MA20 和你自己的最大可承受亏损。若价格跌破技术防守位，同时原始买入理由没有新证据支持，应先降低风险暴露。"
    if re.search(r"买|加仓|进场|追", text):
        return "不建议只因为评分或单日上涨就行动。更稳的确认条件是：突破压力位、量能健康放大、市场环境不拖累、新闻/财报至少一项同步支持。"
    if re.search(r"卖|减仓|止盈", text):
        return "可以把压力位、RSI过热、放量滞涨和单票仓位过高作为减仓观察条件。核心不是猜最高点，而是把利润回撤控制在可接受范围。"
    return "当前更适合按观察计划执行：看趋势是否延续、量能是否配合、支撑压力是否有效，再结合公告、财报和行业消息做二次确认。"


def _screening_rules(question: str) -> dict[str, bool]:
    text = str(question or "").lower()
    return {
        "strong": bool(re.search(r"强|上涨|突破|多头|领涨|positive|up", text)),
        "weak": bool(re.search(r"弱|下跌|破位|空头|谨慎|negative|down", text)),
        "alert": bool(re.search(r"预警|止损|突破|触发|alert", text)),
        "profit": bool(re.search(r"盈利|赚钱|浮盈|profit", text)),
        "loss": bool(re.search(r"亏损|浮亏|回撤|loss", text)),
    }


def _watch_score(item: dict[str, Any]) -> int:
    quote = item.get("quote") or {}
    position = item.get("position") or {}
    score = 50
    cp = _num(quote.get("change_percent")) or 0
    pp = _num(position.get("profit_percent"))
    if cp > 2:
        score += 15
    elif cp < -2:
        score += 12
    if position.get("alerts"):
        score += 20
    if pp is not None and pp <= -8:
        score += 12
    if item.get("notes"):
        score += 4
    return max(0, min(100, int(score)))


def _skill_result(
    skill_id: str,
    symbol: str | None,
    title: str,
    report: str,
    *,
    analysis: dict[str, Any] | None = None,
    cards: list[dict[str, Any]] | None = None,
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "skill_id": skill_id,
        "symbol": symbol or "",
        "title": title,
        "report": report,
        "analysis": analysis,
        "cards": cards or [],
        "items": items or [],
        "disclaimer": "仅供学习研究和个人复盘，不构成投资建议。",
    }


def _risk_footer() -> list[str]:
    return ["", "### 风险提示", "- 以上仅供学习研究和个人复盘，不构成投资建议；请结合公开披露信息和自身风险承受能力独立判断。"]


def _num(value: Any) -> float | None:
    try:
        if value in {"", None}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
