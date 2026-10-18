"""Configuration loading for the Tonghuashun paper-trading adapter.

Credentials are deliberately read from an environment variable or a local JSON
file, never from command-line flags.  This keeps cookies out of shell history
and out of process listings.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from .errors import ThsConfigError

DEFAULT_BASE_URL = "https://mncg.10jqka.com.cn"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0"
)


def _home_dir() -> Path:
    try:
        return Path.home()
    except RuntimeError:
        for name in ("USERPROFILE", "HOME"):
            value = os.environ.get(name)
            if value:
                return Path(value)
        return Path.cwd()


def default_config_path() -> Path:
    override = os.environ.get("THS_CONFIG")
    if override:
        return Path(os.path.expandvars(os.path.expanduser(override)))
    return _home_dir() / ".ths_sim" / "config.json"


def default_journal_path() -> Path:
    return _home_dir() / ".ths_sim" / "orders.sqlite3"


def _clean_cookie(value: str) -> str:
    s = str(value or "").strip()
    if s.lower().startswith("cookie:"):
        s = s.split(":", 1)[1].strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1].strip()
    if not s:
        raise ThsConfigError("THS cookie is empty")
    if any(ch in s for ch in ("\r", "\n", "\x00")):
        raise ThsConfigError("THS cookie contains a newline/control character")
    return s


def _read_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise ThsConfigError(f"config file not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ThsConfigError(f"cannot read config file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ThsConfigError("config file must contain a JSON object")
    return data


def _pick(data: dict, *names: str, default=None):
    for name in names:
        if name in data and data[name] not in (None, ""):
            return data[name]
    return default


@dataclass(frozen=True, repr=False)
class ThsConfig:
    cookie: str = field(repr=False)
    gdzh: str
    base_url: str = DEFAULT_BASE_URL
    timeout: float = 15.0
    max_retries: int = 2
    retry_backoff: float = 0.5
    user_agent: str = DEFAULT_USER_AGENT
    journal_path: Path = field(default_factory=default_journal_path)
    commission_rate: float = 0.0003
    min_commission: float = 5.0
    stamp_duty: float = 0.0005
    transfer_fee: float = 0.00001
    shareholder_accounts: dict[str, str] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (f"ThsConfig(gdzh={self.gdzh!r}, base_url={self.base_url!r}, "
                f"cookie=***, timeout={self.timeout!r})")

    @property
    def origin(self) -> str:
        parts = urlsplit(self.base_url)
        return f"{parts.scheme}://{parts.netloc}"

    @property
    def referer(self) -> str:
        return self.base_url.rstrip("/") + "/cgiwt/index/index"

    def safe_summary(self) -> dict:
        gdzh = self.gdzh
        masked = (gdzh if len(gdzh) <= 4 else
                  f"{gdzh[:2]}***{gdzh[-3:]}")
        return {
            "gdzh": masked,
            "base_url": self.base_url,
            "cookie_present": bool(self.cookie),
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "journal_path": str(self.journal_path),
            "shareholder_accounts": len(self.shareholder_accounts),
        }

    @classmethod
    def load(cls, config_file: str | os.PathLike | None = None,
             *, journal_path: str | os.PathLike | None = None,
             timeout: float | None = None) -> "ThsConfig":
        explicit = config_file is not None
        path = Path(os.path.expandvars(os.path.expanduser(str(config_file)))) \
            if config_file else default_config_path()
        data: dict = {}
        if path.exists():
            data = _read_json(path)
        elif explicit:
            raise ThsConfigError(f"config file not found: {path}")

        cookie = _pick(data, "cookie", "THS_COOKIE")
        gdzh = _pick(data, "gdzh", "account_id", "THS_GDZH")
        cookie = os.environ.get("THS_COOKIE", cookie)
        gdzh = os.environ.get("THS_GDZH",
                              os.environ.get("THS_ACCOUNT_ID", gdzh))
        if not cookie:
            raise ThsConfigError(
                "missing THS cookie. Set THS_COOKIE or put 'cookie' in "
                f"{path} (never paste it into a chat or commit it)."
            )
        if not gdzh:
            raise ThsConfigError(
                "missing THS simulated account id. Set THS_GDZH or put "
                f"'gdzh' in {path}."
            )

        base_url = os.environ.get(
            "THS_BASE_URL", _pick(data, "base_url", default=DEFAULT_BASE_URL))
        base_url = str(base_url).rstrip("/")
        parts = urlsplit(base_url)
        if parts.scheme not in ("https", "http") or not parts.netloc:
            raise ThsConfigError(f"invalid THS base_url: {base_url!r}")

        def number(name: str, env_name: str, default, cast):
            value = os.environ.get(env_name, data.get(name, default))
            try:
                return cast(value)
            except (TypeError, ValueError) as exc:
                raise ThsConfigError(f"invalid {name}: {value!r}") from exc

        t = float(timeout) if timeout is not None else number(
            "timeout", "THS_TIMEOUT", 15.0, float)
        if not (1.0 <= t <= 120.0):
            raise ThsConfigError("timeout must be between 1 and 120 seconds")
        retries = number("max_retries", "THS_MAX_RETRIES", 2, int)
        if not (0 <= retries <= 5):
            raise ThsConfigError("max_retries must be between 0 and 5")

        jp_raw = journal_path or os.environ.get("THS_JOURNAL_PATH") \
            or data.get("journal_path") or default_journal_path()
        jp = Path(os.path.expandvars(os.path.expanduser(str(jp_raw))))
        if not jp.is_absolute() and path.exists():
            jp = path.parent / jp

        gdzh = str(gdzh).strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,32}", gdzh):
            raise ThsConfigError("gdzh must be 3-32 letters/digits/_/-")

        raw_accounts = data.get("shareholder_accounts") or {}
        if not isinstance(raw_accounts, dict):
            raise ThsConfigError("shareholder_accounts must be a JSON object")
        accounts = {
            str(k).strip(): str(v).strip()
            for k, v in raw_accounts.items()
            if str(k).strip() and str(v).strip()
        }

        return cls(
            cookie=_clean_cookie(cookie),
            gdzh=gdzh,
            shareholder_accounts=accounts,
            base_url=base_url,
            timeout=t,
            max_retries=retries,
            retry_backoff=float(data.get("retry_backoff", 0.5)),
            user_agent=str(data.get("user_agent", DEFAULT_USER_AGENT)),
            journal_path=jp,
            commission_rate=float(data.get("commission_rate", 0.0003)),
            min_commission=float(data.get("min_commission", 5.0)),
            stamp_duty=float(data.get("stamp_duty", 0.0005)),
            transfer_fee=float(data.get("transfer_fee", 0.00001)),
        )