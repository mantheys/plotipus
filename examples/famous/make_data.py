"""Write the famous-plot pickles used by input/plots/famous_scripts.txt.

Each figure (F01-F25 of docs/design/research.md, Part 3) has a seeded
generator in one of the group modules; its docstring cites the source and
says which values come from the paper and which are synthetic.

    python make_data.py            # every figure
    python make_data.py F08 F25    # only these
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import anscombe  # noqa: E402
import classics  # noqa: E402
import climate  # noqa: E402
import cosmology  # noqa: E402
import galaxies  # noqa: E402
import gravwaves  # noqa: E402
import hep  # noqa: E402

GENERATORS = dict(sorted({**hep.GENERATORS, **cosmology.GENERATORS, **galaxies.GENERATORS, **climate.GENERATORS,
                          **gravwaves.GENERATORS, **classics.GENERATORS, **anscombe.GENERATORS}.items()))


def main(figures=None, out=None):
    out = Path(out) if out is not None else Path(__file__).parent / "input" / "data"
    out.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    written = []
    for figure, generator in GENERATORS.items():
        if figures and figure not in figures:
            continue
        for name, frame in generator().items():
            frame.to_pickle(out / f"{name}.pkl")
            written.append(name)
    print(f"{len(written)} famous-plot datasets written to {out} in {time.perf_counter() - start:.1f} s")
    return written


if __name__ == "__main__":
    main(sys.argv[1:])
