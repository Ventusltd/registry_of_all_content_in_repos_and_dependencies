#!/usr/bin/env python3
"""Reconcile the registry using config/registry_repos.json."""
from __future__ import annotations

import json
from pathlib import Path

import build_registry
import reconcile_registry

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "registry_repos.json"


def load_scope() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    repos = cfg.get("repos", [])
    if not repos:
        raise RuntimeError("config/registry_repos.json has no repos")
    names = [item["name"] for item in repos]
    build_registry.REPOS = names
    reconcile_registry.build_registry.REPOS = names
    for item in repos:
        role = item.get("role", "GlobalGrid2050 federation repository")
        build_registry.ROLE_BY_REPO[item["name"]] = role
        reconcile_registry.build_registry.ROLE_BY_REPO[item["name"]] = role


def main() -> int:
    load_scope()
    return reconcile_registry.main()


if __name__ == "__main__":
    raise SystemExit(main())
