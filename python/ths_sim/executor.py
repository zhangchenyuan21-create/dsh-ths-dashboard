"""Planning and execution helpers for paper-account rebalancing.

The executor deliberately separates planning from submission.  A caller can
print/inspect a plan, then explicitly execute it.  Sells are submitted before
buys, and buys are trimmed to the cash actually available at submission time.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

from .client import ThsClient
from .config import ThsConfig
from .errors import ThsError, ThsOrderStateUnknown, ThsValidationError
from .models import (
    PlannedOrder,
    Position,
    RebalancePlan,
    normalize_side,
    normalize_symbol,
    positions_by_symbol,
    round_buy_quantity,
    round_price,
    round_sell_quantity,
)

TICK = 0.01
EPS = 1e-9


def estimate_fee(side: str, value: float, config: ThsConfig) -> float:
    side = normalize_side(side)
    value = max(0.0, float(value))
    commission = max(config.min_commission, value * config.commission_rate)
    stamp = value * config.stamp_duty if side == "sell" else 0.0
    transfer = value * config.transfer_fee
    return round(commission + stamp + transfer, 2)


def estimated_buy_cost(price: float, quantity: int, config: ThsConfig) -> float:
    value = float(price) * int(quantity)
    return round(value + estimate_fee("buy", value, config), 2)


def affordable_buy_quantity(cash: float, price: float,
                            config: ThsConfig) -> int:
    cash = max(0.0, float(cash))
    price = float(price)
    if price <= 0:
        return 0
    qty = int(cash // (price * (1 + config.commission_rate + config.transfer_fee))
              // 100 * 100)
    qty = max(0, qty)
    while qty >= 100 and estimated_buy_cost(price, qty, config) > cash + EPS:
        qty -= 100
    return qty


def load_targets(path: str | Path) -> tuple[dict[str, float], float | None]:
    """Load target weights from a JSON or CSV file.

    JSON:
      {"cash_reserve": 0.05, "targets": [{"symbol": "600000", "weight": 0.1}]}
    CSV:
      symbol,weight
      600000,0.1
    """
    p = Path(path)
    if not p.exists():
        raise ThsValidationError(f"targets file not found: {p}")
    cash_reserve: float | None = None
    rows: list[Mapping[str, Any]]
    if p.suffix.lower() == ".json":
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ThsValidationError(f"cannot read targets JSON: {exc}") from exc
        if isinstance(data, Mapping):
            raw_targets = data.get("targets")
            if "cash_reserve" in data:
                cash_reserve = float(data["cash_reserve"])
            if raw_targets is None:
                raise ThsValidationError("targets JSON must contain 'targets'")
            rows = raw_targets
        elif isinstance(data, list):
            rows = data
        else:
            raise ThsValidationError("targets JSON must be a list or object")
    elif p.suffix.lower() in (".csv", ".txt"):
        try:
            with p.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
        except OSError as exc:
            raise ThsValidationError(f"cannot read targets CSV: {exc}") from exc
    else:
        raise ThsValidationError("targets file must be .json or .csv")

    targets: dict[str, float] = {}
    for row in rows:
        if isinstance(row, Mapping):
            raw_symbol = row.get("symbol", row.get("code", row.get("代码")))
            raw_weight = row.get("weight", row.get("权重"))
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            raw_symbol, raw_weight = row[0], row[1]
        else:
            raise ThsValidationError(f"invalid target row: {row!r}")
        symbol = normalize_symbol(raw_symbol)
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError) as exc:
            raise ThsValidationError(
                f"invalid weight for {symbol}: {raw_weight!r}") from exc
        if not (0 <= weight <= 1):
            raise ThsValidationError(f"weight for {symbol} must be in [0, 1]")
        if symbol in targets:
            raise ThsValidationError(f"duplicate target symbol: {symbol}")
        targets[symbol] = weight
    total = sum(targets.values())
    if total > 1 + 1e-9:
        raise ThsValidationError(f"target weights sum to {total:.4f} (> 1)")
    return targets, cash_reserve


def _fallback_price(position: Position, quote: Any) -> float:
    if quote is not None and quote.last_price > 0:
        return float(quote.last_price)
    return float(position.last_price or 0.0)


def _max_order_trim(quantity: int, price: float,
                    max_order_value: float | None) -> tuple[int, str | None]:
    if max_order_value is None or max_order_value <= 0:
        return quantity, None
    if quantity * price <= max_order_value + EPS:
        return quantity, None
    q = int(max_order_value // price // 100 * 100)
    if q < 100:
        return 0, f"order value exceeds max_order_value={max_order_value}"
    return q, (
        f"trimmed to {q} shares to respect max_order_value={max_order_value}"
    )


def build_rebalance_plan(
    client: ThsClient,
    targets: Mapping[str, float],
    *,
    cash_reserve: float = 0.05,
    aggressive_ticks: int = 1,
    max_order_value: float | None = None,
    max_turnover: float | None = None,
) -> RebalancePlan:
    """Build a target-weight rebalance plan without placing any order."""
    if not (0 <= cash_reserve < 1):
        raise ThsValidationError("cash_reserve must be in [0, 1)")
    normalized: dict[str, float] = {}
    for raw_symbol, raw_weight in targets.items():
        symbol = normalize_symbol(raw_symbol)
        weight = float(raw_weight)
        if not (0 <= weight <= 1):
            raise ThsValidationError(f"weight for {symbol} must be in [0, 1]")
        normalized[symbol] = weight
    if sum(normalized.values()) + cash_reserve > 1 + 1e-7:
        raise ThsValidationError(
            f"targets ({sum(normalized.values()):.4f}) + cash_reserve "
            f"({cash_reserve:.4f}) must not exceed 1")

    account = client.get_account()
    positions = client.get_positions()
    held = positions_by_symbol(positions)
    symbols = sorted(set(normalized) | set(held))
    quotes: dict[str, Any] = {}
    warnings: list[str] = []
    for symbol in symbols:
        try:
            quotes[symbol] = client.query_quote(symbol, side="buy")
        except Exception as exc:
            quotes[symbol] = None
            warnings.append(f"quote unavailable for {symbol}: {exc}")

    positions_value = 0.0
    for symbol, pos in held.items():
        px = _fallback_price(pos, quotes.get(symbol))
        if px > 0:
            positions_value += pos.quantity * px
        else:
            warnings.append(f"no valuation price for {symbol}")
    equity = account.total_assets if account.total_assets > 0 else (
        account.available_cash + positions_value)
    equity_source = "account.total_assets" if account.total_assets > 0 \
        else "cash+position_marks"
    reserve_value = equity * cash_reserve

    sells: list[PlannedOrder] = []
    buys: list[PlannedOrder] = []
    expected_sell_proceeds = 0.0

    # Sells first, so the plan's budget can include expected proceeds.  The
    # execution step still re-reads cash before every buy.
    for symbol, pos in sorted(held.items()):
        quote = quotes.get(symbol)
        px = _fallback_price(pos, quote)
        weight = normalized.get(symbol, 0.0)
        desired = 0
        if weight > 0 and px > 0:
            desired = int((equity * weight) // px // 100 * 100)
        current = int(pos.quantity)
        available = int(pos.available)
        delta = current - desired
        if delta <= 0:
            continue
        if available <= 0:
            warnings.append(
                f"{symbol}: {current} shares held but none are sellable "
                "(T+1 lock or broker restriction)")
            continue
        sellable = min(delta, available)
        full_liq = (desired == 0 and sellable == available == current)
        qty = round_sell_quantity(
            sellable, full_liquidation=full_liq, available=available)
        if qty <= 0:
            warnings.append(
                f"{symbol}: sell delta {sellable} is an odd lot; only a full "
                "liquidation may sell an odd lot")
            continue
        if quote is None:
            warnings.append(
                f"{symbol}: sell skipped because no quote is available")
            continue
        limit = quote.bid1 if quote.bid1 > 0 else max(
            TICK, px - TICK * max(1, int(aggressive_ticks)))
        limit = round_price(limit)
        qty, trim_note = _max_order_trim(qty, limit, max_order_value)
        if trim_note:
            warnings.append(f"{symbol}: {trim_note}")
        if qty <= 0:
            continue
        value = round(qty * limit, 2)
        expected_sell_proceeds += max(0.0, value - estimate_fee("sell", value, client.config))
        sells.append(PlannedOrder(
            symbol=symbol, side="sell", quantity=qty,
            reference_price=px, limit_price=limit,
            estimated_value=value,
            reason="target underweight/close" if weight == 0 else "rebalance sell",
            locked_quantity=max(0, current - available),
        ))

    # Buy candidates are ranked by target weight so limited cash goes to the
    # highest-conviction targets first.
    budget = max(0.0, account.available_cash - reserve_value) + expected_sell_proceeds
    candidates: list[dict[str, Any]] = []
    for symbol, weight in normalized.items():
        if weight <= 0:
            continue
        quote = quotes.get(symbol)
        pos = held.get(symbol)
        px = quote.last_price if quote is not None else (
            pos.last_price if pos is not None else 0.0)
        if px <= 0:
            warnings.append(f"{symbol}: buy skipped because no valid price")
            continue
        desired = int((equity * weight) // px // 100 * 100)
        current = int(pos.quantity) if pos is not None else 0
        delta = desired - current
        qty = round_buy_quantity(delta)
        if qty < 100:
            continue
        if quote is None:
            warnings.append(f"{symbol}: buy skipped because no quote is available")
            continue
        limit = quote.ask1 if quote.ask1 > 0 else px + TICK * max(1, int(aggressive_ticks))
        limit = round_price(limit)
        candidates.append({
            "symbol": symbol, "weight": weight, "qty": qty,
            "reference": px, "limit": limit,
        })

    for candidate in sorted(candidates, key=lambda x: (-x["weight"], x["symbol"])):
        symbol = candidate["symbol"]
        qty = int(candidate["qty"])
        limit = float(candidate["limit"])
        qty, trim_note = _max_order_trim(qty, limit, max_order_value)
        if trim_note:
            warnings.append(f"{symbol}: {trim_note}")
        if qty < 100:
            continue
        cost = estimated_buy_cost(limit, qty, client.config)
        if cost > budget + EPS:
            qty = affordable_buy_quantity(budget, limit, client.config)
            qty = min(qty, int(candidate["qty"]))
            if qty < 100:
                warnings.append(
                    f"{symbol}: buy skipped; insufficient planned cash "
                    f"(need {cost:.2f}, budget {budget:.2f})")
                continue
            cost = estimated_buy_cost(limit, qty, client.config)
            warnings.append(
                f"{symbol}: buy trimmed to {qty} shares by available budget")
        if cost > budget + EPS:
            continue
        budget -= cost
        buys.append(PlannedOrder(
            symbol=symbol, side="buy", quantity=qty,
            reference_price=float(candidate["reference"]),
            limit_price=limit,
            estimated_value=round(qty * limit, 2),
            reason=f"target weight {candidate['weight']:.4%}",
        ))

    if max_turnover is not None and max_turnover > 0:
        while buys and sum(x.estimated_value for x in (*sells, *buys)) > max_turnover + EPS:
            removed = buys.pop()
            warnings.append(
                f"{removed.symbol}: buy removed to respect "
                f"max_turnover={max_turnover:.2f}")
        if sum(x.estimated_value for x in (*sells, *buys)) > max_turnover + EPS:
            warnings.append(
                "sell turnover alone exceeds max_turnover; sells are retained "
                "to avoid leaving unintended exposure")

    return RebalancePlan(
        as_of=dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        equity=round(equity, 2),
        available_cash=round(account.available_cash, 2),
        cash_reserve=round(reserve_value, 2),
        sells=sells,
        buys=buys,
        warnings=warnings,
        targets=[{"symbol": s, "weight": w}
                 for s, w in sorted(normalized.items())],
        equity_source=equity_source,
    )


def execute_rebalance(
    client: ThsClient,
    plan: RebalancePlan,
    *,
    wait_seconds: float = 0.0,
    poll_interval: float = 2.0,
    abort_on_sell_failure: bool = True,
) -> dict:
    """Submit a plan: sells first, optional wait, then cash-trimmed buys."""
    if wait_seconds < 0:
        raise ThsValidationError("wait_seconds must be >= 0")
    result: dict[str, Any] = {
        "as_of": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "sells": [],
        "buys": [],
        "errors": [],
        "warnings": list(plan.warnings),
        "aborted": False,
        "waited_seconds": 0.0,
    }

    for planned in plan.sells:
        try:
            submitted = client.place_order(
                planned.symbol, planned.side, planned.quantity,
                price=planned.limit_price, dry_run=False)
            result["sells"].append(submitted.to_dict())
        except Exception as exc:
            result["errors"].append({
                "symbol": planned.symbol, "side": planned.side,
                "quantity": planned.quantity,
                "error": type(exc).__name__, "message": str(exc),
            })
            if abort_on_sell_failure:
                result["aborted"] = True
                result["warnings"].append(
                    "buy phase aborted because a sell failed or is in an "
                    "unknown state; reconcile before retrying")
                return result

    if plan.buys and wait_seconds > 0:
        started = time.monotonic()
        deadline = started + wait_seconds
        target_cash = sum(x.estimated_value for x in plan.buys)
        while True:
            try:
                account = client.get_account()
                if account.available_cash >= target_cash - EPS:
                    break
            except Exception as exc:
                result["warnings"].append(f"cash poll failed: {exc}")
            if time.monotonic() >= deadline:
                break
            time.sleep(min(max(0.1, poll_interval), max(0.0, deadline - time.monotonic())))
        result["waited_seconds"] = round(time.monotonic() - started, 1)

    if plan.buys:
        try:
            available_cash = client.get_account().available_cash
        except Exception as exc:
            result["errors"].append({
                "side": "buy", "error": type(exc).__name__,
                "message": f"cannot read cash before buy phase: {exc}",
            })
            result["aborted"] = True
            return result
        for planned in plan.buys:
            qty = planned.quantity
            max_qty = affordable_buy_quantity(
                available_cash, planned.limit_price, client.config)
            qty = min(qty, max_qty)
            if qty < 100:
                result["warnings"].append(
                    f"{planned.symbol}: buy skipped; cash available "
                    f"{available_cash:.2f} is insufficient")
                continue
            try:
                submitted = client.place_order(
                    planned.symbol, planned.side, qty,
                    price=planned.limit_price, dry_run=False)
                result["buys"].append(submitted.to_dict())
                spent = submitted.intent.amount_value + estimate_fee(
                    "buy", submitted.intent.amount_value, client.config)
                available_cash = max(0.0, available_cash - spent)
            except Exception as exc:
                result["errors"].append({
                    "symbol": planned.symbol, "side": planned.side,
                    "quantity": qty,
                    "error": type(exc).__name__, "message": str(exc),
                })
    result["submitted_orders"] = len(result["sells"]) + len(result["buys"])
    return result


ORDER_COLUMN_ALIASES = {
    "symbol": ("symbol", "code", "stock_code", "股票代码", "代码"),
    "side": ("side", "action", "方向", "买卖"),
    "quantity": ("quantity", "amount", "qty", "数量", "股数"),
    "price": ("price", "价格", "委托价"),
    "client_order_id": ("client_order_id", "order_id", "id", "订单号"),
}


def _normalized_row(row: Mapping[str, Any]) -> dict[str, Any]:
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    out: dict[str, Any] = {}
    for field, aliases in ORDER_COLUMN_ALIASES.items():
        for alias in aliases:
            key = alias.lower()
            if key in lowered and lowered[key] not in (None, ""):
                out[field] = lowered[key]
                break
    return out


def load_orders_csv(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise ThsValidationError(f"orders file not found: {p}")
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ThsValidationError("orders CSV is empty")
    parsed: list[dict[str, Any]] = []
    for i, row in enumerate(rows, start=2):
        normalized = _normalized_row(row)
        missing = [k for k in ("symbol", "side", "quantity") if k not in normalized]
        if missing:
            raise ThsValidationError(
                f"orders CSV line {i}: missing columns {', '.join(missing)}")
        try:
            symbol = normalize_symbol(normalized["symbol"])
            side = normalize_side(normalized["side"])
            qty = int(float(normalized["quantity"]))
            price = (float(normalized["price"])
                     if normalized.get("price") not in (None, "") else None)
        except (TypeError, ValueError) as exc:
            raise ThsValidationError(f"orders CSV line {i}: {exc}") from exc
        if qty <= 0:
            raise ThsValidationError(f"orders CSV line {i}: quantity must be positive")
        parsed.append({
            "symbol": symbol, "side": side, "quantity": qty, "price": price,
            "client_order_id": normalized.get("client_order_id"),
        })
    return parsed


def submit_orders(
    client: ThsClient,
    orders: Iterable[Mapping[str, Any]],
    *,
    live: bool = False,
    continue_on_error: bool = False,
) -> dict:
    orders = list(orders)
    output: dict[str, Any] = {
        "live": bool(live),
        "planned": len(orders),
        "submitted": [],
        "errors": [],
    }
    for order in orders:
        try:
            result = client.place_order(
                order["symbol"], order["side"], int(order["quantity"]),
                price=order.get("price"),
                client_order_id=order.get("client_order_id"),
                dry_run=not live,
            )
            output["submitted"].append(result.to_dict())
        except Exception as exc:
            output["errors"].append({
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "quantity": order.get("quantity"),
                "error": type(exc).__name__,
                "message": str(exc),
            })
            if not continue_on_error:
                break
    return output