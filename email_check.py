#!/usr/bin/env python3
"""Check the `email` export where it matters: on another computer.

A developer's `checksums` hold only what arrived on the developer's own
computer, so a package that another computer alone needs, as `tqdm`
needs `colorama` on Windows, is refused there.  The `email` release
adds those packages (`T.ee`).  This shows both halves:

* `./email_check.py build DIR`: as a developer on this computer, writes
  `prog.py` (the Quick Start's Parts 1-3, needing `tqdm`) and an empty
  `prog.py.toml`, and runs it: that first developer run must build
  release 1.0.0 into `prog_builds/1.0.0/`, write `prog.py.release` and
  run the program; the next run must build nothing.  It leaves
  `DIR/out/prog.py`, `DIR/out/prog-1.0.0.py` and
  `DIR/out/prog-1.0.0.pyz`.  The runs pass over any installed `uv`
  (`EZPKG_UV=fetch`), so `ezpkg` must fetch the `uv` wheel for this
  computer, and both releases must carry `colorama`, which only
  Windows needs.
* `./email_check.py friend DIR OUT`: as a new end user, from a fresh
  home each, runs the three files from `OUT`.  On Windows `prog.py`
  must be refused for `colorama` and the releases must run; elsewhere
  all must run.

Each run uses this tree's `ezpkg.py`, as `~/.ezpkg/ezpkg.whl` where the
bootstrap keeps it, and everything else from pypi.org.  `CI` is set, so
nobody is asked.  Exit 0 means every expectation held.  See
`.github/workflows/email_check.yml`.
"""

import os
import pathlib
import shutil
import subprocess
import sys
import time
import zipfile

HERE: pathlib.Path = pathlib.Path(__file__).resolve().parent


def seed_home(home: pathlib.Path) -> None:
    """Make a fresh home whose `~/.ezpkg/ezpkg.whl` is this tree's.

    Arguments:
    * `home` (`pathlib.Path`):
      The directory to use as the home; it must not exist.
    """
    # The bootstrap imports `ezpkg` straight from the zip.
    cache: pathlib.Path = home / ".ezpkg"
    cache.mkdir(parents=True)
    with zipfile.ZipFile(cache / "ezpkg.whl", "w") as archive:
        archive.write(HERE / "ezpkg.py", "ezpkg.py")


def run(program: pathlib.Path, home: pathlib.Path, **extra: str
        ) -> subprocess.CompletedProcess[str]:
    """Run a program as somebody whose home is `home`.

    Arguments:
    * `program` (`pathlib.Path`):
      The program, run from its own directory.
    * `home` (`pathlib.Path`):
      The home, as `HOME` and `USERPROFILE`.
    * `extra` (`str`):
      More environment, such as `EZPKG_UV="fetch"`.

    Returns:
    * (`subprocess.CompletedProcess[str]`): The finished child.
    """
    # Nothing from this machine's own Python setup, and nobody to ask.
    environment: dict[str, str] = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("PIP_", "EZPKG_"))
        and key not in ("PYTHONPATH", "VIRTUAL_ENV")}
    environment.update(HOME=str(home), USERPROFILE=str(home), CI="1",
                       **extra)
    started: float = time.monotonic()
    done: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, program.name], cwd=program.parent,
        env=environment, capture_output=True, text=True, timeout=900,
        stdin=subprocess.DEVNULL, check=False)
    print(f"--- {program.name} (HOME={home}): exit {done.returncode}, "
          f"{time.monotonic() - started:.1f} s")
    print(f"stdout:\n{done.stdout}stderr:\n{done.stderr}", flush=True)
    return done


def build(directory: pathlib.Path) -> int:
    """Develop `prog.py` here and release it as an `email` copy.

    Arguments:
    * `directory` (`pathlib.Path`):
      A directory that does not exist yet.

    Returns:
    * (`int`): The exit status.
    """
    # The Quick Start's Parts 1-3, needing `tqdm` instead of `cowsay`.
    quick: str = (HERE / "quick_start.py").read_text(encoding="utf-8")
    head: str = quick.partition("# Part 4:")[0]
    head = head.replace('"cowsay"]', '"tqdm"]')
    work: pathlib.Path = directory / "work"
    work.mkdir(parents=True)
    program: pathlib.Path = work / "prog.py"
    program.write_text(
        head + "# Part 4: Your imports, all after the bootstrap.\n"
        "import tqdm\n\n# Part 5: The program itself.\n"
        "print(f'tqdm {tqdm.__version__}')\n", encoding="utf-8")
    home: pathlib.Path = directory / "home"
    seed_home(home)

    # The first developer run releases and runs; the next only runs.
    (work / "prog.py.toml").write_text("", encoding="utf-8")
    first: subprocess.CompletedProcess[str] = run(program, home,
                                                  EZPKG_UV="fetch")
    if first.returncode or "tqdm " not in first.stdout:
        print("FAIL: the first developer run did not run prog.py")
        return 1
    folder: pathlib.Path = work / "prog_builds" / "1.0.0"
    copy: pathlib.Path = folder / "prog-1.0.0.py"
    archive: pathlib.Path = folder / "prog-1.0.0.pyz"
    built: list[str] = sorted(one.name for one in folder.glob("*"))
    print(f"built: {built}")
    if not (copy.is_file() and archive.is_file()
            and (work / "prog.py.release").is_file()):
        print("FAIL: no prog-1.0.0.py, prog-1.0.0.pyz or prog.py.release")
        return 1
    second: subprocess.CompletedProcess[str] = run(program, home,
                                                   EZPKG_UV="fetch")
    if second.returncode or "Released" in second.stderr:
        print("FAIL: the second developer run did not just run")
        return 1

    # `uv` came as a wheel, for this computer, into the cache.
    fetched: list[str] = sorted(
        tree.name for tree in (home / ".ezpkg" / "versions").glob("uv-*"))
    print(f"uv fetched: {fetched}")
    if not fetched:
        print("FAIL: ezpkg did not fetch uv")
        return 1

    # The developer's own approvals have `colorama` only on Windows;
    # both releases have it everywhere.
    out: pathlib.Path = directory / "out"
    out.mkdir()
    shutil.copy2(program, out / "prog.py")
    shutil.copy2(copy, out / "prog-1.0.0.py")
    shutil.copy2(archive, out / "prog-1.0.0.pyz")
    own: bool = "colorama==" in program.read_text(encoding="utf-8")
    sent: bool = "colorama==" in copy.read_text(encoding="utf-8")
    with zipfile.ZipFile(archive) as opened:
        zipped: bool = "colorama/__init__.py" in opened.namelist()
    print(f"colorama approved by prog.py: {own}; by prog-1.0.0.py: "
          f"{sent}; inside prog-1.0.0.pyz: {zipped}")
    if own != (os.name == "nt") or not sent or not zipped:
        print("FAIL: expected colorama in both releases, and in prog.py "
              "on Windows only")
        return 1
    print("OK: built")
    return 0


def friend(directory: pathlib.Path, out: pathlib.Path) -> int:
    """Run both files as a new end user, each from a fresh home.

    Arguments:
    * `directory` (`pathlib.Path`):
      A directory that does not exist yet.
    * `out` (`pathlib.Path`):
      Where `build` left `prog.py` and `prog-1.0.0.py`.

    Returns:
    * (`int`): The exit status.
    """
    # On Windows the developer's own copy should be refused.
    windows: bool = os.name == "nt"
    failures: list[str] = []
    name: str
    for name in ("prog.py", "prog-1.0.0.py", "prog-1.0.0.pyz"):
        stem: str = name.replace(".", "_")
        sent: pathlib.Path = directory / stem / name
        sent.parent.mkdir(parents=True)
        shutil.copy2(out / name, sent)
        home: pathlib.Path = directory / stem / "home"
        seed_home(home)
        done: subprocess.CompletedProcess[str] = run(sent, home)
        failure: pathlib.Path = home / ".ezpkg" / "last_failure.txt"
        if failure.is_file():
            print(f"last_failure.txt:\n"
                  f"{failure.read_text(encoding='utf-8')}")
        refused: bool = windows and name == "prog.py"
        if refused:
            reason: str = (failure.read_text(encoding="utf-8")
                           if failure.is_file() else "")
            if done.returncode == 0 or "colorama" not in (
                    reason + done.stderr):
                failures.append(f"{name}: expected a refusal naming "
                                f"colorama")
        elif done.returncode or "tqdm " not in done.stdout:
            failures.append(f"{name}: expected it to run")

    # One line each way.
    for line in failures:
        print(f"FAIL: {line}")
    if not failures:
        print("OK: " + ("prog.py refused, the releases ran" if windows
                        else "all three ran"))
    return 1 if failures else 0


def main() -> int:
    """Run `build` or `friend`, as the command line says.

    Returns:
    * (`int`): The exit status.
    """
    # `build DIR` or `friend DIR OUT`.
    arguments: list[str] = sys.argv[1:]
    if arguments[:1] == ["build"] and len(arguments) == 2:
        return build(pathlib.Path(arguments[1]))
    if arguments[:1] == ["friend"] and len(arguments) == 3:
        return friend(pathlib.Path(arguments[1]), pathlib.Path(arguments[2]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
