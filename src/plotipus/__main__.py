import sys

from .cli import main

# Guarded: multiprocessing workers (plotipus run's command server) import the
# main module again, and must not run the command line a second time.
if __name__ == "__main__":
    sys.exit(main())
