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

`AGENTS.md` also routes user-facing behavior to `docs/COMMUNICATION.md`. Keep its
Korean honorific, accessible explanation, concise evidence reporting, and
bounded autonomous structural-improvement requirements unless the user
explicitly replaces that contract through a reviewed change.

The callable harness audit has one canonical workflow at
`.agents/skills/audit-harness-health/SKILL.md`, where Codex and shared Agent
Skills clients can discover it. Claude Code uses the matching small `.claude`
pointer. The pointer is a regular managed file rather than a filesystem link,
so Windows checkout and the reparse-point refusal contract remain unchanged.
Invoke `$audit-harness-health` in Codex or `/audit-harness-health` in Claude Code.
The audit is read-only; request repairs separately after reviewing its findings.

If another client does not discover `.agents/skills`, add only one regular
project-local `SKILL.md` at that client's documented discovery path. Keep the
same `name` and `description`, direct it to read the `.agents` canonical file in
full, and do not copy audit steps. Register the new pointer in `REQUIRED_FILES`,
`AUDIT_SKILL_BRIDGES`, `BOOT-001.tracked_files`, the component/source ledgers,
and the install Fixture together. Do not add a client bridge speculatively.

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
   default is unsuitable, `max_output_bytes`. Keep finite runner budgets for
   external command count, aggregate timeout, and combined retained output.
6. Enable only risk profiles whose contiguous V0..Vn levels are configured.
7. Describe actual boundaries in `docs/ARCHITECTURE.md` and current facts in
   `docs/STATE.md`.
8. Do not add `harness.config.json` to feature `tracked_files`; schema-v4
   receipts bind its relevant execution contract separately.
9. List only project-owned dependency or cache trees in
   `clean_state.excluded_dirs`; never exclude product source or generated output
   whose cleanliness is part of completion.

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
`harness.config.json`, `feature_list.json`, `docs/STATE.md`, evidence paths,
missing files, and symbolic-link or Windows junction/reparse-point paths cannot
be tracked.

Keep the `harness:state` marker block in `docs/STATE.md` intact. State commands
update only that bounded block from `feature_list.json`.

Gate commands default to `execution_scope: profile`, meaning every selected
risk profile runs them. Mark a focused command `execution_scope: feature` only
when it should run during completion for a feature that binds its exact ID.
Explicit `verify --risk` runs profile-scope commands only; it never executes an
unbound feature command. Both verify and startup reject a selected level above
V0 when that level has no real profile-scope command. Startup also rejects direct
or indirect same-repository init re-entry.

## 3. Validate

```bash
./init.sh --setup
./init.sh
./init.sh
```

Native Windows PowerShell uses:

```powershell
.\init.ps1 -Setup
.\init.ps1
.\init.ps1
```

The standard path must be safe to repeat. Each init emits the five bounded
`cold-start-summary` answers from the same successful audit. BOOT-001 binds the
Core audit, two initialization runs, and the explicit machine-readable
`cold-start --json` self-check to executable V0/V1 commands.

`init --setup` is the deliberate exception to single-audit reuse. Because the
declared setup command may mutate the project, Core audits again after setup and
uses that post-mutation result as V0 evidence.

The repeated sequence above is adoption evidence, not the cost of every work step.
For an ordinary session, read `AGENTS.md` and the current `docs/STATE.md`, run the
platform init once, and use its `cold-start-summary` to select one current feature.
Run the separate JSON command only when another machine-readable read is required.
Do not load the whole feature list, Source map, receipt directory, architecture,
or validation history unless the selected work needs it. Use focused checks while
editing and the required risk profile once at completion.

For a lightweight health review, invoke `audit-harness-health`. It reads the
current router, state and one selected feature first, runs
`python3 scripts/harness.py audit` once, and opens larger Source, receipt and Git
histories only to explain detected drift. It never replaces the adoption or
completion gates.

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

`complete` is the only supported path to `passing`. It executes profile-wide
commands plus feature-scoped commands bound by the current feature for every
required level, proves that all bindings ran, checks clean state, and writes a
schema-v4 receipt under `.harness/evidence/`. Selection fails before spawning a
gate when external command count or aggregate declared timeout exceeds the
runner budget.

When a resident agent confirms a recurring or reproducible defect in agent
behavior, the harness, or the work loop, the installed contract grants standing
permission for one repository-local improvement without a separate command. If
no feature is active, activate or reopen `BOOT-001`; if another feature is active,
finish it first unless the defect blocks safety or correctness, in which case
block it with a recovery reason. Announce the bounded change, run focused checks,
then complete `BOOT-001`. Do not rewrite the install manifest: its old digest must
continue to identify the intentional local customization during a later upgrade.
Explicit read-only/stop instructions and higher-priority host policy still win.

Strict audit compares the latest receipt with the current:

- receipt file digest and complete schema-v4 execution structure;
- full `harness.config.json` provenance digest recorded at completion;
- freshness digest of the profile-wide and current-feature V0..Vn gates actually
  executed, selected and startup risk
  profiles, effective runner defaults, execution-contract version, project,
  paths, setup/start commands, startup profile, and clean-state rules;
- feature risk, verification, and tracked-path definition digest;
- digest of every exact tracked file;
- Git revision, when both receipt and current project are versioned;
- OS/platform and Python implementation/major.minor runtime identity.

When both completion and current audit are unversioned, exact tracked-file
digests remain authoritative. Moving between unversioned and versioned state
makes the revision evidence stale. A
stale receipt blocks strict audit. Use `state reopen` with a reason and complete
again; recovery validates old receipt structure without pretending it is fresh.
Unselected gates and unrelated risk profiles may change without invalidating a
receipt because current audit still validates them and they did not participate
in that completion run. Older receipts remain history and are not treated as
current proof. Historical schema-v2 and schema-v3 receipts may remain after a
`0.3.x` schema-v4 re-verification, but they cannot be the newest proof; v2 lacks
runtime identity and both lack the execution-scoped configuration digest.

To keep the operational feature ledger bounded, each feature retains its newest
20 transition events and newest 5 receipt references. Older receipt files remain
under `.harness/evidence/`, and Git remains the durable transition history. Audit
rejects manually accumulated arrays beyond those windows rather than silently
loading them into every future session.

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

If the installed and incoming versions match and there is no file or manifest
baseline transition, the actual upgrade is a no-op. It preserves local-only
customizations without rewriting the manifest, creating a timestamp, or leaving
a backup directory.

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
