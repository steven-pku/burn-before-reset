# Burn Before Reset · Roadmap

## v0.1 · Machine-verified local candidate

- Repository-scoped Skill and metadata.
- Standard-library Python runner, strict preflight, allowlisted indexer, frozen queue, atomic state, deadline guard, and report.
- Safe dry run plus explicitly enabled local Codex pilot.
- Core task packs and deterministic tests, including guard-loss, stubborn-descendant, exception-finalization, sixty-minute gate, and prompt-boundary regressions.

Exit gate: all automated tests, historical replay, forward test, fresh-process repository discovery, and requested post-fix terminal reviews pass or return a bounded, documented unavailable state. Lifecycle remains `candidate` until at least three real tasks succeed.

## v0.2 · Bounded autonomy — landed 2026-08-25

- Product direction reset (DECISIONS 2026-08-25): the agent finds the work, one
  up-front mode question, burn to completion. Safety lives in boundaries, not gates.
- Multi-window continuation: quota exhaustion pauses (probe-and-retry), only the
  outer reset stops. Re-planning rounds refill a drained queue from fresh signals.
- `bbr discover`: vault-free source discovery over session logs, repos, documents.

## Earlier v0.2 scope · Safe pilot

- First explicit non-sensitive pilot: **done 2026-08-24**. One real Codex task ran end to end, its artifact was promoted, every receipt was reviewed, and the source roots stayed byte-identical. `PROMOTION_GATE` stands at 1/3.
- Two further real runs with evidence and no boundary violations.
- Stronger OS-level read confinement or a reduced-context worker architecture.
- Improved redaction, resumption, and quota-status adapters that use documented interfaces only.

Exit gate: three real tasks pass, lifecycle can become `verified`, and Steven approves the exact installation targets.

## v0.3 · Distribution

- Public release as a `candidate`: approved 2026-08-24. Topics and launch content follow that decision.
- Package as a plugin only if broad installation or connectors justify it.
- Claude Code adapter: landed early, in v0.1 (2026-08-25), `safe` mode only, after its own negative tests. Remaining here: UI, notifications, community task packs after separate safety review.
- Global installation and any `verified` claim stay gated on 3/3 real successful runs.
- Spend-authority hardening (third external audit, 2026-08-26): an absolute
  latest-stop ceiling independent of `reset_at`, and a second-source balance/cycle
  confirmation near the boundary that stops early when no authoritative answer is
  available. v0.2 ships the honest minimum instead: `max_worker_calls_per_run`
  plus the documented "stops on the user's clock" positioning.
