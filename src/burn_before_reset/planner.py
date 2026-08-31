from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .config import AppConfig
from .indexer import index_all
from .model import SourceRef, TaskSpec
from .state import freeze_queue, write_json_atomic, write_text_atomic


def _clean_title(title: str) -> str:
    """Strip the quoting and punctuation a frontmatter title sometimes collapses to."""
    return title.strip().strip("\"'`*#·-—:：〈〉《》【】[]() \t")


def _task_id(record: SourceRef) -> str:
    material = f"{record.source_type}\0{record.root}\0{record.path}\0{','.join(record.signals)}"
    return "task-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


# Calibrated against a real 3,110-record corpus rather than intuition, because the
# first cut was wrong in a way only measurement showed: `unverified` had the top
# weight while appearing in 27.7% of files — as common as `todo`, which had the
# lowest. A marker that nearly every note carries says almost nothing about which
# note is worth a night.
#
# Measured frequency: next-step 59.8% · fixme 37.9% · blocked 27.9% ·
# unverified 27.7% · todo 27.5% · decision 8.1%.
#
# Weight = how rare the marker is (rare marker, real signal) plus one step when it
# means something is *stuck* — a decision nobody made, a claim nobody checked, a
# blocker nobody cleared. Stuck work is where an unattended night has leverage;
# an unstarted TODO would still be unstarted whoever picked it up.
SIGNAL_WEIGHT = {
    "decision": 5,     # 8.1% — rare and stuck
    "git-dirty": 4,    # one per dirty repository, inherently rare
    "unverified": 3,   # 27.7% — stuck, but common
    "blocked": 3,      # 27.9% — stuck, but common
    "todo": 2,         # 27.5% — common, not stuck
    "fixme": 2,        # 37.9% — common, not stuck
    "next-step": 1,    # 59.8% — nearly universal, says almost nothing
}

# Filenames that carry project state rather than a passing thought. Work recovered
# from these is reusable; work recovered from a dated scratch note usually is not.
DURABLE_STEMS = ("readme", "status", "roadmap", "decisions", "spec", "plan", "charter", "项目主页", "_index", "_索引")

RECENCY_LADDER = ((3, 5), (14, 4), (60, 3), (180, 2), (365, 1))


def _clamp(value: int) -> int:
    return max(0, min(5, value))


def _recency(modified_at: str, now: datetime) -> int:
    """Age is the strongest available signal for what is worth resuming tonight.

    A two-year-old TODO is noise; one from this week is live work. Without this term
    almost every candidate scores identically and the queue becomes an arbitrary
    sample of whatever hashes first.
    """
    try:
        modified = datetime.fromisoformat(modified_at)
    except (TypeError, ValueError):
        return 0
    if modified.tzinfo is None:
        modified = modified.replace(tzinfo=now.tzinfo)
    age_days = (now - modified).total_seconds() / 86400
    if age_days < 0:
        return 5
    for limit, points in RECENCY_LADDER:
        if age_days <= limit:
            return points
    return 0


def _has_real_title(title: str) -> bool:
    return len(_clean_title(title)) >= 2


def _task_from_record(record: SourceRef, run_dir: Path, now: datetime) -> TaskSpec:
    signal_set = set(record.signals)
    is_git = record.source_type == "git"
    stem = Path(record.path).stem.lower()
    durable = any(marker in stem for marker in DURABLE_STEMS)
    snippet_chars = sum(len(snippet) for snippet in record.snippets)

    # Highest-weight signal present, plus a point when several kinds coincide: a file
    # that is blocked *and* has a next step *and* an open decision is a richer target.
    strategic = _clamp(
        max((SIGNAL_WEIGHT.get(name, 2) for name in signal_set), default=2)
        + (1 if len(signal_set) >= 3 else 0)
    )
    reuse = _clamp(
        3
        + (1 if record.source_type in {"codex_sessions", "claude_sessions"} else 0)
        + (1 if durable else 0)
    )
    # Evidence density: how many distinct signal lines the indexer actually found.
    readiness = _clamp(max(1, len(record.snippets)))
    verifiability = _clamp(
        3 + (1 if is_git or "unverified" in signal_set else 0) + (1 if _has_real_title(record.title) else 0)
    )
    recency = _recency(record.modified_at, now)
    checkpointability = 5
    # Smaller, bounded work fits a closing window better than a sprawling target.
    if snippet_chars <= 300:
        token_fitness = 5
    elif snippet_chars <= 700:
        token_fitness = 4
    elif snippet_chars <= 1100:
        token_fitness = 3
    else:
        token_fitness = 2
    risk = 1 if is_git else 0
    # An open decision used to score 2 here and was therefore filtered out entirely
    # by the default maximum of 1 — the rarest, highest-leverage signal in the corpus
    # was the one category the tool systematically avoided. That discount assumed the
    # task meant *making* the decision. The decision archetype does not: it frames the
    # options and the evidence so the decision becomes cheap. That work completes
    # unattended, so it costs one step for still needing a human to close it, not two.
    human = 1 if "decision" in signal_set else 0
    task_id = _task_id(record)
    action, objective, validation = _archetype(signal_set)
    # A frontmatter title can collapse to a quote mark or a single word like
    # "config", which tells a morning reader nothing about which file it was.
    label = _clean_title(record.title)
    relative = Path(record.path)
    if len(label) < 2:
        label = relative.stem or record.path
    if relative.parent != Path("."):
        label = f"{relative.parent.as_posix()}/{label}"
    return TaskSpec(
        id=task_id,
        title=f"{action}: {label}",
        objective=objective,
        source_refs=(record.to_dict(),),
        deliverables=(f"artifacts/{task_id}.md",),
        allowed_read_roots=(record.root,),
        allowed_write_root=str(run_dir),
        validation=validation,
        strategic_value=strategic,
        reuse=reuse,
        readiness=readiness,
        verifiability=verifiability,
        recency=recency,
        checkpointability=checkpointability,
        token_fitness=token_fitness,
        risk=risk,
        human_dependency=human,
    )


# What kind of work a finding deserves. Matching the strongest signal to a shaped
# objective is the difference between "audit this file" for everything and an
# artifact you can act on: a stuck decision needs its options laid out, an
# unverified claim needs checking, a dirty repository needs a patch plan. The
# order matters — the first match wins, strongest signal first.
ARCHETYPES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "decision",
        "Frame the open decision so it can be made",
        "Recover what decision is open, lay out the real options with the evidence for and "
        "against each from the cited source only, name what information is still missing, and "
        "state which option the evidence currently favours. Do not decide; make deciding cheap.",
        (
            "artifact names the decision and at least two genuine options",
            "each option carries evidence cited to the source, or is marked unsupported",
            "missing information is listed explicitly rather than filled in by assumption",
        ),
    ),
    (
        "unverified",
        "Verify the unverified claim",
        "Identify the claim that was recorded as unverified, check it against the cited source "
        "and allowed roots, and report it as confirmed, refuted, or uncheckable-from-here. Where "
        "uncheckable, state exactly what evidence would settle it.",
        (
            "each claim is labelled confirmed / refuted / uncheckable",
            "every verdict cites the specific evidence it rests on",
            "nothing is upgraded from uncheckable to confirmed by inference",
        ),
    ),
    (
        "git-dirty",
        "Audit the repository state and propose a reviewable patch plan",
        "Determine what the uncommitted work was trying to do, whether it is coherent, and what "
        "a reviewer would need to finish or discard it. Produce a patch plan, not a patch.",
        (
            "plan separates work that looks finished from work that looks abandoned",
            "each proposed step names the files it touches",
            "no source-root file is modified",
        ),
    ),
    (
        "blocked",
        "Analyse the blocker and find what can move",
        "Establish precisely what is blocked and by what, distinguish blockers that need another "
        "person from blockers that only need work, and identify what could proceed tonight despite "
        "the block. Say plainly if nothing can.",
        (
            "the blocker is stated concretely, not restated from the note's own wording",
            "blockers needing a human are separated from blockers needing work",
            "artifact says what can proceed now, or states that nothing can",
        ),
    ),
    (
        "next-step",
        "Recover the thread and make the next step executable",
        "Reconstruct where this work actually stopped and why, then turn the recorded next step "
        "into something executable: what exactly to do, against which files, and how the result "
        "would be checked.",
        (
            "artifact states where the work stopped, with evidence",
            "the next step is concrete enough to start without rereading the source",
            "confirmed facts are separated from inference",
        ),
    ),
)

DEFAULT_ARCHETYPE = (
    "Audit and recover the unfinished work",
    "Use only the cited source and allowed roots to determine the current state, separate "
    "confirmed work from assumptions, and produce a bounded next-step artifact.",
    (
        "artifact exists and is non-empty",
        "artifact cites the source reference and separates confirmed facts from uncertainty",
        "no source-root file is modified",
    ),
)


def _archetype(signals: set[str]) -> tuple[str, str, tuple[str, ...]]:
    for name, action, objective, validation in ARCHETYPES:
        if name in signals:
            return action, objective, validation
    return DEFAULT_ARCHETYPE


def _group_key(task: TaskSpec) -> str:
    """The bucket a candidate competes in, for queue diversity.

    Both project and kind of work: one signal type can dominate a whole corpus —
    Chinese project notes say 待验证 constantly — and a night that returns ten
    verifications of ten different files is barely more useful than ten of one.
    Bucketing by project *and* archetype spreads the window across both.
    """
    reference = task.source_refs[0]
    relative = PurePosixPath(str(reference.get("path", ".")))
    parts = relative.parts
    kind = task.title.split(":", 1)[0]
    return f"{reference.get('root', '')}::{parts[0] if parts else '.'}::{kind}"


def _diversify(tasks: list[TaskSpec], limit: int) -> list[TaskSpec]:
    """Fill the queue round-robin across projects instead of straight top-N.

    Recency is the strongest scoring term, so whatever was touched most recently
    sweeps the top of the list. Straight top-N then hands back a morning report
    about one directory. Round-robin keeps score order inside each project while
    spending the window across the work rather than in one corner of it.
    """
    groups: dict[str, list[TaskSpec]] = {}
    for task in tasks:
        groups.setdefault(_group_key(task), []).append(task)
    # Best group first, so the strongest candidate overall is still picked first.
    ordered = sorted(groups.values(), key=lambda members: (-members[0].score, members[0].id))
    selected: list[TaskSpec] = []
    depth = 0
    while len(selected) < limit:
        added = False
        for members in ordered:
            if depth < len(members):
                selected.append(members[depth])
                added = True
                if len(selected) == limit:
                    break
        if not added:
            break
        depth += 1
    return selected


def _new_run_dir(config: AppConfig, now: datetime) -> Path:
    stamp = now.astimezone().strftime("%Y%m%d-%H%M%S")
    run_dir = config.run.output_root / f"run-{stamp}-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=False)
    # Candidate records carry redacted excerpts of the user's own notes. Keep the
    # run readable only by its owner, whatever umask the shell happens to carry.
    os.chmod(run_dir, 0o700)
    (run_dir / "artifacts").mkdir()
    (run_dir / "workers").mkdir()
    return run_dir


def _run_plan(config: AppConfig, run_dir: Path, records: list[SourceRef], tasks: list[dict[str, Any]]) -> str:
    lines = [
        "# Burn Before Reset · Run Plan",
        "",
        f"- Reset at: {config.run.reset_at.isoformat()}",
        f"- Hard stop at: {config.run.hard_stop_at.isoformat()}",
        f"- Mode: {config.run.mode}",
        f"- Source roots: {len(config.sources)}",
        f"- Eligible candidates: {len(records)}",
        f"- Frozen queue items: {len(tasks)}",
        "- Execution: disabled until an explicit `--execute` command and config gate both pass",
        "",
        "## Frozen queue",
        "",
    ]
    if not tasks:
        lines.append("No eligible task. Stop instead of inventing work.")
    for index, task in enumerate(tasks, 1):
        reference = task["source_refs"][0]
        signals = ", ".join(reference.get("signals", [])) or "none"
        lines.extend(
            [
                f"### {index}. {task['title']}",
                "",
                f"- ID: `{task['id']}` · score {task['score']} · risk {task['risk']}",
                f"- Source: `{reference.get('path')}` (last changed {reference.get('modified_at')})",
                f"- Picked because: signals [{signals}] · "
                f"strategic {task['strategic_value']} · recency {task['recency']} · "
                f"evidence {task['readiness']} · reuse {task['reuse']}",
                f"- Deliverable: `{task['deliverables'][0]}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _eligible_tasks(
    config: AppConfig,
    run_dir: Path,
    now: datetime,
    exclude_ids: frozenset[str] = frozenset(),
) -> tuple[list[TaskSpec], list[TaskSpec]]:
    """Index the sources as they are right now and pick this round's queue."""
    records = index_all(config.sources)
    candidates = [_task_from_record(record, run_dir, now) for record in records]
    eligible = [
        task
        for task in candidates
        if task.score >= config.task_policy.minimum_score
        and task.risk <= config.task_policy.maximum_risk
        and task.human_dependency <= config.task_policy.maximum_human_dependency
        and task.id not in exclude_ids
    ]
    eligible.sort(key=lambda task: (-task.score, task.id))
    eligible = eligible[: config.task_policy.max_candidates]
    queued = _diversify(eligible, config.execution.max_tasks)
    return eligible, queued


def plan_followup_round(
    config: AppConfig,
    run_dir: Path,
    round_index: int,
    exclude_ids: frozenset[str],
    *,
    now: datetime | None = None,
) -> tuple[str, str, list[dict[str, Any]]] | None:
    """Freeze another queue for a run whose first queue drained with time left.

    Task ids hash the source reference, so everything already worked this run is
    excluded and a source that produced a done task is not picked again. Returns
    None when nothing new qualifies — the honest end of the night, not a failure.
    """
    current = now or datetime.now(tz=config.run.reset_at.tzinfo)
    eligible, queued = _eligible_tasks(config, run_dir, current, exclude_ids)
    if not queued:
        return None
    created_at = current.astimezone().isoformat(timespec="seconds")
    queue_name = f"QUEUE-r{round_index}.json"
    write_text_atomic(
        run_dir / f"CANDIDATES-r{round_index}.jsonl",
        "".join(json.dumps(task.to_dict(), ensure_ascii=False, sort_keys=True) + "\n" for task in eligible),
    )
    queue = freeze_queue(run_dir / queue_name, [task.to_dict() for task in queued], created_at)
    with (run_dir / "RUN_PLAN.md").open("a", encoding="utf-8") as handle:
        handle.write(f"\n## Round {round_index} · re-planned at {created_at}\n\n")
        for index, task in enumerate(queued, 1):
            handle.write(f"{index}. `{task.id}` · score {task.score} · {task.title}\n")
    return queue_name, queue["tasks_sha256"], queue["tasks"]


def plan_run(config: AppConfig, *, now: datetime | None = None) -> Path:
    current = now or datetime.now(tz=config.run.reset_at.tzinfo)
    run_dir = _new_run_dir(config, current)
    eligible, queued = _eligible_tasks(config, run_dir, current)
    candidates = eligible
    created_at = current.astimezone().isoformat(timespec="seconds")

    candidate_lines = "".join(
        json.dumps(task.to_dict(), ensure_ascii=False, sort_keys=True) + "\n" for task in candidates
    )
    write_text_atomic(run_dir / "CANDIDATES.jsonl", candidate_lines)
    queue_tasks = [task.to_dict() for task in queued]
    queue = freeze_queue(run_dir / "QUEUE.json", queue_tasks, created_at)
    state = {
        "schema_version": 1,
        "run_id": run_dir.name,
        "phase": "frozen",
        "created_at": created_at,
        "reset_at": config.run.reset_at.isoformat(),
        "hard_stop_at": config.run.hard_stop_at.isoformat(),
        "queue_sha256": queue["tasks_sha256"],
        "task_status": {task.id: "queued" for task in queued},
        "completed": [],
        "failed": [],
        "stop_reason": None,
        "source_mutation_detected": False,
        "source_changed_paths": [],
        "worker_errors": [],
        "source_check_incomplete": False,
        "billing_error_detected": False,
        "quota_exhausted": False,
        "quota_wait_cycles": 0,
        "burn": {"cost_usd": 0.0, "cost_known_calls": 0, "input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0},
        "worker_calls": 0,
        "rounds": [{"queue": "QUEUE.json", "tasks_sha256": queue["tasks_sha256"]}],
        "guard_failure_detected": False,
        "stop_unconfirmed_detected": False,
        "task_results": {},
    }
    write_json_atomic(run_dir / "RUN_STATE.json", state)
    write_text_atomic(run_dir / "CHECKPOINTS.md", "# Checkpoints\n\n")
    write_text_atomic(run_dir / "events.jsonl", "")
    write_text_atomic(run_dir / "RUN_PLAN.md", _run_plan(config, run_dir, candidates, queue_tasks))
    return run_dir
