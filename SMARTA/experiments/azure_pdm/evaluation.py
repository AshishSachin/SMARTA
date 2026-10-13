"""Metrics and validation-only operating-point selection for the PdM experiment."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve, precision_score, recall_score

from .pipeline import COMPONENTS


def target_score_map(component_scores: np.ndarray) -> dict[str, np.ndarray]:
    scores = {component: component_scores[:, i] for i, component in enumerate(COMPONENTS)}
    scores["any"] = component_scores.max(axis=1)
    return scores


def target_label_map(component_labels: np.ndarray) -> dict[str, np.ndarray]:
    labels = {component: component_labels[:, i].astype(np.uint8) for i, component in enumerate(COMPONENTS)}
    labels["any"] = component_labels.max(axis=1).astype(np.uint8)
    return labels


def best_f1_threshold(labels: np.ndarray, scores: np.ndarray) -> float:
    """Pick an exploratory threshold on validation only; break ties toward fewer alerts."""
    labels = np.asarray(labels, dtype=np.uint8)
    scores = np.asarray(scores, dtype=float)
    if labels.sum() == 0:
        return 1.0
    precision, recall, thresholds = precision_recall_curve(labels, scores)
    if len(thresholds) == 0:
        return 1.0
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    best = np.flatnonzero(f1 == np.nanmax(f1))
    return float(thresholds[best[-1]])


def row_metrics(labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, Any]:
    labels = np.asarray(labels, dtype=np.uint8)
    scores = np.asarray(scores, dtype=float)
    predicted = scores >= threshold
    tp = int(np.logical_and(predicted, labels == 1).sum())
    fp = int(np.logical_and(predicted, labels == 0).sum())
    fn = int(np.logical_and(~predicted, labels == 1).sum())
    tn = int(np.logical_and(~predicted, labels == 0).sum())
    precision = float(precision_score(labels, predicted, zero_division=0))
    recall = float(recall_score(labels, predicted, zero_division=0))
    return {
        "rows": int(len(labels)),
        "positive_rows": int(labels.sum()),
        "prevalence": float(labels.mean()) if len(labels) else None,
        "average_precision": float(average_precision_score(labels, scores)) if labels.sum() else None,
        "threshold": float(threshold),
        "precision": precision,
        "recall": recall,
        "f1": float(2 * precision * recall / (precision + recall)) if precision + recall else 0.0,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
    }


def event_metrics(rows: pd.DataFrame, failures: pd.DataFrame, horizon_hours: int,
                  target: str, scores: np.ndarray, threshold: float) -> dict[str, Any]:
    """Deduplicate alerts by cooldown and score unique event-level detection/lead time."""
    frame = rows[["machineID", "datetime"]].copy().reset_index(drop=True)
    frame["score"] = np.asarray(scores, dtype=float)
    frame = frame.sort_values(["machineID", "datetime"])
    if target != "any":
        events = failures.loc[failures.failure == target, ["machineID", "datetime"]].drop_duplicates()
    else:
        events = failures[["machineID", "datetime"]].drop_duplicates()
    events = events.loc[events.machineID.isin(frame.machineID.unique())]
    if frame.empty:
        return {"event_count": 0, "detected_events": 0, "missed_events": 0,
                "event_recall": None, "false_alarms": 0, "false_alarms_per_machine_week": None,
                "lead_time_hours": {"count": 0}}
    test_start = frame.datetime.min()
    last_decision = frame.datetime.max()
    covered_end = last_decision + pd.Timedelta(hours=horizon_hours)
    events = events.loc[(events.datetime > test_start) & (events.datetime <= covered_end)]

    by_machine: dict[int, np.ndarray] = {
        int(mid): np.sort(group.datetime.to_numpy(dtype="datetime64[ns]"))
        for mid, group in events.groupby("machineID")
    }
    retained: list[tuple[int, pd.Timestamp]] = []
    cooldown = pd.Timedelta(hours=horizon_hours)
    for mid, group in frame.loc[frame.score >= threshold].groupby("machineID", sort=True):
        last_kept: pd.Timestamp | None = None
        for timestamp in group.datetime:
            # Prediction labels use the open/closed interval (t, t + H].  An
            # alert exactly H hours after the previous one has a disjoint
            # target window, so retain it (hourly observations make this
            # boundary common for the next-hour task).
            if last_kept is None or timestamp >= last_kept + cooldown:
                retained.append((int(mid), timestamp))
                last_kept = timestamp

    matched_event_keys: set[tuple[int, np.datetime64]] = set()
    false_alarms = 0
    lead_times: list[float] = []
    for machine_id, alarm_time in retained:
        event_times = by_machine.get(machine_id, np.array([], dtype="datetime64[ns]"))
        lo = np.searchsorted(event_times, np.datetime64(alarm_time), side="right")
        hi = np.searchsorted(event_times, np.datetime64(alarm_time + cooldown), side="right")
        if lo >= hi:
            false_alarms += 1
            continue
        event_time = event_times[lo]
        matched_event_keys.add((machine_id, event_time))
        lead_times.append(float((pd.Timestamp(event_time) - alarm_time).total_seconds() / 3600))

    total_events = int(len(events))
    detected = len(matched_event_keys)
    elapsed_machine_weeks = len(frame) / 168.0
    return {
        "event_count": total_events,
        "detected_events": int(detected),
        "missed_events": int(total_events - detected),
        "event_recall": float(detected / total_events) if total_events else None,
        "retained_alarms": int(len(retained)),
        "false_alarms": int(false_alarms),
        "false_alarms_per_machine_week": float(false_alarms / elapsed_machine_weeks) if elapsed_machine_weeks else None,
        "lead_time_hours": {
            "count": int(len(lead_times)),
            "median": float(np.median(lead_times)) if lead_times else None,
            "p10": float(np.percentile(lead_times, 10)) if lead_times else None,
            "p90": float(np.percentile(lead_times, 90)) if lead_times else None,
        },
    }


def machine_bootstrap_ap_ci(rows: pd.DataFrame, labels: np.ndarray, scores: np.ndarray,
                            seed: int, replicates: int = 100) -> dict[str, Any]:
    """Percentile CI from resampling whole machines (not correlated hourly rows)."""
    if replicates <= 0:
        return {"replicates": 0, "lower_95": None, "upper_95": None}
    ids = rows.machineID.to_numpy()
    machines = np.unique(ids)
    positions = {int(machine): np.flatnonzero(ids == machine) for machine in machines}
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(replicates):
        sampled = rng.choice(machines, size=len(machines), replace=True)
        indices = np.concatenate([positions[int(machine)] for machine in sampled])
        y = np.asarray(labels)[indices]
        if y.sum() == 0:
            continue
        values.append(float(average_precision_score(y, np.asarray(scores)[indices])))
    return {
        "replicates": int(replicates),
        "valid_replicates": int(len(values)),
        "lower_95": float(np.percentile(values, 2.5)) if values else None,
        "upper_95": float(np.percentile(values, 97.5)) if values else None,
    }
