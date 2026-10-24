"""F25: Anscombe's quartet (real data).

Sources and the "Data" recipe are in docs/design/research.md, Part 3.
"""

import numpy as np
import pandas as pd

# F. J. Anscombe (1973), Table 1 (public domain; also R datasets::anscombe).
X_123 = [10, 8, 13, 9, 11, 14, 6, 4, 12, 7, 5]
QUARTET = {
    "I": (X_123, [8.04, 6.95, 7.58, 8.81, 8.33, 9.96, 7.24, 4.26, 10.84, 4.82, 5.68]),
    "II": (X_123, [9.14, 8.14, 8.74, 8.77, 9.26, 8.10, 6.13, 3.10, 9.13, 7.26, 4.74]),
    "III": (X_123, [7.46, 6.77, 12.74, 7.11, 7.81, 8.84, 6.08, 5.39, 8.15, 6.42, 5.73]),
    "IV": ([8, 8, 8, 8, 8, 8, 8, 19, 8, 8, 8], [6.58, 5.76, 7.71, 8.84, 8.47, 7.04, 5.25, 12.50, 5.56, 7.91, 6.89]),
}


def anscombe_quartet():
    """F25: Anscombe's quartet.

    Source: F. J. Anscombe, "Graphs in Statistical Analysis", The American
    Statistician 27(1), 17-21 (1973), doi:10.1080/00031305.1973.10478966.

    Real: the published values of the four datasets (11 points each).
    Derived: the least-squares line of each dataset (y = 3.00 + 0.500 x in
    all four), with the standard errors of an unweighted fit, and the
    summary statistics (``MeanX``, ``MeanY``, ``VarianceX``,
    ``VarianceY``, ``Correlation``).

    Rows: ``Dataset`` (I-IV, also ``Variable`` for --variables panels),
    x ``X``, y ``Y``.
    """
    rows = []
    for name, (x, y) in QUARTET.items():
        x, y = np.array(x, dtype=float), np.array(y, dtype=float)
        params, covariance = np.polyfit(x, y, 1, cov=True)
        rows.append({"X": x, "Y": y, "Dataset": name, "Variable": name, "FitFunction": "straight_line",
                     "FitFunctionLabel": "Linear", "Params": list(params),
                     "ParamsError": list(np.sqrt(np.diag(covariance))), "ParamsLabel": ["slope", "intercept"],
                     "ParamsFormat": [".3f", ".2f"], "MeanX": x.mean(), "MeanY": y.mean(),
                     "VarianceX": x.var(ddof=1), "VarianceY": y.var(ddof=1), "Correlation": np.corrcoef(x, y)[0, 1]})
    return {"Anscombe": pd.DataFrame(rows)}


GENERATORS = {"F25": anscombe_quartet}
