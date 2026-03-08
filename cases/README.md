# How to Construct a Case

## Naming Convention

Case files must follow a specific naming pattern:

- **File extension**: Must be `.json`
- **Prefix**: Must start with `case_` **or** `case-` (both are discovered by the loader)
- **Format**: `case_<name>.json` or `case-<id>.json`

**Examples:**

- `case_pneumonia_elderly.json` ✅
- `case-017.json` ✅
- `pneumonia.json` ❌ (missing required prefix)
- `case_pneumonia.txt` ❌ (wrong file extension)

The case loader automatically filters for files matching this pattern.

## Creating a Case

All cases must conform to the JSON schema defined in `schemas/case.json` which is strictly enforced during case loading.

### Required Structure

Every case **must have exactly 3 rounds** of clinical decision-making. Each round represents a decision point where the model:

1. Receives available information
2. Makes a diagnosis/assessment
3. Proposes a treatment plan

### Core Fields

- **`case_id`** (integer): Unique identifier for the case
- **`title`** (string): Brief, descriptive case title
- **`patient`** (object): Patient demographics, chief complaint, and initial vital signs
- **`info_items`** (object): Requestable information organized by type (e.g., `"cbc"`, `"ct_chest"`, `"bone_marrow"`)
- **`reference_standard`** (object): The expert reference answers for each round

### Info Items Guidelines

Each info item should:

- Have a descriptive key name (e.g., `"cbc"`, `"echocardiography"`)
- Include `available_round` (1, 2, or 3) indicating when it becomes available
- Include `content` with the actual clinical information
- Optionally include `valid_request_if` with natural language phrases the model might use to request this item (e.g., "Asked for blood count" or "Asked for echocardiogram")

### Reference Standard

For each of the 3 rounds, provide:

- **`working_diagnosis`**: The primary reference diagnosis
- **`differentials`**: List of acceptable differential diagnoses
- **`treatment_plan`**: Array of actions with:
  - `action`: Description of what to do
  - `intention`: One of `"diagnostic"`, `"therapeutic"`, or `"supportive"`
  - `priority`: 1 (highest) to 3 (lowest)
- **`key_findings_quotes`**: Key clinical findings from the case that support the diagnosis

### Validation

Run your case through the JSON schema validator. Invalid cases will fail to load.
