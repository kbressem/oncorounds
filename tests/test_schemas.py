import json
from pathlib import Path
import pytest
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

SCHEMAS_DIR = Path(__file__).parents[1] / "schemas"

def get_schemas():
    """Yields all json files in the schemas directory."""
    for schema_file in SCHEMAS_DIR.glob("*.json"):
        yield schema_file

@pytest.mark.parametrize("schema_path", get_schemas())
def test_schema_is_valid(schema_path):
    """Check if the schema file contains a valid JSON Schema."""
    with open(schema_path, "r") as f:
        try:
            schema = json.load(f)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in {schema_path.name}: {e}")
    
    try:
        Draft7Validator.check_schema(schema)
    except SchemaError as e:
        pytest.fail(f"Invalid JSON Schema in {schema_path.name}: {e}")

def test_all_cases_validate_against_schema():
    """Check if all cases in cases/ validate against case.json."""
    cases_dir = Path(__file__).parents[1] / "cases"
    schema_path = SCHEMAS_DIR / "case.json"
    
    with open(schema_path, "r") as f:
        schema = json.load(f)
    
    validator = Draft7Validator(schema)
    
    for case_file in cases_dir.glob("case-*.json"):
        with open(case_file, "r") as f:
            try:
                case_data = json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {case_file.name}: {e}")
        
        # Remove $schema if present, as it might not be handled by validator directly or might point to remote
        if "$schema" in case_data:
            del case_data["$schema"]

        errors = list(validator.iter_errors(case_data))
        if errors:
            error_messages = "\n".join([f"{e.message} (path: {e.path})" for e in errors])
            pytest.fail(f"Validation failed for {case_file.name}:\n{error_messages}")
