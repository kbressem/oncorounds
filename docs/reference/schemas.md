# Schemas

All interactions in the benchmark are mediated through JSON schemas stored in [`schemas/`](https://github.com/kbressem/oncorounds/blob/main/schemas). They provide a strict contract between the candidate, parser, judge, and the benchmark engine.

## Candidate turn schemas

| File | Purpose |
| --- | --- |
| [`candidate-output.json`](https://github.com/kbressem/oncorounds/blob/main/schemas/candidate-output.json) | Unified schema for all turns. Uses `anyOf` to allow either a `request` action (with a query string) or a `solve` action (with diagnosis and plan). |

The benchmark uses this single schema for every turn, allowing the model to dynamically choose between requesting information or solving the case.

## Supporting schemas

| File | Purpose |
| --- | --- |
| [`parser-output.json`](https://github.com/kbressem/oncorounds/blob/main/schemas/parser-output.json) | Output contract for the parser client. Reports `valid` and the canonical `info_item` when a request is understood. |
| [`judge-output.json`](https://github.com/kbressem/oncorounds/blob/main/schemas/judge-output.json) | Output contract for the judge client. Scores working diagnosis, differentials, treatment plan entries, and key findings. |
| [`case.json`](https://github.com/kbressem/oncorounds/blob/main/schemas/case.json) | Case definition schema. Enforces three rounds, staged info items, and reference standards. |

Each schema is annotated with descriptions and constraints. When extending the benchmark, update the schema first, then regenerate or adjust the prompts, tests, and documentation to match.
