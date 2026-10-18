"""Local backtest-run discovery and replay data.

The dashboard only reads files already produced by ``local_backtest``:

* ``equity.csv``: date, total_value, positions_value, cash, n_pos
* ``fills.csv``: date, code, side, price, amount, value, fee, cash_after, ...

No pandas dependency is needed, so the same backend can be vendored into the
DSH dashboard plugin.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Iterable

DEFAULT_CONFIG = Path.home() / ".ths_sim" / "dashboard.json"


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "--"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def display_code(code: Any) -> str:
    raw = str(code or "").strip()
    digits = re.sub(r"\D", "", raw)
    return digits[-6:] if len(digits) >= 6 else raw


def configured_root() -> Path | None:
    env = os.environ.get("THS_BACKTEST_ROOT")
    if env:
        p = Path(os.path.expandvars(os.path.expanduser(env)))
        if p.exists():
            return p
    try:
        cfg = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8-sig"))
        raw = cfg.get("backtest_root") if isinstance(cfg, dict) else None
        if raw:
            p = Path(os.path.expandvars(os.path.expanduser(str(raw))))
            if p.exists():
                return p
    except (OSError, ValueError):
        pass
    candidates = [
        Path.cwd() / "local_backtest" / "out",
        Path.cwd().parent / "local_backtest" / "out",
        Path.home() / "local_backtest" / "out",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return [dict(row) for row in csv.DictReader(f)]
    except OSError:
        return []


def _equity_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _read_csv(path):
        date = str(row.get("date") or "")[:10]
        if not date:
            continue
        rows.append({
            "date": date,
            "total_value": _as_float(row.get("total_value")),
            "positions_value": _as_float(row.get("positions_value")),
            "cash": _as_float(row.get("cash")),
            "n_pos": _as_int(row.get("n_pos")),
        })
    rows.sort(key=lambda x: x["date"])
    return rows


def _trade_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _read_csv(path):
        date = str(row.get("date") or "")[:10]
        if not date:
            continue
        rows.append({
            "date": date,
            "code": display_code(row.get("code")),
            "side": str(row.get("side") or "").lower(),
            "price": _as_float(row.get("price")),
            "quantity": _as_int(row.get("amount")),
            "value": _as_float(row.get("value")),
            "fee": _as_float(row.get("fee")),
            "cash_after": _as_float(row.get("cash_after")),
            "strategy": str(row.get("run") or ""),
        })
    rows.sort(key=lambda x: (x["date"], x["code"], x["side"]))
    return rows


def _metrics(equity: list[dict[str, Any]]) -> dict[str, Any]:
    if not equity:
        return {
            "start": "", "end": "", "initial": 0.0, "final": 0.0,
            "total_return": 0.0, "max_drawdown": 0.0, "sharpe": 0.0,
            "days": 0,
        }
    values = [float(x["total_value"]) for x in equity]
    initial = values[0]
    final = values[-1]
    peak = values[0]
    max_dd = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, value / peak - 1.0)
    returns = []
    for previous, current in zip(values, values[1:]):
        if previous > 0:
            returns.append(current / previous - 1.0)
    sharpe = 0.0
    if len(returns) >= 2:
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        std = math.sqrt(max(0.0, variance))
        if std > 0:
            sharpe = mean / std * math.sqrt(252.0)
    return {
        "start": equity[0]["date"],
        "end": equity[-1]["date"],
        "initial": round(initial, 2),
        "final": round(final, 2),
        "total_return": round(final / initial - 1.0, 6) if initial else 0.0,
        "max_drawdown": round(max_dd, 6),
        "sharpe": round(sharpe, 4),
        "days": len(equity),
    }


def _run_id_for(root: Path, equity_path: Path) -> str:
    parent = equity_path.parent
    try:
        rel = parent.relative_to(root)
        return str(rel).replace("\\", "/") or parent.name
    except ValueError:
        return parent.name


def list_backtests(root: str | Path | None = None, limit: int = 300) -> dict:
    root_path = Path(root) if root is not None else configured_root()
    if root_path is None or not root_path.exists():
        return {"ok": False, "error": "未配置回测目录", "runs": []}
    runs: list[dict[str, Any]] = []
    for equity_path in root_path.rglob("equity.csv"):
        if len(runs) >= max(1, int(limit)):
            break
        fills_path = equity_path.with_name("fills.csv")
        if not fills_path.exists():
            continue
        equity = _equity_rows(equity_path)
        if not equity:
            continue
        trades = _trade_rows(fills_path)
        metrics = _metrics(equity)
        run_id = _run_id_for(root_path, equity_path)
        strategy = next((x.get("strategy") for x in trades if x.get("strategy")), "")
        try:
            mtime = equity_path.stat().st_mtime
        except OSError:
            mtime = 0.0
        runs.append({
            "id": run_id,
            "name": equity_path.parent.name,
            "path": str(equity_path.parent),
            "strategy": strategy,
            "start": metrics["start"],
            "end": metrics["end"],
            "initial": metrics["initial"],
            "final": metrics["final"],
            "total_return": metrics["total_return"],
            "max_drawdown": metrics["max_drawdown"],
            "sharpe": metrics["sharpe"],
            "trades": len(trades),
            "days": metrics["days"],
            "mtime": mtime,
        })
    runs.sort(key=lambda x: (-float(x["mtime"]), x["name"].lower()))
    return {"ok": True, "root": str(root_path), "runs": runs}


def load_backtest(run_id: str, root: str | Path | None = None) -> dict:
    root_path = Path(root) if root is not None else configured_root()
    if root_path is None or not root_path.exists():
        raise ValueError("未配置回测目录")
    target = (root_path / str(run_id) / "equity.csv").resolve()
    try:
        target.relative_to(root_path.resolve())
    except ValueError as exc:
        raise ValueError("回测路径越界") from exc
    if not target.exists():
        raise ValueError(f"找不到回测: {run_id}")
    fills_path = target.with_name("fills.csv")
    if not fills_path.exists():
        raise ValueError(f"回测缺少 fills.csv: {run_id}")
    equity = _equity_rows(target)
    trades = _trade_rows(fills_path)
    if not equity:
        raise ValueError(f"回测 equity.csv 为空: {run_id}")
    return {
        "ok": True,
        "id": str(run_id),
        "name": target.parent.name,
        "root": str(root_path),
        "summary": _metrics(equity),
        "equity": equity,
        "trades": trades,
        "strategy": next((x.get("strategy") for x in trades if x.get("strategy")), ""),
        "as_of": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def positions_at(trades: Iterable[dict[str, Any]], as_of: str) -> list[dict[str, Any]]:
    """Reconstruct open positions using weighted-average cost."""
    cutoff = str(as_of)[:10]
    book: dict[str, dict[str, Any]] = {}
    for trade in trades:
        if str(trade.get("date", ""))[:10] > cutoff:
            continue
        code = display_code(trade.get("code"))
        side = str(trade.get("side") or "").lower()
        qty = _as_int(trade.get("quantity"))
        price = _as_float(trade.get("price"))
        fee = _as_float(trade.get("fee"))
        if qty <= 0 or price <= 0:
            continue
        row = book.setdefault(code, {
            "code": code, "quantity": 0, "avg_cost": 0.0,
            "last_price": price, "realized_pnl": 0.0,
        })
        row["last_price"] = price
        if side == "buy":
            old_qty = row["quantity"]
            new_qty = old_qty + qty
            row["avg_cost"] = ((old_qty * row["avg_cost"]) + (qty * price) + fee) / new_qty
            row["quantity"] = new_qty
        elif side == "sell":
            sold = min(qty, row["quantity"])
            row["realized_pnl"] += (price - row["avg_cost"]) * sold - fee
            row["quantity"] -= sold
            if row["quantity"] <= 0:
                book.pop(code, None)
    result = []
    for row in book.values():
        row["market_value"] = round(row["quantity"] * row["last_price"], 2)
        row["cost_value"] = round(row["quantity"] * row["avg_cost"], 2)
        row["unrealized_pnl"] = round(row["market_value"] - row["cost_value"], 2)
        result.append(row)
    result.sort(key=lambda x: x["code"])
    return result