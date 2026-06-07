#!/usr/bin/env python3
"""Enrich Rule Pack references from public standards catalog (等保2.0 / ITIL 4 / ISO 20000)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forge.utils.standards_enrich import enrich_rule_pack_file
from forge.utils.standards_fetch import write_metadata_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge public standard citations into Rule Pack JSON")
    parser.add_argument(
        "--pack",
        default=str(ROOT / "rule_packs" / "system_integration_v1.json"),
        help="Rule Pack JSON path",
    )
    parser.add_argument(
        "--catalog",
        default=str(ROOT / "rule_packs" / "standards_public_catalog.json"),
        help="Standards catalog path",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report stats without writing pack")
    parser.add_argument("--no-bump-version", action="store_true", help="Do not bump pack version")
    parser.add_argument(
        "--fetch-metadata",
        action="store_true",
        help="Try fetching openstd.samr.gov.cn titles (fallback to static table)",
    )
    parser.add_argument(
        "--metadata-out",
        default=str(ROOT / "reports" / "standards_public_metadata.json"),
        help="Where to write fetched public metadata report",
    )
    args = parser.parse_args()

    if args.fetch_metadata:
        out = Path(args.metadata_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        meta = write_metadata_report(str(out), try_fetch=True)
        print(json.dumps(meta, ensure_ascii=False, indent=2))

    result = enrich_rule_pack_file(
        args.pack,
        args.catalog,
        dry_run=args.dry_run,
        bump_version=not args.no_bump_version,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
