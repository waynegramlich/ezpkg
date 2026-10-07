# 6.16 Test suite cleanup: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.16 of `LOGBOOK.md` on 2026-10-04.

* Step 6.16: Test suite cleanup, headed towards deleting some of the
  cases in `bootstrap.py` now that `nopip3` ships.
  * 6.16.1 - **Cases are named, not numbered**, 2026-10-01, at Wayne's
    suggestion.  The numbers were the order the cases were written, so
    every addition or removal threatened to renumber something.  A name
    now says what the case needs on the machine, with a digit counting
    within its group: `venv` cases create a virtual environment, `pip`
    cases run a pip already installed, and `nopip` cases need none.
    Old to new:

    | Old | New      | Old | New      | Old | New      |
    |-----|----------|-----|----------|-----|----------|
    | 1   | `venv1`  | 6   | `pip1`   | 11  | `venv4`  |
    | 2   | `venv2`  | 7   | `pip2`   | 12  | `nopip2` |
    | 3   | `nopip1` | 8   | `pip3`   | 13  | `nopip3` |
    | 4   | `venv3`  | 9   | `pip4`   |     |          |
    | 5   | `venv5`  | 10  | `pip5`   |     |          |

    The code, the table and the tests use the names, and the
    `bootstrap.py` docstring carries the same mapping.  Closed tasks
    keep the old numbers, and so do the steps of this task written
    before the change, Step 6.15 included.  `README.md` still passes
    `bootstrap="7"` to `install`, which nothing reads yet; it becomes
    `"nopip3"` whenever Wayne's rewrite reaches the paste.

  * 6.16.2 - **The cull run**, built 2026-10-01, so that cases are
    deleted on evidence rather than by taste.  Wayne's framing: the test
    suite is the product, culling will recur, and one run a night while
    he sleeps is affordable.  The parts:

    * `ALT_VENV_TEST` also takes case names, `pip2` or `pip1,pip2`, and
      `NONE`, which selects no case at all.
    * `selected` gates the few tests written for particular cases, the
      matcher tests for `nopip1` and `nopip2` and the no-`pip` test for
      `nopip3`, so that a run for one case does not quietly include them.
    * `@runs_cases` marks every test that runs a case, and
      `test_case_runners_are_marked` checks the marks against the
      source; deleting a mark was tried and the guard failed, as meant.
    * `alt_venv_coverage.py --per-case <dir>` makes one baseline run of
      the whole suite with `NONE`, then runs only the marked tests once
      per case, two runs at a time, children traced throughout, each run
      writing only under `<dir>/<run>/`.  `--compare <dir>` redoes the
      report from the saved counts in seconds.
    * The trace hook credits a copy of `alt_venv.py` that a bootstrap
      installed to the project's own file, when the two are identical,
      since the copy is deleted with its test.  Checked: the counts land
      on the project path.

    Measured: the whole suite traced for one case took 11 min 23 s, and
    only the marked tests 55 s, so the first design would have cost
    about 75 minutes a night.  The real cull took 12 min 19 s, of which
    the baseline is 717 s and the thirteen cases overlap it.  Wayne
    starts it at bedtime; the command is in `CLAUDE.md`.
  * 6.16.3 - **First cull, 2026-10-01**, in
    `~/alt_venv_cull/2026-10-01/report.md`.  Every case runs every one
    of its own statements.  Beyond the baseline:

    * No case adds a single line of `alt_venv.py`.  The baseline alone
      covers everything the product does.
    * All ten `venv` and `pip` cases add the same 63 lines of the test
      file, the shared every-case tests, and nothing of their own.
    * `nopip1` adds 4 lines nobody else does, the truncated-wheel test.
      `nopip2` adds nothing that `nopip1` does not.
    * `nopip3` adds 32 lines nobody else does, all of them the no-`pip`
      test.
    * Greedy, from the baseline: `nopip3` then `nopip1`, and the other
      eleven add nothing.

    So on coverage alone, eleven of the thirteen cases could go.  What
    coverage cannot see is their other job: the table in `bootstrap.py`
    prices each mechanism, and that record is what Steps 6.14 and 6.15
    were decided on.  Whether that record needs to stay runnable, or can
    live on as a table in the log, is Wayne's call.
  * 6.16.4 - A child's counts include standard library lines, such as
    `/usr/lib/python3.12/zipfile`, although the trace hook names
    `sys.base_prefix` among the directories to ignore.  The report reads
    only this project's files, so the answer is unaffected; the cost is
    time and the size of the counts.  Not yet looked into.

    Looked into, 2026-10-01, and it was worse than a cost.  `trace`'s
    own `Ignore` caches its verdict by a module's **bare name** --
    `__init__`, `utils`, `exceptions` -- not its path, so whichever
    `__init__.py` a process met first decided for every other.  Children
    that met one of this project's first traced every `__init__.py` in
    the standard library; and in the other direction, project files
    were being **skipped** whenever a standard library file of the same
    name came first.  A separate leak: `venv3` runs `pip` in its own
    process, so 57,162 lines of `pip` were traced in one child.  Both
    tracers, the parent's `build_tracer` and the child hook, now swap
    `trace`'s `Ignore` for a positive rule cached by path: follow this
    project's directory and installed copies of `alt_venv`, and nothing
    else.  Measured on one case at a time, nothing was lost and lines of
    `alt_venv.py` that had been skipped were gained; `venv3` went from
    86.5 s to 71.6 s and `nopip3` from 22.6 s to 21.4 s.  A whole
    `COMPLETE` cull still took 761 s against the morning's 739, on a
    suite fifteen tests larger: the time is in the work the tests do,
    not in tracing them.

    That cull's **report is void**.  Claude edited `alt_venv.py` and
    `alt_venv_test.py`, for 6.12, while it ran, so the baseline and the
    later cases counted the same lines under different numbers, and
    cases looked to add hundreds of lines they did not.  A nightly run
    on a still tree is not at risk, but the cull trusts the tree to stay
    still for a quarter of an hour; copying the project somewhere first
    and measuring the copy would remove that trust.  Not built.
  * 6.16.5 - **The other ten cases stay but stop running**, 2026-10-01.
    Wayne: "leaving the tests around hurts nothing.  From now on just
    run nopip1-3."  `FAST_CASES` became `nopip1` to `nopip3`, and the
    cull takes its cases from `ALT_VENV_TEST` as the suite does, so it
    measures those three unless told `COMPLETE`.  `FAST_CASES` had been
    standing in for "the case that ships", which three cases cannot do,
    so that meaning moved to a constant of its own, `SHIPPING`.
  * 6.16.6 - **The cull has tests**, 2026-10-01: `CoverageToolTest`,
    twelve of them, on counts written by hand and with child processes
    mocked, so that nothing is traced inside a run the tool may itself
    be tracing.  They cover `flatten`, `marked` (pulled out of
    `run_suite` to be testable), `case_bodies`, `covered`, `compare`,
    `report`, `merge_children`, `trace_children`, `measure_one`,
    `measure_cases` and `main`'s `--compare` path.  Two bugs found
    earlier in the day were put back one at a time, the own-body count
    and the greedy order ignoring the shipping case, and the comparison
    test failed on each.  Not covered: `run_suite` and `main`'s
    measuring path, which run the suite itself, and `_credit` in the
    trace hook, which only exists inside a traced child.

  * 6.16.7 - **A full traced run, unattended**, 2026-10-01, while Wayne
    wrote `README.md`: `ALT_VENV_TEST=COMPLETE ./alt_venv_coverage.py
    --children`, 215 tests passing in 20 minutes, 343 children folded in.
    `alt_venv.py` 98%, `bootstrap.py` 99%, `alt_venv_test.py` 95%.  No
    test failed and no product bug turned up.  What it did turn up:

    * Six lines of `alt_venv.py` no test reached: a program that does
      not parse, in `find_bootstrap`, and the two `OSError` arms of
      `refresh_pip`.  Three tests now reach them, checked by tracing
      them alone.  Two more lines read as missed but are not: the
      frozen interpreter branch, already noted, and the refusal of a
      module whose `__file__` is not a `.py`, whose test patches the
      very `__file__` that `trace` reads to decide what to follow.
      `alt_venv_coverage.py`'s docstring now names both.
    * The opt-in suites, run too.  `ReportTest`, behind
      `ALT_VENV_REPORT`, had been broken since 6.16.1: it looked for
      `| venv1 |` in the table, but naming the cases widened the label
      column, so all ten shorter names are padded.  It reads the width
      from `bootstrap.COLUMN_WIDTHS` now.  `PyPITest` passed.
    * A new opt-in test, `test_the_shipping_path_against_pypi`: an
      interpreter with no `pip` runs `nopip3` against the **real**
      PyPI for `pip`, then a program declaring `requests` gets it, and
      its four dependencies, from the real PyPI through the private
      `pip`.  Only `alt_venv` itself comes from a local index, since
      no index has it yet.  It passes, in about eight seconds.
    * Writing it found that `run_bootstrap_case` raised `TypeError`
      when `extra` repeated a variable it sets itself, such as
      `BOOTSTRAP_JSON_API`.  `extra` now overrides.

  * 6.16.8 - **The last two missed lines were the tracer's fault**,
    2026-10-02, on a second full traced run while Wayne took a break:
    `ALT_VENV_TEST=COMPLETE ./alt_venv_coverage.py --children`, 220
    tests passing in 20 minutes, 343 children folded in, then the
    opt-in `PyPITest` and `ReportTest`, all passing (one expected
    failure, `I.wtmifs`'s abi3 test).

    The two lines 6.16.7 accepted as unreachable, in
    `repair_module_layout`, were reached all along; a probe saw
    `__file__` arrive as `None` and as a `.txt` path.  The cause is in
    `trace`: `globaltrace_lt` decides whether to follow a call by the
    **calling module's** `__file__`, read from the frame's globals, but
    keys the counts by the code's `co_filename`.  The test patches
    `alt_venv.__file__`, so with `None` `trace` gives up on the frame,
    and with a path outside the project `ProjectOnly` turns it away.
    Both tracers now subclass `trace.Trace` (`ByCode` in
    `alt_venv_coverage.py`, `_ByCode` in the hook) and ask about
    `co_filename`, the file the counts are kept under.  Rerun:
    `alt_venv.py` 100%, `bootstrap.py` 99%, `alt_venv_test.py` 94%.
    What remains missed is environmental -- a non-CPython interpreter,
    no `openssl`, an unexpected server error -- or belongs to the
    opt-in classes and to `skipTest` lines that cannot fire under
    `COMPLETE`.  `alt_venv_coverage.py`'s docstring no longer lists
    the two lines as a blind spot.
  * 6.16.9 - **Python 3.11 found three faults**, 2026-10-02, overnight
    while Wayne slept.  Under 3.12, everything at once --
    `COMPLETE`, `--children`, `ALT_VENV_PYPI` and `ALT_VENV_REPORT` --
    passed, with `alt_venv.py` and, for the first time, `bootstrap.py`
    both at 100%.  The same run under uv's CPython 3.11.16, which is
    not Debian's, failed five tests and passed one it should not:

    * **`pip3` only worked on Debian.**  It takes `pip` from
      `ensurepip._WHEEL_PKG_DIR`, which Debian and Ubuntu patch to
      `/usr/share/python-wheels/`; everywhere else it is `''`, so the
      case globbed the current directory and `next` raised a bare
      `StopIteration`.  `ensurepip` itself falls back to its own
      `_bundled` directory, and now so does the case, at the cost of a
      line: 19 lines, 22 pasted.  A product bug in a case nobody ships.
    * **`test_the_shipping_path_against_pypi` told the two `pip`s apart
      by version**, assuming the local one never matches PyPI's newest.
      uv's 3.11 carries `pip` 26.2.1, which is PyPI's newest, so the
      wheel kept looked local.  It now compares contents.
    * **`I.wtmifs`'s expected failure passed** under 3.11, because
      `cryptography` publishes a `cp311-abi3` wheel that the matcher
      finds by exact tag.  The gap is real only from 3.12, so the test
      expects failure only there, through `ABI3_GAP`.
