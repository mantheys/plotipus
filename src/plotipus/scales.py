"""Axis scales and secondary axes of every kind (catalogue H6, H7).

``--secondary_x SPEC`` (``--secondary_y``) adds the same axis in other units
along the top (right) edge: a built-in conversion (:data:`CONVERSIONS`, e.g.
``cm-1->GHz``), a conversion of the style file's ``mappings.conversions``
(``{"name": "FORWARD;INVERSE"}`` or ``{"forward": ..., "inverse": ...,
"label": ...}``), one registered by a plugin (``registry.conversions``), or
an inline ``'FORWARD;INVERSE'`` pair of expressions in ``x`` (numpy
functions and ``pi`` allowed), e.g. ``'x*29.9792458;x/29.9792458'``. Its
label: ``--secondary_labelx``, else the conversion's.

``--xscale`` (``--yscale``) sets a scale --logx cannot: ``symlog``
(``symlog:LINTHRESH``: linear within ±LINTHRESH, logarithmic beyond, for
signed values over many decades) or ``log<B<linear`` (logarithmic below B,
linear above, the log part taking ``--scale_split`` of the axis, 0.3 by
default: the low multipoles of a CMB power spectrum), plus ``linear`` and
``log``.

Both are applied just before the figure is saved, after the limits are set,
to the outer panels: the secondary x axis on the panels of the top row, the
secondary y axis on those of the last column.
"""

import re

import numpy as np
from matplotlib.ticker import FixedLocator, FuncFormatter, LogLocator, MaxNLocator, NullFormatter
from rich import print as rprint

from . import registry, style

# name -> (forward, inverse, label of the secondary axis)
CONVERSIONS = {
    "cm-1->GHz": ("x*29.9792458", "x/29.9792458", "Frequency (GHz)"),
    "GHz->cm-1": ("x/29.9792458", "x*29.9792458", "Wavenumber (cm$^{-1}$)"),
    "eV->nm": ("1239.84198/x", "1239.84198/x", "Wavelength (nm)"),
    "nm->eV": ("1239.84198/x", "1239.84198/x", "Energy (eV)"),
    "C->F": ("x*9/5+32", "(x-32)*5/9", "Temperature (°F)"),
    "F->C": ("(x-32)*5/9", "x*9/5+32", "Temperature (°C)"),
}
_NAMES = {name: getattr(np, name) for name in ("sqrt", "exp", "log", "log10", "log2", "sin", "cos", "tan", "arcsin",
                                               "arccos", "arctan", "sinh", "cosh", "tanh", "abs", "power")}
_NAMES["pi"] = np.pi
HYBRID = re.compile(r"^log<([^<]+)<linear$")


def add_scale_args(parser):
    group = parser.add_argument_group("axis scales")
    add = group.add_argument
    for axis, edge in (("x", "top"), ("y", "right")):
        add(f"--secondary_{axis}", type=str, default=None, metavar="SPEC",
            help=f"The {axis} axis in other units along the {edge} edge: a conversion name ("
            + ", ".join(CONVERSIONS) + ", or one of the style's mappings.conversions) or 'FORWARD;INVERSE' "
            "expressions in x, e.g. 'x*29.9792458;x/29.9792458'.")
        add(f"--secondary_label{axis}", type=str, default=None,
            help=f"Label of the secondary {axis} axis (default: the conversion's).")
        add(f"--{axis}scale", type=str, default=None, metavar="SCALE",
            help=f"Scale of the {axis} axis: linear, log, symlog (symlog:LINTHRESH, linear within ±LINTHRESH) or "
            "'log<B<linear' (logarithmic below B, linear above; --scale_split).")
    add("--scale_split", type=float, default=0.3, metavar="FRACTION",
        help="With --xscale/--yscale 'log<B<linear': the share of the axis taken by the logarithmic part.")


def _expression(text):
    code = compile(text.strip(), "<conversion>", "eval")
    unknown = set(code.co_names) - set(_NAMES) - {"x"}
    if unknown:
        raise ValueError(f"unknown name(s) {', '.join(sorted(unknown))} in conversion '{text}'")

    def function(x):
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            return eval(code, {"__builtins__": {}}, {**_NAMES, "x": np.asarray(x, dtype=float)})  # noqa: S307

    return function


def conversion(spec):
    """(forward, inverse, label or None) of a --secondary_x/y SPEC."""
    if spec in registry.conversions:
        return registry.conversions[spec]
    named = (style.get_mapping_dict("conversions") or {}).get(spec)
    if isinstance(named, dict):
        return _expression(named["forward"]), _expression(named["inverse"]), named.get("label")
    if isinstance(named, str):
        spec = named
    elif spec in CONVERSIONS:
        forward, inverse, label = CONVERSIONS[spec]
        return _expression(forward), _expression(inverse), label
    if ";" not in spec:
        raise ValueError(f"'{spec}' is no conversion name ({', '.join(CONVERSIONS)}) and no 'FORWARD;INVERSE' pair")
    forward, inverse = spec.split(";", 1)
    return _expression(forward), _expression(inverse), None


def _panels(fig):
    """The data panels of ``fig`` with their grid position (insets and colorbars left out)."""
    panels = []
    for ax in fig.axes:
        spec = ax.get_subplotspec() if hasattr(ax, "get_subplotspec") else None
        if spec is None or ax.get_label() == "<colorbar>" or getattr(ax, "_plotipus_secondary", False):
            continue
        panels.append((ax, spec))
    return panels


def _hybrid(axis_obj, ax, which, low_high, split, value):
    """``log<B<linear`` on one axis: a function scale, log ticks below B, linear ticks above."""
    lo, hi = low_high
    if not 0 < lo < value < hi:
        rprint(f"[yellow]Warning:[/yellow] --{which}scale log<{value:g}<linear needs 0 < {lo:g} < {value:g} < {hi:g} "
               "(the axis range); scale left as it is.")
        return
    llo, lb = np.log10(lo), np.log10(value)

    def forward(x):
        x = np.asarray(x, dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            logs = split * (np.log10(np.where(x > 0, x, np.nan)) - llo) / (lb - llo)
        return np.where(x < value, logs, split + (1 - split) * (x - value) / (hi - value))

    def inverse(y):
        y = np.asarray(y, dtype=float)
        return np.where(y < split, 10 ** (llo + y / split * (lb - llo)), value + (y - split) / (1 - split) * (hi - value))

    getattr(ax, f"set_{which}scale")("function", functions=(forward, inverse))
    getattr(ax, f"set_{which}lim")(lo, hi)
    log_major = [t for t in LogLocator(subs=(1.0,)).tick_values(lo, value) if lo <= t < value]
    log_minor = [t for t in LogLocator(subs=np.arange(2, 10)).tick_values(lo, value) if lo <= t < value]
    steps = MaxNLocator(nbins=max(3, round(8 * (1 - split))), steps=[1, 2, 2.5, 5, 10]).tick_values(value, hi)
    linear = [t for t in steps if value < t <= hi]
    step = float(np.diff(steps)[0]) if len(steps) > 1 else hi - value
    linear_minor = [t for t in np.arange(steps[0], hi + step / 10, step / 5) if value < t <= hi and t not in linear]
    major = sorted(set(log_major + [value] + linear))
    # The lower end too (l = 2 of a power spectrum), unless it crowds the next tick.
    if lo not in major and forward(major[0]) - forward(lo) > 0.05:
        major.insert(0, lo)
    # Linear ticks too close to the break would crowd its label.
    major = [t for t in major if t <= value or forward(t) - split > 0.06]
    axis_obj.set_major_locator(FixedLocator(major))
    axis_obj.set_minor_locator(FixedLocator(log_minor + linear_minor))
    axis_obj.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    axis_obj.set_minor_formatter(NullFormatter())
    # A thin line where the scale changes, so the reader sees the break.
    line = ax.axvline if which == "x" else ax.axhline
    line(value, color=style.role("muted"), linewidth=0.6, linestyle=":", zorder=0.5)


def _set_scale(ax, which, spec, split):
    spec = spec.strip()
    axis_obj = ax.xaxis if which == "x" else ax.yaxis
    setter = getattr(ax, f"set_{which}scale")
    if spec in ("linear", "log"):
        setter(spec)
        return
    if spec.startswith("symlog"):
        _, _, threshold = spec.partition(":")
        setter("symlog", linthresh=float(threshold) if threshold else 1.0)
        return
    match = HYBRID.match(spec)
    if match:
        _hybrid(axis_obj, ax, which, getattr(ax, f"get_{which}lim")(), split, float(match.group(1)))
        return
    rprint(f"[yellow]Warning:[/yellow] --{which}scale: unknown scale '{spec}' (linear, log, symlog[:LINTHRESH], "
           "'log<B<linear'); ignored.")


def apply_scales(fig, args):
    """--xscale/--yscale on every panel, then --secondary_x/y on the outer ones."""
    panels = _panels(fig)
    if not panels:
        return
    done = set()  # axes sharing x (or y) take the scale once
    for which in ("x", "y"):
        spec = getattr(args, f"{which}scale", None)
        if not spec:
            continue
        for ax, _ in panels:
            if which == "y" and getattr(ax, "_plotipus_lower", False):
                continue
            siblings = frozenset(map(id, getattr(ax, f"get_shared_{which}_axes")().get_siblings(ax)))
            if (which, siblings) in done:
                continue
            done.add((which, siblings))
            _set_scale(ax, which, spec, getattr(args, "scale_split", 0.3))
    for which, outer in (("x", lambda spec: spec.rowspan.start == 0),
                         ("y", lambda spec: spec.colspan.stop == spec.get_gridspec().ncols)):
        spec_text = getattr(args, f"secondary_{which}", None)
        if not spec_text:
            continue
        try:
            forward, inverse, label = conversion(spec_text)
        except (ValueError, SyntaxError, KeyError) as error:
            rprint(f"[red]Error:[/red] --secondary_{which}: {error}")
            continue
        label = getattr(args, f"secondary_label{which}", None) or label
        for ax, spec in panels:
            if not outer(spec) or (which == "y" and getattr(ax, "_plotipus_lower", False)):
                continue
            make = ax.secondary_xaxis if which == "x" else ax.secondary_yaxis
            secondary = make("top" if which == "x" else "right", functions=(forward, inverse))
            secondary._plotipus_secondary = True
            secondary.minorticks_on()
            if label:
                secondary.set_xlabel(label) if which == "x" else secondary.set_ylabel(label)
            if which == "x":
                ax.tick_params(axis="x", which="both", top=False)  # the secondary axis has its own ticks
            else:
                ax.tick_params(axis="y", which="both", right=False)
