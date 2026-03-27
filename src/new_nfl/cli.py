from __future__ import annotations

import argparse

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="new-nfl", description="NEW NFL local tooling")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "bootstrap",
        help="Create local directories and baseline DuckDB metadata surface",
    )
    sub.add_parser("health", help="Check whether the baseline database exists")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    settings = load_settings()

    if args.command == "bootstrap":
        bootstrap_local_environment(settings)
        print(f"ENV={settings.env}")
        print(f"REPO_ROOT={settings.repo_root}")
        print(f"DATA_ROOT={settings.data_root}")
        print(f"DB_PATH={settings.db_path}")
        print("BOOTSTRAP=OK")
        return 0

    if args.command == "health":
        if not settings.db_path.exists():
            print("STATUS=missing")
            print(f"DB_PATH={settings.db_path}")
            return 1
        print("STATUS=ok")
        print(f"DB_PATH={settings.db_path}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
