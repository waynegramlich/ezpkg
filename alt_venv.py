# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
#
# The block above is this project eating its own cooking, and it is the
# one place the Python floor is written down.  See Steps 6.7.4 and 6.7.7
# in `LOGBOOK.md`: 3.11, because `tomllib` reads the block and `tomllib`
# arrived in 3.11, and no higher because nothing here needs 3.12.  The
# language features used set only 3.10 -- `Path | None` is evaluated at
# run time and `bootstrap.py` uses `match` -- so the standard library is
# what costs the extra version.  `dependencies` is empty on purpose and
# says so: a project about fetching packages that are not preinstalled
# has none of its own.
#
# Nothing reads it yet.  A tool such as `uv` reads the block belonging to
# the script it is running, and this is a library that is never
# `__main__`, so the block is documentation until Step 6.7 can parse it.
# At that point `build_wheel` should take `Requires-Python` from here
# rather than keeping a second copy.

"""Fetch Python packages that are not preinstalled, from one file.

This module is the second stage of the two stage design described in
`LOGBOOK.md`.  A small bootstrap stub, pasted by hand into a program
that needs it, fetches this package and imports it.  Everything that is
too large to paste lives here.

The stub fetches exactly one package, of known name and with no
dependencies.  `AltVEnv` then fetches whatever the calling program
actually declared, which is the general case: version constraints,
extras, transitive dependencies and compiled wheels.

This file is a placeholder.  `AltVEnv` is deliberately empty until
the shape of the general case fetch has been worked out.

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
import hashlib
import importlib
import inspect
import io
import json
import os
import re
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
import zipfile
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import IO, Any, overload

# How many times `AltVEnv.consent` will put the same question, when the
# answer is neither yes nor no.  Bounded, so that a terminal feeding
# nonsense cannot keep a program alive indefinitely.
ATTEMPTS: int = 3

# How long something has to have been lying about before it is taken for
# litter, and how often the cache is swept.  The grace period is about
# concurrency rather than tidiness: a download in progress lives under
# `pending/`, and an unpacked tree appears in `versions/` a moment before
# the record naming it is written, so anything young may belong to a
# program that is still running.  A day is far longer than either window
# and short enough to keep a crashed run's leftovers from accumulating.
# See Step 6.11 in `LOGBOOK.md`.
CULL_GRACE: float = 86400.0
CULL_INTERVAL: float = 86400.0

# How long a request may go unanswered before the cache stops keeping the
# packages that answered it.  Six months, because the cost of being wrong
# is one download and the cost of being right is a little disk, and those
# are not symmetrical.  See Step 6.11 in `LOGBOOK.md`.
CULL_DAYS: float = 180.0 * 86400.0

# How often the private `pip` is checked for a newer release.  Weekly, as
# `pip` checks itself, because each check asks the index and may fetch
# 1.8 MB, while `pip` releases come every month or two.  See issue
# `3spinu` in `LOGBOOK.md`.
PIP_INTERVAL: float = 7.0 * 86400.0

# Every bootstrap this project has published, by `bootstrap_fingerprint`,
# oldest first, so the last is the current one.  Publishing a changed
# bootstrap means adding its fingerprint here; the test suite renders
# `nopip3` as pasted and fails until the last entry matches it.  Old
# entries stay, because they are how a stale copy is recognised.  See
# Step 6.12 in `LOGBOOK.md`.
BOOTSTRAPS: dict[str, str] = {
    "02e20da610125a90d038db27f77f835dfd7731e29d9a366d85327f24e56d283f":
        "nopip3 of 2026-10-01",
}

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
# dependencies = ["cowsay"]
\x23 ///
"""Try `AltVEnv`: fetch the `cowsay` package on first use, then run."""

# Part 2: The standard library imports that the bootstrap uses.
import hashlib
import importlib
import json
import pathlib
import subprocess
import sys
import urllib.request as req

# Part 3: The bootstrap.  Copy it exactly, and never edit it.
try:
    s = "find home"; t = pathlib.Path.home()/".alt_venv"; w = t/"pip.whl"
    if not (t/"alt_venv").is_dir():  # Not installed yet.
        s = "choose pip"; v = sys.version_info[1]
        d = json.load(req.urlopen("https://pypi.org/pypi/pip/json", None, 30))
        e = max((e for f in d["releases"].values() for e in f  # Newest pip
                 if e["url"][-4:] == ".whl" and not e["yanked"]
                 and (q := e["requires_python"] or "")[:4] == ">=3."
                 and "," not in q and int(q.split(".")[1]) <= v),
                key=lambda e: e["upload_time"])  # whose floor we meet.
        s = "download pip"; r = req.urlopen(e["url"], None, 60).read()
        if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
            raise ValueError(f"{e['filename']} fails its SHA-256 check")
        t.mkdir(parents=True, exist_ok=True); p = t/"pip.part"
        p.write_bytes(r); p.replace(w)  # The rename is atomic.
        s = "install alt_venv"; subprocess.run([
            sys.executable, w/"pip", "install", "--no-input", "-t", t,
            "--disable-pip-version-check", "alt_venv"], check=True)
    s = "import alt_venv"; sys.path.insert(0, str(t))
    importlib.invalidate_caches(); importlib.import_module("alt_venv")
except Exception as x:
    raise SystemExit(f"cannot fetch alt_venv, {s} failed: {x!r}")

# Part 4: Fetch the packages listed in Part 1, then import them.
import alt_venv  # type: ignore[import-not-found]

alt_venv.AltVEnv().install()
import cowsay  # type: ignore[import-not-found]

# Part 5: The program itself.
cowsay.cow("AltVEnv works!")
print(f"cowsay {cowsay.__version__} was loaded from {cowsay.__file__}")
'''

# The one place the version is written down.  `bootstrap.py`
# prints it after importing, and the test suite stamps it into
# the wheel it builds.
__version__: str = "0.0.1"


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
    `AltVEnv.install`, and a wrong guess shows up immediately as a
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


def main_path() -> Path | None:
    """Return the file the running program was started from.

    `sys.modules["__main__"].__file__` rather than walking frames with
    `inspect`, because the main module is exactly what is wanted and
    asking for it directly cannot pick the wrong frame.

    There is often no such file.  The interpreter prompt and `python3
    -c` leave `__main__` without a `__file__` at all, and then there is
    nothing to find.  Every caller has to cope with that rather than
    assume a program has a file; see Step 6.12.1 in `LOGBOOK.md`.

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
# 2026-09-27.  Counting the fences notices them anyway.  See Step 6.7.7.
FENCE: re.Pattern[str] = re.compile(r"(?m)^# /// script$")


# The one `requires-python` shape this understands: a single `>=` clause
# naming two or three numbers, which is what a real block says.  Anything
# else -- `>=3.9,<4`, `!=3.9.*`, `~=3.11`, a pre-release rule -- is left
# alone rather than guessed at, because PEP 440 belongs to `pip`.  See
# Steps 6.3.3 and 6.7.10 in `LOGBOOK.md`.
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
    See Steps 6.7.2 and 6.7.7 in `LOGBOOK.md`.

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

    Three things want this: the PEP 723 block of Step 6.7, the bootstrap
    that Step 6.12 looks for, and the approvals file of Step 6.6, which
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
    is one token, and under 3.12, where it is several.  See Step 6.12.

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
    `alt_venv` and `import_module`, wherever it sits.  Only the `try`
    is taken: the imports above it are moved to the top of a program by
    hand, and would make a correctly pasted copy look edited.

    Arguments:
    * `text` (`str`):
      The program's source.

    Returns:
    * (`str | None`): The block, or `None` when there is none or the
      program does not parse.
    """
    # The first match wins; a program has one bootstrap.
    try:
        tree: ast.Module = ast.parse(text)
    except SyntaxError:
        return None
    node: ast.AST
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            # Padded and then dedented, because the segment's first line
            # otherwise comes without its indentation and the rest with
            # theirs, which `tokenize` rejects when the `try` is nested.
            block: str | None = ast.get_source_segment(text, node,
                                                       padded=True)
            if block and "alt_venv" in block and "import_module" in block:
                return textwrap.dedent(block)
    return None


def refresh(path: Path, text: str) -> None:
    """Write a file only when its contents would change.

    Making an object used to write a file every time, which is a side
    effect nobody asks a constructor for and which touches the
    modification time of a file a person may be reading; see Step
    6.10.5 in `LOGBOOK.md`.  A stale copy is still replaced, so a newer
    `alt_venv` still reaches a cache that holds an older file.

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


class AltVEnv:
    """Fetch and import Python packages that are not preinstalled.

    Most of the class is still to come.  What it eventually holds is
    the general case fetch: read the calling program's declared
    requirements, resolve them, install them into a cache directory
    keyed by interpreter and platform, and put that directory on
    `sys.path`.

    What works today is the cache directory itself.  Constructing an
    `AltVEnv` creates the directory and drops a `README.md` into
    it, so that somebody who finds the directory and wonders what it
    is can read the answer without leaving it.  Beside it goes
    `quick_start.py`, the template a person copies into a program.

    Attributes:
    * `bootstrap` (`str`):
      Which bootstrap the program carries, as `install` was told, or the
      empty string.  Nothing reads it yet; see Step 6.12 in `LOGBOOK.md`.
    * `readme` (`Path`):
      The `README.md` written into `root`.
    * `quick_start` (`Path`):
      The `quick_start.py` written into `root`, a copy of `QUICK_START`.
    * `root` (`Path`):
      The cache directory.  Created if it does not exist.

    Constructor:
    * `AltVEnv(root=None)`
    """

    # Set by the constructor; see `Attributes:` above.
    quick_start: Path
    readme: Path
    root: Path
    bootstrap: str = ""

    def __init__(self, root: Path | None = None) -> None:
        """AltVEnv Package Cache.

        This directory holds Python packages that a program needed but
        that the Python installation did not provide.  A small
        bootstrap, pasted into the top of that program, fetched them
        and put them on `sys.path`.

        Nothing here is managed by the system package manager, and
        nothing here is a virtual environment despite the name.  It is
        an ordinary directory of installed packages.

        What is in it:

        * `versions/` holds one directory per package version, named
          after the wheel it came from, so two programs wanting two
          versions of the same package each get their own.  These are
          the directories that go on `sys.path`.
        * `wheels/` keeps the downloaded wheels themselves.
        * `requests/` records what was asked for, one small file per
          request, so that asking again costs nothing.
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
        * `quick_start.py` is a complete program that uses `AltVEnv`.
          Copy its parts into a program of your own; the comments in
          it say which part is which.  It is the copy that came with
          the `alt_venv` installed here, so after a new release the
          one in the project's `README.md` may be newer.

        Deleting this whole directory is safe.  The next program that
        needs one of these packages will fetch it again.

        A program can say which packages it needs in a PEP 723 block at
        its top, and can carry a `.altvenv` file beside it recording
        which exact wheels its author approved.

        Arguments:
        * `root` (`Path | None`):
          The cache directory to use.  `None`, the default, means
          `~/.alt_venv`, which is the directory the bootstrap
          code names.  Tests pass a temporary directory instead.
        """
        # Default to the cache directory that the bootstrap code names.
        self.root = Path.home() / ".alt_venv" if root is None else root
        self.root.mkdir(parents=True, exist_ok=True)

        # The docstring above is the README; the summary line becomes
        # its title.  Docstrings are absent under `python3 -OO`, so
        # fall back to a title only rather than failing.
        document: str | None = inspect.getdoc(AltVEnv.__init__)
        title: str
        body: str
        if document is None:
            title, body = "AltVEnv Package Cache", ""
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

        # Repair a single module install, so that the bootstrap that
        # fetched this one recognises it next time.  See `0cctfd`.
        self.repair_module_layout()

    def repair_module_layout(self) -> Path | None:
        """Rewrite this module inside the cache as a package directory.

        Every case in `bootstrap.py` decides whether it has already
        installed the package by asking `(target / PACKAGE).is_dir()`.
        A distribution that installs as a single module puts
        `alt_venv.py` there rather than a directory, so the answer
        is no on every run and the fetch is repeated forever.  `venv4`
        does worse than waste a download: it deletes the `pip` it
        installed with, so its second run has nothing to install with
        and fails.  This is the `0cctfd` issue in `LOGBOOK.md`.

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

        See Step 6.3.1 in `LOGBOOK.md`.  `pending` holds wheels that
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
        main program, as `prog.py` to `prog.altvenv`, and is meant to be
        committed next to it.

        A program with no file of its own -- the interpreter prompt,
        `python3 -c`, a frozen executable -- has nowhere to keep one and
        gets no verification.  See Step 6.6 in `LOGBOOK.md`.

        Returns:
        * (`Path | None`): Where the approvals are, or `None` when this
          program has no file to put them beside.
        """
        # The main program is what the approvals belong to.
        where: Path | None = main_path()
        if where is None:
            return None
        return where.with_suffix(".altvenv")

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

    def approve(self, wheels: Sequence[Path]) -> Path | None:
        """Record the wheels that arrived as approved.

        Called when `ALT_VENV_APPROVE` is `write`, which is how an
        author regenerates the file after changing what the program
        needs.  Sorted by name, so that a change shows up as a small
        diff in whatever the program is committed to.

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
        record.write_text(
            "# Wheels this program has approved, by SHA-256.  Regenerate\n"
            "# with ALT_VENV_APPROVE=write after changing what it needs.\n"
            + "".join(f"{row}\n" for row in rows))
        return record

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
        archive: zipfile.ZipFile
        text: str = ""
        try:
            with zipfile.ZipFile(wheel) as archive:
                name: str = next(one for one in archive.namelist()
                                 if one.endswith(".dist-info/METADATA"))
                text = archive.read(name).decode("utf8", "replace")
        except (OSError, KeyError, StopIteration, zipfile.BadZipFile):
            return ""
        line: str
        for line in text.splitlines():
            if line.startswith("Summary:"):
                return "".join(one for one in line[8:].strip()
                               if one.isprintable())[:60]
        return ""

    def details(self, wheels: Sequence[Path],
                asking: Sequence[str]) -> list[str]:
        """Describe each wheel, for somebody who typed `?`.

        Separates what was observed from what the package claims about
        itself.  The size and the digest are ours; the origin is the
        index we were pointed at; the summary is the package's own words.

        Arguments:
        * `wheels` (`Sequence[Path]`):
          The wheels that arrived.
        * `asking` (`Sequence[str]`):
          The requirements that were asked for.

        Returns:
        * (`list[str]`): Lines to show, without trailing newlines.
        """
        # Where these came from is a fact; what they say is a claim.
        origin: str = os.environ.get("PIP_INDEX_URL", "the default index")
        wanted: set[str] = {requirement_name(one).replace("-", "_").lower()
                            for one in asking}
        lines: list[str] = [f"fetched from {origin}"]
        wheel: Path
        for wheel in sorted(wheels):
            fields: list[str] = wheel.stem.split("-")
            asked: str = ("asked for" if fields[0].lower() in wanted
                          else "came along")
            told: str = self.summary(wheel) or "(says nothing about itself)"
            lines.append(f"  {fields[0]} {fields[1]}, {asked}, "
                         f"{wheel.stat().st_size / 1024:.1f} KB")
            lines.append(f"    it says: {told}")
            lines.append(f"    sha256:  {self.digest(wheel)}")
        return lines

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

        Returns:
        * (`tuple[IO[str], IO[str]] | None`): The terminal open for
          writing and for reading, or `None` when there is not one.
        """
        # Whether it opens is the whole of the question.
        try:
            return (Path("/dev/tty").open("w", encoding="utf-8"),
                    Path("/dev/tty").open("r", encoding="utf-8"))
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

        `y` or `yes` goes ahead once; `n`, `no` or a bare newline
        declines; `?` describes each wheel and asks again; `a` or
        `always` stops the question being asked at all, and is the one
        answer that asks for confirmation first, because it is the only
        one that outlives this run.  Declining that confirmation returns
        to the question rather than cancelling the install, and counts as
        an attempt so that the pair cannot loop for ever.

        Anything else is taken for a typo and the question is put again,
        up to `ATTEMPTS` typos.  Asking for the detail is not a typo and
        does not count, so curiosity is never punished.  A terminal that
        has gone away reads as empty, which
        declines at once rather than being asked again forever.

        With no terminal there is nobody to ask, and the answer is yes:
        the list has already been printed, and failing instead would
        break every program run from `cron` or a build on the first day.
        A guarantee rather than a notification is what the approvals file
        is for; see Step 6.6.

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

        # `y` goes ahead, `n` or an empty line declines, `?` says more
        # and asks again, and anything else is a typo worth asking about
        # again.  Only typos are counted, so that reading the detail can
        # never use up the patience meant for mistakes.
        answer: str
        confirm: str
        typos: int = 0
        writer: IO[str]
        reader: IO[str]
        writer, reader = opened
        with writer, reader:
            while typos < ATTEMPTS:
                writer.write(f"{len(asking)} requested, {len(wheels)} to "
                             f"install into {self.root};\n"
                             f"go ahead? "
                             f"[y=>Yes/n=>No/a=>Always/?=>Explanation] ")
                writer.flush()
                answer = reader.readline()

                # An empty read is the terminal going away, not an
                # answer, and asking again would never end.
                if not answer:
                    return False
                answer = answer.strip().lower()
                if answer in ("y", "yes"):
                    return True
                if answer in ("", "n", "no"):
                    return False
                if answer in ("a", "always"):
                    # The only answer that outlives this run, so it is
                    # the only one asked about twice.
                    writer.write("Really never ask again? [y=>Yes/n=>No] ")
                    writer.flush()
                    confirm = reader.readline()
                    if not confirm:
                        return False
                    if confirm.strip().lower() not in ("y", "yes"):
                        # Not wanting this for ever is not the same as
                        # not wanting it now, so the question comes back.
                        # Counted, so that the pair cannot loop for ever.
                        typos += 1
                        continue

                    # A permanent decision deserves a visible way back,
                    # and the command that gives it.
                    marker: Path = self.forever()
                    marker.write_text(
                        "This file means: do not ask again before "
                        "installing packages\ninto this directory.  "
                        "Delete it to be asked again.\n",
                        encoding="utf-8")
                    removal: str = (f"rmdir /s /q {self.root}"
                                    if os.name == "nt"
                                    else f"rm -rf {self.root}")
                    writer.write(
                        f"\nFrom now on packages will be downloaded "
                        f"silently into\n{self.root}.\n"
                        f"To be asked again, delete\n{marker}.\n"
                        f"It is ALWAYS safe to delete the whole "
                        f"directory as well, which costs\nonly a "
                        f"download:\n    {removal}\n\n")
                    return True
                if answer == "?":
                    writer.write("\n" + "\n".join(
                        self.details(wheels, asking)) + "\n")
                    continue
                typos += 1
                writer.write(
                    "Please answer y, n, a for always, or ? for more.\n")
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
        asked once per cache.  See Step 6.10 in `LOGBOOK.md`.

        Returns:
        * (`Path`): The marker, whether or not it exists.
        """
        # One file, named so that somebody listing the directory can
        # guess what it does without reading anything else.
        return self.root / "FOREVER_APPROVE"

    def gate(self, wheels: Sequence[Path],
             asking: Sequence[str] = ()) -> None:
        """Write, skip, enforce or ask, as the environment says.

        `ALT_VENV_APPROVE` unset enforces the approvals or asks when
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

        Arguments:
        * `wheels` (`Sequence[Path]`):
          The wheels to record or to check.
        * `asking` (`Sequence[str]`):
          The requirements that were asked for, for the question.

        Raises:
        * `RuntimeError`:
          Through `verify`, if a wheel is unapproved or altered, or if
          the person asked declines.
        """
        # One place decides, so the cold and warm paths cannot diverge.
        mode: str = os.environ.get("ALT_VENV_APPROVE", "").lower()
        if mode == "write":
            # A program with no file has nowhere to keep approvals, and
            # saying "written to None" would claim otherwise.
            written: Path | None = self.approve(wheels)
            if written is None:
                print("nowhere to write approvals: this program has no "
                      "file of its own", file=sys.stderr)
            else:
                print(f"approvals written to {written}", file=sys.stderr)
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
        if self.forever().is_file():
            return
        if not self.consent(wheels, asking):
            raise RuntimeError(
                f"declined: nothing was installed into {self.root}")

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
                    f"ALT_VENV_APPROVE=write if it should be")
            if expected[wheel.name] != actual:
                raise RuntimeError(
                    f"{wheel.name} does not match its approval in "
                    f"{self.approvals()}: expected "
                    f"{expected[wheel.name]}, got {actual}")

    def announce(self, wheels: Sequence[Path],
                 asking: Sequence[str]) -> None:
        """Say what arrived, separating what was asked for from the rest.

        Written to standard error, never to standard output, because a
        library that writes to standard output corrupts the output of
        any program whose own output is piped or parsed.

        Nothing from the index is printed: not a summary, not a page
        title.  Those are written by whoever uploaded the package, so a
        typosquat's read exactly like the real thing, and index text can
        carry escape sequences that rewrite the terminal.  Only the
        filename, which the wheel specification fixes, and our own
        digest of it.

        Arguments:
        * `wheels` (`Sequence[Path]`):
          The wheels that arrived.
        * `asking` (`Sequence[str]`):
          The requirements that were asked for.
        """
        # Which of these were asked for, and which merely came along?
        wanted: set[str] = {requirement_name(one).replace("-", "_").lower()
                            for one in asking}
        lines: list[str] = []
        wheel: Path
        for wheel in sorted(wheels):
            fields: list[str] = wheel.stem.split("-")
            asked: str = ("asked for" if fields[0].lower() in wanted
                          else "came along")
            lines.append(f"  {fields[0]} {fields[1]}  {asked}")
        print(f"{len(asking)} requested, {len(wheels)} downloaded into "
              f"{self.root}:", file=sys.stderr)
        print("\n".join(lines), file=sys.stderr)

    def digest(self, wheel: Path) -> str:
        """Return the SHA-256 of a wheel, as hexadecimal.

        The hash is of the file that arrived, not of whatever the index
        claimed, which is the better of the two and the only one
        available: `pip download` does not accept `--report`.  See Step
        6.3.7 in `LOGBOOK.md`.  This is the identity Step 6.6 approves,
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
        distribution and version, which is what `0nicav` is about: the
        same directory reached by a different Python would otherwise
        load a shared object built for something else.  It cannot tell
        musl from glibc, which is the blind spot of `2wtmifs`.

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
        See issue `3spinu` in `LOGBOOK.md`.

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
                 argv: Sequence[str] = ()) -> list[Path]:
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
        # See Step 6.17.7 in `LOGBOOK.md`.
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [*self.pip(), "download", "--retries", "1",
             "--no-input", "--disable-pip-version-check",
             "--only-binary", ":all:", *argv, "--dest", str(holding),
             *requirements],
            capture_output=True, text=True, check=False)
        if done.returncode == 2:
            raise ValueError(
                f"pip rejected the command line: "
                f"{done.stderr.strip() or 'pip gave no reason'}")
        if done.returncode != 0:
            raise RuntimeError(
                f"could not fetch {', '.join(requirements)} into "
                f"{holding}: "
                f"{done.stderr.strip() or 'pip gave no reason'}")
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
        see Step 6.3.12.

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
        # handled and are deliberately left where they are; see Step
        # 6.3.12 in `LOGBOOK.md`.
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
        # which is what Step 6.6 approves.
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
        name: str | None = BOOTSTRAPS.get(bootstrap_fingerprint(block))
        if name is None:
            return "edited", ""
        newest: str = list(BOOTSTRAPS.values())[-1]
        return ("current" if name == newest else "stale"), name

    def report_bootstrap(self) -> str:
        """Describe the program's pasted bootstrap in one line.

        Silent by default; `install` prints this only when
        `ALT_VENV_BOOTSTRAP=check` asks, because the person running a
        program cannot act on it and its author can ask.  See Step 6.12.2
        in `LOGBOOK.md`.

        Returns:
        * (`str`): The line, for standard error.
        """
        # One sentence per state.
        state: str
        name: str
        state, name = self.bootstrap_status()
        newest: str = list(BOOTSTRAPS.values())[-1]
        if state == "current":
            return f"alt_venv: this program's bootstrap is current, {name}"
        if state == "stale":
            return (f"alt_venv: this program's bootstrap is stale, {name}; "
                    f"the current one is {newest}")
        if state == "edited":
            return ("alt_venv: this program's bootstrap has been edited, "
                    "or is not one alt_venv published")
        return "alt_venv: no bootstrap found in this program"

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
        see Step 6.7.8 in `LOGBOOK.md`.  A program with no block, or a
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
        succeed.  Anything already in the cache is not fetched again.
        One `pip` is run for the whole set rather than one per package,
        so `pip` resolves them together and can notice a conflict that
        installing them separately would hide.

        The name says `install` rather than something friendlier
        because that is what happens: `pip install`, against an index
        anybody can publish to.  See `README.md`.

        `pip` runs as a child process rather than through
        `pip._internal`, which is not a public interface, and which
        leaves its logging handlers on the root logger of whatever
        imports it.

        `ALT_VENV_APPROVE` decides what happens to what arrives.  Unset,
        each wheel is checked against the approvals file beside the
        program and a mismatch is refused.  `write` records what arrived
        instead of checking it, which is how an author regenerates the
        file.  `skip` checks nothing, which is for an author still
        deciding what the program needs.  A program with no approvals
        file is told what arrived and not asked about it; see Step 6.6.

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
          names itself -- `"nopip3"` for the one that ships.  Kept on
          the instance as `self.bootstrap` and **read by nothing yet**:
          Step 6.12 wants to notice a pasted bootstrap that has gone
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
          that rather than left with an import error.
        * `ModuleNotFoundError`:
          If `pip` succeeds but a package still will not import, which
          means its import name was guessed wrongly and wants the pair
          form.  The no-argument form imports nothing and so cannot
          raise it.
        """
        # Remembered for Step 6.12, which has not been written yet.
        self.bootstrap = bootstrap

        # Say whether the pasted bootstrap is current, but only when the
        # author asks; see Step 6.12.
        if os.environ.get("ALT_VENV_BOOTSTRAP", "").lower() == "check":
            print(self.report_bootstrap(), file=sys.stderr)

        # No arguments means whatever the program declared.  The
        # interpreter is checked first, because a program on the wrong
        # Python should be told that rather than handed packages.
        if requirements is None:
            declaration: dict[str, Any] = self.declaration()
            self.check_python(declaration)
            self.provide(self.declared(), argv)
            return None

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
        self.provide(asking, argv)
        modules: list[ModuleType] = [importlib.import_module(name)
                                     for name in names]
        return modules[0] if single else modules

    def declaration(self) -> dict[str, Any]:
        """Return the running program's PEP 723 declaration.

        The block is in the program's source text, which `main_source`
        supplies; see Steps 6.7.2 and 6.7.7 in `LOGBOOK.md`.  Two callers
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
          Step 6.1.
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

    def provide(self, asking: list[str],
                argv: Sequence[str] = ()) -> None:
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

        Raises:
        * `ValueError`:
          If a requirement reads as an option, or if `pip` exits 2.
        * `RuntimeError`:
          If `pip` fails for any other reason.
        """
        # Nothing asked for is nothing to do, and no `pip` to run.
        if not asking:
            return

        # A good moment to sweep: something is about to be fetched, so a
        # little work here is invisible beside a download, and anything
        # this program is about to create is younger than the grace
        # period and so cannot be swept by mistake.  The same reasoning
        # makes it the moment to see whether `pip` has moved on.
        if self.due():
            self.cull()
        self.refresh_pip()

        # Refuse the one thing `pip` would accept and should not: a
        # leading dash reads as an option, so `install("--index-url=")`
        # could aim the fetch at somebody else's index.  Requirement
        # syntax is not checked here, because `pip` owns PEP 508 and
        # rejects a malformed one locally in half a second without
        # touching the network.  See Step 6.2.4 in `LOGBOOK.md`.
        requirement: str
        for requirement in asking:
            if requirement.startswith("-"):
                raise ValueError(
                    f"requirement reads as an option: {requirement!r}")

        # A request answered before is answered from the cache, keyed by
        # what was asked rather than by what it resolved to; see Step
        # 6.3.4.  No version expression is compared, so no PEP 440
        # parser is needed and none can disagree with `pip`.
        request: str = " ".join(sorted(asking))
        remembered: tuple[list[str], list[str]] | None = (
            self.remember(request))
        trees: list[Path]
        if remembered is None:
            arrived: list[Path] = self.download(asking, argv)
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
                    return

                # Say what turned up, then check it against what the
                # author approved, and only then unpack.  Nothing in a
                # wheel has run at the moment it is refused; see 6.6.
                self.announce(arrived, asking)
                self.gate(arrived, asking)

                trees = [self.unpack(wheel) for wheel in arrived]
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
            trees = [self.paths()[2] / key for key in remembered[0]]

            # A warm cache fetches nothing, so there is nothing new to
            # approve or refuse.  Verification belongs to the moment of
            # fetching: somebody who can rewrite the cache can rewrite
            # the program too, so that is not the threat this defends
            # against.  But an author regenerating the approvals must
            # not have to empty the cache first, so `write` still works.
            if os.environ.get("ALT_VENV_APPROVE", "").lower() == "write":
                kept: Path = self.paths()[1]
                self.gate([kept / name for name in remembered[1]])

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
        # happens only for a wheel the gate already approved; see Step
        # 6.9 in `LOGBOOK.md`.  The guard matters for a second reason
        # now: running the same `.pth` twice in one process would run
        # its import line twice.
        tree: Path
        for tree in trees:
            if str(tree) not in sys.path:
                sys.path.insert(0, str(tree))
                site.addsitedir(str(tree))
        importlib.invalidate_caches()

    def litter(self, grace: float = CULL_GRACE) -> list[Path]:
        """Return what is in the cache that nothing can reach.

        Three kinds, none of which needs a policy to identify.  A
        program killed while fetching or unpacking leaves a directory
        under `pending/`, which is staging space and never on the import
        path.  A tree in `versions/` that no request record names is
        unreachable too: `install` finds trees through those records, so
        a tree nothing names will never be found again.  And a wheel in
        `wheels/` that no record names is in the same position, since the
        only thing that ever looks at a kept wheel is
        `ALT_VENV_APPROVE=write` working from a record.

        A live record protects its wheels, which is what keeps that
        author flow working: an author can still regenerate approvals
        from a warm cache without emptying it first.  A record that has
        aged out takes its wheels with it, which is what stops `wheels/`
        being the one directory that grows for ever.

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
        """Return the request records nothing has used for a long time.

        A record's modification time is when its request was last
        answered, because `remember` touches it on every hit, warm or
        cold.  So age here means *unused*, not merely *old*, which is the
        distinction that matters: a package fetched two years ago and
        used this morning is not stale.

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
        for record in self.paths()[3].glob("*.json"):
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
        garbage for Step 6.11 to cull.

        The request is stored inside the file as well as hashed into its
        name, so that a record can be read by a person and so that a
        hash collision cannot be mistaken for a hit.  A remembered
        request whose trees have since been deleted counts as a miss,
        because the cache is meant to be safe to delete.

        Arguments:
        * `request` (`str`):
          The requirements, sorted and joined, as `install` builds them.
        * `trees` (`list[str] | None`):
          The version directory names to record.  `None`, the default,
          reads instead of writing.
        * `wheels` (`list[str] | None`):
          The wheel filenames those trees came from, recorded so that
          `ALT_VENV_APPROVE=write` can regenerate the approvals from a
          warm cache instead of demanding an empty one.

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
        it is not in the cache at all; see Step 6.3.1 in `LOGBOOK.md`.

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
