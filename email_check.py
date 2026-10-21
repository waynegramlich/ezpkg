#!/usr/bin/env python3
"""Check the `email` export where it matters: on another computer.

A developer's `checksums` hold only what arrived on the developer's own
computer, so a package that another computer alone needs, as `tqdm`
needs `colorama` on Windows, is refused there.  The `email` release
adds those packages (`T.ee`).  This shows both halves:

* `./email_check.py build DIR`: as a developer on this computer, writes
  `prog.py` (the Quick Start's Parts 1-3, needing `tqdm`), runs it
  twice with a `prog.py.toml`, then releases it with `exports =
  ["email"]`, leaving `DIR/out/prog.py` and `DIR/out/prog-1.0.0.py`.
* `./email_check.py friend DIR OUT`: as a new end user, from a fresh
  home each, runs both files from `OUT`.  On Windows `prog.py` must be
  refused for `colorama` and `prog-1.0.0.py` must run; elsewhere both
  must run.

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


def run(program: pathlib.Path, home: pathlib.Path
        ) -> subprocess.CompletedProcess[str]:
    """Run a program as somebody whose home is `home`.

    Arguments:
    * `program` (`pathlib.Path`):
      The program, run from its own directory.
    * `home` (`pathlib.Path`):
      The home, as `HOME` and `USERPROFILE`.

    Returns:
    * (`subprocess.CompletedProcess[str]`): The finished child.
    """
    # Nothing from this machine's own Python setup, and nobody to ask.
    environment: dict[str, str] = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("PIP_", "EZPKG_"))
        and key not in ("PYTHONPATH", "VIRTUAL_ENV")}
    environment.update(HOME=str(home), USERPROFILE=str(home), CI="1")
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

    # Two developer runs, then the release.
    settings: pathlib.Path = work / "prog.py.toml"
    settings.write_text("", encoding="utf-8")
    for _ in range(2):
        if run(program, home).returncode:
            return 1
    settings.write_text('release = "1.0.0"\nexports = ["email"]\n',
                        encoding="utf-8")
    if run(program, home).returncode:
        return 1
    copy: pathlib.Path = work / "prog-1.0.0.py"
    if not copy.is_file():
        print("FAIL: no prog-1.0.0.py")
        return 1

    # The developer's own approvals lack `colorama`; the copy's have it.
    out: pathlib.Path = directory / "out"
    out.mkdir()
    shutil.copy2(program, out / "prog.py")
    shutil.copy2(copy, out / "prog-1.0.0.py")
    own: bool = "colorama==" in program.read_text(encoding="utf-8")
    sent: bool = "colorama==" in copy.read_text(encoding="utf-8")
    print(f"prog.py approves colorama: {own}; prog-1.0.0.py: {sent}")
    if own or not sent:
        print("FAIL: expected colorama in prog-1.0.0.py's checksums only")
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
    for name in ("prog.py", "prog-1.0.0.py"):
        sent: pathlib.Path = directory / name.removesuffix(".py") / name
        sent.parent.mkdir(parents=True)
        shutil.copy2(out / name, sent)
        home: pathlib.Path = directory / name.removesuffix(".py") / "home"
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
        print("OK: " + ("prog.py refused, prog-1.0.0.py ran" if windows
                        else "both ran"))
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
