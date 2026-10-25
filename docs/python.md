# Python

```python
import plotipus

plotipus.plot("line", "--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--hue", "Sample")

from plotipus import load_frame, plot_data, create_common_subplots, format_with_error, style
style.configure("my_style.json")
fig, ax = create_common_subplots()
```
