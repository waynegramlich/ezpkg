#!/usr/bin/env python3
"""Twelve ways to get a package onto `sys.path` with nothing preinstalled.

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
`~/.embedded_venv` is named in the code rather than passed in, so that
stays true.

Measuring twelve cases against one `~/.embedded_venv` would be wrong: the
second case onwards would find `coverage` already on disk and report a
warm time as its cold time.  Each run therefore gets its own `HOME`,
which `pathlib.Path.home()` honours -- the isolation is in the
environment, where it belongs, and not in a line of code that no real
user would type.  The real `~/.embedded_venv` is never touched.

+------+-----------------+---------+-------+-------+--------+--------+--------+
| case | mechanism       | imports | lines | paste | cold   | warm   | size   |
+------+-----------------+---------+-------+-------+--------+--------+--------+
| 1    | venv(pip), pip  | 4       | 20    | 24    | 6.12 s | 0.16 s | 16981  |
|      | in process      |         |       |       |        |        |        |
| 2    | venv(pip), pip  | 4       | 20    | 24    | 6.68 s | 0.15 s | 16981  |
|      | subprocess      |         |       |       |        |        |        |
| 3    | no venv, stdlib | 5       | 45    | 49    | 1.41 s | 0.15 s | 1682   |
|      | wheel           |         |       |       |        |        |        |
| 4    | venv(pip), then | 5       | 26    | 30    | 6.85 s | 0.16 s | 1790   |
|      | delete pip      |         |       |       |        |        |        |
| 5    | venv(no pip),   | 4       | 20    | 24    | 2.65 s | 0.15 s | 1790   |
|      | pip in proc     |         |       |       |        |        |        |
| 6    | no venv, pip in | 1       | 11    | 15    | 2.65 s | 0.14 s | 1762   |
|      | process         |         |       |       |        |        |        |
| 7    | no venv, pip    | 1       | 11    | 15    | 2.73 s | 0.14 s | 1762   |
|      | subprocess      |         |       |       |        |        |        |
| 8    | no venv, pip    | 2       | 15    | 19    | 4.22 s | 0.15 s | 1762   |
|      | from wheel      |         |       |       |        |        |        |
| 9    | as 6 plus --no- | 1       | 11    | 15    | 2.62 s | 0.14 s | 1698   |
|      | compile         |         |       |       |        |        |        |
| 10   | as 7 plus --no- | 1       | 11    | 15    | 2.69 s | 0.14 s | 1698   |
|      | compile         |         |       |       |        |        |        |
| 11   | as 4 but        | 5       | 26    | 30    | 5.25 s | 0.15 s | 1790   |
|      | subprocess      |         |       |       |        |        |        |
| 12   | venv(no pip),   | 7       | 51    | 55    | 1.42 s | 0.16 s | 1714   |
|      | stdlib wheel    |         |       |       |        |        |        |
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
  around.  It is `lines` plus the four shared lines every case needs:
  `import importlib`, `import pathlib`, `import sys` and `PACKAGE`.
  Nothing else lives above `main()`.  The closing `print` is
  diagnostics and is not counted.

* **cold** -- wall clock for the first run into an empty `HOME`: venv
  creation if any, the download, and the install.  Median of
  `REPETITIONS` runs, with `VIRTUAL_ENV` stripped from the environment
  so that an activated virtual environment cannot skew the result.
  Single runs varied by up to 15%, mostly on the network, which is why
  medians are reported rather than single measurements.

* **warm** -- wall clock for the second run, when the package is already
  on disk.  Median of `REPETITIONS` runs.  It is ~0.14 s for every case
  because all twelve then do the same thing: one existence check, one
  `sys.path.insert`, and one import.  Cold cost is paid once per
  machine; warm cost is paid on every run of the program, forever.

* **size** -- kilobytes under `~/.embedded_venv` afterwards, counting
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
  1714, which is case 3 plus 32 KB of empty venv.

The clusters: cases 6, 7, 9 and 10 are the floor at 15 pasted lines but
need pip already present; cases 4 and 11 manufacture a pip with
`ensurepip`, use it once, then delete it, for a machine that has `venv`
but no pip; cases 3 and 12 need neither, and cost 49 and 55 lines for
it.

Cases 4 and 11 are the same mechanism reached two ways, and they are
identical on every column: 5 imports, 26 lines, 30 pasted, 1790 KB.
Case 4 imports the manufactured pip; case 11 runs the venv's own
interpreter as a child instead.  Case 11 therefore reaches the middle
cluster without touching `pip._internal` at all, and costs nothing for
the privilege.

Running pip in process is not free of the user's program.  After a
single in-process install, `sys.modules` grows from 99 entries to 740,
451 of them pip's, and pip leaves three `RichPipStreamHandler` objects
on the *root* logger.  A `log.warning("...")` in the user's program
prints bare before the bootstrap runs and `WARNING: ...` through pip's
handler afterwards.  Every in-process case (1, 4, 5, 6, 8, 9) does
this; the subprocess cases (2, 7, 10, 11) cannot, since that state dies
with the child process, and cases 3 and 12 cannot because they never
load pip at all.

Case 12 exists to answer a question about the instructions rather than
to be shipped.  Those asked for a venv built with `venv`, no spawning
of `python3 -m pip install`, only `venv` and standard libraries, and
an `importlib` import.  Case 12 is the only one of the twelve that
does all four, and it costs 55 pasted lines against case 3's 49.  The
extra 6 lines and 32 KB buy a virtual environment that nothing then
reads, which is finding 3 of the log book arriving from yet another
direction.

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
import pathlib
import sys

PACKAGE = "coverage"


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
            # Ensure `embeddedenv` is downloaded.
            import os
            import sysconfig
            import venv
            root = pathlib.Path.home() / ".embedded_venv"
            if not (root / "pyvenv.cfg").exists():
                venv.EnvBuilder(with_pip=True, symlinks=(os.name != "nt")
                                ).create(root)
            target = pathlib.Path(sysconfig.get_path(
                "purelib", scheme="venv", vars={"base": str(root),
                "platbase": str(root), "installed_base": str(root)}))
            if not (target / PACKAGE).is_dir():
                from pip._internal.cli.main import main as pip_main
                if pip_main(["install", "--quiet", "--no-input",
                             "--disable-pip-version-check", "--target",
                             str(target), PACKAGE]):
                    raise RuntimeError("pip failed")
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "2":
            # Ensure `embeddedenv` is downloaded.
            import os
            import subprocess
            import sysconfig
            import venv
            root = pathlib.Path.home() / ".embedded_venv"
            if not (root / "pyvenv.cfg").exists():
                venv.EnvBuilder(with_pip=True, symlinks=(os.name != "nt")
                                ).create(root)
            target = pathlib.Path(sysconfig.get_path(
                "purelib", scheme="venv", vars={"base": str(root),
                "platbase": str(root), "installed_base": str(root)}))
            if not (target / PACKAGE).is_dir():
                subprocess.run([sys.executable, "-m", "pip", "install",
                                "--quiet", "--no-input",
                                "--disable-pip-version-check", "--target",
                                str(target), PACKAGE], check=True)
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "3":
            # Ensure `embeddedenv` is downloaded.
            import io
            import json
            import sysconfig
            import urllib.request
            import zipfile
            root = pathlib.Path.home() / ".embedded_venv"
            target = root
            target.mkdir(parents=True, exist_ok=True)
            if not (target / PACKAGE).is_dir():
                with urllib.request.urlopen(
                        f"https://pypi.org/pypi/{PACKAGE}/json",
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
            # Ensure `embeddedenv` is downloaded.
            import os
            import shutil
            import sysconfig
            import venv
            root = pathlib.Path.home() / ".embedded_venv"
            if not (root / "pyvenv.cfg").exists():
                venv.EnvBuilder(with_pip=True, symlinks=(os.name != "nt")
                                ).create(root)
            target = pathlib.Path(sysconfig.get_path(
                "purelib", scheme="venv", vars={"base": str(root),
                "platbase": str(root), "installed_base": str(root)}))
            sys.path.insert(0, str(target))
            if not (target / PACKAGE).is_dir():
                from pip._internal.cli.main import main as pip_main
                if pip_main(["install", "--quiet", "--no-input",
                             "--disable-pip-version-check", "--target",
                             str(target), PACKAGE]):
                    raise RuntimeError("pip failed")
                shutil.rmtree(target / "pip", ignore_errors=True)
                for leftover in target.glob("pip-*.dist-info"):
                    shutil.rmtree(leftover)
                for leftover in (root / "bin").glob("pip*"):
                    leftover.unlink()
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "5":
            # Ensure `embeddedenv` is downloaded.
            import os
            import sysconfig
            import venv
            root = pathlib.Path.home() / ".embedded_venv"
            if not (root / "pyvenv.cfg").exists():
                venv.EnvBuilder(with_pip=False, symlinks=(os.name != "nt")
                                ).create(root)
            target = pathlib.Path(sysconfig.get_path(
                "purelib", scheme="venv", vars={"base": str(root),
                "platbase": str(root), "installed_base": str(root)}))
            if not (target / PACKAGE).is_dir():
                from pip._internal.cli.main import main as pip_main
                if pip_main(["install", "--quiet", "--no-input",
                             "--disable-pip-version-check", "--target",
                             str(target), PACKAGE]):
                    raise RuntimeError("pip failed")
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "6":
            # Ensure `embeddedenv` is downloaded.
            target = pathlib.Path.home() / ".embedded_venv"
            if not (target / PACKAGE).is_dir():
                from pip._internal.cli.main import main as pip_main
                if pip_main(["install", "--quiet", "--no-input",
                             "--disable-pip-version-check", "--target",
                             str(target), PACKAGE]):
                    raise RuntimeError("pip failed")
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "7":
            # Ensure `embeddedenv` is downloaded.
            import subprocess
            target = pathlib.Path.home() / ".embedded_venv"
            if not (target / PACKAGE).is_dir():
                subprocess.run([sys.executable, "-m", "pip", "install",
                                "--quiet", "--no-input",
                                "--disable-pip-version-check", "--target",
                                str(target), PACKAGE], check=True)
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "8":
            # Ensure `embeddedenv` is downloaded.
            import ensurepip
            target = pathlib.Path.home() / ".embedded_venv"
            if not (target / PACKAGE).is_dir():
                shipped = ensurepip._WHEEL_PKG_DIR  # type: ignore
                sys.path.insert(0, str(next(
                    pathlib.Path(shipped).glob("pip-*.whl"))))
                from pip._internal.cli.main import main as pip_main
                if pip_main(["install", "--quiet", "--no-input",
                             "--disable-pip-version-check", "--target",
                             str(target), PACKAGE]):
                    raise RuntimeError("pip failed")
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "9":
            # Ensure `embeddedenv` is downloaded.
            target = pathlib.Path.home() / ".embedded_venv"
            if not (target / PACKAGE).is_dir():
                from pip._internal.cli.main import main as pip_main
                if pip_main(["install", "--quiet", "--no-input",
                             "--no-compile", "--disable-pip-version-check",
                             "--target", str(target), PACKAGE]):
                    raise RuntimeError("pip failed")
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "10":
            # Ensure `embeddedenv` is downloaded.
            import subprocess
            target = pathlib.Path.home() / ".embedded_venv"
            if not (target / PACKAGE).is_dir():
                subprocess.run([sys.executable, "-m", "pip", "install",
                                "--quiet", "--no-input", "--no-compile",
                                "--disable-pip-version-check", "--target",
                                str(target), PACKAGE], check=True)
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "11":
            # Ensure `embeddedenv` is downloaded.
            import os
            import shutil
            import subprocess
            import sysconfig
            import venv
            root = pathlib.Path.home() / ".embedded_venv"
            if not (root / "pyvenv.cfg").exists():
                venv.EnvBuilder(with_pip=True, symlinks=(os.name != "nt")
                                ).create(root)
            target = pathlib.Path(sysconfig.get_path(
                "purelib", scheme="venv", vars={"base": str(root),
                "platbase": str(root), "installed_base": str(root)}))
            if not (target / PACKAGE).is_dir():
                subprocess.run([str(root / "bin" / "python3"), "-m", "pip",
                                "install", "--quiet", "--no-input",
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
            # Ensure `embeddedenv` is downloaded.
            import io
            import json
            import os
            import sysconfig
            import urllib.request
            import venv
            import zipfile
            root = pathlib.Path.home() / ".embedded_venv"
            if not (root / "pyvenv.cfg").exists():
                venv.EnvBuilder(with_pip=False, symlinks=(os.name != "nt")
                                ).create(root)
            target = pathlib.Path(sysconfig.get_path(
                "purelib", scheme="venv", vars={"base": str(root),
                "platbase": str(root), "installed_base": str(root)}))
            if not (target / PACKAGE).is_dir():
                with urllib.request.urlopen(
                        f"https://pypi.org/pypi/{PACKAGE}/json",
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
    print(f"{PACKAGE} {module.__version__} imported from {module.__file__}")


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
}
# Lines a case needs but does not contain: the three module level imports
# and PACKAGE.  This is the difference between `lines` and `paste`.
SHARED_LINES = 4
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

    Each case installs into `~/.embedded_venv`, so every run is given
    its own temporary `HOME`, which `pathlib.Path.home()` honours.
    Without that, the second case onwards would find the package
    already on disk and report a warm time as its cold time.  The real
    `~/.embedded_venv` is never touched, and each temporary tree is
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
                size = directory_size(pathlib.Path(home) / ".embedded_venv")
            shutil.rmtree(home, ignore_errors=True)
        cold, warm = statistics.median(colds), statistics.median(warms)
        imports, lines = counts[label]
        rows.append([label, description, imports, lines, lines + SHARED_LINES,
                     f"{cold:.2f} s", f"{warm:.2f} s", size])
        print(f"case {label:>2}: cold {cold:5.2f} s   warm {warm:5.2f} s"
              f"   size {size:>6} KB   {description}", file=sys.stderr)

    now = datetime.datetime.now(datetime.timezone.utc).astimezone()
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
