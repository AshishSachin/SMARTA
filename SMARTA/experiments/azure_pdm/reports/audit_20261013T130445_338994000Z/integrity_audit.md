# Azure PdM integrity audit

This is a post-training audit of saved experimental artifacts. It does not change AI4I, production inference, or the original run's metrics.

- Audit run: `audit_20261013T130445_338994000Z`
- Source training run: `run_20261013T112729_896513000Z`
- Dataset ZIP SHA-256: `7575444d4d605b1f7155ab937cf541243afe07fce1afba998bf4195e8e84e1eb`
- Provenance: the archive matches Microsoft's Azure PdM sample schema and counts. Microsoft's [sample notebook](https://github.com/microsoft/sqlworkshops/blob/master/SQLServerAndAzureMachineLearning/ML%20Services%20for%20SQL%20Server/notebooks/Predictive%20Maintenance%20in%20Python%20Notebook.ipynb) describes simulated data synthesized from multiple real-world business problems. The upstream repository's [MIT license](https://github.com/microsoft/sqlworkshops/blob/master/LICENSE) is not a dataset-specific license, so applicability to the supplied ZIP and redistribution/deployment rights remain unverified.
- Saved selected candidates re-evaluated: 30
- Locked-test AP reproduced within 1e-10: True
- Model outputs remain uncalibrated logged-event scores; none are available for production routing.

## Integrity findings

- Telemetry features are shifted by one full observation before rolling; all windows end at t-1 hour.
- Error, failure, and maintenance windows use [t-window,t); events at t are excluded.
- Labels are generated from failure rows only with interval (t,t+H]; maintenance rows do not create labels.
- Preprocessing saved in each selected artifact is applied without fitting during this audit.
- machineID and datetime are checked out of every saved feature schema; machine age is checked absent.
- Chronological and machine-group masks are rebuilt from the hashed source configuration.
- Failure events at the same cutoff are excluded from historical failure and maintenance features; a failure logged at `t` is also excluded from the target interval `(t,t+H]`.
- The 18 failure rows without exact maintenance matches remain failure labels. Maintenance-only events remain historical features only.
- No direct target, future telemetry, future event, post-failure measurement, or identifier feature was detected in saved selected schemas.

## Why 24-hour AP is unusually high

The audit reproduces the selected saved models on the same configured eligible rows. It also fits small diagnostic ablations with training-only preprocessing. Ablation test values are used only to diagnose benchmark signal and are not used to select or promote a model.

| Split | Feature group | Model | Features | Validation AP | Test AP (diagnostic) |
|---|---|---|---:|---:|---:|
| chronological_known_machines | all_available_features | logistic | 78 | 0.8129 | 0.8454 |
| chronological_known_machines | all_available_features | decision_tree | 78 | 0.9394 | 0.9421 |
| chronological_known_machines | telemetry_only | logistic | 52 | 0.2541 | 0.2565 |
| chronological_known_machines | telemetry_only | decision_tree | 52 | 0.2129 | 0.2133 |
| chronological_known_machines | error_history_only | logistic | 10 | 0.5416 | 0.5685 |
| chronological_known_machines | error_history_only | decision_tree | 10 | 0.6585 | 0.6779 |
| chronological_known_machines | failure_and_maintenance_history_only | logistic | 16 | 0.0324 | 0.0304 |
| chronological_known_machines | failure_and_maintenance_history_only | decision_tree | 16 | 0.0324 | 0.0304 |
| chronological_known_machines | all_event_history | logistic | 26 | 0.6253 | 0.6497 |
| chronological_known_machines | all_event_history | decision_tree | 26 | 0.6872 | 0.7064 |
| chronological_known_machines | without_error_history | logistic | 68 | 0.3538 | 0.3914 |
| chronological_known_machines | without_error_history | decision_tree | 68 | 0.3038 | 0.2973 |
| future_unseen_machines | all_available_features | logistic | 78 | 0.8129 | 0.8575 |
| future_unseen_machines | all_available_features | decision_tree | 78 | 0.9513 | 0.9316 |
| future_unseen_machines | telemetry_only | logistic | 52 | 0.3203 | 0.2113 |
| future_unseen_machines | telemetry_only | decision_tree | 52 | 0.2295 | 0.1492 |
| future_unseen_machines | error_history_only | logistic | 10 | 0.5308 | 0.7324 |
| future_unseen_machines | error_history_only | decision_tree | 10 | 0.6127 | 0.7577 |
| future_unseen_machines | failure_and_maintenance_history_only | logistic | 16 | 0.0330 | 0.0258 |
| future_unseen_machines | failure_and_maintenance_history_only | decision_tree | 16 | 0.0330 | 0.0258 |
| future_unseen_machines | all_event_history | logistic | 26 | 0.6345 | 0.7685 |
| future_unseen_machines | all_event_history | decision_tree | 26 | 0.6571 | 0.7857 |
| future_unseen_machines | without_error_history | logistic | 68 | 0.4360 | 0.3606 |
| future_unseen_machines | without_error_history | decision_tree | 68 | 0.3364 | 0.2056 |

Error history is predictive in this synthetic sample: 24-hour AP falls substantially when error history is removed, while error-only features perform much better than sensor-only or failure/maintenance-only features. The pattern survives the machine-held-out diagnostic, but the archive's generated error/failure process is not evidence that real equipment has equivalent warning behavior.

## Validation-derived alert-budget curves

Candidate budgets are exploratory and unapproved. Thresholds are selected using validation rows only; the table reports validation behavior, not an operational commitment.

| Split | Horizon | Candidate false alarms / machine-week | Validation threshold | Precision | Recall | Event recall | False alarms / machine-week |
|---|---|---:|---:|---:|---:|---:|---:|
| chronological_known_machines | next_hour | 0.05 | 0.210526 | 0.0000 | 0.0000 | 0.0 | 0 |
| chronological_known_machines | next_hour | 0.10 | 0.210526 | 0.1053 | 0.0594 | 0.0594059405940594 | 0.0661111 |
| chronological_known_machines | next_hour | 0.25 | 0.210526 | 0.1053 | 0.0594 | 0.0594059405940594 | 0.0661111 |
| chronological_known_machines | next_hour | 0.50 | 0.210526 | 0.1053 | 0.0594 | 0.0594059405940594 | 0.0661111 |
| chronological_known_machines | next_hour | 1.00 | 0.210526 | 0.1053 | 0.0594 | 0.0594059405940594 | 0.0661111 |
| chronological_known_machines | 24h | 0.05 | 1 | 0.9444 | 0.0070 | 0.0297029702970297 | 0 |
| chronological_known_machines | 24h | 0.10 | 1 | 0.9444 | 0.0070 | 0.0297029702970297 | 0 |
| chronological_known_machines | 24h | 0.25 | 1 | 0.9444 | 0.0070 | 0.0297029702970297 | 0 |
| chronological_known_machines | 24h | 0.50 | 1 | 0.9444 | 0.0070 | 0.0297029702970297 | 0 |
| chronological_known_machines | 24h | 1.00 | 0.00592922 | 0.3109 | 0.9851 | 1.0 | 0.579444 |
| chronological_known_machines | 7d | 0.05 | 0.99331 | 1.0000 | 0.0001 | 0.009009009009009009 | 0 |
| chronological_known_machines | 7d | 0.10 | 0.99331 | 1.0000 | 0.0001 | 0.009009009009009009 | 0 |
| chronological_known_machines | 7d | 0.25 | 0.282755 | 0.5730 | 0.2337 | 0.9369369369369369 | 0.204815 |
| chronological_known_machines | 7d | 0.50 | 0.175767 | 0.4178 | 0.3408 | 0.9459459459459459 | 0.356481 |
| chronological_known_machines | 7d | 1.00 | 0.175767 | 0.4178 | 0.3408 | 0.9459459459459459 | 0.356481 |
| future_unseen_machines | next_hour | 0.05 | 0.0978851 | 0.0000 | 0.0000 | 0.0 | 0 |
| future_unseen_machines | next_hour | 0.10 | 0.0978851 | 0.0000 | 0.0000 | 0.0 | 0 |
| future_unseen_machines | next_hour | 0.25 | 0.0978851 | 0.0000 | 0.0000 | 0.0 | 0 |
| future_unseen_machines | next_hour | 0.50 | 0.0978851 | 0.0000 | 0.0000 | 0.0 | 0 |
| future_unseen_machines | next_hour | 1.00 | 0.0978851 | 0.0000 | 0.0000 | 0.0 | 0 |
| future_unseen_machines | 24h | 0.05 | 1 | 1.0000 | 0.0218 | 0.047619047619047616 | 0 |
| future_unseen_machines | 24h | 0.10 | 1 | 1.0000 | 0.0218 | 0.047619047619047616 | 0 |
| future_unseen_machines | 24h | 0.25 | 1 | 1.0000 | 0.0218 | 0.047619047619047616 | 0 |
| future_unseen_machines | 24h | 0.50 | 0.00576535 | 0.3653 | 0.9821 | 1.0 | 0.427778 |
| future_unseen_machines | 24h | 1.00 | 0.00576535 | 0.3653 | 0.9821 | 1.0 | 0.427778 |
| future_unseen_machines | 7d | 0.05 | 0.940571 | 1.0000 | 0.0003 | 0.043478260869565216 | 0 |
| future_unseen_machines | 7d | 0.10 | 0.940571 | 1.0000 | 0.0003 | 0.043478260869565216 | 0 |
| future_unseen_machines | 7d | 0.25 | 0.310951 | 0.5787 | 0.2248 | 0.9130434782608695 | 0.22037 |
| future_unseen_machines | 7d | 0.50 | 0.14215 | 0.3506 | 0.4086 | 0.9565217391304348 | 0.401852 |
| future_unseen_machines | 7d | 1.00 | 0.14215 | 0.3506 | 0.4086 | 0.9565217391304348 | 0.401852 |

## Locked-test warning-time coverage

Fractions are out of all test-period logged events, including missed events. Times are relative to rounded logged event timestamps.

| Split | Horizon | Target | Events | Event recall | ≥24h coverage | ≥7d coverage | Median lead (hours) |
|---|---|---|---:|---:|---:|---:|---:|
| chronological_known_machines | next_hour | any | 95 | 0.14736842105263157 | 0.0 | 0.0 | 1.0 |
| chronological_known_machines | next_hour | comp1 | 23 | 0.5217391304347826 | 0.0 | 0.0 | 1.0 |
| chronological_known_machines | next_hour | comp2 | 40 | 0.3 | 0.0 | 0.0 | 1.0 |
| chronological_known_machines | next_hour | comp3 | 17 | 0.17647058823529413 | 0.0 | 0.0 | 1.0 |
| chronological_known_machines | next_hour | comp4 | 20 | 0.05 | 0.0 | 0.0 | 1.0 |
| chronological_known_machines | 24h | any | 98 | 0.9591836734693877 | 0.0 | 0.0 | 23.0 |
| chronological_known_machines | 24h | comp1 | 23 | 1.0 | 0.0 | 0.0 | 23.0 |
| chronological_known_machines | 24h | comp2 | 41 | 0.9512195121951219 | 0.0 | 0.0 | 23.0 |
| chronological_known_machines | 24h | comp3 | 17 | 1.0 | 0.0 | 0.0 | 23.0 |
| chronological_known_machines | 24h | comp4 | 22 | 0.9090909090909091 | 0.0 | 0.0 | 23.0 |
| chronological_known_machines | 7d | any | 111 | 0.9009009009009009 | 0.4144144144144144 | 0.0 | 23.0 |
| chronological_known_machines | 7d | comp1 | 30 | 0.8 | 0.4666666666666667 | 0.0 | 25.0 |
| chronological_known_machines | 7d | comp2 | 44 | 0.9545454545454546 | 0.8636363636363636 | 0.0 | 36.0 |
| chronological_known_machines | 7d | comp3 | 18 | 0.9444444444444444 | 0.8333333333333334 | 0.0 | 45.0 |
| chronological_known_machines | 7d | comp4 | 25 | 0.88 | 0.72 | 0.0 | 40.5 |
| future_unseen_machines | next_hour | any | 16 | 0.125 | 0.0 | 0.0 | 1.0 |
| future_unseen_machines | next_hour | comp1 | 1 | 1.0 | 0.0 | 0.0 | 1.0 |
| future_unseen_machines | next_hour | comp2 | 9 | 0.2222222222222222 | 0.0 | 0.0 | 1.0 |
| future_unseen_machines | next_hour | comp3 | 3 | 0.0 | 0.0 | 0.0 | n/a |
| future_unseen_machines | next_hour | comp4 | 3 | 0.6666666666666666 | 0.0 | 0.0 | 1.0 |
| future_unseen_machines | 24h | any | 16 | 1.0 | 0.0 | 0.0 | 23.0 |
| future_unseen_machines | 24h | comp1 | 1 | 1.0 | 0.0 | 0.0 | 23.0 |
| future_unseen_machines | 24h | comp2 | 9 | 1.0 | 0.0 | 0.0 | 23.0 |
| future_unseen_machines | 24h | comp3 | 3 | 1.0 | 0.0 | 0.0 | 23.0 |
| future_unseen_machines | 24h | comp4 | 3 | 1.0 | 0.0 | 0.0 | 23.0 |
| future_unseen_machines | 7d | any | 20 | 0.9 | 0.6 | 0.05 | 44.0 |
| future_unseen_machines | 7d | comp1 | 3 | 0.3333333333333333 | 0.0 | 0.0 | 23.0 |
| future_unseen_machines | 7d | comp2 | 11 | 0.9090909090909091 | 0.8181818181818182 | 0.0 | 44.5 |
| future_unseen_machines | 7d | comp3 | 3 | 1.0 | 0.3333333333333333 | 0.0 | 21.0 |
| future_unseen_machines | 7d | comp4 | 4 | 0.75 | 0.5 | 0.0 | 35.0 |

## Limits and decision

The source uses synthetic benchmark logs, hourly rounded event times, and a replacement process that may change future observed events. The 24-hour benchmark result survives the leakage audit as a logged-event association, but its concentration in error-history signals and lack of real-company validation prevent deployment claims. All probabilities remain uncalibrated. Operational alert budget and minimum event recall are unset, so acceptance is undecided. The saved AI4I classifier remains the only production predictive path.

Candidate budgets are configured in `experiments/azure_pdm/config.json`; this audit did not retrain models or promote artifacts.
