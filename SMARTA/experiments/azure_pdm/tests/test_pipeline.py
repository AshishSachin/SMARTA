from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from experiments.azure_pdm.pipeline import (
    COMPONENTS,
    DatasetTables,
    audit_summary,
    build_features,
    build_targets,
    chronological_masks,
    machine_group_masks,
)
from experiments.azure_pdm.evaluation import event_metrics, validation_alert_budget_curve


def fixture_tables(hours: int = 200) -> DatasetTables:
    times = pd.date_range("2015-01-01 06:00:00", periods=hours, freq="h")
    telemetry = pd.DataFrame([
        {"datetime": timestamp, "machineID": machine, "volt": float(i),
         "rotate": float(i + 10), "pressure": float(i + 20), "vibration": float(i + 30)}
        for machine in (1, 2) for i, timestamp in enumerate(times)
    ])
    failures = pd.DataFrame([
        {"datetime": times[168], "machineID": 1, "failure": "comp1"},  # exactly at cutoff
        {"datetime": times[169], "machineID": 1, "failure": "comp2"},  # next hour
        {"datetime": times[192], "machineID": 1, "failure": "comp1"},  # 24h endpoint from t=168
        {"datetime": times[192], "machineID": 1, "failure": "comp3"},  # simultaneous component
        {"datetime": times[193], "machineID": 1, "failure": "comp4"},  # outside 24h endpoint
    ])
    errors = pd.DataFrame([
        {"datetime": times[167], "machineID": 1, "errorID": "error1"},
        {"datetime": times[167], "machineID": 1, "errorID": "error1"},
        {"datetime": times[168], "machineID": 1, "errorID": "error2"},
    ])
    maintenance = pd.DataFrame([
        {"datetime": times[167], "machineID": 1, "comp": "comp1"},
        {"datetime": times[168], "machineID": 1, "comp": "comp4"},
    ])
    machines = pd.DataFrame([{"machineID": 1, "model": "model1", "age": 3},
                             {"machineID": 2, "model": "model2", "age": 5}])
    return DatasetTables(telemetry, failures, errors, maintenance, machines)


class PipelineTests(unittest.TestCase):
    def test_features_use_only_completed_prior_telemetry(self):
        tables = fixture_tables()
        base = build_features(tables, include_model=True)
        cutoff = tables.telemetry.datetime.unique()[168]
        original = base.loc[(base.machineID == 1) & (base.datetime == cutoff)].iloc[0]
        tables.telemetry.loc[(tables.telemetry.machineID == 1) &
                             (tables.telemetry.datetime >= cutoff), "volt"] = 999999.0
        changed = build_features(tables, include_model=True)
        after = changed.loc[(changed.machineID == 1) & (changed.datetime == cutoff)].iloc[0]
        self.assertEqual(float(original.volt_mean_168h), float(after.volt_mean_168h))
        self.assertAlmostEqual(float(original.volt_mean_168h), float(np.mean(np.arange(168))))
        self.assertNotIn("machineID", [c for c in changed.columns if c.startswith("x_")])

    def test_event_aggregation_and_history_exclude_cutoff_timestamp(self):
        tables = fixture_tables()
        features = build_features(tables)
        cut = tables.telemetry.datetime.unique()[168]
        row = features.loc[(features.machineID == 1) & (features.datetime == cut)].iloc[0]
        self.assertEqual(float(row.past_errorID_error1_24h), 2.0)
        self.assertEqual(float(row.past_errorID_error2_24h), 0.0)
        self.assertEqual(float(row.past_comp_comp1_24h), 1.0)
        self.assertEqual(float(row.past_comp_comp4_24h), 0.0)
        self.assertEqual(float(row.past_failure_comp1_24h), 0.0)  # failure at t is not prior history
        after = features.loc[(features.machineID == 1) &
                             (features.datetime == cut + pd.Timedelta(hours=1))].iloc[0]
        self.assertEqual(float(after.past_comp_comp4_24h), 1.0)
        self.assertEqual(int(features.groupby(["machineID", "datetime"]).size().max()), 1)

    def test_targets_use_open_lower_closed_upper_horizon_and_multilabel(self):
        # Leave room for both the full 168-hour feature history and a complete
        # 7-day future horizon at the final-boundary assertions.
        tables = fixture_tables(hours=400)
        features = build_features(tables)
        targets = build_targets(features, tables.failures)
        cut = tables.telemetry.datetime.unique()[168]
        row = targets.loc[(targets.machineID == 1) & (targets.datetime == cut)].iloc[0]
        self.assertEqual(int(row.y_next_hour_comp1), 0)  # event exactly at t excluded
        self.assertEqual(int(row.y_next_hour_comp2), 1)  # event at t+1 included
        self.assertEqual(int(row.y_24h_comp1), 1)         # event at t+24 included
        self.assertEqual(int(row.y_24h_comp3), 1)         # simultaneous label retained
        self.assertEqual(int(row.y_24h_comp4), 0)         # event at t+25 excluded
        self.assertEqual(int(row.y_24h_any), 1)
        self.assertEqual(int(row.y_7d_any), 1)
        self.assertEqual(len(COMPONENTS), 4)
        coverage_boundary = targets.loc[(targets.machineID == 1) &
                                        (targets.datetime == tables.telemetry.datetime.unique()[231])].iloc[0]
        self.assertTrue(bool(coverage_boundary.valid_7d))  # endpoint at final observation is complete
        after_boundary = targets.loc[(targets.machineID == 1) &
                                     (targets.datetime == tables.telemetry.datetime.unique()[232])].iloc[0]
        self.assertFalse(bool(after_boundary.valid_7d))

    def test_maintenance_only_rows_do_not_become_failure_targets(self):
        tables = fixture_tables()
        tables.maintenance = pd.concat([tables.maintenance, pd.DataFrame([{
            "datetime": tables.telemetry.datetime.max() - pd.Timedelta(hours=2),
            "machineID": 2, "comp": "comp3",
        }])], ignore_index=True)
        features = build_features(tables)
        targets = build_targets(features, tables.failures)
        machine2 = targets.loc[targets.machineID == 2]
        self.assertEqual(int(machine2[[f"y_{h}_{c}" for h in ("next_hour", "24h", "7d")
                                      for c in COMPONENTS]].to_numpy().sum()), 0)

    def test_audit_retains_failure_events_not_linked_to_maintenance(self):
        tables = fixture_tables()
        summary = audit_summary(tables)
        self.assertEqual(summary["failure_labels"]["unmatched_exact_maintenance_rows"], 5)
        self.assertEqual(summary["failure_labels"]["multi_component_failure_hours"], 1)

    def test_chronological_splits_purge_pre_boundary_rows(self):
        rows = pd.DataFrame({"datetime": pd.date_range("2015-08-20", "2015-11-10", freq="h")})
        config = {"max_horizon_hours": 168, "split": {
            "train_start": "2015-08-20 00:00:00",
            "train_validation_cutoff": "2015-09-01 00:00:00",
            "validation_test_cutoff": "2015-11-01 00:00:00",
            "dataset_end": "2015-11-10 00:00:00",
        }}
        masks = chronological_masks(rows, config)
        train_times = rows.loc[masks["train"], "datetime"]
        val_times = rows.loc[masks["validation"], "datetime"]
        test_times = rows.loc[masks["test"], "datetime"]
        self.assertLess(train_times.max(), pd.Timestamp("2015-08-25 00:00:00"))
        self.assertEqual(val_times.min(), pd.Timestamp("2015-09-01 00:00:00"))
        self.assertLess(val_times.max(), pd.Timestamp("2015-10-25 00:00:00"))
        self.assertEqual(test_times.min(), pd.Timestamp("2015-11-01 00:00:00"))
        self.assertLessEqual(test_times.max() + pd.Timedelta(hours=168), pd.Timestamp("2015-11-10 00:00:00"))

    def test_machine_held_out_groups_are_disjoint(self):
        machines = pd.DataFrame({
            "machineID": np.arange(1, 101),
            "model": [f"model{(i % 4) + 1}" for i in range(100)],
        })
        dates = pd.date_range("2015-01-08", "2015-12-25", freq="7D")
        rows = pd.DataFrame([
            {"machineID": int(mid), "datetime": timestamp}
            for mid in machines.machineID for timestamp in dates
        ])
        config = {"seed": 15, "max_horizon_hours": 168, "split": {
            "train_start": "2015-01-08 00:00:00",
            "train_validation_cutoff": "2015-09-01 00:00:00",
            "validation_test_cutoff": "2015-11-01 00:00:00",
            "dataset_end": "2016-01-01 00:00:00",
        }}
        masks, groups = machine_group_masks(rows, machines, config)
        self.assertEqual([len(groups[k]) for k in ("train", "validation", "test")], [60, 20, 20])
        self.assertFalse(set(groups["train"]) & set(groups["validation"]))
        self.assertFalse(set(groups["train"]) & set(groups["test"]))
        self.assertFalse(set(groups["validation"]) & set(groups["test"]))
        self.assertFalse(np.any(masks["train"] & masks["validation"]))
        self.assertFalse(np.any(masks["validation"] & masks["test"]))

    def test_event_dedup_keeps_alert_at_open_closed_horizon_boundary(self):
        # The first alert's (t, t+1h] window contains no event. The next alert
        # is exactly one hour later and warns at the inclusive upper boundary.
        rows = pd.DataFrame({
            "machineID": [1, 1],
            "datetime": pd.to_datetime(["2015-01-10 00:00", "2015-01-10 01:00"]),
        })
        failures = pd.DataFrame({
            "machineID": [1],
            "datetime": pd.to_datetime(["2015-01-10 02:00"]),
            "failure": ["comp1"],
        })
        result = event_metrics(rows, failures, 1, "comp1", np.array([0.9, 0.9]), 0.5)
        self.assertEqual(result["event_count"], 1)
        self.assertEqual(result["detected_events"], 1)
        self.assertEqual(result["false_alarms"], 1)
        self.assertEqual(result["lead_time_hours"]["median"], 1.0)
        self.assertEqual(result["warning_coverage"]["fraction_of_all_events_warned_at_least_24h"], 0.0)

    def test_event_metrics_report_long_warning_coverage_over_all_events(self):
        rows = pd.DataFrame({"machineID": [1], "datetime": pd.to_datetime(["2015-01-10 00:00"])})
        failures = pd.DataFrame({
            "machineID": [1, 1],
            "datetime": pd.to_datetime(["2015-01-11 00:00", "2015-01-11 06:00"]),
            "failure": ["comp1", "comp1"],
        })
        result = event_metrics(rows, failures, 168, "comp1", np.array([0.9]), 0.5)
        self.assertEqual(result["event_count"], 2)
        self.assertEqual(result["warning_coverage"]["events_warned_at_least_24h"], 1)
        self.assertEqual(result["warning_coverage"]["fraction_of_all_events_warned_at_least_24h"], 0.5)
        self.assertEqual(result["warning_coverage"]["events_warned_at_least_7d"], 0)

    def test_validation_alert_budget_curve_selects_only_validation_operating_points(self):
        rows = pd.DataFrame({
            "machineID": [1, 1, 1, 1],
            "datetime": pd.date_range("2015-01-10", periods=4, freq="h"),
        })
        failures = pd.DataFrame({
            "machineID": [1], "datetime": pd.to_datetime(["2015-01-10 02:00"]),
            "failure": ["comp1"],
        })
        scores = np.array([0.9, 0.8, 0.7, 0.1])
        labels = np.array([1, 1, 0, 0], dtype=np.uint8)
        curve = validation_alert_budget_curve(
            rows, failures, 1, "comp1", labels, scores, [0.0, 1.0], threshold_quantiles=5,
        )
        self.assertEqual([p["candidate_budget_per_machine_week"] for p in curve], [0.0, 1.0])
        self.assertTrue(all(p["budget_feasible"] for p in curve))
        self.assertLessEqual(curve[0]["false_alarms_per_machine_week"], 0.0)
        self.assertLessEqual(curve[1]["false_alarms_per_machine_week"], 1.0)
        self.assertGreaterEqual(curve[1]["event_recall"], curve[0]["event_recall"])


if __name__ == "__main__":
    unittest.main()
