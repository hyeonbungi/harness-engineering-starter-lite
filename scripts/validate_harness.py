#!/usr/bin/env python3

"""Validate the starter's dependency-free control plane."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePath


ROOT = Path(__file__).resolve().parent.parent
REQUIRED_FILES = (
    "template/core/.agents/skills/audit-harness-health/SKILL.md",
    "template/core/.claude/skills/audit-harness-health/SKILL.md",
    "AGENTS.md",
    "CLAUDE.md",
    "LICENSE",
    "NOTICE",
    "README.md",
    "VERSION",
    "feature_list.json",
    "init.ps1",
    "docs/STATE.md",
    "docs/source-inventory.md",
    "docs/source-analysis.md",
    "docs/source-disposition.md",
    "docs/design-proposal.md",
    "scripts/install_core.py",
    "template/core/AGENTS.md",
    "template/core/CLAUDE.md",
    "template/core/LICENSE",
    "template/core/NOTICE",
    "template/core/VERSION",
    "template/core/harness.config.json",
    "template/core/feature_list.json",
    "template/core/init.sh",
    "template/core/init.ps1",
    "template/core/scripts/harness.py",
    "template/core/docs/STATE.md",
    "template/core/docs/ARCHITECTURE.md",
    "template/core/docs/COMMUNICATION.md",
    "template/core/docs/VALIDATION.md",
    "template/core/docs/harness/ADOPTION.md",
    "template/core/docs/harness/LIFECYCLE.md",
    "template/core/docs/harness/components.json",
    "template/core/docs/harness/source-map.json",
    "template/core/docs/harness/SOURCES.md",
    "tests/test_core_profile.py",
)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def portable_relative_path(path: PurePath, root: PurePath) -> str:
    return path.relative_to(root).as_posix()


def validate_required_files() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    if missing:
        fail(
            "required starter artifacts are missing: "
            + ", ".join(missing)
            + ". Restore them before continuing."
        )


def validate_claude_entrypoint(path: Path) -> None:
    try:
        lines = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError as exc:
        fail(f"cannot read {path.relative_to(ROOT)}: {exc}")
    if not lines or lines[0] != "@AGENTS.md":
        fail(
            f"{path.relative_to(ROOT)} must begin with a standalone @AGENTS.md "
            "import so shared instructions have one source of truth."
        )


def expand_source_reference(reference: str, known: set[str]) -> list[str]:
    match = re.fullmatch(r"(SRC-[A-Z]+-)(\d+)(?:\.\.(\d+))?", reference)
    if not match:
        fail(f"invalid source reference syntax: {reference!r}")
    prefix, start_text, end_text = match.groups()
    start = int(start_text)
    end = int(end_text) if end_text is not None else start
    if end < start:
        fail(f"reversed source range: {reference}")
    width = len(start_text)
    expanded = [f"{prefix}{value:0{width}d}" for value in range(start, end + 1)]
    missing = [source_id for source_id in expanded if source_id not in known]
    if missing:
        fail(f"{reference} includes unknown source IDs: {', '.join(missing)}")
    return expanded


def validate_source_traceability() -> tuple[set[str], bool]:
    inventory_path = ROOT / "docs/source-inventory.md"
    inventory_text = inventory_path.read_text(encoding="utf-8")
    inventory_rows = re.findall(
        r"^\| (SRC-[^ |]+) \| `([^`]+)` \| ([0-9,]+) \| "
        r"`([0-9a-f]{12})` \| ([^|]+) \|$",
        inventory_text,
        re.MULTILINE,
    )
    if len(inventory_rows) != 65:
        fail(
            "docs/source-inventory.md must contain exactly 65 rows with 12-character hashes."
        )
    inventory: dict[str, dict[str, object]] = {}
    for source_id, path, size_text, digest, role in inventory_rows:
        if source_id in inventory:
            fail(f"duplicate source inventory ID: {source_id}")
        inventory[source_id] = {
            "path": path,
            "size": int(size_text.replace(",", "")),
            "sha256": digest,
            "role": role.strip(),
        }

    disposition_text = (ROOT / "docs/source-disposition.md").read_text(encoding="utf-8")
    disposition_rows = re.findall(
        r"^\| (SRC-[^ |]+) \| `([^`]+)` \| "
        r"(core-direct|merged|deferred|reference-only) \| "
        r"([^|]+) \| ([^|]+) \| ([^|]+) \|$",
        disposition_text,
        re.MULTILINE,
    )
    if len(disposition_rows) != 65:
        fail("docs/source-disposition.md must contain exactly 65 disposition rows.")
    disposition = {
        source_id: {
            "path": path,
            "disposition": decision,
            "components": [
                item.strip() for item in targets.split(",") if item.strip()
            ],
        }
        for source_id, path, decision, _principle, targets, _rationale in disposition_rows
    }
    if set(disposition) != set(inventory):
        fail("source disposition IDs do not exactly match the inventory.")
    for source_id, decision in disposition.items():
        if decision["path"] != inventory[source_id]["path"]:
            fail(f"{source_id} disposition path disagrees with the inventory.")
        if not decision["components"]:
            fail(f"{source_id} disposition must name at least one linked target.")

    source_map = json.loads(
        (ROOT / "template/core/docs/harness/source-map.json").read_text(
            encoding="utf-8"
        )
    )
    link_semantics = source_map.get("link_semantics")
    if not isinstance(link_semantics, dict) or any(
        not isinstance(link_semantics.get(field), str)
        or not link_semantics[field].strip()
        for field in ("source_components", "component_sources")
    ):
        fail("Core source-map.json must declare both traceability link semantics.")
    sources = source_map.get("sources")
    if (
        source_map.get("schema_version") != 1
        or source_map.get("source_count") != 65
        or not isinstance(sources, list)
        or len(sources) != 65
    ):
        fail("Core source-map.json must contain exactly 65 schema-v1 sources.")
    mapped: dict[str, dict[str, object]] = {}
    for source in sources:
        if not isinstance(source, dict):
            fail("Core source-map entries must be objects.")
        source_id = source.get("id")
        if not isinstance(source_id, str) or source_id in mapped:
            fail(f"invalid or duplicate Core source-map ID: {source_id!r}")
        mapped[source_id] = source
    if set(mapped) != set(inventory):
        fail("Core source-map IDs do not exactly match the inventory.")
    for source_id, source in mapped.items():
        if source.get("path") != inventory[source_id]["path"]:
            fail(f"{source_id} source-map path disagrees with the inventory.")
        if source.get("role") != inventory[source_id]["role"]:
            fail(f"{source_id} source-map role disagrees with the inventory.")
        if source.get("disposition") != disposition[source_id]["disposition"]:
            fail(f"{source_id} source-map disposition disagrees with the decision table.")
        if source.get("components") != disposition[source_id]["components"]:
            fail(f"{source_id} source-map targets disagree with the decision table.")
        if (
            source.get("disposition")
            not in {"core-direct", "merged", "deferred", "reference-only"}
            or not isinstance(source.get("rationale"), str)
            or not source["rationale"].strip()
            or not isinstance(source.get("components"), list)
            or not source["components"]
        ):
            fail(f"{source_id} has an incomplete source-map disposition.")

    source_root_value = os.environ.get("HARNESS_ENGINEERING_SOURCE_ROOT")
    root_match = re.search(r"^- 원본 루트: `([^`]+)`$", inventory_text, re.MULTILINE)
    source_live = False
    if source_root_value or root_match:
        source_root = Path(
            source_root_value if source_root_value else root_match.group(1)
        ).expanduser()
        if source_root_value and not source_root.is_dir():
            fail(
                "HARNESS_ENGINEERING_SOURCE_ROOT must point to the readable "
                "Learn Harness Engineering corpus."
            )
        if source_root.is_dir():
            source_live = True
            actual = {
                path.relative_to(source_root).as_posix(): path
                for path in source_root.rglob("*")
                if path.is_file()
            }
            expected_paths = {
                item["path"]: (item["size"], item["sha256"])
                for item in inventory.values()
            }
            if set(actual) != set(expected_paths):
                fail("the live source corpus paths no longer match the 65-row inventory.")
            for relative, path in actual.items():
                expected_size, expected_digest = expected_paths[relative]
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if path.stat().st_size != expected_size or not digest.startswith(
                    expected_digest
                ):
                    fail(f"live source corpus metadata changed: {relative}")
    return set(inventory), source_live


def validate_feature_list(source_ids: set[str]) -> None:
    path = ROOT / "feature_list.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"{path.name} is not readable valid JSON: {exc}")

    legend = data.get("status_legend")
    if not isinstance(legend, dict) or not legend:
        fail(
            "feature_list.json must declare a non-empty status_legend; "
            "do not assume an implicit state machine."
        )

    rules = data.get("rules")
    features = data.get("features")
    if not isinstance(rules, dict):
        fail("feature_list.json rules must be an object.")
    if not isinstance(features, list):
        fail("feature_list.json features must be an array.")

    ids: set[str] = set()
    active = 0
    allowed = set(legend)
    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            fail(f"feature #{index + 1} must be an object.")
        feature_id = feature.get("id")
        if not isinstance(feature_id, str) or not feature_id:
            fail(f"feature #{index + 1} has no stable id.")
        if feature_id in ids:
            fail(f"duplicate feature id: {feature_id}")
        ids.add(feature_id)

        status = feature.get("status")
        if status not in allowed:
            fail(f"{feature_id} uses undeclared status {status!r}.")
        if status == "active":
            active += 1
        if status == "passing" and rules.get("passing_requires_evidence"):
            evidence = feature.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                fail(
                    f"{feature_id} is passing without evidence. "
                    "Record runnable proof or demote the status."
                )

        verification = feature.get("verification")
        if not isinstance(verification, list) or not verification:
            fail(f"{feature_id} must declare verification.")
        sources = feature.get("sources")
        if not isinstance(sources, list) or not sources:
            fail(f"{feature_id} must declare traceable sources.")
        for source in sources:
            expand_source_reference(source, source_ids)

    maximum = rules.get("max_active_features")
    if not isinstance(maximum, int) or maximum < 0:
        fail("rules.max_active_features must be a non-negative integer.")
    if active > maximum:
        fail(
            f"{active} features are active but the WIP limit is {maximum}. "
            "Finish, block, or demote work before activating another feature."
        )


def validate_core_profile(source_ids: set[str]) -> None:
    core = ROOT / "template/core"
    config = json.loads((core / "harness.config.json").read_text(encoding="utf-8"))
    features = json.loads((core / "feature_list.json").read_text(encoding="utf-8"))
    components = json.loads(
        (core / "docs/harness/components.json").read_text(encoding="utf-8")
    )
    if config.get("schema_version") != 1 or config.get("configured") is not False:
        fail("Core distribution config must be schema v1 and explicitly unconfigured.")
    if features.get("schema_version") != 1:
        fail("Core distribution feature list must use schema v1.")

    root_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    core_version = (core / "VERSION").read_text(encoding="utf-8").strip()
    if root_version != core_version or not re.fullmatch(
        r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
        r"(?:-[0-9A-Za-z.-]+)?",
        core_version,
    ):
        fail("root and Core VERSION must match a valid Semantic Version.")
    for name in ("LICENSE", "NOTICE"):
        if (ROOT / name).read_bytes() != (core / name).read_bytes():
            fail(f"root and Core {name} must be byte-identical.")

    source_map = json.loads(
        (core / "docs/harness/source-map.json").read_text(encoding="utf-8")
    )
    source_by_id = {source["id"]: source for source in source_map["sources"]}
    component_ids: set[str] = set()
    directly_cited_source_ids: set[str] = set()
    tracked_paths: set[str] = set()
    for component in components.get("components", []):
        component_id = component.get("id")
        if not isinstance(component_id, str) or component_id in component_ids:
            fail(f"invalid or duplicate Core component id: {component_id!r}")
        component_ids.add(component_id)
        path = component.get("path")
        if not isinstance(path, str) or not (core / path).is_file():
            fail(f"{component_id} points to a missing Core file: {path!r}")
        tracked_paths.add(path)
        if component.get("profile") != "core":
            fail(f"{component_id}.profile must be core.")
        for field in ("purpose", "applies_when", "review_trigger", "rollback"):
            if not isinstance(component.get(field), str) or not component[field].strip():
                fail(f"{component_id}.{field} must be non-empty.")
        validation = component.get("validation")
        if not isinstance(validation, list) or not validation:
            fail(f"{component_id}.validation must be non-empty.")
        for source in component.get("sources", []):
            for source_id in expand_source_reference(source, source_ids):
                directly_cited_source_ids.add(source_id)
                if component_id not in source_by_id[source_id]["components"]:
                    fail(
                        f"{component_id} -> {source_id} lacks a source-map reverse link."
                    )

    uncited_core_direct = sorted(
        source_id
        for source_id, source in source_by_id.items()
        if source.get("disposition") == "core-direct"
        and source_id not in directly_cited_source_ids
    )
    if uncited_core_direct:
        fail(
            "Core-direct sources must appear in at least one component's direct "
            f"provenance: {uncited_core_direct}"
        )

    distributable_paths = {
        portable_relative_path(path, core)
        for path in core.rglob("*")
        if path.is_file()
    }
    if tracked_paths != distributable_paths:
        missing = sorted(distributable_paths - tracked_paths)
        stale = sorted(tracked_paths - distributable_paths)
        fail(
            "Core component ledger coverage mismatch. "
            f"Missing: {missing}; stale: {stale}"
        )
    for source_id, source in source_by_id.items():
        for reference in source["components"]:
            if reference.startswith("HC-") and reference not in component_ids:
                fail(f"{source_id} references unknown Core component {reference}.")

    result = subprocess.run(
        [sys.executable, "scripts/harness.py", "audit", "--template"],
        cwd=core,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        fail(
            "Core distribution self-audit failed:\n"
            + (result.stdout + result.stderr).strip()
        )


def main() -> None:
    validate_required_files()
    validate_claude_entrypoint(ROOT / "CLAUDE.md")
    validate_claude_entrypoint(ROOT / "template/core/CLAUDE.md")
    source_ids, source_live = validate_source_traceability()
    validate_feature_list(source_ids)
    validate_core_profile(source_ids)
    print(f"    required artifacts: {len(REQUIRED_FILES)}/{len(REQUIRED_FILES)}")
    print(
        "    source traceability: 65/65"
        + (" with live corpus hashes" if source_live else " from embedded ledgers")
    )
    print("    feature state machine: valid")
    print("    WIP and evidence gates: valid")
    print("    copy-ready Core profile: valid")


if __name__ == "__main__":
    main()
