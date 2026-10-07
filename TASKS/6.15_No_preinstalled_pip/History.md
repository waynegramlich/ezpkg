# 6.15 No preinstalled `pip`: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.15 of `LOGBOOK.md` on 2026-10-04.

* Step 6.15: No preinstalled `pip`.  Step 6.14.1 chose case 7 and named
  its cost: `pip` must be installed, and Debian and Ubuntu ship
  `python3-pip` separately.  The `README.md` rewrite needed to know
  whether that cost is real, and so whether the claim could be that
  Python and the pasted bootstrap are all a machine needs.
  * 6.15.1 - Three experiments, 2026-10-01, each fetching `pip`'s own
    wheel from the JSON API and installing with it, run on an
    interpreter made by `venv --without-pip` so that no `pip` could
    help.  All three worked against the real PyPI.  The two that ran
    `pip` in process, one from a temporary file and one straight out of
    memory through a hand-written importer, each printed forty
    `DEPRECATION: Unexpected import ... after pip install started`
    warnings.  `pip` 26 objects to a program importing, in the same
    process, what `pip` just installed, and says 26.3 will enforce it.
    That is the in-process argument of 6.14.1 again, made this time by
    `pip`.  Both were dropped, and the subprocess one became case 13.
  * 6.15.2 - **`alt_venv` needed `pip` as well.**  `AltVEnv.download`
    ran `python -m pip download`, so a bootstrap free of `pip` only
    moved the failure to the program's first declared dependency.  The
    answer is a private copy.  Case 13 keeps the wheel it fetched as
    `~/.alt_venv/pip.whl`, and `AltVEnv.pip` runs it as
    `python pip.whl/pip`, which is how `pip` documents running itself
    without being installed.  With no stash, which is every other case,
    it falls back to `python -m pip` as before.
  * 6.15.3 - Measured with the harness: 3 imports, 25 lines, 31 pasted,
    3.11 s cold, 0.14 s warm, 3538 KB, of which 1.8 MB is `pip.whl`.
    Against case 7 that is 15 more pasted lines and a 1.8 MB download
    on the first run only.
  * 6.15.4 - Verified 2026-10-01 on Linux under CPython 3.12.3 and
    3.11.16, each with no `pip`: case 13 against the real PyPI, and
    `test_nothing_but_python_and_the_bootstrap`, which runs case 13 and
    then a program declaring a dependency, against the local index.
    The 3.11 interpreter came from `uv python install 3.11`.  That run
    is a one-off rather than part of the suite: the floor is 3.11 only
    because `tomllib` arrived in it, and nothing in this change is
    expected to break there.  To repeat it, run the suite's two
    private-`pip` tests,
    `InstallTest.test_pip_prefers_the_private_copy` and
    `InstallTest.test_nothing_but_python_and_the_bootstrap`, under
    `~/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu/bin/python3.11`.
  * 6.15.5 - The suite never reaches the network, so every index that
    `build_index` makes now publishes a `pip` wheel as well, zipped by
    `pip_wheel` from the `pip` running the suite.  That works only for
    a `pip` carrying its vendored libraries; a debundled one cannot run
    alone, and the no-`pip` test skips.
  * 6.15.6 - **Case 13 ships**, 2026-10-01.  Wayne's words: "If the
    bootstrap grows some to eliminate the pip preinstalled issue I'm
    probably good with that."  The claim the `README.md` can make is
    Python 3.11 or later, the pasted bootstrap and a network that
    reaches PyPI.  `FAST_CASES` became `("13",)`.  Still open: `I.bfnprp`,
    `I.btosc`, `I.fpfipe` and `I.spinu`, and Windows and macOS are untried,
    which is `I.hmmdrpe`.

  * 6.15.7 - **The paste grew to 43 lines, on purpose**, 2026-10-01.
    Two changes to `nopip3`, both in code nobody can fix once pasted.
    It now fetches not the newest `pip` but the newest **upload** whose
    `requires_python` floor this Python meets, which closes `I.bfnprp`:
    when `pip` drops a Python, that Python keeps getting the last `pip`
    that supported it.  Against the real index, simulated: 3.7 gets
    24.0, 3.8 gets 25.0.1, 3.9 gets 26.0.1, 3.10 to 3.12 get 26.2.1.
    Sorting by upload time avoids parsing versions, and `pip` has
    written its floor as a plain `>=3.N` since it dropped Python 2.
    Pinning a version was considered and declined: a pinned `pip` is
    frozen into every pasted copy, and `pip` releases before 23.2 crash
    on Python 3.12, so a 2022 paste pinning 22.x would fail today.

    And it sets a `stage` before each step, which the `try` wrapper
    reports with the exception's type and text, at Wayne's suggestion,
    in two words at most at his request: `cannot fetch alt_venv, choose
    pip failed: HTTPError: ...`.  The wrapper's `raise` no longer fits
    one line, so `SHARED_LINES` became 7 and every case's `paste` rose
    by one.  Cold
    time is unchanged at 3.05 s; `pip`'s whole release list is 228 KB.
    Two tests: a 404 for `pip`'s page names the first stage, and of
    three stand-in `pip` releases the one whose floor is exactly this
    Python is chosen over a newer one that wants a later Python.  The
    local index now serves `releases`, with each file's floor read from
    its own `METADATA` and its upload time from the file.

  * 6.15.8 - **Each case body is exactly what gets pasted**, 2026-10-01,
    at Wayne's direction: "The code is supposed to be exactly what is
    pasted into the user's code."  The `try` had lived once, at the
    entry point of `bootstrap.py`, so that no body had to be indented
    under it, which meant the text a person copied was not the text in
    the file.  Now every case opens with its comment and its imports,
    which the person moves to the top of their program, and wraps the
    rest in its own `try`; the entry point wraps nothing, `stage` needs
    no `global`, and `SHARED_LINES` is just the three module level
    imports.  The deeper indentation pushed eighteen lines past 79
    columns, and re-wrapping them added a line to some cases, so the
    figures moved once more: `nopip3` is 44 pasted, `pip2` 18.  A
    comment on the selection, at Wayne's request, made `nopip3` 45.  `ruff`'s
    `BLE001` objected to every `except Exception`; the exemption went
    into `ruff.toml` rather than into a `noqa` comment that would be
    pasted along with the code.  All thirteen cases were run against
    the real PyPI afterwards, and a dead network reads `cannot fetch
    coverage, choose pip failed: URLError: <urlopen error [Errno 111]
    Connection refused>`.

  * 6.15.9 - **Each case is its own function**, 2026-10-01, at Wayne's
    suggestion, for a better view of what is pasted: `def nopip3():` and
    so on, in place of thirteen `case` clauses of one `match` in
    `main()`.  A body now sits one level, four spaces, deeper than it
    will in a program, where it sat three levels deeper before.  Each
    function's docstring is not pasted and not counted; `main()` calls
    the function named on its command line and reads the module back
    from `sys.modules`, since a case's last line binds `module` for the
    program it lands in.  `ruff` took that binding for an unused
    variable (`F841`), and its exemption joined `BLE001`'s in
    `ruff.toml`.  No count changed.  `measure_source` and
    `case_bodies` now read the functions rather than the `match`.

  * 6.15.10 - **Reflowed to the function depth**, 2026-10-01.  Lines
    wrapped for the old depth were rejoined wherever they now fit, by
    explicit before and after blocks, with each function's syntax tree
    compared before and after so that only whitespace could move.  The
    comparison caught one real change: re-wrapping for 6.15.8 had
    swapped `--target` and `--disable-pip-version-check` in `venv2` and
    `pip2`, which pip does not mind but which nobody had asked for, and
    this put back the order of revision 394.  Every case shrank:
    `nopip3` is 41 pasted lines, `pip2` 17, `nopip1` 51.  `venv4`,
    `pip4` and `pip5` keep calls that cannot lose a line at this depth.

  * 6.15.11 - **`nopip3` squeezed to 28 pasted lines**, from 41, on
    2026-10-01.  Wayne: "Squeezing the bootstrap down to few lines will
    make people less hesitant to use it.  It is meant to be 'magic'."
    Single letter names, short statements sharing a line, one import
    line, `/` without spaces, no `with` around the downloads, PyPI's
    shorter `upload_time`, and `repr` in the message, which carries the
    exception's type and so freed the `raise`'s second line.  `from
    None` went too, since `SystemExit` never prints a traceback.  Only
    `nopip3`; the other twelve are untouched.  `ruff.toml` now exempts
    `bootstrap.py` from `E401`, `E702` and `I001` as well.

    Three things nearly slipped through.  A first pass swapped pip's
    `--no-input` and `--disable-pip-version-check` for `-q`, which is
    the `--quiet` that 6.17.7 removed because it hides pip's diagnosis
    of a bad certificate; put back.  `t.mkdir(exist_ok=True)` dropped
    `parents=True`, and the no-`pip` test caught it.  And a harness
    name is shorter than what a paste carries: `JSON_API` becomes
    `https://pypi.org/pypi`, so pasted widths are checked separately,
    four columns shallower with the literals spelled out, and the widest
    is exactly 79.  Run against the real PyPI on 3.12 and 3.11 without
    `pip`, cold and warm.

  * 6.15.12 - **Imports one to a line again**, 2026-10-01, at Wayne's
    request: the combined `import json as j, subprocess, urllib.request
    as u` was too un-Pythonic, and the person moves a case's imports to
    the top of their program, where many tools insist on one import to
    a line and sort them.  Semicolons stay, but only between statements
    on one topic, which Wayne finds tools tolerate.  Then, keeping the
    ugliness inside the `try`, `json` lost its alias and
    `urllib.request` became `req`; the longer names cost one line, the
    fetch of `pip`'s release list split in two, since a timeout is not
    worth giving up to save it.  The comment on the choice of `pip`
    then went, at Wayne's word, the docstring explaining it instead.
    `nopip3` is 30 pasted lines, and
    `ruff.toml` exempts `E702` alone of the three squeeze rules.

  * 6.15.13 - **One `if` fewer**, 2026-10-01, from Wayne's suggestion
    to merge the two nested tests with `and`.  Merged literally, a
    machine holding `pip.whl` but not `alt_venv` would skip the install
    and fail at the import, so instead the inner test went: whenever
    `alt_venv` is missing, `pip` is fetched and `alt_venv` installed.
    The cost is a second 1.8 MB download in the rare case an earlier
    run failed between the two.  The level of indentation it freed let
    the fetch of `pip`'s release list rejoin one line, with both
    timeouts passed positionally to fit once pasted.  `nopip3` is 28
    pasted lines; the widest, pasted, is 78.

  * 6.15.14 - **The install on fewer lines, and comments at line ends**,
    2026-10-01, at Wayne's suggestion and the last squeeze for a while.
    The stage and its `subprocess.run` share a line, which needed paths
    passed as they are rather than through `str`, pip's `-t` for
    `--target`, and the argument list opened on its own line.  Wayne:
    a comment may sit in the space at the end of a line, so long as the
    line stays within 79 columns; four do now, costing nothing.
    `nopip3` is 27 pasted lines.

  * 6.15.15 - **`pip`'s SHA-256 is checked**, 2026-10-01, closing
    `I.fpfipe`.  The digest PyPI lists for the file is compared with the
    bytes before anything is written, so a damaged download fails as
    `download pip failed: ValueError('pip-...whl fails its SHA-256
    check')` and leaves no `pip.whl` behind to fail confusingly on every
    later run.  Three lines: `import hashlib` and a two line `if`, which
    made `nopip3` 30 pasted lines.  The local index serves
    `digests` now, and a new test truncates every wheel in flight; with
    the check taken out, that test fails.

  * 6.15.16 - **The private `pip` keeps itself current**, 2026-10-01,
    closing `I.spinu`.  `AltVEnv.refresh_pip` runs from `provide`, beside
    the cull, so only when something is about to be fetched anyway, and
    at most weekly by a `last_pip` stamp, as `pip` checks itself.  It
    asks the current private `pip` to download `pip`; `pip` passes over
    releases this Python cannot run, so what arrives is the newest it
    can.  A new version is added **beside** `pip.whl`, as
    `pip-<version>-...whl`, never over it: a running `pip` reads itself
    out of its wheel by offset as it goes, so replacing the file under
    it would break it.  `pip()` takes the most recently added copy.
    Superseded copies are removed after a day's grace; `pip.whl` is
    kept, for the bootstrap.  Failure of any kind is silent and waits a
    week, since the stamp is written before trying.  A cache with no
    private `pip` is left alone.  Five tests, among them a stand-in
    `pip` 99.0 being added and a dead index changing nothing; with the
    version comparison disabled, the up-to-date test fails.
  * 6.15.17 - **The bootstrap calls `install()` itself**, 2026-10-02,
    31 pasted lines.  Every case had ended at importing `alt_venv`,
    leaving `install()` to `bootstrap.py`'s epilogue, so when
    `README.md`'s example moved to `nopip3` it grew `import alt_venv`
    and `alt_venv.AltVEnv().install()` below the bootstrap, and Wayne
    asked why a program should mention `alt_venv` at all.  Wayne: "The
    end-user should never have to directly touch `AltVEnv`."  The last
    stage is now `fetch packages`, calling
    `AltVEnv().install(bootstrap="nopip3")`; the label is read by
    nothing, but Wayne wants it.  Failures there -- a package that will
    not download, or `n` at the prompt -- now end in the bootstrap's one
    line instead of a traceback, and the message became `alt_venv:
    <stage> failed: <repr>`, since "cannot fetch alt_venv" would be
    wrong for them.  The other twelve cases keep their wording, and
    `test_a_failed_fetch_is_one_line` accepts either.  The fingerprint
    entry of 2026-10-01 was replaced rather than kept, because it was
    never published.
