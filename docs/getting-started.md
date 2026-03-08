# Getting Started

## Requirements

- **Python 3.10+**
- **OpenRouter API key** — Get one at [openrouter.ai](https://openrouter.ai)

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate  # On Windows

pip install -e .[dev]
```

For local documentation: `pip install -e .[dev,docs]`

## Verify Installation

```bash
pytest
```

OpenAI integration tests are skipped without an `OPENAI_API_KEY` environment variable.

## Run the Benchmark

```bash
export OPENROUTER_API_KEY="your-key-here"
python examples/run_benchmark.py --model anthropic/claude-sonnet-4-6 --case 1
```

Use `--case 1` for a quick smoke test. Omit it to run all cases. Any [OpenRouter model](https://openrouter.ai/models) works:

```bash
python examples/run_benchmark.py --model openai/gpt-5.2-2025-12-11 --case 1
python examples/run_benchmark.py --model deepseek/deepseek-v3.2 --case 1
```

## Programmatic Usage

```python
from oncorounds import Benchmark, CaseLoader, OpenRouterClient

benchmark = Benchmark.from_config("config.json")
candidate = OpenRouterClient(model="anthropic/claude-sonnet-4-6")

for case in CaseLoader("cases"):
    benchmark.set_case(case)

    while benchmark.running:
        messages, schema = benchmark.create_candidate_prompt()
        response = candidate.generate_json(messages=messages, response_schema=schema)
        benchmark.process_candidate_response(response.data)
```

Implement `JSONModelClient` to integrate any model — see [LLM Client Integration](usage/llm-clients.md).
