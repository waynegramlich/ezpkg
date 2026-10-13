#!/usr/bin/env python3
"""Measure test suite coverage with the standard library `trace`.

`trace` is used rather than `coverage` because it ships with Python.
A test suite for a project about fetching packages that are not
preinstalled should not itself need a package fetched, which is the
same criterion that chose `http.server` over `pypiserver` in Step 5.1
of `TASKS/`.

Run it with no arguments to measure the suite, or with a directory to
say where the annotated `.cover` files should go.  `EZPKG_TEST`
is honoured by the suite as usual, so `COMPLETE` measures every
`bootstrap.py` case and costs several minutes.

`--per-case <directory>` answers a different question: what does each
`bootstrap.py` case add?  The cases are those `EZPKG_TEST` selects,
so `nopip1` and `nopip5` unless it says `COMPLETE`.  It makes one
baseline run of the whole suite with `EZPKG_TEST=NONE`, so that no
case runs, and then one run per case of only the tests marked
`runs_cases`, with `EZPKG_TEST` naming that case.  Children are
traced throughout.  Runs go two at a time by default (`--jobs`), since
each is a busy tree of processes in its own right, and each writes only
under `<directory>/<run>/`, so runs side by side cannot overwrite each
other.  Then it compares them and writes `report.md`: what each case
adds beyond the baseline, the lines only one case reaches, and a greedy
ordering from the case that ships showing which cases add nothing.
`--compare <directory>` redoes just the comparison from the saved
counts, in seconds, which is what makes culling cases cheap to repeat.
Both work in a copy of the project made under `<directory>/project/`,
so that editing the project during a run cannot spoil its report.
See Step 6.16 of `TASKS/`.

Three workarounds here were each found the hard way, and all matter
more than they look:

1. **Threads have to be instrumented separately.**  `trace` follows
   only the thread it starts in.  Every request handler in
   `ezpkg_test.py` runs in a `ThreadingHTTPServer` worker, so
   without `threading.settrace` the whole server looks dead however
   many requests pass through it.  That one line moved the suite from
   88% to 99%.

2. **Counts for deleted files have to be dropped.**  A test that
   imports out of a temporary cache leaves counts naming a file that
   its own teardown has removed, and `write_results` raises
   `FileNotFoundError` trying to read the source to annotate it.

3. **What to follow is decided by the code's own file.**  `trace`
   decides by reading `frame.f_globals.get("__file__")`, the calling
   module's `__file__`, but keys its counts by `co_filename`.  A test
   that patches `ezpkg.__file__` to `None` or to a file that is not
   a `.py` made `trace` stop following there, so two lines of
   `repair_module_layout` that a passing test reaches read as never
   run.  `ByCode` asks about `co_filename` instead.  Step 6.16.8.

One blind spot remains, and it is not a defect in the tests:

* **Child processes are not followed** unless `--children` is given.
  Without it `bootstrap.py` reports about 7%, because its fifteen
  cases only ever run in child interpreters.  With it, a copy of
  `ezpkg.py` that a bootstrap installed is credited to the project's
  own file when the two are identical; see `trace_hook/sitecustomize.py`.

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

import argparse
import ast
import concurrent.futures
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import trace
import unittest
from pathlib import Path
from types import FrameType
from typing import Any, cast

# The file `report` keeps the counts in, inside the annotation
# directory, so that `compare` can read a run back without redoing it.
COUNTS: str = "counts.pickle"

# The run with no case selected, and the directory it writes into.
BASELINE: str = "baseline"

# Where `--per-case` keeps the copy of the project it measures, under
# its directory; see `take_snapshot`.
SNAPSHOT: str = "project"

# How many per-case runs go at once unless `--jobs` says otherwise.  Two,
# because each run is itself a busy tree of processes -- the suite, its
# index servers, `pip` and the bootstrap children -- so the machine sees
# far more than one process per run.  Wayne's guidance, 2026-10-01: two
# or three at once, not all of them.
JOBS: int = 2

# The files whose lines `compare` attributes to cases.  This file and
# the trace hook are the instrument, and are left out.
MEASURED: tuple[str, ...] = ("ezpkg.py", "bootstrap.py",
                             "ezpkg_test.py")


class ProjectOnly:
    """Tell `trace` to follow this project's files and nothing else.

    `trace` decides what to follow with an `Ignore` object whose
    `names` method it asks on every new frame.  The standard one is
    given directories to skip, and caches its verdict by the module's
    bare name -- `__init__`, `utils`, `exceptions` -- rather than by
    its path, so whichever `__init__.py` a process meets first decides
    for all the others.  A child that met one of this project's first
    went on to trace every `__init__.py` in the standard library, and
    one that met the standard library's first would have skipped this
    project's.  Step 6.16.4 in `TASKS/` found it.

    This replaces it with a positive rule, cached by path: follow a
    file in this project's directory, or a copy of `ezpkg` that a
    bootstrap installed, which `trace_hook/sitecustomize.py` credits to
    the project.  Everything else -- the standard library, `pip` run in
    process, whatever a test installs -- is left alone, which is both
    correct and much faster.  The hook carries the same rule, since it
    cannot import this file.

    Attributes:
    * `here` (`str`):
      This project's directory, ending in a separator.
    * `verdicts` (`dict[str, int]`):
      1 for a file to skip and 0 for one to follow, by path.

    Constructor:
    * `ProjectOnly()`
    """

    # Set by the constructor; see `Attributes:` above.
    here: str
    verdicts: dict[str, int]

    def __init__(self) -> None:
        """Note where this project lives."""
        # A separator on the end, so a sibling with a longer name is out.
        self.here = str(Path(__file__).resolve().parent) + os.sep
        self.verdicts = {}

    def names(self, filename: str, modulename: str) -> int:
        """Say whether `trace` should skip the code in `filename`.

        Arguments:
        * `filename` (`str`):
          The file a new frame's code came from.
        * `modulename` (`str`):
          Its bare module name, which is unreliable and not used.

        Returns:
        * (`int`): 1 to skip it, 0 to follow it, as `trace` expects.
        """
        # Decide once per path, then answer from the table.
        verdict: int | None = self.verdicts.get(filename)
        if verdict is None:
            wanted: bool = filename.startswith(self.here) or filename.endswith(
                (os.sep + "ezpkg.py",
                 os.sep + os.path.join("ezpkg", "__init__.py")))
            verdict = self.verdicts[filename] = 0 if wanted else 1
        return verdict


class ByCode(trace.Trace):
    """A `trace.Trace` that decides what to follow by the code's own file.

    At each call, `trace` asks its `Ignore` about the **calling
    module's** `__file__`, read out of the frame's globals, but it
    records the counts under the code's own `co_filename`.  The two
    agree until a test replaces a module's `__file__`, which
    `test_repair_declines_what_is_not_a_module` does on purpose: with
    `None`, `trace` stops following the call outright, and with a path
    outside the project, `ProjectOnly` turns it away.  Lines that ran
    then read as never run.  Deciding by `co_filename` asks about the
    same file the counts are kept under.

    Constructor:
    * `ByCode(count=1, trace=0)`, as `trace.Trace`.
    """

    def globaltrace_lt(self, frame: FrameType, why: str, arg: Any) -> Any:
        """Follow a new frame when its code is one of ours.

        Arguments:
        * `frame` (`FrameType`):
          The frame being entered.
        * `why` (`str`):
          The event, which is only acted on when it is `call`.
        * `arg` (`Any`):
          The event's argument, unused.

        Returns:
        * (`Any`): The line counting function to use inside the frame,
          or `None` to leave it alone.
        """
        # The code's file, which is also what the counts are keyed by.
        if why == "call" and not self.ignore.names(
                frame.f_code.co_filename, ""):
            return self.localtrace
        return None


def build_tracer() -> trace.Trace:
    """Return a tracer that counts lines in this project only.

    Anything outside the project is not followed at all, which keeps
    the summary to the files somebody here is responsible for and keeps
    the run from being far slower than the suite it measures.  See
    `ProjectOnly` for why `trace`'s own `ignoredirs` is not used.

    Returns:
    * (`trace.Trace`): A line counting tracer, not yet running.
    """
    # The standard `Ignore` is swapped for one that decides by path,
    # and asked about the code's own file; see `ByCode`.
    tracer: trace.Trace = ByCode(count=1, trace=0)
    tracer.ignore = cast(Any, ProjectOnly())
    return tracer


def run_suite(marked_only: bool = False) -> bool:
    """Run the test suite, swallowing the exit it asks for.

    `unittest.main` exits the interpreter when it is finished, which
    would take the counts with it, so the suite is run with
    `exit=False` and any `SystemExit` is absorbed as well.

    Arguments:
    * `marked_only` (`bool`):
      Run only the tests marked `runs_cases`, which is what a per-case
      run needs; everything else is the baseline's business.

    Returns:
    * (`bool`): Whether every test passed.  Coverage from a failing run
      describes code that did not do its job, so the caller says so.
    """
    # Import inside the traced call, so imports are counted too.
    import ezpkg_test
    if marked_only:
        loaded: unittest.TestSuite = (
            unittest.defaultTestLoader.loadTestsFromModule(ezpkg_test))
        kept: unittest.TestSuite = unittest.TestSuite(marked(loaded))
        return unittest.TextTestRunner().run(kept).wasSuccessful()
    try:
        program: unittest.TestProgram = unittest.main(
            module=ezpkg_test, exit=False, argv=[__file__])
    except SystemExit:
        return False
    return program.result.wasSuccessful()


def marked(suite: unittest.TestSuite) -> list[unittest.TestCase]:
    """Return the tests in `suite` whose method is marked `runs_cases`.

    Arguments:
    * `suite` (`unittest.TestSuite`):
      What the loader produced.

    Returns:
    * (`list[unittest.TestCase]`): The marked tests, in loader order.
    """
    # The mark is on the function, and a bound method reads through.
    return [test for test in flatten(suite)
            if getattr(getattr(test, test._testMethodName, None),
                       "runs_cases", False)]


def flatten(suite: unittest.TestSuite) -> list[unittest.TestCase]:
    """Return the individual tests inside a possibly nested suite.

    Arguments:
    * `suite` (`unittest.TestSuite`):
      What the loader produced, which nests a suite per class.

    Returns:
    * (`list[unittest.TestCase]`): The tests, in loader order, which
      keeps each class's tests together so its fixtures run once.
    """
    # A suite holds tests and further suites, to any depth.
    tests: list[unittest.TestCase] = []
    item: unittest.TestCase | unittest.TestSuite
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            tests += flatten(item)
        else:
            tests.append(item)
    return tests


def report(tracer: trace.Trace, coverdir: Path) -> None:
    """Write the annotated files and print the summary table.

    Arguments:
    * `tracer` (`trace.Trace`):
      The tracer that has finished running.
    * `coverdir` (`Path`):
      Where the annotated `.cover` files go, and the saved counts.
      Created if it does not exist.
    """
    # Drop counts naming files that have since been deleted; see the
    # module docstring.  A test's own teardown is the usual culprit.
    # This file goes too: the instrument does not measure itself.
    here: Path = Path(__file__).resolve()
    results: trace.CoverageResults = tracer.results()
    results.counts = {key: hits for key, hits in results.counts.items()
                      if Path(key[0]).is_file()
                      and Path(key[0]).resolve() != here}

    # Annotate, summarize, and say where the annotations landed.  The
    # counts are kept as well, as `COUNTS`, which is what `compare`
    # reads; `trace` writes them itself when given an `outfile`.
    coverdir.mkdir(parents=True, exist_ok=True)
    results.outfile = str(coverdir / COUNTS)
    results.write_results(show_missing=True, summary=True,
                          coverdir=str(coverdir))
    print(f"\nannotated sources in {coverdir}", file=sys.stderr)


def trace_children(counts: Path) -> None:
    """Arrange for child processes to be traced as well.

    Most of what this suite does happens in children: every `pip`, and
    `bootstrap.py` once or fifteen times over.  `trace` follows neither
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
    os.environ["EZPKG_COVER"] = str(counts)


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


def case_bodies() -> dict[str, tuple[set[int], set[int]]]:
    """Return the lines of each case in `bootstrap.py`.

    Each case is a module level function named after it.  A case covers
    its own body and nothing else does, so those lines say nothing about
    what a case adds.  `compare` sets them aside and reports them
    separately.

    Two sets per case, because they answer different questions.  The
    whole function, `def` line, docstring and comments included, is
    what is set aside; the `def` line runs whenever the file is merely
    imported, which any run may do.  The statements of the body are
    what can execute when the case does, so they are what "how much of
    its own body ran" is counted against: a comment never runs, and the
    continuation lines of a statement are not counted separately by
    `trace`.

    Returns:
    * (`dict[str, tuple[set[int], set[int]]]`): Maps each case label
      to its whole range of lines and to the first lines of its
      statements.
    """
    # Parse rather than search, the way `measure_source` does.
    import bootstrap
    source: Path = Path(__file__).resolve().parent / "bootstrap.py"
    tree: ast.Module = ast.parse(source.read_text(encoding="utf-8"))
    bodies: dict[str, tuple[set[int], set[int]]] = {}
    node: ast.stmt
    for node in tree.body:
        if (isinstance(node, ast.FunctionDef)
                and node.name in bootstrap.MECHANISMS):
            last: int = node.end_lineno or node.lineno
            statements: set[int] = {
                inner.lineno for top in node.body[1:]
                for inner in ast.walk(top)
                if isinstance(inner, ast.stmt)}
            bodies[node.name] = (set(range(node.lineno, last + 1)),
                                 statements)
    return bodies


def covered(counts: Path) -> set[tuple[str, int]]:
    """Return the lines of the `MEASURED` files that a run executed.

    Arguments:
    * `counts` (`Path`):
      A `COUNTS` file written by `report`.

    Returns:
    * (`set[tuple[str, int]]`): Each executed line, as the file's bare
      name and its line number.
    """
    # Only this project's own files, named the way the report names them.
    here: Path = Path(__file__).resolve().parent
    results: trace.CoverageResults = trace.CoverageResults(
        infile=str(counts))
    lines: set[tuple[str, int]] = set()
    filename: str
    number: int
    hits: int
    for (filename, number), hits in results.counts.items():
        path: Path = Path(filename).resolve()
        if hits and path.parent == here and path.name in MEASURED:
            lines.add((path.name, number))
    return lines


def compare(directory: Path) -> str:
    """Say what each case adds to coverage, from runs already made.

    The baseline run covers everything the suite reaches without any
    case, and a case run covers what its tests reach with that case.
    Only lines beyond the baseline can belong to a case, and of those,
    what tells cases apart is the lines only one of them reaches: the
    coverage lost by deleting that case alone.  Deleting several at
    once can lose more, since two cases may share a line nobody else
    reaches, so a greedy ordering is given as well: start from the
    baseline and the case that ships, then keep adding whichever case
    contributes most.  Cases that contribute nothing by the end of that
    ordering are the candidates for deletion, as far as coverage can
    tell.

    Arguments:
    * `directory` (`Path`):
      Holds one subdirectory per case and one named `BASELINE`, each
      with a `COUNTS` file.

    Returns:
    * (`str`): The report, in Markdown.
    """
    # Load every run that finished, setting each case's own body aside.
    import bootstrap
    import ezpkg_test
    bodies: dict[str, tuple[set[int], set[int]]] = case_bodies()
    every_body: set[tuple[str, int]] = {
        ("bootstrap.py", number)
        for whole, _ in bodies.values() for number in whole}
    base: Path = directory / BASELINE / COUNTS
    baseline: set[tuple[str, int]] = (covered(base) - every_body
                                      if base.is_file() else set())
    runs: dict[str, set[tuple[str, int]]] = {}
    own: dict[str, set[tuple[str, int]]] = {}
    label: str
    for label in bootstrap.MECHANISMS:
        counts: Path = directory / label / COUNTS
        if counts.is_file():
            lines: set[tuple[str, int]] = covered(counts)
            runs[label] = lines - every_body - baseline
            # Its own statements only: every case's `def` line runs
            # whenever `bootstrap.py` is imported, so the others' are
            # covered too.
            own[label] = lines & {("bootstrap.py", number) for number
                                  in bodies.get(label, (set(), set()))[1]}
    missing: list[str] = [label for label in ezpkg_test.cases()
                          if label not in runs]
    if not base.is_file():
        missing.insert(0, BASELINE)

    # What only one case reaches.
    out: list[str] = [f"# Coverage by case, from `{directory}`", ""]
    if missing:
        out += [f"No counts for: {', '.join(missing)}.", ""]
    out += [(f"The baseline covers {len(baseline)} lines outside the "
             "case bodies.  Below, `beyond` is what a case adds to the "
             "baseline and `only` is what no other case adds.  Lines in "
             "`ezpkg.py` are the ones that matter most: the test file "
             "covers itself."), "",
            ("| case | own body | beyond | of which `ezpkg.py` | only "
             "| of which `ezpkg.py` |"),
            "|------|----------|--------|-----|------|-----|"]
    unique: dict[str, set[tuple[str, int]]] = {}

    def product(lines: set[tuple[str, int]]) -> int:
        """Count the lines of `lines` that are in `ezpkg.py`.

        Arguments:
        * `lines` (`set[tuple[str, int]]`):
          Lines as `covered` names them.

        Returns:
        * (`int`): How many are in the product rather than its tests.
        """
        # The product is the one file that ships.
        return sum(1 for name, _ in lines if name == "ezpkg.py")

    for label, lines in runs.items():
        others: set[tuple[str, int]] = set().union(
            *(runs[other] for other in runs if other != label))
        unique[label] = lines - others
        out.append(f"| {label} | {len(own[label])} of "
                   f"{len(bodies.get(label, (set(), set()))[1])} | "
                   f"{len(lines)} | "
                   f"{product(lines)} | {len(unique[label])} | "
                   f"{product(unique[label])} |")

    # The greedy ordering, starting from what ships.
    out += ["", "## Greedy ordering", "",
            "| step | case | lines added | total |",
            "|------|------|-------------|-------|",
            f"| 0 | {BASELINE} | {len(baseline)} | {len(baseline)} |"]
    total: set[tuple[str, int]] = set(baseline)
    remaining: list[str] = list(runs)
    step: int = 0
    while remaining:
        shipping: list[str] = [label for label in remaining
                               if label == ezpkg_test.SHIPPING]
        best: str = (shipping[0] if shipping else max(
            remaining, key=lambda one: len(runs[one] - total)))
        added: int = len(runs[best] - total)
        total |= runs[best]
        step += 1
        out.append(f"| {step} | {best} | {added} | {len(total)} |")
        remaining.remove(best)

    # The lines themselves, so a decision can be read off the source.
    here: Path = Path(__file__).resolve().parent
    sources: dict[str, list[str]] = {
        name: (here / name).read_text(encoding="utf-8").splitlines()
        for name in MEASURED}
    for label, lines in unique.items():
        if lines:
            out += ["", f"## Only `{label}`", "", "```"]
            name: str
            number: int
            for name, number in sorted(lines):
                out.append(f"{name}:{number}: "
                           f"{sources[name][number - 1].strip()}")
            out.append("```")
    return "\n".join(out) + "\n"


def take_snapshot(here: Path, copy: Path) -> None:
    """Copy the project to `copy`, for a per-case run to measure.

    A per-case run reads the tree for a quarter of an hour, and its
    report is only true if no file changes meanwhile: on 2026-10-01 an
    edit made during a run shifted line numbers between the baseline and
    the cases, and the report claimed lines the cases never ran.  A copy
    cannot be edited by accident.  Caches and version control are left
    out, and symbolic links stay links.  See Step 6.16.4 in `TASKS/`.

    Arguments:
    * `here` (`Path`):
      The project directory, where this file is.
    * `copy` (`Path`):
      Where the copy goes; anything already there is replaced.
    """
    # Replace, so that a second run never measures a stale copy.
    shutil.rmtree(copy, ignore_errors=True)
    shutil.copytree(here, copy, symlinks=True, ignore=shutil.ignore_patterns(
        ".git", ".hg", "__pycache__", ".mypy_cache", ".ruff_cache"))


def measure_one(name: str, selection: str, marked_only: bool,
                directory: Path) -> tuple[str, int, float]:
    """Measure the suite in a child process, writing under `name`.

    A child of its own per run, rather than a loop in this process,
    because `trace` keeps one set of counts per process and the suite's
    module level state is only fresh once.  Everything the run writes
    lands under its own directory, so runs side by side never share a
    file: the annotations, `COUNTS`, the child counts and the log.

    Arguments:
    * `name` (`str`):
      The run's name, which is its directory under `directory`: a case
      label, or `BASELINE`.
    * `selection` (`str`):
      What `EZPKG_TEST` is set to for the run.
    * `marked_only` (`bool`):
      Whether to run only the tests marked `runs_cases`.
    * `directory` (`Path`):
      The parent directory.

    Returns:
    * (`tuple[str, int, float]`): The name, the exit status, and the
      wall clock seconds taken.
    """
    # A fresh directory, then the measurement with children.
    target: Path = directory / name
    target.mkdir(parents=True, exist_ok=True)
    environment: dict[str, str] = dict(os.environ, EZPKG_TEST=selection)
    command: list[str] = [sys.executable, str(Path(__file__).resolve()),
                          "--children", str(target)]
    if marked_only:
        command.append("--marked-only")
    start: float = time.perf_counter()
    with open(target / "log.txt", "w", encoding="utf-8") as log:
        done: subprocess.CompletedProcess[bytes] = subprocess.run(
            command, env=environment, stdout=log,
            stderr=subprocess.STDOUT, check=False)
    return name, done.returncode, time.perf_counter() - start


def measure_cases(directory: Path, jobs: int) -> bool:
    """Measure a baseline, then each case separately, `jobs` at a time.

    The cases are the ones `EZPKG_TEST` selects, as for the suite
    itself: `nopip1` and `nopip5` by default, and all fifteen under
    `COMPLETE`.

    The baseline is the whole suite with no case selected, and is the
    one long run.  Each case then runs only the tests that run cases,
    since everything else would only repeat the baseline.  The baseline
    is submitted first, so that it overlaps the cases rather than
    following them.

    Arguments:
    * `directory` (`Path`):
      Where each case's run goes, one subdirectory per case.
    * `jobs` (`int`):
      How many runs go at once.

    Returns:
    * (`bool`): Whether every run passed its tests.
    """
    # Each run is a process of its own, so threads only wait on them.
    import ezpkg_test
    passed: bool = True
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        pending: list[concurrent.futures.Future[tuple[str, int, float]]] = [
            pool.submit(measure_one, BASELINE, "NONE", False, directory)]
        pending += [pool.submit(measure_one, label, label, True, directory)
                    for label in ezpkg_test.cases()]
        future: concurrent.futures.Future[tuple[str, int, float]]
        for future in concurrent.futures.as_completed(pending):
            label: str
            status: int
            seconds: float
            label, status, seconds = future.result()
            verdict: str = "ok" if status == 0 else f"FAILED ({status})"
            print(f"{label:>7}: {verdict:<12} {seconds:6.0f} s",
                  file=sys.stderr)
            passed = passed and status == 0
    return passed


def main() -> int:
    """Measure the suite and report on it, in one of three ways.

    * With a directory, or none, measure the suite once.  Without one a
      temporary directory is made and its path printed, so nothing
      lands in the project tree.  `--children` also traces child
      processes, which is the only way to see `bootstrap.py` at all and
      costs several minutes.
    * With `--per-case`, copy the project into the directory, then
      measure the copy once per `bootstrap.py` case, children included,
      `--jobs` at a time, and compare the runs.
    * With `--compare`, only compare runs that `--per-case` already
      made, which costs seconds, again in the copy.

    Returns:
    * (`int`): The exit status: 0 when every test passed.
    """
    # The arguments, in whatever order they came.
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Measure test suite coverage with `trace`.")
    parser.add_argument("directory", nargs="?",
                        help="where the annotated files and counts go")
    parser.add_argument("--children", action="store_true",
                        help="trace child processes as well")
    parser.add_argument("--per-case", action="store_true",
                        help="measure once per bootstrap case, then compare")
    parser.add_argument("--compare", action="store_true",
                        help="compare per-case runs already made")
    parser.add_argument("--marked-only", action="store_true",
                        help="internal: only tests marked runs_cases")
    parser.add_argument("--jobs", type=int, default=JOBS,
                        help=f"per-case runs at once (default: {JOBS})")
    arguments: argparse.Namespace = parser.parse_args()
    if (arguments.per_case or arguments.compare) and not arguments.directory:
        parser.error("--per-case and --compare need a directory")
    coverdir: Path = (Path(arguments.directory) if arguments.directory
                      else Path(tempfile.mkdtemp(prefix="cover-")))

    # `--per-case` measures a copy of the project, and `--compare` reads
    # the copy back, because the counts name its files and lines; both
    # go on in the copy's own `ezpkg_coverage.py`.  A directory from
    # before copies were made is compared in place, as it always was.
    here: Path = Path(__file__).resolve().parent
    copy: Path = coverdir.resolve() / SNAPSHOT
    if arguments.per_case and here != copy:
        take_snapshot(here, copy)
    if (arguments.per_case or arguments.compare) and here != copy \
            and copy.is_dir():
        return subprocess.run(
            [sys.executable, str(copy / Path(__file__).name), *sys.argv[1:]],
            check=False).returncode

    # This directory has to be importable for the suite to be found.
    sys.path.insert(0, str(here))

    # The per-case modes measure in children and read the results back.
    if arguments.per_case or arguments.compare:
        passed: bool = True
        if arguments.per_case:
            passed = measure_cases(coverdir, arguments.jobs)
        text: str = compare(coverdir)
        (coverdir / "report.md").write_text(text, encoding="utf-8")
        print(text)
        print(f"report in {coverdir / 'report.md'}", file=sys.stderr)
        return 0 if passed else 1

    # Otherwise one measurement of the whole suite, here.
    counts: Path = coverdir / "child-counts"
    if arguments.children:
        trace_children(counts)

    # Instrument the worker threads as well as this one, then run.
    tracer: trace.Trace = build_tracer()
    threading.settrace(tracer.globaltrace)
    passed = bool(tracer.runfunc(run_suite, arguments.marked_only))
    folded: int = (merge_children(tracer, counts) if arguments.children
                   else 0)
    if arguments.children:
        print(f"folded in {folded} child processes", file=sys.stderr)
    report(tracer, coverdir)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
