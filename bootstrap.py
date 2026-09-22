#!/usr/bin/env python3
"""Ten ways to get a package onto `sys.path` with nothing preinstalled.

Run as `python3 bootstrap.py <1..10>`.  That number is the only
argument.  Each `case` in `main()` is one self-contained mechanism: it
decides where the packages live, installs `PACKAGE` there if it is
missing, and imports it.  Every import a case does not share with all
the others is inside that case, and the pip argument list is spelled
out inside each case rather than hoisted into a constant.  Neither is
Pythonic.  Both are deliberate: nothing above `main()` is hidden from
the count, so `paste` below is honest.

`sys.argv[1]` is this harness, not the bootstrap.  It picks the case,
and exists only so that one file can hold ten mechanisms; a program
that pastes this in keeps one case body and has no `match` and no
`sys.argv` at all.  Neither `mechanism = sys.argv[1]` nor
`match mechanism:` is counted in `paste`, and neither is the closing
`print`.  Every other line in a case is counted, and is exactly the
line a real program would carry -- `~/.embedded_venv` is named in the
code rather than passed in, so that stays true.

Measuring ten cases against one `~/.embedded_venv` would be wrong: the
second case onwards would find `coverage` already on disk and report a
warm time as its cold time.  The ten cold runs were therefore isolated
by giving each case its own `HOME`, which `pathlib.Path.home()` honours
-- the isolation is in the environment, where it belongs, and not in a
line of code that no real user would type.

+------+-----------------+---------+-------+-------+--------+--------+--------+
| case | mechanism       | imports | lines | paste | cold   | warm   | size   |
+------+-----------------+---------+-------+-------+--------+--------+--------+
| 1    | venv(pip), pip  | 4       | 20    | 24    | 5.91 s | 0.15 s | 16984  |
|      | in process      |         |       |       |        |        |        |
| 2    | venv(pip), pip  | 4       | 20    | 24    | 5.82 s | 0.15 s | 16984  |
|      | subprocess      |         |       |       |        |        |        |
| 3    | no venv, stdlib | 5       | 45    | 49    | 1.34 s | 0.15 s | 1684   |
|      | wheel           |         |       |       |        |        |        |
| 4    | venv(pip), then | 5       | 27    | 31    | 5.81 s | 0.14 s | 1788   |
|      | delete pip      |         |       |       |        |        |        |
| 5    | venv(no pip),   | 4       | 20    | 24    | 2.53 s | 0.14 s | 1788   |
|      | pip in proc     |         |       |       |        |        |        |
| 6    | no venv, pip in | 1       | 11    | 15    | 2.58 s | 0.13 s | 1760   |
|      | process         |         |       |       |        |        |        |
| 7    | no venv, pip    | 1       | 11    | 15    | 2.70 s | 0.14 s | 1760   |
|      | subprocess      |         |       |       |        |        |        |
| 8    | no venv, pip    | 2       | 14    | 18    | 4.11 s | 0.13 s | 1760   |
|      | from wheel      |         |       |       |        |        |        |
| 9    | as 6 plus --no- | 1       | 11    | 15    | 2.58 s | 0.14 s | 1700   |
|      | compile         |         |       |       |        |        |        |
| 10   | as 7 plus --no- | 1       | 11    | 15    | 2.70 s | 0.13 s | 1700   |
|      | compile         |         |       |       |        |        |        |
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
  mechanism has to reach into.  The spread is narrow (1 to 5) and it is
  the weakest of these columns; *which* modules are imported says more
  than how many.  A case importing `venv` inherits 15 MB of pip with it.

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
  creation if any, the download, and the install.  Median of three
  runs, measured with `env -i` outside any virtual environment.  Single
  runs varied by up to 15%, mostly on the network, so medians are what
  is reported here.

* **warm** -- wall clock for the second run, when the package is already
  on disk.  Median of three.  It is ~0.14 s for every case because all
  ten then do the same thing: one existence check, `sys.path.insert`,
  and an import.  Cold cost is paid once per machine; warm cost is paid
  on every single run of the program, forever.

* **size** -- kilobytes under `~/.embedded_venv` afterwards, as
  `du -sk` reports.  Kilobytes rather than megabytes because rounding
  to `1.7 MB` hid two real differences.  The 16984 of cases 1 and 2 is
  the venv keeping its own copy of pip, ~15 MB of the total, never used
  again.  Among the rest: 1788 carries an unused venv skeleton, 1760
  adds pip's three generated `coverage` console scripts in `bin/`, and
  1700 is `--no-compile`, worth only 60 KB -- 40 `.pyc` files against
  44 -- because the bootstrap imports the package two lines later and
  Python compiles what it imports anyway.  Case 3 is smallest at 1684
  precisely because it skips the console scripts it never generates.

The clusters: cases 6, 7, 9 and 10 are the floor at 15 pasted lines but
need pip already present; case 4 manufactures a pip with `ensurepip`,
uses it once, then deletes it, for a machine that has `venv` but no
pip; case 3 needs neither and costs 49 lines for it.

Running pip in process is not free of the user's program.  After a
single in-process install, `sys.modules` grows from 99 entries to 740,
451 of them pip's, and pip leaves three `RichPipStreamHandler` objects
on the *root* logger.  A `log.warning("...")` in the user's program
prints bare before the bootstrap runs and `WARNING: ...` through pip's
handler afterwards.  Every in-process case (1, 4, 5, 6, 8, 9) does
this; the subprocess cases (2, 7, 10) cannot, since that state dies
with the child process.
"""

import importlib
import pathlib
import sys

PACKAGE = "coverage"


def main() -> None:
    mechanism = sys.argv[1]
    match mechanism:
        case "1":
            # Ensure `embeddedvenv` is downloaded.
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
            # Ensure `embeddedvenv` is downloaded.
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
            # Ensure `embeddedvenv` is downloaded.
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
            # Ensure `embeddedvenv` is downloaded.
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
            if not (target / PACKAGE).is_dir():
                sys.path.insert(0, str(target))
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
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "5":
            # Ensure `embeddedvenv` is downloaded.
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
            # Ensure `embeddedvenv` is downloaded.
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
            # Ensure `embeddedvenv` is downloaded.
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
            # Ensure `embeddedvenv` is downloaded.
            import ensurepip
            target = pathlib.Path.home() / ".embedded_venv"
            if not (target / PACKAGE).is_dir():
                sys.path.insert(0, str(next(pathlib.Path(
                    ensurepip._WHEEL_PKG_DIR).glob("pip-*.whl"))))
                from pip._internal.cli.main import main as pip_main
                if pip_main(["install", "--quiet", "--no-input",
                             "--disable-pip-version-check", "--target",
                             str(target), PACKAGE]):
                    raise RuntimeError("pip failed")
            sys.path.insert(0, str(target))
            importlib.invalidate_caches()
            module = importlib.import_module(PACKAGE)
        case "9":
            # Ensure `embeddedvenv` is downloaded.
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
            # Ensure `embeddedvenv` is downloaded.
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
    print(f"{PACKAGE} {module.__version__} imported from {module.__file__}")


if __name__ == "__main__":
    main()
