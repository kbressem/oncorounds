# Prompt Templates

Prompt templates live in [`prompts/`](https://github.com/kbressem/oncorounds/prompts). They provide high-level instructions for each model role and can be customised to adapt to different backends or safety requirements.

| File | Role | Notes |
| --- | --- | --- |
| [`candidate-instructions.md`](https://github.com/kbressem/oncorounds/prompts/candidate-instructions.md) | Candidate | Explains the turn structure and sets behavioural expectations. |
| [`parser-instructions.md`](https://github.com/kbressem/oncorounds/prompts/parser-instructions.md) | Parser | Instructs the parser to map natural-language requests to one of the available info item keys and mark validity. |
| [`judge-instructions.md`](https://github.com/kbressem/oncorounds/prompts/judge-instructions.md) | Judge | Guides the judge through scoring each component of the solve payload against the reference for the current round. |

When modifying prompts:

1. Keep the JSON schema descriptions in sync so models receive consistent instructions.
2. Update the tests if the new prompt semantics change expected behaviour (for example, how invalid requests are handled).
3. Consider versioning prompts if you plan to compare runs across different instruction sets.
