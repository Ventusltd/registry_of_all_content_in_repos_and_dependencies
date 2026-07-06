#!/usr/bin/env python3
"""Reconcile the authoritative registry against live GitHub repo trees."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import build_registry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = ROOT / "registry"
RECEIPTS_DIR = REGISTRY_DIR / "receipts"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_receipt(kind: str, payload: dict) -> Path:
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().replace(":", "").replace("-", "")
    path = RECEIPTS_DIR / f"{stamp}_{kind}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def latest_pointer() -> dict:
    path = REGISTRY_DIR / "latest.json"
    if not path.exists():
        raise RuntimeError("registry/latest.json missing")
    return json.loads(path.read_text(encoding="utf-8"))


def authoritative_registry() -> dict:
    latest = latest_pointer()
    json_path = ROOT / latest["json_path"]
    return json.loads(json_path.read_text(encoding="utf-8"))


def count_live() -> dict:
    repos = []
    for repo_name in sorted(build_registry.REPOS, key=str.lower):
        repo = build_registry.fetch_repo_tree(repo_name)
        repos.append({"name": repo_name, "file_count": repo["file_count"]})
    return {
        "repo_count": len(repos),
        "file_count": sum(repo["file_count"] for repo in repos),
        "repos": repos,
    }


def run_builder(reason: str, before: dict | None, live: dict | None) -> None:
    payload = {
        "status": "builder_invoked",
        "reason": reason,
        "before": before,
        "live": live,
        "generated_at": utc_now(),
    }
    receipt = write_receipt("reconcile_trigger", payload)
    print(f"Registry reconciliation invoking builder: {reason}; receipt={receipt}")
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "build_registry.py")])


def main() -> int:
    build_registry.apply_config_scope()
    try:
        current = authoritative_registry()
    except Exception as exc:
        run_builder(f"authoritative registry unreadable: {exc}", None, None)
        return 0

    before = current.get("totals", {})
    if before.get("repo_count", 0) < 1 or before.get("file_count", 0) < 1:
        run_builder("authoritative registry count collapsed toward zero", before, None)
        return 0

    live = count_live()
    if before.get("repo_count") == live.get("repo_count") and before.get("file_count") == live.get("file_count"):
        receipt = write_receipt(
            "heartbeat",
            {
                "status": "ok_no_change",
                "generated_at": utc_now(),
                "authoritative_totals": before,
                "live_totals": live,
            },
        )
        print(f"Registry heartbeat OK: {receipt}")
        return 0

    run_builder("live counts differ from authoritative registry", before, live)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
