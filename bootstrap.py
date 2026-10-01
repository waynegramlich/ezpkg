#!/usr/bin/env python3
"""Thirteen ways to get a package onto `sys.path` with nothing preinstalled.

Run it with no arguments: `python3 bootstrap.py`.  It runs every case
three times and prints the table below to standard output, so
`python3 bootstrap.py > test_results.txt` keeps a copy.  Progress goes
to standard error and stays out of the way of that redirect.  These
numbers are simply what that run produced here; rerunning it on
another machine is the point of the exercise.

Each `case` in `main()` is one self-contained mechanism: it decides
where the packages live, installs `PACKAGE` there if it is missing,
and imports it.  Every import a case does not share with all the
others is inside that case, and the pip argument list is spelled out
inside each case rather than hoisted into a constant.  Neither is
Pythonic.  Both are deliberate: nothing above `main()` is hidden from
the count, so `paste` below is honest.

`sys.argv[1]` is internal.  It names one case, and exists only because
the harness has to run each case in a fresh interpreter -- in process,
case 1's pip and its already imported `coverage` would contaminate
every case after it.  It is how this file invokes itself, not a way to
use it.  A program that pastes a case in keeps one case body and has
no `match` and no `sys.argv` at all, which is why neither
`mechanism = sys.argv[1]` nor `match mechanism:` is counted in
`paste`, and neither is the closing `print`.  Every other line in a
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

The `try` wrapper is the one piece of harness machinery that `paste`
does charge, because a pasted case really does carry it.  Here it sits
at the entry point so that no case body has to be re-indented, but a
program with one case pasted into it spells the same three lines around
that case: `try:`, `except Exception as error:`, and the `raise
SystemExit`.  Without it a missing network is a traceback rather than a
message, which is the `0whwnn` issue.  Those three lines, plus the three
module level imports, are the whole of `SHARED_LINES`, which is 6.  The
`paste` column below was corrected twice on 2026-09-29: it had been left
at `lines + 4` from before the wrapper was charged, and then dropped by
one again when `PACKAGE` stopped being charged.

`JSON_API` is the same arrangement for the same reason.  Cases 3, 12
and 13 read PyPI's JSON API with `urllib`, which knows nothing of
`PIP_INDEX_URL`, so there is no environment variable already able to
steer them at a local server.  A pasted case carries the literal
`https://pypi.org/pypi`; here `BOOTSTRAP_JSON_API` can replace it.
The substitution costs a case no lines, so the `paste` column is
unchanged.

Measuring thirteen cases against one `~/.alt_venv` would be wrong: the
second case onwards would find `coverage` already on disk and report a
warm time as its cold time.  Each run therefore gets its own `HOME`,
which `pathlib.Path.home()` honours -- the isolation is in the
environment, where it belongs, and not in a line of code that no real
user would type.  The real `~/.alt_venv` is never touched.

+------+-----------------+---------+-------+-------+--------+--------+--------+
| case | mechanism       | imports | lines | paste | cold   | warm   | size   |
+------+-----------------+---------+-------+-------+--------+--------+--------+
| 1    | venv(pip), pip  | 4       | 19    | 25    | 6.12 s | 0.16 s | 16981  |
|      | in process      |         |       |       |        |        |        |
| 2    | venv(pip), pip  | 4       | 19    | 25    | 6.68 s | 0.15 s | 16981  |
|      | subprocess      |         |       |       |        |        |        |
| 3    | no venv, stdlib | 5       | 45    | 51    | 1.41 s | 0.15 s | 1682   |
|      | wheel           |         |       |       |        |        |        |
| 4    | venv(pip), then | 5       | 25    | 31    | 6.85 s | 0.16 s | 1790   |
|      | delete pip      |         |       |       |        |        |        |
| 5    | venv(no pip),   | 4       | 19    | 25    | 2.65 s | 0.15 s | 1790   |
|      | pip in proc     |         |       |       |        |        |        |
| 6    | no venv, pip in | 1       | 10    | 16    | 2.65 s | 0.14 s | 1762   |
|      | process         |         |       |       |        |        |        |
| 7    | no venv, pip    | 1       | 10    | 16    | 2.73 s | 0.14 s | 1762   |
|      | subprocess      |         |       |       |        |        |        |
| 8    | no venv, pip    | 2       | 14    | 20    | 4.22 s | 0.15 s | 1762   |
|      | from wheel      |         |       |       |        |        |        |
| 9    | as 6 plus --no- | 1       | 11    | 17    | 2.62 s | 0.14 s | 1698   |
|      | compile         |         |       |       |        |        |        |
| 10   | as 7 plus --no- | 1       | 11    | 17    | 2.69 s | 0.14 s | 1698   |
|      | compile         |         |       |       |        |        |        |
| 11   | as 4 but        | 5       | 26    | 32    | 5.25 s | 0.15 s | 1790   |
|      | subprocess      |         |       |       |        |        |        |
| 12   | venv(no pip),   | 7       | 51    | 57    | 1.42 s | 0.16 s | 1714   |
|      | stdlib wheel    |         |       |       |        |        |        |
| 13   | no venv, PyPI   | 3       | 25    | 31    | 3.11 s | 0.14 s | 3538   |
|      | pip subprocess  |         |       |       |        |        |        |
+------+-----------------+---------+-------+-------+--------+--------+--------+

What the columns mean, in the order they appear above:

* **case** -- the argument to pass on the command line, and the `case`
  label in `main()`.  The numbering is the order they were written, not
  a ranking.

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

* **lines** -- physical lines in the `case` body, including the comment
  that opens it.  Blank lines do not occur; `main()` has none.

* **paste** -- **the number that matters.**  This bootstrap is not
  installed, it is copied by hand into the top of every program that
  wants it, so its real cost is how much text the author has to carry
  around.  It is `lines` plus the six shared lines every case needs:
  `import importlib`, `import pathlib` and `import sys`, and the three
  lines of the `try` wrapper described above.  `PACKAGE`, `JSON_API`
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
  because all thirteen then do the same thing: one existence check, one
  `sys.path.insert`, and one import.  Cold cost is paid once per
  machine; warm cost is paid on every run of the program, forever.

* **size** -- kilobytes under `~/.alt_venv` afterwards, counting
  allocated blocks much as `du -sk` does, landing within about 3 KB of
  it in either direction.  Compare these against each other, not
  against `du`.  Kilobytes rather than
  megabytes because rounding to `1.7 MB` hid two real differences.
  The 16981 of cases 1 and 2 is the venv keeping its own copy of pip,
  ~15 MB of the total and never used again.  Among the rest: 1790
  carries an unused venv skeleton, 1762 adds pip's three generated
  `coverage` console scripts in `bin/`, and 1698 is `--no-compile`,
  worth only 60 KB -- 40 `.pyc` files against 44 -- because the
  bootstrap imports the package two lines later and Python compiles
  what it imports anyway.  Case 3 is smallest at 1682 precisely
  because it never generates the console scripts, and case 12 is
  1714, which is case 3 plus 32 KB of empty venv.  Case 13 is case 7's
  1762 plus the 1.8 MB `pip.whl` it keeps for `AltVEnv` to use.

The clusters: cases 6 and 7 are the floor at 16 pasted lines, with 9
and 10 one line above it, but all four need pip already present; cases
4 and 11 manufacture a pip with `ensurepip`, use it once, then delete
it, for a machine that has `venv` but no pip; cases 3 and 12 need
neither, and cost 51 and 57 lines for it.  Case 13 needs neither as
well, by fetching a pip of its own.

Cases 4 and 11 are the same mechanism reached two ways, and they differ
by one line: 5 imports each, 31 and 32 pasted, 1790 KB each.
Case 4 imports the manufactured pip; case 11 runs the venv's own
interpreter as a child instead.  Case 11 therefore reaches the middle
cluster without touching `pip._internal` at all, and costs one line for
the privilege.

Running pip in process is not free of the user's program.  After a
single in-process install, `sys.modules` grows from 99 entries to 740,
451 of them pip's, and pip leaves three `RichPipStreamHandler` objects
on the *root* logger.  A `log.warning("...")` in the user's program
prints bare before the bootstrap runs and `WARNING: ...` through pip's
handler afterwards.  Every in-process case (1, 4, 5, 6, 8, 9) does
this; the subprocess cases (2, 7, 10, 11, 13) cannot, since that state dies
with the child process, and cases 3 and 12 cannot because they never
load pip at all.

Case 12 exists to answer a question about the instructions rather than
to be shipped.  Those asked for a venv built with `venv`, no spawning
of `python3 -m pip install`, only `venv` and standard libraries, and
an `importlib` import.  Case 12 is the only one of the thirteen that
does all four, and it costs 57 pasted lines against case 3's 51.  The
extra 6 lines and 32 KB buy a virtual environment that nothing then
reads, which is finding 3 of the log book arriving from yet another
direction.

Case 13 is the one that ships; see Step 6.15 of `LOGBOOK.md`.  It is
case 7 with the one thing case 7 assumes taken away.  Rather than run
the machine's pip, it fetches pip's own wheel from the JSON API, keeps
it as `~/.alt_venv/pip.whl`, and runs it as `python pip.whl/pip`, which
is how pip documents running itself without being installed.  `AltVEnv`
then uses that same copy, so nothing on the machine needs pip at all.
It is a subprocess case, so none of pip's state reaches the program,
and it costs 31 pasted lines against case 7's 16.

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

# Where cases 3, 12 and 13 look for the JSON API, steered the same way.
JSON_API: str = os.environ.get("BOOTSTRAP_JSON_API",
                               "https://pypi.org/pypi")


def main() -> None:
    """Run the single bootstrap mechanism named by `sys.argv[1]`.

    This is how `run_tests` invokes one `case` in a fresh interpreter.
    It is internal, and not a supported way to use this file; see the
    module docstring above.

    Raises:
    * `RuntimeError`:
      If pip exits non-zero, or if no compatible wheel is found.
    * `subprocess.CalledProcessError`:
      If the pip child process fails, in the cases that spawn one.
    """
    mechanism = sys.argv[1]
    match mechanism:
        case "1":
            # Ensure `alt_venv` is downloaded.
            import os
            import sysconfig
            import venv
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
        case "2":
            # Ensure `alt_venv` is downloaded.
            import os
            import subprocess
            import sysconfig
            import venv
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
        case "3":
            # Ensure `alt_venv` is downloaded.
            import io
            import json
            import sysconfig
            import urllib.request
            import zipfile
            root = pathlib.Path.home() / ".alt_venv"
            target = root
            target.mkdir(parents=True, exist_ok=True)
            if not (target / PACKAGE).is_dir():
                with urllib.request.urlopen(
                        f"{JSON_API}/{PACKAGE}/json",
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
        case "4":
            # Ensure `alt_venv` is downloaded.
            import os
            import shutil
            import sysconfig
            import venv
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
        case "5":
            # Ensure `alt_venv` is downloaded.
            import os
            import sysconfig
            import venv
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
        case "6":
            # Ensure `alt_venv` is downloaded.
            target = pathlib.Path.home() / ".alt_venv"
            if not (target / PACKAGE).is_dir():
                from pip._internal.cli.main import main as pip_main
                if pip_main(["install", "--no-input", "--target", str(target),
                             "--disable-pip-version-check", PACKAGE]):
                    raise RuntimeError("pip failed")
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "7":
            # Ensure `alt_venv` is downloaded.
            import subprocess
            target = pathlib.Path.home() / ".alt_venv"
            if not (target / PACKAGE).is_dir():
                subprocess.run([sys.executable, "-m", "pip", "install",
                                "--no-input", "--disable-pip-version-check",
                                "--target", str(target), PACKAGE], check=True)
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "8":
            # Ensure `alt_venv` is downloaded.
            import ensurepip
            target = pathlib.Path.home() / ".alt_venv"
            if not (target / PACKAGE).is_dir():
                shipped = ensurepip._WHEEL_PKG_DIR  # type: ignore
                sys.path.insert(0, str(next(
                    pathlib.Path(shipped).glob("pip-*.whl"))))
                from pip._internal.cli.main import main as pip_main
                if pip_main(["install", "--no-input", "--target", str(target),
                             "--disable-pip-version-check", PACKAGE]):
                    raise RuntimeError("pip failed")
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "9":
            # Ensure `alt_venv` is downloaded.
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
        case "10":
            # Ensure `alt_venv` is downloaded.
            import subprocess
            target = pathlib.Path.home() / ".alt_venv"
            if not (target / PACKAGE).is_dir():
                subprocess.run([sys.executable, "-m", "pip", "install",
                                "--no-input", "--no-compile",
                                "--disable-pip-version-check", "--target",
                                str(target), PACKAGE], check=True)
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "11":
            # Ensure `alt_venv` is downloaded.
            import os
            import shutil
            import subprocess
            import sysconfig
            import venv
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
        case "12":
            # Ensure `alt_venv` is downloaded.
            import io
            import json
            import os
            import sysconfig
            import urllib.request
            import venv
            import zipfile
            root = pathlib.Path.home() / ".alt_venv"
            if not (root / "pyvenv.cfg").exists():
                venv.EnvBuilder(with_pip=False, symlinks=(os.name != "nt")
                                ).create(root)
            target = pathlib.Path(sysconfig.get_path(
                "purelib", scheme="venv", vars={"base": str(root),
                "platbase": str(root), "installed_base": str(root)}))
            if not (target / PACKAGE).is_dir():
                with urllib.request.urlopen(
                        f"{JSON_API}/{PACKAGE}/json",
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
        case "13":
            # Ensure `alt_venv` is downloaded.
            import json
            import subprocess
            import urllib.request
            target = pathlib.Path.home() / ".alt_venv"
            wheel = target / "pip.whl"
            if not (target / PACKAGE).is_dir():
                if not wheel.is_file():
                    with urllib.request.urlopen(f"{JSON_API}/pip/json",
                                                timeout=30) as r:
                        metadata = json.load(r)
                    entry = next(e for e in metadata["urls"]
                                 if e["packagetype"] == "bdist_wheel")
                    target.mkdir(parents=True, exist_ok=True)
                    with urllib.request.urlopen(entry["url"],
                                                timeout=60) as r:
                        wheel.with_suffix(".part").write_bytes(r.read())
                    wheel.with_suffix(".part").replace(wheel)
                subprocess.run([sys.executable, str(wheel / "pip"),
                                "install", "--no-input",
                                "--disable-pip-version-check", "--target",
                                str(target), PACKAGE], check=True)
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
    # `type(sys)` is `types.ModuleType`, reached without importing
    # `types`, because `sys` is a module and is already imported.
    assert isinstance(module, type(sys)), f"{PACKAGE} gave {module!r}"

    # A real program constructs one next and calls `install()`, and
    # neither is idle here: the constructor repairs a single module
    # install so that this case's own `is_dir()` guard recognises it on
    # the following run, and `install()` walks the declared path in every
    # one of the thirteen shapes, virtual environments included.  This file
    # has no PEP 723 block, so nothing is fetched.  See `0cctfd` and Step
    # 6.7.8.  Harness machinery, so `paste` does not count it.
    if hasattr(module, "AltVEnv"):
        module.AltVEnv().install(bootstrap=sys.argv[1])

    print(f"{PACKAGE}: module {module.__name__} "
          f"version {module.__version__} from {module.__file__}")


MECHANISMS = {
    "1": "venv(pip), pip in process",
    "2": "venv(pip), pip subprocess",
    "3": "no venv, stdlib wheel",
    "4": "venv(pip), then delete pip",
    "5": "venv(no pip), pip in proc",
    "6": "no venv, pip in process",
    "7": "no venv, pip subprocess",
    "8": "no venv, pip from wheel",
    "9": "as 6 plus --no-compile",
    "10": "as 7 plus --no-compile",
    "11": "as 4 but subprocess",
    "12": "venv(no pip), stdlib wheel",
    "13": "no venv, PyPI pip subprocess",
}
# Lines a case needs but does not contain: the three module level
# imports, PACKAGE, and the three of the `try` wrapper that turns a
# failed fetch into one line of diagnosis.  This is the difference
# between `lines` and `paste`.
SHARED_LINES = 6
REPETITIONS = 3
COLUMNS = ["case", "mechanism", "imports", "lines", "paste", "cold",
           "warm", "size"]
COLUMN_WIDTHS = [4, 0, 7, 5, 5, 6, 6, 6]    # 0 means "use what is left".
TABLE_WIDTH = 79


def measure_source() -> dict[str, tuple[int, int]]:
    """Count the imports and lines of every `case` by parsing this file.

    The counts come from the source itself rather than from a table
    maintained by hand, so they cannot drift when a `case` is edited.
    The comment line that opens each `case` is included in the count,
    because it is a line the user has to paste too.

    Returns:
    * (`dict[str, tuple[int, int]]`):
      Maps each case label to its number of `import` statements and
      its number of lines.
    """
    import ast
    tree = ast.parse(pathlib.Path(__file__).read_text())
    entry = next(n for n in tree.body
                 if isinstance(n, ast.FunctionDef) and n.name == "main")
    matched = next(n for n in ast.walk(entry) if isinstance(n, ast.Match))
    counts: dict[str, tuple[int, int]] = {}
    for clause in matched.cases:
        pattern = clause.pattern
        assert isinstance(pattern, ast.MatchValue)
        first = clause.body[0].lineno
        last = clause.body[-1].end_lineno or first
        counts[ast.literal_eval(pattern.value)] = (
            sum(1 for n in ast.walk(clause)
                if isinstance(n, (ast.Import, ast.ImportFrom))),
            last - first + 2)          # +2 picks up the comment line.
    return counts


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
                done = subprocess.run([sys.executable, script, label],
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
        # A pasted case carries this wrapper around its own body.  The
        # fetch is the part that reaches the network, and a traceback is
        # not an error message; see `0whwnn` and Step 6.1 of
        # `LOGBOOK.md`.  `Exception` rather than `BaseException`, so
        # that a control-C still reads as a control-C.
        try:
            main()                  # internal: one case, one interpreter
        except Exception as error:  # noqa: BLE001 -- deliberate
            raise SystemExit(f"cannot fetch {PACKAGE}: {error}") from None
    else:
        sys.exit(f"usage: {sys.argv[0]}          (takes no arguments)")
