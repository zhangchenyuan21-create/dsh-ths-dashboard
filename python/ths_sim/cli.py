"""Command-line interface for the Tonghuashun paper-trading adapter."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .client import ThsClient
from .config import ThsConfig, default_journal_path
from .errors import (
    ThsApiError,
    ThsConfigError,
    ThsError,
    ThsOrderStateUnknown,
    ThsTransportError,
    ThsValidationError,
)
from .executor import (
    build_rebalance_plan,
    execute_rebalance,
    load_orders_csv,
    load_targets,
    submit_orders,
)
from .journal import OrderJournal


def _json(obj: Any, compact: bool = False) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=None if compact else 2,
                      default=str)


def _client(args: argparse.Namespace) -> ThsClient:
    config = ThsConfig.load(
        args.config,
        journal_path=args.journal,
        timeout=args.timeout,
    )
    return ThsClient(config)


def _common_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m ths_sim",
        description=(
            "Tonghuashun simulated-account adapter. Mutating commands are "
            "dry-run unless --live is supplied."
        ),
    )
    p.add_argument("--config", help="path to config JSON (default: ~/.ths_sim/config.json)")
    p.add_argument("--journal", help="path to local order journal SQLite file")
    p.add_argument("--timeout", type=float, help="HTTP timeout seconds")
    p.add_argument("--compact", action="store_true", help="one-line JSON output")
    return p


def _add_live(p: argparse.ArgumentParser) -> None:
    p.add_argument("--live", action="store_true",
                   help="actually send the request; omitted means dry-run")


def build_parser() -> argparse.ArgumentParser:
    parser = _common_parser()
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="check account, positions and working orders")
    sub.add_parser("account", help="show available cash and total assets")
    sub.add_parser("positions", help="list current positions")
    sub.add_parser("orders", help="list currently cancellable/working orders")
    sub.add_parser("accounts", help="show market-code to shareholder-account mapping")

    q = sub.add_parser("quote", help="query a stock quote and five-level book")
    q.add_argument("symbol")
    q.add_argument("--side", choices=("buy", "sell"), default="buy")

    for name, help_text in (("buy", "submit a buy order"),
                            ("sell", "submit a sell order")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("symbol")
        p.add_argument("quantity", type=int)
        p.add_argument("--price", type=float, default=None,
                       help="limit price; default is the current last price")
        p.add_argument("--client-order-id", default=None,
                       help="idempotency key recorded in the local journal")
        _add_live(p)

    c = sub.add_parser("cancel", help="cancel one working order")
    c.add_argument("order_id")
    c.add_argument("order_date", help="YYYYMMDD")
    _add_live(c)

    ca = sub.add_parser("cancel-all", help="cancel every working order")
    _add_live(ca)

    sc = sub.add_parser("submit-csv", help="submit a batch CSV of orders")
    sc.add_argument("file")
    sc.add_argument("--continue-on-error", action="store_true")
    _add_live(sc)

    rb = sub.add_parser("rebalance", help="rebalance to target weights")
    rb.add_argument("file", help="targets JSON or CSV")
    rb.add_argument("--cash-reserve", type=float, default=None,
                    help="fraction of equity to keep as cash (default: file value or 0.05)")
    rb.add_argument("--wait", type=float, default=0.0,
                    help="seconds to wait for sells to free cash before buys")
    rb.add_argument("--poll", type=float, default=2.0,
                    help="cash polling interval seconds")
    rb.add_argument("--ticks", type=int, default=1,
                    help="aggressive price ticks beyond last price")
    rb.add_argument("--max-order-value", type=float, default=None)
    rb.add_argument("--max-turnover", type=float, default=None)
    _add_live(rb)

    j = sub.add_parser("journal", help="show the local order journal")
    j.add_argument("--limit", type=int, default=30)
    return parser


def _print(obj: Any, args: argparse.Namespace) -> None:
    sys.stdout.write(_json(obj, args.compact) + "\n")


def _cmd_health(args: argparse.Namespace) -> int:
    _print(_client(args).health(), args)
    return 0


def _cmd_account(args: argparse.Namespace) -> int:
    _print(_client(args).get_account().to_dict(), args)
    return 0


def _cmd_positions(args: argparse.Namespace) -> int:
    _print([p.to_dict() for p in _client(args).get_positions()], args)
    return 0


def _cmd_orders(args: argparse.Namespace) -> int:
    _print([o.to_dict() for o in _client(args).get_orders()], args)
    return 0


def _cmd_accounts(args: argparse.Namespace) -> int:
    _print(_client(args).get_shareholder_accounts(force=True), args)
    return 0

def _cmd_quote(args: argparse.Namespace) -> int:
    _print(_client(args).query_quote(args.symbol, side=args.side).to_dict(), args)
    return 0


def _cmd_trade(args: argparse.Namespace) -> int:
    client = _client(args)
    result = client.place_order(
        args.symbol, args.command, args.quantity,
        price=args.price,
        client_order_id=args.client_order_id,
        dry_run=not args.live,
    )
    _print(result.to_dict(), args)
    return 0


def _cmd_cancel(args: argparse.Namespace) -> int:
    result = _client(args).cancel(
        args.order_id, args.order_date, dry_run=not args.live)
    _print(result.to_dict(), args)
    return 0


def _cmd_cancel_all(args: argparse.Namespace) -> int:
    _print(_client(args).cancel_all(dry_run=not args.live), args)
    return 0


def _cmd_submit_csv(args: argparse.Namespace) -> int:
    orders = load_orders_csv(args.file)
    result = submit_orders(
        _client(args), orders, live=args.live,
        continue_on_error=args.continue_on_error)
    _print(result, args)
    return 0 if not result["errors"] else 4


def _cmd_rebalance(args: argparse.Namespace) -> int:
    targets, file_reserve = load_targets(args.file)
    reserve = args.cash_reserve if args.cash_reserve is not None else (
        file_reserve if file_reserve is not None else 0.05)
    client = _client(args)
    plan = build_rebalance_plan(
        client, targets,
        cash_reserve=reserve,
        aggressive_ticks=args.ticks,
        max_order_value=args.max_order_value,
        max_turnover=args.max_turnover,
    )
    output: dict[str, Any] = {
        "dry_run": not args.live,
        "plan": plan.to_dict(),
    }
    if args.live:
        output["execution"] = execute_rebalance(
            client, plan, wait_seconds=args.wait, poll_interval=args.poll)
    _print(output, args)
    return 0 if not (args.live and output.get("execution", {}).get("errors")) else 4


def _journal_path(args: argparse.Namespace) -> Path:
    if args.journal:
        return Path(os.path.expandvars(os.path.expanduser(args.journal)))
    cfg_path = (Path(os.path.expandvars(os.path.expanduser(args.config)))
                if args.config else default_config_path())
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            raw = data.get("journal_path") if isinstance(data, dict) else None
            if raw:
                p = Path(os.path.expandvars(os.path.expanduser(str(raw))))
                return p if p.is_absolute() else cfg_path.parent / p
        except (OSError, ValueError):
            pass
    return default_journal_path()


def _cmd_journal(args: argparse.Namespace) -> int:
    path = _journal_path(args)
    journal = OrderJournal(path)
    _print({
        "path": str(path),
        "counts": journal.counts(),
        "orders": journal.list_recent(args.limit),
    }, args)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "rebalance":
        if args.wait < 0:
            parser.error("--wait must be >= 0")
        if args.poll <= 0:
            parser.error("--poll must be > 0")
    try:
        handlers = {
            "health": _cmd_health,
            "account": _cmd_account,
            "positions": _cmd_positions,
            "orders": _cmd_orders,
            "accounts": _cmd_accounts,
            "quote": _cmd_quote,
            "buy": _cmd_trade,
            "sell": _cmd_trade,
            "cancel": _cmd_cancel,
            "cancel-all": _cmd_cancel_all,
            "submit-csv": _cmd_submit_csv,
            "rebalance": _cmd_rebalance,
            "journal": _cmd_journal,
        }
        return handlers[args.command](args)
    except ThsConfigError as exc:
        error, code = exc, 3
    except ThsValidationError as exc:
        error, code = exc, 2
    except ThsOrderStateUnknown as exc:
        error, code = exc, 5
    except (ThsApiError, ThsTransportError) as exc:
        error, code = exc, 4
    except ThsError as exc:
        error, code = exc, 4
    except KeyboardInterrupt:
        sys.stderr.write("interrupted\n")
        return 130
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        error, code = exc, 1
    sys.stderr.write(_json({
        "ok": False,
        "error_type": type(error).__name__,
        "message": str(error),
    }, getattr(args, "compact", False)) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())