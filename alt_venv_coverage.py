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

`--per-case <directory>` answers a different question: what does each
`bootstrap.py` case add?  The cases are those `ALT_VENV_TEST` selects,
so `nopip1` to `nopip3` unless it says `COMPLETE`.  It makes one
baseline run of the whole suite with `ALT_VENV_TEST=NONE`, so that no
case runs, and then one run per case of only the tests marked
`runs_cases`, with `ALT_VENV_TEST` naming that case.  Children are
traced throughout.  Runs go two at a time by default (`--jobs`), since
each is a busy tree of processes in its own right, and each writes only
under `<directory>/<run>/`, so runs side by side cannot overwrite each
other.  Then it compares them and writes `report.md`: what each case
adds beyond the baseline, the lines only one case reaches, and a greedy
ordering from the case that ships showing which cases add nothing.
`--compare <directory>` redoes just the comparison from the saved
counts, in seconds, which is what makes culling cases cheap to repeat.
See Step 6.16 of `LOGBOOK.md`.

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

* **Child processes are not followed** unless `--children` is given.
  Without it `bootstrap.py` reports about 7%, because its thirteen
  cases only ever run in child interpreters.  With it, a copy of
  `alt_venv.py` that a bootstrap installed is credited to the project's
  own file when the two are identical; see `trace_hook/sitecustomize.py`.
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

import argparse
import ast
import concurrent.futures
import os
import subprocess
import sys
import tempfile
import threading
import time
import trace
import unittest
from pathlib import Path

# The file `report` keeps the counts in, inside the annotation
# directory, so that `compare` can read a run back without redoing it.
COUNTS: str = "counts.pickle"

# The run with no case selected, and the directory it writes into.
BASELINE: str = "baseline"

# How many per-case runs go at once unless `--jobs` says otherwise.  Two,
# because each run is itself a busy tree of processes -- the suite, its
# index servers, `pip` and the bootstrap children -- so the machine sees
# far more than one process per run.  Wayne's guidance, 2026-10-01: two
# or three at once, not all of them.
JOBS: int = 2

# The files whose lines `compare` attributes to cases.  This file and
# the trace hook are the instrument, and are left out.
MEASURED: tuple[str, ...] = ("alt_venv.py", "bootstrap.py",
                             "alt_venv_test.py")


def build_tracer() -> trace.Trace:
    """Return a tracer that counts lines in this project only.

    The standard library is excluded.  Counting it would swamp the
    summary with hundreds of modules nobody here is responsible for,
    and would make the run far slower than the suite it measures.

    Returns:
    * (`trace.Trace`): A line counting tracer, not yet running.
    """
    # Exclude the interpreter's own directories, whatever they are.
    # `sys.prefix` is the virtual environment when there is one, and
    # the standard library then lives under `sys.base_prefix`, so
    # naming only the first traces the whole standard library in a
    # venv child.  Found by Step 6.5.15.
    return trace.Trace(count=1, trace=0,
                       ignoredirs=[sys.prefix, sys.exec_prefix,
                                   sys.base_prefix,
                                   sys.base_exec_prefix])


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
    import alt_venv_test
    if marked_only:
        loaded: unittest.TestSuite = (
            unittest.defaultTestLoader.loadTestsFromModule(alt_venv_test))
        kept: unittest.TestSuite = unittest.TestSuite(marked(loaded))
        return unittest.TextTestRunner().run(kept).wasSuccessful()
    try:
        program: unittest.TestProgram = unittest.main(
            module=alt_venv_test, exit=False, argv=[__file__])
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
    `bootstrap.py` once or thirteen times over.  `trace` follows neither
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
    import alt_venv_test
    import bootstrap
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
    missing: list[str] = [label for label in alt_venv_test.cases()
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
             "`alt_venv.py` are the ones that matter most: the test file "
             "covers itself."), "",
            ("| case | own body | beyond | of which `alt_venv.py` | only "
             "| of which `alt_venv.py` |"),
            "|------|----------|--------|-----|------|-----|"]
    unique: dict[str, set[tuple[str, int]]] = {}

    def product(lines: set[tuple[str, int]]) -> int:
        """Count the lines of `lines` that are in `alt_venv.py`.

        Arguments:
        * `lines` (`set[tuple[str, int]]`):
          Lines as `covered` names them.

        Returns:
        * (`int`): How many are in the product rather than its tests.
        """
        # The product is the one file that ships.
        return sum(1 for name, _ in lines if name == "alt_venv.py")

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
                               if label == alt_venv_test.SHIPPING]
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
      What `ALT_VENV_TEST` is set to for the run.
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
    environment: dict[str, str] = dict(os.environ, ALT_VENV_TEST=selection)
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

    The cases are the ones `ALT_VENV_TEST` selects, as for the suite
    itself: `nopip1` to `nopip3` by default, and all thirteen under
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
    import alt_venv_test
    passed: bool = True
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        pending: list[concurrent.futures.Future[tuple[str, int, float]]] = [
            pool.submit(measure_one, BASELINE, "NONE", False, directory)]
        pending += [pool.submit(measure_one, label, label, True, directory)
                    for label in alt_venv_test.cases()]
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
    * With `--per-case`, measure once per `bootstrap.py` case, children
      included, `--jobs` at a time, and then compare the runs.
    * With `--compare`, only compare runs that `--per-case` already
      made, which costs seconds.

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

    # This directory has to be importable for the suite to be found.
    sys.path.insert(0, str(Path(__file__).resolve().parent))

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
