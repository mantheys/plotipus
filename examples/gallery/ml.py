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
- ``Importance``: the feature importance of the BDT and the DNN, one scalar
  cell per feature and model (normalised to sum to one per model).
- ``Confusion``: the event counts of a three-class particle-ID network, one
  grid of true (rows) against predicted (columns) class.
- ``Calibration``: the reliability curve of the BDT and the DNN: the
  fraction of signal per bin of the predicted probability, with its binomial
  error, and the events per bin (``Count``). The DNN is overconfident.
- ``Correlation``: the correlation matrix of the input features.
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


FEATURES = ("Shower depth", "Track isolation", "E/p", "Hits", "Cluster width", "Timing")


def importance(rng):
    base = np.array([0.30, 0.22, 0.18, 0.13, 0.10, 0.07])
    rows = []
    for model in ("BDT", "DNN"):
        weights = base * rng.uniform(0.7, 1.3, base.size)
        weights /= weights.sum()
        rows += [{"Model": model, "Feature": feature, "Importance": weight}
                 for feature, weight in zip(FEATURES, weights)]
    return pd.DataFrame(rows)


CLASSES = np.array(["electron", "pion", "muon"])


def confusion(rng):
    # rows: the true class, columns: the predicted one
    probabilities = np.array([[0.93, 0.06, 0.01], [0.09, 0.88, 0.03], [0.01, 0.04, 0.95]])
    counts = np.array([rng.multinomial(n, p) for n, p in zip((5200, 6100, 900), probabilities)], dtype=float)
    return pd.DataFrame([{"Predicted": CLASSES, "True": CLASSES, "Count": counts}])


def calibration(rng):
    edges = np.linspace(0, 1, 11)
    predicted = 0.5 * (edges[1:] + edges[:-1])
    rows = []
    for model, sharpness in (("BDT", 1.0), ("DNN", 0.6)):
        # an overconfident model's true probability is pulled towards 0.5
        truth = 0.5 + (predicted - 0.5) * sharpness
        count = np.round(4000 * (0.3 + 4 * (predicted - 0.5) ** 2)).astype(float)
        observed = rng.binomial(count.astype(int), truth) / count
        rows.append({"Model": model, "Predicted": predicted, "Observed": observed,
                     "ObservedError": np.sqrt(observed * (1 - observed) / count), "Count": count})
    return pd.DataFrame(rows)


def correlation(rng):
    loadings = rng.normal(0, 1, (len(FEATURES), 2)) * np.array([1.0, 0.6])
    covariance = loadings @ loadings.T + np.diag(rng.uniform(0.3, 1.0, len(FEATURES)))
    scale = np.sqrt(np.diag(covariance))
    names = np.array(FEATURES)
    return pd.DataFrame([{"FeatureX": names, "FeatureY": names, "Correlation": covariance / np.outer(scale, scale)}])


def _classifier(rng):
    frame = scores(rng)
    return {"Scores": frame, "ROC": roc(frame), "LearningCurve": learning_curve(rng), "Importance": importance(rng),
            "Confusion": confusion(rng), "Calibration": calibration(rng), "Correlation": correlation(rng)}


GENERATORS = {"classifier": _classifier}
