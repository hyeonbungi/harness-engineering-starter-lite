# Starter Lifecycle Contract

## Versioning

The starter uses Semantic Versioning (`MAJOR.MINOR.PATCH`). The installed
starter version is recorded in the root `VERSION` file and in the install
manifest.

- `PATCH`: backward-compatible fixes that do not change the adoption contract.
- `MINOR`: backward-compatible capabilities, commands, or optional files.
- `MAJOR`: incompatible changes to commands, manifest schema, file ownership,
  or required runtime support.

Until `1.0.0`, any minor release may contain an incompatible contract change.
Each such change must be called out in release notes and must not be applied
silently. Patch releases remain backward-compatible within the same minor
series.

The current installer therefore accepts same-version operations and compatible
upgrades within one release line, but refuses downgrades, major-version changes,
and automatic pre-1.0 minor-version changes. A same-version operation with no
file or manifest-baseline transition is a true no-op: it does not rewrite the
manifest, create a backup, or add a timestamp. Incompatible transitions require
a newer compatible installer or a separately reviewed manual adoption.

Core `0.3.0` introduces schema-v4 receipts with an execution-scoped
configuration freshness digest, bounded startup/operational context, and a
repository-local autonomous structural-improvement contract. It also installs
one callable read-only audit Skill and one regular Claude pointer file; no
managed symbolic link or reparse point is introduced. Moving from
`0.2.x` to `0.3.x` is therefore a reviewed manual adoption: preserve schema-v2/v3
receipt files as history, merge the Core files, compact feature transition events
to the newest 20 and receipt references to the newest 5, and re-complete active
evidence under schema v4. Do not reinterpret an older receipt as current proof.
Autonomous edits to managed Core files intentionally remain manifest-detectable
local changes, so a later upgrade must preserve or manually merge them.

## License and Notice

This Core distribution is released under the MIT License in `LICENSE`.
`NOTICE` identifies the distribution and the Learn Harness Engineering material
that informed it. Keep both files when copying or redistributing the profile.
The starter's license does not replace the license of separately copied
upstream material or project code added after adoption.

## Supported Runtime

The Core profile supports:

- either a POSIX-compatible shell or native Windows PowerShell 5.1+;
- Python 3.10 or newer;
- a local filesystem that preserves relative paths and regular-file semantics.

Use `./init.sh` on POSIX and `.\init.ps1` on native Windows. The PowerShell
adapter probes an active virtual environment and installed launchers without
changing execution policy or triggering Python Manager automatic installation.
If policy blocks local scripts, use the equivalent approved Python command
directly instead of weakening machine or user policy.

Gate commands use no configured shell string. The reserved `{python}` token is
valid only at `argv[0]` and expands to the harness's current interpreter.
POSIX timeout handling terminates the command process group. Windows creates a
new process group, attempts CTRL_BREAK, then invokes the absolute System32
`taskkill.exe /T /F` path and finally direct kill if needed.

Automatic lifecycle operations reject all symbolic links and Windows
junction/reparse points in relevant boundaries. This can conservatively refuse
provider-managed mounts. Local regular-file semantics are the guarantee; UNC,
network filesystems, and their atomic-replacement behavior require separate
project validation.

## Install Manifest

Installation, upgrade, and removal use a project-local manifest as the machine
record of starter-owned files. The manifest is expected to record:

- its own schema version and the installed starter version;
- each managed path as a normalized project-relative path;
- the digest of the source artifact installed at that path;
- the digest or state observed immediately after installation;
- enough metadata to distinguish a regular file from an unsupported path type.

Absolute paths, parent traversal, case aliases on Windows, and paths that escape
the target through symbolic links or junction/reparse points are invalid. The
manifest records ownership for lifecycle decisions; it does not grant
permission to overwrite project work.

## Install

Installation must be non-destructive by default.

1. The default operation installs a new profile; `--dry-run` reports every
   planned create, conflict, and refusal without changing the target.
2. Existing paths are conflicts unless an explicit lifecycle operation proves
   that they are unchanged files managed by the manifest.
3. If installation fails partway through, files created by that attempt are
   rolled back.
4. A successful install writes the manifest only after all managed files are in
   place.

Managed file copies are completed in a same-directory temporary file and exposed
with atomic replacement. Failed copies remove their partial temporary file,
new destination, and any newly empty managed directories.

## Upgrade

Use:

```bash
python3 scripts/install_core.py TARGET --upgrade --dry-run
python3 scripts/install_core.py TARGET --upgrade
```

An upgrade compares three states for every managed path:

1. the digest recorded by the installed manifest;
2. the current project digest;
3. the digest supplied by the new starter version.

An unchanged project file may be replaced when the new starter changes it. A
project-modified file must not be overwritten automatically. If only the
project changed, the file is preserved. If both project and incoming Core
changed, upgrade refuses before writing and identifies the current target,
incoming `template/core/` tree, installed version, and manifest baseline.

Before changing files or advancing a manifest baseline, an upgrade must support
`--dry-run` and create a recoverable backup containing the affected files and
prior manifest. A same-version no-op returns before this backup boundary. The
new manifest is committed only after the complete upgrade succeeds. On failure,
the tool restores the prior files and manifest. A version or manifest schema
that the tool cannot interpret is a refusal, not a best-effort mutation.

## Remove

Use:

```bash
python3 scripts/install_core.py TARGET --remove --dry-run
python3 scripts/install_core.py TARGET --remove
```

Removal acts only on paths owned by the install manifest.

- Files whose current digest matches the recorded managed digest may be
  removed.
- Modified files, untracked files, directories with unrelated contents, and
  unsupported path types are retained and reported.
- `--dry-run` shows the exact removal set.
- A backup and the prior manifest are retained until removal succeeds.
- Empty managed directories may be removed only after their contents are
  accounted for; unrelated directories are never recursively deleted.

Removal must leave project-authored files intact. If the operation cannot
prove that a path is safe to remove, it stops or leaves that path for manual
resolution.

## Manual Merge Fallback

Automation must fall back to a documented manual merge when:

- a managed file was edited by the adopting project;
- an upgrade changes the manifest schema incompatibly;
- a file type, symbolic link, or platform behavior is unsupported;
- an interrupted operation cannot prove a safe automatic continuation.

The fallback preserves the current project file and leaves the incoming starter
file under this distribution's `template/core/`. The prior manifest supplies
the installed version and baseline digest. The operator merges and validates
the project, previews the exact acknowledgement set, then advances the
manifest:

```bash
python3 scripts/install_core.py TARGET --upgrade --dry-run --accept-merged
python3 scripts/install_core.py TARGET --upgrade --accept-merged
./init.sh
```

On Windows, use the approved Python 3.10+ launcher for the lifecycle commands
and `.\init.ps1` for the final validation.

`--accept-merged` is valid only with `--upgrade`. It is an explicit assertion
that every reported conflict was reviewed: local files are preserved, incoming
digests become their next baseline, and locally modified files removed from the
incoming profile are released to project ownership. The flag must never be
used as an automatic conflict bypass.

## Rollback Boundary

Backups are recovery artifacts, not long-term configuration. A completed
operation reports their location and whether they can be removed. Rollback is
limited to files that the same lifecycle operation created, replaced, or
removed; it never resets unrelated repository state or invokes destructive Git
commands.
