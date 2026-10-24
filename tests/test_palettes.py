import matplotlib.pyplot as plt
import pytest
from matplotlib.colors import to_hex

from plotipus import palettes, style
from plotipus.palettes import ColorAllocator


def test_palettes_are_hex_lists():
    for name in palettes.names():
        colors = palettes.get(name)
        assert colors and all(to_hex(c) == c.lower() for c in colors), name


def test_petroff_matches_matplotlib():
    for name in ("petroff6", "petroff8", "petroff10"):
        if name in plt.style.library:
            expected = plt.style.library[name]["axes.prop_cycle"].by_key()["color"]
            assert [c.lower() for c in palettes.get(name)] == [c.lower() for c in expected]


def test_default_palette_sets_the_cycle():
    style.reset()
    assert palettes.active == "petroff10"
    assert to_hex("C0") == "#3f90da"


def test_style_palette_key():
    try:
        style.configure({"palette": "okabe-ito"})
        assert to_hex("C0") == "#e69f00"
        assert palettes.active == "okabe-ito"
    finally:
        style.reset()


def test_explicit_prop_cycle_is_kept():
    try:
        style.configure({"rcparams": {"axes.prop_cycle": "cycler('color', ['#112233', '#445566'])"}})
        assert palettes.active is None
        assert ColorAllocator().colors == ["#112233", "#445566"]
    finally:
        style.reset()


def test_unknown_palette():
    with pytest.raises(ValueError):
        palettes.get("rainbow")


def test_category_keeps_its_colour():
    colors = ColorAllocator(palettes.get("petroff10"))
    first = colors.color_for("a")
    assert colors.color_for("b") != first
    assert colors.color_for("a") == first


def test_mapped_colour_is_never_reused():
    petroff = palettes.get("petroff10")
    colors = ColorAllocator(petroff)
    colors.reserve(["mapped"], lambda category: petroff[0] if category == "mapped" else None)
    others = [colors.color_for(i) for i in range(30)]
    assert petroff[0] not in others
    assert colors.color_for("mapped") == petroff[0]


def test_mapped_cn_colour_counts_as_taken():
    style.reset()
    colors = ColorAllocator()
    colors.color_for("small", "C0")
    assert to_hex(colors.color_for("other")) == to_hex("C1")


def test_next_free_skips_taken_colours():
    petroff = palettes.get("petroff10")
    colors = ColorAllocator(petroff)
    taken = {colors.color_for(i) for i in range(3)}
    assert colors.next_free() not in taken
    combined = colors.next_free("combined")
    assert colors.next_free("combined") == combined


def test_overflow_repeats_colours_with_single_warning(capsys):
    colors = ColorAllocator(palettes.get("petroff10"))
    assigned = [colors.color_for(i) for i in range(12)]
    assert len(set(assigned[:10])) == 10
    assert assigned[10:] == assigned[:2]
    assert capsys.readouterr().out.count("Warning") == 1
