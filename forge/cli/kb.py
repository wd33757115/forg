"""Knowledge base CLI — search and display project memory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from forge.core.state import create_initial_state
from forge.utils.knowledge import format_knowledge_context, search_knowledge
from forge.utils.state_persistence import load_state_with_metadata


def build_kb_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forge knowledge base commands")
    sub = parser.add_subparsers(dest="kb_command", required=True)

    search_p = sub.add_parser("search", help="Search knowledge_base by tag/agent")
    search_p.add_argument("--tag", action="append", default=[], help="Filter by tag (repeatable)")
    search_p.add_argument("--agent", help="Filter by source agent")
    search_p.add_argument("--limit", type=int, default=10)
    search_p.add_argument("--load-state", metavar="PATH", help="Load state JSON for search")
    search_p.add_argument("--project-id", default="cli-demo", help="Empty state project id")
    return parser


def kb_main(argv: list[str] | None = None) -> int:
    parser = build_kb_parser()
    args = parser.parse_args(argv)

    if args.kb_command == "search":
        if args.load_state:
            path = Path(args.load_state)
            state, _meta = load_state_with_metadata(path)
        else:
            state = create_initial_state(args.project_id)

        entries = search_knowledge(
            state,
            tags=args.tag or None,
            agent=args.agent,
            limit=args.limit,
        )
        if not entries:
            print("（无匹配知识条目）")
            return 0
        print(format_knowledge_context(entries))
        print("\n--- JSON ---")
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(kb_main())
