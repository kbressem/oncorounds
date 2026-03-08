"""LLM client abstractions using OpenRouter for unified model access."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping, Protocol, Sequence

from jsonschema import Draft7Validator

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore


def _validate_response(
    data: MutableMapping[str, Any], schema: Mapping[str, Any]
) -> list[str]:
    """Validate response against schema and return list of error messages."""
    validator = Draft7Validator(schema)
    errors = []
    for error in validator.iter_errors(data):
        path = (
            " -> ".join(str(p) for p in error.absolute_path)
            if error.absolute_path
            else "root"
        )
        errors.append(f"{path}: {error.message}")
    return errors


_MARKDOWN_JSON_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _schema_has_anyof(schema: Mapping[str, Any]) -> bool:
    """Check if a JSON schema contains anyOf/oneOf (unsupported by some providers)."""
    if "anyOf" in schema or "oneOf" in schema:
        return True
    for value in schema.values():
        if isinstance(value, dict) and _schema_has_anyof(value):
            return True
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and _schema_has_anyof(item):
                    return True
    return False


def _strip_markdown_json(text: str) -> str:
    """Strip markdown code blocks from JSON response."""
    match = _MARKDOWN_JSON_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _get_candidate_specific_errors(data: MutableMapping[str, Any]) -> list[str]:
    """Check candidate response for specific known issues."""
    errors = []
    response = data.get("response", {})

    if response.get("action") == "solve":
        solve = response.get("solve", {})
        treatment_plan = solve.get("treatment_plan", [])

        for i, item in enumerate(treatment_plan):
            priority = item.get("priority")
            if priority is not None and priority not in (1, 2, 3):
                errors.append(
                    f"treatment_plan[{i}].priority: value is {priority}, must be 1, 2, or 3"
                )

            intention = item.get("intention")
            allowed = ("therapeutic", "diagnostic", "supportive")
            if intention is not None and intention not in allowed:
                errors.append(
                    f"treatment_plan[{i}].intention: value is '{intention}', must be one of {allowed}"
                )

    return errors


@dataclass
class ClientResponse:
    """Response from an LLM client."""

    data: MutableMapping[str, Any]
    thinking: str | None = None


class JSONModelClient(Protocol):
    """Protocol for JSON-oriented LLM adapters."""

    def generate_json(
        self,
        *,
        messages: Sequence[Mapping[str, str]],
        response_schema: Mapping[str, Any],
        **kwargs: Any,
    ) -> ClientResponse: ...


@dataclass
class OpenRouterClient:
    """OpenRouter client for unified access to 200+ models.

    Uses OpenAI-compatible API. Set OPENROUTER_API_KEY environment variable.

    Model names follow provider/model format:
    - openai/gpt-4o
    - anthropic/claude-sonnet-4
    - google/gemini-2.0-flash-exp
    - deepseek/deepseek-r1
    - meta-llama/llama-3.3-70b-instruct

    See https://openrouter.ai/models for full list.

    Args:
        reasoning_effort: Request reasoning traces from thinking models.
            Options: "xhigh", "high", "medium", "low", "minimal", None (disabled).
            When enabled, reasoning_details are extracted and returned as thinking.
    """

    model: str
    max_retries: int = 1
    reasoning_effort: str | None = "medium"
    default_kwargs: dict[str, Any] = field(default_factory=dict)
    client: Any | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            if OpenAI is None:
                raise RuntimeError("openai package required: pip install openai")
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise RuntimeError("OPENROUTER_API_KEY environment variable required")
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                timeout=120.0,
            )

    def _parse_response(self, message: Any) -> tuple[MutableMapping[str, Any], str | None]:
        """Parse response content and extract thinking if present."""
        raw = message.content or ""
        thinking = None

        # Extract reasoning from OpenRouter response (multiple formats)
        # 1. Simple string attribute (most reliable across providers)
        if hasattr(message, "reasoning") and message.reasoning:
            thinking = message.reasoning

        # 2. Structured reasoning_details list (typed objects)
        if not thinking and hasattr(message, "reasoning_details") and message.reasoning_details:
            thinking_parts = []
            for detail in message.reasoning_details:
                if isinstance(detail, dict):
                    if detail.get("text"):
                        thinking_parts.append(detail["text"])
                elif hasattr(detail, "type"):
                    if detail.type == "reasoning.text" and hasattr(detail, "text"):
                        thinking_parts.append(detail.text)
            if thinking_parts:
                thinking = "\n".join(thinking_parts)

        # 3. DeepSeek legacy format
        if not thinking and hasattr(message, "reasoning_content") and message.reasoning_content:
            thinking = message.reasoning_content

        # Extract thinking from <think> tags (fallback for some models)
        if not thinking and "</think>" in raw:
            parts = raw.split("</think>", 1)
            thinking = parts[0].replace("<think>", "").strip()
            raw = parts[1].strip()

        # Strip markdown code blocks
        raw = _strip_markdown_json(raw)

        return json.loads(raw), thinking

    def generate_json(
        self,
        *,
        messages: Sequence[Mapping[str, str]],
        response_schema: Mapping[str, Any],
        **kwargs: Any,
    ) -> ClientResponse:
        if self.client is None:
            raise RuntimeError("Client not initialized")
        merged_kwargs = {"max_tokens": 16384, **self.default_kwargs, **kwargs}
        msg_list = list(messages)

        # Add reasoning request via extra_body if enabled
        if self.reasoning_effort:
            extra_body = merged_kwargs.get("extra_body", {})
            extra_body["reasoning"] = {"effort": self.reasoning_effort, "enabled": True}
            merged_kwargs["extra_body"] = extra_body

        # When reasoning is enabled, skip response_format entirely — some
        # providers (e.g. Kimi) suppress reasoning traces in structured-output
        # modes.  The prompt already contains JSON examples and post-hoc
        # validation catches schema errors.
        if self.reasoning_effort:
            fmt_kwargs: dict[str, Any] = {}
        elif _schema_has_anyof(response_schema):
            fmt_kwargs = {"response_format": {"type": "json_object"}}
        else:
            fmt_kwargs = {
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "response", "schema": response_schema},
                }
            }

        for attempt in range(self.max_retries + 1):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=msg_list,
                **fmt_kwargs,
                **merged_kwargs,
            )
            message = response.choices[0].message

            try:
                data, thinking = self._parse_response(message)
            except json.JSONDecodeError as e:
                if attempt < self.max_retries:
                    msg_list = list(messages) + [
                        {"role": "user", "content": f"Invalid JSON. Fix: {e}"}
                    ]
                    continue
                raise RuntimeError(f"Invalid JSON after {self.max_retries + 1} attempts") from e

            errors = _get_candidate_specific_errors(data) + _validate_response(data, response_schema)
            if not errors or attempt == self.max_retries:
                return ClientResponse(data=data, thinking=thinking)

            error_msg = "Schema errors:\n" + "\n".join(f"- {e}" for e in errors[:5])
            msg_list = list(messages) + [
                {"role": "assistant", "content": json.dumps(data)},
                {"role": "user", "content": f"{error_msg}\n\nFix and retry."},
            ]

        raise RuntimeError("No response generated")


@dataclass
class OpenAIClient:
    """Direct OpenAI client using the Responses API.

    Use this for parser/judge models if you want to use OpenAI directly
    instead of through OpenRouter.
    """

    model: str
    model_instructions: str | None = None
    default_kwargs: dict[str, Any] = field(default_factory=dict)
    client: Any | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            if OpenAI is None:
                raise RuntimeError("openai package required: pip install openai")
            self.client = OpenAI()

    def generate_json(
        self,
        *,
        messages: Sequence[Mapping[str, str]],
        response_schema: Mapping[str, Any],
        **kwargs: Any,
    ) -> ClientResponse:
        if self.client is None:
            raise RuntimeError("Client not initialized")
        response = self.client.responses.create(
            model=self.model,
            instructions=self.model_instructions,
            input=list(messages),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "structured_response",
                    "schema": response_schema,
                    "strict": True,
                }
            },
            **{**self.default_kwargs, **kwargs},
        )

        # Extract structured output from Responses API
        for part in response.output:
            if part.content is None:
                continue
            for chunk in part.content:
                if chunk.type == "output_json":
                    data = chunk.json
                    if isinstance(data, Mapping):
                        return ClientResponse(data=dict(data))
                    if isinstance(data, str):
                        return ClientResponse(data=json.loads(data))

        # Fallback to raw text
        if not response.output_text:
            raise RuntimeError(f"No JSON in response: {str(response)[:500]}")
        return ClientResponse(data=json.loads(response.output_text))
