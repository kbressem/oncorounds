"""Run a scripted demo case and log every interaction."""

from __future__ import annotations

import json
from typing import Callable, Mapping, MutableMapping

from oncorounds.benchmark import Benchmark
from oncorounds.clients import ClientResponse
from .test_utils import (
    ScriptedCandidate,
    get_test_logger,
    load_demo_case,
    log_actor,
    run_benchmark_with_logging,
)


class LoggingParserClient:
    """Parser stub that logs both input and output."""

    def __init__(self, mapping: Mapping[str, str | None], logger: Callable[[str, str], None]) -> None:
        self.mapping = mapping
        self.log = logger

    def generate_json(
        self,
        *,
        messages,
        response_schema,
        **_,
    ) -> ClientResponse:
        payload = json.loads(messages[-1]["content"])
        self.log("PARSER", f"Input payload:\n{json.dumps(payload, indent=2)}")

        request = payload["request"].lower()
        info_item = None
        valid = False
        for needle, mapped in self.mapping.items():
            if needle in request:
                info_item = mapped
                valid = mapped is not None
                break

        result: MutableMapping[str, object] = {"request": {"valid": valid, "info_item": info_item}}
        self.log("PARSER", f"Output:\n{json.dumps(result, indent=2)}")
        return ClientResponse(data=result)


class LoggingJudgeClient:
    """Judge stub that returns preconfigured evaluations with logging."""

    def __init__(self, logger: Callable[[str, str], None]) -> None:
        self.log = logger

    def generate_json(
        self,
        *,
        messages,
        response_schema,
        **_,
    ) -> ClientResponse:
        payload = json.loads(messages[-1]["content"])
        self.log("JUDGE", f"Input payload:\n{json.dumps(payload, indent=2)}")

        candidate = payload["candidate_response"]
        evaluation: MutableMapping[str, object] = {
            "case_id": payload["case_id"],
            "round": payload["round"],
            "evaluation": {
                "working_diagnosis": "correct",
                "differentials": ["correct"] * len(candidate.get("differentials", [])),
                "treatment_plan": [
                    {"action": "correct", "intention": "correct", "priority": "correct"}
                    for _ in candidate.get("treatment_plan", [])
                ],
            },
        }
        self.log("JUDGE", f"Output:\n{json.dumps(evaluation, indent=2)}")
        return ClientResponse(data=evaluation)


def main() -> None:
    logger = get_test_logger("tests.integration.scripted")
    demo_case = load_demo_case()
    benchmark = Benchmark(
        parser_client=LoggingParserClient(
            mapping={
                "history": "history_physical",
                "physical": "history_physical",
                "dermoscopy": "dermoscopy",
                "derm": "dermoscopy",
                "biopsy": "biopsy_pathology",
                "pathology": "biopsy_pathology",
            },
            logger=lambda role, message: log_actor(logger, benchmark, role, message),
        ),
        judge_client=LoggingJudgeClient(
            logger=lambda role, message: log_actor(logger, benchmark, role, message),
        ),
        max_consecutive_failures_to_cancellation=3,
    )

    benchmark.set_case(demo_case)
    run_benchmark_with_logging(benchmark, ScriptedCandidate(), logger)


if __name__ == "__main__":
    main()
