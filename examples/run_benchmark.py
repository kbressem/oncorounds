"""OncoRounds benchmark runner using OpenRouter.

Usage:
    python examples/run_benchmark.py --model anthropic/claude-sonnet-4
    python examples/run_benchmark.py --model openai/gpt-5.2 --case 1
    python examples/run_benchmark.py --model deepseek/deepseek-v3.2

Set OPENROUTER_API_KEY environment variable before running.
See https://openrouter.ai/models for available models.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

from oncorounds import Benchmark, CaseLoader, OpenRouterClient, load_prompt

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(description="OncoRounds benchmark runner.")
    parser.add_argument("--model", required=True, help="Model name (e.g., anthropic/claude-sonnet-4-6)")
    parser.add_argument("--config", default="examples/config.json", help="Path to config file")
    parser.add_argument("--case-dir", default="cases", help="Directory with case JSON files")
    parser.add_argument("--case", type=int, help="Run only this case ID")
    parser.add_argument("--provider", help="OpenRouter provider slug (e.g., together, deepinfra)")
    parser.add_argument("--run-name", help="Override run name (default: model name with / replaced by -)")
    parser.add_argument("--reasoning-effort", default="medium", help="Reasoning effort level (default: medium)")
    args = parser.parse_args()

    # Load config and set up output directories
    config = json.loads(Path(args.config).read_text())
    model_name = args.run_name or args.model.replace("/", "-")
    config["run_name"] = model_name
    config["output_dir"] = f"outputs/{model_name}"
    config["log_dir"] = f"logs/{model_name}"

    # Initialize benchmark and candidate model
    benchmark = Benchmark.from_config(config)
    client_kwargs: dict = {}
    if args.provider:
        client_kwargs["default_kwargs"] = {
            "extra_body": {"provider": {"order": [args.provider]}}
        }
    candidate = OpenRouterClient(model=args.model, reasoning_effort=args.reasoning_effort, **client_kwargs)

    # Load cases
    cases = list(CaseLoader(args.case_dir))
    if args.case is not None:
        cases = [c for c in cases if c.case_id == args.case]
        if not cases:
            raise SystemExit(f"Case {args.case} not found.")

    # Optional: log thinking traces
    thinking_log_dir = Path(config["log_dir"])
    thinking_log_dir.mkdir(parents=True, exist_ok=True)
    thinking_log = (thinking_log_dir / f"{model_name}-thinking.jsonl").open("a", encoding="utf-8")

    # Run benchmark
    pbar = tqdm(cases, desc="Cases", unit="case")
    for case in pbar:
        pbar.set_postfix(case=case.case_id, round=1)
        if not benchmark.set_case(case):
            continue

        while benchmark.running:
            round_num = benchmark.state.round_number if benchmark.state else 1
            pbar.set_postfix(case=case.case_id, round=round_num)

            try:
                messages, schema = benchmark.create_candidate_prompt()
                response = candidate.generate_json(messages=messages, response_schema=schema)

                # Log thinking if present
                if response.thinking:
                    entry = {
                        "case_id": case.case_id,
                        "round": round_num,
                        "step": benchmark.state.step_index if benchmark.state else 0,
                        "thinking": response.thinking,
                    }
                    thinking_log.write(json.dumps(entry) + "\n")
                    thinking_log.flush()

                benchmark.process_candidate_response(response.data)
            except Exception as e:
                benchmark.handle_error(str(e))

    thinking_log.close()
    print(f"Done. Run: oncorounds-score --outputs-dir outputs/{model_name} --case-dir cases")


if __name__ == "__main__":
    main()
