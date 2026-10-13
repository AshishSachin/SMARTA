"""Extract and train the AI4I model from the supplied archive."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from predictive.ai4i import DEFAULT_ARCHIVE, inspect_archive, train_model


if __name__ == "__main__":
    csv_path = inspect_archive(DEFAULT_ARCHIVE)
    report = train_model(csv_path)
    print(json.dumps({
        "dataset": str(csv_path),
        "rows": report["dataset"]["rows"],
        "machine_failure": report["machine_failure"]["random_forest"],
        "baseline": report["machine_failure"]["prior_baseline"],
        "failure_modes": report["failure_modes"],
    }, indent=2))
