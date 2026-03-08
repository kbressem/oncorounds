"""Data structures for benchmark cases."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterator, Mapping

from jsonschema import Draft7Validator, ValidationError

from .errors import CaseValidationError

_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_PATH = _ROOT / "schemas" / "case.json"


@lru_cache(maxsize=1)
def _schema_validator() -> Draft7Validator:
    return Draft7Validator(json.loads(_SCHEMA_PATH.read_text()))


@dataclass(frozen=True, slots=True)
class PatientDemographics:
    age: int
    sex: str


@dataclass(frozen=True, slots=True)
class PatientProfile:
    demographics: PatientDemographics
    chief_complaint: str
    vital_signs: str


@dataclass(frozen=True, slots=True)
class RoundGuide:
    setting: str
    capabilities: str


@dataclass(frozen=True, slots=True)
class InfoItem:
    name: str
    available_round: int
    content: str
    valid_request_if: str | None = None

    def to_parser_hint(self) -> dict:
        hint = {"info_item": self.name, "available_round": self.available_round}
        if self.valid_request_if:
            hint["valid_request_if"] = self.valid_request_if
        return hint


@dataclass(frozen=True, slots=True)
class TreatmentAction:
    action: str
    intention: str
    priority: int

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "intention": self.intention,
            "priority": self.priority,
        }


@dataclass(frozen=True, slots=True)
class RoundReference:
    working_diagnosis: str
    differentials: list[str]
    treatment_plan: list[TreatmentAction]
    key_findings_quotes: list[str]

    def to_dict(self) -> dict:
        return {
            "working_diagnosis": self.working_diagnosis,
            "differentials": list(self.differentials),
            "treatment_plan": [a.to_dict() for a in self.treatment_plan],
            "key_findings_quotes": list(self.key_findings_quotes),
        }


@dataclass(frozen=True, slots=True)
class ReferenceStandard:
    rounds: Mapping[int, RoundReference]

    @property
    def max_round(self) -> int:
        return max(self.rounds) if self.rounds else 0


@dataclass(slots=True)
class BenchmarkCase:
    case_id: int
    title: str
    patient: PatientProfile
    round_guides: dict[int, RoundGuide] = field(default_factory=dict)
    info_items: dict[str, InfoItem] = field(default_factory=dict)
    reference_standard: ReferenceStandard | None = None

    def get_info_item(self, name: str) -> InfoItem:
        return self.info_items[name]

    @property
    def max_round(self) -> int:
        return self.reference_standard.max_round if self.reference_standard else 0


def _load_reference_standard(data: Mapping) -> ReferenceStandard:
    rounds = {}
    for key, p in data.items():
        r = int(key.removeprefix("round_"))
        rounds[r] = RoundReference(
            working_diagnosis=p["working_diagnosis"],
            differentials=list(p["differentials"]),
            treatment_plan=[TreatmentAction(**t) for t in p.get("treatment_plan", [])],
            key_findings_quotes=list(p.get("key_findings_quotes", [])),
        )
    return ReferenceStandard(rounds=rounds)


def load_case(path: str | Path) -> BenchmarkCase:
    """Load and validate a benchmark case from disk."""
    path = Path(path)
    data = json.loads(path.read_text())
    data.pop("$schema", None)

    try:
        _schema_validator().validate(data)
    except ValidationError as e:
        raise CaseValidationError(f"{path} failed validation: {e.message}") from e

    p = data["patient"]
    return BenchmarkCase(
        case_id=data["case_id"],
        title=data["title"],
        patient=PatientProfile(
            demographics=PatientDemographics(
                age=p["demographics"]["age"], sex=p["demographics"]["sex"]
            ),
            chief_complaint=p["chief_complaint"],
            vital_signs=p["vital_signs"],
        ),
        round_guides={
            int(k): RoundGuide(**v) for k, v in data.get("round_guides", {}).items()
        },
        info_items={n: InfoItem(name=n, **i) for n, i in data["info_items"].items()},
        reference_standard=_load_reference_standard(data["reference_standard"]),
    )


class CaseLoader:
    """Iterator over cases in a directory."""

    def __init__(self, case_dir: str | Path):
        self.case_dir = Path(case_dir)
        if not self.case_dir.exists():
            raise FileNotFoundError(f"Case directory {self.case_dir} does not exist.")
        self._paths = sorted(
            f for f in self.case_dir.glob("*.json") if f.name.startswith("case-")
        )

    def __len__(self) -> int:
        return len(self._paths)

    def __iter__(self) -> Iterator[BenchmarkCase]:
        for p in self._paths:
            yield load_case(p)
