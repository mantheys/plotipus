"""Machine-learning theme of the gallery: a signal/background classifier
(synthetic, seeded).

- ``Scores``: per-event scores of three models (a cut-based likelihood, a
  BDT and a DNN) for signal and for ten times as much background, drawn from
  beta distributions that separate better from model to model.
- ``ROC``: one row per model with the false- and true-positive rates over a
  grid of score thresholds, and recall/precision at the same thresholds,
  all computed from ``Scores``.
- ``LearningCurve``: training and validation accuracy against the training
  set size, with the spread over five folds as the error.
"""

import numpy as np
import pandas as pd

MODELS = {"Likelihood": (2.0, 3.0), "BDT": (2.0, 4.0), "DNN": (3.0, 6.0)}  # (a, b) of the background beta


def scores(rng):
    rows = []
    for model, (a, b) in MODELS.items():
        rows.append({"Model": model, "Class": "Signal", "Score": rng.beta(b, a, 20000)})
        rows.append({"Model": model, "Class": "Background", "Score": rng.beta(a, b, 200000)})
    return pd.DataFrame(rows)


def roc(frame):
    thresholds = np.linspace(0, 1, 201)
    rows = []
    for model in MODELS:
        signal = frame[(frame.Model == model) & (frame.Class == "Signal")].Score.iloc[0]
        background = frame[(frame.Model == model) & (frame.Class == "Background")].Score.iloc[0]
        tp = np.array([(signal >= t).sum() for t in thresholds], dtype=float)
        fp = np.array([(background >= t).sum() for t in thresholds], dtype=float)
        selected = tp + fp
        keep = selected > 0
        rows.append({"Model": model, "Threshold": thresholds, "FPR": fp / background.size, "TPR": tp / signal.size,
                     "Recall": (tp / signal.size)[keep], "Precision": tp[keep] / selected[keep]})
    return pd.DataFrame(rows)


def learning_curve(rng):
    sizes = np.array([200, 500, 1000, 2000, 5000, 10000, 20000, 50000], dtype=float)
    rows = []
    for split, start, end in (("Training", 0.97, 0.93), ("Validation", 0.78, 0.915)):
        trend = end + (start - end) * np.sqrt(sizes[0] / sizes)
        spread = 0.025 * np.sqrt(sizes[0] / sizes) + 0.002
        rows.append({"Split": split, "TrainSize": sizes, "Accuracy": trend + rng.normal(0, spread / 3),
                     "AccuracyError": spread})
    return pd.DataFrame(rows)


def _classifier(rng):
    frame = scores(rng)
    return {"Scores": frame, "ROC": roc(frame), "LearningCurve": learning_curve(rng)}


GENERATORS = {"classifier": _classifier}
