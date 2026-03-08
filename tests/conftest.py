import json
from typing import Callable, Mapping, MutableMapping

import pytest

from oncorounds.case import (
    BenchmarkCase,
    InfoItem,
    PatientDemographics,
    PatientProfile,
    ReferenceStandard,
    RoundReference,
    TreatmentAction,
)
from oncorounds.clients import ClientResponse


class FakeParserClient:
    """Deterministic parser stub used in tests."""

    def __init__(self, mapping: Mapping[str, str | None]):
        self.mapping = mapping

    def generate_json(
        self,
        *,
        messages,
        response_schema,
        **_,
    ) -> ClientResponse:
        payload = json.loads(messages[-1]["content"])
        request = payload["request"].lower()
        response: MutableMapping[str, object] = {
            "valid": False,
            "info_item": "NO_MATCH",
            "feedback_category": "not_available",
            "feedback": "No matching item.",
            "suggested_item": None,
        }
        for needle, mapped in self.mapping.items():
            if needle in request:
                if mapped is not None:
                    response.update(
                        {
                            "valid": True,
                            "info_item": mapped,
                            "feedback_category": "available",
                            "feedback": "",
                            "suggested_item": None,
                        }
                    )
                break
        return ClientResponse(data={"request": response})


class FakeJudgeClient:
    """Simple judge stub that returns a preconfigured evaluation payload."""

    def __init__(self, factory: Callable[[dict], MutableMapping[str, object]]):
        self.factory = factory

    def generate_json(
        self,
        *,
        messages,
        response_schema,
        **_,
    ) -> ClientResponse:
        payload = json.loads(messages[-1]["content"])
        return ClientResponse(data=self.factory(payload))


@pytest.fixture
def sample_case() -> BenchmarkCase:
    """Return a compact case fixture for unit tests."""

    patient = PatientProfile(
        demographics=PatientDemographics(age=60, sex="female"),
        chief_complaint="Fatigue and easy bruising",
        vital_signs="BP 118/72, HR 92, afebrile",
    )
    info_items = {
        "history": InfoItem(
            name="history", available_round=1, content="Bleeding gums, weight loss."
        ),
        "labs": InfoItem(
            name="labs",
            available_round=2,
            content="WBC 45, Hb 7.8, Plt 30.",
        ),
    }
    reference = ReferenceStandard(
        rounds={
            1: RoundReference(
                working_diagnosis="Acute leukemia",
                differentials=["AML", "ALL"],
                treatment_plan=[
                    TreatmentAction(action="Admit to oncology ward", intention="supportive", priority=1)
                ],
                key_findings_quotes=["\"Bleeding gums\""],
            ),
            2: RoundReference(
                working_diagnosis="AML",
                differentials=["APL"],
                treatment_plan=[
                    TreatmentAction(
                        action="Start 7+3 induction", intention="therapeutic", priority=1
                    )
                ],
                key_findings_quotes=["\"WBC 45\""],
            ),
        }
    )
    return BenchmarkCase(
        case_id=99,
        title="Test Leukemia Case",
        patient=patient,
        info_items=info_items,
        reference_standard=reference,
    )
