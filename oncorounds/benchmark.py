"""Benchmark engine orchestrating the interactive evaluation loop.

This module contains the core Benchmark class that manages the conversation flow
between the candidate model and the evaluation system, handling request validation,
information release, and solution judging.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal, MutableMapping, cast

from jsonschema import Draft7Validator, ValidationError

from .case import BenchmarkCase
from .clients import JSONModelClient, OpenAIClient
from .errors import BenchmarkStateError, JudgeError, ParserError
from .prompts import load_prompt
from .schemas import load_schema


class EventType(str, Enum):
    """Event types for case logging."""

    INITIAL_CASE_PRESENTATION = "initial_case_presentation"
    CANDIDATE_RESPONSE = "candidate_response"
    ENV_RESPONSE = "env_response"
    JUDGE_EVALUATION = "judge_evaluation"


class FeedbackCategory(str, Enum):
    """Parser feedback categories."""

    SIMILAR_AVAILABLE = "similar_available"


class CaseStatus(str, Enum):
    """Case completion status."""

    COMPLETED = "completed"
    CANCELLED = "cancelled"


def _get_validator_schema(validator: Draft7Validator) -> dict[str, Any]:
    """Extract schema from a Draft7Validator instance."""
    return cast(dict[str, Any], getattr(validator, "schema"))


def _majority_vote(values: list[str]) -> str:
    """Return majority vote, with partially_correct as tiebreaker."""
    if not values:
        return ""
    counts = Counter(values)
    max_count = max(counts.values())
    winners = [v for v, c in counts.items() if c == max_count]
    if len(winners) == 1:
        return winners[0]
    for preferred in ["partially_correct", "correct", "incorrect"]:
        if preferred in winners:
            return preferred
    return winners[0]


def _aggregate_evaluations(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate multiple judge evaluations using majority voting."""
    if not evaluations:
        return {}
    if len(evaluations) == 1:
        return evaluations[0]

    result: dict[str, Any] = {}

    # Working diagnosis
    wd_votes = [e.get("working_diagnosis", "") for e in evaluations if e.get("working_diagnosis")]
    if wd_votes:
        result["working_diagnosis"] = _majority_vote(wd_votes)

    # Differentials
    diff_lists = [e.get("differentials", []) for e in evaluations]
    if any(diff_lists):
        max_len = max(len(d) for d in diff_lists)
        result["differentials"] = []
        for i in range(max_len):
            votes = [d[i] for d in diff_lists if i < len(d) and d[i]]
            if votes:
                result["differentials"].append(_majority_vote(votes))

    # Treatment plan
    tp_lists = [e.get("treatment_plan", []) for e in evaluations]
    if any(tp_lists):
        max_len = max(len(tp) for tp in tp_lists)
        result["treatment_plan"] = []
        for i in range(max_len):
            item: dict[str, str] = {}
            for fld in ["action", "intention", "priority"]:
                votes = [tp[i].get(fld, "") for tp in tp_lists if i < len(tp) and tp[i].get(fld)]
                if votes:
                    item[fld] = _majority_vote(votes)
            if item:
                result["treatment_plan"].append(item)

    # Key findings
    kf_lists = [e.get("key_findings", []) for e in evaluations]
    if any(kf_lists):
        max_len = max(len(kf) for kf in kf_lists)
        result["key_findings"] = []
        for i in range(max_len):
            votes = [kf[i] for kf in kf_lists if i < len(kf) and kf[i]]
            if votes:
                result["key_findings"].append(_majority_vote(votes))

    return result


CandidateAction = Literal["request", "solve", "invalid"]


class _CaseLogger:
    """Internal logger for a single case's conversation and events."""

    def __init__(self, log_path: Path, jsonl_path: Path, mode: str = "w"):
        self._log_file = log_path.open(mode, encoding="utf-8")
        self._jsonl_file = jsonl_path.open(mode, encoding="utf-8")

    def close(self) -> None:
        self._log_file.close()
        self._jsonl_file.close()

    def log(
        self,
        case_id: int,
        round_num: int,
        step: int,
        role: str,
        content: str,
        **extras: object,
    ) -> None:
        # Human-readable log
        prefix = f"[Case {case_id} Round {round_num} Step {step}] {role}: "
        lines = content.splitlines() or [""]
        formatted = [prefix + lines[0]] + [
            (" " * len(prefix)) + line for line in lines[1:]
        ]
        self._log_file.write("\n".join(formatted) + "\n")
        self._log_file.flush()

        # JSONL for machine processing and resume
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "case_id": case_id,
            "round_number": round_num,
            "step_index": step,
            "role": role,
            "content": content,
            **extras,
        }
        self._jsonl_file.write(json.dumps(entry) + "\n")
        self._jsonl_file.flush()


@dataclass
class ProcessOutcome:
    """Result of processing a candidate response."""

    action: CandidateAction
    status: str
    message: str = ""
    valid: bool = False
    released_item: str | None = None
    released_content: str | None = None
    judge_evaluation: MutableMapping[str, object] | None = None


@dataclass
class BenchmarkState:
    """Mutable state for a single case evaluation."""

    case: BenchmarkCase
    round_number: int = 1
    step_index: int = 0
    running: bool = True
    n_consecutive_failures: int = 0
    released_items: set[str] = field(default_factory=set)
    conversation: list[dict[str, str]] = field(default_factory=list)
    round_scores: dict[int, MutableMapping[str, object]] = field(default_factory=dict)


class Benchmark:
    """Interactive benchmark controller.

    Provides a simple PyTorch-style loop for running evaluations:

        for case in CaseLoader("cases"):
            benchmark.set_case(case)
            while benchmark.running:
                messages, schema = benchmark.create_candidate_prompt()
                payload = candidate.generate_json(messages=messages, response_schema=schema)
                benchmark.process_candidate_response(payload)

    Logging, persistence, and output saving are handled automatically when
    run_name, output_dir, and log_dir are provided.
    """

    def __init__(
        self,
        *,
        parser_client: JSONModelClient,
        judge_client: JSONModelClient,
        run_name: str | None = None,
        output_dir: str | Path | None = None,
        log_dir: str | Path | None = None,
        parser_instructions: str | None = None,
        judge_instructions: str | None = None,
        max_consecutive_failures: int = 10,
        judge_ensemble_size: int = 5,
        resume: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        self.parser_client = parser_client
        self.judge_client = judge_client
        self.run_name = run_name
        self.output_dir = Path(output_dir) if output_dir else None
        self.log_dir = Path(log_dir) if log_dir else None
        self.resume = resume
        self.judge_ensemble_size = judge_ensemble_size
        self.parser_instructions = parser_instructions or load_prompt(
            "parser-instructions"
        )
        self.judge_instructions = judge_instructions or load_prompt(
            "judge-instructions"
        )
        self.candidate_instructions = load_prompt("candidate-instructions")
        self.max_consecutive_failures = max_consecutive_failures
        self.logger = logger or logging.getLogger("oncorounds.benchmark")

        self._candidate_validator = Draft7Validator(load_schema("candidate-output"))
        self._parser_output_validator = Draft7Validator(load_schema("parser-output"))
        self._judge_output_validator = Draft7Validator(load_schema("judge-output"))

        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)

        self.state: BenchmarkState | None = None
        self._case_logger: _CaseLogger | None = None

    @classmethod
    def from_config(cls, config: str | Path | dict[str, Any]) -> "Benchmark":
        """Create a Benchmark from a config file (JSON/YAML) or dict.

        Config keys: run_name, output_dir, log_dir, resume, max_consecutive_failures,
        parser (dict with model, instructions, kwargs), judge (dict with model, instructions, kwargs)

        Example: {"parser": {"model": "gpt-5", "kwargs": {"reasoning": {"effort": "low"}}}}
        """
        if isinstance(config, (str, Path)):
            path = Path(config)
            text = path.read_text()
            if path.suffix in (".yaml", ".yml"):
                try:
                    import yaml  # type: ignore[import-untyped]

                    data: dict[str, Any] = yaml.safe_load(text)
                except ImportError:
                    raise ImportError(
                        "pyyaml required for YAML configs: pip install pyyaml"
                    )
            else:
                data = json.loads(text)
        else:
            data = config

        parser_cfg = data.get("parser", {})
        judge_cfg = data.get("judge", {})

        return cls(
            parser_client=OpenAIClient(
                model=parser_cfg.get("model", "gpt-5-mini"),
                model_instructions=parser_cfg.get("instructions"),
                default_kwargs=parser_cfg.get("kwargs", {}),
            ),
            judge_client=OpenAIClient(
                model=judge_cfg.get("model", "gpt-5-mini"),
                model_instructions=judge_cfg.get("instructions"),
                default_kwargs=judge_cfg.get("kwargs", {}),
            ),
            run_name=data.get("run_name"),
            output_dir=data.get("output_dir"),
            log_dir=data.get("log_dir"),
            resume=data.get("resume", False),
            max_consecutive_failures=data.get("max_consecutive_failures", 5),
            judge_ensemble_size=judge_cfg.get("ensemble_size", 5),
        )

    @property
    def running(self) -> bool:
        if not self.state:
            return False
        return self.state.running

    def set_case(self, case: BenchmarkCase) -> bool:
        """Initialize state for a case. Returns False if case should be skipped."""
        if self._case_logger:
            self._case_logger.close()
            self._case_logger = None

        case_id = case.case_id

        # Skip if already completed
        if self.resume and self.run_name and self.output_dir:
            out_path = self._get_output_path(case_id)
            if out_path.exists():
                try:
                    if json.load(out_path.open()).get("status") == CaseStatus.COMPLETED:
                        self.state = None
                        return False
                except (json.JSONDecodeError, OSError) as e:
                    self.logger.warning(f"Cannot read {out_path}, re-running case: {e}")

        # Try to restore from JSONL
        restored = None
        mode = "w"
        if self.resume and self.run_name and self.log_dir:
            restored = self._restore_state_from_jsonl(
                case, self._get_jsonl_path(case_id)
            )
            if restored:
                mode = "a"

        if self.run_name and self.log_dir:
            self._case_logger = _CaseLogger(
                self._get_log_path(case_id), self._get_jsonl_path(case_id), mode
            )

        if restored:
            self.state = restored
            # Ensure system message is present (old logs may lack it)
            if not restored.conversation or restored.conversation[0].get("role") != "system":
                restored.conversation.insert(
                    0, {"role": "system", "content": self.candidate_instructions}
                )
        else:
            self.state = BenchmarkState(case=case)
            self.state.conversation.append(
                {"role": "system", "content": self.candidate_instructions}
            )
            intro = self._format_initial_case_message(case)
            self.state.conversation.append({"role": "user", "content": intro})
            if self._case_logger:
                self._case_logger.log(
                    case_id,
                    1,
                    0,
                    "ENV",
                    intro,
                    event_type=EventType.INITIAL_CASE_PRESENTATION,
                )

        return True

    def create_candidate_prompt(self) -> tuple[list[dict[str, str]], dict]:
        if not self.state:
            raise BenchmarkStateError("No active case. Call set_case first.")
        return list(self.state.conversation), _get_validator_schema(
            self._candidate_validator
        )

    def process_candidate_response(
        self, raw_response: str | MutableMapping[str, object]
    ) -> ProcessOutcome:
        """Process a candidate response and return the outcome."""
        if not self.state:
            raise BenchmarkStateError("No active case. Call set_case first.")

        state = self.state
        before_len = len(state.conversation)
        candidate_text, response_obj = self._parse_candidate_response(raw_response)
        state.conversation.append({"role": "assistant", "content": candidate_text})

        # Capture round number before dispatch — _handle_solve calls
        # _advance_round which increments state.round_number, but the
        # judge evaluation belongs to the current (pre-advance) round.
        eval_round = state.round_number

        if self._case_logger:
            self._case_logger.log(
                state.case.case_id,
                eval_round,
                state.step_index,
                "CANDIDATE",
                candidate_text,
                event_type=EventType.CANDIDATE_RESPONSE,
                raw_payload=response_obj,
            )

        outcome = self._dispatch_response(response_obj)
        self._log_env_responses(before_len, outcome, eval_round)

        if outcome.judge_evaluation and self._case_logger:
            self._case_logger.log(
                state.case.case_id,
                eval_round,
                state.step_index,
                "JUDGE",
                json.dumps(outcome.judge_evaluation, indent=2),
                event_type=EventType.JUDGE_EVALUATION,
                evaluation=outcome.judge_evaluation,
            )

        self._advance_step()
        return outcome

    def _dispatch_response(
        self, response_obj: MutableMapping[str, object] | None
    ) -> ProcessOutcome:
        """Route response to appropriate handler."""
        if response_obj is None:
            return self._handle_invalid(
                "Response must be valid JSON following the required schema."
            )

        try:
            self._candidate_validator.validate(response_obj)
        except ValidationError as exc:
            return self._handle_invalid(
                f"Response failed schema validation: {exc.message}"
            )

        # After validation, we know the structure is valid
        response = cast(dict[str, Any], response_obj["response"])
        action = response["action"]
        if action == "request":
            return self._handle_request(cast(str, response["request"]))
        elif action == "solve":
            return self._handle_solve(
                cast(MutableMapping[str, object], response["solve"])
            )
        else:
            return self._handle_invalid(f"Unrecognized action: '{action}'.")

    def _advance_step(self) -> None:
        if not self.state:
            return
        self.state.step_index += 1

        if not self.state.running:
            self._finalize_case()
        elif self.state.n_consecutive_failures >= self.max_consecutive_failures:
            self.state.running = False
            self._reply("Case cancelled: too many consecutive invalid responses.")
            self._finalize_case()

    def handle_error(self, reason: str) -> ProcessOutcome:
        """Handle external error (e.g. API failure) as candidate failure."""
        return self._handle_invalid(reason)

    def _format_initial_case_message(self, case: BenchmarkCase) -> str:
        p = case.patient
        lines = [
            f"Case {case.case_id}:",
            "Initial presentation:",
            f"- Age: {p.demographics.age}",
            f"- Sex: {p.demographics.sex}",
            f"- Chief complaint: {p.chief_complaint}",
            f"- Vital signs: {p.vital_signs}",
        ]
        if 1 in case.round_guides:
            g = case.round_guides[1]
            lines.extend([f"Setting: {g.setting}", f"Capabilities: {g.capabilities}"])
        lines.append("Provide either a request for a single information item or solve.")
        return "\n".join(lines)

    def _parse_candidate_response(
        self, raw: str | MutableMapping[str, object]
    ) -> tuple[str, MutableMapping[str, object] | None]:
        if isinstance(raw, str):
            try:
                return raw, json.loads(raw)
            except json.JSONDecodeError:
                return raw, None
        if isinstance(raw, MutableMapping):
            return json.dumps(raw), raw
        raise TypeError("Response must be JSON string or mapping")

    def _reply(self, message: str) -> None:
        if not self.state:
            raise BenchmarkStateError("No active case")
        self.state.conversation.append({"role": "user", "content": message})

    def _failure_warning(self) -> str:
        """Return a warning string showing remaining tries before cancellation."""
        s = self.state
        assert s is not None
        remaining = self.max_consecutive_failures - s.n_consecutive_failures
        return f"({remaining} invalid request{'s' if remaining != 1 else ''} remaining before case is cancelled. Consider solving with available information or requesting a different item.)"

    def _handle_invalid(self, reason: str) -> ProcessOutcome:
        if not self.state:
            raise BenchmarkStateError("No active case")
        self.state.n_consecutive_failures += 1
        msg = f"{reason}\n{self._failure_warning()}"
        self._reply(msg)
        return ProcessOutcome(action="invalid", status="invalid_response", message=msg)

    def _fail_request(self, message: str) -> ProcessOutcome:
        if not self.state:
            raise BenchmarkStateError("No active case")
        self.state.n_consecutive_failures += 1
        msg = f"{message}\n{self._failure_warning()}"
        self._reply(msg)
        return ProcessOutcome(
            action="request", status="request_invalid", message=msg
        )

    def _handle_request(self, request_text: str) -> ProcessOutcome:
        if not self.state:
            raise BenchmarkStateError("No active case")
        # Parser response is validated, cast to Dict for type checker
        meta = cast(dict[str, Any], self._call_parser(request_text)["request"])
        fb = str(meta.get("feedback", ""))

        if meta.get(
            "feedback_category"
        ) == FeedbackCategory.SIMILAR_AVAILABLE and meta.get("suggested_item"):
            try:
                s = self.state.case.get_info_item(str(meta["suggested_item"]))
                self.state.n_consecutive_failures += 1
                msg = f"'{request_text}' not available. Try '{s.name}' instead."
                warning = self._failure_warning()
                full = f"{msg}\n{fb}\n{warning}" if fb else f"{msg}\n{warning}"
                self._reply(full)
                return ProcessOutcome(
                    action="request", status="request_guidance", message=msg
                )
            except KeyError:
                pass

        if (
            not meta["valid"]
            or not meta.get("info_item")
            or meta.get("info_item") == "NO_MATCH"
        ):
            msg = f"'{request_text}' not available. Request a specific test or report."
            return self._fail_request(f"{msg}\n{fb}" if fb else msg)

        info_item_name = str(meta["info_item"])
        try:
            item = self.state.case.get_info_item(info_item_name)
        except KeyError:
            return self._fail_request(f"'{info_item_name}' is not part of this case.")

        if item.available_round > self.state.round_number:
            self.state.n_consecutive_failures += 1
            msg = f"'{item.name}' available in round {item.available_round}."
            warning = self._failure_warning()
            full = f"{msg}\n{fb}\n{warning}" if fb else f"{msg}\n{warning}"
            self._reply(full)
            return ProcessOutcome(
                action="request", status="request_pending", released_item=item.name
            )

        if item.name in self.state.released_items:
            self.state.n_consecutive_failures += 1
            msg = f"'{item.name}' already provided."
            self._reply(f"{msg}\n{self._failure_warning()}")
            return ProcessOutcome(
                action="request", status="request_invalid", released_item=item.name
            )

        self._reply(f"{item.name.replace('_', ' ').title()}:\n{item.content}")
        self.state.released_items.add(item.name)
        self.state.n_consecutive_failures = 0
        return ProcessOutcome(
            action="request",
            status="request_released",
            valid=True,
            released_item=item.name,
            released_content=item.content,
        )

    def _call_parser(self, request_text: str) -> MutableMapping[str, object]:
        if not self.state:
            raise BenchmarkStateError("No active case")
        payload = {
            "request": request_text,
            "current_round": self.state.round_number,
            "available": [
                i.to_parser_hint() for i in self.state.case.info_items.values()
            ],
        }
        try:
            response = self.parser_client.generate_json(
                messages=[
                    {"role": "system", "content": self.parser_instructions},
                    {"role": "user", "content": json.dumps(payload)},
                ],
                response_schema=_get_validator_schema(self._parser_output_validator),
            )
            result = response.data
            self._parser_output_validator.validate(result)
            return result
        except ValidationError as e:
            raise ParserError(f"Parser validation failed: {e.message}") from e
        except Exception as e:
            raise ParserError("Parser failed") from e

    def _handle_solve(
        self, solve_payload: MutableMapping[str, object]
    ) -> ProcessOutcome:
        if not self.state:
            raise BenchmarkStateError("No active case")
        result = self._call_judge(solve_payload)
        self.state.round_scores[self.state.round_number] = result
        self.state.n_consecutive_failures = 0
        self._reply(json.dumps(result))
        self._advance_round()
        return ProcessOutcome(
            action="solve",
            status="solve_evaluated",
            valid=True,
            judge_evaluation=result,
        )

    def _call_judge(
        self, solve_payload: MutableMapping[str, object]
    ) -> MutableMapping[str, object]:
        if not self.state:
            raise BenchmarkStateError("No active case")
        if not self.state.case.reference_standard:
            raise BenchmarkStateError("Case has no reference standard")
        try:
            ref = self.state.case.reference_standard.rounds[self.state.round_number]
        except KeyError:
            raise BenchmarkStateError(
                f"No reference standard for round {self.state.round_number}"
            )
        payload = {
            "case_id": self.state.case.case_id,
            "round": self.state.round_number,
            "candidate_response": solve_payload,
            "reference_standard": ref.to_dict(),
        }
        messages = [
            {"role": "system", "content": self.judge_instructions},
            {"role": "user", "content": json.dumps(payload)},
        ]
        schema = _get_validator_schema(self._judge_output_validator)

        def single_judge_call() -> dict[str, Any]:
            response = self.judge_client.generate_json(
                messages=messages, response_schema=schema
            )
            self._judge_output_validator.validate(response.data)
            return cast(dict[str, Any], response.data)

        try:
            if self.judge_ensemble_size <= 1:
                return single_judge_call()

            # Run ensemble in parallel
            evaluations: list[dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=self.judge_ensemble_size) as executor:
                futures = [executor.submit(single_judge_call) for _ in range(self.judge_ensemble_size)]
                for future in as_completed(futures):
                    ev = future.result().get("evaluation", {})
                    evaluations.append(ev)

            aggregated = _aggregate_evaluations(evaluations)
            return {"evaluation": aggregated}
        except ValidationError as e:
            raise JudgeError(f"Judge validation failed: {e.message}") from e
        except Exception as e:
            raise JudgeError("Judge failed") from e

    def _advance_round(self) -> None:
        if not self.state:
            raise BenchmarkStateError("No active case")
        if self.state.round_number >= self.state.case.max_round:
            self.state.running = False
            return
        self.state.round_number += 1
        c = self.state.case
        r = self.state.round_number
        lines = [f"Round {r} begins."]
        if r in c.round_guides:
            lines.extend(
                [
                    f"Setting: {c.round_guides[r].setting}",
                    f"Capabilities: {c.round_guides[r].capabilities}",
                ]
            )
        lines.append("Request additional information or solve.")
        if r >= c.max_round:
            lines.append(
                "Final round - provide definitive diagnosis and treatment plan."
            )
        self._reply("\n".join(lines))

    def _log_env_responses(
        self, before_len: int, outcome: ProcessOutcome, round_number: int | None = None
    ) -> None:
        if not self._case_logger or not self.state:
            return
        s = self.state
        rn = round_number if round_number is not None else s.round_number
        for i in range(before_len + 1, len(s.conversation)):
            if s.conversation[i].get("role") != "assistant":
                self._case_logger.log(
                    s.case.case_id,
                    rn,
                    s.step_index,
                    "ENV",
                    s.conversation[i]["content"],
                    event_type=EventType.ENV_RESPONSE,
                    outcome_action=outcome.action,
                    outcome_status=outcome.status,
                    outcome_released_item=outcome.released_item,
                )

    def _build_path(self, base_dir: Path | None, case_id: int, suffix: str) -> Path:
        if not base_dir or not self.run_name:
            raise BenchmarkStateError("base_dir and run_name required")
        return base_dir / f"{self.run_name}-case{case_id:03d}{suffix}"

    def _get_output_path(self, case_id: int) -> Path:
        return self._build_path(self.output_dir, case_id, "-output.json")

    def _get_log_path(self, case_id: int) -> Path:
        return self._build_path(self.log_dir, case_id, "-conversation.log")

    def _get_jsonl_path(self, case_id: int) -> Path:
        return self._build_path(self.log_dir, case_id, "-conversation.jsonl")

    def _restore_state_from_jsonl(
        self, case: BenchmarkCase, path: Path
    ) -> BenchmarkState | None:
        if not path.exists():
            return None
        state = BenchmarkState(case=case)
        done = False
        try:
            for line in path.read_text().splitlines():
                e = json.loads(line)
                state.round_number = e.get("round_number", state.round_number)
                state.step_index = e.get("step_index", state.step_index)
                et = e.get("event_type")
                if et in (EventType.INITIAL_CASE_PRESENTATION, EventType.ENV_RESPONSE):
                    state.conversation.append({"role": "user", "content": e["content"]})
                    done = True
                    if item := e.get("outcome_released_item"):
                        state.released_items.add(item)
                elif et == EventType.CANDIDATE_RESPONSE:
                    state.conversation.append(
                        {"role": "assistant", "content": e["content"]}
                    )
                    done = False
                elif et == EventType.JUDGE_EVALUATION and e.get("evaluation"):
                    state.round_scores[state.round_number] = e["evaluation"]
                    done = True
            if not state.conversation:
                return None
            if done:
                state.step_index += 1
            return state
        except json.JSONDecodeError as e:
            self.logger.warning(f"Malformed JSONL in {path}: {e}")
            return None
        except OSError as e:
            self.logger.warning(f"Cannot read {path}: {e}")
            return None
        except KeyError as e:
            self.logger.warning(f"Missing required field in {path}: {e}")
            return None

    def _finalize_case(self) -> None:
        if not self.state:
            return
        if self._case_logger:
            self._case_logger.close()
            self._case_logger = None
        if self.run_name and self.output_dir:
            s = self.state
            failed = s.n_consecutive_failures >= self.max_consecutive_failures
            status = CaseStatus.CANCELLED if failed else CaseStatus.COMPLETED
            out = {
                "run_name": self.run_name,
                "case_id": s.case.case_id,
                "case_title": s.case.title,
                "status": status,
                "rounds": s.round_scores,
            }
            self._get_output_path(s.case.case_id).write_text(json.dumps(out, indent=2))
