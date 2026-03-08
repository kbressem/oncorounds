import pytest

from oncorounds.benchmark import Benchmark
from oncorounds.clients import ClientResponse
from oncorounds.errors import JudgeError, ParserError

from .conftest import FakeJudgeClient, FakeParserClient


def make_judge() -> FakeJudgeClient:
    def factory(payload: dict):
        candidate = payload["candidate_response"]
        return {
            "case_id": payload["case_id"],
            "round": payload["round"],
            "evaluation": {
                "working_diagnosis": "correct",
                "differentials": ["correct"] * len(candidate["differentials"]),
                "treatment_plan": [
                    {"action": "correct", "intention": "correct", "priority": "correct"}
                    for _ in candidate["treatment_plan"]
                ],
            },
        }

    return FakeJudgeClient(factory=factory)


@pytest.fixture
def benchmark(sample_case):
    parser = FakeParserClient({"history": "history", "lab": "labs", "labs": "labs"})
    judge = make_judge()
    bench = Benchmark(parser_client=parser, judge_client=judge)
    bench.set_case(sample_case)
    return bench


def test_benchmark_releases_information(benchmark):
    messages, schema = benchmark.create_candidate_prompt()
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Initial presentation" in messages[1]["content"]
    candidate_turn = {
        "response": {
            "action": "request",
            "request": "Share the detailed history",
        }
    }
    outcome = benchmark.process_candidate_response(candidate_turn)
    assert outcome.status == "request_released"
    assert outcome.valid
    assert outcome.released_item == "history"
    assert "Bleeding gums" in outcome.released_content
    assert "history" in benchmark.state.released_items  # type: ignore[union-attr]


def test_benchmark_pending_request_for_future_round(benchmark):
    candidate_turn = {
        "response": {
            "action": "request",
            "request": "Provide laboratory values",
        }
    }
    outcome = benchmark.process_candidate_response(candidate_turn)
    assert outcome.status == "request_pending"
    assert not outcome.valid
    # Requesting unavailable info counts as failure to prevent infinite loops
    assert benchmark.state.n_consecutive_failures == 1  # type: ignore[union-attr]


def test_benchmark_solve_advances_round(benchmark):
    solve_payload = {
        "response": {
            "action": "solve",
            "solve": {
                "working_diagnosis": "Acute leukemia",
                "differentials": ["AML"],
                "treatment_plan": [
                    {
                        "action": "Admit to oncology ward",
                        "intention": "supportive",
                        "priority": 1,
                    }
                ],
            },
        }
    }
    outcome = benchmark.process_candidate_response(solve_payload)
    assert outcome.status == "solve_evaluated"
    assert benchmark.state.round_number == 2  # type: ignore[union-attr]
    assert benchmark.running

    final_turn = {
        "response": {
            "action": "solve",
            "solve": {
                "working_diagnosis": "AML",
                "differentials": ["APL"],
                "treatment_plan": [
                    {"action": "Start 7+3 induction", "intention": "therapeutic", "priority": 1}
                ],
            },
        }
    }
    outcome_final = benchmark.process_candidate_response(final_turn)
    assert outcome_final.status == "solve_evaluated"
    assert not benchmark.running


def test_benchmark_handles_invalid_json(benchmark):
    outcome = benchmark.process_candidate_response("not valid json")
    assert outcome.action == "invalid"
    assert not outcome.valid
    assert benchmark.state  # type: ignore[truthy-function]
    assert benchmark.state.n_consecutive_failures == 1  # type: ignore[union-attr]
    assert "Response must be valid JSON" in outcome.message


def test_benchmark_prompts_for_missing_request_payload(benchmark):
    payload = {
        "response": {
            "action": "request",
            # intentionally omit "request"
        }
    }
    outcome = benchmark.process_candidate_response(payload)
    # This should now fail validation because "request" is required in "next_step" when action is "request"
    # Or if the schema validation passes (it shouldn't), the code checks for it.
    # Actually, the schema validation will fail first.
    assert outcome.status == "invalid_response" or outcome.status == "terminated"
    assert not outcome.valid
    assert benchmark.state  # type: ignore[truthy-function]
    assert benchmark.state.n_consecutive_failures == 1  # type: ignore[union-attr]


def test_benchmark_rejects_duplicate_request(benchmark):
    first_request = {
        "response": {
            "action": "request",
            "request": "Share the detailed history",
        }
    }
    benchmark.process_candidate_response(first_request)

    duplicate_request = {
        "response": {
            "action": "request",
            "request": "Share the detailed history",
        }
    }
    outcome = benchmark.process_candidate_response(duplicate_request)
    assert outcome.status == "request_invalid"
    assert not outcome.valid
    assert outcome.released_item == "history"
    assert benchmark.state  # type: ignore[truthy-function]
    assert benchmark.state.n_consecutive_failures == 1  # type: ignore[union-attr]


def test_benchmark_parser_validation_error(sample_case):
    class BrokenParser:
        def generate_json(self, *, messages, response_schema, **_):
            return ClientResponse(data={})  # missing required structure

    benchmark = Benchmark(parser_client=BrokenParser(), judge_client=make_judge())
    benchmark.set_case(sample_case)
    payload = {
        "response": {
            "action": "request",
            "request": "Please provide laboratory values.",
        }
    }
    with pytest.raises(ParserError):
        benchmark.process_candidate_response(payload)


def test_benchmark_judge_validation_error(sample_case):
    parser = FakeParserClient({"history": "history"})

    class BrokenJudge:
        def generate_json(self, *, messages, response_schema, **_):
            return ClientResponse(data={})  # invalid payload for judge schema

    benchmark = Benchmark(parser_client=parser, judge_client=BrokenJudge())
    benchmark.set_case(sample_case)
    solve_payload = {
        "response": {
            "action": "solve",
            "solve": {
                "working_diagnosis": "Acute leukemia",
                "differentials": ["AML"],
                "treatment_plan": [
                    {"action": "Start induction", "intention": "therapeutic", "priority": 1}
                ],
            },
        }
    }

    with pytest.raises(JudgeError):
        benchmark.process_candidate_response(solve_payload)


def test_benchmark_cancels_after_max_failures(sample_case):
    parser = FakeParserClient({"history": "history"})
    judge = make_judge()
    benchmark = Benchmark(
        parser_client=parser,
        judge_client=judge,
        max_consecutive_failures=1,
    )
    benchmark.set_case(sample_case)
    outcome = benchmark.process_candidate_response("not json")  # counts as invalid
    assert outcome.status == "invalid_response"
    assert benchmark.state  # type: ignore[truthy-function]
    assert not benchmark.state.running  # type: ignore[union-attr]
    assert "Case cancelled" in benchmark.state.conversation[-1]["content"]  # type: ignore[index]


def test_benchmark_suggests_similar_item(sample_case):
    class SuggestingParser:
        def generate_json(self, *, messages, response_schema, **_):
            return ClientResponse(data={
                "request": {
                    "valid": False,
                    "info_item": "NO_MATCH",
                    "feedback_category": "similar_available",
                    "feedback": "Ultrasound is unavailable, but routine labs are an option.",
                    "suggested_item": "labs",
                }
            })

    benchmark = Benchmark(parser_client=SuggestingParser(), judge_client=make_judge())
    benchmark.set_case(sample_case)
    outcome = benchmark.process_candidate_response(
        {
            "response": {
                "action": "request",
                "request": "Please provide an ultrasound result.",
            }
        }
    )
    assert outcome.status == "request_guidance"
    assert not outcome.valid
    assert benchmark.state  # type: ignore[truthy-function]
    assert benchmark.state.n_consecutive_failures == 1  # type: ignore[union-attr]
    assert "labs" in outcome.message
