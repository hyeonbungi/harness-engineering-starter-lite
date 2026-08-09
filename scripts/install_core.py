#!/usr/bin/env python3

"""Install, upgrade, or remove the Core profile without overwriting project work."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "template/core"
MANIFEST_RELATIVE = Path(".harness/install-manifest.json")
BACKUP_RELATIVE = Path(".harness/backups")
MANIFEST_SCHEMA = 1
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class LifecycleFailure(Exception):
    """A safe lifecycle precondition or operation failed."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="project directory")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show the complete operation without writing",
    )
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument(
        "--upgrade",
        action="store_true",
        help="upgrade files owned by an existing Core install manifest",
    )
    operation.add_argument(
        "--remove",
        action="store_true",
        help="remove only unchanged files owned by the Core install manifest",
    )
    parser.add_argument(
        "--accept-merged",
        action="store_true",
        help=(
            "with --upgrade, preserve already-merged local conflicts while "
            "recording the incoming version as their new baseline"
        ),
    )
    return parser


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_link_like(path: Path) -> bool:
    """Treat POSIX links and Windows reparse points as unsafe path boundaries."""
    if path.is_symlink():
        return True
    if os.name != "nt":
        return False
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise LifecycleFailure(f"cannot safely inspect managed path {path}: {exc}") from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def managed_path_identity(relative: Path) -> str:
    """Return the filesystem identity used to detect managed-path aliases."""
    normalized = relative.as_posix()
    return normalized.casefold() if os.name == "nt" else normalized


def register_managed_path(
    seen: dict[str, str],
    relative: Path,
    *,
    label: str,
) -> None:
    """Reject leaf and parent paths that alias on the active filesystem."""
    for depth in range(1, len(relative.parts) + 1):
        prefix = Path(*relative.parts[:depth])
        normalized = prefix.as_posix()
        identity = managed_path_identity(prefix)
        existing = seen.get(identity)
        if existing is not None and existing != normalized:
            raise LifecycleFailure(
                f"{label} contains paths that alias on this platform: "
                f"{existing!r} and {normalized!r}"
            )
        seen[identity] = normalized


def is_reserved_lifecycle_path(relative: Path) -> bool:
    identity = managed_path_identity(relative)
    manifest_identity = managed_path_identity(MANIFEST_RELATIVE)
    backup_identity = managed_path_identity(BACKUP_RELATIVE)
    return (
        identity == manifest_identity
        or identity == backup_identity
        or identity.startswith(f"{backup_identity}/")
    )


def parse_semver(value: Any, label: str) -> tuple[int, int, int, tuple[str, ...] | None]:
    if not isinstance(value, str):
        raise LifecycleFailure(f"{label} must be a Semantic Version string.")
    match = SEMVER.fullmatch(value)
    if match is None:
        raise LifecycleFailure(f"{label} is not a valid Semantic Version: {value!r}")
    major, minor, patch, prerelease_text = match.groups()
    prerelease = None
    if prerelease_text is not None:
        prerelease = tuple(prerelease_text.split("."))
        if any(
            identifier.isdigit()
            and len(identifier) > 1
            and identifier.startswith("0")
            for identifier in prerelease
        ):
            raise LifecycleFailure(
                f"{label} has a numeric prerelease identifier with a leading zero."
            )
    return int(major), int(minor), int(patch), prerelease


def compare_semver(left: str, right: str) -> int:
    left_version = parse_semver(left, "incoming Core version")
    right_version = parse_semver(right, "installed Core version")
    if left_version[:3] != right_version[:3]:
        return 1 if left_version[:3] > right_version[:3] else -1
    left_pre = left_version[3]
    right_pre = right_version[3]
    if left_pre is None or right_pre is None:
        if left_pre == right_pre:
            return 0
        return 1 if left_pre is None else -1
    for left_item, right_item in zip(left_pre, right_pre):
        if left_item == right_item:
            continue
        if left_item.isdigit() and right_item.isdigit():
            return 1 if int(left_item) > int(right_item) else -1
        if left_item.isdigit() != right_item.isdigit():
            return -1 if left_item.isdigit() else 1
        return 1 if left_item > right_item else -1
    if len(left_pre) == len(right_pre):
        return 0
    return 1 if len(left_pre) > len(right_pre) else -1


def validate_upgrade_versions(installed: str, incoming: str) -> None:
    installed_version = parse_semver(installed, "installed Core version")
    incoming_version = parse_semver(incoming, "incoming Core version")
    comparison = compare_semver(incoming, installed)
    if comparison < 0:
        raise LifecycleFailure(
            f"Core downgrade is not supported: {installed} -> {incoming}."
        )
    if comparison == 0:
        return
    if installed_version[0] != incoming_version[0]:
        raise LifecycleFailure(
            f"Core major-version upgrade requires manual adoption: "
            f"{installed} -> {incoming}."
        )
    if installed_version[0] == 0 and installed_version[1] != incoming_version[1]:
        raise LifecycleFailure(
            "Pre-1.0 minor-version upgrades may change the lifecycle contract; "
            f"adopt manually: {installed} -> {incoming}."
        )


def normalized_relative(value: str) -> Path:
    if not isinstance(value, str) or not value:
        raise LifecycleFailure("manifest paths must be non-empty strings.")
    if "\\" in value:
        raise LifecycleFailure(
            f"manifest paths must use normalized forward slashes: {value!r}"
        )
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or "." in pure.parts
        or pure.as_posix() != value
    ):
        raise LifecycleFailure(f"unsafe manifest path: {value!r}")
    if os.name == "nt":
        for part in pure.parts:
            if ":" in part or part.endswith((" ", ".")):
                raise LifecycleFailure(
                    f"unsafe Windows managed path segment: {part!r}"
                )
            device_name = part.split(".", 1)[0].upper()
            if device_name in WINDOWS_RESERVED_NAMES:
                raise LifecycleFailure(
                    f"reserved Windows managed path segment: {part!r}"
                )
    return Path(*pure.parts)


def target_root(raw_target: str) -> Path:
    requested = Path(raw_target).expanduser()
    lexical = Path(os.path.abspath(requested))
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current = current / part
        if is_link_like(current):
            raise LifecycleFailure(
                "target path cannot contain symbolic links or Windows reparse points; "
                "use its canonical path: "
                f"{current}"
            )
    target = lexical.resolve(strict=False)
    source = SOURCE.resolve()
    try:
        target.relative_to(source)
    except ValueError:
        pass
    else:
        raise LifecycleFailure("target cannot be the Core template or one of its children.")
    if target.exists() and not target.is_dir():
        raise LifecycleFailure(f"target exists but is not a directory: {target}")
    return target


def assert_safe_target_path(target: Path, relative: Path, *, leaf_may_exist: bool) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise LifecycleFailure(f"unsafe project-relative path: {relative}")
    destination = target / relative
    target_resolved = target.resolve(strict=False)
    current = target
    parts = relative.parts if leaf_may_exist else relative.parent.parts
    for part in parts:
        current = current / part
        if is_link_like(current):
            raise LifecycleFailure(
                "symbolic links and Windows reparse points are not allowed "
                "in managed target paths: "
                f"{current}"
            )
        try:
            current.resolve(strict=False).relative_to(target_resolved)
        except ValueError as exc:
            raise LifecycleFailure(
                f"managed path resolves outside the target project: {current}"
            ) from exc
    if is_link_like(destination):
        raise LifecycleFailure(
            "symbolic links and Windows reparse points are not supported "
            f"as managed files: {destination}"
        )
    return destination


def template_files() -> dict[str, Path]:
    if not SOURCE.is_dir():
        raise LifecycleFailure(f"Core template directory is missing: {SOURCE}")
    entries = list(SOURCE.rglob("*"))
    linked = [path for path in entries if is_link_like(path)]
    if linked:
        raise LifecycleFailure(
            "Core template must not contain symbolic links or Windows reparse points: "
            + ", ".join(str(path.relative_to(SOURCE)) for path in linked)
        )
    files: dict[str, Path] = {}
    identities: dict[str, str] = {}
    for path in entries:
        relative = normalized_relative(path.relative_to(SOURCE).as_posix())
        normalized = relative.as_posix()
        register_managed_path(identities, relative, label="Core template")
        if is_reserved_lifecycle_path(relative):
            raise LifecycleFailure(
                f"Core template path is reserved for lifecycle state: {normalized!r}"
            )
        if not path.is_file():
            continue
        files[normalized] = path
    if not files:
        raise LifecycleFailure("Core template contains no files.")
    return dict(sorted(files.items()))


def source_version(files: dict[str, Path]) -> str:
    version_path = files.get("VERSION")
    if version_path is None:
        raise LifecycleFailure("Core template is missing VERSION.")
    version = version_path.read_text(encoding="utf-8").strip()
    parse_semver(version, "incoming Core version")
    return version


def manifest_payload(files: dict[str, Path], version: str) -> dict[str, Any]:
    managed = []
    for relative, path in files.items():
        digest = sha256_file(path)
        managed.append(
            {
                "path": relative,
                "type": "file",
                "source_sha256": digest,
                "installed_sha256": digest,
            }
        )
    return {
        "schema_version": MANIFEST_SCHEMA,
        "profile": "core",
        "version": version,
        "installed_at": utc_now(),
        "files": managed,
    }


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
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
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
    except OSError as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise LifecycleFailure(f"could not write {path} atomically: {exc}") from exc


def copy_file_atomic(
    source: Path,
    destination: Path,
    *,
    replace_existing: bool = False,
) -> None:
    """Copy metadata and content before atomically exposing the destination."""
    if not source.is_file() or is_link_like(source):
        raise LifecycleFailure(
            f"copy source is missing, non-regular, linked, or a reparse point: {source}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
        shutil.copy2(source, temporary)
        if replace_existing:
            if not destination.is_file() or is_link_like(destination):
                raise LifecycleFailure(
                    f"replacement target is no longer a regular file: {destination}"
                )
        elif destination.exists() or is_link_like(destination):
            raise LifecycleFailure(
                f"copy would overwrite an existing path: {destination}"
            )
        os.replace(temporary, destination)
    except (OSError, LifecycleFailure):
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def read_manifest(target: Path) -> dict[str, Any]:
    path = assert_safe_target_path(target, MANIFEST_RELATIVE, leaf_may_exist=True)
    if not path.is_file():
        raise LifecycleFailure(
            f"Core install manifest is missing: {path}. "
            "Use the default install operation for a new target."
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleFailure(f"Core install manifest is not readable valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise LifecycleFailure("Core install manifest must contain a JSON object.")
    if value.get("schema_version") != MANIFEST_SCHEMA or value.get("profile") != "core":
        raise LifecycleFailure(
            "unsupported Core install manifest schema or profile; merge manually."
        )
    parse_semver(value.get("version"), "installed Core version")
    files = value.get("files")
    if not isinstance(files, list) or not files:
        raise LifecycleFailure("Core install manifest must declare managed files.")
    seen: dict[str, str] = {}
    seen_files: dict[str, str] = {}
    for entry in files:
        if not isinstance(entry, dict):
            raise LifecycleFailure("each Core install manifest file entry must be an object.")
        relative = normalized_relative(entry.get("path"))
        normalized = relative.as_posix()
        if is_reserved_lifecycle_path(relative):
            raise LifecycleFailure(
                f"install manifest cannot own reserved lifecycle path: {normalized!r}"
            )
        identity = managed_path_identity(relative)
        existing_file = seen_files.get(identity)
        if existing_file is not None:
            raise LifecycleFailure(
                "duplicate or platform-aliased managed path in install manifest: "
                f"{existing_file!r} and {normalized!r}"
            )
        for other_identity, other_path in seen_files.items():
            if identity.startswith(f"{other_identity}/") or other_identity.startswith(
                f"{identity}/"
            ):
                raise LifecycleFailure(
                    "install manifest cannot treat a managed file as another "
                    f"managed path's parent: {other_path!r} and {normalized!r}"
                )
        seen_files[identity] = normalized
        register_managed_path(
            seen,
            relative,
            label="Core install manifest",
        )
        if entry.get("type") != "file":
            raise LifecycleFailure(f"unsupported managed path type for {normalized}")
        for field in ("source_sha256", "installed_sha256"):
            digest = entry.get(field)
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise LifecycleFailure(f"{normalized} has invalid {field}.")
        assert_safe_target_path(target, relative, leaf_may_exist=True)
    return value


def create_backup(
    target: Path,
    operation: str,
    paths: list[Path],
    manifest_path: Path,
) -> Path:
    assert_safe_target_path(target, BACKUP_RELATIVE, leaf_may_exist=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_root = target / BACKUP_RELATIVE / f"{stamp}-{operation}"
    try:
        backup_root.mkdir(parents=True, exist_ok=False)
        for path in paths:
            if is_link_like(path):
                raise LifecycleFailure(
                    f"backup source became linked or a reparse point: {path}"
                )
            if not path.is_file():
                continue
            relative = path.relative_to(target)
            destination = backup_root / "files" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            copy_file_atomic(path, destination)
        copy_file_atomic(manifest_path, backup_root / "install-manifest.json")
    except (OSError, LifecycleFailure) as exc:
        raise LifecycleFailure(
            "backup failed before managed files changed; inspect and remove any "
            f"partial backup at {backup_root}: {exc}"
        ) from exc
    return backup_root


def remove_empty_parents(path: Path, target: Path) -> None:
    current = path
    while current != target and current != target / ".harness":
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def install(target: Path, files: dict[str, Path], *, dry_run: bool) -> None:
    destinations: list[tuple[Path, Path]] = []
    conflicts: list[Path] = []
    if is_link_like(target):
        raise LifecycleFailure(
            "target directory cannot be a symbolic link or Windows reparse point."
        )
    for relative, source_path in files.items():
        destination = assert_safe_target_path(
            target, normalized_relative(relative), leaf_may_exist=True
        )
        parent = destination.parent
        while parent != target.parent and parent != target:
            if is_link_like(parent):
                raise LifecycleFailure(
                    "symbolic links and Windows reparse points are not allowed "
                    "in managed target paths: "
                    f"{parent}"
                )
            if parent.exists() and not parent.is_dir():
                conflicts.append(parent)
            parent = parent.parent
        if destination.exists() or is_link_like(destination):
            conflicts.append(destination)
        destinations.append((source_path, destination))
    manifest_path = assert_safe_target_path(
        target, MANIFEST_RELATIVE, leaf_may_exist=True
    )
    if manifest_path.exists() or is_link_like(manifest_path):
        conflicts.append(manifest_path)
    if conflicts:
        unique = sorted(set(conflicts), key=str)
        raise LifecycleFailure(
            "installation would overwrite existing paths:\n"
            + "\n".join(f"  - {path}" for path in unique)
            + "\nMove the files, choose another target, or merge manually."
        )

    print(f"Install Core {source_version(files)}: {len(destinations)} files")
    for _, destination in destinations:
        print(f"  CREATE {destination}")
    print(f"  CREATE {manifest_path}")
    if dry_run:
        print("Dry run only; no files written.")
        return

    created_files: list[Path] = []
    created_directories: list[Path] = []
    try:
        if not target.exists():
            target.mkdir(parents=True)
            created_directories.append(target)
        for source_path, destination in destinations:
            missing_parents: list[Path] = []
            parent = destination.parent
            while not parent.exists():
                if is_link_like(parent):
                    raise LifecycleFailure(
                        "symbolic links and Windows reparse points are not allowed "
                        "in managed target paths: "
                        f"{parent}"
                    )
                missing_parents.append(parent)
                parent = parent.parent
            destination.parent.mkdir(parents=True, exist_ok=True)
            created_directories.extend(reversed(missing_parents))
            created_files.append(destination)
            copy_file_atomic(source_path, destination)
        missing_manifest_parents: list[Path] = []
        parent = manifest_path.parent
        while not parent.exists():
            missing_manifest_parents.append(parent)
            parent = parent.parent
        atomic_write_json(
            manifest_path,
            manifest_payload(files, source_version(files)),
        )
        created_files.append(manifest_path)
        created_directories.extend(reversed(missing_manifest_parents))
    except (OSError, LifecycleFailure) as exc:
        for path in reversed(created_files):
            path.unlink(missing_ok=True)
        for path in reversed(created_directories):
            try:
                path.rmdir()
            except OSError:
                pass
        raise LifecycleFailure(
            f"installation failed and newly created files were rolled back: {exc}"
        ) from exc
    print(f"Installed Core profile into {target}")
    print(f"manifest: {manifest_path}")


def upgrade(
    target: Path,
    files: dict[str, Path],
    *,
    dry_run: bool,
    accept_merged: bool,
) -> None:
    manifest = read_manifest(target)
    manifest_path = target / MANIFEST_RELATIVE
    next_version = source_version(files)
    installed_version = manifest["version"]
    validate_upgrade_versions(installed_version, next_version)
    previous = {entry["path"]: entry for entry in manifest["files"]}
    incoming = {
        relative: {
            "path": source_path,
            "sha256": sha256_file(source_path),
        }
        for relative, source_path in files.items()
    }
    previous_identities = {
        managed_path_identity(normalized_relative(relative)): relative
        for relative in previous
    }
    incoming_identities = {
        managed_path_identity(normalized_relative(relative)): relative
        for relative in incoming
    }
    aliased_changes: list[tuple[str, str]] = []
    for previous_identity, previous_path in previous_identities.items():
        for incoming_identity, incoming_path in incoming_identities.items():
            if previous_path == incoming_path:
                continue
            if (
                previous_identity == incoming_identity
                or previous_identity.startswith(f"{incoming_identity}/")
                or incoming_identity.startswith(f"{previous_identity}/")
            ):
                aliased_changes.append((previous_path, incoming_path))
    if aliased_changes:
        details = ", ".join(
            f"{old!r} -> {new!r}" for old, new in aliased_changes
        )
        raise LifecycleFailure(
            "upgrade contains case-only or platform-aliased managed path changes; "
            f"adopt them manually: {details}"
        )
    replacements: list[tuple[Path, Path]] = []
    additions: list[tuple[Path, Path]] = []
    removals: list[Path] = []
    preserved: list[Path] = []
    accepted_merged: list[Path] = []
    accepted_removed: list[Path] = []
    conflicts: list[str] = []

    for relative in sorted(set(previous) | set(incoming)):
        destination = assert_safe_target_path(
            target, normalized_relative(relative), leaf_may_exist=True
        )
        old = previous.get(relative)
        new = incoming.get(relative)
        if old is None:
            if destination.exists() or is_link_like(destination):
                conflicts.append(f"{relative}: incoming file collides with an unmanaged path")
            else:
                additions.append((new["path"], destination))
            continue
        if not destination.is_file() or is_link_like(destination):
            conflicts.append(f"{relative}: managed file is missing or is not a regular file")
            continue
        current_digest = sha256_file(destination)
        old_digest = old["installed_sha256"]
        if new is None:
            if current_digest == old_digest:
                removals.append(destination)
            elif accept_merged:
                accepted_removed.append(destination)
            else:
                conflicts.append(
                    f"{relative}: locally modified file cannot be removed "
                    f"(baseline {old_digest[:12]}, current {current_digest[:12]}, "
                    "incoming removed)"
                )
            continue
        new_digest = new["sha256"]
        if current_digest == old_digest:
            if new_digest != old_digest:
                replacements.append((new["path"], destination))
        elif new_digest == old_digest:
            preserved.append(destination)
        elif accept_merged:
            accepted_merged.append(destination)
        else:
            conflicts.append(
                f"{relative}: both the project and incoming Core changed "
                f"(baseline {old_digest[:12]}, current {current_digest[:12]}, "
                f"incoming {new_digest[:12]}); merge manually"
            )

    if conflicts:
        raise LifecycleFailure(
            f"upgrade {installed_version} -> {next_version} refused before writing:\n"
            + "\n".join(f"  - {item}" for item in conflicts)
            + f"\nIncoming files remain available at {SOURCE}."
        )

    print(f"Upgrade Core {installed_version} -> {next_version}")
    for _, destination in replacements:
        print(f"  REPLACE {destination}")
    for _, destination in additions:
        print(f"  CREATE {destination}")
    for destination in removals:
        print(f"  REMOVE {destination}")
    for destination in preserved:
        print(f"  PRESERVE LOCAL {destination}")
    for destination in accepted_merged:
        print(f"  ACCEPT MERGED {destination}")
    for destination in accepted_removed:
        print(f"  RELEASE TO PROJECT {destination}")
    if not replacements and not additions and not removals:
        print("  No managed file changes.")
    if dry_run:
        print("Dry run only; no files written.")
        return

    manifest_transition = (
        installed_version != next_version
        or bool(accepted_merged)
        or bool(accepted_removed)
    )
    if (
        not replacements
        and not additions
        and not removals
        and not manifest_transition
    ):
        print("Core is already current; no files or manifest were written.")
        return

    affected_existing = [destination for _, destination in replacements] + removals
    backup_root = create_backup(
        target, "upgrade", affected_existing, manifest_path
    )
    created: list[Path] = []
    try:
        for source_path, destination in replacements:
            copy_file_atomic(source_path, destination, replace_existing=True)
        for source_path, destination in additions:
            assert_safe_target_path(
                target, destination.relative_to(target), leaf_may_exist=True
            )
            created.append(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            copy_file_atomic(source_path, destination)
        for destination in removals:
            destination.unlink()
            remove_empty_parents(destination.parent, target)
        payload = manifest_payload(files, next_version)
        payload["upgraded_at"] = utc_now()
        payload["previous_version"] = manifest.get("version")
        atomic_write_json(manifest_path, payload)
    except (OSError, LifecycleFailure) as exc:
        for path in created:
            path.unlink(missing_ok=True)
            remove_empty_parents(path.parent, target)
        backup_files = backup_root / "files"
        if backup_files.exists():
            for backup in backup_files.rglob("*"):
                if backup.is_file():
                    relative = backup.relative_to(backup_files)
                    destination = target / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    copy_file_atomic(
                        backup,
                        destination,
                        replace_existing=destination.is_file()
                        and not is_link_like(destination),
                    )
        copy_file_atomic(
            backup_root / "install-manifest.json",
            manifest_path,
            replace_existing=manifest_path.is_file()
            and not is_link_like(manifest_path),
        )
        raise LifecycleFailure(
            f"upgrade failed and managed files were restored from {backup_root}: {exc}"
        ) from exc
    print(f"Upgraded Core profile in {target}")
    print(f"backup: {backup_root}")
    print("backup may be removed after the upgraded project passes its init adapter")


def remove(target: Path, *, dry_run: bool) -> None:
    manifest = read_manifest(target)
    manifest_path = target / MANIFEST_RELATIVE
    managed: list[Path] = []
    conflicts: list[str] = []
    for entry in manifest["files"]:
        relative = normalized_relative(entry["path"])
        path = assert_safe_target_path(target, relative, leaf_may_exist=True)
        if not path.is_file() or is_link_like(path):
            conflicts.append(f"{entry['path']}: missing or not a regular file")
            continue
        if sha256_file(path) != entry["installed_sha256"]:
            conflicts.append(f"{entry['path']}: locally modified; preserve and merge manually")
            continue
        managed.append(path)
    if conflicts:
        raise LifecycleFailure(
            "removal refused before writing:\n"
            + "\n".join(f"  - {item}" for item in conflicts)
        )

    print(f"Remove Core {manifest.get('version')}: {len(managed)} files")
    for path in managed:
        print(f"  REMOVE {path}")
    print(f"  REMOVE {manifest_path}")
    if dry_run:
        print("Dry run only; no files written.")
        return

    backup_root = create_backup(target, "remove", managed, manifest_path)
    try:
        for path in managed:
            path.unlink()
            remove_empty_parents(path.parent, target)
        manifest_path.unlink()
    except OSError as exc:
        backup_files = backup_root / "files"
        for backup in backup_files.rglob("*"):
            if backup.is_file():
                relative = backup.relative_to(backup_files)
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                copy_file_atomic(
                    backup,
                    destination,
                    replace_existing=destination.is_file()
                    and not is_link_like(destination),
                )
        copy_file_atomic(
            backup_root / "install-manifest.json",
            manifest_path,
            replace_existing=manifest_path.is_file()
            and not is_link_like(manifest_path),
        )
        raise LifecycleFailure(
            f"removal failed and managed files were restored from {backup_root}: {exc}"
        ) from exc
    print(f"Removed unchanged Core-managed files from {target}")
    print(f"backup: {backup_root}")
    print("backup may be removed after project-owned files are confirmed intact")
    print("Project-authored files and runtime evidence were preserved.")


def main() -> int:
    args = build_parser().parse_args()
    try:
        target = target_root(args.target)
        if args.remove:
            if args.accept_merged:
                raise LifecycleFailure("--accept-merged is valid only with --upgrade.")
            if not target.is_dir():
                raise LifecycleFailure("remove target directory does not exist.")
            remove(target, dry_run=args.dry_run)
        else:
            files = template_files()
        if args.upgrade:
            if not target.is_dir():
                raise LifecycleFailure("upgrade target directory does not exist.")
            upgrade(
                target,
                files,
                dry_run=args.dry_run,
                accept_merged=args.accept_merged,
            )
        elif not args.remove:
            if args.accept_merged:
                raise LifecycleFailure("--accept-merged is valid only with --upgrade.")
            install(target, files, dry_run=args.dry_run)
    except LifecycleFailure as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
