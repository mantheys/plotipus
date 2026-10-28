"""Imported by the command server of :func:`plotipus.runner.run_commands`:
the run's project loaded (``PLOTIPUS_PRELOAD_ROOT``), the kinds imported and
the text layout warmed up in its style, before commands fork."""

import os

from .runner import preload

_root = os.environ.get("PLOTIPUS_PRELOAD_ROOT")
if _root:
    from .project import load_project

    os.chdir(_root)
    load_project()
preload()
