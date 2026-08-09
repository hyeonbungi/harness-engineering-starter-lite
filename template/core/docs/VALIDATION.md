# Validation

## Gate Levels

| Level | Purpose | Typical use |
| --- | --- | --- |
| V0 | Structure, configuration, static syntax | Every change |
| V1 | Focused lint, type, unit, or contract checks | Local code |
| V2 | Startup, runtime, and integration checks | Runtime behavior |
| V3 | End-to-end user or cross-component journey | Visible or boundary changes |
| V4 | Security, performance, or recovery checks | High-risk changes |

Risk profiles are contiguous: selecting V3 also runs V0, V1, and V2. A feature
cannot choose a completion profile weaker than its declared `risk_profile`.

## Executable Feature Contract

- Configure gate commands as argument arrays, not shell strings.
- Use `{python}` only as `argv[0]` when a portable built-in or project Python
  command must run with the current harness interpreter.
- Give each gate a stable `id`, project-relative `cwd`, positive timeout,
  bounded output limit, and actionable `why`/`fix` text.
- Bind every feature verification requirement to one or more
  `{level, command_id}` pairs.
- List the exact regular project files whose digest makes the result current in
  `tracked_files`.
- Do not list `harness.config.json` in `tracked_files`; receipt configuration
  digests cover it without making unrelated unexecuted gates stale.
- A required binding that is missing, outside the declared risk profile, or not
  executed blocks completion.
- V0 includes the reserved built-in `harness-audit`; configured commands cannot
  reuse that ID.

## Runner and Failure Rules

The runner uses no shell evaluation, keeps execution inside the project root,
inherits the environment, closes stdin, and retains only a bounded tail of each
output stream. A timeout terminates the process group on POSIX. On Windows it
creates a new process group, attempts CTRL_BREAK, then uses absolute System32
`taskkill.exe /T /F` and a direct-kill fallback. Missing executables, timeouts,
non-zero exits, and output truncation produce `WHAT / WHY / FIX` diagnostics.
Common secret values and credential forms are masked before output is retained
in a receipt or shown.

The Core distribution tests Windows creation flags, termination fallback,
current-Python expansion, reparse-point rejection, and the PowerShell script
contract on every runner. A native Windows runner must additionally execute
`.\init.ps1 -Setup`, repeat `.\init.ps1`, and the child-process timeout Fixture.

## Receipts and Freshness

Completion records schema-v4 evidence with a receipt-file digest, executed
command IDs, redacted effective-argument digest, effective `cwd`, timeout, exit
code, output counts/truncation, a full configuration provenance digest, an
executed-configuration freshness digest, verification-definition digest, exact
tracked-file digests, Git revision or `unversioned`, and an OS/Python runtime
identity digest.

Only the newest receipt is current evidence. The freshness digest includes the
selected V0..Vn gates, selected and startup risk profiles, runner, project,
paths, setup/start commands, startup profile, and clean-state rules. Unselected
gates and unrelated risk profiles remain in full provenance but do not expire
the receipt. Changes to the executed contract, feature verification, tracked
path or file, runtime, or compatible revision check still make it stale. Reopen
the feature and rerun completion; editing a receipt or weakening a gate is not
a repair. Historical schema-v2 and schema-v3 receipts can remain after
schema-v4 re-verification but cannot be the newest proof.

## Startup Context and Operational History

Audit caps the always-read instruction surfaces: `AGENTS.md` at 8 KiB,
`CLAUDE.md` at 4 KiB, and both `docs/COMMUNICATION.md` and `docs/STATE.md` at
16 KiB. Exceeding a limit requires consolidation or moving task-specific detail
to an existing nearby document; raising a limit just to pass is not a repair.

Normal startup uses the bounded `cold-start --json` answer to select one feature
instead of loading whole feature, Source, receipt, architecture, and validation
histories. Per feature, audit permits at most 20 recent transition events and 5
receipt references. State commands compact to those windows; receipt files and
Git history remain intact.

Audit also requires the versioned `harness:auto-improvement:v1` contract in both
`AGENTS.md` and `docs/COMMUNICATION.md`. Removing its standing authority,
explicit opt-out, repository-local scope, one-loop budget, or `BOOT-001`
maintenance route fails with `WHAT / WHY / FIX`. This proves that an installed
repository still declares the behavior; it does not claim that every host model
will override a higher-priority system policy or correctly identify every defect.

## Callable Harness Health Audit

The canonical on-demand workflow lives at
`.agents/skills/audit-harness-health/SKILL.md`, where Codex and shared Agent
Skills clients can discover it. The `.claude` entry is a regular, bounded
pointer file with matching discovery metadata; it directs Claude Code to the
canonical workflow instead of copying its audit rules. A regular pointer file
preserves the installer's symbolic-link and Windows reparse-point refusal
contract.

Core audit rejects a missing or oversized canonical Skill, missing read-only and
depth boundaries, name or description drift, a broken pointer target, and audit
logic copied into the Claude pointer. The Skill runs the existing
`python3 scripts/harness.py audit` once and expands to related ledgers only when
current evidence requires it. It does not run setup, product commands, full init,
network requests, or repairs as part of the audit.

Static validation proves registration, routing and repository invariants. It
cannot prove that a particular agent client selected the Skill, followed every
instruction, or enforced runtime permissions; evaluate those claims in a clean
client session when the model or agent runtime changes.

## Golden Journeys

- REPLACE_ME: add the first repeatable user or system journey.
