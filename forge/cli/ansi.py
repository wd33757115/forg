"""ANSI terminal styling for Forge CLI (no Rich dependency)."""

from __future__ import annotations

import os
import textwrap

_USE_COLOR = not os.environ.get("NO_COLOR")


def use_color() -> bool:
    return _USE_COLOR


def _c(code: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def bold(t: str) -> str:
    return _c("1", t)


def cyan(t: str) -> str:
    return _c("36", t)


def green(t: str) -> str:
    return _c("32", t)


def yellow(t: str) -> str:
    return _c("33", t)


def red(t: str) -> str:
    return _c("31", t)


def dim(t: str) -> str:
    return _c("2", t)


def banner() -> None:
    print()
    print(bold("╔══════════════════════════════════════════════════════════════╗"))
    print(bold("║") + cyan("   Forge — 项目级 AI 操作系统") + bold("                              ║"))
    print(
        bold("║")
        + dim("   ProblemSolver → Security/Ops → Compliance → Document → PM")
        + bold("   ║")
    )
    print(bold("╚══════════════════════════════════════════════════════════════╝"))
    print()


def section(title: str) -> None:
    width = 62
    print()
    print(bold(f"┌─ {title} " + "─" * max(0, width - len(title) - 4)))


def wrap_text(text: str, indent: int = 2) -> str:
    prefix = " " * indent
    return textwrap.fill(text, width=76, initial_indent=prefix, subsequent_indent=prefix)
