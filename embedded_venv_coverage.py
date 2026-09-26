#!/usr/bin/env python3
"""Measure test suite coverage with the standard library `trace`.

`trace` is used rather than `coverage` because it ships with Python.
A test suite for a project about fetching packages that are not
preinstalled should not itself need a package fetched, which is the
same criterion that chose `http.server` over `pypiserver` in Step 5.1
of `LOGBOOK.md`.

Run it with no arguments to measure the suite, or with a directory to
say where the annotated `.cover` files should go.  `EMBEDDEDVEN_TEST`
is honoured by the suite as usual, so `COMPLETE` measures every
`bootstrap.py` case and costs several minutes.

Two workarounds here were each found the hard way, and both matter
more than they look:

1. **Threads have to be instrumented separately.**  `trace` follows
   only the thread it starts in.  Every request handler in
   `embedded_venv_test.py` runs in a `ThreadingHTTPServer` worker, so
   without `threading.settrace` the whole server looks dead however
   many requests pass through it.  That one line moved the suite from
   88% to 99%.

2. **Counts for deleted files have to be dropped.**  A test that
   imports out of a temporary cache leaves counts naming a file that
   its own teardown has removed, and `write_results` raises
   `FileNotFoundError` trying to read the source to annotate it.

Two blind spots remain, and neither is a defect in the tests:

* **Child processes are not followed.**  `bootstrap.py` reports about
  7% because its twelve cases only ever run in child interpreters.
  They are covered by `test_every_case_bootstraps` and
  `test_every_case_bootstraps_repeatedly` instead, and the percentage
  here measures only the module level code that an import executes.
* **A frame whose `__file__` is false is not followed.**
  `trace.Trace.globaltrace_lt` decides what to follow by reading
  `frame.f_globals.get("__file__")`.  So the one line of
  `embedded_venv.py` that runs only when `__file__` is `None`, the
  frozen interpreter branch of `repair_module_layout`, can never be
  reported as covered.  It is reached by a test that passes; 98% for
  that module means 100%.

MIT No Attribution

Copyright 2026 Wayne C. Gramlich

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
# SPDX-License-Identifier: MIT-0

import sys
import tempfile
import threading
import trace
import unittest
from pathlib import Path
from typing import Any


def build_tracer() -> trace.Trace:
    """Return a tracer that counts lines in this project only.

    The standard library is excluded.  Counting it would swamp the
    summary with hundreds of modules nobody here is responsible for,
    and would make the run far slower than the suite it measures.

    Returns:
    * (`trace.Trace`): A line counting tracer, not yet running.
    """
    # Exclude the interpreter's own directories, whatever they are.
    return trace.Trace(count=1, trace=0,
                       ignoredirs=[sys.prefix, sys.exec_prefix])


def run_suite() -> None:
    """Run the whole test suite, swallowing the exit it asks for.

    `unittest.main` exits the interpreter when it is finished, which
    would take the counts with it, so the suite is run with
    `exit=False` and any `SystemExit` is absorbed as well.
    """
    # Import inside the traced call, so imports are counted too.
    import embedded_venv_test
    try:
        unittest.main(module=embedded_venv_test, exit=False, argv=[__file__])
    except SystemExit:
        pass


def report(tracer: trace.Trace, coverdir: Path) -> None:
    """Write the annotated files and print the summary table.

    Arguments:
    * `tracer` (`trace.Trace`):
      The tracer that has finished running.
    * `coverdir` (`Path`):
      Where the annotated `.cover` files go.  Created if it does not
      exist.
    """
    # Drop counts naming files that have since been deleted; see the
    # module docstring.  A test's own teardown is the usual culprit.
    # This file goes too: the instrument does not measure itself.
    here: Path = Path(__file__).resolve()
    results: Any = tracer.results()
    results.counts = {key: hits for key, hits in results.counts.items()
                      if Path(key[0]).is_file()
                      and Path(key[0]).resolve() != here}

    # Annotate, summarize, and say where the annotations landed.
    coverdir.mkdir(parents=True, exist_ok=True)
    results.write_results(show_missing=True, summary=True,
                          coverdir=str(coverdir))
    print(f"\nannotated sources in {coverdir}", file=sys.stderr)


def main() -> None:
    """Measure the suite and report on it.

    An optional first argument names the directory for the annotated
    files.  Without one a temporary directory is made and its path is
    printed, so that nothing is written into the project tree.
    """
    # Let the caller choose where annotations go, or make somewhere.
    coverdir: Path = (Path(sys.argv[1]) if len(sys.argv) > 1
                      else Path(tempfile.mkdtemp(prefix="cover-")))

    # This directory has to be importable for the suite to be found.
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    # Instrument the worker threads as well as this one, then run.
    tracer: trace.Trace = build_tracer()
    threading.settrace(tracer.globaltrace)
    tracer.runfunc(run_suite)
    report(tracer, coverdir)


if __name__ == "__main__":
    main()
