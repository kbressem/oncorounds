"""Tests for oncorounds.scoring module."""

import json
import tempfile
from pathlib import Path

from oncorounds.scoring import (
    DIMENSIONS,
    Stats,
    score_differentials,
    score_round,
    score_case,
    score_run,
)


class TestStats:
    def test_add_correct(self):
        stats = Stats()
        pts = stats.add("correct")
        assert pts == 1.0
        assert stats.points == 1.0
        assert stats.max_points == 1.0
        assert stats.counts["correct"] == 1

    def test_add_partially_correct(self):
        stats = Stats()
        pts = stats.add("partially_correct")
        assert pts == 0.5
        assert stats.points == 0.5

    def test_add_incorrect(self):
        stats = Stats()
        pts = stats.add("incorrect")
        assert pts == 0.0
        assert stats.points == 0.0
        assert stats.max_points == 1.0

    def test_accuracy(self):
        stats = Stats()
        stats.add("correct")
        stats.add("incorrect")
        assert stats.accuracy == 50.0

    def test_accuracy_empty(self):
        stats = Stats()
        assert stats.accuracy is None


class TestScoreDifferentials:
    def test_zero_reference(self):
        stats = Stats()
        pts, mx = score_differentials(["correct", "correct"], n_ref=0, stats=stats)
        assert pts == 0.0
        assert mx == 0.0

    def test_takes_best_n_ref(self):
        stats = Stats()
        # 3 labels, n_ref=2, should take best 2
        pts, mx = score_differentials(
            ["incorrect", "correct", "partially_correct"], n_ref=2, stats=stats
        )
        # Best 2: correct (1.0) + partially_correct (0.5) = 1.5
        assert pts == 1.5
        assert mx == 2.0

    def test_no_penalty_under_threshold(self):
        stats = Stats()
        # n_ref=1, threshold=max(5, 2)=5, giving 4 labels = no penalty
        pts, mx = score_differentials(
            ["partially_correct", "incorrect", "incorrect", "incorrect"],
            n_ref=1,
            stats=stats,
        )
        assert pts == 0.5  # Best 1 = partially_correct
        assert mx == 1.0

    def test_penalty_over_threshold(self):
        stats = Stats()
        # n_ref=1, threshold=10, giving 12 labels = 2 excess = -2 penalty
        labels = ["correct"] + ["incorrect"] * 11
        pts, mx = score_differentials(labels, n_ref=1, stats=stats)
        # Best 1 = correct (1.0), penalty = 2, result = max(0, 1.0-2) = 0
        assert pts == 0.0
        assert mx == 1.0

    def test_penalty_floors_at_zero(self):
        stats = Stats()
        # n_ref=1, threshold=10, giving 15 labels = 5 excess
        labels = ["partially_correct"] + ["incorrect"] * 14
        pts, mx = score_differentials(labels, n_ref=1, stats=stats)
        # Best 1 = 0.5, penalty = 5, result = max(0, 0.5-5) = 0
        assert pts == 0.0

    def test_large_ref_uses_2x_threshold(self):
        stats = Stats()
        # n_ref=6, threshold=max(10, 12)=12, giving 13 labels = 1 excess
        labels = ["correct"] * 6 + ["incorrect"] * 7
        pts, mx = score_differentials(labels, n_ref=6, stats=stats)
        # Best 6 = 6.0, penalty = 1, result = 5.0
        assert pts == 5.0
        assert mx == 6.0


class TestScoreRound:
    def test_scores_working_diagnosis(self):
        dim_stats = {d: Stats() for d in DIMENSIONS}
        evaluation = {"working_diagnosis": "correct"}
        pts, mx = score_round(evaluation, dim_stats, n_ref_dd=0, n_ref_tx=0)
        assert pts == 1.0
        assert mx == 1.0
        assert dim_stats["working_diagnosis"].points == 1.0

    def test_scores_treatment_plan(self):
        dim_stats = {d: Stats() for d in DIMENSIONS}
        evaluation = {
            "treatment_plan": [
                {"action": "correct", "intention": "partially_correct", "priority": "incorrect"}
            ]
        }
        pts, mx = score_round(evaluation, dim_stats, n_ref_dd=0, n_ref_tx=1)
        assert pts == 1.5  # 1.0 + 0.5 + 0.0
        assert mx == 3.0

    def test_scores_all_dimensions(self):
        dim_stats = {d: Stats() for d in DIMENSIONS}
        evaluation = {
            "working_diagnosis": "correct",
            "differentials": ["correct", "partially_correct"],
            "treatment_plan": [
                {"action": "correct", "intention": "correct", "priority": "correct"}
            ],
        }
        pts, mx = score_round(evaluation, dim_stats, n_ref_dd=2, n_ref_tx=1)
        # WD: 1.0, DD: 1.5, Treatment: 3.0
        assert pts == 5.5
        assert mx == 6.0


class TestScoreCase:
    def test_aggregates_rounds(self):
        dim_stats = {d: Stats() for d in DIMENSIONS}
        payload = {
            "case_id": 1,
            "status": "completed",
            "rounds": {
                "1": {"evaluation": {"working_diagnosis": "correct"}},
                "2": {"evaluation": {"working_diagnosis": "partially_correct"}},
            },
        }
        refs = {1: {"dd": 0, "tx": 0}, 2: {"dd": 0, "tx": 0}}
        result = score_case(payload, dim_stats, refs=refs)
        assert result["case_id"] == 1
        assert result["status"] == "completed"
        assert result["points"] == 1.5
        assert result["max_points"] == 2.0
        assert len(result["rounds"]) == 2


class TestScoreRun:
    def test_empty_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = score_run(tmpdir, tmpdir)
            assert result["cases"] == []
            assert result["dimensions"] == {}
            assert result["categories"] == {}
            assert result["accuracy"] is None

    def test_scores_output_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outputs_dir = Path(tmpdir) / "outputs"
            case_dir = Path(tmpdir) / "cases"
            outputs_dir.mkdir()
            case_dir.mkdir()

            # Create a case file with reference
            case_data = {
                "case_id": 1,
                "reference_standard": {
                    "round_1": {"differentials": ["a", "b"]},
                },
            }
            (case_dir / "case-001.json").write_text(json.dumps(case_data))

            # Create an output file
            output_data = {
                "case_id": 1,
                "run_name": "test",
                "status": "completed",
                "rounds": {
                    "1": {
                        "evaluation": {
                            "working_diagnosis": "correct",
                            "differentials": ["correct", "correct"],
                        }
                    }
                },
            }
            (outputs_dir / "test-case001.json").write_text(json.dumps(output_data))

            result = score_run(outputs_dir, case_dir, run_name="test")
            assert len(result["cases"]) == 1
            assert result["cases"][0]["points"] == 3.0  # WD: 1.0, DD: 2.0
            assert result["accuracy"] == 100.0

    def test_filters_by_run_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outputs_dir = Path(tmpdir) / "outputs"
            case_dir = Path(tmpdir) / "cases"
            outputs_dir.mkdir()
            case_dir.mkdir()

            # Create outputs for different runs
            for run_name in ["run-a", "run-b"]:
                output_data = {
                    "case_id": 1,
                    "run_name": run_name,
                    "status": "completed",
                    "rounds": {"1": {"evaluation": {"working_diagnosis": "correct"}}},
                }
                (outputs_dir / f"{run_name}-case001.json").write_text(json.dumps(output_data))

            result = score_run(outputs_dir, case_dir, run_name="run-a")
            assert len(result["cases"]) == 1
            assert result["run_name"] == "run-a"
