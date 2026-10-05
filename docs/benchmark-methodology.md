# Benchmark methodology

Benchmark Center executes 15 measured conditions: trigger, label flipping and OOD at 1%, 2%, 5%, 10% and 20%, with 100 generated images per condition. Counts TP, FP, FN and TN derive from ground truth compared with actual detector decisions; precision, recall, F1, FPR and FNR are computed from those counts. Performance.now measures latency. GPU, peak memory, AUROC, attack-size sweeps and embedding-fusion comparisons are not reported because they were not measured.

The calibration run uses 120 training and 60 independent held-out fixtures with distinct seeds. A sigmoid model is fit to raw corner scores by logistic loss. Brier score and ten-bin expected calibration error are measured on held-out fixtures. This calibration is only applied to the synthetic test-card trigger domain. Unrelated uploaded images keep confidence null. Risk scores are transparent policy scores, not probabilities.

No claimed precision or detection guarantee extends to real CV datasets. A near-perfect result on these simple fixtures only checks pipeline consistency. The full specification still needs representative poisoned/clean datasets, established baselines, uncertainty estimates, false-positive review and reproducible resource profiling.
