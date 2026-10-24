#!/usr/bin/env python3
"""The shipping bootstrap, kept as a function the test suite can run.

The bootstrap is the text a program pastes in to fetch `ezpkg` with
nothing preinstalled.  Bootstraps are named by the date they were
published, and the one here, `2026-10-23`, is the only one left.  The
older published texts live on in `ezpkg.py` (`BOOTSTRAPS` and
`OLD_BOOTSTRAP_TEXTS`) for the tests of a stale copy.

`MECHANISMS` maps each bootstrap's name to its function.  A function's
body below its docstring is exactly what is pasted, except that two
names let the test suite steer it through the environment without
editing it: `PACKAGE` (`BOOTSTRAP_PACKAGE`) is `ezpkg` once pasted,
and `JSON_API` (`BOOTSTRAP_JSON_API`) is `https://pypi.org/pypi`.
`pasted` renders a body the way a person pastes it, and the suite
checks that its fingerprint matches `BOOTSTRAPS`, `QUICK_START`,
`quick_start.py` and `README.md`.  So the body must never change: a
changed bootstrap is a new one, with a new date.

`python3 bootstrap.py NAME` runs one bootstrap in a fresh interpreter,
which is how the test suite and `ezpkg_coverage.py` use it; it is not
a way to use `ezpkg`.  The suite sets `EZPKG_BOOTSTRAP=unchecked`, since
a body that spells `PACKAGE` and `JSON_API` as variables differs from
the published text, and `EZPkg` would refuse it (`T.reb`).

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
import os
import pathlib
import sys
from collections.abc import Callable

# The package the bootstrap fetches.  A pasted copy spells `ezpkg`; the
# test suite steers this one at its own index instead.
PACKAGE: str = os.environ.get("BOOTSTRAP_PACKAGE", "ezpkg")

# Where the bootstrap looks for PyPI's JSON API, steered the same way.
JSON_API: str = os.environ.get("BOOTSTRAP_JSON_API",
                               "https://pypi.org/pypi")


def bootstrap_2026_10_23() -> None:
    """Fetch `ezpkg`'s wheel, import straight from it, and install.

    The bootstrap `2026-10-23`, the first published.  An `ezpkg` that is
    already importable is used as it is.  Otherwise the newest `ezpkg`
    wheel the JSON API names is fetched (with `curl` when this Python
    has no certificates, `I.btosc`), checked against its SHA-256, kept
    as `~/.ezpkg/ezpkg.whl` and imported from there, since `ezpkg` is
    pure Python.  `EZPkg.own_pip` fetches a `pip` later (`T.abfd`).

    The body is squeezed on purpose, short statements sharing a line
    (`E702`, allowed for this file in `ruff.toml`), so that it is short
    enough to paste without hesitation.

    Raises:
    * `SystemExit`:
      If any step fails, with one line saying what failed and why.
    """
    # Ensure `ezpkg` is downloaded.
    import hashlib
    import json
    import subprocess
    import urllib.request as req
    try:  # Do not edit try block!  See https://pypi.org/project/ezpkg/
        s = f"find {PACKAGE}"; t = pathlib.Path.home()/".ezpkg"; w = t/f"{PACKAGE}.whl"
        def g(u):  # Fetch u, with curl if this Python has no certificates.
            try: return req.urlopen(u, None, 60).read()
            except req.URLError as y: z = y  # As on python.org's macOS Python.
            try: return subprocess.run(["curl", "-fsSL", u],
                                       capture_output=True, check=True).stdout
            except Exception: raise z from None
        try: m = None; m = importlib.import_module(PACKAGE)  # Already importable?
        except ImportError: pass
        if m is None and not w.is_file():  # Not downloaded yet.
            s = f"download {PACKAGE}"; d = g(f"{JSON_API}/{PACKAGE}/json")
            e = next(e for e in json.loads(d)["urls"] if e["url"][-4:] == ".whl")
            r = g(e["url"])
            if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
                raise ValueError(f"{e['filename']} fails its SHA-256 check")
            t.mkdir(parents=True, exist_ok=True); p = t/f"{PACKAGE}.part"
            p.write_bytes(r); p.replace(w)  # The rename is atomic.
        if m is None:  # Python imports it straight from the wheel.
            s = f"import {PACKAGE}"; sys.path.insert(0, str(w))
            m = importlib.import_module(PACKAGE)
        s = "fetch packages"; m.EZPkg().install(bootstrap="2026-10-23")
    except Exception as x:
        raise SystemExit(f"{PACKAGE}: {s} failed: {x!r}")  # Do not edit try block!


# Each bootstrap's published name, and the function that holds its text.
MECHANISMS: dict[str, Callable[[], None]] = {
    "2026-10-23": bootstrap_2026_10_23,
}


def pasted(label: str) -> str:
    """Return a bootstrap exactly as a person pastes it into a program.

    The function's body below its docstring, one level shallower, with
    the two names that exist only so the harness can be steered spelled
    out the way a pasted copy carries them: `PACKAGE` as `"ezpkg"`
    and `JSON_API` as `https://pypi.org/pypi`.  An f-string left with
    nothing to substitute becomes a plain string, as it would be
    written by hand.  This is the text `T.fbanwiis` fingerprints.

    Arguments:
    * `label` (`str`):
      The bootstrap's name in `MECHANISMS`, such as `2026-10-23`.

    Returns:
    * (`str`): The pasted text, ending in a newline.
    """
    import ast
    import re
    import textwrap
    name: str = MECHANISMS[label].__name__
    source: str = pathlib.Path(__file__).read_text()
    node: ast.FunctionDef = next(
        n for n in ast.parse(source).body
        if isinstance(n, ast.FunctionDef) and n.name == name)
    lines: list[str] = (
        source.splitlines()[node.body[1].lineno - 2:node.end_lineno])
    text: str = textwrap.dedent("\n".join(lines)) + "\n"
    text = text.replace("{JSON_API}", "https://pypi.org/pypi")
    text = text.replace("{PACKAGE}", "ezpkg")
    text = re.sub(r"\bPACKAGE\b", '"ezpkg"', text)
    return re.sub(r'\bf"([^"{}]*)"', r'"\1"', text)


def main(label: str) -> None:
    """Run the bootstrap named `label`, then say what it imported.

    The package is read back out of `sys.modules`, since the body binds
    its names for the program it is pasted into rather than for this
    one.  The closing `print` is what the test suite checks.

    Arguments:
    * `label` (`str`):
      The bootstrap's name in `MECHANISMS`.

    Raises:
    * `SystemExit`:
      If the bootstrap fails, with the one line its `except` wrote.
    """
    # Run it, then find the package it left behind.
    MECHANISMS[label]()
    module = sys.modules[PACKAGE]

    # `type(sys)` is `types.ModuleType`, reached without importing
    # `types`, because `sys` is a module and is already imported.
    assert isinstance(module, type(sys)), f"{PACKAGE} gave {module!r}"
    print(f"{PACKAGE}: module {module.__name__} "
          f"version {module.__version__} from {module.__file__}")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] in MECHANISMS:
        main(sys.argv[1])           # internal: one bootstrap, one process
    else:
        sys.exit(f"usage: {sys.argv[0]} NAME, where NAME is one of "
                 f"{', '.join(MECHANISMS)}")
