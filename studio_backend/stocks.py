from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from typing import Any


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
TENCENT_KLINE_URLS = [
    "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
]


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


def _http_json(url: str, timeout: int = 12, retries: int = 2) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(max(1, retries + 1)):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 CreatorStudio/stock-module",
                "Accept": "application/json,text/plain,*/*",
                "Connection": "close",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.35 * (attempt + 1))
    raise last_error or RuntimeError("HTTP request failed")


def fetch_stock_chart(symbol: str, *, range_text: str = "6mo", interval: str = "1d") -> dict[str, Any]:
    errors: list[str] = []
    try:
        return _fetch_yahoo_chart(symbol, range_text=range_text, interval=interval)
    except Exception as exc:
        errors.append(f"Yahoo: {exc}")
    try:
        return _fetch_tencent_chart(symbol, range_text=range_text, interval=interval)
    except Exception as exc:
        errors.append(f"Tencent: {exc}")
    raise RuntimeError("；".join(errors) or "stock data unavailable")


def _fetch_yahoo_chart(symbol: str, *, range_text: str = "6mo", interval: str = "1d") -> dict[str, Any]:
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
        "data_source": "Yahoo Finance",
    }


def _tencent_code(symbol: str) -> str:
    normalized = normalize_stock_symbol(symbol)
    upper = normalized.upper()
    aliases = {
        "^GSPC": "usINX",
        "^IXIC": "usIXIC",
        "^DJI": "usDJI",
        "^HSI": "hkHSI",
    }
    if upper in aliases:
        return aliases[upper]
    if upper.endswith(".SZ"):
        return f"sz{upper[:-3]}"
    if upper.endswith(".SS"):
        return f"sh{upper[:-3]}"
    if upper.endswith(".HK"):
        code = upper[:-3]
        return f"hk{code.zfill(5)}"
    if upper.replace(".", "").replace("-", "").isalnum():
        return f"us{upper.split('.')[0]}"
    raise ValueError(f"unsupported Tencent symbol: {symbol}")


def _fetch_tencent_chart(symbol: str, *, range_text: str = "6mo", interval: str = "1d") -> dict[str, Any]:
    if interval != "1d":
        raise ValueError("Tencent fallback currently supports daily interval only")
    normalized = normalize_stock_symbol(symbol)
    code = _tencent_code(normalized)
    limit = 10 if range_text == "5d" else 180
    query = urllib.parse.urlencode({"param": f"{code},day,,,{limit},"})
    data: dict[str, Any] | None = None
    errors: list[str] = []
    for base_url in TENCENT_KLINE_URLS:
        try:
            data = _http_json(f"{base_url}?{query}", timeout=15, retries=2)
            break
        except Exception as exc:
            errors.append(str(exc))
    if data is None:
        raise RuntimeError("Tencent request failed: " + "；".join(errors))
    payload = (data.get("data") or {}).get(code) or {}
    rows = payload.get("qfqday") or payload.get("day") or []
    if not rows:
        raise RuntimeError("Tencent kline data unavailable")
    points: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            continue
        close = _num(row[2])
        if close is None:
            continue
        points.append(
            {
                "time": str(row[0]),
                "open": _num(row[1]),
                "close": close,
                "high": _num(row[3]),
                "low": _num(row[4]),
                "volume": _num(row[5]) or 0,
            }
        )
    if not points:
        raise RuntimeError("Tencent returned no valid kline points")
    quote_fields = payload.get("qt") or {}
    quote_row = quote_fields.get(code) if isinstance(quote_fields, dict) else None
    quote_row = quote_row if isinstance(quote_row, list) else []
    name = str(quote_row[1] if len(quote_row) > 1 else normalized)
    price = _num(quote_row[3] if len(quote_row) > 3 else points[-1]["close"])
    previous_close = _num(quote_row[4] if len(quote_row) > 4 else None)
    if previous_close is None and len(points) >= 2:
        previous_close = points[-2]["close"]
    market = infer_market(normalized)
    return {
        "symbol": normalized,
        "name": name or normalized,
        "currency": "CNY" if market == "A股" else "HKD" if market == "港股" else "USD",
        "exchange": "SZSE" if normalized.endswith(".SZ") else "SSE" if normalized.endswith(".SS") else "HKEX" if normalized.endswith(".HK") else "US",
        "market": market,
        "regular_market_price": price,
        "previous_close": previous_close,
        "points": points,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": "Tencent Finance fallback",
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
        **{key: chart[key] for key in ["symbol", "name", "currency", "exchange", "market", "fetched_at", "data_source"]},
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
    try:
        data = _http_json(url)
    except Exception:
        normalized = normalize_stock_symbol(text)
        try:
            quote = stock_quote(normalized)
        except Exception:
            return []
        return [
            {
                "symbol": quote["symbol"],
                "name": quote["name"],
                "exchange": quote["exchange"],
                "market": quote["market"],
                "type": "EQUITY",
            }
        ]
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


def analyze_stock(symbol: str, *, question: str = "", position: dict[str, Any] | None = None) -> dict[str, Any]:
    chart = fetch_stock_chart(symbol)
    quote = stock_quote(chart["symbol"])
    points = chart["points"]
    closes = [float(item["close"]) for item in points if item.get("close") is not None]
    volumes = [float(item.get("volume") or 0) for item in points]
    indicators = _technical_indicators(closes, volumes)
    score, stance, risks, opportunities = _score_stock(quote, indicators)
    buffett_framework = _buffett_framework(quote, indicators, score, stance, risks, opportunities, position or {})
    conclusion = _clear_conclusion(quote, indicators, score, stance)
    upside_targets = _upside_targets(quote, indicators)
    plain_answer = _plain_language_answer(quote, indicators, score, stance, conclusion, risks, opportunities, question, position or {})
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
        buffett_framework=buffett_framework,
    )
    return {
        "quote": quote,
        "kline": points[-80:],
        "indicators": indicators,
        "score": score,
        "stance": stance,
        "conclusion": conclusion,
        "plain_answer": plain_answer,
        "buffett_framework": buffett_framework,
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
    buffett_framework: dict[str, Any],
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
        "### 巴菲特价值投资校验",
        f"- 总评：{buffett_framework.get('label')}，价值分 {buffett_framework.get('score')}/100。{buffett_framework.get('summary')}",
        f"- 能力圈：{buffett_framework.get('circle_of_competence')}",
        f"- 安全边际：{buffett_framework.get('margin_of_safety')}",
        f"- 纪律动作：{buffett_framework.get('discipline')}",
        "",
        "### 3M 决策法则",
        *[
            f"- {item.get('name')}：{item.get('status')}。{item.get('note')}"
            for item in buffett_framework.get("three_m") or []
        ],
        "",
        "### 护城河观察",
        *[f"- {item}" for item in buffett_framework.get("moat_checks") or []],
        "",
        "### 财务与估值待核验",
        *[f"- {item}" for item in buffett_framework.get("financial_checklist") or []],
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


def _buffett_framework(
    quote: dict[str, Any],
    indicators: dict[str, Any],
    technical_score: int,
    stance: str,
    risks: list[str],
    opportunities: list[str],
    position: dict[str, Any],
) -> dict[str, Any]:
    text_fields = {
        "circle": str(position.get("circle_of_competence") or position.get("circle") or "").strip(),
        "business": str(position.get("business_quality") or position.get("business") or "").strip(),
        "moat": str(position.get("moat_notes") or position.get("moat") or "").strip(),
        "management": str(position.get("management_notes") or position.get("management") or "").strip(),
        "financials": str(position.get("financial_notes") or position.get("financials") or "").strip(),
        "intrinsic": str(position.get("intrinsic_value") or "").strip(),
    }
    price = _num(quote.get("price") or indicators.get("latest"))
    intrinsic_value = _num(text_fields["intrinsic"])
    margin_pct = ((intrinsic_value - price) / intrinsic_value * 100) if price and intrinsic_value else None
    trend = indicators.get("trend")
    volatility = _num(indicators.get("volatility20")) or 0
    return20 = _num(indicators.get("return20")) or 0

    score = 38
    positives: list[str] = []
    concerns: list[str] = []
    if text_fields["circle"]:
        score += 10
        positives.append("已填写能力圈边界。")
    else:
        concerns.append("未说明自己为什么看得懂这家公司。")
    if text_fields["business"]:
        score += 10
        positives.append("已描述业务本质/盈利模式。")
    else:
        concerns.append("需用一句话讲清公司如何赚钱。")
    if text_fields["moat"]:
        score += 12
        positives.append("已记录护城河线索。")
    else:
        concerns.append("需核验品牌、成本、网络效应或转换成本。")
    if text_fields["management"]:
        score += 8
        positives.append("已记录管理层判断。")
    else:
        concerns.append("需核验回购、分红、股权稀释和资本配置。")
    if text_fields["financials"]:
        score += 8
        positives.append("已记录财务/财报线索。")
    else:
        concerns.append("未接入真实财报数据，ROE、负债率、自由现金流仍待核验。")
    if margin_pct is not None:
        if margin_pct >= 30:
            score += 18
            positives.append(f"你给出的内在价值相对现价有约 {round(margin_pct, 2)}% 安全边际。")
        elif margin_pct > 0:
            score += 6
            concerns.append(f"你给出的安全边际约 {round(margin_pct, 2)}%，低于 30% 缓冲。")
        else:
            score -= 14
            concerns.append(f"现价高于你给出的内在价值约 {abs(round(margin_pct, 2))}%。")
    else:
        concerns.append("未填写内在价值估算，不能判断是否有 30% 安全边际。")
    if trend == "空头排列":
        score -= 8
        concerns.append("技术趋势偏弱，价值投资也不应急着摊平。")
    elif trend == "多头排列" and technical_score >= 70:
        score += 4
        positives.append("价格趋势较强，但仍需用价值而非热度做锚。")
    if volatility >= 45:
        score -= 6
        concerns.append("波动率偏高，仓位上限应更保守。")
    if return20 >= 18:
        concerns.append("近20日涨幅较快，需避免把价格动量误判成安全边际。")
    score = max(0, min(100, int(round(score))))

    if score >= 75:
        label = "可进入深度研究"
        discipline = "先核验10-K/年报和估值，再分批；没有30%安全边际不重仓。"
    elif score >= 58:
        label = "观察池候选"
        discipline = "补齐财务和管理层证据，等待价格进入甜蜜击球区。"
    elif score >= 42:
        label = "证据不足"
        discipline = "先不扩大仓位，把能力圈、护城河和内在价值写清楚。"
    else:
        label = "谨慎回避"
        discipline = "不要因为短线信号或概念热度买入，先保护现金。"

    three_m = [
        {
            "name": "Meaning 业务本质",
            "status": "已描述" if text_fields["business"] else "待补充",
            "note": text_fields["business"] or "用一句话写清盈利模式、客户是谁、为什么能持续赚钱。",
        },
        {
            "name": "Moat 护城河",
            "status": "有线索" if text_fields["moat"] else "待核验",
            "note": text_fields["moat"] or "检查品牌溢价、成本优势、网络效应、转换成本和定价权。",
        },
        {
            "name": "Management 管理层",
            "status": "有记录" if text_fields["management"] else "待核验",
            "note": text_fields["management"] or "检查回购/分红、资本配置、股权稀释、是否坦诚披露错误。",
        },
    ]
    financial_checklist = [
        text_fields["financials"] or "读取近10年年报/10-K：ROE是否长期高于15%，负债率是否低于50%。",
        "核验自由现金流是否持续覆盖利润和再投资需求，增长率是否跑赢通胀。",
        "估值对比历史区间和同行：PE/PB/PS/EV-EBITDA 是否给出足够折价。",
        "若是金融股，重点看P/B、坏账/拨备、资本充足率；若是现金牛，关注股息率和回购质量。",
    ]
    moat_checks = [
        text_fields["moat"] or "暂无护城河描述，先把品牌、成本、网络效应、转换成本四项逐条打分。",
        "优先寻找提价不明显伤害销量的证据，而不是只看短期涨跌。",
        "远离自己无法解释商业模式、靠概念估值或衍生品结构驱动的标的。",
    ]
    margin_text = (
        f"内在价值 {intrinsic_value}，现价 {price}，安全边际约 {round(margin_pct, 2)}%。"
        if margin_pct is not None
        else "未填写内在价值，暂不能判定是否满足30%+安全边际。"
    )
    summary_parts = positives[:2] + concerns[:2]
    return {
        "score": score,
        "label": label,
        "summary": " ".join(summary_parts),
        "circle_of_competence": text_fields["circle"] or "未填写；不在能力圈内就只做观察，不做重仓决策。",
        "margin_of_safety": margin_text,
        "discipline": discipline,
        "three_m": three_m,
        "moat_checks": moat_checks,
        "financial_checklist": financial_checklist,
        "positives": positives,
        "concerns": concerns + risks[:2],
        "opportunity_bridge": opportunities[:2],
        "source": "buffett-investing SKILL.md + 本地行情规则",
    }


def _plain_language_answer(
    quote: dict[str, Any],
    indicators: dict[str, Any],
    score: int,
    stance: str,
    conclusion: dict[str, Any],
    risks: list[str],
    opportunities: list[str],
    question: str = "",
    position: dict[str, Any] | None = None,
) -> dict[str, Any]:
    price = quote.get("price") or indicators.get("latest")
    support = indicators.get("support")
    resistance = indicators.get("resistance")
    ma20 = indicators.get("ma20")
    trend = indicators.get("trend")
    change_percent = _num(quote.get("change_percent")) or 0
    rsi = indicators.get("rsi14")
    volatility = _num(indicators.get("volatility20")) or 0
    low20 = indicators.get("low20") or support
    high20 = indicators.get("high20") or resistance
    text = str(question or "")
    position = position or {}
    cost = _num(position.get("cost"))
    shares = _num(position.get("shares"))
    profit_percent = ((price - cost) / cost * 100) if price and cost else None
    has_position = bool(shares and shares > 0)
    wants_position = any(word in text for word in ["减仓", "加仓", "仓位", "补仓", "持有", "卖", "买"])
    wants_range = any(word in text for word in ["最高", "最低", "目标", "到多少", "预测", "空间"])

    action = _direct_action(score, trend, rsi, volatility, change_percent)
    headline = action["headline"]
    action_text = action["action"]
    invalidation = action["invalidation"].format(support=support, resistance=resistance, ma20=ma20)

    if wants_position:
        action_text = _position_answer(score, trend, rsi, volatility, change_percent, support, resistance, ma20)
    if has_position and profit_percent is not None:
        action_text = _owned_position_answer(
            score,
            trend,
            rsi,
            volatility,
            price,
            cost,
            profit_percent,
            support,
            resistance,
            ma20,
        )
        headline = _owned_position_headline(score, trend, profit_percent, volatility)
    if wants_range:
        invalidation = _range_answer(price, low20, high20, support, resistance, ma20, volatility, trend)

    notes = [f"结论依据：评分 {score}/100，趋势「{trend}」。"]
    if price is not None:
        notes.append(f"现价约 {price}。")
    if has_position and cost:
        notes.append(f"你的成本约 {cost}，当前浮亏约 {round(profit_percent or 0, 2)}%。")
    if change_percent <= -3:
        notes.append("当天跌幅较大，说明短线资金不稳。")
    elif change_percent >= 3:
        notes.append("当天涨得较快，追高性价比下降。")
    if rsi is not None and rsi >= 75:
        notes.append("RSI 偏热，短线要防冲高回落。")
    elif rsi is not None and rsi <= 30:
        notes.append("RSI 偏低，可能有反弹，但还不能当反转。")
    if volatility >= 45:
        notes.append("20日波动率偏高，仓位必须更保守。")
    if opportunities:
        notes.append(f"有利点：{opportunities[0]}")
    if risks:
        notes.append(f"主要风险：{risks[0]}")
    summary = "".join(notes) or f"综合看是「{stance}」，先按计划观察，不要被单日涨跌带节奏。"
    return {
        "headline": headline,
        "summary": summary,
        "action": action_text,
        "invalidation": invalidation,
    }


def _direct_action(
    score: int,
    trend: str | None,
    rsi: float | None,
    volatility: float,
    change_percent: float,
) -> dict[str, str]:
    if score < 40 or trend == "空头排列":
        return {
            "headline": "结论：偏弱，先防守，不要补仓",
            "action": "下一步：已有仓位先降风险；没有仓位先别买，等重新站回 MA20 再看。",
            "invalidation": "只有重新站回 MA20（{ma20}）并且放量突破 {resistance}，才算转强。",
        }
    if rsi is not None and rsi <= 30 and score < 55:
        return {
            "headline": "结论：可能反弹，但不是加仓信号",
            "action": "下一步：可以观察止跌反弹，但不要因为 RSI 低就补仓；先等一根放量阳线或站回 MA20。",
            "invalidation": "如果跌破 {support}，说明反弹失败，先减风险。",
        }
    if volatility >= 45 or change_percent <= -4:
        return {
            "headline": "结论：波动太大，仓位要轻",
            "action": "下一步：已有仓位最多保留观察仓；想买也只适合小仓试，不适合一次性加满。",
            "invalidation": "如果跌破 {support} 或收不回 MA20（{ma20}），继续按弱势处理。",
        }
    if score >= 70 and trend in {"多头排列", "短线强于中期"}:
        return {
            "headline": "结论：趋势偏强，持有比追高更合适",
            "action": "下一步：已有仓位继续拿；没仓等回踩 MA20 或突破 {resistance} 后再小仓跟。",
            "invalidation": "如果跌破 MA20（{ma20}）且不能快速收回，就先降低仓位。",
        }
    if score >= 55:
        return {
            "headline": "结论：略有转好，但还不能重仓",
            "action": "下一步：先观察能否站稳 MA20；确认前不建议加仓，最多小仓试错。",
            "invalidation": "如果跌破 {support}，先停止加仓，重新评估。",
        }
    return {
        "headline": "结论：中性偏弱，先等信号",
        "action": "下一步：不建议加仓；已有仓位看 MA20 和20日低点，守不住就减仓。",
        "invalidation": "只有放量突破 {resistance}，才把它从观察改为进攻。",
    }


def _position_answer(
    score: int,
    trend: str | None,
    rsi: float | None,
    volatility: float,
    change_percent: float,
    support: float | None,
    resistance: float | None,
    ma20: float | None,
) -> str:
    if score < 40 or trend == "空头排列":
        return f"仓位建议：减仓或只留小观察仓。不要加仓。防守线看 {support}，站回 MA20（{ma20}）之前不考虑加仓。"
    if volatility >= 45:
        return f"仓位建议：因为波动太大，只适合轻仓。已有仓位可减到让你睡得着的位置；想加仓也等站稳 MA20（{ma20}）后再分批。"
    if rsi is not None and rsi <= 30:
        return f"仓位建议：不是加仓点。RSI 低只说明可能反弹，先看 {support} 是否止跌，突破 {resistance} 才能提高仓位。"
    if score >= 70 and trend in {"多头排列", "短线强于中期"}:
        return f"仓位建议：已有仓位可以持有；不建议追高满仓。突破 {resistance} 后可小幅加，跌破 MA20（{ma20}）就减。"
    if score >= 55:
        return f"仓位建议：可以观察，不适合重仓。若站稳 MA20（{ma20}）且突破 {resistance}，再考虑小仓加；跌破 {support} 就减。"
    if change_percent <= -3:
        return f"仓位建议：今天弱，不加仓。已有仓位先看 {support}，跌破就减；反弹到 MA20（{ma20}）附近量不够也别追。"
    return f"仓位建议：先不加仓，已有仓位可继续观察。上方看 {resistance}，下方看 {support}；方向没出来前不要扩大仓位。"


def _owned_position_headline(score: int, trend: str | None, profit_percent: float, volatility: float) -> str:
    if profit_percent <= -20 and (score < 55 or trend == "空头排列"):
        return "结论：你已经深套，别补仓摊平，先降风险"
    if profit_percent <= -8 and (score < 55 or volatility >= 45):
        return "结论：亏损持仓偏危险，先别加仓"
    if profit_percent >= 15 and score < 55:
        return "结论：有利润就先保护利润"
    if score >= 70 and trend in {"多头排列", "短线强于中期"}:
        return "结论：持仓可以继续跟，但别追高加满"
    return "结论：先按持仓纪律处理，不要凭感觉加仓"


def _owned_position_answer(
    score: int,
    trend: str | None,
    rsi: float | None,
    volatility: float,
    price: float | None,
    cost: float,
    profit_percent: float,
    support: float | None,
    resistance: float | None,
    ma20: float | None,
) -> str:
    if profit_percent <= -20 and (score < 55 or trend == "空头排列"):
        return (
            f"仓位建议：不加仓，不补仓摊低成本。你成本 {cost}，现价 {price}，浮亏约 {round(profit_percent, 2)}%。"
            f"如果还持有较重，建议先减到小观察仓；只有重新站回 MA20（{ma20}）并突破 {resistance}，才考虑加回。"
        )
    if profit_percent <= -8 and volatility >= 45:
        return (
            f"仓位建议：先减风险，不要扩大仓位。当前浮亏约 {round(profit_percent, 2)}%，且波动率高；"
            f"跌破 {support} 继续减，站回 MA20（{ma20}）再观察。"
        )
    if profit_percent <= -8 and score < 55:
        return (
            f"仓位建议：先不要加仓。当前浮亏约 {round(profit_percent, 2)}%，趋势没有修复；"
            f"守不住 {support} 就减仓，突破 {resistance} 后再谈加仓。"
        )
    if profit_percent >= 15 and score < 55:
        return f"仓位建议：可以分批止盈或上移止损。评分不强，别让利润回吐；跌破 MA20（{ma20}）就减。"
    if score >= 70 and trend in {"多头排列", "短线强于中期"}:
        return f"仓位建议：已有仓位可持有；若突破 {resistance} 可小幅加，跌破 MA20（{ma20}）就减。"
    if rsi is not None and rsi <= 30:
        return f"仓位建议：先等反弹确认，不要立刻补仓。RSI 低可能反弹，但必须站回 MA20（{ma20}）才算修复。"
    return f"仓位建议：维持或小幅降仓，不加仓。上方看 {resistance}，下方看 {support}；突破前不要扩大仓位。"


def _range_answer(
    price: float | None,
    low20: float | None,
    high20: float | None,
    support: float | None,
    resistance: float | None,
    ma20: float | None,
    volatility: float,
    trend: str | None,
) -> str:
    if not price:
        return "价格区间：当前行情数据不足，先不要做价格预测。"
    daily_move = min(max((volatility or 30) / math.sqrt(252) / 100, 0.018), 0.055)
    short_low = min([value for value in [low20, support, price * (1 - daily_move * 2)] if value])
    short_high = max([value for value in [high20, resistance, price * (1 + daily_move * 2)] if value])
    if trend == "空头排列":
        short_high = min(short_high, max(price * 1.08, ma20 or price))
    return (
        f"价格区间：短线先看 {round(short_low, 2)} 到 {round(short_high, 2)}。"
        f"跌破 {support} 偏弱，突破 {resistance} 才有继续上看的理由；"
        f"MA20（{ma20}）是中间分水岭。"
    )


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
