# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
#
# The block above is this project eating its own cooking, and it is the
# one place the Python floor is written down.  See Step 6.7.5 in
# `LOGBOOK.md`: 3.10, because `Path | None` is evaluated at run time and
# `bootstrap.py` uses `match`, and no higher because nothing here needs
# 3.11 or 3.12.  `dependencies` is empty on purpose and says so: a
# project about fetching packages that are not preinstalled has none of
# its own.
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
import hashlib
import importlib
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import zipfile
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import IO, overload

# How many times `AltVEnv.consent` will put the same question, when the
# answer is neither yes nor no.  Bounded, so that a terminal feeding
# nonsense cannot keep a program alive indefinitely.
ATTEMPTS: int = 3

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
    is can read the answer without leaving it.

    Attributes:
    * `readme` (`Path`):
      The `README.md` written into `root`.
    * `root` (`Path`):
      The cache directory.  Created if it does not exist.

    Constructor:
    * `AltVEnv(root=None)`
    """

    # Set by the constructor; see `Attributes:` above.
    readme: Path
    root: Path

    def __init__(self, root: Path | None = None) -> None:
        """AltVEnv Package Cache.

        This directory holds Python packages that a program needed but
        that the Python installation did not provide.  A small
        bootstrap, pasted into the top of that program, fetched them
        and put this directory on `sys.path`.

        Nothing here is managed by the system package manager, and
        nothing here is a virtual environment despite the name.  It is
        an ordinary directory of installed packages.

        Deleting this directory is safe.  The next program that needs
        one of these packages will fetch it again.

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

        # Write it out, replacing any earlier copy.
        self.readme = self.root / "README.md"
        self.readme.write_text(f"# {title}\n{body}\n")

        # Repair a single module install, so that the bootstrap that
        # fetched this one recognises it next time.  See `0cctfd`.
        self.repair_module_layout()

    def repair_module_layout(self) -> Path | None:
        """Rewrite this module inside the cache as a package directory.

        Every case in `bootstrap.py` decides whether it has already
        installed the package by asking `(target / PACKAGE).is_dir()`.
        A distribution that installs as a single module puts
        `alt_venv.py` there rather than a directory, so the answer
        is no on every run and the fetch is repeated forever.  Case 11
        does worse than waste a download: it deletes the `pip` it
        installed with, so its second run has nothing to install with
        and fails.  This is the `0cctfd` issue in `LOGBOOK.md`.

        Rather than edit twelve case bodies that people paste, the
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
        main: ModuleType | None = sys.modules.get("__main__")
        where: str | None = getattr(main, "__file__", None)
        if where is None:
            return None
        return Path(where).resolve().with_suffix(".altvenv")

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

        `y` or `yes` goes ahead; `n`, `no` or a bare newline declines,
        because `[y/N/?]` says the default is no; `?` describes each
        wheel and asks again; anything else is taken for a typo and the
        question is put again, up to `ATTEMPTS` typos.  Asking for the
        detail is not a typo and does not count, so curiosity is never
        punished.  A terminal that has gone away reads as empty, which
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
        typos: int = 0
        writer: IO[str]
        reader: IO[str]
        writer, reader = opened
        with writer, reader:
            while typos < ATTEMPTS:
                writer.write(f"{len(asking)} requested, {len(wheels)} to "
                             f"install into {self.root}; "
                             f"go ahead? [y/N/?] ")
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
                if answer == "?":
                    writer.write("\n" + "\n".join(
                        self.details(wheels, asking)) + "\n")
                    continue
                typos += 1
                writer.write("Please answer y, n, or ? for more.\n")
        return False

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
            print(f"approvals written to {self.approve(wheels)}",
                  file=sys.stderr)
            return
        if mode == "skip":
            return
        if self.approved() is not None:
            self.verify(wheels)
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
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-m", "pip", "download", "--quiet",
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

    @overload
    def install(self, requirements: str,
                argv: Sequence[str] = ()) -> ModuleType: ...

    @overload
    def install(self, requirements: Requirements,
                argv: Sequence[str] = ()) -> list[ModuleType]: ...

    def install(self, requirements: str | Requirements,
                argv: Sequence[str] = ()
                ) -> ModuleType | list[ModuleType]:
        """Install packages if they are missing, and import them.

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
        * `requirements` (`str | Requirements`):
          One requirement, or several.  Each is either a string that
          `pip` accepts, whose import name is taken to be the name with
          any punctuation turned into underscores, or a
          `(import_name, requirement)` pair for when the two differ.
        * `argv` (`Sequence[str]`):
          Extra arguments for `pip install`, such as `--no-deps` or
          `--only-binary`.  They apply to the whole invocation rather
          than to one requirement, and they follow this method's own
          arguments, so `pip` lets them win where it takes the last of
          a repeated option.

        Returns:
        * (`ModuleType | list[ModuleType]`): The imported module when
          `requirements` was a single string, so that
          `cov = v.install("coverage")` reads properly; otherwise one
          module per requirement, in the order given, so that
          `cov, pt = v.install(["coverage", "pytest"])` does.

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
          form.
        """
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

        # Two entries claiming one import name would return a module
        # twice and never mention the other.
        repeated: set[str] = {name for name in names
                              if names.count(name) > 1}
        if repeated:
            raise ValueError("repeated import name: "
                             + ", ".join(sorted(repeated)))

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
        tree: Path
        for tree in trees:
            if str(tree) not in sys.path:
                sys.path.insert(0, str(tree))
        importlib.invalidate_caches()
        modules: list[ModuleType] = [importlib.import_module(name)
                                     for name in names]
        return modules[0] if single else modules

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
        garbage for Step 6.10 to cull.

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
