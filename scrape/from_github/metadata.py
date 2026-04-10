"""Best-effort metadata derived from paths (e.g. product version labels)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


def normalize_product_version(rel_posix: str) -> Optional[str]:
    """Best-effort version segment from path (generic; no vendor lock-in)."""
    for part in Path(rel_posix).parts:
        pl = part.lower()
        if re.match(r"^vs[-_]?\d{4}$", pl):
            return part
        if re.match(r"^\d{4}\.\d+$", part):
            return part
        if pl in ("latest", "stable", "preview"):
            return part
    return None
