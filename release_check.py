#!/usr/bin/env python3
"""Check a published `ezpkg` by running the Quick Start as a new user.

Run as `./release_check.py TARGET [VERSION]`, where `TARGET` is
`testpypi` or `pypi` and `VERSION` defaults to the newest on that
index.  A copy of `quick_start.py` runs outside the project, with a
fresh `HOME`, no `PYTHONPATH` and no `PIP_*` settings, so nothing of
this project's can stand in for what was published.  It passes when
the cow appears and the `ezpkg` installed is the version asked for.
See `T.uttat`.

* `pypi`:
  Exactly what a stranger gets: the bootstrap fetches `ezpkg` itself.
* `testpypi`:
  Only the `ezpkg` wheel comes from test.pypi.org, downloaded here and
  checked against its SHA-256; `pip` and `cowsay` still come from
  pypi.org.  Anybody can upload to test.pypi.org, and its `cowsay` is a
  stranger's, so the two indexes are never searched together.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# The JSON API of each index.
JSON_APIS: dict[str, str] = {
    "testpypi": "https://test.pypi.org/pypi",
    "pypi": "https://pypi.org/pypi",
}

# What `quick_start.py` prints when it works.
COW: str = "EZPkg works!"


def wheel_info(target: str, version: str | None) -> dict[str, Any]:
    """Return the index's record of the `ezpkg` wheel.

    Arguments:
    * `target` (`str`):
      `testpypi` or `pypi`.
    * `version` (`str | None`):
      The version wanted, or `None` for the newest.

    Returns:
    * (`dict[str, Any]`): The JSON API's entry for the wheel, plus
      `version`.

    Raises:
    * `LookupError`:
      If that release has no wheel.
    """
    # The newest is `/ezpkg/json`; a particular one is one level deeper.
    url: str = f"{JSON_APIS[target]}/ezpkg"
    url += f"/{version}/json" if version else "/json"
    with urllib.request.urlopen(url, timeout=30) as response:
        release: dict[str, Any] = json.load(response)
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
    # A target, and perhaps a version.
    arguments: list[str] = sys.argv[1:]
    if not 1 <= len(arguments) <= 2 or arguments[0] not in JSON_APIS:
        print("usage: release_check.py {testpypi|pypi} [VERSION]",
              file=sys.stderr)
        return 2
    target: str = arguments[0]
    info: dict[str, Any]
    try:
        info = wheel_info(
            target, arguments[1] if len(arguments) == 2 else None)
    except (urllib.error.URLError, LookupError) as error:
        print(f"release_check: no ezpkg on {target}: {error}",
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
    environment.update(HOME=str(home), PIP_CONSTRAINT=str(constraint))

    # For test.pypi.org, the one wheel is fetched here and offered to
    # `pip` as a local file.
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

    # No terminal, so the download prompt answers yes by itself.
    done: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "quick_start.py"], cwd=run, env=environment,
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        check=False)
    sys.stderr.write(done.stderr)
    sys.stdout.write(done.stdout)
    sys.stdout.flush()

    # Passed only if it ran, the cow appeared and the right `ezpkg` did it.
    installed: list[str] = sorted(
        path.name for path in (home / ".ezpkg").glob("ezpkg-*.dist-info"))
    problems: list[str] = []
    if done.returncode != 0:
        problems.append(f"exit status {done.returncode}")
    if COW not in done.stdout:
        problems.append(f"no {COW!r} in the output")
    if installed != [f"ezpkg-{version}.dist-info"]:
        problems.append(f"installed {installed}, not ezpkg {version}")
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
