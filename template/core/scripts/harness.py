#!/usr/bin/env python3

"""Dependency-free control plane for Harness Engineering Starter Lite."""

from __future__ import annotations

import argparse
import hashlib
import json
import ntpath
import os
import platform
import re
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "harness.config.json"
ALL_LEVELS = ("V0", "V1", "V2", "V3", "V4")
REQUIRED_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "LICENSE",
    "NOTICE",
    "VERSION",
    "harness.config.json",
    "feature_list.json",
    "init.sh",
    "init.ps1",
    "scripts/harness.py",
    "docs/STATE.md",
    "docs/ARCHITECTURE.md",
    "docs/VALIDATION.md",
    "docs/harness/ADOPTION.md",
    "docs/harness/LIFECYCLE.md",
    "docs/harness/components.json",
    "docs/harness/source-map.json",
    "docs/harness/SOURCES.md",
)
PLACEHOLDERS = ("REPLACE_ME", "YYYY-MM-DD")
PYTHON_TOKEN = "{python}"
STATE_BLOCK_START = "<!-- harness:state:start -->"
STATE_BLOCK_END = "<!-- harness:state:end -->"
SENSITIVE_ENV_NAME = re.compile(
    r"(?:TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|PRIVATE[_-]?KEY|CREDENTIAL|AUTH)",
    re.IGNORECASE,
)
BEARER_VALUE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
URL_CREDENTIALS = re.compile(r"(://)[^/@\s]+@")
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class HarnessFailure(Exception):
    """Expected validation or execution failure."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise HarnessFailure(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise HarnessFailure(
            f"{path.relative_to(ROOT)} is invalid JSON at line {exc.lineno}: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise HarnessFailure(f"{path.relative_to(ROOT)} must contain a JSON object.")
    return value


def validate_claude_entrypoint() -> None:
    path = ROOT / "CLAUDE.md"
    try:
        lines = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError as exc:
        raise HarnessFailure(f"cannot read CLAUDE.md: {exc}") from exc
    if not lines or lines[0] != "@AGENTS.md":
        raise HarnessFailure(
            "CLAUDE.md must begin with a standalone @AGENTS.md import so "
            "shared instructions have one source of truth."
        )


def atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
    except OSError as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise HarnessFailure(f"could not atomically update {path}: {exc}") from exc


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(path, payload)


def safe_repo_path(relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise HarnessFailure("repository paths must be non-empty strings.")
    if os.name == "nt":
        for part in re.split(r"[\\/]", relative):
            if not part or part == ".":
                continue
            if ":" in part or part.endswith((" ", ".")):
                raise HarnessFailure(
                    f"unsafe Windows repository path segment: {part!r}"
                )
            device_name = part.split(".", 1)[0].upper()
            if device_name in WINDOWS_RESERVED_NAMES:
                raise HarnessFailure(
                    f"reserved Windows repository path segment: {part!r}"
                )
    candidate = Path(relative)
    if candidate.is_absolute():
        raise HarnessFailure(f"absolute repository path is not allowed: {relative}")
    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise HarnessFailure(f"repository path escapes the root: {relative}") from exc
    return resolved


def config_digest(config: dict[str, Any]) -> str:
    payload = json.dumps(config, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_link_like(path: Path) -> bool:
    """Return true for symbolic links and Windows junction/reparse boundaries."""
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction) and is_junction():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise HarnessFailure(
            f"cannot safely inspect repository path boundary {path}: {exc}"
        ) from exc
    return bool(
        attributes
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x00000400)
    )


def runtime_identity() -> dict[str, str]:
    identity = {
        "platform": sys.platform,
        "os_name": os.name,
        "python_implementation": platform.python_implementation(),
        "python_version": ".".join(str(item) for item in sys.version_info[:2]),
    }
    payload = json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {**identity, "sha256": hashlib.sha256(payload).hexdigest()}


def runtime_identity_digest(identity: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            field: identity.get(field)
            for field in (
                "platform",
                "os_name",
                "python_implementation",
                "python_version",
            )
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def current_revision() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return "unversioned"
    if result.returncode == 0:
        return result.stdout.strip()
    return "unversioned"


def redact_text(value: str) -> str:
    redacted = BEARER_VALUE.sub("Bearer [REDACTED]", value)
    redacted = URL_CREDENTIALS.sub(r"\1[REDACTED]@", redacted)
    sensitive_values = sorted(
        {
            item
            for name, item in os.environ.items()
            if SENSITIVE_ENV_NAME.search(name) and len(item) >= 4
        },
        key=len,
        reverse=True,
    )
    for item in sensitive_values:
        redacted = redacted.replace(item, "[REDACTED]")
    return redacted


class BoundedOutput:
    """Drain subprocess streams while retaining a bounded tail for each."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.buffers = {"stdout": bytearray(), "stderr": bytearray()}
        self.totals = {"stdout": 0, "stderr": 0}
        self.truncated = {"stdout": False, "stderr": False}
        self.lock = threading.Lock()

    def drain(self, name: str, stream: Any) -> None:
        try:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                with self.lock:
                    self.totals[name] += len(chunk)
                    self.buffers[name].extend(chunk)
                    overflow = len(self.buffers[name]) - self.limit
                    if overflow > 0:
                        del self.buffers[name][:overflow]
                        self.truncated[name] = True
        finally:
            stream.close()

    def text(self, name: str) -> str:
        value = self.buffers[name].decode("utf-8", errors="replace")
        return redact_text(value)


def validate_runner_options(label: str, definition: dict[str, Any]) -> None:
    cwd = definition.get("cwd", ".")
    if not isinstance(cwd, str) or not cwd:
        raise HarnessFailure(f"{label}.cwd must be a non-empty relative path.")
    safe_repo_path(cwd)
    timeout = definition.get("timeout_seconds")
    if timeout is not None and (
        not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or timeout <= 0
        or timeout > 86400
    ):
        raise HarnessFailure(
            f"{label}.timeout_seconds must be greater than 0 and at most 86400."
        )
    output_limit = definition.get("max_output_bytes")
    if output_limit is not None and (
        not isinstance(output_limit, int)
        or isinstance(output_limit, bool)
        or output_limit < 1024
        or output_limit > 10 * 1024 * 1024
    ):
        raise HarnessFailure(
            f"{label}.max_output_bytes must be between 1024 and 10485760."
        )


def validate_argv(label: str, argv: Any, *, allow_empty: bool) -> list[str]:
    if not isinstance(argv, list) or any(
        not isinstance(item, str) or not item for item in argv
    ):
        raise HarnessFailure(f"{label}.argv must be an array of non-empty strings.")
    if not allow_empty and not argv:
        raise HarnessFailure(f"{label}.argv cannot be empty.")
    if PYTHON_TOKEN in argv[1:]:
        raise HarnessFailure(
            f"{label}.argv may use {PYTHON_TOKEN!r} only as argv[0]."
        )
    return argv


def expand_argv(argv: list[str]) -> list[str]:
    if PYTHON_TOKEN in argv[1:]:
        raise HarnessFailure(
            f"{PYTHON_TOKEN!r} may be used only as argv[0], never as an argument."
        )
    if argv and argv[0] == PYTHON_TOKEN:
        return [sys.executable, *argv[1:]]
    return list(argv)


def validate_command_definition(name: str, definition: Any) -> None:
    if not isinstance(definition, dict):
        raise HarnessFailure(f"command {name!r} must be an object.")
    argv = validate_argv(
        f"command {name!r}", definition.get("argv"), allow_empty=True
    )
    required = definition.get("required")
    if not isinstance(required, bool):
        raise HarnessFailure(f"command {name!r}.required must be boolean.")
    reason = definition.get("unavailable_reason")
    if not argv and (not isinstance(reason, str) or not reason.strip()):
        raise HarnessFailure(
            f"command {name!r} needs argv or a non-empty unavailable_reason."
        )
    if required and not argv:
        raise HarnessFailure(f"required command {name!r} has no argv.")
    validate_runner_options(f"command {name!r}", definition)


def validate_gate_command(level: str, index: int, command: Any) -> None:
    label = f"{level} command #{index + 1}"
    if not isinstance(command, dict):
        raise HarnessFailure(f"{label} must be an object.")
    for field in ("id", "name", "why", "fix"):
        if not isinstance(command.get(field), str) or not command[field].strip():
            raise HarnessFailure(f"{label}.{field} must be a non-empty string.")
    validate_argv(label, command.get("argv"), allow_empty=False)
    validate_runner_options(label, command)


def validate_config(config: dict[str, Any], *, template_mode: bool) -> None:
    if config.get("schema_version") != 1:
        raise HarnessFailure("harness.config.json schema_version must be 1.")
    configured = config.get("configured")
    if not isinstance(configured, bool):
        raise HarnessFailure("harness.config.json configured must be boolean.")
    if not configured and not template_mode:
        raise HarnessFailure(
            "harness.config.json is not configured. "
            "Follow docs/harness/ADOPTION.md, replace placeholders, then set configured=true."
        )
    if configured and not template_mode:
        serialized = json.dumps(config, ensure_ascii=False)
        for placeholder in PLACEHOLDERS:
            if placeholder in serialized:
                raise HarnessFailure(
                    f"harness.config.json still contains placeholder {placeholder!r}."
                )

    project = config.get("project")
    if not isinstance(project, dict):
        raise HarnessFailure("config.project must be an object.")
    for field in ("name", "summary", "architecture"):
        if not isinstance(project.get(field), str) or not project[field].strip():
            raise HarnessFailure(f"config.project.{field} must be a non-empty string.")

    paths = config.get("paths")
    if not isinstance(paths, dict):
        raise HarnessFailure("config.paths must be an object.")
    for field in ("feature_list", "state", "evidence_dir"):
        safe_repo_path(paths.get(field))

    commands = config.get("commands")
    if not isinstance(commands, dict):
        raise HarnessFailure("config.commands must be an object.")
    for name in ("setup", "start"):
        validate_command_definition(name, commands.get(name))

    runner = config.get("runner")
    if not isinstance(runner, dict):
        raise HarnessFailure("config.runner must be an object.")
    default_timeout = runner.get("default_timeout_seconds")
    if (
        not isinstance(default_timeout, (int, float))
        or isinstance(default_timeout, bool)
        or default_timeout <= 0
        or default_timeout > 86400
    ):
        raise HarnessFailure(
            "config.runner.default_timeout_seconds must be greater than 0 "
            "and at most 86400."
        )
    default_output = runner.get("max_output_bytes")
    if (
        not isinstance(default_output, int)
        or isinstance(default_output, bool)
        or default_output < 1024
        or default_output > 10 * 1024 * 1024
    ):
        raise HarnessFailure(
            "config.runner.max_output_bytes must be between 1024 and 10485760."
        )

    gates = config.get("gates")
    if not isinstance(gates, dict):
        raise HarnessFailure("config.gates must be an object.")
    for level in ALL_LEVELS:
        gate = gates.get(level)
        if not isinstance(gate, dict):
            raise HarnessFailure(f"config.gates.{level} must be an object.")
        if not isinstance(gate.get("description"), str) or not gate["description"].strip():
            raise HarnessFailure(f"config.gates.{level}.description is required.")
        gate_commands = gate.get("commands")
        if not isinstance(gate_commands, list):
            raise HarnessFailure(f"config.gates.{level}.commands must be an array.")
        command_ids: set[str] = set()
        for index, command in enumerate(gate_commands):
            validate_gate_command(level, index, command)
            command_id = command["id"]
            if command_id == "harness-audit" or command_id in command_ids:
                raise HarnessFailure(
                    f"config.gates.{level} contains reserved or duplicate command id "
                    f"{command_id!r}."
                )
            command_ids.add(command_id)

    profiles = config.get("risk_profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise HarnessFailure("config.risk_profiles must be a non-empty object.")
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise HarnessFailure(f"risk profile {name!r} must be an object.")
        enabled = profile.get("enabled")
        levels = profile.get("levels")
        if not isinstance(enabled, bool):
            raise HarnessFailure(f"risk profile {name!r}.enabled must be boolean.")
        if not isinstance(levels, list) or not levels:
            raise HarnessFailure(f"risk profile {name!r}.levels must be non-empty.")
        if levels != list(ALL_LEVELS[: len(levels)]):
            raise HarnessFailure(
                f"risk profile {name!r} must use contiguous levels beginning with V0."
            )
        if enabled:
            for level in levels:
                if level != "V0" and not gates[level]["commands"]:
                    raise HarnessFailure(
                        f"enabled risk profile {name!r} requires {level}, "
                        f"but config.gates.{level}.commands is empty."
                    )
        else:
            reason = profile.get("unavailable_reason")
            if not isinstance(reason, str) or not reason.strip():
                raise HarnessFailure(
                    f"disabled risk profile {name!r} needs unavailable_reason."
                )

    startup_profile = config.get("startup_profile")
    if startup_profile not in profiles:
        raise HarnessFailure("startup_profile must name a declared risk profile.")
    if configured and not profiles[startup_profile]["enabled"]:
        raise HarnessFailure("startup_profile must be enabled in a configured project.")

    clean = config.get("clean_state")
    if not isinstance(clean, dict):
        raise HarnessFailure("config.clean_state must be an object.")
    sections = clean.get("required_state_sections")
    globs = clean.get("forbidden_globs")
    if not isinstance(sections, list) or not sections or any(
        not isinstance(item, str) or not item for item in sections
    ):
        raise HarnessFailure("clean_state.required_state_sections must be non-empty strings.")
    if not isinstance(globs, list) or any(not isinstance(item, str) or not item for item in globs):
        raise HarnessFailure("clean_state.forbidden_globs must contain strings.")


def feature_path(config: dict[str, Any]) -> Path:
    return safe_repo_path(config["paths"]["feature_list"])


def state_path(config: dict[str, Any]) -> Path:
    return safe_repo_path(config["paths"]["state"])


def tracked_file_entries(
    config: dict[str, Any], feature: dict[str, Any]
) -> list[dict[str, str]]:
    feature_id = feature.get("id", "unknown")
    tracked = feature.get("tracked_files")
    if not isinstance(tracked, list) or not tracked:
        raise HarnessFailure(f"{feature_id}.tracked_files must be a non-empty array.")
    if any(not isinstance(item, str) or not item for item in tracked):
        raise HarnessFailure(f"{feature_id}.tracked_files must contain non-empty strings.")
    tracked_keys = [
        ntpath.normcase(item) if os.name == "nt" else item for item in tracked
    ]
    if len(set(tracked_keys)) != len(tracked_keys):
        raise HarnessFailure(f"{feature_id}.tracked_files contains duplicate paths.")

    mutable = {
        Path(config["paths"]["feature_list"]).as_posix(),
        Path(config["paths"]["state"]).as_posix(),
    }
    evidence_dir = Path(config["paths"]["evidence_dir"])
    entries: list[dict[str, str]] = []
    for relative in sorted(tracked):
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts or candidate == Path("."):
            raise HarnessFailure(
                f"{feature_id} tracked path must name one repository file: {relative!r}"
            )
        normalized = candidate.as_posix()
        if normalized in mutable or candidate == evidence_dir or evidence_dir in candidate.parents:
            raise HarnessFailure(
                f"{feature_id} cannot track mutable state or evidence path {relative!r}."
            )
        lexical = ROOT
        for part in candidate.parts:
            lexical = lexical / part
            if is_link_like(lexical):
                raise HarnessFailure(
                    f"{feature_id} tracked path cannot contain a link, junction, "
                    f"or reparse point: {relative}"
                )
        path = safe_repo_path(relative)
        if not path.is_file():
            raise HarnessFailure(
                f"{feature_id} tracked file does not exist or is not regular: {relative}"
            )
        entries.append({"path": normalized, "sha256": sha256_file(path)})
    return entries


def tracked_files_digest(entries: list[dict[str, str]]) -> str:
    payload = json.dumps(entries, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def revision_is_current_or_ancestor(receipt_revision: str) -> bool:
    current = current_revision()
    if receipt_revision == current:
        return True
    if receipt_revision == "unversioned" or current == "unversioned":
        return True
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", receipt_revision, current],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def validate_receipt_reference(
    config: dict[str, Any],
    feature: dict[str, Any],
    evidence: Any,
    *,
    check_freshness: bool,
) -> None:
    feature_id = feature["id"]
    if not isinstance(evidence, dict):
        raise HarnessFailure(f"{feature_id} passing evidence entries must be receipt objects.")
    receipt = evidence.get("receipt")
    if not isinstance(receipt, str) or not receipt:
        raise HarnessFailure(f"{feature_id} passing evidence must include receipt.")
    receipt_path = safe_repo_path(receipt)
    if not receipt_path.is_file():
        raise HarnessFailure(f"{feature_id} receipt does not exist: {receipt}")
    receipt_sha256 = sha256_file(receipt_path)
    if evidence.get("receipt_sha256") != receipt_sha256:
        raise HarnessFailure(
            f"{feature_id} receipt digest is missing or does not match: {receipt}"
        )
    receipt_data = read_json(receipt_path)
    if receipt_data.get("feature_id") != feature_id or receipt_data.get("result") != "passing":
        raise HarnessFailure(f"{feature_id} receipt is not a matching passing result: {receipt}")
    receipt_schema = receipt_data.get("schema_version")
    if receipt_schema not in (2, 3):
        raise HarnessFailure(
            f"{feature_id} receipt must use current schema_version 3 "
            f"or historical schema_version 2: {receipt}"
        )
    for field in ("recorded_at", "revision", "risk_profile"):
        if not isinstance(receipt_data.get(field), str) or not receipt_data[field]:
            raise HarnessFailure(f"{feature_id} receipt has invalid {field}: {receipt}")
    for field in ("config_sha256", "verification_sha256", "tracked_files_sha256"):
        value = receipt_data.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise HarnessFailure(f"{feature_id} receipt has invalid {field}: {receipt}")
    runtime = receipt_data.get("runtime")
    if receipt_schema == 3:
        if not isinstance(runtime, dict):
            raise HarnessFailure(
                f"{feature_id} receipt has invalid runtime identity: {receipt}"
            )
        for field in (
            "platform",
            "os_name",
            "python_implementation",
            "python_version",
        ):
            if not isinstance(runtime.get(field), str) or not runtime[field]:
                raise HarnessFailure(
                    f"{feature_id} receipt runtime has invalid {field}: {receipt}"
                )
        if not isinstance(runtime.get("sha256"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", runtime["sha256"]
        ):
            raise HarnessFailure(
                f"{feature_id} receipt runtime has invalid sha256: {receipt}"
            )
        if runtime["sha256"] != runtime_identity_digest(runtime):
            raise HarnessFailure(
                f"{feature_id} receipt runtime digest does not match its identity: "
                f"{receipt}"
            )
    required_levels = receipt_data.get("required_levels")
    if (
        not isinstance(required_levels, list)
        or not required_levels
        or required_levels != list(ALL_LEVELS[: len(required_levels)])
    ):
        raise HarnessFailure(
            f"{feature_id} receipt has invalid contiguous required_levels: {receipt}"
        )
    skipped_levels = receipt_data.get("skipped_levels")
    if skipped_levels != [level for level in ALL_LEVELS if level not in required_levels]:
        raise HarnessFailure(f"{feature_id} receipt has invalid skipped_levels: {receipt}")
    executed = receipt_data.get("executed")
    if not isinstance(executed, list) or not executed:
        raise HarnessFailure(f"{feature_id} receipt must record executed gates: {receipt}")
    for record in executed:
        if not isinstance(record, dict):
            raise HarnessFailure(f"{feature_id} receipt has a non-object gate record.")
        for field in ("level", "command_id", "name", "cwd"):
            if not isinstance(record.get(field), str) or not record[field]:
                raise HarnessFailure(
                    f"{feature_id} receipt gate record has invalid {field}: {receipt}"
                )
        argv = record.get("argv")
        if not isinstance(argv, list) or any(not isinstance(item, str) for item in argv):
            raise HarnessFailure(f"{feature_id} receipt gate record has invalid argv.")
        argv_sha256 = record.get("argv_sha256")
        if not isinstance(argv_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", argv_sha256
        ):
            raise HarnessFailure(
                f"{feature_id} receipt gate record has invalid argv_sha256."
            )
        if receipt_schema == 3:
            expected_argv_sha256 = hashlib.sha256(
                json.dumps(argv, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            if argv_sha256 != expected_argv_sha256:
                raise HarnessFailure(
                    f"{feature_id} receipt gate argv digest does not match its argv."
                )
        for field in ("timeout_seconds", "duration_ms", "stdout_bytes", "stderr_bytes"):
            value = record.get(field)
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or value < 0
            ):
                raise HarnessFailure(
                    f"{feature_id} receipt gate record has invalid {field}."
                )
        if record.get("exit_code") != 0:
            raise HarnessFailure(f"{feature_id} passing receipt contains a failed gate.")
        for field in ("output_truncated", "timed_out"):
            if not isinstance(record.get(field), bool):
                raise HarnessFailure(
                    f"{feature_id} receipt gate record has invalid {field}."
                )
        if record["timed_out"]:
            raise HarnessFailure(
                f"{feature_id} passing receipt contains a timed-out gate."
            )
    tracked = receipt_data.get("tracked_files")
    if not isinstance(tracked, list) or not tracked:
        raise HarnessFailure(f"{feature_id} receipt must record tracked files: {receipt}")
    for entry in tracked:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("path"), str)
            or not entry["path"]
            or not isinstance(entry.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
        ):
            raise HarnessFailure(f"{feature_id} receipt has invalid tracked file entries.")
    if receipt_data.get("tracked_files_sha256") != tracked_files_digest(tracked):
        raise HarnessFailure(
            f"{feature_id} receipt tracked-file digest does not match its entries."
        )
    for field in ("recorded_at", "risk_profile", "revision"):
        if evidence.get(field) != receipt_data.get(field):
            raise HarnessFailure(
                f"{feature_id} evidence summary disagrees with receipt {field}: {receipt}"
            )
    if not check_freshness:
        return

    stale: list[str] = []
    if receipt_schema != 3:
        stale.append("historical receipt schema lacks current runtime identity")
    elif receipt_data.get("runtime") != runtime_identity():
        stale.append("operating system or Python runtime changed")
    if receipt_data.get("config_sha256") != config_digest(config):
        stale.append("harness.config.json changed")
    if receipt_data.get("verification_sha256") != verification_digest(feature):
        stale.append("feature verification or risk definition changed")
    current_entries = tracked_file_entries(config, feature)
    if receipt_data.get("tracked_files") != current_entries:
        stale.append("one or more tracked files changed")
    if receipt_data.get("tracked_files_sha256") != tracked_files_digest(current_entries):
        stale.append("tracked file digest is missing or changed")
    receipt_risk = receipt_data["risk_profile"]
    profile = config["risk_profiles"].get(receipt_risk)
    if (
        not isinstance(profile, dict)
        or receipt_data["required_levels"] != profile.get("levels")
    ):
        stale.append("receipt risk profile or required levels changed")
    else:
        expected_pairs: list[tuple[str, str]] = []
        for level in receipt_data["required_levels"]:
            if level == "V0":
                expected_pairs.append(("V0", "harness-audit"))
            expected_pairs.extend(
                (level, command["id"])
                for command in config["gates"][level]["commands"]
            )
        actual_pairs = [
            (record["level"], record["command_id"])
            for record in receipt_data["executed"]
        ]
        if actual_pairs != expected_pairs:
            stale.append("receipt does not contain the current complete gate sequence")
        try:
            assert_feature_verification(
                feature,
                receipt_data["required_levels"],
                receipt_data["executed"],
            )
        except HarnessFailure:
            stale.append("receipt does not prove every feature verification binding")
    receipt_revision = receipt_data.get("revision")
    if not isinstance(receipt_revision, str) or not revision_is_current_or_ancestor(
        receipt_revision
    ):
        stale.append("recorded Git revision is not current or an ancestor")
    if stale:
        raise HarnessFailure(
            f"{feature_id} has stale passing evidence ({'; '.join(stale)}). "
            f"Run the current Python with `scripts/harness.py state reopen {feature_id} "
            "--reason \"Evidence became stale\"`, then re-run completion."
        )


def validate_features(
    config: dict[str, Any],
    features_data: dict[str, Any],
    *,
    template_mode: bool,
    receipt_freshness: bool = True,
) -> None:
    if features_data.get("schema_version") != 1:
        raise HarnessFailure("feature_list.json schema_version must be 1.")
    rules = features_data.get("rules")
    legend = features_data.get("status_legend")
    features = features_data.get("features")
    if not isinstance(rules, dict):
        raise HarnessFailure("feature_list.json rules must be an object.")
    if not isinstance(legend, dict) or not legend:
        raise HarnessFailure(
            "feature_list.json must declare a non-empty status_legend; "
            "implicit state machines are not allowed."
        )
    if not isinstance(features, list):
        raise HarnessFailure("feature_list.json features must be an array.")

    maximum = rules.get("max_active_features")
    if (
        not isinstance(maximum, int)
        or isinstance(maximum, bool)
        or maximum != 1
    ):
        raise HarnessFailure("rules.max_active_features must remain exactly 1.")
    if rules.get("passing_requires_receipt") is not True:
        raise HarnessFailure("rules.passing_requires_receipt must remain true.")

    ids: set[str] = set()
    active = 0
    profiles = config["risk_profiles"]
    source_map = read_json(ROOT / "docs/harness/source-map.json")
    known_sources = {
        source.get("id")
        for source in source_map.get("sources", [])
        if isinstance(source, dict) and isinstance(source.get("id"), str)
    }
    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            raise HarnessFailure(f"feature #{index + 1} must be an object.")
        feature_id = feature.get("id")
        if not isinstance(feature_id, str) or not feature_id:
            raise HarnessFailure(f"feature #{index + 1} has no stable id.")
        if feature_id in ids:
            raise HarnessFailure(f"duplicate feature id: {feature_id}")
        ids.add(feature_id)

        status = feature.get("status")
        if status not in legend:
            raise HarnessFailure(f"{feature_id} uses undeclared status {status!r}.")
        if status == "active":
            active += 1
        risk_profile = feature.get("risk_profile")
        if risk_profile not in profiles:
            raise HarnessFailure(f"{feature_id} uses unknown risk profile {risk_profile!r}.")
        verification = feature.get("verification")
        if not isinstance(verification, list) or not verification:
            raise HarnessFailure(f"{feature_id} must declare executable verification.")
        requirement_ids: set[str] = set()
        available_bindings = {("V0", "harness-audit")}
        for level in ALL_LEVELS:
            available_bindings.update(
                (level, command["id"])
                for command in config["gates"][level]["commands"]
            )
        declared_levels = set(profiles[risk_profile]["levels"])
        for requirement_index, requirement in enumerate(verification):
            if not isinstance(requirement, dict):
                raise HarnessFailure(
                    f"{feature_id}.verification #{requirement_index + 1} must be an object."
                )
            requirement_id = requirement.get("id")
            description = requirement.get("description")
            bindings = requirement.get("bindings")
            if (
                not isinstance(requirement_id, str)
                or not requirement_id
                or requirement_id in requirement_ids
            ):
                raise HarnessFailure(
                    f"{feature_id} has an invalid or duplicate verification id."
                )
            requirement_ids.add(requirement_id)
            if not isinstance(description, str) or not description.strip():
                raise HarnessFailure(
                    f"{feature_id}.{requirement_id}.description must be non-empty."
                )
            if not isinstance(bindings, list) or not bindings:
                raise HarnessFailure(
                    f"{feature_id}.{requirement_id}.bindings must be non-empty."
                )
            for binding in bindings:
                if not isinstance(binding, dict):
                    raise HarnessFailure(
                        f"{feature_id}.{requirement_id} binding must be an object."
                    )
                pair = (binding.get("level"), binding.get("command_id"))
                if pair not in available_bindings:
                    raise HarnessFailure(
                        f"{feature_id}.{requirement_id} references missing gate command "
                        f"{pair[0]}/{pair[1]}."
                    )
                if pair[0] not in declared_levels:
                    raise HarnessFailure(
                        f"{feature_id}.{requirement_id} requires {pair[0]}, outside "
                        f"risk profile {risk_profile!r}."
                    )
        tracked_file_entries(config, feature)
        for field in ("evidence", "history", "sources"):
            if not isinstance(feature.get(field), list):
                raise HarnessFailure(f"{feature_id}.{field} must be an array.")
        if not feature["sources"]:
            raise HarnessFailure(f"{feature_id}.sources must be non-empty.")
        for reference in feature["sources"]:
            expand_source_reference(reference, known_sources)
        if status == "passing" and rules.get("passing_requires_receipt"):
            if not feature["evidence"]:
                raise HarnessFailure(f"{feature_id} is passing without a receipt.")
            for evidence_index, evidence in enumerate(feature["evidence"]):
                validate_receipt_reference(
                    config,
                    feature,
                    evidence,
                    check_freshness=(
                        receipt_freshness
                        and evidence_index == len(feature["evidence"]) - 1
                    ),
                )

    if active > maximum:
        raise HarnessFailure(
            f"{active} features are active but the WIP limit is {maximum}. "
            "Finish, block, or reopen work before activating another feature."
        )

    if config["configured"] and not template_mode:
        serialized = json.dumps(features_data, ensure_ascii=False)
        for placeholder in PLACEHOLDERS:
            if placeholder in serialized:
                raise HarnessFailure(
                    f"feature_list.json still contains placeholder {placeholder!r}."
                )


def expand_source_reference(reference: str, known: set[str]) -> list[str]:
    if not isinstance(reference, str):
        raise HarnessFailure("source references must be strings.")
    match = re.fullmatch(r"(SRC-[A-Z]+-)(\d+)(?:\.\.(\d+))?", reference)
    if not match:
        raise HarnessFailure(f"invalid source reference syntax: {reference!r}")
    prefix, start_text, end_text = match.groups()
    start = int(start_text)
    end = int(end_text) if end_text is not None else start
    if end < start:
        raise HarnessFailure(f"source reference range is reversed: {reference}")
    width = len(start_text)
    expanded = [f"{prefix}{value:0{width}d}" for value in range(start, end + 1)]
    missing = [source_id for source_id in expanded if source_id not in known]
    if missing:
        raise HarnessFailure(
            f"source reference {reference} includes unknown IDs: {', '.join(missing)}"
        )
    return expanded


def validate_components() -> None:
    manifest_path = ROOT / "docs/harness/components.json"
    manifest = read_json(manifest_path)
    source_map = read_json(ROOT / "docs/harness/source-map.json")
    link_semantics = source_map.get("link_semantics")
    if not isinstance(link_semantics, dict) or any(
        not isinstance(link_semantics.get(field), str)
        or not link_semantics[field].strip()
        for field in ("source_components", "component_sources")
    ):
        raise HarnessFailure(
            "docs/harness/source-map.json must declare both traceability "
            "link semantics."
        )
    sources = source_map.get("sources")
    if (
        source_map.get("schema_version") != 1
        or source_map.get("source_count") != 65
        or not isinstance(sources, list)
        or len(sources) != 65
    ):
        raise HarnessFailure(
            "docs/harness/source-map.json must contain exactly 65 schema-v1 sources."
        )
    source_by_id: dict[str, dict[str, Any]] = {}
    allowed_dispositions = {"core-direct", "merged", "deferred", "reference-only"}
    for source in sources:
        if not isinstance(source, dict):
            raise HarnessFailure("each Source map entry must be an object.")
        source_id = source.get("id")
        if (
            not isinstance(source_id, str)
            or not source_id
            or source_id in source_by_id
        ):
            raise HarnessFailure(f"invalid or duplicate Source map id: {source_id!r}")
        for field in ("path", "role", "rationale"):
            if not isinstance(source.get(field), str) or not source[field].strip():
                raise HarnessFailure(f"{source_id}.{field} must be non-empty.")
        if source.get("disposition") not in allowed_dispositions:
            raise HarnessFailure(f"{source_id} has an invalid disposition.")
        references = source.get("components")
        if not isinstance(references, list) or not references or any(
            not isinstance(item, str) or not item for item in references
        ):
            raise HarnessFailure(f"{source_id}.components must be non-empty strings.")
        source_by_id[source_id] = source

    components = manifest.get("components")
    if not isinstance(components, list) or not components:
        raise HarnessFailure("docs/harness/components.json needs components.")
    ids: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            raise HarnessFailure("each harness component must be an object.")
        component_id = component.get("id")
        if not isinstance(component_id, str) or not component_id or component_id in ids:
            raise HarnessFailure(f"invalid or duplicate harness component id: {component_id!r}")
        ids.add(component_id)
        path = component.get("path")
        if not isinstance(path, str) or not safe_repo_path(path).is_file():
            raise HarnessFailure(f"{component_id} points to missing file: {path!r}")
        if component.get("profile") != "core":
            raise HarnessFailure(f"{component_id}.profile must be 'core'.")
        for field in ("purpose", "applies_when", "review_trigger", "rollback"):
            if not isinstance(component.get(field), str) or not component[field].strip():
                raise HarnessFailure(f"{component_id}.{field} must be non-empty.")
        validation = component.get("validation")
        if not isinstance(validation, list) or not validation or any(
            not isinstance(item, str) or not item.strip() for item in validation
        ):
            raise HarnessFailure(f"{component_id}.validation must be non-empty strings.")
        sources = component.get("sources")
        if not isinstance(sources, list) or not sources:
            raise HarnessFailure(f"{component_id}.sources must be non-empty.")
        expanded_sources: list[str] = []
        for reference in sources:
            expanded_sources.extend(
                expand_source_reference(reference, set(source_by_id))
            )
        for source_id in expanded_sources:
            if component_id not in source_by_id[source_id]["components"]:
                raise HarnessFailure(
                    f"{component_id} -> {source_id} is missing from the Source map reverse link."
                )

    expected_paths = set(REQUIRED_FILES)
    component_paths = {component["path"] for component in components}
    if component_paths != expected_paths:
        raise HarnessFailure(
            "component ledger must exactly cover installed Core files. "
            f"Missing: {sorted(expected_paths - component_paths)}; "
            f"stale: {sorted(component_paths - expected_paths)}"
        )
    for source_id, source in source_by_id.items():
        for reference in source["components"]:
            if reference.startswith("HC-") and reference not in ids:
                raise HarnessFailure(
                    f"{source_id} references unknown installed component {reference}."
                )


def state_values(features_data: dict[str, Any]) -> tuple[str, str, str]:
    active = [
        feature["id"]
        for feature in features_data["features"]
        if feature["status"] == "active"
    ]
    active_value = active[0] if active else "none"
    upcoming = next_feature(features_data)
    next_value = upcoming["id"] if upcoming is not None else "none"
    latest: tuple[str, dict[str, Any]] | None = None
    for feature in features_data["features"]:
        history = feature.get("history", [])
        if history:
            event = history[-1]
            candidate = (str(event.get("at", "")), event)
            if latest is None or candidate[0] > latest[0]:
                latest = candidate
    if latest is None:
        transition = "not recorded"
    else:
        event = latest[1]
        transition = (
            f"{event.get('at', 'unknown')} "
            f"{event.get('from', '?')}->{event.get('to', '?')}"
        )
    return active_value, next_value, transition


def render_state_block(features_data: dict[str, Any]) -> str:
    active, upcoming, transition = state_values(features_data)
    return "\n".join(
        (
            STATE_BLOCK_START,
            f"- Active feature: {active}",
            f"- Next feature: {upcoming}",
            f"- Last transition: {transition}",
            STATE_BLOCK_END,
        )
    )


def replace_state_block(text: str, features_data: dict[str, Any]) -> str:
    pattern = re.compile(
        re.escape(STATE_BLOCK_START) + r".*?" + re.escape(STATE_BLOCK_END),
        re.DOTALL,
    )
    if not pattern.search(text):
        raise HarnessFailure(
            "state file is missing the harness-managed state marker block."
        )
    return pattern.sub(render_state_block(features_data), text, count=1)


def validate_state(
    config: dict[str, Any],
    features_data: dict[str, Any],
    *,
    template_mode: bool,
    check_consistency: bool = True,
) -> None:
    path = state_path(config)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HarnessFailure(f"cannot read state file {path}: {exc}") from exc
    missing = [
        heading
        for heading in config["clean_state"]["required_state_sections"]
        if heading not in text
    ]
    if missing:
        raise HarnessFailure(f"state file is missing required sections: {', '.join(missing)}")
    if STATE_BLOCK_START not in text or STATE_BLOCK_END not in text:
        raise HarnessFailure("state file is missing the harness-managed state marker block.")
    expected_block = render_state_block(features_data)
    current_block = text[
        text.index(STATE_BLOCK_START) : text.index(STATE_BLOCK_END)
        + len(STATE_BLOCK_END)
    ]
    if check_consistency and current_block != expected_block:
        raise HarnessFailure(
            "docs/STATE.md disagrees with feature_list.json. "
            "Run the current Python with `scripts/harness.py state sync` "
            "to repair the managed block."
        )
    if config["configured"] and not template_mode:
        for placeholder in PLACEHOLDERS:
            if placeholder in text:
                raise HarnessFailure(f"state file still contains placeholder {placeholder!r}.")


def audit_repository(
    *,
    template_mode: bool = False,
    receipt_freshness: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    missing = [relative for relative in REQUIRED_FILES if not (ROOT / relative).is_file()]
    if missing:
        raise HarnessFailure(
            "required Core profile files are missing: "
            + ", ".join(missing)
            + ". Restore them before continuing."
        )
    validate_claude_entrypoint()
    config = read_json(CONFIG_PATH)
    validate_config(config, template_mode=template_mode)
    features_data = read_json(feature_path(config))
    validate_features(
        config,
        features_data,
        template_mode=template_mode,
        receipt_freshness=receipt_freshness,
    )
    validate_components()
    validate_state(config, features_data, template_mode=template_mode)
    if config["configured"] and not template_mode:
        for relative in (
            config["project"]["architecture"],
            "docs/ARCHITECTURE.md",
            "docs/VALIDATION.md",
        ):
            text = safe_repo_path(relative).read_text(encoding="utf-8")
            for placeholder in PLACEHOLDERS:
                if placeholder in text:
                    raise HarnessFailure(
                        f"{relative} still contains placeholder {placeholder!r}."
                    )
    return config, features_data


def command_label(argv: list[str], *, platform_name: str | None = None) -> str:
    effective_platform = os.name if platform_name is None else platform_name
    rendered = (
        subprocess.list2cmdline(argv)
        if effective_platform == "nt"
        else shlex.join(argv)
    )
    return redact_text(rendered)


def process_creation_options(
    *, platform_name: str | None = None
) -> dict[str, Any]:
    effective_platform = os.name if platform_name is None else platform_name
    if effective_platform == "posix":
        return {"start_new_session": True}
    if effective_platform == "nt":
        return {
            "creationflags": getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
            )
        }
    return {}


def windows_taskkill_path(system_root: str | None = None) -> str:
    root = system_root or os.environ.get("SystemRoot") or r"C:\Windows"
    return ntpath.join(root, "System32", "taskkill.exe")


def terminate_process_tree(
    process: subprocess.Popen[bytes],
    *,
    platform_name: str | None = None,
    taskkill_runner: Any = subprocess.run,
) -> None:
    effective_platform = os.name if platform_name is None else platform_name
    if process.poll() is not None:
        return
    if effective_platform == "nt":
        try:
            process.send_signal(getattr(signal, "CTRL_BREAK_EVENT", 1))
            process.wait(timeout=2)
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            result = taskkill_runner(
                [
                    windows_taskkill_path(),
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                if process.poll() is not None:
                    return
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            process.kill()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return

    try:
        if effective_platform == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        try:
            if effective_platform == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass


def execute_gate_command(
    config: dict[str, Any],
    level: str,
    command: dict[str, Any],
) -> dict[str, Any]:
    argv = expand_argv(command["argv"])
    print(f"==> {level} {command['name']}")
    cwd = safe_repo_path(command.get("cwd", "."))
    timeout_seconds = command.get(
        "timeout_seconds", config["runner"]["default_timeout_seconds"]
    )
    max_output_bytes = command.get(
        "max_output_bytes", config["runner"]["max_output_bytes"]
    )
    if not cwd.is_dir():
        raise HarnessFailure(
            f"WHAT: {level} command {command['name']!r} has an unavailable cwd."
            f"\nWHY: commands must run inside an existing repository directory."
            f"\nFIX: create or correct {command.get('cwd', '.')} and retry."
            f"\nCOMMAND: {command_label(argv)}"
        )

    started = time.monotonic()
    output = BoundedOutput(max_output_bytes)
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **process_creation_options(),
        )
    except OSError as exc:
        raise HarnessFailure(
            f"WHAT: {level} command {command['name']!r} could not start: "
            f"{redact_text(str(exc))}."
            f"\nWHY: {command['why']}"
            f"\nFIX: {command['fix']}"
            f"\nCOMMAND: {command_label(argv)}"
            f"\nCWD: {cwd.relative_to(ROOT) or Path('.')}"
        ) from exc

    assert process.stdout is not None
    assert process.stderr is not None
    readers = [
        threading.Thread(
            target=output.drain,
            args=("stdout", process.stdout),
            daemon=True,
        ),
        threading.Thread(
            target=output.drain,
            args=("stderr", process.stderr),
            daemon=True,
        ),
    ]
    for reader in readers:
        reader.start()
    timed_out = False
    try:
        return_code = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        terminate_process_tree(process)
        return_code = process.returncode if process.returncode is not None else -1
    for reader in readers:
        reader.join(timeout=3)

    duration_ms = round((time.monotonic() - started) * 1000)
    redacted_argv = [redact_text(item) for item in argv]
    record = {
        "level": level,
        "command_id": command["id"],
        "name": command["name"],
        "argv": redacted_argv,
        "argv_sha256": hashlib.sha256(
            json.dumps(redacted_argv, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
        "cwd": str(cwd.relative_to(ROOT)) or ".",
        "timeout_seconds": timeout_seconds,
        "exit_code": return_code,
        "duration_ms": duration_ms,
        "stdout_bytes": output.totals["stdout"],
        "stderr_bytes": output.totals["stderr"],
        "output_truncated": output.truncated["stdout"] or output.truncated["stderr"],
        "timed_out": timed_out,
    }
    if timed_out or return_code != 0:
        failure = (
            f"timed out after {timeout_seconds} seconds"
            if timed_out
            else f"failed with exit code {return_code}"
        )
        details = [
            f"WHAT: {level} command {command['name']!r} {failure}.",
            f"WHY: {command['why']}",
            f"FIX: {command['fix']}",
            f"COMMAND: {command_label(argv)}",
            f"CWD: {record['cwd']}",
        ]
        for stream_name in ("stdout", "stderr"):
            stream_text = output.text(stream_name).rstrip()
            if stream_text:
                suffix = (
                    f"\n[{stream_name} truncated; "
                    f"{output.totals[stream_name]} bytes produced]"
                    if output.truncated[stream_name]
                    else ""
                )
                details.append(f"{stream_name.upper()} (bounded tail):\n{stream_text}{suffix}")
        raise HarnessFailure("\n".join(details))
    return record


def gate_levels(config: dict[str, Any], risk: str) -> list[str]:
    profile = config["risk_profiles"].get(risk)
    if not isinstance(profile, dict):
        raise HarnessFailure(f"unknown risk profile: {risk}")
    if not profile["enabled"]:
        raise HarnessFailure(
            f"risk profile {risk!r} is disabled. "
            f"{profile.get('unavailable_reason', 'Configure and enable it first.')}"
        )
    return profile["levels"]


def run_gates(
    config: dict[str, Any],
    features_data: dict[str, Any],
    risk: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    levels = gate_levels(config, risk)
    records: list[dict[str, Any]] = []
    for level in levels:
        if level == "V0":
            audit_repository()
            records.append(
                {
                    "level": "V0",
                    "command_id": "harness-audit",
                    "name": "harness-audit",
                    "argv": ["built-in:audit"],
                    "argv_sha256": hashlib.sha256(
                        json.dumps(
                            ["built-in:audit"], ensure_ascii=False
                        ).encode("utf-8")
                    ).hexdigest(),
                    "cwd": ".",
                    "timeout_seconds": 0,
                    "exit_code": 0,
                    "duration_ms": 0,
                    "stdout_bytes": 0,
                    "stderr_bytes": 0,
                    "output_truncated": False,
                    "timed_out": False,
                }
            )
        for command in config["gates"][level]["commands"]:
            records.append(execute_gate_command(config, level, command))
    return levels, records


def assert_feature_verification(
    feature: dict[str, Any],
    levels: list[str],
    records: list[dict[str, Any]],
) -> None:
    executed = {(record["level"], record["command_id"]) for record in records}
    selected = set(levels)
    missing: list[str] = []
    for requirement in feature["verification"]:
        for binding in requirement["bindings"]:
            pair = (binding["level"], binding["command_id"])
            if pair[0] not in selected or pair not in executed:
                missing.append(
                    f"{requirement['id']} -> {pair[0]}/{pair[1]}"
                )
    if missing:
        raise HarnessFailure(
            "WHAT: feature-specific verification did not execute every binding: "
            + ", ".join(missing)
            + "\nWHY: a feature cannot pass from prose or an unrelated gate result."
            + "\nFIX: select a sufficient risk profile and restore the referenced gate commands."
        )


def validate_clean_state(
    config: dict[str, Any], features_data: dict[str, Any]
) -> None:
    validate_state(config, features_data, template_mode=False)
    offenders: list[str] = []
    for pattern in config["clean_state"]["forbidden_globs"]:
        for path in ROOT.rglob(pattern):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if relative.parts and relative.parts[0] == ".git":
                continue
            offenders.append(str(relative))
    if offenders:
        raise HarnessFailure(
            "WHAT: clean-state check found temporary artifacts: "
            + ", ".join(sorted(set(offenders)))
            + "\nWHY: the next session cannot distinguish intentional files from leftovers."
            + "\nFIX: remove or intentionally rename the artifacts, then rerun completion."
        )


def find_feature(features_data: dict[str, Any], feature_id: str) -> dict[str, Any]:
    for feature in features_data["features"]:
        if feature["id"] == feature_id:
            return feature
    raise HarnessFailure(f"unknown feature id: {feature_id}")


def ensure_no_other_active(features_data: dict[str, Any], feature_id: str) -> None:
    other = [
        feature["id"]
        for feature in features_data["features"]
        if feature["status"] == "active" and feature["id"] != feature_id
    ]
    if other:
        raise HarnessFailure(
            f"cannot activate {feature_id}; WIP=1 and {', '.join(other)} is already active."
        )


def append_history(
    feature: dict[str, Any], previous: str, target: str, reason: str
) -> None:
    feature.setdefault("history", []).append(
        {
            "at": utc_now(),
            "from": previous,
            "to": target,
            "reason": reason,
            "revision": current_revision(),
        }
    )


def persist_features(
    config: dict[str, Any],
    features_data: dict[str, Any],
    *,
    receipt_freshness: bool = True,
) -> None:
    features_data["last_updated"] = datetime.now(timezone.utc).date().isoformat()
    validate_features(
        config,
        features_data,
        template_mode=False,
        receipt_freshness=receipt_freshness,
    )
    features_path = feature_path(config)
    state_document_path = state_path(config)
    original_features = features_path.read_text(encoding="utf-8")
    original_state = state_document_path.read_text(encoding="utf-8")
    updated_state = replace_state_block(original_state, features_data)
    atomic_write_json(features_path, features_data)
    try:
        atomic_write_text(state_document_path, updated_state)
    except Exception as exc:
        try:
            atomic_write_text(features_path, original_features)
        except Exception as rollback_exc:
            raise HarnessFailure(
                "state update failed and feature rollback also failed. "
                f"STATE ERROR: {exc}; ROLLBACK ERROR: {rollback_exc}"
            ) from rollback_exc
        raise


def change_state(action: str, feature_id: str, reason: str | None) -> None:
    lenient_recovery = action in {"reopen", "block"}
    config, features_data = audit_repository(
        receipt_freshness=not lenient_recovery
    )
    if lenient_recovery:
        print(
            "WARNING: state recovery validates receipt structure but defers freshness "
            "until the next strict audit.",
            file=sys.stderr,
        )
    feature = find_feature(features_data, feature_id)
    previous = feature["status"]

    if action == "activate":
        if previous != "not_started":
            raise HarnessFailure(
                f"{feature_id} is {previous}; activate only supports not_started. "
                "Use reopen for blocked or passing work."
            )
        ensure_no_other_active(features_data, feature_id)
        target = "active"
        effective_reason = reason or "Selected as the single active feature."
    elif action == "reopen":
        if previous not in {"blocked", "passing"}:
            raise HarnessFailure(f"{feature_id} must be blocked or passing before reopen.")
        if not reason:
            raise HarnessFailure("reopen requires --reason to preserve the audit trail.")
        ensure_no_other_active(features_data, feature_id)
        target = "active"
        effective_reason = reason
    elif action == "block":
        if previous != "active":
            raise HarnessFailure(f"{feature_id} must be active before it can be blocked.")
        if not reason:
            raise HarnessFailure("block requires --reason and a recovery condition.")
        target = "blocked"
        effective_reason = reason
    else:
        raise HarnessFailure(f"unsupported state action: {action}")

    feature["status"] = target
    append_history(feature, previous, target, effective_reason)
    persist_features(
        config,
        features_data,
        receipt_freshness=not lenient_recovery,
    )
    print(f"{feature_id}: {previous} -> {target}")


def sync_state() -> None:
    config = read_json(CONFIG_PATH)
    validate_config(config, template_mode=False)
    features_data = read_json(feature_path(config))
    validate_features(
        config,
        features_data,
        template_mode=False,
        receipt_freshness=False,
    )
    validate_components()
    validate_state(
        config,
        features_data,
        template_mode=False,
        check_consistency=False,
    )
    path = state_path(config)
    current = path.read_text(encoding="utf-8")
    atomic_write_text(path, replace_state_block(current, features_data))
    validate_state(config, features_data, template_mode=False)
    print(
        "WARNING: state sync validates receipt structure but defers freshness "
        "until the next strict audit.",
        file=sys.stderr,
    )
    print("docs/STATE.md synchronized with feature_list.json")


def verification_digest(feature: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "risk_profile": feature.get("risk_profile"),
            "verification": feature.get("verification", []),
            "tracked_files": feature.get("tracked_files", []),
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def complete_feature(feature_id: str, risk: str) -> None:
    config, features_data = audit_repository()
    feature = find_feature(features_data, feature_id)
    if feature["status"] != "active":
        raise HarnessFailure(f"{feature_id} must be active before completion.")

    selected_levels = gate_levels(config, risk)
    declared_levels = gate_levels(config, feature["risk_profile"])
    if len(selected_levels) < len(declared_levels):
        raise HarnessFailure(
            f"{risk!r} is weaker than {feature_id}'s declared profile "
            f"{feature['risk_profile']!r}; completion cannot downgrade required gates."
        )

    levels, records = run_gates(config, features_data, risk)
    assert_feature_verification(feature, levels, records)
    validate_clean_state(config, features_data)
    tracked_entries = tracked_file_entries(config, feature)

    recorded_at = utc_now()
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", feature_id)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    evidence_dir = safe_repo_path(config["paths"]["evidence_dir"])
    receipt_path = evidence_dir / f"{stamp}-{safe_id}.json"
    relative_receipt = str(receipt_path.relative_to(ROOT))
    receipt = {
        "schema_version": 3,
        "feature_id": feature_id,
        "result": "passing",
        "recorded_at": recorded_at,
        "revision": current_revision(),
        "risk_profile": risk,
        "required_levels": levels,
        "executed": records,
        "skipped_levels": [level for level in ALL_LEVELS if level not in levels],
        "config_sha256": config_digest(config),
        "verification_sha256": verification_digest(feature),
        "tracked_files": tracked_entries,
        "tracked_files_sha256": tracked_files_digest(tracked_entries),
        "runtime": runtime_identity(),
    }

    atomic_write_json(receipt_path, receipt)
    previous = feature["status"]
    feature["status"] = "passing"
    feature.setdefault("evidence", []).append(
        {
            "receipt": relative_receipt,
            "receipt_sha256": sha256_file(receipt_path),
            "recorded_at": recorded_at,
            "risk_profile": risk,
            "revision": receipt["revision"],
        }
    )
    append_history(feature, previous, "passing", f"Required {risk} gates passed.")
    try:
        persist_features(config, features_data)
    except Exception:
        receipt_path.unlink(missing_ok=True)
        raise
    print(f"{feature_id}: active -> passing")
    print(f"receipt: {relative_receipt}")


def run_declared_command(config: dict[str, Any], name: str) -> None:
    definition = config["commands"][name]
    argv = definition["argv"]
    if not argv:
        print(f"{name}: unavailable ({definition['unavailable_reason']})")
        return
    command = {
        "id": name,
        "name": name,
        "argv": argv,
        "cwd": definition.get("cwd", "."),
        "timeout_seconds": definition.get("timeout_seconds"),
        "max_output_bytes": definition.get("max_output_bytes"),
        "why": f"The declared {name} path must execute successfully.",
        "fix": f"Run {command_label(argv)} directly, correct the project configuration, and retry.",
    }
    command = {key: value for key, value in command.items() if value is not None}
    execute_gate_command(config, "CMD", command)


def next_feature(features_data: dict[str, Any]) -> dict[str, Any] | None:
    unfinished = [
        feature for feature in features_data["features"] if feature["status"] != "passing"
    ]
    if not unfinished:
        return None
    return sorted(
        unfinished,
        key=lambda feature: (
            0 if feature["status"] == "active" else 1,
            feature.get("priority", 999999),
            feature["id"],
        ),
    )[0]


def cold_start_answers(
    config: dict[str, Any], features_data: dict[str, Any]
) -> dict[str, Any]:
    feature = next_feature(features_data)
    enabled_profiles = {
        name: profile["levels"]
        for name, profile in config["risk_profiles"].items()
        if profile["enabled"]
    }
    return {
        "what": {
            "name": config["project"]["name"],
            "summary": config["project"]["summary"],
        },
        "structure": {
            "architecture": config["project"]["architecture"],
            "exists": safe_repo_path(config["project"]["architecture"]).is_file(),
        },
        "start": {
            "setup": config["commands"]["setup"]["argv"]
            or config["commands"]["setup"]["unavailable_reason"],
            "start": config["commands"]["start"]["argv"]
            or config["commands"]["start"]["unavailable_reason"],
        },
        "verify": {
            "startup_profile": config["startup_profile"],
            "enabled_risk_profiles": enabled_profiles,
        },
        "current": {
            "state_file": config["paths"]["state"],
            "next_feature": None
            if feature is None
            else {
                "id": feature["id"],
                "status": feature["status"],
                "title": feature["title"],
            },
        },
    }


def print_status(features_data: dict[str, Any], *, as_json: bool) -> None:
    payload = [
        {
            "id": feature["id"],
            "priority": feature.get("priority"),
            "status": feature["status"],
            "title": feature["title"],
        }
        for feature in features_data["features"]
    ]
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for feature in payload:
        print(
            f"{feature['id']}  {feature['status']:<11} "
            f"P{feature['priority']}  {feature['title']}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="validate the Core profile")
    audit.add_argument(
        "--template",
        action="store_true",
        help="allow unconfigured placeholders in the distribution template",
    )

    init = subparsers.add_parser("init", help="run the standard startup preflight")
    init.add_argument("--setup", action="store_true", help="run the declared setup command")

    cold = subparsers.add_parser("cold-start", help="answer the five cold-start questions")
    cold.add_argument("--json", action="store_true", help="emit machine-readable output")

    run = subparsers.add_parser("run", help="run a declared setup or start command")
    run.add_argument("name", choices=("setup", "start"))

    verify = subparsers.add_parser("verify", help="run a risk profile without state change")
    verify.add_argument("--risk", required=True)

    complete = subparsers.add_parser(
        "complete", help="run gates, write a receipt, and move active work to passing"
    )
    complete.add_argument("feature_id")
    complete.add_argument("--risk", required=True)

    state = subparsers.add_parser("state", help="perform an audited state transition")
    state_subparsers = state.add_subparsers(dest="state_action", required=True)
    for action in ("activate", "reopen", "block"):
        state_command = state_subparsers.add_parser(action)
        state_command.add_argument("feature_id")
        state_command.add_argument("--reason")
    state_subparsers.add_parser(
        "sync", help="repair the managed STATE block from feature_list.json"
    )

    status = subparsers.add_parser("status", help="show current feature states")
    status.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "audit":
            audit_repository(template_mode=args.template)
            print("Core profile audit: healthy")
        elif args.command == "init":
            config, features_data = audit_repository()
            if args.setup:
                run_declared_command(config, "setup")
            levels, _ = run_gates(
                config, features_data, config["startup_profile"]
            )
            start = config["commands"]["start"]
            start_value = (
                command_label(start["argv"]) if start["argv"] else start["unavailable_reason"]
            )
            print(f"startup profile: {config['startup_profile']} ({', '.join(levels)})")
            print(f"start: {start_value}")
            print("Harness baseline: healthy")
        elif args.command == "cold-start":
            config, features_data = audit_repository()
            answers = cold_start_answers(config, features_data)
            if args.json:
                print(json.dumps(answers, ensure_ascii=False, indent=2))
            else:
                for question, answer in answers.items():
                    print(f"{question}: {answer}")
        elif args.command == "run":
            config, _ = audit_repository()
            run_declared_command(config, args.name)
        elif args.command == "verify":
            config, features_data = audit_repository()
            levels, _ = run_gates(config, features_data, args.risk)
            print(f"verification passed: {args.risk} ({', '.join(levels)})")
        elif args.command == "complete":
            complete_feature(args.feature_id, args.risk)
        elif args.command == "state":
            if args.state_action == "sync":
                sync_state()
            else:
                change_state(args.state_action, args.feature_id, args.reason)
        elif args.command == "status":
            _, features_data = audit_repository()
            print_status(features_data, as_json=args.json)
        else:
            raise HarnessFailure(f"unsupported command: {args.command}")
    except HarnessFailure as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
