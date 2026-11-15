# Python

```python
import plotipus

plotipus.plot("line", "--datafile", "Distributions", "-x", "Bin", "-y", "Counts", "--hue", "Sample")

from plotipus import load_frame, plot_data, create_common_subplots, format_with_error, style
style.configure("my_style.json")
fig, ax = create_common_subplots()
```

`plotipus.plot(kind, *arguments)` takes the words of a command line after
`plotipus KIND`, one string each, and draws, saves and prints exactly what
the command does. Every command of the [options reference](options.md) is
therefore also a Python call: the
[web gallery](https://mantheys.github.io/plotipus/#gallery) shows each one
both ways (its Shell / Python switch), for instance

```python
import plotipus

plotipus.plot(
    "map",
    "--datafile", "Posterior",
    "--corner", "Strength", "Mass", "Width",
    "--contour",
    "--corner_labels", r"$\mu$", "$m$ (GeV)", r"$\Gamma$ (GeV)",
)
```

LaTeX labels read best as raw strings (`r"$\mu$"`): the quotes a shell needs
around them are not part of the argument.

`load_frame(path)` reads one data file (`.pkl` or `.parquet`) as a
DataFrame; `save_frame(frame, path)` writes a frame as Parquet, array cells
(also 2D) included, so that `load_frame` and `--datafile` read it back
unchanged. Parquet needs pyarrow (`pip install 'plotipus[parquet]'`).
