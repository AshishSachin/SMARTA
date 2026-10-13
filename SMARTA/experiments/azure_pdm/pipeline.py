"""Leakage-aware preparation for the isolated Azure PdM benchmark experiment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import zipfile

import numpy as np
import pandas as pd


FILES = {
    "telemetry": "PdM_telemetry.csv",
    "failures": "PdM_failures.csv",
    "errors": "PdM_errors.csv",
    "maintenance": "PdM_maint.csv",
    "machines": "PdM_machines.csv",
}
SENSORS = ("volt", "rotate", "pressure", "vibration")
COMPONENTS = ("comp1", "comp2", "comp3", "comp4")
ERROR_CODES = ("error1", "error2", "error3", "error4", "error5")
HORIZONS_HOURS = {"next_hour": 1, "24h": 24, "7d": 168}


@dataclass
class DatasetTables:
    telemetry: pd.DataFrame
    failures: pd.DataFrame
    errors: pd.DataFrame
    maintenance: pd.DataFrame
    machines: pd.DataFrame


def load_tables(zip_path: str | Path) -> DatasetTables:
    """Read the supplied archive without extracting or changing its raw files."""
    path = Path(zip_path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset archive does not exist: {path}")
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        missing = sorted(set(FILES.values()) - names)
        if missing:
            raise ValueError(f"Dataset archive is missing required CSV files: {missing}")

        def read(name: str, dates: bool = True) -> pd.DataFrame:
            frame = pd.read_csv(archive.open(name))
            if dates:
                frame["datetime"] = pd.to_datetime(frame["datetime"], errors="raise")
            return frame

        tables = DatasetTables(
            telemetry=read(FILES["telemetry"]),
            failures=read(FILES["failures"]),
            errors=read(FILES["errors"]),
            maintenance=read(FILES["maintenance"]),
            machines=read(FILES["machines"], dates=False),
        )
    validate_tables(tables)
    return tables


def validate_tables(tables: DatasetTables) -> dict[str, Any]:
    """Validate the observed schema and return a reproducible data-quality summary."""
    expected = {
        "telemetry": {"datetime", "machineID", *SENSORS},
        "failures": {"datetime", "machineID", "failure"},
        "errors": {"datetime", "machineID", "errorID"},
        "maintenance": {"datetime", "machineID", "comp"},
        "machines": {"machineID", "model", "age"},
    }
    for table_name, columns in expected.items():
        frame = getattr(tables, table_name)
        if not columns.issubset(frame.columns):
            raise ValueError(f"{table_name} missing columns: {sorted(columns - set(frame.columns))}")
        if frame[list(columns)].isna().any().any():
            raise ValueError(f"{table_name} contains missing required values")

    tel = tables.telemetry.sort_values(["machineID", "datetime"])
    if tel.duplicated(["machineID", "datetime"]).any():
        raise ValueError("Telemetry has duplicate machine/time keys")
    machine_ids = set(tables.machines.machineID.astype(int))
    telemetry_ids = set(tel.machineID.astype(int))
    if machine_ids != telemetry_ids:
        raise ValueError("Machine metadata IDs do not exactly match telemetry IDs")
    if not set(tables.failures.failure).issubset(COMPONENTS):
        raise ValueError("Unexpected component in failure labels")
    if not set(tables.maintenance.comp).issubset(COMPONENTS):
        raise ValueError("Unexpected component in maintenance records")
    if not set(tables.errors.errorID).issubset(ERROR_CODES):
        raise ValueError("Unexpected error code")
    for name in ("failures", "errors", "maintenance"):
        frame = getattr(tables, name)
        join = frame[["machineID", "datetime"]].merge(
            tel[["machineID", "datetime"]], on=["machineID", "datetime"], how="left", indicator=True
        )
        if (join["_merge"] == "left_only").any():
            # Maintenance includes dates outside telemetry coverage, so only assert
            # event alignment for failure/error labels that define model targets.
            if name != "maintenance":
                raise ValueError(f"{name} contains records not aligned to telemetry")

    return audit_summary(tables)


def audit_summary(tables: DatasetTables) -> dict[str, Any]:
    tel = tables.telemetry
    failures = tables.failures
    maintenance = tables.maintenance
    exact = failures.merge(
        maintenance,
        left_on=["machineID", "datetime", "failure"],
        right_on=["machineID", "datetime", "comp"],
        how="left",
        indicator=True,
    )
    fail_hours = failures[["machineID", "datetime"]].drop_duplicates()
    multi = failures.groupby(["machineID", "datetime"]).size()
    telemetry_gap_hours = (
        tel.sort_values(["machineID", "datetime"])
        .groupby("machineID")["datetime"]
        .diff()
        .dropna()
        .dt.total_seconds()
        .div(3600)
    )
    return {
        "row_counts": {
            "telemetry": int(len(tel)),
            "failures": int(len(failures)),
            "errors": int(len(tables.errors)),
            "maintenance": int(len(maintenance)),
            "machines": int(len(tables.machines)),
        },
        "telemetry": {
            "machines": int(tel.machineID.nunique()),
            "rows_per_machine_min": int(tel.groupby("machineID").size().min()),
            "rows_per_machine_max": int(tel.groupby("machineID").size().max()),
            "start": tel.datetime.min().isoformat(),
            "end": tel.datetime.max().isoformat(),
            "cadence_hours": sorted(telemetry_gap_hours.unique().tolist()),
        },
        "failure_labels": {
            "machines_with_failures": int(failures.machineID.nunique()),
            "counts_by_component": {str(k): int(v) for k, v in failures.failure.value_counts().sort_index().items()},
            "unique_machine_failure_hours": int(len(fail_hours)),
            "multi_component_failure_hours": int((multi > 1).sum()),
            "unmatched_exact_maintenance_rows": int((exact["_merge"] == "left_only").sum()),
            "unmatched_failure_timestamps": sorted(
                failures.merge(
                    maintenance,
                    left_on=["machineID", "datetime", "failure"],
                    right_on=["machineID", "datetime", "comp"],
                    how="left",
                    indicator=True,
                ).loc[lambda x: x["_merge"] == "left_only", "datetime"].dt.strftime("%Y-%m-%d %H:%M:%S").unique().tolist()
            ),
        },
        "maintenance": {
            "not_in_failure_table_exact_key": int(len(maintenance) - int((exact["_merge"] == "both").sum())),
            "start": maintenance.datetime.min().isoformat(),
            "end": maintenance.datetime.max().isoformat(),
        },
        "errors": {
            "counts_by_code": {str(k): int(v) for k, v in tables.errors.errorID.value_counts().sort_index().items()},
            "same_machine_hour_excess_rows": int(tables.errors.duplicated(["machineID", "datetime"]).sum()),
        },
        "machines": {
            "model_counts": {str(k): int(v) for k, v in tables.machines.model.value_counts().sort_index().items()},
            "age_min": int(tables.machines.age.min()),
            "age_max": int(tables.machines.age.max()),
            "age_used": False,
        },
    }


def _prior_event_window_counts(events: pd.DataFrame, machine_id: int, index: pd.DatetimeIndex,
                               value_col: str, value: str, window: int) -> np.ndarray:
    """Count aggregated events in [t-window, t), including pre-telemetry history."""
    part = events.loc[(events.machineID == machine_id) & (events[value_col] == value), ["datetime"]]
    if part.empty:
        return np.zeros(len(index), dtype="float32")
    # Aggregate on machine/code/time before the rolling join. Prefix sums preserve
    # multiple logged events in one hour while avoiding row multiplication.
    aggregated = part.groupby("datetime").size().sort_index()
    event_times = pd.DatetimeIndex(aggregated.index).to_numpy(dtype="datetime64[ns]")
    cumulative = np.concatenate(([0], aggregated.to_numpy(dtype=np.int64).cumsum()))
    decision_times = index.to_numpy(dtype="datetime64[ns]")
    left = np.searchsorted(event_times, decision_times - np.timedelta64(window, "h"), side="left")
    right = np.searchsorted(event_times, decision_times, side="left")
    return (cumulative[right] - cumulative[left]).astype("float32")


def build_features(tables: DatasetTables, include_model: bool = False) -> pd.DataFrame:
    """Build one hourly row per machine using only observations strictly before t."""
    tel = tables.telemetry.sort_values(["machineID", "datetime"]).copy()
    model_by_id = tables.machines.set_index("machineID")["model"].to_dict()
    feature_rows: list[pd.DataFrame] = []
    for machine_id, group in tel.groupby("machineID", sort=True):
        group = group.set_index("datetime").sort_index()
        index = pd.DatetimeIndex(group.index)
        row = pd.DataFrame(index=index)
        # The timestamp t is the decision cutoff. Shift first, then roll over the
        # previous complete hourly samples [t-window, t-1h].
        for sensor in SENSORS:
            past = group[sensor].shift(1)
            for window in (3, 24, 168):
                rolling = past.rolling(window=window, min_periods=window)
                row[f"{sensor}_mean_{window}h"] = rolling.mean().astype("float32")
                row[f"{sensor}_std_{window}h"] = rolling.std(ddof=0).astype("float32")
                row[f"{sensor}_min_{window}h"] = rolling.min().astype("float32")
                row[f"{sensor}_max_{window}h"] = rolling.max().astype("float32")
            row[f"{sensor}_delta_3h"] = (past - past.shift(3)).astype("float32")

        for source, label_col, values, windows in (
            (tables.errors, "errorID", ERROR_CODES, (24, 168)),
            (tables.failures, "failure", COMPONENTS, (24, 168)),
            (tables.maintenance, "comp", COMPONENTS, (24, 168)),
        ):
            for value in values:
                for window in windows:
                    row[f"past_{label_col}_{value}_{window}h"] = _prior_event_window_counts(
                        source, int(machine_id), index, label_col, value, window
                    )

        row["machineID"] = int(machine_id)
        if include_model:
            row["model"] = model_by_id[int(machine_id)]
        feature_rows.append(row.reset_index(names="datetime"))

    frame = pd.concat(feature_rows, ignore_index=True).sort_values(["machineID", "datetime"])
    # A full 7-day telemetry history is mandatory; this also ensures every
    # requested trailing telemetry window is fully observed.
    return frame.loc[frame[[f"volt_mean_168h", f"rotate_mean_168h", f"pressure_mean_168h", f"vibration_mean_168h"]].notna().all(axis=1)].reset_index(drop=True)


def build_targets(features: pd.DataFrame, failures: pd.DataFrame) -> pd.DataFrame:
    """Return multi-label targets for (t, t+H], excluding the event at t."""
    result = features[["machineID", "datetime"]].copy()
    event_map = {
        (int(machine_id), component): pd.DatetimeIndex(group.datetime.sort_values())
        for (machine_id, component), group in failures.groupby(["machineID", "failure"])
    }
    last_by_machine = features.groupby("machineID").datetime.max().to_dict()
    for horizon_name, hours in HORIZONS_HOURS.items():
        components = np.zeros((len(features), len(COMPONENTS)), dtype=np.uint8)
        valid = np.zeros(len(features), dtype=bool)
        for machine_id, positions in features.groupby("machineID", sort=False).indices.items():
            ts = pd.DatetimeIndex(features.iloc[positions].datetime)
            valid[positions] = ts + pd.Timedelta(hours=hours) <= last_by_machine[int(machine_id)]
            for j, component in enumerate(COMPONENTS):
                events = event_map.get((int(machine_id), component))
                if events is None or len(events) == 0:
                    continue
                lo = events.searchsorted(ts, side="right")  # strict: event at t is not future
                hi = events.searchsorted(ts + pd.Timedelta(hours=hours), side="right")
                components[positions, j] = (hi > lo).astype(np.uint8)
        for j, component in enumerate(COMPONENTS):
            result[f"y_{horizon_name}_{component}"] = components[:, j]
        result[f"y_{horizon_name}_any"] = components.max(axis=1)
        result[f"valid_{horizon_name}"] = valid
    return result


def chronological_masks(rows: pd.DataFrame, config: dict[str, Any]) -> dict[str, np.ndarray]:
    """Global time split with a 7-day label purge at both cut points."""
    cut1 = pd.Timestamp(config["split"]["train_validation_cutoff"])
    cut2 = pd.Timestamp(config["split"]["validation_test_cutoff"])
    purge = pd.Timedelta(hours=int(config["max_horizon_hours"]))
    t = pd.to_datetime(rows.datetime)
    train_start = pd.Timestamp(config["split"]["train_start"])
    val_start = cut1
    test_start = cut2
    test_end = pd.Timestamp(config["split"]["dataset_end"]) - purge
    return {
        "train": ((t >= train_start) & (t < cut1 - purge)).to_numpy(),
        "validation": ((t >= val_start) & (t < cut2 - purge)).to_numpy(),
        "test": ((t >= test_start) & (t <= test_end)).to_numpy(),
    }


def machine_group_masks(rows: pd.DataFrame, machines: pd.DataFrame,
                        config: dict[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, list[int]]]:
    """60/20/20 machine split stratified only on static model, then chronological."""
    from sklearn.model_selection import train_test_split

    ids = machines.machineID.to_numpy()
    model = machines.set_index("machineID").loc[ids, "model"].to_numpy()
    seed = int(config["seed"])
    train_ids, remainder = train_test_split(ids, test_size=0.4, random_state=seed, stratify=model)
    remainder_model = machines.set_index("machineID").loc[remainder, "model"].to_numpy()
    val_ids, test_ids = train_test_split(remainder, test_size=0.5, random_state=seed + 1,
                                         stratify=remainder_model)
    temporal = chronological_masks(rows, config)
    machine_col = rows.machineID.to_numpy()
    masks = {
        "train": temporal["train"] & np.isin(machine_col, train_ids),
        "validation": temporal["validation"] & np.isin(machine_col, val_ids),
        "test": temporal["test"] & np.isin(machine_col, test_ids),
    }
    groups = {"train": sorted(map(int, train_ids)), "validation": sorted(map(int, val_ids)),
              "test": sorted(map(int, test_ids))}
    return masks, groups
