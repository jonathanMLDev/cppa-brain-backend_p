"""Layout constants for the from_github package directory."""

from pathlib import Path

FROM_GITHUB_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = FROM_GITHUB_ROOT.parents[2]

DEFAULT_CONFIG = FROM_GITHUB_ROOT / "repos.json"
DEFAULT_RAW = FROM_GITHUB_ROOT / "raw"
DEFAULT_EXPORT_DIR = FROM_GITHUB_ROOT / "export"
