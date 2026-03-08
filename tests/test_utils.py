from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import MutableMapping, Sequence

from oncorounds.benchmark import Benchmark, ProcessOutcome
from oncorounds.case import BenchmarkCase, load_case

DEFAULT_CASE_PATH = Path(__file__).with_name("testcase.json")


def load_demo_case(path: str | Path | None = None) -> BenchmarkCase:
    """Load the scripted demo case from disk."""
    case_path = Path(path) if path is not None else DEFAULT_CASE_PATH
    return load_case(case_path)


class ScriptedCandidate:
    """Deterministic candidate tuned for the basal cell carcinoma demo case."""

    def __init__(self) -> None:
        self.turn = 0
        self._script = [
            self._request_history_physical,
            self._solve_round_one,
            self._request_dermoscopy,
            self._solve_round_two,
            self._request_biopsy_pathology,
            self._solve_round_three,
        ]

    def respond(self, conversation: Sequence[dict[str, str]]) -> MutableMapping[str, object]:
        handler_index = min(self.turn, len(self._script) - 1)
        payload = self._script[handler_index](conversation)
        self.turn += 1
        return payload

    def _request_history_physical(self, conversation: Sequence[dict[str, str]]) -> MutableMapping[str, object]:
        return {
            "response": {
                "action": "request",
                "request": "Could you share the detailed history and physical examination findings for this lesion?",
            }
        }

    def _solve_round_one(self, conversation: Sequence[dict[str, str]]) -> MutableMapping[str, object]:
        return {
            "response": {
                "action": "solve",
                "solve": {
                    "working_diagnosis": "Suspected nonmelanoma skin cancer, likely basal cell carcinoma",
                    "differentials": [
                        "Basal cell carcinoma",
                        "Cutaneous squamous cell carcinoma",
                        "Seborrheic keratosis",
                    ],
                    "treatment_plan": [
                        {
                            "action": "Request dermoscopy of the lesion",
                            "intention": "diagnostic",
                            "priority": 1,
                        },
                        {
                            "action": "Avoid destructive treatment before tissue diagnosis",
                            "intention": "supportive",
                            "priority": 1,
                        },
                        {
                            "action": "Provide brief sun protection advice",
                            "intention": "supportive",
                            "priority": 3,
                        },
                    ],
                },
            }
        }

    def _request_dermoscopy(self, conversation: Sequence[dict[str, str]]) -> MutableMapping[str, object]:
        return {
            "response": {
                "action": "request",
                "request": "Please provide the dermoscopy findings for the lesion.",
            }
        }

    def _solve_round_two(self, conversation: Sequence[dict[str, str]]) -> MutableMapping[str, object]:
        return {
            "response": {
                "action": "solve",
                "solve": {
                    "working_diagnosis": "Probable basal cell carcinoma",
                    "differentials": [
                        "Basal cell carcinoma",
                        "Cutaneous squamous cell carcinoma",
                    ],
                    "treatment_plan": [
                        {
                            "action": "Perform shave biopsy of the lesion for histologic confirmation",
                            "intention": "diagnostic",
                            "priority": 1,
                        },
                        {
                            "action": "Prepare for simple surgical excision under local anesthesia if basal cell carcinoma is confirmed",
                            "intention": "therapeutic",
                            "priority": 2,
                        },
                    ],
                },
            }
        }

    def _request_biopsy_pathology(self, conversation: Sequence[dict[str, str]]) -> MutableMapping[str, object]:
        return {
            "response": {
                "action": "request",
                "request": "Share the biopsy pathology report for this lesion.",
            }
        }

    def _solve_round_three(self, conversation: Sequence[dict[str, str]]) -> MutableMapping[str, object]:
        return {
            "response": {
                "action": "solve",
                "solve": {
                    "working_diagnosis": "Nodular basal cell carcinoma of the left forearm, low-risk",
                    "differentials": [
                        "Basal cell carcinoma",
                    ],
                    "treatment_plan": [
                        {
                            "action": "Simple surgical excision with 4 mm clinical margins and pathology margin assessment",
                            "intention": "therapeutic",
                            "priority": 1,
                        },
                        {
                            "action": "No imaging or staging tests",
                            "intention": "supportive",
                            "priority": 2,
                        },
                        {
                            "action": "Schedule full skin examination follow-up at 6 to 12 months",
                            "intention": "supportive",
                            "priority": 3,
                        },
                    ],
                },
            }
        }




def get_test_logger(name: str = "oncorounds.tests") -> logging.Logger:
    """Return a logger configured to stream INFO logs to stdout once."""
    logger = logging.getLogger(name)
    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = True
    return logger


def log_actor(logger: logging.Logger, benchmark: Benchmark, role: str, message: str) -> None:
    """Log an interaction annotated with case metadata."""
    state = benchmark.state
    case_id = state.case.case_id if state else "-"
    round_number = state.round_number if state else "-"
    step_index = state.step_index if state else "-"
    prefix = f"[Case {case_id} Round {round_number} Step {step_index}] {role}: "
    lines = message.splitlines() or [""]
    logger.info("%s%s", prefix, lines[0])
    indent = " " * len(prefix)
    for line in lines[1:]:
        logger.info("%s%s", indent, line)


def log_new_conversation_entries(
    logger: logging.Logger, benchmark: Benchmark, start: int, end: int
) -> None:
    """Emit any new user messages that entered the conversation."""
    state = benchmark.state
    if not state:
        return
    conversation = state.conversation
    for idx in range(start, min(end, len(conversation))):
        entry = conversation[idx]
        role = entry.get("role", "user")
        if role == "assistant":
            continue
        log_actor(logger, benchmark, "ENV", entry.get("content", ""))


def log_outcome_details(logger: logging.Logger, benchmark: Benchmark, outcome: ProcessOutcome) -> None:
    """Log parser releases, judge feedback, and terminal messages."""
    if outcome.released_content:
        message = f"Released content for '{outcome.released_item}':\n{outcome.released_content}"
        log_actor(logger, benchmark, "ENV", message)
    if outcome.judge_evaluation:
        log_actor(logger, benchmark, "JUDGE", json.dumps(outcome.judge_evaluation, indent=2))
    if outcome.status in {"request_invalid", "request_pending", "invalid_response", "request_guidance"}:
        log_actor(logger, benchmark, "ENV", outcome.message)
    if not benchmark.running and outcome.status == "solve_evaluated":
        log_actor(logger, benchmark, "ENV", "Case complete.")


def run_benchmark_with_logging(
    benchmark: Benchmark,
    candidate: ScriptedCandidate,
    logger: logging.Logger,
) -> list[MutableMapping[str, object]]:
    """Drive a benchmark loop, emitting conversation logs and returning judge evaluations."""
    evaluations: list[MutableMapping[str, object]] = []
    state = benchmark.state
    if state and state.conversation:
        log_actor(logger, benchmark, "ENV", state.conversation[-1]["content"])

    while benchmark.running:
        messages, _ = benchmark.create_candidate_prompt()
        payload = candidate.respond(messages)
        log_actor(logger, benchmark, "CANDIDATE", json.dumps(payload, indent=2))

        before_len = len(benchmark.state.conversation) if benchmark.state else 0  # type: ignore[union-attr]
        outcome = benchmark.process_candidate_response(payload)
        after_len = len(benchmark.state.conversation) if benchmark.state else before_len  # type: ignore[union-attr]

        log_new_conversation_entries(logger, benchmark, before_len, after_len)
        log_outcome_details(logger, benchmark, outcome)

        if outcome.judge_evaluation:
            evaluations.append(outcome.judge_evaluation)

    return evaluations
