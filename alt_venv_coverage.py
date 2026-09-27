#!/usr/bin/env python3
"""Measure test suite coverage with the standard library `trace`.

`trace` is used rather than `coverage` because it ships with Python.
A test suite for a project about fetching packages that are not
preinstalled should not itself need a package fetched, which is the
same criterion that chose `http.server` over `pypiserver` in Step 5.1
of `LOGBOOK.md`.

Run it with no arguments to measure the suite, or with a directory to
say where the annotated `.cover` files should go.  `ALT_VENV_TEST`
is honoured by the suite as usual, so `COMPLETE` measures every
`bootstrap.py` case and costs several minutes.

Two workarounds here were each found the hard way, and both matter
more than they look:

1. **Threads have to be instrumented separately.**  `trace` follows
   only the thread it starts in.  Every request handler in
   `alt_venv_test.py` runs in a `ThreadingHTTPServer` worker, so
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
  `alt_venv.py` that runs only when `__file__` is `None`, the
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

import os
import sys
import tempfile
import threading
import trace
import unittest
from pathlib import Path


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
    import alt_venv_test
    try:
        unittest.main(module=alt_venv_test, exit=False, argv=[__file__])
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
    results: trace.CoverageResults = tracer.results()
    results.counts = {key: hits for key, hits in results.counts.items()
                      if Path(key[0]).is_file()
                      and Path(key[0]).resolve() != here}

    # Annotate, summarize, and say where the annotations landed.
    coverdir.mkdir(parents=True, exist_ok=True)
    results.write_results(show_missing=True, summary=True,
                          coverdir=str(coverdir))
    print(f"\nannotated sources in {coverdir}", file=sys.stderr)


def trace_children(counts: Path) -> None:
    """Arrange for child processes to be traced as well.

    Most of what this suite does happens in children: every `pip`, and
    `bootstrap.py` four or twelve times over.  `trace` follows neither
    those nor threads by itself, so `bootstrap.py` reads as about 7%
    however thoroughly its cases are exercised.

    The only hook that reaches a process nobody wrote the command line
    for is `sitecustomize`, which Python imports at startup from
    `sys.path`.  `trace_hook/` holds one, and is put on `PYTHONPATH`
    here rather than living anywhere Python would find on its own.

    Arguments:
    * `counts` (`Path`):
      Where each child should leave its counts.  Created if needed.
    """
    # Children inherit the environment, so setting it here is enough.
    counts.mkdir(parents=True, exist_ok=True)
    hook: Path = Path(__file__).resolve().parent / "trace_hook"
    existing: str = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = (f"{hook}{os.pathsep}{existing}"
                                if existing else str(hook))
    os.environ["ALT_VENV_COVER"] = str(counts)


def merge_children(tracer: trace.Trace, counts: Path) -> int:
    """Fold every child's counts into this process's results.

    `trace` can do this itself: `CoverageResults` reads a saved count
    file through `infile` and merges another through `update`.  Each
    child writes its own file, named after its process id, so no two
    writers ever touch one path and nothing can be lost.

    Arguments:
    * `tracer` (`trace.Trace`):
      The tracer that has finished running.
    * `counts` (`Path`):
      The directory the children wrote into.

    Returns:
    * (`int`): How many child count files were folded in.
    """
    # Merge into this process's own results, one child at a time.
    mine: trace.CoverageResults = tracer.results()
    found: int = 0
    child: Path
    for child in sorted(counts.iterdir()):
        mine.update(trace.CoverageResults(infile=str(child)))
        found += 1
    return found


def main() -> None:
    """Measure the suite and report on it.

    Arguments come in any order.  A directory names where the annotated
    files go; without one a temporary directory is made and its path
    printed, so nothing lands in the project tree.  `--children` also
    traces child processes, which is the only way to see
    `bootstrap.py` at all and costs several minutes.
    """
    # Sort the arguments into the flag and the directory.
    wanted: list[str] = [word for word in sys.argv[1:] if word != "--children"]
    children: bool = "--children" in sys.argv[1:]
    coverdir: Path = (Path(wanted[0]) if wanted
                      else Path(tempfile.mkdtemp(prefix="cover-")))

    # This directory has to be importable for the suite to be found.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    counts: Path = coverdir / "child-counts"
    if children:
        trace_children(counts)

    # Instrument the worker threads as well as this one, then run.
    tracer: trace.Trace = build_tracer()
    threading.settrace(tracer.globaltrace)
    tracer.runfunc(run_suite)
    folded: int = merge_children(tracer, counts) if children else 0
    if children:
        print(f"folded in {folded} child processes", file=sys.stderr)
    report(tracer, coverdir)


if __name__ == "__main__":
    main()
