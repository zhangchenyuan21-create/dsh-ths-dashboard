"""Tonghuashun simulated-trading HTTP client.

This is an independent, safer implementation of the endpoints documented by
https://github.com/Cfu4536/ths_simulated_API.  The upstream repository hard-codes
a cookie and prints errors; this module instead:

* loads credentials from env/config;
* never logs the cookie;
* retries only read-only queries;
* journals every order intent before submission;
* distinguishes explicit rejection from an unknown submission state;
* enforces board-lot, T+1 availability, and odd-lot sell rules.

The API is a reverse-engineered web interface and may change without notice.
Only use it against a simulated account (mncg.10jqka.com.cn).

Safety default: every write helper (place_order/cancel/cancel_all) defaults to
``dry_run=True``.  Pass ``dry_run=False`` explicitly to submit.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import time
import uuid
from typing import Any, Callable, Mapping
from urllib.parse import urlencode

from .config import ThsConfig
from .errors import (
    ThsApiError,
    ThsHttpError,
    ThsOrderRejected,
    ThsOrderStateUnknown,
    ThsTransportError,
    ThsValidationError,
)
from .journal import OrderJournal
from .models import (
    Account,
    CancelResult,
    Order,
    OrderIntent,
    OrderResult,
    Position,
    Quote,
    as_float,
    as_int,
    normalize_side,
    normalize_symbol,
    round_buy_quantity,
    round_price,
    round_sell_quantity,
)
from .transport import HttpResponse, UrllibTransport


QUOTE_FIELDS = {
    "price": ("st_price", "cur_price", "price", "last", "last_price"),
    "can_buy": ("canbuy", "can_buy", "kymr", "ksl"),
    "market_code": ("mkcode", "mktcode", "market_code"),
}


def _dig(obj: Any, *keys: str, default: Any = None) -> Any:
    cur = obj
    for key in keys:
        if not isinstance(cur, Mapping) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _first(mapping: Mapping, keys: tuple[str, ...], default=None):
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def _first_float(mapping: Mapping, keys: tuple[str, ...],
                 default: float | None = None) -> float | None:
    return as_float(_first(mapping, keys, None), default)


def market_code_for_symbol(symbol: str) -> str:
    symbol = normalize_symbol(symbol)
    if symbol.startswith("6"):
        return "2"   # Shanghai A
    if symbol.startswith(("0", "3")):
        return "1"   # Shenzhen A
    if symbol.startswith(("4", "8")):
        return ":"   # Beijing A
    return ""


class ThsClient:
    """Client for the Tonghuashun simulated-trading web API."""

    BUY_PATH = "/cgiwt/delegate/tradestock/"
    SELL_PATH = "/cgiwt/delegate/tradestock/"
    CANCEL_PATH = "/cgiwt/delegate/cancelDelegated/"
    ORDERS_PATH = "/cgiwt/delegate/updateclass/"
    POSITIONS_PATH = "/cgiwt/delegate/updateclass"
    QUOTE_PATH = "/cgiwt/delegate/qrystock/"
    BUY_DIV_PATH = "/cgiwt/stock/buydiv/"

    def __init__(self, config: ThsConfig, *,
                 transport: Any | None = None,
                 journal: OrderJournal | None = None,
                 sleep_fn: Callable[[float], None] = time.sleep) -> None:
        self.config = config
        self.transport = transport or UrllibTransport()
        self.journal = journal or OrderJournal(config.journal_path)
        self._sleep = sleep_fn
        self._shareholder_accounts = dict(config.shareholder_accounts)

    # ------------------------------------------------------------------
    # HTTP plumbing
    # ------------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {
            "Host": self.config.base_url.split("://", 1)[-1],
            "Origin": self.config.origin,
            "Referer": self.config.referer,
            "Cookie": self.config.cookie,
            "User-Agent": self.config.user_agent,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }

    def _url(self, path: str) -> str:
        return self.config.base_url.rstrip("/") + path

    def _decode_json(self, response: HttpResponse) -> dict:
        raw = response.body or b""
        text = ""
        for enc in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if not text:
            text = raw.decode("utf-8", errors="replace")
        text = text.lstrip("\ufeff\x00 \t\r\n")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            m = re.match(r"^\s*[\w$.]+\((.*)\)\s*;?\s*$", text, re.S)
            if not m:
                snippet = re.sub(r"\s+", " ", text)[:240]
                raise ThsApiError(
                    "Tonghuashun returned non-JSON content; the cookie may "
                    f"have expired. Body: {snippet!r}"
                )
            try:
                payload = json.loads(m.group(1))
            except json.JSONDecodeError as exc:
                raise ThsApiError("invalid JSONP response from Tonghuashun") from exc
        if not isinstance(payload, dict):
            raise ThsApiError("unexpected non-object JSON response from Tonghuashun")
        return payload

    def _raise_for_api_error(self, payload: dict) -> None:
        code = payload.get("errorcode")
        if code is None:
            code = payload.get("errcode")
        if code is not None and str(code).strip() not in ("", "0", "200"):
            msg = (payload.get("errormsg") or payload.get("message")
                   or payload.get("msg") or f"Tonghuashun errorcode {code}")
            raise ThsApiError(str(msg), code=code, payload=payload)
        if payload.get("success") is False:
            msg = payload.get("errormsg") or payload.get("message") or "request failed"
            raise ThsApiError(str(msg), code=code, payload=payload)

    def _retry_after(self, headers: Mapping[str, str]) -> float | None:
        for key, value in headers.items():
            if key.lower() == "retry-after":
                try:
                    return max(0.0, float(value))
                except (TypeError, ValueError):
                    return None
        return None

    def _post(self, path: str, data: Mapping[str, object], *,
              idempotent: bool, operation: str) -> dict:
        last_error: Exception | None = None
        attempts = self.config.max_retries + 1
        for attempt in range(attempts):
            retry_after = None
            try:
                response = self.transport.post_form(
                    self._url(path), data, self._headers(), self.config.timeout)
            except ThsTransportError as exc:
                last_error = exc
                if not idempotent or not exc.retryable or attempt >= attempts - 1:
                    raise
                self._sleep(self.config.retry_backoff * (2 ** attempt))
                continue

            if response.status in (301, 302, 303, 307, 308):
                raise ThsApiError(
                    f"{operation}: got HTTP {response.status} redirect; the "
                    "THS cookie has probably expired. Refresh it in the browser."
                )
            if not (200 <= response.status < 300):
                err = ThsHttpError(response.status, response.text(500))
                last_error = err
                if not idempotent or not err.retryable or attempt >= attempts - 1:
                    raise err
                retry_after = self._retry_after(response.headers)
                delay = retry_after if retry_after is not None else (
                    self.config.retry_backoff * (2 ** attempt))
                self._sleep(delay)
                continue

            payload = self._decode_json(response)
            self._raise_for_api_error(payload)
            return payload

        # Unreachable, but keeps type checkers and future edits honest.
        assert last_error is not None
        raise last_error

    def _get_raw(self, path: str, params: Mapping[str, object] | None = None,
                 *, operation: str) -> HttpResponse:
        url = self._url(path)
        if params:
            sep = "&" if "?" in url else "?"
            url += sep + urlencode({k: str(v) for k, v in params.items()})
        attempts = self.config.max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = self.transport.get(
                    url, self._headers(), self.config.timeout)
            except ThsTransportError as exc:
                last_error = exc
                if not exc.retryable or attempt >= attempts - 1:
                    raise
                self._sleep(self.config.retry_backoff * (2 ** attempt))
                continue
            if response.status in (301, 302, 303, 307, 308):
                raise ThsApiError(
                    f"{operation}: got HTTP {response.status} redirect; the "
                    "THS cookie has probably expired. Refresh it in the browser."
                )
            if not (200 <= response.status < 300):
                err = ThsHttpError(response.status, response.text(500))
                last_error = err
                if not err.retryable or attempt >= attempts - 1:
                    raise err
                self._sleep(self.config.retry_backoff * (2 ** attempt))
                continue
            return response
        assert last_error is not None
        raise last_error

    def get_shareholder_accounts(self, *, force: bool = False) -> dict[str, str]:
        """Return a market-code -> shareholder-account mapping.

        The buy/sell form has options like ``<option value="2">沪A A123456789
        </option>``.  The same ``gdzh`` is not valid for every market: Shanghai
        A-shares and Shenzhen A-shares can use different shareholder accounts.
        The mapping is read from the form and cached in memory.
        """
        if self._shareholder_accounts and not force:
            return dict(self._shareholder_accounts)
        response = self._get_raw(
            self.BUY_DIV_PATH, {"ajaxdatatype": "html"},
            operation="query shareholder accounts")
        text = ""
        for enc in ("utf-8", "gb18030"):
            try:
                text = response.body.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if not text:
            text = response.body.decode("utf-8", errors="replace")
        pattern = re.compile(
            r'<option\s+value=["\']([^"\']+)["\'][^>]*>(.*?)</option>',
            re.I | re.S)
        accounts: dict[str, str] = {}
        for market_code, raw_label in pattern.findall(text):
            label = html.unescape(re.sub(r"<[^>]+>", "", raw_label)).strip()
            match = re.search(r"([A-Za-z0-9]{6,32})\s*$", label)
            if match:
                accounts[str(market_code)] = match.group(1)
        if not accounts:
            raise ThsApiError(
                "shareholder account form contained no usable gddm options; "
                "the cookie may have expired or the page layout changed")
        self._shareholder_accounts.update(accounts)
        return dict(self._shareholder_accounts)

    def account_for_market(self, market_code: str | int | None) -> str:
        code = str(market_code or "").strip()
        if code and code not in self._shareholder_accounts:
            try:
                self.get_shareholder_accounts()
            except Exception:
                # Fall back to the configured account. This keeps read-only
                # behaviour and single-market accounts working, while the
                # caller will get a clear broker rejection if it is wrong.
                pass
        return self._shareholder_accounts.get(code) or self.config.gdzh

    # ------------------------------------------------------------------
    # Read-only queries    # ------------------------------------------------------------------
    def get_account(self) -> Account:
        payload = self._post(
            self.POSITIONS_PATH,
            {"type": "cmd_wt_mairu", "updateClass": "qryzijin|"},
            idempotent=True,
            operation="query account",
        )
        data = _dig(payload, "result", "qryzijin", "result", "data")
        if not isinstance(data, Mapping):
            raise ThsApiError(
                "unexpected account response: result.qryzijin.result.data missing",
                payload=payload,
            )
        available = _first_float(data, ("kyje", "available_cash", "可用金额"), 0.0)
        total = _first_float(data, ("zzc", "total_assets", "总资产"), 0.0)
        market = _first_float(data, ("zsz", "market_value", "总市值"), 0.0)
        return Account(
            available_cash=float(available or 0.0),
            total_assets=float(total or 0.0),
            market_value=float(market or 0.0),
            raw=dict(data),
        )

    def get_positions(self) -> list[Position]:
        payload = self._post(
            self.POSITIONS_PATH,
            {"type": "cmd_wt_mairu",
             "updateClass": "qryzijin|qryChicang|"},
            idempotent=True,
            operation="query positions",
        )
        rows = _dig(payload, "result", "qryChicang", "result", "list", default=[])
        if rows is None:
            rows = []
        if not isinstance(rows, list):
            raise ThsApiError("unexpected positions response: list expected",
                              payload=payload)
        positions: list[Position] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            symbol = normalize_symbol(row.get("d_2102"))
            balance = as_int(row.get("d_2117"), 0) or 0
            amount = as_int(row.get("d_2164"), 0) or 0
            available = as_int(row.get("d_2121"), balance)
            if available is None:
                available = balance
            cost_price = float(as_float(row.get("d_2122"), 0.0) or 0.0)
            market_price = float(as_float(row.get("d_2124"), cost_price) or cost_price)
            market_value = float(as_float(row.get("d_2125"), 0.0) or 0.0)
            positions.append(Position(
                symbol=symbol,
                name=str(row.get("d_2103") or ""),
                balance=balance,
                available=int(available),
                amount=amount,
                last_price=market_price,
                pnl=float(as_float(row.get("d_2147"), 0.0) or 0.0),
                pnl_ratio=float(as_float(row.get("d_3616"), 0.0) or 0.0),
                market_type=str(row.get("d_2108") or ""),
                account_id=str(row.get("d_2106") or ""),
                market_code=str(row.get("d_2167") or ""),
                cost_price=cost_price,
                market_value=market_value,
                frozen=int(as_int(row.get("d_2118"), 0) or 0),
                currency=str(row.get("d_2172") or ""),
            ))
        return positions

    def get_orders(self) -> list[Order]:
        """Return the currently cancellable/working orders.

        The upstream endpoint is named ``cmd_qu_chedan``; it is not guaranteed
        to include every historical fill.  It is the right list to use before
        cancelling.
        """
        payload = self._post(
            self.ORDERS_PATH,
            {"type": "cmd_qu_chedan",
             "updateClass": "qryzijin|qryChedan|"},
            idempotent=True,
            operation="query orders",
        )
        rows = _dig(payload, "result", "qryChedan", "result", "list", default=[])
        if rows is None:
            rows = []
        if not isinstance(rows, list):
            raise ThsApiError("unexpected orders response: list expected",
                              payload=payload)
        orders: list[Order] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            try:
                symbol = normalize_symbol(row.get("d_2102"))
            except ValueError:
                continue
            orders.append(Order(
                time=str(row.get("d_2140") or ""),
                order_id=str(row.get("d_2135") or ""),
                order_date=re.sub(r"\D", "", str(row.get("d_2139") or "")),
                symbol=symbol,
                name=str(row.get("d_2103") or ""),
                price=float(as_float(row.get("d_2127"), 0.0) or 0.0),
                quantity=int(as_int(row.get("d_2126"), 0) or 0),
                side=normalize_side(row.get("d_2109")) if str(row.get("d_2109") or "") in (
                    "买入", "卖出", "buy", "sell") else str(row.get("d_2109") or "").lower(),
                status=str(row.get("d_2105") or ""),
                market_type=str(row.get("d_2108") or ""),
            ))
        return orders

    def query_quote(self, symbol: str, *, side: str = "buy",
                    market_code: str | None = None) -> Quote:
        symbol = normalize_symbol(symbol)
        side = normalize_side(side)
        order_type = "cmd_wt_mairu" if side == "buy" else "cmd_wt_maichu"
        form = {"type": order_type, "stockcode": symbol}
        mkcode = str(market_code).strip() if market_code is not None \
            else market_code_for_symbol(symbol)
        if mkcode:
            form["mkcode"] = mkcode
        payload = None
        for attempt in range(2):
            try:
                payload = self._post(
                    self.QUOTE_PATH,
                    form,
                    idempotent=True,
                    operation=f"query quote {symbol}",
                )
                break
            except ThsApiError as exc:
                # The simulated counter occasionally returns this transient
                # "quote not available" error even for valid stocks. Quote
                # queries are safe to retry; order submissions never are.
                if attempt == 0 and "暂时不提供" in str(exc):
                    self._sleep(self.config.retry_backoff)
                    continue
                raise
        assert payload is not None
        data = _dig(payload, "result", "data")
        if not isinstance(data, Mapping):
            raise ThsApiError(
                f"unexpected quote response for {symbol}: result.data missing",
                payload=payload,
            )
        price = _first_float(data, QUOTE_FIELDS["price"], None)
        if price is None or price <= 0:
            raise ThsApiError(
                f"no valid last price for {symbol}; it may be suspended or "
                "the code may be wrong", payload=payload)
        can_buy = int(as_int(_first(data, QUOTE_FIELDS["can_buy"], 0), 0) or 0)
        market_code = str(_first(data, QUOTE_FIELDS["market_code"], "") or "")
        bids = self._levels(data, "mrjw", "mrsl")
        asks = self._levels(data, "mcjw", "mcsl")
        return Quote(
            symbol=symbol,
            last_price=float(price),
            can_buy=can_buy,
            market_code=market_code,
            bid1=bids[0][0] if bids else 0.0,
            ask1=asks[0][0] if asks else 0.0,
            bids=tuple(bids),
            asks=tuple(asks),
        )

    @staticmethod
    def _levels(data: Mapping, price_prefix: str,
                qty_prefix: str) -> list[tuple[float, int]]:
        out: list[tuple[float, int]] = []
        for i in range(1, 6):
            px = as_float(data.get(f"{price_prefix}{i}"), None)
            qty = as_int(data.get(f"{qty_prefix}{i}"), None)
            if px is not None and px > 0:
                out.append((float(px), int(qty or 0)))
        return out

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------
    def place_order(self, symbol: str, side: str, quantity: int, *,
                    price: float | None = None,
                    client_order_id: str | None = None,
                    dry_run: bool = True,
                    quote: Quote | None = None) -> OrderResult:
        symbol = normalize_symbol(symbol)
        side = normalize_side(side)
        try:
            qty = int(quantity)
        except (TypeError, ValueError) as exc:
            raise ThsValidationError(f"quantity must be an integer: {quantity!r}") from exc
        if qty <= 0:
            raise ThsValidationError("quantity must be positive")

        q = quote or self.query_quote(symbol, side=side)
        limit_price = round_price(price if price is not None else q.last_price)
        if limit_price <= 0:
            raise ThsValidationError("limit price must be positive")

        if side == "buy":
            rounded = round_buy_quantity(qty)
            if rounded < 100:
                raise ThsValidationError(
                    f"buy quantity must be at least 100 shares (got {qty})")
            if q.can_buy > 0 and rounded > q.can_buy:
                raise ThsValidationError(
                    f"buy quantity {rounded} exceeds broker can-buy {q.can_buy}")
            qty = rounded
            account_id = self.account_for_market(q.market_code)
        else:
            position = next((p for p in self.get_positions()
                             if p.symbol == symbol), None)
            if position is None:
                raise ThsValidationError(f"no position in {symbol} to sell")
            available = int(position.available)
            if available <= 0:
                raise ThsValidationError(
                    f"{symbol} has no sellable quantity (T+1 lock or zero balance)")
            if qty > available:
                raise ThsValidationError(
                    f"sell quantity {qty} exceeds sellable {available} for {symbol}")
            qty = round_sell_quantity(
                qty, full_liquidation=(qty == available), available=available)
            if qty <= 0:
                raise ThsValidationError(
                    "partial sell must be at least 100 shares; an odd lot can "
                    "only be sold as a full liquidation")
            account_id = (position.account_id
                           or self.account_for_market(q.market_code))

        if client_order_id is None:
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
            client_order_id = f"THS-{stamp}-{uuid.uuid4().hex[:10]}"
        intent = OrderIntent(
            client_order_id=str(client_order_id),
            symbol=symbol,
            side=side,
            quantity=qty,
            price=limit_price,
            amount_value=round(qty * limit_price, 2),
            account_id=account_id,
        )

        if dry_run:
            return OrderResult(
                intent=intent,
                accepted=False,
                dry_run=True,
                broker_code="DRY_RUN",
                message=f"dry run: would {side} {qty} {symbol} at {limit_price:.2f}",
            )

        self.journal.begin(intent)
        order_type = "cmd_wt_mairu" if side == "buy" else "cmd_wt_maichu"
        form = {
            "type": order_type,
            "mkcode": q.market_code,
            "gdzh": account_id,
            "stockcode": symbol,
            "price": f"{limit_price:.2f}",
            "amount": str(qty),
        }
        path = self.BUY_PATH if side == "buy" else self.SELL_PATH
        try:
            payload = self._post(
                path, form, idempotent=False, operation=f"{side} {symbol}")
        except ThsApiError as exc:
            if exc.code is None:
                # A redirect/login page or malformed JSON means we cannot tell
                # whether the browser session accepted the order.  Treat it as
                # unknown rather than a definitive rejection.
                self._safe_mark(intent.client_order_id, "unknown", message=str(exc))
                raise ThsOrderStateUnknown(
                    f"{side} {symbol} submission state is UNKNOWN after an "
                    f"unreadable/redirected broker response. Run 'orders' to "
                    f"reconcile before resubmitting. "
                    f"client_order_id={intent.client_order_id}. Cause: {exc}",
                    client_order_id=intent.client_order_id,
                ) from exc
            self._safe_mark(intent.client_order_id, "rejected", message=str(exc))
            raise ThsOrderRejected(
                str(exc), client_order_id=intent.client_order_id,
                code=exc.code, payload=exc.payload) from exc
        except ThsTransportError as exc:
            self._safe_mark(intent.client_order_id, "unknown", message=str(exc))
            raise ThsOrderStateUnknown(
                f"{side} {symbol} submission state is UNKNOWN after a transport "
                f"error. Do not resubmit blindly. Run 'orders' to reconcile. "
                f"client_order_id={intent.client_order_id}. Cause: {exc}",
                client_order_id=intent.client_order_id,
            ) from exc

        code = str(payload.get("errorcode", "")) if "errorcode" in payload else ""
        message = str(payload.get("errormsg") or payload.get("message") or "")
        broker_ref = self._extract_order_ref(payload)
        journal_note = ""
        try:
            self.journal.mark(intent.client_order_id, "submitted",
                              broker_ref=broker_ref or None,
                              message=message or None)
        except Exception as exc:  # journal must not turn an accepted order into a retry
            journal_note = f" (warning: journal update failed: {exc})"
        return OrderResult(
            intent=intent,
            accepted=True,
            broker_code=code,
            message=(message or "accepted") + journal_note,
            broker_ref=broker_ref,
        )

    @staticmethod
    def _extract_order_ref(payload: Mapping) -> str:
        candidates = (
            ("result", "data", "htbh"),
            ("result", "htbh"),
            ("data", "htbh"),
            ("htbh",),
            ("result", "data", "d_2135"),
            ("result", "d_2135"),
        )
        for path in candidates:
            value = _dig(payload, *path)
            if value not in (None, ""):
                return str(value)
        return ""

    def _safe_mark(self, client_order_id: str, status: str, *,
                   broker_ref: str | None = None, message: str | None = None) -> None:
        try:
            self.journal.mark(client_order_id, status,
                              broker_ref=broker_ref, message=message)
        except Exception:
            # The caller is already handling a broker/network failure.  Losing
            # the journal update must not mask the more actionable error.
            pass

    def cancel(self, order_or_id: Any, order_date: str | None = None, *,
               dry_run: bool = True) -> CancelResult:
        if isinstance(order_or_id, Order):
            order_id = order_or_id.order_id
            order_date = order_or_id.order_date
        else:
            order_id = str(order_or_id).strip()
        if not order_id:
            raise ThsValidationError("order id is required")
        date_digits = re.sub(r"\D", "", str(order_date or ""))
        if len(date_digits) != 8:
            raise ThsValidationError("order date must be YYYYMMDD")
        if dry_run:
            return CancelResult(
                order_id=order_id, order_date=date_digits, accepted=False,
                dry_run=True, message=f"dry run: would cancel {order_id}")
        try:
            payload = self._post(
                self.CANCEL_PATH,
                {"htbh": order_id, "wtrq": date_digits},
                idempotent=False,
                operation=f"cancel {order_id}",
            )
        except ThsApiError as exc:
            if exc.code is None:
                raise ThsOrderStateUnknown(
                    f"cancel {order_id} state is UNKNOWN after an unreadable/"
                    "redirected broker response. Run 'orders' to reconcile.",
                    client_order_id=order_id,
                ) from exc
            raise ThsOrderRejected(
                str(exc), client_order_id=order_id,
                code=exc.code, payload=exc.payload) from exc
        except ThsTransportError as exc:
            raise ThsOrderStateUnknown(
                f"cancel {order_id} state is UNKNOWN after a transport error. "
                "Run 'orders' to reconcile.",
                client_order_id=order_id,
            ) from exc
        message = str(payload.get("errormsg") or payload.get("message")
                      or "cancel accepted")
        return CancelResult(order_id=order_id, order_date=date_digits,
                            accepted=True, message=message)

    def cancel_all(self, *, dry_run: bool = True) -> dict:
        orders = self.get_orders()
        if dry_run:
            return {
                "dry_run": True,
                "orders": [o.to_dict() for o in orders],
                "cancelled": 0,
            }
        cancelled: list[dict] = []
        errors: list[dict] = []
        for order in orders:
            try:
                result = self.cancel(order)
                cancelled.append(result.to_dict())
            except Exception as exc:
                errors.append({
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "error": type(exc).__name__,
                    "message": str(exc),
                })
        return {
            "dry_run": False,
            "found": len(orders),
            "cancelled": len(cancelled),
            "results": cancelled,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Health and upstream-compatible aliases
    # ------------------------------------------------------------------
    def health(self) -> dict:
        started = time.monotonic()
        account = self.get_account()
        positions = self.get_positions()
        orders = self.get_orders()
        return {
            "ok": True,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "available_cash": account.available_cash,
            "total_assets": account.total_assets,
            "positions": len(positions),
            "working_orders": len(orders),
            "config": self.config.safe_summary(),
        }

    def get_fund(self) -> float:
        return self.get_account().available_cash

    def get_chicang(self) -> list[Position]:
        return self.get_positions()

    def get_order(self) -> list[Order]:
        return self.get_orders()

    def qry_stock(self, stock_code: str, cmd: str = "cmd_wt_mairu") -> Quote:
        return self.query_quote(stock_code,
                                side="buy" if cmd == "cmd_wt_mairu" else "sell")

    def buy(self, stock_code: str, amount: int, price: float | None = None,
            **kwargs) -> OrderResult:
        return self.place_order(stock_code, "buy", amount, price=price, **kwargs)

    def sell(self, position_or_symbol: Any, amount: int,
             price: float | None = None, **kwargs) -> OrderResult:
        symbol = position_or_symbol.symbol if isinstance(position_or_symbol, Position) \
            else position_or_symbol
        return self.place_order(symbol, "sell", amount, price=price, **kwargs)


def cancel_all(client: ThsClient, *, dry_run: bool = True) -> dict:
    """Module-level compatibility helper mirroring the upstream API."""
    return client.cancel_all(dry_run=dry_run)