#!/usr/bin/env python3
"""Create registry/graph_latest.json for Spider Printer from registry/latest.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry"

LAYERS = [
    {"id": "data", "label": "Data and registry repositories", "defaultOn": True},
    {"id": "engines", "label": "Engines and topology tools", "defaultOn": True},
    {"id": "apps", "label": "Applications and dashboards", "defaultOn": True},
    {"id": "libs", "label": "Important files", "defaultOn": True},
    {"id": "schemas", "label": "Workflows and contracts", "defaultOn": True},
    {"id": "infra", "label": "Infrastructure and platforms", "defaultOn": True},
    {"id": "external", "label": "External authorities", "defaultOn": False},
    {"id": "future", "label": "Future cartridges", "defaultOn": True},
]

EDGE_TYPES = {
    "raw_flow": {"label": "Data flow raw", "layer": "data", "colour": "#46ff63", "dash": ""},
    "derived_flow": {"label": "Data flow derived", "layer": "data", "colour": "#3ee7ff", "dash": "8 8"},
    "dependency": {"label": "Dependency / uses", "layer": "engines", "colour": "#3385ff", "dash": ""},
    "provides": {"label": "Provides / exposes", "layer": "apps", "colour": "#b35cff", "dash": ""},
    "federation": {"label": "Kernel registry record", "layer": "engines", "colour": "#ffb000", "dash": "12 8"},
    "schema": {"label": "Schema / contract", "layer": "schemas", "colour": "#ff4b4b", "dash": ""},
    "api": {"label": "API integration", "layer": "external", "colour": "#10e0c4", "dash": ""},
    "reference": {"label": "Repo contains file", "layer": "libs", "colour": "#d8dde8", "dash": "4 7"},
}


def repo_kind(name: str) -> str:
    if name.startswith("data") or name.startswith("registry"):
        return "data"
    if name == "spiders":
        return "engine"
    if name == "globalgrid2050":
        return "app"
    return "future"


def repo_layer(name: str) -> str:
    if name.startswith("data") or name.startswith("registry"):
        return "data"
    if name == "spiders":
        return "engines"
    if name == "globalgrid2050":
        return "apps"
    return "future"


def key_files(files: list[dict]) -> list[dict]:
    chosen = []
    names = {
        "README.md",
        "ARCHITECTURE.md",
        "federation.yaml",
        "DATA_CONTRACT.md",
        "IMPLEMENTATION.md",
        "DEPENDENCIES.md",
        "anchor_AI_MUST_READ.md",
    }
    for item in files:
        path = item["path"]
        lower = path.lower()
        if path in names or lower.endswith("latest.json") or lower.endswith("sources.json") or lower.endswith("index.html") or lower.startswith(".github/workflows/"):
            chosen.append(item)
    return chosen[:10]


def main() -> int:
    latest = json.loads((REGISTRY / "latest.json").read_text(encoding="utf-8"))
    registry_path = ROOT / latest["json_path"]
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    nodes = []
    edges = []
    start_x = 280
    spacing = 420
    repo_y = 300
    file_y = 1180

    for idx, repo in enumerate(registry["repos"]):
        rid = f"repo::{repo['name']}"
        nodes.append({
            "id": rid,
            "label": repo["name"],
            "subtitle": f"{repo['file_count']} files · {repo['default_branch']}",
            "kind": repo_kind(repo["name"]),
            "layer": repo_layer(repo["name"]),
            "x": start_x + idx * spacing,
            "y": repo_y,
            "source": repo["html_url"],
        })
        for fidx, item in enumerate(key_files(repo["files"])):
            fid = f"file::{repo['name']}::{item['path']}"
            nodes.append({
                "id": fid,
                "label": Path(item["path"]).name[:28],
                "subtitle": item["role"][:42],
                "kind": "schema" if item["type"] in {"schema", "workflow"} else "library",
                "layer": "schemas" if item["type"] in {"schema", "workflow"} else "libs",
                "x": start_x + idx * spacing,
                "y": file_y + fidx * 120,
                "source": item["github_url"],
            })
            edges.append({"from": rid, "to": fid, "type": "reference"})

    registry_node = "repo::registry_of_all_content_in_repos_and_dependencies"
    for repo in registry["repos"]:
        rid = f"repo::{repo['name']}"
        if rid != registry_node:
            edges.append({"from": registry_node, "to": rid, "type": "federation"})

    graph = {
        "schemaVersion": "globalgrid2050.spider_printer_graph.v1",
        "species": "spider_printer_v1",
        "title": "GlobalGrid2050 Kernel Registry Graph",
        "methodState": "screening",
        "mapType": "registry_driven_topological_sld_not_geospatial",
        "dataSource": {
            "repo": "Ventusltd/registry_of_all_content_in_repos_and_dependencies",
            "registryVersion": registry["registry_version"],
            "jsonPath": latest["json_path"],
            "generatedAt": registry["generated_at"],
        },
        "canvas": {"width": 4200, "height": 2600, "print": "A1 landscape"},
        "principles": ["Boot from the kernel registry", "Render recorded repo and file truth", "Fallback to static topology if unavailable"],
        "layers": LAYERS,
        "edgeTypes": EDGE_TYPES,
        "nodes": nodes,
        "edges": edges,
    }
    out = REGISTRY / "graph_latest.json"
    out.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {out} from {latest['json_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
