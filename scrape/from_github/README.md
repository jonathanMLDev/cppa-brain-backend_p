# `from_github` — GitHub Markdown / RST → JSON files

Location: **`copilot_data/scrape/from_github/`** (not under `cloud_rag`).

### Module layout

| Module                  | Role                                                                     |
| ----------------------- | ------------------------------------------------------------------------ |
| `export_github_docs.py` | CLI entry (`argparse`, logging).                                         |
| `paths.py`              | `FROM_GITHUB_ROOT`, `BACKEND_ROOT`, default paths.                       |
| `git_ops.py`            | Clone / fetch / checkout, `git log` timestamps, mtime fallback.          |
| `markdown_scan.py`      | Pathspec include/exclude, `iter_doc_files` / `iter_markdown_files`, keyword filter. |
| `metadata.py`           | `normalize_product_version` from path segments.                          |
| `config_io.py`          | `load_config` (JSON).                                                    |
| `exporter.py`           | `export_documents` — per-file JSON.                                      |
| `utility.py`            | `clean_text`, `validate_content_length`.                                 |

General-purpose export: clone **any** documentation repositories listed in `repos.json`, walk Markdown or RST under configurable roots (`include_globs`), normalize text, and write **one JSON file per document** (mirroring paths under `export/<slug>/…`). Optional **`sparse_paths`** (cone mode) reduces clone size for monorepos (e.g. `llvm/llvm-project` with `clang/docs` only). Downstream projects consume these files; **this pipeline does not call Pinecone.**

## Layout

| Path                 | Purpose                                                                                                         |
| -------------------- | --------------------------------------------------------------------------------------------------------------- |
| `repos.json`         | Active configuration (repos, refs, globs, tags).                                                                |
| `repos.example.json` | Example entries for large IDE doc repos (e.g. vscode-docs, visualstudio-docs). Copy or merge into `repos.json`. |
| `raw/<slug>/`        | Shallow Git clones (gitignored; recreated on each run unless `--no-clone`).                                     |
| `export/<slug>/…`    | One `.json` per page: `page_content`, `metadata` (paths mirror the clone).                                      |

## Requirements

- Python 3.10+
- `git` on `PATH`
- **`pathspec`** — see [requirements.txt](requirements.txt) in this folder.
- **Text normalization** — `clean_text` and `validate_content_length` live in [utility.py](utility.py) (no `cloud_rag` dependency).

Install:

```bash
cd copilot_data/scrape/from_github
pip install -r requirements.txt
```

## Usage

From this directory:

```bash
python export_github_docs.py
```

From the `cppa-brain-backend` repo root:

```bash
python copilot_data/scrape/from_github/export_github_docs.py
```

Options:

| Flag              | Meaning                                                   |
| ----------------- | --------------------------------------------------------- |
| `--config PATH`   | Config file (default: `repos.json` next to this script).  |
| `--raw-dir PATH`  | Clone directory (default: `raw/`).                        |
| `--json-dir PATH` | Root for per-file JSON (default: `export`).               |
| `--no-clone`      | Use existing clones under `raw-dir` (must already exist). |
| `--limit N`       | Stop after **N** total records (testing).                 |

## Configuration (`repos.json`)

Top-level keys:

- **`schema_version`**: integer (currently `1`).
- **`default_lang`**: default `metadata.lang` (e.g. `"en"`).
- **`last_modified_mode`**: `"git"` (preferred: `git log -1 --format=%cI`) or `mtime` (filesystem).
- **`min_content_length`**: minimum characters after cleaning (short pages skipped).
- **`repos`**: array of repository entries.

Each repository entry:

| Field              | Description                                                                                  |
| ------------------ | -------------------------------------------------------------------------------------------- |
| `repo`             | `org/name` on GitHub.                                                                        |
| `ref`              | Branch, tag, or SHA (SHA uses shallow fetch).                                                |
| `slug`             | Directory name under `raw/` (default: `org_name`).                                           |
| `doc_roots`        | List of roots relative to repo root (e.g. `["docs"]` or `["."]`).                            |
| `include_globs`    | Gitwildmatch patterns; files must match at least one (default `**/*.md`).                    |
| `exclude_globs`    | Gitwildmatch patterns; matching paths are skipped.                                           |
| `content_keywords` | If non-empty, at least one keyword must appear in the first ~48k chars (optional narrowing). |
| `tags`             | Arbitrary key/value pairs merged into `metadata` (e.g. `category`, `ide`).                   |
| `lang`             | Overrides `default_lang` for this repo.                                                      |
| `max_files`        | Optional cap on files processed per repo (after sorting paths).                              |

## Record schema

Each JSON file is one object:

```json
{
  "page_content": "<markdown body, cleaned>",
  "metadata": {
    "url": "https://github.com/org/repo/blob/<sha>/path/to/file.md",
    "doc_id": "<same as url>",
    "type": "github-markdown",
    "repo": "org/repo",
    "commit": "<sha>",
    "relpath": "path/to/file.md",
    "source": "github",
    "lang": "en",
    "last_modified": "2025-11-25T00:27:27+11:00",
    "product_version": null
  }
}
```

- **`url` / `doc_id`**: Canonical GitHub **blob** URL at the resolved **`commit`** (stable links).
- **`last_modified`**: From `git log` when `last_modified_mode` is `git`; falls back to file mtime if Git returns nothing.
- **`product_version`**: Best-effort from path segments (e.g. `vs-2022`, `2024.1`); `null` if unknown.

Extra keys from `tags` appear in `metadata`.

## Adding IDE / large doc repos

1. Copy lines from `repos.example.json` into `repos.json`, or merge manually.
2. Large repos (e.g. `microsoft/vscode-docs`) may take a long time to clone; use `--limit` while testing.
3. Re-run `python export_github_docs.py` to refresh clones and regenerate outputs.

## Pinecone

**Out of scope here.** The consuming project loads JSON (or batches files) and handles embeddings / Pinecone upsert.

## Licensing

Respect each upstream repository’s license before redistributing or indexing content.
