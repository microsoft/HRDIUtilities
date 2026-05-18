#!/usr/bin/env python3
"""
Shared hardening helpers used by every deployment script.

These utilities exist so that the runtime behavior of the deployment scripts
matches the safety guarantees documented in the plugin's SKILL.md (sections
7.2, 7.4, 7.8, 7.9). They centralize:

    * input validation       -> validate_value()
    * path containment       -> assert_within_repo() / safe_resolve_under()
    * secret redaction       -> redact_secrets()
    * safe subprocess        -> run_argv() (shell=False, argv list)

Nothing here imports anything outside the Python standard library, so the
helpers can be used from any of the deployment scripts without adding a
dependency.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Iterable, Optional, Tuple


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------

_VALIDATION_RULES = {
    # Identity & scope
    "workspaceName":   re.compile(r"^[A-Za-z0-9_\- ]{1,64}$"),
    "lakehouseName":   re.compile(r"^[A-Za-z0-9_\- ]{1,64}$"),
    "connectionName":  re.compile(r"^[A-Za-z0-9_\- ]{1,80}$"),
    "shortcutName":    re.compile(r"^[A-Za-z0-9_\- ]{1,80}$"),
    "folderName":      re.compile(r"^[A-Za-z0-9_\-./ ]{1,200}$"),
    "tenantName":      re.compile(r"^[A-Za-z0-9_\-]{1,32}$"),
    "environment":     re.compile(r"^(dev|test|prod)$", re.IGNORECASE),
    "guid":            re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    ),
    "role":            re.compile(r"^(admin|contributor|member|viewer)$", re.IGNORECASE),
    "nodeSize":        re.compile(r"^(Small|Medium|Large|XLarge|XXLarge)$"),
    "storageAccount":  re.compile(r"^[a-z0-9]{3,24}$"),
    "containerPath":   re.compile(r"^[A-Za-z0-9_\-./ ]{1,200}$"),
    # Property names accepted on `fab set` calls.
    "propertyName":    re.compile(r"^[A-Za-z0-9_.]{1,64}$"),
    # Property values written via `fab set`. Conservative allowlist to avoid
    # any shell metacharacters even though we run with shell=False.
    "propertyValue":   re.compile(r"^[A-Za-z0-9_.\- ]{1,64}$"),
}

# Characters that should never appear in a value that ends up on a command
# line, even with shell=False, because they often indicate someone is trying
# to break out of an expected value.
_FORBIDDEN_SHELL_CHARS = set(";&|<>$`\\\"'\n\r\t\x00")


class ValidationError(ValueError):
    """Raised when a value fails the documented validation rules."""


def validate_value(value, kind: str, *, allow_empty: bool = False) -> str:
    """
    Validate `value` against the named rule (see _VALIDATION_RULES).

    Returns the value as a string on success. Raises ValidationError on
    failure. Empty / None values are rejected unless `allow_empty=True`,
    in which case an empty string is returned unchanged.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        if allow_empty:
            return ""
        raise ValidationError(f"{kind!r} is required but empty")

    s = str(value)

    # Reject any shell-metacharacter regardless of regex match.
    bad = _FORBIDDEN_SHELL_CHARS.intersection(s)
    if bad:
        raise ValidationError(
            f"{kind!r} contains forbidden character(s): {sorted(bad)!r}"
        )

    rule = _VALIDATION_RULES.get(kind)
    if rule is None:
        raise ValidationError(f"unknown validation kind: {kind!r}")
    if not rule.match(s):
        raise ValidationError(
            f"{kind!r} value does not match the allowed pattern"
        )
    return s


def validate_int_range(value, kind: str, lo: int, hi: int) -> int:
    """Validate that `value` is an int (or int-string) within [lo, hi]."""
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{kind!r} must be an integer") from exc
    if not (lo <= n <= hi):
        raise ValidationError(f"{kind!r}={n} is outside [{lo}, {hi}]")
    return n


def validate_https_url(value, kind: str = "url") -> str:
    """Allow only https:// URLs with safe characters."""
    s = str(value or "").strip()
    if not s.lower().startswith("https://"):
        raise ValidationError(f"{kind!r} must start with https://")
    if any(ch in _FORBIDDEN_SHELL_CHARS for ch in s):
        raise ValidationError(f"{kind!r} contains forbidden character(s)")
    if not re.match(r"^https://[A-Za-z0-9._\-/:%?=&]{1,2048}$", s):
        raise ValidationError(f"{kind!r} contains characters outside the URL allowlist")
    return s


# ---------------------------------------------------------------------------
# 2. Path containment
# ---------------------------------------------------------------------------

def safe_resolve_under(candidate: Path | str, repo_root: Path) -> Path:
    """
    Resolve `candidate` and confirm it stays under `repo_root`.

    Rejects paths containing `..`, UNC roots, environment-variable tokens,
    and anything that resolves outside `repo_root` after symlink resolution.

    Returns the resolved absolute Path. Raises ValidationError on violation.
    """
    raw = str(candidate)
    if not raw:
        raise ValidationError("path is empty")
    if "%" in raw or "$" in raw:
        raise ValidationError(f"path contains env-var token(s): {raw!r}")
    if raw.startswith("\\\\") or raw.startswith("//"):
        raise ValidationError(f"UNC paths are not allowed: {raw!r}")

    repo_root = repo_root.resolve()
    p = (repo_root / raw) if not Path(raw).is_absolute() else Path(raw)
    try:
        resolved = p.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ValidationError(f"could not resolve path {raw!r}: {exc}") from exc

    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ValidationError(
            f"path {raw!r} resolves outside repo root {str(repo_root)!r}"
        ) from exc
    return resolved


def assert_within_repo(candidate: Path | str, repo_root: Path) -> Path:
    """Alias for safe_resolve_under() with a more readable call-site name."""
    return safe_resolve_under(candidate, repo_root)


# ---------------------------------------------------------------------------
# 3. Secret redaction
# ---------------------------------------------------------------------------

_REDACTION_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    # JWT / bearer tokens
    (re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}"),
     "***REDACTED_JWT***"),
    # GitHub PAT
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
     "***REDACTED_GHPAT***"),
    # Common connection-string fragments
    (re.compile(r"(AccountKey|SharedAccessSignature|Password|ClientSecret)\s*=\s*[^;\s\"]+",
                re.IGNORECASE),
     r"\1=***REDACTED***"),
    # SAS sig= component
    (re.compile(r"(?i)\bsig=[A-Za-z0-9%]{20,}"),
     "sig=***REDACTED***"),
    # 88-char base64 (likely storage account key)
    (re.compile(r"\b[A-Za-z0-9+/]{86,88}={0,2}\b"),
     "***REDACTED_KEY***"),
)


def redact_secrets(text: str) -> str:
    """Apply all secret-shaped redactions to `text`.

    Best-effort defense-in-depth before writing to console / log / CSV.
    """
    if not text:
        return text
    out = str(text)
    for pat, repl in _REDACTION_PATTERNS:
        out = pat.sub(repl, out)
    return out


# ---------------------------------------------------------------------------
# 4. Safe subprocess execution (shell=False, argv list)
# ---------------------------------------------------------------------------

def run_argv(
    argv: Iterable[str],
    *,
    capture: bool = False,
    timeout: int = 300,
    cwd: Optional[Path] = None,
) -> Tuple[bool, str, str]:
    """
    Run `argv` with shell=False. Returns (success, stdout, stderr).

    Every element of `argv` is coerced to str. No element may contain a NUL
    byte. The function NEVER concatenates these into a single shell string,
    so values that contain spaces or quotes are passed verbatim as a single
    argument to the child process.
    """
    args = [str(a) for a in argv]
    for a in args:
        if "\x00" in a:
            raise ValidationError("argv element contains NUL byte")

    try:
        r = subprocess.run(
            args,
            shell=False,
            capture_output=capture,
            text=True if capture else False,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
        )
        out = (r.stdout or "").strip() if capture else ""
        err = (r.stderr or "").strip() if capture else ""
        return r.returncode == 0, out, err
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except FileNotFoundError as exc:
        return False, "", f"Executable not found: {exc}"
    except Exception as exc:  # pragma: no cover - defensive
        return False, "", str(exc)
