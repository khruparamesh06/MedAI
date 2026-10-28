"""Dependency-free evaluation metrics (NumPy only)."""
from __future__ import annotations

import numpy as np


def auroc(y_true: np.ndarray, scores: np.ndarray) -> float | None:
    """Area under the ROC curve via the rank-sum statistic (ties get average rank).

    Returns None when only one class is present, because AUROC is undefined then.
    """
    mask = ~np.isnan(y_true)
    y, s = y_true[mask].astype(int), scores[mask].astype(float)
    n_pos, n_neg = int(y.sum()), int((1 - y).sum())
    if n_pos == 0 or n_neg == 0:
        return None
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=float)
    sorted_s = s[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1
        i = j + 1
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def threshold_metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float = 0.5) -> dict:
    mask = ~np.isnan(y_true)
    y, pred = y_true[mask].astype(int), (scores[mask] >= threshold).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    return {
        "n": int(mask.sum()), "positives": int(y.sum()),
        "sensitivity": tp / (tp + fn) if tp + fn else None,
        "specificity": tn / (tn + fp) if tn + fp else None,
        "ppv": tp / (tp + fp) if tp + fp else None,
    }


def per_label_report(y_true: np.ndarray, scores: np.ndarray, labels: list[str], threshold: float = 0.5) -> dict:
    report = {}
    for i, label in enumerate(labels):
        report[label] = {"auroc": auroc(y_true[:, i], scores[:, i]), **threshold_metrics(y_true[:, i], scores[:, i], threshold)}
    valid = [r["auroc"] for r in report.values() if r["auroc"] is not None]
    report["_mean_auroc"] = float(np.mean(valid)) if valid else None
    return report
