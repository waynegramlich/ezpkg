#!/usr/bin/env python3
"""Run every local test of `EZPkg`, coverage included, in one command.

Usage: `./ezpkg_test_all.py [DIR]` (about 35 minutes; it needs the
network, for pypi.org).  `DIR` is where the logs and results go; it must
not exist yet, or be empty, and defaults to a new temporary directory.
The steps are the local layers of "How To Test `EZPkg`" at the top of
`ezpkg_test.py`, in its order, each with its own log in `DIR`:

1. `ruff check .` and `mypy .`.
2. and 3. `./ezpkg_coverage.py --children DIR/coverage`, which runs the
   whole test suite (layer 2) while it measures it (layer 3), with a
   scratch home whose `~/.ezpkg/pip.whl` is the newest `pip`, so that no
   test skips for want of one.  Unrun lines are in
   `DIR/coverage/missing.txt`.
4. `ux/drive.py`, writing its per-step files into `DIR/ux` rather than
   `ux/`, so that a run never overwrites the agreed output.
5. `./email_check.py build` and then `friend`, which builds `email` and
   `zipapp` releases and runs them as a new user would, here.

A failed step does not stop the others, except that `friend` needs what
`build` built.  The summary at the end gives each step's result, time
and log; the exit status is 0 only when every step passed.  The GitHub
Actions checks are not run from here: they test a published `ezpkg`,
and are started by hand (layer 5 of the same docstring).

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

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE: pathlib.Path = pathlib.Path(__file__).resolve().parent


def seed_pip(home: pathlib.Path) -> None:
    """Put the newest `pip` wheel at `home/.ezpkg/pip.whl`.

    Fetched from pypi.org's JSON API and checked against its SHA-256,
    so that no `pip` need be installed here.  The date tests borrow it
    (`dating_pip` in `ezpkg_test.py`).

    Arguments:
    * `home` (`pathlib.Path`):
      The scratch home.

    Raises:
    * `ValueError`:
      If the wheel fails its SHA-256 check.
    """
    # The first wheel the newest release lists.
    with urllib.request.urlopen("https://pypi.org/pypi/pip/json",
                                timeout=60) as answer:
        listing: dict = json.load(answer)
    entry: dict = next(one for one in listing["urls"]
                       if one["filename"].endswith(".whl"))
    with urllib.request.urlopen(entry["url"], timeout=60) as answer:
        wheel: bytes = answer.read()
    if hashlib.sha256(wheel).hexdigest() != entry["digests"]["sha256"]:
        raise ValueError(f"{entry['filename']} fails its SHA-256 check")
    cache: pathlib.Path = home / ".ezpkg"
    cache.mkdir(parents=True)
    (cache / "pip.whl").write_bytes(wheel)


def step(name: str, command: list[str], log: pathlib.Path,
         home: pathlib.Path | None = None) -> tuple[bool, float]:
    """Run one step, its output going to `log`.

    Arguments:
    * `name` (`str`):
      What the step is called, for the progress line.
    * `command` (`list[str]`):
      The command, run from the project directory.
    * `log` (`pathlib.Path`):
      Where its standard output and error go.
    * `home` (`pathlib.Path | None`):
      A `HOME` to run it with, or `None` for this one's.

    Returns:
    * (`tuple[bool, float]`): Whether it passed, and the minutes taken.
    """
    # One line before, one after, so a long step shows it is running.
    print(f"==> {name}: {' '.join(command)}", flush=True)
    environment: dict[str, str] = dict(os.environ)
    if home is not None:
        environment.update(HOME=str(home), USERPROFILE=str(home))
    start: float = time.monotonic()
    with log.open("w", encoding="utf-8") as output:
        try:
            passed: bool = subprocess.run(
                command, cwd=HERE, env=environment, stdout=output,
                stderr=subprocess.STDOUT, check=False).returncode == 0
        except FileNotFoundError as error:
            output.write(f"not installed: {error}\n")
            passed = False
    minutes: float = (time.monotonic() - start) / 60
    print(f"    {'passed' if passed else 'FAILED'} in {minutes:.1f} min;"
          f" log {log}", flush=True)
    return passed, minutes


def main() -> int:
    """Run every step and print the summary.

    Returns:
    * (`int`): The exit status: 0 when every step passed.
    """
    # Where everything goes, which must hold nothing yet.
    if len(sys.argv) > 2 or sys.argv[1:2] in (["-h"], ["--help"]):
        print("usage: ./ezpkg_test_all.py [DIR]", file=sys.stderr)
        return 2
    directory: pathlib.Path = (
        pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) == 2
        else pathlib.Path(tempfile.mkdtemp(prefix="ezpkg-all-")))
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        print(f"{directory} is not empty", file=sys.stderr)
        return 2
    print(f"results in {directory}", flush=True)
    home: pathlib.Path = directory / "home"
    seed_pip(home)
    (directory / "ux").mkdir()
    (directory / "email").mkdir()
    python: str = sys.executable

    # Each layer in turn; `friend` only after a good `build`.
    results: list[tuple[str, bool, float, pathlib.Path]] = []
    steps: list[tuple[str, list[str], pathlib.Path | None]] = [
        ("ruff", ["ruff", "check", "."], None),
        ("mypy", ["mypy", "."], None),
        ("suite and coverage",
         [python, "ezpkg_coverage.py", "--children",
          str(directory / "coverage")], home),
        ("ux/drive.py",
         [python, "ux/drive.py", "--ux-dir", str(directory / "ux"),
          str(directory / "ux" / "drive_output.txt")], None),
        ("email build",
         [python, "email_check.py", "build",
          str(directory / "email" / "build")], None),
        ("email friend",
         [python, "email_check.py", "friend",
          str(directory / "email" / "friend"),
          str(directory / "email" / "build" / "out")], None),
    ]
    name: str
    command: list[str]
    run_home: pathlib.Path | None
    for name, command, run_home in steps:
        log: pathlib.Path = directory / (
            name.replace(" ", "_").replace("/", "_") + ".log")
        if name == "email friend" and not results[-1][1]:
            print(f"==> {name}: skipped, since the build failed")
            results.append((name, False, 0.0, log))
            continue
        passed: bool
        minutes: float
        passed, minutes = step(name, command, log, run_home)
        results.append((name, passed, minutes, log))

    # The summary, and where coverage's unrun lines are.
    print("\nSummary:")
    for name, passed, minutes, log in results:
        print(f"  {'passed' if passed else 'FAILED':6}  {minutes:5.1f} min"
              f"  {name:20}  {log}")
    missing: pathlib.Path = directory / "coverage" / "missing.txt"
    if missing.is_file():
        print(f"Unrun lines: {missing}")
    return 0 if all(passed for _, passed, _, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
