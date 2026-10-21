"""Extension points a project (plugin) can fill in.

A plugin is any importable module listed under ``plugins`` in
``plotipus.toml``; if it defines ``setup(registry)``, it is called with this
module once the project is loaded. Everything here is optional.
"""

# resolver(entry, input_dir, prefix) -> list of candidate Paths for the
# datafile ``{prefix}{entry}.pkl`` under ``input_dir``. Plugin candidates are
# tried before the plain ``input_dir / f"{prefix}{entry}.pkl"``.
resolvers = []

# post_load(df, path, input_dir) -> df, applied to every loaded file.
post_load_hooks = []

# post_concat(df) -> df or None, applied once to the combined frame.
post_concat_hooks = []

# Label/colour hooks keyed by column name: label(value, n_unique) -> str or
# None, color(value) -> colour or None. Used when no explicit mapping is set.
label_hooks = {}
color_hooks = {}

# config_label(args, config, name, iterable) -> legend label of one
# config/name series (replaces the mapping-based default).
config_label = None

# Column builders for the table kind (--add_column NAME[=COLUMN]):
# name -> func(df, args, column) -> df with ``column`` added.
table_columns = {}

# Extra plot kinds: name -> module exposing ``main(argv)``.
kinds = {}

# Extra command-line options: (flags, kwargs) pairs passed to
# ``parser.add_argument`` for every plot kind, e.g. a watermark switch read
# back by a figure hook.
arguments = []

# figure_hook(fig, args), called on every figure just before it is saved
# (after the title, note and margins are in place).
figure_hooks = []

# Legacy script names (basename without .py) -> (kind, [extra args]) used by
# the runner to translate old command lines.
legacy_scripts = {}


def add_resolver(func):
    resolvers.append(func)
    return func


def add_post_load(func):
    post_load_hooks.append(func)
    return func


def add_post_concat(func):
    post_concat_hooks.append(func)
    return func


def add_label_hook(column, func):
    label_hooks[column] = func


def add_color_hook(column, func):
    color_hooks[column] = func


def add_kind(name, module):
    kinds[name] = module


def add_legacy_script(script_name, kind, extra_args=()):
    legacy_scripts[script_name] = (kind, list(extra_args))


def add_argument(*flags, **kwargs):
    arguments.append((flags, kwargs))


def add_figure_hook(func):
    figure_hooks.append(func)
    return func
