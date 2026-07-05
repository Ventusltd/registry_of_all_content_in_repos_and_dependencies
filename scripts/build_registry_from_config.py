#!/usr/bin/env python3
"""Build the registry using config/registry_repos.json instead of the legacy hardcoded scope."""
from __future__ import annotations

import json
from pathlib import Path

import build_registry

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "registry_repos.json"


def load_scope() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    repos = cfg.get("repos", [])
    if not repos:
        raise RuntimeError("config/registry_repos.json has no repos")
    build_registry.REPOS = [item["name"] for item in repos]
    for item in repos:
        build_registry.ROLE_BY_REPO[item["name"]] = item.get("role", "GlobalGrid2050 federation repository")


def main() -> int:
    load_scope()
    return build_registry.main()


if __name__ == "__main__":
    raise SystemExit(main())
