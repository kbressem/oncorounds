<p align="center">
  <img src="img/oncorounds-wordmark.svg" alt="OncoRounds" width="400">
</p>

# OncoRounds

OncoRounds is an interactive benchmark for evaluating oncology clinical reasoning in large language models. Unlike static benchmarks that present complete case information upfront, OncoRounds simulates the incremental, uncertainty-driven nature of real clinical decision-making.

## Why Interactive Evaluation?

Static benchmarks measure whether models reach correct conclusions, but not whether they employ appropriate reasoning strategies to get there. In practice, physicians start with limited information, iteratively request investigations, and must decide when evidence sufficiently supports clinical action. OncoRounds tests these competencies directly.

## Benchmark Structure

Each case progresses through three clinical rounds:

- **Round 1 (Outpatient Presentation)** — Vital signs, chief complaint, point-of-care tests. Maximal uncertainty, minimal data.
- **Round 2 (Inpatient Workup)** — Imaging, biopsies, specialist consults.
- **Round 3 (Definitive Characterization)** — Full pathology, molecular markers, staging.

Information designated for later rounds remains inaccessible during earlier phases — requests return "pending", mirroring real turnaround times.

### Turn Protocol

Each turn, the model must either:

1. **Request** a specific piece of information (one item per turn, enforcing prioritization)
2. **Solve** with a working diagnosis, differential diagnoses, and treatment plan

## Documentation

- **[Getting Started](getting-started.md)** — Installation and first benchmark run
- **[Running the Benchmark](usage/running-benchmark.md)** — CLI flags, output formats, scoring
- **[LLM Client Integration](usage/llm-clients.md)** — Custom model integration
- **[Architecture](architecture.md)** — System design and extension points
- **[Schema Reference](reference/schemas.md)** — JSON schema specifications
- **[Prompt Templates](reference/prompts.md)** — Candidate, parser, and judge prompts
