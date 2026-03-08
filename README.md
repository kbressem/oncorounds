<p align="center">
  <img src="img/oncorounds-wordmark.svg" alt="OncoRounds" width="400">
</p>

<p align="center">
  <strong>Interactive benchmark for evaluating LLM clinical reasoning in oncology</strong>
</p>

<p align="center">
  <a href="https://github.com/kbressem/oncorounds/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"></a>
</p>

---

## Overview

OncoRounds evaluates how well language models handle the uncertainty and sequential decision-making inherent in clinical oncology. Unlike static benchmarks that present complete case information upfront, OncoRounds simulates real diagnostic workflows where information must be actively requested and synthesized across three clinical rounds.

**Key insight:** Clinical reasoning isn't just about reaching the right diagnosis—it's about knowing what information to gather, when to act, and how to manage uncertainty along the way.

## How It Works

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Candidate LLM  │────▶│     Parser      │────▶│     Judge       │
│  (under test)   │     │  (maps requests │     │  (scores solve  │
│                 │     │   to info items)│     │   attempts)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

Each case progresses through **three clinical rounds**:

| Round | Setting | Available Information |
|-------|---------|----------------------|
| **1** | Initial Presentation | Vitals, chief complaint, point-of-care tests |
| **2** | Inpatient Workup | Imaging, biopsies, specialist consults |
| **3** | Definitive | Full pathology, molecular markers, staging |

At each turn, the model must either:

- **Request** a specific piece of information (one item per turn)
- **Solve** by providing diagnosis, differentials, and treatment plan

## Features

- **Round-based progression** with staged information release
- **Structured JSON schemas** for reproducible evaluation
- **200+ models** via [OpenRouter](https://openrouter.ai) (OpenAI, Anthropic, Google, Meta, DeepSeek, etc.)
- **Automated scoring** across diagnosis accuracy, differential quality, and treatment appropriateness
- **Resume capability** for interrupted runs

## Quick Start

```bash
# Setup
pip install oncorounds
export OPENROUTER_API_KEY="your-key-here"  # Get one at openrouter.ai

# Run benchmark
python examples/run_benchmark.py --model anthropic/claude-sonnet-4-6 --case 1

# Score results
oncorounds-score --outputs-dir outputs --case-dir cases
```

## Usage

```python
from oncorounds import Benchmark, CaseLoader, OpenRouterClient

# Initialize benchmark and model
benchmark = Benchmark.from_config("config.json")
candidate = OpenRouterClient(model="anthropic/claude-sonnet-4-6")

# Evaluation loop
for case in CaseLoader("cases"):
    benchmark.set_case(case)

    while benchmark.running:
        messages, schema = benchmark.create_candidate_prompt()
        response = candidate.generate_json(messages=messages, response_schema=schema)
        benchmark.process_candidate_response(response.data)

```
See examples/run_benchmark.py for a complete implementation with progress bars and logging.

## Leaderboard

Results on 20 oncology cases (higher is better). Scored with `oncorounds-score`.

| Rank | Model | Params | Provider | Overall | Diagnosis | Differentials | Treatment |
|-----:|-------|-------:|----------|--------:|----------:|--------------:|----------:|
| 1 | Claude Opus 4.6 | — | Anthropic | **68.1%** | 84.2% | 55.2% | 65.1% |
| 2 | [MiniMax M2.1](https://huggingface.co/MiniMaxAI/MiniMax-M2.1) | 230B / A10B | MiniMax | 66.3% | 72.5% | 61.4% | 65.0% |
| 3 | Claude Opus 4.5 | — | Anthropic | 64.9% | 81.7% | 49.8% | 63.2% |
| 4 | Claude Sonnet 4.6 | — | Anthropic | 64.8% | 77.5% | 51.8% | 65.2% |
| 5 | [MiniMax M2.5](https://huggingface.co/MiniMaxAI/MiniMax-M2.5) | 230B / A10B | MiniMax | 64.3% | 72.5% | 57.7% | 62.8% |
| 6 | Claude Sonnet 4.5 | — | Anthropic | 63.8% | 72.8% | 51.9% | 66.8% |
| 7 | GPT-5.2 Reasoning | — | OpenAI | 62.3% | 76.3% | 47.3% | 63.3% |
| 8 | Claude Haiku 4.5 | — | Anthropic | 62.2% | 67.5% | 54.1% | 65.1% |
| 9 | GPT-5.2 Instant | — | OpenAI | 62.1% | 78.3% | 46.5% | 61.4% |
| 10 | GPT-5 Mini | — | OpenAI | 61.2% | 65.4% | 47.5% | 70.7% |
| 11 | [Kimi K2.5](https://huggingface.co/moonshotai/Kimi-K2.5) | 1T / A32B | Moonshot | 60.9% | 70.8% | 50.1% | 61.7% |
| 12 | [Kimi K2 Thinking](https://huggingface.co/moonshotai/Kimi-K2-thinking) | 1T / A32B | Moonshot | 59.0% | 60.0% | 52.2% | 64.7% |
| 13 | Gemini 3 Pro | — | Google | 58.8% | 69.2% | 46.4% | 60.8% |
| 14 | [GLM 5](https://huggingface.co/zai-org/GLM-5) | 744B / A40B | Zhipu | 58.6% | 70.0% | 45.8% | 59.9% |
| 15 | Grok 4 | — | xAI | 58.4% | 74.2% | 39.2% | 61.8% |
| 16 | GPT-4.1 | — | OpenAI | 58.1% | 72.5% | 45.0% | 56.9% |
| 17 | Gemini 3 Flash | — | Google | 57.4% | 63.3% | 53.3% | 55.5% |
| 18 | [DeepSeek V3.2 Speciale](https://huggingface.co/deepseek-ai/DeepSeek-V3.2-Speciale) | 685B / A37B | DeepSeek | 57.1% | 70.0% | 38.9% | 62.4% |
| 19 | [GPT-OSS 120B](https://huggingface.co/openai/gpt-oss-120b) | 120B | OpenAI | 56.4% | 71.7% | 40.6% | 56.9% |
| 20 | [DeepSeek V3.2](https://huggingface.co/deepseek-ai/DeepSeek-V3.2) | 685B / A37B | DeepSeek | 55.9% | 70.0% | 43.3% | 54.5% |
| 21 | Grok 4.1 Fast | — | xAI | 55.0% | 67.5% | 39.1% | 58.5% |
| 22 | GPT-5 Nano | — | OpenAI | 54.9% | 57.9% | 47.9% | 58.8% |
| 23 | Gemini 3.1 Pro | — | Google | 54.8% | 61.4% | 42.9% | 60.1% |
| 24 | [Mistral 3 Large](https://huggingface.co/mistralai/Mistral-Large-3-675B-Instruct-2512) | 675B / A41B | Mistral | 51.1% | 54.2% | 36.9% | 62.2% |
| 25 | [GLM 4.7](https://huggingface.co/zai-org/GLM-4.7) | 357B / A32B | Zhipu | 50.3% | 65.8% | 31.8% | 53.2% |
| 26 | [GPT-OSS 20B](https://huggingface.co/openai/gpt-oss-20b) | 20B | OpenAI | 50.0% | 64.2% | 33.6% | 52.1% |
| 27 | Qwen3 Max | ~1T (MoE) | Alibaba | 49.8% | 56.7% | 38.4% | 54.2% |
| 28 | [Arcee Trinity](https://huggingface.co/arcee-ai/Trinity-Large-Preview) | 398B / A13B | Arcee | 46.9% | 58.3% | 32.4% | 49.9% |
| 29 | [Qwen3 235B A22B](https://huggingface.co/Qwen/Qwen3-235B-A22B-Instruct) | 235B / A22B | Alibaba | 45.6% | 50.8% | 35.9% | 49.9% |
| 30 | Mistral 3.1 Medium | — | Mistral | 42.7% | 49.2% | 27.4% | 51.6% |
| 31 | [Qwen3 Next 80B](https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Thinking) | 80B / A3B | Alibaba | 40.9% | 48.3% | 30.1% | 44.3% |
| 32 | [Llama 3.3 70B](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct) | 70B | Meta | 40.2% | 56.7% | 20.8% | 43.1% |

## Scoring

OncoRounds evaluates across multiple dimensions:

| Dimension | Description |
|-----------|-------------|
| Working Diagnosis | Primary diagnostic accuracy |
| Differentials | Quality and appropriateness of differential diagnoses |
| Treatment Action | Correctness of proposed interventions |
| Treatment Intention | Appropriate categorization (diagnostic/therapeutic/supportive) |
| Treatment Priority | Correct urgency ranking |

```bash
oncorounds-score --outputs-dir outputs --case-dir cases
```

## Supported Models

Any model on [OpenRouter](https://openrouter.ai/models), including:

| Provider | Models |
|----------|--------|
| Anthropic | `anthropic/claude-opus-4-6`, `anthropic/claude-sonnet-4-6-6`, `anthropic/claude-haiku-4-5-20251001` |
| OpenAI | `openai/gpt-5.2-2025-12-11`, `openai/gpt-5-2025-08-07`, `openai/gpt-4.1-2025-04-14` |
| Google | `google/gemini-3-pro-preview`, `google/gemini-3-flash-preview`, `google/gemini-3.1-pro-preview` |
| DeepSeek | `deepseek/deepseek-v3.2`, `deepseek/deepseek-v3.2-speciale` |
| Moonshot | `moonshot/kimi-2.5`, `moonshot/kimi-k2` |
| MiniMax | `minimax/minimax-m2p1`, `minimax/minimax-m2.5` |
| xAI | `x-ai/grok-4-0709`, `x-ai/grok-4-1-fast-non-reasoning` |
| Zhipu | `zhipu/glm-5`, `zhipu/glm-4.7` |
| Mistral | `mistralai/mistral-large-2512`, `mistralai/mistral-medium-3.1` |
| Alibaba | `qwen/qwen3-max`, `qwen/qwen3-next-80b-a3b` |
| Meta | `meta-llama/llama-3.3-70b-instruct-turbo` |

## Documentation

- [Getting Started](https://kbressem.github.io/oncorounds/getting-started/)
- [Running the Benchmark](https://kbressem.github.io/oncorounds/usage/running-benchmark/)
- [Architecture](https://kbressem.github.io/oncorounds/architecture/)

## License

MIT License - see [LICENSE](LICENSE) for details.
