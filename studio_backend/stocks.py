from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from typing import Any


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"


def normalize_stock_symbol(symbol: str, market: str = "") -> str:
    raw = str(symbol or "").strip().upper()
    normalized_market = str(market or "").strip().upper()
    if not raw:
        return ""
    if "." in raw or "-" in raw:
        return raw
    if normalized_market in {"US", "NYSE", "NASDAQ"}:
        return raw
    if normalized_market in {"HK", "HKG"}:
        return f"{raw.zfill(4)}.HK" if raw.isdigit() else raw
    if normalized_market in {"CN", "A", "ASHARE", "A股"}:
        if raw.startswith(("5", "6", "9")):
            return f"{raw}.SS"
        return f"{raw}.SZ"
    if raw.isdigit():
        if len(raw) <= 5:
            return f"{raw.zfill(4)}.HK"
        if raw.startswith(("5", "6", "9")):
            return f"{raw}.SS"
        return f"{raw}.SZ"
    return raw


def infer_market(symbol: str) -> str:
    text = str(symbol or "").upper()
    if text.endswith(".SS") or text.endswith(".SZ"):
        return "A股"
    if text.endswith(".HK"):
        return "港股"
    return "美股"


def _http_json(url: str, timeout: int = 12) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 CreatorStudio/stock-module",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def fetch_stock_chart(symbol: str, *, range_text: str = "6mo", interval: str = "1d") -> dict[str, Any]:
    safe_symbol = urllib.parse.quote(normalize_stock_symbol(symbol), safe="")
    if not safe_symbol:
        raise ValueError("stock symbol is required")
    query = urllib.parse.urlencode({"range": range_text, "interval": interval, "includePrePost": "false"})
    data = _http_json(f"{YAHOO_CHART_URL.format(symbol=safe_symbol)}?{query}")
    result = ((data.get("chart") or {}).get("result") or [None])[0]
    if not result:
        error = (data.get("chart") or {}).get("error") or {}
        raise RuntimeError(error.get("description") or "stock data unavailable")
    meta = result.get("meta") or {}
    timestamps = result.get("timestamp") or []
    quote = (((result.get("indicators") or {}).get("quote") or [{}])[0]) or {}
    closes = quote.get("close") or []
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    volumes = quote.get("volume") or []
    points: list[dict[str, Any]] = []
    for index, ts in enumerate(timestamps):
        close = _num(closes[index] if index < len(closes) else None)
        if close is None:
            continue
        points.append(
            {
                "time": time.strftime("%Y-%m-%d", time.localtime(int(ts))),
                "open": _num(opens[index] if index < len(opens) else None),
                "high": _num(highs[index] if index < len(highs) else None),
                "low": _num(lows[index] if index < len(lows) else None),
                "close": close,
                "volume": _num(volumes[index] if index < len(volumes) else None) or 0,
            }
        )
    return {
        "symbol": meta.get("symbol") or normalize_stock_symbol(symbol),
        "name": meta.get("shortName") or meta.get("longName") or meta.get("symbol") or symbol,
        "currency": meta.get("currency") or "",
        "exchange": meta.get("exchangeName") or meta.get("fullExchangeName") or "",
        "market": infer_market(meta.get("symbol") or symbol),
        "regular_market_price": _num(meta.get("regularMarketPrice")),
        "previous_close": _num(meta.get("chartPreviousClose") or meta.get("previousClose")),
        "points": points,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def stock_quote(symbol: str) -> dict[str, Any]:
    chart = fetch_stock_chart(symbol, range_text="5d", interval="1d")
    points = chart["points"]
    latest = points[-1] if points else {}
    previous = chart.get("previous_close")
    if previous is None and len(points) >= 2:
        previous = points[-2].get("close")
    price = chart.get("regular_market_price") or latest.get("close")
    change = price - previous if price is not None and previous else 0
    change_percent = (change / previous * 100) if previous else 0
    return {
        **{key: chart[key] for key in ["symbol", "name", "currency", "exchange", "market", "fetched_at"]},
        "price": round(price, 4) if price is not None else None,
        "previous_close": round(previous, 4) if previous is not None else None,
        "change": round(change, 4),
        "change_percent": round(change_percent, 2),
        "volume": latest.get("volume", 0),
    }


def search_stocks(query: str) -> list[dict[str, Any]]:
    text = str(query or "").strip()
    if not text:
        return []
    url = f"{YAHOO_SEARCH_URL}?{urllib.parse.urlencode({'q': text, 'quotesCount': 10, 'newsCount': 0})}"
    data = _http_json(url)
    items = []
    for item in data.get("quotes", [])[:10]:
        symbol = item.get("symbol") or ""
        if not symbol:
            continue
        items.append(
            {
                "symbol": symbol,
                "name": item.get("shortname") or item.get("longname") or symbol,
                "exchange": item.get("exchDisp") or item.get("exchange") or "",
                "market": infer_market(symbol),
                "type": item.get("quoteType") or "",
            }
        )
    return items


def analyze_stock(symbol: str, *, question: str = "") -> dict[str, Any]:
    chart = fetch_stock_chart(symbol)
    quote = stock_quote(chart["symbol"])
    points = chart["points"]
    closes = [float(item["close"]) for item in points if item.get("close") is not None]
    volumes = [float(item.get("volume") or 0) for item in points]
    indicators = _technical_indicators(closes, volumes)
    score, stance, risks, opportunities = _score_stock(quote, indicators)
    conclusion = _clear_conclusion(quote, indicators, score, stance)
    upside_targets = _upside_targets(quote, indicators)
    plain_answer = _plain_language_answer(quote, indicators, score, stance, conclusion, risks, opportunities)
    report = _build_report(
        quote,
        indicators,
        score,
        stance,
        risks,
        opportunities,
        question=question,
        conclusion=conclusion,
        upside_targets=upside_targets,
        plain_answer=plain_answer,
    )
    return {
        "quote": quote,
        "kline": points[-80:],
        "indicators": indicators,
        "score": score,
        "stance": stance,
        "conclusion": conclusion,
        "plain_answer": plain_answer,
        "upside_targets": upside_targets,
        "opportunities": opportunities,
        "risks": risks,
        "alerts": _suggest_alerts(quote, indicators),
        "sentiment": _sentiment_stub(quote, indicators),
        "market_context": _market_context_stub(quote, indicators),
        "position_plan": _position_plan(quote, indicators),
        "report": report,
        "disclaimer": "AI 和规则分析仅供学习研究，不构成投资建议。请结合公开披露信息、风险承受能力和专业意见独立判断。",
    }


def _technical_indicators(closes: list[float], volumes: list[float]) -> dict[str, Any]:
    latest = closes[-1] if closes else None
    ma5 = _ma(closes, 5)
    ma20 = _ma(closes, 20)
    ma60 = _ma(closes, 60)
    rsi14 = _rsi(closes, 14)
    vol5 = _ma(volumes, 5)
    vol20 = _ma(volumes, 20)
    high20 = max(closes[-20:]) if len(closes) >= 20 else latest
    low20 = min(closes[-20:]) if len(closes) >= 20 else latest
    drawdown20 = ((latest - high20) / high20 * 100) if latest and high20 else 0
    macd = _macd(closes)
    boll = _boll(closes, 20)
    kdj = _kdj_from_closes(closes)
    return5 = _return(closes, 5)
    return20 = _return(closes, 20)
    volatility20 = _volatility(closes, 20)
    return {
        "latest": _round(latest),
        "ma5": _round(ma5),
        "ma20": _round(ma20),
        "ma60": _round(ma60),
        "rsi14": _round(rsi14),
        "volume_ma5": _round(vol5),
        "volume_ma20": _round(vol20),
        "volume_ratio": _round(vol5 / vol20) if vol5 and vol20 else None,
        "high20": _round(high20),
        "low20": _round(low20),
        "drawdown20": _round(drawdown20),
        "return5": _round(return5),
        "return20": _round(return20),
        "volatility20": _round(volatility20),
        "macd": macd,
        "boll": boll,
        "kdj": kdj,
        "support": _round(low20),
        "resistance": _round(high20),
        "trend": _trend_label(latest, ma5, ma20, ma60),
    }


def _score_stock(quote: dict[str, Any], indicators: dict[str, Any]) -> tuple[int, str, list[str], list[str]]:
    score = 50
    risks: list[str] = []
    opportunities: list[str] = []
    cp = float(quote.get("change_percent") or 0)
    rsi = indicators.get("rsi14")
    volume_ratio = indicators.get("volume_ratio")
    trend = indicators.get("trend")
    macd = indicators.get("macd") or {}
    boll = indicators.get("boll") or {}
    return20 = indicators.get("return20")
    volatility20 = indicators.get("volatility20")
    if trend == "多头排列":
        score += 15
        opportunities.append("均线呈多头排列，趋势动能较强。")
    elif trend == "空头排列":
        score -= 15
        risks.append("均线呈空头排列，趋势仍偏弱。")
    if rsi is not None:
        if rsi >= 75:
            score -= 10
            risks.append("RSI 偏高，短线可能存在过热回撤风险。")
        elif rsi <= 30:
            score += 8
            opportunities.append("RSI 偏低，若基本面未恶化，可能进入超卖观察区。")
    if volume_ratio and volume_ratio >= 1.5:
        opportunities.append("近期成交量明显放大，需要结合新闻确认资金来源。")
        if cp < 0:
            risks.append("放量下跌，需警惕资金分歧或利空释放。")
        else:
            score += 6
    if macd.get("signal") == "金叉偏多":
        score += 6
        opportunities.append("MACD 出现金叉/向上信号，趋势修复概率提高。")
    elif macd.get("signal") == "死叉偏空":
        score -= 6
        risks.append("MACD 偏空，短线仍需等待动能修复。")
    if boll.get("position") == "上轨附近":
        risks.append("价格靠近布林上轨，短线追高性价比下降。")
    elif boll.get("position") == "下轨附近":
        opportunities.append("价格靠近布林下轨，可观察是否出现止跌与缩量。")
    if return20 is not None and return20 <= -12:
        risks.append("近 20 日跌幅较深，需区分技术反弹与趋势反转。")
    if volatility20 is not None and volatility20 >= 45:
        risks.append("20 日波动率偏高，仓位和止损线需要更保守。")
    if abs(cp) >= 5:
        risks.append("单日波动较大，追涨杀跌风险上升。")
    score = max(0, min(100, int(round(score))))
    if score >= 70:
        stance = "偏强观察"
    elif score >= 55:
        stance = "中性偏多"
    elif score >= 40:
        stance = "中性观望"
    else:
        stance = "偏弱谨慎"
    if not opportunities:
        opportunities.append("当前没有明显技术面优势，适合等待更明确的趋势或基本面信号。")
    if not risks:
        risks.append("仍需关注大盘环境、行业政策、财报和突发新闻。")
    return score, stance, risks[:5], opportunities[:5]


def _build_report(
    quote: dict[str, Any],
    indicators: dict[str, Any],
    score: int,
    stance: str,
    risks: list[str],
    opportunities: list[str],
    *,
    question: str,
    conclusion: dict[str, Any],
    upside_targets: list[dict[str, Any]],
    plain_answer: dict[str, Any],
) -> str:
    lines = [
        f"## {quote.get('name')}（{quote.get('symbol')}）AI 辅助分析",
        "",
        f"### 大白话：{plain_answer.get('headline')}",
        f"- {plain_answer.get('summary')}",
        f"- 今天先做：{plain_answer.get('action')}",
        f"- 看错就改：{plain_answer.get('invalidation')}",
        "",
        f"### 明确结论：{conclusion.get('label')}",
        f"- {conclusion.get('summary')}",
        f"- 当前动作：{conclusion.get('action')}",
        "",
        f"- 市场：{quote.get('market')} / {quote.get('exchange')}",
        f"- 最新价：{quote.get('price')} {quote.get('currency')}，涨跌幅：{quote.get('change_percent')}%",
        f"- 综合评分：{score}/100，结论：{stance}",
        f"- 趋势：{indicators.get('trend')}，MA5/MA20/MA60：{indicators.get('ma5')} / {indicators.get('ma20')} / {indicators.get('ma60')}",
        f"- RSI14：{indicators.get('rsi14')}，量能比：{indicators.get('volume_ratio')}",
        f"- MACD：{(indicators.get('macd') or {}).get('signal')}，BOLL：{(indicators.get('boll') or {}).get('position')}",
        f"- 近5日/20日收益：{indicators.get('return5')}% / {indicators.get('return20')}%，20日波动率：{indicators.get('volatility20')}%",
        "",
        "### 目标价情景测算",
        *[
            f"- {item.get('label')}：{item.get('target_price')} {quote.get('currency')}，"
            f"对应约 {item.get('upside_percent')}%，依据：{item.get('basis')}"
            for item in upside_targets
        ],
        "",
        "### 机会",
        *[f"- {item}" for item in opportunities],
        "",
        "### 风险",
        *[f"- {item}" for item in risks],
        "",
        "### 操作纪律",
        "- 不把这份分析当作买卖指令；先确认财报、公告、行业政策和仓位风险。",
        "- 若已有持仓，优先检查成本线、止损线和单票仓位上限。",
        "- 若准备新开仓，等待价格、量能和市场情绪至少两项信号同向。",
    ]
    if question:
        lines.extend(["", "### 你的问题", f"- {question}"])
    return "\n".join(lines)


def _plain_language_answer(
    quote: dict[str, Any],
    indicators: dict[str, Any],
    score: int,
    stance: str,
    conclusion: dict[str, Any],
    risks: list[str],
    opportunities: list[str],
) -> dict[str, Any]:
    price = quote.get("price") or indicators.get("latest")
    support = indicators.get("support")
    resistance = indicators.get("resistance")
    trend = indicators.get("trend")
    change_percent = _num(quote.get("change_percent")) or 0
    rsi = indicators.get("rsi14")

    if score >= 70:
        headline = "这票现在偏强，但别追着买"
        action = f"有仓可以继续拿，重点看能不能放量突破 {resistance}；没仓就等回踩或突破确认。"
        invalidation = f"如果跌回 {support} 附近还没有资金承接，就别硬扛。"
    elif score >= 55:
        headline = "有点转好，但还没到放心加仓"
        action = f"先看价格能不能站稳 MA20，并且靠近 {resistance} 时不是缩量冲高。"
        invalidation = f"如果跌破 {support} 或反弹没量，先按观望处理。"
    elif score >= 40:
        headline = "现在更适合等，不适合上头操作"
        action = f"围绕 {price} 观察，先确认 {support} 能不能守住，再考虑下一步。"
        invalidation = "如果大盘也弱、个股又破位，就先保护本金。"
    else:
        headline = "偏弱，先别急着补仓"
        action = f"重点不是猜底，而是看 {support} 附近能不能止跌；不能止跌就先降风险。"
        invalidation = "只有重新放量站回关键均线，才算情况变好。"

    notes = []
    if trend:
        notes.append(f"趋势是「{trend}」。")
    if change_percent <= -3:
        notes.append("今天跌得比较明显，先查有没有公告、财报或行业利空。")
    elif change_percent >= 3:
        notes.append("今天涨得比较快，追高的性价比会变差。")
    if rsi is not None and rsi >= 75:
        notes.append("RSI 已偏热，短线要防回撤。")
    elif rsi is not None and rsi <= 30:
        notes.append("RSI 偏低，可能有反弹，但不等于反转。")
    if opportunities:
        notes.append(f"好处是：{opportunities[0]}")
    if risks:
        notes.append(f"风险是：{risks[0]}")
    summary = "".join(notes) or f"综合看是「{stance}」，先按计划观察，不要被单日涨跌带节奏。"
    return {
        "headline": headline,
        "summary": summary,
        "action": action,
        "invalidation": invalidation,
    }


def _suggest_alerts(quote: dict[str, Any], indicators: dict[str, Any]) -> list[dict[str, Any]]:
    price = quote.get("price") or indicators.get("latest")
    if not price:
        return []
    high = indicators.get("high20") or price * 1.08
    low = indicators.get("low20") or price * 0.92
    return [
        {"type": "breakout", "label": "突破 20 日高点", "price": _round(high), "enabled": False},
        {"type": "stop_loss", "label": "跌破 20 日低点", "price": _round(low), "enabled": False},
        {"type": "ma20", "label": "回踩/跌破 MA20", "price": indicators.get("ma20"), "enabled": False},
        {"type": "daily_move", "label": "单日涨跌超过 5%", "percent": 5, "enabled": False},
    ]


def _clear_conclusion(quote: dict[str, Any], indicators: dict[str, Any], score: int, stance: str) -> dict[str, Any]:
    trend = indicators.get("trend")
    rsi = indicators.get("rsi14")
    price = quote.get("price") or indicators.get("latest")
    support = indicators.get("support")
    resistance = indicators.get("resistance")
    if score >= 70:
        label = "偏强，可继续观察突破"
        action = f"持有或观察突破 {resistance} 后的量能确认。"
    elif score >= 55:
        label = "中性偏多，但需要确认"
        action = f"等待站稳 MA20 或突破 {resistance}，再提高关注级别。"
    elif score >= 40:
        label = "中性观望，不建议追高"
        action = f"先观察 {support} 是否守住；若不能收复 MA20，继续谨慎。"
    else:
        label = "偏弱谨慎，优先控制风险"
        action = f"若跌破 {support} 或反弹无量，优先降低风险暴露。"
    if trend == "空头排列" and rsi is not None and rsi <= 30:
        summary = (
            f"当前价格 {price} 处在弱趋势里的超卖区，可能有技术反弹，"
            "但还不能当作趋势反转。"
        )
    elif trend == "多头排列":
        summary = f"当前价格 {price} 处在多头结构中，趋势占优，但仍需留意放量滞涨。"
    else:
        summary = f"当前价格 {price} 的趋势结论为「{trend}」，综合评级为「{stance}」。"
    return {"label": label, "summary": summary, "action": action}


def _upside_targets(quote: dict[str, Any], indicators: dict[str, Any]) -> list[dict[str, Any]]:
    price = _num(quote.get("price") or indicators.get("latest"))
    if not price:
        return []
    ma20 = _num(indicators.get("ma20"))
    ma60 = _num(indicators.get("ma60"))
    resistance = _num(indicators.get("resistance"))
    high20 = _num(indicators.get("high20"))
    volatility = _num(indicators.get("volatility20")) or 30
    trend = indicators.get("trend")

    conservative_candidates = [value for value in [ma20, resistance] if value and value > price]
    conservative = min(conservative_candidates) if conservative_candidates else price * 1.04
    neutral = max([value for value in [resistance, high20, ma60] if value and value > price] or [conservative * 1.05])
    volatility_cap = min(max(volatility / 100 * 0.45, 0.08), 0.28)
    if trend == "空头排列":
        optimistic = max(neutral, price * (1 + min(volatility_cap, 0.18)))
        basis = "弱趋势下只按技术反弹上沿估算，需放量收复均线才有效"
    elif trend == "多头排列":
        optimistic = max(neutral * 1.05, price * (1 + volatility_cap))
        basis = "多头趋势延续时参考阻力突破和20日波动上沿"
    else:
        optimistic = max(neutral, price * (1 + min(volatility_cap, 0.22)))
        basis = "震荡结构下参考阻力位和20日波动上沿"
    targets = [
        {"label": "保守目标", "target_price": conservative, "basis": "先看 MA20/近端压力位能否收复"},
        {"label": "中性目标", "target_price": neutral, "basis": "参考20日高点、MA60和主要压力区"},
        {"label": "最高上沿", "target_price": optimistic, "basis": basis},
    ]
    normalized: list[dict[str, Any]] = []
    for item in targets:
        target = max(price, float(item["target_price"]))
        normalized.append(
            {
                "label": item["label"],
                "target_price": _round(target),
                "upside_percent": _round((target - price) / price * 100),
                "basis": item["basis"],
            }
        )
    return normalized


def _sentiment_stub(quote: dict[str, Any], indicators: dict[str, Any]) -> dict[str, Any]:
    cp = float(quote.get("change_percent") or 0)
    trend = indicators.get("trend")
    if cp > 2 and trend in {"多头排列", "短线强于中期"}:
        label = "偏积极"
        score = 68
    elif cp < -2:
        label = "偏谨慎"
        score = 38
    else:
        label = "中性"
        score = 52
    return {
        "label": label,
        "score": score,
        "note": "当前情绪基于价格和量能规则估算；接入新闻/社媒数据后可升级为真实舆情分析。",
    }


def _market_context_stub(quote: dict[str, Any], indicators: dict[str, Any]) -> dict[str, Any]:
    cp = float(quote.get("change_percent") or 0)
    trend = indicators.get("trend")
    if cp >= 1.5 and trend in {"多头排列", "短线强于中期"}:
        regime = "风险偏好回升"
    elif cp <= -1.5 or trend == "空头排列":
        regime = "风险偏好承压"
    else:
        regime = "结构性分化"
    return {
        "regime": regime,
        "focus": ["大盘指数方向", "行业资金流", "公司公告/财报", "隔夜外围市场"],
        "note": "市场上下文为本地规则推断；后续可接入东方财富/问财/雪球等数据源进一步增强。",
    }


def _position_plan(quote: dict[str, Any], indicators: dict[str, Any]) -> list[dict[str, str]]:
    price = quote.get("price") or indicators.get("latest")
    support = indicators.get("support")
    resistance = indicators.get("resistance")
    trend = indicators.get("trend")
    return [
        {"title": "观察位", "text": f"围绕 {price} 附近观察量价是否同向，趋势标签：{trend}。"},
        {"title": "防守位", "text": f"若有效跌破 {support} 或 MA20，需要降低仓位或重新评估逻辑。"},
        {"title": "进攻位", "text": f"若放量突破 {resistance}，再结合新闻/财报确认突破质量。"},
    ]


def _trend_label(latest: float | None, ma5: float | None, ma20: float | None, ma60: float | None) -> str:
    if latest and ma5 and ma20 and ma60:
        if latest > ma5 > ma20 > ma60:
            return "多头排列"
        if latest < ma5 < ma20 < ma60:
            return "空头排列"
        if latest > ma5 and ma5 > ma20:
            return "短线强于中期"
        if latest < ma5 and ma5 < ma20:
            return "短线弱于中期"
    return "震荡观察"


def _ma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def _rsi(values: list[float], window: int) -> float | None:
    if len(values) <= window:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(values[-window - 1 : -1], values[-window:]):
        change = current - previous
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
    avg_gain = sum(gains) / window
    avg_loss = sum(losses) / window
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _ema(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    multiplier = 2 / (window + 1)
    ema = sum(values[:window]) / window
    for value in values[window:]:
        ema = (value - ema) * multiplier + ema
    return ema


def _macd(values: list[float]) -> dict[str, Any]:
    if len(values) < 35:
        return {"dif": None, "dea": None, "histogram": None, "signal": "数据不足"}
    ema12 = _ema(values, 12)
    ema26 = _ema(values, 26)
    if ema12 is None or ema26 is None:
        return {"dif": None, "dea": None, "histogram": None, "signal": "数据不足"}
    dif_series: list[float] = []
    for index in range(26, len(values) + 1):
        short = _ema(values[:index], 12)
        long = _ema(values[:index], 26)
        if short is not None and long is not None:
            dif_series.append(short - long)
    dea = _ema(dif_series, 9)
    dif = ema12 - ema26
    histogram = (dif - dea) * 2 if dea is not None else None
    previous_histogram = None
    if len(dif_series) >= 10:
        previous_dea = _ema(dif_series[:-1], 9)
        previous_histogram = (dif_series[-2] - previous_dea) * 2 if previous_dea is not None else None
    if histogram is not None and previous_histogram is not None and previous_histogram <= 0 < histogram:
        signal = "金叉偏多"
    elif histogram is not None and previous_histogram is not None and previous_histogram >= 0 > histogram:
        signal = "死叉偏空"
    elif histogram is not None and histogram > 0:
        signal = "红柱延续"
    elif histogram is not None:
        signal = "绿柱延续"
    else:
        signal = "数据不足"
    return {"dif": _round(dif), "dea": _round(dea), "histogram": _round(histogram), "signal": signal}


def _boll(values: list[float], window: int) -> dict[str, Any]:
    if len(values) < window:
        return {"upper": None, "middle": None, "lower": None, "position": "数据不足"}
    sample = values[-window:]
    middle = sum(sample) / window
    variance = sum((value - middle) ** 2 for value in sample) / window
    std = math.sqrt(variance)
    upper = middle + 2 * std
    lower = middle - 2 * std
    latest = values[-1]
    if latest >= upper * 0.98:
        position = "上轨附近"
    elif latest <= lower * 1.02:
        position = "下轨附近"
    else:
        position = "通道中部"
    return {"upper": _round(upper), "middle": _round(middle), "lower": _round(lower), "position": position}


def _kdj_from_closes(values: list[float]) -> dict[str, Any]:
    if len(values) < 9:
        return {"k": None, "d": None, "j": None, "signal": "数据不足"}
    sample = values[-9:]
    low = min(sample)
    high = max(sample)
    rsv = 50 if high == low else (values[-1] - low) / (high - low) * 100
    k = (2 / 3) * 50 + (1 / 3) * rsv
    d = (2 / 3) * 50 + (1 / 3) * k
    j = 3 * k - 2 * d
    if j >= 90:
        signal = "短线过热"
    elif j <= 10:
        signal = "短线超卖"
    elif k > d:
        signal = "偏多"
    else:
        signal = "偏弱"
    return {"k": _round(k), "d": _round(d), "j": _round(j), "signal": signal}


def _return(values: list[float], window: int) -> float | None:
    if len(values) <= window or values[-window - 1] == 0:
        return None
    return (values[-1] - values[-window - 1]) / values[-window - 1] * 100


def _volatility(values: list[float], window: int) -> float | None:
    if len(values) <= window:
        return None
    returns = []
    for previous, current in zip(values[-window - 1 : -1], values[-window:]):
        if previous:
            returns.append((current - previous) / previous)
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252) * 100


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 2) -> float | None:
    number = _num(value)
    return round(number, digits) if number is not None else None
