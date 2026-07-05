#!/usr/bin/env python3
"""Build the GlobalGrid2050 kernel registry.

The registry is a complete versioned snapshot, not a diff. This script never edits
an existing registry_vNNNN.json. It writes the next number, regenerates
registry.md from the JSON, and then updates latest.json only after validation.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OWNER = "Ventusltd"
REPOS = [
    "data_uk_dno_and_tso",
    "data-federation-map-for-globalgrid2050-all-repos",
    "globalgrid2050",
    "spiders",
    "data-gb-electricity",
    "registry_of_all_content_in_repos_and_dependencies",
]

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = ROOT / "registry"
RECEIPTS_DIR = REGISTRY_DIR / "receipts"
SCHEMA_VERSION = "globalgrid2050.kernel_registry.v1"
API_ROOT = "https://api.github.com"

BINARY_EXTENSIONS = {
    ".7z", ".avif", ".bmp", ".doc", ".docx", ".eot", ".gif", ".gz", ".ico",
    ".jpeg", ".jpg", ".otf", ".parquet", ".pdf", ".png", ".ppt", ".pptx",
    ".sqlite", ".sqlite3", ".tar", ".tif", ".tiff", ".ttf", ".webp", ".woff",
    ".woff2", ".xls", ".xlsm", ".xlsx", ".zip",
}

TEXT_EXTENSIONS = {
    "", ".csv", ".css", ".geojson", ".gitignore", ".html", ".js", ".json",
    ".md", ".py", ".txt", ".ts", ".tsx", ".yml", ".yaml", ".xml",
}

ROLE_BY_REPO = {
    "data_uk_dno_and_tso": "UK and Ireland DNO/TSO declared data spine",
    "data-federation-map-for-globalgrid2050-all-repos": "federation node and edge control ledger",
    "globalgrid2050": "retiring monolith, atlas and application source",
    "spiders": "spider species lab and topology viewers",
    "data-gb-electricity": "GB electricity time-series Parquet data layer",
    "registry_of_all_content_in_repos_and_dependencies": "authoritative kernel registry of repo contents and dependencies",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def github_headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "globalgrid2050-kernel-registry",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def api_get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=github_headers())
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {url}: {body[:500]}") from exc


def repo_api(repo: str) -> str:
    return f"{API_ROOT}/repos/{OWNER}/{repo}"


def repo_html(repo: str) -> str:
    return f"https://github.com/{OWNER}/{repo}"


def blob_url(repo: str, branch: str, path: str) -> str:
    return f"https://github.com/{OWNER}/{repo}/blob/{branch}/{path}"


def raw_url(repo: str, branch: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{OWNER}/{repo}/{branch}/{path}"


def classify_type(path: str) -> str:
    lower = path.lower()
    suffix = Path(lower).suffix
    if suffix in BINARY_EXTENSIONS:
        return "binary"
    if lower.endswith(".schema.json"):
        return "schema"
    if "/workflows/" in lower or lower.startswith(".github/workflows/"):
        return "workflow"
    if lower.endswith(".geojson"):
        return "geojson"
    if suffix == ".json":
        return "json"
    if suffix in {".md", ".txt"}:
        return "document"
    if suffix in {".py", ".js", ".ts", ".tsx"}:
        return "code"
    if suffix in {".csv"}:
        return "tabular"
    if suffix in {".html", ".css"}:
        return "web"
    return "file"


def classify_role(path: str) -> str:
    lower = path.lower()
    name = Path(lower).name
    if name == "readme.md":
        return "human entry point"
    if name in {"anchor_ai_must_read.md", "federation.yaml"}:
        return "AI boot and federation manifest"
    if "data_contract" in lower or lower.endswith(".schema.json"):
        return "data contract or schema"
    if "data_sources" in lower or "sources.json" in lower:
        return "source registry"
    if lower.startswith(".github/workflows/"):
        return "automation workflow"
    if lower.startswith("registry/"):
        return "kernel registry artifact"
    if lower.startswith("scripts/") or "/scripts/" in lower:
        return "builder or automation script"
    if lower.startswith("data/") or "/data/" in lower:
        return "data artifact"
    if lower.startswith("docs/") or "/docs/" in lower:
        return "documentation"
    if lower.endswith("index.html"):
        return "web entry point"
    if lower.endswith(".geojson"):
        return "geospatial layer"
    if lower.endswith(".parquet"):
        return "Parquet data product"
    return "repository content"


def classify_state(path: str, tree_item: dict[str, Any]) -> str:
    if Path(path.lower()).suffix in BINARY_EXTENSIONS:
        return "binary"
    if tree_item.get("type") != "blob":
        return "unreachable"
    return "verified"


def fetch_repo_tree(repo: str) -> dict[str, Any]:
    meta = api_get_json(repo_api(repo))
    default_branch = meta.get("default_branch")
    if not default_branch:
        raise RuntimeError(f"No default branch detected for {repo}")
    tree = api_get_json(f"{repo_api(repo)}/git/trees/{default_branch}?recursive=1")
    if "tree" not in tree or not isinstance(tree["tree"], list):
        raise RuntimeError(f"Tree response missing tree array for {repo}")
    files = []
    for item in tree["tree"]:
        if item.get("type") != "blob":
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path:
            continue
        files.append(
            {
                "path": path,
                "github_url": blob_url(repo, default_branch, path),
                "raw_url": raw_url(repo, default_branch, path),
                "type": classify_type(path),
                "role": classify_role(path),
                "state": classify_state(path, item),
            }
        )
    files.sort(key=lambda f: f["path"].lower())
    return {
        "name": repo,
        "html_url": meta.get("html_url") or repo_html(repo),
        "api_url": meta.get("url") or repo_api(repo),
        "default_branch": default_branch,
        "role": ROLE_BY_REPO.get(repo, "GlobalGrid2050 federation repository"),
        "file_count": len(files),
        "files": files,
    }


def boot_sequence() -> list[dict[str, str]]:
    return [
        {"repo": "data-federation-map-for-globalgrid2050-all-repos", "path": "anchor_AI_MUST_READ.md", "reason": "AI boot doctrine"},
        {"repo": "data-federation-map-for-globalgrid2050-all-repos", "path": "federation.yaml", "reason": "machine federation manifest"},
        {"repo": "data-federation-map-for-globalgrid2050-all-repos", "path": "DATA_CONTRACT.md", "reason": "node and edge contract"},
        {"repo": "data-federation-map-for-globalgrid2050-all-repos", "path": "IMPLEMENTATION.md", "reason": "scanner implementation description"},
        {"repo": "data-federation-map-for-globalgrid2050-all-repos", "path": "scripts/build_federation_map.py", "reason": "scanner source of truth"},
        {"repo": "registry_of_all_content_in_repos_and_dependencies", "path": "registry/latest.json", "reason": "authoritative registry pointer"},
        {"repo": "data_uk_dno_and_tso", "path": "README.md", "reason": "DNO/TSO spine discipline"},
        {"repo": "data_uk_dno_and_tso", "path": "config/sources.json", "reason": "DNO/TSO source registry"},
        {"repo": "data-gb-electricity", "path": "README.md", "reason": "GB electricity data law"},
        {"repo": "globalgrid2050", "path": "ARCHITECTURE.md", "reason": "monolith and platform architecture"},
        {"repo": "spiders", "path": "README.md", "reason": "spider species operating law"},
    ]


def existing_versions() -> list[int]:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    versions = []
    for path in REGISTRY_DIR.glob("registry_v*.json"):
        match = re.fullmatch(r"registry_v(\d{4})\.json", path.name)
        if match:
            versions.append(int(match.group(1)))
    return sorted(versions)


def read_latest() -> dict[str, Any] | None:
    latest = REGISTRY_DIR / "latest.json"
    if not latest.exists():
        return None
    return json.loads(latest.read_text(encoding="utf-8"))


def next_version() -> int:
    versions = existing_versions()
    return (versions[-1] + 1) if versions else 1


def assemble_registry(version: int) -> dict[str, Any]:
    repos = []
    for repo in sorted(REPOS, key=str.lower):
        repos.append(fetch_repo_tree(repo))
        time.sleep(0.1)
    file_count = sum(repo["file_count"] for repo in repos)
    reachable_count = sum(1 for repo in repos for file in repo["files"] if file["state"] in {"verified", "declared", "binary"})
    unreachable_count = sum(1 for repo in repos for file in repo["files"] if file["state"] == "unreachable")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "registry_version": version,
        "boot_sequence": boot_sequence(),
        "totals": {
            "repo_count": len(repos),
            "file_count": file_count,
            "reachable_count": reachable_count,
            "unreachable_count": unreachable_count,
        },
        "repos": repos,
    }


def validate_registry(registry: dict[str, Any], expected_version: int) -> None:
    if registry.get("registry_version") != expected_version:
        raise RuntimeError("registry_version does not match filename version")
    repos = registry.get("repos")
    if not isinstance(repos, list) or not repos:
        raise RuntimeError("registry contains no repos")
    if any(not repo.get("files") for repo in repos):
        empty = [repo.get("name", "<unknown>") for repo in repos if not repo.get("files")]
        raise RuntimeError(f"repo block empty: {empty}")
    actual_file_count = sum(len(repo.get("files", [])) for repo in repos)
    if registry.get("totals", {}).get("file_count") != actual_file_count:
        raise RuntimeError("file_count does not equal actual file entries")
    if registry.get("totals", {}).get("repo_count") != len(repos):
        raise RuntimeError("repo_count does not equal actual repo entries")
    encoded = json.dumps(registry, indent=2, sort_keys=True)
    json.loads(encoded)


def render_markdown(registry: dict[str, Any]) -> str:
    totals = registry["totals"]
    version = int(registry["registry_version"])
    lines = [
        "# GlobalGrid2050 Kernel Registry",
        "",
        "This file is generated from the authoritative JSON snapshot. Do not edit it by hand.",
        "",
        f"Authoritative version: `{version:04d}`",
        f"Generated at: `{registry['generated_at']}`",
        "",
        "## Totals",
        "",
        f"- Repositories: {totals['repo_count']}",
        f"- Files: {totals['file_count']}",
        f"- Reachable: {totals['reachable_count']}",
        f"- Unreachable: {totals['unreachable_count']}",
        "",
        "## Boot sequence",
        "",
    ]
    for item in registry["boot_sequence"]:
        repo = item["repo"]
        path = item["path"]
        url = f"https://github.com/{OWNER}/{repo}/blob/HEAD/{path}"
        lines.append(f"- [{repo}/{path}]({url}) — {item['reason']}")
    lines.extend(["", "## Repositories", ""])
    for repo in registry["repos"]:
        lines.extend([
            f"### [{repo['name']}]({repo['html_url']})",
            "",
            f"Role: {repo['role']}",
            "",
            f"Default branch: `{repo['default_branch']}`",
            "",
            f"File count: {repo['file_count']}",
            "",
            "| State | Type | Path | Role |",
            "|---|---|---|---|",
        ])
        for file in repo["files"]:
            state = file["state"]
            ftype = file["type"]
            path = file["path"]
            role = file["role"]
            lines.append(f"| {state} | {ftype} | [{path}]({file['github_url']}) | {role} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_registry(registry: dict[str, Any], version: int) -> None:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REGISTRY_DIR / f"registry_v{version:04d}.json"
    if json_path.exists():
        raise RuntimeError(f"Refusing to overwrite existing {json_path}")
    validate_registry(registry, version)
    json_text = json.dumps(registry, indent=2, sort_keys=True) + "\n"
    md_text = render_markdown(registry)
    tmp_json = REGISTRY_DIR / f"registry_v{version:04d}.json.tmp"
    tmp_json.write_text(json_text, encoding="utf-8")
    json.loads(tmp_json.read_text(encoding="utf-8"))
    tmp_json.replace(json_path)
    md_path = REGISTRY_DIR / "registry.md"
    md_path.write_text(md_text, encoding="utf-8")
    latest = {
        "authoritative_version": version,
        "json_path": f"registry/registry_v{version:04d}.json",
        "md_path": "registry/registry.md",
        "updated_at": registry["generated_at"],
    }
    (REGISTRY_DIR / "latest.json").write_text(json.dumps(latest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    version = next_version()
    registry = assemble_registry(version)
    write_registry(registry, version)
    print(f"Wrote registry_v{version:04d}.json with {registry['totals']['file_count']} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
