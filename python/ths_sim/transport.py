"""Minimal HTTP transport built on the standard library.

No third-party dependency is required.  Redirects are not followed because a
redirect on the simulated-trading endpoints usually means the cookie expired;
following it could also leak the Cookie header across hosts.
"""
from __future__ import annotations

import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import urlencode

from .errors import ThsTransportError


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)

    def text(self, limit: int | None = None) -> str:
        raw = self.body
        if limit is not None:
            raw = raw[:limit]
        for enc in ("utf-8", "gb18030"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


class UrllibTransport:
    """Default transport; injectable for tests and for a different HTTP stack."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_NoRedirect())

    def _open(self, method: str, url: str, data: bytes | None,
              headers: Mapping[str, str], timeout: float) -> HttpResponse:
        req = urllib.request.Request(
            url, data=data, headers=dict(headers), method=method)
        try:
            with self._opener.open(req, timeout=timeout) as resp:
                return HttpResponse(
                    status=int(resp.status),
                    body=resp.read(),
                    headers=dict(resp.headers.items()),
                )
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read()
            except Exception:
                body = b""
            return HttpResponse(
                status=int(exc.code),
                body=body,
                headers=dict(exc.headers.items()) if exc.headers else {},
            )
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise ThsTransportError(
                f"network error while calling Tonghuashun: {reason}",
                retryable=True,
            ) from exc

    def post_form(self, url: str, data: Mapping[str, object],
                  headers: Mapping[str, str], timeout: float) -> HttpResponse:
        payload = urlencode({k: str(v) for k, v in data.items()}).encode("utf-8")
        return self._open("POST", url, payload, headers, timeout)

    def get(self, url: str, headers: Mapping[str, str],
            timeout: float) -> HttpResponse:
        return self._open("GET", url, None, headers, timeout)