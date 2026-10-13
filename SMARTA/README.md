# SMARTA

SMARTA indexes the PDFs and spreadsheet files in `data/` into a local SQLite database (`data/smarta.sqlite3`) and uses SQLite full-text search for grounded chat responses. The workbook's maintenance rows are also stored in the `maintenance_logs` SQL table. The corpus is built automatically when the API starts.

## Run

From this directory:

```sh
../.venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000
```

The Flutter app is under `flutter_app/`. The API's `/health` endpoint reports whether its corpus is ready and how many indexed records it contains.

When files in `data/` change, restart the API or force a refresh with:

```sh
../.venv/bin/python refresh_corpus.py
```

## Optional external SQL source

SMARTA reads `maintenance_logs`, `smarta_maintenance_logs`, and `smarta_documents` from MySQL when configured. On macOS, add the existing MySQL credential to the login Keychain with service `Mysql@localhost:3306` and account `root`. SMARTA retrieves it through the Keychain API; the password is not stored in source code or a `.env` file. Alternatively, set `SMARTA_DATABASE_URL` in the API process environment using a secure local launcher.

After the Keychain entry is present, run:

```sh
../.venv/bin/python transfer_to_mysql.py
```

This creates or updates SMARTA-owned MySQL tables, leaving any existing `maintenance_logs` table untouched. It transfers every indexed PDF chunk and spreadsheet maintenance row. The API imports those MySQL rows into its local searchable corpus on startup. If SQL is unavailable, local documents continue to work.

## AI4I predictive maintenance model

The predictive model uses the supplied AI4I 2020 archive. Keep the original ZIP unchanged and place it at `~/Downloads/ai4i+2020+predictive+maintenance+dataset.zip` (or edit `DEFAULT_ARCHIVE` in `predictive/ai4i.py` to point to another local copy). Training extracts its single CSV to `data/ai4i/ai4i2020.csv`; raw data and generated models/metrics are excluded from Git.

Train and evaluate the model from this directory:

```sh
../.venv/bin/python predictive/train_ai4i.py
```

This creates `models/ai4i_model.joblib` and `models/ai4i_metrics.json`. The dataset has 10,000 records. Model inputs are `Type`, air temperature, process temperature, rotational speed, torque, and tool wear. `UDI`, `Product ID`, `Machine failure`, and all mode indicators are excluded from input features. Machine failure is trained as a binary classifier; TWF, HDF, PWF, OSF, and RNF are handled independently because labels are not treated as mutually exclusive. RNF is omitted from inference because there are only 19 positive examples (the minimum support is 20).

Start the API as above, then submit an operating point to `POST /predict`:

```json
{
  "machine_id": "Machine-01",
  "observed_at": "2026-10-13T09:00:00Z",
  "features": {
    "product_type": "M",
    "air_temperature_k": 298.1,
    "process_temperature_k": 308.6,
    "rotational_speed_rpm": 1551,
    "torque_nm": 42.8,
    "tool_wear_min": 20
  }
}
```

The response separates model classifications/scores from retrieved evidence and a grounded recommendation. Scores are explicitly uncalibrated random-forest scores. A machine identifier is not considered evidence of a sensor connection; the API uses it only to look for exact machine-specific historical records. If the records do not support an action, SMARTA says so. This model categorizes the supplied operating point within a synthetic dataset distribution; it does not predict a failure date, lead time, or real-world machine outcome.

The Flutter app exposes **Predict** in the chat top bar. The prediction section has a **Dashboard** tab for model readiness/version, supported modes, the selected operating point, and the latest result; and a **Machine Simulator** tab with editable values, dataset-range validation, **Run Prediction**, and **Reset**. The simulator inputs are explicitly marked as simulated, not live sensor readings. Model classes/scores are displayed separately from RAG evidence and possible checks. `GET /predict/metadata` supplies artifact readiness, supported labels, and the exact feature ranges without retraining.

Run the web UI from `flutter_app/` with:

```sh
flutter run -d web-server --web-hostname 127.0.0.1 --web-port 5173
```

The app calls `http://localhost:8000` by default. Configure a different address in `flutter_app/lib/services/api_service.dart` when running the API on another host.

Run backend tests from this directory with `../.venv/bin/python -m unittest discover -s tests -v`. Run Flutter checks from `flutter_app/` with `flutter test` and `flutter analyze` when Flutter is installed.

## Experimental Azure PdM benchmark

The separate `experiments/azure_pdm/` package is an offline experiment only. It predicts logged events from trailing telemetry and event history; it is not connected to the production API or Flutter simulator. The scores are uncalibrated and the archive is a synthetic benchmark. Its license was not included in the supplied ZIP, so redistribution and deployment rights remain unverified.

Run the experiment with the supplied archive:

```sh
../.venv/bin/python -m experiments.azure_pdm.train \
  --dataset-zip ~/Downloads/archive.zip
```

To reproduce the integrity audit of the completed saved run without retraining it:

```sh
../.venv/bin/python -m experiments.azure_pdm.audit \
  --dataset-zip ~/Downloads/archive.zip \
  --source-run run_20261013T112729_896513000Z
```

Each training or audit run writes unique metrics and reports. `config.json` contains unapproved exploratory alert-budget candidates; the approved operating budget and minimum event recall remain unset. The audit command verifies the supplied ZIP hash, reloads saved artifacts, reproduces locked-test AP, and reports feature-group diagnostics and validation-only alert-budget curves. It does not modify the production AI4I artifact.
