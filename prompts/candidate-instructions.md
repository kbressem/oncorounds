# ONCOLOGY REASONING BENCHMARK INSTRUCTIONS

You are being evaluated on your clinical reasoning abilities in hematology and oncology.
This is a standardized benchmark designed to assess diagnostic accuracy, evidence-based reasoning, and treatment planning.

## TASK OVERVIEW

You will be presented with a patient case and must work toward a diagnosis and treatment plan.
Information will be provided progressively and you must request specific information one piece at a time until you are confident enough to provide a final assessment.

## HOW THIS WORKS

1. Initial Presentation: You receive basic patient demographics, chief complaint, and vital signs
2. Iterative Investigation: You request ONE type of information at a time (e.g., physical exam, labs, imaging)
3. Information Provided: The system provides requested information if available
4. Repeat or Solve: Continue requesting information OR provide your final assessment when ready

## RESPONSE FORMAT

Each turn involves a SINGLE response from you that includes your next step (either a request or a solution).

### Structure

You must respond with a JSON object following this structure:

```json
{
  "response": {
    "action": "<'request' or 'solve'>",
    ...
  }
}
```

### Option A: Requesting Information

If you need more information, set `action` to "request" and provide the `request` field:

```json
{
  "response": {
    "action": "request",
    "request": "<specific information you need, e.g. 'complete blood count'>"
  }
}
```

Examples of valid requests:

- "physical examination"
- "complete blood count"
- "chest CT scan"

You can only request ONE piece of information at a time.

### Option B: Solving the Case

If you have enough information, set `action` to "solve" and provide the `solve` object:

```json
{
  "response": {
    "action": "solve",
    "solve": {
      "working_diagnosis": "<your primary diagnosis>",
      "differentials": [
        "<differential diagnosis 1>",
        "<differential diagnosis 2>"
      ],
      "treatment_plan": [
        {
          "action": "<specific intervention>",
          "intention": "therapeutic",
          "priority": 1
        }
      ]
    }
  }
}
```

Field Definitions for Solve:

- working_diagnosis: Your primary diagnosis (string)
- differentials: List of alternative diagnoses to consider (array of strings, minimum 1)
- treatment_plan: Array of interventions, each with:
  - action: Specific intervention or test (string)
  - intention: EXACTLY one of: "therapeutic", "diagnostic", "supportive" (no other values allowed)
  - priority: EXACTLY 1, 2, or 3 only (1=highest, 2=medium, 3=lower). Values like 0, 4, 5 are INVALID.

## IMPORTANT RULES

1. You can only request ONE type of information per turn. Do not request multiple tests simultaneously.

2. Adhere strictly to the JSON schema.

3. Some tests may not be available yet (e.g., pathology results in early rounds). If this occurs, you can:
   - Request different available information
   - Proceed with your assessment based on current data

4. Request information in a logical clinical sequence. Consider what would be most important given the presentation.

## BEGIN

You will now receive your first patient case.
