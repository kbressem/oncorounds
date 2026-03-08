# Leaderboard

Results on 20 oncology cases (higher is better). Last updated: 2026-03-08.

| Rank | Model | Provider | Overall | Diagnosis | Differentials | Treatment |
|-----:|-------|----------|--------:|----------:|--------------:|----------:|
| 1 | Claude Opus 4.6 | Anthropic | **68.1%** | 84.2% | 55.2% | 65.1% |
| 2 | MiniMax M2.1 | MiniMax | 66.3% | 72.5% | 61.4% | 65.0% |
| 3 | Claude Opus 4.5 | Anthropic | 64.9% | 81.7% | 49.8% | 63.2% |
| 4 | Claude Sonnet 4.6 | Anthropic | 64.8% | 77.5% | 51.8% | 65.2% |
| 5 | MiniMax M2.5 | MiniMax | 64.3% | 72.5% | 57.7% | 62.8% |
| 6 | Claude Sonnet 4.5 | Anthropic | 63.8% | 72.8% | 51.9% | 66.8% |
| 7 | GPT-5.2 Reasoning | OpenAI | 62.3% | 76.3% | 47.3% | 63.3% |
| 8 | Claude Haiku 4.5 | Anthropic | 62.2% | 67.5% | 54.1% | 65.1% |
| 9 | GPT-5.2 Instant | OpenAI | 62.1% | 78.3% | 46.5% | 61.4% |
| 10 | GPT-5 Mini | OpenAI | 61.2% | 65.4% | 47.5% | 70.7% |
| 11 | Kimi K2.5 | Moonshot | 60.9% | 70.8% | 50.1% | 61.7% |
| 12 | Kimi K2 Thinking | Moonshot | 59.0% | 60.0% | 52.2% | 64.7% |
| 13 | Gemini 3 Pro | Google | 58.8% | 69.2% | 46.4% | 60.8% |
| 14 | GLM 5 | Zhipu | 58.6% | 70.0% | 45.8% | 59.9% |
| 15 | Grok 4 | xAI | 58.4% | 74.2% | 39.2% | 61.8% |
| 16 | GPT-4.1 | OpenAI | 58.1% | 72.5% | 45.0% | 56.9% |
| 17 | Gemini 3 Flash | Google | 57.4% | 63.3% | 53.3% | 55.5% |
| 18 | DeepSeek V3.2 Speciale | DeepSeek | 57.1% | 70.0% | 38.9% | 62.4% |
| 19 | GPT-OSS 120B | OpenAI | 56.4% | 71.7% | 40.6% | 56.9% |
| 20 | DeepSeek V3.2 | DeepSeek | 55.9% | 70.0% | 43.3% | 54.5% |
| 21 | Grok 4.1 Fast | xAI | 55.0% | 67.5% | 39.1% | 58.5% |
| 22 | GPT-5 Nano | OpenAI | 54.9% | 57.9% | 47.9% | 58.8% |
| 23 | Gemini 3.1 Pro | Google | 54.8% | 61.4% | 42.9% | 60.1% |
| 24 | Mistral 3 Large | Mistral | 51.1% | 54.2% | 36.9% | 62.2% |
| 25 | GLM 4.7 | Zhipu | 50.3% | 65.8% | 31.8% | 53.2% |
| 26 | GPT-OSS 20B | OpenAI | 50.0% | 64.2% | 33.6% | 52.1% |
| 27 | Qwen3 Max | Alibaba | 49.8% | 56.7% | 38.4% | 54.2% |
| 28 | Arcee Trinity | Arcee | 46.9% | 58.3% | 32.4% | 49.9% |
| 29 | Qwen3 235B A22B | Alibaba | 45.6% | 50.8% | 35.9% | 49.9% |
| 30 | Mistral 3.1 Medium | Mistral | 42.7% | 49.2% | 27.4% | 51.6% |
| 31 | Qwen3 Next 80B | Alibaba | 40.9% | 48.3% | 30.1% | 44.3% |
| 32 | Llama 3.3 70B | Meta | 40.2% | 56.7% | 20.8% | 43.1% |

## Submit Results

Run the benchmark on your model:

```bash
pip install oncorounds
python examples/run_benchmark.py --model your-model-name
oncorounds-score --outputs-dir outputs --case-dir cases
```

Then [submit your results](https://github.com/kbressem/oncorounds/edit/main/docs/leaderboard/data.json) via pull request.
