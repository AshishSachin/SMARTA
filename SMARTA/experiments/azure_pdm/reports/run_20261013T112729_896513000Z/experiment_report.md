# Isolated Azure PdM experiment

## Status and scope

This report describes an offline benchmark experiment. It does not change or replace AI4I, production API behavior, or Flutter. Scores are uncalibrated model scores and are not production predictions.

- Dataset ZIP SHA-256: `7575444d4d605b1f7155ab937cf541243afe07fce1afba998bf4195e8e84e1eb`
- Configuration SHA-256: `b47f6edcfc3d93cce33247388b1fffa220432777ea88ab0cf2c63bfdb023f403`
- Random seed: `20261013`
- Deployment acceptance: undecided: operational alert budget and minimum recall are unset
- Provenance: matches the Microsoft Azure PdM sample schema and counts. Microsoft's [sample notebook](https://github.com/microsoft/sqlworkshops/blob/master/SQLServerAndAzureMachineLearning/ML%20Services%20for%20SQL%20Server/notebooks/Predictive%20Maintenance%20in%20Python%20Notebook.ipynb) describes a synthesis of real-world business problems whose data is created through simulation. The notebook repository has an [MIT license](https://github.com/microsoft/sqlworkshops/blob/master/LICENSE), but the supplied ZIP has no dataset-specific license; whether the repository license applies to the data, and the rights to redistribute or deploy this dataset, remain unverified.

## Data audit

- Rows: telemetry 876,100; failures 761; errors 3,919; maintenance 3,286; machines 100.
- Telemetry coverage: 2015-01-01T06:00:00 to 2016-01-01T06:00:00; 100 machines; observed cadence hours [1.0].
- Failure labels: {'comp1': 192, 'comp2': 259, 'comp3': 131, 'comp4': 179}; 719 distinct machine-hours; 42 hours include multiple component failures.
- Exact failure-to-maintenance triple mismatches: 18. The failure table remains the target source, so unmatched failures are retained. Maintenance-only rows remain historical replacement events and are never relabeled as failures.
- Errors with multiple same-machine/hour rows: 303 excess rows; event counts are aggregated before feature construction.
- Machine age is excluded because its as-of date is not defined in the archive. Model category is evaluated only as a separate feature ablation. Machine ID is never a predictor.

## Labels and feature timing

- Each target is a logged component failure in `(t, t + H]`. The event at exactly `t` is excluded. Next-hour uses H=1 hour; candidate warning horizons use H=24 and H=168 hours.
- Features at cutoff t use only telemetry and event records with timestamps strictly less than t. Rolling telemetry windows contain the previous complete hourly observations. A 168-hour telemetry history is required.
- Rows are excluded when the full future horizon is not observed. Failure timestamps are hourly rounded, so event-time boundaries and warning lead times are approximate. These are logged-event targets, not verified physical onset labels.
- Historical failure and maintenance counts are included only for events strictly before t. Future maintenance is not a feature. The primary target is an event under the benchmark’s observed replacement process; preventive maintenance can alter future observed event risk.

## Evaluation design

- Chronological split: train before the validation cutoff with a 7-day pre-boundary purge, validate in the following date block with a 7-day pre-test purge, and test in the final date block with full 7-day label coverage.
- Machine-held-out split: machines are assigned 60/20/20 by a seeded split stratified on static model category only. Train, validation, and test use distinct machine IDs and chronological date blocks.
- Comparisons use identical eligible rows per split and horizon: constant prior/majority, regularized logistic regression, and a bounded-depth decision tree. The model-category ablation is compared separately.
- Decision thresholds are selected on validation only by the configured maximum-F1 rule. Test thresholds are never tuned. Validation selection among model/feature variants uses validation average precision only.
- Average precision is the stepwise PR-area metric. Event metrics deduplicate machine/component alerts with a horizon-length cooldown. Cluster bootstrap intervals resample whole machines.

## Locked-test results

Test results are reported for the predeclared candidates. Candidate selection is recorded from validation results; the test set was not used to select thresholds or features. The constant-prior AP is the test prevalence; its fixed 0.5 majority threshold emits no alerts for these rare targets, so it has no false alarms and misses every logged event. Review `metrics/run_20261013T112729_896513000Z/evaluation.json` for per-target confusion counts, AP, event recall, missed events, false alarms per machine-week, lead times, and machine-cluster AP intervals.

| Split | Horizon | Target | Selected on validation | Test AP | Prior AP | Test precision | Test recall | Test event recall | False alarms / machine-week | Missed events | Majority misses | AP 95% machine CI |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| chronological_known_machines | next_hour | any | decision_tree / base_no_model | 0.0793 | 0.0007 | 0.0714 | 0.1474 | 0.14736842105263157 | 0.23574402467232075 | 81 | 95 | 0.0625–0.0996 |
| chronological_known_machines | next_hour | comp1 | logistic / base_no_model | 0.0523 | 0.0002 | 0.0401 | 0.5217 | 0.5217391304347826 | 0.37175019275250576 | 11 | 23 | 0.0464–0.1314 |
| chronological_known_machines | next_hour | comp2 | logistic / base_no_model | 0.0570 | 0.0003 | 0.0538 | 0.3000 | 0.3 | 0.273307632999229 | 28 | 40 | 0.0473–0.0985 |
| chronological_known_machines | next_hour | comp3 | decision_tree / base_no_model | 0.0500 | 0.0001 | 0.0857 | 0.1765 | 0.17647058823529413 | 0.041449498843484964 | 14 | 17 | 0.0340–0.0894 |
| chronological_known_machines | next_hour | comp4 | logistic / base_no_model | 0.0627 | 0.0002 | 0.0333 | 0.0500 | 0.05 | 0.03756360832690825 | 19 | 20 | 0.0537–0.1102 |
| chronological_known_machines | 24h | any | decision_tree / base_no_model | 0.9352 | 0.0176 | 0.9228 | 0.9325 | 0.9591836734693877 | 0.014248265227447958 | 4 | 2283 | 0.9067–0.9493 |
| chronological_known_machines | 24h | comp1 | decision_tree / base_no_model | 0.8421 | 0.0043 | 0.8895 | 0.9330 | 1.0 | 0.0051811873554356205 | 0 | 552 | 0.7374–0.9313 |
| chronological_known_machines | 24h | comp2 | decision_tree / plus_model_ablation | 0.9551 | 0.0074 | 0.9581 | 0.9272 | 0.9512195121951219 | 0.0012952968388589051 | 2 | 961 | 0.9481–0.9605 |
| chronological_known_machines | 24h | comp3 | logistic / plus_model_ablation | 0.9493 | 0.0031 | 0.9369 | 0.9461 | 1.0 | 0.0051811873554356205 | 0 | 408 | 0.9330–0.9634 |
| chronological_known_machines | 24h | comp4 | decision_tree / base_no_model | 0.9502 | 0.0037 | 0.9485 | 0.9544 | 0.9090909090909091 | 0.0025905936777178102 | 2 | 482 | 0.9370–0.9590 |
| chronological_known_machines | 7d | any | logistic / plus_model_ablation | 0.4494 | 0.1260 | 0.3613 | 0.4881 | 0.9009009009009009 | 0.5492058596761757 | 11 | 16336 | 0.4086–0.5090 |
| chronological_known_machines | 7d | comp1 | logistic / base_no_model | 0.2644 | 0.0293 | 0.6168 | 0.1737 | 0.8 | 0.05699306090979183 | 6 | 3799 | 0.2093–0.3123 |
| chronological_known_machines | 7d | comp2 | logistic / plus_model_ablation | 0.2887 | 0.0552 | 0.3974 | 0.2318 | 0.9545454545454546 | 0.18393215111796454 | 2 | 7156 | 0.2489–0.3293 |
| chronological_known_machines | 7d | comp3 | logistic / plus_model_ablation | 0.3739 | 0.0217 | 0.5236 | 0.2802 | 0.9444444444444444 | 0.05699306090979183 | 1 | 2809 | 0.3087–0.4443 |
| chronological_known_machines | 7d | comp4 | logistic / plus_model_ablation | 0.2577 | 0.0272 | 0.4190 | 0.2058 | 0.88 | 0.06735543562066307 | 3 | 3533 | 0.2017–0.3094 |
| future_unseen_machines | next_hour | any | logistic / base_no_model | 0.0539 | 0.0006 | 0.0488 | 0.1250 | 0.125 | 0.25258288357748654 | 14 | 16 | 0.0455–0.1309 |
| future_unseen_machines | next_hour | comp1 | logistic / plus_model_ablation | 0.0909 | 0.0000 | 0.0625 | 1.0000 | 1.0 | 0.09714726291441789 | 0 | 1 | 0.0500–0.5000 |
| future_unseen_machines | next_hour | comp2 | logistic / base_no_model | 0.0605 | 0.0003 | 0.0571 | 0.2222 | 0.2222222222222222 | 0.21372397841171936 | 7 | 9 | 0.0483–0.2730 |
| future_unseen_machines | next_hour | comp3 | logistic / base_no_model | 0.0942 | 0.0001 | 0.0000 | 0.0000 | 0.0 | 0.0 | 3 | 3 | 0.0262–0.2500 |
| future_unseen_machines | next_hour | comp4 | decision_tree / base_no_model | 0.0979 | 0.0001 | 0.1429 | 0.6667 | 0.6666666666666666 | 0.07771781033153431 | 1 | 3 | 0.0394–0.2500 |
| future_unseen_machines | 24h | any | decision_tree / plus_model_ablation | 0.9400 | 0.0148 | 0.9547 | 0.8776 | 1.0 | 0.006476484194294526 | 0 | 384 | 0.8988–0.9609 |
| future_unseen_machines | 24h | comp1 | logistic / base_no_model | 0.4994 | 0.0009 | 0.6875 | 0.9167 | 1.0 | 0.006476484194294526 | 0 | 24 | 0.2804–0.8831 |
| future_unseen_machines | 24h | comp2 | logistic / plus_model_ablation | 0.9428 | 0.0083 | 0.9324 | 0.9583 | 1.0 | 0.006476484194294526 | 0 | 216 | 0.9232–0.9577 |
| future_unseen_machines | 24h | comp3 | decision_tree / base_no_model | 0.8172 | 0.0028 | 0.9318 | 0.5694 | 1.0 | 0.006476484194294526 | 0 | 72 | 0.6626–0.9612 |
| future_unseen_machines | 24h | comp4 | decision_tree / plus_model_ablation | 0.9488 | 0.0028 | 0.9583 | 0.9583 | 1.0 | 0.0 | 0 | 72 | 0.9375–0.9567 |
| future_unseen_machines | 7d | any | logistic / plus_model_ablation | 0.3926 | 0.1186 | 0.3602 | 0.3703 | 0.9 | 0.4209714726291442 | 2 | 3076 | 0.3195–0.4411 |
| future_unseen_machines | 7d | comp1 | logistic / base_no_model | 0.0657 | 0.0158 | 0.1949 | 0.0561 | 0.3333333333333333 | 0.05181187355435621 | 2 | 410 | 0.0107–0.1452 |
| future_unseen_machines | 7d | comp2 | logistic / plus_model_ablation | 0.3168 | 0.0667 | 0.3530 | 0.2451 | 0.9090909090909091 | 0.18781804163454124 | 1 | 1730 | 0.2070–0.3908 |
| future_unseen_machines | 7d | comp3 | logistic / plus_model_ablation | 0.2429 | 0.0194 | 0.4303 | 0.2143 | 1.0 | 0.05828835774865074 | 0 | 504 | 0.1568–0.3286 |
| future_unseen_machines | 7d | comp4 | logistic / plus_model_ablation | 0.1742 | 0.0213 | 0.3516 | 0.1392 | 0.75 | 0.07124132613723978 | 1 | 553 | 0.0446–0.2324 |

## Acceptance and limitations

The alert budget and minimum acceptable event recall are intentionally unset in `config.json`; no defensible operational values were supplied. Deployment acceptance is therefore undecided regardless of benchmark scores. The benchmark is synthetic, spans about one year, has sparse component events, uses rounded timestamps, and does not verify repairs or physical failure onset. These results cannot establish calibrated probabilities, guaranteed 24-hour/7-day warning, or production generalization.

## Reproduction

```bash
cd /Users/ashishsachinas/Desktop/SMARTA/SMARTA
../.venv/bin/python -m experiments.azure_pdm.train
../.venv/bin/python -m unittest discover -s experiments/azure_pdm/tests -v
```

To use another copy of the supplied archive, pass `--dataset-zip /path/to/archive.zip`. Raw CSV members are read directly from the ZIP; they are not extracted or modified.
