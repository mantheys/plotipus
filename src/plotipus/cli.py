"""``plotipus`` command line.

    plotipus <kind> [options]          draw one plot/table (kinds: line, scatter,
                                       hist, map, cat, table)
    plotipus run <list> [--tables]     run a command list (--dry_run, --check, --jobs N)
    plotipus translate <command...>    show the plotipus form of a legacy command
    plotipus init [directory]          create a project skeleton
"""

import argparse
import shlex
import sys
from pathlib import Path

from . import __version__
from .legacy import KINDS, kind_module, translate

_TEMPLATE = """[project]
data_root = "input/data"
plots = "input/plots"
tables = "input/tables"
output = "output"
# style = ["config/style.json"]
# plugins = ["my_plugin"]

# [outputs.plots]
# paper = ["../paper/figures"]
"""

_EXAMPLE_LIST = """# One plot per line: plotipus <kind> [options] without the 'plotipus'.
# line --datafile Example -x Energy -y Counts --hue Sample
"""


def _init(directory):
    root = Path(directory).resolve()
    for sub in ("input/data", "input/plots", "input/tables", "output/plots", "output/tables"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    config = root / "plotipus.toml"
    if not config.exists():
        config.write_text(_TEMPLATE, encoding="utf-8")
    example = root / "input/plots/example_scripts.txt"
    if not example.exists():
        example.write_text(_EXAMPLE_LIST, encoding="utf-8")
    print(f"Project ready in {root}")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] in ("-V", "--version"):
        print(f"plotipus {__version__}")
        return 0

    command, rest = argv[0], argv[1:]
    if command == "run":
        parser = argparse.ArgumentParser(prog="plotipus run", description="Run a command list.")
        parser.add_argument("list", help="List name (<plots>/<list>_scripts.txt) or a .txt path")
        parser.add_argument("--tables", action="store_true", help="Look the list up in the tables directory")
        parser.add_argument("--show", action="store_true", help="Keep figures open")
        parser.add_argument("--debug", "-d", action="store_true")
        parser.add_argument("--jobs", "-j", type=int, default=1, help="Commands run in parallel")
        parser.add_argument("--dry_run", "--dry-run", action="store_true", help="Print the translated commands only")
        parser.add_argument("--match", type=str, default=None, help="Only commands containing this text")
        parser.add_argument("--check", action="store_true", help="Only check that every command parses")
        options = parser.parse_args(rest)
        from .runner import run_list

        failures = run_list(options.list, options.tables, options.show, options.debug, options.jobs,
                            options.dry_run, options.match, options.check)
        return 1 if failures else 0
    if command == "translate":
        tokens = shlex.split(" ".join(rest)) if len(rest) == 1 else rest
        kind, args = translate(tokens)
        print("plotipus " + shlex.join([kind, *args]))
        return 0
    if command == "init":
        return _init(rest[0] if rest else ".")
    if command.endswith(".py"):
        kind, rest = translate(argv)
        command = kind
    if command in KINDS or command:
        module = kind_module(command)
        module.main(rest)
        return 0
    print(__doc__)
    return 2
