"""Exception types for the Tonghuashun paper-trading adapter.

The upstream project (Cfu4536/ths_simulated_API) uses plain exceptions and
prints API failures.  This adapter keeps failures typed so a strategy runner
can distinguish "definitely rejected" from "state unknown" and can never
accidentally retry a non-idempotent order submission.
"""
from __future__ import annotations


class ThsError(Exception):
    """Base class for every error raised by :mod:`ths_sim`."""


class ThsConfigError(ThsError):
    """Missing or invalid local configuration (cookie/account/etc.)."""


class ThsValidationError(ThsError, ValueError):
    """A request is invalid before it reaches the broker."""


class ThsTransportError(ThsError):
    """Network/HTTP failure.

    ``retryable`` only means that retrying an *idempotent* request is safe.
    Order submissions are never retried automatically.
    """

    def __init__(self, message: str, *, retryable: bool = True,
                 status: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.retryable = bool(retryable)
        self.status = status
        self.body = body


class ThsHttpError(ThsTransportError):
    """Non-2xx HTTP response."""

    def __init__(self, status: int, body: str) -> None:
        retryable = status in (408, 425, 429) or status >= 500
        super().__init__(f"HTTP {status} from Tonghuashun", retryable=retryable,
                         status=status, body=body)


class ThsApiError(ThsError):
    """The broker returned ``errorcode != 0`` or an unreadable response."""

    def __init__(self, message: str, *, code: str | int | None = None,
                 payload: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.payload = payload


class ThsOrderRejected(ThsApiError):
    """The broker explicitly rejected a submitted order."""

    def __init__(self, message: str, *, client_order_id: str | None = None,
                 code: str | int | None = None, payload: dict | None = None) -> None:
        super().__init__(message, code=code, payload=payload)
        self.client_order_id = client_order_id


class ThsOrderStateUnknown(ThsError):
    """The order submission may or may not have reached the broker.

    This is raised on a timeout/connection loss during a POST that changes
    state.  Do **not** blindly resubmit: query ``orders`` and reconcile first.
    """

    def __init__(self, message: str, *, client_order_id: str | None = None) -> None:
        super().__init__(message)
        self.client_order_id = client_order_id


class DuplicateOrderError(ThsError):
    """An idempotency key was already used."""