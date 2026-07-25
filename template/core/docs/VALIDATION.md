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

Completion records schema-v3 evidence with a receipt-file digest, executed
command IDs, redacted effective-argument digest, effective `cwd`, timeout, exit
code, output counts/truncation, configuration digest, verification-definition
digest, exact tracked-file digests, Git revision or `unversioned`, and an
OS/Python runtime identity digest.

Only the newest receipt is current evidence. Strict audit rejects it after a
configuration, risk, verification, tracked path, tracked file, runtime, or
incompatible revision change. Reopen the feature and rerun completion; editing
a receipt or weakening a gate is not a repair.

## Golden Journeys

- REPLACE_ME: add the first repeatable user or system journey.
