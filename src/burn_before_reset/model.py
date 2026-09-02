from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceRef:
    source_type: str
    root: str
    path: str
    modified_at: str
    signals: tuple[str, ...] = ()
    snippets: tuple[str, ...] = ()
    title: str = ""
    # Identity of the content behind the reference where mtime cannot carry it:
    # a git source's whole dirty set, a sweep's membership. Empty when unused.
    fingerprint: str = ""

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["signals"] = list(self.signals)
        value["snippets"] = list(self.snippets)
        return value


@dataclass(frozen=True)
class TaskSpec:
    id: str
    title: str
    objective: str
    source_refs: tuple[dict[str, Any], ...]
    deliverables: tuple[str, ...]
    allowed_read_roots: tuple[str, ...]
    allowed_write_root: str
    validation: tuple[str, ...]
    strategic_value: int
    reuse: int
    readiness: int
    verifiability: int
    recency: int
    checkpointability: int
    token_fitness: int
    risk: int
    human_dependency: int
    estimated_class: str = "small"
    checkpoint_interval_minutes: int = 10
    status: str = "queued"
    score: int = field(init=False)

    def __post_init__(self) -> None:
        fields = (
            self.strategic_value,
            self.reuse,
            self.readiness,
            self.verifiability,
            self.recency,
            self.checkpointability,
            self.token_fitness,
            self.risk,
            self.human_dependency,
        )
        if any(value < 0 or value > 5 for value in fields):
            raise ValueError("task score inputs must be between 0 and 5")
        if not self.source_refs or not self.deliverables or not self.validation:
            raise ValueError("task requires source_refs, deliverables, and validation")
        if not self.allowed_read_roots or not self.allowed_write_root:
            raise ValueError("task requires explicit read and write boundaries")
        score = (
            3 * self.strategic_value
            + 2 * self.reuse
            + 2 * self.readiness
            + 2 * self.verifiability
            + 2 * self.recency
            + self.checkpointability
            + self.token_fitness
            - 3 * self.risk
            - 2 * self.human_dependency
        )
        object.__setattr__(self, "score", score)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in (
            "source_refs",
            "deliverables",
            "allowed_read_roots",
            "validation",
        ):
            value[key] = list(value[key])
        return value
