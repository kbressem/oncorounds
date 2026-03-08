import json
from pathlib import Path

import pytest

from oncorounds.case import CaseLoader, load_case
from oncorounds.errors import CaseValidationError
from oncorounds.prompts import load_prompt
from oncorounds.schemas import load_schema


def test_case_loader_reads_cases():
    loader = CaseLoader(Path("cases"))
    cases = list(loader)
    assert cases, "Expected at least one case file in cases/ directory."
    ids = [case.case_id for case in cases]
    assert ids == sorted(ids)


def test_load_case_has_reference_rounds():
    case = load_case(Path("cases") / "case-001.json")
    assert case.max_round == 3
    assert "cbc" in case.info_items


def test_case_loader_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        CaseLoader(tmp_path / "does-not-exist")


def test_load_case_invalid_schema(tmp_path):
    invalid_case_path = tmp_path / "case_invalid.json"
    invalid_case_path.write_text('{"case_id": 123}', encoding="utf-8")
    with pytest.raises(CaseValidationError):
        load_case(invalid_case_path)


def test_case_loader_loads_multiple_cases(tmp_path):
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    template = json.loads(Path(__file__).with_name("testcase.json").read_text())

    first = json.loads(json.dumps(template))
    first["case_id"] = 2001
    (case_dir / "case-001.json").write_text(json.dumps(first), encoding="utf-8")

    second = json.loads(json.dumps(template))
    second["case_id"] = 2002
    (case_dir / "case-002.json").write_text(json.dumps(second), encoding="utf-8")

    loader = CaseLoader(case_dir)
    assert len(loader) == 2
    ids = [case.case_id for case in loader]
    assert set(ids) == {2001, 2002}


def test_load_schema_missing_file():
    with pytest.raises(FileNotFoundError):
        load_schema("does-not-exist")


def test_load_prompt_missing_file():
    with pytest.raises(FileNotFoundError):
        load_prompt("missing-prompt")
