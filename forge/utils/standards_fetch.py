"""Fetch public metadata for national / international standards (titles only)."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

# Known GB standards — static fallback when network or page layout changes
_GB_STANDARD_TITLES: dict[str, str] = {
    "GB/T 22239-2019": "信息安全技术 网络安全等级保护基本要求",
    "GB/T 28448-2019": "信息安全技术 网络安全等级保护测评要求",
    "GB/T 25070-2019": "信息安全技术 网络安全等级保护安全设计技术要求",
}

_ISO_TITLES: dict[str, str] = {
    "ISO/IEC 20000-1:2018": "信息技术 服务管理 第1部分：服务管理体系要求",
}

_USER_AGENT = "Forge-StandardsBot/1.0 (+https://github.com/forge; public-metadata-only)"


def fetch_url_text(url: str, *, timeout: float = 12.0) -> str | None:
    """GET a public page; returns body text or None on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("Fetch failed for %s: %s", url, exc)
        return None


def resolve_gb_title(std_code: str, *, try_fetch: bool = False) -> str:
    """Resolve GB standard display title from static table or optional openstd fetch."""
    if std_code in _GB_STANDARD_TITLES:
        return _GB_STANDARD_TITLES[std_code]

    if not try_fetch:
        return std_code

    # openstd search — best-effort; layout may change
    query = std_code.replace("/", "%2F")
    url = f"https://openstd.samr.gov.cn/bzgk/gb/index?keyword={query}"
    html = fetch_url_text(url)
    if not html:
        return std_code

    match = re.search(r"《([^》]+)》", html)
    if match:
        title = match.group(1).strip()
        _GB_STANDARD_TITLES[std_code] = title
        return title
    return std_code


def build_public_metadata_report(*, try_fetch: bool = False) -> dict[str, Any]:
    """Build a JSON-serializable report of known public standard metadata."""
    gb_entries = {
        code: {
            "title": resolve_gb_title(code, try_fetch=try_fetch),
            "source": "static" if code in _GB_STANDARD_TITLES else "fetch",
        }
        for code in ("GB/T 22239-2019", "GB/T 28448-2019", "GB/T 25070-2019")
    }
    iso_entries = {
        code: {"title": _ISO_TITLES.get(code, code), "source": "static"}
        for code in _ISO_TITLES
    }
    return {
        "gb_standards": gb_entries,
        "iso_standards": iso_entries,
        "itil": {
            "framework": "ITIL 4",
            "publisher": "AXELOS",
            "note": "Practice names sourced from AXELOS public practice catalog",
        },
        "fetch_attempted": try_fetch,
    }


def write_metadata_report(path: str, *, try_fetch: bool = False) -> dict[str, Any]:
    report = build_public_metadata_report(try_fetch=try_fetch)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return report
