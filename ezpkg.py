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
# ever (`I.owenabd`).
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

# How long a request may go unanswered before the cache stops keeping the
# packages that answered it.  Six months, because the cost of being wrong
# is one download and the cost of being right is a little disk, and those
# are not symmetrical.  See `T.gc`.
CULL_DAYS: float = 180.0 * 86400.0

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

# Part 2: EZPkg required imports are immediately below.
import hashlib
import importlib
import json
import pathlib
import subprocess
import sys
import urllib.request as req

# All other imports are added after the EZPkg bootstrap.

# Part 3: The EZPkg bootstrap.  Never edit it.
try:  # Do not edit try block!  See https://pypi.org/project/ezpkg/
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
    raise SystemExit(f"ezpkg: {s} failed: {x!r}")  # Do not edit try block!

# Part 4: Your imports, all after the bootstrap.
import cowsay  # type: ignore[import-not-found]  # For mypy.

# Part 5: The program itself.
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


def removal_command(root: Path) -> str:
    """Return the command that runs a cache's `remove.py`.

    Arguments:
    * `root` (`Path`):
      The cache.

    Returns:
    * (`str`): Such as `python3 ~/.ezpkg/remove.py`; on Windows, whose
      Python is started as `py`, the full path.
    """
    return (f"py {shown(root / 'remove.py')}" if os.name == "nt"
            else f"python3 {shown(root / 'remove.py')}")


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
    # Beside the package directory, or beside a lone module.
    here: Path = Path(__file__).resolve().parent
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
            "it; run once with EZPKG_APPROVE=write, using an ezpkg "
            "installed from a wheel")
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
      How long to wait; `ANSWER_SECONDS` if not given.

    Returns:
    * (`str`): The line, with its newline, or empty.
    """
    # Something that is not a terminal, such as a test's string, is read
    # at once.
    limit: float = ANSWER_SECONDS if seconds is None else seconds
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
    writer.write(f"\nNo answer in {limit / 60:g} minutes, so: no.\n")
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
      with its quotes, or `true`; `None` removes the key.
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
        lines += ["", f"[tool.{table}]", setting]
    elif header is not None:
        end: int = next((index for index in range(header + 1, len(lines))
                         if lines[index].lstrip().startswith("[")),
                        len(lines))
        existing: int | None = next(
            (index for index in range(header + 1, end)
             if re.match(rf"\s*{re.escape(key)}\s*=", lines[index])), None)
        if value is None:
            if existing is not None:
                del lines[existing]
        elif existing is None:
            lines.insert(header + 1, setting)
        else:
            lines[existing] = setting

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


def with_dependency_list(text: str, entries: Sequence[str]) -> str | None:
    """Return a program's text with Part 1's `dependencies` replaced.

    An array written on one line stays on one line while it fits in 79
    columns; otherwise it is written one entry per line, as
    `pin_dependencies` writes it.  A block with no `dependencies` gets
    one above its first table, since a key after a table header would
    belong to that table.  Everything else in the block, and outside
    it, stays as written.  See `T.kdaiis`.

    Arguments:
    * `text` (`str`):
      The program's source.
    * `entries` (`Sequence[str]`):
      The requirement strings, in order.

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

    # Replaced where it is, or added above the first table.
    span: tuple[int, int] | None = dependencies_span(toml)
    if span is not None:
        array: str = (
            one_line
            if "\n" not in toml[span[0]:span[1]] and len(one_line) <= 77
            else "dependencies = [\n"
            + "".join(f'  "{entry}",\n' for entry in entries) + "]")
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
    TYPE_CHECKING:` -- are included, marked optional: such an import
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
YES_NO: dict[str, str] = {"y": "yes", "yes": "yes", "n": "no", "no": "no"}


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
    "serial": "pyserial",
    "skimage": "scikit-image",
    "sklearn": "scikit-learn",
    "usb": "pyusb",
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
    """Return the approved wheels a `uv` lock disagrees with.

    `uv` resolves for itself, so its lock is checked against the
    approvals: each approved wheel must be listed, by file name, with
    the same SHA-256.  Wheels for other platforms are listed too and
    are not checked, since nothing here has approved them.

    Arguments:
    * `lock` (`dict[str, Any]`):
      A `prog.py.lock`, as `tomllib` reads it.
    * `approved` (`dict[str, str]`):
      Wheel names to digests, as `approved` returns them.

    Returns:
    * (`list[str]`): One line per wheel missing or different, sorted;
      empty when the lock agrees.
    """
    # Every wheel the lock lists, by the last part of its URL or path.
    listed: dict[str, str] = {}
    package: dict[str, Any]
    for package in lock.get("package", []):
        wheel: dict[str, Any]
        for wheel in package.get("wheels", []):
            where: str = wheel.get("url") or wheel.get("path") or ""
            listed[where.rsplit("/", 1)[-1]] = str(wheel.get("hash", ""))
    problems: list[str] = []
    name: str
    digest: str
    for name, digest in sorted(approved.items()):
        if name not in listed:
            problems.append(f"{name}: not in the lock")
        elif not listed[name]:
            problems.append(f"{name}: lock has no hash")
        elif listed[name] != f"sha256:{digest}":
            problems.append(f"{name}: lock has {listed[name]}")
    return problems


def find_uv() -> str | None:
    """Return the `uv` command, or `None` when it is not installed.

    The `PATH` first, then `~/.local/bin`, which is where `uv`'s own
    installer puts it and which is not always on the `PATH`.

    Returns:
    * (`str | None`): The command to run.
    """
    # `shutil.which` also checks that the file is executable.
    return (shutil.which("uv")
            or shutil.which("uv", path=str(Path.home() / ".local" / "bin")))


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


def unimported(text: str) -> list[str]:
    """Return the packages a program keeps though nothing imports them.

    Listed in Part 1 as `[tool.ezpkg] unimported = [...]`, which the
    `k` answer writes: a plugin that another package loads for itself,
    say.  See `T.kdaiis`.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`list[str]`): The names, or an empty list for none or a block
      that cannot be read.
    """
    # Anything malformed is simply nothing kept.
    try:
        metadata: dict[str, Any] | None = script_metadata(text)
    except ValueError:
        return []
    tool: object = (metadata or {}).get("tool", {})
    table: object = tool.get("ezpkg", {}) if isinstance(tool, dict) else {}
    kept: object = (table.get("unimported", [])
                    if isinstance(table, dict) else [])
    return ([one for one in kept if isinstance(one, str)]
            if isinstance(kept, list) else [])


def dependency_fingerprint(text: str, entries: Sequence[str],
                           approved: Collection[str]) -> str:
    """Return a short fingerprint of what decides a program's target.

    Its imports in order (optional or not), its `dependencies`, what it
    keeps unimported and what its approvals cover: when none of these
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
        "unimported": unimported(text),
        "approved": sorted(approved),
        "ezpkg": __version__})
    return hashlib.sha256(key.encode()).hexdigest()[:8]


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


def importable(module: str) -> bool:
    """Say whether a top-level module can be imported here, without importing it.

    Arguments:
    * `module` (`str`):
      A top-level module name.

    Returns:
    * (`bool`): True when this Python can find it.
    """
    # A broken finder counts as not found.
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def and_list(words: Sequence[str]) -> str:
    """Return words joined the way a sentence lists them.

    Arguments:
    * `words` (`Sequence[str]`):
      The words, in order.

    Returns:
    * (`str`): Such as `a`, `a and b` or `a, b and c`.
    """
    # The last two joined by "and".
    return (", ".join(words[:-1]) + " and " + words[-1] if len(words) > 1
            else "".join(words))


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


def inserted(before: str, after: str, marker: str,
             script: bool) -> list[tuple[int | None, str, str]]:
    """Return the lines `after` has that `before` lacks, for a display.

    Arguments:
    * `before`, `after` (`str`):
      A program before and after one kind of change.
    * `marker` (`str`):
      What to mark each new line with, such as `mypy`.
    * `script` (`bool`):
      True for lines of the script block, shown without their `# `,
      and with any line they replace shown as removed; otherwise a line
      is shown stripped, and only as it is now.

    Returns:
    * (`list[tuple[int | None, str, str]]`): Each line's number in
      `after` (`None` for a removed one), marker and text.
    """
    # Line by line, in the order they come.  A script block change is
    # one block (`with_unimported` writes one table), found between the
    # lines that are the same at both ends: matched line by line, its
    # own `]` could pair with the `]` of `dependencies` above it and be
    # shown as the wrong line (`ux03`, 2026-10-18).
    old: list[str] = before.splitlines()
    new: list[str] = after.splitlines()
    rows: list[tuple[int | None, str, str]] = []
    opcodes: list[tuple[str, int, int, int, int]]
    if script:
        same: int = 0
        while (same < min(len(old), len(new))
               and old[same] == new[same]):
            same += 1
        tail: int = 0
        while (tail < min(len(old), len(new)) - same
               and old[-1 - tail] == new[-1 - tail]):
            tail += 1
        opcodes = [("replace", same, len(old) - tail, same,
                    len(new) - tail)]
    else:
        opcodes = difflib.SequenceMatcher(
            None, old, new, autojunk=False).get_opcodes()
    operation: str
    first: int
    last: int
    start: int
    end: int
    for operation, first, last, start, end in opcodes:
        if operation == "equal":
            continue
        if script:
            rows += [(None, "remove", script_text(line))
                     for line in old[first:last]]
        rows += [(index + 1, marker,
                  script_text(new[index]) if script else new[index].strip())
                 for index in range(start, end)]
    return rows


@dataclasses.dataclass
class Discrepancy:
    """How a program's `dependencies` differ from what its imports imply.

    The target is the `dependencies` the imports imply: each imported
    module's package, in the order of each module's first import.  An
    entry no import explains -- one kept as `unimported`, or one whose
    modules are unknown here, such as `pywin32` on Linux -- keeps its
    place after the same neighbour.  Built by `EZPkg.discrepancy`.  See
    `T.kdaiis` in `TASKS/`.

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
        # Either kind of difference.
        return self.target() != self.entries or self.uncommented is not None

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

    def target(self) -> list[str]:
        """Return the `dependencies` with every change made.

        Returns:
        * (`list[str]`): The target.
        """
        # Everything added, everything unexplained removed.
        return self.arrange({package for _, _, package in self.additions},
                            self.removals)

    def stopping(self, missing: Sequence[tuple[int, str, str]],
                 asking: bool, width: int = LINE_WIDTH) -> str:
        """Say where the program will stop, whose mistake it is, and the fix.

        For an end-user, whom a missing package stops on every run
        (Wayne, 2026-10-18): someone who edited the author's program
        without knowing `ezpkg` must not be left blaming it.

        Arguments:
        * `missing` (`Sequence[tuple[int, str, str]]`):
          The additions whose modules cannot be imported here.
        * `asking` (`bool`):
          True on a terminal, where answering `y` next time is a fix.
        * `width` (`int`):
          The width to wrap to.

        Returns:
        * (`str`): The paragraph, ending with a newline.
        """
        # One import or several, then the fixes.
        name: str = f"`{self.program.name}`"
        lines: list[int] = [line for line, _, _ in missing]
        modules: list[str] = [f"`{module}`" for _, module, _ in missing]
        packages: list[str] = [f'"{package}"' for _, _, package in missing]
        declared: list[int] = [line for line in self.lines if line]
        where: str = f" ({line_list(declared)})" if declared else ""
        one: bool = len(lines) == 1
        text: str = (
            f"{line_list(lines).capitalize()} of {name} "
            f"{'imports' if one else 'import'} {and_list(modules)}, but "
            f"its `dependencies`{where} do not list "
            f"{'it' if one else 'them'}, so {name} will stop "
            f"{'there' if one else f'at line {lines[0]}'}.  This is a "
            f"mistake in {name}, not in Python or `ezpkg`.  To fix it, add "
            f"{and_list(packages)} to the `dependencies` list near the top "
            f"of {name}{where}"
            f"{f', or run {name} again and answer `y`' if asking else ''}.")
        return wrapped(text, width) + "\n"

    def summary(self) -> str:
        """Return the line that says where the two disagree.

        Returns:
        * (`str`): Such as `EZPkg: prog.py: its dependencies (lines
          5-6) and its imports (lines 14-15) disagree.`, wrapped.
        """
        # Moved entries count on both sides, as well as the changes.
        target: list[str] = self.target()
        moved: set[int] = set()
        operation: str
        first: int
        last: int
        for operation, first, last, _, _ in difflib.SequenceMatcher(
                None, self.entries, target).get_opcodes():
            if operation in ("replace", "delete"):
                moved |= {index for index in range(first, last)
                          if self.entries[index] in target}
        declared: list[int] = [self.lines[index]
                               for index in (*self.removals, *moved)]
        imported: list[int] = [line for line, _, _ in self.additions]
        if self.uncommented is not None:
            imported.append(self.uncommented)
        imported += [self.placed_by[index] for index in moved
                     if index in self.placed_by]
        sides: str = (f"its `dependencies`"
                      f"{f' ({line_list(declared)})' if declared else ''} "
                      f"and its imports"
                      f"{f' ({line_list(imported)})' if imported else ''}")
        return textwrap.fill(f"EZPkg: {self.program.name}: {sides} "
                             f"disagree.", 76)

    def needing(self, count: int, end: str = ".") -> str:
        """Return the line that says how many entries need updating.

        For `reconcile`'s one question about several changes (Wayne,
        2026-10-17).

        Arguments:
        * `count` (`int`):
          How many entries would change (`updating`).
        * `end` (`str`):
          `:` when the changes are listed after it (`ux/ux04_Batch_y.txt`).

        Returns:
        * (`str`): Such as `` `prog.py` has 3 entries in `dependencies`
          (line 5) that need to be updated. ``, wrapped.
        """
        # Where `dependencies` is, when its entries say.
        lines: list[int] = [line for line in self.lines if line]
        where: str = f" ({line_list(lines)})" if lines else ""
        also: str = (f", and its import of `ezpkg` (line {self.uncommented}) "
                     f"needs the mypy comment" if self.uncommented is not None
                     else "")
        entries: str = ("1 entry" if count == 1 else f"{count} entries")
        need: str = "needs" if count == 1 else "need"
        return wrapped(f"`{self.program.name}` has {entries} in "
                       f"`dependencies`{where} that {need} to be "
                       f"updated{also}{end}", LINE_WIDTH)

    def display(self, final: Sequence[str], source: str, listed: str,
                kept: str, edited: str, made: bool, heading: str = ""
                ) -> str:
        """Return every change to the program, line by line.

        Wayne's layout (`ux/ux02_Batch_y.txt`, `ux03`): each line's
        number in the file afterwards (blank for a removed line), a
        marker (`add`, `remove`, `move`, `mypy`, or none for an anchor)
        and the line's text, script block lines without their `# `.
        The `dependencies` changes come with the nearest unchanged entry
        or bracket above and below as anchors, unless the array is on
        one line, which is then shown before and after; the
        `[tool.ezpkg]` lines of a `k` and the imports given a `mypy`
        comment come alone.

        Arguments:
        * `final` (`Sequence[str]`):
          The `dependencies` afterwards.
        * `source` (`str`):
          The program as it is.
        * `listed` (`str`):
          The program with only `dependencies` changed.
        * `kept` (`str`):
          That, with `[tool.ezpkg] unimported` changed as well.
        * `edited` (`str`):
          That, with the `mypy` comments added: the whole edit.
        * `made` (`bool`):
          True when the changes are being made without asking, so the
          heading says "made" rather than "to be made".
        * `heading` (`str`):
          Another heading, such as `needing`'s line before `Update
          them?`.

        Returns:
        * (`str`): The heading and lines, ending with a newline.
        """
        # Each entry's line afterwards, and the brackets' lines around
        # them.
        after: list[str] = edited.splitlines()
        where: list[int] = dependency_lines(edited) or []
        named: bool = len(where) == len(final)

        def bracket(entry: str) -> int | None:
            """Return the line of the array's `[` or `]`."""
            # Out from the entries, or the `dependencies` line itself.
            if not where:
                return next((index + 1 for index, line in enumerate(after)
                             if "dependencies" in line), None)
            if entry == "[":
                return next((index + 1 for index in
                             range(where[0] - 1, -1, -1)
                             if "[" in after[index]), None)
            return next((index + 1 for index in
                         range(where[-1] - 1, len(after))
                         if "]" in after[index]), None)

        rows: list[tuple[int | None, str, str]] = []
        label: str
        entry: str
        for label, entry in ([] if len(set(where)) < len(where) else
                             self.rows(final, ())):
            marker: str = label.split(" ")[0]
            if marker not in ("add", "remove", "move"):
                marker = ""
            number: int | None = None
            text: str = entry
            if marker == "remove":
                pass
            elif entry in ("[", "]"):
                number = bracket(entry)
                if number is not None:
                    text = script_text(after[number - 1])
            elif named and entry[1:-2] in final:
                number = where[list(final).index(entry[1:-2])]
            rows.append((number, marker, text))
        if len(set(where)) < len(where):
            rows += inserted(source, listed, "add", True)
        rows += inserted(listed, kept, "add", True)
        rows += inserted(kept, edited, "mypy", False)

        # Colon-aligned numbers, then the marker column.
        width: int = len(str(max((one for one, _, _ in rows if one),
                                 default=0)))
        heading = heading or (f"Changes {'made' if made else 'to be made'} "
                              f"to `{self.program.name}`:")
        return "\n".join(
            [heading]
            + [f"{'' if number is None else number:>{width}}:    "
               f"{marker:<7}{text}".rstrip()
               for number, marker, text in rows]) + "\n"

    def updating(self, final: Sequence[str]) -> int:
        """Count the entries that `final` adds, removes or moves.

        Arguments:
        * `final` (`Sequence[str]`):
          The `dependencies` afterwards.

        Returns:
        * (`int`): How many rows of `display` are not anchors.
        """
        # The labels `rows` gives a change.
        return sum(1 for label, _ in self.rows(final, ())
                   if label.split(" ")[0] in ("add", "remove", "move"))

    def reported(self, final: Sequence[str], before: str, edited: str,
                 modules: Mapping[str, str]) -> list[str]:
        """Return a line for each change Auto mode made, in line order.

        Nothing was shown before an Auto mode edit, so each entry added,
        removed or moved is named, with its line afterwards, and the
        `mypy` comment an added entry's import was given (Wayne,
        `ux11`).

        Arguments:
        * `final` (`Sequence[str]`):
          The `dependencies` afterwards.
        * `before`, `edited` (`str`):
          The program before and after the `mypy` comments, which add
          no lines.
        * `modules` (`Mapping[str, str]`):
          The module each added entry was added for.

        Returns:
        * (`list[str]`): Such as `ezpkg: added "sprocket" to
          `prog.py`'s `dependencies` (line 12).`.
        """
        # Each entry's line afterwards, if it can be counted.
        name: str = f"`{self.program.name}`'s `dependencies`"
        lines: list[int] = dependency_lines(edited) or []
        at: dict[str, str] = {
            entry: f" (line {line})" for entry, line in zip(final, lines)}
        reports: list[str] = [
            f'ezpkg: removed "{entry}" from {name}.'
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
                reports.append(f'ezpkg: added "{entry}" to {name}'
                               f'{at.get(entry, "")}{comment}.')
            elif entry in moved:
                reports.append(f'ezpkg: moved "{entry}" in {name}'
                               f'{at.get(entry, "")}.')
        return reports

    def rows(self, final: Sequence[str],
             kept: Sequence[str]) -> list[tuple[str, str]]:
        """Return the label and entry of each `dependencies` line of `display`.

        Arguments:
        * `final` (`Sequence[str]`):
          The `dependencies` afterwards.
        * `kept` (`Sequence[str]`):
          Entries to add to `[tool.ezpkg] unimported`.

        Returns:
        * (`list[tuple[str, str]]`): Such as `("add", '"sprocket",')`.
        """
        # The operations, then each with its label.
        rows: list[tuple[str, str]] = []
        numbered: bool = (0 not in self.lines
                          and len(set(self.lines)) == len(self.lines))
        opcodes: list[tuple[str, int, int, int, int]] = (
            difflib.SequenceMatcher(None, self.entries,
                                    list(final)).get_opcodes())

        def row(label: str, entry: str) -> None:
            """Add one line of the display."""
            rows.append((label, entry))
        position: int
        operation: str
        first: int
        last: int
        start: int
        end: int
        index: int
        for position, (operation, first, last, start, end) in enumerate(
                opcodes):
            if operation == "equal":
                # Only the ends that touch a change, as anchors.
                shown: list[int] = []
                if position > 0:
                    shown.append(first)
                if position < len(opcodes) - 1:
                    shown.append(last - 1)
                for index in sorted(set(shown)):
                    row(f"line {self.lines[index]}" if numbered else "",
                        f'"{self.entries[index]}",')
                continue
            if position == 0:
                row("", "[")
            for index in range(first, last):
                if self.entries[index] not in final:
                    row("remove", f'"{self.entries[index]}",')
            entry: str
            for entry in final[start:end]:
                if entry in self.entries:
                    row(f"move ({self.lines[self.entries.index(entry)]})"
                        if numbered else "move", f'"{entry}",')
                else:
                    row("add", f'"{entry}",')
            if position == len(opcodes) - 1:
                row("", "]")
        for entry in kept:
            row("keep", f'"{entry}" (added to [tool.ezpkg] unimported)')
        return rows


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
        * `develop/` remembers, one small file per program, what was
          last said about differences between its imports and the
          packages it declares, so that each is raised once.  Delete
          a file to be asked again.
        * `pending/` is scratch space used while fetching and
          unpacking.  Anything left in it is litter from an interrupted
          run and is safe to remove.
        * `pip.whl` is a private copy of `pip`, which the bootstrap
          fetched so that this machine needs no `pip` of its own.  It
          is run straight from the wheel and never installed.  Newer
          releases are added beside it as `pip-<version>-...whl` about
          once a week, and the newest is the one used.
        * `last_cull` and `last_pip` are stamps recording when the
          cache was last swept and when `pip` was last checked.
        * `ezpkg/` and `ezpkg-<version>.dist-info/` are `EZPkg`
          itself, which the bootstrap installed.
        * `FOREVER_APPROVE`, if present, means somebody answered `a` or
          `s` to the download prompt, so nobody is asked before packages
          are installed (and, after `s`, nothing is said about them).
          Delete it to be asked again.
        * `remove.py` removes this whole directory.
        * `quick_start.py` is a complete program that uses `EZPkg`.
          Copy its parts into a program of your own; the comments in
          it say which part is which.  It is the copy that came with
          the `ezpkg` installed here, so after a new release the
          one in the project's `README.md` may be newer.

        Deleting this whole directory is safe.  The next program that
        needs one of these packages will fetch it again.  To delete it:

        * Linux and macOS: `python3 ~/.ezpkg/remove.py`
        * Windows: `py %USERPROFILE%\\.ezpkg\\remove.py`

        A program can say which packages it needs in a PEP 723 block at
        its top, and can carry a `.ezpkg` file beside it recording
        which exact wheels its author approved.

        Arguments:
        * `root` (`Path | None`):
          The cache directory to use.  `None`, the default, means
          `~/.ezpkg`, which is the directory the bootstrap
          code names.  Tests pass a temporary directory instead.
        * `pip` (`subprocess.CompletedProcess[str] | None`):
          What the bootstrap's `pip install ezpkg` printed, captured,
          on the run that installed `ezpkg` (a first run), else `None`
          (`T.abfd`).
        * `later` (`object`):
          Keywords a newer bootstrap passes, ignored, so that it can
          still reach `install` and switch to the `ezpkg` it asks for
          (`T.eui`).
        """
        # Default to the cache directory that the bootstrap code names.
        self.pip_run: subprocess.CompletedProcess[str] | None = pip
        self.told: bool = False  # Have `bootstrapped`'s been listed?
        self.listings: int = 0  # How many lists `provide` has printed.
        self.developer: bool | None = None  # See `developing`.
        self.changed: str = ""  # The changed file's SHA-256, if so.
        self.declined: bool = False  # `n` to `working_on`, this run.
        self.reported: set[str] = set()  # Modules `reconcile` named.
        self.edited: bool = False  # Was the program's file changed?
        self.restarted: bool = False  # Is this run a `restart`'s?
        self.root = Path.home() / ".ezpkg" if root is None else root
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

    def approvals(self) -> Path | None:
        """Return the file that records what the author approved.

        The file travels with the program rather than with the cache,
        because the judgement it records is the author's: they chose the
        dependencies and can tell `requests` from `reqeusts`, where the
        person who merely ran the program cannot.  So it sits beside the
        main program, as `prog.py` to `prog.ezpkg`, and is meant to be
        committed next to it.

        A program with no file of its own -- the interpreter prompt,
        `python3 -c`, a frozen executable -- has nowhere to keep one and
        gets no verification.  See `T.sawaw`.

        Returns:
        * (`Path | None`): Where the approvals are, or `None` when this
          program has no file to put them beside.
        """
        # The main program is what the approvals belong to.
        where: Path | None = main_path()
        if where is None:
            return None
        return where.with_suffix(".ezpkg")

    def approved(self) -> dict[str, str] | None:
        """Read the approvals, as a mapping from wheel name to digest.

        Returns:
        * (`dict[str, str] | None`): What was approved, or `None` when
          there is no approvals file, which means nothing is verified.
        """
        # An unreadable file is treated as absent: nothing is verified,
        # and `install` says as much rather than failing obscurely.
        record: Path | None = self.approvals()
        if record is None or not record.is_file():
            return None
        found: dict[str, str] = {}
        line: str
        for line in record.read_text().splitlines():
            if line.startswith("#") or not line.strip():
                continue
            fields: list[str] = line.split()
            if len(fields) == 2:
                found[fields[0]] = fields[1]
        return found

    def approve(self, wheels: Sequence[Path],
                resolved: str = "") -> Path | None:
        """Record the wheels that arrived as approved.

        Called when `EZPKG_APPROVE` is `write`, which is how an
        author regenerates the file after changing what the program
        needs.  Sorted by name, so that a change shows up as a small
        diff in whatever the program is committed to, and dated, since
        the list is what `pip` chose on that day.

        It records what arrived without judging it, because judging it is
        the author's part.  An author who runs this while pointed at an
        index they should not trust will approve whatever that index
        sent, and the file will then vouch for it on every machine the
        program reaches.  That is the one way this mechanism can be
        turned against itself, and there is no technical answer to it:
        run it against an index you mean to trust.

        Arguments:
        * `wheels` (`Sequence[Path]`):
          The wheels to record.
        * `resolved` (`str`):
          When `pip` chose them, as `stamp` also writes it.  Empty means
          now.

        Returns:
        * (`Path | None`): The file written, or `None` when this program
          has nowhere to keep one.
        """
        # One line per wheel, name then digest, sorted for the diff.
        record: Path | None = self.approvals()
        if record is None:
            return None
        rows: list[str] = sorted(f"{wheel.name} {self.digest(wheel)}"
                                 for wheel in wheels)
        # The date says when `pip` chose these, which is what the list
        # is true of: the same request tomorrow may resolve differently.
        # A comment, so `approved` reads the file as it always has.
        resolved = resolved or time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                             time.gmtime())
        record.write_text(
            "# Wheels this program has approved, by SHA-256.  Regenerate\n"
            "# with EZPKG_APPROVE=write after changing what it needs.\n"
            f"# Resolved: {resolved}\n"
            + "".join(f"{row}\n" for row in rows))
        return record

    def resolution(self) -> str:
        """Return the approvals' `# Resolved:` date, or an empty string.

        Returns:
        * (`str`): The date `approve` wrote, such as
          `2026-10-17T18:40:11Z`; empty with no file or no date line.
        """
        # The line `approve` writes, third in the file.
        record: Path | None = self.approvals()
        if record is None or not record.is_file():
            return ""
        found: re.Match[str] | None = re.search(
            r"(?m)^# Resolved: (\S+)$", record.read_text())
        return found.group(1) if found else ""

    def pins(self) -> list[str]:
        """Return an exact `==` pin for every approved wheel.

        The approvals already name every wheel the program needs, the
        ones that came along included, and a wheel's file name carries
        its distribution and version.  Pinned, they make `pip` fetch the
        same versions every time, and the approvals then check that
        those are the same files: together, a freeze.  `locked` hands
        them to `pip` as constraints, and `build_uv` writes them into
        the `uv` script's Part 1.  See `T.ewar` and `T.rafal` in
        `TASKS/`.

        Returns:
        * (`list[str]`): Requirements such as `widget==1.2.3`, sorted.

        Raises:
        * `RuntimeError`:
          If there is no approvals file to pin from, if it names
          something that is not a wheel, or if it approves two versions
          of one distribution, which no single pin can say.
        """
        # A wheel is `{name}-{version}-...`, and the name has no hyphen.
        approved: dict[str, str] | None = self.approved()
        if not approved:
            raise RuntimeError(
                "no approvals to pin; run once with "
                "EZPKG_APPROVE=write first")
        versions: dict[str, set[str]] = {}
        wheel: str
        for wheel in approved:
            # Only a hand edit makes anything else, and since `locked`
            # pins on every run, it must say which file and line.
            if not wheel.endswith(".whl") or wheel.count("-") < 4:
                raise RuntimeError(
                    f"{wheel} in {self.approvals()} is not a wheel name; "
                    f"regenerate it with EZPKG_APPROVE=write")
            name, version = wheel.split("-")[:2]
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

        `write` and `skip` get no lock, because both are an author
        choosing again: `write` resolves afresh and records the result,
        which is how a program's packages are upgraded.  See `T.rafal`
        in `TASKS/`.

        Returns:
        * (`list[str]`): Constraints such as `widget==1.2.3`, sorted, or
          an empty list when nothing is locked.

        Raises:
        * `RuntimeError`:
          Through `pins`, if the approvals name two versions of one
          distribution.
        """
        # Only an ordinary run, and only with something approved.
        mode: str = os.environ.get("EZPKG_APPROVE", "").lower()
        if mode in ("write", "skip") or not self.approved():
            return []
        return self.pins()

    def cutoff(self) -> str:
        """Return the upload date a fetch must keep before, if any.

        The date is `exclude-newer` in Part 1's `[tool.uv]` table, which
        is where `uv run` reads it too, so one line serves both.  It is
        for a program sent on its own, without its approvals: it gets the
        packages that were newest when its author recorded them, rather
        than whatever is newest the day it is run.  `write` stamps it;
        see `stamp`.

        With approvals there is no date, because the lock already says
        exactly which versions.  `write` and `skip` get none either, for
        the reason `locked` gives.  See `T.srdisb` in `TASKS/`.

        Returns:
        * (`str`): The date as `pip`'s `--uploaded-prior-to` takes it, or
          an empty string for none.
        """
        # Only an ordinary run without approvals.
        mode: str = os.environ.get("EZPKG_APPROVE", "").lower()
        if mode in ("write", "skip") or self.approved():
            return ""

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
        return when if isinstance(when, str) else ""

    def stamp(self, resolved: str) -> str:
        """Write the resolution date into the program's Part 1.

        As `exclude-newer` in the `[tool.uv]` table, so that the date
        travels inside the `.py` even when the approvals do not; see
        `cutoff`.  The author is asked first, naming the line, because
        this edits a file they wrote; with no terminal to ask on, the
        file is left alone.  Nothing else in the program changes.  Its encoding,
        byte order mark and line endings are kept, since a program is
        not obliged to be UTF-8 with `\\n`.

        Arguments:
        * `resolved` (`str`):
          The date, as `approve` wrote it.

        Returns:
        * (`str`): A line for standard error, or an empty string when
          there is nothing to say, as for a program with no `script`
          block, which has nowhere to put a date.
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

        # No block, no date and nothing to say.
        block: tuple[re.Match[str], str] | None = script_toml(text)
        if block is None:
            return ""
        found: re.Match[str]
        toml: str
        found, toml = block
        setting: str = f'exclude-newer = "{resolved}"'
        by_hand: str = (f"add `# {setting}` under `# [tool.uv]` in its "
                        f"script block by hand")
        dated: str | None = uv_setting(toml, "exclude-newer", f'"{resolved}"')
        if dated is None:
            return f"could not write the resolution date into {where}; {by_hand}"
        if dated == toml:
            return ""

        # Ask, naming the line the setting will be on afterwards.
        edited: str = with_script_toml(text, found, dated)
        line: int = edited.splitlines().index(f"# {setting}") + 1
        verb: str = ("change" if "exclude-newer" in (
            tomllib.loads(toml).get("tool", {}).get("uv", {})) else "add")
        if not self.ask(f"ezpkg: could I {verb} `{setting}` at line "
                        f"{line} of {where.name}?"):
            return f"{where} left as it was; to date it, {by_hand}"
        write_program(where, edited, encoding, crlf)
        self.edited = True
        return f"resolution date {resolved} written to {where}"

    def offer_ranges(self, asking: Sequence[str]) -> list[str]:
        """Offer version ranges for the bare entries in Part 1.

        Under `EZPKG_APPROVE=write`, once the approvals are written: each
        entry that is a name alone gets the range `version_range` makes
        from the version just approved, so that a `.py` sent without its
        approvals cannot be handed a much newer package than the one it
        was tested with ("I used EZPkg and it put the wrong packages
        in!", Wayne, 2026-10-15).  Development is never interrupted for
        this, nor is the Quick Start's newcomer.  An entry with any
        specifier, extra or marker is the author's decision and is left
        alone.  Asked first, as `stamp` asks; no terminal, no edit.
        See `T.kdaiis`.

        Arguments:
        * `asking` (`Sequence[str]`):
          The requirements the program declared.

        Returns:
        * (`list[str]`): The requirements now declared.
        """
        # The approved version of each bare entry.
        versions: dict[str, str] = {
            normal_name(wheel.split("-")[0]): wheel.split("-")[1]
            for wheel in self.approved() or {}}
        ranged: list[str] = [
            version_range(entry, versions[normal_name(entry)])
            if requirement_name(entry) == entry.strip()
            and normal_name(entry) in versions else entry
            for entry in asking]
        changed: list[str] = [after for before, after
                              in zip(asking, ranged, strict=True)
                              if before != after]
        where: Path | None = main_path()
        if not changed or where is None:
            return list(asking)

        # Asked, then written, keeping the encoding and line endings.
        source: str
        encoding: str
        crlf: bool
        try:
            source, encoding, crlf = read_program(where)
        except OSError:
            return list(asking)
        edited: str | None = with_dependency_list(source, ranged)
        if edited is None:
            return list(asking)
        entries: str = "entry" if len(changed) == 1 else "entries"
        listed: str = ", ".join(f'"{entry}"' for entry in changed)
        if not self.ask(textwrap.fill(
                f"ezpkg: could I add version ranges to {len(changed)} "
                f"{entries} of {where.name} ({listed})?", 76)):
            return list(asking)
        try:
            write_program(where, edited, encoding, crlf)
            self.edited = True
        except OSError as error:
            print(f"ezpkg: {where.name}: could not write it ({error})",
                  file=sys.stderr)
            return list(asking)
        print(f"ezpkg: {where.name}: version ranges written", file=sys.stderr)
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

    def export(self, form: str, asking: Sequence[str] = ()) -> None:
        """Write what the approvals record in another tool's form.

        Called when `EZPKG_EXPORT` is set, after the packages have
        been provided and checked, and the program exits straight after
        without running its own code.  Every form first checks that Part
        1 covers what the program imports; see `check_imports`.
        `zipapp` writes `prog.pyz` beside the program,
        and `zipapp:PATH` writes it at `PATH`; see `build_zipapp`.
        `uv` writes `prog-uv.py` and its lock file, and `uv:PATH`
        names the script; see `build_uv`.

        There was once a `pins` form, printing Part 1 with every package
        pinned, for a `.py` sent on its own.  The `exclude-newer` date
        that `write` puts in Part 1 does that job now, with no step to
        remember (Wayne, 2026-10-12).

        Arguments:
        * `form` (`str`):
          What to write: `zipapp`, `zipapp:PATH`, `uv` or `uv:PATH`.  The kind is read in any case; the path is taken as
          written.
        * `asking` (`Sequence[str]`):
          The requirements just provided, which `build_zipapp` bundles.

        Raises:
        * `ValueError`:
          If `form` is not one this knows.
        * `RuntimeError`:
          If `check_imports`, `build_zipapp` or `build_uv` does;
          see there.
        """
        # The kind, then for a file an optional place to put it.  A
        # misspelt form is refused before anything is read.
        kind: str
        target: str
        kind, _, target = form.partition(":")
        kind = kind.lower()
        if kind not in ("zipapp", "uv"):
            raise ValueError(
                f"EZPKG_EXPORT is {form!r}; use zipapp or uv")

        # Whatever leaves this machine must not lean on what is on it.
        self.check_imports(asking)
        if kind == "zipapp":
            self.build_zipapp(asking, Path(target) if target else None)
        else:
            self.build_uv(Path(target) if target else None)

    def sync_dependencies(self, asking: Sequence[str],
                          argv: Sequence[str] = ()) -> list[str]:
        """Offer to bring Part 1's `dependencies` in line with the imports.

        Once per change of the program's imports or `dependencies`
        (`dependency_fingerprint`), any discrepancy (`discrepancy`) is
        named.  Two or more changes are one question, whose `y` shows
        and makes them all; with one change, or `i`, each addition and
        removal is asked about in line order, since only the answer can
        say whether an import is coming or going, and the changes are
        shown and approved once.  Additions are fetched and proved to
        contain their modules, and only then is the file edited, once.  `EZPkg` edits `dependencies` and `[tool.ezpkg]`,
        and never an import, except to copy the author's `mypy` comment
        (`with_type_ignores`).  With no terminal, the discrepancy is
        only named, once per change.  See `T.kdaiis` in `TASKS/`.

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
        if source is None:
            return list(asking)
        program: Path
        text: str
        program, text = source
        approved: set[str] = {normal_name(wheel.split("-")[0])
                              for wheel in self.approved() or {}}
        try:
            fingerprint: str = dependency_fingerprint(text, asking, approved)
        except SyntaxError:
            return list(asking)
        record: Path
        kept: dict[str, Any]
        record, kept = self.development_record(program)
        breaking: bool = (kept.get("breaking") == fingerprint
                          and not self.developing())
        if (kept.get("asked") == fingerprint and not self.changed
                and not breaking):
            return list(asking)

        # Worked out only now, since it reads the installed metadata.
        found: Discrepancy | None = self.discrepancy(program, text, asking)
        if found is None or not found.pending():
            # A changed copy with nothing to offer asks nothing yet.
            self.keep(record, kept, asked=fingerprint,
                      **({"source": self.changed} if self.changed else {}))
            return list(asking)

        # A missing package breaks the program on every run, whoever
        # runs it, so an end-user hears of it every run; the rest is a
        # developer's business (Wayne, 2026-10-18).
        missing: list[tuple[int, str, str]] = [
            addition for addition in found.additions
            if not self.developing() and not importable(addition[1])]
        breaking = bool(missing)
        if breaking:
            self.keep(record, kept, breaking=fingerprint)

        # Named once per change; asked only of a developer, and only on
        # a terminal.  An end-user whose copy has changed, or will break,
        # may be its developer, and is asked.
        opened: tuple[IO[str], IO[str]] | None = (
            None if not (self.developing() or self.changed or breaking)
            else self.terminal())
        if opened is not None and not self.developing():
            with opened[0], opened[1]:
                if not self.working_on(found, missing, opened, record,
                                       kept):
                    self.keep(record, kept, warned=fingerprint,
                              asked=fingerprint)
                    return list(asking)
            opened = self.terminal()
        if opened is None:
            if breaking:
                print(found.stopping(missing, False), file=sys.stderr)
                self.declined = True  # Said, so `scan_imports` is quiet.
            elif kept.get("warned") != fingerprint:
                print(found.summary(), file=sys.stderr)
            self.keep(record, kept, warned=fingerprint)
            return list(asking)
        writer: IO[str]
        reader: IO[str]
        writer, reader = opened
        with writer, reader:
            return self.reconcile(found, list(asking), argv, record, kept,
                                  fingerprint, approved, opened)

    def fetching(self, final: Sequence[str]) -> list[str]:
        """Return what fetching a `dependencies` asks of the index.

        The `ezpkg` entry this `ezpkg` meets is left out, as in
        `install`: the index may not have this very version.

        Arguments:
        * `final` (`Sequence[str]`):
          The `dependencies`.

        Returns:
        * (`list[str]`): The requirements to fetch.
        """
        # Only an entry this one meets.
        own: str | None = own_entry(final)
        return ([one for one in final if one != own]
                if own is not None and self.chosen(own) else list(final))

    def versions_of(self, requirements: Sequence[str],
                    argv: Sequence[str] = ()) -> dict[str, str]:
        """Return the versions fetching some requirements would bring.

        Fetched into a holding directory as `provide` would fetch them
        (lock and date included), read off the wheels' names, and
        thrown away: nothing is unpacked or run, and `pip`'s own cache
        makes the real fetch cheap.  For the list before `reconcile`'s
        question.

        Arguments:
        * `requirements` (`Sequence[str]`):
          What to fetch; nothing is fetched for none.
        * `argv` (`Sequence[str]`):
          Extra arguments for `pip`, as `install` takes them.

        Returns:
        * (`dict[str, str]`): Each wheel's version by its `normal_name`,
          empty when nothing could be fetched.
        """
        # A failure here is reported by the real fetch, if it comes.
        if not requirements:
            return {}
        arrived: list[Path] = []
        try:
            arrived = self.download(requirements, argv, self.locked(),
                                    self.cutoff())
            return {normal_name(one.name.split("-")[0]):
                    one.name.split("-")[1] for one in arrived}
        except (RuntimeError, ValueError):
            return {}
        finally:
            holding: Path
            for holding in {one.parent for one in arrived}:
                shutil.rmtree(holding, ignore_errors=True)

    def edit_for(self, found: Discrepancy, final: Sequence[str],
                 keeping: Sequence[str], why: Mapping[str, str],
                 modules: Collection[str], comment: bool
                 ) -> tuple[str, str, bool, str, str, str] | str:
        """Work out the whole edit `reconcile` would make, in stages.

        In three stages, so that `Discrepancy.display` can say which
        change each line is.

        Arguments:
        * `found` (`Discrepancy`):
          What disagrees.
        * `final` (`Sequence[str]`):
          The `dependencies` afterwards.
        * `keeping`, `why` (`Sequence[str]`, `Mapping[str, str]`):
          The entries kept as `unimported`, and the developer's reasons.
        * `modules` (`Collection[str]`):
          The added imports, which get the author's `mypy` comment.
        * `comment` (`bool`):
          True when `import ezpkg` gets it too.

        Returns:
        * (`tuple[str, str, bool, str, str, str] | str`): The source,
          its encoding, whether its lines end in CRLF, then the program
          with only `dependencies` changed, with `[tool.ezpkg]` too, and
          the whole edit; or the line saying why it cannot be made.
        """
        # The file as it is, then each stage.
        program: Path = found.program
        source: str
        encoding: str
        crlf: bool
        try:
            source, encoding, crlf = read_program(program)
        except OSError as error:
            return f"ezpkg: {program.name}: cannot read it: {error}\n"
        listed: str | None = with_dependency_list(source, final)
        kept: str | None = listed
        if kept is not None and keeping:
            kept = self.with_unimported(kept, list(keeping), dict(why))
        if listed is None or kept is None:
            return (f"ezpkg: {program.name}: cannot edit its script "
                    f"block; change `dependencies` by hand\n")
        edited: str
        edited, _ = with_type_ignores(
            kept, {*modules, *(["ezpkg"] if comment else [])}, found.used)
        return source, encoding, crlf, listed, kept, edited

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
            return f'no package "{package}" is currently available'
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
                  fingerprint: str, approved: set[str],
                  opened: tuple[IO[str], IO[str]]) -> list[str]:
        """Talk a discrepancy through on the terminal, and fix it.

        The conversation `sync_dependencies` describes, in Wayne's
        design (2026-10-15).

        Arguments:
        * `found` (`Discrepancy`):
          What disagrees.
        * `asking` (`list[str]`):
          The requirements the program declared.
        * `argv` (`Sequence[str]`):
          Extra arguments for `pip install`.
        * `record` (`Path`):
          The program's development record.
        * `kept` (`dict[str, Any]`):
          What the record holds.
        * `fingerprint` (`str`):
          The program's `dependency_fingerprint`.
        * `approved` (`set[str]`):
          The names its approvals cover.
        * `opened` (`tuple[IO[str], IO[str]]`):
          The terminal.

        Returns:
        * (`list[str]`): The requirements now declared.
        """
        # Guessed names are proved first, so that nothing is offered,
        # or counted, that could never be added.
        writer: IO[str] = opened[0]
        program: Path = found.program
        # Only Auto is remembered; an old `d` ("never") is forgotten.
        answer: str = ("update" if kept.get("answer") == "update" else "")
        offered: list[int] = []
        position: int
        line: int
        module: str
        package: str
        for position, (line, module, package) in enumerate(found.additions):
            problem: str = (self.prove(package, module, argv)
                            if package in found.guessed else "")
            if problem:
                declared: list[int] = [one for one in found.lines if one]
                where: str = (f" ({line_list(declared)})" if declared
                              else "")
                writer.write(wrapped(
                    f"{program.name}:{line}: `import {module}` needs a "
                    f"package, but {problem}.  Please check the spelling, "
                    f"or manually add the right package to "
                    f"`dependencies`{where}.", columns(writer)) + "\n")
                self.reported.add(module)
            else:
                offered.append(position)
        every: set[str] = {found.additions[position][2]
                           for position in offered}
        count: int = found.updating(found.arrange(every, found.removals))
        if not count and found.uncommented is None:
            writer.write("Nothing to change.\n")
            self.keep(record, kept, asked=fingerprint, answer=answer)
            return asking

        # Several changes are one question, unless `a` chose Auto;
        # `i` goes through them one by one.  Two modes only, Manual
        # (asked) and Auto (`a`, done with a line per change): an old
        # record's `d` ("never") now just asks (Wayne, `ux11`).  See
        # `T.kdaiis`.
        added: set[str] = set()
        removed: set[int] = set()
        keeping: list[str] = []
        why: dict[str, str] = {}
        comment: bool = False
        confirm: bool = True
        chosen: str = "update" if answer == "update" else (
            "individually" if count < 1 else "")
        remembered: bool = chosen == "update"  # Auto (`ux11`).
        modules: dict[str, str]
        listed_first: list[str] | None = None
        if not chosen:
            # Listed before the question, ranges and all, so the answer
            # is an informed one (Wayne, `ux/ux04_Batch_y.txt`); the
            # additions are fetched for that silently, then let go.
            listed_first = found.arrange(every, found.removals)
            modules = {package: module for _, module, package
                       in found.additions if package in every}
            versions: dict[str, str] = self.versions_of(
                self.fetching(listed_first) if modules else [], argv)
            listed_first = [version_range(entry, versions[normal_name(entry)])
                     if entry in modules and normal_name(entry) in versions
                     else entry for entry in listed_first]
            edit: tuple[str, str, bool, str, str, str] | str = self.edit_for(
                found, listed_first, [], {}, set(modules.values()),
                found.uncommented is not None)
            if isinstance(edit, str):
                listed_first = None
                writer.write(found.needing(count) + "\n")
            else:
                writer.write(found.display(
                    listed_first, edit[0], edit[3], edit[4], edit[5], False,
                    found.needing(count, ":")))
        # Asked once: nobody wants to answer the same question twice
        # (Wayne, `ux10`), so `a` takes effect at once, and says how to
        # undo it.  A lone unused entry can be kept with `k`.
        lone: bool = count == 1 and not offered and len(found.removals) == 1
        if not chosen:
            chosen = self.choose(
                opened, (f"Update it? [y=>Yes|n=>No|"
                         f"{'k=>Keep it, needed without an import|' if lone else ''}"
                         f"a=>Auto, from now on]: ") if count == 1
                else "Update them? [y=>Yes|n=>No|i=>Individually|"
                     "a=>Auto, from now on]: ",
                {"y": "yes", "yes": "yes", "n": "no", "no": "no",
                 "a": "update", "auto": "update",
                 **({"i": "individually"} if count > 1 else {}),
                 **({"k": "keep", "keep": "keep"} if lone else {})}) or "no"
            if chosen == "update":
                writer.write(wrapped(
                    f"From now on, `ezpkg` updates `{program.name}`'s "
                    f"`dependencies` without asking.  To be asked again, "
                    f"delete `{shown(record)}`.", columns(writer)) + "\n")
                answer = chosen
        if chosen == "no":
            # Said here, so `scan_imports` is quiet (`ux06_Batch_n`).
            writer.write(wrapped(
                f"Nothing changed.  This is asked again when the "
                f"imports or `dependencies` of `{program.name}` "
                f"change.", columns(writer)) + "\n")
            self.declined = True
            self.keep(record, kept, asked=fingerprint, answer=answer)
            return asking
        # A blank line comes before what follows: the list of new
        # packages, or the changes (`ux/ux02_Batch_y.txt`).
        blank: bool = False
        if chosen in ("yes", "update", "keep"):
            # A remembered `a` is silent (Wayne, `ux10`).
            if listed_first is not None:
                writer.write("\n")
                blank = True
            added = every
            removed = set(found.removals) if chosen != "keep" else set()
            comment = found.uncommented is not None
            confirm = False
            if chosen == "keep":
                lone_name: str = requirement_name(
                    found.entries[found.removals[0]])
                keeping.append(lone_name)
                writer.write(f"What needs `{lone_name}`? (a few words, or "
                             f"Enter to skip): ")
                writer.flush()
                why[lone_name] = "".join(
                    one for one in answer_from(opened[1], writer).strip()
                    if one.isprintable())

        # Otherwise each addition and removal, in line order.
        else:
            writer.write(found.summary() + "\n" if count < 2 else "\n")
            items: list[tuple[int, str, int]] = sorted(
                [(found.additions[position][0], "add", position)
                 for position in offered]
                + [(found.lines[index], "remove", index)
                   for index in found.removals]
                + ([(found.uncommented, "comment", 0)]
                   if found.uncommented is not None else []))
            kind: str
            which: int
            for line, kind, which in items:
                reply: str
                if kind == "comment":
                    reply = self.choose(
                        opened, f"Line {line}: `ezpkg` is imported without "
                        f"the mypy comment your other\nimports carry.  Add "
                        f"it? [y=>Yes|n=>No]: ", YES_NO)
                    comment = reply == "yes"
                elif kind == "add":
                    _, module, package = found.additions[which]
                    reply = self.choose(
                        opened, f"Line {line}: `{module}` is imported, but "
                        f'not in `dependencies`.\nAdd "{package}"? '
                        f"[y=>Yes|n=>No]: ", YES_NO)
                    if reply == "yes":
                        added.add(package)
                else:
                    entry: str = found.entries[which]
                    reply = self.choose(
                        opened, f'Line {line}: "{entry}" is in '
                        f"`dependencies`, but nothing imports it.\nRemove "
                        f"it? [y=>Yes|n=>No|k=>Keep it, needed without an "
                        f"import]: ",
                        {**YES_NO, "k": "keep", "keep": "keep"})
                    if reply == "yes":
                        removed.add(which)
                    elif reply == "keep":
                        # Only the developer knows why, so the program
                        # says it in their words (Wayne, 2026-10-18).
                        kept_name: str = requirement_name(entry)
                        keeping.append(kept_name)
                        writer.write(f"What needs `{kept_name}`? (a few "
                                     f"words, or Enter to skip): ")
                        writer.flush()
                        why[kept_name] = "".join(
                            one for one in answer_from(opened[1], writer
                                                       ).strip()
                            if one.isprintable())
                if not reply:
                    return asking

        # The additions are fetched and proved first, since the versions
        # that arrive decide what is written: each gets a range from the
        # version it ran with (`version_range`).
        final: list[str] = found.arrange(added, removed)
        if final == found.entries and not keeping and not comment:
            writer.write("Nothing to change.\n")
            self.keep(record, kept, asked=fingerprint, answer=answer)
            return asking
        modules = {package: module for _, module, package
                   in found.additions if package in added}
        fetching: list[str] = self.fetching(final)
        listings: int = self.listings
        writer.flush()
        try:
            self.provide(fetching, argv, {normal_name(package): module
                                          for package, module
                                          in modules.items()})
            if self.listings != listings:
                blank = True  # The list ends with one.
        except Declined:
            # A no to the download stops the program, as on any run;
            # nothing is recorded, so the change is offered again.
            raise
        except (RuntimeError, ValueError) as error:
            reason: str = failure_reason(error)
            hint: str = ("; with an approvals file, run it with "
                         "EZPKG_APPROVE=write" if self.approved() else "")
            writer.write(f"ezpkg: {program.name}: nothing changed: "
                         f"{reason}{hint}\n")
            self.keep(record, kept, asked=fingerprint, answer=answer)
            return asking
        fetched: tuple[list[str], list[str]] | None = self.remember(
            self.request_for(fetching))
        ranged: dict[str, str] = {}
        for package in modules:
            try:
                ranged[package] = version_range(
                    package, importlib.metadata.version(package))
            except importlib.metadata.PackageNotFoundError:
                ranged[package] = package
        final = [ranged.get(entry, entry) for entry in final]

        # The whole edit, worked out before it is shown; not shown
        # again when the list before the question already was.
        made: tuple[str, str, bool, str, str, str] | str = self.edit_for(
            found, final, keeping, why, set(modules.values()), comment)
        if isinstance(made, str):
            writer.write(made)
            return asking
        source: str
        encoding: str
        crlf: bool
        listed: str
        kept_text: str
        edited: str
        source, encoding, crlf, listed, kept_text, edited = made
        if confirm or final != listed_first and not remembered:
            writer.write(("" if blank else "\n")
                         + found.display(final, source, listed, kept_text,
                                         edited, not confirm))
        if confirm and self.choose(
                opened, "Make these changes? [y=>Yes|n=>No]: ",
                YES_NO) != "yes":
            self.keep(record, kept, asked=fingerprint, answer=answer)
            return asking

        # Written once.  What was just fetched answers the request the
        # ranges make, so the next run does not fetch it all again.
        try:
            write_program(program, edited, encoding, crlf)
            self.edited = True
        except OSError as error:
            writer.write(f"ezpkg: {program.name}: nothing changed: "
                         f"{error}\n")
            self.keep(record, kept, asked=fingerprint, answer=answer)
            return asking
        if fetched is not None:
            self.remember(self.request_for(final), *fetched)

        # In Auto mode nothing was shown, so each change gets a line,
        # since the file changed under its developer (Wayne, `ux11`).
        # Otherwise the display has said it all (Wayne, `ux02`).
        if remembered:
            report: str
            for report in found.reported(
                    final, kept_text, edited,
                    {ranged.get(package, package): module
                     for package, module in modules.items()}):
                writer.write(wrapped(report, columns(writer)) + "\n")

        # Remembered as settled.
        try:
            settled: str = dependency_fingerprint(edited, final, approved)
        except SyntaxError:
            settled = fingerprint
        self.keep(record, kept, asked=settled, answer=answer)
        return final

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
        and it is not kept as `unimported`.  See `T.kdaiis`.

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
        except SyntaxError:
            return None
        bootstrap: ast.Try | None = bootstrap_node(text)
        implied: int | None = None if bootstrap is None else bootstrap.lineno
        if implied is not None:
            imports = sorted([*imports, ("ezpkg", implied, False)],
                             key=lambda one: one[1])
        entries: list[str] = list(asking)
        lines: list[int] = dependency_lines(text) or [0] * len(entries)
        names: list[str] = [normal_name(requirement_name(entry))
                            for entry in entries]
        keep: set[str] = {normal_name(name) for name in unimported(text)}
        approved: set[str] = {normal_name(wheel.split("-")[0])
                              for wheel in self.approved() or {}}
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
                adding.add(normal_name(packages[0]))
                order.append(("add", 0, packages[0]))
                additions.append((line, module, packages[0]))

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

    def with_unimported(self, text: str, adding: Sequence[str],
                        reasons: Mapping[str, str] | None = None
                        ) -> str | None:
        """Return a program with names added to `[tool.ezpkg] unimported`.

        One entry per line, each with the developer's reason as its
        comment, such as `"requests",  # Needed by the sync script`, so
        the program says why a package nothing imports is kept (Wayne,
        2026-10-18).  An array already written that way gains lines
        before its `]`, and its comments are kept as they are.

        Arguments:
        * `text` (`str`):
          The program's source.
        * `adding` (`Sequence[str]`):
          The package names to keep.
        * `reasons` (`Mapping[str, str] | None`):
          What needs each, for its comment; one missing gets
          `Needed, but not imported.`

        Returns:
        * (`str | None`): The program, or `None` when its block cannot
          be edited safely.
        """
        # The new lines, then where they go.
        block: tuple[re.Match[str], str] | None = script_toml(text)
        if block is None:
            return None
        names: list[str] = unimported(text)
        fresh: list[str] = [name for name in adding if name not in names]

        def entry(name: str) -> str:
            """Return one line of the array, with its comment."""
            # A reason ending in neither stop gets one.
            reason: str = (f"Needed by {(reasons or {})[name]}"
                           if (reasons or {}).get(name)
                           else "Needed, but not imported")
            return (f'  "{name}",  # {reason}'
                    + ("" if reason[-1] in ".!?" else "."))

        # Lines added before the `]` of an array already one per line,
        # checked by parsing; otherwise the whole key is written anew.
        toml: str | None = None
        lines: list[str] = block[1].split("\n")
        start: int | None = next(
            (index for index, line in enumerate(lines)
             if re.fullmatch(r"\s*unimported\s*=\s*\[\s*(#.*)?", line)),
            None)
        end: int | None = None if start is None else next(
            (index for index in range(start + 1, len(lines))
             if re.fullmatch(r"\s*\]\s*(#.*)?", lines[index])), None)
        if start is not None and end is not None:
            lines[end:end] = [entry(name) for name in fresh]
            toml = "\n".join(lines)
            try:
                if tomllib.loads(toml).get("tool", {}).get("ezpkg", {}).get(
                        "unimported") != names + fresh:
                    toml = None
            except tomllib.TOMLDecodeError:
                toml = None
        else:
            toml = uv_setting(
                block[1], "unimported",
                "[\n" + "".join(f'  "{name}",\n' for name in names)
                + "".join(entry(name) + "\n" for name in fresh) + "]",
                "ezpkg")
        return None if toml is None else with_script_toml(
            text, block[0], toml)

    def developing(self) -> bool:
        """Say whether the running program's developer is running it.

        `ezpkg` has two kinds of customer, end-users and developers,
        and cannot tell which is running a program the first time it
        sees it, so it assumes an end-user: somebody who can only
        decide whether to trust its author, and must never be asked
        about `dependencies` or have the program edited (Wayne,
        2026-10-18).  When the program's file has changed since then,
        its developer may be at work, so `changed` is set, and
        `working_on` asks the first time there is something to offer;
        only a `y` puts the program in developer mode, from then on.
        Per program, in its record under `develop/` (`mode` and the
        file's SHA-256 as `source`), so one person can be an end-user of
        some programs and the developer of others.  Deleting the record
        makes it an end-user's again.

        Returns:
        * (`bool`): True in developer mode.  A program with no file of
          its own is an end-user's.
        """
        # Decided once per run.
        if self.developer is not None:
            return self.developer
        self.developer = False
        found: tuple[Path, str] | None = main_source()
        if found is None:
            return False
        digest: str = hashlib.sha256(
            found[1].encode("utf-8", "surrogateescape")).hexdigest()
        record: Path
        kept: dict[str, Any]
        record, kept = self.development_record(found[0])
        if kept.get("mode") == "developer":
            self.developer = True
        elif "source" not in kept:
            self.keep(record, kept, mode="end-user", source=digest)
        elif kept["source"] != digest:
            self.changed = digest
        return self.developer

    def working_on(self, found: Discrepancy,
                   missing: Sequence[tuple[int, str, str]],
                   opened: tuple[IO[str], IO[str]], record: Path,
                   kept: dict[str, Any]) -> bool:
        """Ask whether the person running a changed program is its developer.

        Asked only when `developing` saw the file change and there is a
        discrepancy to offer (Wayne, 2026-10-18).  `y` puts the program
        in developer mode; `n` leaves it an end-user's, says so, and
        is asked again only when the file changes again.  No answer
        decides nothing.

        Arguments:
        * `found` (`Discrepancy`):
          What there is to offer.
        * `missing` (`Sequence[tuple[int, str, str]]`):
          The additions whose modules cannot be imported here, which
          will stop the program (`Discrepancy.additions`' shape).
        * `opened` (`tuple[IO[str], IO[str]]`):
          The terminal.
        * `record`, `kept` (`Path`, `dict[str, Any]`):
          The program's record and what it holds, which the caller
          writes again (`development_record`).

        Returns:
        * (`bool`): True for a `y`.
        """
        # The paragraph, then the question, as the download prompt does.
        writer: IO[str] = opened[0]
        name: str = f"`{found.program.name}`"
        width: int = columns(writer)
        why: str = (f"{name} has changed since it was first run"
                    if self.changed or not missing else
                    f"{name} imports a package its `dependencies` do not "
                    f"list")
        writer.write(wrapped(
            f"{why}, so you may be working on it.  If you are, `ezpkg` "
            f"will offer to keep its `dependencies` in step with its "
            f"imports, and you can turn down any change until you are "
            f"ready.  If the imports and dependencies are not in sync, the "
            f"program will typically fail at an `import` statement.",
            width) + "\n\n")
        reply: str = self.choose(
            opened, f"Are you working on {name}? [y=>Yes|n=>No]: ", YES_NO)
        source: dict[str, str] = (
            {"source": self.changed} if self.changed else {})
        if reply == "yes":
            self.keep(record, kept, mode="developer", **source)
            self.developer = True
            writer.write("\n")
            return True
        if reply == "no":
            self.keep(record, kept, **source)
            self.declined = True  # Said here, so `scan_imports` is quiet.
            writer.write(
                found.stopping(missing, True, width) if missing
                else wrapped(f"{name} is left as it is.  This is asked again "
                             f"when {name} changes.", width) + "\n")
        return False

    def development_record(self, program: Path
                           ) -> tuple[Path, dict[str, Any]]:
        """Return a program's record under `develop/`, and what it holds.

        It holds the program's path, the fingerprint last dealt with on
        a terminal (`asked`) and without one (`warned`), the answer that
        outlives a run, `update` or `never`, and the program's mode and
        the SHA-256 that decided it (`developing`).  Touched on
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
             **changes: str) -> None:
        """Update a development record, the way `scan_imports` writes.

        Arguments:
        * `record` (`Path`):
          The record, under `develop/`.
        * `kept` (`dict[str, Any]`):
          What it held, which is updated too.
        * `changes` (`str`):
          `asked`, `warned` or `answer`.
        """
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

    def choose(self, opened: tuple[IO[str], IO[str]], question: str,
               answers: Mapping[str, str]) -> str:
        """Ask a question on the terminal until it is answered.

        Anything that is not an answer is asked about again, up to
        `ATTEMPTS` times; there is no default, as for the download
        prompt.

        Arguments:
        * `opened` (`tuple[IO[str], IO[str]]`):
          The terminal.
        * `question` (`str`):
          The question, with its answers spelled out.
        * `answers` (`Mapping[str, str]`):
          What each reply means, lowercased.

        Returns:
        * (`str`): The meaning, or empty when the terminal went away
          or nothing sensible was said.
        """
        # A terminal that has gone away reads as empty.
        writer: IO[str]
        reader: IO[str]
        writer, reader = opened
        attempt: int
        for attempt in range(ATTEMPTS):
            writer.write(question if not attempt
                         else "Please answer with one of the letters.\n"
                         + question)
            writer.flush()
            reply: str = answer_from(reader, writer)
            if not reply:
                return ""
            meaning: str | None = answers.get(reply.strip().lower())
            if meaning is not None:
                return meaning
        return ""

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
            print(f"ezpkg: {program.name}: {problem}", file=sys.stderr)
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
            print(f"ezpkg: {program.name}: {problem}", file=sys.stderr)
        if problems:
            print(f"ezpkg: {program.name}: shown once; shown again "
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
        covered |= {normal_name(wheel.split("-")[0])
                    for wheel in self.approved() or {}}
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
        either is refused rather than bundled half working.

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
        raw: bytes = program.read_bytes()
        encoding: str = tokenize.detect_encoding(io.BytesIO(raw).readline)[0]
        text: str = raw.decode(encoding)

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

        # What this request resolved to, as the cache recorded it.
        approved: dict[str, str] | None = self.approved()
        if not approved:
            raise RuntimeError(
                "no approvals to bundle from; run once with "
                "EZPKG_APPROVE=write first")
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
        unapproved: list[str] = sorted(set(wheels) - set(approved))
        compiled: list[str] = sorted(
            wheel for wheel in wheels
            if not wheel.endswith("-none-any.whl"))
        hooks: list[str] = sorted(
            found.name for tree in trees
            for found in (versions / tree).glob("*.pth"))
        problem: str
        names: list[str]
        for problem, names in (("not approved", unapproved),
                               ("compiled, which a zip cannot import",
                                compiled),
                               ("a .pth file, which a zip never runs",
                                hooks)):
            if names:
                raise RuntimeError(
                    f"cannot bundle {', '.join(names)}: {problem}")

        # Stage the trees and the program, then zip them.
        staging: str
        with tempfile.TemporaryDirectory(prefix="ezpkg-zipapp-") \
                as staging:
            stage: Path = Path(staging)
            tree: str
            for tree in trees:
                shutil.copytree(
                    versions / tree, stage, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
            (stage / "__main__.py").write_bytes(stripped.encode(encoding))
            zipapp.create_archive(stage, target,
                                  interpreter="/usr/bin/env python3")
        print(f"ezpkg: wrote {target}")
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
        raw: bytes = program.read_bytes()
        encoding: str = tokenize.detect_encoding(io.BytesIO(raw).readline)[0]
        stripped: str | None = strip_bootstrap(
            raw.decode(encoding), "uv installs the packages.")
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
        print(f"ezpkg: wrote {target}")

        # `uv` locks it; without `uv`, say how to finish elsewhere.
        commands: list[list[str]] = [["lock", "--script", str(target)]]
        uv: str | None = find_uv()
        if uv is None:
            print("ezpkg: uv is not installed; to finish, run:")
            command: list[str]
            for command in commands:
                print("    uv " + " ".join(command))
            return target
        environment: dict[str, str] = dict(os.environ)
        index: str = environment.get("PIP_INDEX_URL", "")
        if index and not (environment.get("UV_DEFAULT_INDEX")
                          or environment.get("UV_INDEX_URL")):
            environment["UV_DEFAULT_INDEX"] = index
        for command in commands:
            done: subprocess.CompletedProcess[str] = subprocess.run(
                [uv, *command], env=environment, capture_output=True,
                text=True, check=False)
            if done.returncode:
                raise RuntimeError(
                    f"uv {command[0]} failed: {done.stderr.strip()}")

        # The lock must list the very wheels that were approved.
        lock: Path = target.with_name(target.name + ".lock")
        approved: dict[str, str] = self.approved() or {}
        problems: list[str] = lock_mismatches(
            tomllib.loads(lock.read_text(encoding="utf-8")),
            {name: approved[name]
             for name in for_export(approved, stripped)})
        if problems:
            raise RuntimeError(
                "uv's lock disagrees with the approvals: "
                + "; ".join(problems))
        print(f"ezpkg: wrote {lock}")
        return target

    def summary(self, wheel: Path) -> str:
        """Return what a wheel says about itself, in one safe line.

        Read from the `METADATA` inside the archive, so no network call
        and no unpacking: the wheel is still an inert zip when this runs.

        The text is written by whoever uploaded the package, which is the
        adversary in the case this is meant to help with, so a
        typosquat's summary reads exactly like the real one.  It is
        offered as description, never as evidence, and everything
        unprintable is removed: a summary may contain escape sequences,
        and printing those beside a question lets them rewrite the
        question.

        Arguments:
        * `wheel` (`Path`):
          A wheel to look inside.

        Returns:
        * (`str`): The summary, or an empty string if it has none.
        """
        # `Summary` is one header among many, and nominally one line.
        return self.metadata(wheel).get("Summary", "")

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
        the run whose bootstrap installed them (`pip_run` set) lists
        them, and only once (`told`).

        Returns:
        * (`list[tuple[str, str]]`): Each one's name and version, then
          its summary, `pip` first, as they arrived.
        """
        # Nothing, unless this run's bootstrap fetched them.  The mark
        # goes before the summary, which may be cut.
        if self.pip_run is None or self.told:
            return []
        found: list[tuple[str, str]] = []
        fields: dict[str, str] = self.metadata(self.root / "pip.whl")
        if fields:
            title: str = (f"{fields.get('Name', 'pip')} "
                          f"{fields.get('Version', '')} (used by `ezpkg`)")
            found.append((title, fields.get("Summary", "")))

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
        """Say what is now installed, after it has been unpacked.

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
            f"installed in {place}:", width)]
        lines += [cut(f"{number}. {title}" + (f": {told}" if told else ""),
                      width)
                  for number, (title, told) in enumerate(packages, 1)]
        lines.append(wrapped(f"`ezpkg` ({HOME_PAGE}) manages {place}.",
                             width))
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

        `y` or `yes` goes ahead once; `n` or `no` declines; `?`
        describes each wheel and asks again; `a` or
        `always` stops the question being asked at all, and is the one
        answer that asks for confirmation first, because it is the only
        one that outlives this run.  Declining that confirmation returns
        to the question rather than cancelling the install, and counts as
        an attempt so that the pair cannot loop for ever.

        Anything else is taken for a typo and the question is put again,
        up to `ATTEMPTS` typos.  A bare newline is one of them: there is
        no default, because a distracted Enter should neither install
        nor quietly decline, so it is asked again like any other
        non-answer.  Asking for the detail is not a typo and
        does not count, so curiosity is never punished.  A terminal that
        has gone away reads as empty, which
        declines at once rather than being asked again forever.

        With no terminal there is nobody to ask, and the answer is yes:
        a line says how many packages were stored, and failing instead would
        break every program run from `cron` or a build on the first day.
        A guarantee rather than a notification is what the approvals file
        is for; see `T.sawaw`.

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

        # `y` goes ahead, `n` declines, `?` says more and asks again,
        # and anything else, an empty line included, is a typo worth
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
        paragraph: str = wrapped(
            f"The author of {name} has selected some software packages "
            f"from the internet.  If you agree, they will be retained in "
            f"{place}.  If you do not trust the author, answer `n` and "
            f"{place} will simply go away without running {name}.", width)
        question: str = wrapped(f"Retain {place} and run {name}?", width)
        if self.developing():
            # The developer chose them, by changing the program, and
            # `n` removes only these (Wayne, 2026-10-18).
            paragraph = wrapped(
                f"Your changes to {name} need {len(wheels)} more software "
                f"package(s) from the internet.  They have been downloaded, "
                f"but nothing in them has run yet.  Answer `n` and they "
                f"will be removed again, without running {name}.", width)
            question = wrapped(f"Keep them in {place} and run {name}?",
                               width)
        question += ("\n[y=>Yes, this time|n=>No|a=>Always, list|"
                     "s=>Always, silently|?=>Explain]: ")
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
                if answer in ("y", "yes"):
                    # This time only; `a` is for never being asked
                    # again (Wayne, 2026-10-18).
                    return True
                if answer in ("n", "no"):
                    return False
                if answer in ("a", "always", "s", "silently"):
                    # Asked once, since the label says what it does
                    # (Wayne, `ux10`).  `a` still lists each new
                    # download; `s` says nothing more (Wayne, `ux22`).
                    # A permanent decision deserves a visible way back.
                    silent: bool = answer.startswith("s")
                    marker: Path = self.forever()
                    marker.write_text(
                        ("silent" if silent else "always")
                        + "\nThis file means: do not ask again before "
                        "installing packages\ninto this directory"
                        + (", or list them" if silent else "")
                        + ".  Delete it to be asked again.\n",
                        encoding="utf-8")
                    writer.write("\n" + wrapped(
                        f"From now on, `ezpkg` downloads software packages "
                        f"into {place} "
                        f"{'silently' if silent else 'without asking'}.  "
                        f"To be asked again, delete `{shown(marker)}`.  To "
                        f"remove `ezpkg` and everything it downloaded, run "
                        f"`{removal_command(self.root)}`.", width) + "\n\n")
                    return True
                if answer == "?":
                    writer.write(
                        "\nSoftware packages are code from PyPI, the "
                        "Python Package Index:\n"
                        + "\n".join(self.details(wheels)) + "\n\n")
                    continue
                typos += 1
                writer.write(
                    "Please answer y, n, a for always, s for silently, or ? for "
                    "more.\n")
        return False

    def ask(self, question: str) -> bool:
        """Ask a yes-or-no question on the terminal, and say which.

        For the author's own decisions, such as letting `stamp` edit the
        program.  Unlike `consent`, no terminal means no: the question
        is about changing a file somebody wrote, and nobody present to
        agree is not agreement.  Anything but `y`, `yes`, `n` or `no` is
        asked again, up to `ATTEMPTS` times; a terminal that has gone
        away reads as empty, which is no.

        Arguments:
        * `question` (`str`):
          The question, without the answers, which this adds.

        Returns:
        * (`bool`): True only for a yes.
        """
        # No terminal, nobody to say yes.
        opened: tuple[IO[str], IO[str]] | None = self.terminal()
        if opened is None:
            return False
        writer: IO[str]
        reader: IO[str]
        writer, reader = opened
        answer: str
        with writer, reader:
            for _attempt in range(ATTEMPTS):
                writer.write(f"{question} [y=>Yes|n=>No]: ")
                writer.flush()
                answer = answer_from(reader, writer)
                if not answer:
                    return False
                answer = answer.strip().lower()
                if answer in ("y", "yes"):
                    return True
                if answer in ("n", "no"):
                    return False
                writer.write("Please answer y or n.\n")
        return False

    def forever(self) -> Path:
        """Return the file that says never to ask on this machine again.

        The `a` answer to the consent question writes it.  It belongs to
        the cache rather than to any program, because it records a
        decision by whoever uses this machine and not by any author: the
        person has understood that packages are downloaded and would
        rather not be asked each time a new cache needs filling.

        It lives in the cache, so deleting the cache restores the
        question, which is the same lifetime the question already had:
        asked once per cache.  See `T.rd`.

        Returns:
        * (`Path`): The marker, whether or not it exists.
        """
        # One file, named so that somebody listing the directory can
        # guess what it does without reading anything else.
        return self.root / "FOREVER_APPROVE"

    def silent(self) -> bool:
        """Say whether `s` answered the download prompt for good.

        `s` writes `silent` as the marker's first line; `a`, or a marker
        from before `s` existed, means only "do not ask" (`ux22`).

        Returns:
        * (`bool`): True when no download is to be listed either.
        """
        # Unreadable or absent is not silent.
        try:
            first: str = self.forever().read_text(
                encoding="utf-8").partition("\n")[0]
        except OSError:
            return False
        return first.strip() == "silent"

    def gate(self, wheels: Sequence[Path], asking: Sequence[str] = (),
             new: Sequence[Path] | None = None) -> None:
        """Write, skip, enforce or ask, as the environment says.

        `EZPKG_APPROVE` unset enforces the approvals or asks when
        there are none, `write` records what arrived instead, and `skip`
        does neither, which is for an author still deciding what the
        program needs.

        An author running `write` or `skip` is present and deliberate,
        so neither asks anything.  Otherwise, approvals decide: if the
        author approved this set, it is verified in silence, and if there
        are no approvals at all the person who started the program is
        asked once.  The author's judgement replaces the recipient's
        prompt rather than being added to it.

        A `FOREVER_APPROVE` marker in the cache, written by answering `a`,
        skips the question.  It is checked **after** the approvals, so it
        can never hide a wheel that fails `verify`; see `forever`.
        Nor is anybody asked about a fetch that brought nothing new,
        since there is nothing to agree to (`ux/ux03_Batch_i_with_keep`).

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
        # One place decides, so the cold and warm paths cannot diverge.
        mode: str = os.environ.get("EZPKG_APPROVE", "").lower()
        if mode == "write":
            # A program with no file has nowhere to keep approvals, and
            # saying "written to None" would claim otherwise.
            # The same wheels as already approved keep their date, which
            # is still true of them, so a second `write` asks nothing.
            resolved: str = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                          time.gmtime())
            unchanged: bool = self.approved() == {
                wheel.name: self.digest(wheel) for wheel in wheels}
            if unchanged:
                resolved = self.resolution() or resolved
            written: Path | None = self.approve(wheels, resolved)
            if written is None:
                print("nowhere to write approvals: this program has no "
                      "file of its own", file=sys.stderr)
            else:
                print(f"approvals {'unchanged in' if unchanged else 'written to'}"
                      f" {written}", file=sys.stderr)
            stamped: str = self.stamp(resolved)
            if stamped:
                print(stamped, file=sys.stderr)
            return
        if mode == "skip":
            return
        if self.approved() is not None:
            self.verify(wheels)
            return

        # The marker answers the question; it does **not** answer
        # `verify`, which is above it on purpose.  A wheel that does not
        # match what an author approved is a different matter from a
        # person who would rather not be asked, and no amount of
        # impatience should hide it.
        asked: Sequence[Path] = wheels if new is None else new
        if self.forever().is_file() or not (asked or self.bootstrapped()):
            return
        # Control-C before the answer's Enter is a no; after it, the
        # answer stands (Wayne, `ux14`).
        how: str = "Declined"
        try:
            agreed: bool = self.consent(asked, asking)
        except KeyboardInterrupt:
            agreed = False
            how = "Interrupted"
            print(file=sys.stderr)  # After the `^C`.
        if not agreed:
            raise Declined(
                f"declined: nothing was installed into {self.root}",
                f"{how}, so {self.removed()} and "
                f"{name_of(program_name())} did not run.")

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
        if (self.pip_run is not None and self.root != Path.home()
                and (self.root / "pip.whl").is_file()):
            shutil.rmtree(self.root, ignore_errors=True)
            return f"{self.place()} has been removed"
        return "the new software package(s) have been removed"

    def verify(self, wheels: Sequence[Path]) -> None:
        """Refuse anything the author did not approve.

        Checked after the wheels have arrived and **before** any of them
        is unpacked, which is what makes the refusal meaningful: a wheel
        is an inert zip, so nothing in it has run at the moment it is
        turned away.

        Arguments:
        * `wheels` (`Sequence[Path]`):
          The wheels that arrived.

        Raises:
        * `RuntimeError`:
          If a wheel is absent from the approvals, or present with a
          different digest.  The message names the file to regenerate,
          because that is the only sensible next step.
        """
        # No approvals file means nothing to check against.
        expected: dict[str, str] | None = self.approved()
        if expected is None:
            return
        wheel: Path
        actual: str
        for wheel in wheels:
            actual = self.digest(wheel)
            if wheel.name not in expected:
                raise RuntimeError(
                    f"{wheel.name} is not approved in "
                    f"{self.approvals()}; regenerate it with "
                    f"EZPKG_APPROVE=write if it should be")
            if expected[wheel.name] != actual:
                raise RuntimeError(
                    f"{wheel.name} does not match its approval in "
                    f"{self.approvals()}: expected "
                    f"{expected[wheel.name]}, got {actual}")

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
            shutil.rmtree(holding, ignore_errors=True)
            print(f"ezpkg: fetching without the program's exclude-newer "
                  f"date {before}, which this index or pip cannot apply",
                  file=sys.stderr)
            return self.download(requirements, argv, constraints)
        if done.returncode == 2:
            raise ValueError(
                f"pip rejected the command line: "
                f"{done.stderr.strip() or 'pip gave no reason'}")
        # A lock that `dependencies` has moved past fails here, as a
        # conflict `pip` cannot resolve, so say which file to regenerate.
        if done.returncode != 0:
            stale: str = (
                f"; if `dependencies` changed, the versions locked in "
                f"{self.approvals()} may be the conflict: regenerate it "
                f"with EZPKG_APPROVE=write" if constraints else "")
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

    def report_bootstrap(self) -> str:
        """Describe the program's pasted bootstrap in one line.

        Silent by default; `install` prints this only when
        `EZPKG_BOOTSTRAP=check` asks, because the person running a
        program cannot act on it and its author can ask.  See 6.12.2 of
        `T.fbanwiis`.

        Returns:
        * (`str`): The line, for standard error.
        """
        # One sentence per state.
        state: str
        name: str
        state, name = self.bootstrap_status()
        newest: str = list(BOOTSTRAPS.values())[-1]
        if state == "current":
            return f"ezpkg: this program's bootstrap is current, {name}"
        if state == "stale":
            return (f"ezpkg: this program's bootstrap is stale, {name}; "
                    f"the current one is {newest}")
        if state == "edited":
            return ("ezpkg: this program's bootstrap has been edited, "
                    "or is not one ezpkg published")
        return "ezpkg: no bootstrap found in this program"

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
        this `ezpkg` runs the program and is not fetched, except under
        `EZPKG_APPROVE=write`, which fetches exactly this version so that
        the approvals pin it, and so a later run on another machine
        switches to it (`T.eui`).  A copy not installed from a wheel is
        on no index, so it is left out, and the author is told.  An
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
        if os.environ.get("EZPKG_APPROVE", "").lower() != "write":
            # An export of a program that imports `ezpkg` itself
            # carries the pinned one (`for_export`), which `chosen`
            # has checked is this version.
            if os.environ.get("EZPKG_EXPORT"):
                wheels: list[str] = list(self.approved() or {})
                if len(without_ezpkg(wheels)) < len(wheels):
                    return [f"ezpkg=={__version__}", *others]
            return others
        if not from_wheel():
            print(f"ezpkg: this ezpkg {__version__} was not installed "
                  f"from a wheel, so the approvals do not pin it",
                  file=sys.stderr)
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

    def restart(self) -> None:
        """Run the program again after `ezpkg` has changed its file.

        Python compiled the file as it was when the run began, but a
        traceback reads its lines from the file as it is now, so after
        an edit every line number below it would point at the wrong
        line (Wayne, `ux08`, 2026-10-18).  So every edit is followed by
        a fresh start, which reads the edited file and has nothing more
        to ask.  Only the docstring and the bootstrap have run so far;
        anything else above the bootstrap is flagged
        (`statements_above_bootstrap`).  Once only: `EZPKG_RESTARTED`
        marks the second start, and a second edit is only reported.
        `EZPKG_APPROVE` is held back from `ezpkg` in the second start, so
        that `write` does not ask its questions again, and given back to
        the program.

        Raises:
        * `SystemExit`:
          With the program's own exit status on Windows.
        """
        # A second edit is said, not restarted, so nothing can loop.
        if self.restarted:
            print(f"ezpkg: {program_name()} was changed again after "
                  f"starting it again, so a traceback's line numbers may "
                  f"be off until it runs again", file=sys.stderr)
            return
        # The second start is an ordinary run: everything `write` asks
        # was asked and recorded by the first.
        environment: dict[str, str] = dict(
            os.environ, EZPKG_RESTARTED=os.environ.get("EZPKG_APPROVE", ""))
        environment.pop("EZPKG_APPROVE", None)
        run_again(environment)

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
        # A `restart`'s mark is for this run only, not its children,
        # which get back the `EZPKG_APPROVE` it held from `ezpkg`.
        held: str | None = os.environ.pop("EZPKG_RESTARTED", None)
        self.restarted = held is not None
        try:
            self.provide_declared(argv, bootstrap)
        except Declined as declined:
            # One line, not a traceback or the bootstrap's `failed:`
            # line, which would read as a fault; from the first fetch or
            # a `dependencies` update's (`ux16`).
            raise SystemExit(wrapped(declined.said, columns(sys.stderr))
                             ) from None
        finally:
            if held:
                os.environ["EZPKG_APPROVE"] = held

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

        # Before anything else can change the file, the program's mode.
        self.developing()

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

        # Recording approvals is a release step, so it is also when
        # bare entries are offered their ranges.
        if os.environ.get("EZPKG_APPROVE", "").lower() == "write":
            asked = self.offer_ranges(asked)

        # An export is a build step, not a run: once written, the
        # program stops before its own code.  See `export`.
        form: str = os.environ.get("EZPKG_EXPORT", "")
        if form:
            self.export(form, providing)
            sys.exit(0)

        # An ordinary run keeps Part 1 in step with the imports for
        # somebody developing the program, then warns about every
        # import still uncovered, now that the declared packages
        # can be found.
        self.scan_imports(self.sync_dependencies(asked, argv))
        if self.edited:
            self.restart()

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

        `EZPKG_APPROVE` decides what happens to what arrives.  Unset,
        each wheel is checked against the approvals file beside the
        program and a mismatch is refused.  `write` records what arrived
        instead of checking it, which is how an author regenerates the
        file.  `skip` checks nothing, which is for an author still
        deciding what the program needs.  A program with no approvals
        file is told what arrived and not asked about it; see `T.sawaw`.
        Unset, the approvals also lock: the versions they record are
        the ones fetched, whatever is newer; see `locked`.

        `EZPKG_EXPORT`, in the no-argument form, writes what the
        approvals record in another form and then exits instead of
        returning, so the program's own code never runs: `zipapp` or
        `uv`, as `export` describes.  Otherwise the program's imports
        are checked against Part 1, and any it misses are reported once
        on standard error; see `scan_imports`.

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

        # Say whether the pasted bootstrap is current, but only when the
        # author asks; see `T.fbanwiis`.
        if os.environ.get("EZPKG_BOOTSTRAP", "").lower() == "check":
            print(self.report_bootstrap(), file=sys.stderr)

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
        # Except under `write`, which always fetches: an author recording
        # approvals is choosing again, and a remembered answer may be
        # weeks old.  See `T.rafal` in `TASKS/`.
        locked: list[str] = self.locked()
        before: str = self.cutoff()
        request: str = self.request_for(asking)
        writing: bool = (
            os.environ.get("EZPKG_APPROVE", "").lower() == "write")
        remembered: tuple[list[str], list[str]] | None = (
            None if writing else self.remember(request))
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

                # Then say what is stored, the bootstrap's own
                # packages too on a first run, once.  Said from the
                # wheels before `unpack` moves them away.
                stored: str = self.listing(new, columns(sys.stderr))
                trees = [self.unpack(wheel) for wheel in arrived]
                if (new or self.bootstrapped()) and not self.silent():
                    print(stored, file=sys.stderr)
                    self.listings += 1
                self.told = True
                self.remember(request, [tree.name for tree in trees],
                              [wheel.name for wheel in arrived])
            finally:
                # The holding directory has served its purpose once every
                # wheel in it is either kept or already unpacked -- and
                # equally once one has been refused, because a refusal
                # means do not install this, not keep it for later.
                for holding in {wheel.parent for wheel in arrived}:
                    shutil.rmtree(holding, ignore_errors=True)
        else:
            # A warm cache fetches nothing, so there is nothing new to
            # approve or refuse.  Verification belongs to the moment of
            # fetching: somebody who can rewrite the cache can rewrite
            # the program too, so that is not the threat this defends
            # against.
            trees = [self.paths()[2] / key for key in remembered[0]]

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
        records in `develop/`, which `development_record` touches.

        Nothing else is aged.  Trees are kept or dropped by whether a
        record still names them, so removing a record is what makes its
        packages collectable, and `litter` does the rest.  One rule each,
        rather than two overlapping ones.

        Arguments:
        * `days` (`float`):
          Seconds of disuse before a record counts as stale.  Named for
          the unit a person thinks in; `CULL_DAYS` does the arithmetic.

        Returns:
        * (`list[Path]`): The records, sorted, removed by nobody.
        """
        # An unreadable record is `litter`'s business, not this one's.
        cutoff: float = time.time() - days
        found: list[Path] = []
        record: Path
        for record in [*self.paths()[3].glob("*.json"),
                       *(self.root / "scans").glob("*.json"),
                       *(self.root / "develop").glob("*.json")]:
            try:
                if record.stat().st_mtime < cutoff:
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

    def contains(self, package: str) -> bool:
        """Report whether the cache holds an importable package.

        Every unpacked tree under `versions` is searched, because there
        is one per distribution and version and a package may sit in
        any of them.  A package arrives either as a directory or as a
        single module, so both spellings count.

        Nothing under `pending` is looked at.  A wheel there has not
        been approved, so as far as the rest of the world is concerned
        it is not in the cache at all; see 6.3.1 of `T.vcbow`.

        Arguments:
        * `package` (`str`):
          The import name to look for.

        Returns:
        * (`bool`): True if some approved tree holds it.
        """
        # Either spelling, in any version directory, counts as present.
        tree: Path
        for tree in self.paths()[2].iterdir():
            if ((tree / package).is_dir()
                    or (tree / f"{package}.py").is_file()):
                return True
        return False
