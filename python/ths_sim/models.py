"""Small, serialisable domain models for the Tonghuashun adapter."""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


def normalize_symbol(value: Any) -> str:
    """Return a six-digit A-share code from common code formats.

    Accepts ``600519``, ``sh600519``, ``SH.600519``, ``600519.XSHG`` and
    ``sz000001``.  Rejecting unknown formats here prevents a typo from being
    sent to the broker.
    """
    if value is None:
        raise ValueError("empty stock code")
    s = str(value).strip().upper()
    if s.endswith(".XSHG") or s.endswith(".XSHE") or s.endswith(".BJSE"):
        s = s.split(".", 1)[0]
    elif s.startswith(("SH.", "SZ.", "BJ.")):
        s = s.split(".", 1)[1]
    elif len(s) == 8 and s[:2] in ("SH", "SZ", "BJ"):
        s = s[2:]
    if not (len(s) == 6 and s.isdigit()):
        raise ValueError(f"invalid A-share stock code: {value!r}")
    return s


def normalize_side(value: Any) -> str:
    s = str(value or "").strip().lower()
    if s in ("buy", "b", "买", "买入", "cmd_wt_mairu"):
        return "buy"
    if s in ("sell", "s", "卖", "卖出", "cmd_wt_maichu"):
        return "sell"
    raise ValueError(f"invalid order side: {value!r}")


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "").replace("，", "")
    if s in ("", "-", "--", "None", "null", "N/A", "nan"):
        return default
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int | None = None) -> int | None:
    f = as_float(value, None)
    if f is None:
        return default
    return int(f)


def _clean_side(raw: Any) -> str:
    try:
        return normalize_side(raw)
    except ValueError:
        return str(raw or "").strip().lower()


def _round_price(value: float) -> float:
    # A-share tick is 0.01 yuan.  round() alone is subject to binary float
    # surprises, so add a tiny epsilon before the final round.
    return round(float(value) + 1e-9, 2)


@dataclass(frozen=True)
class Quote:
    symbol: str
    last_price: float
    can_buy: int
    market_code: str
    bid1: float = 0.0
    ask1: float = 0.0
    bids: tuple[tuple[float, int], ...] = field(default_factory=tuple)
    asks: tuple[tuple[float, int], ...] = field(default_factory=tuple)

    @property
    def stock_code(self) -> str:
        return self.symbol

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["bids"] = [list(x) for x in self.bids]
        d["asks"] = [list(x) for x in self.asks]
        return d


@dataclass(frozen=True)
class Account:
    available_cash: float
    total_assets: float = 0.0
    market_value: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def kyje(self) -> float:
        return self.available_cash

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("raw", None)
        return d


@dataclass(frozen=True)
class Position:
    symbol: str
    name: str
    balance: int
    available: int
    amount: int
    last_price: float
    pnl: float = 0.0
    pnl_ratio: float = 0.0
    market_type: str = ""
    account_id: str = ""
    market_code: str = ""
    cost_price: float = 0.0
    market_value: float = 0.0
    frozen: int = 0
    currency: str = ""

    @property
    def stockcode(self) -> str:
        return self.symbol

    @property
    def stockname(self) -> str:
        return self.name

    @property
    def quantity(self) -> int:
        return self.balance if self.balance else self.amount

    @property
    def value(self) -> float:
        if self.market_value:
            return self.market_value
        return self.quantity * self.last_price

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Order:
    time: str
    order_id: str
    order_date: str
    symbol: str
    name: str
    price: float
    quantity: int
    side: str
    status: str
    market_type: str = ""

    @property
    def htbh(self) -> str:
        return self.order_id

    @property
    def wtrq(self) -> str:
        return self.order_date

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OrderIntent:
    client_order_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    amount_value: float
    account_id: str
    created_at: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OrderResult:
    intent: OrderIntent
    accepted: bool
    dry_run: bool = False
    broker_code: str = ""
    message: str = ""
    broker_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


@dataclass(frozen=True)
class CancelResult:
    order_id: str
    order_date: str
    accepted: bool
    dry_run: bool = False
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlannedOrder:
    symbol: str
    side: str
    quantity: int
    reference_price: float
    limit_price: float
    estimated_value: float
    reason: str = ""
    locked_quantity: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RebalancePlan:
    as_of: str
    equity: float
    available_cash: float
    cash_reserve: float
    sells: list[PlannedOrder] = field(default_factory=list)
    buys: list[PlannedOrder] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    targets: list[dict[str, Any]] = field(default_factory=list)
    equity_source: str = "cash+positions"

    @property
    def estimated_turnover(self) -> float:
        return sum(x.estimated_value for x in (*self.sells, *self.buys))

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "equity": self.equity,
            "available_cash": self.available_cash,
            "cash_reserve": self.cash_reserve,
            "equity_source": self.equity_source,
            "estimated_turnover": self.estimated_turnover,
            "sells": [x.to_dict() for x in self.sells],
            "buys": [x.to_dict() for x in self.buys],
            "warnings": list(self.warnings),
            "targets": list(self.targets),
        }


def positions_by_symbol(positions: Iterable[Position]) -> dict[str, Position]:
    """Aggregate duplicate rows defensively."""
    out: dict[str, Position] = {}
    for p in positions:
        old = out.get(p.symbol)
        if old is None:
            out[p.symbol] = p
            continue
        out[p.symbol] = Position(
            symbol=p.symbol,
            name=p.name or old.name,
            balance=old.balance + p.balance,
            available=old.available + p.available,
            amount=old.amount + p.amount,
            last_price=p.last_price or old.last_price,
            pnl=old.pnl + p.pnl,
            pnl_ratio=p.pnl_ratio or old.pnl_ratio,
            market_type=p.market_type or old.market_type,
            account_id=p.account_id or old.account_id,
            market_code=p.market_code or old.market_code,
            cost_price=p.cost_price or old.cost_price,
            market_value=(old.market_value + p.market_value),
            frozen=old.frozen + p.frozen,
            currency=p.currency or old.currency,
        )
    return out


def round_buy_quantity(quantity: int) -> int:
    return max(0, int(quantity) // 100 * 100)


def round_sell_quantity(quantity: int, *, full_liquidation: bool,
                        available: int) -> int:
    """A-share sell quantity rule.

    Partial sells must be whole lots.  An odd-lot may only be sold when the
    entire remaining position is being liquidated.
    """
    q = max(0, int(quantity))
    if full_liquidation and q == int(available):
        return q
    return q // 100 * 100


def round_price(value: float) -> float:
    return _round_price(value)