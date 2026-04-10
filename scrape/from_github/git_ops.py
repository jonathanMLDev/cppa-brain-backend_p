"""Shallow clone / fetch and Git timestamps for exported files."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def looks_like_git_sha(ref: str) -> bool:
    if not ref or len(ref) < 7 or len(ref) > 40:
        return False
    return bool(re.fullmatch(r"[0-9a-fA-F]+", ref))


def git_output(args: List[str], cwd: Path) -> str:
    return subprocess.check_output(
        args, cwd=str(cwd), text=True, stderr=subprocess.PIPE
    ).strip()


def _configure_sparse_checkout(dest: Path, paths: List[str]) -> None:
    """Apply cone sparse-checkout paths (Git 2.25+)."""
    if not paths:
        return
    subprocess.run(
        ["git", "-C", str(dest), "sparse-checkout", "set", "--cone", *paths],
        check=True,
        capture_output=True,
    )


def clone_repo_at_ref(
    repo: str,
    dest: Path,
    ref: str,
    sparse_paths: Optional[List[str]] = None,
) -> str:
    """Clone ``org/name`` into ``dest`` at ``ref``. Returns resolved HEAD SHA.

    If ``sparse_paths`` is non-empty, uses a partial clone (``blob:none`` filter)
    and cone sparse-checkout to those directories under the repo root.
    """
    url = f"https://github.com/{repo}.git"
    paths = [p.strip().strip("/") for p in (sparse_paths or []) if p and str(p).strip()]
    use_sparse = bool(paths)

    if dest.exists() and (dest / ".git").exists():
        logger.info("Updating existing clone %s @ %s -> %s", repo, ref, dest)
        if looks_like_git_sha(ref):
            fetch_cmd = ["git", "-C", str(dest), "fetch", "--depth", "1", "origin", ref]
            if use_sparse:
                fetch_cmd[4:4] = ["--filter=blob:none"]
            subprocess.run(fetch_cmd, check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(dest), "checkout", "FETCH_HEAD"],
                check=True,
                capture_output=True,
            )
        else:
            fetch_cmd = ["git", "-C", str(dest), "fetch", "--depth", "1", "origin", ref]
            if use_sparse:
                fetch_cmd[4:4] = ["--filter=blob:none"]
            subprocess.run(fetch_cmd, check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(dest), "checkout", ref],
                check=True,
                capture_output=True,
            )
        if use_sparse:
            _configure_sparse_checkout(dest, paths)
        return git_output(["git", "rev-parse", "HEAD"], dest)

    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if looks_like_git_sha(ref):
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=str(dest), check=True, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", url],
            cwd=str(dest),
            check=True,
            capture_output=True,
        )
        fetch_cmd = ["git", "fetch", "--depth", "1", "origin", ref]
        if use_sparse:
            fetch_cmd.insert(2, "--filter=blob:none")
        subprocess.run(fetch_cmd, cwd=str(dest), check=True, capture_output=True)
        subprocess.run(
            ["git", "checkout", "FETCH_HEAD"],
            cwd=str(dest),
            check=True,
            capture_output=True,
        )
        if use_sparse:
            subprocess.run(
                ["git", "-C", str(dest), "sparse-checkout", "init", "--cone"],
                check=True,
                capture_output=True,
            )
            _configure_sparse_checkout(dest, paths)
        return git_output(["git", "rev-parse", "HEAD"], dest)

    if use_sparse:
        clone_cmd = [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            "-b",
            ref,
            url,
            str(dest),
        ]
        try:
            subprocess.run(clone_cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            err = (e.stderr or b"").decode("utf-8", errors="replace").strip()
            if err:
                logger.warning(
                    "Sparse shallow clone failed (exit %s); retrying init/fetch: %s",
                    e.returncode,
                    err,
                )
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            dest.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "init"], cwd=str(dest), check=True, capture_output=True
            )
            subprocess.run(
                ["git", "remote", "add", "origin", url],
                cwd=str(dest),
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    "git",
                    "fetch",
                    "--depth",
                    "1",
                    "--filter=blob:none",
                    "origin",
                    ref,
                ],
                cwd=str(dest),
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "checkout", "FETCH_HEAD"],
                cwd=str(dest),
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(dest), "sparse-checkout", "init", "--cone"],
                check=True,
                capture_output=True,
            )
        _configure_sparse_checkout(dest, paths)
        return git_output(["git", "rev-parse", "HEAD"], dest)

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "-b", ref, url, str(dest)],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        if err:
            logger.warning(
                "Shallow clone failed (exit %s); retrying with init/fetch: %s",
                e.returncode,
                err,
            )
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init"], cwd=str(dest), check=True, capture_output=True
        )
        subprocess.run(
            ["git", "remote", "add", "origin", url],
            cwd=str(dest),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "fetch", "--depth", "1", "origin", ref],
            cwd=str(dest),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "FETCH_HEAD"],
            cwd=str(dest),
            check=True,
            capture_output=True,
        )

    return git_output(["git", "rev-parse", "HEAD"], dest)


def git_last_modified_iso(repo_path: Path, relpath: str) -> str:
    """ISO 8601 last commit time for ``relpath`` (POSIX), or empty if unknown."""
    try:
        return git_output(
            ["git", "log", "-1", "--format=%cI", "--", relpath.replace("\\", "/")],
            repo_path,
        )
    except subprocess.CalledProcessError:
        return ""


def mtime_iso_fallback(file_path: Path) -> str:
    ts = file_path.stat().st_mtime
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
