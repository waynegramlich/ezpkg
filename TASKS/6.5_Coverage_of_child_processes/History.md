# 6.5 Coverage of child processes: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.5 of `LOGBOOK.md` on 2026-10-04.

* Step 6.5: Coverage of child processes.  Most of what this suite does
  happens in children, and `trace` follows neither those nor threads, so
  `bootstrap.py` read as 7% however thoroughly its twelve cases were
  exercised.
  * 6.5.1 - `trace` merges its own results: `CoverageResults` reads a
    saved count file through `infile` and folds another in through
    `update`, so no third party tool is wanted.  Each child writes its
    own file named after its process id, so there is no shared file for
    two writers to lose an entry in.
  * 6.5.2 - The only hook that reaches a process nobody wrote the
    command line for is `sitecustomize`, which Python imports from
    `sys.path` at startup.  It lives in `trace_hook/`, which is **not**
    anywhere Python looks by default: `alt_venv_coverage.py --children`
    puts it on `PYTHONPATH`.  A `sitecustomize.py` in the project root
    would quietly affect every interpreter started from that directory.
  * 6.5.3 - Two mistakes worth not repeating.  Reading the counts while
    the tracer still runs raises
    `RuntimeError: dictionary changed size during iteration`, so
    tracing has to be switched off first.  And
    `CoverageResults.write_results` also writes annotated `.cover` files
    into the working directory, which littered the project root; the
    counts are pickled directly instead.
  * 6.5.4 - `pip` is skipped by the hook.  It is nobody here's code and
    it is most of the cost: case 6, which runs `pip._internal` in
    process, went from 1.21 s to 10.33 s traced, where case 3 went from
    0.16 s to 0.29 s.
  * 6.5.5 - The result on the fast suite: `bootstrap.py` 7% to 41%,
    113 child processes folded in, 60 tests in 357 s against 70 s.
  * 6.5.6 - **`I.wtmifs` is now measured rather than argued.**  Cases 3
    and 12 each have exactly seven uncovered lines, the same seven: the
    wheel tag matcher's platform branch,
    `or (machine in name and "linux" in name and sys.platform ==
    "linux")`, has **never executed**, and neither has
    `raise RuntimeError("no compatible wheel found")`.  The issue said
    the matcher "agreed with pip for one package on one platform"; the
    interesting half of it has never run at all.
  * 6.5.7 - The `.data/purelib` and `.data/platlib` move in cases 3 and
    12 has never executed either, for the same reason it had never
    executed in `AltVEnv.unpack`: no wheel the suite builds has a
    `.data` tree.  That gap hid a real bug in the second stage, a
    `.data` directory left behind after the move, found the same day.
    The pasted code has the identical blind spot.
  * 6.5.8 - What is not a defect: on the fast suite, cases 1, 2, 4, 5
    and 7 to 10 are barely covered because `FAST` selects only 3, 6, 11
    and 12, and 98 module level lines are `run_tests`,
    `measure_source`, `format_table` and `directory_size`, which run
    only when `bootstrap.py` is invoked from the command line.
  * 6.5.9 - The complete run settles it.  `ALT_VENV_TEST=COMPLETE` with
    children traced: 60 tests in 837 s, 184 child processes, and
    `bootstrap.py` at 72%.  **Ten of the twelve cases are covered
    completely, 0 lines missed.**  The only dead code inside any pasted
    case is the seven lines in each of cases 3 and 12 named above: the
    matcher's platform branch, its `raise`, and the `.data` move.  The
    remaining 98 are the measurement harness, which runs from the
    command line and produced the Task 5 chart by hand.
  * 6.5.10 - So the hook is worth keeping.  It turned one open issue
    into a measurement, found the same `.data` blind spot in the pasted
    code that had just hidden a real bug in the second stage, and
    cleared ten of twelve cases outright.  Nothing else here could have
    said any of that.
  * 6.5.11 - Done 2026-09-26.  `build_wheel` gained a `tag`, the index
    publishes a second `alt-venv` wheel wearing this interpreter's
    compiled tag and carrying a `.data/purelib` member, and a third
    test serves one `cp312-cp312-win_amd64` wheel so that nothing
    matches.  Cases 3 and 12 prefer the tagged wheel, move its `.data`
    member up beside the module, and refuse the Windows one with
    `no compatible wheel found` and no traceback.  `bootstrap.py` is at
    75% and **all twelve pasted cases are covered completely**; the
    remaining 98 lines are the command line measurement harness.
  * 6.5.12 - No new bug was found in that round, which is worth
    recording as a result rather than a disappointment.  The matcher
    behaved correctly for all three shapes a Linux machine can build.
    The earlier rounds did find three: the stray `.data` directory, the
    `repair_module_layout` unlink race, and a jail boundary crossed
    while staging.  Cost to keep: 62 tests in 87 s normally, about
    seventeen minutes with `--children` on `COMPLETE`, and the hook is
    off unless asked for.
  * 6.5.13 - The quick run is one case, from 2026-09-27.  Six tests loop
    over `cases()`, so the four `FAST_CASES` were costing 42.5 s of a
    91.5 s run; measured with `unittest --durations`, which also named
    `test_an_untrusted_certificate_is_refused` at 19.8 s against 5.3 s
    for the trusted one, unexplained and worth a look, since retrying a
    rejected certificate is wrong on its own terms.  `FAST_CASES` is now
    case 7 alone and the suite runs in 61 s.

    Case 7 because this project is not shipping a virtual environment,
    which leaves the shortest paste, and four cases tie there at sixteen
    lines.  Cases 6 and 9 run `pip` in process, which leaves 451 of its
    modules in `sys.modules` and three handlers on the root logger of
    somebody else's program; case 10 is 7 plus `--no-compile`, worth
    60 KB.  Case 7 is what is left, and is the likeliest product.  The
    other eleven, including the no-`pip` case 3 that is the whole point
    of the exercise, run under `ALT_VENV_TEST=COMPLETE`, which is what
    the end of a task gets.

    One consequence to expect rather than be alarmed by: `bootstrap.py`
    reads 39% traced instead of 75%, because eleven case bodies no longer
    run in the quick suite.  It is not a regression, and `COMPLETE` is
    where those lines are covered now.
  * 6.5.14 - Sixth traced round, 2026-09-27, after Step 6.7 landed the
    locator, the parser and `install()`.  118 tests, 524 s with children
    traced, 170 child processes folded in; `alt_venv.py` at 98% and
    `alt_venv_test.py` at 99%.  Five unexercised lines, and chasing them
    was worth it again:

    * **A real defect.** `approve` returning `None` was never reached, and
      the reason it mattered was one line up its call chain: with
      `ALT_VENV_APPROVE=write` and a program that has no file, `gate`
      printed `approvals written to None`, announcing a file it had not
      written.  It now says there is nowhere to write one.
    * **Three guards that were simply untested**, now tested: `verify`
      with no approvals file, which `gate` cannot reach because it looks
      first, so the guard is for anyone calling the public method;
      a cache record naming a different request, which means an edited
      file or a digest collision and is not evidence either way; and
      `consent` reading end of file from the terminal, where asking again
      would spend the patience meant for typos on a terminal that has
      gone away.
    * **One line that should stay uncovered.** The `__file__ is None` arm
      of `repair_module_layout`, for a frozen interpreter: `trace` cannot
      follow a frame whose `__file__` is false, so the tracer could not
      see that line run even if it did.

    Found by hand in the same sitting, while the tracer was busy, which
    is worth recording because no coverage tool would have found it: a
    `# -*- coding: latin-1 -*-` program is perfectly legal Python and the
    interpreter honours the cookie, but `Path.read_text(encoding="utf-8")`
    refused it, so `main_source` returned `None` and the program declared
    nothing at all, in silence.  `tokenize.open` is the standard library's
    own answer to the question and honours a cookie and a byte order mark
    alike, so a program the interpreter can run is now a program we can
    read.

  * 6.5.15 - Seventh traced round, 2026-09-27, everything turned up at
    once: `ALT_VENV_TEST=COMPLETE`, `ALT_VENV_PYPI=1` and `--children`.
    Nothing new in the product -- `alt_venv.py` still has exactly one
    uncovered line, the frozen interpreter arm, and `bootstrap.py`'s 98
    uncovered lines are precisely the command line measurement harness,
    so all twelve pasted cases remain covered.

    The instrument, though, has a defect this run exposed and no `FAST`
    run could: **the child tracer stops ignoring the standard library
    inside a virtual environment.**  Both tracers are built with
    `ignoredirs=[sys.prefix, sys.exec_prefix]`, which is correct for an
    ordinary interpreter.  In a virtual environment `sys.prefix` is the
    environment and the standard library is under `sys.base_prefix`;
    measured 2026-09-27, `/usr/lib/python3.12/pathlib.py` does not start
    with the venv's `sys.prefix`.  So the six venv cases traced the whole
    standard library, which is why this report carries dozens of
    `/usr/lib/python3.12` rows that earlier reports did not.

    Consequences are noise and time rather than wrong numbers -- each
    file's percentage is still its own -- but tracing every line of
    `typing`, `tarfile` and `ssl` in six children is not free.  The fix
    is to add `sys.base_prefix` and `sys.base_exec_prefix` to both
    `ignoredirs` lists, in `alt_venv_coverage.py` and in
    `trace_hook/sitecustomize.py`.  Left unapplied for Wayne to call,
    since it changes what the instrument considers ours.

    Two smaller observations, neither a defect.  In
    `test_a_racing_unpack_is_recovered` the patched `Path.rename` never
    falls through to the genuine one, so the guard against patching too
    broadly is itself unexercised; the test wheel has no `.data` member
    to move.  And the `sys.path` cleanup helper never finds an entry to
    remove, because the tests that use it install in children.
  * 6.5.16 - Eighth traced round, overnight 2026-09-29 into the 30th, at
    Wayne's instruction to run everything and keep fixing until done:
    `ALT_VENV_TEST=COMPLETE`, `ALT_VENV_PYPI=1`, `--children`, and from
    the fourth pass `ALT_VENV_REPORT=1` as well.  Five traced passes of
    roughly twenty-five minutes each.  **`bootstrap.py` reached 100%**,
    `alt_venv.py` and `alt_venv_test.py` are at 99%, and 184 tests pass.

    What each pass found:

    * **First**: `alt_venv.py` had fallen to 97%, all of it the new
      garbage collection: seven `except OSError: continue` arms plus the
      confirmation's empty read.  The lesson for writing them was that
      **deterministic beats racy** -- a dangling symlink makes `stat`
      raise on demand, a directory named `something.json` makes `unlink`
      refuse, and `chmod 0o500` on `pending/` makes removal fail while
      the listing still works.  Only two arms needed `unittest.mock`:
      `Path.touch`, because `utime` succeeds for a file's owner whatever
      its mode, and `Path.lstat` in `directory_size`.
    * **Second**: 99% again, and `bootstrap.py` exposed as the real gap
      at 75% -- 98 lines, the measurement harness that runs only when the
      file is invoked with no arguments.
    * **Third**: three of its four functions are pure and quick, so they
      now have tests, and one of them is the test that was missing on
      2026-09-29: `test_the_recorded_table_matches_the_measurement`
      parses the table out of the module docstring and compares every
      counted column against `measure_source`.  Had it existed, the
      `paste` column being three lines short in every row since
      `SHARED_LINES` changed would have failed immediately instead of
      surviving for days.  85%.
    * **Fourth**: `run_tests` covered by an opt-in `ReportTest` behind
      `ALT_VENV_REPORT`, which runs the real report in 105 s, plus the
      usage branch, which needs neither network nor measurement.  99%,
      three lines left.
    * **Fifth**: those three were the path that names a case which
      *failed* during the report -- the report's most useful output.
      Covered by patching `subprocess.run` so all twelve cases fail
      instantly, which costs milliseconds where a broken index would
      cost minutes.  **100%.**

    One test got stronger rather than merely covered.  The tracer showed
    that in `test_unpack_survives_losing_the_race` the patched
    `Path.rename` never fell through to the genuine one, so its comment
    -- "only the staging rename fails; the `.data` moves must not" -- was
    a hope rather than a claim: the test wheel had no `.data` member to
    move.  It has one now, and the test records which renames were
    allowed through and asserts the member was among them.

    What remains uncovered, and why each one stays:

    * `alt_venv.py` line 495, the frozen interpreter arm of
      `repair_module_layout`.  `trace` decides what to follow by reading
      `frame.f_globals["__file__"]`, so a frame whose `__file__` is
      `None` is invisible to it: the line could execute and still be
      reported as unexecuted.  Unfixable from here.
    * Eleven lines of `alt_venv_test.py`, all configuration rather than
      code: `platform_tag`'s non-CPython branch, `cases()` returning
      `FAST_CASES` (covered by every fast run instead of this one), the
      openssl-missing skip, the server's unexpected-error handler, the
      two exits of the pty read loop where only one can be taken, the
      `sys.path` cleanup helper's loop body, and the file's own
      `__main__` entry.
