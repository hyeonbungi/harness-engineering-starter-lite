from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import ntpath
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "scripts/install_core.py"
VALIDATOR = ROOT / "scripts/validate_harness.py"


def gate_command(level: str, exit_code: int = 0) -> dict[str, object]:
    script = (
        "from pathlib import Path; "
        "p=Path('.harness/gates.log'); "
        "p.parent.mkdir(parents=True, exist_ok=True); "
        f"p.write_text((p.read_text() if p.exists() else '') + '{level}\\n'); "
        f"raise SystemExit({exit_code})"
    )
    return {
        "id": f"fixture-{level.lower()}",
        "name": f"fixture-{level.lower()}",
        "argv": [sys.executable, "-c", script],
        "cwd": ".",
        "timeout_seconds": 30,
        "max_output_bytes": 8192,
        "why": f"The fixture uses {level} to prove staged gate execution.",
        "fix": f"Restore the passing {level} fixture command and rerun.",
    }


def next_patch_version(version: str) -> str:
    major, minor, patch = (
        int(part) for part in version.split("-", 1)[0].split(".")
    )
    return f"{major}.{minor}.{patch + 1}"


class CoreProfileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="harness-core-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.target = self.base / "project"
        result = subprocess.run(
            [sys.executable, str(INSTALLER), str(self.target)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.configure_fixture()

    def configure_fixture(self) -> None:
        config_path = self.target / "harness.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["configured"] = True
        config["project"] = {
            "name": "cold-start-fixture",
            "summary": "A deterministic fixture for the Core harness profile.",
            "architecture": "docs/ARCHITECTURE.md",
        }
        config["commands"]["setup"] = {
            "argv": [
                sys.executable,
                "-c",
                "from pathlib import Path; Path('.fixture-setup').write_text('ready\\n')",
            ],
            "cwd": ".",
            "timeout_seconds": 30,
            "required": False,
            "unavailable_reason": "",
        }
        config["commands"]["start"] = {
            "argv": [sys.executable, "-c", "print('fixture-start-ready')"],
            "cwd": ".",
            "timeout_seconds": 30,
            "required": True,
            "unavailable_reason": "",
        }
        for level in ("V0", "V1", "V2", "V3", "V4"):
            existing = config["gates"][level]["commands"] if level == "V1" else []
            config["gates"][level]["commands"] = [*existing, gate_command(level)]
        for profile in config["risk_profiles"].values():
            profile["enabled"] = True
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        feature_path = self.target / "feature_list.json"
        features = json.loads(feature_path.read_text(encoding="utf-8"))
        features["project"] = "cold-start-fixture"
        features["last_updated"] = date.today().isoformat()
        features["features"].append(
            {
                "id": "BOOT-002",
                "priority": 2,
                "area": "fixture",
                "title": "Prove the WIP limit",
                "behavior": "A second feature cannot become active while BOOT-001 is active.",
                "status": "not_started",
                "risk_profile": "docs_only",
                "verification": [
                    {
                        "id": "BOOT-002-V1",
                        "description": "Audit the WIP state contract.",
                        "bindings": [
                            {
                                "level": "V0",
                                "command_id": "harness-audit",
                            }
                        ],
                    }
                ],
                "tracked_files": ["docs/ARCHITECTURE.md"],
                "evidence": [],
                "history": [],
                "sources": ["SRC-CH-007"],
                "notes": "",
            }
        )
        feature_path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        (self.target / "docs/STATE.md").write_text(
            """# Current State

## Project

- Name: cold-start-fixture
- Purpose: Prove the Core profile without hidden context.

## Current verified state

- Core profile installed and configured.
- BOOT-001 is the highest-priority unfinished feature.

<!-- harness:state:start -->
- Active feature: none
- Next feature: BOOT-001
- Last transition: not recorded
<!-- harness:state:end -->

## Risks

- This is an isolated temporary fixture.

## Next action

- Activate BOOT-001 and execute its required gates.
""",
            encoding="utf-8",
        )
        (self.target / "docs/ARCHITECTURE.md").write_text(
            """# Architecture

## System shape

- A temporary project with one Python-driven verification surface.

## Boundaries

- The installed Core profile owns only harness files.
- Product commands are declared as argument arrays.
""",
            encoding="utf-8",
        )
        (self.target / "docs/VALIDATION.md").write_text(
            """# Validation

## Gate levels

- V0 through V4 append their level to `.harness/gates.log`.

## Golden journeys

- Install, initialize twice, transition state, and preserve a receipt.
""",
            encoding="utf-8",
        )

    def run_cli(
        self,
        *args: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/harness.py", *args],
            cwd=self.target,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_init(self, *args: str) -> subprocess.CompletedProcess[str]:
        if os.name == "nt":
            powershell = shutil.which("pwsh") or shutil.which("powershell")
            if powershell is None:
                self.fail("native Windows verification requires PowerShell 5.1+")
            command = [
                powershell,
                "-NoProfile",
                "-File",
                str(self.target / "init.ps1"),
            ]
            if "--setup" in args or "-Setup" in args:
                command.append("-Setup")
        else:
            command = ["./init.sh", *args]
        return subprocess.run(
            command,
            cwd=self.target,
            text=True,
            capture_output=True,
            check=False,
        )

    def read_features(self) -> dict[str, object]:
        return json.loads(
            (self.target / "feature_list.json").read_text(encoding="utf-8")
        )

    def feature(self, feature_id: str) -> dict[str, object]:
        return next(
            feature
            for feature in self.read_features()["features"]
            if feature["id"] == feature_id
        )

    def replace_gate(self, level: str, exit_code: int) -> None:
        path = self.target / "harness.config.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config["gates"][level]["commands"] = [gate_command(level, exit_code)]
        path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def append_gate_command(self, level: str, command: dict[str, object]) -> None:
        path = self.target / "harness.config.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config["gates"][level]["commands"].append(command)
        path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def set_gate_commands(
        self,
        level: str,
        commands: list[dict[str, object]],
    ) -> None:
        path = self.target / "harness.config.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config["gates"][level]["commands"] = commands
        path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def append_feature(
        self,
        feature_id: str,
        *,
        command_id: str,
        tracked_file: str,
    ) -> None:
        path = self.target / "feature_list.json"
        features = json.loads(path.read_text(encoding="utf-8"))
        features["features"].append(
            {
                "id": feature_id,
                "priority": 3,
                "area": "representative-stack",
                "title": f"Verify {feature_id}",
                "behavior": "The representative stack command runs through the Core gate contract.",
                "status": "not_started",
                "risk_profile": "local_code",
                "verification": [
                    {
                        "id": f"{feature_id}-V1",
                        "description": "Run the representative stack verification.",
                        "bindings": [
                            {
                                "level": "V1",
                                "command_id": command_id,
                            }
                        ],
                    }
                ],
                "tracked_files": [tracked_file],
                "evidence": [],
                "history": [],
                "sources": ["SRC-PRJ-002"],
                "notes": "",
            }
        )
        path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def make_release(
        self,
        version: str,
        *,
        changed_files: tuple[str, ...] = (),
    ) -> Path:
        release = self.base / f"release-{version}"
        (release / "scripts").mkdir(parents=True)
        shutil.copy2(INSTALLER, release / "scripts/install_core.py")
        shutil.copytree(ROOT / "template/core", release / "template/core")
        (release / "template/core/VERSION").write_text(
            version + "\n",
            encoding="utf-8",
        )
        for relative in changed_files:
            path = release / "template/core" / relative
            path.write_text(
                path.read_text(encoding="utf-8")
                + f"\nFixture release {version} change.\n",
                encoding="utf-8",
            )
        return release / "scripts/install_core.py"

    def load_installer_module(self, label: str) -> object:
        spec = importlib.util.spec_from_file_location(
            f"harness_install_core_{label}",
            INSTALLER,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def load_harness_module(self, label: str) -> object:
        harness_path = self.target / "scripts/harness.py"
        spec = importlib.util.spec_from_file_location(
            f"harness_core_{label}",
            harness_path,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def load_validator_module(self, label: str) -> object:
        spec = importlib.util.spec_from_file_location(
            f"harness_validator_{label}",
            VALIDATOR,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def make_directory_symlink(self, source: Path, destination: Path) -> None:
        try:
            destination.symlink_to(source, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"directory symlinks are unavailable: {exc}")

    def test_installer_dry_run_and_collision_safety(self) -> None:
        another = self.base / "dry-run-project"
        dry_run = subprocess.run(
            [sys.executable, str(INSTALLER), str(another), "--dry-run"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(dry_run.returncode, 0, dry_run.stdout + dry_run.stderr)
        self.assertFalse(another.exists())

        collision = subprocess.run(
            [sys.executable, str(INSTALLER), str(self.target)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(collision.returncode, 0)
        self.assertIn("overwrite", collision.stderr)

        blocked = self.base / "blocked-project"
        blocked.mkdir()
        (blocked / "docs").write_text("not a directory\n", encoding="utf-8")
        blocked_result = subprocess.run(
            [sys.executable, str(INSTALLER), str(blocked)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(blocked_result.returncode, 0)
        self.assertFalse((blocked / "AGENTS.md").exists())

    def test_installer_rejects_symlink_escape(self) -> None:
        target = self.base / "symlink-project"
        outside = self.base / "outside"
        target.mkdir()
        outside.mkdir()
        self.make_directory_symlink(outside, target / "docs")

        result = subprocess.run(
            [sys.executable, str(INSTALLER), str(target)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symbolic", result.stderr)
        self.assertFalse((outside / "STATE.md").exists())
        self.assertFalse((target / "AGENTS.md").exists())

        target_link = self.base / "linked-target"
        self.make_directory_symlink(outside, target_link)
        linked_result = subprocess.run(
            [sys.executable, str(INSTALLER), str(target_link)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(linked_result.returncode, 0)
        self.assertIn("symbolic", linked_result.stderr)

        real_parent = self.base / "real-parent"
        real_parent.mkdir()
        alias_parent = self.base / "alias-parent"
        self.make_directory_symlink(real_parent, alias_parent)
        ancestor_result = subprocess.run(
            [
                sys.executable,
                str(INSTALLER),
                str(alias_parent / "nested-project"),
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(ancestor_result.returncode, 0)
        self.assertIn("symbolic", ancestor_result.stderr)
        self.assertFalse((real_parent / "nested-project").exists())

    def test_link_like_helpers_reject_windows_reparse_attributes(self) -> None:
        installer_module = self.load_installer_module("reparse_contract")
        harness_module = self.load_harness_module("reparse_contract")
        fake_path = mock.Mock()
        fake_path.is_symlink.return_value = False
        fake_path.is_junction.return_value = False
        fake_path.lstat.return_value = SimpleNamespace(
            st_file_attributes=0x00000400
        )
        with mock.patch.object(installer_module.os, "name", "nt"):
            self.assertTrue(installer_module.is_link_like(fake_path))
        self.assertTrue(harness_module.is_link_like(fake_path))
        denied = mock.Mock()
        denied.is_symlink.return_value = False
        denied.is_junction.return_value = False
        denied.lstat.side_effect = PermissionError("fixture access denied")
        with self.assertRaises(harness_module.HarnessFailure):
            harness_module.is_link_like(denied)

    def test_windows_manifest_rejects_case_aliased_paths(self) -> None:
        installer_module = self.load_installer_module("case_alias")
        manifest_path = self.target / ".harness/install-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        duplicate = dict(
            next(entry for entry in manifest["files"] if entry["path"] == "AGENTS.md")
        )
        duplicate["path"] = "agents.md"
        manifest["files"].append(duplicate)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with mock.patch.object(installer_module.os, "name", "nt"):
            with self.assertRaisesRegex(
                installer_module.LifecycleFailure,
                "platform-aliased",
            ):
                installer_module.read_manifest(self.target)
            for unsafe in ("CON.txt", "folder/name.", "file:stream"):
                with self.subTest(unsafe=unsafe):
                    with self.assertRaises(installer_module.LifecycleFailure):
                        installer_module.normalized_relative(unsafe)
        with self.assertRaises(installer_module.LifecycleFailure):
            installer_module.normalized_relative(r"folder\file.txt")
        harness_module = self.load_harness_module("windows_reserved_paths")
        with mock.patch.object(harness_module.os, "name", "nt"):
            for unsafe in ("CON.txt", "folder/name.", "file:stream"):
                with self.subTest(harness_unsafe=unsafe):
                    with self.assertRaises(harness_module.HarnessFailure):
                        harness_module.safe_repo_path(unsafe)
            with self.assertRaisesRegex(
                harness_module.HarnessFailure,
                "escapes the root",
            ):
                harness_module.safe_repo_path("../outside")

    def test_versioned_install_upgrade_and_remove_lifecycle(self) -> None:
        target = self.base / "lifecycle-project"
        installed = subprocess.run(
            [sys.executable, str(INSTALLER), str(target)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        manifest_path = target / ".harness/install-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], (ROOT / "VERSION").read_text().strip())
        self.assertEqual(
            len(manifest["files"]),
            len([path for path in (ROOT / "template/core").rglob("*") if path.is_file()]),
        )

        patch_version = next_patch_version(manifest["version"])
        patch_installer = self.make_release(
            patch_version,
            changed_files=("NOTICE",),
        )
        upgrade_preview = subprocess.run(
            [
                sys.executable,
                str(patch_installer),
                str(target),
                "--upgrade",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            upgrade_preview.returncode,
            0,
            upgrade_preview.stdout + upgrade_preview.stderr,
        )
        self.assertIn("Dry run only", upgrade_preview.stdout)
        upgraded = subprocess.run(
            [sys.executable, str(patch_installer), str(target), "--upgrade"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(upgraded.returncode, 0, upgraded.stdout + upgraded.stderr)
        self.assertIn("backup:", upgraded.stdout)
        self.assertEqual((target / "VERSION").read_text().strip(), patch_version)
        self.assertIn(
            f"Fixture release {patch_version} change.",
            (target / "NOTICE").read_text(encoding="utf-8"),
        )
        upgraded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(upgraded_manifest["version"], patch_version)

        product_file = target / "product.txt"
        product_file.write_text("project-owned\n", encoding="utf-8")
        remove_preview = subprocess.run(
            [
                sys.executable,
                str(patch_installer),
                str(target),
                "--remove",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            remove_preview.returncode,
            0,
            remove_preview.stdout + remove_preview.stderr,
        )
        self.assertTrue((target / "VERSION").is_file())

        removed = subprocess.run(
            [sys.executable, str(patch_installer), str(target), "--remove"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
        self.assertTrue(product_file.is_file())
        self.assertFalse((target / "VERSION").exists())
        self.assertFalse(manifest_path.exists())
        self.assertTrue(any((target / ".harness/backups").iterdir()))

    def test_same_version_noop_upgrade_does_not_write(self) -> None:
        target = self.base / "same-version-noop-project"
        installed = subprocess.run(
            [sys.executable, str(INSTALLER), str(target)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)

        config_path = target / "harness.config.json"
        config_path.write_text(
            config_path.read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
        )
        manifest_path = target / ".harness/install-manifest.json"
        manifest_before = manifest_path.read_bytes()
        file_digests_before = {
            path.relative_to(target).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in target.rglob("*")
            if path.is_file()
        }

        preview = subprocess.run(
            [
                sys.executable,
                str(INSTALLER),
                str(target),
                "--upgrade",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        self.assertIn("No managed file changes", preview.stdout)
        self.assertEqual(manifest_path.read_bytes(), manifest_before)

        upgraded = subprocess.run(
            [sys.executable, str(INSTALLER), str(target), "--upgrade"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(upgraded.returncode, 0, upgraded.stdout + upgraded.stderr)
        self.assertIn("Core is already current", upgraded.stdout)
        self.assertNotIn("backup:", upgraded.stdout)
        self.assertFalse((target / ".harness/backups").exists())
        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        self.assertEqual(
            {
                path.relative_to(target).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in target.rglob("*")
                if path.is_file()
            },
            file_digests_before,
        )

    def test_remove_refuses_locally_modified_managed_files(self) -> None:
        result = subprocess.run(
            [sys.executable, str(INSTALLER), str(self.target), "--remove"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("locally modified", result.stderr)
        self.assertTrue((self.target / "harness.config.json").is_file())

    def test_upgrade_rejects_downgrade_and_incompatible_pre_one_minor(self) -> None:
        manifest_path = self.target / ".harness/install-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["version"] = "9.0.0"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        downgrade = subprocess.run(
            [
                sys.executable,
                str(INSTALLER),
                str(self.target),
                "--upgrade",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(downgrade.returncode, 0)
        self.assertIn("downgrade", downgrade.stderr)

        manifest["version"] = "0.3.9"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        incompatible = subprocess.run(
            [
                sys.executable,
                str(INSTALLER),
                str(self.target),
                "--upgrade",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(incompatible.returncode, 0)
        self.assertIn("Pre-1.0 minor-version", incompatible.stderr)

    def test_upgrade_failure_restores_replaced_files_and_manifest(self) -> None:
        target = self.base / "rollback-project"
        installed = subprocess.run(
            [sys.executable, str(INSTALLER), str(target)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        manifest_path = target / ".harness/install-manifest.json"
        originals = {
            "NOTICE": (target / "NOTICE").read_bytes(),
            "VERSION": (target / "VERSION").read_bytes(),
            "manifest": manifest_path.read_bytes(),
        }

        incoming = self.base / "rollback-incoming"
        shutil.copytree(ROOT / "template/core", incoming)
        current_version = (target / "VERSION").read_text(encoding="utf-8").strip()
        (incoming / "VERSION").write_text(
            next_patch_version(current_version) + "\n",
            encoding="utf-8",
        )
        for relative in ("NOTICE",):
            path = incoming / relative
            path.write_text(
                path.read_text(encoding="utf-8") + "\nRollback fixture change.\n",
                encoding="utf-8",
            )

        installer_module = self.load_installer_module("rollback")
        installer_module.SOURCE = incoming
        incoming_files = installer_module.template_files()
        real_copy = shutil.copy2
        replacement_count = 0

        def fail_during_second_replacement(
            source: str | os.PathLike[str],
            destination: str | os.PathLike[str],
            *args: object,
            **kwargs: object,
        ) -> object:
            nonlocal replacement_count
            source_path = Path(source).resolve()
            destination_path = Path(destination).resolve(strict=False)
            try:
                source_path.relative_to(incoming.resolve())
                destination_path.relative_to(target.resolve())
            except ValueError:
                pass
            else:
                replacement_count += 1
                if replacement_count == 2:
                    raise OSError("injected replacement failure")
            return real_copy(source, destination, *args, **kwargs)

        with mock.patch.object(
            installer_module.shutil,
            "copy2",
            side_effect=fail_during_second_replacement,
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(installer_module.LifecycleFailure):
                    installer_module.upgrade(
                        target,
                        incoming_files,
                        dry_run=False,
                        accept_merged=False,
                    )

        self.assertEqual((target / "NOTICE").read_bytes(), originals["NOTICE"])
        self.assertEqual((target / "VERSION").read_bytes(), originals["VERSION"])
        self.assertEqual(manifest_path.read_bytes(), originals["manifest"])
        self.assertTrue(any((target / ".harness/backups").iterdir()))

    def test_partial_created_files_are_removed_after_lifecycle_failure(self) -> None:
        installer_module = self.load_installer_module("partial_install")
        install_target = self.base / "partial-install-project"
        install_files = installer_module.template_files()
        real_copy = shutil.copy2
        injected_install_failure = False

        def fail_after_partial_install(
            source: str | os.PathLike[str],
            destination: str | os.PathLike[str],
            *args: object,
            **kwargs: object,
        ) -> object:
            nonlocal injected_install_failure
            if not injected_install_failure:
                Path(destination).write_bytes(b"partial install")
                injected_install_failure = True
                raise OSError("injected partial install failure")
            return real_copy(source, destination, *args, **kwargs)

        with mock.patch.object(
            installer_module.shutil,
            "copy2",
            side_effect=fail_after_partial_install,
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(installer_module.LifecycleFailure):
                    installer_module.install(
                        install_target,
                        install_files,
                        dry_run=False,
                    )
        self.assertFalse(install_target.exists())

        upgrade_target = self.base / "partial-upgrade-project"
        installed = subprocess.run(
            [sys.executable, str(INSTALLER), str(upgrade_target)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        manifest_path = upgrade_target / ".harness/install-manifest.json"
        original_manifest = manifest_path.read_bytes()
        original_version = (upgrade_target / "VERSION").read_bytes()
        incoming = self.base / "partial-upgrade-incoming"
        shutil.copytree(ROOT / "template/core", incoming)
        current_version = (upgrade_target / "VERSION").read_text(
            encoding="utf-8"
        ).strip()
        (incoming / "VERSION").write_text(
            next_patch_version(current_version) + "\n",
            encoding="utf-8",
        )
        added_source = incoming / "new/NEW-MANAGED.txt"
        added_source.parent.mkdir()
        added_source.write_text("incoming\n", encoding="utf-8")

        upgrade_module = self.load_installer_module("partial_upgrade")
        upgrade_module.SOURCE = incoming
        incoming_files = upgrade_module.template_files()

        def fail_after_partial_addition(
            source: str | os.PathLike[str],
            destination: str | os.PathLike[str],
            *args: object,
            **kwargs: object,
        ) -> object:
            if Path(source).resolve() == added_source.resolve():
                Path(destination).write_bytes(b"partial addition")
                raise OSError("injected partial addition failure")
            return real_copy(source, destination, *args, **kwargs)

        with mock.patch.object(
            upgrade_module.shutil,
            "copy2",
            side_effect=fail_after_partial_addition,
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(upgrade_module.LifecycleFailure):
                    upgrade_module.upgrade(
                        upgrade_target,
                        incoming_files,
                        dry_run=False,
                        accept_merged=False,
                    )
        self.assertFalse((upgrade_target / "new").exists())
        self.assertEqual((upgrade_target / "VERSION").read_bytes(), original_version)
        self.assertEqual(manifest_path.read_bytes(), original_manifest)
        self.assertEqual(
            list(upgrade_target.rglob("*.tmp")),
            [],
        )

    def test_upgrade_requires_explicit_acceptance_for_manual_merge(self) -> None:
        target = self.base / "manual-merge-project"
        installed = subprocess.run(
            [sys.executable, str(INSTALLER), str(target)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)

        managed_path = target / "AGENTS.md"
        merged_content = managed_path.read_text(encoding="utf-8") + "\nLocal merge.\n"
        managed_path.write_text(merged_content, encoding="utf-8")
        manifest_path = target / ".harness/install-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_entry = next(
            entry for entry in manifest["files"] if entry["path"] == "AGENTS.md"
        )
        manifest_entry["installed_sha256"] = "0" * 64
        manifest_entry["source_sha256"] = "0" * 64
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        refused = subprocess.run(
            [sys.executable, str(INSTALLER), str(target), "--upgrade"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("merge manually", refused.stderr)

        accepted = subprocess.run(
            [
                sys.executable,
                str(INSTALLER),
                str(target),
                "--upgrade",
                "--accept-merged",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        self.assertIn("ACCEPT MERGED", accepted.stdout)
        self.assertEqual(managed_path.read_text(encoding="utf-8"), merged_content)
        next_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        next_entry = next(
            entry for entry in next_manifest["files"] if entry["path"] == "AGENTS.md"
        )
        self.assertEqual(
            next_entry["installed_sha256"],
            hashlib.sha256((ROOT / "template/core/AGENTS.md").read_bytes()).hexdigest(),
        )

    def test_init_is_repeatable_and_cold_start_answers_are_complete(self) -> None:
        first = self.run_init("--setup")
        second = self.run_init("--setup")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual((self.target / ".fixture-setup").read_text(), "ready\n")
        for result in (first, second):
            summary_line = next(
                line
                for line in result.stdout.splitlines()
                if line.startswith("cold-start-summary: ")
            )
            inline_answers = json.loads(summary_line.split(": ", 1)[1])
            self.assertEqual(
                set(inline_answers),
                {"what", "structure", "start", "verify", "current"},
            )
            self.assertEqual(
                inline_answers["current"]["next_feature"]["id"],
                "BOOT-001",
            )

        cold = self.run_cli("cold-start", "--json")
        self.assertEqual(cold.returncode, 0, cold.stdout + cold.stderr)
        answers = json.loads(cold.stdout)
        self.assertEqual(
            set(answers), {"what", "structure", "start", "verify", "current"}
        )
        self.assertEqual(answers["what"]["name"], "cold-start-fixture")
        self.assertTrue(answers["structure"]["exists"])
        self.assertEqual(answers["current"]["next_feature"]["id"], "BOOT-001")
        start = self.run_cli("run", "start")
        self.assertEqual(start.returncode, 0, start.stdout + start.stderr)

    def test_init_reuses_audit_and_rejects_recursive_startup(self) -> None:
        harness = self.load_harness_module("init_budget")
        previous_guard = os.environ.pop(harness.INIT_REENTRANCY_ENV, None)
        try:
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch.object(
                harness,
                "audit_repository",
                wraps=harness.audit_repository,
            ) as audited:
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    result = harness.main(["init"])
            self.assertEqual(result, 0, stdout.getvalue() + stderr.getvalue())
            self.assertEqual(audited.call_count, 1)
            self.assertIn("cold-start-summary: ", stdout.getvalue())

            setup_stdout = io.StringIO()
            setup_stderr = io.StringIO()
            with mock.patch.object(
                harness,
                "audit_repository",
                wraps=harness.audit_repository,
            ) as audited_after_setup, mock.patch.object(
                harness,
                "run_declared_command",
            ) as setup_command:
                with contextlib.redirect_stdout(
                    setup_stdout
                ), contextlib.redirect_stderr(setup_stderr):
                    setup_result = harness.main(["init", "--setup"])
            self.assertEqual(
                setup_result,
                0,
                setup_stdout.getvalue() + setup_stderr.getvalue(),
            )
            setup_command.assert_called_once()
            self.assertEqual(audited_after_setup.call_count, 2)
        finally:
            if previous_guard is not None:
                os.environ[harness.INIT_REENTRANCY_ENV] = previous_guard

        guarded_environment = os.environ.copy()
        guarded_environment[harness.INIT_REENTRANCY_ENV] = json.dumps(
            [harness.repository_identity()]
        )
        guarded = self.run_cli("init", env=guarded_environment)
        self.assertNotEqual(guarded.returncode, 0)
        self.assertIn("another init is active", guarded.stderr)
        self.assertIn("WHAT:", guarded.stderr)

        sibling_environment = os.environ.copy()
        sibling_environment[harness.INIT_REENTRANCY_ENV] = json.dumps(
            [os.path.normcase(str(self.base / "different-core"))]
        )
        sibling = self.run_cli("init", env=sibling_environment)
        self.assertEqual(sibling.returncode, 0, sibling.stdout + sibling.stderr)

        config_path = self.target / "harness.config.json"
        original_config = config_path.read_text(encoding="utf-8")
        config = json.loads(original_config)
        config["startup_profile"] = "local_code"
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        safe_startup = self.run_cli("init")
        self.assertEqual(
            safe_startup.returncode,
            0,
            safe_startup.stdout + safe_startup.stderr,
        )
        self.assertNotIn("Core initialization first pass", safe_startup.stdout)
        self.assertNotIn("Core initialization repeat pass", safe_startup.stdout)

        config["gates"]["V1"]["commands"].append(
            {
                "id": "product-init-script",
                "name": "Product init script",
                "argv": ["tools/init.sh"],
                "cwd": ".",
                "timeout_seconds": 10,
                "execution_scope": "profile",
                "why": "A product script with the same basename is not Core init.",
                "fix": "Resolve only the actual repository init path.",
            }
        )
        config["gates"]["V1"]["commands"].append(
            {
                "id": "init-path-as-data",
                "name": "Init path as data",
                "argv": [sys.executable, "-c", "print('data only')", "./init.sh"],
                "cwd": ".",
                "timeout_seconds": 10,
                "execution_scope": "profile",
                "why": "A data argument is not an init invocation.",
                "fix": "Inspect interpreter argument roles before rejecting recursion.",
            }
        )
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        product_script = self.run_cli("audit")
        self.assertEqual(
            product_script.returncode,
            0,
            product_script.stdout + product_script.stderr,
        )

        config["gates"]["V1"]["commands"][0]["execution_scope"] = "profile"
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        recursive = self.run_cli("audit")
        self.assertNotEqual(recursive.returncode, 0)
        self.assertIn("can invoke init again", recursive.stderr)
        self.assertIn("WHAT:", recursive.stderr)
        self.assertIn("FIX:", recursive.stderr)
        config_path.write_text(original_config, encoding="utf-8")

    def test_claude_entrypoint_imports_agents_and_rejects_drift(self) -> None:
        for path in (
            ROOT / "CLAUDE.md",
            ROOT / "template/core/CLAUDE.md",
            self.target / "CLAUDE.md",
        ):
            lines = [
                line.strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(lines, f"{path} must not be empty")
            self.assertEqual(lines[0], "@AGENTS.md")

        (self.target / "CLAUDE.md").write_text(
            "# CLAUDE.md\n\nRead AGENTS.md manually.\n",
            encoding="utf-8",
        )
        rejected = self.run_cli("audit")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("@AGENTS.md", rejected.stderr)

    def test_resident_agent_communication_contract_is_installed_and_routed(self) -> None:
        for root in (ROOT / "template/core", self.target):
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            contract = (root / "docs/COMMUNICATION.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("docs/COMMUNICATION.md", agents)
            for required in (
                "항상 한국어",
                "존댓말",
                "컴퓨터공학과 대학생",
                "결론과 현재 상태",
                "사실·추론·제안",
            ):
                self.assertIn(required, agents)
            for required in (
                "시각적 보고",
                "완료 증거",
                "안전과 권한",
                "최종 응답 전 자기점검",
                "종료되는 자기개선 루프",
                "상시 자기개선 권한",
                "별도 사용자 명령 없이도",
            ):
                self.assertIn(required, contract)

        components = json.loads(
            (self.target / "docs/harness/components.json").read_text(
                encoding="utf-8"
            )
        )
        communication = next(
            component
            for component in components["components"]
            if component["id"] == "HC-019"
        )
        self.assertEqual(communication["path"], "docs/COMMUNICATION.md")

    def test_autonomous_structural_self_improvement_contract_is_enforced(self) -> None:
        marker = "<!-- harness:auto-improvement:v1 -->"
        for root in (ROOT / "template/core", self.target):
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            contract = (root / "docs/COMMUNICATION.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(marker, agents)
            self.assertIn(marker, contract)
            for required in (
                "별도 사용자 명령 없이도",
                "변경 금지·중지",
                "BOOT-001",
                "최대 한 번",
            ):
                self.assertIn(required, agents)
            for required in (
                "상시 자기개선 권한",
                "답변·진단·제안 중 발견해도",
                "제품 기능·데이터",
                "최대 한 번",
                "호스트의 상위 정책",
                "최종 응답 직전에 발동 조건",
            ):
                self.assertIn(required, contract)
            self.assertNotIn(
                "답변·진단·제안 요청에서는 문제와 최소 수정안만 보고",
                contract,
            )

        root_agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("별도 명령 없이도", root_agents)

        for relative in ("AGENTS.md", "docs/COMMUNICATION.md"):
            path = self.target / relative
            original = path.read_text(encoding="utf-8")
            path.write_text(original.replace(marker, "", 1), encoding="utf-8")
            rejected = self.run_cli("audit")
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("autonomous self-improvement contract drifted", rejected.stderr)
            path.write_text(original, encoding="utf-8")

        for relative, clause in (
            ("AGENTS.md", "최종 응답 직전에"),
            ("docs/COMMUNICATION.md", "답변·진단·제안 중 발견해도"),
            ("docs/COMMUNICATION.md", "제품 기능·데이터"),
        ):
            path = self.target / relative
            original = path.read_text(encoding="utf-8")
            path.write_text(original.replace(clause, "", 1), encoding="utf-8")
            rejected = self.run_cli("audit")
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("autonomous self-improvement contract drifted", rejected.stderr)
            path.write_text(original, encoding="utf-8")

        self.assertEqual(self.run_cli("audit").returncode, 0)

    def test_agent_coordination_contract_is_installed_routed_and_enforced(self) -> None:
        marker = "<!-- harness:agent-coordination:v1 -->"
        handoff_fields = (
            "task_id:",
            "status: completed | blocked | failed",
            "base_revision:",
            "result_revision:",
            "worktree_or_diff:",
            "assigned_paths:",
            "changed_paths:",
            "summary:",
            "validation:",
            "not_run:",
            "assumptions:",
            "unknowns:",
            "failures_or_conflicts:",
            "remaining_risks:",
            "integration_order:",
        )
        for root in (ROOT / "template/core", self.target):
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            contract = (root / "docs/AGENT_COORDINATION.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(marker, agents)
            self.assertIn(marker, contract)
            self.assertIn(
                "복수 에이전트 또는 병렬 작업을 명시적으로 요청한 경우에만",
                agents,
            )
            self.assertIn("일반 작업에서는 에이전트를 자동으로", agents)
            self.assertIn("writer마다 별도 worktree", contract)
            self.assertIn("소유 경로는 서로 겹치지", contract)
            self.assertIn("lead만 갱신", contract)
            self.assertIn("비 Git 프로젝트", contract)
            self.assertIn("공유 상태 격리를 정의하지 않은", contract)
            self.assertIn("lead가 직접 다시 실행", contract)
            self.assertIn("read-only reviewer", contract)
            self.assertIn("worker의 `status`는 하위 작업 결과만", contract)
            self.assertIn("`passing`이나 기능의 최종", contract)
            for field in handoff_fields:
                self.assertIn(field, contract)
            self.assertLess((root / "AGENTS.md").stat().st_size, 8 * 1024)

        root_agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(marker, root_agents)
        self.assertIn("template/core/docs/AGENT_COORDINATION.md", root_agents)

        components = json.loads(
            (self.target / "docs/harness/components.json").read_text(
                encoding="utf-8"
            )
        )
        coordination = next(
            component
            for component in components["components"]
            if component["id"] == "HC-022"
        )
        self.assertEqual(coordination["path"], "docs/AGENT_COORDINATION.md")
        self.assertEqual(
            coordination["sources"],
            [
                "SRC-CH-007..009",
                "SRC-TPL-001",
                "SRC-TPL-006",
                "SRC-TPL-010",
                "SRC-PRJ-004",
                "SRC-PRJ-006",
            ],
        )
        manifest = json.loads(
            (self.target / ".harness/install-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        managed = {entry["path"] for entry in manifest["files"]}
        self.assertEqual(len(managed), 22)
        self.assertIn("docs/AGENT_COORDINATION.md", managed)

        harness = self.load_harness_module("agent_coordination")
        for relative, required_text in harness.AGENT_COORDINATION_REQUIREMENTS.items():
            path = self.target / relative
            original = path.read_text(encoding="utf-8")
            for clause in (harness.AGENT_COORDINATION_MARKER, *required_text):
                with self.subTest(relative=relative, clause=clause):
                    try:
                        path.write_text(
                            original.replace(clause, ""),
                            encoding="utf-8",
                        )
                        rejected = self.run_cli("audit")
                        self.assertNotEqual(rejected.returncode, 0)
                        self.assertIn(
                            "agent coordination contract drifted",
                            rejected.stderr,
                        )
                        self.assertIn("WHAT:", rejected.stderr)
                        self.assertIn("WHY:", rejected.stderr)
                        self.assertIn("FIX:", rejected.stderr)
                    finally:
                        path.write_text(original, encoding="utf-8")

        restored = self.run_cli("audit")
        self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)

    @unittest.skipUnless(shutil.which("git"), "Git is not installed")
    def test_parallel_writer_worktrees_preserve_lead_control_plane(self) -> None:
        def git(
            cwd: Path,
            *args: str,
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", *args],
                cwd=cwd,
                text=True,
                capture_output=True,
                check=False,
            )

        left = self.target / "worker-left.txt"
        right = self.target / "worker-right.txt"
        left.write_bytes(b"baseline-left\n")
        right.write_bytes(b"baseline-right\n")
        self.assertEqual(git(self.target, "init").returncode, 0)
        self.assertEqual(
            git(self.target, "config", "user.name", "Harness Fixture").returncode,
            0,
        )
        self.assertEqual(
            git(
                self.target,
                "config",
                "user.email",
                "harness-fixture@example.invalid",
            ).returncode,
            0,
        )
        self.assertEqual(git(self.target, "add", "-A").returncode, 0)
        baseline_commit = git(self.target, "commit", "-m", "shared clean baseline")
        self.assertEqual(
            baseline_commit.returncode,
            0,
            baseline_commit.stdout + baseline_commit.stderr,
        )
        baseline = git(self.target, "rev-parse", "HEAD").stdout.strip()
        self.assertTrue(baseline)
        self.assertEqual(git(self.target, "status", "--porcelain").stdout, "")

        control_paths = ("feature_list.json", "docs/STATE.md")

        def control_digests() -> dict[str, str]:
            return {
                relative: hashlib.sha256(
                    (self.target / relative).read_bytes()
                ).hexdigest()
                for relative in control_paths
            }

        control_before = control_digests()
        left_worktree = self.base / "writer-left-worktree"
        right_worktree = self.base / "writer-right-worktree"
        for branch, worktree in (
            ("fixture/writer-left", left_worktree),
            ("fixture/writer-right", right_worktree),
        ):
            created = git(
                self.target,
                "worktree",
                "add",
                "-b",
                branch,
                str(worktree),
                baseline,
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            self.assertEqual(git(worktree, "rev-parse", "HEAD").stdout.strip(), baseline)

        (left_worktree / left.name).write_bytes(b"baseline-left\nwriter-left\n")
        (right_worktree / right.name).write_bytes(
            b"baseline-right\nwriter-right\n"
        )
        self.assertEqual(control_digests(), control_before)
        self.assertEqual(git(self.target, "status", "--porcelain").stdout, "")

        worker_heads: list[str] = []
        for worktree, owned_path in (
            (left_worktree, left.name),
            (right_worktree, right.name),
        ):
            self.assertEqual(git(worktree, "add", owned_path).returncode, 0)
            committed = git(worktree, "commit", "-m", f"update {owned_path}")
            self.assertEqual(committed.returncode, 0, committed.stdout + committed.stderr)
            head = git(worktree, "rev-parse", "HEAD").stdout.strip()
            worker_heads.append(head)
            changed = {
                line
                for line in git(
                    worktree,
                    "diff",
                    "--name-only",
                    f"{baseline}..{head}",
                ).stdout.splitlines()
                if line
            }
            self.assertEqual(changed, {owned_path})
            focused = git(worktree, "diff", "--check", f"{baseline}..{head}")
            self.assertEqual(focused.returncode, 0, focused.stdout + focused.stderr)

        self.assertEqual(control_digests(), control_before)
        for head in worker_heads:
            integrated = git(self.target, "cherry-pick", head)
            self.assertEqual(
                integrated.returncode,
                0,
                integrated.stdout + integrated.stderr,
            )
            focused = git(self.target, "diff", "--check", "HEAD^", "HEAD")
            self.assertEqual(focused.returncode, 0, focused.stdout + focused.stderr)

        self.assertEqual(control_digests(), control_before)
        self.assertEqual(left.read_text(encoding="utf-8"), "baseline-left\nwriter-left\n")
        self.assertEqual(
            right.read_text(encoding="utf-8"),
            "baseline-right\nwriter-right\n",
        )
        lead_gate = self.run_cli("audit")
        self.assertEqual(lead_gate.returncode, 0, lead_gate.stdout + lead_gate.stderr)

        for worktree in (left_worktree, right_worktree):
            removed = git(self.target, "worktree", "remove", str(worktree))
            self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
        self.assertEqual(git(self.target, "status", "--porcelain").stdout, "")

    def test_callable_harness_audit_skill_is_installed_and_routed(self) -> None:
        canonical_relative = ".agents/skills/audit-harness-health/SKILL.md"
        bridge_relatives = (
            ".claude/skills/audit-harness-health/SKILL.md",
        )
        target = "../../../.agents/skills/audit-harness-health/SKILL.md"

        def frontmatter_value(text: str, key: str) -> str:
            prefix = f"{key}:"
            return next(
                line.split(":", 1)[1].strip()
                for line in text.splitlines()
                if line.startswith(prefix)
            )

        for root in (ROOT / "template/core", self.target):
            self.assertFalse(
                (root / ".codex/skills/audit-harness-health/SKILL.md").exists()
            )
            canonical_path = root / canonical_relative
            canonical = canonical_path.read_text(encoding="utf-8")
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("$audit-harness-health", agents)
            self.assertIn("감사 중에는 자동 개선을 수행하지 않고", agents)
            self.assertIn("<!-- harness:audit-skill:v1 -->", canonical)
            self.assertIn("읽기 전용", canonical)
            self.assertIn("python3 scripts/harness.py audit", canonical)
            self.assertIn("빠른 감사", canonical)
            self.assertIn("집중 감사", canonical)
            self.assertIn("깊은 감사", canonical)
            self.assertIn("git status --short", canonical)
            self.assertIn("일반 코드 리뷰", canonical)
            self.assertIn("작은 수정", canonical)
            canonical_description = frontmatter_value(canonical, "description")

            for relative in bridge_relatives:
                path = root / relative
                bridge = path.read_text(encoding="utf-8")
                self.assertIn("<!-- harness:skill-bridge:v1 -->", bridge)
                self.assertIn(target, bridge)
                self.assertIn("처음부터 끝까지 읽고", bridge)
                self.assertNotIn("<!-- harness:audit-skill:v1 -->", bridge)
                self.assertNotIn("## 핵심 계약", bridge)
                self.assertLess(path.stat().st_size, 2 * 1024)
                self.assertLess(path.stat().st_size, canonical_path.stat().st_size)
                self.assertEqual(
                    frontmatter_value(bridge, "description"),
                    canonical_description,
                )
                self.assertEqual(
                    (path.parent / target).resolve(),
                    canonical_path.resolve(),
                )

        manifest = json.loads(
            (self.target / ".harness/install-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        managed = {entry["path"] for entry in manifest["files"]}
        self.assertIn(canonical_relative, managed)
        self.assertTrue(set(bridge_relatives).issubset(managed))

        def snapshot() -> dict[str, str]:
            return {
                path.relative_to(self.target).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in self.target.rglob("*")
                if path.is_file()
            }

        before = snapshot()
        healthy = self.run_cli("audit")
        self.assertEqual(healthy.returncode, 0, healthy.stdout + healthy.stderr)
        self.assertEqual(snapshot(), before)

        drift_cases = (
            (canonical_relative, "<!-- harness:audit-skill:v1 -->", ""),
            (bridge_relatives[0], target, "../../../.broken/SKILL.md"),
            (bridge_relatives[0], "description:", "description: drifted "),
        )
        for relative, old, new in drift_cases:
            path = self.target / relative
            original = path.read_text(encoding="utf-8")
            path.write_text(original.replace(old, new, 1), encoding="utf-8")
            rejected = self.run_cli("audit")
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("audit Skill", rejected.stderr)
            path.write_text(original, encoding="utf-8")

        self.assertEqual(self.run_cli("audit").returncode, 0)

    def test_startup_context_and_operational_history_are_bounded(self) -> None:
        agents = (self.target / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("cold-start --json", agents)
        self.assertIn("cold-start-summary", agents)
        self.assertIn("일반 시작에서는 미리 읽지 않고", agents)
        self.assertIn("집중 검사를 우선", agents)

        harness = self.load_harness_module("bounded_context")
        self.assertEqual(
            harness.ALWAYS_READ_CONTEXT_LIMITS,
            {
                "AGENTS.md": 8 * 1024,
                "CLAUDE.md": 4 * 1024,
                "docs/STATE.md": 16 * 1024,
            },
        )
        self.assertEqual(harness.MAX_ALWAYS_READ_CONTEXT_BYTES, 12 * 1024)
        self.assertEqual(
            harness.ON_DEMAND_CONTEXT_LIMITS,
            {
                "docs/COMMUNICATION.md": 16 * 1024,
                "docs/AGENT_COORDINATION.md": 12 * 1024,
            },
        )
        always_total = sum(
            (self.target / relative).stat().st_size
            for relative in harness.ALWAYS_READ_CONTEXT_LIMITS
        )
        self.assertLessEqual(always_total, harness.MAX_ALWAYS_READ_CONTEXT_BYTES)

        agents_path = self.target / "AGENTS.md"
        original_agents = agents_path.read_text(encoding="utf-8")
        agents_path.write_text(
            original_agents + "\n" + "x" * (8 * 1024),
            encoding="utf-8",
        )
        oversized = self.run_cli("audit")
        self.assertNotEqual(oversized.returncode, 0)
        self.assertIn("context limit", oversized.stderr)
        self.assertIn("do not raise the limit", oversized.stderr)
        agents_path.write_text(original_agents, encoding="utf-8")

        state_path = self.target / "docs/STATE.md"
        original_state = state_path.read_text(encoding="utf-8")
        state_path.write_text(
            original_state + "\n" + "s" * (6 * 1024),
            encoding="utf-8",
        )
        combined = self.run_cli("audit")
        self.assertNotEqual(combined.returncode, 0)
        self.assertIn("always-read context", combined.stderr)
        self.assertIn("combined limit", combined.stderr)
        state_path.write_text(original_state, encoding="utf-8")

        communication_path = self.target / "docs/COMMUNICATION.md"
        original_communication = communication_path.read_text(encoding="utf-8")
        communication_path.write_text(
            original_communication.replace(
                "온디맨드 조건을 만족할 때만",
                "항상 읽는 경우에",
                1,
            ),
            encoding="utf-8",
        )
        ambiguous = self.run_cli("audit")
        self.assertNotEqual(ambiguous.returncode, 0)
        self.assertIn("context routing drifted", ambiguous.stderr)
        communication_path.write_text(original_communication, encoding="utf-8")

        coordination_path = self.target / "docs/AGENT_COORDINATION.md"
        original_coordination = coordination_path.read_text(encoding="utf-8")
        coordination_path.write_text(
            original_coordination + "\n" + "c" * (12 * 1024),
            encoding="utf-8",
        )
        oversized_on_demand = self.run_cli("audit")
        self.assertNotEqual(oversized_on_demand.returncode, 0)
        self.assertIn("docs/AGENT_COORDINATION.md", oversized_on_demand.stderr)
        coordination_path.write_text(original_coordination, encoding="utf-8")

        feature = {"history": [], "evidence": []}
        for index in range(harness.MAX_FEATURE_HISTORY_EVENTS + 3):
            harness.append_bounded_feature_entry(
                feature,
                "history",
                {"index": index},
                harness.MAX_FEATURE_HISTORY_EVENTS,
            )
        for index in range(harness.MAX_FEATURE_EVIDENCE_REFERENCES + 3):
            harness.append_bounded_feature_entry(
                feature,
                "evidence",
                {"index": index},
                harness.MAX_FEATURE_EVIDENCE_REFERENCES,
            )
        self.assertEqual(len(feature["history"]), 20)
        self.assertEqual(feature["history"][0]["index"], 3)
        self.assertEqual(len(feature["evidence"]), 5)
        self.assertEqual(feature["evidence"][0]["index"], 3)

        feature_path = self.target / "feature_list.json"
        original_features = feature_path.read_text(encoding="utf-8")
        features = json.loads(original_features)
        features["features"][1]["history"] = [
            {"index": index}
            for index in range(harness.MAX_FEATURE_HISTORY_EVENTS + 1)
        ]
        feature_path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        accumulated = self.run_cli("audit")
        self.assertNotEqual(accumulated.returncode, 0)
        self.assertIn("operational window is 20", accumulated.stderr)

        features = json.loads(original_features)
        features["features"][1]["evidence"] = [
            {"index": index}
            for index in range(harness.MAX_FEATURE_EVIDENCE_REFERENCES + 1)
        ]
        feature_path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        accumulated = self.run_cli("audit")
        self.assertNotEqual(accumulated.returncode, 0)
        self.assertIn("operational window is 5", accumulated.stderr)

    def test_feature_and_tracked_evidence_audit_work_is_bounded(self) -> None:
        harness = self.load_harness_module("tracked_evidence_budget")
        feature_path = self.target / "feature_list.json"
        original_features = feature_path.read_text(encoding="utf-8")
        features = json.loads(original_features)
        features["features"] = features["features"] * (
            harness.MAX_FEATURES // len(features["features"]) + 1
        )
        feature_path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        too_many_features = self.run_cli("audit")
        self.assertNotEqual(too_many_features.returncode, 0)
        self.assertIn("audit limit is 256", too_many_features.stderr)

        features = json.loads(original_features)
        features["features"][0]["tracked_files"] = [
            "docs/ARCHITECTURE.md"
        ] * (harness.MAX_TRACKED_FILES_PER_FEATURE + 1)
        feature_path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        too_many_paths = self.run_cli("audit")
        self.assertNotEqual(too_many_paths.returncode, 0)
        self.assertIn("per-feature limit is 128", too_many_paths.stderr)

        features = json.loads(original_features)
        features["features"][0]["verification"] = [
            features["features"][0]["verification"][0]
        ] * (harness.MAX_VERIFICATION_REQUIREMENTS_PER_FEATURE + 1)
        feature_path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        too_many_requirements = self.run_cli("audit")
        self.assertNotEqual(too_many_requirements.returncode, 0)
        self.assertIn("verification has 65 requirements", too_many_requirements.stderr)

        features = json.loads(original_features)
        features["features"][0]["sources"] = ["SRC-CH-001..012"] * 11
        feature_path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        too_many_source_edges = self.run_cli("audit")
        self.assertNotEqual(too_many_source_edges.returncode, 0)
        self.assertIn("sources expands to", too_many_source_edges.stderr)
        feature_path.write_text(original_features, encoding="utf-8")

        with self.assertRaises(harness.HarnessFailure) as huge_source_range:
            harness.expand_source_reference(
                "SRC-CH-1..999999999999999999999999999999",
                {"SRC-CH-001"},
            )
        self.assertIn("finite parser budget", str(huge_source_range.exception))

        validator_spec = importlib.util.spec_from_file_location(
            "bounded_root_validator",
            ROOT / "scripts/validate_harness.py",
        )
        self.assertIsNotNone(validator_spec)
        self.assertIsNotNone(validator_spec.loader)
        validator = importlib.util.module_from_spec(validator_spec)
        validator_spec.loader.exec_module(validator)
        with self.assertRaises(SystemExit) as root_source_range:
            validator.expand_source_reference("SRC-CH-1..999999999", {"SRC-CH-001"})
        self.assertIn("finite parser budget", str(root_source_range.exception))

        oversized_json = self.target / "oversized.json"
        oversized_json.write_text(
            "{}" + " " * harness.MAX_JSON_BYTES,
            encoding="utf-8",
        )
        try:
            with self.assertRaises(harness.HarnessFailure) as json_budget:
                harness.read_json(oversized_json)
            self.assertIn("JSON audit limit", str(json_budget.exception))
        finally:
            oversized_json.unlink()

        config = json.loads(
            (self.target / "harness.config.json").read_text(encoding="utf-8")
        )
        first = {
            "id": "CACHE-A",
            "tracked_files": ["docs/ARCHITECTURE.md"],
        }
        second = {
            "id": "CACHE-B",
            "tracked_files": ["docs/ARCHITECTURE.md"],
        }
        cache = harness.TrackedFileDigestCache()
        with mock.patch.object(
            harness,
            "sha256_file",
            wraps=harness.sha256_file,
        ) as hashed:
            harness.tracked_file_entries(config, first, cache)
            harness.tracked_file_entries(config, second, cache)
        self.assertEqual(hashed.call_count, 1)

        with mock.patch.object(harness, "MAX_UNIQUE_TRACKED_BYTES", 1):
            with self.assertRaises(harness.HarnessFailure) as byte_budget:
                harness.tracked_file_entries(
                    config,
                    first,
                    harness.TrackedFileDigestCache(),
                )
        self.assertIn("per-audit byte budget", str(byte_budget.exception))

        growing_file = self.target / "growing-evidence.bin"
        growing_file.write_bytes(b"xx")
        with self.assertRaises(harness.HarnessFailure) as growing_hash:
            harness.sha256_file(growing_file, expected_size=1)
        self.assertIn("grew while it was being hashed", str(growing_hash.exception))

        receipt_cache = harness.ReceiptPayloadCache()
        config_path = self.target / "harness.config.json"
        with mock.patch.object(
            harness,
            "read_bounded_json_bytes",
            wraps=harness.read_bounded_json_bytes,
        ) as receipt_reads:
            receipt_cache.load(config_path, "harness.config.json")
            receipt_cache.load(config_path, "harness.config.json")
        self.assertEqual(receipt_reads.call_count, 1)
        with mock.patch.object(harness, "MAX_UNIQUE_RECEIPT_BYTES_PER_AUDIT", 1):
            with self.assertRaises(harness.HarnessFailure) as receipt_budget:
                harness.ReceiptPayloadCache().load(
                    config_path,
                    "harness.config.json",
                )
        self.assertIn("receipt payloads exceed", str(receipt_budget.exception))

    def test_powershell_adapters_have_a_safe_static_contract(self) -> None:
        for path in (ROOT / "init.ps1", ROOT / "template/core/init.ps1"):
            raw = path.read_bytes()
            raw.decode("ascii")
            text = raw.decode("ascii").lower()
            for required in (
                "#requires -version 5.1",
                "$psscriptroot",
                "push-location -literalpath",
                "python_manager_automatic_install",
                "sys.version_info >= (3, 10)",
                "get-command",
                "-commandtype application",
                "$lastexitcode",
                "exit $exitcode",
            ):
                self.assertIn(required, text, f"{required!r} missing from {path}")
            for forbidden in (
                "set-executionpolicy",
                "invoke-expression",
                "-executionpolicy bypass",
            ):
                self.assertNotIn(forbidden, text, f"{forbidden!r} found in {path}")
        root_text = (ROOT / "init.ps1").read_text(encoding="ascii").lower()
        core_text = (ROOT / "template/core/init.ps1").read_text(
            encoding="ascii"
        ).lower()
        self.assertIn("scripts\\validate_harness.py", root_text)
        self.assertIn('"unittest"', root_text)
        self.assertIn("[switch]$quick", root_text)
        self.assertIn("-not $quick.ispresent", root_text)
        self.assertIn("pythondontwritebytecode", root_text)
        self.assertIn(
            "export pythondontwritebytecode=1",
            (ROOT / "init.sh").read_text(encoding="ascii").lower(),
        )
        self.assertIn("[switch]$setup", core_text)
        self.assertIn('"--setup"', core_text)
        self.assertIn("scripts\\harness.py", core_text)

    def test_root_quick_preflight_defers_the_full_fixture_suite(self) -> None:
        validator = self.load_validator_module("root_quick_budgets")
        oversized_tree = self.base / "quick-tree"
        oversized_tree.mkdir()
        for index in range(3):
            (oversized_tree / f"{index}.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(SystemExit) as file_budget:
            validator.bounded_relative_files(
                oversized_tree,
                max_files=2,
                max_entries=10,
                label="test tree",
            )
        self.assertIn("more than 2 files", str(file_budget.exception))

        changed_size = oversized_tree / "0.txt"
        with self.assertRaises(SystemExit) as size_budget:
            validator.bounded_sha256(changed_size, 0, "test file")
        self.assertIn("size changed", str(size_budget.exception))

        started = time.monotonic()
        _, _, _, timed_out = validator.run_bounded_subprocess(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            cwd=self.base,
            timeout_seconds=0.1,
            max_output_bytes=1024,
        )
        self.assertTrue(timed_out)
        self.assertLess(time.monotonic() - started, 2)
        return_code, output, truncated, timed_out = validator.run_bounded_subprocess(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdout.write('x' * 100000); raise SystemExit(3)",
            ],
            cwd=self.base,
            timeout_seconds=5,
            max_output_bytes=1024,
        )
        self.assertEqual(return_code, 3)
        self.assertTrue(truncated)
        self.assertFalse(timed_out)
        self.assertLessEqual(len(output.encode("utf-8")), 1024)

        quick_orphan = self.base / "quick-orphan"
        child = (
            "import time; from pathlib import Path; "
            f"time.sleep(1.5); Path({str(quick_orphan)!r}).write_text('orphan')"
        )
        parent = (
            "import subprocess,sys; "
            f"subprocess.Popen([sys.executable, '-c', {child!r}])"
        )
        return_code, _, _, timed_out = validator.run_bounded_subprocess(
            [sys.executable, "-c", parent],
            cwd=self.base,
            timeout_seconds=5,
            max_output_bytes=1024,
        )
        self.assertEqual(return_code, 0)
        self.assertFalse(timed_out)
        time.sleep(0.8)
        self.assertFalse(quick_orphan.exists())

        environment = os.environ.copy()
        environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment.get(
            "PATH", ""
        )
        if os.name == "nt":
            powershell = shutil.which("pwsh") or shutil.which("powershell")
            if powershell is None:
                self.fail("native Windows verification requires PowerShell 5.1+")
            command = [
                powershell,
                "-NoProfile",
                "-File",
                str(ROOT / "init.ps1"),
                "-Quick",
            ]
        else:
            command = ["./init.sh", "--quick"]
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Quick baseline healthy", result.stdout)
        self.assertNotIn("test_agent_coordination_contract", result.stdout)
        self.assertNotIn("Ran 47 tests", result.stderr)

    def test_root_validator_normalizes_windows_component_paths(self) -> None:
        validator = self.load_validator_module("windows_component_paths")
        root = PureWindowsPath(r"C:\fixture\template\core")
        path = root / "docs" / "STATE.md"
        self.assertEqual(
            validator.portable_relative_path(path, root),
            "docs/STATE.md",
        )

    def test_native_powershell_adapter_when_runtime_is_available(self) -> None:
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell is None:
            if os.name == "nt":
                self.fail("native Windows verification requires PowerShell 5.1+")
            self.skipTest("PowerShell is unavailable on this non-Windows runner")
        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-File",
                str(self.target / "init.ps1"),
                "-Setup",
            ],
            cwd=self.base,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.target / ".fixture-setup").is_file())
        self.assertFalse((self.base / ".fixture-setup").exists())

        config_path = self.target / "harness.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["schema_version"] = 999
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        failed = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-File",
                str(self.target / "init.ps1"),
            ],
            cwd=self.base,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)

    def test_state_transitions_enforce_wip_and_preserve_receipts(self) -> None:
        activate = self.run_cli("state", "activate", "BOOT-001")
        self.assertEqual(activate.returncode, 0, activate.stdout + activate.stderr)

        concurrent = self.run_cli("state", "activate", "BOOT-002")
        self.assertNotEqual(concurrent.returncode, 0)
        self.assertIn("WIP=1", concurrent.stderr)

        complete = self.run_cli("complete", "BOOT-001", "--risk", "cross_component")
        self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)
        feature = self.feature("BOOT-001")
        self.assertEqual(feature["status"], "passing")
        self.assertEqual(len(feature["evidence"]), 1)
        receipt_path = self.target / feature["evidence"][0]["receipt"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["required_levels"], ["V0", "V1", "V2", "V3"])
        self.assertEqual(receipt["skipped_levels"], ["V4"])
        executed_ids = {
            (record["level"], record["command_id"])
            for record in receipt["executed"]
        }
        self.assertIn(("V0", "harness-audit"), executed_ids)
        self.assertIn(("V1", "core-init-first"), executed_ids)
        self.assertIn(("V1", "core-init-repeat"), executed_ids)
        self.assertIn(("V1", "core-cold-start"), executed_ids)
        self.assertEqual(
            [entry["path"] for entry in receipt["tracked_files"]],
            sorted(feature["tracked_files"]),
        )
        self.assertEqual(len(receipt["tracked_files_sha256"]), 64)
        self.assertEqual(receipt["schema_version"], 4)
        current_config = json.loads(
            (self.target / "harness.config.json").read_text(encoding="utf-8")
        )
        expected_config_sha256 = hashlib.sha256(
            json.dumps(
                current_config,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(receipt["config_sha256"], expected_config_sha256)
        self.assertEqual(len(receipt["execution_config_sha256"]), 64)
        self.assertEqual(receipt["runtime"]["platform"], sys.platform)
        self.assertEqual(len(receipt["runtime"]["sha256"]), 64)
        core_init_record = next(
            record
            for record in receipt["executed"]
            if record["command_id"] == "core-init-first"
        )
        self.assertEqual(core_init_record["argv"][0], sys.executable)
        self.assertNotIn("{python}", core_init_record["argv"])

        reopen = self.run_cli(
            "state",
            "reopen",
            "BOOT-001",
            "--reason",
            "A regression invalidated the current passing state.",
        )
        self.assertEqual(reopen.returncode, 0, reopen.stdout + reopen.stderr)
        reopened = self.feature("BOOT-001")
        self.assertEqual(reopened["status"], "active")
        self.assertEqual(len(reopened["evidence"]), 1)

        blocked = self.run_cli(
            "state",
            "block",
            "BOOT-001",
            "--reason",
            "External dependency unavailable; retry when it is restored.",
        )
        self.assertEqual(blocked.returncode, 0, blocked.stdout + blocked.stderr)
        self.assertEqual(self.feature("BOOT-001")["status"], "blocked")
        state = (self.target / "docs/STATE.md").read_text(encoding="utf-8")
        self.assertIn("- Active feature: none", state)
        self.assertIn("- Next feature: BOOT-001", state)

    def test_feature_verification_rejects_missing_or_out_of_profile_bindings(self) -> None:
        path = self.target / "feature_list.json"
        original = path.read_text(encoding="utf-8")
        features = json.loads(original)
        features["features"][0]["verification"][1]["bindings"][0][
            "command_id"
        ] = "missing-command"
        path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        missing = self.run_cli("audit")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("missing gate command", missing.stderr)

        features = json.loads(original)
        features["features"][0]["risk_profile"] = "docs_only"
        path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        weak = self.run_cli("audit")
        self.assertNotEqual(weak.returncode, 0)
        self.assertIn("outside risk profile", weak.stderr)

        features = json.loads(original)
        features["features"][0]["tracked_files"].append("harness.config.json")
        path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tracked_config = self.run_cli("audit")
        self.assertNotEqual(tracked_config.returncode, 0)
        self.assertIn("cannot track mutable state", tracked_config.stderr)

    def test_wip_receipt_and_receipt_schema_invariants_cannot_be_weakened(self) -> None:
        path = self.target / "feature_list.json"
        original = path.read_text(encoding="utf-8")
        features = json.loads(original)
        features["rules"]["max_active_features"] = 2
        path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        weak_wip = self.run_cli("audit")
        self.assertNotEqual(weak_wip.returncode, 0)
        self.assertIn("exactly 1", weak_wip.stderr)

        features = json.loads(original)
        features["rules"]["passing_requires_receipt"] = False
        path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        weak_receipt = self.run_cli("audit")
        self.assertNotEqual(weak_receipt.returncode, 0)
        self.assertIn("must remain true", weak_receipt.stderr)

        path.write_text(original, encoding="utf-8")
        self.assertEqual(
            self.run_cli("state", "activate", "BOOT-001").returncode,
            0,
        )
        complete = self.run_cli("complete", "BOOT-001", "--risk", "local_code")
        self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)
        features = self.read_features()
        evidence = features["features"][0]["evidence"][-1]
        receipt_path = self.target / evidence["receipt"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt.pop("schema_version")
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        evidence["receipt_sha256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        invalid_schema = self.run_cli("audit")
        self.assertNotEqual(invalid_schema.returncode, 0)
        self.assertIn("schema_version 4", invalid_schema.stderr)

    def test_receipt_freshness_detects_config_verification_and_file_changes(self) -> None:
        self.assertEqual(
            self.run_cli("state", "activate", "BOOT-001").returncode,
            0,
        )
        complete = self.run_cli("complete", "BOOT-001", "--risk", "local_code")
        self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)

        config_path = self.target / "harness.config.json"
        original_config = config_path.read_text(encoding="utf-8")
        config = json.loads(original_config)
        config["runner"]["default_timeout_seconds"] = 301
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stale_config = self.run_cli("audit")
        self.assertNotEqual(stale_config.returncode, 0)
        self.assertIn("stale passing evidence", stale_config.stderr)
        config_path.write_text(original_config, encoding="utf-8")
        self.assertEqual(self.run_cli("audit").returncode, 0)

        architecture_path = self.target / "docs/ARCHITECTURE.md"
        original_architecture = architecture_path.read_text(encoding="utf-8")
        architecture_path.write_text(
            original_architecture + "\nChanged after completion.\n",
            encoding="utf-8",
        )
        stale_file = self.run_cli("audit")
        self.assertNotEqual(stale_file.returncode, 0)
        self.assertIn("tracked files changed", stale_file.stderr)
        architecture_path.write_text(original_architecture, encoding="utf-8")
        self.assertEqual(self.run_cli("audit").returncode, 0)

        feature_path = self.target / "feature_list.json"
        features = self.read_features()
        features["features"][0]["verification"][0][
            "description"
        ] = "Changed verification definition."
        feature_path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stale_verification = self.run_cli("audit")
        self.assertNotEqual(stale_verification.returncode, 0)
        self.assertIn("verification or risk definition changed", stale_verification.stderr)

        reopen = self.run_cli(
            "state",
            "reopen",
            "BOOT-001",
            "--reason",
            "Verification definition changed and requires new evidence.",
        )
        self.assertEqual(reopen.returncode, 0, reopen.stdout + reopen.stderr)
        self.assertEqual(self.feature("BOOT-001")["status"], "active")

    def test_receipt_freshness_ignores_unexecuted_config_changes(self) -> None:
        self.assertEqual(
            self.run_cli("state", "activate", "BOOT-001").returncode,
            0,
        )
        complete = self.run_cli("complete", "BOOT-001", "--risk", "local_code")
        self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)

        config_path = self.target / "harness.config.json"
        original_config = config_path.read_text(encoding="utf-8")
        config = json.loads(original_config)
        config["gates"]["V4"]["commands"][0]["why"] = (
            "An unexecuted V4 explanation changed after local-code completion."
        )
        config["risk_profiles"]["high_risk"]["description"] = (
            "An unrelated high-risk profile description changed."
        )
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        still_current = self.run_cli("audit")
        self.assertEqual(
            still_current.returncode,
            0,
            still_current.stdout + still_current.stderr,
        )
        evidence = self.feature("BOOT-001")["evidence"][-1]
        receipt = json.loads(
            (self.target / evidence["receipt"]).read_text(encoding="utf-8")
        )
        current_full_digest = hashlib.sha256(
            json.dumps(
                config,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        self.assertNotEqual(receipt["config_sha256"], current_full_digest)
        harness_module = self.load_harness_module("execution_config_digest")
        self.assertEqual(
            receipt["execution_config_sha256"],
            harness_module.execution_config_digest(
                config,
                "local_code",
                ["V0", "V1"],
                self.feature("BOOT-001"),
            ),
        )

        original = json.loads(original_config)
        config["gates"]["V1"]["commands"][0]["why"] = (
            "An executed V1 contract changed after completion."
        )
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stale = self.run_cli("audit")
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("executed configuration contract changed", stale.stderr)

        config["gates"]["V1"] = original["gates"]["V1"]
        config["risk_profiles"]["local_code"]["description"] = (
            "The selected local-code profile changed after completion."
        )
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stale_profile = self.run_cli("audit")
        self.assertNotEqual(stale_profile.returncode, 0)
        self.assertIn(
            "executed configuration contract changed",
            stale_profile.stderr,
        )

    def test_complete_selects_only_profile_and_bound_feature_gates(self) -> None:
        def scoped_command(command_id: str, sentinel_name: str) -> dict[str, object]:
            return {
                "id": command_id,
                "name": command_id,
                "argv": [
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; "
                        f"Path({sentinel_name!r}).write_text('ran\\n')"
                    ),
                ],
                "cwd": ".",
                "timeout_seconds": 10,
                "max_output_bytes": 4096,
                "execution_scope": "feature",
                "why": "Only the binding feature should execute this focused gate.",
                "fix": "Restore exact feature binding and scope selection.",
            }

        feature_a_file = self.target / "feature-a.txt"
        feature_b_file = self.target / "feature-b.txt"
        feature_a_file.write_text("a\n", encoding="utf-8")
        feature_b_file.write_text("b\n", encoding="utf-8")
        command_a = scoped_command("feature-a-gate", "feature-a.ran")
        command_b = scoped_command("feature-b-gate", "feature-b.ran")
        self.append_gate_command("V1", command_a)
        self.append_gate_command("V1", command_b)
        self.append_feature(
            "FEATURE-A",
            command_id="feature-a-gate",
            tracked_file="feature-a.txt",
        )
        self.append_feature(
            "FEATURE-B",
            command_id="feature-b-gate",
            tracked_file="feature-b.txt",
        )

        activated = self.run_cli("state", "activate", "FEATURE-A")
        self.assertEqual(activated.returncode, 0, activated.stdout + activated.stderr)
        completed = self.run_cli("complete", "FEATURE-A", "--risk", "local_code")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertTrue((self.target / "feature-a.ran").is_file())
        self.assertFalse((self.target / "feature-b.ran").exists())

        feature_a = self.feature("FEATURE-A")
        receipt = json.loads(
            (self.target / feature_a["evidence"][-1]["receipt"]).read_text(
                encoding="utf-8"
            )
        )
        executed_ids = [record["command_id"] for record in receipt["executed"]]
        self.assertIn("feature-a-gate", executed_ids)
        self.assertIn("fixture-v1", executed_ids)
        self.assertNotIn("feature-b-gate", executed_ids)
        self.assertNotIn("core-init-first", executed_ids)
        self.assertNotIn("core-init-repeat", executed_ids)
        self.assertNotIn("core-cold-start", executed_ids)

        harness = self.load_harness_module("gate_scope_selection")
        config_path = self.target / "harness.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        profile_ids = {
            command["id"]
            for _, command in harness.selected_gate_commands(
                config,
                ["V0", "V1"],
                purpose="profile",
            )
        }
        self.assertNotIn("feature-a-gate", profile_ids)
        self.assertNotIn("feature-b-gate", profile_ids)
        self.assertNotIn("core-init-first", profile_ids)
        self.assertIn("fixture-v1", profile_ids)
        (self.target / "feature-a.ran").unlink()
        verified = self.run_cli("verify", "--risk", "local_code")
        self.assertEqual(
            verified.returncode,
            0,
            verified.stdout + verified.stderr,
        )
        self.assertFalse((self.target / "feature-a.ran").exists())
        self.assertFalse((self.target / "feature-b.ran").exists())

        for command in config["gates"]["V1"]["commands"]:
            if command["id"] == "feature-b-gate":
                command["why"] = "Unrelated feature B changed."
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        unrelated = self.run_cli("audit")
        self.assertEqual(unrelated.returncode, 0, unrelated.stdout + unrelated.stderr)

        for command in config["gates"]["V1"]["commands"]:
            if command["id"] == "feature-a-gate":
                command["why"] = "Executed feature A changed."
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stale = self.run_cli("audit")
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("executed configuration contract changed", stale.stderr)

    def test_receipt_freshness_rejects_another_platform_runtime(self) -> None:
        self.assertEqual(
            self.run_cli("state", "activate", "BOOT-001").returncode,
            0,
        )
        complete = self.run_cli("complete", "BOOT-001", "--risk", "local_code")
        self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)

        features_path = self.target / "feature_list.json"
        features = self.read_features()
        evidence = features["features"][0]["evidence"][-1]
        receipt_path = self.target / evidence["receipt"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["runtime"]["platform"] = "win32" if sys.platform != "win32" else "linux"
        runtime_payload = {
            field: receipt["runtime"][field]
            for field in (
                "platform",
                "os_name",
                "python_implementation",
                "python_version",
            )
        }
        receipt["runtime"]["sha256"] = hashlib.sha256(
            json.dumps(
                runtime_payload,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        evidence["receipt_sha256"] = hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest()
        features_path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stale = self.run_cli("audit")
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("operating system or Python runtime changed", stale.stderr)

    def test_receipt_rejects_internally_inconsistent_argv_digest(self) -> None:
        self.assertEqual(
            self.run_cli("state", "activate", "BOOT-001").returncode,
            0,
        )
        complete = self.run_cli("complete", "BOOT-001", "--risk", "local_code")
        self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)

        features_path = self.target / "feature_list.json"
        features = self.read_features()
        evidence = features["features"][0]["evidence"][-1]
        receipt_path = self.target / evidence["receipt"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["executed"][0]["argv"].append("tampered")
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        evidence["receipt_sha256"] = hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest()
        features_path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        invalid = self.run_cli("audit")
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("argv digest does not match", invalid.stderr)

    def test_historical_schema_two_and_three_receipts_survive_reverification(
        self,
    ) -> None:
        self.assertEqual(
            self.run_cli("state", "activate", "BOOT-001").returncode,
            0,
        )
        complete = self.run_cli("complete", "BOOT-001", "--risk", "local_code")
        self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)

        features_path = self.target / "feature_list.json"
        features = self.read_features()
        evidence = features["features"][0]["evidence"][-1]
        receipt_path = self.target / evidence["receipt"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["schema_version"] = 2
        receipt.pop("runtime")
        receipt.pop("execution_config_sha256")
        built_in = next(
            record
            for record in receipt["executed"]
            if record["command_id"] == "harness-audit"
        )
        built_in["argv_sha256"] = hashlib.sha256(b"built-in:audit").hexdigest()
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        evidence["receipt_sha256"] = hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest()
        features_path.write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        stale = self.run_cli("audit")
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("historical receipt schema", stale.stderr)
        reopen = self.run_cli(
            "state",
            "reopen",
            "BOOT-001",
            "--reason",
            "Migrate historical schema-v2 evidence to schema v4.",
        )
        self.assertEqual(reopen.returncode, 0, reopen.stdout + reopen.stderr)
        recomplete = self.run_cli(
            "complete",
            "BOOT-001",
            "--risk",
            "local_code",
        )
        self.assertEqual(
            recomplete.returncode,
            0,
            recomplete.stdout + recomplete.stderr,
        )
        current_features = self.read_features()
        current = current_features["features"][0]
        second_evidence = current["evidence"][-1]
        second_receipt_path = self.target / second_evidence["receipt"]
        second_receipt = json.loads(
            second_receipt_path.read_text(encoding="utf-8")
        )
        second_receipt["schema_version"] = 3
        second_receipt.pop("execution_config_sha256")
        second_receipt_path.write_text(
            json.dumps(second_receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        second_evidence["receipt_sha256"] = hashlib.sha256(
            second_receipt_path.read_bytes()
        ).hexdigest()
        features_path.write_text(
            json.dumps(current_features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        stale_three = self.run_cli("audit")
        self.assertNotEqual(stale_three.returncode, 0)
        self.assertIn("historical receipt schema", stale_three.stderr)
        reopen_three = self.run_cli(
            "state",
            "reopen",
            "BOOT-001",
            "--reason",
            "Migrate historical schema-v3 evidence to schema v4.",
        )
        self.assertEqual(
            reopen_three.returncode,
            0,
            reopen_three.stdout + reopen_three.stderr,
        )
        recomplete_three = self.run_cli(
            "complete",
            "BOOT-001",
            "--risk",
            "local_code",
        )
        self.assertEqual(
            recomplete_three.returncode,
            0,
            recomplete_three.stdout + recomplete_three.stderr,
        )

        current = self.feature("BOOT-001")
        self.assertEqual(len(current["evidence"]), 3)
        receipt_schemas = [
            json.loads(
                (self.target / evidence["receipt"]).read_text(
                    encoding="utf-8"
                )
            )["schema_version"]
            for evidence in current["evidence"]
        ]
        self.assertEqual(receipt_schemas, [2, 3, 4])
        newest = json.loads(
            (self.target / current["evidence"][-1]["receipt"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(newest["schema_version"], 4)
        healthy = self.run_cli("audit")
        self.assertEqual(healthy.returncode, 0, healthy.stdout + healthy.stderr)

    def test_failing_required_gate_prevents_completion_with_actionable_error(self) -> None:
        self.assertEqual(
            self.run_cli("state", "activate", "BOOT-001").returncode,
            0,
        )
        self.replace_gate("V3", 7)
        failed = self.run_cli("complete", "BOOT-001", "--risk", "cross_component")
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("WHAT:", failed.stderr)
        self.assertIn("WHY:", failed.stderr)
        self.assertIn("FIX:", failed.stderr)
        feature = self.feature("BOOT-001")
        self.assertEqual(feature["status"], "active")
        self.assertEqual(feature["evidence"], [])
        evidence_dir = self.target / ".harness/evidence"
        self.assertFalse(evidence_dir.exists())

    def test_missing_executable_is_actionable_without_traceback(self) -> None:
        self.set_gate_commands(
            "V2",
            [
                {
                    "id": "missing-executable",
                    "name": "missing executable",
                    "argv": ["/definitely/missing/harness-command"],
                    "cwd": ".",
                    "timeout_seconds": 5,
                    "why": "The configured executable must exist.",
                    "fix": "Install it or correct the configured argv.",
                }
            ],
        )
        result = self.run_cli("verify", "--risk", "runtime_change")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("WHAT:", result.stderr)
        self.assertIn("FIX:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_runner_timeout_terminates_the_gate(self) -> None:
        self.set_gate_commands(
            "V2",
            [
                {
                    "id": "timeout-gate",
                    "name": "timeout gate",
                    "argv": [
                        sys.executable,
                        "-c",
                        "import time; time.sleep(5)",
                    ],
                    "cwd": ".",
                    "timeout_seconds": 0.1,
                    "why": "A bounded command must finish within its timeout.",
                    "fix": "Fix the hang or choose an evidence-based larger timeout.",
                }
            ],
        )
        started = time.monotonic()
        result = self.run_cli("verify", "--risk", "runtime_change")
        duration = time.monotonic() - started
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("timed out", result.stderr)
        self.assertLess(duration, 3)
        self.assertNotIn("Traceback", result.stderr)

    def test_runner_timeout_terminates_child_process_group(self) -> None:
        sentinel = self.base / "orphan-child-ran"
        child = (
            "import time; from pathlib import Path; "
            f"time.sleep(0.8); Path({str(sentinel)!r}).write_text('orphan')"
        )
        parent = (
            "import subprocess,sys,time; "
            f"subprocess.Popen([sys.executable, '-c', {child!r}]); "
            "time.sleep(5)"
        )
        self.set_gate_commands(
            "V2",
            [
                {
                    "id": "child-timeout-gate",
                    "name": "child timeout gate",
                    "argv": [sys.executable, "-c", parent],
                    "cwd": ".",
                    "timeout_seconds": 0.1,
                    "why": "Timed-out descendants must not survive the gate.",
                    "fix": "Repair the hang before increasing the evidence-based timeout.",
                }
            ],
        )
        result = self.run_cli("verify", "--risk", "runtime_change")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("timed out", result.stderr)
        time.sleep(1)
        self.assertFalse(sentinel.exists())

    def test_runner_cleans_a_parent_that_leaves_a_pipe_holding_child(self) -> None:
        sentinel = self.base / "orphan-after-parent-exit"
        child = (
            "import time; from pathlib import Path; "
            f"time.sleep(1.5); Path({str(sentinel)!r}).write_text('orphan')"
        )
        parent = (
            "import subprocess,sys; "
            f"subprocess.Popen([sys.executable, '-c', {child!r}])"
        )
        self.set_gate_commands(
            "V2",
            [
                {
                    "id": "exited-parent-gate",
                    "name": "exited parent gate",
                    "argv": [sys.executable, "-c", parent],
                    "cwd": ".",
                    "timeout_seconds": 5,
                    "why": "A successful parent must not abandon inherited descendants.",
                    "fix": "Wait for or explicitly shut down every child process.",
                }
            ],
        )
        result = self.run_cli("verify", "--risk", "runtime_change")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        time.sleep(0.8)
        self.assertFalse(sentinel.exists())

    def test_runner_rejects_cwd_outside_the_project(self) -> None:
        self.set_gate_commands(
            "V2",
            [
                {
                    "id": "escaping-cwd",
                    "name": "escaping cwd",
                    "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                    "cwd": "../outside",
                    "timeout_seconds": 5,
                    "why": "A gate must remain inside the repository.",
                    "fix": "Use a project-relative directory.",
                }
            ],
        )
        result = self.run_cli("audit")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("escapes the root", result.stderr)

    def test_runner_bounds_and_redacts_failure_output(self) -> None:
        secret = "fixture-super-secret-value"
        self.set_gate_commands(
            "V2",
            [
                {
                    "id": "bounded-output",
                    "name": "bounded output",
                    "argv": [
                        sys.executable,
                        "-c",
                        (
                            "import os,sys; "
                            "sys.stderr.write(os.environ['HARNESS_TEST_TOKEN'] * 500); "
                            "raise SystemExit(7)"
                        ),
                    ],
                    "cwd": ".",
                    "timeout_seconds": 5,
                    "max_output_bytes": 1024,
                    "why": "Failure output must remain bounded and redact inherited secrets.",
                    "fix": "Inspect the bounded diagnostic without exposing credentials.",
                }
            ],
        )
        environment = os.environ.copy()
        environment["HARNESS_TEST_TOKEN"] = secret
        result = self.run_cli(
            "verify",
            "--risk",
            "runtime_change",
            env=environment,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("truncated", result.stderr)
        self.assertIn("[REDACTED]", result.stderr)
        self.assertNotIn(secret, result.stderr)

    def test_runner_preflights_aggregate_budgets_and_combined_output(self) -> None:
        harness = self.load_harness_module("aggregate_runner_budgets")
        self.assertEqual(harness.DEFAULT_MAX_GATE_COMMANDS_PER_RUN, 32)
        self.assertEqual(harness.DEFAULT_MAX_GATE_TIMEOUT_SECONDS_PER_RUN, 1800)
        self.assertEqual(harness.DEFAULT_MAX_COMBINED_OUTPUT_BYTES, 128 * 1024)
        config_path = self.target / "harness.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))

        profileless = json.loads(json.dumps(config))
        profileless["gates"]["V1"]["commands"] = [
            command
            for command in profileless["gates"]["V1"]["commands"]
            if command.get("execution_scope", "profile") == "feature"
        ]
        with mock.patch.object(harness.subprocess, "Popen") as popen:
            with self.assertRaises(harness.HarnessFailure) as empty_profile:
                harness.run_gates(
                    profileless,
                    {},
                    "local_code",
                    purpose="profile",
                    repository_already_audited=True,
                )
        self.assertIn("no profile-scope commands", str(empty_profile.exception))
        popen.assert_not_called()

        extra_profile = gate_command("V1")
        extra_profile["id"] = "fixture-v1-extra"
        config["gates"]["V1"]["commands"].append(extra_profile)

        config["runner"]["max_gate_commands_per_run"] = 1
        with mock.patch.object(harness.subprocess, "Popen") as popen:
            with self.assertRaises(harness.HarnessFailure) as command_error:
                harness.run_gates(
                    config,
                    {},
                    "local_code",
                    purpose="profile",
                    repository_already_audited=True,
                )
        self.assertIn("external commands", str(command_error.exception))
        popen.assert_not_called()

        config["runner"]["max_gate_commands_per_run"] = 32
        config["runner"]["max_gate_timeout_seconds_per_run"] = 1
        with mock.patch.object(harness.subprocess, "Popen") as popen:
            with self.assertRaises(harness.HarnessFailure) as timeout_error:
                harness.run_gates(
                    config,
                    {},
                    "local_code",
                    purpose="profile",
                    repository_already_audited=True,
                )
        self.assertIn("timeouts total", str(timeout_error.exception))
        popen.assert_not_called()

        config["runner"]["max_gate_timeout_seconds_per_run"] = 900
        config["runner"]["max_combined_output_bytes"] = 2048
        noisy_failure = {
            "id": "combined-output",
            "name": "combined output",
            "argv": [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "sys.stdout.write('A' * 10000); "
                    "sys.stderr.write('B' * 10000); "
                    "raise SystemExit(7)"
                ),
            ],
            "cwd": ".",
            "timeout_seconds": 5,
            "max_output_bytes": 10 * 1024 * 1024,
            "why": "Both retained streams must share one finite output budget.",
            "fix": "Inspect the bounded tails instead of returning the full log.",
        }
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(harness.HarnessFailure) as output_error:
                harness.execute_gate_command(config, "V2", noisy_failure)
        rendered = str(output_error.exception)
        self.assertIn("STDOUT (bounded tail)", rendered)
        self.assertIn("STDERR (bounded tail)", rendered)
        self.assertGreaterEqual(rendered.count("truncated"), 2)
        self.assertLess(len(rendered.encode("utf-8")), 6 * 1024)

        finite_output = dict(noisy_failure)
        finite_output["id"] = "finite-combined-output"
        finite_output["argv"] = [
            sys.executable,
            "-c",
            (
                "import sys; "
                "sys.stdout.write('A' * 100000); "
                "sys.stderr.write('B' * 100000)"
            ),
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            finite_record = harness.execute_gate_command(config, "V2", finite_output)
        self.assertEqual(finite_record["exit_code"], 0)
        self.assertTrue(finite_record["output_truncated"])
        self.assertFalse(finite_record["timed_out"])

        compatible = json.loads(config_path.read_text(encoding="utf-8"))
        for field in (
            "max_gate_commands_per_run",
            "max_gate_timeout_seconds_per_run",
            "max_combined_output_bytes",
        ):
            compatible["runner"].pop(field, None)
        config_path.write_text(
            json.dumps(compatible, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        legacy_shape = self.run_cli("audit")
        self.assertEqual(
            legacy_shape.returncode,
            0,
            legacy_shape.stdout + legacy_shape.stderr,
        )

        overconfigured = json.loads(config_path.read_text(encoding="utf-8"))
        overconfigured["gates"]["V4"]["commands"] = [
            gate_command("V4")
            for _ in range(harness.MAX_GATE_COMMANDS_PER_LEVEL + 1)
        ]
        config_path.write_text(
            json.dumps(overconfigured, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        too_many_declared = self.run_cli("audit")
        self.assertNotEqual(too_many_declared.returncode, 0)
        self.assertIn("commands has 257 entries", too_many_declared.stderr)

        overconfigured = json.loads(config_path.read_text(encoding="utf-8"))
        overconfigured["gates"]["V4"]["commands"] = [gate_command("V4")]
        overconfigured["gates"]["V4"]["commands"][0]["argv"] = [
            "x"
        ] * (harness.MAX_ARGV_ITEMS + 1)
        config_path.write_text(
            json.dumps(overconfigured, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        oversized_argv = self.run_cli("audit")
        self.assertNotEqual(oversized_argv.returncode, 0)
        self.assertIn("argv has 65 items", oversized_argv.stderr)

        bounded_start = json.loads(
            (self.target / "harness.config.json").read_text(encoding="utf-8")
        )
        bounded_start["gates"]["V4"]["commands"] = [gate_command("V4")]
        bounded_start["commands"]["start"]["argv"] = [
            sys.executable,
            "x" * 20000,
        ]
        config_path.write_text(
            json.dumps(bounded_start, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        oversized_cold_start = self.run_cli("cold-start", "--json")
        self.assertNotEqual(oversized_cold_start.returncode, 0)
        self.assertIn("cold-start output", oversized_cold_start.stderr)

        nan_config = json.loads(json.dumps(config))
        nan_config["runner"]["default_timeout_seconds"] = float("nan")
        config_path.write_text(
            json.dumps(nan_config, ensure_ascii=False, indent=2, allow_nan=True) + "\n",
            encoding="utf-8",
        )
        nonfinite = self.run_cli("audit")
        self.assertNotEqual(nonfinite.returncode, 0)
        self.assertIn("non-finite JSON number", nonfinite.stderr)

    def test_execution_contract_digest_and_git_queries_are_bounded(self) -> None:
        harness = self.load_harness_module("execution_contract_budget")
        config = json.loads(
            (self.target / "harness.config.json").read_text(encoding="utf-8")
        )
        feature = self.feature("BOOT-001")
        explicit_defaults = json.loads(json.dumps(config))
        explicit_defaults["runner"].update(
            {
                "max_gate_commands_per_run": harness.DEFAULT_MAX_GATE_COMMANDS_PER_RUN,
                "max_gate_timeout_seconds_per_run": (
                    harness.DEFAULT_MAX_GATE_TIMEOUT_SECONDS_PER_RUN
                ),
                "max_combined_output_bytes": harness.DEFAULT_MAX_COMBINED_OUTPUT_BYTES,
            }
        )
        explicit_digest = harness.execution_config_digest(
            explicit_defaults,
            "local_code",
            ["V0", "V1"],
            feature,
        )
        omitted_defaults = json.loads(json.dumps(explicit_defaults))
        for field in (
            "max_gate_commands_per_run",
            "max_gate_timeout_seconds_per_run",
            "max_combined_output_bytes",
        ):
            omitted_defaults["runner"].pop(field)
        self.assertEqual(
            explicit_digest,
            harness.execution_config_digest(
                omitted_defaults,
                "local_code",
                ["V0", "V1"],
                feature,
            ),
        )
        self.assertEqual(harness.EXECUTION_CONTRACT_VERSION, 2)

        revision_cache = harness.GitRevisionCache()
        with mock.patch.object(harness, "current_revision", return_value="head"):
            with mock.patch.object(
                harness,
                "revision_is_current_or_ancestor",
                return_value=True,
            ) as ancestry:
                for index in range(33):
                    self.assertTrue(
                        revision_cache.is_current_or_ancestor(f"revision-{index}")
                    )
        self.assertEqual(ancestry.call_count, 33)
        expired_cache = harness.GitRevisionCache()
        expired_cache.deadline = time.monotonic() - 1
        with self.assertRaises(harness.HarnessFailure) as git_budget:
            expired_cache.is_current_or_ancestor("revision")
        self.assertIn("wall-clock budget", str(git_budget.exception))

        self.assertEqual(
            self.run_cli("state", "activate", "BOOT-001").returncode,
            0,
        )
        completed = self.run_cli("complete", "BOOT-001", "--risk", "local_code")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        features = self.read_features()
        boot = next(item for item in features["features"] if item["id"] == "BOOT-001")
        evidence = boot["evidence"][-1]
        receipt_path = self.target / evidence["receipt"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        with mock.patch.object(harness, "EXECUTION_CONTRACT_VERSION", 1):
            receipt["execution_config_sha256"] = harness.execution_config_digest(
                config,
                "local_code",
                ["V0", "V1"],
                boot,
            )
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        evidence["receipt_sha256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        (self.target / "feature_list.json").write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stale_contract = self.run_cli("audit")
        self.assertNotEqual(stale_contract.returncode, 0)
        self.assertIn("executed configuration contract changed", stale_contract.stderr)

    @unittest.skipUnless(shutil.which("git"), "Git is not installed")
    def test_receipt_revision_must_be_current_or_an_ancestor(self) -> None:
        def git(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", *args],
                cwd=self.target,
                text=True,
                input=input_text,
                capture_output=True,
                check=False,
            )

        self.assertEqual(git("init").returncode, 0)
        self.assertEqual(git("config", "user.name", "Harness Fixture").returncode, 0)
        self.assertEqual(
            git("config", "user.email", "harness-fixture@example.invalid").returncode,
            0,
        )
        self.assertEqual(git("add", "-A").returncode, 0)
        self.assertEqual(git("commit", "-m", "fixture baseline").returncode, 0)
        self.assertEqual(
            self.run_cli("state", "activate", "BOOT-001").returncode,
            0,
        )
        self.assertEqual(git("add", "-A").returncode, 0)
        self.assertEqual(git("commit", "-m", "activate feature").returncode, 0)
        complete = self.run_cli("complete", "BOOT-001", "--risk", "local_code")
        self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)
        self.assertEqual(git("add", "-A").returncode, 0)
        self.assertEqual(git("commit", "-m", "record completion").returncode, 0)
        healthy = self.run_cli("audit")
        self.assertEqual(healthy.returncode, 0, healthy.stdout + healthy.stderr)

        tree = git("rev-parse", "HEAD^{tree}").stdout.strip()
        unrelated = git("commit-tree", tree, input_text="unrelated root\n")
        self.assertEqual(unrelated.returncode, 0, unrelated.stdout + unrelated.stderr)
        branch = git("symbolic-ref", "HEAD").stdout.strip()
        moved = git("update-ref", branch, unrelated.stdout.strip())
        self.assertEqual(moved.returncode, 0, moved.stdout + moved.stderr)
        stale = self.run_cli("audit")
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("not current or an ancestor", stale.stderr)

    def test_clean_state_and_high_risk_gate(self) -> None:
        self.assertEqual(
            self.run_cli("state", "activate", "BOOT-001").returncode,
            0,
        )
        leftover = self.target / "leftover.tmp"
        leftover.write_text("temporary\n", encoding="utf-8")
        dirty = self.run_cli("complete", "BOOT-001", "--risk", "local_code")
        self.assertNotEqual(dirty.returncode, 0)
        self.assertIn("clean-state", dirty.stderr)
        self.assertEqual(self.feature("BOOT-001")["status"], "active")

        leftover.unlink()
        excluded_leftover = self.target / "node_modules" / "dependency.tmp"
        excluded_leftover.parent.mkdir()
        excluded_leftover.write_text("dependency cache\n", encoding="utf-8")
        complete = self.run_cli("complete", "BOOT-001", "--risk", "high_risk")
        self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)
        receipt_path = self.target / self.feature("BOOT-001")["evidence"][0]["receipt"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["required_levels"], ["V0", "V1", "V2", "V3", "V4"])
        self.assertEqual(receipt["skipped_levels"], [])
        gate_log = (self.target / ".harness/gates.log").read_text(encoding="utf-8")
        self.assertIn("V4\n", gate_log)

        harness = self.load_harness_module("clean_scan_budget")
        config = json.loads(
            (self.target / "harness.config.json").read_text(encoding="utf-8")
        )
        features = self.read_features()
        synthetic_entries = [
            (self.target / name, True) for name in ("a", "b", "c")
        ]
        with mock.patch.object(harness, "MAX_CLEAN_STATE_SCAN_ENTRIES", 2):
            with mock.patch.object(
                harness,
                "iter_clean_state_entries",
                return_value=synthetic_entries,
            ):
                with self.assertRaises(harness.HarnessFailure) as scan_budget:
                    harness.validate_clean_state(config, features)
        self.assertIn("clean-state scan exceeded", str(scan_budget.exception))

        with mock.patch.object(
            harness.os,
            "scandir",
            side_effect=PermissionError("denied"),
        ):
            with self.assertRaises(harness.HarnessFailure) as unreadable:
                harness.validate_clean_state(config, features)
        self.assertIn("silently skipped subtrees", str(unreadable.exception))

        long_offenders = [
            (self.target / (("x" * 100) + f"-{index}.tmp"), True)
            for index in range(100)
        ]
        with mock.patch.object(harness, "MAX_CLEAN_STATE_REPORTED_BYTES", 256):
            with mock.patch.object(
                harness,
                "iter_clean_state_entries",
                return_value=long_offenders,
            ):
                with self.assertRaises(harness.HarnessFailure) as bounded_offenders:
                    harness.validate_clean_state(config, features)
        rendered_offenders = str(bounded_offenders.exception)
        self.assertIn("more omitted", rendered_offenders)
        self.assertLess(len(rendered_offenders.encode("utf-8")), 1024)

    def test_completion_cannot_downgrade_declared_risk(self) -> None:
        features = self.read_features()
        features["features"][0]["risk_profile"] = "runtime_change"
        (self.target / "feature_list.json").write_text(
            json.dumps(features, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(
            self.run_cli("state", "activate", "BOOT-001").returncode,
            0,
        )
        result = self.run_cli("complete", "BOOT-001", "--risk", "local_code")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("weaker", result.stderr)
        self.assertEqual(self.feature("BOOT-001")["status"], "active")

    def test_config_rejects_placeholders_and_disabled_profiles(self) -> None:
        path = self.target / "harness.config.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config["project"]["summary"] = "REPLACE_ME"
        path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        placeholder = self.run_cli("audit")
        self.assertNotEqual(placeholder.returncode, 0)
        self.assertIn("placeholder", placeholder.stderr)

        config["project"]["summary"] = "Configured fixture."
        config["risk_profiles"]["cross_component"]["enabled"] = False
        path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        disabled = self.run_cli("verify", "--risk", "cross_component")
        self.assertNotEqual(disabled.returncode, 0)
        self.assertIn("disabled", disabled.stderr)

    def test_current_python_token_is_portable_and_position_bound(self) -> None:
        harness_module = self.load_harness_module("python_token")
        self.assertEqual(
            harness_module.expand_argv(
                ["{python}", "scripts/harness.py", "cold-start", "--json"]
            ),
            [sys.executable, "scripts/harness.py", "cold-start", "--json"],
        )
        self.assertEqual(
            harness_module.expand_argv(["node", "--version"]),
            ["node", "--version"],
        )
        with self.assertRaises(harness_module.HarnessFailure):
            harness_module.expand_argv(["echo", "{python}"])

        path = self.target / "harness.config.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config["gates"]["V2"]["commands"][0]["argv"] = [
            sys.executable,
            "{python}",
        ]
        path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        invalid = self.run_cli("audit")
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("only as argv[0]", invalid.stderr)

    def test_platform_process_options_and_windows_quoting(self) -> None:
        harness_module = self.load_harness_module("process_options")
        self.assertEqual(
            harness_module.process_creation_options(platform_name="posix"),
            {"start_new_session": True},
        )
        self.assertEqual(
            harness_module.process_creation_options(platform_name="nt"),
            {
                "creationflags": getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
                )
            },
        )
        self.assertEqual(
            harness_module.process_creation_options(platform_name="other"),
            {},
        )
        rendered = harness_module.command_label(
            [r"C:\Program Files\Python\python.exe", "argument with spaces"],
            platform_name="nt",
        )
        self.assertIn('"C:\\Program Files\\Python\\python.exe"', rendered)
        self.assertIn('"argument with spaces"', rendered)

    def test_windows_timeout_uses_tree_kill_then_direct_fallback(self) -> None:
        harness_module = self.load_harness_module("windows_termination")

        class FakeProcess:
            def __init__(self) -> None:
                self.pid = 4242
                self.returncode: int | None = None
                self.events: list[object] = []

            def poll(self) -> int | None:
                return self.returncode

            def send_signal(self, value: int) -> None:
                self.events.append(("signal", value))

            def wait(self, timeout: float) -> int:
                self.events.append(("wait", timeout))
                if self.returncode is None:
                    raise subprocess.TimeoutExpired("fake-process", timeout)
                return self.returncode

            def kill(self) -> None:
                self.events.append(("kill",))
                self.returncode = -9

        process = FakeProcess()
        taskkill_calls: list[list[str]] = []

        def failed_taskkill(argv: list[str], **_: object) -> SimpleNamespace:
            taskkill_calls.append(argv)
            return SimpleNamespace(returncode=1)

        def fake_signal_sender(pid: int, value: int) -> None:
            self.assertEqual(pid, process.pid)
            process.events.append(("signal", value))

        harness_module.terminate_process_tree(
            process,
            platform_name="nt",
            taskkill_runner=failed_taskkill,
            signal_sender=fake_signal_sender,
        )
        self.assertTrue(taskkill_calls)
        taskkill_argv = taskkill_calls[0]
        self.assertTrue(ntpath.isabs(taskkill_argv[0]))
        self.assertTrue(
            taskkill_argv[0].lower().endswith(
                ntpath.join("system32", "taskkill.exe")
            )
        )
        self.assertEqual(taskkill_argv[1:], ["/PID", "4242", "/T", "/F"])
        signal_index = next(
            index
            for index, event in enumerate(process.events)
            if event[0] == "signal"
        )
        kill_index = process.events.index(("kill",))
        self.assertLess(signal_index, kill_index)

    @unittest.skipUnless(
        os.name == "posix" and shutil.which("sh"),
        "generic POSIX fixture requires a POSIX sh",
    )
    def test_generic_posix_stack_fixture_completes_from_nested_cwd(self) -> None:
        tools = self.target / "tools"
        tools.mkdir()
        script = tools / "verify.sh"
        script.write_text(
            "#!/bin/sh\nset -eu\nprintf 'generic-ready\\n' > generic.ok\n",
            encoding="utf-8",
        )
        script.chmod(0o755)
        self.append_gate_command(
            "V1",
            {
                "id": "generic-stack",
                "name": "generic POSIX stack",
                "argv": ["sh", "verify.sh"],
                "cwd": "tools",
                "timeout_seconds": 10,
                "why": "The generic POSIX project path must execute.",
                "fix": "Repair tools/verify.sh and retry.",
            },
        )
        self.append_feature(
            "STACK-GENERIC",
            command_id="generic-stack",
            tracked_file="tools/verify.sh",
        )
        self.assertEqual(
            self.run_cli("state", "activate", "STACK-GENERIC").returncode,
            0,
        )
        result = self.run_cli(
            "complete",
            "STACK-GENERIC",
            "--risk",
            "local_code",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((tools / "generic.ok").read_text(), "generic-ready\n")

    def test_python_stack_fixture_completes(self) -> None:
        test_file = self.target / "python_stack_test.py"
        test_file.write_text(
            (
                "import unittest\n\n"
                "class ExampleTest(unittest.TestCase):\n"
                "    def test_stack(self):\n"
                "        self.assertEqual(2 + 2, 4)\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
            encoding="utf-8",
        )
        self.append_gate_command(
            "V1",
            {
                "id": "python-stack",
                "name": "Python unittest stack",
                "argv": [
                    sys.executable,
                    "-m",
                    "unittest",
                    "python_stack_test.py",
                ],
                "cwd": ".",
                "timeout_seconds": 30,
                "why": "A standard-library Python project must verify through Core.",
                "fix": "Repair the Python fixture and retry.",
            },
        )
        self.append_feature(
            "STACK-PYTHON",
            command_id="python-stack",
            tracked_file="python_stack_test.py",
        )
        self.assertEqual(
            self.run_cli("state", "activate", "STACK-PYTHON").returncode,
            0,
        )
        result = self.run_cli(
            "complete",
            "STACK-PYTHON",
            "--risk",
            "local_code",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_node_stack_fixture_completes(self) -> None:
        test_file = self.target / "node-stack.test.js"
        test_file.write_text(
            (
                "const test = require('node:test');\n"
                "const assert = require('node:assert/strict');\n"
                "test('stack', () => assert.equal(2 + 2, 4));\n"
            ),
            encoding="utf-8",
        )
        self.append_gate_command(
            "V1",
            {
                "id": "node-stack",
                "name": "Node test stack",
                "argv": ["node", "--test", "node-stack.test.js"],
                "cwd": ".",
                "timeout_seconds": 30,
                "why": "A dependency-free Node project must verify through Core.",
                "fix": "Repair the Node fixture and retry.",
            },
        )
        self.append_feature(
            "STACK-NODE",
            command_id="node-stack",
            tracked_file="node-stack.test.js",
        )
        self.assertEqual(
            self.run_cli("state", "activate", "STACK-NODE").returncode,
            0,
        )
        result = self.run_cli(
            "complete",
            "STACK-NODE",
            "--risk",
            "local_code",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_state_drift_is_detected_and_repairable(self) -> None:
        path = self.target / "docs/STATE.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace("- Next feature: BOOT-001", "- Next feature: BOOT-999"),
            encoding="utf-8",
        )
        audit = self.run_cli("audit")
        self.assertNotEqual(audit.returncode, 0)
        self.assertIn("disagrees", audit.stderr)

        sync = self.run_cli("state", "sync")
        self.assertEqual(sync.returncode, 0, sync.stdout + sync.stderr)
        healthy = self.run_cli("audit")
        self.assertEqual(healthy.returncode, 0, healthy.stdout + healthy.stderr)
        self.assertIn("- Next feature: BOOT-001", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
