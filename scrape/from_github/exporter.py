"""Per-file JSON export from repo config."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from git_ops import (
    clone_repo_at_ref,
    git_last_modified_iso,
    git_output,
    mtime_iso_fallback,
)
from markdown_scan import content_keywords_match, iter_doc_files
from metadata import normalize_product_version
from utility import clean_text, validate_content_length

logger = logging.getLogger(__name__)


def _metadata_type_for_suffix(suffix: str) -> str:
    s = suffix.lower()
    if s == ".md":
        return "github-markdown"
    if s == ".rst":
        return "github-rst"
    return "github-doc"


def export_documents(
    config: Dict[str, Any],
    raw_base: Path,
    export_root: Path,
    *,
    clone: bool = False,
    global_limit: Optional[int] = None,
) -> int:
    min_len = int(config.get("min_content_length", 50))
    last_modified_mode = config.get("last_modified_mode", "git")
    repos_cfg = config.get("repos") or []

    if not repos_cfg:
        logger.warning("No repositories in config; nothing to export.")

    total_records = 0
    export_root.mkdir(parents=True, exist_ok=True)

    for entry in repos_cfg:
        repo = entry["repo"].strip()
        if repo != "fossas/fossa-cli":
            continue
        ref = str(entry.get("ref", "main")).strip()
        slug = (entry.get("slug") or repo.replace("/", "_")).strip()
        doc_roots = entry.get("doc_roots") or ["."]
        include_globs = entry.get("include_globs") or ["**/*.md"]
        exclude_globs = entry.get("exclude_globs") or []
        content_keywords = entry.get("content_keywords") or []
        tags = entry.get("tags") or {}
        max_files = entry.get("max_files")
        sparse_paths = entry.get("sparse_paths")

        repo_dest = raw_base / slug
        commit_sha = ""
        if clone:
            logger.info("Syncing %s @ %s -> %s", repo, ref, repo_dest)
            commit_sha = clone_repo_at_ref(
                repo, repo_dest, ref, sparse_paths=sparse_paths
            )
        else:
            if not repo_dest.is_dir():
                raise FileNotFoundError(
                    f"Expected existing clone at {repo_dest} (omit --no-clone to clone)"
                )
            commit_sha = git_output(["git", "rev-parse", "HEAD"], repo_dest)

        inc = include_globs if include_globs else ["**/*.md"]
        doc_files = iter_doc_files(repo_dest, doc_roots, inc, exclude_globs)
        if max_files is not None:
            doc_files = doc_files[: int(max_files)]

        slug_dir = export_root / slug
        if slug_dir.exists():
            shutil.rmtree(slug_dir)

        for doc_path in doc_files:
            if global_limit is not None and total_records >= global_limit:
                break
            try:
                rel = doc_path.relative_to(repo_dest).as_posix()
            except ValueError:
                continue

            raw_text = doc_path.read_text(encoding="utf-8", errors="ignore")
            if not content_keywords_match(raw_text, content_keywords):
                continue

            body = clean_text(raw_text, remove_extra_spaces=True)
            if not validate_content_length(body, min_length=min_len):
                continue

            if last_modified_mode == "git":
                lm = git_last_modified_iso(repo_dest, rel)
                if not lm:
                    lm = mtime_iso_fallback(doc_path)
            else:
                lm = mtime_iso_fallback(doc_path)

            url = f"https://github.com/{repo}/blob/{ref}/{rel}"
            doc_id = url
            pv = normalize_product_version(rel)
            doc_type = _metadata_type_for_suffix(doc_path.suffix)

            meta: Dict[str, Any] = {
                "url": url,
                "doc_id": doc_id,
                "type": doc_type,
                "repo": repo,
                "commit": commit_sha,
                "relpath": rel,
                "source": "github",
                "lang": entry.get("lang") or config.get("default_lang") or "en",
                "last_modified": lm,
            }
            if pv is not None:
                meta["product_version"] = pv
            else:
                meta["product_version"] = None
            for k, v in tags.items():
                meta[k] = v

            record = {"page_content": body, "metadata": meta}
            json_path = export_root / slug / Path(rel).with_suffix(".json")
            if not json_path.exists():
                json_path.parent.mkdir(parents=True, exist_ok=True)
                with open(json_path, "w", encoding="utf-8") as jf:
                    json.dump(record, jf, ensure_ascii=False)

            total_records += 1

        if global_limit is not None and total_records >= global_limit:
            break

    return total_records


__all__ = ["export_documents"]
