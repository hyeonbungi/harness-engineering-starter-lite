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
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "scripts/install_core.py"


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

        patch_installer = self.make_release(
            "0.2.1",
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
        self.assertEqual((target / "VERSION").read_text().strip(), "0.2.1")
        self.assertIn(
            "Fixture release 0.2.1 change.",
            (target / "NOTICE").read_text(encoding="utf-8"),
        )
        upgraded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(upgraded_manifest["version"], "0.2.1")

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

        manifest["version"] = "0.0.9"
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
        (incoming / "VERSION").write_text("0.2.1\n", encoding="utf-8")
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
        (incoming / "VERSION").write_text("0.2.1\n", encoding="utf-8")
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
        self.assertIn("[switch]$setup", core_text)
        self.assertIn('"--setup"', core_text)
        self.assertIn("scripts\\harness.py", core_text)

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
        self.assertEqual(len(receipt["tracked_files"]), 16)
        self.assertEqual(len(receipt["tracked_files_sha256"]), 64)
        self.assertEqual(receipt["schema_version"], 3)
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
        self.assertIn("schema_version 3", invalid_schema.stderr)

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

    def test_historical_schema_two_receipt_can_be_preserved_after_reverification(
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
            "Migrate historical evidence to schema v3.",
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
        current = self.feature("BOOT-001")
        self.assertEqual(len(current["evidence"]), 2)
        newest = json.loads(
            (self.target / current["evidence"][-1]["receipt"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(newest["schema_version"], 3)
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
        complete = self.run_cli("complete", "BOOT-001", "--risk", "high_risk")
        self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)
        receipt_path = self.target / self.feature("BOOT-001")["evidence"][0]["receipt"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["required_levels"], ["V0", "V1", "V2", "V3", "V4"])
        self.assertEqual(receipt["skipped_levels"], [])
        gate_log = (self.target / ".harness/gates.log").read_text(encoding="utf-8")
        self.assertIn("V4\n", gate_log)

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

        harness_module.terminate_process_tree(
            process,
            platform_name="nt",
            taskkill_runner=failed_taskkill,
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
