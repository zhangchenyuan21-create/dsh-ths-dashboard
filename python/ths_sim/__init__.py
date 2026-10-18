"""Tonghuashun simulated-account adapter.

Public entry points::

    from ths_sim import ThsConfig, ThsClient
    client = ThsClient(ThsConfig.load())
    print(client.get_account())

Mutating calls default to dry-run in the CLI.  The library API itself requires
an explicit ``dry_run=False`` and therefore does not hide submissions.
"""
from __future__ import annotations

from .client import ThsClient, cancel_all
from .config import ThsConfig, default_config_path, default_journal_path
from .errors import (
    DuplicateOrderError,
    ThsApiError,
    ThsConfigError,
    ThsError,
    ThsHttpError,
    ThsOrderRejected,
    ThsOrderStateUnknown,
    ThsTransportError,
    ThsValidationError,
)
from .executor import (
    affordable_buy_quantity,
    build_rebalance_plan,
    estimate_fee,
    execute_rebalance,
    load_orders_csv,
    load_targets,
    submit_orders,
)
from .journal import OrderJournal
from .models import (
    Account,
    CancelResult,
    Order,
    OrderIntent,
    OrderResult,
    PlannedOrder,
    Position,
    Quote,
    RebalancePlan,
    normalize_side,
    normalize_symbol,
)
from .transport import HttpResponse, UrllibTransport

__all__ = [
    "ThsClient", "ThsConfig", "OrderJournal", "UrllibTransport",
    "HttpResponse", "cancel_all",
    "Account", "CancelResult", "Order", "OrderIntent", "OrderResult",
    "PlannedOrder", "Position", "Quote", "RebalancePlan",
    "normalize_side", "normalize_symbol",
    "build_rebalance_plan", "execute_rebalance", "load_orders_csv",
    "load_targets", "submit_orders", "affordable_buy_quantity", "estimate_fee",
    "ThsError", "ThsConfigError", "ThsValidationError", "ThsTransportError",
    "ThsHttpError", "ThsApiError", "ThsOrderRejected", "ThsOrderStateUnknown",
    "DuplicateOrderError",
    "default_config_path", "default_journal_path",
]