"""Run command lists: ``<plots>/<list>_scripts.txt`` (or the tables dir).

One command per line, either ``<kind> [options]``, a legacy
``scripts/script_*.py [options]`` line, or any other ``*.py`` script of the
project (run with the current Python); blank lines and lines starting with
``#`` or ``%`` are skipped. Commands without ``-o``/``--output`` get the
output directories configured for the list in ``plotipus.toml``.
"""

import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rich import print as rprint

from .legacy import translate
from .project import load_project


def list_path(project, name, tables=False):
    path = Path(name)
    if path.suffix == ".txt" and path.exists():
        return path
    base = project.tables_dir if tables else project.plots_dir
    return base / f"{name}_scripts.txt"


def read_commands(path):
    commands = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text and not text.startswith(("#", "%")):
                commands.append(" ".join(text.split()))
    return commands


SCRIPT = "__script__"


def build_command(line, extra_outputs=(), show=False, debug=False, root=None):
    """Translated argument vector ``[kind, ...]`` of one command line. A
    ``*.py`` line without a translation runs as a project script when the
    file exists (``[SCRIPT, path, ...]``)."""
    tokens = shlex.split(line)
    try:
        kind, args = translate(tokens)
    except KeyError:
        script = Path(root or ".") / tokens[0]
        if not tokens[0].endswith(".py") or not script.exists():
            raise
        kind, args = SCRIPT, [str(script), *tokens[1:]]
    if extra_outputs and "-o" not in args and "--output" not in args:
        args += ["-o", *extra_outputs]
    if show:
        args.append("--show")
    if debug:
        args.append("--debug")
    return [kind, *args]


def _run_one(argv, cwd):
    command = [sys.executable, *argv[1:]] if argv[0] == SCRIPT else [sys.executable, "-m", "plotipus", *argv]
    proc = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=cwd,
    )
    return proc.returncode, proc.stdout


def check_command(argv):
    """Parse a translated command with its kind's parser; None or the error."""
    import contextlib
    import io

    from .legacy import kind_module

    parser = kind_module(argv[0]).build_parser()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            parser.parse_args(argv[1:])
    except SystemExit:
        return stderr.getvalue().strip().splitlines()[-1] if stderr.getvalue().strip() else "invalid arguments"
    return None


def run_list(name, tables=False, show=False, debug=False, jobs=1, dry_run=False, match=None, check=False):
    """Run every command of a list; returns the number of failed commands.
    ``dry_run`` prints the translated commands, ``check`` only parses them."""
    project = load_project()
    path = list_path(project, name, tables)
    if not path.exists():
        rprint(f"[red]Error:[/red] Command list {path} not found.")
        return 1
    extra_outputs = project.output_paths("tables" if tables else "plots", Path(name).stem.removesuffix("_scripts"))
    lines = [line for line in read_commands(path) if match is None or match in line]

    planned = []
    failures = []
    for line in lines:
        try:
            planned.append((line, build_command(line, extra_outputs, show, debug, project.root)))
        except (KeyError, ValueError) as error:
            failures.append((line, 2, str(error)))

    if check:
        for line, argv in planned:
            error = None if argv[0] == SCRIPT else check_command(argv)
            if error:
                failures.append((line, 2, error))
        for line, _, message in failures:
            rprint(f"[red]Invalid:[/red] {line}\n  {message}")
        rprint(f"{len(lines)} commands checked, {len(failures)} invalid")
        return len(failures)

    if dry_run:
        for line, argv in planned:
            print(shlex.join(["python", *argv[1:]]) if argv[0] == SCRIPT else "plotipus " + shlex.join(argv))
        for line, _, message in failures:
            rprint(f"[red]Cannot translate:[/red] {line}\n  {message}")
        return len(failures)

    def _task(item):
        line, argv = item
        code, output = _run_one(argv, project.root)
        return line, argv, code, output

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        for line, argv, code, output in pool.map(_task, planned):
            shown = shlex.join(["python", *argv[1:]]) if argv[0] == SCRIPT else "plotipus " + shlex.join(argv)
            rprint(f"\n[cyan]Running[/cyan] {shown}")
            sys.stdout.write(output)
            if code != 0:
                rprint(f"[yellow]Command failed (exit {code}):[/yellow] {line}")
                failures.append((line, code, "\n".join(output.splitlines()[-10:])))

    if not failures:
        rprint("\n[green]All commands executed successfully![/green]")
    else:
        rprint("\n[red]--- Failed commands ---[/red]")
        for line, code, tail in failures:
            rprint(f"\n[red]Error (exit {code}):[/red] {line}")
            if tail:
                rprint(f"[dim]{tail}[/dim]")
    return len(failures)
