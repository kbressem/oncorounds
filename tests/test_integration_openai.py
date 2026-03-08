import os

import pytest

from oncorounds.benchmark import Benchmark
from oncorounds.clients import OpenAIClient
from .test_utils import (
    ScriptedCandidate,
    get_test_logger,
    load_demo_case,
    run_benchmark_with_logging,
)


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Requires OPENAI_API_KEY to contact OpenAI Responses API.",
)
def test_scripted_case_with_openai_parser_and_judge() -> None:
    openai = pytest.importorskip("openai")
    client = openai.OpenAI()

    parser = OpenAIClient(
        client=client,
        model="gpt-5-mini",
        default_kwargs={"max_output_tokens": 4096},
    )
    judge = OpenAIClient(
        client=client,
        model="gpt-5-mini",
        default_kwargs={"max_output_tokens": 4096},
    )

    logger = get_test_logger("tests.integration.openai")

    benchmark = Benchmark(
        parser_client=parser,
        judge_client=judge,
        logger=None,
    )
    benchmark.set_case(load_demo_case())
    candidate = ScriptedCandidate()

    evaluations = run_benchmark_with_logging(benchmark, candidate, logger)

    assert benchmark.state is not None
    assert not benchmark.running
    assert len(evaluations) == 3

    for result in evaluations:
        evaluation = result["evaluation"]
        assert evaluation["working_diagnosis"] == "correct", "Working diagnosis not correct."
        assert all(label == "correct" for label in evaluation["differentials"]), "Differentials not correct."
        assert all(
            step["action"] == "correct" and step["intention"] == "correct" and step["priority"] == "correct"
            for step in evaluation["treatment_plan"]
        ), "Treatment plan not correct."
