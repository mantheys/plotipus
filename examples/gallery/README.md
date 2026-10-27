# Gallery

One example for every working row of the
[chart catalogue](../../docs/design/catalogue.md): histograms, scatters,
maps and contours, fits with residual and pull panels, ratio and
significance panels, ROC and learning curves, error bars and bands, facets,
annotations and LaTeX/HTML tables. It mixes a toy calorimeter test beam
(`detector.py`) and a toy classifier (`ml.py`), both synthetic, with the
[famous-plot](../famous/README.md) data, all in the default style.

```bash
make -C examples gallery
```

Then open `examples/gallery/output/gallery.md`: every figure for slides and
for paper side by side with its command below, the tables as LaTeX, and the
catalogue rows still waiting for a feature. The outputs are not committed.

The command lists, `input/{plots,tables}/gallery_scripts.txt`, are also a
test (`tests/test_gallery.py`, marked `slow`).
