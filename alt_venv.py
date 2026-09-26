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
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

# The one place the version is written down.  `bootstrap.py`
# prints it after importing, and the test suite stamps it into
# the wheel it builds.
__version__: str = "0.0.1"


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

    def include(self, package: str, argv: Sequence[str] = (),
                distribution: str | None = None) -> ModuleType:
        """Make a package importable, fetching it if it is missing.

        The package is installed into the cache directory with
        `pip install --target`, which needs no virtual environment,
        and the cache directory is then put on `sys.path` so that the
        import succeeds.  A package already in the cache is not
        fetched again.

        `pip` runs as a child process rather than through
        `pip._internal`, which is not a public interface, and which
        leaves its logging handlers on the root logger of whatever
        imports it.

        Arguments:
        * `package` (`str`):
          The import name: what `import` is given afterwards, and
          what the cache is checked for.
        * `argv` (`Sequence[str]`):
          Extra arguments for `pip install`, such as a version
          specifier or `--no-deps`.  They follow this method's own
          arguments, so `pip` lets them win where it takes the last
          of a repeated option.
        * `distribution` (`str | None`):
          What to ask `pip` for, when that differs from the import
          name.  `None`, the default, means they are the same, which
          covers most packages and all of the ones this project
          builds.  They part company often enough to matter, though:
          `python-dateutil` imports as `dateutil`, and
          `typing-extensions` as `typing_extensions`.  `pip`
          normalizes punctuation, so only a real difference needs
          this.

        Returns:
        * (`ModuleType`): The imported module.

        Raises:
        * `RuntimeError`:
          If `pip` fails.  Its standard error is included, because
          the usual cause is no network and the caller deserves to
          be told that rather than left with an import error.
        * `ModuleNotFoundError`:
          If `pip` succeeds but the package still will not import,
          which means `package` is not the import name.
        """
        # A package already in the cache costs nothing but a path
        # insert; see the `2apiia` issue in `LOGBOOK.md`.
        done: subprocess.CompletedProcess[str]
        if not self.contains(package):
            done = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet",
                 "--no-input", "--disable-pip-version-check",
                 *argv, "--target", str(self.root),
                 package if distribution is None else distribution],
                capture_output=True, text=True, check=False)
            if done.returncode != 0:
                raise RuntimeError(
                    f"could not fetch "
                    f"{package if distribution is None else distribution!r}"
                    f" into {self.root}: "
                    f"{done.stderr.strip() or 'pip gave no reason'}")

        # Put the cache on `sys.path` before importing out of it.
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        importlib.invalidate_caches()
        return importlib.import_module(package)

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
