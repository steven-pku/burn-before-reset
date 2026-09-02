"""The HTML report must hold up across languages, outcomes, and delivery shapes.

This page ships to strangers. One good night on one machine is not a standard,
so every scenario below is synthetic and adversarial on purpose: every stop
reason the runner can write, every archetype as the dominant delivery, ties,
empty runs, giant runs, missing files, hostile markup, unsupported languages,
providers that report tokens but no price, runs with no events at all.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from burn_before_reset import report_html
from burn_before_reset.report_html import (
    ARCHETYPE_ORDER,
    PROVERBS,
    STOP_TONE,
    STOP_WORD,
    STOP_WORD_DEFAULT,
    pick_proverb,
    write_html_report,
)
from burn_before_reset.validation import KNOWN_STOP_REASONS

ACTION = {
    "decision": "Frame the open decision so it can be made",
    "verify": "Verify the unverified claim",
    "blocker": "Analyse the blocker and find what can move",
    "patch": "Audit the repository state and propose a reviewable patch plan",
    "thread": "Recover the thread and make the next step executable",
    "recover": "Audit and recover the unfinished work",
    "sweep": "Sweep the project for what nobody wrote down",
}
EXTERNAL = re.compile(r'(?:src|href)\s*=\s*["\']https?://|@import|url\(https?:')
T0 = datetime(2026, 9, 1, 23, 10, tzinfo=timezone(timedelta(hours=8)))


def make_run(
    root: Path,
    *,
    stop_reason: str | None = "quota_exhausted",
    items: list[tuple[str, str, str]] = (),
    bodies: dict[str, str] | None = None,
    failed: int = 0,
    waits: int = 0,
    priced: bool = True,
    tokens: int = 120_000,
    hours: float = 3.2,
    events: bool = True,
    burn_pace: bool = True,
    reused: int = 0,
    moved: list[str] = (),
    attributed: bool = False,
    worker_errors: list[str] = (),
    drop_artifact_for: set[int] = frozenset(),
) -> Path:
    """Build a run directory from a shape description. Returns its state."""
    run_dir = root / "run-20260901-231000-synthetic"
    (run_dir / "artifacts").mkdir(parents=True)
    tasks, completed, lines = [], [], []
    clock = T0
    if events:
        lines.append({"timestamp": clock.isoformat(), "type": "run.started", "run_id": run_dir.name})
    for index, (archetype, short, project) in enumerate(items):
        prefix = "sweep" if archetype == "sweep" else "task"
        task_id = f"{prefix}-{index:012x}"
        tasks.append(
            {
                "id": task_id,
                "title": f"{ACTION[archetype]}: {short}",
                "deliverables": [f"artifacts/{task_id}.md"],
                "source_refs": [
                    {"source_type": "markdown", "root": f"/srv/{project}", "path": f"notes/{short}.md",
                     "modified_at": (T0 - timedelta(days=1)).isoformat(), "signals": ["todo"]}
                ],
            }
        )
        completed.append(task_id)
        body = (bodies or {}).get(short, f"# {short}\n\nConfirmed from source. | a | b |\n|---|---|\n| 1 | 2 |\n")
        if index not in drop_artifact_for:
            (run_dir / "artifacts" / f"{task_id}.md").write_text(body, encoding="utf-8")
        if events:
            clock += timedelta(minutes=2)
            lines.append({"timestamp": clock.isoformat(), "type": "task.started", "task_id": task_id})
            clock += timedelta(minutes=9)
            lines.append({"timestamp": clock.isoformat(), "type": "task.completed", "task_id": task_id})
    failed_ids = []
    for index in range(failed):
        task_id = f"task-fail{index:08x}"
        tasks.append({"id": task_id, "title": f"{ACTION['verify']}: failing-{index}", "deliverables": [f"artifacts/{task_id}.md"],
                      "source_refs": [{"root": "/srv/x", "path": "x.md", "modified_at": T0.isoformat(), "signals": []}]})
        failed_ids.append(task_id)
        if events:
            clock += timedelta(minutes=1)
            lines.append({"timestamp": clock.isoformat(), "type": "task.started", "task_id": task_id})
            clock += timedelta(minutes=3)
            lines.append({"timestamp": clock.isoformat(), "type": "task.failed", "task_id": task_id, "error_type": "WorkerReportedError"})
    for cycle in range(waits):
        if events:
            clock += timedelta(minutes=5)
            lines.append({"timestamp": clock.isoformat(), "type": "quota.waiting", "task_id": "task-x", "wait_cycle": cycle + 1})
    if events:
        clock += timedelta(minutes=1)
        lines.append({"timestamp": clock.isoformat(), "type": "run.stopped", "stop_reason": stop_reason})
        (run_dir / "events.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in lines), encoding="utf-8")
    (run_dir / "QUEUE.json").write_text(json.dumps({"tasks": tasks, "tasks_sha256": "x"}, ensure_ascii=False), encoding="utf-8")
    state = {
        "run_id": run_dir.name, "phase": "stopped", "stop_reason": stop_reason,
        "completed": completed, "failed": failed_ids, "quota_wait_cycles": waits,
        "rounds": [{"queue": "QUEUE.json"}], "worker_calls": len(completed) + failed,
        "burn": {"cost_usd": 12.5 if priced else None, "cost_known_calls": len(completed) if priced else 0},
        "reused_from_prior_runs": reused, "source_changed_paths": list(moved),
        "source_mutation_detected": attributed, "source_movement_observed": bool(moved),
        "worker_errors": list(worker_errors),
        "task_results": {fid: {"error_type": "WorkerReportedError"} for fid in failed_ids},
    }
    if burn_pace:
        state["burn_pace"] = {"spent_usd": 12.5 if priced else 0.0, "hours_elapsed": hours, "output_tokens": tokens}
    (run_dir / "RUN_STATE.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return run_dir


def render(run_dir: Path, language: str = "zh") -> str:
    state = json.loads((run_dir / "RUN_STATE.json").read_text(encoding="utf-8"))
    return write_html_report(run_dir, state, language=language).read_text(encoding="utf-8")


class ReportScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)

    def fresh(self) -> Path:
        sub = self.root / f"s{len(list(self.root.iterdir()))}"
        sub.mkdir()
        return sub

    # ---- every outcome the runner can write, in both languages ----
    def test_every_stop_reason_renders_in_both_languages(self) -> None:
        reasons = [*sorted(KNOWN_STOP_REASONS), None, "some_future_reason"]
        for reason in reasons:
            for lang in ("zh", "en"):
                with self.subTest(reason=reason, lang=lang):
                    run = make_run(self.fresh(), stop_reason=reason, items=[("verify", "claim-a", "proj")])
                    page = render(run, lang)
                    zh_word, en_word = STOP_WORD.get(reason or "", STOP_WORD_DEFAULT)
                    self.assertIn(zh_word if lang == "zh" else en_word, page)
                    self.assertFalse(EXTERNAL.search(page), "no external requests, ever")
                    tone = STOP_TONE.get(reason or "", "bad")
                    expect = "bad" if tone == "bad" else "good"
                    self.assertIn(f'class="oracle {expect}"', page)

    # ---- the proverb is a pure function of what was delivered ----
    def test_each_archetype_as_dominant_picks_its_own_proverb(self) -> None:
        for archetype in ARCHETYPE_ORDER:
            items = [*[(archetype, f"{archetype}-{i}", "p") for i in range(3)], ("verify" if archetype != "verify" else "sweep", "other", "p")]
            key, dominant = pick_proverb("good", [{"archetype": a} for a, _, _ in items])
            self.assertEqual((key, dominant), (archetype, archetype))
            for lang in ("zh", "en"):
                page = render(make_run(self.fresh(), items=items), lang)
                self.assertIn(PROVERBS[archetype][lang], page)

    def test_tie_breaks_toward_what_needs_a_human_first(self) -> None:
        items = [{"archetype": "sweep"}, {"archetype": "decision"}, {"archetype": "sweep"}, {"archetype": "decision"}]
        self.assertEqual(pick_proverb("good", items)[0], "decision")

    def test_fault_consoles_and_empty_reassures(self) -> None:
        self.assertEqual(pick_proverb("bad", [{"archetype": "decision"}])[0], "fault")
        self.assertEqual(pick_proverb("bad", [])[0], "fault")
        self.assertEqual(pick_proverb("good", [])[0], "empty")
        self.assertEqual(pick_proverb("warn", [{"archetype": "patch"}])[0], "patch")

    # ---- languages ----
    def test_language_selection_and_fallback(self) -> None:
        run = make_run(self.fresh(), items=[("decision", "choose", "p")])
        self.assertIn('<html lang="zh">', render(run, "中文"))
        self.assertIn('<html lang="en">', render(run, "en"))
        for unsupported in ("ja", "de", "Français", "日本語"):
            with self.subTest(lang=unsupported):
                self.assertIn('<html lang="en">', render(run, unsupported), "no dictionary → English, never a machine guess")
        # auto follows the artifacts themselves
        zh_run = make_run(self.fresh(), items=[("decision", "决策", "p")], bodies={"决策": "# 决策\n\n这是一段中文正文，用来判断语言。" * 20})
        self.assertIn('<html lang="zh">', render(zh_run, "auto"))
        en_run = make_run(self.fresh(), items=[("decision", "choose", "p")], bodies={"choose": "# Choose\n\nPlain English prose for detection. " * 20})
        self.assertIn('<html lang="en">', render(en_run, "auto"))

    def test_chinese_page_echoes_english_proverb_but_english_page_stays_english(self) -> None:
        run = make_run(self.fresh(), items=[("thread", "resume", "p")])
        zh = render(run, "zh")
        self.assertIn(PROVERBS["thread"]["zh"], zh)
        self.assertIn(PROVERBS["thread"]["en"], zh)
        en = render(run, "en")
        self.assertNotIn(PROVERBS["thread"]["zh"], en)

    # ---- hostile and unusual content ----
    def test_worker_output_and_titles_are_data_not_markup(self) -> None:
        hostile = "<script>alert('x')</script><img src=x onerror=alert(1)>"
        run = make_run(self.fresh(), items=[("verify", hostile, "proj</script>")],
                       bodies={hostile: f"# {hostile}\n\n{hostile}\n\n```\n</script><script>bad()</script>\n```\n"})
        page = render(run, "en")
        # Raw tags must never survive; their escaped text must.
        self.assertNotIn("<script>alert", page)
        self.assertNotIn("<img src=x", page)
        self.assertIn("&lt;script&gt;alert", page)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", page)
        # the JSON payload must not be able to close its own script tag
        payload = page.split('id="bbr-data">', 1)[1].split("</script>", 1)[0]
        self.assertNotIn("</", payload)

    def test_non_latin_titles_and_projects_survive(self) -> None:
        run = make_run(self.fresh(), items=[("sweep", "設定ファイルの整理", "プロジェクト"), ("decision", "اختيار المسار", "مشروع"), ("thread", "🔥 hot path 🔥", "emoji-proj")])
        for lang in ("zh", "en"):
            page = render(run, lang)
            for needle in ("設定ファイルの整理", "اختيار المسار", "🔥 hot path 🔥", "プロジェクト"):
                self.assertIn(needle, page)

    # ---- delivery shapes ----
    def test_empty_run_renders_calmly(self) -> None:
        for reason in ("deadline_guard", "billing_or_auth_error"):
            for lang in ("zh", "en"):
                with self.subTest(reason=reason, lang=lang):
                    page = render(make_run(self.fresh(), stop_reason=reason, items=[]), lang)
                    self.assertNotIn('class="comp"', page)
                    self.assertIn("first-empty", page)
                    expected = PROVERBS["empty" if reason == "deadline_guard" else "fault"][lang]
                    self.assertIn(expected, page)

    def test_sixty_artifacts_render(self) -> None:
        items = [(ARCHETYPE_ORDER[i % 7], f"item-{i}", f"proj-{i % 5}") for i in range(60)]
        page = render(make_run(self.fresh(), items=items), "en")
        self.assertEqual(page.count('class="card"'), 60)
        self.assertEqual(page.count('class="act-queue"'), 60)

    def test_oversized_artifact_is_truncated_not_fatal(self) -> None:
        original = report_html.MAX_EMBED_BYTES
        report_html.MAX_EMBED_BYTES = 2_000
        self.addCleanup(setattr, report_html, "MAX_EMBED_BYTES", original)
        run = make_run(self.fresh(), items=[("recover", "big", "p")], bodies={"big": "# big\n\n" + ("x" * 500 + "\n") * 40})
        page = render(run, "en")
        self.assertIn("truncnote", page)

    def test_missing_artifact_file_does_not_crash(self) -> None:
        run = make_run(self.fresh(), items=[("verify", "gone", "p"), ("verify", "there", "p")], drop_artifact_for={0})
        page = render(run, "zh")
        self.assertEqual(page.count('class="card"'), 2)

    def test_tokens_only_provider_shows_tokens_not_dollars(self) -> None:
        page = render(make_run(self.fresh(), items=[("verify", "a", "p")], priced=False, tokens=98_765), "en")
        self.assertIn("98,765", page)
        self.assertNotIn("$", page.split('class="facts"')[1].split("</div></div>")[0])

    def test_no_burn_pace_and_no_events_still_renders(self) -> None:
        run = make_run(self.fresh(), items=[("verify", "a", "p")], burn_pace=False, events=False)
        page = render(run, "en")
        self.assertNotIn('id="watch"', page)
        self.assertIn('class="oracle good"', page)

    def test_exception_line_omits_zero_parts(self) -> None:
        both = render(make_run(self.fresh(), items=[("verify", "a", "p")], failed=1, waits=2), "zh")
        self.assertIn("失败 1", both)
        self.assertIn("中途额度关闭 2 次", both)
        waits_only = render(make_run(self.fresh(), items=[("verify", "a", "p")], waits=3), "zh")
        self.assertNotIn("失败", waits_only.split('class="tile fline warn"')[1][:80])
        clean = render(make_run(self.fresh(), items=[("verify", "a", "p")]), "zh")
        self.assertNotIn('fline warn', clean)

    def test_ledger_reports_movement_attribution_and_errors(self) -> None:
        benign = render(make_run(self.fresh(), items=[("verify", "a", "p")], moved=["/srv/p/notes/a.md"], attributed=False, worker_errors=["worker reported is_error: spend limit"], reused=4), "en")
        self.assertIn("cannot be the cause", benign)
        self.assertIn("spend limit", benign)
        self.assertIn("named in RUN_PLAN.md", benign)
        blamed = render(make_run(self.fresh(), stop_reason="source_mutation_detected", items=[("verify", "a", "p")], moved=["/srv/p/notes/a.md"], attributed=True), "en")
        self.assertIn("boundary violation", blamed)

    def test_rendering_is_deterministic(self) -> None:
        run = make_run(self.fresh(), items=[("decision", "a", "p"), ("sweep", "b", "q")], failed=1, waits=1)
        self.assertEqual(render(run, "zh"), render(run, "zh"))


if __name__ == "__main__":
    unittest.main()


class SingularLabelTests(unittest.TestCase):
    """English counts one thing in the singular; the Chinese page counts with 个 and needs nothing."""

    def test_one_decision_reads_in_the_singular(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = make_run(Path(temporary) / "run", items=[("decision", "d-1", "p"), ("sweep", "s-1", "p"), ("sweep", "s-2", "p")])
            page = render(run_dir, "en")
            self.assertIn("1 decision framed", page)
            self.assertNotIn("1 decisions framed", page)
            self.assertIn('class="name">decision framed<', page)
            self.assertIn('class="name">project sweeps<', page)
            self.assertNotIn('class="name">decisions framed<', page)
            self.assertIn("Elapsed", page)
            zh = render(run_dir, "zh")
            self.assertIn("1 个备好的决策", zh)
