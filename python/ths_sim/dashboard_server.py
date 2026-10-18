"""Local HTTP data service for the DSH THS dashboard panel.

The panel itself is a thin browser plugin.  This process owns the simulated
account client, the public market-data calls, caching, and JSON shaping.  It
binds to 127.0.0.1 only and never returns the session cookie or account id.

Run:
    python -m ths_sim.dashboard_server --port 8766
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from .client import ThsClient
from .config import ThsConfig
from .errors import ThsError
from .backtest_data import list_backtests, load_backtest
from .market_data import (
    fetch_flow,
    fetch_history,
    fetch_kline,
    now_text,
    sina_flow_history,
    tencent_quote,
    ths_quote,
)
from .models import normalize_symbol

DEFAULT_SYMBOL = "600519"


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def public_position(pos: Any) -> dict:
    row = pos.to_dict()
    row.pop("account_id", None)
    row["value"] = round(float(getattr(pos, "value", 0.0)), 2)
    cost = float(getattr(pos, "cost_price", 0.0) or 0.0)
    last = float(getattr(pos, "last_price", 0.0) or 0.0)
    row["market_price"] = last
    row["pnl_pct"] = (round((last / cost - 1.0) * 100.0, 2)
                      if cost > 0 and last > 0 else float(row.get("pnl_ratio", 0.0) or 0.0))
    return row


class DataService:
    def __init__(self) -> None:
        self._client: ThsClient | None = None
        self._client_lock = threading.Lock()
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_lock = threading.Lock()

    def client(self) -> ThsClient:
        with self._client_lock:
            if self._client is None:
                self._client = ThsClient(ThsConfig.load())
            return self._client

    def _cached(self, key: str, ttl: float,
                fn: Callable[[], Any]) -> Any:
        now = time.monotonic()
        with self._cache_lock:
            hit = self._cache.get(key)
            if hit is not None and now - hit[0] <= ttl:
                return hit[1]
        value = fn()
        with self._cache_lock:
            self._cache[key] = (time.monotonic(), value)
        return value

    def account_snapshot(self) -> dict:
        def load() -> dict:
            client = self.client()
            account = client.get_account()
            positions = client.get_positions()
            rows = [public_position(p) for p in positions]
            market_value = sum(float(r.get("value", 0.0) or 0.0) for r in rows)
            return {
                "available_cash": round(account.available_cash, 2),
                "total_assets": round(account.total_assets or
                                      (account.available_cash + market_value), 2),
                "market_value": round(account.market_value or market_value, 2),
                "positions": rows,
                "position_count": len(rows),
                "as_of": now_text(),
            }
        return self._cached("account", 3.0, load)

    def quote(self, symbol: str) -> dict:
        key = f"quote:{symbol}"

        def load() -> dict:
            try:
                data = ths_quote(self.client(), symbol)
            except Exception as first:
                data = tencent_quote(symbol)
                data["fallback_reason"] = str(first)
            if not data.get("name"):
                try:
                    public = tencent_quote(symbol)
                    for field in ("name", "pre_close", "open", "high", "low",
                                  "change", "change_pct", "volume", "amount"):
                        if field not in data or data.get(field) in (None, "", 0):
                            data[field] = public.get(field)
                except Exception:
                    pass
            return data
        return self._cached(key, 3.0, load)

    def chart(self, symbol: str, period: str) -> dict:
        key = f"kline:{symbol}:{period}"

        def load() -> dict:
            return fetch_kline(symbol, period=period, limit=240)
        return self._cached(key, 10.0, load)

    def daily_chart(self, symbol: str) -> dict:
        key = f"kline:{symbol}:day"

        def load() -> dict:
            return fetch_kline(symbol, period="day", limit=120)
        return self._cached(key, 20.0, load)

    def flow(self, symbol: str) -> dict:
        key = f"flow:{symbol}"

        def load() -> dict:
            return fetch_flow(symbol)
        return self._cached(key, 12.0, load)

    def overview(self, symbol: str | None, period: str = "5") -> dict:
        period = str(period or "5").lower()
        if period not in ("1", "5", "15", "30", "60"):
            period = "5"
        try:
            account = self.account_snapshot()
        except Exception as exc:
            account = {
                "available_cash": 0.0,
                "total_assets": 0.0,
                "market_value": 0.0,
                "positions": [],
                "position_count": 0,
                "error": str(exc),
            }
        if symbol:
            symbol = normalize_symbol(symbol)
        elif account.get("positions"):
            symbol = normalize_symbol(account["positions"][0]["symbol"])
        else:
            symbol = DEFAULT_SYMBOL

        errors: dict[str, str] = {}
        with cf.ThreadPoolExecutor(max_workers=4) as pool:
            future_quote = pool.submit(self.quote, symbol)
            future_chart = pool.submit(self.chart, symbol, period)
            future_daily = pool.submit(self.daily_chart, symbol)
            future_flow = pool.submit(self.flow, symbol)
            quote = self._future(future_quote, "quote", errors)
            chart = self._future(future_chart, "chart", errors)
            daily = self._future(future_daily, "daily", errors)
            flow = self._future(future_flow, "flow", errors)

        if chart is not None and not chart.get("name") and quote:
            chart["name"] = quote.get("name") or ""
        if daily is not None and not daily.get("name") and quote:
            daily["name"] = quote.get("name") or ""
        held = next((p for p in account.get("positions", [])
                     if p.get("symbol") == symbol), None)
        return {
            "ok": True,
            "as_of": now_text(),
            "symbol": symbol,
            "period": period,
            "account": account,
            "held": held,
            "quote": quote,
            "chart": chart,
            "daily": daily,
            "flow": flow,
            "errors": errors,
        }

    @staticmethod
    def _future(future, name: str, errors: dict[str, str]):
        try:
            return future.result()
        except Exception as exc:
            errors[name] = str(exc)
            return None

    def backtests(self) -> dict:
        return self._cached("backtests", 30.0, lambda: list_backtests(limit=300))

    def backtest(self, run_id: str) -> dict:
        return self._cached(f"backtest:{run_id}", 60.0,
                            lambda: load_backtest(run_id))

    def history(self, symbol: str, start: str, end: str) -> dict:
        return self._cached(f"history:{symbol}:{start}:{end}", 60.0,
                            lambda: fetch_history(symbol, start, end))

    def backtest_flow(self, symbol: str, date: str) -> dict:
        return self._cached(f"backtest_flow:{symbol}:{date}", 60.0,
                            lambda: sina_flow_history(symbol, date))
    def health(self) -> dict:
        return {
            "ok": True,
            "service": "ths_sim.dashboard",
            "time": now_text(),
            "pid": __import__("os").getpid(),
        }

SERVICE = DataService()


class Handler(BaseHTTPRequestHandler):
    server_version = "ThsDashboard/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep the console quiet; errors are returned as JSON.  Never log the
        # Cookie because this server never receives it from the browser.
        if getattr(self, "_log_errors", False):
            sys.stderr.write("[ths-dashboard] " + (fmt % args) + "\n")

    def _send(self, status: int, payload: Any) -> None:
        body = json.dumps(_jsonable(payload), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, {})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
        try:
            if parsed.path == "/api/health":
                self._send(200, SERVICE.health())
                return
            if parsed.path == "/api/account":
                self._send(200, {"ok": True, **SERVICE.account_snapshot()})
                return
            if parsed.path == "/api/quote":
                symbol = normalize_symbol(query.get("symbol", DEFAULT_SYMBOL))
                self._send(200, {"ok": True, **SERVICE.quote(symbol)})
                return
            if parsed.path == "/api/kline":
                symbol = normalize_symbol(query.get("symbol", DEFAULT_SYMBOL))
                period = query.get("period", "5")
                self._send(200, {"ok": True, **SERVICE.chart(symbol, period)})
                return
            if parsed.path == "/api/daily":
                symbol = normalize_symbol(query.get("symbol", DEFAULT_SYMBOL))
                self._send(200, {"ok": True, **SERVICE.daily_chart(symbol)})
                return
            if parsed.path == "/api/flow":
                symbol = normalize_symbol(query.get("symbol", DEFAULT_SYMBOL))
                self._send(200, {"ok": True, **SERVICE.flow(symbol)})
                return
            if parsed.path == "/api/overview":
                payload = SERVICE.overview(query.get("symbol"), query.get("period", "5"))
                self._send(200 if payload.get("ok") else 503, payload)
                return
            if parsed.path == "/api/backtests":
                payload = SERVICE.backtests()
                self._send(200 if payload.get("ok") else 503, payload)
                return
            if parsed.path == "/api/backtest":
                run_id = query.get("run", "").strip()
                if not run_id:
                    self._send(400, {"ok": False, "error": "run is required"})
                    return
                self._send(200, SERVICE.backtest(run_id))
                return
            if parsed.path == "/api/history":
                symbol = normalize_symbol(query.get("symbol", DEFAULT_SYMBOL))
                start = query.get("start", "")
                end = query.get("end", "")
                if not start or not end:
                    self._send(400, {"ok": False, "error": "start and end are required"})
                    return
                self._send(200, {"ok": True, **SERVICE.history(symbol, start, end)})
                return
            if parsed.path == "/api/backtest_flow":
                symbol = normalize_symbol(query.get("symbol", DEFAULT_SYMBOL))
                date = query.get("date", "")
                if not date:
                    self._send(400, {"ok": False, "error": "date is required"})
                    return
                self._send(200, {"ok": True, **SERVICE.backtest_flow(symbol, date)})
                return
            self._send(404, {"ok": False, "error": "not found"})
        except (ValueError, ThsError, RuntimeError) as exc:
            self._send(503, {"ok": False, "error": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            traceback.print_exc()
            self._send(500, {"ok": False, "error": str(exc)})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="THS dashboard local data service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args(argv)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"THS dashboard data service: http://{args.host}:{args.port}/api/health",
          flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())