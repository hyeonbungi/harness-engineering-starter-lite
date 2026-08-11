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
- Use `execution_scope: profile` for cross-cutting checks that every selected
  profile must run. Use `execution_scope: feature` for a focused check that
  runs during completion only when the current feature binds it. Missing scope
  keeps the backward-compatible `profile` meaning.
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
`taskkill.exe /T /F` and a direct-kill fallback. After a successful gate root
exits, Core signals its isolated group once so redirected background children
cannot survive it. Missing executables, timeouts, non-zero exits, and descendants
that still hold captured streams produce `WHAT / WHY / FIX` diagnostics.
Common secret values and credential forms are masked before output is retained
in a receipt or shown.

Before starting any external gate, the runner selects commands for the current
purpose and rejects a command count or finite declared-timeout sum above the
per-run budget. Retained stdout plus stderr is bounded by the combined-output
budget even when a command requests a larger per-stream tail. Startup skips
feature-scoped bootstrap checks, rejects direct or indirect init re-entry, and
reuses its already successful repository audit as V0 evidence. Explicit profile
verification also skips unbound feature commands and refuses to claim a selected
non-V0 level that has no profile-scope command. Non-finite JSON numbers are invalid.

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
profile-scoped gates plus current-feature bindings actually selected from
V0..Vn, selected and startup risk profiles, effective runner defaults, the
execution-contract version, project,
paths, setup/start commands, startup profile, and clean-state rules. Unselected
gates and unrelated risk profiles remain in full provenance but do not expire
the receipt. Changes to the executed contract, feature verification, tracked
path or file, runtime, or compatible revision check still make it stale. Reopen
the feature and rerun completion; editing a receipt or weakening a gate is not
a repair. Historical schema-v2 and schema-v3 receipts can remain after
schema-v4 re-verification but cannot be the newest proof.

## Startup Context and Operational History

Audit classifies `AGENTS.md`, the thin `CLAUDE.md` pointer, and `docs/STATE.md`
as always-read surfaces. Their individual limits remain 8 KiB, 4 KiB, and
16 KiB, and their combined byte budget is 12 KiB. `docs/COMMUNICATION.md` and
`docs/AGENT_COORDINATION.md` are on-demand surfaces capped at 16 KiB and 12 KiB.
The callable audit Skill remains separately capped. Files cannot belong to both
classes. Bytes are a deterministic proxy for context growth; audit does not
claim an exact provider-token count.

Normal startup uses the bounded `cold-start-summary` emitted by the same init
process to select one feature instead of running another audit or loading whole
feature, Source, receipt, architecture, and validation histories. The separate
`cold-start --json` command remains available for an explicit machine reread.
Audit permits at most 256 operational features, 128 tracked paths per feature,
256 MiB of unique tracked bytes, 64 MiB of unique receipt payloads per audit,
20 recent transitions, and 5 receipt references per feature. Each unique receipt
is read, hashed, and parsed once. Control-plane JSON, gate lists, argv,
verification bindings, pre-allocation Source ranges and expanded edges,
cold-start output, clean-state scan entries, and clean-state diagnostic bytes
also have finite limits. Shared tracked paths are hashed once per audit. Git
revision queries share a 10-second audit deadline. Declared dependency and cache
directories are pruned from the streaming clean-state walk, and unreadable
subtrees fail instead of being skipped. State commands compact operational
windows; receipt files and Git history remain intact.

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

## Parallel Agent Coordination Contract

The versioned `harness:agent-coordination:v1` contract is installed in
`docs/AGENT_COORDINATION.md` and routed from `AGENTS.md` only when the user
explicitly requests multiple agents or parallel work. Core audit rejects drift
in that trigger, writer-per-worktree isolation, disjoint ownership, lead-only
control-plane writes, structured handoff fields, lead evidence re-verification,
the read-only reviewer requirement for `cross_component` and `high_risk`, and
finite worker, round, review, delegation, timeout, token/context, handoff, and
cleanup budgets.

The contract Fixture also exercises two disjoint writer worktrees from one
clean Git commit, verifies that the lead checkout's control plane stays
unchanged while workers run, and integrates one result at a time before the
lead audit. Non-Git work, overlapping paths, and undefined shared-state
isolation are explicit stop conditions for parallel writers.

These checks prove that the contract and a representative Git flow remain
available. They cannot prove that a Codex, Claude Code, model, or host runtime
semantically follows the instructions, measures tokens, enforces the declared
deadline, or blocks recursive delegation. Re-run a clean-clone client smoke
test when those clients or runtimes change; its host execution record must show
agent parentage, maximum concurrency, rounds, elapsed time, context mode, token
measurement when available, and budget-exhaustion behavior.

## Golden Journeys

- REPLACE_ME: add the first repeatable user or system journey.
