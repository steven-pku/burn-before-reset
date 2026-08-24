# Burn Before Reset · Roadmap

## v0.1 · Machine-verified local candidate

- Repository-scoped Skill and metadata.
- Standard-library Python runner, strict preflight, allowlisted indexer, frozen queue, atomic state, deadline guard, and report.
- Safe dry run plus explicitly enabled local Codex pilot.
- Core task packs and deterministic tests, including guard-loss, stubborn-descendant, exception-finalization, sixty-minute gate, and prompt-boundary regressions.

Exit gate: all automated tests, historical replay, forward test, fresh-process repository discovery, and requested post-fix terminal reviews pass or return a bounded, documented unavailable state. Lifecycle remains `candidate` until at least three real tasks succeed.

## v0.2 · Safe pilot

- First explicit non-sensitive pilot: **done 2026-08-24**. One real Codex task ran end to end, its artifact was promoted, every receipt was reviewed, and the source roots stayed byte-identical. `PROMOTION_GATE` stands at 1/3.
- Two further real runs with evidence and no boundary violations.
- Stronger OS-level read confinement or a reduced-context worker architecture.
- Improved redaction, resumption, and quota-status adapters that use documented interfaces only.

Exit gate: three real tasks pass, lifecycle can become `verified`, and Steven approves the exact installation targets.

## v0.3 · Distribution

- Public release as a `candidate`: approved 2026-08-24. Topics and launch content follow that decision.
- Package as a plugin only if broad installation or connectors justify it.
- Optional Claude Code adapter, UI, notifications, or community task packs after separate safety review.
- Global installation and any `verified` claim stay gated on 3/3 real successful runs.
