"""Custom exception types for the OncoRounds benchmark package."""


class OncoRoundsError(Exception):
    """Base exception for the package."""


class CaseValidationError(OncoRoundsError):
    """Raised when a benchmark case fails schema validation."""


class ParserError(OncoRoundsError):
    """Raised when the request parser response is invalid or unusable."""


class JudgeError(OncoRoundsError):
    """Raised when the judge output cannot be interpreted."""


class BenchmarkStateError(OncoRoundsError):
    """Raised when the benchmark state machine encounters an invalid transition."""
