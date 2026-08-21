from __future__ import annotations

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support


def compute_classification_metrics(labels, predictions) -> dict:
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels,
        predictions,
        average="macro",
        zero_division=0,
    )
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision_macro": float(precision),
        "recall_macro": float(recall),
        "f1_macro": float(f1),
    }


def confusion_matrix_as_list(labels, predictions) -> list[list[int]]:
    return confusion_matrix(labels, predictions, labels=[0, 1, 2, 3]).tolist()
