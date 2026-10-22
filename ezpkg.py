# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
#
# The lines above are standard PEP 723 metadata, read by tools such as
# `uv` and by `EZPkg` itself.  See `README.md` for more details.

"""Automatic Package Fetching for One-File Programs

This package allows a Python program to find its missing Python packages and
automatically download and import them in conjunction with the `pip` program.
Read `README.md` or [EZPkg](https://pypi.org/project/ezpkg/) for more details.

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

# Every import below is in the standard library, and none of them comes
# from a package a distribution can leave out.
import ast
import atexit
import dataclasses
import datetime
import difflib
import hashlib
import html
import importlib
import importlib.metadata
import importlib.util
import inspect
import io
import json
import os
import platform
import re
import select
import shutil
import site
import subprocess
import sys
import sysconfig
import tempfile
import textwrap
import time
import tokenize
import tomllib
import urllib.error
import urllib.request
import zipapp
import zipfile
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import IO, Any, overload

# The one place the version is written down.  `bootstrap.py` prints it
# after importing, and `release_wheel` in the test suite writes the
# wheel's version over it in the copy that it packages.
__version__: str = "0.0.1"

# How many times `EZPkg.consent` will put the same question, when the
# answer is neither yes nor no.  Bounded, so that a terminal feeding
# nonsense cannot keep a program alive indefinitely.
ATTEMPTS: int = 3

# The widest a message to the person running a program is wrapped to,
# narrower still on a narrower terminal (`T.abfd`).
LINE_WIDTH: int = 79

# Where to read about `EZPkg`, named after the list of what it stored.
HOME_PAGE: str = "https://pypi.org/project/ezpkg/"

# How long a question waits for its answer before taking it as no.  On
# Windows a program started by Task Scheduler, a CI system or a service
# often has a console with nobody at it, and would otherwise wait for
# ever (`I.owenabd`).  `EZPKG_ANSWER_SECONDS` shortens it, for tests and
# `ux/drive.py` only (Wayne, 2026-10-19).
ANSWER_SECONDS: float = 300.0

# How long something has to have been lying about before it is taken for
# litter, and how often the cache is swept.  The grace period is about
# concurrency rather than tidiness: a download in progress lives under
# `pending/`, and an unpacked tree appears in `versions/` a moment before
# the record naming it is written, so anything young may belong to a
# program that is still running.  A day is far longer than either window
# and short enough to keep a crashed run's leftovers from accumulating.
# See `T.gc`.
CULL_GRACE: float = 86400.0
CULL_INTERVAL: float = 86400.0

# How long anything in the cache may go unused before `cull` takes it:
# a request and the packages that answered it, a scan, the record of a
# program that no longer exists.  One number for all of it, 30 days
# unless a program's `prog.py.toml` sets `cull-days` for what that
# program holds (Wayne, 2026-10-22; it was six months).  The yes and the
# stash of a program that still exists never go.  See `T.gc`.
CULL_DAYS: float = 30.0 * 86400.0

# How often the private `pip` is checked for a newer release.  Weekly, as
# `pip` checks itself, because each check asks the index and may fetch
# 1.8 MB, while `pip` releases come every month or two.  See issue
# `I.spinu` in `ISSUES/`.
PIP_INTERVAL: float = 7.0 * 86400.0

# Every bootstrap this project has published, by `bootstrap_fingerprint`,
# oldest first, so the last is the current one.  Publishing a changed
# bootstrap means adding its fingerprint here; the test suite renders
# the shipping case as pasted and fails until the last entry matches it.  Old
# entries stay, because they are how a stale copy is recognised.  See
# `T.fbanwiis`.
BOOTSTRAPS: dict[str, str] = {
    "46336be666731d6a8999d4233d51b99a0cc327d479e57ece2f7b003290ffa466":
        "nopip3 of 2026-10-02",
    "1bbfbc6633ef35ce5e2c5bb742465cff84b0c89c13af3e3a97363f81daf1d0a3":
        "nopip4 of 2026-10-10",
    "4512ebb40d8c29285f226215e273a7f0eb320a6a6cc3d38bc701eccddd28f2a0":
        "nopip5 of 2026-10-12",
    "c12d783a7cbae0de29b7b5cf3a864c627e0e76d962ed31272f6a1cec8bf9c5f1":
        "nopip6 of 2026-10-16",
    "670d697c070c800990a8b63cd25327e7470d16552c4e9e70b4706cb4a46b2d25":
        "nopip7 of 2026-10-17",
    "d200c60b0ca90f33516417eeb799cf09c86d313a863f2fca3c16a46d3d47e9aa":
        "nopip8 of 2026-10-20",
}

# The constructor writes this into the cache as `remove.py`, so that
# removing the cache is one command that is the same everywhere, and
# never an `rm -rf` handed to a stranger (Wayne, `ux22`).  It removes
# only a directory that looks like a cache, and moves out of it first,
# since Windows cannot remove the directory a process is in.
REMOVE_SCRIPT: str = '''#!/usr/bin/env python3
"""Remove this `ezpkg` cache, and everything `ezpkg` downloaded into it.

Written by `ezpkg` (https://pypi.org/project/ezpkg/).  It is always
safe: a program that needs a package again downloads it again.
"""

import os
import shutil
import sys
from pathlib import Path

here: Path = Path(__file__).resolve().parent
# As `ezpkg` shows it: `~/.ezpkg`, except on Windows, which has no `~`.
shown: str = str(here)
if os.name != "nt" and here.is_relative_to(Path.home()):
    shown = "~/" + here.relative_to(Path.home()).as_posix()
if here == Path.home() or not (here / "versions").is_dir():
    sys.exit(f"`{shown}` does not look like an `ezpkg` cache, so it is "
             f"left alone.")
os.chdir(here.parent)
shutil.rmtree(here, ignore_errors=True)
if here.exists():
    sys.exit(f"`{shown}` could not be removed completely; a program may "
             f"still be using it.")
print(f"Removed `{shown}`.")
'''

# The constructor writes this into the cache as `list.py`, so that
# anybody can see what `ezpkg` keeps there and for whom, without being
# asked anything (Wayne, 2026-10-22: an end user could hold a lot and not
# know it).  Standard library only, like `remove.py`.
LIST_SCRIPT: str = '''#!/usr/bin/env python3
"""List what this `ezpkg` cache holds, and for which programs.

Written by `ezpkg` (https://pypi.org/project/ezpkg/).  It changes
nothing.  `ezpkg` removes what nothing has used for 30 days (or a
program's own `cull-days`), and `remove.py` removes everything.
"""

import json
import os
import time
from pathlib import Path

here: Path = Path(__file__).resolve().parent
# As `ezpkg` shows it: `~/.ezpkg`, except on Windows, which has no `~`.
shown: str = str(here)
if os.name != "nt" and here.is_relative_to(Path.home()):
    shown = "~/" + here.relative_to(Path.home()).as_posix()


def size(path: Path) -> int:
    """Return the bytes under a path."""
    if path.is_file():
        return path.stat().st_size
    return sum(one.stat().st_size for one in path.rglob("*")
               if one.is_file() and not one.is_symlink())


def megabytes(count: int) -> str:
    """Return a size as people read it."""
    return f"{count / 1e6:,.1f} MB"


# Each request's trees, by the request's hash.
trees: dict[str, list[str]] = {}
for record in (here / "requests").glob("*.json"):
    try:
        trees[record.stem] = list(json.loads(record.read_text())["trees"])
    except (OSError, ValueError, KeyError, TypeError):
        continue

# Each program, newest use first.
rows: list[tuple[float, str]] = []
for record in (here / "develop").glob("*.json"):
    try:
        kept: dict = json.loads(record.read_text())
        used: float = record.stat().st_mtime
    except (OSError, ValueError):
        continue
    program: Path = Path(str(kept.get("program", "")))
    how: str = ("developed here" if "stash" in kept
                else "agreed to" if kept.get("agreed") else "seen")
    held: int = sum(size(here / "versions" / tree)
                    for request in kept.get("requests", []) or []
                    for tree in trees.get(str(request), [])
                    if (here / "versions" / tree).exists())
    rows.append((used, f"{program}\\n    {how}, last run "
                 f"{time.strftime('%Y-%m-%d', time.localtime(used))}, "
                 f"{megabytes(held)}"
                 + ("" if program.is_file() else ", no longer there")))
print(f"`{shown}` holds {megabytes(size(here))}.")
if rows:
    print("Programs (the sizes overlap where they share packages):")
for _, row in sorted(rows, reverse=True):
    print(row)
'''

# The Quick Start program from `README.md`, which the constructor writes
# into the cache as `quick_start.py`, so that somebody who has run one
# program can open the template in an editor and copy its parts into
# their own.  `quick_start.py` in the repository is the authority and
# the test suite fails until this matches it.  The two fence lines are
# written with `\x23`, which is `#`, so that this file's own source
# holds only one PEP 723 block: two would be refused as ambiguous.
QUICK_START: str = '''#!/usr/bin/env python3
# Part 1: The packages this program needs.
\x23 /// script
# requires-python = ">=3.11"
# dependencies = ["ezpkg>=0.0.1.dev0,<0.1", "cowsay"]
\x23 ///
"""Try `EZPkg`: fetch the `cowsay` package on first use, then run."""

# Part 2: The EZPkg bootstrap.  Paste all of it, `# Begin` to `# End`,
# below your docstring and any `from __future__` lines.
# Begin the EZPkg bootstrap.  Never edit it.
import hashlib
import importlib
import json
import pathlib
import subprocess
import sys
import urllib.request as req
try:  # Do not edit try block!  See https://pypi.org/project/ezpkg/
    s = "find ezpkg"; t = pathlib.Path.home()/".ezpkg"; w = t/"ezpkg.whl"
    def g(u):  # Fetch u, with curl if this Python has no certificates.
        try: return req.urlopen(u, None, 60).read()
        except req.URLError as y: z = y  # As on python.org's macOS Python.
        try: return subprocess.run(["curl", "-fsSL", u],
                                   capture_output=True, check=True).stdout
        except Exception: raise z from None
    try: m = None; m = importlib.import_module("ezpkg")  # Already importable?
    except ImportError: pass
    if m is None and not w.is_file():  # Not downloaded yet.
        s = "download ezpkg"; d = g("https://pypi.org/pypi/ezpkg/json")
        e = next(e for e in json.loads(d)["urls"] if e["url"][-4:] == ".whl")
        r = g(e["url"])
        if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
            raise ValueError(f"{e['filename']} fails its SHA-256 check")
        t.mkdir(parents=True, exist_ok=True); p = t/"ezpkg.part"
        p.write_bytes(r); p.replace(w)  # The rename is atomic.
    if m is None:  # Python imports it straight from the wheel.
        s = "import ezpkg"; sys.path.insert(0, str(w))
        m = importlib.import_module("ezpkg")
    s = "fetch packages"; m.EZPkg().install(bootstrap="nopip8")
except Exception as x:
    raise SystemExit(f"ezpkg: {s} failed: {x!r}")  # Do not edit try block!
# End the EZPkg bootstrap.  Your imports go below it.

# Part 3: Your imports, all after the bootstrap.
import cowsay  # type: ignore[import-not-found]  # For mypy.

# Part 4: The program itself.
cowsay.cow("EZPkg works!")
print(f"The cow above was drawn by cowsay {cowsay.__version__}.")
'''


# The text of every published bootstrap that names `ezpkg`, as
# `find_bootstrap` returns it, apart from the current one, which is
# `QUICK_START`'s own.  An edited copy is compared with the nearest, to
# say which lines changed (`T.reb`).  `nopip3` and `nopip4` named
# `alt_venv`, so no program that reaches this module carries them.
OLD_BOOTSTRAP_TEXTS: dict[str, str] = {
    "nopip5 of 2026-10-12": '''try:  # Do not edit try block!  See https://pypi.org/project/ezpkg/
    s = "find home"; t = pathlib.Path.home()/".ezpkg"; w = t/"pip.whl"
    m = None
    try: m = importlib.import_module("ezpkg")  # Already importable?
    except ImportError: pass
    if m is None and not (t/"ezpkg").is_dir():  # Not installed yet.
        s = "choose pip"; v = sys.version_info[1]
        d = json.load(req.urlopen("https://pypi.org/pypi/pip/json", None, 30))
        e = max((e for f in d["releases"].values() for e in f  # Newest pip ...
                 if e["url"][-4:] == ".whl" and not e["yanked"]
                 and (q := e["requires_python"] or "")[:4] == ">=3."
                 and "," not in q and int(q.split(".")[1]) <= v),
                key=lambda e: e["upload_time"])  # ... whose floor we meet.
        s = "download pip"; r = req.urlopen(e["url"], None, 60).read()
        if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
            raise ValueError(f"{e['filename']} fails its SHA-256 check")
        t.mkdir(parents=True, exist_ok=True); p = t/"pip.part"
        p.write_bytes(r); p.replace(w)  # The rename is atomic.
        s = "install ezpkg"; subprocess.run([
            sys.executable, w/"pip", "install", "--no-input", "-t", t,
            "--disable-pip-version-check", "ezpkg"], check=True, stdout=2)
    if m is None:
        s = "import ezpkg"; sys.path.insert(0, str(t))
        importlib.invalidate_caches(); m = importlib.import_module("ezpkg")
    s = "fetch packages"; m.EZPkg().install(bootstrap="nopip5")
except Exception as x:
    raise SystemExit(f"ezpkg: {s} failed: {x!r}")''',
    "nopip6 of 2026-10-16": '''try:  # Do not edit try block!  See https://pypi.org/project/ezpkg/
    s = "find home"; t = pathlib.Path.home()/".ezpkg"; w = t/"pip.whl"
    m = None
    def g(u):  # Fetch u, with curl if this Python has no certificates.
        try: return req.urlopen(u, None, 60).read()
        except req.URLError as y: z = y  # As on python.org's macOS Python.
        try: return subprocess.run(["curl", "-fsSL", u],
                                   capture_output=True, check=True).stdout
        except Exception: raise z from None
    try: m = importlib.import_module("ezpkg")  # Already importable?
    except ImportError: pass
    if m is None and not (t/"ezpkg").is_dir():  # Not installed yet.
        s = "choose pip"; v = sys.version_info[1]
        d = json.loads(g("https://pypi.org/pypi/pip/json"))
        e = max((e for f in d["releases"].values() for e in f  # Newest pip ...
                 if e["url"][-4:] == ".whl" and not e["yanked"]
                 and (q := e["requires_python"] or "")[:4] == ">=3."
                 and "," not in q and int(q.split(".")[1]) <= v),
                key=lambda e: e["upload_time"])  # ... whose floor we meet.
        s = "download pip"; r = g(e["url"])
        if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
            raise ValueError(f"{e['filename']} fails its SHA-256 check")
        t.mkdir(parents=True, exist_ok=True); p = t/"pip.part"
        p.write_bytes(r); p.replace(w)  # The rename is atomic.
        s = "install ezpkg"; subprocess.run([
            sys.executable, w/"pip", "install", "--no-input", "-t", t,
            "--disable-pip-version-check", "ezpkg"], check=True, stdout=2)
    if m is None:
        s = "import ezpkg"; sys.path.insert(0, str(t))
        importlib.invalidate_caches(); m = importlib.import_module("ezpkg")
    s = "fetch packages"; m.EZPkg().install(bootstrap="nopip6")
except Exception as x:
    raise SystemExit(f"ezpkg: {s} failed: {x!r}")''',
    "nopip7 of 2026-10-17": '''try:  # Do not edit try block!  See https://pypi.org/project/ezpkg/
    s = "find home"; t = pathlib.Path.home()/".ezpkg"; w = t/"pip.whl"
    m = n = None
    def g(u):  # Fetch u, with curl if this Python has no certificates.
        try: return req.urlopen(u, None, 60).read()
        except req.URLError as y: z = y  # As on python.org's macOS Python.
        try: return subprocess.run(["curl", "-fsSL", u],
                                   capture_output=True, check=True).stdout
        except Exception: raise z from None
    try: m = importlib.import_module("ezpkg")  # Already importable?
    except ImportError: pass
    if m is None and not (t/"ezpkg").is_dir():  # Not installed yet.
        s = "choose pip"; v = sys.version_info[1]
        d = json.loads(g("https://pypi.org/pypi/pip/json"))
        e = max((e for f in d["releases"].values() for e in f  # Newest pip ...
                 if e["url"][-4:] == ".whl" and not e["yanked"]
                 and (q := e["requires_python"] or "")[:4] == ">=3."
                 and "," not in q and int(q.split(".")[1]) <= v),
                key=lambda e: e["upload_time"])  # ... whose floor we meet.
        s = "download pip"; r = g(e["url"])
        if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
            raise ValueError(f"{e['filename']} fails its SHA-256 check")
        t.mkdir(parents=True, exist_ok=True); p = t/"pip.part"
        p.write_bytes(r); p.replace(w)  # The rename is atomic.
        s = "install ezpkg"; n = subprocess.run([sys.executable, w/"pip",
            "install", "--no-input", "-t", t, "--disable-pip-version-check",
            "ezpkg"], check=False, capture_output=True, text=True)
        if n.returncode: raise RuntimeError(n.stderr.strip()[-300:])
    if m is None:
        s = "import ezpkg"; sys.path.insert(0, str(t))
        importlib.invalidate_caches(); m = importlib.import_module("ezpkg")
    s = "fetch packages"; m.EZPkg(pip=n).install(bootstrap="nopip7")
except Exception as x:
    raise SystemExit(f"ezpkg: {s} failed: {x!r}")''',
}


# Where a requirement stops naming a package and starts constraining
# it: a version specifier, an extras list or an environment marker.
SPECIFIER = re.compile(r"[<>=!~\[;\s]")


def requirement_name(requirement: str) -> str:
    """Return the part of a requirement that names the distribution.

    Arguments:
    * `requirement` (`str`):
      A requirement as `pip` spells it.

    Returns:
    * (`str`): Everything before the first specifier, extra or marker.
    """
    # Everything from the first constraint onwards is about versions.
    return SPECIFIER.split(requirement, maxsplit=1)[0].strip()


def import_name(requirement: str) -> str:
    """Guess the import name that a requirement string will provide.

    The guess is the distribution name with punctuation turned into
    underscores, which is right for most packages and wrong for the
    ones that deliberately differ: `python-dateutil` imports as
    `dateutil`, not `python_dateutil`.  Those need the pair form of
    `EZPkg.install`, and a wrong guess shows up immediately as a
    `ModuleNotFoundError` rather than as anything subtle.

    Arguments:
    * `requirement` (`str`):
      A requirement as `pip` spells it, with any version constraint,
      extras or environment marker attached.

    Returns:
    * (`str`): The import name to try.
    """
    # Everything from the first constraint, extra or marker onwards is
    # about which version to fetch, not about what to import.
    return re.sub(r"[-.]+", "_", requirement_name(requirement))


# One clause of a version specifier that `satisfied` can be sure about:
# a comparison against a plain release such as `2.32.0`.  Wildcards,
# `===`, pre-releases and anything else do not match, and so fetch.
CLAUSE = re.compile(r"(==|!=|>=|<=|>|<|~=)\s*(\d+(?:\.\d+)*)")


def satisfied(requirement: str, cache: Path | None = None) -> bool:
    """Report whether a requirement is already met without the cache.

    Under `uv run`, in a virtual environment, or with a package the
    operating system installed, a requirement may already be importable, and
    fetching it again wastes a download and, with no network, fails.
    The installed version is read from its metadata and compared with
    the requirement's specifier.  Only plain releases and the common
    operators are understood: anything else -- an extra, an environment
    marker, a URL, a wildcard, a pre-release, a missing `.dist-info` --
    answers `False`, which fetches exactly as before.  A wrong `True`
    would run the program against the wrong version; a wrong `False`
    costs one download.  See `T.ewar` and `I.apiia`.

    A copy in `EZPkg`'s own cache does not count, though an earlier
    `provide` in this process put it on `sys.path`: the next run starts
    without it, and fetches, so this one must too, or the two would
    run different versions (found by `drive`, 2026-10-17).

    Arguments:
    * `requirement` (`str`):
      A requirement as `pip` spells it.
    * `cache` (`Path | None`):
      The cache whose copies do not count.

    Returns:
    * (`bool`): True only when the installed version certainly meets
      the requirement.
    """
    # Extras, markers and URLs are not this function's to judge.
    name: str = requirement_name(requirement)
    rest: str = requirement[requirement.find(name) + len(name):].strip()
    if not name or any(mark in rest for mark in "[;@"):
        return False

    # Installed at all, and as a plain release, against plain releases?
    try:
        found: str = importlib.metadata.version(name)
        where: Path | None = None if cache is None else Path(str(
            importlib.metadata.distribution(name).locate_file(""))).resolve()
    except importlib.metadata.PackageNotFoundError:
        return False
    if cache is not None and where is not None and where.is_relative_to(
            cache.resolve()):
        return False
    if not re.fullmatch(r"\d+(?:\.\d+)*", found):
        return False
    if not all(CLAUSE.fullmatch(clause) for clause in
               filter(None, (one.strip() for one in rest.split(",")))):
        return False
    return meets(found, rest)


# A version `meets` understands: a release, perhaps a development
# release of it, as `0.0.1.dev202610170307` is on test.pypi.org.
RELEASE: re.Pattern[str] = re.compile(r"(\d+(?:\.\d+)*)(?:\.dev(\d+))?")

# One clause of a specifier `meets` understands.
DEV_CLAUSE: re.Pattern[str] = re.compile(
    r"(==|!=|>=|<=|>|<|~=)\s*(\d+(?:\.\d+)*(?:\.dev\d+)?)")


def meets(version: str, specifier: str) -> bool:
    """Report whether a version certainly meets a specifier.

    Releases and their development releases only, with the common
    operators, which is all this project's own `ezpkg` entries use: a
    development release comes before its release, so `0.0.1.devN` is
    older than `0.0.1`, as PEP 440 orders them.  Anything else is
    `False`.  See `T.eui`.

    Arguments:
    * `version` (`str`):
      A version, such as `0.0.1` or `0.0.1.dev202610170307`.
    * `specifier` (`str`):
      Comma-separated clauses, such as `>=0.0.1.dev0,<0.1`, or empty.

    Returns:
    * (`bool`): True only when every clause holds.
    """
    # A release, padded, then whether it is final, then its number.
    def key(text: str, width: int) -> tuple[tuple[int, ...], int, int]:
        matched: re.Match[str] | None = RELEASE.fullmatch(text)
        assert matched is not None
        parts: list[int] = [int(part) for part in matched.group(1).split(".")]
        dev: str | None = matched.group(2)
        return (tuple(parts + [0] * (width - len(parts))),
                0 if dev is not None else 1, int(dev or 0))

    if not RELEASE.fullmatch(version):
        return False
    have: list[str] = version.split(".dev")[0].split(".")
    clause: str
    for clause in filter(None, (one.strip() for one in specifier.split(","))):
        matched: re.Match[str] | None = DEV_CLAUSE.fullmatch(clause)
        if matched is None:
            return False
        operator: str = matched.group(1)
        want: list[str] = matched.group(2).split(".dev")[0].split(".")
        width: int = max(len(have), len(want))
        mine: tuple[tuple[int, ...], int, int] = key(version, width)
        theirs: tuple[tuple[int, ...], int, int] = key(matched.group(2),
                                                       width)
        holds: bool
        if operator == "~=":
            # `~=2.32.1` is `>=2.32.1` and `==2.32.*`; one number is
            # not allowed.
            if len(want) < 2:
                return False
            holds = mine >= theirs and have[:len(want) - 1] == want[:-1]
        else:
            holds = {"==": mine == theirs, "!=": mine != theirs,
                     ">=": mine >= theirs, "<=": mine <= theirs,
                     ">": mine > theirs, "<": mine < theirs}[operator]
        if not holds:
            return False
    return True


class Declined(RuntimeError):
    """The person asked said no to the packages that arrived.

    A `RuntimeError`, as it always was, for a program calling `install`
    with arguments.  `install()` with none ends the program instead, with
    one line saying so (`T.abfd`).

    Attributes:
    * `said` (`str`):
      That line, such as "Declined, so `~/.ezpkg` has been removed and
      `prog.py` did not run."
    """

    def __init__(self, message: str, said: str = "") -> None:
        """Keep the line to say, beside the message."""
        super().__init__(message)
        self.said: str = said


class Unapproved(RuntimeError):
    """A wheel arrived that Part 1's `checksums` do not name.

    Usually an author sent the `prog.py` they work on, not its release,
    and this computer needs a package theirs never fetched (`colorama`
    on Windows).  A `RuntimeError`, as it always was; the end user's
    line comes from `pin` (`T.ee`).

    Attributes:
    * `pin` (`str`):
      The wheel's name and version, such as `colorama==0.4.6`.
    """

    def __init__(self, message: str, pin: str) -> None:
        """Keep the pin beside the message."""
        super().__init__(message)
        self.pin: str = pin


def shown(path: Path) -> str:
    """Return a path as a person reads it: `~/.ezpkg`, not `/home/...`.

    Windows has no `~`, so there the path is shown in full (`T.abfd`).

    Arguments:
    * `path` (`Path`):
      Any path.

    Returns:
    * (`str`): The path, under `~` when it is inside the home directory.
    """
    # Only where a shell would understand the `~`.
    if os.name == "nt":
        return str(path)
    try:
        return "~/" + path.relative_to(Path.home()).as_posix()
    except ValueError:
        return str(path)


def columns(stream: IO[str]) -> int:
    """Return the width to wrap a message to on `stream`.

    The narrower of the terminal and `LINE_WIDTH`, because a program's
    name, and so a message's length, is not known in advance (`T.abfd`).

    Arguments:
    * `stream` (`IO[str]`):
      Where the message goes.

    Returns:
    * (`int`): The width, in characters.
    """
    # A file, a pipe or a `StringIO` has no size, so takes the default.
    try:
        width: int = os.get_terminal_size(stream.fileno()).columns
    except (OSError, ValueError, AttributeError):
        return LINE_WIDTH
    return min(width, LINE_WIDTH) if width > 0 else LINE_WIDTH


def wrapped(text: str, width: int) -> str:
    """Return `text` filled to `width`, never breaking a word or a path.

    Arguments:
    * `text` (`str`):
      One paragraph.
    * `width` (`int`):
      The longest line wanted; a longer word runs long.

    Returns:
    * (`str`): The paragraph, with no trailing newline.
    """
    # A backquoted path split at a hyphen would read as two.
    return textwrap.fill(text, width, break_long_words=False,
                         break_on_hyphens=False)


def cut(line: str, width: int) -> str:
    """Return `line` cut to `width` with `...` when it is longer.

    Arguments:
    * `line` (`str`):
      One line.
    * `width` (`int`):
      The longest line wanted.

    Returns:
    * (`str`): The line, at most `width` characters.
    """
    # The cut lands before trailing spaces, so `...` follows a word.
    return line if len(line) <= width else line[:width - 3].rstrip() + "..."


def metadata_fields(text: str) -> dict[str, str]:
    """Return a package's `Name`, `Version` and `Summary`, made safe.

    The headers end at the first blank line; anything after is the long
    description, which may well contain a line starting `Summary:`.  The
    text is the uploader's, so everything unprintable is removed: an
    escape sequence printed beside a question could rewrite it.

    Arguments:
    * `text` (`str`):
      The contents of a `METADATA` file.

    Returns:
    * (`dict[str, str]`): Whichever of the three headers it has.
    """
    # The first of each wins, as for any e-mail style header.
    fields: dict[str, str] = {}
    line: str
    for line in text.splitlines():
        if not line.strip():
            break
        key: str
        separator: str
        value: str
        key, separator, value = line.partition(":")
        if separator and key in ("Name", "Version", "Summary") and (
                key not in fields):
            fields[key] = "".join(one for one in value.strip()
                                  if one.isprintable())
    return fields


def program_name() -> str:
    """Return the running program's file name, for messages.

    Returns:
    * (`str`): Such as `prog.py`, or `this program` when it has no file.
    """
    # The interactive interpreter and `-c` have none.
    program: Path | None = main_path()
    return program.name if program is not None else "this program"


def name_of(name: str) -> str:
    """Return a program's name as the questions show it, in backticks.

    Arguments:
    * `name` (`str`):
      From `program_name`; `this program` is left bare.

    Returns:
    * (`str`): Such as `` `prog.py` ``.
    """
    return f"`{name}`" if main_path() is not None else name


def main_path() -> Path | None:
    """Return the file the running program was started from.

    `sys.modules["__main__"].__file__` rather than walking frames with
    `inspect`, because the main module is exactly what is wanted and
    asking for it directly cannot pick the wrong frame.

    There is often no such file.  The interpreter prompt and `python3
    -c` leave `__main__` without a `__file__` at all, and then there is
    nothing to find.  Every caller has to cope with that rather than
    assume a program has a file; see 6.12.1 of `T.fbanwiis`.

    Worse, a `__file__` that is present is not necessarily a file.  A
    program piped in as `python3 - < program.py` gets the literal
    `<stdin>`, `exec` of a string gets `<string>`, and a frozen
    interpreter gets something under `<frozen ...>`; resolving any of
    those yields a plausible looking path in the working directory that
    names nothing.  So the file has to exist to count, which also
    rejects a program deleted from under itself.

    Returns:
    * (`Path | None`): The program's file, resolved, or `None` when the
      program does not have a file that exists.
    """
    # A module with no file is the normal case at a prompt.
    main: ModuleType | None = sys.modules.get("__main__")
    where: str | None = getattr(main, "__file__", None)
    if where is None:
        return None

    # `<stdin>` and its relatives resolve to paths that name nothing.
    found: Path = Path(where).resolve()
    if not found.is_file():
        return None
    return found


# The regex PEP 723 specifies for finding a metadata block, copied from
# the PEP rather than written afresh, because a block this project fails
# to recognise is a block some other tool accepts.  `(?m)` makes `^` and
# `$` match per line, and the `type` group is what tells a `script` block
# from any other kind the PEP may come to define.
BLOCK: re.Pattern[str] = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)"
    r"^# ///$")

# Opening fences, counted separately from the blocks themselves.
# `BLOCK`'s `content` group matches commented lines greedily and will
# swallow a closing fence and the next block's opener, so two adjacent
# blocks arrive as one match and never look duplicated; measured
# 2026-09-27.  Counting the fences notices them anyway.  See 6.7.7 of `T.p7i`.
FENCE: re.Pattern[str] = re.compile(r"(?m)^# /// script$")


# The one `requires-python` shape this understands: a single `>=` clause
# naming two or three numbers, which is what a real block says.  Anything
# else -- `>=3.9,<4`, `!=3.9.*`, `~=3.11`, a pre-release rule -- is left
# alone rather than guessed at, because PEP 440 belongs to `pip`.  See
# 6.3.3 of `T.vcbow` and 6.7.10 of `T.p7i`.
PYTHON_FLOOR: re.Pattern[str] = re.compile(
    r"^>=\s*(\d+)\.(\d+)(?:\.(\d+))?$")


def python_floor(specifier: str) -> tuple[int, ...] | None:
    """Return the lowest Python a specifier allows, when that is certain.

    Only the single `>=` form is read; see `PYTHON_FLOOR`.  The point of
    refusing the rest is that a partial reading of somebody else's
    specification is worse than no reading at all: it disagrees silently.
    Two or three numbers come back as a tuple, which compares against
    `sys.version_info` the way PEP 440 compares that shape.

    Arguments:
    * `specifier` (`str`):
      A `requires-python` value, such as `>=3.11`.

    Returns:
    * (`tuple[int, ...] | None`): The floor as numbers, or `None` when
      the specifier is not one this can be sure about.
    """
    # No match means no opinion, which is the safe answer.
    found: re.Match[str] | None = PYTHON_FLOOR.match(specifier.strip())
    if found is None:
        return None
    return tuple(int(part) for part in found.groups() if part is not None)


def script_metadata(text: str) -> dict[str, Any] | None:
    """Return the PEP 723 metadata declared in a program's source.

    PEP 723 puts the metadata in `#` comments, opened by `# /// script`
    and closed by `# ///`, with every line between them commented too.
    Stripping the comment markers leaves TOML, which `tomllib` reads.
    See 6.7.2 and 6.7.7 of `T.p7i`.

    The argument is source **text**, not a module or a path, because a
    comment does not exist at run time: the compiler drops it, and `-OO`
    drops the docstrings as well.  `main_source` is where the text comes
    from.

    Blocks of other types are ignored rather than refused, since the PEP
    reserves the syntax for kinds it has not defined yet and a program
    carrying one is not making a mistake.

    Two measured consequences of using the PEP's regex rather than one of
    our own, both of which a tool that shares the regex also has.  An
    empty block gives `None` and not an empty dictionary, because the
    pattern requires at least one commented line between the fences, so
    an empty block matches nothing and is indistinguishable from no
    block.  And a block of another type immediately above a `script`
    block hides it, because the first block's match runs on through the
    second; one blank or uncommented line between them is enough to
    separate them.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`dict[str, Any] | None`): What the block declared, or `None` when
      the program has no `script` block at all.  An empty block gives an
      empty dictionary, which is not the same thing.

    Raises:
    * `ValueError`:
      If there is more than one `script` block, which PEP 723 makes an
      error, or if the block is not valid TOML.  Both are the author's
      mistake and silence would hide it.  Which of two blocks was meant
      is unknowable, so neither is guessed at.
    """
    # Fences first, since two adjacent blocks match as one.
    fences: int = len(FENCE.findall(text))
    if fences > 1:
        raise ValueError(
            f"{fences} PEP 723 script blocks; there may be only one")

    # Only `script` blocks; the PEP reserves other types for later.
    found: list[re.Match[str]] = [
        match for match in BLOCK.finditer(text)
        if match.group("type") == "script"]
    if not found:
        return None

    # Each line is `#`, or `# ` and then the TOML, so two characters go.
    lines: list[str] = [
        line[2:] if line.startswith("# ") else line[1:]
        for line in found[0].group("content").splitlines()]
    try:
        return tomllib.loads("\n".join(lines))
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"PEP 723 block is not valid TOML: {error}") from None


def main_source() -> tuple[Path, str] | None:
    """Return the running program's file and its text.

    Three things want this: the PEP 723 block of `T.p7i`, the bootstrap
    that `T.fbanwiis` looks for, and the approvals file of `T.sawaw`, which
    needs only the path.  One function so that the awkward cases are got
    right once and tested once.

    The **text** is what callers read, never the module's own attributes.
    `python3 -O` and `-OO` change what the interpreter keeps -- `-OO`
    discards docstrings entirely -- and comments never survive compiling
    at all.  Only the source has everything that was written.

    `tokenize.open` reads it rather than `Path.read_text`, because a
    program is not obliged to be UTF-8: a `# -*- coding: latin-1 -*-`
    line, or a byte order mark, tells the interpreter otherwise and it
    obeys.  `tokenize.open` is the standard library's own answer to that
    question and honours both, so a program the interpreter can run is a
    program this can read.  Measured 2026-09-27: with `read_text` a
    perfectly legal latin-1 program declared nothing at all, silently.

    Returns:
    * (`tuple[Path, str] | None`): The program's file and its contents,
      or `None` when there is no file or it cannot be read.
    """
    # A file that has been moved or deleted since the program started
    # is as good as absent.
    where: Path | None = main_path()
    if where is None:
        return None

    # `SyntaxError` is what `tokenize` raises for an encoding it cannot
    # make sense of, and such a file would not have got this far.
    try:
        with tokenize.open(where) as source:
            return where, source.read()
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None


# What an empty `prog.py.toml` is filled with: every setting, commented
# out at its default (`T.abfd`), except `exports`, whose empty list is
# left open so that each form is one `#` to remove (Wayne, 2026-10-21).
# `README.md` shows it verbatim, so it names no particular program:
# `PROG_NAME` is the README's word for one (Wayne, 2026-10-22).  With
# `EDIT_PROGRAM` on, `first_run_note` follows `AUTO_DEPENDENCIES_LINE`.
SETTINGS_TEMPLATE: str = """\
# PROG_NAME.py.toml: EZPkg settings for PROG_NAME.py, the program
# beside this file.  More: https://pypi.org/project/ezpkg/
#
# This file makes you the program's developer.  If you delete this file,
# you are no longer treated as a developer.  This file is the only place
# where your development decisions get recorded (i.e. there are no unexpected
# text prompts when the program runs.)  All information that EZPkg collects
# is stored in files in the `~/.ezpkg/` directory (not this file.)
#
# Wayne has edited to here.
#
# to control what EZPkg does.  
# ezpkg asks you nothing,
# fetches the packages the program's imports need, and remembers them
# and the versions you ran in ~/.ezpkg, never in the program itself.  A
# release writes them into the copies it makes, so that whoever you
# send a release to gets exactly those.  Without this file, the program
# is an end user's: they are asked once, on its first run, and the
# program is never edited.
#
# Each setting is shown at its default, after a `#`.  To change one,
# remove its `#` and edit its value.  A misspelt setting or a wrong
# value stops the program, naming the line.  To see this text again,
# empty this file and run the program.

# Keep the packages matching the imports: a new import gets a package,
# with a version range, and one whose import is gone is dropped.  With
# `false`, ezpkg fetches only what `dependencies` (at the end of this
# file) lists, with the program's own Part 1, if it has one.
# auto-dependencies = true

# How much ezpkg says: "none", "low", "medium" or "high".
# verbosity = "low"

# The versions are frozen at the date of the program's first run, so
# they never change by themselves.  With `upgrade = true`, every run
# takes the newest versions; put the `#` back to freeze them at the
# last run's date.
# upgrade = false

# How many days the packages the program uses may go unused before
# ezpkg removes them from ~/.ezpkg (they are fetched again if needed).
# cull-days = 30

# Releases: a release builds the copies you send to others, beside the
# program, and records each one in PROG_NAME.py.releases.  Releases are
# off until you remove the `#` from at least one entry of `exports` and
# from `release` below.  Then each run where `release` differs from the
# last one released builds that release, in place of the last one's
# files, and then runs the program as usual.  Each release checks the
# imports and the bootstrap, and gives each package without a version
# a range.
exports = [  # Remove the `#`s of the forms each release builds.
#   "email",   # PROG_NAME-VERSION.py, to send; for every computer.
#   "zipapp",  # PROG_NAME-VERSION.pyz, no network; pure Python only.
#   "uv",      # PROG_NAME-VERSION-uv.py and its lock, for `uv run`.
]

# The version of the next release.  Change it whenever you like, even
# to go back to an older number.
# release = "1.0.0"

# The bootstrap the program carries: "update" replaces an older one at
# the next release; a name, such as "nopip8", keeps exactly that one.
# bootstrap = "update"

# Rarely needed: ezpkg works these out, and you set them only when it
# gets one wrong.

# The Pythons the program runs on.  Each release works this out from
# the program's syntax and its packages (never older than 3.11, which
# ezpkg needs), and says so when it is older than every Python you have
# run the program on.  Set it if the program needs a newer Python.
# requires-python = ">=3.11"

# Packages ezpkg cannot work out.  It finds a package for each import,
# with a range from the version you ran, takes a marker from a guard
# such as `if sys.platform == "win32":`, and adds a package when the
# program stops because one is missing.  For anything else, write an
# entry such as "numpy>=2.1" or "requests[socks]", a Python "dependency
# specifier", as explained at
# https://packaging.python.org/en/latest/specifications/dependency-specifiers/
# An entry here wins over the one ezpkg would choose for that package.
# dependencies = []
"""

# The template's line that `first_run_note` follows, when it is used.
AUTO_DEPENDENCIES_LINE: str = "# auto-dependencies = true\n"

def first_run_note(name: str, adding: Sequence[str] | None) -> str:
    """Return the note a filled `prog.py.toml` carries beside its
    `auto-dependencies` line.

    The run that fills the file edits nothing in the program, so the
    developer is told before anything is changed, and can say no in the
    file first (Wayne, 2026-10-21).  The file is never written again, so
    the note says to delete it once it has done its job.

    Arguments:
    * `name` (`str`):
      The program's file name, such as `prog.py`.
    * `adding` (`Sequence[str] | None`):
      The entries the next run would add, or `None` when that is not
      known (the imports were not looked at).

    Returns:
    * (`str`): The note's comment lines, without a final newline.
    """
    # What the next run does, then how to stop it.
    quoted: list[str] = [f'"{one}"' for one in adding or ()]
    now: str = ("" if adding is None else
                " (right now nothing needs adding)" if not adding else
                f" (right now that means adding "
                f"{and_list(quoted)})")
    text: str = (
        f"First run ({time.strftime('%Y-%m-%d')}): ezpkg has not edited "
        f"{name}.  From the next run, it keeps the `dependencies` in "
        f"{name}'s Part 1 matching the imports{now}, and records there the "
        f"versions {name} ran with.  To stop the `dependencies` edits, set "
        f"`auto-dependencies = false` above before running {name} again.  "
        f"Once {name} has run again, this note has done its job: delete it.")
    return textwrap.fill(text, 72, initial_indent="# ",
                         subsequent_indent="# ", break_on_hyphens=False)


# How many of a developer's finished runs `EZPkg.note_loaded` remembers,
# newest last.  An entry nothing imports goes once one of them declared
# it and none loaded its package (Wayne, 2026-10-20; `T.abfd`).
RUNS_KEPT: int = 10

# Whether a developer's runs edit the program's Part 1.  Off: what
# `ezpkg` works out (the entries for imports Part 1 does not declare,
# the `checksums`, the frozen date) is kept in the
# program's `develop/` record, its stash (`EZPkg.stash`), and only a
# release's copies carry it (Wayne, 2026-10-22).  Whether `prog.py` is
# never to be edited is not yet decided, so the editing code stays, and
# the tests that need it turn this on (`EZPKG_EDIT_PROGRAM=on`, for the
# test suite only).
EDIT_PROGRAM: bool = os.environ.get("EZPKG_EDIT_PROGRAM", "").lower() == "on"

# What a release can build, in the order it builds them.  `exports`
# names none of them until the developer turns releases on (Wayne,
# 2026-10-21: no release on a first run).
EXPORT_FORMS: tuple[str, ...] = ("email", "zipapp", "uv")

# The values of `verbosity`, quietest first, so that each one's index is
# its level for `EZPkg.say` (`T.abfd`, S1.5).
VERBOSITY: tuple[str, ...] = ("none", "low", "medium", "high")


@dataclasses.dataclass(frozen=True)
class Settings:
    """A developer's settings for a program, from `prog.py.toml`.

    The file's presence is what makes a program its developer's; an
    empty one means every default (`T.abfd`).  Each key is a field, its
    `-` spelt `_`.

    Attributes:
    * `auto_dependencies` (`bool`):
      Keep `dependencies` matching the imports.
    * `verbosity` (`str`):
      How much `ezpkg` says, from `VERBOSITY`; see `EZPkg.say`.
    * `release` (`str | None`):
      The version of the next release, such as `"1.0.0"`, or `None`
      for no release (`EZPkg.release_due`).
    * `exports` (`tuple[str, ...]`):
      What a release builds, from `EXPORT_FORMS`; none unless the file
      says otherwise, and with none there are no releases.
    * `bootstrap` (`str`):
      `update`, or the short name of the published bootstrap the
      program must carry, such as `nopip7` (Wayne, S5.1).
    * `upgrade` (`bool`):
      Take the newest versions on every run, rather than those of the
      frozen date (`EZPkg.declared_date`).
    * `cull_days` (`int | None`):
      How many days what the program holds may go unused before `cull`
      takes it, or `None` for `CULL_DAYS` (`cull_seconds`).
    * `dependencies` (`tuple[str, ...]`):
      The developer's own requirements, for what the imports cannot say
      (an extra, an exact version), declared with Part 1's and kept as
      they are (`EZPkg.written`).
    * `requires_python` (`str | None`):
      The Pythons a release's Part 1 admits, or `None` for the floor
      the release works out (`EZPkg.python_range`).
    """

    auto_dependencies: bool = True
    verbosity: str = "low"
    release: str | None = None
    exports: tuple[str, ...] = ()
    bootstrap: str = "update"
    upgrade: bool = False
    cull_days: int | None = None
    dependencies: tuple[str, ...] = ()
    requires_python: str | None = None


def settings_path(program: Path) -> Path:
    """Return the settings file of a program: `prog.py.toml` beside it.

    Arguments:
    * `program` (`Path`):
      The program, such as `prog.py`.

    Returns:
    * (`Path`): The settings file, whether or not it exists.
    """
    # The whole name, suffix included, so `prog.py` and `prog.pyw`
    # cannot share one.
    return program.with_name(f"{program.name}.toml")


def releases_path(program: Path) -> Path:
    """Return a program's release record: `prog.py.releases` beside it.

    One file, so that a developer who keeps the program in version
    control keeps one more file, not a folder of builds (Wayne,
    2026-10-22).  `EZPkg.release` adds a `[[release]]` entry at its end
    for each release: what it needs to make that release again, and
    nothing more (`release_entry`).

    Arguments:
    * `program` (`Path`):
      The program, such as `prog.py`.

    Returns:
    * (`Path`): The record, whether or not it exists.
    """
    # Named like the settings file.
    return program.with_name(f"{program.name}.releases")


def release_files(program: Path, version: str) -> list[Path]:
    """Return the files a release of a program may build, beside it.

    Arguments:
    * `program` (`Path`):
      The program, such as `prog.py`.
    * `version` (`str`):
      The release, such as `1.0.0`.

    Returns:
    * (`list[Path]`): The `email` copy, the `zipapp`, the `uv` script
      and its lock, in `EXPORT_FORMS` order, whether or not they exist.
    """
    # Named by version, so a recipient can tell one from another.
    stem: str = f"{program.stem}-{version}"
    return [program.with_name(f"{stem}.py"),
            program.with_name(f"{stem}.pyz"),
            program.with_name(f"{stem}-uv.py"),
            program.with_name(f"{stem}-uv.py.lock")]


def read_releases(program: Path) -> list[dict[str, Any]]:
    """Return the entries of a program's `prog.py.releases`, oldest first.

    Arguments:
    * `program` (`Path`):
      The program.

    Returns:
    * (`list[dict[str, Any]]`): Each `[[release]]` table; empty when
      there is no file.

    Raises:
    * `ValueError`:
      If the file cannot be read as TOML, naming it.
    """
    # A missing file is no releases yet.
    path: Path = releases_path(program)
    try:
        table: dict[str, Any] = tomllib.loads(
            path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"{path.name}: {error}") from None
    entries: object = table.get("release", [])
    return [one for one in (entries if isinstance(entries, list) else [])
            if isinstance(one, dict)]


def release_entry(version: str, dated: str, entries: Sequence[str],
                  commit: str) -> str:
    """Return the `[[release]]` entry `prog.py.releases` gets for a release.

    The version, when it was made, the date its versions are frozen at
    and the `dependencies` it shipped with, which are enough to make
    it again, plus the version control commit it was made from, if
    there is one (Wayne, 2026-10-22: no copy of the program).

    Arguments:
    * `version` (`str`):
      Such as `1.0.0`.
    * `dated` (`str`):
      The `exclude-newer` date, or empty for none.
    * `entries` (`Sequence[str]`):
      The release's `dependencies`.
    * `commit` (`str`):
      Such as `git dd6c8b3`, or empty.

    Returns:
    * (`str`): The entry, a blank line first.
    """
    # One key per line, `dependencies` one entry per line.
    lines: list[str] = [
        "", "[[release]]", f"version = {json.dumps(version)}",
        f'date = "{time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}"']
    if commit:
        lines.append(f"commit = {json.dumps(commit)}")
    if dated:
        lines.append(f"exclude-newer = {json.dumps(dated)}")
    lines.append("dependencies = [")
    lines += [f"    {json.dumps(entry)}," for entry in entries]
    lines.append("]")
    return "\n".join(lines) + "\n"


def commit_of(program: Path) -> str:
    """Return the version control commit a program's folder is at.

    Arguments:
    * `program` (`Path`):
      The program.

    Returns:
    * (`str`): Such as `git dd6c8b3` (with `+` when the program differs
      from it), `hg 1a2b3c4d5e6f`, or empty when neither knows it.
    """
    # `git`, then `hg`; either may be missing.
    command: list[str]
    for command in (["git", "rev-parse", "--short", "HEAD"],
                    ["hg", "id", "-i"]):
        try:
            found: subprocess.CompletedProcess[str] = subprocess.run(
                command, cwd=program.parent, capture_output=True,
                text=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if found.returncode or not found.stdout.strip():
            continue
        commit: str = found.stdout.strip()
        if command[0] == "git":
            try:
                changed: subprocess.CompletedProcess[str] = subprocess.run(
                    ["git", "status", "--porcelain", "--", program.name],
                    cwd=program.parent, capture_output=True, text=True,
                    timeout=10, check=False)
                if changed.stdout.strip():
                    commit += "+"
            except (OSError, subprocess.TimeoutExpired):
                pass
        return f"{command[0]} {commit}"
    return ""


def cull_seconds(program: Path, default: float = CULL_DAYS) -> float:
    """Return how long what a program holds may go unused, in seconds.

    Its `prog.py.toml`'s `cull-days`, for a developer's program that
    still has one; otherwise `default` (`CULL_DAYS`).  A settings file
    that cannot be read is the default, since `cull` must not stop.

    Arguments:
    * `program` (`Path`):
      The program, which may no longer exist.
    * `default` (`float`):
      The seconds otherwise.

    Returns:
    * (`float`): The seconds.
    """
    # Only a file that is there, reads, and sets it.
    try:
        if settings_path(program).is_file():
            chosen: int | None = read_settings(
                settings_path(program)).cull_days
            if chosen is not None:
                return chosen * 86400.0
    except (OSError, ValueError):
        pass
    return default


def next_release(last: str) -> str:
    """Return the version after the last release: its last number plus 1.

    Arguments:
    * `last` (`str`):
      The last release, such as `1.0.0`; empty for none.

    Returns:
    * (`str`): Such as `1.0.1`; `1.0.0` when there was none.  A
      `.devN` is dropped, and a short version is padded (`2.1` gives
      `2.1.1`).
    """
    # Three numbers at least, the last one counted on.
    found: re.Match[str] | None = RELEASE.fullmatch(last)
    if found is None:
        return "1.0.0"
    numbers: list[int] = [int(one) for one in found[1].split(".")]
    numbers += [0] * (3 - len(numbers))
    numbers[-1] += 1
    return ".".join(map(str, numbers))


def setting_line(text: str, key: str) -> int:
    """Return the line of `prog.py.toml` that sets a top-level key.

    `tomllib` reports no positions, and a message naming the line lets
    the developer go straight to it.

    Arguments:
    * `text` (`str`):
      The file's text.
    * `key` (`str`):
      The top-level key, as `tomllib` read it.

    Returns:
    * (`int`): The first line (from 1) that sets `key` or opens it as a
      table, or 0 when none is found.
    """
    # A bare, quoted or dotted key before `=`, or a `[table]` header.
    pattern: re.Pattern[str] = re.compile(
        r"""\s*(?:\[+\s*)?(?:"([^"]*)"|'([^']*)'|([A-Za-z0-9_-]+))"""
        r"""\s*[.=\]]""")
    number: int
    line: str
    for number, line in enumerate(text.splitlines(), 1):
        found: re.Match[str] | None = pattern.match(line)
        if found is not None and key in found.groups():
            return number
    return 0


def read_settings(path: Path) -> Settings:
    """Read and check a program's `prog.py.toml`.

    Every key and value is checked, so a typo stops the run rather than
    being quietly ignored (`T.abfd`).

    Arguments:
    * `path` (`Path`):
      The settings file, which exists.

    Returns:
    * (`Settings`): What it sets, with the defaults for the rest.

    Raises:
    * `ValueError`:
      With the message for the developer, such as `prog.py.toml line 3:
      unknown setting `relase` (did you mean `release`?)`.
    """
    # TOML is UTF-8, and `tomllib`'s own messages give the line.
    try:
        text: str = path.read_text(encoding="utf-8")
        table: dict[str, Any] = tomllib.loads(text)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"{path.name}: {error}") from None

    # Each key, then the form of its value.
    known: dict[str, str] = {field.name.replace("_", "-"): field.name
                             for field in dataclasses.fields(Settings)}
    values: dict[str, Any] = {}
    key: str
    value: Any
    for key, value in table.items():
        where: str = f"{path.name} line {setting_line(text, key)}"
        if key not in known:
            near: list[str] = difflib.get_close_matches(key, list(known), 1)
            raise ValueError(
                f"{where}: unknown setting `{key}` " + (
                    f"(did you mean `{near[0]}`?)" if near else
                    "(the settings are "
                    + and_list([f"`{one}`" for one in known]) + ")"))
        wrong: str = ""
        if key == "release":
            if not (isinstance(value, str) and RELEASE.fullmatch(value)):
                wrong = 'a version in quotes, such as "1.0.0"'
        elif key == "bootstrap":
            published: list[str] = [one.split()[0]
                                    for one in BOOTSTRAPS.values()]
            if value != "update" and value not in published:
                wrong = '"update" or a published bootstrap, ' + and_list(
                    [f'"{one}"' for one in published], "or")
        elif key == "cull-days":
            if (isinstance(value, bool) or not isinstance(value, int)
                    or value < 1):
                wrong = "a whole number of days, 1 or more"
        elif key == "verbosity":
            if value not in VERBOSITY:
                wrong = "one of " + and_list(
                    [f'"{one}"' for one in VERBOSITY], "or")
        elif key == "exports":
            if (isinstance(value, list)
                    and all(one in EXPORT_FORMS for one in value)
                    and len(set(value)) == len(value)):
                value = tuple(value)
            else:
                wrong = ("a list of " + and_list(
                    [f'"{one}"' for one in EXPORT_FORMS], "or")
                    + ", each at most once")
        elif key == "dependencies":
            if isinstance(value, list) and all(
                    isinstance(one, str) and requirement_name(one)
                    for one in value):
                value = tuple(value)
            else:
                wrong = 'a list of requirements in quotes, such as "numpy>=2"'
        elif key == "requires-python":
            if not (isinstance(value, str) and python_floor(value)):
                wrong = 'a Python version range in quotes, such as ">=3.11"'
        elif not isinstance(value, bool):
            wrong = "`true` or `false`"
        if wrong:
            raise ValueError(f"{where}: `{key}` must be {wrong}")
        values[known[key]] = value
    return Settings(**values)


def bootstrap_fingerprint(text: str) -> str:
    """Fingerprint a pasted bootstrap so that layout cannot change it.

    Comments are dropped and then every space, tab and line break, so
    re-indenting, re-wrapping or annotating a pasted copy leaves it the
    same bootstrap, while changing any code makes it a different one.
    `tokenize` finds the comments, because a `#` may sit inside a
    string.  The tokens are joined back into text before the whitespace
    goes, which makes the result the same under 3.11, where an f-string
    is one token, and under 3.12, where it is several.  See `T.fbanwiis`.

    Arguments:
    * `text` (`str`):
      The bootstrap's `try` block, as found in a program.

    Returns:
    * (`str`): A SHA-256, in hexadecimal.
    """
    # Comments out, then all whitespace, then the digest.
    kept: list[str] = []
    token: tokenize.TokenInfo
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type != tokenize.COMMENT:
            kept.append(token.string)
    return hashlib.sha256("".join("".join(kept).split()).encode()).hexdigest()


def find_bootstrap(text: str) -> str | None:
    """Return the pasted bootstrap's `try` block from a program's text.

    The bootstrap is recognised as a `try` whose text mentions both
    `ezpkg` and `import_module`, wherever it sits.  Only the `try`
    is taken: the imports above it are moved to the top of a program by
    hand, and would make a correctly pasted copy look edited.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`str | None`): The block, or `None` when there is none or the
      program does not parse.
    """
    # Padded and then dedented, because the segment's first line
    # otherwise comes without its indentation and the rest with theirs,
    # which `tokenize` rejects when the `try` is nested.
    found: ast.Try | None = bootstrap_node(text)
    if found is None:
        return None
    return textwrap.dedent(
        ast.get_source_segment(text, found, padded=True) or "")


def bootstrap_node(text: str) -> ast.Try | None:
    """Return the pasted bootstrap's `try` statement, parsed.

    The search `find_bootstrap` and `strip_bootstrap` share: a `try`
    whose text mentions both `ezpkg` and `import_module`.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`ast.Try | None`): The statement, or `None` when there is none or
      the program does not parse.
    """
    # The first match wins; a program has one bootstrap.
    try:
        tree: ast.Module = ast.parse(text)
    except SyntaxError:
        return None
    node: ast.AST
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            block: str | None = ast.get_source_segment(text, node)
            if block and "ezpkg" in block and "import_module" in block:
                return node
    return None


def own_entry(asking: Sequence[str]) -> str | None:
    """Return a program's `ezpkg` requirement, or `None` if it has none.

    Arguments:
    * `asking` (`Sequence[str]`):
      Its `dependencies`.

    Returns:
    * (`str | None`): The entry, such as `ezpkg>=0.1,<0.2`.
    """
    # By name, as `pip` compares them.
    return next((entry for entry in asking
                 if normal_name(requirement_name(entry)) == "ezpkg"), None)


def from_wheel() -> bool:
    """Say whether this `ezpkg` was installed from a wheel.

    A wheel leaves `ezpkg-VERSION.dist-info` beside the package, as
    the bootstrap's `pip install --target` and an unpacked version tree
    both do.  A copy run from a source tree has none, and its version
    is not on any index, so the approvals cannot pin it (`T.eui`).

    Returns:
    * (`bool`): True if this one came from a wheel of `__version__`.
    """
    # Inside the wheel `nopip8` imports from, beside the package
    # directory, or beside a lone module.
    here: Path = Path(__file__).resolve().parent
    archive: zipfile.ZipFile
    if here.suffix == ".whl":
        try:
            with zipfile.ZipFile(here) as archive:
                return (f"ezpkg-{__version__}.dist-info/METADATA"
                        in archive.namelist())
        except (OSError, zipfile.BadZipFile):
            return False
    if here.name == "ezpkg":
        here = here.parent
    return (here / f"ezpkg-{__version__}.dist-info").is_dir()


def without_ezpkg(names: Collection[str]) -> list[str]:
    """Drop `ezpkg` from pins, wheel names or version tree names.

    The approvals pin `ezpkg` so that the program runs the version its
    author approved (`T.eui`), but an export takes the bootstrap out,
    and with it the need for `ezpkg`.

    Arguments:
    * `names` (`Collection[str]`):
      Such as `ezpkg==0.1.0`, `ezpkg-0.1.0-py3-none-any.whl` or
      `cowsay-6.1-cpython-312-linux-x86_64`.

    Returns:
    * (`list[str]`): The others, in the same order.
    """
    # The name ends at the first `=` or `-`.
    return [name for name in names
            if normal_name(re.split(r"[=<>!~ ;-]", name, maxsplit=1)[0])
            != "ezpkg"]


# How many hex digits of a wheel's SHA-256 Part 1 records as its `id:`:
# 64 bits, which nobody can forge a wheel to match (Wayne, S2.4c).
ID_DIGITS: int = 16


def wheel_pin(wheel: str) -> str:
    """Return a wheel's name and version as a pin.

    Arguments:
    * `wheel` (`str`):
      A wheel's file name, such as `cowsay-6.1-py3-none-any.whl`.

    Returns:
    * (`str`): Such as `cowsay==6.1`, the name spelt as in the wheel.
    """
    # A wheel is `{name}-{version}-...`, and the name has no hyphen.
    name: str
    version: str
    name, version = (wheel.split("-") + [""])[:2]
    return f"{name}=={version}"


def normal_pin(pin: str) -> str:
    """Return a pin with its name normalized, for comparing.

    Arguments:
    * `pin` (`str`):
      Such as `PyYAML==6.0.1`.

    Returns:
    * (`str`): Such as `pyyaml==6.0.1`.
    """
    # Only the name differs between spellings.
    name: str
    version: str
    name, _, version = pin.partition("==")
    return f"{normal_name(name)}=={version}"


def wheel_tag(wheel: str) -> str:
    """Return the platform a wheel was built for, or empty for any.

    A compiled package has a different wheel, and so a different `id:`,
    for each platform and Python; a pure-Python one has one wheel for
    every machine (S2.4d).

    Arguments:
    * `wheel` (`str`):
      A wheel's file name, such as
      `numpy-2.1.0-cp312-cp312-manylinux_2_17_x86_64.whl`.

    Returns:
    * (`str`): Its tags, such as `cp312-cp312-manylinux_2_17_x86_64`,
      or empty for a wheel that runs anywhere (`none-any`).
    """
    # The last three fields, after any build tag.
    tags: list[str] = wheel.removesuffix(".whl").split("-")[-3:]
    return "" if tags[1:] == ["none", "any"] else "-".join(tags)


def approval_fields(text: str) -> list[list[str]] | None:
    """Return each approval Part 1 records, split into its fields.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`list[list[str]] | None`): Such as `["cowsay==6.1",
      "id:3f4e9a0c71d2b8e5"]`, or `None` when Part 1 records none.
    """
    # Anything malformed is no approvals, as a missing file was.
    try:
        metadata: dict[str, Any] | None = script_metadata(text)
    except ValueError:
        return None
    tool: object = (metadata or {}).get("tool", {})
    table: object = tool.get("ezpkg", {}) if isinstance(tool, dict) else {}
    listed: object = (table.get("checksums")
                      if isinstance(table, dict) else None)
    if not isinstance(listed, list):
        return None
    return [str(entry).split() or [""] for entry in listed]


def approval_tags(text: str) -> dict[str, str]:
    """Return the platform each compiled approval was recorded on.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`dict[str, str]`): Each pin's `tag:`, for the pins that have one
      (`wheel_tag`); a pure-Python pin has none.
    """
    # Only the pins that carry one.
    return {fields[0]: one[4:] for fields in approval_fields(text) or []
            for one in fields[1:] if one.startswith("tag:")}


def approvals_in(text: str) -> dict[str, str] | None:
    """Return the approvals Part 1 records, pin to `id:`.

    They are `[tool.ezpkg] checksums`, one string per package, such as
    `"cowsay==6.1  id:3f4e9a0c71d2b8e5"`, which a developer's runs
    write (`EZPkg.record_approvals`, `T.abfd`).

    Arguments:
    * `text` (`str`):
      The program's source.

    A compiled package's also carries the platform its wheel was built
    for, `"numpy==2.1.0  id:...  tag:cp312-cp312-manylinux_2_17_x86_64"`
    (`approval_tags`, S2.4d).

    Returns:
    * (`dict[str, str] | None`): Each pin's id, or `None` when Part 1
      records no approvals, which means nothing is verified.
    """
    # The pin, then its `id:`.
    listed: list[list[str]] | None = approval_fields(text)
    if listed is None:
        return None
    return {fields[0]: next((one[3:] for one in fields[1:]
                             if one.startswith("id:")), "")
            for fields in listed}


def approvals_array(approved: Mapping[str, str],
                    tags: Mapping[str, str] | None = None) -> str:
    """Return the `checksums` array as Part 1 writes it.

    Arguments:
    * `approved` (`Mapping[str, str]`):
      Each pin's id.
    * `tags` (`Mapping[str, str] | None`):
      The platform of each compiled pin's wheel (`wheel_tag`).

    Returns:
    * (`str`): `[`, one line per package, sorted, then `]`.
    """
    # Two spaces before `id:` and `tag:`, so the pins read as a column.
    return ("[\n" + "".join(
        f'  "{pin}  id:{identity}'
        + (f"  tag:{(tags or {})[pin]}" if (tags or {}).get(pin) else "")
        + '",\n' for pin, identity in sorted(approved.items())) + "]")


def for_export(names: Collection[str], program: str) -> list[str]:
    """Keep `ezpkg` in an export only when the program imports it.

    The bootstrap is taken out of an export, and with it the need for
    `ezpkg`, unless the program also imports `ezpkg` itself to use its
    API: then the export has to carry the version the approvals pin
    (`I.uedepi`).

    Arguments:
    * `names` (`Collection[str]`):
      Pins, wheel names or version tree names, as for `without_ezpkg`.
    * `program` (`str`):
      The program's source, with its bootstrap taken out.

    Returns:
    * (`list[str]`): The names the export needs, in the same order.

    Raises:
    * `RuntimeError`:
      If the program imports `ezpkg` but the approvals do not pin it.
    """
    # The bootstrap imports with `importlib`, so any import is the
    # program's own.
    try:
        imported: bool = any(module == "ezpkg" for module, _, _
                             in every_import(program))
    except SyntaxError:
        imported = False
    others: list[str] = without_ezpkg(names)
    if not imported:
        return others
    if len(others) == len(names):
        raise RuntimeError(
            "the program imports ezpkg, but the approvals do not pin "
            "it; run it as its developer, using an ezpkg installed from "
            "a wheel")
    return list(names)


def answer_from(reader: IO[str], writer: IO[str],
                seconds: float | None = None) -> str:
    """Read one answer from a terminal, or nothing if none comes in time.

    Nothing is what a terminal that has gone away gives, and every
    question already takes it as no.  On Windows a console can exist
    with nobody at it, so a question that nobody answers within
    `ANSWER_SECONDS` says so and gives up (`I.owenabd`).  A terminal
    returns at most one line per read, so nothing typed ahead is
    lost to the wait.

    Arguments:
    * `reader` (`IO[str]`):
      The terminal, open for reading.
    * `writer` (`IO[str]`):
      The terminal, open for writing, for the message.
    * `seconds` (`float | None`):
      How long to wait; `EZPKG_ANSWER_SECONDS` if set to a number, else
      `ANSWER_SECONDS`, if not given.

    Returns:
    * (`str`): The line, with its newline, or empty.
    """
    # Something that is not a terminal, such as a test's string, is read
    # at once.  A testing setting that is not a number is ignored.
    limit: float = ANSWER_SECONDS if seconds is None else seconds
    if seconds is None:
        try:
            limit = float(os.environ["EZPKG_ANSWER_SECONDS"])
        except (KeyError, ValueError):
            pass
    try:
        handle: int = reader.fileno()
    except (OSError, ValueError):
        return reader.readline()

    # Windows cannot `select` a console, but can ask whether a key is
    # waiting.
    arrived: bool
    if os.name == "nt":
        import msvcrt
        deadline: float = time.monotonic() + limit
        while not (arrived := msvcrt.kbhit()):  # type: ignore[attr-defined]
            if time.monotonic() >= deadline:
                break
            time.sleep(0.1)
    else:
        arrived = bool(select.select([handle], [], [], limit)[0])
    if arrived:
        return reader.readline()
    writer.write(f"\nNo answer in {limit / 60:g} minutes, so: no.\n"
                 if limit >= 60 else
                 f"\nNo answer in {limit:g} seconds, so: no.\n")
    writer.flush()
    return ""


def published_bootstraps() -> dict[str, list[str]]:
    """Return every published bootstrap that names `ezpkg`, as trimmed lines.

    Returns:
    * (`dict[str, list[str]]`): Each name, such as `nopip6 of
      2026-10-16`, and its `try` block, each line stripped.
    """
    # The current one is `QUICK_START`'s own.
    texts: dict[str, str] = dict(OLD_BOOTSTRAP_TEXTS)
    texts[list(BOOTSTRAPS.values())[-1]] = find_bootstrap(QUICK_START) or ""
    return {name: trimmed(text) for name, text in texts.items()}


def trimmed(block: str) -> list[str]:
    """Return a bootstrap's lines with their leading and trailing space gone.

    So the indentation a program gives the paste does not count, and
    nothing else is forgiven (Wayne, 2026-10-16; see `T.reb`).

    Arguments:
    * `block` (`str`):
      A bootstrap's `try` block.

    Returns:
    * (`list[str]`): Its lines, stripped.
    """
    return [line.strip() for line in block.splitlines()]


def bootstrap_name(block: str) -> str | None:
    """Return the published bootstrap this one is exactly, or `None`.

    Arguments:
    * `block` (`str`):
      A bootstrap's `try` block, as `find_bootstrap` returns it.

    Returns:
    * (`str | None`): Its name, such as `nopip6 of 2026-10-16`.
    """
    # Line for line, once trimmed.
    mine: list[str] = trimmed(block)
    name: str
    lines: list[str]
    for name, lines in published_bootstraps().items():
        if lines == mine:
            return name
    return None


def bootstrap_refusal(path: Path, text: str, bootstrap: str,
                      shown: int = 6) -> str | None:
    """Say why a program's bootstrap must not run, or `None` if it may.

    It may only when, line for line once each line is trimmed, it is a
    published bootstrap, and that is the one it names itself
    (`bootstrap="nopip6"`).  So a re-indented paste passes, and so does
    a stale one, which is still code this project published; any other
    change, a comment or a space included, is an edit, and nobody can
    say what an edited bootstrap did before `EZPkg` got control (Wayne,
    2026-10-16; see `T.reb`).

    Each differing line is shown beside the published one, with a `|`
    under the first character that differs.

    Arguments:
    * `path` (`Path`):
      The program, for the message.
    * `text` (`str`):
      The program's source.
    * `bootstrap` (`str`):
      The name the calling bootstrap gave itself.
    * `shown` (`int`):
      At most this many differing lines are shown.

    Returns:
    * (`str | None`): The refusal, several lines long, or `None`.
    """
    # Found, published and rightly named is the only way through.
    advice: str = ("Replace it with the bootstrap from "
                   "https://pypi.org/project/ezpkg/, then run it again.")
    node: ast.Try | None = bootstrap_node(text)
    if node is None:
        return (f"ezpkg: {path.name} calls ezpkg as bootstrap "
                f"{bootstrap!r}, but no ezpkg bootstrap was found in it, "
                f"so ezpkg stops here.\n{advice}")
    block: str = find_bootstrap(text) or ""
    name: str | None = bootstrap_name(block)
    if name is not None and name.split()[0] == bootstrap:
        return None
    first: int = node.lineno
    last: int = node.end_lineno or first
    lines: list[str] = [
        (f"ezpkg: {path.name}: its bootstrap (lines {first}-{last}) has "
         f"been edited, so ezpkg stops here.")]
    if name is not None:
        lines.append(f"  It is {name}, but calls itself {bootstrap!r}.")

    # Otherwise each difference from the nearest published bootstrap.
    else:
        mine: list[str] = trimmed(block)
        known: dict[str, list[str]] = published_bootstraps()
        matches: dict[str, difflib.SequenceMatcher[str]] = {
            label: difflib.SequenceMatcher(None, theirs, mine, autojunk=False)
            for label, theirs in known.items()}
        nearest: str = max(matches, key=lambda label: matches[label].ratio())
        lines += bootstrap_differences(
            known[nearest], mine, first, nearest.split()[0],
            matches[nearest].get_opcodes(), shown)
    lines.append(advice)
    return "\n".join(lines)


def bootstrap_differences(published: list[str], mine: list[str], first: int,
                          short: str, opcodes: list[tuple[str, int, int,
                                                          int, int]],
                          shown: int) -> list[str]:
    """Return the lines showing how a bootstrap differs from a published one.

    A changed line is shown twice, the program's and the published
    one's, and then a `|` under the first character that differs.  A
    line only the program has, or only the published one has, is shown
    once and says so.

    Arguments:
    * `published` (`list[str]`):
      The published bootstrap's trimmed lines.
    * `mine` (`list[str]`):
      The program's trimmed lines.
    * `first` (`int`):
      The program's line number of `mine[0]`.
    * `short` (`str`):
      The published bootstrap's short name, such as `nopip6`.
    * `opcodes` (`list[tuple[str, int, int, int, int]]`):
      `difflib.SequenceMatcher.get_opcodes()` from `published` to `mine`.
    * `shown` (`int`):
      At most this many differences are shown.

    Returns:
    * (`list[str]`): The lines, indented, without the advice.
    """
    # The labels are padded alike, so the two texts line up.
    width: int = max(len(f"line {first + len(mine)}:"), len(f"{short}:"))
    differences: list[list[str]] = []
    tag: str
    low: int
    high: int
    start: int
    end: int
    for tag, low, high, start, end in opcodes:
        if tag == "equal":
            continue
        pairs: int = min(high - low, end - start)
        index: int
        for index in range(pairs):
            ours: str = mine[start + index]
            theirs: str = published[low + index]
            column: int = len(os.path.commonprefix([ours, theirs]))
            differences.append([
                f"  {f'line {first + start + index}:':<{width}} {ours}",
                f"  {f'{short}:':<{width}} {theirs}",
                f"  {'':<{width}} {' ' * column}|"])
        for index in range(start + pairs, end):
            differences.append([
                f"  {f'line {first + index}:':<{width}} {mine[index]}",
                f"  {'':<{width}} (not in {short})"])
        for index in range(low + pairs, high):
            differences.append([
                f"  {f'{short}:':<{width}} {published[index]}",
                (f"  {'':<{width}} (missing after line "
                 f"{first + start + pairs - 1})")])
    result: list[str] = [line for difference in differences[:shown]
                         for line in difference]
    if len(differences) > shown:
        result.append(f"  ... and {len(differences) - shown} more")
    return result


def strip_bootstrap(text: str, why: str = "a zipapp carries its packages.",
                    statement: str = "pass") -> str | None:
    """Return a program's text with its pasted bootstrap taken out.

    For a `zipapp`, which carries the program's packages and not
    `ezpkg`, or a `uv` script, whose packages `uv` installs: there
    the bootstrap has nothing to do, and left in it would find no
    `ezpkg` and go to the network for one.  The `try` becomes one
    statement at the same indentation, `pass` unless the caller has a
    use for the line, so a bootstrap nested in a function or an `if`
    leaves that block still valid.  The imports of
    Part 2 stay; they are the standard library, and harmless.

    Arguments:
    * `text` (`str`):
      The program's source.
    * `why` (`str`):
      The comment on the statement, saying where the packages come from.
    * `statement` (`str`):
      The one-line statement that takes the bootstrap's place.

    Returns:
    * (`str | None`): The program without its bootstrap, or `None` when
      it has none to take out.
    """
    # Whole lines, from the `try` to the end of its `except`.
    found: ast.Try | None = bootstrap_node(text)
    if found is None or found.end_lineno is None:
        return None
    lines: list[str] = text.splitlines(keepends=True)
    ending: str = "\r\n" if lines[found.lineno - 1].endswith("\r\n") else "\n"
    replacement: str = (" " * found.col_offset
                        + f"{statement}  # The bootstrap: {why}" + ending)
    return "".join(lines[:found.lineno - 1] + [replacement]
                   + lines[found.end_lineno:])


def script_toml(text: str) -> tuple[re.Match[str], str] | None:
    """Return a program's `script` block and its TOML, uncommented.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`tuple[re.Match[str], str] | None`): Where the block is, for
      `with_script_toml`, and its TOML without the comment markers, or
      `None` when the program has no `script` block.
    """
    # The first `script` block; `script_metadata` refuses two.
    found: re.Match[str] | None = next(
        (match for match in BLOCK.finditer(text)
         if match.group("type") == "script"), None)
    if found is None:
        return None
    return found, "\n".join(
        line[2:] if line.startswith("# ") else line[1:]
        for line in found.group("content").splitlines())


def with_script_toml(text: str, found: re.Match[str], toml: str) -> str:
    """Return a program's text with its `script` block's TOML replaced.

    Arguments:
    * `text` (`str`):
      The program's source, as `script_toml` read it.
    * `found` (`re.Match[str]`):
      The block, as `script_toml` returned it.
    * `toml` (`str`):
      The new TOML, without comment markers.

    Returns:
    * (`str`): The program with the new block and nothing else changed.
    """
    # Commented back, `#` alone for a blank line, as the PEP spells it.
    content: str = "".join(f"# {line}\n" if line else "#\n"
                           for line in toml.splitlines())
    return (text[:found.start("content")] + content
            + text[found.end("content"):])


def uv_setting(toml: str, key: str, value: str | None,
               table: str = "uv") -> str | None:
    """Return a block's TOML with one key of `[tool.uv]` set or removed.

    Or of another `[tool.*]` table, such as `[tool.ezpkg]`.

    The line is edited in place when the key is already there, added
    under the `[tool.uv]` header when the table is, and a table is
    added at the end when neither is.  Removing deletes the line and
    leaves the table, even an empty one.  The result is parsed and compared
    with the original, and anything but the one key changing -- a
    `[tool.uv]` spelled as dotted keys, say, or a value running over
    several lines -- gives `None` rather than a damaged block.

    Arguments:
    * `toml` (`str`):
      The block's TOML, as `script_toml` returns it.
    * `key` (`str`):
      A bare key, such as `exclude-newer`.
    * `value` (`str | None`):
      Its value as TOML spells it, such as `"2026-10-12T19:05:41Z"`
      with its quotes, or `true`, or an array over several lines;
      `None` removes the key, all its lines.
    * `table` (`str`):
      The table under `tool`, `uv` unless said otherwise.

    Returns:
    * (`str | None`): The new TOML, or `None` when this cannot set the
      key safely.
    """
    # What the block says now, and what it should say afterwards.
    setting: str = f"{key} = {value}"
    try:
        expected: dict[str, Any] = tomllib.loads(toml)
        if value is None:
            expected.get("tool", {}).get(table, {}).pop(key, None)
        else:
            expected.setdefault("tool", {}).setdefault(table, {})[key] = (
                tomllib.loads(setting)[key])
    except (tomllib.TOMLDecodeError, AttributeError):
        return None

    # The table runs from its header to the next header, or the end.
    lines: list[str] = toml.split("\n")
    header: int | None = next(
        (index for index, line in enumerate(lines)
         if re.fullmatch(rf"\s*\[tool\.{re.escape(table)}\]\s*(#.*)?",
                         line)), None)
    if header is None and value is not None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", f"[tool.{table}]", *setting.split("\n")]
    elif header is not None:
        # An array's header line is `name = [`, and its last is `]`.
        end: int = next((index for index in range(header + 1, len(lines))
                         if re.match(r"\s*\[[^\]\"']*\]\s*(#.*)?$",
                                     lines[index])),
                        len(lines))
        existing: int | None = next(
            (index for index in range(header + 1, end)
             if re.match(rf"\s*{re.escape(key)}\s*=", lines[index])), None)
        stop: int = (existing or 0) + 1
        if existing is not None and re.match(
                rf"\s*{re.escape(key)}\s*=\s*\[\s*(#.*)?$", lines[existing]):
            while stop < end and not re.match(r"\s*\]", lines[stop]):
                stop += 1
            stop += 1
        if value is None:
            if existing is not None:
                del lines[existing:stop]
        elif existing is None:
            lines[header + 1:header + 1] = setting.split("\n")
        else:
            lines[existing:stop] = setting.split("\n")

    # Only the one key may have changed.
    result: str = "\n".join(lines)
    try:
        if tomllib.loads(result) != expected:
            return None
    except tomllib.TOMLDecodeError:
        return None
    return result


def dependencies_span(toml: str) -> tuple[int, int] | None:
    """Return where a block's `dependencies = [...]` starts and ends.

    Arguments:
    * `toml` (`str`):
      The block's TOML, as `script_toml` returns it.

    Returns:
    * (`tuple[int, int] | None`): The offsets of the key and of the
      character after the `]` that closes its array, or `None` when
      there is no such array, or it does not close.
    """
    # The array runs to the `]` that closes it, skipping over strings,
    # which may hold a `]` of their own, as in `widget[extra]`.
    key: re.Match[str] | None = re.search(
        r"(?m)^dependencies\s*=\s*\[", toml)
    if key is None:
        return None
    depth: int = 1
    index: int = key.end()
    while depth and index < len(toml):
        char: str = toml[index]
        if char in "\"'":
            index = toml.find(char, index + 1)
            if index < 0:
                return None
        elif char == "#":
            index = toml.find("\n", index)
            if index < 0:
                return None
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
        index += 1
    if depth:
        return None
    return key.start(), index


def dependency_comments(text: str) -> dict[str, str]:
    """Return the comment after each entry of Part 1's `dependencies`.

    Such as `# Needed by pandas (excel)`, which keeps an entry no import
    explains (`T.abfd`).  Only a comment that ends an entry's line, with
    no other entry after it on that line, belongs to that entry.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`dict[str, str]`): Each commented entry's comment, `#` and all,
      by the `normal_name` of its requirement's name.
    """
    # The block's lines, and the entries on each.
    lines: list[int] | None = dependency_lines(text)
    block: tuple[re.Match[str], str] | None = script_toml(text)
    if lines is None or block is None:
        return {}
    declared: object = tomllib.loads(block[1]).get("dependencies")
    if not isinstance(declared, list):
        return {}
    source: list[str] = text.splitlines()
    comments: dict[str, str] = {}
    entry: str
    line: int
    for entry, line in zip(declared, lines):
        if lines.count(line) != 1 or line > len(source):
            continue
        rest: str = script_text(source[line - 1])
        found: re.Match[str] | None = re.search(
            r"""^\s*(["'])[^"']*\1\s*,?\s*(#.*?)\s*$""", rest)
        if found is not None:
            comments[normal_name(requirement_name(str(entry)))] = (
                found.group(2))
    return comments


def with_dependency_list(text: str, entries: Sequence[str],
                         comments: Mapping[str, str] | None = None
                         ) -> str | None:
    """Return a program's text with Part 1's `dependencies` replaced.

    An array written on one line stays on one line while it fits in 79
    columns and has no comments; otherwise it is written one entry per
    line, as `pin_dependencies` writes it, each entry keeping its
    comment (`dependency_comments`).  A block with no `dependencies`
    gets one above its first table, since a key after a table header
    would belong to that table.  Everything else in the block, and
    outside it, stays as written.  See `T.kdaiis`.

    Arguments:
    * `text` (`str`):
      The program's source.
    * `entries` (`Sequence[str]`):
      The requirement strings, in order.
    * `comments` (`Mapping[str, str] | None`):
      New comments, `#` and all, by the `normal_name` of an entry's
      name, as `dependency_comments` returns them.

    Returns:
    * (`str | None`): The program with the new block, or `None` when it
      has no block, or one this cannot edit safely.
    """
    # The block, and what it should say afterwards.
    block: tuple[re.Match[str], str] | None = script_toml(text)
    if block is None:
        return None
    found: re.Match[str]
    toml: str
    found, toml = block
    try:
        expected: dict[str, Any] = tomllib.loads(toml)
    except tomllib.TOMLDecodeError:
        return None
    had: bool = "dependencies" in expected
    expected["dependencies"] = list(entries)
    one_line: str = ("dependencies = ["
                     + ", ".join(f'"{entry}"' for entry in entries) + "]")
    noted: dict[str, str] = {**dependency_comments(text), **(comments or {})}
    remarks: list[str] = [noted.get(normal_name(requirement_name(entry)), "")
                          for entry in entries]

    # Replaced where it is, or added above the first table.
    span: tuple[int, int] | None = dependencies_span(toml)
    if span is not None:
        array: str = (
            one_line
            if "\n" not in toml[span[0]:span[1]] and len(one_line) <= 77
            and not any(remarks)
            else "dependencies = [\n"
            + "".join(f'  "{entry}",{f"  {remark}" if remark else ""}\n'
                      for entry, remark in zip(entries, remarks)) + "]")
        toml = toml[:span[0]] + array + toml[span[1]:]
    elif had:
        return None
    else:
        lines: list[str] = toml.split("\n")
        table: int = next((index for index, line in enumerate(lines)
                           if line.lstrip().startswith("[")), len(lines))
        while table and not lines[table - 1].strip():
            table -= 1
        lines.insert(table, one_line)
        toml = "\n".join(lines)

    # Only the dependencies may have changed.
    try:
        if tomllib.loads(toml) != expected:
            return None
    except tomllib.TOMLDecodeError:
        return None
    return with_script_toml(text, found, toml)


def dependency_lines(text: str) -> list[int] | None:
    """Return the line of each entry in Part 1's `dependencies`.

    For messages, which name the line an entry is on.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`list[int] | None`): One line number per entry, in order, or
      `None` when there is no array, or its strings cannot be counted.
    """
    # The block's TOML lines are the program's lines, one for one.
    block: tuple[re.Match[str], str] | None = script_toml(text)
    if block is None:
        return None
    found: re.Match[str]
    toml: str
    found, toml = block
    span: tuple[int, int] | None = dependencies_span(toml)
    if span is None:
        return None
    first: int = text.count("\n", 0, found.start("content")) + 1

    # Each string starts an entry; comments are skipped.
    starts: list[int] = []
    index: int = toml.index("[", span[0]) + 1
    while index < span[1]:
        char: str = toml[index]
        if char in "\"'":
            starts.append(index)
            index = toml.find(char, index + 1)
            if index < 0:
                return None
        elif char == "#":
            index = toml.find("\n", index)
            if index < 0:
                return None
        index += 1
    lines: list[int] = [first + toml.count("\n", 0, start)
                        for start in starts]
    try:
        declared: object = tomllib.loads(toml).get("dependencies")
    except tomllib.TOMLDecodeError:
        return None
    if not isinstance(declared, list) or len(declared) != len(lines):
        return None
    return lines


def pin_dependencies(text: str, pins: Sequence[str]) -> str | None:
    """Return a program's text with Part 1 pinned for `uv`.

    The `dependencies` array in the PEP 723 block is replaced by `pins`,
    and unless the block's `[tool.uv]` table already says otherwise,
    `no-build = true` is added to it: `uv` then installs wheels only, as
    `ezpkg` does with `--only-binary`, and never needs a compiler.
    `exclude-newer` is taken out: the pins and `uv`'s lock already say
    exactly which versions, and `uv` with a date refuses any file whose
    index gives no upload time.  Everything else in the block, and
    outside it, stays as written.

    Arguments:
    * `text` (`str`):
      The program's source.
    * `pins` (`Sequence[str]`):
      The requirements to declare, such as `widget==1.2.3`.

    Returns:
    * (`str | None`): The program with the new block, or `None` when it
      has no block, or no `dependencies` this can find and replace.
    """
    # The block's TOML, without its comment markers.
    block: tuple[re.Match[str], str] | None = script_toml(text)
    if block is None:
        return None
    found: re.Match[str]
    toml: str
    found, toml = block

    # The array is replaced whole.
    span: tuple[int, int] | None = dependencies_span(toml)
    if span is None:
        return None
    array: str = ("dependencies = [\n"
                  + "".join(f'  "{pin}",\n' for pin in pins) + "]")
    toml = toml[:span[0]] + array + toml[span[1]:]
    try:
        metadata: dict[str, Any] = tomllib.loads(toml)
    except tomllib.TOMLDecodeError:
        return None
    if "no-build" not in metadata.get("tool", {}).get("uv", {}):
        built: str | None = uv_setting(toml, "no-build", "true")
        if built is None:
            return None
        toml = built
    undated: str | None = uv_setting(toml, "exclude-newer", None)
    if undated is None:
        return None
    toml = undated
    if tomllib.loads(toml).get("dependencies") != list(pins):
        return None
    return with_script_toml(text, found, toml)


def normal_name(name: str) -> str:
    """Return a distribution name in one spelling.

    PEP 503 compares names this way, so `PyYAML` and `pyyaml`, or
    `python-dateutil` and `python_dateutil`, are one.

    Arguments:
    * `name` (`str`):
      A distribution name.

    Returns:
    * (`str`): The name lowercased, with runs of `-`, `_` and `.` as `_`.
    """
    # The one rule, applied everywhere names are compared.
    return re.sub(r"[-_.]+", "_", name).lower()


def read_program(where: Path) -> tuple[str, str, bool]:
    """Read a program for editing, noting how to write it back.

    A program is not obliged to be UTF-8 with `\\n`, so its encoding
    (byte order mark included) and line endings are kept.

    Arguments:
    * `where` (`Path`):
      The program.

    Returns:
    * (`tuple[str, str, bool]`): The text with `\\n` line endings, its
      encoding, and whether it used `\\r\\n`.

    Raises:
    * `OSError`:
      If it cannot be read.
    """
    # The bytes decide the encoding, as Python itself decides it.
    raw: bytes = where.read_bytes()
    encoding: str = tokenize.detect_encoding(io.BytesIO(raw).readline)[0]
    text: str = raw.decode(encoding)
    return text.replace("\r\n", "\n"), encoding, "\r\n" in text


def write_program(where: Path, text: str, encoding: str,
                  crlf: bool) -> None:
    """Write a program back the way `read_program` found it.

    Arguments:
    * `where` (`Path`):
      The program.
    * `text` (`str`):
      Its new text, with `\\n` line endings.
    * `encoding` (`str`):
      Its encoding, from `read_program`.
    * `crlf` (`bool`):
      Whether it used `\\r\\n`, from `read_program`.

    Raises:
    * `OSError`:
      If it cannot be written.
    """
    # Line endings first, then the encoding.
    if crlf:
        text = text.replace("\n", "\r\n")
    where.write_bytes(text.encode(encoding))


def every_import(text: str) -> list[tuple[str, int, bool]]:
    """Return every top-level module a program imports, in order.

    Unlike `program_imports`, imports the program is ready to see fail
    -- in a `try` that catches `ImportError`, or under `if
    TYPE_CHECKING:` -- are included, marked optional, as are modules
    named in a string (`importlib.import_module("yaml")`): such an import
    never demands a package, but a declared package it uses is not
    unused.  Relative imports are left out.  See `T.kdaiis`.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`list[tuple[str, int, bool]]`): Each module once, its first
      line, and whether every import of it is optional, ordered by
      that line.

    Raises:
    * `SyntaxError`:
      If the program does not parse.
    """
    # The ones that must succeed, and then everything.
    required: set[str] = {module for module, _, _
                          in program_imports(text)}
    first: dict[str, int] = {}
    node: ast.AST
    for node in ast.walk(ast.parse(text)):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level:
            names = [node.module or ""]
        elif (isinstance(node, ast.Call) and node.args
              and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str)
              and (isinstance(node.func, ast.Name)
                   and node.func.id in ("__import__", "import_module")
                   or isinstance(node.func, ast.Attribute)
                   and node.func.attr == "import_module")
              and not node.args[0].value.startswith(".")):
            # A module named in a string, as by `importlib.import_module`
            # (`T.abfd`), never relative.
            names = [node.args[0].value]
        name: str
        for name in names:
            top: str = name.split(".")[0]
            if top and node.lineno < first.get(top, node.lineno + 1):
                first[top] = node.lineno
    return sorted(((module, line, module not in required)
                   for module, line in first.items()),
                  key=lambda one: one[1])


def wheel_modules(wheel: Path) -> set[str]:
    """Return the top-level names a wheel makes importable.

    Read from the zip's member names, so nothing in it runs.  A file
    under `.data/purelib` or `.data/platlib` counts where it will be
    unpacked, beside the others; see `EZPkg.unpack`.

    Arguments:
    * `wheel` (`Path`):
      The wheel.

    Returns:
    * (`set[str]`): Packages, modules and extension modules, such as
      `{"yaml", "_yaml"}`.
    """
    # The first part of each path, after `.data` is moved into place.
    names: set[str] = set()
    archive: zipfile.ZipFile
    member: str
    with zipfile.ZipFile(wheel) as archive:
        for member in archive.namelist():
            parts: list[str] = member.split("/")
            if parts[0].endswith(".dist-info"):
                continue
            if parts[0].endswith(".data"):
                if len(parts) < 3 or parts[1] not in ("purelib", "platlib"):
                    continue
                parts = parts[2:]
            if len(parts) > 1:
                names.add(parts[0])
            elif parts[0].endswith((".py", ".so", ".pyd")):
                names.add(parts[0].split(".")[0])
    return names


# A comment that tells `mypy` to accept an import it cannot follow, in
# any of its spellings: `# type: ignore`, `# type: ignore[import-not-found]`
# and so on, perhaps with the author's own note after it.
TYPE_IGNORE: re.Pattern[str] = re.compile(r"#\s*type:\s*ignore\b")


def with_type_ignores(text: str, adding: Collection[str],
                      others: Collection[str]) -> tuple[str, list[str]]:
    """Give new imports the `mypy` comment the author's others carry.

    An author who checks a program with `mypy` marks each import of a
    fetched package `# type: ignore[import-not-found]`, as the Quick
    Start does, since `mypy` cannot see into the cache.  When the
    imports of declared packages (`others`) carry such a comment, the
    imports whose packages were just added (`adding`) get the same
    one, copied word for word from the nearest such import above, or
    the first when none is above.  When none carries one, nothing is
    added (Wayne, 2026-10-15).  A line that already has a `type:
    ignore`, or continues with a backslash, is left alone; one with a
    comment of its own gets this one first, since `mypy` reads only a
    comment that starts with `type:`.  See `T.kdaiis`.

    Arguments:
    * `text` (`str`):
      The program's source.
    * `adding` (`Collection[str]`):
      The modules whose imports may get the comment.
    * `others` (`Collection[str]`):
      The modules whose imports show the author's habit.

    Returns:
    * (`tuple[str, list[str]]`): The program, and the modules whose
      imports were given the comment.
    """
    # Every comment, by line, with the column it starts at.
    comments: dict[int, tuple[int, str]] = {}
    token: tokenize.TokenInfo
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                comments[token.start[0]] = (token.start[1], token.string)
    except (tokenize.TokenError, SyntaxError):
        return text, []

    # The author's own comments, in the order they appear.
    imports: list[tuple[str, int, bool]] = program_imports(text)
    habits: list[tuple[int, str]] = sorted(
        (line, comments[line][1]) for module, line, _ in imports
        if module in others and line in comments
        and TYPE_IGNORE.match(comments[line][1]))
    if not habits:
        return text, []

    # Each new import gets the nearest one above it.
    lines: list[str] = text.split("\n")
    given: list[str] = []
    module: str
    line: int
    for module, line, _ in imports:
        if module not in adding:
            continue
        written: str = lines[line - 1]
        if written.rstrip().endswith("\\"):
            continue
        copied: str = next((comment for at, comment in reversed(habits)
                            if at < line), habits[0][1])
        if line in comments:
            column: int
            existing: str
            column, existing = comments[line]
            if TYPE_IGNORE.match(existing):
                continue
            lines[line - 1] = (written[:column] + copied + "  "
                               + written[column:])
        else:
            lines[line - 1] = written.rstrip() + "  " + copied
        comments[line] = (len(written), copied)
        given.append(module)
    return "\n".join(lines), given


def index_files(name: str) -> list[str] | None:
    """Ask the package index which files it has for a project.

    The index is the one `pip` would use: `PIP_INDEX_URL`, else PyPI,
    then any `PIP_EXTRA_INDEX_URL`.  Asked before offering to add a
    package whose name was only guessed, so that a misspelt import, or
    a name somebody else has used for source code only (PyPI's `bogus`),
    is caught before any question (Wayne's dogfood, 2026-10-15 and
    2026-10-17).  See `T.kdaiis`.

    Arguments:
    * `name` (`str`):
      A distribution name.

    Returns:
    * (`list[str] | None`): The file names on the first index that has
      the project, an empty list if every one said it has not, and
      `None` when that could not be found out, as with no network.
    """
    # PEP 503 project pages, one per index, until one has it.  Each
    # file is a link whose text is its name.
    indexes: list[str] = [os.environ.get("PIP_INDEX_URL", "")
                          or "https://pypi.org/simple"]
    indexes += os.environ.get("PIP_EXTRA_INDEX_URL", "").split()
    project: str = re.sub(r"[-_.]+", "-", name).lower()
    answer: list[str] | None = []
    index: str
    for index in indexes:
        try:
            with urllib.request.urlopen(
                    f"{index.rstrip('/')}/{project}/", timeout=10) as page:
                text: str = page.read().decode("utf-8", "replace")
            return [html.unescape(found).strip() for found in
                    re.findall(r"<a\b[^>]*>([^<]*)</a>", text)]
        except urllib.error.HTTPError as error:
            if error.code != 404:
                answer = None
        except (OSError, ValueError):
            answer = None
    return answer


# What `pip` says, somewhere in its output, when the index could not be
# reached at all, rather than reached and refusing (`I.ffspo`, case 1).
NO_NETWORK: re.Pattern[str] = re.compile(
    r"NewConnectionError|Failed to establish a new connection"
    r"|Temporary failure in name resolution|Name or service not known"
    r"|nodename nor servname|getaddrinfo failed|Network is unreachable"
    r"|No route to host|ConnectTimeoutError|Read timed out|ProxyError")


def unavailable(text: str, pinned: Mapping[str, str]) -> tuple[str, str]:
    """Work out which package a failed fetch could not get, and why.

    For the end user's one line (`I.ffspo`, cases 2 and 3).  `pip`'s
    `--only-binary` lists only the versions with a wheel for this
    machine, so a version it does not list either was taken off the
    index, or never had a wheel for this machine; the index's own list
    of files tells the two apart (`index_files`).

    Arguments:
    * `text` (`str`):
      What `pip` printed.
    * `pinned` (`Mapping[str, str]`):
      The version each package must be, by `normal_name`, from the
      approvals and from `==` requirements.

    Returns:
    * (`tuple[str, str]`): The package (with its version, if pinned)
      and `"gone"` or `"no wheel"`; or two empty strings when it is
      neither, or cannot be told.
    """
    # `pip`'s own line names the requirement and what it found.
    found: re.Match[str] | None = re.search(
        r"Could not find a version that satisfies the requirement "
        r"(\S+) \(from versions: ([^)]*)\)", text)
    if found is None:
        return "", ""
    name: str = requirement_name(found.group(1))
    listed: list[str] = [one.strip() for one in found.group(2).split(",")
                         if one.strip() and one.strip() != "none"]
    version: str = (found.group(1).partition("==")[2]
                    or pinned.get(normal_name(name), ""))
    files: list[str] | None = index_files(name)
    if files is None:
        return "", ""
    project: str = normal_name(name).replace("-", "_")
    offered: bool = any(
        normal_name(one.split("-")[0]).replace("-", "_") == project
        and (not version or one.split("-")[1:2] == [version]
             or one.startswith(f"{one.split('-')[0]}-{version}."))
        for one in files)
    label: str = f"{name} {version}" if version else name
    if version and not offered:
        return label, "gone"
    if offered and (not listed or version):
        return label, "no wheel"
    return "", ""


def json_api(project: str) -> str:
    """Return the JSON API address of a project, on `pip`'s index.

    pypi.org's, unless `PIP_INDEX_URL` names another index, whose
    `/simple` is replaced by `/pypi`, as PyPI and test.pypi.org lay
    them out, so that `own_pip` asks the index `pip` will (the test
    suite's serves both at its root).

    Arguments:
    * `project` (`str`):
      Such as `pip`.

    Returns:
    * (`str`): Such as `https://pypi.org/pypi/pip/json`.
    """
    # The index without its `/simple`, if it has one.
    base: str = os.environ.get("PIP_INDEX_URL", "").rstrip("/")
    if not base:
        return f"https://pypi.org/pypi/{project}/json"
    base = base.removesuffix("/simple")
    return f"{base}/pypi/{project}/json"


def fetch_url(url: str) -> bytes:
    """Fetch a URL as the bootstrap's `g` does, with `curl` as a fallback.

    python.org's macOS Python has no certificates until its `Install
    Certificates.command` is run, and every Mac has `/usr/bin/curl`,
    which uses the Keychain (`I.btosc`).

    Arguments:
    * `url` (`str`):
      What to fetch.

    Returns:
    * (`bytes`): The body.

    Raises:
    * `urllib.error.URLError`:
      `urllib`'s own error, when `curl` cannot do better.
    """
    # `urllib` first, then `curl`, then `urllib`'s reason.
    try:
        with urllib.request.urlopen(url, None, 60) as response:
            body: bytes = response.read()
            return body
    except urllib.error.URLError as error:
        first: urllib.error.URLError = error
    try:
        return subprocess.run(["curl", "-fsSL", url], capture_output=True,
                              check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        raise first from None


def failure_reason(error: BaseException) -> str:
    """Return the line of a failure that says why, for a message.

    `pip` puts warnings ahead of its error, such as one about an old
    `.egg` somewhere in the system's Python, so the first line is often
    not the reason; its `ERROR:` line is.

    Arguments:
    * `error` (`BaseException`):
      What was raised, perhaps with `pip`'s output in it.

    Returns:
    * (`str`): The last `ERROR:` line, else the first line.
    """
    # `pip` says `ERROR:` before the reason that matters.
    lines: list[str] = [line.strip() for line in str(error).splitlines()
                        if line.strip()]
    errors: list[str] = [line[line.index("ERROR:"):] for line in lines
                         if "ERROR:" in line]
    return (errors or lines or ["failed"])[-1 if errors else 0]


def version_range(name: str, version: str) -> str:
    """Return a requirement for a package, from the version it ran with.

    The floor is the version fetched, so a program never meets an older
    one than it was written against.  The cap is conservative (Wayne,
    2026-10-15): the next minor release for `0.x`, where minor releases
    may break things, and the next major for majors 1 to 9.  A major of
    10 or more gets no cap, since that is where calendar versions live
    (`pip 25.2`, `certifi 2025.8.3`) and fast-moving projects
    (`setuptools 80`), whose next "major" is no warning.  See
    `T.kdaiis`.

    Arguments:
    * `name` (`str`):
      The distribution name, as it will be written.
    * `version` (`str`):
      The version that was fetched, such as `2.32.3`.

    Returns:
    * (`str`): Such as `requests>=2.32.3,<3`, or the name alone when the
      version cannot be read.
    """
    # Only the leading release numbers decide the cap.
    found: re.Match[str] | None = re.match(r"(\d+)(?:\.(\d+))?", version)
    if found is None:
        return name
    major: int = int(found.group(1))
    minor: int = int(found.group(2) or 0)
    cap: str = (f",<0.{minor + 1}" if major == 0
                else f",<{major + 1}" if major < 10 else "")
    return f"{name}>={version}{cap}"


# The answers to a yes-or-no question.


# Imports whose package on PyPI has a different name, for the ones
# that are not installed anywhere to ask.  Only well-known ones: any
# other import is guessed to be its own package's name, and every guess
# is then checked against the wheel that arrives (`wheel_modules`), so
# a wrong guess, or a name somebody squatted, is refused rather than
# installed.  See `T.kdaiis`.
MODULE_PACKAGES: dict[str, str] = {
    "attr": "attrs",
    "bs4": "beautifulsoup4",
    "Crypto": "pycryptodome",
    "cv2": "opencv-python",
    "dateutil": "python-dateutil",
    "docx": "python-docx",
    "dotenv": "python-dotenv",
    "fitz": "PyMuPDF",
    "git": "GitPython",
    "jwt": "PyJWT",
    "OpenSSL": "pyOpenSSL",
    "PIL": "Pillow",
    "pptx": "python-pptx",
    "pythoncom": "pywin32",
    "pywintypes": "pywin32",
    "serial": "pyserial",
    "skimage": "scikit-image",
    "sklearn": "scikit-learn",
    "socks": "PySocks",
    "usb": "pyusb",
    "win32api": "pywin32",
    "win32com": "pywin32",
    "win32con": "pywin32",
    "win32file": "pywin32",
    "win32gui": "pywin32",
    "win32process": "pywin32",
    "yaml": "PyYAML",
}


def providing(module: str, providers: Mapping[str, list[str]]) -> list[str]:
    """Return the installed distributions that provide a top-level module.

    `packages_distributions` reads each distribution's `RECORD` or
    `top_level.txt`, and Debian and Ubuntu strip both from the packages
    they install, so here it cannot see that `python3-rich` provides
    `rich` (found by `drive`, 2026-10-17).  Then a distribution named
    as the module, or as `MODULE_PACKAGES` names it, whose metadata
    lists no files at all, is taken to be the one.  One that does list
    its files, and not this module, is not.

    Arguments:
    * `module` (`str`):
      An importable top-level module.
    * `providers` (`Mapping[str, list[str]]`):
      What `importlib.metadata.packages_distributions` returned.

    Returns:
    * (`list[str]`): The distribution names, sorted, perhaps none.
    """
    # The metadata's own answer, when it has one.
    found: list[str] = sorted(set(providers.get(module, [])))
    if found:
        return found

    # Otherwise a silent distribution of the expected name.
    name: str
    for name in dict.fromkeys([MODULE_PACKAGES.get(module, module), module]):
        try:
            distribution: importlib.metadata.Distribution = (
                importlib.metadata.distribution(name))
        except (importlib.metadata.PackageNotFoundError, ValueError):
            continue
        if all(distribution.read_text(listing) is None for listing in (
                "RECORD", "top_level.txt", "installed-files.txt",
                "SOURCES.txt")):
            return [distribution.metadata["Name"] or name]
    return []


# The names an `if` test uses when it picks an import by platform, as in
# `if sys.platform == "win32": import winreg`.  See `program_imports`.
PLATFORM_NAMES: frozenset[str] = frozenset(
    {"sys.platform", "os.name", "platform.system", "sys_platform"})

# The platform tests `platform_marker` turns into PEP 508 markers: the
# test's own spelling, and the marker variable it means.
MARKER_VARIABLES: dict[str, str] = {
    "sys.platform": "sys_platform",
    "os.name": "os_name",
    "platform.system()": "platform_system",
}

# The values `sys.platform.startswith(...)` can test that are whole
# `sys.platform` values under Python 3, so that `==` says the same.
WHOLE_PLATFORMS: frozenset[str] = frozenset(
    {"win32", "darwin", "linux", "cygwin", "emscripten", "wasi"})


def platform_marker(test: ast.expr, negate: bool = False) -> str | None:
    """Return the PEP 508 marker an `if` test on the platform means.

    Only the plain forms are read: `sys.platform == "win32"` (or `!=`,
    either way round), `sys.platform.startswith("linux")`, `os.name ==
    "nt"`, `platform.system() == "Windows"`, `not` before one of them,
    and `and` between them.  Anything else has no marker, rather than a
    guessed one (Wayne, 2026-10-22).

    Arguments:
    * `test` (`ast.expr`):
      The `if` statement's test.
    * `negate` (`bool`):
      True for the `else` branch, which runs when the test fails.

    Returns:
    * (`str | None`): Such as `sys_platform == 'win32'`, or `None`;
      single quotes, since the entry goes inside TOML's double ones.
    """
    # `not` flips the test, and `and` joins tests (which cannot be
    # negated as one marker).
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return platform_marker(test.operand, not negate)
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        if negate:
            return None
        parts: list[str | None] = [platform_marker(one)
                                   for one in test.values]
        if None in parts:
            return None
        return " and ".join(one for one in parts if one is not None)

    # `sys.platform.startswith("linux")` is `==` for a whole value.
    if (isinstance(test, ast.Call) and isinstance(test.func, ast.Attribute)
            and test.func.attr == "startswith"
            and ast.unparse(test.func.value) == "sys.platform"
            and len(test.args) == 1 and not test.keywords
            and isinstance(test.args[0], ast.Constant)
            and test.args[0].value in WHOLE_PLATFORMS):
        return (f'sys_platform {"!=" if negate else "=="} '
                f"'{test.args[0].value}'")

    # A comparison of one of `MARKER_VARIABLES` with a string.
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq | ast.NotEq)):
        return None
    sides: list[ast.expr] = [test.left, test.comparators[0]]
    variable: str | None = next(
        (MARKER_VARIABLES[ast.unparse(side)] for side in sides
         if ast.unparse(side) in MARKER_VARIABLES), None)
    value: object = next(
        (side.value for side in sides if isinstance(side, ast.Constant)),
        None)
    if variable is None or not isinstance(value, str) or "'" in value:
        return None
    equal: bool = isinstance(test.ops[0], ast.Eq) != negate
    return f"{variable} {'==' if equal else '!='} '{value}'"


def import_markers(text: str) -> dict[str, str]:
    """Return the platform marker each guarded import implies.

    A module every import of which sits under the same platform test
    (`platform_marker`), such as `win32api` under `if sys.platform ==
    "win32":`, needs its package only there, so its entry gets that
    marker: `pywin32; sys_platform == 'win32'` (Wayne, 2026-10-22).  A
    module imported anywhere else, or under a test this cannot read,
    gets none.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`dict[str, str]`): The marker of each guarded top-level module.

    Raises:
    * `SyntaxError`:
      If the program does not parse.
    """
    # The marker over each import, "" for none, by module.
    seen: dict[str, set[str]] = {}

    def visit(nodes: list[ast.stmt], over: list[str | None]) -> None:
        """Note the imports in `nodes`, under the markers `over`."""
        node: ast.stmt
        for node in nodes:
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                names = [node.module or ""]
            known: bool = bool(over) and None not in over
            marker: str = (" and ".join(one for one in over if one)
                           if known else "")
            name: str
            for name in names:
                if name:
                    seen.setdefault(name.split(".")[0], set()).add(marker)
            if isinstance(node, ast.If):
                visit(node.body, [*over, platform_marker(node.test)])
                visit(node.orelse,
                      [*over, platform_marker(node.test, negate=True)])
                continue
            field: str
            for field in ("body", "orelse", "finalbody"):
                inner: Any = getattr(node, field, None)
                if isinstance(inner, list):
                    visit(inner, over)
            if isinstance(node, ast.Try | ast.TryStar):
                handler: ast.ExceptHandler
                for handler in node.handlers:
                    visit(handler.body, over)
            if isinstance(node, ast.Match):
                case: ast.match_case
                for case in node.cases:
                    visit(case.body, over)

    visit(ast.parse(text).body, [])
    return {module: next(iter(markers)) for module, markers in seen.items()
            if len(markers) == 1 and "" not in markers}


def marker_holds(marker: str) -> bool:
    """Say whether a marker `platform_marker` wrote holds on this computer.

    Arguments:
    * `marker` (`str`):
      Clauses such as `sys_platform == 'win32'`, joined by ` and `.

    Returns:
    * (`bool`): True when every clause holds here.
    """
    # Each clause is `variable op "value"`.
    here: dict[str, str] = {"sys_platform": sys.platform,
                            "os_name": os.name,
                            "platform_system": platform.system()}
    clause: str
    for clause in marker.split(" and "):
        variable, operator, value = clause.split(" ", 2)
        if (here.get(variable) == value.strip("'\"")) != (operator == "=="):
            return False
    return True


def holds_here(entry: str) -> bool:
    """Say whether an entry with a `platform_marker` applies here.

    Arguments:
    * `entry` (`str`):
      A requirement, such as `pywin32; sys_platform == 'win32'`.

    Returns:
    * (`bool`): True with no marker, or one that holds on this computer.
    """
    # Only the markers `import_markers` writes are read.
    marker: str = entry.partition(";")[2].strip()
    return not marker or marker_holds(marker)


def syntax_floor(text: str) -> tuple[int, int]:
    """Return the oldest Python, 3.11 or newer, whose syntax a program uses.

    Python's own parser is asked to accept only each version's grammar
    in turn (`feature_version`), which catches most new syntax, such as
    3.12's `type` statement, though not all of it (Wayne, 2026-10-22).

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`tuple[int, int]`): Such as `(3, 11)`; the running Python's own
      when no older grammar parses it.
    """
    # The oldest first; this Python's own parses whatever it runs.
    minor: int
    for minor in range(11, sys.version_info.minor):
        try:
            ast.parse(text, feature_version=(3, minor))
            return 3, minor
        except SyntaxError:
            continue
    return 3, sys.version_info.minor


def package_floor(specifier: str) -> tuple[int, ...] | None:
    """Return the floor of a package's `Requires-Python`, if it has one.

    Unlike `python_floor`, which reads a program's own `requires-python`
    and refuses anything but one clause, this takes the highest `>=` (or
    `>`, `==`, `~=`) clause of a list such as `>=3.9,<4`, since only the
    floor matters for a release's Part 1.

    Arguments:
    * `specifier` (`str`):
      A distribution's `Requires-Python`, such as `>=3.9`.

    Returns:
    * (`tuple[int, ...] | None`): The floor, or `None` for none.
    """
    # Every lower-bound clause, the highest wins.
    floors: list[tuple[int, ...]] = [
        tuple(int(part) for part in found.group(1).split("."))
        for found in re.finditer(r"(?:>=|>|==|~=)\s*(\d+(?:\.\d+)*)",
                                 specifier)]
    return max(floors) if floors else None


def with_script_block(text: str) -> str:
    """Return a program with an empty `script` block, if it had none.

    A developer writes no Part 1 (Wayne, 2026-10-22), so a release puts
    one into its copy, after the `#!` line and any encoding line, where
    `quick_start.py` has its own.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`str`): The program, with a block declaring no packages.
    """
    # Already there, or after the lines that must stay first.
    if script_toml(text) is not None:
        return text
    lines: list[str] = text.splitlines(keepends=True)
    at: int = 0
    while at < min(len(lines), 2) and (
            (at == 0 and lines[0].startswith("#!"))
            or re.match(r"^[ \t\f]*#.*?coding[:=]", lines[at])):
        at += 1
    block: str = ("# Part 1: The packages this program needs, written by "
                  "ezpkg.\n# /// script\n# dependencies = []\n# ///\n")
    return "".join(lines[:at]) + block + "".join(lines[at:])


def with_requires_python(toml: str, value: str) -> str | None:
    """Return a block's TOML with its top-level `requires-python` set.

    Arguments:
    * `toml` (`str`):
      The block's TOML, as `script_toml` returns it.
    * `value` (`str`):
      Such as `>=3.11`, without quotes.

    Returns:
    * (`str | None`): The new TOML, or `None` when this cannot set it
      safely.
    """
    # In place, or first, since a key after a table would be the table's.
    setting: str = f'requires-python = "{value}"'
    lines: list[str] = toml.split("\n")
    existing: int | None = next(
        (index for index, line in enumerate(lines)
         if re.match(r"\s*requires-python\s*=", line)), None)
    if existing is None:
        lines.insert(0, setting)
    else:
        lines[existing] = setting
    result: str = "\n".join(lines)
    try:
        expected: dict[str, Any] = tomllib.loads(toml)
        expected["requires-python"] = value
        if tomllib.loads(result) != expected:
            return None
    except tomllib.TOMLDecodeError:
        return None
    return result


def program_imports(text: str) -> list[tuple[str, int, bool]]:
    """Return the top-level modules a program imports, and where.

    Read with `ast`, so nothing is imported and nothing runs.  Called
    by `EZPkg.import_problems`, for an export, which is when a
    package the author's own Python happens to have, and Part 1 does
    not name, turns into a program that fails somewhere else, and for
    an ordinary run's warning.  See `T.cibe` and `T.siofr` in
    `TASKS/`.

    Three kinds of import are left out, because the program is ready
    for them to fail or never runs them: one in the body of a `try`
    whose handlers catch `ImportError`, `ModuleNotFoundError`,
    `Exception` or everything; one under `if TYPE_CHECKING:`; and a
    relative one.  An import under an `if` that tests the platform is
    kept but marked, since on this machine it may find nothing and
    still be right.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`list[tuple[str, int, bool]]`): Each module once, as its
      top-level name, the line that first imports it, and whether that
      import is under a platform test, in order of first appearance.

    Raises:
    * `SyntaxError`:
      If the text is not Python, which a running program's is.
    """
    # Breadth does not matter, only what encloses each import.
    found: dict[str, tuple[int, bool]] = {}
    tolerant: tuple[str, ...] = (
        "ImportError", "ModuleNotFoundError", "Exception", "BaseException")

    def catches(handler: ast.ExceptHandler) -> bool:
        """Report whether an `except` clause catches a failed import."""
        # A bare `except:`, one name, or a tuple of names.
        if handler.type is None:
            return True
        kinds: list[ast.expr] = (list(handler.type.elts)
                                 if isinstance(handler.type, ast.Tuple)
                                 else [handler.type])
        return any(ast.unparse(kind).split(".")[-1] in tolerant
                   for kind in kinds)

    def visit(nodes: list[ast.stmt], guarded: bool) -> None:
        """Record the imports in `nodes`, descending into blocks."""
        node: ast.stmt
        for node in nodes:
            # The imports themselves, top-level names only.
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                names = [node.module or ""]
            name: str
            for name in names:
                top: str = name.split(".")[0]
                if top and top not in found:
                    found[top] = (node.lineno, guarded)

            # A `try` that expects the import to fail keeps its body.
            if isinstance(node, ast.Try | ast.TryStar):
                if not any(catches(one) for one in node.handlers):
                    visit(node.body, guarded)
                visit(node.orelse, guarded)
                visit(node.finalbody, guarded)
                handler: ast.ExceptHandler
                for handler in node.handlers:
                    visit(handler.body, guarded)
                continue

            # `TYPE_CHECKING` never runs; a platform test may not here.
            if isinstance(node, ast.If):
                test: str = ast.unparse(node.test)
                if "TYPE_CHECKING" not in test:
                    visit(node.body, guarded or any(
                        platform in test for platform in PLATFORM_NAMES))
                visit(node.orelse, guarded)
                continue

            # Everything else with statements inside it.
            field: str
            for field in ("body", "orelse", "finalbody"):
                inner: Any = getattr(node, field, None)
                if isinstance(inner, list):
                    visit(inner, guarded)
            if isinstance(node, ast.Match):
                case: ast.match_case
                for case in node.cases:
                    visit(case.body, guarded)

    visit(ast.parse(text).body, False)
    return [(name, line, guarded)
            for name, (line, guarded) in found.items()]


def imports_above_bootstrap(text: str) -> list[tuple[str, int]]:
    """Return the imports a program makes before its bootstrap runs.

    The README rule is that every import goes after the bootstrap,
    because one above it runs first: on a machine whose cache is still
    empty, `import cowsay` there fails before the bootstrap can fetch
    `cowsay`, though the author's own machine never shows it.  The
    exceptions are `from __future__`, which must come first, and the
    bootstrap's own imports (Part 2), recognised as the ones binding a
    name the bootstrap uses, so that every bootstrap's Part 2 passes
    without a list to keep up to date.  See `T.fipab` in `TASKS/`.

    An import inside a function or lambda defined above the bootstrap
    runs only when called, so it is not counted.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`list[tuple[str, int]]`): Each offending import, as the module
      it names and its line, in order; empty when there is no
      bootstrap.

    Raises:
    * `SyntaxError`:
      If the text is not Python, which a running program's is.
    """
    # Without a bootstrap there is no above.
    tree: ast.Module = ast.parse(text)
    bootstrap: ast.Try | None = bootstrap_node(text)
    if bootstrap is None:
        return []
    used: set[str] = {node.id for node in ast.walk(bootstrap)
                      if isinstance(node, ast.Name)}

    # Every statement that runs before the bootstrap's line.
    found: list[tuple[str, int]] = []

    def visit(node: ast.AST) -> None:
        """Record the imports under `node` that run before the paste."""
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef
                      | ast.Lambda) or node is bootstrap:
            return
        bound: list[str] = []
        module: str = ""
        if isinstance(node, ast.Import):
            bound = [alias.asname or alias.name.split(".")[0]
                     for alias in node.names]
            module = ", ".join(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                return
            bound = [alias.asname or alias.name for alias in node.names]
            module = "." * node.level + (node.module or "")
        if bound and getattr(node, "lineno", 0) < bootstrap.lineno:
            if not set(bound) <= used:
                found.append((module, node.lineno))
            return
        child: ast.AST
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return sorted(found, key=lambda one: one[1])


def statements_above_bootstrap(text: str) -> list[int]:
    """Return the lines of statements that do something before the bootstrap.

    They run before `ezpkg` has done its work, and again when
    `EZPkg.restart` starts the program afresh after an edit, so a
    `print` there is seen twice (Wayne, 2026-10-18).  Allowed above
    the bootstrap: the docstring, imports (`imports_above_bootstrap`
    judges those), `def`, `class`, assignments and `pass`.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`list[int]`): Each such statement's first line; empty when there
      is no bootstrap.

    Raises:
    * `SyntaxError`:
      If the text is not Python.
    """
    # Only the top level: anything nested is inside one of these.
    tree: ast.Module = ast.parse(text)
    bootstrap: ast.Try | None = bootstrap_node(text)
    if bootstrap is None:
        return []
    quiet: tuple[type, ...] = (
        ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef,
        ast.ClassDef, ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Pass)
    found: list[int] = []
    index: int
    node: ast.stmt
    for index, node in enumerate(tree.body):
        # The bootstrap, or the `if` it is indented in, ends it (by
        # line, since `bootstrap_node` parsed a tree of its own).
        if (node.end_lineno or node.lineno) >= bootstrap.lineno:
            break
        docstring: bool = (index == 0 and isinstance(node, ast.Expr)
                           and isinstance(node.value, ast.Constant)
                           and isinstance(node.value.value, str))
        if not docstring and not isinstance(node, quiet):
            found.append(node.lineno)
    return found


def lock_mismatches(lock: dict[str, Any],
                    approved: dict[str, str]) -> list[str]:
    """Return the approved packages a `uv` lock disagrees with.

    `uv` resolves for itself, so its lock is checked against the
    approvals: each approved package must be listed, at its version,
    with a wheel whose SHA-256 starts with the approved `id:`.  Wheels
    for other platforms are listed too and are not checked, since
    nothing here has approved them.

    Arguments:
    * `lock` (`dict[str, Any]`):
      A `prog.py.lock`, as `tomllib` reads it.
    * `approved` (`dict[str, str]`):
      Pins to ids, as `EZPkg.approved` returns them.

    Returns:
    * (`list[str]`): One line per package missing or different, sorted;
      empty when the lock agrees.
    """
    # Every wheel the lock lists, by its pin, with its hashes.
    listed: dict[str, list[str]] = {}
    package: dict[str, Any]
    for package in lock.get("package", []):
        wheel: dict[str, Any]
        for wheel in package.get("wheels", []):
            where: str = wheel.get("url") or wheel.get("path") or ""
            pin: str = wheel_pin(where.rsplit("/", 1)[-1])
            listed.setdefault(normal_pin(pin), []).append(
                str(wheel.get("hash", "")))
    problems: list[str] = []
    identity: str
    for pin, identity in sorted(approved.items()):
        hashes: list[str] = listed.get(normal_pin(pin), [])
        if not hashes:
            problems.append(f"{pin}: not in the lock")
        elif not any(hashes):
            problems.append(f"{pin}: lock has no hash")
        elif not any(one.startswith(f"sha256:{identity}") for one in hashes):
            problems.append(f"{pin}: lock has another file ("
                            + ", ".join(one for one in hashes if one) + ")")
    return problems


def everywhere_approvals(lock: dict[str, Any], approved: Mapping[str, str],
                         tags: Mapping[str, str]
                         ) -> tuple[dict[str, str], dict[str, str]]:
    """Return approvals that cover every computer a `uv` lock covers.

    A developer's run approves what arrived on the developer's own
    computer, but a package can need others only elsewhere, as `tqdm`
    needs `colorama` on Windows alone, and `verify` refuses anything
    unapproved.  `pip` judges such markers by the computer it runs on
    even when told another platform (measured 2026-10-20, `pip`
    26.2.2), while `uv` resolves for every computer at once, so its
    lock names them all, with each wheel's SHA-256 (`T.ee`).

    What was approved stays as it was.  Each package the lock adds gets
    one row: its pure-Python wheel if it has one, which serves every
    computer, or else its first compiled wheel, with that wheel's
    `tag:`, so that elsewhere only its version is checked, as for the
    developer's own compiled packages (S2.4d).  A package with no wheel
    in the lock is left out: `ezpkg` installs only wheels anyway.

    Arguments:
    * `lock` (`dict[str, Any]`):
      A `prog.py.lock`, as `tomllib` reads it.
    * `approved` (`Mapping[str, str]`):
      Pins to ids, as `EZPkg.approved` returns them.
    * `tags` (`Mapping[str, str]`):
      The platform of each compiled pin, as `approval_tags` returns
      them.

    Returns:
    * (`tuple[dict[str, str], dict[str, str]]`): The pins to ids, and
      the pins to tags, as `approvals_array` takes them.
    """
    # The approvals as they were, then what only other computers need.
    rows: dict[str, str] = dict(approved)
    platforms: dict[str, str] = dict(tags)
    known: set[str] = {normal_pin(pin) for pin in approved}
    package: dict[str, Any]
    for package in lock.get("package", []):
        files: list[tuple[str, str]] = []
        wheel: dict[str, Any]
        for wheel in package.get("wheels", []):
            where: str = wheel.get("url") or wheel.get("path") or ""
            name: str = where.rsplit("/", 1)[-1]
            digest: str = str(wheel.get("hash", ""))
            if name.endswith(".whl") and digest.startswith("sha256:"):
                files.append((name, digest.removeprefix("sha256:")))
        if not files or normal_pin(wheel_pin(files[0][0])) in known:
            continue

        # One wheel speaks for the package, pure Python first.
        chosen: str
        chosen, digest = min(files, key=lambda one: (
            wheel_tag(one[0]) != "", one[0]))
        pin: str = wheel_pin(chosen)
        rows[pin] = digest[:ID_DIGITS]
        if wheel_tag(chosen):
            platforms[pin] = wheel_tag(chosen)
        known.add(normal_pin(pin))
    return rows, platforms


# The oldest `uv` an installed one may be; anything older is passed over
# and `EZPkg.uv` fetches a newer one.  Measured 2026-10-21: `uv` 0.6.0
# passed the `email`, `zipapp` and `uv` export tests.
UV_FLOOR: tuple[int, ...] = (0, 6, 0)


def uv_version(command: str) -> tuple[int, ...] | None:
    """Return the version of a `uv`, or `None` if it does not say.

    Arguments:
    * `command` (`str`):
      The `uv` to ask.

    Returns:
    * (`tuple[int, ...] | None`): Such as `(0, 12, 21)`, from `uv
      0.12.21 (x86_64-unknown-linux-gnu)`.
    """
    # The second word, up to anything that is not a number.
    try:
        said: str = subprocess.run(
            [command, "--version"], capture_output=True, text=True,
            check=False, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    found: re.Match[str] | None = re.match(r"uv (\d+(?:\.\d+)*)", said)
    return tuple(map(int, found[1].split("."))) if found else None


def find_uv() -> str | None:
    """Return an installed `uv`, or `None` when none is new enough.

    The `PATH` first, then `~/.local/bin`, which is where `uv`'s own
    installer puts it and which is not always on the `PATH`.  One older
    than `UV_FLOOR` does not count.  `EZPkg.uv` fetches one when this
    finds none.

    Returns:
    * (`str | None`): The command to run.
    """
    # `shutil.which` also checks that the file is executable.
    found: str | None = (
        shutil.which("uv")
        or shutil.which("uv", path=str(Path.home() / ".local" / "bin")))
    version: tuple[int, ...] | None = (
        uv_version(found) if found else None)
    return found if version is not None and version >= UV_FLOOR else None


def refresh(path: Path, text: str) -> None:
    """Write a file only when its contents would change.

    Making an object used to write a file every time, which is a side
    effect nobody asks a constructor for and which touches the
    modification time of a file a person may be reading; see
    6.10.5 of `T.rd`.  A stale copy is still replaced, so a newer
    `ezpkg` still reaches a cache that holds an older file.

    Arguments:
    * `path` (`Path`):
      The file to write.
    * `text` (`str`):
      What it should hold.
    """
    # An unreadable file is treated as absent, and so is rewritten.
    present: str = ""
    try:
        present = path.read_text(encoding="utf-8")
    except OSError:
        present = ""
    if present != text:
        path.write_text(text, encoding="utf-8")


def dependency_fingerprint(text: str, entries: Sequence[str],
                           approved: Collection[str]) -> str:
    """Return a short fingerprint of what decides a program's target.

    Its imports in order (optional or not), its `dependencies` (with
    their comments, which keep an entry) and what its approvals cover: when none of these
    has changed, neither has any discrepancy between them, so it is not
    worked out again.  `ezpkg`'s own version goes in too, so a newer
    `ezpkg`, whose rules may differ, looks at every program once more
    (Wayne's dogfood, 2026-10-15).  Eight hex digits, since it is only ever compared
    with the last one for the same program (Wayne, 2026-10-15).

    Arguments:
    * `text` (`str`):
      The program's source.
    * `entries` (`Sequence[str]`):
      Its `dependencies`.
    * `approved` (`Collection[str]`):
      The normalized names its approvals cover.

    Returns:
    * (`str`): Eight hex digits of a SHA-256.

    Raises:
    * `SyntaxError`:
      If the program does not parse.
    """
    # Moving an import can change the target's order, so order counts.
    key: str = json.dumps({
        "imports": [[module, optional] for module, _, optional
                    in every_import(text)],
        "entries": list(entries),
        "comments": dependency_comments(text),
        "approved": sorted(approved),
        "ezpkg": __version__})
    return hashlib.sha256(key.encode()).hexdigest()[:8]


def unused_key(unused: Collection[str]) -> str:
    """Return what `EZPkg.unused_lately` adds to a dependency fingerprint.

    So that `EZPkg.sync_dependencies` looks again once recorded runs
    show an entry unused, though nothing in the program has changed.

    Arguments:
    * `unused` (`Collection[str]`):
      The `normal_name`s `unused_lately` returned.

    Returns:
    * (`str`): Empty when there are none, else `/` and eight hex digits.
    """
    # Empty keeps the fingerprints of programs with nothing unused.
    if not unused:
        return ""
    joined: str = ",".join(sorted(unused))
    return "/" + hashlib.sha256(joined.encode()).hexdigest()[:8]


def line_list(numbers: Collection[int]) -> str:
    """Return line numbers the way a message names them.

    Arguments:
    * `numbers` (`Collection[int]`):
      Line numbers, in any order, perhaps repeated.

    Returns:
    * (`str`): Such as `line 5`, `lines 5-6` or `lines 5, 8-9`.
    """
    # Runs of consecutive lines become ranges.
    ordered: list[int] = sorted(set(numbers))
    runs: list[list[int]] = []
    number: int
    for number in ordered:
        if runs and number == runs[-1][-1] + 1:
            runs[-1].append(number)
        else:
            runs.append([number])
    spelled: str = ", ".join(str(run[0]) if len(run) == 1
                             else f"{run[0]}-{run[-1]}" for run in runs)
    return ("line " if len(ordered) == 1 else "lines ") + spelled


def run_again(environment: Mapping[str, str]) -> None:
    """Start the running program again, as it was started, and never return.

    For `EZPkg.switch` and `EZPkg.restart`: the same Python, the same
    arguments, in the environment given.  Windows has no `exec` that
    keeps the process, so there the program runs as a child and its
    status is passed on.

    Arguments:
    * `environment` (`Mapping[str, str]`):
      The environment to start it in.

    Raises:
    * `SystemExit`:
      With the program's own exit status on Windows.
    """
    # Everything said so far is said before the program starts again.
    command: list[str] = [sys.executable, *sys.orig_argv[1:]]
    sys.stdout.flush()
    sys.stderr.flush()
    if os.name == "nt":
        raise SystemExit(subprocess.run(command, env=dict(environment),
                                        check=False).returncode)
    os.execve(sys.executable, command, dict(environment))


def and_list(words: Sequence[str], last: str = "and") -> str:
    """Return words joined the way a sentence lists them.

    Arguments:
    * `words` (`Sequence[str]`):
      The words, in order.
    * `last` (`str`):
      The word before the last one, such as `or`.

    Returns:
    * (`str`): Such as `a`, `a and b` or `a, b and c`.
    """
    # The last two joined by "and".
    return (", ".join(words[:-1]) + f" {last} " + words[-1]
            if len(words) > 1 else "".join(words))


def script_text(line: str) -> str:
    """Return a script block line as TOML, without its leading `# `.

    Arguments:
    * `line` (`str`):
      A line of a PEP 723 block, such as `# [tool.ezpkg]`.

    Returns:
    * (`str`): Such as `[tool.ezpkg]`; a bare `#` is empty.
    """
    # PEP 723 allows exactly `#` or `# ` in front.
    return line[2:] if line.startswith("# ") else line.lstrip("#")


@dataclasses.dataclass
class Discrepancy:
    """How a program's `dependencies` differ from what its imports imply.

    The target is the `dependencies` the imports imply: each imported
    module's package, in the order of each module's first import.  An
    entry no import explains -- one with a comment, which keeps it, or
    one whose modules are unknown here, such as `pywin32` on Linux --
    keeps its place after the same neighbour.  Built by
    `EZPkg.discrepancy`.  See `T.kdaiis` in `TASKS/`.

    Attributes:
    * `program` (`Path`):
      The program.
    * `entries` (`list[str]`):
      Its `dependencies`, as written.
    * `lines` (`list[int]`):
      The line of each entry.
    * `order` (`list[tuple[str, int, str]]`):
      The target's skeleton, in import order: `("entry", index, "")`
      for an entry an import places, `("add", 0, package)` for an
      addition.
    * `placed_by` (`dict[int, int]`):
      For each entry an import places, that import's line.
    * `additions` (`list[tuple[int, str, str]]`):
      The line, module and package of each import that needs one.
    * `removals` (`list[int]`):
      The index of each entry nothing imports.
    * `used` (`set[str]`):
      The modules whose packages are declared, for
      `with_type_ignores`.
    * `guessed` (`set[str]`):
      The additions whose package names were guessed, which the index
      is asked about before they are offered.
    * `uncommented` (`int | None`):
      The line of an import of `ezpkg` that lacks the `type: ignore`
      comment the author's other imports carry, or `None`.  `mypy`
      cannot see `~/.ezpkg`, where the bootstrap puts `ezpkg`, any more
      than it can see the packages (Wayne's dogfood, 2026-10-15).
    """

    program: Path
    entries: list[str]
    lines: list[int]
    order: list[tuple[str, int, str]]
    placed_by: dict[int, int]
    additions: list[tuple[int, str, str]]
    removals: list[int]
    used: set[str]
    guessed: set[str] = dataclasses.field(default_factory=set)
    uncommented: int | None = None

    def pending(self) -> bool:
        """Say whether there is anything to raise at all.

        Returns:
        * (`bool`): True when `dependencies` is not the target, or an
          import of `ezpkg` lacks the author's `mypy` comment.
        """
        # Any kind of difference.
        return (self.target() != self.entries
                or self.uncommented is not None)

    def arrange(self, added: Collection[str],
                removed: Collection[int]) -> list[str]:
        """Return the `dependencies` with some changes made.

        Arguments:
        * `added` (`Collection[str]`):
          The packages of the additions to make.
        * `removed` (`Collection[int]`):
          The indexes of the entries to remove.

        Returns:
        * (`list[str]`): The entries, in the target's order.
        """
        # What the imports place, then the rest after their neighbours.
        result: list[tuple[str, int, str]] = [
            item for item in self.order
            if item[0] == "entry" or item[2] in added]
        placed: set[int] = {item[1] for item in result
                            if item[0] == "entry"}
        front: int = 0
        index: int
        for index in range(len(self.entries)):
            if index in placed or index in removed:
                continue
            before: list[tuple[int, int]] = [
                (item[1], position) for position, item in enumerate(result)
                if item[0] == "entry" and item[1] < index]
            at: int
            if before:
                at = max(before)[1] + 1
            else:
                at = front
                front += 1
            result.insert(at, ("entry", index, ""))
            placed.add(index)
        return [self.entries[item[1]] if item[0] == "entry" else item[2]
                for item in result]

    def imported(self, added: Collection[str]) -> list[str]:
        """Return the packages the imports imply, for the next run.

        So that `EZPkg.note_loaded` can tell a package the program
        imports from one loaded behind the scenes (`T.abfd`).

        Arguments:
        * `added` (`Collection[str]`):
          The packages of the additions being made.

        Returns:
        * (`list[str]`): Their `normal_name`s, sorted.
        """
        # The entries the imports place, and the additions.
        return sorted({normal_name(requirement_name(self.entries[index]))
                       for index in self.placed_by}
                      | {normal_name(requirement_name(package))
                         for package in added})

    def target(self) -> list[str]:
        """Return the `dependencies` with every change made.

        Returns:
        * (`list[str]`): The target.
        """
        # Everything added, everything unexplained removed.
        return self.arrange({package for _, _, package in self.additions},
                            self.removals)

    def reported(self, final: Sequence[str], before: str, edited: str,
                 modules: Mapping[str, str]) -> list[str]:
        """Return a line for each change `reconcile` made, in line order.

        For `verbosity = "medium"` (`T.abfd`): each entry added, removed or
        moved is named, with its line afterwards, and the `mypy` comment
        an added entry's import was given (Wayne, `ux11`).

        Arguments:
        * `final` (`Sequence[str]`):
          The `dependencies` afterwards.
        * `before`, `edited` (`str`):
          The program before and after the `mypy` comments, which add
          no lines.
        * `modules` (`Mapping[str, str]`):
          The module each added entry was added for.

        Returns:
        * (`list[str]`): Such as `Added "sprocket" to
          `prog.py`'s `dependencies` (line 12).`.
        """
        # Each entry's line afterwards, if it can be counted.
        name: str = f"`{self.program.name}`'s `dependencies`"
        lines: list[int] = dependency_lines(edited) or []
        at: dict[str, str] = {
            entry: f" (line {line})" for entry, line in zip(final, lines)}
        reports: list[str] = [
            f'Removed "{entry}" from {name}.'
            for entry in self.entries if entry not in final]
        moved: set[str] = {
            entry for entry in final if entry in self.entries
            and [one for one in self.entries if one in final].index(entry)
            != [one for one in final if one in self.entries].index(entry)}
        # The import lines that were given the comment, by module.
        old: list[str] = before.splitlines()
        new: list[str] = edited.splitlines()
        commented: dict[str, int] = {
            module: line for module, line, _ in program_imports(edited)
            if line <= min(len(old), len(new))
            and old[line - 1] != new[line - 1]}
        entry: str
        for entry in final:
            if entry not in self.entries:
                module: str = modules.get(entry, "")
                comment: str = (
                    f", and the `mypy` comment to `import {module}` (line "
                    f"{commented[module]})" if module in commented else "")
                reports.append(f'Added "{entry}" to {name}'
                               f'{at.get(entry, "")}{comment}.')
            elif entry in moved:
                reports.append(f'Moved "{entry}" in {name}'
                               f'{at.get(entry, "")}.')
        return reports


class EZPkg:
    """Fetch and import Python packages that are not preinstalled.

    Most of the class is still to come.  What it eventually holds is
    the general case fetch: read the calling program's declared
    requirements, resolve them, install them into a cache directory
    keyed by interpreter and platform, and put that directory on
    `sys.path`.

    What works today is the cache directory itself.  Constructing an
    `EZPkg` creates the directory and drops a `README.md` into
    it, so that somebody who finds the directory and wonders what it
    is can read the answer without leaving it.  Beside it goes
    `quick_start.py`, the template a person copies into a program.

    Attributes:
    * `bootstrap` (`str`):
      Which bootstrap the program carries, as `install` was told, or the
      empty string.  Nothing reads it yet; see `T.fbanwiis`.
    * `readme` (`Path`):
      The `README.md` written into `root`.
    * `quick_start` (`Path`):
      The `quick_start.py` written into `root`, a copy of `QUICK_START`.
    * `root` (`Path`):
      The cache directory.  Created if it does not exist.

    Constructor:
    * `EZPkg(root=None)`
    """

    # Set by the constructor; see `Attributes:` above.
    quick_start: Path
    readme: Path
    root: Path
    bootstrap: str = ""

    def __init__(self, root: Path | None = None,
                 pip: subprocess.CompletedProcess[str] | None = None,
                 **later: object) -> None:
        """EZPkg Package Cache.

        This directory holds Python packages that a program needed but
        that the Python installation did not provide.  A small
        bootstrap, pasted into the top of that program, fetched them
        and put them on `sys.path`.

        Nothing here is managed by the system package manager, and
        nothing here is a virtual environment.  It is an ordinary
        directory of installed packages.

        What is in it:

        * `versions/` holds one directory per package version, named
          after the wheel it came from, so two programs wanting two
          versions of the same package each get their own.  These are
          the directories that go on `sys.path`.
        * `wheels/` keeps the downloaded wheels themselves.
        * `requests/` records what was asked for, one small file per
          request, so that asking again costs nothing.
        * `scans/` records which programs have had their imports
          checked against what they declare, so that each is checked
          again only when its imports change.
        * `develop/` remembers, one small file per program, whether
          the person running it agreed to its packages, and what was
          last said about differences between its imports and the
          packages it declares, so that each is raised once.  Delete
          a file to be asked again.
        * `pending/` is scratch space used while fetching and
          unpacking.  Anything left in it is litter from an interrupted
          run and is safe to remove.
        * `pip.whl` is a private copy of `pip`, fetched so that this
          machine needs no `pip` of its own.  It
          is run straight from the wheel and never installed.  Newer
          releases are added beside it as `pip-<version>-...whl` about
          once a week, and the newest is the one used.
        * `last_cull` and `last_pip` are stamps recording when the
          cache was last swept and when `pip` was last checked.
        * `ezpkg.whl` is `EZPkg` itself, which the bootstrap fetched
          and imports straight from the wheel.  (`ezpkg/` and
          `ezpkg-<version>.dist-info/` are `EZPkg` as bootstraps before
          `nopip8` installed it.)
        * `remove.py` removes this whole directory.
        * `list.py` says what is here and for which programs, and
          changes nothing.
        * `quick_start.py` is a complete program that uses `EZPkg`.
          Copy its parts into a program of your own; the comments in
          it say which part is which.  It is the copy that came with
          the `ezpkg` installed here, so after a new release the
          one in the project's `README.md` may be newer.

        Deleting this whole directory is safe.  The next program that
        needs one of these packages will fetch it again.  To delete it:

        * Linux and macOS: `python3 ~/.ezpkg/remove.py`
        * Windows PowerShell: `py $HOME\\.ezpkg\\remove.py`
        * Windows `cmd.exe`: `py %USERPROFILE%\\.ezpkg\\remove.py`

        A program can say which packages it needs in a PEP 723 block at
        its top, where its author's runs also record which exact wheels
        were approved.

        Arguments:
        * `root` (`Path | None`):
          The cache directory to use.  `None`, the default, means
          `~/.ezpkg`, which is the directory the bootstrap
          code names.  Tests pass a temporary directory instead.
        * `pip` (`subprocess.CompletedProcess[str] | None`):
          What `nopip7`'s `pip install ezpkg` printed, captured, on the
          run that installed `ezpkg` (a first run), else `None`
          (`T.abfd`).  `nopip8` passes nothing: its first run is known
          by its `ezpkg.whl` in a cache with nothing installed yet.
        * `later` (`object`):
          Keywords a newer bootstrap passes, ignored, so that it can
          still reach `install` and switch to the `ezpkg` it asks for
          (`T.eui`).
        """
        # Default to the cache directory that the bootstrap code names.
        self.pip_run: subprocess.CompletedProcess[str] | None = pip
        self.told: bool = False  # Have `bootstrapped`'s been listed?
        self.listings: int = 0  # How many lists `provide` has printed.
        self.agreeing: bool = False  # Agreed to for the first time?
        self.looked: bool = False  # Has `settings` read the file yet?
        self.chosen_settings: Settings | None = None  # See `settings`.
        self.declined: bool = False  # `n` to `reconcile`, this run.
        self.reported: set[str] = set()  # Modules `reconcile` named.
        self.edited: bool = False  # Was the program's file changed?
        self.stashed: dict[str, Any] | None = None  # See `stash`.
        # A release's copy of the program while it is built (`staged`).
        self.staging: tuple[str, str, bool] | None = None
        # The `prog.py.toml` this run filled, and what it wrote, so that
        # nothing in the program is edited until the next run.
        self.filled: tuple[Path, str] | None = None
        self.adding: list[str] | None = None  # The note's additions.
        self.restarted: bool = False  # Is this run a `restart`'s?
        self.root = Path.home() / ".ezpkg" if root is None else root
        # A first run: `nopip7` says so with `pip`'s output; `nopip8`
        # leaves only its `ezpkg.whl`, before anything was installed.
        self.first_run: bool = pip is not None or (
            (self.root / "ezpkg.whl").is_file()
            and not (self.root / "versions").exists())
        self.root.mkdir(parents=True, exist_ok=True)

        # The docstring above is the README; the summary line becomes
        # its title.  Docstrings are absent under `python3 -OO`, so
        # fall back to a title only rather than failing.
        document: str | None = inspect.getdoc(EZPkg.__init__)
        title: str
        body: str
        if document is None:
            title, body = "EZPkg Package Cache", ""
        else:
            title, _, body = document.partition("\n")
            title = title.rstrip(".")
            body = body.split("Arguments:")[0].rstrip()

        # Both files are written only when they would change; see
        # `refresh`.  The Quick Start program sits beside the README, so
        # that a person can open it and copy its parts into their own.
        self.readme = self.root / "README.md"
        refresh(self.readme, f"# {title}\n{body}\n")
        self.quick_start = self.root / "quick_start.py"
        refresh(self.quick_start, QUICK_START)
        refresh(self.root / "remove.py", REMOVE_SCRIPT)
        refresh(self.root / "list.py", LIST_SCRIPT)

        # Repair a single module install, so that the bootstrap that
        # fetched this one recognises it next time.  See `I.cctfd`.
        self.repair_module_layout()

    def repair_module_layout(self) -> Path | None:
        """Rewrite this module inside the cache as a package directory.

        Every case in `bootstrap.py` decides whether it has already
        installed the package by asking `(target / PACKAGE).is_dir()`.
        A distribution that installs as a single module puts
        `ezpkg.py` there rather than a directory, so the answer
        is no on every run and the fetch is repeated forever.  `venv4`
        does worse than waste a download: it deletes the `pip` it
        installed with, so its second run has nothing to install with
        and fails.  This is the `I.cctfd` issue in `ISSUES/`.

        Rather than edit every case body that people paste, the
        second stage repairs the layout once, the first time it runs.
        The file this module was imported from becomes
        `<name>/__init__.py` in the same directory, which every case's
        `is_dir()` test then finds.  The cost is one extra fetch, on
        the first run only.

        The file is only touched when it lies somewhere under `root`,
        which is what keeps a checkout being worked on from being
        rewritten.  Half the cases install into `root` itself and half
        into a `site-packages` directory inside it, so anywhere under
        `root` is the test that covers both.

        Repairing twice must not nest, so this returns `None` once the
        module is already a package.

        Returns:
        * (`Path | None`): The directory now holding the module, or
          `None` when there was nothing to repair.
        """
        # Once repaired, this module is a package, and a package has a
        # `__path__`.  Without this test the second run would take
        # `__init__.py`, whose stem is `__init__`, and bury it one
        # directory deeper, leaving the package with no `__init__.py`
        # at all.  The run after that would import a namespace package
        # and fail on `__version__`.
        if "__path__" in globals():
            return None

        # A frozen interpreter gives a module no file to move.
        origin: str | None = globals().get("__file__")
        if origin is None:
            return None

        # Only ever rewrite inside the cache, never a checkout.
        module: Path = Path(origin).resolve()
        if module.suffix != ".py" or not module.is_file():
            return None
        try:
            module.relative_to(self.root.resolve())
        except ValueError:
            return None

        # Move the module into a directory named after it, then drop it.
        # Two programs starting at once both get this far, so the
        # removal has to tolerate the other one having done it already.
        package: Path = module.parent / module.stem
        package.mkdir(exist_ok=True)
        (package / "__init__.py").write_bytes(module.read_bytes())
        module.unlink(missing_ok=True)
        return package

    def paths(self) -> tuple[Path, Path, Path, Path]:
        """Return the four cache directories, creating them if needed.

        See 6.3.1 of `T.vcbow`.  `pending` holds wheels that
        have arrived and are not approved, `wheels` holds the approved
        artifacts, `versions` holds one unpacked tree per resolved
        distribution and version, and `requests` holds one small record
        per request answered.  Only `versions` is ever put on
        `sys.path`, which is what makes `pending` a jail rather than a
        waiting room: a wheel is an inert zip, so nothing in it can
        have run.

        Returns:
        * (`tuple[Path, Path, Path, Path]`): `pending`, `wheels`,
          `versions`, `requests`.
        """
        # One call site creates all four, so they cannot drift apart.
        made: list[Path] = []
        leaf: str
        for leaf in ("pending", "wheels", "versions", "requests"):
            made.append(self.root / leaf)
            made[-1].mkdir(parents=True, exist_ok=True)
        return made[0], made[1], made[2], made[3]

    def approved(self) -> dict[str, str] | None:
        """Read the approvals in the program's Part 1, pin to `id:`.

        They travel inside the program, so the end user's copy carries
        the author's judgement: they chose the dependencies and can tell
        `requests` from `reqeusts`, where the person who merely ran the
        program cannot.  Written by the developer's runs
        (`record_approvals`); see `approvals_in` and `T.abfd`.

        A program with no file of its own -- the interpreter prompt,
        `python3 -c`, a frozen executable -- has nowhere to keep them
        and gets no verification.  See `T.sawaw`.

        Returns:
        * (`dict[str, str] | None`): What was approved, or `None` when
          there are no approvals, which means nothing is verified.
        """
        # A developer's are in the stash (seeded from Part 1's).
        if self.stashing():
            held: object = self.stash().get("checksums")
            return dict(held) if isinstance(held, dict) and held else None

        # The program's text as it is now, since this run may edit it.
        found: tuple[Path, str] | None = main_source()
        return None if found is None else approvals_in(found[1])

    def released(self) -> str:
        """Return the newest version in `prog.py.releases`, if any.

        Written by `release`, so that a `release` setting releases once
        each time it changes (`T.abfd`, Wayne, 2026-10-22).

        Returns:
        * (`str`): Such as `1.0.0`; empty when nothing was released.

        Raises:
        * `SystemExit`:
          If `prog.py.releases` cannot be read, since a release made
          without knowing the last one could repeat it.
        """
        # The last entry is the newest.
        program: Path | None = main_path()
        if program is None:
            return ""
        try:
            entries: list[dict[str, Any]] = read_releases(program)
        except ValueError as error:
            raise SystemExit(str(error)) from None
        version: object = entries[-1].get("version") if entries else None
        return version if isinstance(version, str) else ""

    def edit_part1(self, settings: Sequence[tuple[str, str, str | None]]
                   ) -> str:
        """Set keys of the program's Part 1, in one edit.

        Its encoding, byte order mark and line endings are kept, since a
        program is not obliged to be UTF-8 with `\\n`, and the program
        starts again afterwards (`restart`).

        Arguments:
        * `settings` (`Sequence[tuple[str, str, str | None]]`):
          Each table under `tool`, key and value, as `uv_setting` takes
          them.

        Returns:
        * (`str`): Why the edit could not be made, for the developer, or
          an empty string when it was made, or was not needed, as for a
          program with no `script` block.
        """
        # The bytes, so that the encoding can be kept on the way back.
        where: Path | None = main_path()
        if where is None:
            return ""
        text: str
        encoding: str
        crlf: bool
        try:
            text, encoding, crlf = read_program(where)
        except OSError:
            return ""
        block: tuple[re.Match[str], str] | None = script_toml(text)
        if block is None:
            return ""

        # Each setting, then one write.
        toml: str | None = block[1]
        table: str
        key: str
        value: str | None
        for table, key, value in settings:
            toml = uv_setting(toml, key, value, table) if toml else None
            if toml is None:
                return (f"could not set `{key}` in `[tool.{table}]` of "
                        f"{where.name}'s script block")
        if toml is None or toml == block[1]:
            return ""
        try:
            write_program(where, with_script_toml(text, block[0], toml),
                          encoding, crlf)
        except OSError as error:
            return f"could not write {where.name} ({error})"
        self.edited = True
        return ""

    def pins(self) -> list[str]:
        """Return an exact `==` pin for every approved package.

        The approvals already name every package the program needs, the
        ones that came along included, each as a pin.  They make `pip`
        fetch the same versions every time, and the approvals' ids then
        check that those are the same files: together, a freeze.  `locked` hands
        them to `pip` as constraints, and `build_uv` writes them into
        the `uv` script's Part 1.  See `T.ewar` and `T.rafal` in
        `TASKS/`.

        Returns:
        * (`list[str]`): Requirements such as `widget==1.2.3`, sorted.

        Raises:
        * `RuntimeError`:
          If there are no approvals to pin from, if one is not a pin, or
          if they approve two versions of one distribution, which no
          single pin can say.
        """
        # Each approval is `name==version`.
        approved: dict[str, str] | None = self.approved()
        if not approved:
            raise RuntimeError(
                "no approvals to pin; run the program once as its "
                "developer (with its `.py.toml`) first")
        versions: dict[str, set[str]] = {}
        pin: str
        for pin in approved:
            # Only a hand edit makes anything else, and since `locked`
            # pins on every run, it must say where.
            name: str
            version: str
            name, _, version = pin.partition("==")
            if not (name and RELEASE.match(version)):
                raise RuntimeError(
                    f"{pin!r} in Part 1's `approved` is not `name==version`; "
                    f"delete `approved` and run the program as its "
                    f"developer to write it again")
            versions.setdefault(name, set()).add(version)
        mixed: list[str] = sorted(name for name, found in versions.items()
                                  if len(found) > 1)
        if mixed:
            raise RuntimeError(
                "more than one version approved for "
                + ", ".join(mixed))
        return sorted(f"{name}=={found.pop()}"
                      for name, found in versions.items())

    def locked(self) -> list[str]:
        """Return the versions a fetch must keep to, as constraints.

        The approvals are a lock as well as a check.  Without this, `pip`
        resolves `dependencies` afresh on every fetch and picks the
        newest of everything, so a new release of a package is refused
        by `verify` rather than replaced by the version the author
        recorded.  Handed to `pip` as constraints, the recorded versions
        are what gets fetched, and `verify` then checks they are the
        same files.  Constraints rather than requirements, so a package
        the program no longer asks for is not fetched just because it
        is recorded.

        A developer's run with no `exclude-newer` date in Part 1 gets no
        lock: that is the first run, or an upgrade, which resolves
        afresh and records the result (`gate`).  See `T.rafal` and
        `T.abfd` in `TASKS/`.

        Returns:
        * (`list[str]`): Constraints such as `widget==1.2.3`, sorted, or
          an empty list when nothing is locked.

        Raises:
        * `RuntimeError`:
          Through `pins`, if the approvals name two versions of one
          distribution.
        """
        # Only with something approved, and not when upgrading.
        if not self.approved() or (self.developing()
                                   and not self.declared_date()):
            return []
        return self.pins()

    def cutoff(self) -> str:
        """Return the upload date a fetch must keep before, if any.

        The date is `exclude-newer` in Part 1's `[tool.uv]` table, which
        is where `uv run` reads it too, so one line serves both.  It is
        for a program sent on its own, without its approvals: it gets the
        packages that were newest when its author recorded them, rather
        than whatever is newest the day it is run.  The developer's
        first run stamps it; see `stamp`.

        An end user's run with approvals has no date, because the lock
        already says exactly which versions.  A developer's run always
        has it, so that a package added later is one that existed then
        (`T.abfd`).  See `T.srdisb` in `TASKS/`.

        Returns:
        * (`str`): The date as `pip`'s `--uploaded-prior-to` takes it, or
          an empty string for none.
        """
        # Not for an end user's run with approvals.
        if self.approved() and not self.developing():
            return ""
        return self.declared_date()

    def declared_date(self) -> str:
        """Return Part 1's `exclude-newer` date, or an empty string.

        For a developer whose Part 1 is not edited (`stashing`), Part 1's
        own date if the developer wrote one, else the stash's; and none
        at all while `upgrade` is on, so that each run fetches the newest
        versions and `record_approvals` dates them afresh.

        Returns:
        * (`str`): The date as written, such as `2026-10-19T12:00:00Z`.
        """
        # Part 1's, else the stash's, unless upgrading.
        stashed: object = None
        if self.stashing():
            settings: Settings | None = self.settings()
            if settings is not None and settings.upgrade:
                return ""
            stashed = self.stash().get("exclude-newer")

        # A block that will not parse is reported elsewhere, by the
        # code that needs it; here it simply has no date.
        try:
            declared: dict[str, Any] = self.declaration()
        except ValueError:
            return ""
        tool: object = declared.get("tool", {})
        uv: object = tool.get("uv", {}) if isinstance(tool, dict) else {}
        when: object = uv.get("exclude-newer") if isinstance(uv, dict) else None

        # TOML lets the date go unquoted, and then it arrives as one.
        if isinstance(when, datetime.date):
            return when.isoformat()
        if isinstance(when, str) and when:
            return when
        return stashed if isinstance(stashed, str) else ""

    def program_text(self, where: Path) -> tuple[str, str, bool]:
        """Read the program as a release sees it.

        While a release is built for a developer whose Part 1 is not
        edited, that is its staged copy (`staging`), with the stash
        merged in; otherwise the file itself (`read_program`).

        Arguments:
        * `where` (`Path`):
          The program.

        Returns:
        * (`tuple[str, str, bool]`): As `read_program` returns.

        Raises:
        * `OSError`:
          If the file cannot be read.
        """
        # The staged copy, if there is one.
        return self.staging or read_program(where)

    def rewrite(self, where: Path, text: str, encoding: str,
                crlf: bool) -> None:
        """Write the program as a release changes it.

        Into the staged copy while there is one (`program_text`),
        otherwise into the file (`write_program`).

        Arguments:
        * `where` (`Path`):
          The program.
        * `text`, `encoding`, `crlf` (`str`, `str`, `bool`):
          As `write_program` takes them.

        Raises:
        * `OSError`:
          If the file cannot be written.
        """
        # The staged copy, if there is one.
        if self.staging is not None:
            self.staging = (text, encoding, crlf)
        else:
            write_program(where, text, encoding, crlf)

    def staged(self, asking: Sequence[str]) -> tuple[str, str, bool]:
        """Return the program with the stash merged into its Part 1.

        What a release's copies are made from when Part 1 is not edited
        (Wayne, 2026-10-22): `dependencies` as this run declared them
        (Part 1's and the stash's), with the stash's `checksums` and
        date.

        Arguments:
        * `asking` (`Sequence[str]`):
          The requirements the program declared.

        Returns:
        * (`tuple[str, str, bool]`): As `read_program` returns.

        Raises:
        * `RuntimeError`:
          If Part 1 cannot be edited.
        * `OSError`:
          If the program cannot be read.
        """
        # The file, then each change to its block.
        where: Path | None = main_path()
        if where is None:
            raise RuntimeError("a release needs the program's own file")
        text: str
        encoding: str
        crlf: bool
        text, encoding, crlf = read_program(where)
        text = with_script_block(text)
        listed: str | None = (
            with_dependency_list(text, list(asking))
            if list(asking) != self.part1_entries() else text)
        block: tuple[re.Match[str], str] | None = (
            None if listed is None else script_toml(listed))
        if listed is None or block is None:
            raise RuntimeError(f"cannot edit the script block of a copy "
                               f"of {where.name}")
        stashed: dict[str, Any] = self.stash()
        toml: str | None = block[1]
        rows: dict[str, str] = self.approved() or {}
        if rows and toml is not None:
            toml = uv_setting(toml, "checksums", approvals_array(
                rows, stashed.get("tags") or {}), "ezpkg")
        dated: str = self.declared_date() or str(
            stashed.get("exclude-newer") or "")
        if dated and toml is not None:
            toml = uv_setting(toml, "exclude-newer", f'"{dated}"', "uv")
        wanted: str | None = self.python_range(text, asking)
        if wanted and toml is not None:
            toml = with_requires_python(toml, wanted)
        if toml is None:
            raise RuntimeError(f"cannot edit the script block of a copy "
                               f"of {where.name}")
        return with_script_toml(listed, block[0], toml), encoding, crlf

    def python_range(self, text: str, asking: Sequence[str]) -> str | None:
        """Return the `requires-python` a release's Part 1 should say.

        `requires-python` in `prog.py.toml` when it is set; otherwise
        Part 1's own, left alone, when it has one; otherwise the floor
        worked out here: the highest of 3.11 (which `ezpkg` needs), the
        program's syntax (`syntax_floor`) and each package's own
        `Requires-Python` (`package_floor`).  A worked-out floor older
        than every Python the developer has run the program on is said,
        in one line, since a library function newer than the floor would
        not show in the source (Wayne, 2026-10-22).

        Arguments:
        * `text` (`str`):
          The program's source.
        * `asking` (`Sequence[str]`):
          The requirements it declared, already provided.

        Returns:
        * (`str | None`): Such as `>=3.12`, or `None` to leave Part 1's.
        """
        # Chosen by the developer, in either place.
        settings: Settings | None = self.settings()
        if settings is not None and settings.requires_python:
            return settings.requires_python
        if "requires-python" in (script_metadata(text) or {}):
            return None

        # Otherwise the highest floor of three.
        floor: tuple[int, ...] = max((3, 11), syntax_floor(text))
        entry: str
        for entry in asking:
            try:
                stated: list[str] = importlib.metadata.metadata(
                    requirement_name(entry)).get_all("Requires-Python") or []
            except (importlib.metadata.PackageNotFoundError, ValueError):
                continue
            found: tuple[int, ...] | None = package_floor(",".join(stated))
            if found is not None:
                floor = max(floor, found[:2])
        wanted: str = ">=" + ".".join(str(part) for part in floor)

        # Said when nobody has run it on a Python that old.
        program: Path | None = main_path()
        if program is not None:
            ran: object = self.development_record(program)[1].get("pythons")
            tried: list[tuple[int, ...]] = sorted(
                tuple(int(part) for part in one.split("."))
                for one in (ran if isinstance(ran, list) else [])
                if isinstance(one, str) and re.fullmatch(r"\d+\.\d+", one))
            if tried and floor[:2] < tried[0]:
                self.say(1, f"`{program.name}` is released for Python "
                         f"{wanted}, but you have run it only on "
                         + and_list(["Python " + ".".join(map(str, one))
                                     for one in tried])
                         + f".  If it needs a newer Python, set "
                         f"`requires-python` in `{program.name}.toml`.")
        return wanted

    def give_ranges(self, asking: Sequence[str]) -> list[str]:
        """Give each bare entry in Part 1 a range from its approved version.

        At every release (S5.1b): each entry that is a name alone
        gets the range `version_range` makes from the version the
        approvals record, so that a `.py` sent without its approvals
        cannot be handed a much newer package than the one it was tested
        with ("I used EZPkg and it put the wrong packages in!", Wayne,
        2026-10-15).  An entry with any specifier, extra or marker is the
        author's decision and is left alone.  See `T.kdaiis`, `T.abfd`.

        Arguments:
        * `asking` (`Sequence[str]`):
          The requirements the program declared.

        Returns:
        * (`list[str]`): The requirements now declared.
        """
        # The approved version of each bare entry.
        versions: dict[str, str] = {
            normal_name(pin.partition("==")[0]): pin.partition("==")[2]
            for pin in self.approved() or {}}
        ranged: list[str] = [
            version_range(entry, versions[normal_name(entry)])
            if requirement_name(entry) == entry.strip()
            and normal_name(entry) in versions else entry
            for entry in asking]
        where: Path | None = main_path()
        if ranged == list(asking) or where is None:
            return list(asking)

        # Written, keeping the encoding and line endings.
        source: str
        encoding: str
        crlf: bool
        try:
            source, encoding, crlf = self.program_text(where)
        except OSError:
            return list(asking)
        edited: str | None = with_dependency_list(source, ranged)
        if edited is None:
            raise SystemExit(f"{where.name}: cannot edit its script "
                             f"block to give `dependencies` ranges")
        self.rewrite(where, edited, encoding, crlf)
        return ranged

    def request_for(self, asking: Sequence[str]) -> str:
        """Return the key a request's record is filed under.

        What was asked, sorted, the lock and the date, since the same
        requirements under another lock or date resolve to other
        versions.
        ` -c ` cannot occur inside a requirement, which never starts with
        a dash.  One method, so that `provide`, which files the record,
        and `export`, which reads it back, cannot disagree.

        Arguments:
        * `asking` (`Sequence[str]`):
          Requirement strings as `pip` spells them.

        Returns:
        * (`str`): The key, for `remember`.
        """
        # Without a lock or a date the key is what it always was.
        request: str = " ".join(sorted(asking))
        locked: list[str] = self.locked()
        if locked:
            request += " -c " + " ".join(locked)
        before: str = self.cutoff()
        if before:
            request += " --uploaded-prior-to " + before
        return request

    def export(self, form: str, asking: Sequence[str] = (),
               target: Path | None = None) -> Path:
        """Write what the approvals record in another tool's form.

        Called by `release` for each of `exports`, after the packages
        have been provided and the imports checked (`check_imports`).
        `zipapp` writes a `.pyz` (`build_zipapp`); `uv` writes a script
        and its lock file (`build_uv`); `email` writes the program to
        send, approved for every computer (`build_email`, `T.ee`).

        There was once a `pins` form, printing Part 1 with every package
        pinned, for a `.py` sent on its own.  The `exclude-newer` date
        in Part 1 does that job now, with no step to remember (Wayne,
        2026-10-12).

        Arguments:
        * `form` (`str`):
          What to write: `zipapp`, `uv` or `email`, in any case.
        * `asking` (`Sequence[str]`):
          The requirements just provided, which `build_zipapp` bundles.
        * `target` (`Path | None`):
          Where to write it; `None` means beside the program, named as
          `build_zipapp`, `build_uv` and `build_email` name it.

        Returns:
        * (`Path`): What was written (for `uv`, the script).

        Raises:
        * `ValueError`:
          If `form` is not one this knows.
        * `RuntimeError`:
          If `check_imports`, `build_zipapp`, `build_uv` or
          `build_email` does; see there.
        """
        # A misspelt form is refused before anything is read.
        kind: str = form.lower()
        if kind not in EXPORT_FORMS:
            raise ValueError(f"cannot export as {form!r}; use "
                             + and_list(list(EXPORT_FORMS), "or"))

        # Whatever leaves this machine must not lean on what is on it.
        self.check_imports(asking)
        if kind == "zipapp":
            return self.build_zipapp(asking, target)
        if kind == "email":
            return self.build_email(target)
        return self.build_uv(target)

    def sync_dependencies(self, asking: Sequence[str],
                          argv: Sequence[str] = ()) -> list[str]:
        """Keep Part 1's `dependencies` in step with the imports, silently.

        For the program's developer, with `auto-dependencies` on, once
        per change of the program's imports or `dependencies`
        (`dependency_fingerprint`): any discrepancy (`discrepancy`) is
        fixed without asking (`reconcile`, `T.abfd`).

        Arguments:
        * `asking` (`Sequence[str]`):
          The requirements the program declared, already provided.
        * `argv` (`Sequence[str]`):
          Extra arguments for `pip install`, as `install` documents.

        Returns:
        * (`list[str]`): The requirements now declared, for
          `scan_imports`.
        """
        # Nothing has changed since this program was last looked at.
        source: tuple[Path, str] | None = main_source()
        settings: Settings | None = self.settings()
        if source is None or settings is None:
            return list(asking)
        program: Path
        text: str
        program, text = source
        approved: set[str] = {normal_name(pin.partition("==")[0])
                              for pin in self.approved() or {}}
        try:
            fingerprint: str = dependency_fingerprint(text, asking, approved)
        except SyntaxError:
            return list(asking)
        record: Path
        kept: dict[str, Any]
        record, kept = self.development_record(program)
        fingerprint += unused_key(self.unused_lately(kept))
        if kept.get("asked") == fingerprint and "imported" in kept:
            return list(asking)

        # Worked out only now, since it reads the installed metadata.
        found: Discrepancy | None = self.discrepancy(program, text, asking)
        if found is None:
            return list(asking)
        if not found.pending():
            self.keep(record, kept, asked=fingerprint,
                      imported=found.imported(set()))
            return list(asking)
        return self.reconcile(found, list(asking), argv, record, kept,
                              fingerprint, approved)

    def fetching(self, final: Sequence[str]) -> list[str]:
        """Return what fetching a `dependencies` asks of the index.

        The same as an ordinary run asks (`providing`), so that the
        approvals `reconcile`'s fetch records are the ones the restarted
        run finds, with this `ezpkg`'s pin kept on a developer's run, and
        nothing is edited twice (`ux` step 2.2, 2026-10-19).

        Arguments:
        * `final` (`Sequence[str]`):
          The `dependencies`.

        Returns:
        * (`list[str]`): The requirements to fetch.
        """
        # As `provide_declared` would ask.
        own: str | None = own_entry(final)
        return self.providing(final, own,
                              own is not None and not self.chosen(own))

    def edit_for(self, found: Discrepancy, final: Sequence[str],
                 modules: Collection[str],
                 comment: bool) -> tuple[str, str, bool, str, str] | str:
        """Work out the whole edit `reconcile` makes, in two stages.

        Arguments:
        * `found` (`Discrepancy`):
          What disagrees.
        * `final` (`Sequence[str]`):
          The `dependencies` afterwards.
        * `modules` (`Collection[str]`):
          The added imports, which get the author's `mypy` comment.
        * `comment` (`bool`):
          True when `import ezpkg` gets it too.

        Returns:
        * (`tuple[str, str, bool, str, str] | str`): The source, its
          encoding, whether its lines end in CRLF, then the program with
          only `dependencies` changed, and the whole edit; or the line
          saying why it cannot be made.
        """
        # The file as it is, then each stage.
        program: Path = found.program
        source: str
        encoding: str
        crlf: bool
        try:
            source, encoding, crlf = read_program(program)
        except OSError as error:
            return f"{program.name}: cannot read it: {error}"
        listed: str | None = with_dependency_list(source, final)
        if listed is None:
            return (f"{program.name}: cannot edit its script "
                    f"block; change `dependencies` by hand")
        edited: str
        edited, _ = with_type_ignores(
            listed, {*modules, *(["ezpkg"] if comment else [])}, found.used)
        return source, encoding, crlf, listed, edited

    def prove(self, package: str, module: str,
              argv: Sequence[str] = ()) -> str:
        """Say why a guessed package cannot be the one an import wants.

        A guess is only the import's name, so before anybody is asked
        about it, the index must have it, as a wheel, and the wheel must
        hold the module.  Fetched into a holding directory, looked at
        and thrown away: nothing is unpacked or run, and `pip`'s own
        cache makes the later fetch cheap.  See `T.kdaiis`.

        Arguments:
        * `package` (`str`):
          The guessed distribution name.
        * `module` (`str`):
          The top-level module the program imports.
        * `argv` (`Sequence[str]`):
          Extra arguments for `pip`, as `install` takes them.

        Returns:
        * (`str`): Why not, to follow "is imported, but", or an empty
          string when the package does provide the module.
        """
        # The index's list of files first, which costs one page.  No
        # answer (no network) leaves it to the fetch.
        files: list[str] | None = index_files(package)
        if files is not None and not files:
            return f"PyPI has none called `{package}`"
        if files is not None and not any(
                one.endswith(".whl") for one in files):
            return (f'the index\'s "{package}" has no wheel, only '
                    f'source code, so it cannot be installed')

        # Then the wheel itself, with whatever it needs.
        arrived: list[Path] = []
        try:
            arrived = self.download([package], argv)
            wheel: Path | None = next(
                (one for one in arrived
                 if normal_name(one.name.split("-")[0])
                 == normal_name(package)), None)
            if wheel is None:
                return f'"{package}" could not be fetched'
            if module not in wheel_modules(wheel):
                return (f'the index\'s "{package}" does not provide '
                        f'`{module}`')
            return ""
        except (RuntimeError, ValueError) as error:
            return f'"{package}" could not be fetched: ' + (
                failure_reason(error))
        finally:
            holding: Path
            for holding in {one.parent for one in arrived}:
                shutil.rmtree(holding, ignore_errors=True)

    def reconcile(self, found: Discrepancy, asking: list[str],
                  argv: Sequence[str], record: Path, kept: dict[str, Any],
                  fingerprint: str, approved: set[str]) -> list[str]:
        """Fix a discrepancy without asking, as `sync_dependencies` says.

        Each new import gets an entry, a guessed name only once `prove`
        shows it provides the module (else one line, and Python's
        `ImportError` follows), with a range from the version that
        arrived (`version_range`), and its import gets the author's
        `mypy` comment.  An entry nothing imports, with no comment, is
        removed once the last `RUNS_KEPT` runs show it unused
        (`unused_lately`): declared, but never loaded behind the scenes
        (Wayne, 2026-10-20).  So the Quick Start's `cowsay`, pasted in
        with the bootstrap, goes after the first run, and `matplotlib`'s
        backend stays.  Entries
        follow the order of the first imports.  The file is edited once,
        and `verbosity` decides what is said (`T.abfd`).

        Arguments:
        * `found` (`Discrepancy`):
          What disagrees.
        * `asking` (`list[str]`):
          The requirements the program declared.
        * `argv` (`Sequence[str]`):
          Extra arguments for `pip install`.
        * `record`, `kept` (`Path`, `dict[str, Any]`):
          The program's development record, and what it holds.
        * `fingerprint` (`str`):
          The program's `dependency_fingerprint`, then `unused_key`'s.
        * `approved` (`set[str]`):
          The names its approvals cover.

        Returns:
        * (`list[str]`): The requirements now declared.
        """
        # Guessed names are proved first, so that nothing is added that
        # does not provide its module.
        program: Path = found.program
        declared: list[int] = [one for one in found.lines if one]
        where: str = f" ({line_list(declared)})" if declared else ""
        modules: dict[str, str] = {}
        # Each guess that failed to prove itself, said unless the file is
        # edited, since the restarted run says it with the new lines.
        doubts: list[str] = []
        line: int
        module: str
        package: str
        for line, module, package in found.additions:
            # A package for another platform cannot be fetched here.
            problem: str = (
                self.prove(requirement_name(package), module, argv)
                if package in found.guessed and holds_here(package)
                else "")
            if problem:
                doubts.append(
                    f"`{program.name}` line {line}: `import {module}` "
                    f"needs a package, but {problem}.  Please check the "
                    f"spelling, or add the right package to "
                    f"`dependencies`{where} by hand.")
                self.reported.add(module)
            else:
                modules[package] = module

        # An entry nothing imports goes once recent runs show it unused.
        unused: set[str] = self.unused_lately(kept)
        removed: set[int] = {
            index for index in found.removals
            if normal_name(requirement_name(found.entries[index])) in unused}
        final: list[str] = found.arrange(set(modules), removed)
        # Only an edited program gets the author's `mypy` comments.
        comment: bool = found.uncommented is not None and EDIT_PROGRAM
        imported: list[str] = found.imported(set(modules))
        doubt: str
        if final == found.entries and not comment:
            for doubt in doubts:
                self.say(1, doubt)
            # A failed guess is tried again next run, since the network
            # may have been the reason (S3.3a).
            if not doubts:
                self.keep(record, kept, asked=fingerprint,
                          imported=imported)
            return asking

        # The additions are fetched and proved first, since the versions
        # that arrive decide what is written.
        fetching: list[str] = self.fetching(final)
        try:
            self.provide(fetching, argv, {
                normal_name(requirement_name(package)): module
                for package, module in modules.items()
                if holds_here(package)})
        except Declined:
            raise
        except (RuntimeError, ValueError) as error:
            self.too_new(found, modules, argv)
            for doubt in doubts:
                self.say(1, doubt)
            # Not recorded as settled, so the next run tries again
            # (S3.3a).
            self.say(1, f"{program.name}: `dependencies` is left as it "
                     f"is: {failure_reason(error)}")
            self.say(3, f"ezpkg: in full: {error}", wrap=False)
            return asking
        fetched: tuple[list[str], list[str]] | None = self.remember(
            self.request_for(fetching))
        ranged: dict[str, str] = {}
        for package in modules:
            # A marker follows the range; another platform's has none.
            name: str = requirement_name(package)
            marker: str = package.partition(";")[2].strip()
            try:
                if not holds_here(package):
                    raise importlib.metadata.PackageNotFoundError(name)
                ranged[package] = version_range(
                    name, importlib.metadata.version(name)) + (
                        f"; {marker}" if marker else "")
            except importlib.metadata.PackageNotFoundError:
                ranged[package] = package
        final = [ranged.get(entry, entry) for entry in final]

        # Not edited: the entries Part 1 does not declare are stashed,
        # and what arrived serves this run.
        if self.stashing():
            for doubt in doubts:
                self.say(1, doubt)
            if fetched is not None:
                self.remember(self.request_for(self.fetching(final)),
                              *fetched)
            own: set[str] = {normal_name(requirement_name(entry))
                             for entry in self.written()}
            self.put_stash(dependencies=[
                entry for entry in final
                if normal_name(requirement_name(entry)) not in own])
            if self.verbosity() >= 2:
                before: set[str] = {normal_name(requirement_name(entry))
                                    for entry in found.entries}
                after: set[str] = {normal_name(requirement_name(entry))
                                   for entry in final}
                for entry in final:
                    if normal_name(requirement_name(entry)) not in before:
                        self.say(2, f"Added {entry} for `{program.name}`.")
                for entry in found.entries:
                    if normal_name(requirement_name(entry)) not in after:
                        self.say(2, f"Dropped {entry} from "
                                 f"`{program.name}`'s packages.")
            try:
                settled_now: str = (
                    dependency_fingerprint(read_program(program)[0], final,
                                           approved)
                    + unused_key(self.unused_lately(kept)))
            except (SyntaxError, OSError):
                settled_now = fingerprint
            self.keep(record, kept,
                      **({} if doubts else {"asked": settled_now}),
                      imported=imported)
            return final

        # The run that filled `prog.py.toml` only says what it would add
        # (`first_run_note`); what arrived serves this run.
        if self.filled is not None:
            for doubt in doubts:
                self.say(1, doubt)
            self.adding = [ranged.get(package, package)
                           for package in modules]
            return final

        # Written once.  What was just fetched answers the request the
        # ranges make, so the next run does not fetch it all again.
        made: tuple[str, str, bool, str, str] | str = self.edit_for(
            found, final, set(modules.values()), comment)
        if isinstance(made, str):
            for doubt in doubts:
                self.say(1, doubt)
            print(made, file=sys.stderr)
            return asking
        encoding: str
        crlf: bool
        listed: str
        edited: str
        _, encoding, crlf, listed, edited = made
        try:
            write_program(program, edited, encoding, crlf)
            self.edited = True
        except OSError as error:
            for doubt in doubts:
                self.say(1, doubt)
            self.say(1, f"{program.name}: `dependencies` is left as it is: "
                     f"{error}")
            return asking
        if fetched is not None:
            self.remember(self.request_for(self.fetching(final)), *fetched)

        # A line per change from `medium` up (S1.5).
        if self.verbosity() >= 2:
            report: str
            for report in found.reported(
                    final, listed, edited,
                    {ranged.get(package, package): module
                     for package, module in modules.items()}):
                self.say(2, report)

        # Remembered as settled, unless a guess failed (S3.3a).
        try:
            settled: str = (dependency_fingerprint(edited, final, approved)
                            + unused_key(self.unused_lately(kept)))
        except SyntaxError:
            settled = fingerprint
        self.keep(record, kept, **({} if doubts else {"asked": settled}),
                  imported=imported)
        return final

    def too_new(self, found: Discrepancy, modules: Mapping[str, str],
                argv: Sequence[str]) -> None:
        """Stop if an addition has no release before the program's date.

        The end user's copy would fail the same way, so the developer is
        told how to upgrade instead (`T.abfd`).

        Arguments:
        * `found` (`Discrepancy`):
          What disagrees.
        * `modules` (`Mapping[str, str]`):
          The module of each addition, by package.
        * `argv` (`Sequence[str]`):
          Extra arguments for `pip`.

        Raises:
        * `SystemExit`:
          Naming the import and the date's line, when one fails under
          the date alone.
        """
        # Each addition alone, under the date: what `prove` fetched
        # without it.
        before: str = self.cutoff()
        if not before:
            return
        program: Path = found.program
        source: list[str] = read_program(program)[0].splitlines()
        dated: int = next((number for number, line in enumerate(source, 1)
                           if re.match(r"#\s*exclude-newer\s*=", line)), 0)
        line: int
        module: str
        package: str
        for line, module, package in found.additions:
            if package not in modules:
                continue
            arrived: list[Path] = []
            try:
                # Only a package the index has at all.
                arrived = self.download([package], argv)
            except (RuntimeError, ValueError):
                continue
            finally:
                for holding in {one.parent for one in arrived}:
                    shutil.rmtree(holding, ignore_errors=True)
            arrived = []
            try:
                arrived = self.download([package], argv, (), before)
            except (RuntimeError, ValueError):
                if self.stashing() and not dated:
                    raise SystemExit(wrapped(
                        f"{program.name} line {line} imports `{module}`, "
                        f"but no release of it existed before "
                        f"{before[:10]}, the date {program.name}'s versions "
                        f"are frozen at.  To upgrade everything to today's "
                        f"versions, set `upgrade = true` in "
                        f"{program.name}.toml and run {program.name} "
                        f"again.",
                        columns(sys.stderr))) from None
                raise SystemExit(wrapped(
                    f"{program.name} line {line} imports `{module}`, but no "
                    f"release of it existed before the date "
                    f"{program.name}'s versions are frozen at (line "
                    f"{dated}, {before[:10]}).  To upgrade everything to "
                    f"today's versions, delete line {dated} and run "
                    f"{program.name} again.", columns(sys.stderr))) from None
            finally:
                for holding in {one.parent for one in arrived}:
                    shutil.rmtree(holding, ignore_errors=True)

    def unused_lately(self, kept: Mapping[str, Any]) -> set[str]:
        """Return the entries recent runs show to be unused.

        From the last `RUNS_KEPT` finished runs, as `note_loaded`
        records them: an entry is unused when the latest of them
        declared it and none of them loaded its package behind the
        scenes (Wayne, 2026-10-20).  So nothing is unused before a run
        is recorded, and an entry added by hand is safe until a run has
        had the chance to load it.

        Arguments:
        * `kept` (`Mapping[str, Any]`):
          The program's development record.

        Returns:
        * (`set[str]`): Their `normal_name`s.
        """
        # The latest run's entries, less every recorded run's loads.
        runs: object = kept.get("runs")
        recorded: list[dict[str, Any]] = [
            run for run in (runs if isinstance(runs, list) else [])
            if isinstance(run, dict)]
        if not recorded:
            return set()
        loaded: set[str] = {normal_name(name) for run in recorded
                            for name in run.get("loaded", [])}
        return {normal_name(name)
                for name in recorded[-1].get("declared", [])} - loaded

    def note_loaded(self, program: Path, asking: Sequence[str]) -> None:
        """Record what this run declared, and what it loaded unasked.

        Registered with `atexit` for a developer's run that reaches its
        own code, so a run that ends in `os._exit`, or is replaced by a
        restart, records nothing.  Each top-level module in
        `sys.modules` is traced to its distribution; those the imports
        imply (the record's `imported`) are left out, so that an import
        deleted from the source does not keep its entry, and what is
        left was loaded behind the scenes, as `matplotlib` loads its
        backend.  Only the program's own entries are noted, since a
        `.pth` file in the machine's Python can load anything.  Never
        fails: a run that cannot be recorded just does not count.

        Arguments:
        * `program` (`Path`):
          The program.
        * `asking` (`Sequence[str]`):
          Its `dependencies`, as this run declared them.
        """
        # What arrived, less what the source imports, kept per run.
        try:
            providers: Mapping[str, list[str]] = (
                importlib.metadata.packages_distributions())
            tops: set[str] = {name.partition(".")[0]
                              for name in list(sys.modules)}
            record: Path
            kept: dict[str, Any]
            record, kept = self.development_record(program)
            direct: object = kept.get("imported")
            imported: set[str] = (set(direct) if isinstance(direct, list)
                                  else set())
            declared: set[str] = {normal_name(requirement_name(entry))
                                  for entry in asking}
            behind: list[str] = sorted(
                ({normal_name(name) for top in tops
                  for name in providers.get(top, [])} - imported) & declared)
            runs: object = kept.get("runs")
            earlier: list[Any] = runs if isinstance(runs, list) else []
            # And the Python it ran on, for `python_range`.
            pythons: object = kept.get("pythons")
            this: str = f"{sys.version_info.major}.{sys.version_info.minor}"
            self.keep(record, kept, runs=[
                *earlier[-(RUNS_KEPT - 1):],
                {"declared": sorted(declared), "loaded": behind}],
                pythons=sorted({*(pythons if isinstance(pythons, list)
                                  else []), this}))
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.say(3, f"ezpkg: this run's packages were not noted "
                     f"({error!r})")

    def discrepancy(self, program: Path, text: str,
                    asking: Sequence[str]) -> Discrepancy | None:
        """Work out how `dependencies` differ from what the imports imply.

        Each import, in order, is placed by the declared entry that
        provides it, if there is one.  Otherwise it needs a package,
        unless it is optional (`every_import`), the standard library or
        local (`exempt`), or covered by the approvals; that package is
        named from the installed metadata, else `MODULE_PACKAGES`, else
        the module's own name.  An entry no import places is unused if
        its package is installed here, so that its modules are known,
        and it has no comment, which keeps it.  See `T.kdaiis`.

        Arguments:
        * `program` (`Path`):
          The program.
        * `text` (`str`):
          Its source.
        * `asking` (`Sequence[str]`):
          Its `dependencies`.

        Returns:
        * (`Discrepancy | None`): What disagrees, which may be nothing,
          or `None` when the program does not parse.
        """
        # What is declared, what is kept, what is installed.  The
        # bootstrap imports `ezpkg` where it stands, so a program that
        # carries one needs an `ezpkg` entry there, which chooses the
        # `ezpkg` that runs it (`T.eui`).
        try:
            imports: list[tuple[str, int, bool]] = every_import(text)
            markers: dict[str, str] = import_markers(text)
        except SyntaxError:
            return None
        bootstrap: ast.Try | None = bootstrap_node(text)
        implied: int | None = None if bootstrap is None else bootstrap.lineno
        if implied is not None:
            imports = sorted([*imports, ("ezpkg", implied, False)],
                             key=lambda one: one[1])
        entries: list[str] = list(asking)
        lines: list[int] = dependency_lines(text) or []
        # The stash's entries, after Part 1's, have no line.
        lines = (lines + [0] * len(entries))[:len(entries)]
        names: list[str] = [normal_name(requirement_name(entry))
                            for entry in entries]
        # Any comment on an entry is the developer's, and keeps it
        # (Wayne, S3.4).
        keep: set[str] = set(dependency_comments(text))
        # And, when Part 1 is not edited, every entry it holds, since
        # only the stash's can go.
        if self.stashing():
            keep |= {normal_name(requirement_name(entry))
                     for entry in self.written()}
        approved: set[str] = {normal_name(pin.partition("==")[0])
                              for pin in self.approved() or {}}
        providers: Mapping[str, list[str]] = (
            importlib.metadata.packages_distributions())
        installed: set[str] = {normal_name(name) for found in
                               providers.values() for name in found}

        # Each import, in order.
        order: list[tuple[str, int, str]] = []
        placed_by: dict[int, int] = {}
        additions: list[tuple[int, str, str]] = []
        used: set[str] = set()
        adding: set[str] = set()
        guessed: set[str] = set()
        module: str
        line: int
        optional: bool
        for module, line, optional in imports:
            from_bootstrap: bool = (module, line) == ("ezpkg", implied)
            if not from_bootstrap and self.exempt(program, module):
                continue
            packages: list[str] = (
                ["ezpkg"] if from_bootstrap
                else providing(module, providers))
            normal: set[str] = {normal_name(name) for name in packages}
            index: int | None = next(
                (index for index, name in enumerate(names)
                 if name in normal), None)
            if index is None and not packages:
                spec: Any
                try:
                    spec = importlib.util.find_spec(module)
                except (ImportError, ValueError):
                    spec = None
                if spec is not None:
                    continue
                guess: str = MODULE_PACKAGES.get(module, module)
                if normal_name(guess) in names:
                    index = names.index(normal_name(guess))
                else:
                    packages = [guess]
                    normal = {normal_name(guess)}
                    guessed.add(guess)
            if index is not None:
                used.add(module)
                if index not in placed_by:
                    placed_by[index] = line
                    order.append(("entry", index, ""))
                continue
            if optional or normal & approved or len(packages) != 1:
                continue
            if normal_name(packages[0]) not in adding:
                # Under a platform test, only for that platform.
                adding.add(normal_name(packages[0]))
                package: str = packages[0]
                if module in markers:
                    package = f"{package}; {markers[module]}"
                    if packages[0] in guessed:
                        guessed.add(package)
                order.append(("add", 0, package))
                additions.append((line, module, package))

        # Unused only when its modules are known and it is not kept.
        removals: list[int] = [
            index for index, name in enumerate(names)
            if index not in placed_by and name in installed
            and name not in keep]
        # `ezpkg` is the bootstrap's, never a dependency, but `mypy`
        # needs the same comment for it as for the packages.
        uncommented: int | None = None
        if any(module == "ezpkg" for module, _, _ in imports):
            commented: list[str]
            _, commented = with_type_ignores(text, {"ezpkg"}, used)
            if commented:
                uncommented = next(line for module, line, _ in imports
                                   if module == "ezpkg")
        return Discrepancy(program, entries, lines, order, placed_by,
                           additions, removals, used, guessed, uncommented)

    def settings(self) -> Settings | None:
        """Return the running program's developer settings, if it has any.

        `ezpkg` has two customers (`T.abfd`).  A program with a
        `prog.py.toml` beside it is its developer's, who is never asked
        anything and whose settings are in that file; without one, it is
        an end user's, who is asked one question and whose program is
        never edited.  Nothing else decides.

        An empty file (or one of blank lines) is an invitation: it is
        filled with `SETTINGS_TEMPLATE`, every setting commented out at
        its default, and one line says so.  After that run `ezpkg`
        never writes the file.  With `EDIT_PROGRAM` on, that run edits
        nothing in the program (`filled`), and the file's note
        (`first_run_note`) says what the next run will change.

        Returns:
        * (`Settings | None`): The settings, or `None` for an end user's
          program, as for one with no file of its own.

        Raises:
        * `SystemExit`:
          With `read_settings`' message, when the file is wrong, since
          running with a setting the developer misspelt would mislead.
        """
        # Read once per run.
        if self.looked:
            return self.chosen_settings
        self.looked = True
        program: Path | None = main_path()
        if program is None:
            return None
        path: Path = settings_path(program)
        try:
            text: str = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError) as error:
            raise SystemExit(f"{path.name}: {error}") from None
        if not text.strip():
            try:
                filling: str = SETTINGS_TEMPLATE if not EDIT_PROGRAM else (
                    SETTINGS_TEMPLATE.replace(
                        AUTO_DEPENDENCIES_LINE, AUTO_DEPENDENCIES_LINE
                        + first_run_note(program.name, None) + "\n", 1))
                path.write_text(filling, encoding="utf-8")
                if EDIT_PROGRAM:
                    self.filled = (path, filling)
                print(wrapped(
                    f"`{path.name}` was empty, so `ezpkg` filled it in"
                    + (f" and left `{program.name}` as it is; the note "
                       f"under `auto-dependencies` says what changes from "
                       f"the next run." if EDIT_PROGRAM else
                       ", with every setting at its default."),
                    columns(sys.stderr)), file=sys.stderr)
            except OSError:
                pass  # Empty is every default anyway.
        try:
            self.chosen_settings = read_settings(path)
        except ValueError as error:
            raise SystemExit(str(error)) from None
        return self.chosen_settings

    def name_the_additions(self) -> None:
        """Rewrite the note of a just-filled `prog.py.toml` with names.

        Only in the run that filled it, and only if nobody has changed
        it since, so it is still `ezpkg`'s own first write (`settings`).
        """
        # Nothing filled, or the file is no longer what was written.
        if self.filled is None:
            return
        path: Path
        written: str
        path, written = self.filled
        program: Path | None = main_path()
        if program is None:
            return
        named: str = written.replace(
            first_run_note(program.name, None),
            first_run_note(program.name, self.adding or []))
        try:
            if named != written and path.read_text(
                    encoding="utf-8") == written:
                path.write_text(named, encoding="utf-8")
        except OSError:
            pass  # The note without names still says what happens.

    def developing(self) -> bool:
        """Say whether the running program is its developer's.

        Returns:
        * (`bool`): True when it has a `prog.py.toml`; see `settings`.
        """
        # The file decides, and nothing else.
        return self.settings() is not None

    def verbosity(self) -> int:
        """Return how much the developer wants said, as a level.

        `none` is 0, `low` 1, `medium` 2, `high` 3 (`VERBOSITY`).  An end
        user's program has no settings and counts as `low`, which none
        of the end user's own messages go through (S1.5).

        Returns:
        * (`int`): The level, 0 to 3.
        """
        # The default is `low`.
        settings: Settings | None = self.settings()
        return VERBOSITY.index(settings.verbosity if settings else "low")

    def say(self, level: int, text: str, wrap: bool = True) -> None:
        """Print a line to standard error if `verbosity` reaches its level.

        Arguments:
        * `level` (`int`):
          1 for a one-off notice (`low`), 2 for each change (`medium`),
          3 for what was decided and why (`high`).
        * `text` (`str`):
          The text.
        * `wrap` (`bool`):
          False for text with lines of its own, such as `pip`'s output.
        """
        # Wrapped like every other paragraph.
        if self.verbosity() >= level:
            print(wrapped(text, columns(sys.stderr)) if wrap else text,
                  file=sys.stderr)

    def development_record(self, program: Path
                           ) -> tuple[Path, dict[str, Any]]:
        """Return a program's record under `develop/`, and what it holds.

        It holds the program's path, the fingerprint `reconcile` last
        settled (`asked`), the packages its imports implied then
        (`imported`), what its last runs declared and loaded behind the
        scenes (`runs`, `note_loaded`), and whether its end user agreed to its
        packages (`agreed`, `gate`).  Touched on
        use, so that `stale` ages out only records nothing uses.

        Arguments:
        * `program` (`Path`):
          The program.

        Returns:
        * (`tuple[Path, dict[str, Any]]`): The record, and its contents,
          empty when there is none yet.
        """
        # Named by the program's path, which it also holds.
        where: str = str(program.resolve())
        record: Path = (self.root / "develop"
                        / f"{hashlib.sha256(where.encode()).hexdigest()[:16]}"
                          ".json")
        kept: dict[str, Any] = {"program": where}
        try:
            loaded: object = json.loads(record.read_text())
            if isinstance(loaded, dict) and loaded.get("program") == where:
                kept = loaded
                record.touch()
        except (OSError, ValueError):
            pass
        return record, kept

    def keep(self, record: Path, kept: dict[str, Any],
             **changes: object) -> None:
        """Update a development record, the way `scan_imports` writes.

        Arguments:
        * `record` (`Path`):
          The record, under `develop/`.
        * `kept` (`dict[str, Any]`):
          What it held, which is updated too.
        * `changes` (`str`):
          `asked`, `warned` or `answer`.
        """
        # The stash on disk wins over an older copy in `kept`, which a
        # caller may have read before `put_stash` changed it.
        if "stash" not in changes:
            try:
                there: object = json.loads(record.read_text())
                if isinstance(there, dict) and "stash" in there:
                    kept["stash"] = there["stash"]
            except (OSError, ValueError):
                pass

        # Atomically, and quietly: a record is a convenience.
        kept.update(changes)
        handle: int
        temporary: str
        try:
            record.parent.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(dir=record.parent)
            with os.fdopen(handle, "w") as opened:
                json.dump(kept, opened, indent=1, sort_keys=True)
            Path(temporary).replace(record)
        except OSError:
            pass

    def stashing(self) -> bool:
        """Say whether this run keeps what it works out in the stash.

        Returns:
        * (`bool`): True for a developer's run with `EDIT_PROGRAM` off.
        """
        # The developer's, unless their Part 1 is edited.
        return not EDIT_PROGRAM and self.developing()

    def stash(self) -> dict[str, Any]:
        """Return what `ezpkg` keeps for a developer's program.

        In the program's `develop/` record, never in `prog.py` or its
        `.toml` (Wayne, 2026-10-22): `dependencies`, the entries for
        imports Part 1 does not declare; `checksums` and `tags`, the
        approvals (`record_approvals`); `exclude-newer`, the frozen
        date.  A program with none yet
        (a new program, a deleted `~/.ezpkg`, another computer, a moved
        program) is seeded once from what Part 1 itself holds, as an
        older `ezpkg` wrote it there, else from the newest entry of
        `prog.py.releases` (`seed_from_releases`), else starts empty.

        Returns:
        * (`dict[str, Any]`): The stash, empty for a program with no
          file.
        """
        # Read once per run; `put_stash` keeps the copy current.
        if self.stashed is not None:
            return self.stashed
        program: tuple[Path, str] | None = main_source()
        if program is None:
            return {}
        record: Path
        kept: dict[str, Any]
        record, kept = self.development_record(program[0])
        held: object = kept.get("stash")
        if isinstance(held, dict):
            self.stashed = held
            return held

        # Seeded from Part 1, then from the newest release.
        text: str = program[1]
        seeded: dict[str, Any] = {}
        approved: dict[str, str] | None = approvals_in(text)
        if approved:
            seeded["checksums"] = approved
            seeded["tags"] = approval_tags(text)
        dated: object = self.part1_value("uv", "exclude-newer")
        if isinstance(dated, datetime.date):
            dated = dated.isoformat()
        if isinstance(dated, str) and dated:
            seeded["exclude-newer"] = dated
        if "checksums" not in seeded:
            seeded = {**self.seed_from_releases(program[0]), **seeded}
        self.stashed = seeded
        self.keep(record, kept, stash=seeded)
        return seeded

    def seed_from_releases(self, program: Path) -> dict[str, Any]:
        """Return a stash taken from a program's newest release.

        Its entry in `prog.py.releases` holds the `dependencies` it
        shipped with and the date its versions are frozen at, so a
        program whose stash was lost resolves the same versions again,
        and its next run approves them afresh.

        Arguments:
        * `program` (`Path`):
          The program.

        Returns:
        * (`dict[str, Any]`): The stash, empty when there is no release.
        """
        # The newest entry, if the file can be read.
        try:
            entries: list[dict[str, Any]] = read_releases(program)
        except ValueError:
            return {}
        if not entries:
            return {}
        seeded: dict[str, Any] = {}
        listed: object = entries[-1].get("dependencies")
        if isinstance(listed, list):
            seeded["dependencies"] = [one for one in listed
                                      if isinstance(one, str)]
        when: object = entries[-1].get("exclude-newer")
        if isinstance(when, str) and when:
            seeded["exclude-newer"] = when
        self.say(3, f"ezpkg: {program.name}'s versions taken from "
                 f"{releases_path(program).name}")
        return seeded

    def put_stash(self, **changes: object) -> None:
        """Change keys of the stash, as `stash` describes them.

        Arguments:
        * `changes` (`object`):
          The keys and their new values.
        """
        # The record as it is now, so that nothing else in it is lost.
        program: Path | None = main_path()
        if program is None:
            return
        stashed: dict[str, Any] = {**self.stash(), **changes}
        record: Path
        kept: dict[str, Any]
        record, kept = self.development_record(program)
        self.stashed = stashed
        self.keep(record, kept, stash=stashed)

    def part1_value(self, table: str, key: str) -> object:
        """Return a key of a `[tool]` table in Part 1 itself.

        Arguments:
        * `table` (`str`):
          The table under `tool`, such as `uv`.
        * `key` (`str`):
          The key.

        Returns:
        * (`object`): Its value, or `None` when there is none or the
          block will not parse.
        """
        # A block that will not parse holds nothing.
        try:
            declared: dict[str, Any] = self.declaration()
        except ValueError:
            return None
        tool: object = declared.get("tool", {})
        found: object = tool.get(table, {}) if isinstance(tool, dict) else {}
        return found.get(key) if isinstance(found, dict) else None

    def check_imports(self, asking: Sequence[str]) -> None:
        """Refuse an export whose imports Part 1 does not cover.

        What a running program does not show is a package the author's
        own Python happens to have -- one a Linux distribution
        installed, say -- that Part 1 never names: it works here and
        fails on the machine the program is sent to.  Exporting is when
        the program leaves, so every export checks first, and lists
        every problem before failing.  Ordinary runs check too, but
        only warn; see `scan_imports`.  See `T.cibe` in `TASKS/`.

        Arguments:
        * `asking` (`Sequence[str]`):
          The requirements the program declared.

        Raises:
        * `RuntimeError`:
          If any import is not covered, after each one is printed on
          standard error with its line number.
        """
        # Every problem first, so one export shows them all.
        found: tuple[Path, list[str]] | None = self.import_problems(asking)
        if found is None or not found[1]:
            return
        program: Path
        problems: list[str]
        program, problems = found
        problem: str
        for problem in problems:
            print(f"{program.name}: {problem}", file=sys.stderr)
        raise RuntimeError(
            f"{len(problems)} import(s) in {program.name} are not "
            f"covered by Part 1; see above")

    def scan_imports(self, asking: Sequence[str]) -> list[str]:
        """Warn, during an ordinary run, about imports Part 1 misses.

        Python stops at the first missing import, so without this an
        author learns of missing packages one run at a time, and of a
        package their own Python happens to have only at export.  The
        scan reports them all at once, on standard error, and carries
        on; an export still refuses (`check_imports`).  See `T.siofr`
        in `TASKS/`.

        The scan costs a few hundred milliseconds when it has to ask
        which package provides a module, so every scan is remembered in
        `scans/`, one small file per fingerprint, and repeated only
        when the fingerprint changes.  The fingerprint is the program's
        path, the Python running it, the modules it imports (whether
        guarded, whether above the bootstrap), Part 1 and the approvals,
        so editing or moving code does not rescan, but adding an import
        does.  A scan that found problems is remembered too, so a
        warning is given once per change rather than on every run
        (Wayne, 2026-10-12).  Records age out with the request records;
        see `stale`.

        Arguments:
        * `asking` (`Sequence[str]`):
          The requirements the program declared.

        Returns:
        * (`list[str]`): The problems just reported, or an empty list
          when there were none or the scan was skipped as remembered.
        """
        # A program with no file, or one that does not parse, has
        # nothing to scan.
        source: tuple[Path, str] | None = main_source()
        if source is None:
            return []
        program: Path
        text: str
        program, text = source
        try:
            key: str = json.dumps({
                "program": str(program.resolve()),
                "python": sys.executable,
                "imports": [[module, guarded] for module, _, guarded
                            in program_imports(text)],
                "above": [module for module, _
                          in imports_above_bootstrap(text)],
                "statements": len(statements_above_bootstrap(text)),
                "asking": sorted(asking),
                "approved": sorted((self.approved() or {}).items()),
            }, sort_keys=True)
        except SyntaxError:
            return []

        # Remembered: touched, so that a scan in use does not age out.
        scans: Path = self.root / "scans"
        record: Path = scans / (
            hashlib.sha256(key.encode()).hexdigest() + ".json")
        try:
            if json.loads(record.read_text()).get("key") == key:
                record.touch()
                return []
        except (OSError, ValueError, AttributeError):
            pass

        # Scanned, reported, then remembered the way `remember` writes.
        found: tuple[Path, list[str]] | None = self.import_problems(asking)
        problems: list[str] = [] if found is None else found[1]
        problem: str
        # Not what this run has said already, and nothing after a
        # `restart`, whose first run said it all.
        if self.declined or self.restarted:
            problems = []
        problems = [problem for problem in problems
                    if not any(f": `{module}` " in problem
                               for module in self.reported)]
        for problem in problems:
            print(f"{program.name}: {problem}", file=sys.stderr)
        if problems:
            print(f"{program.name}: shown once; shown again "
                  f"when its imports, Part 1 or approvals change",
                  file=sys.stderr)
        handle: int
        temporary: str
        try:
            scans.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(dir=scans)
            with os.fdopen(handle, "w") as opened:
                json.dump({"key": key, "problems": problems}, opened,
                          indent=1, sort_keys=True)
            Path(temporary).replace(record)
        except OSError:
            pass
        return problems

    def import_problems(self, asking: Sequence[str]
                        ) -> tuple[Path, list[str]] | None:
        """Find the running program's imports Part 1 does not cover.

        The finding that `check_imports` refuses on and `scan_imports`
        warns about: one line for each import `uncovered_imports`
        finds, and one for each import above the bootstrap, which is a
        problem of its own; see `imports_above_bootstrap`.

        Arguments:
        * `asking` (`Sequence[str]`):
          The requirements the program declared.

        Returns:
        * (`tuple[Path, list[str]] | None`): The program and one line
          per problem, in order, or `None` when there is no program
          file to read or it does not parse.
        """
        # What Part 1 misses, and what runs too early.
        found: tuple[Path, str, list[tuple[int, str, list[str] | None]]
                     ] | None = self.uncovered_imports(asking)
        if found is None:
            return None
        program: Path
        text: str
        uncovered: list[tuple[int, str, list[str] | None]]
        program, text, uncovered = found
        problems: list[tuple[int, str]] = []
        line: int
        module: str
        names: list[str] | None
        for line, module, names in uncovered:
            if names is None:
                problem: str = (f"`{module}` is not importable here; "
                                f"add its package to Part 1")
            elif not names:
                problem = (f"`{module}` comes from "
                           f"{self.module_origin(module)}, which no "
                           f"package provides; it cannot travel with "
                           f"the program")
            else:
                problem = (f"`{module}` comes from {' or '.join(names)}, "
                           f"which Part 1 does not declare; add it to "
                           f"`dependencies`")
            problems.append((line, f"line {line}: {problem}"))

        # On a machine with an empty cache, these run before anything
        # has been fetched.
        for module, line in imports_above_bootstrap(text):
            problem = (f"`{module}` is imported above the bootstrap; "
                       f"move it below, with the other imports")
            problems.append((line, f"line {line}: {problem}"))
        for line in statements_above_bootstrap(text):
            problem = ("this runs before the bootstrap, and again "
                       "whenever ezpkg starts the program afresh; move it "
                       "below the bootstrap")
            problems.append((line, f"line {line}: {problem}"))
        return program, [problem for _, problem in sorted(
            problems, key=lambda one: one[0])]

    def uncovered_imports(self, asking: Sequence[str]) -> tuple[
            Path, str, list[tuple[int, str, list[str] | None]]] | None:
        """Find the running program's imports that Part 1 does not cover.

        Each module `program_imports` finds is accepted when it is in
        the standard library, is `ezpkg` itself (the bootstrap's
        business), is a file or directory beside the program, or comes
        from a distribution that Part 1 declares or that the approvals
        record, which covers the packages that came along.  Which
        distribution provides a module is read from the installed
        metadata and never guessed, and only when some module needs it,
        since reading it is the slow part.  An import guarded by
        `except ImportError` that finds nothing is accepted too.

        Arguments:
        * `asking` (`Sequence[str]`):
          The requirements the program declared.

        Returns:
        * (`tuple[Path, str, list[tuple[int, str, list[str] | None]]]
          | None`): The program, its text, and for each uncovered
          import its line, its module, and the distributions that
          provide it here: `None` when it is not importable at all,
          and an empty list when it is but no package provides it.
          `None` when there is no program file to read or it does not
          parse.
        """
        # A program with no file has no imports to read.
        source: tuple[Path, str] | None = main_source()
        if source is None:
            return None
        program: Path
        text: str
        program, text = source
        try:
            imports: list[tuple[str, int, bool]] = program_imports(text)
        except SyntaxError:
            return None

        # Distributions are compared by normalized name.
        covered: set[str] = {normal_name(requirement_name(one))
                             for one in asking}
        covered |= {normal_name(pin.partition("==")[0])
                    for pin in self.approved() or {}}
        providers: Mapping[str, list[str]] | None = None

        # Everything left after the exemptions has to be covered.
        uncovered: list[tuple[int, str, list[str] | None]] = []
        module: str
        line: int
        guarded: bool
        for module, line, guarded in imports:
            if self.exempt(program, module):
                continue
            spec: Any
            try:
                spec = importlib.util.find_spec(module)
            except (ImportError, ValueError):
                spec = None
            if spec is None:
                if not guarded:
                    uncovered.append((line, module, None))
                continue
            if providers is None:
                providers = importlib.metadata.packages_distributions()
            names: list[str] = providing(module, providers)
            if not names or not covered & {normal_name(name)
                                           for name in names}:
                uncovered.append((line, module, names))
        return program, text, uncovered

    @staticmethod
    def exempt(program: Path, module: str) -> bool:
        """Say whether an import needs no package from Part 1.

        The standard library, `ezpkg` itself (the bootstrap's
        business), and a file or directory beside the program.

        Arguments:
        * `program` (`Path`):
          The program.
        * `module` (`str`):
          A top-level module it imports.

        Returns:
        * (`bool`): True when Part 1 has nothing to do with it.
        """
        # Three kinds of import that never travel as packages.
        return (module in sys.stdlib_module_names or module == "ezpkg"
                or (program.parent / f"{module}.py").is_file()
                or (program.parent / module).is_dir())

    @staticmethod
    def module_origin(module: str) -> str:
        """Return where an importable module comes from, for a message.

        Arguments:
        * `module` (`str`):
          A top-level module that `find_spec` can find.

        Returns:
        * (`str`): Its file, or `somewhere` when it has none.
        """
        # A namespace package has no single file.
        spec: Any
        try:
            spec = importlib.util.find_spec(module)
        except (ImportError, ValueError):
            spec = None
        return getattr(spec, "origin", None) or "somewhere"

    def build_zipapp(self, asking: Sequence[str],
                     target: Path | None = None) -> Path:
        """Bundle the program and its packages into a `.pyz`.

        The result runs as `python3 prog.pyz` on a machine with no
        network, and leaves nothing behind: `ezpkg` is not in it and
        never runs.  The program goes in as `__main__.py` with its
        pasted bootstrap taken out (`strip_bootstrap`), because the
        packages the bootstrap would have fetched are already inside,
        and its own imports find them there.  In the bootstrap's place
        goes the one thing it did that still matters: a check that the
        Python running the archive meets Part 1's `requires-python`.  A program with no
        bootstrap to take out is refused, since it must use `ezpkg`
        some other way and would fail without it.

        Only what the approvals vouch for goes in, and only what a zip
        can carry: Python cannot import compiled code from inside an
        archive, and does not run `.pth` files there, so a package with
        either is refused rather than bundled half working.  With `uv`,
        the pure packages that only other computers need go in too,
        each checked against `uv`'s lock (`elsewhere_trees`).

        Arguments:
        * `asking` (`Sequence[str]`):
          The requirements the program declared.
        * `target` (`Path | None`):
          Where to write the archive; `None` means beside the program,
          as `prog.py` to `prog.pyz`.

        Returns:
        * (`Path`): The archive written.

        Raises:
        * `RuntimeError`:
          If the program has no file or no bootstrap, there are no
          approvals, the packages did not come from the cache, or any
          of them is unapproved, compiled, or carries a `.pth` file.
        """
        # The program, without its bootstrap, is the archive's
        # `__main__.py`.  Read as bytes and written back in the encoding
        # it declares, so a `coding:` line stays true.
        program: Path | None = main_path()
        if program is None:
            raise RuntimeError("a zipapp needs the program's own file")
        target = target or program.with_suffix(".pyz")
        text: str
        encoding: str
        text, encoding, _ = self.program_text(program)

        # The bootstrap checked the Python version; the archive has no
        # bootstrap, so its line checks instead, when Part 1 gives a
        # floor `python_floor` can read.  `__import__` because the
        # program's own `import sys` is not guaranteed.  A program whose
        # syntax is newer than the Python running it still fails to
        # compile before this line runs, as it would have anyway.
        statement: str = "pass"
        try:
            declared: dict[str, Any] = script_metadata(text) or {}
        except ValueError:
            declared = {}
        wanted: object = declared.get("requires-python")
        floor: tuple[int, ...] | None = (
            python_floor(wanted) if isinstance(wanted, str) else None)
        if floor is not None:
            statement = (
                f"if __import__('sys').version_info < {floor}: "
                f"raise SystemExit('{target.name} needs Python "
                f"{'.'.join(map(str, floor))} or newer, not ' "
                f"+ __import__('platform').python_version())")
        stripped: str | None = strip_bootstrap(
            text, "a zipapp carries its packages.", statement)
        if stripped is None:
            raise RuntimeError(
                "a zipapp leaves ezpkg out, so the program needs the "
                "pasted bootstrap for it to take out, and has none")

        # What this request resolved to, as the cache recorded it.  No
        # approvals means nothing was fetched, so nothing is approved.
        approved: dict[str, str] = self.approved() or {}
        pinned: set[str] = {normal_pin(pin) for pin in approved}
        remembered: tuple[list[str], list[str]] | None = (
            self.remember(self.request_for(asking)) if asking
            else ([], []))
        if remembered is None:
            raise RuntimeError(
                "the declared packages did not come from the cache, so "
                "there is nothing approved to bundle")
        trees: list[str]
        wheels: list[str]
        trees, wheels = remembered
        trees, wheels = (for_export(trees, stripped),
                         for_export(wheels, stripped))

        # Approved, pure Python, and no `.pth` to go unrun.
        versions: Path = self.paths()[2]
        unapproved: list[str] = sorted(
            wheel for wheel in wheels
            if normal_pin(wheel_pin(wheel)) not in pinned)
        compiled: list[str] = sorted(
            wheel for wheel in wheels
            if not wheel.endswith("-none-any.whl"))
        hooks: list[str] = sorted(
            found.name for tree in trees
            for found in (versions / tree).glob("*.pth"))
        problem: str
        names: list[str]
        for problem, names in (("not in the `checksums`", unapproved),
                               ("compiled, which a zip cannot import",
                                compiled),
                               ("a .pth file, which a zip never runs",
                                hooks)):
            if names:
                raise RuntimeError(
                    f"cannot bundle {', '.join(names)}: {problem}")

        # What other computers need too, when `uv` can say.
        elsewhere: list[Path] = self.elsewhere_trees(
            stripped, encoding, approved, target)
        hooks = sorted(found.name for tree in elsewhere
                       for found in tree.glob("*.pth"))
        if hooks:
            raise RuntimeError(f"cannot bundle {', '.join(hooks)}: a .pth "
                               f"file, which a zip never runs")

        # Stage the trees and the program, then zip them.
        staging: str
        with tempfile.TemporaryDirectory(prefix="ezpkg-zipapp-") \
                as staging:
            stage: Path = Path(staging)
            source: Path
            for source in [versions / tree for tree in trees] + elsewhere:
                shutil.copytree(
                    source, stage, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
            (stage / "__main__.py").write_bytes(stripped.encode(encoding))
            zipapp.create_archive(stage, target,
                                  interpreter="/usr/bin/env python3")
        self.say(3, f"ezpkg: wrote {target}, with {len(elsewhere)} more "
                 f"package(s) that other computers need")
        return target

    def build_uv(self, target: Path | None = None) -> Path:
        """Write the program as a `uv` script, with its lock file.

        Two files, beside the program unless `target` says otherwise:
        `prog-uv.py`, the program with Part 1 pinned to what was approved
        and its bootstrap taken out (`pin_dependencies`,
        `strip_bootstrap`); and `prog-uv.py.lock`, which `uv run
        prog-uv.py` finds by its name and uses.  Unlike a `zipapp`,
        compiled packages are fine: the lock lists every platform's
        wheels.  The same lock in PEP 751's `pylock.toml` format is not
        written: `uv run` ignores it, and nobody this release is for
        needs it (Wayne, 2026-10-12).

        `uv` writes the locks, because it resolves for every platform and
        records where each wheel is downloaded from, which the approvals
        do not.  The pins hold it to the approved versions, and the lock
        is then checked against the approvals by SHA-256
        (`lock_mismatches`).  A `PIP_INDEX_URL` is handed on as `uv`'s
        default index, so both resolve against the same one.  Without
        `uv`, the script is still written, with the commands to finish.

        Arguments:
        * `target` (`Path | None`):
          The script to write; `None` means `prog-uv.py` beside the
          program.  The locks are named after it.

        Returns:
        * (`Path`): The script written.

        Raises:
        * `RuntimeError`:
          If the program has no file, bootstrap or readable Part 1, there
          are no approvals, `uv` fails, or its lock disagrees with them.
        """
        # The program, pinned and without its bootstrap, in the encoding
        # it declares, so a `coding:` line stays true.
        program: Path | None = main_path()
        if program is None:
            raise RuntimeError("a uv script needs the program's own file")
        target = target or program.with_name(f"{program.stem}-uv.py")
        text: str
        encoding: str
        text, encoding, _ = self.program_text(program)
        stripped: str | None = strip_bootstrap(
            text, "uv installs the packages.")
        if stripped is None:
            raise RuntimeError(
                "a uv script leaves ezpkg out, so the program needs "
                "the pasted bootstrap for it to take out, and has none")
        pinned: str | None = pin_dependencies(
            stripped, for_export(self.pins(), stripped))
        if pinned is None:
            raise RuntimeError(
                "cannot find the dependencies in Part 1 to pin")
        target.write_bytes(pinned.encode(encoding))
        self.say(3, f"ezpkg: wrote {target}")

        # `uv` locks it; without `uv`, say how to finish elsewhere.
        uv: str | None = self.uv()
        if uv is None:
            print("uv could not be had; to finish, run:")
            print(f"    uv lock --script {target}")
            return target

        # The lock must list the very wheels that were approved.
        lock: Path = target.with_name(target.name + ".lock")
        approved: dict[str, str] = self.approved() or {}
        problems: list[str] = lock_mismatches(
            self.lock_script(uv, target),
            {pin: approved[pin]
             for pin in for_export(approved, stripped)})
        if problems:
            raise RuntimeError(
                "uv's lock disagrees with the approvals: "
                + "; ".join(problems))
        self.say(3, f"ezpkg: wrote {lock}")
        return target

    def lock_script(self, uv: str, script: Path,
                    before: str = "") -> dict[str, Any]:
        """Have `uv` lock a script for every computer, and read the lock.

        `uv lock --script` writes `prog.py.lock` beside `prog.py`.  A
        `PIP_INDEX_URL` is handed on as `uv`'s default index, so both
        resolve against the same one.

        Arguments:
        * `uv` (`str`):
          The `uv` command, from `find_uv`.
        * `script` (`Path`):
          The script, with Part 1 as it should be locked.
        * `before` (`str`):
          Lock only what was uploaded before this date, the program's
          `exclude-newer`; empty means no date.  An index without
          upload times cannot apply it, so a failure with a date tries
          once more without, as `download` does.

        Returns:
        * (`dict[str, Any]`): The lock, as `tomllib` reads it.

        Raises:
        * `RuntimeError`:
          If `uv` fails.
        """
        # The same index as `pip`, unless `uv` was told one itself.
        environment: dict[str, str] = dict(os.environ)
        index: str = environment.get("PIP_INDEX_URL", "")
        if index and not (environment.get("UV_DEFAULT_INDEX")
                          or environment.get("UV_INDEX_URL")):
            environment["UV_DEFAULT_INDEX"] = index
        dated: list[str] = ["--exclude-newer", before] if before else []
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [uv, "lock", "--script", str(script), *dated], env=environment,
            capture_output=True, text=True, check=False)
        if done.returncode and before:
            self.say(2, f"Locking without the program's exclude-newer "
                     f"date {before}, which uv could not apply")
            return self.lock_script(uv, script)
        if done.returncode:
            raise RuntimeError(f"uv lock failed: {done.stderr.strip()}")
        lock: Path = script.with_name(script.name + ".lock")
        return tomllib.loads(lock.read_text(encoding="utf-8"))

    def uv(self) -> str | None:
        """Return a `uv` to lock with, fetching one if none is installed.

        A release resolves for every computer with `uv` (`T.ee`), and the
        developer should never have to install it (Wayne, 2026-10-21).
        `uv` is published on PyPI as a wheel for each kind of computer,
        with the program inside, so `pip` picks the right one exactly as
        it does for any package.  An installed `uv` at least `UV_FLOOR`
        is used first; then the newest one already fetched into the
        cache; then the newest from the index, unpacked into the cache
        like any other package, where `cull` ages it out.
        `EZPKG_UV=fetch` passes over an installed `uv`, for tests only.

        Returns:
        * (`str | None`): The command to run, or `None` when none could
          be had; what went wrong has been said.
        """
        # Installed, unless a test wants the fetch.
        if os.environ.get("EZPKG_UV", "").lower() != "fetch":
            installed: str | None = find_uv()
            if installed is not None:
                return installed

        # Already fetched, the newest first.
        name: str = "uv.exe" if os.name == "nt" else "uv"
        versions: Path = self.paths()[2]
        key: str = self.version_key(Path("uv-0-x-x-x.whl"))
        suffix: str = key.removeprefix("uv-0")

        def numbered(tree: Path) -> tuple[int, ...]:
            # `uv-0.12.21-cpython-312-linux-x86_64` to `(0, 12, 21)`.
            version: str = tree.name.removeprefix("uv-").removesuffix(suffix)
            return tuple(int(part) if part.isdigit() else -1
                         for part in version.split("."))
        tree: Path
        for tree in sorted(versions.glob(f"uv-*{suffix}"), key=numbered,
                           reverse=True):
            if numbered(tree) >= UV_FLOOR:
                binary: Path | None = next(
                    tree.glob(f"uv-*.data/scripts/{name}"), None)
                if binary is not None:
                    return str(binary)

        # Fetched, as `pip` chooses the wheel for this computer.
        floor: str = ".".join(map(str, UV_FLOOR))
        arrived: list[Path] = []
        try:
            arrived = self.download([f"uv>={floor}"], ["--no-deps"])
            wheel: Path | None = next(
                (one for one in arrived if one.name.startswith("uv-")), None)
            if wheel is None:
                raise RuntimeError("no uv wheel arrived")
            tree = self.unpack(wheel)
        except (RuntimeError, ValueError, OSError) as error:
            self.say(1, f"`uv`, which a release uses to find what other "
                     f"computers need, could not be fetched: "
                     f"{failure_reason(error)}")
            return None
        finally:
            holding: Path
            for holding in {one.parent for one in arrived}:
                shutil.rmtree(holding, ignore_errors=True)

        # A zip keeps no permissions, so the program is made runnable.
        fetched: Path | None = next(
            tree.glob(f"uv-*.data/scripts/{name}"), None)
        if fetched is None:
            self.say(1, f"The `uv` wheel in {tree} has no {name}.")
            return None
        fetched.chmod(fetched.stat().st_mode | 0o111)
        self.say(2, f"Fetched `uv` into {tree} for this release.")
        return str(fetched)

    def lock_everywhere(self, uv: str, name: str, stripped: str,
                        encoding: str, approved: Mapping[str, str]
                        ) -> dict[str, Any]:
        """Lock the program for every computer, held to its approvals.

        A copy of the program, pinned to what was approved, is locked
        in a scratch directory under the program's `exclude-newer`
        date, and the lock is checked against the approvals by SHA-256
        (`lock_mismatches`).  Shared by `build_email` and
        `build_zipapp`, which both need what other computers fetch.

        Arguments:
        * `uv` (`str`):
          The `uv` command, from `find_uv`.
        * `name` (`str`):
          The program's file name, which the copy takes.
        * `stripped` (`str`):
          The program without its bootstrap, which `uv` has no use for.
        * `encoding` (`str`):
          The program's encoding.
        * `approved` (`Mapping[str, str]`):
          Pins to ids, as `EZPkg.approved` returns them.

        Returns:
        * (`dict[str, Any]`): The lock, as `tomllib` reads it.

        Raises:
        * `RuntimeError`:
          If Part 1 cannot be pinned, `uv` fails, or its lock disagrees
          with the approvals.
        """
        # Pinned, so `uv` resolves to what was approved, with the
        # entries nothing here fetched, such as another platform's
        # (`pywin32; sys_platform == 'win32'`), kept as they are.
        pins: list[str] = for_export(self.pins(), stripped)
        named: set[str] = {normal_name(requirement_name(pin))
                           for pin in pins} | {"ezpkg"}
        listed: object = (script_metadata(stripped) or {}).get(
            "dependencies")
        pinned: str | None = pin_dependencies(stripped, pins + [
            entry for entry in (listed if isinstance(listed, list) else [])
            if isinstance(entry, str)
            and normal_name(requirement_name(entry)) not in named])
        if pinned is None:
            raise RuntimeError(
                "cannot find the dependencies in Part 1 to pin")
        folder: str
        with tempfile.TemporaryDirectory() as folder:
            script: Path = Path(folder) / name
            script.write_bytes(pinned.encode(encoding))
            lock: dict[str, Any] = self.lock_script(
                uv, script, self.declared_date())
        problems: list[str] = lock_mismatches(
            lock, {pin: approved[pin]
                   for pin in for_export(approved, stripped)})
        if problems:
            raise RuntimeError("uv's lock disagrees with the approvals: "
                               + "; ".join(problems))
        return lock

    def elsewhere_trees(self, stripped: str, encoding: str,
                        approved: Mapping[str, str], target: Path
                        ) -> list[Path]:
        """Return the trees of pure packages only other computers need.

        For a `zipapp`, which carries its packages: a developer's run
        fetched what this computer needs, but a package can need others
        only elsewhere, as `tqdm` needs `colorama` on Windows alone.
        With `uv`, the program is locked for every computer
        (`lock_everywhere`), and each package the lock adds is fetched
        by the lock's URL, checked against its SHA-256 and unpacked into
        the cache.  A package already approved is never added again,
        even at another version for another Python, since a zip can hold
        only one.  A compiled one cannot go in a zip, so it is named,
        and the archive runs only where it is not needed.  Without `uv`,
        one line says the archive carries what this computer needed
        (Wayne, 2026-10-21: a `zipapp` does not require `uv`).

        Arguments:
        * `stripped` (`str`):
          The program without its bootstrap.
        * `encoding` (`str`):
          The program's encoding.
        * `approved` (`Mapping[str, str]`):
          Pins to ids, as `EZPkg.approved` returns them.
        * `target` (`Path`):
          The archive being built, to name in what is said.

        Returns:
        * (`list[Path]`): The unpacked trees to add, in the lock's order.

        Raises:
        * `RuntimeError`:
          If the lock fails, or a fetched wheel is not the one it names.
        """
        # Without `uv`, this computer's packages are all there is.
        uv: str | None = self.uv()
        if uv is None:
            self.say(1, f"So `{target.name}` carries only the packages "
                     f"this computer needed; another kind of computer "
                     f"may need more.")
            return []
        program: Path | None = main_path()
        lock: dict[str, Any] = self.lock_everywhere(
            uv, program.name if program else target.stem + ".py",
            stripped, encoding, approved)

        # Each package the lock adds, by its pure wheel, if it has one.
        known: set[str] = {normal_name(pin.partition("==")[0])
                           for pin in approved}
        pending: Path
        wheels: Path
        versions: Path
        pending, wheels, versions, _unused = self.paths()
        trees: list[Path] = []
        compiled: list[str] = []
        package: dict[str, Any]
        for package in lock.get("package", []):
            files: list[tuple[str, str, str]] = []
            wheel: dict[str, Any]
            for wheel in package.get("wheels", []):
                url: str = str(wheel.get("url", ""))
                file: str = url.rsplit("/", 1)[-1]
                digest: str = str(wheel.get("hash", ""))
                if file.endswith(".whl") and digest.startswith("sha256:"):
                    files.append((file, url, digest.removeprefix("sha256:")))
            if (not files or normal_name(wheel_pin(files[0][0])
                                         .partition("==")[0]) in known):
                continue
            pure: list[tuple[str, str, str]] = [
                one for one in files if not wheel_tag(one[0])]
            if not pure:
                compiled.append(wheel_pin(files[0][0]))
                continue

            # The cache's tree, if its wheel is this one; else fetched.
            url, digest = pure[0][1], pure[0][2]
            name: Path = Path(pure[0][0])
            tree: Path = versions / self.version_key(name)
            hashed: Path = (wheels / name.name).with_suffix(".sha256")
            if not (tree.is_dir() and hashed.is_file()
                    and hashed.read_text().strip() == digest):
                body: bytes = fetch_url(url)
                if hashlib.sha256(body).hexdigest() != digest:
                    raise RuntimeError(f"{name.name} from {url} is not "
                                       f"the file uv's lock names")
                arrived: Path = pending / name.name
                arrived.write_bytes(body)
                tree = self.unpack(arrived)
            trees.append(tree)
        if compiled:
            self.say(1, f"`{target.name}` cannot carry "
                     f"{and_list(compiled)}, which another kind of "
                     f"computer needs and which is compiled, so it will "
                     f"not run on that kind of computer.")
        return trees

    def build_email(self, target: Path | None = None) -> Path:
        """Write the program to send, approved for every computer.

        The program itself, bootstrap and all, with its `checksums`
        completed for every computer and Python its `requires-python`
        admits (`T.ee`).  A developer's runs approve only what arrived
        on the developer's own computer, so a package that another
        computer alone needs, as `tqdm` needs `colorama` on Windows, would
        be refused there.  `uv` resolves for every computer at once, so
        a copy of the program, pinned to what was approved and without
        its bootstrap as for `build_uv`, is locked in a scratch
        directory, and `everywhere_approvals` adds what the lock needs
        beyond the approvals.  The program's own `checksums` are left
        alone: the developer's next run would put them back.

        Arguments:
        * `target` (`Path | None`):
          The file to write; `None` means `prog-email.py` beside the
          program.  A release names it by version (`prog-1.0.0.py`).

        Returns:
        * (`Path`): The file written.

        Raises:
        * `RuntimeError`:
          If the program has no file, bootstrap, readable Part 1 or
          approvals, if `uv` is not installed or fails, or if its lock
          disagrees with the approvals.
        """
        # The program as it is, and what was approved.
        program: Path | None = main_path()
        if program is None:
            raise RuntimeError("an email release needs the program's "
                               "own file")
        target = target or program.with_name(f"{program.stem}-email.py")
        uv: str | None = self.uv()
        if uv is None:
            raise RuntimeError(
                "an email release needs `uv` to find the packages other "
                "computers need, and none could be had")
        text: str
        encoding: str
        crlf: bool
        text, encoding, crlf = self.program_text(program)
        # No approvals means nothing was fetched, so nothing is approved.
        approved: dict[str, str] = self.approved() or {}

        # Locked for every computer, from a pinned copy without the
        # bootstrap, which `uv` has no use for.
        stripped: str | None = strip_bootstrap(text, "uv installs the "
                                               "packages.")
        if stripped is None:
            raise RuntimeError("an email release sends the program with "
                               "its bootstrap, and it has none")
        lock: dict[str, Any] = self.lock_everywhere(
            uv, program.name, stripped, encoding, approved)

        # The copy, with every computer's approvals in its Part 1.
        rows: dict[str, str]
        tags: dict[str, str]
        rows, tags = everywhere_approvals(lock, approved,
                                          approval_tags(text))
        block: tuple[re.Match[str], str] | None = script_toml(text)
        toml: str | None = (uv_setting(block[1], "checksums",
                                       approvals_array(rows, tags), "ezpkg")
                            if block else None)
        if block is None or toml is None:
            raise RuntimeError("cannot write the checksums into Part 1 "
                               "of the email copy")
        write_program(target, with_script_toml(text, block[0], toml),
                      encoding, crlf)
        self.say(3, f"ezpkg: wrote {target}, with "
                 f"{len(rows) - len(approved)} more package(s) that "
                 f"other computers need")
        return target

    def metadata(self, wheel: Path) -> dict[str, str]:
        """Return a wheel's `Name`, `Version` and `Summary`, made safe.

        Read from the `METADATA` inside the archive, unpacking nothing;
        see `metadata_fields`.

        Arguments:
        * `wheel` (`Path`):
          A wheel to look inside.

        Returns:
        * (`dict[str, str]`): Whichever of the three it has, perhaps
          none, as for a file that is not a wheel at all.
        """
        # Any `.dist-info/METADATA`: a wheel holds exactly one.
        archive: zipfile.ZipFile
        try:
            with zipfile.ZipFile(wheel) as archive:
                name: str = next(one for one in archive.namelist()
                                 if one.endswith(".dist-info/METADATA"))
                return metadata_fields(
                    archive.read(name).decode("utf8", "replace"))
        except (OSError, KeyError, StopIteration, zipfile.BadZipFile):
            return {}

    def bootstrapped(self) -> list[tuple[str, str]]:
        """Return what the bootstrap put here on this, its first, run.

        A first run's bootstrap has already stored `pip` and `ezpkg` by
        the time anybody is asked anything, and answering `n` removes
        them too, so they are listed with the program's own packages
        rather than hidden (Wayne, 2026-10-18).  `pip` is marked as
        `ezpkg`'s, since the program's author did not choose it.  Only
        the run whose bootstrap fetched them (`first_run`) lists them,
        and only once (`told`).

        Returns:
        * (`list[tuple[str, str]]`): Each one's name and version, then
          its summary, `pip` first, as they arrived.
        """
        # Nothing, unless this run's bootstrap fetched them.  The mark
        # goes before the summary, which may be cut.
        if not self.first_run or self.told:
            return []
        found: list[tuple[str, str]] = []
        fields: dict[str, str] = self.metadata(self.root / "pip.whl")
        if fields:
            title: str = (f"{fields.get('Name', 'pip')} "
                          f"{fields.get('Version', '')} (used by `ezpkg`)")
            found.append((title, fields.get("Summary", "")))
        fields = self.metadata(self.root / "ezpkg.whl")
        if fields:
            title = f"{fields.get('Name', 'ezpkg')} {fields.get('Version', '')}"
            found.append((title.strip(), fields.get("Summary", "")))

        # `pip install --target` leaves a `.dist-info` for each package
        # it installed: `ezpkg`, and anything `ezpkg` ever comes to need.
        record: Path
        for record in sorted(self.root.glob("*.dist-info/METADATA")):
            try:
                fields = metadata_fields(
                    record.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if "Name" in fields:
                title = f"{fields['Name']} {fields.get('Version', '')}"
                found.append((title.strip(), fields.get("Summary", "")))
        return found

    def described(self, wheels: Sequence[Path]
                  ) -> list[tuple[str, str]]:
        """Return the name and version, and summary, of every new package.

        What the bootstrap stored on a first run (`bootstrapped`), then
        the wheels that arrived, by name.  A wheel's version is the one
        its file name fixes; its name is the one its metadata spells,
        such as `PyYAML` for `pyyaml-6.0.3-...whl`.

        Arguments:
        * `wheels` (`Sequence[Path]`):
          The wheels that arrived.

        Returns:
        * (`list[tuple[str, str]]`): One entry per package.
        """
        # The file name is the authority for the version.
        found: list[tuple[str, str]] = self.bootstrapped()
        wheel: Path
        for wheel in sorted(wheels, key=lambda one: normal_name(
                one.name.split("-")[0])):
            parts: list[str] = wheel.stem.split("-")
            fields: dict[str, str] = self.metadata(wheel)
            found.append((f"{fields.get('Name', parts[0])} {parts[1]}",
                          fields.get("Summary", "")))
        return found

    def details(self, wheels: Sequence[Path],
                width: int = LINE_WIDTH) -> list[str]:
        """Describe each new package in one numbered line, for `?`.

        The name and version, then the package's own summary, cut to fit
        `width` (Wayne, 2026-10-17: the earlier origin, size, digest and
        "it says" lines were "way, way, way too verbose").  The summary
        is the uploader's words, so a typosquat's reads like the real
        one.  The same packages as the list after a `y` (`listing`).

        Arguments:
        * `wheels` (`Sequence[Path]`):
          The wheels that arrived.
        * `width` (`int`):
          The longest line, in characters.

        Returns:
        * (`list[str]`): Lines to show, without trailing newlines.
        """
        # `  1. cowsay 6.1: The famous cowsay ...`, cut with `...`.
        return [cut(f"{number}. {title}" + (f": {told}" if told else ""),
                    width)
                for number, (title, told)
                in enumerate(self.described(wheels), 1)]

    def place(self) -> str:
        """Return how messages name the cache, such as `` `~/.ezpkg` ``.

        PowerShell understands `~`, but `cmd.exe` and File Explorer do
        not, so on Windows it is the full path (`shown`; Wayne,
        2026-10-18: "ugly, but so is Windows").  Any other root, as tests
        and some programs give, is named the same way.

        Returns:
        * (`str`): The path in backquotes.
        """
        # One way of naming it, everywhere.
        return f"`{shown(self.root)}`"

    def listing(self, wheels: Sequence[Path], width: int) -> str:
        """Say what is now retained, after it has been unpacked.

        "Retained", as the question says it (Wayne, 2026-10-19).

        Every package this run put into the cache, the bootstrap's
        included, one numbered line each, then where to read about
        `ezpkg`, then a blank line before the program's own output
        (`ux/ux01_Baseline.txt`).  "N package(s)" is literal, for any N
        (Wayne).

        Arguments:
        * `wheels` (`Sequence[Path]`):
          The wheels that arrived.
        * `width` (`int`):
          The longest line wanted.

        Returns:
        * (`str`): The lines, ending with the blank one, but for the
          last newline, which `print` adds.
        """
        # A heading, a line per package, and a footing.
        packages: list[tuple[str, str]] = self.described(wheels)
        place: str = self.place()
        lines: list[str] = [wrapped(
            f"The following {len(packages)} package(s) are now "
            f"retained in {place}:", width)]
        lines += [cut(f"{number}. {title}" + (f": {told}" if told else ""),
                      width)
                  for number, (title, told) in enumerate(packages, 1)]
        lines.append(wrapped(f"`ezpkg` ({HOME_PAGE}) manages {place}; "
                             f"its `list.py` says what is there.", width))
        return "\n".join(lines) + "\n"


    def terminal(self) -> tuple[IO[str], IO[str]] | None:
        """Return the controlling terminal, or `None` if there is none.

        `/dev/tty` rather than `sys.stdin`, because a program used as a
        filter has its standard input bound to a pipe and reading a line
        from it would silently eat the program's own data.  This is how
        `ssh` and `sudo` ask for a password.

        Two handles rather than one opened `r+`.  Measured 2026-09-26
        against a pseudoterminal: `r+` raises
        `UnsupportedOperation: File or stream is not seekable`, because
        buffered read-write text mode wants to seek and a character
        device cannot.  That exception is a subclass of `OSError`, so a
        single handle plus `except OSError` would have caught it and
        reported no terminal, silently never asking anybody anything.

        Opening it is the test.  There is often no controlling terminal
        at all -- under `cron`, a service manager, a build, or a
        double-clicked launcher -- and then there is nobody to ask.

        Windows has no `/dev/tty`, so until 2026-10-16 nobody there was
        ever asked (`I.owenabd`).  Its console's own names are `CONOUT$`
        and `CONIN$`, which reach the console even when standard input
        is a pipe, and fail to open when there is no console, as for a
        `.pyw` or a service.

        A set `CI` (GitHub Actions, GitLab and most others set it) means
        nobody is there either, whatever terminal or console exists.

        Returns:
        * (`tuple[IO[str], IO[str]] | None`): The terminal open for
          writing and for reading, or `None` when there is not one.
        """
        # A CI system is nobody to ask, though it may provide a console.
        if os.environ.get("CI", "").lower() not in ("", "0", "false"):
            return None

        # Whether both open is the whole of the question.
        writing: str
        reading: str
        writing, reading = (("CONOUT$", "CONIN$") if os.name == "nt"
                            else ("/dev/tty", "/dev/tty"))
        try:
            return (Path(writing).open("w", encoding="utf-8"),
                    Path(reading).open("r", encoding="utf-8"))
        except OSError:
            return None

    def consent(self, wheels: Sequence[Path],
                asking: Sequence[str]) -> bool:
        """Ask once whether to install what arrived.

        One question, not one per package: the count is the part anybody
        can judge.  Somebody who cannot say whether
        `charset-normalizer 3.3.2` belongs can still say that seven
        packages is a surprise when they asked for one.

        Each answer is spelled out in the prompt rather than abbreviated,
        because a person who has never seen this question before should
        not have to guess what a letter means.  Case does not matter.

        `y` or `yes` goes ahead, for this program and every later
        version of it (`gate` remembers); `n` or `no` declines; `?`
        describes each wheel and asks again (`T.abfd`).

        Anything else is taken for a typo and the question is put again,
        up to `ATTEMPTS` typos.  A bare newline just asks again, without
        a word and without counting (Wayne, 2026-10-19): there is no
        default, because a distracted Enter should neither install nor
        quietly decline, and `ANSWER_SECONDS` already ends a wait that
        nobody answers.  Asking for the detail is not a typo and does
        not count either, so curiosity is never punished.  A terminal that
        has gone away reads as empty, which
        declines at once rather than being asked again forever.

        With no terminal (or a set `CI`) there is nobody to ask, and the
        answer is yes: the list of what was retained is still printed, and
        failing instead would break every program run from `cron` or a
        build on the first day.  The author's `checksums` still decide
        which files are accepted.

        Arguments:
        * `wheels` (`Sequence[Path]`):
          The wheels that arrived.
        * `asking` (`Sequence[str]`):
          The requirements that were asked for.

        Returns:
        * (`bool`): True to go ahead.
        """
        # No terminal, no question.
        opened: tuple[IO[str], IO[str]] | None = self.terminal()
        if opened is None:
            return True

        # `y` goes ahead, `n` declines, `?` says more and asks again, an
        # empty line just asks again, and anything else is a typo worth
        # asking about again.  Only typos are counted, so that reading
        # the detail can never use up the patience meant for mistakes.
        answer: str
        typos: int = 0
        writer: IO[str]
        reader: IO[str]
        writer, reader = opened

        # Wayne's words (`ux/ux01_Baseline.txt`): a paragraph, said
        # once, then the question, put again after a `?` or a typo.
        # It does not say the packages are already downloaded:
        # "retained" is true, and on `n` nothing runs.
        name: str = name_of(program_name())
        place: str = self.place()
        width: int = columns(writer)
        # A no takes the whole cache only on a first run (`removed`).
        refused: str = (f"{place} will simply go away without running "
                        f"{name}" if self.newly_filled() else
                        f"{name} will not run")
        paragraph: str = wrapped(
            f"The author of {name} has selected some software packages "
            f"from the internet.  If you agree, they are retained in "
            f"{place}.  If you do not trust the author, answer `n` and "
            f"{refused}.", width)
        question: str = wrapped(f"Retain {place} and run {name}?", width)
        question += "\n[y=>Yes|n=>No|?=>Explain]: "
        told: bool = False
        with writer, reader:
            writer.write(paragraph + "\n\n")
            while typos < ATTEMPTS:
                writer.write(question)
                writer.flush()
                answer = answer_from(reader, writer)

                # Standard error sent to a file gets the question and
                # the answer too, so that it tells the whole story.
                if not sys.stderr.isatty():
                    print(("" if told else paragraph + "\n\n")
                          + f"{question}{answer.strip()}", file=sys.stderr)
                    told = True

                # An empty read is the terminal going away, not an
                # answer, and asking again would never end.  Control-D
                # leaves the cursor after the question (`ux21`).
                if not answer:
                    writer.write("\n")
                    return False
                answer = answer.strip().lower()
                if not answer:
                    continue
                if answer in ("y", "yes"):
                    return True
                if answer in ("n", "no"):
                    return False
                if answer == "?":
                    writer.write(
                        "\nSoftware packages are code from PyPI, the "
                        "Python Package Index:\n"
                        + "\n".join(self.details(wheels)) + "\n\n")
                    continue
                typos += 1
                writer.write("Please answer y, n, or ? for more.\n")
        return False

    def gate(self, wheels: Sequence[Path], asking: Sequence[str] = (),
             new: Sequence[Path] | None = None) -> None:
        """Record, enforce or ask, as the program's mode says.

        A developer's run records what arrived (`record_approvals`).
        Otherwise approvals decide: if the author approved this set, it
        is verified in silence, and if there are no approvals at all the
        person who started the program is asked once.  The author's
        judgement replaces the recipient's prompt rather than being
        added to it.

        The program's developer is never asked, and an end user is asked
        once per program (its path): a yes covers it and its later
        versions, whose new packages arrive silently, as Ubuntu updates
        do (`T.abfd`).  The run that agrees sets `agreeing`, so that
        `provide` lists what was stored.  Approvals stand in for the
        question, but never for `verify`.  See `agree`.

        Arguments:
        * `wheels` (`Sequence[Path]`):
          The wheels to record or to check.
        * `asking` (`Sequence[str]`):
          The requirements that were asked for, for the question.
        * `new` (`Sequence[Path] | None`):
          Those of `wheels` not already unpacked, which are what the
          question is about; `None` means all of them.

        Raises:
        * `RuntimeError`:
          Through `verify`, if a wheel is unapproved or altered, or if
          the person asked declines.
        """
        # The developer's run records what arrived, and dates it, but
        # not on the run that filled `prog.py.toml` (`settings`).
        if self.developing():
            if self.filled is None:
                self.record_approvals(wheels)
            return

        # Approvals are checked, never skipped; then the program's end
        # user agrees, once.
        if self.approved() is not None:
            self.verify(wheels)
        self.agree(wheels if new is None else new, asking, True)

    def agree(self, wheels: Sequence[Path], asking: Sequence[str],
              fresh: bool) -> None:
        """Ask the end user once per program, on its first run, ever.

        Whether or not this run downloaded anything: a program whose
        packages another program already fetched is still somebody's
        code to run (Wayne, S2.2).  A yes is recorded in the program's
        `develop/` record (`agreed`), which never ages out (S2.1); so is
        a program that has no terminal to ask on (S2.3).  The author's
        `checksums` never stand in for the question: they say which
        files, and only the person running the program can say whether
        they trust its author (Wayne, 2026-10-20).  The run that agrees sets
        `agreeing`, so that `provide` lists what was stored.  The
        developer is never asked (`T.abfd`).

        Arguments:
        * `wheels` (`Sequence[Path]`):
          The wheels the question is about, for its `?` list.
        * `asking` (`Sequence[str]`):
          The requirements that were asked for.
        * `fresh` (`bool`):
          True when this run downloaded them, so that a no removes them.

        Raises:
        * `Declined`:
          If the person asked says no.
        """
        # Agreed before, or nobody to ask: nothing to do.
        if self.developing():
            return
        program: Path | None = main_path()
        record: Path | None = None
        kept: dict[str, Any] = {}
        if program is not None:
            record, kept = self.development_record(program)
        if kept.get("agreed") or (program is None and not fresh):
            return

        # Control-C before the answer's Enter is a no; after it, the
        # answer stands (Wayne, `ux14`).
        how: str = "Declined"
        try:
            agreed: bool = self.consent(wheels, asking)
        except KeyboardInterrupt:
            agreed = False
            how = "Interrupted"
            print(file=sys.stderr)  # After the `^C`.
        if not agreed:
            name: str = name_of(program_name())
            raise Declined(
                f"declined: nothing was installed into {self.root}",
                f"{how}, so {self.removed()} and {name} did not run."
                if fresh else f"{how}, so {name} did not run.")
        self.agreeing = True
        if record is not None:
            self.keep(record, kept, agreed="yes")

    def note_request(self, request: str) -> None:
        """Remember which cached request a program uses now.

        So that `cull` keeps its packages for as long as the program's
        own `cull-days` says (`stale`), which may be longer than the
        default.  Only the latest is kept: a program whose
        `dependencies` changed lets its old packages go at the default
        age (Wayne, 2026-10-22; S3.3b kept an agreed program's for
        ever).

        Arguments:
        * `request` (`str`):
          The key `request_for` built, as `remember` files it.
        """
        # A developer's program, or an end user's agreed one.
        program: Path | None = main_path()
        if program is None:
            return
        record: Path
        kept: dict[str, Any]
        record, kept = self.development_record(program)
        if not (kept.get("agreed") or self.developing()):
            return
        digest: str = hashlib.sha256(request.encode()).hexdigest()
        if kept.get("requests") != [digest]:
            self.keep(record, kept, requests=[digest])

    def record_approvals(self, wheels: Sequence[Path]) -> None:
        """Keep a developer's approvals and date up to date, silently.

        The approvals live in Part 1 (`[tool.ezpkg] checksums`), one pin
        and `id:` per package, and change only when what arrived does.
        With no `exclude-newer` date (the first run, or an upgrade,
        which deleted it), the date is now, and both go into Part 1 in
        one edit, after which the program starts again (`T.abfd`).  With
        `EDIT_PROGRAM` off they go into the stash instead (`stashing`),
        and nothing starts again.

        Arguments:
        * `wheels` (`Sequence[Path]`):
          Every wheel the program's `dependencies` brought.
        """
        # What Part 1 should say, and whether it does.
        dated: str = self.declared_date()
        resolved: str = dated or time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                               time.gmtime())
        rows: dict[str, str] = {
            wheel_pin(wheel.name): self.digest(wheel)[:ID_DIGITS]
            for wheel in wheels}
        tags: dict[str, str] = {wheel_pin(wheel.name): wheel_tag(wheel.name)
                                for wheel in wheels if wheel_tag(wheel.name)}
        if self.stashing():
            stashed: dict[str, Any] = self.stash()
            if (self.approved() == rows and stashed.get("tags", {}) == tags
                    and dated):
                self.say(3, "ezpkg: approvals unchanged")
                return
            self.put_stash(checksums=rows, tags=tags,
                           **{"exclude-newer": resolved})
            self.say(3, "ezpkg: approvals kept in the stash"
                     + (f", dated {resolved}" if not dated else ""))
            return
        found: tuple[Path, str] | None = main_source()
        changes: list[tuple[str, str, str | None]] = []
        if self.approved() != rows or (
                found is not None and approval_tags(found[1]) != tags):
            changes.append(("ezpkg", "checksums",
                            approvals_array(rows, tags)))
        if not dated:
            changes.append(("uv", "exclude-newer", f'"{resolved}"'))
        if not changes:
            self.say(3, "ezpkg: approvals unchanged")
            return
        trouble: str = self.edit_part1(changes)
        if trouble:
            self.say(1, f"{trouble}; the approvals are not recorded")
            return
        self.say(3, "ezpkg: approvals written into Part 1"
                 + (f", dated {resolved}" if not dated else ""))

    def removed(self) -> str:
        """Take away what a no refuses, and say what that was.

        On a first run the bootstrap's `pip` and `ezpkg` are refused
        too, so the whole cache goes and it never happened, as the
        first question promises (`ux01`); if in doubt, delete, since
        anything deleted is simply fetched again.  Otherwise only the
        new downloads go, which `provide` does as the refusal passes.

        Returns:
        * (`str`): Such as "`~/.ezpkg` has been removed".
        """
        # Only a cache this run's bootstrap filled, never a home.
        if self.newly_filled():
            shutil.rmtree(self.root, ignore_errors=True)
            return f"{self.place()} has been removed"
        return "the new software package(s) have been removed"

    def newly_filled(self) -> bool:
        """Say whether this run's bootstrap filled the cache, a first run.

        Only then does a no take the whole cache away; a cache that was
        already there holds what other programs' end users agreed to,
        which a no to this program must not take from them (Wayne,
        2026-10-19).

        Returns:
        * (`bool`): True on the run whose bootstrap made the cache.
        """
        # Only a cache a bootstrap made, never a home.
        return (self.first_run and self.root != Path.home()
                and ((self.root / "pip.whl").is_file()
                     or (self.root / "ezpkg.whl").is_file()))

    def verify(self, wheels: Sequence[Path]) -> None:
        """Refuse anything the author did not approve.

        Checked after the wheels have arrived and **before** any of them
        is unpacked, which is what makes the refusal meaningful: a wheel
        is an inert zip, so nothing in it has run at the moment it is
        turned away.

        Arguments:
        * `wheels` (`Sequence[Path]`):
          The wheels that arrived.

        A compiled package's `id:` is its author's platform's wheel's
        (its `tag:`), so on another platform only its version is held to
        the approval, since nothing here approved that wheel (S2.4d).

        Raises:
        * `RuntimeError`:
          If a wheel is absent from the approvals, or present with a
          different `id:`.
        """
        # No approvals means nothing to check against.
        expected: dict[str, str] | None = self.approved()
        if expected is None:
            return
        named: dict[str, str] = {normal_pin(pin): identity
                                 for pin, identity in expected.items()}
        found: tuple[Path, str] | None = main_source()
        built: dict[str, str] = {
            normal_pin(pin): tag for pin, tag
            in (approval_tags(found[1]) if found else {}).items()}
        where: str = f"Part 1 of {program_name()}"
        wheel: Path
        for wheel in wheels:
            actual: str = self.digest(wheel)[:ID_DIGITS]
            pin: str = normal_pin(wheel_pin(wheel.name))
            if pin not in named:
                raise Unapproved(
                    f"{wheel.name} is not in the `checksums` of {where}; "
                    f"running the program as its developer brings them up "
                    f"to date", pin)
            if pin in built and built[pin] != wheel_tag(wheel.name):
                self.say(3, f"ezpkg: {wheel.name}: approved for "
                         f"{built[pin]} only, so its version is checked "
                         f"but not its id")
                continue
            if named[pin] != actual:
                raise RuntimeError(
                    f"{wheel.name} does not match its approval in {where}: "
                    f"expected id:{named[pin]}, got id:{actual}")

    def digest(self, wheel: Path) -> str:
        """Return the SHA-256 of a wheel, as hexadecimal.

        The hash is of the file that arrived, not of whatever the index
        claimed, which is the better of the two and the only one
        available: `pip download` does not accept `--report`.  See
        6.3.7 of `T.vcbow`.  This is the identity `T.sawaw` approves,
        and the only thing that can notice a distribution being
        re-uploaded under a version it already used.

        The file is read in blocks, because a wheel with compiled
        extensions can be tens of megabytes.

        Arguments:
        * `wheel` (`Path`):
          Any file, though in practice a wheel.

        Returns:
        * (`str`): Sixty-four hexadecimal characters.
        """
        # Read in blocks rather than whole, because a wheel carrying
        # compiled extensions runs to tens of megabytes.  64 KiB is
        # large enough that the loop is not the cost.
        running: hashlib._Hash = hashlib.sha256()
        opened: IO[bytes]
        block: bytes
        with wheel.open("rb") as opened:
            while block := opened.read(65536):
                running.update(block)
        return running.hexdigest()

    def version_key(self, wheel: Path) -> str:
        """Return the directory name an unpacked wheel belongs in.

        The name carries the interpreter and the platform as well as the
        distribution and version, which is what `I.nicav` is about: the
        same directory reached by a different Python would otherwise
        load a shared object built for something else.  It cannot tell
        musl from glibc, which is the blind spot of `I.wtmifs`.

        Arguments:
        * `wheel` (`Path`):
          A wheel, named as the specification requires:
          `distribution-version-python-abi-platform.whl`.

        Returns:
        * (`str`): The directory name, such as
          `sprocket-1.0.0-cpython-312-linux-x86_64`.
        """
        # The first two fields of a wheel name are what identify it.
        fields: list[str] = wheel.stem.split("-")
        tag: str = sys.implementation.cache_tag or "unknown"
        return (f"{fields[0]}-{fields[1]}-{tag}-"
                f"{sysconfig.get_platform()}")

    def pip(self) -> list[str]:
        """Return the command that runs `pip`, preferring a private copy.

        The bootstrap leaves `pip`'s own wheel in the cache as
        `pip.whl`, and a wheel is a zip that Python can run directly:
        `python pip.whl/pip` is how `pip` documents running itself
        without being installed.  A private copy is preferred whenever
        there is one, so that a machine with no `pip` at all needs
        nothing beyond Python and the pasted bootstrap.

        `refresh_pip` keeps that copy current by adding newer wheels
        beside it under their own names, such as
        `pip-26.3-py3-none-any.whl`, and the most recently added one
        wins.  `pip.whl` itself is never replaced, because a `pip` that
        is running reads itself out of its wheel as it goes, and
        swapping the file under it would break it.

        Without any private copy, which is every bootstrap except the
        one that ships, the interpreter's own `pip` is used, as it
        always was.  If that is missing too, `pip`'s own complaint
        reaches the caller through `download`.

        Returns:
        * (`list[str]`): The interpreter followed by whatever makes it
          run `pip`, ready to have `pip` arguments appended.
        """
        # The newest refreshed copy, then the bootstrap's, then the
        # interpreter's own.
        refreshed: list[Path] = sorted(self.root.glob("pip-*.whl"),
                                       key=lambda one: one.stat().st_mtime)
        if refreshed:
            return [sys.executable, str(refreshed[-1] / "pip")]
        stashed: Path = self.root / "pip.whl"
        if stashed.is_file():
            return [sys.executable, str(stashed / "pip")]
        return [sys.executable, "-m", "pip"]

    def refresh_pip(self, interval: float = PIP_INTERVAL,
                    grace: float = CULL_GRACE) -> Path | None:
        """Add the newest `pip` this Python can run, if it is newer.

        Only a cache the bootstrap gave a private `pip` is refreshed;
        one that uses the interpreter's own leaves that to its owner.
        At most once per `interval`, the current private `pip` is asked
        to download `pip`, and since `pip` passes over releases whose
        `requires_python` the running interpreter does not meet, what
        arrives is the newest it can run.  When that is not the copy
        already in use, it is added beside it, and `pip` takes it from
        then on.  Superseded refreshed copies older than `grace` are
        removed; any younger may still be running somewhere.

        Nothing here is allowed to fail the program it runs in.  A
        missing network, a refusal from the index or a full disk all
        leave the cache as it was, and the next attempt is a whole
        `interval` away, because the stamp is written before trying.
        See issue `I.spinu` in `ISSUES/`.

        Arguments:
        * `interval` (`float`):
          Seconds between attempts.
        * `grace` (`float`):
          Seconds a superseded copy is kept, in case it is in use.

        Returns:
        * (`Path | None`): The wheel added, or `None` when nothing was.
        """
        # Not this cache's business, or not yet time.
        if not ((self.root / "pip.whl").is_file()
                or any(self.root.glob("pip-*.whl"))):
            return None
        stamp: Path = self.root / "last_pip"
        try:
            if stamp.stat().st_mtime >= time.time() - interval:
                return None
        except OSError:
            pass
        stamp.write_text("", encoding="utf-8")

        # Ask the current `pip` for the newest `pip`, into scratch space.
        current: Path = Path(self.pip()[1]).parent
        holding: Path = Path(tempfile.mkdtemp(dir=self.paths()[0]))
        added: Path | None = None
        try:
            done: subprocess.CompletedProcess[str] = subprocess.run(
                [*self.pip(), "download", "pip", "--no-deps", "--retries",
                 "1", "--no-input", "--disable-pip-version-check",
                 "--only-binary", ":all:", "--dest", str(holding)],
                capture_output=True, text=True, check=False)
            fresh: Path | None = next(holding.glob("pip-*.whl"), None)
            if done.returncode == 0 and fresh is not None:
                version: str = fresh.name.split("-")[1]
                with zipfile.ZipFile(current) as running:
                    known: bool = any(
                        name.startswith(f"pip-{version}.dist-info/")
                        for name in running.namelist())
                if not known:
                    added = fresh.replace(self.root / fresh.name)
        except OSError:
            added = None
        finally:
            shutil.rmtree(holding, ignore_errors=True)

        # Superseded refreshed copies go once nothing can be running them.
        old: Path
        for old in self.root.glob("pip-*.whl"):
            try:
                if (old != added and added is not None
                        and old.stat().st_mtime < time.time() - grace):
                    old.unlink()
            except OSError:
                continue
        return added

    def download(self, requirements: Sequence[str],
                 argv: Sequence[str] = (),
                 constraints: Sequence[str] = (),
                 before: str = "") -> list[Path]:
        """Fetch wheels into the holding area without installing them.

        `pip download` is used rather than `pip install`, so that
        nothing is unpacked and nothing runs until the wheels have been
        looked at.  Dependencies come too: the transitive closure is
        exactly what somebody approving the set needs to see, and it is
        the part nobody ever looks at.  `--only-binary :all:` refuses
        source distributions, which would run `setup.py` at install
        time where a wheel does not.

        Each call downloads into a directory of its own under
        `pending`, so that two programs starting at once cannot mix
        their wheels together.

        Arguments:
        * `requirements` (`Sequence[str]`):
          Requirements as `pip` spells them.
        * `argv` (`Sequence[str]`):
          Extra arguments for `pip download`.
        * `constraints` (`Sequence[str]`):
          Versions to keep to, such as `widget==1.2.3`, as `locked`
          returns them.  Empty means none.
        * `before` (`str`):
          Fetch only what was uploaded before this date, as `cutoff`
          returns it.  Empty means no date.  An index that does not
          publish upload times, or a `pip` too old to filter by them,
          fetches without it and says so, rather than failing.

        Returns:
        * (`list[Path]`): The wheels that arrived, in sorted order.

        Raises:
        * `ValueError`:
          If `pip` exits 2, meaning the command line was wrong rather
          than the index.
        * `RuntimeError`:
          If `pip` fails for any other reason, with its standard error
          included.
        """
        # A private `pip` first, if the bootstrap fetched none (`I.ffspo`).
        self.own_pip()

        # A directory per call, so concurrent downloads stay apart.
        pending: Path = self.paths()[0]
        holding: Path = Path(tempfile.mkdtemp(dir=pending))

        # `pip` takes constraints only from a file.  It goes in the
        # holding directory, which is removed with the wheels, and is
        # never mistaken for one, since only `*.whl` is collected.
        lock: list[str] = []
        if constraints:
            listed: Path = holding / "constraints.txt"
            listed.write_text("".join(f"{one}\n" for one in constraints))
            lock = ["--constraint", str(listed)]
        dated: list[str] = ["--uploaded-prior-to", before] if before else []

        # Not `--quiet`, and only one retry, and the two go together.
        # Measured 2026-09-28 against a server with an untrusted
        # certificate: `--quiet` with pip's five retries takes 8.4 s and
        # names the certificate **only in the retry warnings**, while
        # `--quiet --retries 0` takes 0.7 s and reports nothing but
        # `no matching distribution found`, which is a lie about the
        # cause.  Loud takes 0.7 s and names the certificate in the
        # error itself.  Everything pip prints is captured here, so
        # dropping `--quiet` costs the caller no noise at all, and the
        # retries that were buying the diagnosis are no longer needed
        # for it.  One is kept for a genuinely flaky network.  A caller
        # wanting pip's defaults back passes them in `argv`, which wins.
        # See 6.17.7 of `T.ffrp`.
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [*self.pip(), "download", "--retries", "1",
             "--no-input", "--disable-pip-version-check",
             "--only-binary", ":all:", *lock, *dated, *argv,
             "--dest", str(holding),
             *requirements],
            capture_output=True, text=True, check=False)

        # `pip` refuses outright when the index gives no upload times,
        # and an old `pip` does not know the option.  The date is a
        # nicety for a program sent on its own, not a guarantee, so
        # fetch without it rather than fail.  Measured 2026-10-12 with
        # `pip` 26.2.1, which says "does not provide upload-time
        # metadata".
        undated: bool = before != "" and done.returncode != 0 and (
            "does not provide upload-time metadata" in done.stderr
            or "no such option: --uploaded-prior-to" in done.stderr)
        if undated:
            # Said from `medium` up: the approvals still freeze what they
            # record (`T.abfd`).
            shutil.rmtree(holding, ignore_errors=True)
            self.say(2, f"Fetching without the program's "
                     f"exclude-newer date {before}, which this index or "
                     f"pip cannot apply")
            return self.download(requirements, argv, constraints)
        if done.returncode == 2:
            raise ValueError(
                f"pip rejected the command line: "
                f"{done.stderr.strip() or 'pip gave no reason'}")
        # A lock that `dependencies` has moved past fails here, as a
        # conflict `pip` cannot resolve, so say which file to regenerate.
        if done.returncode != 0:
            # On a line of its own, so `failure_reason` keeps `pip`'s
            # `ERROR:` line apart from this guess (`ux` step 2.9).
            stale: str = (
                f"\nIf `dependencies` changed, the versions locked in "
                f"Part 1 of {program_name()} may be the conflict: to "
                f"upgrade them, delete the `exclude-newer` line in Part 1 "
                f"and run the program again." if constraints else "")
            raise RuntimeError(
                f"could not fetch {', '.join(requirements)} into "
                f"{holding}: "
                f"{done.stderr.strip() or 'pip gave no reason'}{stale}")
        return sorted(holding.glob("*.whl"))

    def unpack(self, wheel: Path) -> Path:
        """Unpack one wheel into a directory of its own, and keep it.

        The unpacking happens beside the destination and is renamed
        into place, which is atomic within one filesystem, so a second
        program doing the same thing at the same time cannot see a half
        written tree.  That is the `6.4` concurrency answer as a side
        effect rather than a separate mechanism.

        A wheel's `.data/purelib` and `.data/platlib` contents belong
        beside the modules rather than under a `.data` directory, which
        is the one part of the wheel specification this has to know;
        see 6.3.12 of `T.vcbow`.

        Arguments:
        * `wheel` (`Path`):
          A wheel in the holding area.

        Returns:
        * (`Path`): The directory now holding the unpacked tree, which
          is where it already was if another call got there first.
        """
        # A tree that is already in place is left exactly as it is.
        pending: Path
        wheels: Path
        versions: Path
        pending, wheels, versions, _unused = self.paths()
        target: Path = versions / self.version_key(wheel)
        if target.is_dir():
            return target

        # Unpack inside the holding area rather than beside the
        # destination, so that an incomplete tree is never inside
        # `versions`, which is the directory `contains` and `sys.path`
        # trust.  Both are under `root`, so the rename is still within
        # one filesystem and still atomic.
        staging: Path = Path(tempfile.mkdtemp(dir=pending,
                                              prefix="unpacking-"))
        archive: zipfile.ZipFile
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(staging)

        # `.data/purelib` and `.data/platlib` belong one level up, and
        # the directory they came from is then removed, so that an empty
        # `.data` is not left sitting in an otherwise tidy tree.  A
        # wheel's `scripts`, `headers` or `data` subdirectories are not
        # handled and are deliberately left where they are; see
        # 6.3.12 of `T.vcbow`.
        data: Path
        sub: str
        item: Path
        for data in staging.glob("*.data"):
            for sub in ("purelib", "platlib"):
                if (data / sub).is_dir():
                    for item in (data / sub).iterdir():
                        item.rename(staging / item.name)
                    (data / sub).rmdir()
            if not any(data.iterdir()):
                data.rmdir()
        try:
            staging.rename(target)
        except OSError:
            # Another call won the race, which is the right answer.
            shutil.rmtree(staging, ignore_errors=True)
            return target

        # Keep the artifact, and beside it the hash of what arrived,
        # which is what `T.sawaw` approves.
        kept: Path = wheels / wheel.name
        wheel.rename(kept)
        kept.with_suffix(".sha256").write_text(f"{self.digest(kept)}\n")
        return target

    # What `install` accepts: a requirement as `pip` spells it, or a
    # `(import_name, requirement)` pair for the packages whose two
    # names differ.  The plural form is spelled `list` and `tuple`
    # rather than `Sequence`, because a `str` is itself a
    # `Sequence[str]` and the two overloads below would then overlap.
    Requirement = str | tuple[str, str]
    Requirements = list[Requirement] | tuple[Requirement, ...]

    def bootstrap_status(self) -> tuple[str, str]:
        """Say whether the running program's pasted bootstrap is current.

        Returns:
        * (`tuple[str, str]`): One of `current`, `stale`, `edited` or
          `absent`, and the name of the bootstrap found, which is empty
          unless it is one this project published.
        """
        # No program, or no bootstrap in it, is simply absent.
        found: tuple[Path, str] | None = main_source()
        block: str | None = find_bootstrap(found[1]) if found else None
        if block is None:
            return "absent", ""
        name: str | None = bootstrap_name(block)
        if name is None:
            return "edited", ""
        newest: str = list(BOOTSTRAPS.values())[-1]
        return ("current" if name == newest else "stale"), name

    def chosen(self, entry: str) -> bool:
        """Report whether this `ezpkg` is the one the program asks for.

        It must meet the program's `ezpkg` entry and, when the approvals
        pin `ezpkg`, be that version.  See `T.eui`.

        Arguments:
        * `entry` (`str`):
          The program's `ezpkg` requirement, such as `ezpkg>=0.1,<0.2`.

        Returns:
        * (`bool`): True when this `ezpkg` will do.
        """
        # The entry, then the pin.
        name: str = requirement_name(entry)
        specifier: str = entry[entry.find(name) + len(name):].strip()
        if not meets(__version__, specifier):
            return False
        pinned: str
        for pinned in self.locked():
            if normal_name(requirement_name(pinned)) == "ezpkg":
                return pinned.split("==", 1)[-1] == __version__
        return True

    def providing(self, asked: Sequence[str], own: str | None,
                  switching: bool) -> list[str]:
        """Return what `provide` fetches for the program's `dependencies`.

        Switching, everything, the `ezpkg` entry included.  Otherwise
        this `ezpkg` runs the program and is not fetched, except on a
        developer's run, which fetches exactly this version so that the
        approvals pin it, and so a later run on another machine switches
        to it (`T.eui`).  A copy not installed from a wheel is on no
        index, so it is left out.  An
        export fetches the pinned `ezpkg` too, for a program that
        imports it (`for_export`).

        Arguments:
        * `asked` (`Sequence[str]`):
          The program's `dependencies`.
        * `own` (`str | None`):
          Its `ezpkg` entry, from `own_entry`.
        * `switching` (`bool`):
          True when this `ezpkg` is not the one the program chose.

        Returns:
        * (`list[str]`): The requirements to hand `provide`.
        """
        # The entry is met by this `ezpkg` unless switching.
        if switching or own is None:
            return list(asked)
        others: list[str] = [one for one in asked if one != own]
        if not self.developing():
            return others
        if not from_wheel():
            return others
        return [f"ezpkg=={__version__}", *others]

    def switch(self, trees: Sequence[Path]) -> None:
        """Run the program again with the `ezpkg` it asked for, if not this.

        `provide` has fetched and unpacked the program's `ezpkg` entry
        like any other package, so the tree it returns for `ezpkg` is
        the one the program chose, pinned by its approvals and its
        resolution date.  When that is not this `ezpkg`, the program is
        started again with that tree first on `PYTHONPATH`, so that the
        bootstrap's `import ezpkg` finds it, wherever this one came from
        (Wayne, 2026-10-16; see `T.eui`).  Once only: `EZPKG_SWITCHED`
        marks the second start, and a second switch stops instead.

        Arguments:
        * `trees` (`Sequence[Path]`):
          The version trees `provide` returned.

        Raises:
        * `SystemExit`:
          With the program's own exit status on Windows, or when a
          switch has already been made and did not take.
        """
        # Nothing to do unless an `ezpkg` other than this one arrived.
        tree: Path | None = next(
            (one for one in trees if one.name.split("-")[0] == "ezpkg"),
            None)
        if tree is None or tree.name.split("-")[1] == __version__:
            return
        version: str = tree.name.split("-")[1]
        if "EZPKG_SWITCHED" in os.environ:
            raise SystemExit(
                f"ezpkg: this program asks for ezpkg {version}, but ezpkg "
                f"{__version__} is still running after switching to it "
                f"once, so it stops here.  Is Python running with -I or "
                f"-E, which ignore PYTHONPATH?")

        # Everything said so far is said before the program starts again.
        paths: str = os.environ.get("PYTHONPATH", "")
        run_again(dict(
            os.environ, EZPKG_SWITCHED=version, EZPKG_PYTHONPATH=paths,
            PYTHONPATH=os.pathsep.join(filter(None, [str(tree), paths]))))

    def release_due(self, settings: Settings | None) -> str:
        """Return the version to release now, or empty for none.

        Only a developer's run releases, and only once `exports` names a
        form and `release` names a version: releases are off until the
        developer turns them on (Wayne, 2026-10-21).  Then a release is
        due whenever `release` differs from the newest entry of
        `prog.py.releases`, which is how a developer chooses each
        number, even an older one (Wayne, 2026-10-22).

        Arguments:
        * `settings` (`Settings | None`):
          The developer's settings, or `None` for an end user's run.

        Returns:
        * (`str`): Such as `1.0.1`, or empty.
        """
        # Nothing for an end user, without the program's file, or with
        # releases off.
        program: Path | None = main_path()
        if (settings is None or program is None or not settings.exports
                or not settings.release):
            return ""
        return "" if settings.release == self.released() else settings.release

    def restart(self, after_release: bool = False) -> None:
        """Run the program again after `ezpkg` has changed its file.

        Python compiled the file as it was when the run began, but a
        traceback reads its lines from the file as it is now, so after
        an edit every line number below it would point at the wrong
        line (Wayne, `ux08`, 2026-10-18).  So every edit is followed by
        a fresh start, which reads the edited file and has nothing more
        to ask.  Only the docstring and the bootstrap have run so far;
        anything else above the bootstrap is flagged
        (`statements_above_bootstrap`).  Once only: `EZPKG_RESTARTED`
        marks the second start, and a second edit is only reported;
        except after a release, which cannot come twice, since it has
        recorded its version in `prog.py.releases`.

        Arguments:
        * `after_release` (`bool`):
          The edit was a release's, so start again even a second time.

        Raises:
        * `SystemExit`:
          With the program's own exit status on Windows.
        """
        # A second edit is said, not restarted, so nothing can loop.
        if self.restarted and not after_release:
            print(f"{program_name()} was changed again after "
                  f"starting it again, so a traceback's line numbers may "
                  f"be off until it runs again", file=sys.stderr)
            return
        # The second start is an ordinary run.
        run_again(dict(os.environ, EZPKG_RESTARTED="1"))

    def switched(self) -> None:
        """Put the environment back after `switch` ran the program again.

        The program's own children should see the `PYTHONPATH` it was
        given, not the one `switch` made, and no `EZPKG_SWITCHED`, so
        that one of them may switch in its turn.  See `T.eui`.

        Raises:
        * `SystemExit`:
          If the `ezpkg` running is not the one switched to.
        """
        # Only after a switch.
        version: str | None = os.environ.pop("EZPKG_SWITCHED", None)
        if version is None:
            return
        paths: str = os.environ.pop("EZPKG_PYTHONPATH", "")
        if paths:
            os.environ["PYTHONPATH"] = paths
        else:
            os.environ.pop("PYTHONPATH", None)
        if version != __version__:
            raise SystemExit(
                f"ezpkg: switched to ezpkg {version}, but ezpkg "
                f"{__version__} is running, so it stops here.  Is Python "
                f"running with -I or -E, which ignore PYTHONPATH?")

    def stale_bootstrap(self) -> str:
        """Say that the program carries an older bootstrap, if it does.

        Returns:
        * (`str`): Such as "`prog.py` carries the bootstrap `nopip6`
          (lines 21-54), but `ezpkg` now has `nopip7`.", or empty when it
          is current, absent or (as `refuse_an_edited_bootstrap` says)
          edited.
        """
        # Only a published bootstrap that is not the newest.
        state: str
        name: str
        state, name = self.bootstrap_status()
        found: tuple[Path, str] | None = main_source()
        node: ast.Try | None = bootstrap_node(found[1]) if found else None
        if state != "stale" or found is None or node is None:
            return ""
        newest: str = list(BOOTSTRAPS.values())[-1]
        return (f"`{found[0].name}` carries the bootstrap "
                f"`{name.split()[0]}` (lines {node.lineno}-"
                f"{node.end_lineno or node.lineno}), but `ezpkg` now has "
                f"`{newest.split()[0]}`.")

    def newer_bootstrap(self, settings: Settings) -> None:
        """Tell the developer, once, that a newer bootstrap exists.

        Once per newer bootstrap, per program (its `develop/` record's
        `newest`).  With `bootstrap = "update"` the next release replaces
        it; a program whose developer named its bootstrap hears nothing,
        and one left with the old bootstrap goes on working (`T.abfd`,
        S5.1).

        Arguments:
        * `settings` (`Settings`):
          The developer's settings.
        """
        # Said, then remembered.
        said: str = self.stale_bootstrap()
        program: Path | None = main_path()
        if not said or program is None or settings.bootstrap != "update":
            return
        record: Path
        kept: dict[str, Any]
        record, kept = self.development_record(program)
        newest: str = list(BOOTSTRAPS.values())[-1]
        if kept.get("newest") != newest:
            self.say(1, f"{said}  The next release replaces it.")
            self.keep(record, kept, newest=newest)

    def named_bootstrap(self, settings: Settings) -> None:
        """Stop unless the program carries the bootstrap its developer named.

        `bootstrap = "nopip6"` in `prog.py.toml` keeps exactly that one,
        which takes the developer's explicit effort (Wayne, S5.1).

        Arguments:
        * `settings` (`Settings`):
          The developer's settings.

        Raises:
        * `SystemExit`:
          Saying what the program carries instead.
        """
        # `update` takes whatever is published.
        wanted: str = settings.bootstrap
        if wanted == "update":
            return
        state: str
        name: str
        state, name = self.bootstrap_status()
        if state in ("current", "stale") and name.split()[0] == wanted:
            return
        carries: str = (f"`{name.split()[0]}`" if name else
                        "an edited one" if state == "edited" else "none")
        raise SystemExit(wrapped(
            f"`{settings_path(main_path() or Path('prog.py')).name}` asks "
            f"for the bootstrap `{wanted}`, but `{program_name()}` carries "
            f"{carries}.  Paste in `{wanted}`, or change `bootstrap`.",
            columns(sys.stderr)))

    def replace_bootstrap(self) -> str:
        """Replace an older bootstrap with the current one, in place.

        At a release with `bootstrap = "update"` (Wayne, S5.1): the
        current text (`QUICK_START`'s), indented as the old one was, in
        the lines the old one took.  The encoding and line endings are
        kept.

        Returns:
        * (`str`): What was replaced, for the developer, or empty when
          nothing was.
        """
        # The old one's lines, and the new text indented to match.
        state: str
        name: str
        state, name = self.bootstrap_status()
        where: Path | None = main_path()
        fresh: str | None = find_bootstrap(QUICK_START)
        if state != "stale" or where is None or fresh is None:
            return ""
        text: str
        encoding: str
        crlf: bool
        text, encoding, crlf = self.program_text(where)
        node: ast.Try | None = bootstrap_node(text)
        if node is None:
            return ""
        lines: list[str] = text.splitlines(keepends=True)
        first: int = node.lineno - 1
        last: int = node.end_lineno or node.lineno
        indent: str = lines[first][:len(lines[first])
                                   - len(lines[first].lstrip())]
        lines[first:last] = [textwrap.indent(fresh.rstrip("\n"), indent)
                             + "\n"]
        self.rewrite(where, "".join(lines), encoding, crlf)
        newest: str = list(BOOTSTRAPS.values())[-1].split()[0]
        if self.staging is not None:
            return (f"This release's copies carry the bootstrap `{newest}` "
                    f"in place of `{name.split()[0]}` (lines "
                    f"{first + 1}-{last} of `{where.name}`).")
        return (f"Replaced the bootstrap `{name.split()[0]}` (lines "
                f"{first + 1}-{last} of `{where.name}`) with `{newest}`.")

    def release(self, settings: Settings, asking: list[str],
                providing: Sequence[str], version: str) -> bool:
        """Make a release, when `release_due` says one is due.

        `dependencies` has been reconciled already; then, with
        `bootstrap = "update"`, an older bootstrap is replaced; the
        program's `ezpkg` entry gets the range of this `ezpkg` (S5.1,
        S5.1c); the imports are checked; bare entries get ranges
        (S5.1b); the approvals (kept up to date by every developer run)
        are frozen as they are; each of `exports` is built beside the
        program, named by version (`prog-1.0.0.py`, `prog-1.0.0.pyz`,
        `prog-1.0.0-uv.py`; `release_files`), a `zipapp` that cannot
        carry a compiled package being skipped with a line; an entry is
        added to `prog.py.releases` (`release_entry`); and the last
        release's files are removed, so one set is ever there.  The
        caller then runs the program as usual (Wayne, 2026-10-21,
        2026-10-22).

        A release that fails says why, removes what it built and records
        nothing, so the program still runs, and its next run tries again.

        With `EDIT_PROGRAM` off, every change is made to a staged copy
        of the program (`staged`, `program_text`), never to `prog.py`
        (Wayne, 2026-10-22).

        Arguments:
        * `settings` (`Settings`):
          The developer's settings.
        * `asking` (`list[str]`):
          The program's `dependencies`.
        * `providing` (`Sequence[str]`):
          What `provide` fetched for them, which `build_zipapp` bundles.
        * `version` (`str`):
          The version to release, from `release_due`.

        Returns:
        * (`bool`): Whether the release was made.
        """
        # Made from a staged copy, if Part 1 is not edited.
        program: Path | None = main_path()
        if program is None:
            return False
        try:
            if self.stashing():
                self.staging = self.staged(asking)
            return self.build_release(program, settings, asking,
                                      providing, version)
        except (RuntimeError, OSError) as error:
            self.say(1, f"`{program.name}` {version} was not released: "
                     f"{error}.  `{program.name}` runs as usual, and its "
                     f"next run tries again.")
            return False
        finally:
            self.staging = None

    def build_release(self, program: Path, settings: Settings,
                      asking: list[str], providing: Sequence[str],
                      version: str) -> bool:
        """Do `release`'s work, once its copy is staged.

        Arguments:
        * `program` (`Path`):
          The program.
        * `settings`, `asking`, `providing`, `version`:
          As `release` takes them.

        Returns:
        * (`bool`): Whether the release was made.
        """
        # The bootstrap and the `ezpkg` entry, kept current.
        if settings.bootstrap == "update":
            replaced: str = self.replace_bootstrap()
            if replaced:
                self.say(1, replaced)
        built: list[Path] = []
        try:
            asking = self.range_ezpkg(asking)
            self.check_imports(asking)

            # Ranges, then what `exports` lists, beside the program.
            # Every form takes the pasted bootstrap out or sends it, so a
            # program that uses `ezpkg` some other way builds none.
            asking = self.give_ranges(asking)
            forms: list[str] = sorted(settings.exports,
                                      key=EXPORT_FORMS.index)
            if forms and find_bootstrap(
                    self.program_text(program)[0]) is None:
                self.say(1, f"`{program.name}` has no pasted bootstrap, "
                         f"so its release builds no "
                         f"{and_list(forms, 'or')}.")
                forms = []
            files: list[Path] = release_files(program, version)
            form: str
            for form in forms:
                target: Path = files[EXPORT_FORMS.index(form)]
                try:
                    built.append(self.export(form, providing, target))
                except RuntimeError as error:
                    # A zip cannot carry compiled code; the rest can.
                    if form != "zipapp" or "cannot bundle" not in str(error):
                        raise
                    self.say(1, f"No `{target.name}`: {error}.")

                # The lock `uv` wrote beside the script, if `uv` was there.
                if form == "uv" and files[3].is_file():
                    built.append(files[3])

            # What the entry records: the copy's `dependencies`.
            declared: dict[str, Any] = script_metadata(
                self.program_text(program)[0]) or {}
            shipped: object = declared.get("dependencies", [])
            entry: str = release_entry(
                version, self.declared_date()
                or str(self.stash().get("exclude-newer") or ""),
                [one for one in (shipped if isinstance(shipped, list)
                                 else []) if isinstance(one, str)],
                commit_of(program))
        except (RuntimeError, ValueError, SystemExit, OSError) as error:
            for made in built:
                made.unlink(missing_ok=True)
            self.say(1, f"`{program.name}` {version} was not released: "
                     f"{error}.  `{program.name}` runs as usual, and its "
                     f"next run tries again.")
            return False

        # Recorded at the end of `prog.py.releases`, a heading first in
        # a new file; then the last release's files go, so that one set
        # is ever beside the program.
        record: Path = releases_path(program)
        last: str = self.released()
        with record.open("a", encoding="utf-8") as adding:
            if adding.tell() == 0:
                adding.write(
                    f"# {record.name}: the releases of {program.name}, "
                    f"oldest first, written by ezpkg.\n"
                    f"# Change `release` in {program.name}.toml and run "
                    f"{program.name} to make the next one.\n")
            adding.write(entry)
        if last and last != version:
            for gone in release_files(program, last):
                gone.unlink(missing_ok=True)
        names: list[str] = [f"`{one.name}`" for one in built]
        self.say(1, f"Released `{program.name}` {version}"
                 + (f": {and_list(names)}" if names else "")
                 + f".  To make the next release, change `release` in "
                 f"`{program.name}.toml` (to \"{next_release(version)}\", "
                 f"say) and run `{program.name}`.")
        return True

    def range_ezpkg(self, asking: list[str]) -> list[str]:
        """Give the program's `ezpkg` entry the range of this `ezpkg`.

        At every release (Wayne, S5.1), so that the entry always admits
        the `ezpkg` the release was made with, and nothing much newer
        (`version_range`).  An `ezpkg` run from a source tree is left
        alone (S5.1c): its version is on no index, and its range would
        shut out the `.devN` rehearsals the entry admits.

        Arguments:
        * `asking` (`list[str]`):
          The program's `dependencies`.

        Returns:
        * (`list[str]`): The `dependencies` now.
        """
        # Only an entry that differs, in a block that can be edited.
        own: str | None = own_entry(asking)
        where: Path | None = main_path()
        ranged: str = version_range("ezpkg", __version__)
        if (own is None or own == ranged or where is None
                or not from_wheel()):
            return asking
        entries: list[str] = [ranged if one == own else one
                              for one in asking]
        source: str
        encoding: str
        crlf: bool
        source, encoding, crlf = self.program_text(where)
        edited: str | None = with_dependency_list(source, entries)
        if edited is None:
            raise SystemExit(f"{where.name}: cannot edit its script block "
                             f"to give `{own}` this ezpkg's range")
        self.rewrite(where, edited, encoding, crlf)
        self.say(2, f'Changed "{own}" to "{ranged}" in `{where.name}`\'s '
                 f"`dependencies`.")
        return entries

    def refuse_an_edited_bootstrap(self, bootstrap: str) -> None:
        """Stop the program if the bootstrap that called is not published.

        Called by `install` for a caller that names its bootstrap, which
        every published bootstrap does and nothing else need.  A program
        whose source cannot be read (`python -c`, a frozen program) has
        nothing to compare, and goes on.  `EZPKG_BOOTSTRAP=unchecked`
        skips the check, saying so every time, for this project's own
        `bootstrap.py`, whose copies spell `ezpkg` and the index as
        variables so that its tests can aim them elsewhere.  See `T.reb`.

        Arguments:
        * `bootstrap` (`str`):
          The name the calling bootstrap gave itself, such as `nopip6`.

        Raises:
        * `SystemExit`:
          If the bootstrap has been edited, saying where.
        """
        # Never silently skipped.
        if os.environ.get("EZPKG_BOOTSTRAP", "").lower() == "unchecked":
            print("ezpkg: the bootstrap is not checked "
                  "(EZPKG_BOOTSTRAP=unchecked)", file=sys.stderr)
            return
        found: tuple[Path, str] | None = main_source()
        if found is None:
            return
        refusal: str | None = bootstrap_refusal(found[0], found[1],
                                                bootstrap)
        if refusal is not None:
            raise SystemExit(refusal)

    def install_declared(self, argv: Sequence[str], bootstrap: str) -> None:
        """Provide what the program declared: `install()`'s usual form.

        Arguments:
        * `argv` (`Sequence[str]`):
          Extra arguments for `pip install`, as `install` documents.
        * `bootstrap` (`str`):
          The bootstrap's name, or empty when no bootstrap called.
        """
        # A `restart`'s mark is for this run only, not its children.
        self.restarted = os.environ.pop("EZPKG_RESTARTED", None) is not None
        try:
            self.provide_declared(argv, bootstrap)
        except Declined as declined:
            # One line, not a traceback or the bootstrap's `failed:`
            # line, which would read as a fault; from the first fetch or
            # a `dependencies` update's (`ux16`).
            raise SystemExit(wrapped(declined.said, columns(sys.stderr))
                             ) from None
        except RuntimeError as error:
            # A developer's failed fetch is one line with `pip`'s reason,
            # and its whole output only at `high` (S1.5f).  An end user's
            # is one plain line, `pip`'s text kept for the author
            # (`I.ffspo`).
            if not self.developing():
                raise SystemExit(wrapped(self.end_user_failure(error),
                                         columns(sys.stderr))) from None
            self.say(3, f"ezpkg: {error}", wrap=False)
            raise SystemExit(wrapped(
                f"{name_of(program_name())} did not run: "
                f"{failure_reason(error)}"
                + ("" if self.verbosity() >= 3 else
                   '  (`verbosity = "high"` shows all of pip\'s output.)'),
                columns(sys.stderr))) from None

    def end_user_failure(self, error: BaseException) -> str:
        """Return the one line an end user sees when a fetch fails.

        Never `pip`'s text, which is the author's business: it goes
        into `last_failure.txt` in the cache, which the line names, so
        the end user can send it on (Wayne, 2026-10-17: never put the
        problem on the end user's plate).  The cases are `I.ffspo`'s:
        no network; a pinned version the index no longer has; nothing
        that runs on this machine; a package the author did not approve
        (`Unapproved`); and anything else, with `pip`'s
        `ERROR:` reason, never its warnings.

        Arguments:
        * `error` (`BaseException`):
          What the fetch raised, with `pip`'s output in it.

        Returns:
        * (`str`): The line, unwrapped.
        """
        # Kept for the author, if it can be.
        text: str = str(error)
        name: str = name_of(program_name())
        details: Path = self.root / "last_failure.txt"
        try:
            details.write_text(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} {program_name()}, "
                f"ezpkg {__version__}, Python {sys.version.split()[0]} "
                f"on {sys.platform}\n\n{text}\n", encoding="utf-8")
            kept: str = (f"  (For its author: `{shown(details)}` says "
                         f"what went wrong.)")
        except OSError:
            kept = ""

        # The cases, most likely first.
        if isinstance(error, Unapproved):
            return (f"{name} needs {error.pin.replace('==', ' ')} on this "
                    f"computer, which its author did not approve, so "
                    f"{name} did not run.  Ask its author for its "
                    f"release, and try again.{kept}")
        if NO_NETWORK.search(text):
            return (f"{name} needs software packages from the internet, "
                    f"but the internet could not be reached, so {name} "
                    f"did not run.  Connect, then run it again.")
        pinned: dict[str, str] = {
            normal_name(pin.partition("==")[0]): pin.partition("==")[2]
            for pin in self.approved() or {}}
        package: str
        why: str
        package, why = unavailable(text, pinned)
        if why == "gone":
            return (f"{name} needs {package}, which PyPI "
                    f"(https://pypi.org) no longer offers, so {name} did "
                    f"not run.  Request an updated version of {name} and "
                    f"try again.{kept}")
        if why == "no wheel":
            here: str = (f"Python {sys.version_info[0]}."
                         f"{sys.version_info[1]} on {platform.system()} "
                         f"{platform.machine()}")
            return (f"{name} needs {package}, which has no version for "
                    f"this computer ({here}), so {name} did not run.  "
                    f"Request an updated version of {name} and try "
                    f"again.{kept}")
        return (f"{name} could not get its software packages, so it did "
                f"not run: {failure_reason(error)}{kept}")

    def own_pip(self) -> None:
        """Fetch a private `pip`, as `nopip7` did, if there is none.

        `nopip8` fetches only `ezpkg`, so this is where a stranger's
        `pip` comes from, before anything is asked (`T.abfd`).  And when
        `ezpkg` was already importable (`pip install ezpkg`), no
        bootstrap fetched anything, and the interpreter's own `pip` may
        be old or missing (`I.ffspo`, case 5).  The newest `pip` whose
        `requires_python` floor this Python meets is taken, from the
        index `pip` will use (`json_api`; `I.bfnprp`).  Only for the real
        `~/.ezpkg`: a cache a caller names keeps the interpreter's
        `pip`, as it always has.  Nothing here fails the program; with
        no network, the interpreter's `pip` is tried, and its failure is
        the one reported.
        """
        # Only the cache the bootstrap would have filled, and only once.
        if (self.root != Path.home() / ".ezpkg"
                or (self.root / "pip.whl").is_file()
                or any(self.root.glob("pip-*.whl"))):
            return
        try:
            index: Any = json.loads(fetch_url(json_api("pip")))
            floor: int = sys.version_info[1]
            newest: dict[str, Any] = max(
                (one for files in index["releases"].values() for one in files
                 if one["url"].endswith(".whl") and not one["yanked"]
                 and (needs := one["requires_python"] or "")[:4] == ">=3."
                 and "," not in needs
                 and int(needs.split(".")[1]) <= floor),
                key=lambda one: one["upload_time"])
            body: bytes = fetch_url(newest["url"])
            if hashlib.sha256(body).hexdigest() != newest["digests"]["sha256"]:
                raise ValueError(f"{newest['filename']} fails its SHA-256 "
                                 f"check")
            self.root.mkdir(parents=True, exist_ok=True)
            part: Path = self.root / "pip.part"
            part.write_bytes(body)
            part.replace(self.root / "pip.whl")  # Atomic, as the bootstrap's.
            self.say(3, f"ezpkg: fetched a private pip, {newest['filename']}")
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.say(3, f"ezpkg: no private pip ({error!r}); using "
                     f"{sys.executable}'s own")

    def provide_declared(self, argv: Sequence[str], bootstrap: str) -> None:
        """Do `install_declared`'s work, once its environment is set.

        Arguments:
        * `argv` (`Sequence[str]`):
          Extra arguments for `pip install`, as `install` documents.
        * `bootstrap` (`str`):
          The bootstrap's name, or empty when no bootstrap called.
        """
        declaration: dict[str, Any] = self.declaration()
        self.check_python(declaration)
        asked: list[str] = self.declared()

        # The program's mode, and a misspelt setting, or a bootstrap
        # other than the one named, stops it at once.
        named: Settings | None = self.settings()
        if named is not None:
            self.named_bootstrap(named)

        # The program's own `ezpkg` entry chooses which `ezpkg` runs
        # it.  This one judges the bootstrap only if it is that one;
        # otherwise the one switched to does (`T.eui`).
        own: str | None = own_entry(asked)
        switching: bool = own is not None and not self.chosen(own)
        if bootstrap and not switching:
            self.refuse_an_edited_bootstrap(bootstrap)
        providing: list[str] = self.providing(asked, own, switching)
        self.switch(self.provide(providing, argv))
        if bootstrap and switching:
            # Still here, so no other `ezpkg` came: this one judges.
            self.refuse_an_edited_bootstrap(bootstrap)

        # An ordinary run keeps Part 1 in step with the imports for
        # the program's developer, then warns about every import still
        # uncovered, now that the declared packages can be found.  An
        # end user's program is never edited, and a forgotten package
        # is Python's `ImportError` to report; a developer who turned
        # `auto-dependencies` off hears nothing either (`T.abfd`).
        settings: Settings | None = self.settings()
        if settings is not None and settings.auto_dependencies:
            asked = self.sync_dependencies(asked, argv)
            self.scan_imports(asked)
        self.name_the_additions()

        # A new `release` value builds a release, after which the
        # program runs as usual (`release`).
        version: str = self.release_due(settings)
        if version and settings is not None:
            if self.edited:
                self.restart()
            built: bool = self.release(settings, asked, providing, version)
            if self.edited:
                self.restart(after_release=built)
        if settings is not None:
            self.newer_bootstrap(settings)
        if self.edited:
            self.restart()

        # What the developer's run loads behind the scenes keeps its
        # entries (`reconcile`), so it is noted as the program ends.
        # And a module the program stops for want of gets its package
        # for the next run.
        program: Path | None = main_path()
        if (settings is not None and settings.auto_dependencies
                and program is not None):
            atexit.register(self.note_loaded, program, list(asked))
            if self.stashing():
                self.catch_missing(program)

    def catch_missing(self, program: Path) -> None:
        """Have a developer's program that stops for a module add its package.

        `sys.excepthook` sees an uncaught `ModuleNotFoundError` before
        the traceback is printed, and `add_missing` gets the chance to
        explain it in one line instead.  Only uncaught ones: a library
        that tries an optional module (`try: import ujson`) catches its
        own (Wayne, 2026-10-22).

        Arguments:
        * `program` (`Path`):
          The program.
        """
        # Whatever was there before still prints the rest.
        previous: Any = sys.excepthook

        def hook(kind: type[BaseException], error: BaseException,
                 trace: Any) -> None:
            """Explain a missing module, or pass the error on."""
            if not self.add_missing(program, error, trace):
                previous(kind, error, trace)

        sys.excepthook = hook

    def add_missing(self, program: Path, error: BaseException,
                    trace: Any) -> bool:
        """Add the package of a module a developer's program stopped for.

        A module the program loads without importing it in its source,
        such as `requests`'s `socks` for a SOCKS proxy, or a plugin, is
        found the way an import's package is (`MODULE_PACKAGES`, else
        the module's own name, then `prove`), added to the stash's
        `dependencies`, and said in one line; the developer runs the
        program again.  It is not restarted, since it may already have
        done something (Wayne, 2026-10-22).  A module the source imports
        is `reconcile`'s, and a package already declared, or none to be
        found, leaves the traceback to say the rest.

        Arguments:
        * `program` (`Path`):
          The program.
        * `error` (`BaseException`):
          What stopped it.
        * `trace` (`Any`):
          Its traceback, for who wanted the module.

        Returns:
        * (`bool`): True when the package was added and said.
        """
        # A missing module the source does not import, and no package
        # yet for it.
        if not isinstance(error, ModuleNotFoundError) or not error.name:
            return False
        top: str = error.name.partition(".")[0]
        source: tuple[Path, str] | None = main_source()
        if source is None or self.exempt(program, top):
            return False
        try:
            if top in {module for module, _, _ in every_import(source[1])}:
                return False
            declared: set[str] = {normal_name(requirement_name(entry))
                                  for entry in self.declared()}
        except (SyntaxError, ValueError, TypeError):
            return False
        package: str = MODULE_PACKAGES.get(top, top)
        if normal_name(package) in declared:
            return False
        problem: str = self.prove(package, top)
        if problem:
            self.say(1, f"`{program.name}` stopped for want of `{top}`, "
                     f"and no package for it was added: {problem}.")
            return False

        # Who wanted it: the last frame outside the import machinery.
        wanting: str = program.name
        while trace is not None:
            name: object = trace.tb_frame.f_globals.get("__name__")
            if (isinstance(name, str) and name != "__main__"
                    and not name.startswith("importlib")):
                wanting = name.partition(".")[0]
            elif name == "__main__":
                wanting = program.name
            trace = trace.tb_next
        held: object = self.stash().get("dependencies")
        self.put_stash(dependencies=[
            *(held if isinstance(held, list) else []), package])
        print(wrapped(f"`{wanting}` needed `{top}`, so `ezpkg` added "
                      f"`{package}` to `{program.name}`'s packages; run "
                      f"`{program.name}` again.", columns(sys.stderr)),
              file=sys.stderr)
        return True

    @overload
    def install(self, *, bootstrap: str = "") -> None: ...

    @overload
    def install(self, requirements: str,
                argv: Sequence[str] = ()) -> ModuleType: ...

    @overload
    def install(self, requirements: Requirements,
                argv: Sequence[str] = ()) -> list[ModuleType]: ...

    def install(self, requirements: str | Requirements | None = None,
                argv: Sequence[str] = (), *, bootstrap: str = ""
                ) -> ModuleType | list[ModuleType] | None:
        """Install packages if they are missing, and import them.

        **With no arguments**, the packages are the ones the program
        declared in its PEP 723 block, and nothing is imported: the
        cache goes on `sys.path` and the program's own `import`
        statements, written below the bootstrap, then succeed.  This is
        the form the bootstrap calls and the one `README.md` teaches;
        see 6.7.8 of `T.p7i`.  A program with no block, or a
        block declaring nothing, asks for nothing and gets nothing,
        without complaint.

        Nothing is imported in that form because a PEP 508 requirement
        names a distribution and not a module, and the two differ often
        enough -- `python-dateutil` imports as `dateutil` -- that
        guessing would fail on real programs.  The `import` statement is
        where a module name belongs.

        Whatever is missing is installed into the cache directory with
        `pip install --target`, which needs no virtual environment, and
        the cache directory is put on `sys.path` so that the imports
        succeed.  Anything already in the cache is not fetched again,
        and when every requirement is already importable at a version
        it allows, as under `uv run`, nothing is
        fetched or put on `sys.path` at all; see `satisfied`.  One
        `pip` is run for the whole set rather than one per package, so
        `pip` resolves them together and can notice a conflict that
        installing them separately would hide.

        The name says `install` rather than something friendlier
        because that is what happens: `pip install`, against an index
        anybody can publish to.  See `README.md`.

        `pip` runs as a child process rather than through
        `pip._internal`, which is not a public interface, and which
        leaves its logging handlers on the root logger of whatever
        imports it.

        The program's mode decides what happens to what arrives
        (`gate`).  On its developer's run (a `prog.py.toml`), it is
        recorded in the approvals file beside the program.  Otherwise
        each wheel is checked against that file and a mismatch is
        refused, and a program with no approvals file asks its end user
        once.  The approvals also lock: the versions they record are the
        ones fetched, whatever is newer; see `locked`.

        In the no-argument form, a developer's new `release` value
        builds a release and exits instead of returning, so the
        program's own code never runs; see `release`.  Otherwise the
        developer's `dependencies` are kept in step with the imports;
        see `sync_dependencies`.

        A requirement is spelled the way `pip` spells it, so a version
        constraint needs no special support:
        `install(["coverage", "pytest>=7.0,<8"])`.  The one thing a
        requirement string cannot carry is an import name that differs
        from the distribution name, and a pair supplies that:
        `install([("dateutil", "python-dateutil>=2.8")])`.

        Arguments:
        * `requirements` (`str | Requirements | None`):
          `None`, the default, means whatever the program declared.
          Otherwise one requirement, or several.  Each is either a string that
          `pip` accepts, whose import name is taken to be the name with
          any punctuation turned into underscores, or a
          `(import_name, requirement)` pair for when the two differ.
        * `argv` (`Sequence[str]`):
          Extra arguments for `pip install`, such as `--no-deps` or
          `--only-binary`.  They apply to the whole invocation rather
          than to one requirement, and they follow this method's own
          arguments, so `pip` lets them win where it takes the last of
          a repeated option.
        * `bootstrap` (`str`):
          Which bootstrap the calling program carries, as the pasted code
          names itself -- `"nopip6"` for the one that ships.  Kept on
          the instance as `self.bootstrap` and **read by nothing yet**:
          `T.fbanwiis` wants to notice a pasted bootstrap that has gone
          stale, and telling it which one this is costs the caller no
          line and saves it guessing.  An empty string means the caller
          did not say.

        Returns:
        * (`ModuleType | list[ModuleType] | None`): The imported module
          when `requirements` was a single string, so that
          `cov = v.install("coverage")` reads properly; one module per
          requirement, in the order given, when it was several, so that
          `cov, pt = v.install(["coverage", "pytest"])` does; and
          `None` when it was omitted, since that form imports nothing.

        Raises:
        * `ValueError`:
          If a requirement reads as an option, or repeats another's
          import name, both checked before `pip` runs; or if `pip`
          exits 2, which means the command line was wrong rather than
          the index.  A malformed requirement is `pip`'s to report.
        * `RuntimeError`:
          If `pip` fails.  Its standard error is included, because the
          usual cause is no network and the caller deserves to be told
          that rather than left with an import error.  Also if a module
          asked for is already imported from another version, as by an
          earlier `install` of another version, since this process
          cannot hold both.
        * `ModuleNotFoundError`:
          If `pip` succeeds but a package still will not import, which
          means its import name was guessed wrongly and wants the pair
          form.  The no-argument form imports nothing and so cannot
          raise it.
        """
        # Remembered, though nothing reads it yet; see `T.fbanwiis`.
        self.bootstrap = bootstrap

        # A program run again with the `ezpkg` it asked for puts things
        # back as they were for its own children; see `switch`.
        self.switched()

        # No arguments means whatever the program declared.  The
        # interpreter is checked first, because a program on the wrong
        # Python should be told that rather than handed packages.
        if requirements is None:
            try:
                self.install_declared(argv, bootstrap)
            except KeyboardInterrupt:
                # Control-C at a question, or during a download, is a
                # person saying stop, not a fault (`I.ffspo`).
                raise SystemExit(f"\nInterrupted, so "
                                 f"{name_of(program_name())} stops here."
                                 ) from None
            return None

        # An edited bootstrap stops the program; see `bootstrap_refusal`.
        if bootstrap:
            self.refuse_an_edited_bootstrap(bootstrap)

        # One string is the simple case, and it returns one module.
        single: bool = isinstance(requirements, str)
        wanted: list[str | tuple[str, str]] = (
            [requirements] if isinstance(requirements, str)
            else list(requirements))

        # Split each requirement into the name to import and the string
        # to hand `pip`.  A bare requirement supplies both.
        names: list[str] = []
        asking: list[str] = []
        entry: str | tuple[str, str]
        for entry in wanted:
            if isinstance(entry, tuple):
                names.append(entry[0])
                asking.append(entry[1])
            else:
                names.append(import_name(entry))
                asking.append(entry)

        # Two entries claiming one import name would return a module
        # twice and never mention the other.
        repeated: set[str] = {name for name in names
                              if names.count(name) > 1}
        if repeated:
            raise ValueError("repeated import name: "
                             + ", ".join(sorted(repeated)))

        # Everything up to the imports is the same work either form does.
        trees: list[Path] = self.provide(asking, argv)

        # `sys.modules` is keyed by name, so a module already imported
        # from another version's tree would be handed back in place of
        # the version just asked for, silently.  One process holds one
        # version of a module; say so instead.  See 6.3.11 of `T.vcbow`.
        name: str
        for name in names:
            loaded: ModuleType | None = sys.modules.get(name)
            where: str | None = getattr(loaded, "__file__", None)
            fresh: list[Path] = [
                tree for tree in trees
                if (tree / name).is_dir() or (tree / f"{name}.py").is_file()]
            if where and fresh and not any(
                    Path(where).is_relative_to(tree) for tree in fresh):
                raise RuntimeError(
                    f"{name} is already imported from {where}, so this "
                    f"process cannot also have the version in "
                    f"{fresh[0].name}: one process holds one version of a "
                    f"module")
        modules: list[ModuleType] = [importlib.import_module(name)
                                     for name in names]
        return modules[0] if single else modules

    def declaration(self) -> dict[str, Any]:
        """Return the running program's PEP 723 declaration.

        The block is in the program's source text, which `main_source`
        supplies; see 6.7.2 and 6.7.7 of `T.p7i`.  Two callers
        want it -- `declared` for the packages and `check_python` for the
        interpreter -- and reading it once means they cannot disagree.

        Returns:
        * (`dict[str, Any]`): What the block declared.  Empty when the
          program has no file or no `script` block, which are two ways of
          declaring nothing.

        Raises:
        * `ValueError`:
          Through `script_metadata`, if the block will not parse.
        """
        # No file and no block are both "nothing declared".
        found: tuple[Path, str] | None = main_source()
        if found is None:
            return {}
        return script_metadata(found[1]) or {}

    def check_python(self, declaration: dict[str, Any] | None = None
                     ) -> None:
        """Refuse to go on when the program declared a different Python.

        PEP 723's `requires-python` is written for a tool that chooses an
        interpreter before the program starts, which `uv run` does and we
        cannot: by the time this runs, the program is already running on
        whatever it got.  So this reports rather than prevents, and the
        report is the point -- the alternative is a `SyntaxError` forty
        lines into a module the person has never heard of.

        Only the `>=X.Y` form is judged; see `python_floor`.  Anything
        else is left to `pip` and `uv`, and the divergence that leaves is
        worth naming: a pre-release such as 3.11.0a1 does not satisfy
        `>=3.11` under PEP 440, but its `sys.version_info` compares equal
        here, so an alpha is let through.  Every error this can make is
        in that direction -- failing to refuse, never refusing wrongly --
        which is what makes a whitelist safe here where 6.3.3's tuple
        comparison was not.

        Arguments:
        * `declaration` (`dict[str, Any] | None`):
          What `declaration` returned, when the caller has it already.
          `None` reads it.

        Raises:
        * `RuntimeError`:
          If the running Python is below a floor this understands.  Named
          so that the bootstrap's one line of diagnosis carries it; see
          `T.eoff`.
        * `TypeError`:
          If `requires-python` is present but not a string.
        """
        # Nothing declared is nothing to check.
        found: dict[str, Any] = (self.declaration()
                                 if declaration is None else declaration)
        stated: object = found.get("requires-python")
        if stated is None:
            return
        if not isinstance(stated, str):
            raise TypeError(
                f"PEP 723 `requires-python` must be a string, "
                f"not {stated!r}")

        # An unrecognised specifier gets no opinion, not a guess.
        floor: tuple[int, ...] | None = python_floor(stated)
        if floor is None:
            return
        running: tuple[int, ...] = (sys.version_info.major,
                                    sys.version_info.minor,
                                    sys.version_info.micro)[:len(floor)]
        if running < floor:
            where: Path | None = main_path()
            name: str = where.name if where is not None else "this program"
            raise RuntimeError(
                f"{name} declares requires-python {stated}, but this is "
                f"Python {'.'.join(str(part) for part in running)}")

    def declared(self) -> list[str]:
        """Return the requirements the running program declared.

        Asking this rather than `install()` is how a caller finds out
        what would be fetched without fetching it.

        Returns:
        * (`list[str]`): The requirement strings, in the order declared.
          Empty when the program has no file, no `script` block, or a
          block that declares no dependencies -- three different ways of
          asking for nothing, which all deserve the same silence.

        Raises:
        * `ValueError`:
          If the block is unreadable as PEP 723, which `script_metadata`
          reports.  A declaration that cannot be read is not the same as
          no declaration and must not be mistaken for one.
        * `TypeError`:
          If `dependencies` is not a list of strings.
        """
        # Part 1's own, then, for a developer, the stash's entries for
        # the imports Part 1 does not declare (Part 1's win by name).
        written: list[str] = self.written()
        if not self.stashing():
            return written
        names: set[str] = {normal_name(requirement_name(entry))
                           for entry in written}
        held: object = self.stash().get("dependencies")
        return written + [
            entry for entry in (held if isinstance(held, list) else [])
            if isinstance(entry, str)
            and normal_name(requirement_name(entry)) not in names]

    def written(self) -> list[str]:
        """Return the requirements the developer wrote, never `ezpkg`'s.

        Part 1's own (`part1_entries`), then, for a developer, those of
        `dependencies` in `prog.py.toml` that Part 1 does not name
        (Wayne, 2026-10-22).  Both are kept as written: no entry of
        either is removed, and the imports add only what they lack.

        Returns:
        * (`list[str]`): As `declared` says, but never the stash's.

        Raises:
        * `ValueError`, `TypeError`:
          As `declared` says.
        """
        # Part 1's win by name.
        own: list[str] = self.part1_entries()
        settings: Settings | None = self.settings()
        if settings is None:
            return own
        names: set[str] = {normal_name(requirement_name(entry))
                           for entry in own}
        return own + [entry for entry in settings.dependencies
                      if normal_name(requirement_name(entry)) not in names]

    def part1_entries(self) -> list[str]:
        """Return the requirements Part 1 itself declares.

        Returns:
        * (`list[str]`): As `declared` says, but neither the stash's nor
          `prog.py.toml`'s.

        Raises:
        * `ValueError`, `TypeError`:
          As `declared` says.
        """
        # `requires-python` is `check_python`'s business, not this one's.
        metadata: dict[str, Any] = self.declaration()
        declared: object = metadata.get("dependencies", [])
        if not isinstance(declared, list) or not all(
                isinstance(entry, str) for entry in declared):
            raise TypeError(
                f"PEP 723 `dependencies` must be a list of strings, "
                f"not {declared!r}")
        return list(declared)

    def provide(self, asking: list[str], argv: Sequence[str] = (),
                expect: Mapping[str, str] | None = None) -> list[Path]:
        """Fetch whatever of `asking` is missing, and make it importable.

        The engine both forms of `install` share: it fetches, verifies,
        unpacks and puts the result on `sys.path`, and imports nothing.
        `install` with arguments imports afterwards; `install` with none
        leaves that to the program.

        Arguments:
        * `asking` (`list[str]`):
          Requirement strings as `pip` spells them.  An empty list is
          not an error and does nothing at all, not even a `pip` run.
        * `argv` (`Sequence[str]`):
          Extra arguments for `pip install`, as `install` documents.
        * `expect` (`Mapping[str, str] | None`):
          For packages whose names were guessed, the module each must
          provide, keyed by `normal_name` of the package.  A wheel that
          arrives without its module is refused before anything is
          unpacked; see `sync_dependencies`.

        Returns:
        * (`list[Path]`): The version trees put on `sys.path`, which is
          empty when nothing came from the cache, as when everything was
          already importable.

        Raises:
        * `ValueError`:
          If a requirement reads as an option, or if `pip` exits 2.
        * `RuntimeError`:
          If `pip` fails for any other reason.
        """
        # Nothing asked for is nothing to do, and no `pip` to run.
        if not asking:
            return []

        # Refuse the one thing `pip` would accept and should not: a
        # leading dash reads as an option, so `install("--index-url=")`
        # could aim the fetch at somebody else's index.  Requirement
        # syntax is not checked here, because `pip` owns PEP 508 and
        # rejects a malformed one locally in half a second without
        # touching the network.  See 6.2.4 of `T.spioc`.
        requirement: str
        for requirement in asking:
            if requirement.startswith("-"):
                raise ValueError(
                    f"requirement reads as an option: {requirement!r}")

        # Everything already importable at the right version, as under
        # `uv run` or in a virtual environment, needs nothing from the
        # cache or the network.  All or nothing: fetching only the rest
        # would let `pip` resolve them apart from what is installed, and the
        # cache, which goes first on `sys.path`, could then shadow a
        # shared dependency with a version the installed ones never
        # agreed to.  See `satisfied`.
        if not argv and all(satisfied(one, self.root) for one in asking):
            return []

        # A good moment to sweep: something is about to be fetched, so a
        # little work here is invisible beside a download, and anything
        # this program is about to create is younger than the grace
        # period and so cannot be swept by mistake.  The same reasoning
        # makes it the moment to see whether `pip` has moved on.
        if self.due():
            self.cull()
        self.refresh_pip()

        # A request answered before is answered from the cache, keyed by
        # what was asked rather than by what it resolved to; see
        # 6.3.4 of `T.vcbow`.  No version expression is compared, so no PEP 440
        # parser is needed and none can disagree with `pip`.  The lock
        # is part of what was asked; see `request_for`.
        #
        # Except on a developer's run with no approvals file, or no date
        # (an upgrade), which must fetch to record them.  See `T.rafal`
        # and `T.abfd` in `TASKS/`.
        locked: list[str] = self.locked()
        before: str = self.cutoff()
        request: str = self.request_for(asking)
        writing: bool = self.developing() and not (
            self.approved() and self.declared_date())
        remembered: tuple[list[str], list[str]] | None = (
            None if writing else self.remember(request))

        # What was decided, and why, at `high` (S1.5).
        self.say(3, f"ezpkg: lock: {len(locked)} pin(s) from the approvals"
                 if locked else "ezpkg: lock: none (" + (
                     "no approvals" if not self.approved() else
                     "no exclude-newer date, so resolving afresh") + ")")
        self.say(3, f"ezpkg: date: {before or 'none'}")
        self.say(3, "ezpkg: request remembered, nothing fetched"
                 if remembered is not None else
                 f"ezpkg: fetching {' '.join(asking)}")
        trees: list[Path]
        if remembered is None:
            arrived: list[Path] = self.download(asking, argv, locked,
                                                before)
            holding: Path
            try:
                # Nothing arriving is a real answer, not a failure: every
                # requirement may have been excluded by an environment
                # marker, as `"pywin32; sys_platform == \'win32\'"` is on
                # anything but Windows.  There is then nothing to say and
                # nobody to ask, and asking whether to install no
                # packages is worse than silence.  Measured 2026-09-30,
                # when it printed `1 requested, 0 downloaded`.
                if not arrived:
                    return []

                # A guessed name must prove itself before anything else
                # happens to it: a package that does not contain the
                # module it was guessed for is the wrong package, or a
                # squatter's.  See `T.kdaiis`.
                wheel: Path
                for wheel in arrived:
                    module: str | None = (expect or {}).get(
                        normal_name(wheel.name.split("-")[0]))
                    if module is not None and (
                            module not in wheel_modules(wheel)):
                        raise RuntimeError(
                            f"{wheel.name} does not provide `{module}`, "
                            f"so it is not the package that import wants")

                # Check what turned up against what the author approved,
                # or ask, and only then unpack and say so.  Nothing in a
                # wheel has run at the moment it is refused; see 6.6.
                # Only what is new is asked about and listed: a fetch
                # brings every wheel a request needs, those already
                # unpacked included (`T.abfd`).
                versions: Path = self.paths()[2]
                new: list[Path] = [
                    wheel for wheel in arrived
                    if not (versions / self.version_key(wheel)).is_dir()]
                self.gate(arrived, asking, new)
                # A developer's first run dates the program, which
                # changes the key the next run looks for (`T.abfd`).
                request = self.request_for(asking)

                # Then say what is stored, the bootstrap's own
                # packages too on a first run, once.  Said from the
                # wheels before `unpack` moves them away.
                stored: str = self.listing(new, columns(sys.stderr))
                trees = [self.unpack(wheel) for wheel in arrived]
                # Only on the run that agreed: later downloads are
                # silent, and a developer, who chose them and is never
                # asked, sees the changes to `dependencies` instead
                # (`ux` step 2.7, Wayne, 2026-10-19).
                if (new or self.bootstrapped()) and self.agreeing:
                    print(stored, file=sys.stderr)
                    self.listings += 1
                self.told = True
                self.remember(request, [tree.name for tree in trees],
                              [wheel.name for wheel in arrived])
                self.note_request(request)
            finally:
                # The holding directory has served its purpose once every
                # wheel in it is either kept or already unpacked -- and
                # equally once one has been refused, because a refusal
                # means do not install this, not keep it for later.
                for holding in {wheel.parent for wheel in arrived}:
                    shutil.rmtree(holding, ignore_errors=True)
        else:
            # A warm cache fetches nothing, so there is nothing new to
            # verify.  Verification belongs to the moment of fetching:
            # somebody who can rewrite the cache can rewrite the
            # program too, so that is not the threat this defends
            # against.  But a program never agreed to is asked now,
            # though another program fetched its packages (S2.2).
            trees = [self.paths()[2] / key for key in remembered[0]]
            self.agree([self.paths()[1] / name for name in remembered[1]],
                       asking, False)
            self.note_request(request)

        # Only the unpacked trees go on the path, never the holding
        # area.  That one rule is the whole of the jail; see 6.3.1.
        #
        # `sys.path.insert` puts the tree first, which is the precedence
        # this cache is meant to have, and `site.addsitedir` runs the
        # `.pth` files in it, which `sys.path` alone never does.  Both,
        # because neither suffices: measured 2026-09-28, `addsitedir`
        # appends to the **back** of `sys.path`, and it skips a directory
        # already listed while still processing that directory's `.pth`
        # files, so inserting first and calling it second gets the order
        # we want and the files run.  `setuptools` ships
        # `distutils-precedence.pth` and `pytest-cov` ships
        # `pytest-cov.pth`, and without this both install half working.
        #
        # A `.pth` line beginning with `import` is **executed** here.
        # That is the specification, not a liberty we are taking, and it
        # happens only for a wheel the gate already approved; see
        # `T.pf`.  The guard matters for a second reason
        # now: running the same `.pth` twice in one process would run
        # its import line twice.
        tree: Path
        for tree in trees:
            if str(tree) not in sys.path:
                sys.path.insert(0, str(tree))
                site.addsitedir(str(tree))
        importlib.invalidate_caches()
        return trees

    def litter(self, grace: float = CULL_GRACE) -> list[Path]:
        """Return what is in the cache that nothing can reach.

        Three kinds, none of which needs a policy to identify.  A
        program killed while fetching or unpacking leaves a directory
        under `pending/`, which is staging space and never on the import
        path.  A tree in `versions/` that no request record names is
        unreachable too: `install` finds trees through those records, so
        a tree nothing names will never be found again.  And a wheel in
        `wheels/` that no record names is in the same position.

        A live record protects its wheels.  A record that has aged out
        takes its wheels with it, which is what stops `wheels/` being
        the one directory that grows for ever.

        Both wait out `grace` first, and that is about concurrency, not
        tidiness: another program's download is sitting in `pending/`
        right now, and a tree is renamed into `versions/` a moment
        before the record naming it is written.  Anything young may
        belong to somebody still running.

        Arguments:
        * `grace` (`float`):
          How many seconds old a thing must be to count.  Tests pass a
          small number; a test wanting the boundary passes a large one.

        Returns:
        * (`list[Path]`): Paths that can be removed, sorted, without
          removing them.  Deciding is kept separate from deleting so that
          a caller -- or a test -- can look without acting.
        """
        # Which trees are still spoken for?
        pending: Path
        versions: Path
        requests: Path
        kept: Path
        pending, kept, versions, requests = self.paths()
        spoken: set[str] = set()
        record: Path
        key: str
        for record in requests.glob("*.json"):
            try:
                known: object = json.loads(record.read_text())
            except (OSError, ValueError):
                continue
            if not isinstance(known, dict):
                continue
            for key in ("trees", "wheels"):
                named: object = known.get(key)
                if isinstance(named, list):
                    spoken.update(str(one) for one in named)

        # Anything old enough, in staging or unspoken for.
        cutoff: float = time.time() - grace
        found: list[Path] = []
        entry: Path
        for entry in (list(pending.iterdir()) + list(versions.iterdir())
                      + list(kept.iterdir())):
            if entry.parent != pending and entry.name in spoken:
                continue
            try:
                if entry.stat().st_mtime < cutoff:
                    found.append(entry)
            except OSError:
                continue
        return sorted(found)

    def stale(self, days: float = CULL_DAYS) -> list[Path]:
        """Return the records nothing has used for a long time.

        A record's modification time is when its request was last
        answered, because `remember` touches it on every hit, warm or
        cold.  So age here means *unused*, not merely *old*, which is the
        distinction that matters: a package fetched two years ago and
        used this morning is not stale.

        Scan records in `scans/` age the same way, since `scan_imports`
        touches them too, and nothing else names them; so do the
        records in `develop/`, which `development_record` touches on
        every run, except that the record of a program that still exists
        never goes: it holds the end user's yes (`agreed`), asked once
        and never again, and the developer's `stash`.  A program deleted
        (or moved, or on a drive that is not there) lets its record go
        once it has been unused for its time.  The latest request a
        program uses (`note_request`) is kept as long as that program's
        own `cull-days` says (`cull_seconds`), if that is longer; every
        other age is `days` (Wayne, 2026-10-22).

        Nothing else is aged.  Trees are kept or dropped by whether a
        record still names them, so removing a record is what makes its
        packages collectable, and `litter` does the rest.  One rule each,
        rather than two overlapping ones.

        Arguments:
        * `days` (`float`):
          Seconds of disuse before a record counts as stale, unless a
          program's `cull-days` says otherwise.  Named for the unit a
          person thinks in; `CULL_DAYS` does the arithmetic.

        Returns:
        * (`list[Path]`): The records, sorted, removed by nobody.
        """
        # Each program's record: kept while the program exists, and
        # its latest request kept for the program's own time.
        now: float = time.time()
        allowed: dict[str, float] = {}
        found: list[Path] = []
        record: Path
        for record in sorted((self.root / "develop").glob("*.json")):
            try:
                kept: object = json.loads(record.read_text())
                used: float = record.stat().st_mtime
            except (OSError, ValueError):
                continue
            if not isinstance(kept, dict):
                continue
            program: Path = Path(str(kept.get("program", "")))
            alive: bool = program.is_file()
            seconds: float = cull_seconds(program, days) if alive else days
            if not alive and used < now - seconds:
                found.append(record)
                continue
            digest: object
            for digest in kept.get("requests", []) or []:
                allowed[str(digest)] = max(allowed.get(str(digest), days),
                                           seconds)

        # Requests and scans, by their own last use.  An unreadable one
        # is `litter`'s business, not this one's.
        for record in [*self.paths()[3].glob("*.json"),
                       *(self.root / "scans").glob("*.json")]:
            try:
                if record.stat().st_mtime < now - allowed.get(record.stem,
                                                              days):
                    found.append(record)
            except OSError:
                continue
        return sorted(found)

    def due(self, interval: float = CULL_INTERVAL) -> bool:
        """Say whether the cache is due for a sweep.

        A stamp file records when the last one happened, so that a
        machine running a hundred programs an hour sweeps once rather
        than a hundred times.  An absent stamp means it has never been
        swept, which is due.

        Arguments:
        * `interval` (`float`):
          Seconds between sweeps.

        Returns:
        * (`bool`): True when a sweep is due.
        """
        # An unreadable stamp is treated as absent, not as an error.
        try:
            return (self.root / "last_cull").stat().st_mtime < (
                time.time() - interval)
        except OSError:
            return True

    def cull(self, grace: float = CULL_GRACE,
             days: float = CULL_DAYS) -> list[Path]:
        """Sweep the cache: stale requests first, then anything unreachable.

        The order is what makes the two halves one mechanism.  A stale
        record is removed, which leaves the trees and wheels it named
        spoken for by nobody, and the same sweep then collects them as
        litter.  So *unused* is expressed once, about records, and
        *unreachable* is expressed once, about everything else.

        Arguments:
        * `grace` (`float`):
          Passed to `litter`.
        * `days` (`float`):
          Passed to `stale`.

        Returns:
        * (`list[Path]`): What was removed.  A path that has gone by
          itself -- another program swept first -- is not an error and is
          not reported, because the point is what the cache no longer
          holds, not who removed it.
        """
        removed: list[Path] = []
        record: Path
        for record in self.stale(days):
            try:
                record.unlink()
            except OSError:
                continue
            removed.append(record)

        # A kept wheel is a file; everything else here is a directory.
        entry: Path
        for entry in self.litter(grace):
            try:
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
            except OSError:
                continue
            removed.append(entry)

        # Stamp it even when nothing was found, so that an empty cache is
        # not swept again a second later.
        (self.root / "last_cull").write_text("", encoding="utf-8")
        return removed

    def remember(self, request: str, trees: list[str] | None = None,
                 wheels: list[str] | None = None
                 ) -> tuple[list[str], list[str]] | None:
        """Read or write what a request resolved to last time.

        One small file per request, named by the hash of the request, so
        that two programs recording different requests never touch the
        same path.  A single shared file would be read, modified and
        written, and two overlapping writers would lose one of the two
        entries; measured 2026-09-26, they do.

        Writing goes to a temporary file and is moved into place with
        `replace`, so a reader sees the old record or the new one and
        never a partial one.  Two writers recording the *same* request
        may legitimately disagree, if the index gained a release between
        them; one wins, both trees exist, and the loser's becomes
        garbage for `T.gc` to cull.

        The request is stored inside the file as well as hashed into its
        name, so that a record can be read by a person and so that a
        hash collision cannot be mistaken for a hit.  A remembered
        request whose trees have since been deleted counts as a miss,
        because the cache is meant to be safe to delete.

        Arguments:
        * `request` (`str`):
          The key `request_for` builds.
        * `trees` (`list[str] | None`):
          The version directory names to record.  `None`, the default,
          reads instead of writing.
        * `wheels` (`list[str] | None`):
          The wheel filenames those trees came from, recorded so that
          `export` can check them against the approvals.

        Returns:
        * (`tuple[list[str], list[str]] | None`): The trees and the
          wheels the request resolved to, or `None` when it is unknown,
          when its trees are gone, or when this call was a write.
        """
        # The file name is the hash; the request itself is inside it.
        requests: Path = self.paths()[3]
        digest: str = hashlib.sha256(request.encode()).hexdigest()
        record: Path = requests / f"{digest}.json"

        # Writing: a temporary file moved into place cannot be seen
        # half written, and cannot lose anybody else's record.
        handle: int
        temporary: str
        if trees is not None:
            handle, temporary = tempfile.mkstemp(dir=requests)
            with os.fdopen(handle, "w") as opened:
                json.dump({"request": request, "trees": trees,
                           "wheels": wheels or []}, opened,
                          indent=1, sort_keys=True)
            Path(temporary).replace(record)
            return None

        # Reading: an absent or unreadable record means nothing is known.
        known: dict[str, object]
        try:
            known = json.loads(record.read_text())
        except (OSError, ValueError):
            return None

        # Reading a record is using it, and being used is what keeps a
        # package in the cache; see `stale`.  Touched before the checks
        # below, because a record naming a tree somebody deleted by hand
        # is still evidence that this request was wanted today.
        try:
            record.touch()
        except OSError:
            pass

        # A record counts only if it is this request and its trees are
        # all still there.
        found: object = known.get("trees")
        came: object = known.get("wheels", [])
        versions: Path = self.paths()[2]
        if known.get("request") != request or not isinstance(found, list):
            return None
        if not all(isinstance(key, str) and (versions / key).is_dir()
                   for key in found):
            return None
        return ([str(key) for key in found],
                [str(one) for one in came] if isinstance(came, list) else [])
