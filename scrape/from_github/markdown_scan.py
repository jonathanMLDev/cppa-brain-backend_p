"""Discover doc files under doc roots with include/exclude gitwildmatch rules."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import pathspec

logger = logging.getLogger(__name__)


def build_specs(
    include_globs: List[str], exclude_globs: List[str]
) -> Tuple[Optional[pathspec.PathSpec], pathspec.PathSpec]:
    """Include spec: None means all non-excluded files under roots."""
    inc = (
        pathspec.PathSpec.from_lines("gitwildmatch", include_globs)
        if include_globs
        else None
    )
    exc = (
        pathspec.PathSpec.from_lines("gitwildmatch", exclude_globs)
        if exclude_globs
        else pathspec.PathSpec.from_lines("gitwildmatch", [])
    )
    return inc, exc


def iter_doc_files(
    repo_root: Path,
    doc_roots: List[str],
    include_globs: List[str],
    exclude_globs: List[str],
) -> List[Path]:
    """List files under doc_roots matching include_globs and not exclude_globs."""
    inc_spec, exc_spec = build_specs(include_globs, exclude_globs)
    files: List[Path] = []
    roots = doc_roots or ["."]
    for root in roots:
        base = (repo_root / root).resolve()
        if not base.exists():
            logger.warning("Doc root missing, skip: %s", base)
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(repo_root).as_posix()
            except ValueError:
                continue
            if exc_spec.match_file(rel):
                continue
            if inc_spec is not None and not inc_spec.match_file(rel):
                continue
            files.append(path)
    return sorted(files)


def iter_markdown_files(
    repo_root: Path,
    doc_roots: List[str],
    include_globs: List[str],
    exclude_globs: List[str],
) -> List[Path]:
    """Same as iter_doc_files with default **/*.md when include_globs is empty."""
    inc = include_globs if include_globs else ["**/*.md"]
    return iter_doc_files(repo_root, doc_roots, inc, exclude_globs)


def content_keywords_match(text: str, keywords: List[str]) -> bool:
    if not keywords:
        return True
    head = text[:48_000].lower()
    return any(k.lower() in head for k in keywords)
