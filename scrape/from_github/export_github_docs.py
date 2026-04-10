"""
Clone configured GitHub doc repos, filter Markdown or RST (per repos.json), and write per-file JSON.

Run from this directory::

    python export_github_docs.py

Or from ``cppa-brain-backend``::

    python copilot_data/scrape/from_github/export_github_docs.py
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

try:
    import pathspec  # noqa: F401
except ImportError as e:
    raise SystemExit(
        "pathspec is required. Install with: pip install pathspec>=0.11.0"
    ) from e

from config_io import load_config
from exporter import export_documents
from paths import (
    DEFAULT_CONFIG,
    DEFAULT_EXPORT_DIR,
    DEFAULT_RAW,
)

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Export GitHub documentation (Markdown/RST per config) to JSON files."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to repos.json",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW,
        help="Directory for shallow clones",
    )
    parser.add_argument(
        "--json-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help="Root for per-file JSON mirroring repo paths under <slug>/... (default: export/)",
    )
    parser.add_argument(
        "--no-clone",
        action="store_true",
        help="Use existing repos under raw-dir (must already be cloned)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max total records across all repos (for testing)",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    n = export_documents(
        config,
        args.raw_dir,
        args.json_dir,
        clone=not args.no_clone,
        global_limit=args.limit,
    )
    logger.info("Wrote %s JSON files under %s", n, args.json_dir)


if __name__ == "__main__":
    main()
