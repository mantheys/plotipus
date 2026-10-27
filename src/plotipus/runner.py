"""Run command lists: ``<plots>/<list>_scripts.txt`` (or the tables dir).

One command per line, either ``<kind> [options]``, a legacy
``scripts/script_*.py [options]`` line, or any other ``*.py`` script of the
project (run with the current Python); blank lines and lines starting with
``#`` or ``%`` are skipped. Commands without ``-o``/``--output`` get the
output directories configured for the list in ``plotipus.toml``.

``--medium`` (or ``[project] media``) runs every plot command once per
medium, each writing to its own output folder (see :mod:`plotipus.project`).

Plot commands run in forked children of the runner (``--isolate fork``, the
default where ``os.fork`` exists): the runner imports plotipus, matplotlib and
every kind and warms up the text layout once, then each command runs in a
fresh copy of that state, so no command sees another's style, plugins or
figures and none pays the imports again. ``--isolate subprocess`` (and
``--show``, scripts, systems without fork) starts a new Python per command.
``--jobs N`` runs up to N commands at a time.
"""

import os
import shlex
import subprocess
import sys
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rich import print as rprint

from .args import parse_media_args, with_medium
from .legacy import translate
from .project import describe_rendering, load_project


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


def _run_one(argv, cwd, env=None):
    command = [sys.executable, *argv[1:]] if argv[0] == SCRIPT else [sys.executable, "-m", "plotipus", *argv]
    proc = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=cwd,
        env=env,
    )
    return proc.returncode, proc.stdout


def fork_available():
    return hasattr(os, "fork") and hasattr(os, "waitstatus_to_exitcode")


def preload():
    """Import every kind and draw a little mathtext once, so forked commands
    start with the imports done and the text layout warm (the mathtext
    parser and the font lookups take most of a second the first time)."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    from .legacy import KINDS, kind_module

    for kind in KINDS:
        kind_module(kind)
    fig = Figure(figsize=(1, 1))
    FigureCanvasAgg(fig)
    fig.text(0.5, 0.5, r"$\sigma_{x}^{2} \pm 1$ x")
    fig.canvas.draw()


def _child(argv, cwd, env, fd):
    """Run one command in this forked child, its output to ``fd``; never returns."""
    code = 1
    try:
        os.dup2(fd, 1)
        os.dup2(fd, 2)
        os.close(fd)
        # Fresh stream objects on the redirected descriptors (the parent's may be replaced, e.g. under pytest).
        sys.stdout = open(1, "w", buffering=1, closefd=False)
        sys.stderr = open(2, "w", buffering=1, closefd=False)
        os.chdir(cwd)
        os.environ.update(env)
        from .cli import main

        code = main(list(argv)) or 0
    except SystemExit as exit_:
        code = exit_.code if isinstance(exit_.code, int) else (0 if exit_.code is None else 1)
    except BaseException:
        traceback.print_exc()
        code = 1
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            os._exit(code)


def _run_forked(planned, cwd, env, jobs):
    """Yield (code, output) of each planned (line, argv) in order, running up
    to ``jobs`` forked children at a time (scripts run as subprocesses)."""
    pending = list(enumerate(planned))
    running = {}  # pid -> (index, output path)
    results = {}
    shown = 0
    try:
        while pending or running:
            while pending and len(running) < max(1, jobs):
                index, (_, argv) = pending.pop(0)
                if argv[0] == SCRIPT:
                    results[index] = _run_one(argv, cwd, dict(os.environ, **env))
                    continue
                fd, path = tempfile.mkstemp(prefix="plotipus-run-", suffix=".log")
                sys.stdout.flush()
                sys.stderr.flush()
                pid = os.fork()
                if pid == 0:
                    _child(argv, cwd, env, fd)
                os.close(fd)
                running[pid] = (index, path)
            while shown in results:
                yield results.pop(shown)
                shown += 1
            if not running:
                continue
            pid, status = os.wait()
            if pid not in running:
                continue
            index, path = running.pop(pid)
            with open(path, encoding="utf-8", errors="replace") as handle:
                output = handle.read()
            os.unlink(path)
            results[index] = (os.waitstatus_to_exitcode(status), output)
            while shown in results:
                yield results.pop(shown)
                shown += 1
    finally:
        for pid, (_, path) in running.items():
            try:
                os.kill(pid, 9)
                os.waitpid(pid, 0)
            except OSError:
                pass
            if os.path.exists(path):
                os.unlink(path)


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


def list_media(project, medium=None):
    """Media a list runs for: ``--medium`` (``all``: the project's media),
    else ``[project] media``; [None] leaves each command as it is."""
    if medium == "all":
        return project.all_media()
    if medium is not None:
        return [medium]
    return list(project.media) if project.media else [None]


def for_media(argv, media, theme=None):
    """One argument vector per medium (commands naming their own --medium,
    and scripts, are left alone)."""
    if argv[0] == SCRIPT:
        return [argv]
    if theme is not None and "--theme" not in argv:
        argv = [*argv, "--theme", theme]
    if "--medium" in argv or any(t.startswith("--medium=") for t in argv):
        return [argv]
    return [argv if medium is None else with_medium(argv, medium) for medium in media]


def _describe(argv, project):
    if argv[0] == SCRIPT:
        return ""
    media = parse_media_args(argv[1:])
    medium = None if media.medium == "all" else media.medium
    try:
        return "  # " + describe_rendering(medium, media.theme, media.width, media.aspect, project,
                                           media.style_preset, media.experiment).describe()
    except ValueError as error:
        return f"  # {error}"


def run_list(name, tables=False, show=False, debug=False, jobs=1, dry_run=False, match=None, check=False,
             medium=None, theme=None, isolate=None):
    """Run every command of a list; returns the number of failed commands.
    ``dry_run`` prints the translated commands (with the medium, theme,
    width and style layers each resolves to), ``check`` only parses them;
    ``medium``/``theme`` apply to every plot command. ``isolate`` is fork
    (forked children of a preloaded runner, the default where available) or
    subprocess (a new Python per command)."""
    project = load_project()
    path = list_path(project, name, tables)
    if not path.exists():
        rprint(f"[red]Error:[/red] Command list {path} not found.")
        return 1
    extra_outputs = project.output_paths("tables" if tables else "plots", Path(name).stem.removesuffix("_scripts"))
    lines = [line for line in read_commands(path) if match is None or match in line]

    media = [None] if tables else list_media(project, medium)
    planned = []
    failures = []
    for line in lines:
        try:
            argv = build_command(line, extra_outputs, show, debug, project.root)
        except (KeyError, ValueError) as error:
            failures.append((line, 2, str(error)))
            continue
        for expanded in ([argv] if tables else for_media(argv, media, theme)):
            planned.append((line, expanded))

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
            shown = shlex.join(["python", *argv[1:]]) if argv[0] == SCRIPT else "plotipus " + shlex.join(argv)
            print(shown + ("" if tables else _describe(argv, project)))
        for line, _, message in failures:
            rprint(f"[red]Cannot translate:[/red] {line}\n  {message}")
        return len(failures)

    # One-off notices (e.g. map's 2-dof levels) are printed once per list, not once per command.
    notices = tempfile.TemporaryDirectory(prefix="plotipus-notices-")
    env = dict(os.environ, PLOTIPUS_NOTICE_DIR=notices.name)
    isolate = isolate or os.environ.get("PLOTIPUS_ISOLATE") or "fork"
    forked = isolate == "fork" and fork_available() and not show

    def _task(item):
        line, argv = item
        code, output = _run_one(argv, project.root, env)
        return code, output

    def _results(pool):
        if forked:
            preload()
            return _run_forked(planned, project.root, {"PLOTIPUS_NOTICE_DIR": notices.name}, jobs)
        return pool.map(_task, planned)

    with notices, ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        for (line, argv), (code, output) in zip(planned, _results(pool)):
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
