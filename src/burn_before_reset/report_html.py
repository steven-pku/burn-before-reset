"""The run's human-facing deliverable: one self-contained HTML page.

`MORNING_REPORT.md` (the Markdown twin) stays the machine contract the
orchestrating agent reads back. This page is what the *user* opens after a run
they slept through — or worked through; nothing here assumes morning — so it is
held to a product standard, not a log standard:

- Generated deterministically by this module, never improvised by the
  orchestrating agent: every agent and every model produces the same page, and
  every piece of copy comes from a fixed dictionary — data fills slots, nothing
  is composed freestyle.
- The verdict is a proverb, chosen deterministically from a curated bilingual
  table by what the run *delivered* — not by how much it burned. Spend is a
  fact tile; the judgment is about what the user woke up to.
- Follow-up is the primary action: pick artifacts, copy a handoff brief for any
  agent to continue the work. Grading is a small optional feedback channel.
- Visual system: neutral surfaces, one brand accent (the ember orange), a
  validated categorical palette for the seven kinds of work, reserved status
  colours for safety, stroke icons on every section and tile. Identity never
  rides on colour alone — every hue ships with a label.
- Fully self-contained: no network request of any kind. The page embeds excerpts
  of the user's own notes, so even a CDN font would leak.
- A failed run renders as carefully as a good one, and says plainly why.
- Every string that originates in a task, an artifact, or an event is
  HTML-escaped; worker output is data here, never markup.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .state import read_json, write_text_atomic

MAX_EMBED_BYTES = 8_000_000
REPORT_BASENAME = "REPORT.html"

ARCHETYPE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("Frame the open decision", "decision"),
    ("Verify the unverified claim", "verify"),
    ("Analyse the blocker", "blocker"),
    ("Audit the repository state", "patch"),
    ("Recover the thread", "thread"),
    ("Sweep the project", "sweep"),
)
DEFAULT_ARCHETYPE = "recover"
ARCHETYPE_ORDER = ("decision", "verify", "blocker", "patch", "thread", "recover", "sweep")

STOP_TONE = {
    "quota_exhausted": "good",
    "queue_exhausted": "good",
    "drain_window": "good",
    "deadline_guard": "good",
    "operator_stop": "warn",
    "worker_call_cap": "warn",
    "worker_reported_error": "warn",
    "task_timeout": "warn",
}
DEFAULT_TONE = "bad"

STOP_WORD = {
    "quota_exhausted": ("烧尽", "Burned out"),
    "queue_exhausted": ("做完", "All done"),
    "drain_window": ("准点收手", "On time"),
    "deadline_guard": ("准点收手", "On time"),
    "operator_stop": ("中途叫停", "Called off"),
    "worker_call_cap": ("中途叫停", "Called off"),
    "task_timeout": ("中途叫停", "Called off"),
    "worker_reported_error": ("中途叫停", "Called off"),
}
STOP_WORD_DEFAULT = ("异常停机", "Fault stop")

# ---------------------------------------------------------------------------
# The verdict: a proverb about what the run DELIVERED, never about the burn.
# Real proverbs in each language, matched by spirit. Selection is deterministic:
# a fault consoles, an empty-but-safe run reassures, otherwise the dominant
# delivered archetype speaks.
# ---------------------------------------------------------------------------
PROVERBS: dict[str, dict[str, str]] = {
    "decision": {"zh": "谋定而后动", "en": "Measure twice, cut once."},
    "verify": {"zh": "耳听为虚，眼见为实", "en": "Trust, but verify."},
    "blocker": {"zh": "解铃还须系铃人", "en": "A problem shared is a problem halved."},
    "patch": {"zh": "磨刀不误砍柴工", "en": "A stitch in time saves nine."},
    "thread": {"zh": "趁热打铁", "en": "Strike while the iron is hot."},
    "recover": {"zh": "亡羊补牢，为时未晚", "en": "Better late than never."},
    "sweep": {"zh": "当局者迷，旁观者清", "en": "The spectator sees more of the game."},
    "empty": {"zh": "小心驶得万年船", "en": "Better safe than sorry."},
    "fault": {"zh": "吃一堑，长一智", "en": "A smooth sea never made a skilled sailor."},
}


def pick_proverb(tone: str, items: list[dict[str, Any]]) -> tuple[str, str]:
    """Return (proverb key, dominant archetype or ''). Pure function of the receipts."""
    if tone == "bad":
        return "fault", ""
    if not items:
        return "empty", ""
    counts: dict[str, int] = {}
    for item in items:
        counts[item["archetype"]] = counts.get(item["archetype"], 0) + 1
    dominant = max(counts, key=lambda k: (counts[k], -ARCHETYPE_ORDER.index(k)))
    return dominant, dominant


# ---------------------------------------------------------------------------
# Icons: stroke glyphs on a 24-grid, currentColor, so they inherit the tile's
# hue and need no assets.
# ---------------------------------------------------------------------------
def _svg(paths: str, size: int = 18) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths}</svg>'
    )


ICON = {
    "flag": '<path d="M4 22V4a1 1 0 0 1 1-1h11l-1.5 4 1.5 4H5"/>',
    "layers": '<path d="m12 3 9 4.5-9 4.5-9-4.5L12 3z"/><path d="m3 12 9 4.5 9-4.5"/><path d="m3 16.5 9 4.5 9-4.5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "shield": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3z"/><path d="m9 12 2 2 4-4"/>',
    "scale": '<path d="M12 3v18M5 7l7-4 7 4"/><path d="M3 13l2-6 2 6a2.5 2.5 0 0 1-4 0z"/><path d="M17 13l2-6 2 6a2.5 2.5 0 0 1-4 0z"/><path d="M8 21h8"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a6 6 0 0 1-8 8L6.6 20.4a2.1 2.1 0 0 1-3-3l6.9-6.9a6 6 0 0 1 8-8l-3.8 3.8z"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
    "archive": '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9"/><path d="M10 13h4"/>',
    "scan": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/><path d="M8 11h6M11 8v6"/>',
    "check-square": '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="m8 12 3 3 5-6"/>',
    "file": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6z"/><path d="M14 3v6h6"/><path d="M8 13h8M8 17h6"/>',
    "flame": '<path d="M12 22c4.4 0 7-2.9 7-7 0-3.5-2.5-5.5-3.5-7.5-.5 1.5-1.5 2.5-2.5 3-0.3-2.5-1.5-5-4-7-.5 4-4 6-4 11 0 4.1 2.6 7.5 7 7.5z"/>',
    "power": '<path d="M12 3v9"/><path d="M6.3 7.3a8 8 0 1 0 11.4 0"/>',
    "send": '<path d="M22 2 11 13"/><path d="m22 2-7 20-4-9-9-4 20-7z"/>',
    "sparkle": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z"/><path d="M19 17l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2z"/>',
    "arrow": '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
    "alert": '<path d="M12 3 2 20h20L12 3z"/><path d="M12 10v4M12 17h.01"/>',
    "copy": '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
    "x-circle": '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/>',
    "hourglass": '<path d="M6 3h12M6 21h12"/><path d="M8 3v4l4 5 4-5V3M8 21v-4l4-5 4 5v4"/>',
}
ARCHETYPE_ICON = {
    "decision": "scale", "verify": "check-circle", "blocker": "lock", "patch": "wrench",
    "thread": "link", "recover": "archive", "sweep": "scan",
}


def _archetype_of(title: str) -> str:
    for prefix, key in ARCHETYPE_PREFIXES:
        if title.startswith(prefix):
            return key
    return DEFAULT_ARCHETYPE


_CJK = re.compile(r"[぀-ヿ㐀-鿿豈-﫿]")


# Only these spellings select the Chinese dictionary. "Any CJK character" was the
# first draft, and it handed a Japanese user (日本語 is written in Han characters) a
# Chinese page. Everything that is not explicitly Chinese or auto falls to English.
CHINESE_NAMES = {"zh", "zh-cn", "zh-tw", "zh-hans", "zh-hant", "chinese", "中文", "汉语", "漢語",
                 "简体中文", "繁體中文", "繁体中文", "华语", "華語", "普通话", "國語"}


def _chrome_language(requested: str, sample_text: str) -> str:
    lowered = (requested or "auto").strip().lower()
    if lowered in CHINESE_NAMES:
        return "zh"
    if lowered not in {"auto", "source", ""}:
        return "en"
    relevant = [ch for ch in sample_text if ch.isalpha() or _CJK.match(ch)]
    if not relevant:
        return "en"
    ratio = sum(1 for ch in relevant if _CJK.match(ch)) / len(relevant)
    return "zh" if ratio > 0.2 else "en"


CHROME: dict[str, dict[str, Any]] = {
    "en": {
        "doc_title": "Burn Before Reset · Report",
        "headline": "While you were away, your quota became these things.",
        "oracle_label": "The closing word",
        "why_archetype": "For a run that mostly delivered {name} — {hint}",
        "why_fault": "For a run that hit a snag — the ledger says why, and nothing finished was lost",
        "why_fault_empty": "For a run that hit a snag before it could deliver — the ledger says why",
        "why_empty": "For a run that chose to stop rather than burn your quota through uncertainty",
        "facts": {"completed": "Tasks completed", "artifacts": "Artifacts", "spent": "Burned",
                  "tokens": "Tokens out", "hours": "Hours", "stop": "How it stopped"},
        "sections": {
            "first": ("Start here", "Grouped by the kind of work. Decisions come first."),
            "work": ("The work", "Every artifact, with where it came from. Queue any of them for your agent."),
            "watch": ("The watch", "How the run spent its time, minute by minute."),
            "ledger": ("Safety & ledger", "What the run promised not to do, and the receipts."),
        },
        "attention_empty": "Nothing needs a decision. Read at leisure.",
        "archetype": {
            "decision": ("decisions framed", "the evidence is laid out; they only need your call"),
            "verify": ("claims verified", "confirmed, refuted, or uncheckable — read the verdicts"),
            "blocker": ("blockers analysed", "what needs a person, and what only needs work"),
            "patch": ("patch plans", "reviewable plans for uncommitted work; review before touching the repo"),
            "thread": ("threads recovered", "where the work stopped, and the next executable step"),
            "recover": ("work recovered", "unfinished work inventoried and made resumable"),
            "sweep": ("project sweeps", "whole-project audits: what nobody wrote down"),
        },
        "first_action": "First: {n} {name} — {hint}",
        "exc_failed": "Failed {n}",
        "exc_waits": "allowance closed {n} time(s) mid-run",
        "handoff_add": "Queue for my agent",
        "handoff_added": "Queued for my agent",
        "handoff_copy": "Copy handoff brief",
        "grade_label": "Worth the quota?",
        "grades": {"worth": "worth it", "low": "low value", "wrong": "wrong pick"},
        "grade_note": "a note for your agent, if you have one",
        "feedback_copy": "Copy feedback",
        "copied": "Copied",
        "queued_n": "queued",
        "filter_all_projects": "All projects",
        "filter_all_kinds": "All kinds",
        "prov": {"project": "project", "source": "picked from", "signals": "signals",
                 "modified": "source last changed", "artifact": "artifact"},
        "truncated": "Truncated to keep this page openable — the full text is in the file above.",
        "failed_title": "Failed or stopped tasks",
        "watch": {
            "run.started": "Run started", "round.planned": "New round planned",
            "round.nothing_left": "Nothing new found — honest end", "round.plan_failed": "Re-planning failed",
            "task.completed": "Done", "task.failed": "Failed",
            "quota.waiting": "Allowance closed · waiting", "run.stopped": "Stopped",
        },
        "strip_start": "start", "strip_stop": "stop", "strip_wait": "allowance closed",
        "ledger": {
            "attributed": "Source writes attributed to the Worker",
            "billing": "Billing or auth error",
            "guard": "Deadline-guard failure",
            "unconfirmed": "Process-group stop unconfirmed",
            "incomplete": "Source check incomplete",
            "reused": "Skipped — already answered by an earlier run",
            "reused_note": "named in RUN_PLAN.md",
            "moved": "Allowlisted files that moved during the run",
            "moved_note": "The Worker held no tool that writes, so it cannot be the cause; something else on this machine touched these. Worth a glance, not an alarm.",
            "moved_note_writable": "This Worker could write, so these are attributed to it and the run stopped. Treat as a boundary violation until each is explained.",
            "worker_errors": "Errors reported by the Worker",
            "priced": "Priced calls",
            "yes": "yes", "no": "no",
        },
        "foot": "Generated by Burn Before Reset — machine-readable twin: MORNING_REPORT.md · receipts: RUN_STATE.json, events.jsonl",
        "handoff_header": "These artifacts came out of a Burn Before Reset run. Read each file, then continue the work it proposes:",
        "handoff_field_file": "file", "handoff_field_from": "from", "handoff_field_note": "note",
        "feedback_header": "BBR artifact grades",
    },
    "zh": {
        "doc_title": "Burn Before Reset · 成果报告",
        "headline": "你不在的时候，额度变成了这些东西。",
        "oracle_label": "此行判语",
        "why_archetype": "因为这一趟的交付，以{name}为主——{hint}",
        "why_fault": "因为这一趟栽了个跟头——原因在账目里，做完的成果一份没丢",
        "why_fault_empty": "因为这一趟还没来得及交付就栽了跟头——原因在账目里",
        "why_empty": "因为这一趟宁可停下，也不在不确定里烧你的额度",
        "facts": {"completed": "完成任务", "artifacts": "产出成果", "spent": "烧掉",
                  "tokens": "输出 tokens", "hours": "用时", "stop": "停机方式"},
        "sections": {
            "first": ("先看这里", "按工作类型分组，决策排最前。"),
            "work": ("全部成果", "每一份成果和它的来路。任何一份都可以交办给你的 agent。"),
            "watch": ("值守纪事", "这一趟的时间是怎么花的，逐分钟。"),
            "ledger": ("安全与账目", "它承诺不做的事，和每一张回执。"),
        },
        "attention_empty": "没有等拍板的事，可以慢慢读。",
        "archetype": {
            "decision": ("备好的决策", "证据已摆齐，只差你一句话"),
            "verify": ("核验的主张", "confirmed / refuted / uncheckable，直接看判词"),
            "blocker": ("定性的堵点", "哪些等人、哪些只差干活，分开了"),
            "patch": ("补丁计划", "未提交工作的可审计划，审完再动仓库"),
            "thread": ("接上的断线", "停在哪、下一步怎么走，已可执行"),
            "recover": ("清点的欠账", "未完成工作已盘点，可以续做"),
            "sweep": ("全项目体检", "整个项目扫一遍：没人写下来的问题"),
        },
        "first_action": "先看：{n} 个{name}——{hint}",
        "exc_failed": "失败 {n}",
        "exc_waits": "中途额度关闭 {n} 次",
        "handoff_add": "交办给我的 agent",
        "handoff_added": "已交办给我的 agent",
        "handoff_copy": "复制交办清单",
        "grade_label": "值得这份额度吗？",
        "grades": {"worth": "值得", "low": "价值不大", "wrong": "选错了"},
        "grade_note": "给 agent 的一句备注（可空）",
        "feedback_copy": "复制评分反馈",
        "copied": "已复制",
        "queued_n": "项待交办",
        "filter_all_projects": "全部项目",
        "filter_all_kinds": "全部类型",
        "prov": {"project": "项目", "source": "线索来自", "signals": "信号",
                 "modified": "源最后改动", "artifact": "产物文件"},
        "truncated": "为保证页面可打开已截断——全文在上面的文件里。",
        "failed_title": "失败或中止的任务",
        "watch": {
            "run.started": "开跑", "round.planned": "新一轮规划",
            "round.nothing_left": "没有新发现——诚实收尾", "round.plan_failed": "重规划失败",
            "task.completed": "完成", "task.failed": "失败",
            "quota.waiting": "额度窗口关闭 · 等待", "run.stopped": "停机",
        },
        "strip_start": "开始", "strip_stop": "停机", "strip_wait": "额度关闭",
        "ledger": {
            "attributed": "归因给 Worker 的源写入",
            "billing": "计费 / 认证异常",
            "guard": "deadline guard 故障",
            "unconfirmed": "进程组停止未确认",
            "incomplete": "源检查未完成",
            "reused": "已答任务跳过（前序 run 已完成）",
            "reused_note": "名单见 RUN_PLAN.md",
            "moved": "运行期间动过的白名单文件",
            "moved_note": "Worker 没有任何写工具，不可能是原因；是这台机器上别的进程动了它们。值得扫一眼，不必报警。",
            "moved_note_writable": "本次 Worker 有写权限，变动归因于它，运行已停。逐条解释清楚之前按越界处理。",
            "worker_errors": "Worker 报告的错误",
            "priced": "计价调用",
            "yes": "有", "no": "无",
        },
        "foot": "由 Burn Before Reset 生成 — 机器可读版：MORNING_REPORT.md · 回执：RUN_STATE.json、events.jsonl",
        "handoff_header": "以下成果来自一次 Burn Before Reset 运行。请逐项读取文件，继续推进它提出的工作：",
        "handoff_field_file": "文件", "handoff_field_from": "来源", "handoff_field_note": "备注",
        "feedback_header": "BBR 成果评分",
    },
}


# ---------------------------------------------------------------------------
# Markdown subset renderer. Every piece of inline text passes through
# html.escape; nothing from an artifact reaches the page as markup.
# ---------------------------------------------------------------------------
def _inline(text: str) -> str:
    out = html.escape(text)
    spans: list[str] = []

    def stash(match: re.Match[str]) -> str:
        spans.append(match.group(1))
        return f"\x00{len(spans) - 1}\x00"

    out = re.sub(r"`([^`]+)`", stash, out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", out)
    for index, span in enumerate(spans):
        out = out.replace(f"\x00{index}\x00", f"<code>{span}</code>")
    return out


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def render_markdown(source: str) -> str:
    lines = source.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    index = 0
    list_stack: list[str] = []

    def close_lists(depth: int = 0) -> None:
        while len(list_stack) > depth:
            out.append(f"</{list_stack.pop()}>")

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            close_lists()
            index += 1
            body: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                body.append(lines[index])
                index += 1
            index += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(body))}</code></pre>")
            continue
        if not stripped:
            close_lists()
            index += 1
            continue
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            close_lists()
            out.append("<hr>")
            index += 1
            continue
        heading = re.match(r"(#{1,6})\s+(.*)", stripped)
        if heading:
            close_lists()
            level = min(len(heading.group(1)) + 1, 6)
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            index += 1
            continue
        if (
            stripped.startswith("|")
            and index + 1 < len(lines)
            and re.fullmatch(r"\|[\s:|-]+\|", lines[index + 1].strip())
        ):
            close_lists()
            header = _split_row(stripped)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(_split_row(lines[index].strip()))
                index += 1
            head = "".join(f"<th>{_inline(cell)}</th>" for cell in header)
            body_rows = "".join(
                "<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in row) + "</tr>" for row in rows
            )
            out.append(
                '<div class="tablewrap"><table><thead><tr>' + head + "</tr></thead><tbody>"
                + body_rows + "</tbody></table></div>"
            )
            continue
        if stripped.startswith(">"):
            close_lists()
            quote: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip().lstrip(">").strip())
                index += 1
            out.append(f"<blockquote>{_inline(' '.join(quote))}</blockquote>")
            continue
        bullet = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)", line)
        if bullet:
            indent = len(bullet.group(1)) // 2 + 1
            kind = "ul" if bullet.group(2) in "-*+" else "ol"
            while len(list_stack) > indent:
                out.append(f"</{list_stack.pop()}>")
            while len(list_stack) < indent:
                out.append(f"<{kind}>")
                list_stack.append(kind)
            out.append(f"<li>{_inline(bullet.group(3))}</li>")
            index += 1
            continue
        close_lists()
        paragraph = [stripped]
        index += 1
        while index < len(lines) and lines[index].strip() and not re.match(
            r"^\s*([-*+]|\d+[.)]|#{1,6}\s|>|\||```)", lines[index]
        ):
            paragraph.append(lines[index].strip())
            index += 1
        out.append(f"<p>{_inline(' '.join(paragraph))}</p>")
    close_lists()
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Data assembly
# ---------------------------------------------------------------------------
def _merged_tasks(run_dir: Path) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    for queue_path in [run_dir / "QUEUE.json", *sorted(run_dir.glob("QUEUE-r*.json"))]:
        queue = read_json(queue_path)
        if not isinstance(queue, dict):
            continue
        for task in queue.get("tasks", []):
            if isinstance(task, dict) and isinstance(task.get("id"), str):
                tasks[task["id"]] = task
    return tasks


def _project_of(task: dict[str, Any]) -> str:
    refs = task.get("source_refs") or [{}]
    root = str(refs[0].get("root", "")) if isinstance(refs[0], dict) else ""
    return Path(root).name if root else "—"


def _collect_artifacts(run_dir: Path, state: dict[str, Any], tasks: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    budget = MAX_EMBED_BYTES
    for task_id in sorted(state.get("completed") or []):
        task = tasks.get(task_id)
        if not task:
            continue
        deliverables = task.get("deliverables") or []
        path = run_dir / str(deliverables[0]) if deliverables else None
        text = ""
        truncated = False
        if path is not None:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
        encoded = len(text.encode("utf-8"))
        if encoded > budget:
            text = text.encode("utf-8")[: max(budget, 0)].decode("utf-8", errors="ignore")
            truncated = True
        budget -= min(encoded, MAX_EMBED_BYTES)
        refs = task.get("source_refs") or [{}]
        ref = refs[0] if isinstance(refs[0], dict) else {}
        title = str(task.get("title", task_id))
        items.append(
            {
                "id": task_id, "title": title, "short": title.split(": ", 1)[-1],
                "archetype": _archetype_of(title), "project": _project_of(task),
                "root": str(ref.get("root", "")), "source": str(ref.get("path", "")),
                "signals": sorted({s for r in refs if isinstance(r, dict) for s in (r.get("signals") or [])}),
                "modified": str(ref.get("modified_at", ""))[:16].replace("T", " "),
                "path": str(path) if path else "",
                "kb": max(1, round(encoded / 1024)) if text else 0,
                "truncated": truncated,
                "body": render_markdown(text) if text else "<p>—</p>",
                "raw_text": text,
            }
        )
    return items


def _parse_stamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _read_events(run_dir: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        lines = (run_dir / "events.jsonl").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return events
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


# ---------------------------------------------------------------------------
# Visual system. Surfaces and ink from a validated reference palette; one brand
# accent (ember orange); categorical hues for the kinds of work validated for
# CVD separation in both modes (yellow/aqua/magenta sit below 3:1 on light and
# therefore always ship with a text label); status colours reserved for safety.
# ---------------------------------------------------------------------------
CSS = """
:root {
  --page:#f9f9f7; --card:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --hair:#e1e0d9; --ring:rgba(11,11,11,.10); --wash:#f0efec;
  --brand:#eb6834; --brand-ink:#c4501f; --brand-soft:rgba(235,104,52,.13);
  --good:#006300; --good-soft:rgba(12,163,12,.12); --warn:#b97a00; --warn-soft:rgba(250,178,25,.16);
  --crit:#d03b3b; --crit-soft:rgba(208,59,59,.12); --calm:#2a78d6; --calm-soft:rgba(42,120,214,.12);
  --c-decision:#2a78d6; --c-verify:#1baf7a; --c-blocker:#eda100; --c-patch:#4a3aa7;
  --c-thread:#e87ba4; --c-sweep:#008300; --c-recover:#898781;
  --dark:#141413; --dark-2:#232321; --on-dark:#f5f5f2;
  --shadow:0 1px 2px rgba(11,11,11,.05), 0 1px 1px rgba(11,11,11,.03);
}
@media (prefers-color-scheme: dark) {
  :root {
    --page:#0d0d0d; --card:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
    --hair:#2c2c2a; --ring:rgba(255,255,255,.10); --wash:#222220;
    --brand:#d95926; --brand-ink:#f08a5c; --brand-soft:rgba(217,89,38,.20);
    --good:#0ca30c; --good-soft:rgba(12,163,12,.18); --warn:#fab219; --warn-soft:rgba(250,178,25,.18);
    --crit:#e66767; --crit-soft:rgba(230,103,103,.18); --calm:#3987e5; --calm-soft:rgba(57,135,229,.18);
    --c-decision:#3987e5; --c-verify:#199e70; --c-blocker:#c98500; --c-patch:#9085e9;
    --c-thread:#d55181; --c-sweep:#008300; --c-recover:#898781;
    --dark:#222220; --dark-2:#2c2c2a; --on-dark:#ffffff;
    --shadow:none;
  }
}
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
@media (prefers-reduced-motion:reduce) { html { scroll-behavior:auto; } }
body { margin:0; background:var(--page); color:var(--ink);
  font:15px/1.65 system-ui,-apple-system,"PingFang SC","Segoe UI",sans-serif; }
code,pre { font-family:ui-monospace,"SF Mono",SFMono-Regular,Menlo,monospace; }
button { font:inherit; color:inherit; }
:focus-visible { outline:2px solid var(--brand); outline-offset:2px; }
svg { flex:none; }

/* ---- header ---- */
.band { background:var(--dark); color:var(--on-dark); border-bottom:3px solid var(--brand); }
.band-in { max-width:1080px; margin:0 auto; padding:16px 28px;
  display:flex; justify-content:space-between; align-items:center; }
.brand { display:flex; align-items:center; gap:10px; font-weight:800; letter-spacing:.14em;
  font-size:13px; white-space:nowrap; }
.brand .mark { width:22px; height:22px; border-radius:6px; background:var(--brand);
  display:grid; place-items:center; color:#fff; }
.runid { font-family:ui-monospace,Menlo,monospace; font-size:11px; opacity:.6;
  border:1px solid rgba(255,255,255,.18); border-radius:6px; padding:3px 8px; }

.wrap { max-width:1080px; margin:0 auto; padding:0 28px 140px; }
.headline { font-size:26px; line-height:1.35; font-weight:800; letter-spacing:-.01em;
  margin:36px 0 22px; max-width:820px; }

/* ---- the closing word ---- */
.oracle { position:relative; border-radius:16px; padding:36px 40px 32px 46px;
  background:var(--dark); color:var(--on-dark); overflow:hidden; box-shadow:var(--shadow); }
.oracle::before { content:""; position:absolute; left:0; top:0; bottom:0; width:6px; background:var(--brand); }
.oracle.bad::before { background:var(--crit); }
.oracle.calm::before { background:var(--calm); }
.oracle .label { display:flex; align-items:center; gap:8px; font-size:11.5px; letter-spacing:.14em;
  text-transform:uppercase; font-weight:700; opacity:.7; margin-bottom:16px; }
.oracle .label svg { color:var(--brand); }
.oracle.bad .label svg { color:var(--crit); } .oracle.calm .label svg { color:var(--calm); }
.oracle .zh { font-family:"Songti SC","Noto Serif SC",Georgia,serif; font-size:40px; line-height:1.3;
  font-weight:700; letter-spacing:.03em; margin:0; }
.oracle .en { font-family:Georgia,"Iowan Old Style",serif; font-size:36px; line-height:1.25;
  font-weight:600; font-style:italic; margin:0; }
.oracle .echo { margin-top:10px; font-family:Georgia,serif; font-style:italic; font-size:15px; opacity:.55; }
.oracle .why { margin-top:22px; font-size:13.5px; opacity:.85; display:flex; align-items:center; gap:10px; }
.oracle .why::before { content:""; width:24px; height:2px; background:var(--brand); flex:none; border-radius:2px; }
.oracle.bad .why::before { background:var(--crit); } .oracle.calm .why::before { background:var(--calm); }

/* ---- tiles ---- */
.tile { background:var(--card); border:1px solid var(--ring); border-radius:12px; box-shadow:var(--shadow); }
.comp { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin-top:14px; }
.comp .c { display:flex; align-items:center; gap:12px; padding:12px 14px; --h:var(--muted); }
.comp .c .ico { width:36px; height:36px; border-radius:10px; display:grid; place-items:center;
  color:var(--h); background:color-mix(in srgb, var(--h) 13%, var(--card)); }
.comp .c b { display:block; font-size:22px; line-height:1.1; font-weight:800; }
.comp .c span { font-size:12px; color:var(--ink2); font-weight:600; }
.comp .c.hero { border:2px solid var(--h); background:color-mix(in srgb, var(--h) 7%, var(--card)); }
.comp .c.hero .badge { margin-left:auto; font-size:10px; font-weight:800; letter-spacing:.08em;
  color:#fff; background:var(--h); border-radius:5px; padding:3px 6px; }

.facts { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin-top:10px; }
.fact { padding:14px 16px 12px; }
.fact .ico { color:var(--muted); margin-bottom:8px; display:flex; }
.fact b { display:block; font-size:24px; line-height:1.15; font-weight:800; }
.fact span { font-size:11.5px; color:var(--ink2); }
.fact.word b { font-size:20px; padding-top:2px; }
.fact.word.good b, .fact.word.good .ico { color:var(--good); }
.fact.word.warn b, .fact.word.warn .ico { color:var(--warn); }
.fact.word.bad b, .fact.word.bad .ico { color:var(--crit); }
.fact code { font-size:10px; color:var(--muted); }

.fline { display:flex; align-items:center; gap:12px; margin-top:10px; padding:11px 14px; font-size:14px; }
.fline .ico { width:30px; height:30px; border-radius:8px; display:grid; place-items:center; flex:none;
  color:var(--brand-ink); background:var(--brand-soft); }
.fline.warn .ico { color:var(--crit); background:var(--crit-soft); }
.fline b { color:var(--brand-ink); }

/* ---- section headers ---- */
section { margin-top:64px; }
.sh { display:flex; align-items:center; gap:14px; margin-bottom:18px; }
.sh .ico { width:40px; height:40px; border-radius:11px; display:grid; place-items:center;
  color:var(--brand-ink); background:var(--brand-soft); }
.sh h2 { font-size:18px; margin:0; line-height:1.2; letter-spacing:-.01em; }
.sh p { margin:3px 0 0; font-size:13px; color:var(--ink2); }

/* ---- start here ---- */
.fgroup { display:grid; grid-template-columns:40px 1fr; gap:0 14px; padding:16px 18px; margin-bottom:10px; --h:var(--muted); }
.fgroup .ico { width:40px; height:40px; border-radius:11px; display:grid; place-items:center;
  color:var(--h); background:color-mix(in srgb, var(--h) 13%, var(--card)); }
.fgroup-head { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }
.fgroup-head .n { font-size:20px; font-weight:800; color:var(--h); }
.fgroup-head .name { font-size:15px; font-weight:700; }
.fgroup-head .hint { color:var(--ink2); font-size:12.5px; }
.chips { display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; grid-column:2; }
.chip { display:inline-flex; align-items:center; gap:6px; font-size:12.5px; padding:6px 11px; border-radius:8px;
  cursor:pointer; border:1px solid var(--hair); background:var(--page); color:var(--ink); text-align:left; }
.chip:hover { border-color:var(--brand); color:var(--brand-ink); }
.chip .cp { color:var(--muted); }
.first-empty { color:var(--ink2); font-size:14px; }

/* ---- browser ---- */
.browser { display:grid; grid-template-columns:330px minmax(0,1fr); gap:24px; align-items:start; }
@media (max-width:900px){ .browser { grid-template-columns:1fr; } .side { position:static !important; max-height:none !important; } }
.side { position:sticky; top:16px; max-height:calc(100vh - 32px); overflow-y:auto; padding:8px; }
.tools { display:flex; gap:7px; flex-wrap:wrap; margin:4px 4px 10px; }
.tools select { font:inherit; font-size:12px; padding:7px 9px; border:1px solid var(--hair);
  border-radius:8px; background:var(--card); color:var(--ink); flex:1 1 44%; min-width:0; }
.card { display:block; width:100%; text-align:left; background:transparent; cursor:pointer;
  border:1px solid transparent; border-radius:10px; padding:10px 10px; --h:var(--muted); }
.card:hover { background:var(--wash); }
.card.on { background:var(--wash); border-color:var(--ring); }
.card-top { display:flex; align-items:center; gap:8px; }
.card-top .k { display:inline-flex; align-items:center; gap:5px; font-size:10.5px; font-weight:700;
  letter-spacing:.04em; color:var(--h); }
.marks { margin-left:auto; display:flex; gap:6px; align-items:center; }
.qmark { display:none; color:var(--brand-ink); }
.qmark.on { display:inline-flex; }
.grade-dot { width:7px; height:7px; border-radius:50%; }
.grade-dot.worth { background:var(--good); } .grade-dot.low { background:var(--warn); } .grade-dot.wrong { background:var(--crit); }
.card-title { font-weight:650; font-size:13px; margin:5px 0 3px; line-height:1.45; }
.card-meta { font-size:11px; color:var(--muted); }

.reader { min-width:0; padding:26px 30px; }
.pane { display:none; }
.pane.on { display:block; }
.pane-head { padding-bottom:18px; margin-bottom:22px; border-bottom:1px solid var(--hair); --h:var(--muted); }
.pane-kind { display:inline-flex; align-items:center; gap:7px; font-size:11.5px; font-weight:700;
  color:var(--h); background:color-mix(in srgb, var(--h) 12%, var(--card)); border-radius:7px; padding:5px 10px; }
.pane-head h3 { font-size:21px; line-height:1.4; margin:12px 0 12px; font-weight:750; letter-spacing:-.01em; }
.prov { display:flex; flex-wrap:wrap; gap:6px 22px; margin:0 0 18px; padding:0; }
.prov div { min-width:0; font-size:12px; }
.prov dt { display:inline; color:var(--muted); }
.prov dt::after { content:" · "; color:var(--hair); }
.prov dd { display:inline; margin:0; word-break:break-all; }
.prov code { background:var(--wash); padding:1px 5px; border-radius:4px; font-size:11px; }

.actions { display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
.act-queue { display:inline-flex; align-items:center; gap:9px; font-size:14px; font-weight:800;
  padding:11px 20px; border-radius:10px; cursor:pointer; border:2px solid var(--brand);
  background:var(--brand); color:#fff; box-shadow:0 2px 8px rgba(235,104,52,.35); }
.act-queue:hover { filter:brightness(1.06); }
.act-queue.on { background:var(--good-soft); border-color:var(--good); color:var(--good); box-shadow:none; }
.gnote { flex:1; min-width:180px; font-size:13px; padding:9px 12px; border:1px solid var(--hair);
  border-radius:9px; background:var(--card); color:var(--ink); }
.gnote:focus { outline:none; border-color:var(--brand); }
.gline { margin-top:12px; display:flex; gap:4px; align-items:center; font-size:11.5px; color:var(--muted); }
.g { border:none; background:transparent; cursor:pointer; font-size:11.5px; color:var(--muted); padding:3px 7px; border-radius:5px; }
.g:hover { color:var(--ink); background:var(--wash); }
.g.w.on { color:var(--good); font-weight:700; } .g.l.on { color:var(--warn); font-weight:700; } .g.x.on { color:var(--crit); font-weight:700; }
.truncnote { border-left:3px solid var(--warn); padding:6px 14px; margin:0 0 18px; font-size:12.5px; color:var(--ink2); }

.md h2 { font-size:18px; margin:30px 0 8px; }
.md h3 { font-size:15.5px; margin:24px 0 7px; }
.md h4,.md h5,.md h6 { font-size:13.5px; margin:18px 0 6px; color:var(--ink2); }
.md p { margin:10px 0; } .md li { margin:4px 0; }
.md code { background:var(--wash); padding:1.5px 5px; border-radius:4px; font-size:12.5px; }
.md pre { background:var(--wash); padding:13px 16px; border-radius:8px; overflow-x:auto; }
.md pre code { background:none; padding:0; font-size:12.5px; line-height:1.55; }
.md blockquote { margin:12px 0; padding:2px 0 2px 14px; border-left:3px solid var(--brand); color:var(--ink2); }
.md hr { border:0; border-top:1px solid var(--hair); margin:26px 0; }
.tablewrap { overflow-x:auto; margin:14px 0; }
.md table { border-collapse:collapse; font-size:12.5px; min-width:100%; }
.md th,.md td { border:1px solid var(--hair); padding:6px 10px; text-align:left; vertical-align:top; }
.md th { background:var(--wash); font-weight:600; }

/* ---- watch ---- */
.watchbox { padding:22px 24px; }
.strip { margin:0 0 22px; }
.strip-track { position:relative; height:14px; border-radius:4px; background:var(--wash); overflow:hidden; }
.seg { position:absolute; top:0; bottom:0; }
.seg.done { background:var(--brand); border-right:2px solid var(--card); }
.seg.fail { background:var(--crit); border-right:2px solid var(--card); }
.seg.wait { width:3px; background:var(--card); box-shadow:0 0 0 1px var(--card); }
.strip-cap { position:absolute; right:0; top:0; bottom:0; width:3px; background:var(--ink); }
.strip-axis { display:flex; justify-content:space-between; margin-top:6px;
  font:11px/1 ui-monospace,Menlo,monospace; color:var(--muted); }
.rail { display:grid; gap:0; }
.tick { display:grid; grid-template-columns:48px 20px 1fr; gap:0 10px; align-items:center; padding:6px 0; }
.tick .clock { font:11.5px/1.6 ui-monospace,Menlo,monospace; color:var(--muted); text-align:right; }
.tick .dot { width:20px; height:20px; border-radius:50%; display:grid; place-items:center;
  color:var(--muted); background:var(--wash); }
.tick.completed .dot { color:var(--good); background:var(--good-soft); }
.tick.failed .dot { color:var(--crit); background:var(--crit-soft); }
.tick.waiting .dot { color:var(--warn); background:var(--warn-soft); }
.tick.stopped .dot { color:var(--brand-ink); background:var(--brand-soft); }
.tick .what { font-size:13px; }
.tick .detail { color:var(--muted); font-size:11.5px; font-family:ui-monospace,Menlo,monospace; margin-left:10px; }

/* ---- ledger ---- */
.ledger { padding:6px 22px; }
.lrow { display:flex; align-items:center; gap:12px; padding:11px 0; border-bottom:1px solid var(--hair); font-size:13.5px; }
.lrow:last-child { border-bottom:none; }
.lrow .st { width:22px; height:22px; border-radius:50%; display:grid; place-items:center; flex:none; }
.lrow .st.ok { color:var(--good); background:var(--good-soft); }
.lrow .st.hot { color:var(--crit); background:var(--crit-soft); }
.lrow .st.info { color:var(--calm); background:var(--calm-soft); }
.lrow .k { color:var(--ink2); flex:1; }
.lrow .v { font-weight:700; }
.lrow .v.ok { color:var(--good); } .lrow .v.hot { color:var(--crit); }
.lsub { margin:16px 0 0; padding:16px 22px; }
.lsub h3 { font-size:14px; margin:0 0 4px; }
.lsub .subnote { color:var(--ink2); font-size:12.5px; margin:2px 0 8px; }
.pathlist { margin:4px 0 0; padding-left:18px; font-size:12.5px; }
.pathlist code { background:var(--wash); padding:1px 5px; border-radius:4px; font-size:11.5px; }

.foot { margin-top:80px; color:var(--muted); font-size:11.5px; border-top:1px solid var(--hair); padding-top:16px; }

/* ---- action bar ---- */
.bar { position:fixed; right:22px; bottom:22px; z-index:30; display:flex; gap:10px; align-items:center;
  background:var(--card); border:1px solid var(--ring); border-radius:14px; padding:10px 12px 10px 16px;
  box-shadow:0 10px 34px rgba(0,0,0,.18); }
.bar .n { display:flex; align-items:center; gap:8px; font-size:13px; color:var(--ink2); font-weight:600; }
.bar .n .cnt { min-width:24px; height:24px; padding:0 7px; border-radius:12px; display:grid; place-items:center;
  background:var(--brand); color:#fff; font-weight:800; font-size:12px; }
.bar .primary { display:inline-flex; align-items:center; gap:8px; font-size:13.5px; font-weight:800;
  padding:10px 16px; border-radius:10px; cursor:pointer; border:none; background:var(--brand); color:#fff; }
.bar .primary:hover { filter:brightness(1.06); }
.bar .ghost { display:inline-flex; align-items:center; gap:7px; font-size:12.5px; padding:9px 12px; border-radius:10px;
  cursor:pointer; border:1px solid var(--hair); background:transparent; color:var(--ink2); }
.bar .ghost:hover { color:var(--ink); border-color:var(--muted); }
"""

JS = """
const DATA = JSON.parse(document.getElementById('bbr-data').textContent);
const GKEY = 'bbr-grades-' + DATA.run_id;
const QKEY = 'bbr-queue-' + DATA.run_id;
let grades = {}, queue = {};
try { grades = JSON.parse(localStorage.getItem(GKEY) || '{}'); } catch (e) { grades = {}; }
try { queue = JSON.parse(localStorage.getItem(QKEY) || '{}'); } catch (e) { queue = {}; }
const cards = [...document.querySelectorAll('.card')];
const panes = [...document.querySelectorAll('.pane')];

function persist() {
  try { localStorage.setItem(GKEY, JSON.stringify(grades)); } catch (e) {}
  try { localStorage.setItem(QKEY, JSON.stringify(queue)); } catch (e) {}
  document.getElementById('qn').textContent = Object.values(queue).filter(Boolean).length;
  document.getElementById('gn').textContent = Object.values(grades).filter(v => v && v.g).length;
}
function paint(id) {
  const g = grades[id] || {};
  const dot = document.querySelector('[data-dot="' + id + '"]');
  if (dot) dot.className = 'grade-dot' + (g.g ? ' ' + g.g : '');
  const qm = document.querySelector('[data-qmark="' + id + '"]');
  if (qm) qm.classList.toggle('on', !!queue[id]);
  document.querySelectorAll('[data-queue="' + id + '"]').forEach(b => {
    b.classList.toggle('on', !!queue[id]);
    b.querySelector('.t').textContent = queue[id] ? DATA.t.handoff_added : DATA.t.handoff_add;
  });
  document.querySelectorAll('.gline[data-id="' + id + '"] .g').forEach(b => {
    b.classList.toggle('on', b.dataset.g === g.g);
  });
  const note = document.querySelector('.gnote[data-id="' + id + '"]');
  if (note && g.note !== undefined && note.value !== g.note) note.value = g.note;
}
function show(id, scroll) {
  cards.forEach(c => c.classList.toggle('on', c.dataset.id === id));
  panes.forEach(p => p.classList.toggle('on', p.id === 'pane-' + id));
  if (scroll) document.getElementById('work').scrollIntoView({behavior:'smooth', block:'start'});
}
cards.forEach(c => c.addEventListener('click', () => show(c.dataset.id, false)));
document.querySelectorAll('.chip').forEach(ch => ch.addEventListener('click', () => show(ch.dataset.id, true)));
document.querySelectorAll('[data-queue]').forEach(b => b.addEventListener('click', () => {
  const id = b.dataset.queue; queue[id] = !queue[id]; paint(id); persist();
}));
document.querySelectorAll('.gline .g').forEach(btn => btn.addEventListener('click', () => {
  const id = btn.closest('.gline').dataset.id;
  grades[id] = grades[id] || {};
  grades[id].g = grades[id].g === btn.dataset.g ? null : btn.dataset.g;
  paint(id); persist();
}));
document.querySelectorAll('.gnote').forEach(inp => inp.addEventListener('input', () => {
  const id = inp.dataset.id; grades[id] = grades[id] || {}; grades[id].note = inp.value; persist();
}));
function applyFilter() {
  const p = document.getElementById('fproj').value, k = document.getElementById('fkind').value;
  cards.forEach(c => { c.style.display = ((!p || c.dataset.project === p) && (!k || c.dataset.kind === k)) ? '' : 'none'; });
}
document.getElementById('fproj').addEventListener('change', applyFilter);
document.getElementById('fkind').addEventListener('change', applyFilter);
async function toClipboard(text, btn) {
  try { await navigator.clipboard.writeText(text); }
  catch (e) { const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); }
  const old = btn.innerHTML; btn.textContent = DATA.t.copied;
  setTimeout(() => { btn.innerHTML = old; }, 2400);
}
document.getElementById('copy-handoff').addEventListener('click', e => {
  const chosen = DATA.items.filter(m => queue[m.id]);
  const lines = [DATA.t.handoff_header, ''];
  chosen.forEach((m, i) => {
    lines.push((i + 1) + '. ' + m.title);
    lines.push('   ' + DATA.t.handoff_field_file + ': ' + m.path);
    if (m.source) lines.push('   ' + DATA.t.handoff_field_from + ': ' + m.root + '/' + m.source);
    const note = (grades[m.id] || {}).note;
    if (note && note.trim()) lines.push('   ' + DATA.t.handoff_field_note + ': ' + note.trim());
  });
  if (!chosen.length) lines.push('—');
  toClipboard(lines.join('\\n'), e.currentTarget);
});
document.getElementById('copy-feedback').addEventListener('click', e => {
  const lines = [DATA.t.feedback_header + ' · ' + DATA.run_id, ''];
  let n = 0;
  DATA.items.forEach(m => {
    const g = grades[m.id] || {};
    if (!g.g && !(g.note || '').trim()) return;
    n++;
    lines.push(n + '. [' + (g.g || 'ungraded') + '] ' + m.id + ' — ' + m.title);
    if ((g.note || '').trim()) lines.push('   note: ' + g.note.trim());
  });
  if (!n) lines.push('—');
  toClipboard(lines.join('\\n'), e.currentTarget);
});
DATA.items.forEach(m => paint(m.id));
persist();
if (cards.length) show(cards[0].dataset.id, false);
"""


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _ico(name: str, size: int = 18) -> str:
    return _svg(ICON[name], size)


def _hue(archetype: str) -> str:
    return f"--h:var(--c-{archetype})"


def _band(state: dict[str, Any]) -> str:
    return (
        '<div class="band"><div class="band-in">'
        f'<span class="brand"><span class="mark">{_ico("flame", 14)}</span>BURN&nbsp;BEFORE&nbsp;RESET</span>'
        f'<span class="runid">{_esc(state.get("run_id", ""))}</span>'
        "</div></div>"
    )


def _section_head(key: str, icon: str, chrome: dict[str, Any]) -> str:
    title, sub = chrome["sections"][key]
    return (
        f'<div class="sh"><span class="ico">{_ico(icon, 20)}</span>'
        f"<div><h2>{_esc(title)}</h2><p>{_esc(sub)}</p></div></div>"
    )


def _oracle_block(state: dict[str, Any], items: list[dict[str, Any]], chrome: dict[str, Any], lang: str) -> str:
    reason = str(state.get("stop_reason") or "unknown")
    tone = STOP_TONE.get(reason, DEFAULT_TONE)
    key, dominant = pick_proverb(tone, items)
    proverb = PROVERBS[key]
    if key == "fault":
        why = chrome["why_fault"] if items else chrome["why_fault_empty"]
    elif key == "empty":
        why = chrome["why_empty"]
    else:
        name, hint = chrome["archetype"][dominant]
        why = chrome["why_archetype"].format(name=name, hint=hint)
    card_tone = {"fault": "bad", "empty": "calm"}.get(key, "good")
    if lang == "zh":
        body = f'<p class="zh">{_esc(proverb["zh"])}</p><p class="echo">{_esc(proverb["en"])}</p>'
    else:
        body = f'<p class="en">{_esc(proverb["en"])}</p>'
    return (
        f'<div class="oracle {card_tone}">'
        f'<div class="label">{_ico("sparkle", 16)}{_esc(chrome["oracle_label"])}</div>'
        f"{body}<p class=\"why\">{_esc(why)}</p></div>"
    )


def _comp_block(items: list[dict[str, Any]], chrome: dict[str, Any]) -> str:
    if not items:
        return ""
    counts: dict[str, int] = {}
    for item in items:
        counts[item["archetype"]] = counts.get(item["archetype"], 0) + 1
    dominant = max(counts, key=lambda k: (counts[k], -ARCHETYPE_ORDER.index(k)))
    cards = []
    for key in ARCHETYPE_ORDER:
        if key not in counts:
            continue
        name = chrome["archetype"][key][0]
        hero = key == dominant
        cards.append(
            f'<div class="tile c{" hero" if hero else ""}" style="{_hue(key)}">'
            f'<span class="ico">{_ico(ARCHETYPE_ICON[key])}</span>'
            f"<div><b>{counts[key]}</b><span>{_esc(name)}</span></div>"
            + ('<span class="badge">TOP</span>' if hero else "")
            + "</div>"
        )
    return f'<div class="comp">{"".join(cards)}</div>'


def _fact_block(state: dict[str, Any], items: list[dict[str, Any]], chrome: dict[str, Any], lang: str) -> str:
    f = chrome["facts"]
    pace = state.get("burn_pace") or {}
    burn = state.get("burn") or {}
    reason = str(state.get("stop_reason") or "unknown")
    tone = STOP_TONE.get(reason, DEFAULT_TONE)
    zh_word, en_word = STOP_WORD.get(reason, STOP_WORD_DEFAULT)
    stop_word = zh_word if lang == "zh" else en_word

    def tile(icon: str, value: str, label: str, extra_cls: str = "") -> str:
        return (
            f'<div class="tile fact{extra_cls}"><span class="ico">{_ico(icon)}</span>'
            f"<b>{value}</b><span>{_esc(label)}</span></div>"
        )

    tiles = [
        tile("check-square", str(len(state.get("completed") or [])), f["completed"]),
        tile("file", str(len(items)), f["artifacts"]),
    ]
    if burn.get("cost_known_calls"):
        tiles.append(tile("flame", f"${float(pace.get('spent_usd', 0.0)):.2f}", f["spent"]))
    elif pace.get("output_tokens"):
        tiles.append(tile("flame", f"{int(pace.get('output_tokens', 0)):,}", f["tokens"]))
    hours = float(pace.get("hours_elapsed", 0) or 0)
    if hours >= 0.1:
        tiles.append(tile("clock", f"{hours:.1f}h", f["hours"]))
    tiles.append(
        f'<div class="tile fact word {tone}"><span class="ico">{_ico("power")}</span>'
        f'<b>{_esc(stop_word)}</b><span>{_esc(f["stop"])} · <code>{_esc(reason)}</code></span></div>'
    )
    return f'<div class="facts">{"".join(tiles)}</div>'


def _fixed_lines(state: dict[str, Any], items: list[dict[str, Any]], chrome: dict[str, Any]) -> str:
    out = []
    counts: dict[str, int] = {}
    for item in items:
        counts[item["archetype"]] = counts.get(item["archetype"], 0) + 1
    for key in ARCHETYPE_ORDER:
        if key in counts:
            name, hint = chrome["archetype"][key]
            text = chrome["first_action"].format(n=counts[key], name=name, hint=hint)
            out.append(f'<div class="tile fline"><span class="ico">{_ico("arrow")}</span><span>{_esc(text)}</span></div>')
            break
    failed = len(state.get("failed") or [])
    waits = int(state.get("quota_wait_cycles", 0))
    parts = []
    if failed:
        parts.append(chrome["exc_failed"].format(n=failed))
    if waits:
        parts.append(chrome["exc_waits"].format(n=waits))
    if parts:
        out.append(
            f'<div class="tile fline warn"><span class="ico">{_ico("alert")}</span>'
            f'<span>{_esc(" · ".join(parts))}</span></div>'
        )
    return "".join(out)


def _first_section(items: list[dict[str, Any]], chrome: dict[str, Any]) -> str:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        groups.setdefault(item["archetype"], []).append(item)
    blocks: list[str] = []
    for key in ARCHETYPE_ORDER:
        members = groups.get(key)
        if not members:
            continue
        name, hint = chrome["archetype"][key]
        chips = "".join(
            f'<button class="chip" data-id="{_esc(m["id"])}">{_ico("arrow", 12)}{_esc(m["short"])}'
            f' <span class="cp">· {_esc(m["project"])}</span></button>'
            for m in members
        )
        blocks.append(
            f'<div class="tile fgroup" style="{_hue(key)}"><span class="ico">{_ico(ARCHETYPE_ICON[key], 20)}</span>'
            f'<div class="fgroup-head"><span class="n">{len(members)}</span><span class="name">{_esc(name)}</span>'
            f'<span class="hint">{_esc(hint)}</span></div>'
            f'<div class="chips">{chips}</div></div>'
        )
    body = "".join(blocks) if blocks else f'<p class="first-empty">{_esc(chrome["attention_empty"])}</p>'
    return f'<section id="first">{_section_head("first", "flag", chrome)}{body}</section>'


def _work_section(items: list[dict[str, Any]], chrome: dict[str, Any]) -> str:
    prov = chrome["prov"]
    grades = chrome["grades"]
    projects = sorted({item["project"] for item in items})
    options = "".join(f'<option value="{_esc(p)}">{_esc(p)}</option>' for p in projects)
    kinds = "".join(
        f'<option value="{key}">{_esc(chrome["archetype"][key][0])}</option>'
        for key in ARCHETYPE_ORDER if any(item["archetype"] == key for item in items)
    )
    cards: list[str] = []
    panes: list[str] = []
    for item in items:
        a = item["archetype"]
        kind_label = chrome["archetype"][a][0]
        cards.append(
            f'<button class="card" data-id="{_esc(item["id"])}" data-project="{_esc(item["project"])}" '
            f'data-kind="{a}" style="{_hue(a)}">'
            f'<div class="card-top"><span class="k">{_ico(ARCHETYPE_ICON[a], 13)}{_esc(kind_label)}</span>'
            f'<span class="marks"><span class="qmark" data-qmark="{_esc(item["id"])}">{_ico("send", 12)}</span>'
            f'<span class="grade-dot" data-dot="{_esc(item["id"])}"></span></span></div>'
            f'<div class="card-title">{_esc(item["short"])}</div>'
            f'<div class="card-meta">{_esc(item["project"])} · {item["kb"]}KB</div></button>'
        )
        signals = ", ".join(item["signals"]) or "—"
        trunc = f'<aside class="truncnote">{_esc(chrome["truncated"])}</aside>' if item["truncated"] else ""
        panes.append(
            f'<article class="pane" id="pane-{_esc(item["id"])}">'
            f'<header class="pane-head" style="{_hue(a)}">'
            f'<span class="pane-kind">{_ico(ARCHETYPE_ICON[a], 14)}{_esc(kind_label)}</span>'
            f'<h3>{_esc(item["short"])}</h3>'
            f'<dl class="prov">'
            f'<div><dt>{_esc(prov["project"])}</dt><dd>{_esc(item["project"])}</dd></div>'
            f'<div><dt>{_esc(prov["source"])}</dt><dd><code>{_esc(item["source"] or "—")}</code></dd></div>'
            f'<div><dt>{_esc(prov["signals"])}</dt><dd>{_esc(signals)}</dd></div>'
            f'<div><dt>{_esc(prov["modified"])}</dt><dd>{_esc(item["modified"] or "—")}</dd></div>'
            f'<div><dt>{_esc(prov["artifact"])}</dt><dd><code>{_esc(item["path"])}</code></dd></div>'
            f'</dl>'
            f'<div class="actions">'
            f'<button class="act-queue" data-queue="{_esc(item["id"])}">{_ico("send", 16)}<span class="t">{_esc(chrome["handoff_add"])}</span></button>'
            f'<input class="gnote" data-id="{_esc(item["id"])}" placeholder="{_esc(chrome["grade_note"])}">'
            f'</div>'
            f'<div class="gline" data-id="{_esc(item["id"])}"><span>{_esc(chrome["grade_label"])}</span>'
            f'<button class="g w" data-g="worth">{_esc(grades["worth"])}</button>'
            f'<button class="g l" data-g="low">{_esc(grades["low"])}</button>'
            f'<button class="g x" data-g="wrong">{_esc(grades["wrong"])}</button></div>'
            f'</header>{trunc}<div class="md">{item["body"]}</div></article>'
        )
    return (
        f'<section id="work">{_section_head("work", "layers", chrome)}'
        '<div class="browser"><nav class="tile side"><div class="tools">'
        f'<select id="fproj"><option value="">{_esc(chrome["filter_all_projects"])}</option>{options}</select>'
        f'<select id="fkind"><option value="">{_esc(chrome["filter_all_kinds"])}</option>{kinds}</select>'
        f'</div>{"".join(cards)}</nav>'
        f'<div class="tile reader">{"".join(panes)}</div></div></section>'
    )


def _burn_strip(events: list[dict[str, Any]], chrome: dict[str, Any]) -> str:
    stamps = [(_parse_stamp(e.get("timestamp")), e) for e in events]
    stamps = [(t, e) for t, e in stamps if t is not None]
    if len(stamps) < 2:
        return ""
    start, end = stamps[0][0], stamps[-1][0]
    total = (end - start).total_seconds()
    if total <= 0:
        return ""

    def pos(t: datetime) -> float:
        return max(0.0, min(100.0, (t - start).total_seconds() / total * 100))

    segments: list[str] = []
    open_tasks: dict[str, datetime] = {}
    waits: list[datetime] = []
    for t, e in stamps:
        etype = str(e.get("type", ""))
        task_id = str(e.get("task_id", ""))
        if etype == "task.started" and task_id:
            open_tasks[task_id] = t
        elif etype in {"task.completed", "task.failed"} and task_id in open_tasks:
            left = pos(open_tasks.pop(task_id))
            width = max(pos(t) - left, 0.35)
            cls = "seg done" if etype == "task.completed" else "seg fail"
            segments.append(f'<div class="{cls}" style="left:{left:.2f}%;width:{width:.2f}%" title="{html.escape(task_id)}"></div>')
        elif etype == "quota.waiting":
            waits.append(t)
    for t in waits:
        segments.append(f'<div class="seg wait" style="left:{pos(t):.2f}%" title="{html.escape(chrome["strip_wait"])}"></div>')
    clock = lambda t: t.strftime("%H:%M")  # noqa: E731
    return (
        '<div class="strip"><div class="strip-track">' + "".join(segments) + '<div class="strip-cap"></div></div>'
        '<div class="strip-axis">'
        f'<span>{clock(start)} {html.escape(chrome["strip_start"])}</span>'
        f'<span>{clock(end)} {html.escape(chrome["strip_stop"])}</span></div></div>'
    )


def _watch_section(events: list[dict[str, Any]], chrome: dict[str, Any]) -> str:
    labels = chrome["watch"]
    tone = {"task.completed": "completed", "task.failed": "failed", "quota.waiting": "waiting", "run.stopped": "stopped"}
    icon = {"task.completed": "check-circle", "task.failed": "x-circle", "quota.waiting": "hourglass",
            "run.stopped": "power", "run.started": "flame", "round.planned": "layers",
            "round.nothing_left": "check-circle", "round.plan_failed": "alert"}
    ticks: list[str] = []
    for event in events:
        etype = str(event.get("type", ""))
        if etype not in labels or etype == "task.started":
            continue
        stamp = str(event.get("timestamp", ""))
        clock = stamp[11:16] if len(stamp) >= 16 else ""
        detail = ""
        if etype in {"task.completed", "task.failed"}:
            detail = str(event.get("task_id", ""))
            if etype == "task.failed" and event.get("error_type"):
                detail += f" · {event.get('error_type')}"
        elif etype == "quota.waiting":
            detail = f"cycle {event.get('wait_cycle', '?')}"
        elif etype == "round.planned":
            detail = str(event.get("queue", ""))
        elif etype == "run.stopped":
            detail = str(event.get("stop_reason", ""))
        ticks.append(
            f'<div class="tick {tone.get(etype, "")}"><span class="clock">{_esc(clock)}</span>'
            f'<span class="dot">{_ico(icon.get(etype, "clock"), 12)}</span><span class="what">{_esc(labels[etype])}'
            + (f'<span class="detail">{_esc(detail)}</span>' if detail else "") + "</span></div>"
        )
    if not ticks:
        return ""
    return (
        f'<section id="watch">{_section_head("watch", "clock", chrome)}'
        f'<div class="tile watchbox">{_burn_strip(events, chrome)}<div class="rail">{"".join(ticks)}</div></div></section>'
    )


def _ledger_section(state: dict[str, Any], tasks: dict[str, dict[str, Any]], chrome: dict[str, Any]) -> str:
    led = chrome["ledger"]

    def row(key: str, bad: bool) -> str:
        st = "hot" if bad else "ok"
        return (
            f'<div class="lrow"><span class="st {st}">{_ico("x-circle" if bad else "check-circle", 13)}</span>'
            f'<span class="k">{_esc(key)}</span><span class="v {st}">{_esc(led["yes"] if bad else led["no"])}</span></div>'
        )

    rows = [
        row(led["attributed"], bool(state.get("source_mutation_detected"))),
        row(led["billing"], bool(state.get("billing_error_detected"))),
        row(led["guard"], bool(state.get("guard_failure_detected"))),
        row(led["unconfirmed"], bool(state.get("stop_unconfirmed_detected"))),
        row(led["incomplete"], bool(state.get("source_check_incomplete"))),
    ]
    reused = int(state.get("reused_from_prior_runs", 0))
    if reused:
        rows.append(
            f'<div class="lrow"><span class="st info">{_ico("archive", 13)}</span><span class="k">{_esc(led["reused"])}</span>'
            f'<span class="v">{reused} · {_esc(led["reused_note"])}</span></div>'
        )
    burn = state.get("burn") or {}
    calls = int(state.get("worker_calls", 0))
    if calls:
        rows.append(
            f'<div class="lrow"><span class="st info">{_ico("flame", 13)}</span><span class="k">{_esc(led["priced"])}</span>'
            f'<span class="v">{int(burn.get("cost_known_calls", 0))} / {calls}</span></div>'
        )
    extras: list[str] = []
    moved = state.get("source_changed_paths") or []
    if moved:
        note = led["moved_note_writable"] if state.get("source_mutation_detected") else led["moved_note"]
        paths = "".join(f"<li><code>{_esc(p)}</code></li>" for p in moved)
        extras.append(f'<div class="tile lsub"><h3>{_esc(led["moved"])}</h3><p class="subnote">{_esc(note)}</p><ul class="pathlist">{paths}</ul></div>')
    errors = state.get("worker_errors") or []
    if errors:
        rows_html = "".join(f"<li>{_esc(e)}</li>" for e in errors)
        extras.append(f'<div class="tile lsub"><h3>{_esc(led["worker_errors"])}</h3><ul class="pathlist">{rows_html}</ul></div>')
    failed_ids = state.get("failed") or []
    if failed_ids:
        results = state.get("task_results") or {}
        failed_rows = "".join(
            f'<li><code>{_esc(fid)}</code> · {_esc(tasks.get(fid, {}).get("title", ""))}'
            + (f' — <code>{_esc(results[fid].get("error_type"))}</code>'
               if isinstance(results.get(fid), dict) and results[fid].get("error_type") else "")
            + "</li>" for fid in failed_ids
        )
        extras.append(f'<div class="tile lsub"><h3>{_esc(chrome["failed_title"])}</h3><ul class="pathlist">{failed_rows}</ul></div>')
    return (
        f'<section id="ledger">{_section_head("ledger", "shield", chrome)}'
        f'<div class="tile ledger">{"".join(rows)}</div>{"".join(extras)}</section>'
    )


def write_html_report(run_dir: Path, state: dict[str, Any], *, language: str = "auto") -> Path:
    """Render the run's human-facing page from its receipts on disk."""
    tasks = _merged_tasks(run_dir)
    items = _collect_artifacts(run_dir, state, tasks)
    sample = "\n".join(item["raw_text"][:4000] for item in items)
    lang = _chrome_language(language, sample)
    chrome = CHROME[lang]
    events = _read_events(run_dir)

    payload = json.dumps(
        {
            "run_id": state.get("run_id", run_dir.name),
            "items": [{"id": i["id"], "title": i["title"], "path": i["path"], "root": i["root"], "source": i["source"]} for i in items],
            "t": {k: chrome[k] for k in ("handoff_add", "handoff_added", "handoff_header", "handoff_field_file",
                                          "handoff_field_from", "handoff_field_note", "feedback_header", "copied")},
        },
        ensure_ascii=False,
    )
    # JSON inside a <script> block: escape every angle bracket and ampersand so no
    # title or path can close the tag or read as markup — data, never markup.
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")

    page = (
        "<!doctype html>\n"
        f'<html lang="{lang}"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_esc(chrome['doc_title'])} · {_esc(state.get('run_id', run_dir.name))}</title>\n"
        f"<style>{CSS}</style></head><body>\n"
        + _band(state)
        + '<div class="wrap">\n'
        + f'<h1 class="headline">{_esc(chrome["headline"])}</h1>'
        + _oracle_block(state, items, chrome, lang)
        + _comp_block(items, chrome)
        + _fact_block(state, items, chrome, lang)
        + _fixed_lines(state, items, chrome)
        + _first_section(items, chrome)
        + _work_section(items, chrome)
        + _watch_section(events, chrome)
        + _ledger_section(state, tasks, chrome)
        + f'<footer class="foot">{_esc(chrome["foot"])}</footer>\n</div>\n'
        + '<div class="bar">'
        + f'<span class="n"><span class="cnt" id="qn">0</span>{_esc(chrome["queued_n"])}</span>'
        + f'<button class="primary" id="copy-handoff">{_ico("send", 15)}{_esc(chrome["handoff_copy"])}</button>'
        + f'<button class="ghost" id="copy-feedback">{_ico("copy", 14)}{_esc(chrome["feedback_copy"])} (<span id="gn">0</span>)</button>'
        + "</div>\n"
        + f'<script type="application/json" id="bbr-data">{payload}</script>\n'
        + f"<script>{JS}</script>\n</body></html>\n"
    )
    out = run_dir / REPORT_BASENAME
    write_text_atomic(out, page)
    return out


def generate_report(run_dir: Path, language: str = "auto") -> Path:
    """Regenerate the HTML report for an existing run directory (`bbr report`)."""
    state = read_json(run_dir / "RUN_STATE.json")
    if not isinstance(state, dict):
        raise ValueError(f"{run_dir} has no readable RUN_STATE.json")
    return write_html_report(run_dir, state, language=language)
