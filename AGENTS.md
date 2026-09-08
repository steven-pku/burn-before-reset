# Burn Before Reset · Project Guidance

Read the workspace-level `AGENTS.md` (the parent `Codex/AGENTS.md`) if not loaded, then `PROJECT.md`, current `STATUS.md`, relevant confirmed `DECISIONS.md` entries and `SECURITY.md` before execution-related work.

- Maintain the repository-scoped Skill and standard-library runner. A public candidate release, machine tests, real pilot coverage, a `verified` claim and global installation are distinct gates; use the latest confirmed decision and dated VALIDATION entries.
- Runner sources remain read-only; outputs are confined to the approved run directory. Deadline, billing assertion, provider, process-group stop and source-boundary checks fail closed. No paid fallback, external mutation or release is implied by autopilot selection.
- In an authorized autopilot run, preserve the one up-front mode decision and bounded continuation across inner allowance windows. Do not introduce mid-flow approval waits for already-authorized local work; the outer deadline and safety boundaries still apply.
- Claude worker confinement depends on the actual `--tools` allowlist, `--restricted`, `--safe-mode` and strict empty MCP configuration plus capability preflight. Old logs describing `--safe-mode` alone as removing built-in tools are superseded by the A21 repair; do not weaken current guards from old prose.
- Use hermetic unit/integration and negative regression tests for changed guards. Real worker calls, overnight runs, external reviews, publishing and installation require their own applicable authorization; routine governance does not rerun them.
- Preserve dated validation entries. Cross-agent ownership and business action ordering must come from confirmed project state, not from a registry-validator workaround.
