#!/usr/bin/env python3
"""Validate the registry pointer, kernel export, and graph export.

This is a non-mutating safety gate. It does not crawl GitHub and it does not write
new registry versions. It proves the current committed BIOS/kernel outputs are
internally consistent before Spider Printer or other applications boot from them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = ROOT / "registry"


def fail(message: str) -> None:
    raise RuntimeError(message)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"Missing required file: {path.relative_to(ROOT)}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}")
    if not isinstance(data, dict):
        fail(f"Expected object at top level: {path.relative_to(ROOT)}")
    return data


def rel(path_str: str) -> Path:
    path = ROOT / path_str
    try:
        path.relative_to(ROOT)
    except ValueError:
        fail(f"Pointer escapes repository root: {path_str}")
    return path


def validate_registry(latest: dict[str, Any]) -> dict[str, Any]:
    for key in ["authoritative_version", "json_path", "md_path", "graph_path", "kernel_path"]:
        if key not in latest:
            fail(f"latest.json missing key: {key}")
    version = latest["authoritative_version"]
    if not isinstance(version, int) or version < 1:
        fail("latest.json authoritative_version must be a positive integer")
    expected_json = f"registry/registry_v{version:04d}.json"
    if latest["json_path"] != expected_json:
        fail(f"latest.json json_path should be {expected_json}, got {latest['json_path']}")
    registry = read_json(rel(latest["json_path"]))
    if registry.get("registry_version") != version:
        fail("registry_vNNNN.json registry_version does not match latest.json")
    totals = registry.get("totals", {})
    repos = registry.get("repos", [])
    if not isinstance(repos, list) or not repos:
        fail("registry contains no repos")
    actual_files = sum(len(repo.get("files", [])) for repo in repos)
    if totals.get("repo_count") != len(repos):
        fail("registry repo_count does not match actual repo entries")
    if totals.get("file_count") != actual_files:
        fail("registry file_count does not match actual file entries")
    if any(not repo.get("files") for repo in repos):
        empty = [repo.get("name", "<unknown>") for repo in repos if not repo.get("files")]
        fail(f"registry contains empty repo blocks: {empty}")
    if not rel(latest["md_path"]).exists():
        fail("registry.md pointer target is missing")
    return registry


def validate_kernel(latest: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    kernel = read_json(rel(latest["kernel_path"]))
    if kernel.get("registry_version") != registry.get("registry_version"):
        fail("kernel.json registry_version does not match authoritative registry")
    if kernel.get("source_registry") != latest.get("json_path"):
        fail("kernel.json source_registry does not match latest.json json_path")
    if not kernel.get("boot_sequence"):
        fail("kernel.json boot_sequence is empty")
    if not kernel.get("repos"):
        fail("kernel.json repos is empty")
    return kernel


def validate_graph(latest: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    graph = read_json(rel(latest["graph_path"]))
    data_source = graph.get("dataSource", {})
    if data_source.get("registryVersion") != registry.get("registry_version"):
        fail("graph_latest.json registryVersion does not match authoritative registry")
    if data_source.get("jsonPath") != latest.get("json_path"):
        fail("graph_latest.json jsonPath does not match latest.json json_path")
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if not isinstance(nodes, list) or not nodes:
        fail("graph_latest.json nodes is empty")
    if not isinstance(edges, list) or not edges:
        fail("graph_latest.json edges is empty")
    node_ids = {node.get("id") for node in nodes}
    if None in node_ids:
        fail("graph_latest.json contains a node without an id")
    dangling = []
    for edge in edges:
        if edge.get("from") not in node_ids or edge.get("to") not in node_ids:
            dangling.append(edge)
    if dangling:
        fail(f"graph_latest.json contains dangling edges: {dangling[:5]}")
    return graph


def main() -> int:
    latest = read_json(REGISTRY_DIR / "latest.json")
    registry = validate_registry(latest)
    kernel = validate_kernel(latest, registry)
    graph = validate_graph(latest, registry)
    print(
        "Kernel outputs OK:",
        f"registry_v{registry['registry_version']:04d}",
        f"repos={registry['totals']['repo_count']}",
        f"files={registry['totals']['file_count']}",
        f"kernel_repos={len(kernel['repos'])}",
        f"graph_nodes={len(graph['nodes'])}",
        f"graph_edges={len(graph['edges'])}",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Kernel output validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
