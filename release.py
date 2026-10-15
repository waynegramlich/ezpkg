#!/usr/bin/env python3
"""Build the `ezpkg` wheel that the release workflow publishes.

Run as `./release.py TARGET DIRECTORY`, where `TARGET` is `testpypi` or
`pypi`.  The wheel is built by `release_wheel` from `ezpkg_test.py`, so
the tests and the release build the same wheel, and only the wheel is
written into `DIRECTORY`.  Nothing here uploads anything; that is
`.github/workflows/release.yml`'s job.  See `T.wrw`.

* `testpypi`:
  The version is `dev_version()`, such as `0.0.1.dev202610151830`, so
  every rehearsal is new and needs no tag.
* `pypi`:
  The version is `ezpkg.__version__`, and the build is refused unless
  the commit being built carries the tag `v` + that version.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import ezpkg_test

# The distribution name on both indexes, so that the rehearsal publishes
# exactly what the real upload will.
DISTRIBUTION: str = "ezpkg"


def tags_here() -> list[str]:
    """Return the tags on the commit being built.

    Returns:
    * (`list[str]`): The tag names, possibly none.
    """
    # The checkout of a tag fetches the tag itself, so this works in
    # the workflow as well as in a full clone.
    done: subprocess.CompletedProcess[str] = subprocess.run(
        ["git", "tag", "--points-at", "HEAD"],
        capture_output=True, text=True, check=True)
    return done.stdout.split()


def main() -> int:
    """Build the wheel for the target named on the command line.

    Returns:
    * (`int`): The exit status.
    """
    # Exactly two arguments, the first one of the two targets.
    if len(sys.argv) != 3 or sys.argv[1] not in ("testpypi", "pypi"):
        print("usage: release.py {testpypi|pypi} DIRECTORY",
              file=sys.stderr)
        return 2
    target: str = sys.argv[1]
    directory: Path = Path(sys.argv[2])

    # A real release must be built from the commit its tag names.
    version: str
    if target == "pypi":
        version = ezpkg_test.VERSION
        tag: str = f"v{version}"
        if tag not in tags_here():
            print(f"release.py: HEAD is not tagged {tag}",
                  file=sys.stderr)
            return 1
    else:
        version = ezpkg_test.dev_version()

    # `release_wheel` writes a copy of the module beside the wheel, and
    # the upload takes everything in the directory, so it builds
    # elsewhere and only the wheel is copied over.
    directory.mkdir(parents=True, exist_ok=True)
    scratch: str
    with tempfile.TemporaryDirectory() as scratch:
        wheel: Path = ezpkg_test.release_wheel(
            Path(scratch), distribution=DISTRIBUTION, version=version)
        shutil.copy2(wheel, directory / wheel.name)
    print(directory / wheel.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
