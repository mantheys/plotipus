"""Write the gallery data into input/data:

- the example data (``../make_data.py``: Distributions and the files
  derived from it);
- the famous-plot data (``../famous``, T24), with the colour and label
  mappings of its style file copied to ``input/famous_mappings.json`` (the
  gallery keeps the default style otherwise);
- the gallery's own themes: ``detector.py`` and ``ml.py``.

    python make_data.py
"""

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent
FAMOUS = EXAMPLES / "famous"
sys.path.insert(0, str(HERE))

import detector  # noqa: E402
import ml  # noqa: E402

THEMES = {"detector": detector.GENERATORS, "ml": ml.GENERATORS}


def main(out=None):
    out = Path(out) if out is not None else HERE / "input" / "data"
    out.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    subprocess.run([sys.executable, str(EXAMPLES / "make_data.py"), str(out)], check=True)

    spec = importlib.util.spec_from_file_location("famous_make_data", FAMOUS / "make_data.py")
    famous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(famous)
    famous.main(out=out)
    mappings = json.loads((FAMOUS / "style.json").read_text()).get("mappings", {})
    (HERE / "input" / "famous_mappings.json").write_text(json.dumps({"mappings": mappings}, indent=1) + "\n")

    written = []
    for theme, generators in THEMES.items():
        rng = np.random.default_rng(sum(map(ord, theme)))
        for generator in generators.values():
            for name, frame in generator(rng).items():
                frame.to_pickle(out / f"{name}.pkl")
                written.append(name)
    print(f"Gallery data written to {out} ({len(written)} gallery datasets) in {time.perf_counter() - start:.1f} s")


if __name__ == "__main__":
    main()
