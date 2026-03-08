# Architecture

The OncoRounds benchmark implements a lightweight state machine that orchestrates interactions between three language model actors (candidate, parser, judge) while enforcing the turn-based evaluation protocol.

## Module Organization

### `oncorounds.case`

This module manages all case-related data operations:

- Discovery of case files matching the pattern `case-*.json` within specified directories
- Validation of case definitions against the `case.json` schema
- Exposure of dataclasses (`BenchmarkCase`, `InfoItem`, `RoundReference`, `ReferenceStandard`)
- Iteration via `CaseLoader(directory)` returning all valid case instances

### `oncorounds.benchmark`

This module constitutes the system's core functionality. The `Benchmark` class coordinates:

- **Conversation state management**: Tracking all message exchanges with the candidate model
- **Round progression control**: Determining information availability at each evaluation stage
- **Schema enforcement**: Enforcing the `candidate-output` schema which uses `anyOf` logic to handle both requests and solutions in a single turn
- **Parser invocation**: Disambiguating candidates natural language requests via parser model
- **Judge invocation**: Evaluating solve attempts against reference standards
- **Error handling**: Managing schema validation failures and implementing case cancellation thresholds

**Principal methods:**

- `set_case(case)`: Initializes conversation with case presentation, resets evaluation state
- `create_candidate_prompt()`: Returns current conversation history and the `candidate-output` schema
- `process_candidate_response(payload)`: Validates response, interprets content, advances state

### `oncorounds.clients`

The `JSONModelClient` protocol specifies a singular method:

```python
def generate_json(messages: list, schema: dict) -> ClientResponse:
    """Accept chat messages and JSON schema, return conforming response"""
```

Two implementations are provided:

- **`OpenRouterClient`** – Primary client providing unified access to 200+ models via [OpenRouter](https://openrouter.ai). Supports OpenAI, Anthropic, Google, Meta, DeepSeek, and more through a single API.
- **`OpenAIClient`** – Direct OpenAI client using the Responses API, useful for parser/judge models if you want to avoid OpenRouter.

The minimal interface accommodates custom implementations for open-source inference servers (vLLM, TGI, LlamaCpp) or sophisticated workflows such as retrieval-augmented generation pipelines.

### `oncorounds.prompts`

Three markdown files within `prompts/` define behavioral specifications for each actor:

- `candidate-instructions.md`: Specifies turn structure requirements and evidence-grounding expectations
- `parser-instructions.md`: Directs request-to-item mapping procedures
- `judge-instructions.md`: Defines evaluation criteria for solve attempt scoring

This module provides file loading functionality, making templates accessible to the benchmark.

### `oncorounds.schemas`

Provides `load_schema(name)` functionality to retrieve schemas from the `schemas/` directory. These schemas enforce response formats for:

- Candidate outputs (response)
- Parser outputs
- Judge evaluation structures
- Case definitions

Parser and judge outputs are enforced via structured output mode (JSON schema) during generation. Candidate responses use the same mechanism to ensure valid JSON. Schema violations increment the failure counter and may trigger case cancellation if thresholds are exceeded.

## How a Case Progresses

### 1. Initialization: `set_case(case)`

The benchmark receives a `Case` object and:

- Extracts the initial presentation (patient demographics, chief complaint, vitals)
- Creates a first message with the initial clinical scenario
- Resets all state (conversation, released items, turn counter, round scores)
- Sets current round to 1

At this point The candidate sees only the minimal information from Round 1.

### 2. Candidate Turn: `create_candidate_prompt()`

The benchmark constructs the prompt for the candidate:

- Returns the full conversation history so far
- Includes the `candidate-output.json` schema which defines the structure for both requests and solutions using `anyOf` logic.

The schema guides the model to either request information or solve the case in a single turn.
It is crucial the candidate adheres to this schema.

### 3. Response Processing: `process_candidate_response(payload)`

When the candidate returns JSON, the benchmark:

1. Validates the payload against the `candidate-output` schema
   - If invalid: logs error, increments failure counter, may cancel case
   - If valid: continues

2. Routes based on action in `response`:
   - `action: "request"` → `_handle_request()`
   - `action: "solve"` → `_handle_solve()`

### 4a. Request Path: `_handle_request(payload)`

The candidate wants more information:

1. Extract the request text from the `response.request` field
2. Send the request text + metadata about available items to the parser client
3. Check availability:
   - If the requested `info_item` is available in current round: release it (add content to conversation)
   - If available in future round: return "pending, not yet available"
   - If invalid item: return "unrecognized request"
4. Verify the parser output against `parser-output.json`
5. Record the released item in state
6. Advance turn counter

The parser is a LLM, so the model can request results in natural language. The parser maps requests to the most likely item names.

### 4b. Solve Path: `_handle_solve(payload)`

If the candidate requested a `solve` action, it needs to provide the `working_diagnosis`, `differentials`, and a `treatment_plan` in the `response.solve` object.

1. The solve payload is extracted from `response.solve`
2. Together with the current round's reference standard, it is sent to the judge
3. The validate judge output must match `judge-output.json`
4. The judge evaluation is stored in `round_scores[current_round]`
5. If more rounds remain, increment round counter and continue

## Conversation State: What's Tracked

The `BenchmarkState` dataclass maintains:

- **`case`**: The current case as class `BenchmarkCase`
- **`running`**: Whether the case is currently evaluated.
- **`conversation`**: List of all messages (system, user, assistant) exchanged
- **`released_items`**: Set of info item keys that have been revealed
- **`round_scores`**: Dictionary mapping round number → judge evaluation
- **`step_index`**: Total turn counter across round
- **`n_consecutive_failures`**: Schema validation failure streak
- **`round_number`**: Which clinical stage (1, 2, or 3) we're in

## Error Handling Philosophy

The benchmark distinguishes between different error types:

- **Candidate schema errors**: Expected occasionally, especially with weaker models. Counted, can trigger cancellation if they occur subsequently.
- **Parser errors**: Unexpected. The parser is typically a strong model. If it fails, we abort the case.
- **Judge errors**: Unexpected. If the judge can't score a solve attempt, we abort.
