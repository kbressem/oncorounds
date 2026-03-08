# Integrating LLM Clients

OncoRounds uses a simple protocol-based design that makes it easy to integrate any language model. You can use the built-in OpenRouter client for quick access to 200+ models, or implement your own client for custom inference servers.

## Custom Client Implementation

Implement the `JSONModelClient` protocol to integrate any model:

```python
from oncorounds import JSONModelClient, ClientResponse, Benchmark, CaseLoader

class MyCustomClient:
    """Custom client for your inference server."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def generate_json(
        self,
        *,
        messages: list[dict[str, str]],
        response_schema: dict,
        **kwargs
    ) -> ClientResponse:
        # Call your API
        result = call_your_api(self.endpoint, messages, response_schema)
        return ClientResponse(data=result)

# Use with the benchmark
benchmark = Benchmark.from_config("config.json")
candidate = MyCustomClient(endpoint="http://localhost:8000/v1/chat")

for case in CaseLoader("cases"):
    benchmark.set_case(case)
    while benchmark.running:
        messages, schema = benchmark.create_candidate_prompt()
        response = candidate.generate_json(messages=messages, response_schema=schema)
        benchmark.process_candidate_response(response.data)
```

The protocol requires a single method:

```python
def generate_json(
    self,
    *,
    messages: Sequence[Mapping[str, str]],
    response_schema: Mapping[str, Any],
    **kwargs
) -> ClientResponse:
    """Accept chat messages and JSON schema, return conforming response."""
```

## OpenRouter (Recommended for Quick Start)

[OpenRouter](https://openrouter.ai) provides unified access to 200+ models from all major providers through a single API.

### Setup

1. Get an API key at [openrouter.ai](https://openrouter.ai)
2. Set the environment variable:

```bash
export OPENROUTER_API_KEY="your-key-here"
```

### Usage

```python
from oncorounds import OpenRouterClient

# Any model from openrouter.ai/models
client = OpenRouterClient(model="anthropic/claude-sonnet-4-6")

response = client.generate_json(
    messages=[{"role": "user", "content": "What is the diagnosis?"}],
    response_schema={"type": "object", "properties": {"diagnosis": {"type": "string"}}}
)
```

### Available Models

| Provider | Example Models |
|----------|---------------|
| Anthropic | `anthropic/claude-opus-4-6`, `anthropic/claude-sonnet-4-6-6`, `anthropic/claude-haiku-4-5-20251001` |
| OpenAI | `openai/gpt-5.2-2025-12-11`, `openai/gpt-5-2025-08-07`, `openai/gpt-4.1-2025-04-14` |
| Google | `google/gemini-3-pro-preview`, `google/gemini-3-flash-preview` |
| DeepSeek | `deepseek/deepseek-v3.2`, `deepseek/deepseek-v3.2-speciale` |
| Moonshot | `moonshot/kimi-2.5`, `moonshot/kimi-k2` |
| MiniMax | `minimax/minimax-m2p1`, `minimax/minimax-m2.5` |
| xAI | `x-ai/grok-4-0709`, `x-ai/grok-4-1-fast-non-reasoning` |
| Mistral | `mistralai/mistral-large-2512`, `mistralai/mistral-medium-3.1` |
| Meta | `meta-llama/llama-3.3-70b-instruct-turbo` |

See [openrouter.ai/models](https://openrouter.ai/models) for the complete list.

## Direct OpenAI Access

For parser/judge models, you may want to use OpenAI directly (without OpenRouter overhead):

```python
from oncorounds import OpenAIClient

client = OpenAIClient(model="gpt-5-mini")
```

This uses the OpenAI Responses API directly and requires `OPENAI_API_KEY`.
