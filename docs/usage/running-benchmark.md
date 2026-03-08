# Running the Benchmark

The benchmark orchestrates a turn-based conversation between three actors:

1. **Candidate** – produces the JSON response for each turn.
2. **Parser client** – maps natural-language requests to canonical information item names.
3. **Judge client** – scores solve payloads against expert references.

The `Benchmark` class coordinates these actors and enforces the interaction protocol.

## Quick Start

```bash
# Set your OpenRouter API key
export OPENROUTER_API_KEY="your-key-here"

# Run benchmark with any model
python examples/run_benchmark.py --model anthropic/claude-sonnet-4-6 --case 1
```

## Using the Example Script

The `examples/run_benchmark.py` script provides a complete benchmark runner using [OpenRouter](https://openrouter.ai) for unified model access.

```bash
# Run a single case (smoke test)
python examples/run_benchmark.py --model openai/gpt-5.2-2025-12-11 --case 1

# Run all cases
python examples/run_benchmark.py --model deepseek/deepseek-v3.2

# Use a custom config
python examples/run_benchmark.py --model meta-llama/llama-3.3-70b-instruct-turbo --config my-config.json
```

The config file (`examples/config.json`) specifies:

```json
{
  "run_name": "example-run",
  "output_dir": "outputs",
  "log_dir": "logs",
  "resume": true,
  "parser": {"model": "gpt-5-mini"},
  "judge": {"model": "gpt-5-mini", "ensemble_size": 5}
}
```

Key flags:

- `--model` – OpenRouter model name (e.g., `anthropic/claude-sonnet-4-6-6`, `openai/gpt-5.2-2025-12-11`).
- `--config` – path to config JSON file (default: `examples/config.json`).
- `--case-dir` – directory containing case definition JSON (`case-*.json`).
- `--case <ID>` – run only a specific case ID (e.g., `--case 1` for smoke testing).
- `--run-name` – override the run name (default: model name with `/` replaced by `-`).
- `--reasoning-effort` – reasoning effort level (default: `medium`).
- `--provider` – OpenRouter provider slug (e.g., `together`, `deepinfra`).

## Conversation artifacts

For each case the runner records:

- `logs/<run-name>-case<ID>-conversation.jsonl` – full transcript in JSON Lines format.
- `outputs/<run-name>-case<ID>.json` – structured summary of judge evaluations per round.

## Scoring Results

After running the benchmark, use the built-in scoring command to compute aggregate metrics:

```bash
oncorounds-score --outputs-dir outputs --case-dir cases --log-dir logs
```

This produces a summary with:

- Per-case scores and completion status
- Dimension-level accuracy (working diagnosis, differentials, treatment action/intention/priority)
- Efficiency metrics (requests per case, valid/invalid ratios)

For JSON output suitable for further processing:

```bash
oncorounds-score --outputs-dir outputs --case-dir cases --json
```

You can also use the scoring API programmatically:

```python
from oncorounds import score_run

result = score_run(
    outputs_dir="outputs",
    case_dir="cases",
    log_dir="logs",
    run_name="demo",  # optional filter
)
print(f"Overall accuracy: {result['totals']['accuracy']:.1f}%")
```
