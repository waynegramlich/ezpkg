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

import importlib
import inspect
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import overload

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
        package: Path = module.parent / module.stem
        package.mkdir(exist_ok=True)
        (package / "__init__.py").write_bytes(module.read_bytes())
        module.unlink()
        return package

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

        # Fetch only what is missing, in one `pip` for the whole set;
        # see the `2apiia` issue in `LOGBOOK.md`.
        missing: list[str] = [requirement for name, requirement
                              in zip(names, asking, strict=True)
                              if not self.contains(name)]
        done: subprocess.CompletedProcess[str]
        if missing:
            done = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet",
                 "--no-input", "--disable-pip-version-check",
                 *argv, "--target", str(self.root), *missing],
                capture_output=True, text=True, check=False)
            if done.returncode == 2:
                raise ValueError(
                    f"pip rejected the command line: "
                    f"{done.stderr.strip() or 'pip gave no reason'}")
            if done.returncode != 0:
                raise RuntimeError(
                    f"could not fetch {', '.join(missing)} into "
                    f"{self.root}: "
                    f"{done.stderr.strip() or 'pip gave no reason'}")

        # Put the cache on `sys.path` before importing out of it.
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        importlib.invalidate_caches()
        modules: list[ModuleType] = [importlib.import_module(name)
                                     for name in names]
        return modules[0] if single else modules

    def contains(self, package: str) -> bool:
        """Report whether a package is already in the cache.

        A package arrives either as a directory or as a single
        module, so both spellings count.

        Arguments:
        * `package` (`str`):
          The import name to look for.

        Returns:
        * (`bool`): True if the cache already holds it.
        """
        # Either spelling means there is nothing to fetch.
        return ((self.root / package).is_dir()
                or (self.root / f"{package}.py").is_file())
