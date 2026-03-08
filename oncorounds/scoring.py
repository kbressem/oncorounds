"""Scoring utilities for benchmark outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SCORE_VALUES = {"correct": 1.0, "partially_correct": 0.5, "incorrect": 0.0}
DIMENSIONS = [
    "working_diagnosis",
    "differentials",
    "treatment_action",
    "treatment_intention",
    "treatment_priority",
]


@dataclass
class Stats:
    """Accumulator for dimension-level scoring statistics."""

    points: float = 0.0
    max_points: float = 0.0
    counts: dict[str, int] = field(
        default_factory=lambda: {"correct": 0, "partially_correct": 0, "incorrect": 0}
    )

    def add(self, label: str) -> float:
        pts = SCORE_VALUES.get(label, 0.0)
        self.points += pts
        self.max_points += 1
        if label in self.counts:
            self.counts[label] += 1
        return pts

    @property
    def accuracy(self) -> float | None:
        return (self.points / self.max_points * 100) if self.max_points > 0 else None


def load_case_refs(case_dir: Path) -> dict[int, dict[int, dict[str, int]]]:
    """Load reference counts from case files.

    Returns: {case_id: {round: {"dd": n_differentials, "tx": n_treatment}}}
    """
    refs: dict[int, dict[int, dict[str, int]]] = {}
    for path in case_dir.glob("case-*.json"):
        try:
            data = json.loads(path.read_text())
            if (cid := data.get("case_id")) is None:
                continue
            rs = data.get("reference_standard", {})
            refs[cid] = {
                i: {
                    "dd": len(rs.get(f"round_{i}", {}).get("differentials", [])),
                    "tx": len(rs.get(f"round_{i}", {}).get("treatment_plan", [])),
                }
                for i in [1, 2, 3]
            }
        except (json.JSONDecodeError, ValueError):
            continue
    return refs


def load_efficiency(log_dir: Path, run_name: str, case_id: int) -> dict | None:
    """Parse JSONL log for efficiency metrics."""
    path = log_dir / f"{run_name}-case{case_id:03d}-conversation.jsonl"
    if not path.exists():
        return None
    total = valid = invalid = 0
    for line in path.read_text().splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            e.get("event_type") == "env_response"
            and e.get("outcome_action") == "request"
        ):
            total += 1
            status = e.get("outcome_status", "")
            if status == "request_released":
                valid += 1
            elif status == "request_invalid":
                invalid += 1
    return {"total": total, "valid": valid, "invalid": invalid}


def score_differentials(
    labels: list[str], n_ref: int, stats: Stats
) -> tuple[float, float]:
    """Score differentials with generous matching and anti-gaming penalty.

    - Takes best n_ref items (sorted by quality)
    - Penalizes -1 per item beyond threshold (max of 5 or 2× reference count)
    - Floors at 0
    """
    if n_ref == 0:
        return 0.0, 0.0

    sorted_labels = sorted(
        labels, key=lambda x: {"correct": 0, "partially_correct": 1}.get(x, 2)
    )
    pts = sum(SCORE_VALUES.get(lbl, 0.0) for lbl in sorted_labels[:n_ref])
    for lbl in sorted_labels[:n_ref]:
        if lbl in stats.counts:
            stats.counts[lbl] += 1

    threshold = max(10, 2 * n_ref)  # Allow at least 10 DDs without penalty
    excess = max(0, len(labels) - threshold)
    pts = max(0.0, pts - excess)

    stats.points += pts
    stats.max_points += n_ref
    return pts, float(n_ref)


def score_treatment(
    treatment_evals: list[dict],
    n_ref: int,
    dim_stats: dict[str, Stats],
) -> tuple[float, float]:
    """Score treatment with best-N selection and anti-gaming penalty.

    - Takes best n_ref items (sorted by total score)
    - Penalizes -1 per item beyond threshold (max of 10 or 2× reference count)
    - Floors at 0
    """
    if n_ref == 0:
        return 0.0, 0.0

    # Score each candidate item (sum of action + intention + priority)
    item_scores: list[tuple[float, dict]] = []
    for item in treatment_evals:
        score = sum(
            SCORE_VALUES.get(item.get(f, ""), 0.0)
            for f in ["action", "intention", "priority"]
        )
        item_scores.append((score, item))

    # Sort by score descending, take best n_ref
    item_scores.sort(key=lambda x: x[0], reverse=True)
    best_items = item_scores[:n_ref]
    pts = sum(s for s, _ in best_items)

    # Update dimension stats with best items only
    for _, item in best_items:
        dim_stats["treatment_action"].add(item.get("action", "incorrect"))
        dim_stats["treatment_intention"].add(item.get("intention", "incorrect"))
        dim_stats["treatment_priority"].add(item.get("priority", "incorrect"))

    # Penalty: max(10, 2*n_ref), -1 per excess
    threshold = max(10, 2 * n_ref)
    excess = max(0, len(treatment_evals) - threshold)
    pts = max(0.0, pts - excess)

    return pts, float(n_ref * 3)  # max_points = 3 per reference item


def score_round(
    evaluation: dict,
    dim_stats: dict[str, Stats],
    n_ref_dd: int,
    n_ref_tx: int,
) -> tuple[float, float]:
    """Score a single round's evaluation."""
    pts = mx = 0.0

    if wd := evaluation.get("working_diagnosis"):
        pts += dim_stats["working_diagnosis"].add(wd)
        mx += 1

    dd_pts, dd_mx = score_differentials(
        evaluation.get("differentials", []), n_ref_dd, dim_stats["differentials"]
    )
    pts += dd_pts
    mx += dd_mx

    tx_pts, tx_mx = score_treatment(
        evaluation.get("treatment_plan", []), n_ref_tx, dim_stats
    )
    pts += tx_pts
    mx += tx_mx

    return pts, mx


def score_case(
    payload: dict, dim_stats: dict[str, Stats], refs: dict[int, dict[str, int]]
) -> dict:
    """Compute scores for a single case output."""
    total_pts = total_mx = 0.0
    rounds = []

    for rnd_key, rnd_data in sorted(
        payload.get("rounds", {}).items(), key=lambda x: int(x[0])
    ):
        rnd = int(rnd_key)
        rnd_refs = refs.get(rnd, {"dd": 0, "tx": 0})
        pts, mx = score_round(
            rnd_data.get("evaluation", {}), dim_stats, rnd_refs["dd"], rnd_refs["tx"]
        )
        total_pts += pts
        total_mx += mx
        rounds.append({"round": rnd, "points": pts, "max_points": mx})

    return {
        "case_id": payload.get("case_id"),
        "status": payload.get("status", "unknown"),
        "points": total_pts,
        "max_points": total_mx,
        "rounds": rounds,
    }


def score_run(
    outputs_dir: Path | str,
    case_dir: Path | str,
    log_dir: Path | str | None = None,
    run_name: str | None = None,
) -> dict:
    """Score all outputs for a benchmark run.

    Args:
        outputs_dir: Directory containing case output JSON files
        case_dir: Directory containing case JSON files (for reference data)
        log_dir: Optional directory with JSONL logs (for efficiency metrics)
        run_name: Optional filter for specific run

    Returns:
        Dict with 'cases' (list of case summaries) and 'dimensions' (aggregate stats)
    """
    outputs_dir = Path(outputs_dir)
    case_dir = Path(case_dir)
    log_dir = Path(log_dir) if log_dir else None

    # Load outputs
    dataset = []
    for path in sorted(outputs_dir.glob("*.json")):
        payload = json.loads(path.read_text())
        if run_name and payload.get("run_name") != run_name:
            continue
        dataset.append(payload)

    if not dataset:
        return {"cases": [], "dimensions": {}, "categories": {}, "accuracy": None}

    case_refs = load_case_refs(case_dir)
    dim_stats = {d: Stats() for d in DIMENSIONS}
    case_summaries = []

    for payload in dataset:
        cid = payload.get("case_id")
        summary = score_case(payload, dim_stats, case_refs.get(cid, {}))
        if log_dir and (rn := payload.get("run_name")) and cid:
            summary["efficiency"] = load_efficiency(log_dir, rn, cid)
        case_summaries.append(summary)

    # Category-level aggregation (each category contributes 33.3%)
    categories = {
        "diagnosis": Stats(
            points=dim_stats["working_diagnosis"].points,
            max_points=dim_stats["working_diagnosis"].max_points,
            counts=dim_stats["working_diagnosis"].counts.copy(),
        ),
        "differentials": Stats(
            points=dim_stats["differentials"].points,
            max_points=dim_stats["differentials"].max_points,
            counts=dim_stats["differentials"].counts.copy(),
        ),
        "treatment": Stats(
            points=sum(
                dim_stats[d].points
                for d in [
                    "treatment_action",
                    "treatment_intention",
                    "treatment_priority",
                ]
            ),
            max_points=sum(
                dim_stats[d].max_points
                for d in [
                    "treatment_action",
                    "treatment_intention",
                    "treatment_priority",
                ]
            ),
        ),
    }

    category_accuracies = [
        c.accuracy for c in categories.values() if c.accuracy is not None
    ]
    balanced_accuracy = (
        sum(category_accuracies) / len(category_accuracies)
        if category_accuracies
        else None
    )

    return {
        "run_name": run_name,
        "cases": case_summaries,
        "dimensions": {
            d: {"points": s.points, "max_points": s.max_points, "accuracy": s.accuracy}
            for d, s in dim_stats.items()
        },
        "categories": {
            name: {
                "points": c.points,
                "max_points": c.max_points,
                "accuracy": c.accuracy,
            }
            for name, c in categories.items()
        },
        "accuracy": balanced_accuracy,
    }


def _cli() -> None:
    """CLI entry point for oncorounds-score command."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="oncorounds-score", description="Score benchmark outputs."
    )
    parser.add_argument(
        "--outputs-dir", default="outputs", help="Directory with output JSON files"
    )
    parser.add_argument(
        "--case-dir", default="cases", help="Directory with case JSON files"
    )
    parser.add_argument("--log-dir", default="logs", help="Directory with JSONL logs")
    parser.add_argument("--run-name", default=None, help="Filter by run name")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    result = score_run(args.outputs_dir, args.case_dir, args.log_dir, args.run_name)

    if not result["cases"]:
        print(f"No outputs found for run '{args.run_name}' in {args.outputs_dir}.")
        return

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        # Simple text output
        print(f"OncoRounds - {result.get('run_name') or 'all runs'}")
        print(f"Cases: {len(result['cases'])}")
        acc = result.get("accuracy")
        print(f"Score: {acc:.1f}%" if acc is not None else "Score: n/a")

        print("\nCategories (balanced average):")
        for name, c in result["categories"].items():
            cat_acc = (
                f"{c['accuracy']:.1f}%" if c.get("accuracy") is not None else "n/a"
            )
            print(
                f"  {name.title():<15} {c['points']:.1f}/{c['max_points']:.1f} ({cat_acc})"
            )

        print("\nDimensions (detailed):")
        for name, d in result["dimensions"].items():
            dim_acc = (
                f"{d['accuracy']:.1f}%" if d.get("accuracy") is not None else "n/a"
            )
            print(
                f"  {name.replace('_', ' ').title():<22} {d['points']:.1f}/{d['max_points']:.1f} ({dim_acc})"
            )
