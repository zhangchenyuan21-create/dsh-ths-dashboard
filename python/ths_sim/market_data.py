"""Public market-data helpers for the local THS dashboard.

The dashboard deliberately mixes sources:

* account / positions / five-level quote: Tonghuashun simulated account;
* minute and daily candles: Eastmoney public kline endpoint;
* money flow: Eastmoney public fund-flow endpoint;
* quote fallback: Tencent public quote endpoint.

No cookie is sent to the public providers.  ``ths_sim.client`` remains the only
place that talks to the simulated trading account.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.error
import urllib.request
from typing import Any, Iterable

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0"
)
EM_HEADERS = {
    "User-Agent": UA,
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "application/json,text/plain,*/*",
}
TX_HEADERS = {
    "User-Agent": UA,
    "Referer": "https://gu.qq.com/",
}


def _http_text(url: str, *, headers: dict[str, str] | None = None,
               timeout: float = 15.0, retries: int = 2) -> str:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            for enc in ("utf-8-sig", "utf-8", "gb18030"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"market data request failed: {last}")


def symbol_for_public(symbol: str) -> tuple[str, str]:
    """Return (exchange-prefixed code, Eastmoney secid)."""
    symbol = str(symbol).strip()
    if "." in symbol and not symbol[0].isdigit():
        right = symbol.split(".", 1)[1]
        if right.isdigit() and len(right) == 6:
            symbol = right
    digits = re.sub(r"\D", "", symbol)[-6:]
    if len(digits) != 6:
        raise ValueError(f"invalid stock code: {symbol!r}")
    if digits.startswith("6"):
        return "sh" + digits, "1." + digits
    if digits.startswith(("0", "3")):
        return "sz" + digits, "0." + digits
    if digits.startswith(("4", "8")):
        return "bj" + digits, "0." + digits
    return "sh" + digits, "1." + digits


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "-", "--"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def simple_ma(values: Iterable[float], window: int) -> list[float | None]:
    vals = [float(v) for v in values]
    if window <= 0:
        return [None] * len(vals)
    out: list[float | None] = []
    total = 0.0
    for i, value in enumerate(vals):
        total += value
        if i >= window:
            total -= vals[i - window]
        out.append(round(total / window, 6) if i + 1 >= window else None)
    return out


def _ema(values: list[float], window: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (window + 1.0)
    out = [float(values[0])]
    for value in values[1:]:
        out.append(alpha * float(value) + (1.0 - alpha) * out[-1])
    return out


def macd(values: Iterable[float], fast: int = 12, slow: int = 26,
         signal: int = 9) -> dict[str, list[float]]:
    closes = [float(v) for v in values]
    if not closes:
        return {"dif": [], "dea": [], "hist": []}
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    dif = [a - b for a, b in zip(ema_fast, ema_slow)]
    dea = _ema(dif, signal)
    hist = [2.0 * (a - b) for a, b in zip(dif, dea)]
    return {
        "dif": [round(x, 6) for x in dif],
        "dea": [round(x, 6) for x in dea],
        "hist": [round(x, 6) for x in hist],
    }


def eastmoney_kline(symbol: str, period: str = "5", limit: int = 240) -> dict:
    code, secid = symbol_for_public(symbol)
    klt = "101" if str(period).lower() in ("day", "d", "daily") else str(period)
    if klt not in ("1", "5", "15", "30", "60", "101"):
        raise ValueError(f"unsupported kline period: {period}")
    limit = max(30, min(int(limit), 500))
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}&klt={klt}&fqt=1&lmt={limit}&end=20500101"
        "&fields1=f1,f2,f3,f4,f5,f6"
        "&fields2=f51,f52,f53,f54,f55,f56,f57"
    )
    payload = json.loads(_http_text(url, headers=EM_HEADERS))
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or not data.get("klines"):
        raise RuntimeError(f"Eastmoney returned no kline for {symbol} ({period})")
    bars: list[dict[str, Any]] = []
    for row in data["klines"]:
        parts = str(row).split(",")
        if len(parts) < 7:
            continue
        bars.append({
            "time": parts[0],
            "open": _as_float(parts[1]),
            "close": _as_float(parts[2]),
            "high": _as_float(parts[3]),
            "low": _as_float(parts[4]),
            "volume": _as_float(parts[5]) * 100.0,  # Eastmoney volume is in lots
            "amount": _as_float(parts[6]),
        })
    closes = [b["close"] for b in bars]
    return {
        "symbol": code,
        "name": str(data.get("name") or ""),
        "period": "day" if klt == "101" else f"{klt}m",
        "bars": bars,
        "ma5": simple_ma(closes, 5),
        "ma10": simple_ma(closes, 10),
        "macd": macd(closes),
        "pre_close": _as_float(data.get("preKPrice")),
        "source": "eastmoney",
    }


def _flow_row(row: str) -> dict[str, Any] | None:
    parts = str(row).split(",")
    if len(parts) < 6:
        return None
    return {
        "time": parts[0],
        "main": _as_float(parts[1]),
        "small": _as_float(parts[2]),
        "medium": _as_float(parts[3]),
        "large": _as_float(parts[4]),
        "super": _as_float(parts[5]),
    }


def eastmoney_flow(symbol: str, minute_limit: int = 240,
                   daily_limit: int = 20) -> dict:
    _, secid = symbol_for_public(symbol)
    minute_url = (
        "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
        f"?lmt=0&klt=1&secid={secid}&fields1=f1,f2,f3,f7"
        "&fields2=f51,f52,f53,f54,f55,f56"
    )
    daily_url = (
        "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
        f"?lmt={max(5, min(int(daily_limit), 60))}&klt=101&secid={secid}"
        "&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56"
    )
    minute = [_flow_row(x) for x in (
        json.loads(_http_text(minute_url, headers=EM_HEADERS))
        .get("data", {}) or {}).get("klines", [])]
    daily = [_flow_row(x) for x in (
        json.loads(_http_text(daily_url, headers=EM_HEADERS))
        .get("data", {}) or {}).get("klines", [])]
    minute = [x for x in minute if x is not None][-minute_limit:]
    daily = [x for x in daily if x is not None][-daily_limit:]
    last5 = daily[-5:]
    five_day = {
        key: round(sum(float(x.get(key, 0)) for x in last5), 2)
        for key in ("main", "small", "medium", "large", "super")
    }
    return {
        "symbol": symbol_for_public(symbol)[0],
        "minute": minute,
        "daily": daily,
        "today": minute[-1] if minute else (daily[-1] if daily else None),
        "five_day": five_day,
        "source": "eastmoney",
    }


def tencent_quote(symbol: str) -> dict:
    prefixed, _ = symbol_for_public(symbol)
    text = _http_text(
        f"https://qt.gtimg.cn/q={prefixed}", headers=TX_HEADERS)
    match = re.search(r'="([^"]*)"', text)
    if not match:
        raise RuntimeError(f"Tencent returned no quote for {symbol}")
    fields = match.group(1).split("~")
    if len(fields) < 35:
        raise RuntimeError(f"Tencent quote layout changed for {symbol}")
    def px(i: int) -> float:
        return _as_float(fields[i]) if i < len(fields) else 0.0
    def qty(i: int) -> int:
        return _as_int(fields[i]) if i < len(fields) else 0
    bids = [(px(9 + 2 * i), qty(10 + 2 * i)) for i in range(5)]
    asks = [(px(19 + 2 * i), qty(20 + 2 * i)) for i in range(5)]
    bids = [x for x in bids if x[0] > 0]
    asks = [x for x in asks if x[0] > 0]
    return {
        "symbol": prefixed,
        "name": fields[1],
        "last_price": px(3),
        "pre_close": px(4),
        "open": px(5),
        "high": px(33),
        "low": px(34),
        "change": px(31),
        "change_pct": px(32),
        "volume": px(6),
        "amount": px(37) * 10000.0,
        "bid1": bids[0][0] if bids else 0.0,
        "ask1": asks[0][0] if asks else 0.0,
        "bids": [list(x) for x in bids],
        "asks": [list(x) for x in asks],
        "source": "tencent",
    }


def ths_quote(client: Any, symbol: str) -> dict:
    quote = client.query_quote(symbol)
    return {
        "symbol": quote.symbol,
        "name": "",
        "last_price": quote.last_price,
        "can_buy": quote.can_buy,
        "market_code": quote.market_code,
        "bid1": quote.bid1,
        "ask1": quote.ask1,
        "bids": [list(x) for x in quote.bids],
        "asks": [list(x) for x in quote.asks],
        "source": "ths",
    }


def now_text() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")

SINA_HEADERS = {
    "User-Agent": UA,
    "Referer": "https://finance.sina.com.cn/",
}
SINA_FLOW_HEADERS = {
    "User-Agent": UA,
    "Referer": "https://vip.stock.finance.sina.com.cn/",
}


def sina_kline(symbol: str, period: str = "5", limit: int = 240) -> dict:
    prefixed, _ = symbol_for_public(symbol)
    scale = "240" if str(period).lower() in ("day", "d", "daily") else str(period)
    if scale not in ("1", "5", "15", "30", "60", "240"):
        raise ValueError(f"unsupported kline period: {period}")
    limit = max(30, min(int(limit), 500))
    url = (
        "https://quotes.sina.cn/cn/api/json_v2.php/"
        "CN_MarketDataService.getKLineData"
        f"?symbol={prefixed}&scale={scale}&ma=5&datalen={limit}"
    )
    payload = json.loads(_http_text(url, headers=SINA_HEADERS))
    if not isinstance(payload, list) or not payload:
        raise RuntimeError(f"Sina returned no kline for {symbol} ({period})")
    bars: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        bars.append({
            "time": str(row.get("day") or ""),
            "open": _as_float(row.get("open")),
            "close": _as_float(row.get("close")),
            "high": _as_float(row.get("high")),
            "low": _as_float(row.get("low")),
            "volume": _as_float(row.get("volume")),
            "amount": _as_float(row.get("amount")),
        })
    closes = [b["close"] for b in bars]
    pre_close = bars[-2]["close"] if len(bars) >= 2 else 0.0
    return {
        "symbol": prefixed,
        "name": "",
        "period": "day" if scale == "240" else f"{scale}m",
        "bars": bars,
        "ma5": simple_ma(closes, 5),
        "ma10": simple_ma(closes, 10),
        "macd": macd(closes),
        "pre_close": pre_close,
        "source": "sina",
    }


def fetch_kline(symbol: str, period: str = "5", limit: int = 240) -> dict:
    """Sina first (stable in this environment), Eastmoney as fallback."""
    errors = []
    for source in (sina_kline, eastmoney_kline):
        try:
            return source(symbol, period=period, limit=limit)
        except Exception as exc:
            errors.append(f"{source.__name__}: {exc}")
    raise RuntimeError("all kline sources failed: " + " | ".join(errors))


def _sina_daily_flow(symbol: str, limit: int = 30) -> list[dict[str, Any]]:
    prefixed, _ = symbol_for_public(symbol)
    url = (
        "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        "MoneyFlow.ssl_qsfx_zjlrqs"
        f"?page=1&num={max(5, min(int(limit), 5000))}"
        f"&sort=opendate&asc=0&daima={prefixed}"
    )
    text = _http_text(url, headers=SINA_FLOW_HEADERS)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        text = re.sub(r"([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', text)
        payload = json.loads(text)
    if not isinstance(payload, list):
        raise RuntimeError(f"Sina returned no flow history for {symbol}")
    rows = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        rows.append({
            "time": str(item.get("opendate") or ""),
            "main": _as_float(item.get("netamount")),
            "super": _as_float(item.get("r0_net")),
            "large": None,
            "medium": None,
            "small": None,
        })
    rows.sort(key=lambda x: x["time"])
    return rows


def _sina_today_flow(symbol: str) -> dict[str, Any] | None:
    prefixed, _ = symbol_for_public(symbol)
    url = (
        "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        f"MoneyFlow.ssi_ssfx_flzjtj?daima={prefixed}"
    )
    payload = json.loads(_http_text(url, headers=SINA_FLOW_HEADERS))
    if not isinstance(payload, dict):
        return None
    def side(a: str, b: str) -> float:
        return _as_float(payload.get(a)) - _as_float(payload.get(b))
    return {
        "time": "",
        "main": _as_float(payload.get("netamount")),
        "super": side("r0_in", "r0_out"),
        "large": side("r1_in", "r1_out"),
        "medium": side("r2_in", "r2_out"),
        "small": side("r3_in", "r3_out"),
    }


def sina_flow(symbol: str, daily_limit: int = 20) -> dict:
    daily = _sina_daily_flow(symbol, limit=max(daily_limit, 20))[-daily_limit:]
    today = _sina_today_flow(symbol)
    if today is not None:
        if daily:
            today["time"] = daily[-1]["time"]
    elif daily:
        today = daily[-1]
    last5 = daily[-5:]
    five_day = {
        "main": round(sum(float(x.get("main") or 0) for x in last5), 2),
        "super": round(sum(float(x.get("super") or 0) for x in last5), 2),
        "large": None,
        "medium": None,
        "small": None,
    }
    return {
        "symbol": symbol_for_public(symbol)[0],
        "minute": [],
        "daily": daily,
        "today": today,
        "five_day": five_day,
        "source": "sina",
    }


def fetch_flow(symbol: str) -> dict:
    """Sina daily/category flow first; Eastmoney intraday flow as fallback."""
    errors = []
    for source in (sina_flow, eastmoney_flow):
        try:
            return source(symbol)
        except Exception as exc:
            errors.append(f"{source.__name__}: {exc}")
    raise RuntimeError("all flow sources failed: " + " | ".join(errors))

def _normalize_date(value: str) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 8:
        raise ValueError(f"invalid date: {value!r}")
    return digits


def eastmoney_kline_range(symbol: str, start: str, end: str) -> dict:
    code, secid = symbol_for_public(symbol)
    beg = _normalize_date(start)
    fin = _normalize_date(end)
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}&klt=101&fqt=1&beg={beg}&end={fin}"
        "&fields1=f1,f2,f3,f4,f5,f6"
        "&fields2=f51,f52,f53,f54,f55,f56,f57"
    )
    payload = json.loads(_http_text(url, headers=EM_HEADERS))
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or not data.get("klines"):
        raise RuntimeError(f"Eastmoney returned no history for {symbol} {start}~{end}")
    bars = []
    for row in data["klines"]:
        parts = str(row).split(",")
        if len(parts) < 7:
            continue
        bars.append({
            "time": parts[0],
            "open": _as_float(parts[1]),
            "close": _as_float(parts[2]),
            "high": _as_float(parts[3]),
            "low": _as_float(parts[4]),
            "volume": _as_float(parts[5]) * 100.0,
            "amount": _as_float(parts[6]),
        })
    closes = [b["close"] for b in bars]
    return {
        "symbol": code,
        "name": str(data.get("name") or ""),
        "period": "day",
        "bars": bars,
        "ma5": simple_ma(closes, 5),
        "ma10": simple_ma(closes, 10),
        "macd": macd(closes),
        "pre_close": _as_float(data.get("preKPrice")),
        "source": "eastmoney",
    }


def fetch_history(symbol: str, start: str, end: str) -> dict:
    errors = []
    for source in (tencent_kline_range, eastmoney_kline_range):
        try:
            return source(symbol, start, end)
        except Exception as exc:
            errors.append(f"{source.__name__}: {exc}")
    try:
        # Sina only serves a recent window; useful as a best-effort fallback.
        data = sina_kline(symbol, period="day", limit=500)
        start_key = str(start)[:10]
        end_key = str(end)[:10]
        filtered = [b for b in data["bars"] if start_key <= b["time"][:10] <= end_key]
        if filtered:
            closes = [b["close"] for b in filtered]
            data = dict(data)
            data["bars"] = filtered
            data["ma5"] = simple_ma(closes, 5)
            data["ma10"] = simple_ma(closes, 10)
            data["macd"] = macd(closes)
            return data
        errors.append("sina: requested range outside recent window")
    except Exception as exc:
        errors.append(f"sina: {exc}")
    raise RuntimeError("all history sources failed: " + " | ".join(errors))

def tencent_kline_range(symbol: str, start: str, end: str) -> dict:
    prefixed, _ = symbol_for_public(symbol)
    beg = _normalize_date(start)
    fin = _normalize_date(end)
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={prefixed},day,{beg[:4]}-{beg[4:6]}-{beg[6:]},"
        f"{fin[:4]}-{fin[4:6]}-{fin[6:]},1000,qfq"
    )
    payload = json.loads(_http_text(url, headers=TX_HEADERS))
    data = (payload.get("data") or {}).get(prefixed) if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError(f"Tencent returned no history for {symbol} {start}~{end}")
    rows = data.get("qfqday") or data.get("day") or []
    bars = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            continue
        bars.append({
            "time": str(row[0]),
            "open": _as_float(row[1]),
            "close": _as_float(row[2]),
            "high": _as_float(row[3]),
            "low": _as_float(row[4]),
            "volume": _as_float(row[5]) * 100.0,
            "amount": round(_as_float(row[2]) * _as_float(row[5]) * 100.0, 2),
        })
    bars.sort(key=lambda x: x["time"])
    if not bars:
        raise RuntimeError(f"Tencent returned no usable bars for {symbol}")
    closes = [b["close"] for b in bars]
    return {
        "symbol": prefixed,
        "name": str((data.get("qt") or {}).get(prefixed, [None, ""])[1]
                    if isinstance(data.get("qt"), dict) else ""),
        "period": "day",
        "bars": bars,
        "ma5": simple_ma(closes, 5),
        "ma10": simple_ma(closes, 10),
        "macd": macd(closes),
        "pre_close": bars[-2]["close"] if len(bars) > 1 else 0.0,
        "source": "tencent",
    }

def sina_flow_history(symbol: str, date: str, days: int = 20) -> dict:
    """Historical daily flow up to ``date`` (Sina public data)."""
    rows = _sina_daily_flow(symbol, limit=5000)
    cutoff = str(date or "")[:10]
    rows = [row for row in rows if not cutoff or str(row.get("time", ""))[:10] <= cutoff]
    rows = rows[-max(5, min(int(days), 60)):]
    if not rows:
        raise RuntimeError(f"Sina returned no historical flow for {symbol} <= {date}")
    last5 = rows[-5:]
    five_day = {
        "main": round(sum(float(x.get("main") or 0) for x in last5), 2),
        "super": round(sum(float(x.get("super") or 0) for x in last5), 2),
        "large": None,
        "medium": None,
        "small": None,
    }
    return {
        "symbol": symbol_for_public(symbol)[0],
        "minute": [],
        "daily": rows,
        "today": rows[-1],
        "five_day": five_day,
        "source": "sina",
    }