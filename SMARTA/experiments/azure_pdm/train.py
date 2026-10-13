"""Run the separate, offline Azure PdM benchmark experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
import zipfile
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from .evaluation import (
    best_f1_threshold,
    event_metrics,
    machine_bootstrap_ap_ci,
    row_metrics,
    target_label_map,
    target_score_map,
    validation_alert_budget_curve,
)
from .pipeline import (
    COMPONENTS,
    HORIZONS_HOURS,
    build_features,
    build_targets,
    chronological_masks,
    load_tables,
    machine_group_masks,
)


ROOT = Path(__file__).resolve().parent
ACTIVE_RUN_STATUS_PATH: Path | None = None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def make_preprocessor(feature_columns: list[str], include_model: bool) -> ColumnTransformer:
    numeric = [c for c in feature_columns if c != "model"]
    transformers: list[tuple[str, Any, list[str]]] = [
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")),
                               ("scale", StandardScaler())]), numeric)
    ]
    if include_model:
        transformers.append(("model", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["model"]))
    return ColumnTransformer(transformers, remainder="drop", sparse_threshold=0.0)


def model_candidates(config: dict[str, Any]) -> dict[str, Any]:
    settings = config["models"]
    return {
        "logistic": MultiOutputClassifier(
            LogisticRegression(C=float(settings["logistic_c"]), max_iter=int(settings["logistic_max_iter"]),
                               solver="liblinear", class_weight=None),
            n_jobs=1,
        ),
        "decision_tree": DecisionTreeClassifier(
            max_depth=int(settings["tree_max_depth"]),
            min_samples_leaf=int(settings["tree_min_samples_leaf"]),
            class_weight=None,
            random_state=int(config["seed"]),
        ),
    }


def positive_probabilities(estimator: Any, matrix: np.ndarray) -> np.ndarray:
    raw = estimator.predict_proba(matrix)
    columns = []
    for output, probabilities in enumerate(raw):
        classes = estimator.classes_[output]
        if 1 in classes:
            columns.append(probabilities[:, int(np.flatnonzero(classes == 1)[0])])
        else:
            columns.append(np.zeros(len(matrix), dtype=float))
    return np.column_stack(columns)


def build_comparison_table(tables: Any, include_model: bool) -> pd.DataFrame:
    features = build_features(tables, include_model=True)
    targets = build_targets(features, tables.failures)
    # Index alignment is exact because targets are generated from this feature order.
    frame = pd.concat([features.reset_index(drop=True),
                       targets.drop(columns=["machineID", "datetime"]).reset_index(drop=True)], axis=1)
    if not include_model:
        frame = frame.drop(columns=["model"])
    return frame


def fit_preprocess(train: pd.DataFrame, validation: pd.DataFrame, test: pd.DataFrame,
                   include_model: bool) -> tuple[ColumnTransformer, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    excluded = {"machineID", "datetime", "model"}
    feature_columns = [c for c in train.columns if c not in excluded and not c.startswith("y_") and not c.startswith("valid_")]
    if include_model:
        feature_columns.append("model")
    preprocessor = make_preprocessor(feature_columns, include_model)
    train_x = preprocessor.fit_transform(train[feature_columns]).astype(np.float32, copy=False)
    validation_x = preprocessor.transform(validation[feature_columns]).astype(np.float32, copy=False)
    test_x = preprocessor.transform(test[feature_columns]).astype(np.float32, copy=False)
    return preprocessor, train_x, validation_x, test_x, feature_columns


def _output_targets(target_matrix: np.ndarray) -> dict[str, np.ndarray]:
    labels = target_label_map(target_matrix)
    return labels


def run(config_path: Path, dataset_override: str | None = None) -> dict[str, Any]:
    global ACTIVE_RUN_STATUS_PATH
    config = json.loads(config_path.read_text())
    zip_path = Path(dataset_override or config["dataset_zip"]).expanduser().resolve()
    if not zip_path.is_file():
        raise FileNotFoundError(f"Dataset ZIP not found: {zip_path}. Pass --dataset-zip or edit config.json.")

    directories = {key: (ROOT / value).resolve() for key, value in config["directories"].items()}
    run_id = time.strftime("run_%Y%m%dT%H%M%S", time.gmtime()) + f"_{time.time_ns() % 1_000_000_000:09d}Z"
    run_directories = {key: directory / run_id for key, directory in directories.items()}
    for directory in run_directories.values():
        directory.mkdir(parents=True, exist_ok=False)
    status_path = run_directories["metrics"] / "run_status.json"
    ACTIVE_RUN_STATUS_PATH = status_path
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    status_path.write_text(json.dumps({
        "status": "running", "run_id": run_id,
        "started_utc": started_utc,
    }, indent=2) + "\n")

    started = time.time()
    tables = load_tables(zip_path)
    from .pipeline import audit_summary
    data_audit = audit_summary(tables)
    features = build_features(tables, include_model=True)
    targets = build_targets(features, tables.failures)
    rows = pd.concat([features.reset_index(drop=True),
                      targets.drop(columns=["machineID", "datetime"]).reset_index(drop=True)], axis=1)

    split_sets: dict[str, tuple[dict[str, np.ndarray], dict[str, list[int]] | None]] = {
        "chronological_known_machines": (chronological_masks(rows, config), None),
    }
    group_masks, group_ids = machine_group_masks(rows, tables.machines, config)
    split_sets["future_unseen_machines"] = (group_masks, group_ids)

    metric_document: dict[str, Any] = {
        "experiment": "azure_pdm_offline_experiment",
        "experiment_version": "0.2.0",
        "dataset_zip": str(zip_path),
        "dataset_zip_sha256": sha256(zip_path),
        "config_sha256": sha256(config_path),
        "seed": int(config["seed"]),
        "probability_status": "uncalibrated raw classifier scores",
        "alert_budget_per_machine_week": config.get("false_alarm_budget_per_machine_week"),
        "minimum_event_recall": config.get("minimum_event_recall"),
        "deployment_acceptance": "undecided: operational alert budget and minimum recall are unset",
        "data_audit": data_audit,
        "split_machines": group_ids,
        "results": [],
    }
    result_lookup: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    test_score_cache: dict[tuple[str, str, str, str, str], tuple[pd.DataFrame, np.ndarray, np.ndarray, float]] = {}
    validation_score_cache: dict[tuple[str, str, str, str, str], tuple[pd.DataFrame, np.ndarray, np.ndarray]] = {}
    horizons = list(HORIZONS_HOURS.items())

    for split_name, (masks, _) in split_sets.items():
        for horizon_name, horizon_hours in horizons:
            valid_col = f"valid_{horizon_name}"
            eligible = rows[valid_col].to_numpy(dtype=bool)
            split_masks = {name: mask & eligible for name, mask in masks.items()}
            sliced: dict[str, pd.DataFrame] = {}
            for name, mask in split_masks.items():
                subset = rows.loc[mask].reset_index(drop=True)
                if subset.empty:
                    raise ValueError(f"No eligible {name} rows for {split_name}/{horizon_name}")
                sliced[name] = subset
            y_cols = [f"y_{horizon_name}_{c}" for c in COMPONENTS]
            y_train = sliced["train"][y_cols].to_numpy(dtype=np.uint8)
            y_validation = sliced["validation"][y_cols].to_numpy(dtype=np.uint8)
            y_test = sliced["test"][y_cols].to_numpy(dtype=np.uint8)
            validation_targets = target_label_map(y_validation)
            test_targets = target_label_map(y_test)

            for include_model in (False, True):
                feature_variant = "plus_model_ablation" if include_model else "base_no_model"
                prep, X_train, X_val, X_test, feature_columns = fit_preprocess(
                    sliced["train"], sliced["validation"], sliced["test"], include_model
                )
                y_train_any = target_label_map(y_train)["any"]
                prior_scores = {
                    **{c: np.full(len(sliced["test"]), y_train[:, i].mean(), dtype=float)
                       for i, c in enumerate(COMPONENTS)},
                    "any": np.full(len(sliced["test"]), y_train_any.mean(), dtype=float),
                }
                if not include_model:
                    for target_name in ("any", *COMPONENTS):
                        baseline_metrics = row_metrics(test_targets[target_name], prior_scores[target_name], 0.5)
                        baseline_metrics.update({
                            "split": split_name, "horizon": horizon_name, "model": "constant_prior",
                            "feature_variant": "shared", "target": target_name,
                            "threshold_source": "fixed_majority_threshold_0.5",
                        })
                        baseline_metrics["event_metrics"] = event_metrics(
                            sliced["test"], tables.failures, horizon_hours, target_name,
                            prior_scores[target_name], 0.5,
                        )
                        metric_document["results"].append(baseline_metrics)

                for model_name, estimator in model_candidates(config).items():
                    model_started = time.time()
                    estimator.fit(X_train, y_train)
                    validation_component_scores = positive_probabilities(estimator, X_val)
                    test_component_scores = positive_probabilities(estimator, X_test)
                    val_scores = target_score_map(validation_component_scores)
                    test_scores = target_score_map(test_component_scores)
                    thresholds = {
                        target_name: best_f1_threshold(validation_targets[target_name], val_scores[target_name])
                        for target_name in ("any", *COMPONENTS)
                    }

                    model_dir = run_directories["artifacts"] / split_name
                    model_dir.mkdir(parents=True, exist_ok=True)
                    model_path = model_dir / f"{horizon_name}_{feature_variant}_{model_name}.joblib"
                    joblib.dump({
                        "preprocessor": prep,
                        "estimator": estimator,
                        "feature_columns": feature_columns,
                        "component_order": list(COMPONENTS),
                        "horizon_hours": horizon_hours,
                        "experiment_name": "azure_pdm_offline_experiment",
                        "experiment_version": "0.2.0",
                        "model_version": f"azure-pdm-{run_id}-{split_name}-{horizon_name}-{feature_variant}-{model_name}",
                        "dataset_identifier": "microsoft-azure-pdm-synthetic-benchmark",
                        "dataset_zip_sha256": metric_document["dataset_zip_sha256"],
                        "config_sha256": metric_document["config_sha256"],
                        "split": split_name,
                        "run_id": run_id,
                        "thresholds_selected_on_validation": thresholds,
                        "probabilities_calibrated": False,
                    }, model_path, compress=3)

                    for target_name in ("any", *COMPONENTS):
                        score = test_scores[target_name]
                        threshold = thresholds[target_name]
                        entry = row_metrics(test_targets[target_name], score, threshold)
                        entry.update({
                            "split": split_name, "horizon": horizon_name, "model": model_name,
                            "feature_variant": feature_variant, "target": target_name,
                            "threshold_source": "validation_max_f1_tie_break_fewer_alerts",
                            "threshold_validation": float(threshold),
                            "model_fit_seconds": round(time.time() - model_started, 3),
                            "artifact": str(model_path.relative_to(ROOT)),
                            "probabilities_calibrated": False,
                        })
                        entry["event_metrics"] = event_metrics(
                            sliced["test"], tables.failures, horizon_hours, target_name, score, threshold
                        )
                        key = (split_name, horizon_name, feature_variant, model_name, target_name)
                        result_lookup[key] = entry
                        test_score_cache[key] = (sliced["test"][["machineID", "datetime"]],
                                                  test_targets[target_name], score, threshold)
                        validation_score_cache[key] = (
                            sliced["validation"][["machineID", "datetime"]],
                            validation_targets[target_name],
                            val_scores[target_name],
                        )
                        metric_document["results"].append(entry)

                    # Keep validation AP alongside all test metrics so candidate selection
                    # is explicitly based on validation, never on the locked test set.
                    for target_name in ("any", *COMPONENTS):
                        entry = result_lookup[(split_name, horizon_name, feature_variant, model_name, target_name)]
                        from sklearn.metrics import average_precision_score
                        labels = validation_targets[target_name]
                        entry["validation_average_precision"] = (
                            float(average_precision_score(labels, val_scores[target_name])) if labels.sum() else None
                        )

    # Select a candidate separately for each output using validation AP only.
    selected: list[dict[str, Any]] = []
    candidates = [("base_no_model", "logistic"), ("base_no_model", "decision_tree"),
                  ("plus_model_ablation", "logistic"), ("plus_model_ablation", "decision_tree")]
    for split_name in split_sets:
        for horizon_name, _ in horizons:
            for target_name in ("any", *COMPONENTS):
                choices = []
                for feature_variant, model_name in candidates:
                    entry = result_lookup[(split_name, horizon_name, feature_variant, model_name, target_name)]
                    ap = entry.get("validation_average_precision")
                    choices.append((float(ap) if ap is not None else -1.0, feature_variant, model_name))
                _, feature_variant, model_name = max(choices, key=lambda x: x[0])
                key = (split_name, horizon_name, feature_variant, model_name, target_name)
                entry = result_lookup[key]
                entry["selected_by_validation"] = True
                test_rows, labels, scores, threshold = test_score_cache[key]
                bootstrap_seed = int(config["seed"]) + int(hashlib.sha256(
                    f"{split_name}|{horizon_name}|{target_name}".encode()
                ).hexdigest()[:8], 16)
                ci = machine_bootstrap_ap_ci(
                    test_rows, labels, scores,
                    bootstrap_seed,
                    int(config.get("machine_bootstrap_replicates", 100)),
                )
                entry["machine_cluster_average_precision_ci_95"] = ci
                validation_rows, validation_labels, validation_scores = validation_score_cache[key]
                budget_curve = validation_alert_budget_curve(
                    validation_rows,
                    tables.failures,
                    dict(horizons)[horizon_name],
                    target_name,
                    validation_labels,
                    validation_scores,
                    list(map(float, config.get("candidate_false_alarm_budgets_per_machine_week", []))),
                    threshold_quantiles=int(config.get("alert_curve_threshold_quantiles", 21)),
                )
                entry["validation_alert_budget_curve"] = budget_curve
                selected.append({"split": split_name, "horizon": horizon_name, "target": target_name,
                                 "model": model_name, "feature_variant": feature_variant,
                                 "validation_average_precision": entry.get("validation_average_precision"),
                                 "test_average_precision": entry.get("average_precision"),
                                 "test_threshold": threshold,
                                 "validation_alert_budget_curve": budget_curve,
                                 "test_machine_cluster_ap_ci_95": ci})

    metric_document["selected_by_validation"] = selected
    metric_document["runtime_seconds"] = round(time.time() - started, 3)
    metric_document["run_id"] = run_id
    metric_path = run_directories["metrics"] / "evaluation.json"
    metric_document["output_paths"] = {
        "metrics": str(metric_path.relative_to(ROOT)),
        "report": str((run_directories["reports"] / "experiment_report.md").relative_to(ROOT)),
        "artifacts": str(run_directories["artifacts"].relative_to(ROOT)),
    }
    metric_path.write_text(json.dumps(metric_document, indent=2, allow_nan=False) + "\n")
    (run_directories["reports"] / "data_audit.json").write_text(json.dumps(data_audit, indent=2) + "\n")
    (run_directories["reports"] / "config_snapshot.json").write_text(json.dumps(config, indent=2) + "\n")
    (run_directories["reports"] / "feature_schema.json").write_text(json.dumps({
        "feature_columns": feature_columns,
        "identifier_columns_excluded": ["machineID", "datetime"],
        "target_columns_excluded": [f"y_{horizon}_{target}" for horizon in HORIZONS_HOURS
                                    for target in (*COMPONENTS, "any")],
        "model_category_included_only_as_ablation": True,
        "machine_age_included": False,
    }, indent=2) + "\n")
    write_report(run_directories["reports"] / "experiment_report.md", metric_document, config)
    status_path.write_text(json.dumps({
        "status": "complete", "run_id": run_id,
        "started_utc": started_utc,
        "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "result_count": len(metric_document["results"]),
    }, indent=2) + "\n")
    ACTIVE_RUN_STATUS_PATH = None
    return metric_document


def write_report(path: Path, metrics: dict[str, Any], config: dict[str, Any]) -> None:
    audit = metrics["data_audit"]
    lines = [
        "# Isolated Azure PdM experiment",
        "",
        "## Status and scope",
        "",
        "This report describes an offline benchmark experiment. It does not change or replace AI4I, production API behavior, or Flutter. Scores are uncalibrated model scores and are not production predictions.",
        "",
        f"- Dataset ZIP SHA-256: `{metrics['dataset_zip_sha256']}`",
        f"- Configuration SHA-256: `{metrics['config_sha256']}`",
        f"- Random seed: `{metrics['seed']}`",
        f"- Deployment acceptance: {metrics['deployment_acceptance']}",
        "- Provenance: matches the Microsoft Azure PdM sample schema and counts; Microsoft describes the benchmark as synthesized from multiple real-world problems. The supplied ZIP contains no license manifest; redistribution and deployment rights remain unverified.",
        "",
        "## Data audit",
        "",
        f"- Rows: telemetry {audit['row_counts']['telemetry']:,}; failures {audit['row_counts']['failures']:,}; errors {audit['row_counts']['errors']:,}; maintenance {audit['row_counts']['maintenance']:,}; machines {audit['row_counts']['machines']:,}.",
        f"- Telemetry coverage: {audit['telemetry']['start']} to {audit['telemetry']['end']}; {audit['telemetry']['machines']} machines; observed cadence hours {audit['telemetry']['cadence_hours']}.",
        f"- Failure labels: {audit['failure_labels']['counts_by_component']}; {audit['failure_labels']['unique_machine_failure_hours']} distinct machine-hours; {audit['failure_labels']['multi_component_failure_hours']} hours include multiple component failures.",
        f"- Exact failure-to-maintenance triple mismatches: {audit['failure_labels']['unmatched_exact_maintenance_rows']}. The failure table remains the target source, so unmatched failures are retained. Maintenance-only rows remain historical replacement events and are never relabeled as failures.",
        f"- Errors with multiple same-machine/hour rows: {audit['errors']['same_machine_hour_excess_rows']} excess rows; event counts are aggregated before feature construction.",
        "- Machine age is excluded because its as-of date is not defined in the archive. Model category is evaluated only as a separate feature ablation. Machine ID is never a predictor.",
        "",
        "## Labels and feature timing",
        "",
        "- Each target is a logged component failure in `(t, t + H]`. The event at exactly `t` is excluded. Next-hour uses H=1 hour; candidate warning horizons use H=24 and H=168 hours.",
        "- Features at cutoff t use only telemetry and event records with timestamps strictly less than t. Rolling telemetry windows contain the previous complete hourly observations. A 168-hour telemetry history is required.",
        "- Rows are excluded when the full future horizon is not observed. Failure timestamps are hourly rounded, so event-time boundaries and warning lead times are approximate. These are logged-event targets, not verified physical onset labels.",
        "- Historical failure and maintenance counts are included only for events strictly before t. Future maintenance is not a feature. The primary target is an event under the benchmark’s observed replacement process; preventive maintenance can alter future observed event risk.",
        "",
        "## Evaluation design",
        "",
        "- Chronological split: train before the validation cutoff with a 7-day pre-boundary purge, validate in the following date block with a 7-day pre-test purge, and test in the final date block with full 7-day label coverage.",
        "- Machine-held-out split: machines are assigned 60/20/20 by a seeded split stratified on static model category only. Train, validation, and test use distinct machine IDs and chronological date blocks.",
        "- Comparisons use identical eligible rows per split and horizon: constant prior/majority, regularized logistic regression, and a bounded-depth decision tree. The model-category ablation is compared separately.",
        "- Decision thresholds are selected on validation only by the configured maximum-F1 rule. Test thresholds are never tuned. Validation selection among model/feature variants uses validation average precision only.",
        "- Average precision is the stepwise PR-area metric. Event metrics deduplicate machine/component alerts with a horizon-length cooldown. Cluster bootstrap intervals resample whole machines.",
        "",
        "## Locked-test results",
        "",
        f"Test results are reported for the predeclared candidates. Candidate selection is recorded from validation results; the test set was not used to select thresholds or features. The constant-prior AP is the test prevalence; its fixed 0.5 majority threshold emits no alerts for these rare targets, so it has no false alarms and misses every logged event. Review `{metrics['output_paths']['metrics']}` for per-target confusion counts, AP, event recall, missed events, false alarms per machine-week, lead times, and machine-cluster AP intervals.",
        "",
        "| Split | Horizon | Target | Selected on validation | Test AP | Prior AP | Test precision | Test recall | Test event recall | False alarms / machine-week | Missed events | Majority misses | AP 95% machine CI |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in metrics["selected_by_validation"]:
        matches = [r for r in metrics["results"] if r.get("split") == item["split"] and
                   r.get("horizon") == item["horizon"] and r.get("target") == item["target"] and
                   r.get("model") == item["model"] and r.get("feature_variant") == item["feature_variant"]]
        if not matches:
            continue
        entry = matches[0]
        baseline_matches = [r for r in metrics["results"] if r.get("split") == item["split"] and
                            r.get("horizon") == item["horizon"] and r.get("target") == item["target"] and
                            r.get("model") == "constant_prior"]
        baseline = baseline_matches[0] if baseline_matches else {}
        event = entry.get("event_metrics", {})
        ci = item["test_machine_cluster_ap_ci_95"]
        interval = "n/a" if ci.get("lower_95") is None else f"{ci['lower_95']:.4f}–{ci['upper_95']:.4f}"
        ap = entry.get("average_precision")
        ap_text = f"{ap:.4f}" if ap is not None else "n/a"
        baseline_ap = baseline.get("average_precision")
        baseline_ap_text = f"{baseline_ap:.4f}" if baseline_ap is not None else "n/a"
        lines.append(
            f"| {item['split']} | {item['horizon']} | {item['target']} | {item['model']} / {item['feature_variant']} | "
            f"{ap_text} | {baseline_ap_text} | {entry['precision']:.4f} | {entry['recall']:.4f} | "
            f"{event.get('event_recall') if event.get('event_recall') is not None else 'n/a'} | "
            f"{event.get('false_alarms_per_machine_week') if event.get('false_alarms_per_machine_week') is not None else 'n/a'} | "
            f"{event.get('missed_events', 'n/a')} | {baseline.get('false_negatives', 'n/a')} | {interval} |"
        )
    lines.extend([
        "",
        "## Validation-only alert-budget trade-offs",
        "",
        "Candidate budgets below are configurable exploration settings, not approved operational limits. For each selected candidate, the threshold is chosen on validation data to maximize event recall under the candidate false-alarm rate, with precision and threshold as tie-breaks. Test data does not choose these thresholds. Component-level curves are in `evaluation.json`.",
        "",
        "| Split | Horizon | Candidate budget / machine-week | Validation threshold | Validation precision | Validation recall | Validation event recall | Validation false alarms / machine-week |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ])
    for item in metrics["selected_by_validation"]:
        if item["target"] != "any":
            continue
        for point in item.get("validation_alert_budget_curve", []):
            if not point.get("budget_feasible"):
                continue
            lines.append(
                f"| {item['split']} | {item['horizon']} | {point['candidate_budget_per_machine_week']:.2f} | "
                f"{point['threshold']:.6g} | {point['precision']:.4f} | {point['recall']:.4f} | "
                f"{point['event_recall'] if point['event_recall'] is not None else 'n/a'} | "
                f"{point['false_alarms_per_machine_week']:.6g} |"
            )
    lines.extend([
        "",
        "## Logged-event warning lead-time coverage",
        "",
        "Fractions use all test-period logged events as the denominator, including missed events. These are lead times to rounded logged timestamps, not physical-onset warnings.",
        "",
        "| Split | Horizon | Any-component events | Events warned ≥24h | Events warned ≥7d | Median lead time (hours) |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for item in metrics["selected_by_validation"]:
        if item["target"] != "any":
            continue
        entry = next((row for row in metrics["results"] if row.get("split") == item["split"]
                      and row.get("horizon") == item["horizon"] and row.get("target") == "any"
                      and row.get("selected_by_validation")), {})
        event = entry.get("event_metrics", {})
        coverage = event.get("warning_coverage", {})
        lead = event.get("lead_time_hours", {}).get("median")
        total_events = event.get("event_count", 0)
        fraction_24h = coverage.get("fraction_of_all_events_warned_at_least_24h")
        fraction_7d = coverage.get("fraction_of_all_events_warned_at_least_7d")
        lines.append(
            f"| {item['split']} | {item['horizon']} | {total_events} | "
            f"{coverage.get('events_warned_at_least_24h', 0)} ({fraction_24h if fraction_24h is not None else 'n/a'}) | "
            f"{coverage.get('events_warned_at_least_7d', 0)} ({fraction_7d if fraction_7d is not None else 'n/a'}) | "
            f"{lead if lead is not None else 'n/a'} |"
        )
    lines.extend([
        "",
        "## Acceptance and limitations",
        "",
        "The alert budget and minimum acceptable event recall are intentionally unset in `config.json`; no defensible operational values were supplied. Deployment acceptance is therefore undecided regardless of benchmark scores. The benchmark is synthetic, spans about one year, has sparse component events, uses rounded timestamps, and does not verify repairs or physical failure onset. These results cannot establish calibrated probabilities, guaranteed 24-hour/7-day warning, or production generalization.",
        "",
        "## Reproduction",
        "",
        "```bash",
        "cd /Users/ashishsachinas/Desktop/SMARTA/SMARTA",
        "../.venv/bin/python -m experiments.azure_pdm.train",
        "../.venv/bin/python -m unittest discover -s experiments/azure_pdm/tests -v",
        "```",
        "",
        "To use another copy of the supplied archive, pass `--dataset-zip /path/to/archive.zip`. Raw CSV members are read directly from the ZIP; they are not extracted or modified.",
    ])
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--dataset-zip", default=None, help="Override the ZIP path in config.json")
    args = parser.parse_args()
    try:
        result = run(args.config.resolve(), args.dataset_zip)
    except BaseException as exc:
        if ACTIVE_RUN_STATUS_PATH is not None and ACTIVE_RUN_STATUS_PATH.exists():
            ACTIVE_RUN_STATUS_PATH.write_text(json.dumps({
                "status": "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                "error_type": type(exc).__name__,
            }, indent=2) + "\n")
        raise
    print(json.dumps({
        "dataset_zip_sha256": result["dataset_zip_sha256"],
        "result_count": len(result["results"]),
        "selected_validation_candidates": len(result["selected_by_validation"]),
        "runtime_seconds": result["runtime_seconds"],
        "deployment_acceptance": result["deployment_acceptance"],
        "metrics": str((ROOT / result["output_paths"]["metrics"]).resolve()),
        "report": str((ROOT / result["output_paths"]["report"]).resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
