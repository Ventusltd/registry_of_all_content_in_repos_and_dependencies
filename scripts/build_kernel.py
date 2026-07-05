#!/usr/bin/env python3
"""Build compact registry/kernel.json from the authoritative registry snapshot."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry"
IMPORTANT_NAMES = {
    "README.md",
    "ARCHITECTURE.md",
    "federation.yaml",
    "DATA_CONTRACT.md",
    "DATA_SOURCES.md",
    "DEPENDENCIES.md",
    "IMPLEMENTATION.md",
    "anchor_AI_MUST_READ.md",
    "latest.json",
    "sources.json",
    "index.html",
}


def important(path: str) -> bool:
    lower = path.lower()
    name = Path(path).name
    return name in IMPORTANT_NAMES or lower.startswith(".github/workflows/") or lower.endswith(".schema.json")


def main() -> int:
    latest = json.loads((REGISTRY / "latest.json").read_text(encoding="utf-8"))
    registry = json.loads((ROOT / latest["json_path"]).read_text(encoding="utf-8"))
    repos = []
    for repo in registry["repos"]:
        repos.append({
            "name": repo["name"],
            "html_url": repo["html_url"],
            "default_branch": repo["default_branch"],
            "role": repo["role"],
            "file_count": repo["file_count"],
            "important_files": [f for f in repo["files"] if important(f["path"])],
        })
    kernel = {
        "schema_version": "globalgrid2050.kernel_boot.v1",
        "generated_at": registry["generated_at"],
        "registry_version": registry["registry_version"],
        "source_registry": latest["json_path"],
        "boot_sequence": registry["boot_sequence"],
        "totals": registry["totals"],
        "repos": repos,
    }
    (REGISTRY / "kernel.json").write_text(json.dumps(kernel, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Wrote registry/kernel.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
