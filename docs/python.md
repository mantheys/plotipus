# Python

```python
import plotipus

plotipus.plot("line", "--datafile", "Distributions", "-x", "Bin", "-y", "Counts", "--hue", "Sample")

from plotipus import load_frame, plot_data, create_common_subplots, format_with_error, style
style.configure("my_style.json")
fig, ax = create_common_subplots()
```

`load_frame(path)` reads one data file (`.pkl` or `.parquet`) as a
DataFrame; `save_frame(frame, path)` writes a frame as Parquet, array cells
(also 2D) included, so that `load_frame` and `--datafile` read it back
unchanged. Parquet needs pyarrow (`pip install 'plotipus[parquet]'`).
