"""OncoRounds: Interactive benchmark for LLM clinical reasoning in oncology."""

from .benchmark import Benchmark, BenchmarkState, ProcessOutcome
from .case import (
    BenchmarkCase,
    CaseLoader,
    InfoItem,
    ReferenceStandard,
    RoundReference,
    TreatmentAction,
    load_case,
)
from .clients import (
    ClientResponse,
    JSONModelClient,
    OpenAIClient,
    OpenRouterClient,
)
from .errors import (
    BenchmarkStateError,
    CaseValidationError,
    JudgeError,
    OncoRoundsError,
    ParserError,
)
from .prompts import load_prompt
from .schemas import load_schema
from .scoring import score_run

__all__ = [
    # Core benchmark
    "Benchmark",
    "BenchmarkCase",
    "BenchmarkState",
    "CaseLoader",
    "ProcessOutcome",
    "load_case",
    "score_run",
    # Dataclasses
    "InfoItem",
    "ReferenceStandard",
    "RoundReference",
    "TreatmentAction",
    # Clients
    "ClientResponse",
    "JSONModelClient",
    "OpenAIClient",
    "OpenRouterClient",
    # Errors
    "BenchmarkStateError",
    "CaseValidationError",
    "JudgeError",
    "OncoRoundsError",
    "ParserError",
    # Utilities
    "load_prompt",
    "load_schema",
]
