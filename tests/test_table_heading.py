"""--heading and --footer_rows of the table kind."""

import pandas as pd

from plotipus.kinds import table


def test_heading_and_footer_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = tmp_path / "input" / "data"
    data.mkdir(parents=True)
    pd.DataFrame({"Config": ["a", "a"], "Variable": ["X", "Y"], "Value": [1.0, 2.0]}).to_pickle(data / "a_s_Demo.pkl")
    table.main(["--datafile", "Demo", "--configs", "a", "--names", "s", "-y", "Value", "-v", "X", "Y",
                "-t", "", "--flat_header", "--first_header", "Configuration", "--heading", r"Demo~(\%)", "--footer_rows", "ref & 3 & 4", r"ref2 & 5 & 6 \\",
                "--output_name", "demo.tex", "--output", str(tmp_path / "out")])
    text = next((tmp_path / "out").rglob("demo.tex")).read_text()
    assert text.startswith("\\centering\nDemo~(\\%)\\\\\n\\begin{tabular}")
    assert "\\midrule\nref & 3 & 4 \\\\\nref2 & 5 & 6 \\\\\n\\bottomrule" in text
    assert "\\toprule\nConfiguration & X & Y \\\\\n\\midrule" in text
