#!/usr/bin/env python3
"""Fourteen ways to get a package onto `sys.path` with nothing preinstalled.

Run it with no arguments: `python3 bootstrap.py`.  It runs every case
three times and prints the table below to standard output, so
`python3 bootstrap.py > test_results.txt` keeps a copy.  Progress goes
to standard error and stays out of the way of that redirect.  These
numbers are simply what that run produced here; rerunning it on
another machine is the point of the exercise.

Each case is a module level function named after it, `venv1` to
`nopip3`, and is one self-contained mechanism: it decides where the
packages live, installs `PACKAGE` there if it is missing, and imports
it.  Every import a case does not share with all the others is inside
that case, and the pip argument list is spelled out inside each case
rather than hoisted into a constant.  Neither is Pythonic.  Both are
deliberate: nothing outside a case is hidden from the count, so `paste`
below is honest.  A function rather than a `case` of one big `match`
since 2026-10-01, at Wayne's suggestion, so that a body sits only one
level deeper than it will in a program and looks the way it will look
there.  The docstring of each function is not pasted and not counted.

`sys.argv[1]` is internal.  It names one case, and exists only because
the harness has to run each case in a fresh interpreter -- in process,
`venv1`'s pip and its already imported `coverage` would contaminate
every case after it.  It is how this file invokes itself, not a way to
use it.  A program that pastes a case in keeps one case body and has
no `def` and no `sys.argv` at all, which is why neither the function's
`def` line and docstring nor `main()` is counted in `paste`, and
neither is the closing `print`.  Every other line in a
case is counted and is exactly the line a real program would carry --
`~/.alt_venv` is named in the code rather than passed in, so that
stays true.

`PACKAGE` is internal, and stopped being charged on 2026-09-29.  It
exists here so that `BOOTSTRAP_PACKAGE` can aim the cases at a locally
built wheel without editing a case body, and the `import os` that makes
that lookup possible is harness machinery in the same way.  A real
pasted program does not need the variable at all: it spells `alt_venv`
in the four places that use it, which costs no line, so charging a line
for the name overstated what a program actually carries.  `PACKAGE`,
`import os`, `sys.argv[1]` and the closing `print` are all excluded from
the count for that reason.

**Each case body is exactly what gets pasted**, `try` and all, as of
2026-10-01 at Wayne's direction.  A case opens with its comment and its
imports, which the person moves to the top of their program, and the
rest sits inside a `try` whose `except Exception` turns any failure into
one line on standard error and exit status 1.  Without it a missing
network is a traceback rather than a message, which is the `I.whwnn`
issue.  `Exception` rather than `BaseException`, so that a control-C
still reads as a control-C.  The `try` used to live once, at this file's
entry point, so that no case body had to be indented under it; moving
it into the bodies costs nothing in `paste`, which always charged it,
and means the text a person copies is the text that was measured.
`SHARED_LINES` is now just the three module level imports.

The message names a **stage** where a case sets one.  `nopip3` sets
its stage, `s`, before each step of its work -- `find home`, `choose
pip`, `download pip`, `install alt_venv`, `import alt_venv`, `fetch
packages`, two words at most -- and its `except` reports the stage that
was running, then the exception's `repr`, which carries its type as
well as its text: `alt_venv: choose pip failed: <HTTPError 404: 'Not
Found'>`.  The type matters because some exceptions have no text at
all: a bare `StopIteration` used to print `cannot fetch alt_venv: ` and
nothing more.  The other cases name no stage, report the type and text
alone, and begin `cannot fetch alt_venv`, which `nopip3` cannot say
since its last stage fetches the program's packages.  See issue
`I.fpfipe`.

The `paste` column was corrected twice on 2026-09-29: it had been left
at `lines + 4` from before the `try` was charged, and then dropped by
one again when `PACKAGE` stopped being charged.

`JSON_API` is the same arrangement for the same reason.  The three
`nopip` cases read PyPI's JSON API with `urllib`, which knows nothing of
`PIP_INDEX_URL`, so there is no environment variable already able to
steer them at a local server.  A pasted case carries the literal
`https://pypi.org/pypi`; here `BOOTSTRAP_JSON_API` can replace it.
The substitution costs a case no lines, so the `paste` column is
unchanged.

Measuring fourteen cases against one `~/.alt_venv` would be wrong: the
second case onwards would find `coverage` already on disk and report a
warm time as its cold time.  Each run therefore gets its own `HOME`,
which `pathlib.Path.home()` honours -- the isolation is in the
environment, where it belongs, and not in a line of code that no real
user would type.  The real `~/.alt_venv` is never touched.

+--------+---------------+---------+-------+-------+--------+--------+--------+
| case   | mechanism     | imports | lines | paste | cold   | warm   | size   |
+--------+---------------+---------+-------+-------+--------+--------+--------+
| venv1  | venv(pip),    | 4       | 23    | 26    | 6.12 s | 0.16 s | 16981  |
|        | pip in        |         |       |       |        |        |        |
|        | process       |         |       |       |        |        |        |
| venv2  | venv(pip),    | 4       | 23    | 26    | 6.68 s | 0.15 s | 16981  |
|        | pip           |         |       |       |        |        |        |
|        | subprocess    |         |       |       |        |        |        |
| venv3  | venv(pip),    | 5       | 29    | 32    | 6.85 s | 0.16 s | 1790   |
|        | then delete   |         |       |       |        |        |        |
|        | pip           |         |       |       |        |        |        |
| venv4  | as venv3 but  | 5       | 30    | 33    | 5.25 s | 0.15 s | 1790   |
|        | subprocess    |         |       |       |        |        |        |
| venv5  | venv(no pip), | 4       | 23    | 26    | 2.65 s | 0.15 s | 1790   |
|        | pip in proc   |         |       |       |        |        |        |
| pip1   | no venv, pip  | 1       | 14    | 17    | 2.65 s | 0.14 s | 1762   |
|        | in process    |         |       |       |        |        |        |
| pip2   | no venv, pip  | 1       | 14    | 17    | 2.73 s | 0.14 s | 1762   |
|        | subprocess    |         |       |       |        |        |        |
| pip3   | no venv, pip  | 2       | 19    | 22    | 4.22 s | 0.15 s | 1762   |
|        | from wheel    |         |       |       |        |        |        |
| pip4   | as pip1 plus  | 1       | 15    | 18    | 2.62 s | 0.14 s | 1698   |
|        | --no-compile  |         |       |       |        |        |        |
| pip5   | as pip2 plus  | 1       | 15    | 18    | 2.69 s | 0.14 s | 1698   |
|        | --no-compile  |         |       |       |        |        |        |
| nopip1 | no venv,      | 5       | 48    | 51    | 1.41 s | 0.15 s | 1682   |
|        | stdlib wheel  |         |       |       |        |        |        |
| nopip2 | venv(no pip), | 7       | 54    | 57    | 1.42 s | 0.16 s | 1714   |
|        | stdlib wheel  |         |       |       |        |        |        |
| nopip3 | no venv, PyPI | 4       | 28    | 31    | 3.05 s | 0.14 s | 3538   |
|        | pip           |         |       |       |        |        |        |
|        | subprocess    |         |       |       |        |        |        |
| nopip4 | as nopip3,    | 4       | 32    | 35    | --     | --     | --     |
|        | importable    |         |       |       |        |        |        |
|        | first         |         |       |       |        |        |        |
+--------+---------------+---------+-------+-------+--------+--------+--------+

What the columns mean, in the order they appear above:

* **case** -- the argument to pass on the command line, and the name of
  the function holding that case.  The name says what the case needs
  on the machine: `venv` cases create a virtual environment, `pip`
  cases run a pip the machine already has, and `nopip` cases need no
  pip at all.  The digit numbers a case within its group and is not a
  ranking, so adding or removing a case renames nothing else.

  Until 2026-10-01 the cases were numbered 1 to 13 in the order they
  were written, and the `History.md` files under `TASKS/` still use those
  numbers.  Old to new: 1 `venv1`, 2 `venv2`, 3 `nopip1`, 4 `venv3`,
  5 `venv5`, 6 `pip1`, 7 `pip2`, 8 `pip3`, 9 `pip4`, 10 `pip5`,
  11 `venv4`, 12 `nopip2`, 13 `nopip3`.

* **mechanism** -- a one-line summary, wrapped onto a second line where
  it does not fit.  `venv(pip)` means the venv was built with
  `with_pip=True`, `venv(no pip)` with `with_pip=False`, and `no venv`
  means no virtual environment is created at all.

* **imports** -- `import` statements inside that `case`, counting the
  `from pip._internal...` one.  It is a proxy for how much of the
  standard library, and how much of pip's unsupported interior, the
  mechanism has to reach into.  The spread is narrow (1 to 7) and it is
  the weakest of these columns; *which* modules are imported says more
  than how many.  Importing `venv` costs nothing by itself; asking it
  for pip, as `with_pip=True` does, is what drags in 15 MB.

* **lines** -- physical lines in the case's body, below its docstring,
  including the comment that opens it.  Blank lines do not occur; no
  case has any.

* **paste** -- **the number that matters.**  This bootstrap is not
  installed, it is copied by hand into the top of every program that
  wants it, so its real cost is how much text the author has to carry
  around.  It is `lines` plus the three shared lines every case needs:
  `import importlib`, `import pathlib` and `import sys`.  The `try`
  is inside `lines`, since each case carries its own.  `PACKAGE`, `JSON_API`
  and `import os` live above `main()` too, but are harness machinery
  and are not counted, and neither is the closing `print`.

* **cold** -- wall clock for the first run into an empty `HOME`: venv
  creation if any, the download, and the install.  Median of
  `REPETITIONS` runs, with `VIRTUAL_ENV` stripped from the environment
  so that an activated virtual environment cannot skew the result.
  Single runs varied by up to 15%, mostly on the network, which is why
  medians are reported rather than single measurements.

* **warm** -- wall clock for the second run, when the package is already
  on disk.  Median of `REPETITIONS` runs.  It is ~0.14 s for every case
  because all fourteen then do the same thing: one existence check, one
  `sys.path.insert`, and one import.  Cold cost is paid once per
  machine; warm cost is paid on every run of the program, forever.

* **size** -- kilobytes under `~/.alt_venv` afterwards, counting
  allocated blocks much as `du -sk` does, landing within about 3 KB of
  it in either direction.  Compare these against each other, not
  against `du`.  Kilobytes rather than
  megabytes because rounding to `1.7 MB` hid two real differences.
  The 16981 of `venv1` and `venv2` is the venv keeping its own copy of
  pip, ~15 MB of the total and never used again.  Among the rest: 1790
  carries an unused venv skeleton, 1762 adds pip's three generated
  `coverage` console scripts in `bin/`, and 1698 is `--no-compile`,
  worth only 60 KB -- 40 `.pyc` files against 44 -- because the
  bootstrap imports the package two lines later and Python compiles
  what it imports anyway.  `nopip1` is smallest at 1682 precisely
  because it never generates the console scripts, and `nopip2` is
  1714, which is `nopip1` plus 32 KB of empty venv.  `nopip3` is
  `pip2`'s 1762 plus the 1.8 MB `pip.whl` it keeps for `AltVEnv`.

The clusters: `pip1` and `pip2` are the floor at 17 pasted lines, with
`pip4` and `pip5` one above it, but all four need pip already present;
`venv3` and `venv4` manufacture a pip with `ensurepip`, use it once,
then delete it, for a machine that has `venv` but no pip; `nopip1` and
`nopip2` need neither, and cost 51 and 57 lines for it.  `nopip3` needs
neither as well, by fetching a pip of its own.

`venv3` and `venv4` are the same mechanism reached two ways, and they
differ by one line: 5 imports each, 32 and 33 pasted, 1790 KB each.
`venv3` imports the manufactured pip; `venv4` runs the venv's own
interpreter as a child instead.  `venv4` therefore reaches the middle
cluster without touching `pip._internal` at all, and costs one line for
the privilege.

Running pip in process is not free of the user's program.  After a
single in-process install, `sys.modules` grows from 99 entries to 740,
451 of them pip's, and pip leaves three `RichPipStreamHandler` objects
on the *root* logger.  A `log.warning("...")` in the user's program
prints bare before the bootstrap runs and `WARNING: ...` through pip's
handler afterwards.  Every in-process case (`venv1`, `venv3`, `venv5`,
`pip1`, `pip3`, `pip4`) does this; the subprocess cases (`venv2`,
`venv4`, `pip2`, `pip5`, `nopip3`) cannot, since that state dies with
the child process, and `nopip1` and `nopip2` cannot because they never
load pip at all.

`nopip2` exists to answer a question about the instructions rather than
to be shipped.  Those asked for a venv built with `venv`, no spawning
of `python3 -m pip install`, only `venv` and standard libraries, and
an `importlib` import.  `nopip2` is the only one of the fourteen that
does all four, and it costs 57 pasted lines against `nopip1`'s 51.  The
extra 6 lines and 32 KB buy a virtual environment that nothing then
reads, which is finding 3 of the log book arriving from yet another
direction.

`nopip3` shipped until 2026-10-10, when `nopip4` replaced it; see Step
6.15 and `T.ewar` of `TASKS/`.  It is
`pip2` with the one thing `pip2` assumes taken away.  Rather than run
the machine's pip, it fetches pip's own wheel from the JSON API, keeps
it as `~/.alt_venv/pip.whl`, and runs it as `python pip.whl/pip`, which
is how pip documents running itself without being installed.  `AltVEnv`
then uses that same copy, so nothing on the machine needs pip at all.
It is a subprocess case, so none of pip's state reaches the program,
and it costs 31 pasted lines against `pip2`'s 17.

It is also the one case **squeezed on purpose**, on 2026-10-01: a
bootstrap is meant to feel like magic, and a short one is pasted with
less hesitation.  The ugliness is kept inside the `try`.  There, names are
single letters, short statements on one topic share a line, `/` goes
without spaces, the downloads skip `with`, and the message uses `repr`.
Outside it, the imports are one to a line, in order, and named plainly
except for `urllib.request as req`, because the person moves them to the
top of their program, where many tools check exactly that.  That took it
from 41 pasted lines to 27, and checking the SHA-256 of the pip it
downloads, against the digest PyPI lists, then added three: `import
hashlib` and a two line `if` that raises.  On 2026-10-02 it took one
more, to call `AltVEnv().install()` itself, so that a program using it
never has to name `alt_venv` at all; Wayne: "The end-user should never
have to directly touch `AltVEnv`."  `ruff.toml` exempts this file
from the one rule the squeeze breaks, `E702`.  The comment on the choice
of pip went too, at Wayne's word, since this docstring explains it.  Not
squeezed: pip's `--no-input` and `--disable-pip-version-check`, which
change what pip does.  It fetches pip whenever `alt_venv` is missing,
even if an earlier run that failed before installing left a `pip.whl`
behind; skipping that rare download cost a whole level of indentation.
Paths go to `subprocess.run` as they are, and pip's `--target` is
spelled `-t`.  What comments it has sit at the ends of lines, where they
cost nothing.  Its lines are checked at the width they will have once
pasted, with the URL spelled out; the widest is 78.

Of its lines, the best spent set the stage, so that a failure says
where it happened, and choose which pip to fetch: not the newest, but
the newest upload whose `requires_python` floor this Python meets, so
that when pip drops a Python every bootstrap already pasted on that
Python keeps working.  Sorting by upload time rather than by version
avoids parsing version strings, and pip has written its floor as a
plain `>=3.N` since it dropped Python 2; an older or odder specifier is
simply passed over.  Against the real index that gives pip 24.0 on
3.7, 25.0.1 on 3.8 and 26.0.1 on 3.9, each the last release for its
Python.  See issue `I.bfnprp`.

`nopip4` is the one that ships, since 2026-10-10.  It is `nopip3` with
one question asked first: is `alt_venv` already importable?  Under
`uv run`, beside a working copy, or wherever an installer such as shiv
or PEX has already put it, `nopip3` fetched `pip` and `alt_venv`
regardless, and with no network it failed.  `nopip4` tries the import,
and only when that fails does `nopip3`'s work, unchanged.  It costs four
lines, 35 pasted: `m = None`, a one line `try` and `except`, and an `if`
around the import from `~/.alt_venv`.  The `m = None` is there for
`mypy`, which at module level, where a program pastes it, refuses `None`
assigned in the `except` to a name the `try` made a module.  The
harness runs every case with `python -P`, so that this directory, which
holds `alt_venv.py`, is not on the child's `sys.path`; otherwise
`nopip4` would import the working copy and measure nothing.  See
`T.ewar` and `I.apiia`.

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

import importlib
import os
import pathlib
import sys

# The package every case fetches.  See the docstring above: a pasted
# case carries a literal, while the harness steers this one instead.
PACKAGE: str = os.environ.get("BOOTSTRAP_PACKAGE", "coverage")

# Where the `nopip` cases look for the JSON API, steered the same way.
JSON_API: str = os.environ.get("BOOTSTRAP_JSON_API",
                               "https://pypi.org/pypi")


def venv1() -> None:
    """Venv(pip), pip in process.

    The body below this docstring is exactly what a program pastes, one
    level deeper than it will sit there; see the module docstring.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `alt_venv` is downloaded.
    import os
    import sysconfig
    import venv
    try:
        root = pathlib.Path.home() / ".alt_venv"
        if not (root / "pyvenv.cfg").exists():
            venv.EnvBuilder(with_pip=True, symlinks=(os.name != "nt")
                            ).create(root)
        target = pathlib.Path(sysconfig.get_path(
            "purelib", scheme="venv", vars={"base": str(root),
            "platbase": str(root), "installed_base": str(root)}))
        if not (target / PACKAGE).is_dir():
            from pip._internal.cli.main import main as pip_main
            if pip_main(["install", "--no-input", "--target", str(target),
                         "--disable-pip-version-check", PACKAGE]):
                raise RuntimeError("pip failed")
        sys.path.insert(0, str(target))
        importlib.invalidate_caches()
        module = importlib.import_module(PACKAGE)
    except Exception as error:
        raise SystemExit(f"cannot fetch {PACKAGE}: "
                         f"{type(error).__name__}: {error}") from None


def venv2() -> None:
    """Venv(pip), pip subprocess.

    The body below this docstring is exactly what a program pastes, one
    level deeper than it will sit there; see the module docstring.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `alt_venv` is downloaded.
    import os
    import subprocess
    import sysconfig
    import venv
    try:
        root = pathlib.Path.home() / ".alt_venv"
        if not (root / "pyvenv.cfg").exists():
            venv.EnvBuilder(with_pip=True, symlinks=(os.name != "nt")
                            ).create(root)
        target = pathlib.Path(sysconfig.get_path(
            "purelib", scheme="venv", vars={"base": str(root),
            "platbase": str(root), "installed_base": str(root)}))
        if not (target / PACKAGE).is_dir():
            subprocess.run([sys.executable, "-m", "pip", "install",
                            "--no-input", "--disable-pip-version-check",
                            "--target", str(target), PACKAGE], check=True)
        sys.path.insert(0, str(target))
        importlib.invalidate_caches()
        module = importlib.import_module(PACKAGE)
    except Exception as error:
        raise SystemExit(f"cannot fetch {PACKAGE}: "
                         f"{type(error).__name__}: {error}") from None


def venv3() -> None:
    """Venv(pip), then delete pip.

    The body below this docstring is exactly what a program pastes, one
    level deeper than it will sit there; see the module docstring.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `alt_venv` is downloaded.
    import os
    import shutil
    import sysconfig
    import venv
    try:
        root = pathlib.Path.home() / ".alt_venv"
        if not (root / "pyvenv.cfg").exists():
            venv.EnvBuilder(with_pip=True, symlinks=(os.name != "nt")
                            ).create(root)
        target = pathlib.Path(sysconfig.get_path(
            "purelib", scheme="venv", vars={"base": str(root),
            "platbase": str(root), "installed_base": str(root)}))
        sys.path.insert(0, str(target))
        if not (target / PACKAGE).is_dir():
            from pip._internal.cli.main import main as pip_main
            if pip_main(["install", "--no-input", "--target", str(target),
                         "--disable-pip-version-check", PACKAGE]):
                raise RuntimeError("pip failed")
            shutil.rmtree(target / "pip", ignore_errors=True)
            for leftover in target.glob("pip-*.dist-info"):
                shutil.rmtree(leftover)
            for leftover in (root / "bin").glob("pip*"):
                leftover.unlink()
        importlib.invalidate_caches()
        module = importlib.import_module(PACKAGE)
    except Exception as error:
        raise SystemExit(f"cannot fetch {PACKAGE}: "
                         f"{type(error).__name__}: {error}") from None


def venv4() -> None:
    """As venv3 but subprocess.

    The body below this docstring is exactly what a program pastes, one
    level deeper than it will sit there; see the module docstring.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `alt_venv` is downloaded.
    import os
    import shutil
    import subprocess
    import sysconfig
    import venv
    try:
        root = pathlib.Path.home() / ".alt_venv"
        if not (root / "pyvenv.cfg").exists():
            venv.EnvBuilder(with_pip=True, symlinks=(os.name != "nt")
                            ).create(root)
        target = pathlib.Path(sysconfig.get_path(
            "purelib", scheme="venv", vars={"base": str(root),
            "platbase": str(root), "installed_base": str(root)}))
        if not (target / PACKAGE).is_dir():
            subprocess.run([str(root / "bin" / "python3"), "-m", "pip",
                            "install", "--no-input",
                            "--disable-pip-version-check", "--target",
                            str(target), PACKAGE], check=True)
            shutil.rmtree(target / "pip", ignore_errors=True)
            for leftover in target.glob("pip-*.dist-info"):
                shutil.rmtree(leftover)
            for leftover in (root / "bin").glob("pip*"):
                leftover.unlink()
        sys.path.insert(0, str(target))
        importlib.invalidate_caches()
        module = importlib.import_module(PACKAGE)
    except Exception as error:
        raise SystemExit(f"cannot fetch {PACKAGE}: "
                         f"{type(error).__name__}: {error}") from None


def venv5() -> None:
    """Venv(no pip), pip in proc.

    The body below this docstring is exactly what a program pastes, one
    level deeper than it will sit there; see the module docstring.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `alt_venv` is downloaded.
    import os
    import sysconfig
    import venv
    try:
        root = pathlib.Path.home() / ".alt_venv"
        if not (root / "pyvenv.cfg").exists():
            venv.EnvBuilder(with_pip=False, symlinks=(os.name != "nt")
                            ).create(root)
        target = pathlib.Path(sysconfig.get_path(
            "purelib", scheme="venv", vars={"base": str(root),
            "platbase": str(root), "installed_base": str(root)}))
        if not (target / PACKAGE).is_dir():
            from pip._internal.cli.main import main as pip_main
            if pip_main(["install", "--no-input", "--target", str(target),
                         "--disable-pip-version-check", PACKAGE]):
                raise RuntimeError("pip failed")
        sys.path.insert(0, str(target))
        importlib.invalidate_caches()
        module = importlib.import_module(PACKAGE)
    except Exception as error:
        raise SystemExit(f"cannot fetch {PACKAGE}: "
                         f"{type(error).__name__}: {error}") from None


def pip1() -> None:
    """No venv, pip in process.

    The body below this docstring is exactly what a program pastes, one
    level deeper than it will sit there; see the module docstring.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `alt_venv` is downloaded.
    try:
        target = pathlib.Path.home() / ".alt_venv"
        if not (target / PACKAGE).is_dir():
            from pip._internal.cli.main import main as pip_main
            if pip_main(["install", "--no-input", "--target", str(target),
                         "--disable-pip-version-check", PACKAGE]):
                raise RuntimeError("pip failed")
        sys.path.insert(0, str(target))
        importlib.invalidate_caches()
        module = importlib.import_module(PACKAGE)
    except Exception as error:
        raise SystemExit(f"cannot fetch {PACKAGE}: "
                         f"{type(error).__name__}: {error}") from None


def pip2() -> None:
    """No venv, pip subprocess.

    The body below this docstring is exactly what a program pastes, one
    level deeper than it will sit there; see the module docstring.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `alt_venv` is downloaded.
    import subprocess
    try:
        target = pathlib.Path.home() / ".alt_venv"
        if not (target / PACKAGE).is_dir():
            subprocess.run([sys.executable, "-m", "pip", "install",
                            "--no-input", "--disable-pip-version-check",
                            "--target", str(target), PACKAGE], check=True)
        sys.path.insert(0, str(target))
        importlib.invalidate_caches()
        module = importlib.import_module(PACKAGE)
    except Exception as error:
        raise SystemExit(f"cannot fetch {PACKAGE}: "
                         f"{type(error).__name__}: {error}") from None


def pip3() -> None:
    """No venv, pip from wheel.

    The body below this docstring is exactly what a program pastes, one
    level deeper than it will sit there; see the module docstring.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `alt_venv` is downloaded.
    import ensurepip
    try:
        target = pathlib.Path.home() / ".alt_venv"
        if not (target / PACKAGE).is_dir():
            shipped = (ensurepip._WHEEL_PKG_DIR  # type: ignore
                       or pathlib.Path(ensurepip.__file__).parent / "_bundled")
            sys.path.insert(0, str(next(
                pathlib.Path(shipped).glob("pip-*.whl"))))
            from pip._internal.cli.main import main as pip_main
            if pip_main(["install", "--no-input", "--target", str(target),
                         "--disable-pip-version-check", PACKAGE]):
                raise RuntimeError("pip failed")
        sys.path.insert(0, str(target))
        importlib.invalidate_caches()
        module = importlib.import_module(PACKAGE)
    except Exception as error:
        raise SystemExit(f"cannot fetch {PACKAGE}: "
                         f"{type(error).__name__}: {error}") from None


def pip4() -> None:
    """As pip1 plus --no-compile.

    The body below this docstring is exactly what a program pastes, one
    level deeper than it will sit there; see the module docstring.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `alt_venv` is downloaded.
    try:
        target = pathlib.Path.home() / ".alt_venv"
        if not (target / PACKAGE).is_dir():
            from pip._internal.cli.main import main as pip_main
            if pip_main(["install", "--no-input",
                         "--no-compile", "--disable-pip-version-check",
                         "--target", str(target), PACKAGE]):
                raise RuntimeError("pip failed")
        sys.path.insert(0, str(target))
        importlib.invalidate_caches()
        module = importlib.import_module(PACKAGE)
    except Exception as error:
        raise SystemExit(f"cannot fetch {PACKAGE}: "
                         f"{type(error).__name__}: {error}") from None


def pip5() -> None:
    """As pip2 plus --no-compile.

    The body below this docstring is exactly what a program pastes, one
    level deeper than it will sit there; see the module docstring.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `alt_venv` is downloaded.
    import subprocess
    try:
        target = pathlib.Path.home() / ".alt_venv"
        if not (target / PACKAGE).is_dir():
            subprocess.run([sys.executable, "-m", "pip", "install",
                            "--no-input", "--no-compile",
                            "--disable-pip-version-check", "--target",
                            str(target), PACKAGE], check=True)
        sys.path.insert(0, str(target))
        importlib.invalidate_caches()
        module = importlib.import_module(PACKAGE)
    except Exception as error:
        raise SystemExit(f"cannot fetch {PACKAGE}: "
                         f"{type(error).__name__}: {error}") from None


def nopip1() -> None:
    """No venv, stdlib wheel.

    The body below this docstring is exactly what a program pastes, one
    level deeper than it will sit there; see the module docstring.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `alt_venv` is downloaded.
    import io
    import json
    import sysconfig
    import urllib.request
    import zipfile
    try:
        root = pathlib.Path.home() / ".alt_venv"
        target = root
        target.mkdir(parents=True, exist_ok=True)
        if not (target / PACKAGE).is_dir():
            with urllib.request.urlopen(f"{JSON_API}/{PACKAGE}/json",
                                        timeout=30) as r:
                metadata = json.load(r)
            impl = "cp" if sys.implementation.name == "cpython" else "py"
            pyver = f"{sys.version_info.major}{sys.version_info.minor}"
            machine = sysconfig.get_platform().split("-")[-1]
            chosen = None
            for tag in (f"{impl}{pyver}-{impl}{pyver}-",
                        f"{impl}{pyver}-abi3-", "py3-none-any"):
                for entry in metadata["urls"]:
                    name = entry["filename"]
                    if (name.endswith(".whl") and not entry.get("yanked")
                            and tag in name
                            and (name.endswith("-none-any.whl")
                                 or (machine in name and "linux" in name
                                     and sys.platform == "linux"))):
                        chosen = entry
                        break
                if chosen:
                    break
            if chosen is None:
                raise RuntimeError("no compatible wheel found")
            with urllib.request.urlopen(chosen["url"], timeout=60) as r:
                blob = r.read()
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                archive.extractall(target)
            for data_dir in target.glob("*.data"):
                for sub in ("purelib", "platlib"):
                    if (data_dir / sub).is_dir():
                        for item in (data_dir / sub).iterdir():
                            item.rename(target / item.name)
        sys.path.insert(0, str(target))
        importlib.invalidate_caches()
        module = importlib.import_module(PACKAGE)
    except Exception as error:
        raise SystemExit(f"cannot fetch {PACKAGE}: "
                         f"{type(error).__name__}: {error}") from None


def nopip2() -> None:
    """Venv(no pip), stdlib wheel.

    The body below this docstring is exactly what a program pastes, one
    level deeper than it will sit there; see the module docstring.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `alt_venv` is downloaded.
    import io
    import json
    import os
    import sysconfig
    import urllib.request
    import venv
    import zipfile
    try:
        root = pathlib.Path.home() / ".alt_venv"
        if not (root / "pyvenv.cfg").exists():
            venv.EnvBuilder(with_pip=False, symlinks=(os.name != "nt")
                            ).create(root)
        target = pathlib.Path(sysconfig.get_path(
            "purelib", scheme="venv", vars={"base": str(root),
            "platbase": str(root), "installed_base": str(root)}))
        if not (target / PACKAGE).is_dir():
            with urllib.request.urlopen(f"{JSON_API}/{PACKAGE}/json",
                                        timeout=30) as r:
                metadata = json.load(r)
            impl = "cp" if sys.implementation.name == "cpython" else "py"
            pyver = f"{sys.version_info.major}{sys.version_info.minor}"
            machine = sysconfig.get_platform().split("-")[-1]
            chosen = None
            for tag in (f"{impl}{pyver}-{impl}{pyver}-",
                        f"{impl}{pyver}-abi3-", "py3-none-any"):
                for entry in metadata["urls"]:
                    name = entry["filename"]
                    if (name.endswith(".whl") and not entry.get("yanked")
                            and tag in name
                            and (name.endswith("-none-any.whl")
                                 or (machine in name and "linux" in name
                                     and sys.platform == "linux"))):
                        chosen = entry
                        break
                if chosen:
                    break
            if chosen is None:
                raise RuntimeError("no compatible wheel found")
            with urllib.request.urlopen(chosen["url"], timeout=60) as r:
                blob = r.read()
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                archive.extractall(target)
            for data_dir in target.glob("*.data"):
                for sub in ("purelib", "platlib"):
                    if (data_dir / sub).is_dir():
                        for item in (data_dir / sub).iterdir():
                            item.rename(target / item.name)
        sys.path.insert(0, str(target))
        importlib.invalidate_caches()
        module = importlib.import_module(PACKAGE)
    except Exception as error:
        raise SystemExit(f"cannot fetch {PACKAGE}: "
                         f"{type(error).__name__}: {error}") from None


def nopip3() -> None:
    """No venv, PyPI pip subprocess.

    The body below this docstring is exactly what a program pastes, one
    level deeper than it will sit there; see the module docstring.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `alt_venv` is downloaded.
    import hashlib
    import json
    import subprocess
    import urllib.request as req
    try:
        s = "find home"; t = pathlib.Path.home()/".alt_venv"; w = t/"pip.whl"
        if not (t/PACKAGE).is_dir():  # Not installed yet.
            s = "choose pip"; v = sys.version_info[1]
            d = json.load(req.urlopen(f"{JSON_API}/pip/json", None, 30))
            e = max((e for f in d["releases"].values() for e in f  # Newest pip
                     if e["url"][-4:] == ".whl" and not e["yanked"]
                     and (q := e["requires_python"] or "")[:4] == ">=3."
                     and "," not in q and int(q.split(".")[1]) <= v),
                    key=lambda e: e["upload_time"])  # whose floor we meet.
            s = "download pip"; r = req.urlopen(e["url"], None, 60).read()
            if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
                raise ValueError(f"{e['filename']} fails its SHA-256 check")
            t.mkdir(parents=True, exist_ok=True); p = t/"pip.part"
            p.write_bytes(r); p.replace(w)  # The rename is atomic.
            s = f"install {PACKAGE}"; subprocess.run([
                sys.executable, w/"pip", "install", "--no-input", "-t", t,
                "--disable-pip-version-check", PACKAGE], check=True)
        s = f"import {PACKAGE}"; sys.path.insert(0, str(t))
        importlib.invalidate_caches(); m = importlib.import_module(PACKAGE)
        s = "fetch packages"; m.AltVEnv().install(bootstrap="nopip3")
    except Exception as x:
        raise SystemExit(f"{PACKAGE}: {s} failed: {x!r}")


def nopip4() -> None:
    """As nopip3, but first use an `alt_venv` that is already importable.

    `nopip3` asks only whether `~/.alt_venv` holds `alt_venv`, so under
    `uv run`, or beside a working copy, it fetches `pip` and `alt_venv`
    that are already on `sys.path`, and fails with no network.  This case
    tries the import first and falls back to `nopip3` unchanged.  See
    `T.ewar` and `I.apiia`.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `alt_venv` is downloaded.
    import hashlib
    import json
    import subprocess
    import urllib.request as req
    try:
        s = "find home"; t = pathlib.Path.home()/".alt_venv"; w = t/"pip.whl"
        m = None
        try: m = importlib.import_module(PACKAGE)  # Already importable?
        except ImportError: pass
        if m is None and not (t/PACKAGE).is_dir():  # Not installed yet.
            s = "choose pip"; v = sys.version_info[1]
            d = json.load(req.urlopen(f"{JSON_API}/pip/json", None, 30))
            e = max((e for f in d["releases"].values() for e in f  # Newest pip
                     if e["url"][-4:] == ".whl" and not e["yanked"]
                     and (q := e["requires_python"] or "")[:4] == ">=3."
                     and "," not in q and int(q.split(".")[1]) <= v),
                    key=lambda e: e["upload_time"])  # whose floor we meet.
            s = "download pip"; r = req.urlopen(e["url"], None, 60).read()
            if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
                raise ValueError(f"{e['filename']} fails its SHA-256 check")
            t.mkdir(parents=True, exist_ok=True); p = t/"pip.part"
            p.write_bytes(r); p.replace(w)  # The rename is atomic.
            s = f"install {PACKAGE}"; subprocess.run([
                sys.executable, w/"pip", "install", "--no-input", "-t", t,
                "--disable-pip-version-check", PACKAGE], check=True)
        if m is None:
            s = f"import {PACKAGE}"; sys.path.insert(0, str(t))
            importlib.invalidate_caches(); m = importlib.import_module(PACKAGE)
        s = "fetch packages"; m.AltVEnv().install(bootstrap="nopip4")
    except Exception as x:
        raise SystemExit(f"{PACKAGE}: {s} failed: {x!r}")


def main() -> None:
    """Run the single bootstrap mechanism named by `sys.argv[1]`.

    This is how `run_tests` invokes one case in a fresh interpreter.
    It is internal, and not a supported way to use this file; see the
    module docstring above.  The case is the module level function of
    that name, and the package it imported is read back out of
    `sys.modules`, because a case's own last line binds `module` for
    the program it is pasted into rather than for this one.

    Raises:
    * `SystemExit`:
      If the case fails, with the one line its `except` wrote.
    """
    mechanism = sys.argv[1]
    globals()[mechanism]()
    module = sys.modules[PACKAGE]

    # `type(sys)` is `types.ModuleType`, reached without importing
    # `types`, because `sys` is a module and is already imported.
    assert isinstance(module, type(sys)), f"{PACKAGE} gave {module!r}"

    # A real program constructs one next and calls `install()` -- the
    # shipping case does so itself, and a second call is harmless -- and
    # neither is idle here: the constructor repairs a single module
    # install so that this case's own `is_dir()` guard recognises it on
    # the following run, and `install()` walks the declared path in every
    # one of the fourteen shapes, virtual environments included.  This
    # file has no PEP 723 block, so nothing is fetched.  See `I.cctfd` and Step
    # 6.7.8.  Harness machinery, so `paste` does not count it.
    if hasattr(module, "AltVEnv"):
        module.AltVEnv().install(bootstrap=sys.argv[1])

    print(f"{PACKAGE}: module {module.__name__} "
          f"version {module.__version__} from {module.__file__}")


MECHANISMS = {
    "venv1": "venv(pip), pip in process",
    "venv2": "venv(pip), pip subprocess",
    "venv3": "venv(pip), then delete pip",
    "venv4": "as venv3 but subprocess",
    "venv5": "venv(no pip), pip in proc",
    "pip1": "no venv, pip in process",
    "pip2": "no venv, pip subprocess",
    "pip3": "no venv, pip from wheel",
    "pip4": "as pip1 plus --no-compile",
    "pip5": "as pip2 plus --no-compile",
    "nopip1": "no venv, stdlib wheel",
    "nopip2": "venv(no pip), stdlib wheel",
    "nopip3": "no venv, PyPI pip subprocess",
    "nopip4": "as nopip3, importable first",
}
# Lines a case needs but does not contain: the three module level
# imports.  This is the difference between `lines` and `paste`.
SHARED_LINES = 3
REPETITIONS = 3
COLUMNS = ["case", "mechanism", "imports", "lines", "paste", "cold",
           "warm", "size"]
COLUMN_WIDTHS = [6, 0, 7, 5, 5, 6, 6, 6]    # 0 means "use what is left".
TABLE_WIDTH = 79


def measure_source() -> dict[str, tuple[int, int]]:
    """Count the imports and lines of every case by parsing this file.

    The counts come from the source itself rather than from a table
    maintained by hand, so they cannot drift when a case is edited.
    Each case is the function of the same name, and its docstring is
    not counted, since nobody pastes it.  The comment line that opens
    each body is counted, because it is a line the user has to paste
    too.

    Returns:
    * (`dict[str, tuple[int, int]]`):
      Maps each case label to its number of `import` statements and
      its number of lines.
    """
    import ast
    tree = ast.parse(pathlib.Path(__file__).read_text())
    counts: dict[str, tuple[int, int]] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in MECHANISMS:
            code = node.body[1:]       # Past the docstring.
            first = code[0].lineno
            last = code[-1].end_lineno or first
            counts[node.name] = (
                sum(1 for n in ast.walk(node)
                    if isinstance(n, (ast.Import, ast.ImportFrom))),
                last - first + 2)      # +2 picks up the comment line.
    return counts


def pasted(label: str) -> str:
    """Return a case exactly as a person pastes it into their program.

    The function's body below its docstring, one level shallower, with
    the two names that exist only so the harness can be steered spelled
    out the way a pasted copy carries them: `PACKAGE` as `"alt_venv"`
    and `JSON_API` as `https://pypi.org/pypi`.  An f-string left with
    nothing to substitute becomes a plain string, as it would be
    written by hand.  This is the text Step 6.12 fingerprints, and the
    text a `README.md` can quote.

    Arguments:
    * `label` (`str`):
      The case, such as `nopip3`.

    Returns:
    * (`str`): The pasted text, ending in a newline.
    """
    import ast
    import re
    import textwrap
    source = pathlib.Path(__file__).read_text()
    node = next(n for n in ast.parse(source).body
                if isinstance(n, ast.FunctionDef) and n.name == label)
    lines = source.splitlines()[node.body[1].lineno - 2:node.end_lineno]
    text = textwrap.dedent("\n".join(lines)) + "\n"
    text = text.replace("{JSON_API}", "https://pypi.org/pypi")
    text = text.replace("{PACKAGE}", "alt_venv")
    text = re.sub(r"\bPACKAGE\b", '"alt_venv"', text)
    return re.sub(r'\bf"([^"{}]*)"', r'"\1"', text)


def directory_size(path: pathlib.Path) -> int:
    """Measure the disk space used by a directory tree.

    Allocated blocks are counted rather than apparent file sizes, which
    is how `du -sk` counts, and symbolic links are not followed.  Block
    counts are unavailable on some platforms, and file sizes are used
    there instead.  The result lands within about 3 KB of `du -sk`, in
    either direction; the entry for `path` itself is not counted here,
    and rounding differs.  Use these figures against each other and not
    against `du`.

    Arguments:
    * `path` (`pathlib.Path`):
      Root of the tree to measure.  A missing directory measures zero.

    Returns:
    * (`int`): Kilobytes of disk used by the tree.
    """
    import os
    total = 0
    for parent, directories, files in os.walk(path):
        for name in directories + files:
            try:
                status = (pathlib.Path(parent) / name).lstat()
            except OSError:
                continue
            blocks = getattr(status, "st_blocks", None)
            total += blocks * 512 if blocks else status.st_size
    return total // 1024


def format_table(rows: list[list]) -> str:
    """Render measurement rows as a fixed width ASCII table.

    The `mechanism` column is given whatever width the other columns
    leave over, and its text wraps onto additional lines when it does
    not fit.  Those continuation lines repeat nothing but the wrapped
    text, so each case still reads as one row.

    Arguments:
    * `rows` (`list[list]`):
      One list per case, holding the eight column values in the order
      named by `COLUMNS`.

    Returns:
    * (`str`):
      The table, newline separated and without a trailing newline.
      Every line is exactly `TABLE_WIDTH` characters long.
    """
    import textwrap
    widths = list(COLUMN_WIDTHS)
    widths[1] = TABLE_WIDTH - 1 - 3 * len(COLUMNS) - sum(widths)
    rule = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    def line(cells: list) -> str:
        """Render one row of `cells`, padded to the column widths.

        Arguments:
        * `cells` (`list`):
          One value per column, in the order named by `COLUMNS`.

        Returns:
        * (`str`): The row, bracketed and separated by `|`.
        """
        return ("| " + " | ".join(str(c).ljust(w)
                                  for c, w in zip(cells, widths)) + " |")

    out = [rule, line(COLUMNS), rule]
    for row in rows:
        wrapped = textwrap.wrap(str(row[1]), widths[1]) or [""]
        out.append(line([row[0], wrapped[0], *row[2:]]))
        out += [line(["", extra, "", "", "", "", "", ""])
                for extra in wrapped[1:]]
    out.append(rule)
    return "\n".join(out)


def run_tests() -> None:
    """Run every case in a throwaway `HOME` and print the report.

    Each case installs into `~/.alt_venv`, so every run is given
    its own temporary `HOME`, which `pathlib.Path.home()` honours.
    Without that, the second case onwards would find the package
    already on disk and report a warm time as its cold time.  The real
    `~/.alt_venv` is never touched, and each temporary tree is
    removed once it has been measured.

    Every case is run `REPETITIONS` times, cold and then warm, and the
    medians are reported.  The report is written to standard output and
    the per case progress to standard error, so that redirecting
    standard output captures the report by itself.
    """
    import datetime
    import os
    import shutil
    import statistics
    import subprocess
    import tempfile
    import time

    counts = measure_source()
    base = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    script = str(pathlib.Path(__file__).resolve())
    rows, failures = [], []

    for label, description in MECHANISMS.items():
        colds: list[float] = []
        warms: list[float] = []
        size = 0
        for repetition in range(REPETITIONS):
            home = tempfile.mkdtemp(prefix=f"bootstrap-{label}-")
            environment = dict(base, HOME=home)
            for samples in (colds, warms):
                start = time.perf_counter()
                done = subprocess.run([sys.executable, "-P", script, label],
                                      env=environment, capture_output=True,
                                      text=True, check=False)
                samples.append(time.perf_counter() - start)
                if done.returncode or PACKAGE not in done.stdout:
                    failures.append((label, done.stderr.strip()[-300:]))
            if repetition == 0:
                size = directory_size(pathlib.Path(home) / ".alt_venv")
            shutil.rmtree(home, ignore_errors=True)
        cold, warm = statistics.median(colds), statistics.median(warms)
        imports, lines = counts[label]
        rows.append([label, description, imports, lines, lines + SHARED_LINES,
                     f"{cold:.2f} s", f"{warm:.2f} s", size])
        print(f"case {label:>2}: cold {cold:5.2f} s   warm {warm:5.2f} s"
              f"   size {size:>6} KB   {description}", file=sys.stderr)

    now = datetime.datetime.now(datetime.UTC).astimezone()
    report = [
        "Results of `python3 bootstrap.py`.  Column meanings are in the",
        "module docstring of bootstrap.py.",
        "",
        f"date        : {now:%Y-%m-%d %H:%M}",
        f"python      : {sys.version.split()[0]} at {sys.executable}",
        f"platform    : {sys.platform}",
        f"inside venv : {sys.prefix != sys.base_prefix}",
        f"package     : {PACKAGE}",
        f"repetitions : {REPETITIONS}; cold and warm are medians",
        "",
        format_table(rows),
        "",
    ]
    if failures:
        report.append(f"{len(failures)} FAILURES:")
        report += [f"  case {label}: {message}" for label, message in failures]
    else:
        report.append("All cases succeeded.")

    print("\n".join(report))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        run_tests()
    elif sys.argv[1] in MECHANISMS:
        main()                      # internal: one case, one interpreter
    else:
        sys.exit(f"usage: {sys.argv[0]}          (takes no arguments)")
