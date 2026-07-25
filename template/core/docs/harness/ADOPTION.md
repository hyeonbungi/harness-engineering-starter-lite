# Core Profile Adoption

The Core version recorded in `VERSION` supports either a POSIX shell or native
Windows PowerShell 5.1+, plus Python 3.10 or newer. Run lifecycle commands from
a checkout of Harness Engineering Starter Lite; the target can be an empty
directory or a path that does not exist yet.

## 1. Install

```bash
python3 scripts/install_core.py /absolute/path/to/project --dry-run
python3 scripts/install_core.py /absolute/path/to/project
```

On Windows, use an installed 3.10+ interpreter, for example:

```powershell
py -3 scripts/install_core.py C:\absolute\path\to\project --dry-run
py -3 scripts/install_core.py C:\absolute\path\to\project
```

The installer refuses existing managed paths, every existing symbolic-link or
Windows junction/reparse-point segment in the target and managed paths,
case-aliased paths, reserved device names, alternate-data-stream separators, and
trailing dot/space segments on Windows, and paths that resolve outside the target
root. Use a canonical target path. A successful install writes
`.harness/install-manifest.json` with the Core version and managed-file digests.
Keep this manifest; upgrade and removal use it as their ownership boundary.

Claude Code loads the shared agent contract through the first non-empty line of
`CLAUDE.md`: `@AGENTS.md`. Keep shared rules in `AGENTS.md`; add Claude-only
notes below the import only when a concrete project need appears. `audit`
rejects a missing or replaced import.

Rejecting every reparse point is deliberately conservative. A project under a
provider-managed mount may need a canonical local NTFS path or a reviewed manual
install. UNC and network-filesystem atomicity are outside the automatic lifecycle
guarantee.

## 2. Configure

1. Replace every `REPLACE_ME` and `YYYY-MM-DD`.
2. Set `configured` to `true` in `harness.config.json`.
3. Define setup and start commands as argument arrays, or document why they are
   unavailable.
4. Give every gate command a stable, unique `id`; never use the reserved
   `harness-audit` ID.
5. Set a project-relative `cwd`, a positive `timeout_seconds`, and, when the
   default is unsuitable, `max_output_bytes`.
6. Enable only risk profiles whose contiguous V0..Vn levels are configured.
7. Describe actual boundaries in `docs/ARCHITECTURE.md` and current facts in
   `docs/STATE.md`.

Commands inherit the caller's environment. Do not store tokens, passwords, or
private values in configuration or command arguments. The runner bounds retained
stdout/stderr and masks common credential forms, but redaction is defense in
depth rather than permission to print secrets.

Use the reserved `{python}` token only as `argv[0]` when a gate should run with
the same interpreter as the harness:

```json
{"argv": ["{python}", "-m", "unittest", "tests/test_contract.py"]}
```

The token remains stable in configuration and expands to `sys.executable` only
at execution. Never place it in later arguments. Project `.cmd` or `.bat` files
may be interpreted by Windows itself; prefer a native executable or Python/Node
entrypoint, and make any intentional `cmd.exe` boundary explicit in the argv.

Each feature must declare its own executable checks and exact evidence inputs:

```json
{
  "risk_profile": "local_code",
  "verification": [
    {
      "id": "FEATURE-001-V1",
      "description": "Run the focused contract test.",
      "bindings": [{"level": "V1", "command_id": "focused-contract"}]
    }
  ],
  "tracked_files": ["src/contract.py", "tests/test_contract.py"]
}
```

Every binding must exist inside the feature's risk profile. Mutable
`feature_list.json`, `docs/STATE.md`, evidence paths, missing files, and
symbolic-link or Windows junction/reparse-point paths cannot be tracked.

Keep the `harness:state` marker block in `docs/STATE.md` intact. State commands
update only that bounded block from `feature_list.json`.

## 3. Validate

```bash
./init.sh --setup
./init.sh
./init.sh
python3 scripts/harness.py cold-start --json
```

Native Windows PowerShell uses:

```powershell
.\init.ps1 -Setup
.\init.ps1
.\init.ps1
py -3 scripts/harness.py cold-start --json
```

The standard path must be safe to repeat. BOOT-001 already binds the Core audit,
two initialization runs, and the five cold-start answers to executable V0/V1
commands.

`init.ps1` checks the active virtual environment, `py -3`, `python`, and
`python3`, selects Python 3.10+, preserves the child exit code, and temporarily
disables Python Manager automatic installation while probing. It does not change
PowerShell execution policy. If organization policy blocks local scripts, keep
that policy and run the equivalent approved interpreter command directly, such
as `py -3 scripts/harness.py init --setup`; do not silently weaken machine or
user policy.

## 4. Work with State and Evidence

```bash
python3 scripts/harness.py state activate BOOT-001
python3 scripts/harness.py state block BOOT-001 --reason "Documented blocker and recovery condition"
python3 scripts/harness.py state reopen BOOT-001 --reason "Blocker or evidence issue resolved"
python3 scripts/harness.py complete BOOT-001 --risk local_code
```

On Windows, replace `python3` with the same approved Python 3.10+ command chosen
for adoption, such as `py -3`.

`complete` is the only supported path to `passing`. It executes every level
required by the selected risk profile, proves that all feature bindings ran,
checks clean state, and writes a schema-v3 receipt under `.harness/evidence/`.

Strict audit compares the latest receipt with the current:

- receipt file digest and complete schema-v3 execution structure;
- complete `harness.config.json` digest;
- feature risk, verification, and tracked-path definition digest;
- digest of every exact tracked file;
- Git revision, when both receipt and current project are versioned.
- OS/platform and Python implementation/major.minor runtime identity.

When Git is unavailable, exact tracked-file digests remain authoritative. A
stale receipt blocks strict audit. Use `state reopen` with a reason and complete
again; recovery validates old receipt structure without pretending it is fresh.
Older receipts remain history and are not treated as current proof.
Historical schema-v2 receipts may remain after a `0.2.x` re-verification, but
they cannot be the newest proof because they do not bind OS/Python runtime
identity.

If the managed STATE block is damaged, repair it with:

```bash
python3 scripts/harness.py state sync
```

`sync` repairs presentation only and deliberately does not renew evidence.

## 5. Upgrade

Always inspect a dry run first:

```bash
python3 scripts/install_core.py /absolute/path/to/project --upgrade --dry-run
python3 scripts/install_core.py /absolute/path/to/project --upgrade
```

Upgrade compares the manifest baseline, current project file, and incoming Core
file. It replaces only unchanged managed files, preserves local-only changes,
and refuses files changed on both sides. Successful changes create a recoverable
backup under `.harness/backups/` before updating the manifest.

The installer refuses downgrades and major-version changes. Before `1.0.0`, it
also refuses automatic minor-version changes because they may alter the
lifecycle contract; use a separately reviewed manual adoption path. Compatible
patch upgrades are automatic.

For a refused conflict, merge the current project file with the incoming file
under this starter checkout's `template/core/`, rerun project validation, inspect
another dry run, and explicitly acknowledge all reported merges:

```bash
python3 scripts/install_core.py /absolute/path/to/project \
  --upgrade --dry-run --accept-merged
python3 scripts/install_core.py /absolute/path/to/project \
  --upgrade --accept-merged
```

`--accept-merged` is a global assertion for the conflicts shown by that run. It
preserves those local files and advances their incoming baseline; use it only
after reviewing every `ACCEPT MERGED` or `RELEASE TO PROJECT` line.

## 6. Remove

```bash
python3 scripts/install_core.py /absolute/path/to/project --remove --dry-run
python3 scripts/install_core.py /absolute/path/to/project --remove
```

Removal deletes only regular managed files whose digest still matches the
manifest. Any modified, missing, linked, or unsupported managed path refuses the
operation before writes. A backup is created, while project-authored files,
runtime evidence, and unrelated directories are preserved.

See `docs/harness/LIFECYCLE.md` for version, license, upgrade, removal, rollback,
and support guarantees. Preserve `LICENSE`, `NOTICE`,
`docs/harness/SOURCES.md`, and `docs/harness/source-map.json` when
redistributing an adapted profile.
