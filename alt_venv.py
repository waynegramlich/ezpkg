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
        remembered: list[str] | None = self.remember(request)
        trees: list[Path]
        if remembered is None:
            arrived: list[Path] = self.download(asking, argv)
            trees = [self.unpack(wheel) for wheel in arrived]
            self.remember(request, [tree.name for tree in trees])

            # The holding directory has served its purpose once every
            # wheel in it is either kept or already unpacked.
            holding: Path
            for holding in {wheel.parent for wheel in arrived}:
                shutil.rmtree(holding, ignore_errors=True)
        else:
            trees = [self.root / "versions" / key for key in remembered]

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

    def remember(self, request: str,
                 trees: list[str] | None = None) -> list[str] | None:
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

        Returns:
        * (`list[str] | None`): What the request resolved to, or `None`
          when it is unknown, when its trees are gone, or when this call
          was a write.
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
                json.dump({"request": request, "trees": trees}, opened,
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
        versions: Path = self.paths()[2]
        if known.get("request") != request or not isinstance(found, list):
            return None
        if not all(isinstance(key, str) and (versions / key).is_dir()
                   for key in found):
            return None
        return [str(key) for key in found]

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
