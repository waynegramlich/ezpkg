#!/usr/bin/env python3
"""Check a published `ezpkg` by running the Quick Start as a new user.

Run as `./release_check.py [--python PYTHON] [--console] TARGET
[VERSION]`, where `TARGET` is `testpypi` or `pypi`.  `VERSION` defaults to the one the newest
successful `release` run for `TARGET` built, found with `gh`; not the
index's own newest, which is cached for up to 15 minutes and so names
the previous upload just when a check is wanted.  A copy of `quick_start.py` runs outside the project, with a
fresh `HOME`, no `PYTHONPATH` and no `PIP_*` settings, so nothing of
this project's can stand in for what was published.  It passes when
the cow appears and the `ezpkg` installed is the version asked for.
See `T.uttat`.

`--python` runs the Quick Start with another interpreter than the one
running this script, such as python.org's macOS Python before its
`Install Certificates.command`, which cannot fetch from the indexes
the way this script must (`I.btosc`, `T.gar`).

`--console` runs it on a terminal of its own, a pseudoterminal on
Linux and macOS and a Windows pseudoconsole through `pywinpty`, and
answers `y` when the download prompt appears; the check then also fails
if the prompt never does.  Without it there is no terminal, and the
prompt answers yes by itself.  See `I.owenabd`.

* `pypi`:
  Exactly what a stranger gets: the bootstrap fetches `ezpkg` itself,
  the newest that pypi.org's JSON API names, which may lag an upload
  by a few minutes.
* `testpypi`:
  Only the `ezpkg` wheel comes from test.pypi.org, downloaded here,
  checked against its SHA-256 and put where `2026-10-23` keeps it,
  `~/.ezpkg/ezpkg.whl`, since the bootstrap asks pypi.org only; `pip`
  and `cowsay` still come from pypi.org.  Anybody can upload to test.pypi.org, and its `cowsay` is a
  stranger's, so the two indexes are never searched together.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

# The JSON API of each index.
JSON_APIS: dict[str, str] = {
    "testpypi": "https://test.pypi.org/pypi",
    "pypi": "https://pypi.org/pypi",
}

# What `quick_start.py` prints when it works.
COW: str = "EZPkg works!"

# The end of the download prompt, which `--console` answers: short,
# so that a console wrapping the long line cannot split it.
PROMPT: str = "=>Explain]"

# A terminal's control sequences, which a Windows pseudoconsole mixes
# into what it passes on.
CONTROL: re.Pattern[str] = re.compile(r"\x1b(\[[0-?]*[ -/]*[@-~]|\][^\x07]*\x07|.)")


def on_a_terminal(command: list[str], cwd: Path,
                  environment: dict[str, str]) -> tuple[int, str, bool]:
    """Run a command on a terminal of its own, answering the prompt.

    Arguments:
    * `command` (`list[str]`):
      The command.
    * `cwd` (`Path`):
      Where to run it.
    * `environment` (`dict[str, str]`):
      Its environment.

    Returns:
    * (`tuple[int, str, bool]`): The exit status, everything shown on
      the terminal with control sequences removed, and whether the
      prompt appeared.
    """
    # Windows: a pseudoconsole, which is what `CONIN$` then reaches.
    seen: str = ""
    asked: bool = False
    if os.name == "nt":
        import winpty  # type: ignore[import-not-found]  # Windows only.
        child: Any = winpty.PtyProcess.spawn(command, cwd=str(cwd),
                                             env=environment)
        while True:
            try:
                seen += CONTROL.sub("", child.read(4096))
            except EOFError:
                break
            if not asked and PROMPT in seen:
                child.write("y\r\n")
                asked = True
        child.wait()
        return child.exitstatus, seen, asked

    # Elsewhere a pseudoterminal, made the child's controlling terminal
    # by a launcher so that `/dev/tty` reaches it, as in `ezpkg_test.py`.
    import pty
    import select
    master: int
    slave: int
    master, slave = pty.openpty()
    launcher: str = ("import os, sys\n"
                     "os.login_tty(int(sys.argv[1]))\n"
                     "os.execv(sys.argv[2], sys.argv[2:])\n")
    process: subprocess.Popen[bytes] = subprocess.Popen(
        [sys.executable, "-c", launcher, str(slave), *command],
        cwd=cwd, env=environment, pass_fds=(slave,))
    os.close(slave)
    deadline: float = time.monotonic() + 600
    while time.monotonic() < deadline:
        ready: list[int] = select.select([master], [], [], 1.0)[0]
        if not ready:
            if process.poll() is not None:
                break
            continue
        try:
            block: bytes = os.read(master, 4096)
        except OSError:
            break
        if not block:
            break
        seen += CONTROL.sub("", block.decode(errors="replace"))
        if not asked and PROMPT in seen:
            os.write(master, b"y\n")
            asked = True
    os.close(master)
    return process.wait(timeout=60), seen, asked


def built_version(target: str) -> str:
    """Return the version the newest successful release run built.

    `release.yml` titles each run `release TARGET`, and saves the wheel
    as the artifact `dist`, whose file name carries the version.

    Arguments:
    * `target` (`str`):
      `testpypi` or `pypi`.

    Returns:
    * (`str`): The version, such as `0.0.1.dev202610151925`.

    Raises:
    * `LookupError`:
      If no such run exists, or its artifact has expired (after 90
      days), in which case the version has to be given by hand.
    """
    # Newest first; earlier runs, titled only `release`, never match.
    listed: subprocess.CompletedProcess[str] = subprocess.run(
        ["gh", "run", "list", "--workflow", "release.yml",
         "--status", "success", "--limit", "50",
         "--json", "databaseId,displayTitle"],
        capture_output=True, text=True, check=True)
    runs: list[dict[str, Any]] = [
        run for run in json.loads(listed.stdout)
        if run["displayTitle"] == f"release {target}"]
    if not runs:
        raise LookupError(f"no successful release run for {target}")

    # The wheel's name is `ezpkg-VERSION-py3-none-any.whl`.
    run_id: str = str(runs[0]["databaseId"])
    scratch: str
    with tempfile.TemporaryDirectory() as scratch:
        fetched: subprocess.CompletedProcess[str] = subprocess.run(
            ["gh", "run", "download", run_id, "--name", "dist",
             "--dir", scratch],
            capture_output=True, text=True, check=False)
        wheels: list[Path] = sorted(Path(scratch).glob("ezpkg-*.whl"))
        if fetched.returncode != 0 or len(wheels) != 1:
            raise LookupError(f"run {run_id} has no wheel to read; "
                              "give the version by hand")
        return wheels[0].name.split("-")[1]


def wheel_info(target: str, version: str | None, attempts: int = 4,
               pause: float = 10.0) -> dict[str, Any]:
    """Return the index's record of the `ezpkg` wheel.

    A release just uploaded can be answered "not found" for a while:
    on 2026-10-16 test.pypi.org gave a 404 for one, two minutes after
    the same question had been answered.  So a failed request is tried
    again, a few times, before it counts.

    Arguments:
    * `target` (`str`):
      `testpypi` or `pypi`.
    * `version` (`str | None`):
      The version wanted, or `None` for the newest.
    * `attempts` (`int`):
      How many times to ask.
    * `pause` (`float`):
      Seconds to wait between them.

    Returns:
    * (`dict[str, Any]`): The JSON API's entry for the wheel, plus
      `version`.

    Raises:
    * `LookupError`:
      If that release has no wheel.
    * `urllib.error.URLError`:
      If every attempt failed.
    """
    # The newest is `/ezpkg/json`, which is cached; a particular one is
    # one level deeper, and is usually fresh.
    url: str = f"{JSON_APIS[target]}/ezpkg"
    url += f"/{version}/json" if version else "/json"
    release: dict[str, Any] = {}
    attempt: int
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                release = json.load(response)
            break
        except urllib.error.URLError:
            if attempt == attempts - 1:
                raise
            print(f"release_check: {url} did not answer; asking again in "
                  f"{pause:.0f} s", file=sys.stderr)
            time.sleep(pause)
    entry: dict[str, Any]
    for entry in release["urls"]:
        if entry["filename"].endswith(".whl"):
            return dict(entry, version=release["info"]["version"])
    raise LookupError(f"ezpkg {release['info']['version']} has no wheel")


def main() -> int:
    """Run the Quick Start against the named index.

    Returns:
    * (`int`): The exit status.
    """
    # Options, then a target, and perhaps a version.
    arguments: list[str] = sys.argv[1:]
    python: str = sys.executable
    console: bool = False
    while arguments[:1] in (["--python"], ["--console"]):
        if arguments[0] == "--console":
            console = True
            arguments = arguments[1:]
        elif len(arguments) >= 2:
            python = arguments[1]
            arguments = arguments[2:]
        else:
            break
    if not 1 <= len(arguments) <= 2 or arguments[0] not in JSON_APIS:
        print("usage: release_check.py [--python PYTHON] [--console] "
              "{testpypi|pypi} [VERSION]", file=sys.stderr)
        return 2
    target: str = arguments[0]
    info: dict[str, Any]
    try:
        info = wheel_info(target, arguments[1] if len(arguments) == 2
                          else built_version(target))
    except (urllib.error.URLError, LookupError,
            subprocess.CalledProcessError) as error:
        print(f"release_check: cannot check {target}: {error}",
              file=sys.stderr)
        return 1
    version: str = info["version"]
    print(f"release_check: ezpkg {version} from {target}", file=sys.stderr)

    here: Path = Path(__file__).resolve().parent
    scratch: Path = Path(tempfile.mkdtemp(prefix="release_check-"))
    home: Path = scratch / "home"
    run: Path = scratch / "run"
    home.mkdir()
    run.mkdir()
    shutil.copy2(here / "quick_start.py", run)

    # A clean environment.  The constraint pins `ezpkg` to the version
    # being checked, which matters once pypi.org has a release newer
    # than a test.pypi.org rehearsal.
    environment: dict[str, str] = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("PIP_", "EZPKG_"))
        and key not in ("PYTHONPATH", "VIRTUAL_ENV")}
    constraint: Path = scratch / "constraint.txt"
    constraint.write_text(f"ezpkg=={version}\n", encoding="utf-8")
    # `Path.home()` reads `HOME`, except on Windows, where it reads
    # `USERPROFILE`.
    environment.update(HOME=str(home), USERPROFILE=str(home),
                       PIP_CONSTRAINT=str(constraint))

    # For test.pypi.org, the one wheel is fetched here, kept where the
    # bootstrap keeps it, and offered to `pip` as a local file.
    if target == "testpypi":
        wheels: Path = scratch / "wheels"
        wheels.mkdir()
        data: bytes
        with urllib.request.urlopen(info["url"], timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != info["digests"]["sha256"]:
            print(f"release_check: {info['filename']} fails its SHA-256 "
                  "check", file=sys.stderr)
            return 1
        (wheels / info["filename"]).write_bytes(data)
        environment["PIP_FIND_LINKS"] = str(wheels)
        (home / ".ezpkg").mkdir()
        (home / ".ezpkg" / "ezpkg.whl").write_bytes(data)

    # On a terminal the prompt is answered; with none it answers yes
    # by itself.
    status: int
    shown: str
    asked: bool = False
    if console:
        # `CI`, which runners set, would tell `ezpkg` nobody is there.
        environment.pop("CI", None)
        status, shown, asked = on_a_terminal(
            [python, "quick_start.py"], run, environment)
        sys.stdout.write(shown)
    else:
        # On Windows a child shares the console, which `ezpkg` finds
        # and asks on, so it is detached from it (`I.owenabd`).
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [python, "quick_start.py"], cwd=run, env=environment,
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            check=False,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        status, shown = done.returncode, done.stdout
        sys.stderr.write(done.stderr)
        sys.stdout.write(done.stdout)
    sys.stdout.flush()

    # Passed only if it ran, the cow appeared and the right `ezpkg` did it.
    # `2026-10-23` keeps `ezpkg` as `ezpkg.whl`; older bootstraps installed it.
    installed: list[str] = sorted(
        path.name for path in (home / ".ezpkg").glob("ezpkg-*.dist-info"))
    kept: Path = home / ".ezpkg" / "ezpkg.whl"
    if kept.is_file():
        with zipfile.ZipFile(kept) as archive:
            installed += sorted({
                name.split("/")[0] for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")})
    problems: list[str] = []
    if status != 0:
        problems.append(f"exit status {status}")
    if COW not in shown:
        problems.append(f"no {COW!r} in the output")
    if console and not asked:
        problems.append(f"no {PROMPT!r} on the terminal")
    if installed != [f"ezpkg-{version}.dist-info"]:
        problems.append(f"installed {installed}, not ezpkg {version}")
    # A `pip` fetched this run is the newest, so it is stamped as such,
    # or the second run pauses to look for a newer one (2026-10-25).
    cache: Path = home / ".ezpkg"
    if (cache / "pip.whl").is_file() and not (cache / "last_pip").is_file():
        problems.append("a fresh pip.whl but no last_pip, so the second "
                        "run would look for a newer pip")
    if problems:
        print(f"release_check: FAILED ({'; '.join(problems)}); "
              f"left {scratch}", file=sys.stderr)
        return 1
    shutil.rmtree(scratch)
    print(f"release_check: PASSED, ezpkg {version} from {target}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
