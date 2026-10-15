#!/usr/bin/env python3
"""Test framework for `ezpkg.py`.

This module is the test half of Experiment 2.  The experiment is a
pipeline rather than a set of alternatives -- publish a package to a
local index, fetch it with the bootstrap stub, and import it -- so
`EZPkgTest` is shaped around building and discarding that index
rather than around a table of measurements.

The index is a [PEP 503](https://peps.python.org/pep-0503/) directory
tree, published over HTTP by `serve_index` so that `pip` reaches it
through a socket rather than reading the files directly.  5.1 of `T.rps`
settled that `http.server` is enough for this; a third party package
server would have cost between 4 and 43 dependencies and given the
tests nothing they do not already have.

Three helpers here do the publishing half, using nothing but the
standard library.  `build_wheel` turns a single module into a pure
Python wheel, `build_index` lays those wheels out as a PEP 503 tree,
and `serve_index` serves that tree.  None of them needs `build`,
`twine` or `setuptools`, which keeps the test suite as dependency free
as the thing it tests.

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

import _csv
import base64
import contextlib
import csv
import datetime
import functools
import hashlib
import html
import http.server
import importlib
import importlib.metadata
import inspect
import io
import json
import os
import pickle
import pty
import re
import shutil
import ssl
import subprocess
import sys
import sysconfig
import tempfile
import textwrap
import threading
import time
import tomllib
import trace
import unittest
import unittest.mock
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path, PurePath
from types import ModuleType
from typing import IO, Any, TypeVar, cast

import bootstrap
import ezpkg
import ezpkg_coverage

# The version and the summary come from the module, so each is written
# down once: the summary is the first line of its docstring, and is what
# PyPI shows under the name.
DISTRIBUTION: str = "ezpkg"
MODULE: str = "ezpkg"
VERSION: str = ezpkg.__version__
SUMMARY: str = (ezpkg.__doc__ or "").splitlines()[0]

# Whether `I.wtmifs` shows on this interpreter.  `cryptography`, the
# package its test fetches, publishes a `cp311-abi3` wheel, which the
# matcher finds by exact tag under 3.11; from 3.12 on there is no exact
# tag to find, and the gap the test documents appears.
ABI3_GAP: bool = sys.version_info >= (3, 12)

# The distribution name for a rehearsal upload, which is deliberately
# not `ezpkg` and deliberately not `ezpkg_test` either: the second
# is this file's own module name, and a published module spelled that way
# would shadow this suite whenever a cache went on `sys.path` in front of
# the project.  Spelled with an underscore so that one word serves as the
# `pip` name and the import name at once, which is what `bootstrap.py`'s
# single `PACKAGE` needs.  See 6.17.2 of `T.ffrp`.
RELEASE_DISTRIBUTION: str = "ezpkg_trial"


def floor() -> str:
    """Return the Python floor `ezpkg.py` declares for itself.

    Read out of that file's own PEP 723 block, with our own parser, so
    that the floor is written down once and the dogfooding of 6.7.5 of `T.p7i`
    has a consequence: break the parser or the block and the wheels stop
    claiming the right `Requires-Python`.  See 6.7.9 of `T.p7i`.

    Returns:
    * (`str`): The specifier, such as `>=3.11`.

    Raises:
    * `AssertionError`:
      If the block or its `requires-python` has gone missing, which is
      a broken `ezpkg.py` rather than a broken test.
    """
    # Read from disk; the block is a comment and is gone at run time.
    source: Path = Path(__file__).resolve().parent / f"{MODULE}.py"
    metadata: dict[str, Any] | None = ezpkg.script_metadata(
        source.read_text(encoding="utf-8"))
    assert metadata is not None, f"{source} has no PEP 723 block"
    stated: object = metadata.get("requires-python")
    assert isinstance(stated, str), f"{source} declares no requires-python"
    return stated


# The lowest Python `ezpkg.py` runs on, written into the wheel as
# `Requires-Python`.  It is 3.11 because `tomllib` reads the PEP 723
# block and arrived in 3.11; the language features used need only 3.10.
# See 6.7.4 and 6.7.7 of `T.p7i`.
FLOOR: str = floor()

# The consent question, spelled once here so that changing the wording in
# `ezpkg.py` fails in one obvious place rather than in six.
PROMPT: str = "go ahead? [y=>Yes/n=>No/a=>Always/?=>Explanation]"
CONFIRM: str = "Really never ask again? [y=>Yes/n=>No]"

# The case that ships: `nopip5` uses an `ezpkg` that is already
# importable, and otherwise fetches a `pip` of its own and runs it as a
# subprocess, with its output on standard error, so it needs no `pip`
# on the machine and leaves none of `pip`'s state in the program.  See
# `T.npp`, `T.ewar` and `T.rp`.
SHIPPING: str = "nopip5"

# Which cases the all-case tests exercise by default.  The first cull
# found that only the four needing no `pip` add anything to coverage
# (6.16.3 of `T.tsc`), and the cull of 2026-10-12 that `nopip2` and `nopip3`
# add nothing beyond `nopip1` and `nopip4`, so those two went too
# (Wayne).  `nopip5`, which ships, took `nopip4`'s place in 2026-10-12's
# rename, being the same code with `pip`'s output on standard error.
# The others are kept, because keeping them costs nothing, and run
# under `EZPKG_TEST=COMPLETE`; a test that names a case of its own
# still runs it.
FAST_CASES: tuple[str, ...] = ("nopip1", "nopip5")

def platform_tag() -> str:
    """Return a compatibility tag this interpreter would accept.

    Built from the running interpreter rather than written down, so the
    wheel it names is one `pip` will install and one the matcher in
    `nopip1` and `nopip2` of `bootstrap.py` will recognise: that matcher looks
    for `cp312-cp312-`, then for the machine name and `linux` in the
    same filename.

    Returns:
    * (`str`): Something like `cp312-cp312-linux_x86_64`.
    """
    # A wheel filename may not contain a hyphen inside a field.
    release: str = f"{sys.version_info.major}{sys.version_info.minor}"
    implementation: str = ("cp" if sys.implementation.name == "cpython"
                           else "py")
    machine: str = sysconfig.get_platform().replace("-", "_")
    machine = machine.replace(".", "_")
    return f"{implementation}{release}-{implementation}{release}-{machine}"


# How long the `slow` fault waits.  Long enough that several processes
# fetching at once overlap, short enough not to lengthen the suite.
SLOW_SECONDS: float = 0.4

# How long the `hang` fault waits.  Longer than the client timeouts the
# failure tests set, and short enough not to slow the suite down.
HANG_SECONDS: float = 3.0


def cases() -> tuple[str, ...]:
    """Return the case labels the all-case tests should exercise.

    `EZPKG_TEST` chooses.  Unset or `FAST`, which is the usual
    way to run, gives `FAST_CASES`.  `COMPLETE` gives every case
    `bootstrap.py` defines, which is thorough and slow.  Anything else
    is read as case names separated by commas, such as `venv3` or
    `pip1,pip2`, which is how `ezpkg_coverage.py --per-case` runs
    the suite once per case.  Names are case sensitive, as the
    `case` labels in `bootstrap.py` are.  `NONE` gives no cases at
    all, which is that tool's baseline: everything the suite covers
    without running a single bootstrap.

    Returns:
    * (`tuple[str, ...]`): The labels, in `bootstrap.py` order.

    Raises:
    * `ValueError`:
      If `EZPKG_TEST` names something that is neither a choice nor
      a case, because a typo that silently ran the fast tests would be
      worse than a refusal.
    """
    # The two choices first, then a list of names.
    choice: str = os.environ.get("EZPKG_TEST", "FAST")
    if choice.upper() == "FAST":
        return FAST_CASES
    if choice.upper() == "COMPLETE":
        return tuple(bootstrap.MECHANISMS)
    if choice.upper() == "NONE":
        return ()
    named: set[str] = {name.strip() for name in choice.split(",")}
    unknown: list[str] = sorted(named - set(bootstrap.MECHANISMS))
    if unknown:
        raise ValueError(
            f"EZPKG_TEST is {choice!r}; use FAST, COMPLETE, NONE or "
            f"case names from bootstrap.py, and {', '.join(unknown)} is "
            f"none of them")
    return tuple(label for label in bootstrap.MECHANISMS if label in named)


def selected(*labels: str) -> tuple[str, ...]:
    """Return which of `labels` a test that names its cases may run.

    Most tests that run a case take theirs from `cases`.  A few cannot,
    because they exist for one particular case: the matcher belongs to
    `nopip1` and `nopip2`, and the no-`pip` test to `nopip3`.  Under
    `FAST` and `COMPLETE` they run regardless, as they always have.
    When `EZPKG_TEST` names cases, they run only for those, so that
    a per-case coverage run measures that case and not these as well.

    Arguments:
    * `labels` (`str`):
      The cases the test is written for.

    Returns:
    * (`tuple[str, ...]`): Those of `labels` to run, possibly none.
    """
    # Named cases narrow the set; the two choices leave it alone.
    choice: str = os.environ.get("EZPKG_TEST", "FAST")
    if choice.upper() in ("FAST", "COMPLETE"):
        return labels
    chosen: tuple[str, ...] = cases()
    return tuple(label for label in labels if label in chosen)


# Anything a decorator can be applied to and hand back unchanged.
Marked = TypeVar("Marked", bound=Callable[..., Any])


def runs_cases(test: Marked) -> Marked:
    """Mark a test that runs `bootstrap.py` cases.

    `ezpkg_coverage.py --per-case` measures the suite once with no
    cases, as a baseline, and then only the marked tests once per case,
    which is what makes measuring fifteen cases take minutes rather
    than hours.  An unmarked test that runs a case would be missing
    from every per-case run, so its coverage would be credited to no
    case at all.  `test_case_runners_are_marked` checks the marking
    against the source.

    Arguments:
    * `test` (`Marked`):
      The test method.

    Returns:
    * (`Marked`): The same method, carrying `runs_cases`.
    """
    # An attribute rather than a registry, so it travels with the method.
    test.__dict__["runs_cases"] = True
    return test


def run_bootstrap_case(label: str, home: Path, index_url: str,
                       extra: dict[str, str] | None = None,
                       python: str = sys.executable,
                       safe_path: bool = True
                       ) -> subprocess.CompletedProcess[str]:
    """Run one `bootstrap.py` case against a local index.

    The case is aimed at the index entirely through the environment,
    which is what `bootstrap.py` documents that `BOOTSTRAP_PACKAGE` and
    `BOOTSTRAP_JSON_API` are for, so no case body is edited to make it
    testable.  `HOME` is given because every case installs into
    `~/.ezpkg`, and a fresh `HOME` is what makes a run cold.

    Arguments:
    * `label` (`str`):
      The case label, as `bootstrap.py` spells it in `MECHANISMS`.
    * `home` (`Path`):
      The `HOME` for the child.  Reusing one makes a warm run.
    * `index_url` (`str`):
      The base URL of the index, ending in a slash.
    * `extra` (`dict[str, str] | None`):
      More environment, such as the trust store the TLS tests set.  It
      wins over the settings above, so it can aim the JSON API at the
      real PyPI.
    * `python` (`str`):
      The interpreter to run the case with.  The default is this one;
      the no-`pip` test passes one that has never had `pip`.
    * `safe_path` (`bool`):
      Run with `-P`, so that this directory, which holds `ezpkg.py`,
      is not put on the child's `sys.path`.  Without it `nopip4` imports
      the working copy and fetches nothing, which is right for a program
      but defeats every test of the fetch.  Only the test that wants the
      working copy found passes `False`.

    Returns:
    * (`subprocess.CompletedProcess[str]`): The finished child.
    """
    # Aim it at the index, for `pip` and for the JSON API alike.
    script: Path = Path(__file__).resolve().parent / "bootstrap.py"
    # `extra` overrides rather than collides, so a caller can aim the
    # JSON API somewhere else; as keyword arguments, a repeat raised
    # `TypeError`.
    environment: dict[str, str] = dict(
        os.environ, HOME=str(home), PIP_INDEX_URL=index_url,
        BOOTSTRAP_PACKAGE=MODULE, BOOTSTRAP_JSON_API=f"{index_url}pypi")
    environment.update(extra or {})
    environment.pop("VIRTUAL_ENV", None)
    # `-P` keeps the script's directory off `sys.path`; it is new in
    # 3.11, which is the floor.
    command: list[str] = [python, *(["-P"] if safe_path else []),
                          str(script), label]
    return subprocess.run(
        command, env=environment, capture_output=True, text=True,
        check=False)


def escaped_name(distribution: str) -> str:
    """Return the form of a distribution name used inside a wheel.

    Wheel filenames and `.dist-info` directory names may not contain
    the hyphens that a distribution name may, because a hyphen is the
    field separator in a wheel filename.  Runs of anything that is not
    a word character or a period collapse to a single underscore.

    Arguments:
    * `distribution` (`str`):
      The distribution name, as PyPI spells it.

    Returns:
    * (`str`): The escaped name, as a wheel spells it.
    """
    # A hyphen would be read as a wheel filename field separator.
    return re.sub(r"[^\w\d.]+", "_", distribution)


def build_wheel(module: Path, distribution: str, version: str,
                summary: str, directory: Path,
                tag: str = "py3-none-any",
                requires: Sequence[str] = (),
                floor: str = "",
                description: str = "",
                license_name: str = "",
                author: str = "",
                urls: Mapping[str, str] | None = None,
                classifiers: Sequence[str] = ()) -> Path:
    """Build a pure Python wheel holding one module.

    A wheel is a zip archive with an agreed layout, so building one
    needs no packaging tools at all.  Three files go in beside the
    module: `METADATA` names the distribution, `WHEEL` declares the
    archive format and its compatibility tag, and `RECORD` lists every
    member with its SHA-256 digest and size.  `RECORD` lists itself
    with both fields left empty, because it cannot contain its own
    digest.

    The default tag is `py3-none-any`, meaning any Python 3, any ABI,
    any platform, which is what makes a wheel `pip` installable
    everywhere without a compiled component.  Another tag can be given,
    and then the wheel is pure Python wearing a compiled wheel's name.
    That is a faithful input for anything which reads wheel filenames,
    such as the matcher in `nopip1` and `nopip2` of `bootstrap.py`, because
    that code never opens the archive; it is not a substitute for a
    genuinely compiled wheel.  See 6.5.11 of `T.ccp`.

    Arguments:
    * `module` (`Path`):
      The `.py` file to package.
    * `distribution` (`str`):
      The distribution name, as PyPI spells it.
    * `version` (`str`):
      The version string to record.
    * `summary` (`str`):
      The one line summary for `METADATA`.
    * `directory` (`Path`):
      Where to write the wheel.  Created if it does not exist.
    * `tag` (`str`):
      The compatibility tag, as a wheel filename spells it.
    * `requires` (`Sequence[str]`):
      Requirements this wheel depends on, written into `METADATA` as
      `Requires-Dist`.  Without one of these, every wheel the suite
      builds is a leaf, `pip` never pulls anything along, and the
      distinction between what was asked for and what merely arrived
      cannot be exercised at all.
    * `floor` (`str`):
      The lowest Python this wheel runs on, as a specifier such as
      `>=3.11`, written into `METADATA` as `Requires-Python`.  Empty,
      the default, claims nothing.  With it, `pip` refuses the wheel on
      an interpreter that cannot run it and says why; without it the
      install succeeds and the program fails later with a `SyntaxError`
      that explains nothing.
    * `description` (`str`):
      The long description, which becomes the body of `METADATA` and the
      project page on an index.  Markdown, and declared as such.  Empty,
      the default, writes none: a test wheel wants no project page.
    * `license_name` (`str`):
      The `License` field, as free text.  Free text on purpose: a
      `Classifier` naming a license is validated by PyPI and a wrong one
      is rejected, where this field is not checked at all.
    * `author` (`str`):
      The `Author` field.  No email, because an address in package
      metadata is published to everybody and is the author's to give.
    * `urls` (`Mapping[str, str] | None`):
      Labels and addresses for `Project-URL`.  `T.m`'s failed fetch
      message wants somewhere to point, and this is where a wheel
      carries it.
    * `classifiers` (`Sequence[str]`):
      Trove classifiers.  Every one is validated on upload, so an
      invented classifier fails the upload rather than being ignored.

    Returns:
    * (`Path`): The wheel that was written.
    """
    # Collect the module and the two text members it ships beside.
    escaped: str = escaped_name(distribution)
    info: str = f"{escaped}-{version}.dist-info"
    members: dict[str, bytes] = {
        module.name: module.read_bytes(),
        f"{info}/METADATA": (
            f"Metadata-Version: 2.1\nName: {distribution}\n"
            f"Version: {version}\nSummary: {summary}\n"
            + (f"Requires-Python: {floor}\n" if floor else "")
            + (f"License: {license_name}\n" if license_name else "")
            + (f"Author: {author}\n" if author else "")
            + "".join(f"Project-URL: {label}, {address}\n"
                      for label, address in (urls or {}).items())
            + "".join(f"Classifier: {one}\n" for one in classifiers)
            + "".join(f"Requires-Dist: {one}\n"
                      for one in requires)
            # The description is the message body, after a blank line,
            # which is how a `METADATA` file carries a project page.
            + ("Description-Content-Type: text/markdown\n\n"
               + description if description else "")).encode(),
        f"{info}/WHEEL": (b"Wheel-Version: 1.0\n"
                          b"Generator: ezpkg_test\n"
                          b"Root-Is-Purelib: true\n"
                          + f"Tag: {tag}\n".encode()),
    }

    # Hash every member, then append the self referential RECORD row.
    record: io.StringIO = io.StringIO()
    writer: _csv._writer = csv.writer(record, lineterminator="\n")
    path: str
    content: bytes
    digest: str
    for path, content in members.items():
        digest = base64.urlsafe_b64encode(
            hashlib.sha256(content).digest()).rstrip(b"=").decode()
        writer.writerow([path, f"sha256={digest}", len(content)])
    writer.writerow([f"{info}/RECORD", "", ""])
    members[f"{info}/RECORD"] = record.getvalue().encode()

    # A wheel is just a zip archive; write every member into one.
    directory.mkdir(parents=True, exist_ok=True)
    wheel: Path = directory / f"{escaped}-{version}-{tag}.whl"
    archive: zipfile.ZipFile
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in members.items():
            archive.writestr(path, content)
    return wheel


def dev_version(version: str = VERSION) -> str:
    """Return a development version that no index can have seen.

    An index never lets a filename be re-uploaded, even after the
    release is deleted, so every rehearsal needs a version of its own.
    A minute stamped suffix gives one without anybody having to
    remember what the last attempt was called, and `.devN` sorts below
    the release it rehearses, so publishing `0.0.1` afterwards still
    supersedes them all.  See 6.17.2 of `T.ffrp`.

    Arguments:
    * `version` (`str`):
      The release being rehearsed.

    Returns:
    * (`str`): Something like `0.0.1.dev202609272231`.
    """
    # UTC, so that two machines cannot disagree about the order.
    stamp: str = datetime.datetime.now(
        datetime.UTC).strftime("%Y%m%d%H%M")
    return f"{version}.dev{stamp}"


def release_wheel(directory: Path,
                  distribution: str = RELEASE_DISTRIBUTION,
                  version: str = VERSION,
                  readme: Path | None = None) -> Path:
    """Build the wheel this project would publish.

    The same builder the tests use, given the metadata an index wants:
    a long description, a license, an author, a project address and
    classifiers.  Nothing here uploads anything; see 6.17.2 of
    `T.ffrp`, and uploading is Wayne's by hand in any case.

    The module inside is named after the distribution, so that one word
    serves as both the `pip` name and the import name -- which is what
    `bootstrap.py`'s single `PACKAGE` requires.  For a rehearsal that
    means a copy of `ezpkg.py` under another name, which is also the
    honest thing to publish: it is the same code.

    `Requires-Python` comes from `ezpkg.py`'s own PEP 723 block, per
    6.7.9 of `T.p7i`, so a published wheel cannot claim a floor the source
    does not.

    Arguments:
    * `directory` (`Path`):
      Where to write the wheel, and the copied module.  Created if
      absent.
    * `distribution` (`str`):
      The distribution name, which is also the module name.
    * `version` (`str`):
      The version to publish, which PyPI will never let be reused.
    * `readme` (`Path | None`):
      The file to use as the long description.  `None` takes the
      project's own `README.md`.

    Returns:
    * (`Path`): The wheel that was written.
    """
    # The module is a copy of ours under the published name, with the
    # wheel's version written in, so a rehearsal's `__version__` says
    # which rehearsal it is.
    here: Path = Path(__file__).resolve().parent
    directory.mkdir(parents=True, exist_ok=True)
    module: Path = directory / f"{distribution}.py"
    source: bytes = (here / f"{MODULE}.py").read_bytes()
    stated: bytes = f'__version__: str = "{VERSION}"\n'.encode()
    assert source.count(stated) == 1, f"{MODULE}.py: no single {stated!r}"
    module.write_bytes(source.replace(
        stated, f'__version__: str = "{version}"\n'.encode()))

    # Everything else is metadata an index asks for and a test does not.
    page: Path = (here / "README.md") if readme is None else readme
    return build_wheel(
        module, distribution, version, SUMMARY, directory,
        floor=floor(),
        description=page.read_text(encoding="utf-8"),
        license_name="MIT No Attribution",
        author="Wayne C. Gramlich",
        urls={"Homepage": "https://github.com/waynegramlich/ezpkg"},
        classifiers=["Development Status :: 3 - Alpha",
                     "Intended Audience :: Developers",
                     "Operating System :: OS Independent",
                     "Programming Language :: Python :: 3",
                     "Topic :: System :: Installation/Setup"])


def add_data_member(wheel: Path, sub: str, name: str,
                    text: str) -> Path:
    """Rewrite a wheel with one extra member under its `.data` tree.

    `build_wheel` makes the simple shape, a module and a `.dist-info`.
    A real wheel may also carry a `{distribution}-{version}.data`
    directory whose `purelib` and `platlib` contents belong beside the
    modules rather than under `.data`, and moving them is the one part
    of the wheel specification `EZPkg.unpack` has to know; see
    6.3.12 of `T.vcbow`.  Nothing here can test that without a wheel
    shaped this way.

    Arguments:
    * `wheel` (`Path`):
      The wheel to rewrite, which is replaced.
    * `sub` (`str`):
      `purelib` or `platlib`.
    * `name` (`str`):
      The file to add under it.
    * `text` (`str`):
      What that file contains.

    Returns:
    * (`Path`): The wheel, rewritten in place.
    """
    # A zip cannot grow in place, so it is rebuilt beside itself.
    fields: list[str] = wheel.stem.split("-")
    member: str = f"{fields[0]}-{fields[1]}.data/{sub}/{name}"
    rebuilt: Path = wheel.with_suffix(".rebuilt")
    old: zipfile.ZipFile
    new: zipfile.ZipFile
    with zipfile.ZipFile(wheel) as old, \
            zipfile.ZipFile(rebuilt, "w", zipfile.ZIP_DEFLATED) as new:
        for entry in old.infolist():
            new.writestr(entry.filename, old.read(entry.filename))
        new.writestr(member, text)
    rebuilt.replace(wheel)
    return wheel


def add_root_member(wheel: Path, name: str, text: str) -> Path:
    """Add a file at the top level of a wheel.

    `add_data_member` puts a file inside the `.data` directory, which is
    where a wheel carries things that belong elsewhere.  A `.pth` file
    is not one of those: it sits at the root, beside the module, and is
    installed straight into the directory packages land in.  See
    `T.pf`.

    `RECORD` is left alone, as `add_data_member` leaves it: nothing in
    this project verifies it, and a wheel that disagrees with its own
    `RECORD` is a fair thing for a test to hand us.

    Arguments:
    * `wheel` (`Path`):
      The wheel to rewrite.
    * `name` (`str`):
      The member's name, such as `zz_widget.pth`.
    * `text` (`str`):
      What that file contains.

    Returns:
    * (`Path`): The wheel, rewritten in place.
    """
    # A zip cannot grow in place, so it is rebuilt beside itself.
    rebuilt: Path = wheel.with_suffix(".rebuilt")
    old: zipfile.ZipFile
    new: zipfile.ZipFile
    with zipfile.ZipFile(wheel) as old, \
            zipfile.ZipFile(rebuilt, "w", zipfile.ZIP_DEFLATED) as new:
        for entry in old.infolist():
            new.writestr(entry.filename, old.read(entry.filename))
        new.writestr(name, text)
    rebuilt.replace(wheel)
    return wheel


def requires_python(wheel: Path) -> str | None:
    """Return the `Requires-Python` a wheel declares, as PyPI reports it.

    Arguments:
    * `wheel` (`Path`):
      The wheel to read.

    Returns:
    * (`str | None`): The specifier, or `None` when the wheel declares
      none, which is what PyPI's JSON says for such a file.
    """
    # The one `METADATA` in the `.dist-info` directory holds it.
    with zipfile.ZipFile(wheel) as archive:
        name: str
        for name in archive.namelist():
            if name.endswith(".dist-info/METADATA"):
                line: str
                for line in archive.read(name).decode().splitlines():
                    if line.startswith("Requires-Python:"):
                        return line.partition(":")[2].strip()
    return None


# The `pip` wheel every index publishes, built once on first use.
_PIP_WHEEL: tuple[str, bytes] | None = None


def dating_pip() -> Path | None:
    """Return a `pip` wheel that knows `--uploaded-prior-to`, if any.

    The option arrived in `pip` 26, and the suite's own `pip_wheel` is
    whatever `pip` is installed here, often older, and the suite never
    reaches the network to fetch another.  So the copy that the real
    `~/.ezpkg` keeps is borrowed when it is new enough, and the tests
    that need one skip when it is not.

    Returns:
    * (`Path | None`): A wheel to copy into a test cache as `pip.whl`,
      or `None` when there is none that filters by date.
    """
    # The newest refreshed copy first, as `EZPkg.pip` chooses.
    home: Path = Path.home() / ".ezpkg"
    candidates: list[Path] = sorted(home.glob("pip-*.whl"),
                                    key=lambda one: one.stat().st_mtime)
    candidate: Path
    for candidate in [*reversed(candidates), home / "pip.whl"]:
        if not candidate.is_file():
            continue
        helped: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, str(candidate / "pip"), "download", "--help"],
            capture_output=True, text=True, check=False)
        if "--uploaded-prior-to" in helped.stdout:
            return candidate
    return None


def pip_wheel() -> tuple[str, bytes]:
    """Return a runnable `pip` wheel built from the one installed here.

    `nopip3` of `bootstrap.py` fetches `pip` itself from the JSON API,
    and the suite never reaches the network, so every index has to be
    able to hand out a `pip`.  The installed `pip` package is zipped as
    it stands, with just enough `.dist-info` to be called a wheel.  It
    is never installed, only run as `python pip.whl/pip`, which needs
    nothing but `pip/__main__.py` and the vendored libraries beside it.

    A distribution that strips those vendored libraries out, which
    `pip._vendor.DEBUNDLED` reports, yields a wheel that only runs
    where that distribution's own `pip` is present.  The no-`pip`
    test checks for that and skips.

    Returns:
    * (`tuple[str, bytes]`): The wheel's filename and its contents.
    """
    # Zip it once; every index after the first copies the bytes.
    global _PIP_WHEEL
    if _PIP_WHEEL is None:
        import pip
        package: Path = Path(pip.__file__).parent
        version: str = pip.__version__
        buffer: io.BytesIO = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            member: Path
            for member in sorted(package.rglob("*")):
                if member.is_file() and "__pycache__" not in member.parts:
                    archive.write(member, PurePath(
                        "pip", member.relative_to(package)).as_posix())
            information: str = f"pip-{version}.dist-info"
            # A single valued field, though the stubs allow a list.
            floor: object = importlib.metadata.metadata(
                "pip").json.get("requires_python")
            archive.writestr(f"{information}/METADATA",
                             "Metadata-Version: 2.1\nName: pip\n"
                             f"Version: {version}\n"
                             + (f"Requires-Python: {floor}\n"
                                if isinstance(floor, str) else ""))
            archive.writestr(f"{information}/WHEEL",
                             "Wheel-Version: 1.0\nRoot-Is-Purelib: true\n"
                             "Tag: py3-none-any\n")
        _PIP_WHEEL = (f"pip-{version}-py3-none-any.whl", buffer.getvalue())
    return _PIP_WHEEL


def build_index(wheels: list[Path],
                root: Path) -> Path:
    """Lay wheels out as a PEP 503 simple repository.

    The layout is two levels of HTML.  The root `index.html` links to
    one directory per project, and each project directory holds its
    own `index.html` linking to that project's files.  Project names
    are normalized as PEP 503 requires: lower cased, with runs of
    `-`, `_` and `.` collapsed to a single hyphen.

    A directory in this shape is a complete implementation of the
    protocol rather than a simplification of it, because `pip` does
    all of its filtering locally; the index only has to list files.
    Each link carries its `#sha256=` digest, as PyPI's do, so that a
    `uv` lock made from the index has hashes to check.

    Arguments:
    * `wheels` (`list[Path]`):
      The wheels to publish.  Each is copied into the tree, and a
      `pip` wheel from `pip_wheel` joins them unless one is given.
    * `root` (`Path`):
      Where to build the tree.  Created if it does not exist.

    Returns:
    * (`Path`): The root of the tree, suitable for
      `PIP_INDEX_URL` once it is spelled as a `file://` URL.
    """
    # Group the wheels by their PEP 503 normalized project name.
    projects: dict[str, list[Path]] = {}
    wheel: Path
    raw: str
    for wheel in wheels:
        raw = wheel.name.split("-")[0]
        projects.setdefault(re.sub(r"[-_.]+", "-", raw).lower(),
                            []).append(wheel)

    # Give each project a directory, an index page and its files.
    root.mkdir(parents=True, exist_ok=True)
    project: str
    files: list[Path]
    directory: Path
    links: str
    for project, files in sorted(projects.items()):
        directory = root / project
        directory.mkdir(exist_ok=True)
        links = "".join(
            f'<a href="{html.escape(wheel.name)}#sha256='
            f'{hashlib.sha256(wheel.read_bytes()).hexdigest()}">'
            f'{wheel.name}</a><br>'
            for wheel in files)
        (directory / "index.html").write_text(
            f"<!DOCTYPE html><html><body>{links}</body></html>")
        for wheel in files:
            (directory / wheel.name).write_bytes(wheel.read_bytes())

    # Publish `pip` as well, so that `nopip3` has one to fetch.
    name: str
    contents: bytes
    name, contents = pip_wheel()
    if "pip" not in projects:
        projects["pip"] = []
        (root / "pip").mkdir(exist_ok=True)
        (root / "pip" / name).write_bytes(contents)
        (root / "pip" / "index.html").write_text(
            f'<!DOCTYPE html><html><body><a href="{name}">{name}</a><br>'
            "</body></html>")

    # Finish with the root page that lists the projects.
    links = "".join(f'<a href="{project}/">{project}</a><br>'
                    for project in sorted(projects))
    (root / "index.html").write_text(
        f"<!DOCTYPE html><html><body>{links}</body></html>")
    return root


# The PEP 691 content type for a JSON project page.
SIMPLE_JSON: str = "application/vnd.pypi.simple.v1+json"


class _IndexServer(http.server.ThreadingHTTPServer):
    """A `ThreadingHTTPServer` that can be told to serve badly.

    A directory index cannot misbehave, which is why the failure cases
    carried over from Task 3 went untested for so long.  A server can,
    so this one carries a table of faults that `_IndexHandler` reads
    before answering.  Tests add an entry, make a request, and take the
    entry out again.

    Attributes:
    * `faults` (`dict[str, str]`):
      Maps a path suffix to what should go wrong for a request whose
      path ends that way.  The fault names are `truncate`, which sends
      half the file and a `Content-Length` that agrees with the half,
      `missing`, which answers 404, `error`, which answers 500,
      `hang`, which waits `HANG_SECONDS` and then answers normally,
      and `slow`, which waits `SLOW_SECONDS` and then answers
      normally.  `slow` exists so that several processes fetching at
      once genuinely overlap rather than finishing one after another.
      An empty table, which is the default, serves everything
      correctly.

    Constructor:
    * `_IndexServer(address, handler)`, as `ThreadingHTTPServer`.
    """

    # Assigned per instance by `serve_index`, never shared between them.
    faults: dict[str, str]

    # Whether a project page may be answered as PEP 691 JSON carrying
    # PEP 700 upload times, which is what `--uploaded-prior-to` needs.
    # Off by default, so that the index is plain HTML, which has none.
    upload_times: bool

    # `http` or `https`, so that `send_json` can build a URL that works.
    scheme: str

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Stay quiet when a client hangs up, report anything else.

        A client that times out closes its socket while the answer is
        still being written, which the `hang` fault provokes on
        purpose.  The base class prints a traceback for that, which
        would look like a test failure in the middle of a passing run.
        Every other error still gets reported.

        Arguments:
        * `request` (`Any`):
          The socket the failure happened on.
        * `client_address` (`Any`):
          Where it came from.
        """
        # A hangup or a refused handshake is expected; the rest is news.
        if isinstance(sys.exc_info()[1], (ConnectionError, ssl.SSLError)):
            return
        super().handle_error(request, client_address)


class _IndexHandler(http.server.SimpleHTTPRequestHandler):
    """Serve a PEP 503 tree from disk, plus PyPI's JSON API.

    `SimpleHTTPRequestHandler` already does most of the job: it serves
    a directory's `index.html` for a path ending in a slash, which is
    exactly what the two levels of a PEP 503 tree ask for.  Two things
    are added.  The request log is silenced, because it would
    otherwise interleave with the test output on standard error.  And
    `/pypi/{project}/json` is answered from the tree, because `nopip1`
    and `nopip2` of `bootstrap.py` read that endpoint with `urllib` rather
    than going through `pip`.

    The JSON is the modern per release shape, `{"urls": [...]}` with a
    `filename` and a `url` in each entry, which is what those two
    cases parse.  It is not PyPI's full payload; it is the subset they
    read, which is the only part a test can check them against.

    Constructor:
    * `_IndexHandler(...)`, by `http.server` rather than by hand.  The
      `directory` argument is bound by `serve_index` beforehand.
    """

    def do_GET(self) -> None:
        """Answer the JSON API here, and everything else from disk."""
        # A configured fault takes precedence over answering properly.
        fault: str | None = self.fault()
        if fault is not None and self.send_fault(fault):
            return

        # `/pypi/<project>/json` is synthesized, and so is a project page
        # in JSON when upload times are on and the client asks for it.
        parts: list[str] = self.path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "pypi" and parts[2] == "json":
            self.send_json(parts[1])
            return
        if (cast(_IndexServer, self.server).upload_times and len(parts) == 1
                and self.path.endswith("/")
                and SIMPLE_JSON in self.headers.get("Accept", "")):
            self.send_simple_json(parts[0])
            return
        super().do_GET()

    def send_simple_json(self, project: str) -> None:
        """Answer a project page as PEP 691 JSON, with upload times.

        Each wheel's upload time is its file's modification time, as in
        `send_json`, so a test dates a release with `os.utime`.

        Arguments:
        * `project` (`str`):
          The project name as the request spelled it.
        """
        # The wheels, which are the whole of the answer.
        normalized: str = re.sub(r"[-_.]+", "-", project).lower()
        wheels: list[Path] = sorted(
            (Path(self.directory) / normalized).glob("*.whl"))
        if not wheels:
            self.send_error(404, f"no project {normalized}")
            return
        body: bytes = json.dumps({
            "meta": {"api-version": "1.1"},
            "name": normalized,
            "versions": sorted({wheel.name.split("-")[1]
                                for wheel in wheels}),
            "files": [
                {"filename": wheel.name, "url": wheel.name,
                 "hashes": {"sha256": hashlib.sha256(
                     wheel.read_bytes()).hexdigest()},
                 "size": wheel.stat().st_size,
                 "upload-time": datetime.datetime.fromtimestamp(
                     wheel.stat().st_mtime, datetime.UTC).strftime(
                         "%Y-%m-%dT%H:%M:%S.%fZ")}
                for wheel in wheels]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", SIMPLE_JSON)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def fault(self) -> str | None:
        """Return the fault configured for this request, if any.

        Returns:
        * (`str | None`): The fault name, or `None` when this request
          should be answered properly.
        """
        # The table is keyed by path suffix, so `.whl` picks any wheel.
        server: _IndexServer = cast(_IndexServer, self.server)
        suffix: str
        name: str
        for suffix, name in server.faults.items():
            if self.path.endswith(suffix):
                return name
        return None

    def send_fault(self, fault: str) -> bool:
        """Answer this request badly, in the manner `fault` names.

        Arguments:
        * `fault` (`str`):
          One of `truncate`, `missing`, `error`, `hang` or `slow`.  See
          `_IndexServer.faults`.

        Returns:
        * (`bool`): True when the request has been answered and the
          caller should stop.  `hang` and `slow` return False, because
          they delay a correct answer rather than replacing it.
        """
        # Two of the faults are nothing but a status code.
        if fault == "missing":
            self.send_error(404, "fault: missing")
            return True
        if fault == "error":
            self.send_error(500, "fault: error")
            return True

        # A hang or a slow answer delays the real one rather than
        # replacing it.
        if fault == "hang":
            time.sleep(HANG_SECONDS)
            return False
        if fault == "slow":
            time.sleep(SLOW_SECONDS)
            return False

        # A truncated file is the interesting one: the download looks
        # complete, because the length agrees with the bytes sent, and
        # the bytes are half a wheel.  Nothing but unzipping catches it.
        whole: bytes = (Path(self.directory)
                        / self.path.lstrip("/")).read_bytes()
        half: bytes = whole[:len(whole) // 2]
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(half)))
        self.end_headers()
        self.wfile.write(half)
        return True

    def send_json(self, project: str) -> None:
        """Answer one JSON API request for `project`.

        Arguments:
        * `project` (`str`):
          The project name as the request spelled it.  It is
          normalized the way PEP 503 and `build_index` normalize it,
          so that `EZPkg` and `ezpkg` both arrive.
        """
        # Find the project's wheels, which are the whole of the answer.
        normalized: str = re.sub(r"[-_.]+", "-", project).lower()
        directory: Path = Path(self.directory) / normalized
        wheels: list[Path] = sorted(directory.glob("*.whl"))

        # A project with no files is a 404, exactly as PyPI answers.
        if not wheels:
            self.send_error(404, f"no project {normalized}")
            return

        # Build the subset of the payload that the `nopip` cases read:
        # `urls` for `nopip1` and `nopip2`, and `releases` for `nopip3`,
        # which chooses a `pip` by `requires_python` and `upload_time` and
        # checks it against `digests`.
        # Both are taken from the wheels themselves, the floor from their
        # `METADATA` and the time from the file, in PyPI's own format, so
        # a test controls them by building the wheel it wants.
        host: str = self.headers.get("Host", "127.0.0.1")
        files: list[dict[str, Any]] = [
            {"filename": wheel.name, "yanked": False,
             "packagetype": "bdist_wheel",
             "digests": {"sha256": hashlib.sha256(
                 wheel.read_bytes()).hexdigest()},
             "requires_python": requires_python(wheel),
             "upload_time": datetime.datetime.fromtimestamp(
                 wheel.stat().st_mtime, datetime.UTC).strftime(
                     "%Y-%m-%dT%H:%M:%S"),
             "url": f"{cast(_IndexServer, self.server).scheme}"
                    f"://{host}/{normalized}/{wheel.name}"}
            for wheel in wheels]
        releases: dict[str, list[dict[str, Any]]] = {}
        entry: dict[str, Any]
        for entry in files:
            releases.setdefault(entry["filename"].split("-")[1],
                                []).append(entry)
        payload: dict[str, Any] = {"urls": files, "releases": releases}
        body: bytes = json.dumps(payload).encode()

        # Send it with a length, so `urllib` does not wait for a close.
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Discard a request log line.

        Arguments:
        * `format` (`str`):
          A printf style template, named as the base class names it.
        * `args` (`Any`):
          Whatever the template interpolates.
        """
        # The tests care about responses, not about a request log.
        return


def make_certificate(directory: Path) -> tuple[Path, Path] | None:
    """Make a throwaway self signed certificate for `127.0.0.1`.

    The standard library can consume a certificate but cannot create
    one, so this shells out to `openssl`.  That is a program rather
    than a Python package, so it does not cost the test suite a
    dependency, and a machine without it skips the TLS tests instead
    of failing them.

    The certificate is its own issuer, so the same file that the
    server presents is the trust anchor a client is given.  It carries
    `subjectAltName=IP:127.0.0.1`, because Python has ignored
    `commonName` since 3.7 and would otherwise refuse the connection
    it is supposed to accept.

    Arguments:
    * `directory` (`Path`):
      Where to write the files.  Created if it does not exist.

    Returns:
    * (`tuple[Path, Path] | None`): The chain file holding both the
      certificate and its private key, for the server, and the
      certificate alone, for a client trust store.  `None` when
      `openssl` is missing or fails.
    """
    # Without `openssl` there is no certificate and no TLS test.
    program: str | None = shutil.which("openssl")
    if program is None:
        return None

    # Ten years, so that a stored expectation cannot rot into a failure.
    directory.mkdir(parents=True, exist_ok=True)
    certificate: Path = directory / "certificate.pem"
    key: Path = directory / "key.pem"
    done: subprocess.CompletedProcess[str] = subprocess.run(
        [program, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", str(key), "-out", str(certificate),
         "-days", "3650", "-subj", "/CN=127.0.0.1",
         "-addext", "subjectAltName=IP:127.0.0.1"],
        capture_output=True, text=True, check=False)
    if done.returncode != 0:
        return None

    # The server wants one file holding both halves.
    chain: Path = directory / "chain.pem"
    chain.write_text(certificate.read_text() + key.read_text())
    return chain, certificate


def serve_index(root: Path,
                chain: Path | None = None) -> tuple[_IndexServer, str]:
    """Serve a PEP 503 tree over HTTP and return the server and its URL.

    The server binds port 0, so the operating system picks a free port
    and the caller reads back which one.  A fixed port would collide
    with a server left over from an interrupted run, and the failure
    that produced would look like a packaging bug rather than a stale
    process.

    Serving happens on a daemon thread, which is what makes a
    control-C leave nothing behind: the interpreter does not wait for
    a daemon thread to finish, so the process exits whether or not
    `shutdown` was ever reached.

    Arguments:
    * `root` (`Path`):
      The root of the tree to serve, as `build_index` returns it.
    * `chain` (`Path | None`):
      A certificate and key, as `make_certificate` returns first, to
      serve HTTPS instead of HTTP.  `None`, the default, is plain
      HTTP.

    Returns:
    * (`tuple[_IndexServer, str]`): The running server, which the
      caller shuts down and which carries the fault table, and the
      base URL to hand to `PIP_INDEX_URL`.
    """
    # Bind port 0 and let the operating system choose.
    handler: functools.partial[_IndexHandler] = functools.partial(
        _IndexHandler, directory=str(root))
    server: _IndexServer = _IndexServer(("127.0.0.1", 0), handler)
    server.faults = {}
    server.upload_times = False
    server.scheme = "http"

    # Wrap the listening socket before anything is accepted on it.
    context: ssl.SSLContext
    if chain is not None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(chain)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        server.scheme = "https"

    # Serve on a daemon thread, so a control-C cannot strand it.
    thread: threading.Thread = threading.Thread(target=server.serve_forever,
                                                daemon=True)
    thread.start()

    # The port is only knowable once the bind has happened.  The
    # standard library types `server_address` loosely, because a
    # `socketserver` address may be a path rather than a host and a
    # port.  This one is an internet socket, so the host is a string,
    # and saying so keeps the URL from ever being built out of
    # `b'127.0.0.1'`.
    address: tuple[str | bytes | bytearray, int] = server.server_address
    assert isinstance(address[0], str), address
    return server, f"{server.scheme}://{address[0]}:{address[1]}/"


def with_path(*entries: Path) -> str:
    """Return `PYTHONPATH` with `entries` put in front of it.

    Replacing `PYTHONPATH` outright would discard whatever is already
    there, and what is already there may be the `trace_hook` directory
    that `ezpkg_coverage.py` uses to measure this very child; see
    `T.sawaw`.

    Arguments:
    * `entries` (`Path`):
      Directories to put first, in order.

    Returns:
    * (`str`): A value for `PYTHONPATH`.
    """
    # Keep whatever was inherited, behind what the caller asked for.
    inherited: str = os.environ.get("PYTHONPATH", "")
    wanted: list[str] = [str(entry) for entry in entries]
    if inherited:
        wanted.append(inherited)
    return os.pathsep.join(wanted)


class _KeptStringIO(io.StringIO):
    """A `StringIO` that survives being closed.

    `EZPkg.consent` closes the handles `terminal` gave it, which is
    right, and leaves a plain `StringIO` unreadable afterwards.  This one
    ignores the close so that a test can still see what was asked.

    Constructor:
    * `_KeptStringIO(initial)`, as `io.StringIO`.
    """

    def close(self) -> None:
        """Do nothing, so that `getvalue` still works afterwards."""
        # Deliberately not calling `super().close()`.
        return


def inject(case: unittest.TestCase, server: _IndexServer, suffix: str,
           fault: str) -> None:
    """Make a server misbehave for the rest of one test only.

    The entry is removed by a cleanup rather than by the test, so a
    failing assertion cannot leave the fault in place for whatever test
    `unittest` runs next.  Shared by every class that runs a server.

    Arguments:
    * `case` (`unittest.TestCase`):
      The test, which the cleanup is registered on.
    * `server` (`_IndexServer`):
      The server to afflict.
    * `suffix` (`str`):
      The path suffix to afflict, such as `.whl`.
    * `fault` (`str`):
      The fault name.  See `_IndexServer.faults`.
    """
    # Register the removal first, so an exception cannot skip it.
    case.addCleanup(server.faults.pop, suffix, None)
    server.faults[suffix] = fault


class EZPkgTest(unittest.TestCase):
    """Build, exercise and discard the Experiment 2 pipeline.

    The wheel and the index are built once for the whole class, in a
    temporary directory that is removed afterwards.  Building them is
    the expensive part and no test needs a private copy.

    Attributes:
    * `index` (`Path`):
      The root of the PEP 503 directory tree that the server serves.
    * `index_url` (`str`):
      That same tree as an HTTP URL, for `PIP_INDEX_URL`.
    * `root` (`Path`):
      The temporary directory holding everything this class builds.
    * `server` (`_IndexServer`):
      The server publishing `index`.
    * `tagged` (`Path`):
      A second wheel of the same package, wearing this interpreter's
      compiled tag and carrying a `.data/purelib` member.
    * `wheel` (`Path`):
      The wheel built from `ezpkg.py`, tagged `py3-none-any`.

    Constructor:
    * `EZPkgTest()`, by `unittest` rather than by hand.
    """

    # Built once by `setUpClass`, shared by every test below.
    index: Path
    index_url: str
    root: Path
    server: _IndexServer
    tagged: Path
    wheel: Path

    @classmethod
    def setUpClass(cls) -> None:
        """Build the wheels and the index, then publish it over HTTP."""
        # Publish this project into a throwaway index.
        cls.root = Path(tempfile.mkdtemp(prefix="ezpkg-"))
        module: Path = Path(__file__).resolve().parent / f"{MODULE}.py"
        cls.wheel = build_wheel(module, DISTRIBUTION, VERSION, SUMMARY,
                                cls.root / "dist", floor=FLOOR)
        # A second wheel, wearing this interpreter's compiled tag and
        # carrying a `.data/purelib` member.  `nopip1` and `nopip2` prefer it,
        # which is the only way to reach their platform branch and their
        # `.data` move; see 6.5.11 of `T.ccp`.
        cls.tagged = build_wheel(module, DISTRIBUTION, VERSION, SUMMARY,
                                 cls.root / "dist", tag=platform_tag(),
                                 floor=FLOOR)
        add_data_member(cls.tagged, "purelib", "beside_ezpkg.py",
                        "BESIDE = True\n")
        cls.index = build_index([cls.wheel, cls.tagged],
                                cls.root / "index")

        # Start the server last, so nothing can fail after it is up.
        cls.server, cls.index_url = serve_index(cls.index)

    @classmethod
    def tearDownClass(cls) -> None:
        """Stop the server, then remove everything the class built."""
        # Stop serving before the tree underneath goes away.
        cls.server.shutdown()
        cls.server.server_close()

        # One directory holds everything, so one removal suffices.
        shutil.rmtree(cls.root, ignore_errors=True)

    def pip_install(self, target: Path, requirement: str,
                    extra: dict[str, str] | None = None
                    ) -> subprocess.CompletedProcess[str]:
        """Install a requirement from the local index into `target`.

        The index is passed through `PIP_INDEX_URL` rather than on the
        command line, because that is how a `bootstrap.py` case will
        be pointed at it: the environment steers `pip` without adding
        a line to any case body.  The URL is the HTTP one, so this
        goes over a socket rather than reading the tree directly.

        Arguments:
        * `target` (`Path`):
          The directory to install into.
        * `requirement` (`str`):
          What to ask `pip` for.
        * `extra` (`dict[str, str] | None`):
          More environment for the child, such as the shorter timeout
          and the disabled retries that the failure tests want.

        Returns:
        * (`subprocess.CompletedProcess[str]`): The finished child.
        """
        # Steer pip entirely through the environment, then run it.
        # `extra` is applied last, so a caller naming `PIP_INDEX_URL`
        # itself overrides this class's index rather than colliding
        # with it.
        environment: dict[str, str] = dict(
            os.environ, PIP_INDEX_URL=self.index_url)
        environment.update(extra or {})
        environment.pop("VIRTUAL_ENV", None)
        return subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "--no-input",
             "--disable-pip-version-check", "--target", str(target),
             requirement],
            env=environment, capture_output=True, text=True, check=False)

    def test_wheel_members(self) -> None:
        """The wheel holds the module and a complete `.dist-info`."""
        # Open the wheel once, and read its names and RECORD out.
        escaped: str = escaped_name(DISTRIBUTION)
        info: str = f"{escaped}-{VERSION}.dist-info"
        names: set[str]
        record: str
        archive: zipfile.ZipFile
        with zipfile.ZipFile(self.wheel) as archive:
            names = set(archive.namelist())
            record = archive.read(f"{info}/RECORD").decode()
        self.assertEqual(names, {f"{MODULE}.py", f"{info}/METADATA",
                                 f"{info}/WHEEL", f"{info}/RECORD"})
        self.assertIn(f"{MODULE}.py,sha256=", record)

    def test_the_wheel_declares_its_python_floor(self) -> None:
        """The wheel says which Pythons it runs on, so `pip` can refuse.

        Without it an old interpreter installs the wheel happily and the
        program then fails with a `SyntaxError` from an annotation, which
        explains nothing.  Measured 2026-09-27: `pip` refuses a wheel it
        cannot satisfy with
        `requires a different Python: 3.12.3 not in '>=3.99'`.
        """
        # The floor is in the metadata of the real wheel.
        archive: zipfile.ZipFile
        escaped: str = escaped_name(DISTRIBUTION)
        with zipfile.ZipFile(self.wheel) as archive:
            text: str = archive.read(
                f"{escaped}-{VERSION}.dist-info/METADATA").decode()
        self.assertIn(f"Requires-Python: {FLOOR}", text)

    def test_a_floor_this_python_fails_is_refused(self) -> None:
        """`pip` turns away a wheel this interpreter cannot run.

        This is what the metadata buys, and it is why claiming a floor is
        worth the line.
        """
        # A wheel claiming a Python nobody has yet.
        module: Path = Path(__file__).resolve().parent / f"{MODULE}.py"
        absurd: Path = build_wheel(module, DISTRIBUTION, VERSION, SUMMARY,
                                   self.root / "absurd-dist",
                                   floor=">=3.99")
        index: Path = build_index([absurd], self.root / "absurd-index")
        server: _IndexServer
        url: str
        server, url = serve_index(index)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        # `pip` says which Python is wanted rather than failing later.
        done: subprocess.CompletedProcess[str] = self.pip_install(
            self.root / "absurd-target", DISTRIBUTION,
            {"PIP_INDEX_URL": url})
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("requires a different Python", done.stderr)
        self.assertIn(">=3.99", done.stderr)

    def test_wheel_is_named_correctly(self) -> None:
        """The wheel filename carries the name, version and tag."""
        # The distribution name needs no escaping: it is the module's.
        self.assertEqual(self.wheel.name,
                         f"{MODULE}-{VERSION}-py3-none-any.whl")

    def test_index_layout(self) -> None:
        """The index has a root page, a project page, and the wheel."""
        # Both pages exist, both name what they should, file is there.
        project: Path = self.index / DISTRIBUTION
        self.assertTrue((self.index / "index.html").is_file())
        self.assertTrue((project / "index.html").is_file())
        self.assertTrue((project / self.wheel.name).is_file())
        self.assertIn(DISTRIBUTION, (self.index / "index.html").read_text())
        self.assertIn(self.wheel.name, (project / "index.html").read_text())

    def test_pip_installs_from_the_index(self) -> None:
        """`pip` finds, installs and records the package from the tree."""
        # A real pip run against the tree leaves module and metadata.
        target: Path = self.root / "target"
        done: subprocess.CompletedProcess[str] = self.pip_install(
            target, DISTRIBUTION)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((target / f"{MODULE}.py").is_file())
        escaped: str = escaped_name(DISTRIBUTION)
        info: Path = target / f"{escaped}-{VERSION}.dist-info"
        self.assertTrue((info / "METADATA").is_file())

    def run_case(self, label: str, home: Path | None = None
                 ) -> subprocess.CompletedProcess[str]:
        """Run one `bootstrap.py` case against the local server.

        The case is aimed at the local index entirely through the
        environment, which is what `bootstrap.py` documents that
        `BOOTSTRAP_PACKAGE` and `BOOTSTRAP_JSON_API` are for, so no
        case body is edited to make it testable.  `HOME` is faked
        because every case installs into `~/.ezpkg`.

        Arguments:
        * `label` (`str`):
          The case label, as `bootstrap.py` spells it in `MECHANISMS`.
        * `home` (`Path | None`):
          A `HOME` to reuse, which makes this a warm run.  `None`, the
          default, makes a fresh one and so a cold run.

        Returns:
        * (`subprocess.CompletedProcess[str]`): The finished child.
        """
        # A fresh HOME cannot hold a warm cache; a reused one can.
        if home is None:
            home = Path(tempfile.mkdtemp(prefix=f"case-{label}-",
                                         dir=self.root))
        return run_bootstrap_case(label, home, self.index_url)

    def inject(self, suffix: str, fault: str) -> None:
        """Make this class's server misbehave for one test only.

        Arguments:
        * `suffix` (`str`):
          The path suffix to afflict, such as `.whl`.
        * `fault` (`str`):
          The fault name.  See `_IndexServer.faults`.
        """
        # The shared helper does the work; see `inject` above.
        inject(self, self.server, suffix, fault)

    def test_a_truncated_wheel_fails_the_install(self) -> None:
        """Half a wheel is refused rather than half installed."""
        # The download looks complete, so only unzipping can catch it.
        self.inject(".whl", "truncate")
        target: Path = self.root / "truncated"
        done: subprocess.CompletedProcess[str] = self.pip_install(
            target, DISTRIBUTION)
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse((target / f"{MODULE}.py").exists())

    @runs_cases
    def test_a_truncated_wheel_fails_nopip1(self) -> None:
        """`nopip1` unzips the wheel itself, so it must fail too."""
        # `zipfile` is what notices, since the fetch itself succeeded.
        # `T.eoff` replaced the traceback with one line, so the
        # assertion reads the message rather than the module name.
        self.inject(".whl", "truncate")
        if not selected("nopip1"):
            self.skipTest("nopip1 is not selected")
        done: subprocess.CompletedProcess[str] = self.run_case("nopip1")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn(f"cannot fetch {MODULE}", done.stderr)
        self.assertIn("not a zip file", done.stderr)

    def test_a_missing_project_page_fails_the_install(self) -> None:
        """A 404 for the project page is reported, not worked around."""
        # This is the missing `index.html` case carried over from Task 3.
        self.inject(f"/{DISTRIBUTION}/", "missing")
        target: Path = self.root / "no-page"
        done: subprocess.CompletedProcess[str] = self.pip_install(
            target, DISTRIBUTION)
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse((target / f"{MODULE}.py").exists())

    def test_an_index_error_fails_the_install(self) -> None:
        """A 500 from the index is reported rather than retried forever."""
        # Retries are off, so this measures the first failure.
        self.inject(f"/{DISTRIBUTION}/", "error")
        target: Path = self.root / "index-error"
        done: subprocess.CompletedProcess[str] = self.pip_install(
            target, DISTRIBUTION, {"PIP_RETRIES": "0"})
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse((target / f"{MODULE}.py").exists())

    def test_a_hanging_index_times_out(self) -> None:
        """A server that stops answering ends as a timeout, not a hang."""
        # The fault waits longer than the timeout this passes to pip.
        self.inject(f"/{DISTRIBUTION}/", "hang")
        target: Path = self.root / "hanging"
        done: subprocess.CompletedProcess[str] = self.pip_install(
            target, DISTRIBUTION, {"PIP_TIMEOUT": "1", "PIP_RETRIES": "0"})
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse((target / f"{MODULE}.py").exists())

    @runs_cases
    def test_a_failed_fetch_is_one_line(self) -> None:
        """A case that cannot reach the index says so, without a traceback.

        This is the `I.whwnn` issue.  Before `T.eoff`, `nopip1` buried
        `Connection refused` under 47 lines of traceback and `pip1`
        ended in `RuntimeError: pip failed` without ever mentioning the
        network.
        """
        # A port nothing listens on stands in for a missing network.
        dead: str = "http://127.0.0.1:1/"
        label: str
        home: Path
        done: subprocess.CompletedProcess[str]
        for label in cases():
            with self.subTest(case=label):
                home = Path(tempfile.mkdtemp(prefix=f"dead-{label}-",
                                             dir=self.root))
                done = run_bootstrap_case(
                    label, home, dead,
                    {"PIP_RETRIES": "0", "PIP_TIMEOUT": "2"})
                self.assertNotEqual(done.returncode, 0)
                self.assertNotIn("Traceback", done.stderr)
                # `nopip3` names its stage, since it may fail fetching
                # the program's packages rather than `ezpkg` itself.
                self.assertRegex(done.stderr, rf"cannot fetch {MODULE}"
                                 rf"|{MODULE}: [a-z_ ]+ failed: ")

    def test_json_api_lists_the_wheel(self) -> None:
        """The synthesized JSON API answers in the shape `nopip1` reads."""
        # Ask the way `nopip1` asks, by import name rather than PyPI name.
        url: str = f"{self.index_url}pypi/{MODULE}/json"
        payload: dict[str, Any]
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.load(response)

        # Both wheels are listed, the pure one and the tagged one, so
        # that `nopip1` and `nopip2` have something to choose between.
        listed: list[str] = sorted(entry["filename"]
                                   for entry in payload["urls"])
        self.assertEqual(listed, sorted([self.wheel.name, self.tagged.name]))
        entry: dict[str, Any]
        for entry in payload["urls"]:
            self.assertTrue(entry["url"].endswith(entry["filename"]))

    def test_json_api_reports_a_missing_project(self) -> None:
        """A project the index does not hold is a 404, as on PyPI."""
        # `urllib` raises on a 404 rather than returning it.
        url: str = f"{self.index_url}pypi/nosuchproject/json"
        error: urllib.error.HTTPError
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(url, timeout=30)
        error = caught.exception
        self.assertEqual(error.code, 404)

    @runs_cases
    def test_every_case_bootstraps(self) -> None:
        """Every `bootstrap.py` case fetches and imports from our server.

        This is what Task 5 exists to establish.  The case list comes
        from `bootstrap.py` rather than from a copy here, so a case
        added there cannot quietly go untested.
        """
        # Each case gets a fresh HOME, so every run here is a cold one.
        label: str
        done: subprocess.CompletedProcess[str]
        for label in cases():
            with self.subTest(case=label):
                done = self.run_case(label)
                self.assertEqual(done.returncode, 0, done.stderr[-400:])
                self.assertIn(f"module {MODULE}", done.stdout)
                self.assertIn(ezpkg.__version__, done.stdout)
                self.assertIn(".ezpkg", done.stdout)

    @runs_cases
    def test_every_case_bootstraps_repeatedly(self) -> None:
        """Three runs in one cache all succeed.

        This is the warm path, which nothing tested before.  It is
        where `I.cctfd` lived: the guard every case uses asks whether
        the package is a directory, a single module install is not
        one, and `venv4` deletes the `pip` it would need for the
        second fetch.  `EZPkg.repair_module_layout` is what
        makes this pass.

        Three runs rather than two, because the repair has to be
        idempotent.  An earlier version of it passed two runs and broke
        the cache on the third, by treating the `__init__.py` it had
        just written as another single module to move.
        """
        # One HOME per case, used three times: cold, then warm twice.
        label: str
        home: Path
        run: int
        done: subprocess.CompletedProcess[str]
        for label in cases():
            with self.subTest(case=label):
                home = Path(tempfile.mkdtemp(prefix=f"warm-{label}-",
                                             dir=self.root))
                for run in (1, 2, 3):
                    done = self.run_case(label, home)
                    self.assertEqual(done.returncode, 0,
                                     f"run {run}: {done.stderr[-400:]}")
                    self.assertIn(f"module {MODULE}", done.stdout)

    def test_repair_module_layout_leaves_a_checkout_alone(self) -> None:
        """A module outside the cache is never rewritten."""
        # This file's own directory must survive constructing one.
        source: Path = Path(__file__).resolve().parent / f"{MODULE}.py"
        ezpkg.EZPkg(self.root / "elsewhere")
        self.assertTrue(source.is_file())

    @runs_cases
    def test_the_stdlib_cases_choose_the_tagged_wheel(self) -> None:
        """`nopip1` and `nopip2` prefer the compiled tag, and move its `.data`.

        Both regions were dead until the index carried a wheel with this
        interpreter's tag: the matcher's platform branch short-circuits
        on `py3-none-any`, and its `.data` move needs a wheel with a
        `.data` tree.  See `I.wtmifs` and 6.5.11 of `T.ccp`.

        What this cannot check is that a genuinely compiled wheel would
        import, since ours is pure Python wearing a compiled name.
        """
        # The `.data/purelib` member is the evidence: it only appears
        # beside the module if the move ran.
        label: str
        home: Path
        done: subprocess.CompletedProcess[str]
        wanted: tuple[str, ...] = selected("nopip1", "nopip2")
        if not wanted:
            self.skipTest("neither nopip1 nor nopip2 is selected")
        for label in wanted:
            with self.subTest(case=label):
                home = Path(tempfile.mkdtemp(prefix=f"tagged-{label}-",
                                             dir=self.root))
                done = run_bootstrap_case(label, home, self.index_url)
                self.assertEqual(done.returncode, 0, done.stderr[-400:])
                moved: list[Path] = list(
                    (home / ".ezpkg").rglob("beside_ezpkg.py"))
                self.assertEqual(len(moved), 1, done.stdout)
                self.assertNotIn(".data", str(moved[0]))

    @runs_cases
    def test_no_compatible_wheel_is_reported(self) -> None:
        """A wheel for another platform is refused, not installed.

        The `raise RuntimeError("no compatible wheel found")` in `nopip1`
        and `nopip2` had never executed.  This is as close as a Linux machine
        can get to the failure `I.wtmifs` predicts, which is a manylinux
        wheel being taken on Alpine: here the only wheel on offer is
        tagged for Windows, so nothing matches.
        """
        # An index of its own, holding one wheel for the wrong platform.
        module: Path = Path(__file__).resolve().parent / f"{MODULE}.py"
        wrong: Path = build_wheel(module, DISTRIBUTION, VERSION, SUMMARY,
                                  self.root / "wrong-dist",
                                  tag="cp312-cp312-win_amd64")
        index: Path = build_index([wrong], self.root / "wrong-index")
        server: _IndexServer
        url: str
        server, url = serve_index(index)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        # Both cases read the JSON API, so both see the tag and give
        # up.  `nopip2` as well as `nopip1`, because each carries its own
        # copy of the matcher and its own `raise`.
        label: str
        home: Path
        done: subprocess.CompletedProcess[str]
        wanted: tuple[str, ...] = selected("nopip1", "nopip2")
        if not wanted:
            self.skipTest("neither nopip1 nor nopip2 is selected")
        for label in wanted:
            with self.subTest(case=label):
                home = Path(tempfile.mkdtemp(prefix=f"wrong-{label}-",
                                             dir=self.root))
                done = run_bootstrap_case(label, home, url)
                self.assertNotEqual(done.returncode, 0)
                self.assertIn("no compatible wheel found", done.stderr)
                self.assertNotIn("Traceback", done.stderr)

    @runs_cases
    def test_the_shipping_case_says_which_stage_failed(self) -> None:
        """A failure names the stage it happened in, and the error's type.

        Before 2026-10-01 a bare exception reached the person as
        `cannot fetch ezpkg: ` with nothing after it whenever the
        exception had no text.  See issue `I.fpfipe`.
        """
        # A 404 for `pip`'s own page fails the very first stage.
        if not selected(SHIPPING):
            self.skipTest(f"{SHIPPING} is not selected")
        self.inject("/pip/json", "missing")
        done: subprocess.CompletedProcess[str] = self.run_case(SHIPPING)
        self.assertNotEqual(done.returncode, 0)
        self.assertNotIn("Traceback", done.stderr)
        self.assertIn(f"{MODULE}: choose pip failed: <HTTPError 404",
                      done.stderr)

    @runs_cases
    def test_the_shipping_case_uses_an_importable_ezpkg(self) -> None:
        """An `ezpkg` already on `sys.path` is used, and nothing fetched.

        Under `uv run`, or beside a working copy, `ezpkg` imports
        before the bootstrap has done anything.  `nopip3` fetched `pip`
        and `ezpkg` regardless, and failed with no network.  Here the
        index is dead and this directory, with `ezpkg.py` in it, is on
        the child's `sys.path`.  See `T.ewar` and `I.apiia`.
        """
        # A port nothing listens on: any fetch at all would fail.
        if not selected(SHIPPING):
            self.skipTest(f"{SHIPPING} is not selected")
        home: Path = Path(tempfile.mkdtemp(prefix="importable-",
                                           dir=self.root))
        done: subprocess.CompletedProcess[str] = run_bootstrap_case(
            SHIPPING, home, "http://127.0.0.1:1/", safe_path=False)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        here: Path = Path(__file__).resolve().parent
        self.assertIn(f"from {here / 'ezpkg.py'}", done.stdout)
        self.assertFalse((home / ".ezpkg" / "pip.whl").exists())

    @runs_cases
    def test_the_shipping_case_refuses_a_damaged_pip(self) -> None:
        """A `pip` wheel that fails its SHA-256 is refused, and not kept.

        Without the check a truncated download became `pip.whl`, and the
        failure surfaced one stage later as a zip error from running it,
        which said nothing about the download.  See issue `I.fpfipe`.
        """
        # Half of every wheel, so the digest PyPI lists cannot match.
        if not selected(SHIPPING):
            self.skipTest(f"{SHIPPING} is not selected")
        self.inject(".whl", "truncate")
        home: Path = Path(tempfile.mkdtemp(prefix="damaged-", dir=self.root))
        done: subprocess.CompletedProcess[str] = self.run_case(SHIPPING, home)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("download pip failed: ValueError(", done.stderr)
        self.assertIn("fails its SHA-256 check", done.stderr)
        self.assertFalse((home / ".ezpkg" / "pip.whl").exists())

    @runs_cases
    def test_the_shipping_case_chooses_a_pip_this_python_runs(self) -> None:
        """The newest `pip` whose floor this Python meets, not the newest.

        Three `pip` releases: an old one for any Python 3, one whose
        floor is exactly this Python, and the newest, which wants a
        Python that does not exist yet.  The middle one is right.  When
        `pip` drops a Python, this is what keeps every pasted bootstrap
        on that Python working; see issue `I.bfnprp`.  The releases are
        stand-ins that cannot install anything, so the case fails at the
        next stage, and the wheel it kept says which one it chose.
        """
        # Stand-in `pip` wheels, uploaded oldest to newest.
        if not selected(SHIPPING):
            self.skipTest(f"{SHIPPING} is not selected")
        minor: int = sys.version_info[1]
        offered: list[tuple[str, str]] = [("97.0", ">=3.0"),
                                          ("98.0", f">=3.{minor}"),
                                          ("99.0", f">=3.{minor + 1}")]
        wheels: list[Path] = []
        version: str
        floor: str
        for version, floor in offered:
            source: Path = self.root / f"pip-{version}" / "pip.py"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text('"""A stand-in."""\n')
            wheels.append(build_wheel(source, "pip", version, "A stand-in.",
                                      self.root / "pip-dist", floor=floor))
        index: Path = build_index(wheels, self.root / "pip-index")
        moment: float
        for moment, wheel in enumerate(wheels):
            os.utime(index / "pip" / wheel.name, (moment, moment))
        server: _IndexServer
        url: str
        server, url = serve_index(index)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        # It gets past choosing and downloading, then cannot install.
        home: Path = Path(tempfile.mkdtemp(prefix="choose-", dir=self.root))
        done: subprocess.CompletedProcess[str] = run_bootstrap_case(
            SHIPPING, home, url)
        self.assertIn(f"install {MODULE} failed", done.stderr)
        with zipfile.ZipFile(home / ".ezpkg" / "pip.whl") as kept:
            self.assertIn("pip-98.0.dist-info/METADATA", kept.namelist())

    @runs_cases
    def test_json_api_cases_bootstrap_end_to_end(self) -> None:
        """`nopip1` and `nopip2` fetch and import through the JSON API."""
        # These two are the only cases that bypass pip entirely.
        label: str
        done: subprocess.CompletedProcess[str]
        wanted: tuple[str, ...] = selected("nopip1", "nopip2")
        if not wanted:
            self.skipTest("neither nopip1 nor nopip2 is selected")
        for label in wanted:
            with self.subTest(case=label):
                done = self.run_case(label)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn(f"module {MODULE}", done.stdout)
                self.assertIn(ezpkg.__version__, done.stdout)

    def cached_module(self, name: str) -> tuple[Path, Path]:
        """Plant a copy of this module where a case would install it.

        Arguments:
        * `name` (`str`):
          A directory name to keep one test's cache from another's.

        Returns:
        * (`tuple[Path, Path]`): The cache root, and the planted
          `ezpkg.py` inside it.  The path is the deep one that
          the six virtual environment cases install into, because that
          is the harder of the two for the repair to find.
        """
        # Plant it deep, where `sysconfig` puts a venv's purelib.
        root: Path = self.root / name
        deep: Path = root / "lib" / "python3.12" / "site-packages"
        deep.mkdir(parents=True, exist_ok=True)
        stray: Path = deep / f"{MODULE}.py"
        shutil.copy(Path(__file__).resolve().parent / f"{MODULE}.py", stray)
        return root, stray

    def test_repair_rewrites_a_cached_module(self) -> None:
        """A module in the cache becomes a package directory.

        The repair only ever fires inside a bootstrap child, so
        `__file__` is patched to say this module came from the cache.
        That is what the child sees for real.
        """
        # Plant the module, then make the repair believe it is ours.
        root: Path
        stray: Path
        root, stray = self.cached_module("repair")
        cache: ezpkg.EZPkg = ezpkg.EZPkg(root)
        package: Path | None
        with unittest.mock.patch.object(ezpkg, "__file__",
                                        str(stray)):
            package = cache.repair_module_layout()
        self.assertEqual(package, stray.parent / MODULE)
        self.assertTrue((stray.parent / MODULE / "__init__.py").is_file())
        self.assertFalse(stray.exists())

    def test_repair_survives_another_process_getting_there_first(self
                                                                 ) -> None:
        """The module vanishing mid-repair is not an error.

        Two programs starting at once both read the module and both try
        to remove it; the second must not raise `FileNotFoundError` out
        of a constructor.  Simulated by making the read delete the file,
        which is what the other process would have done.
        """
        # Plant the module, then make reading it also remove it.
        root: Path
        stray: Path
        root, stray = self.cached_module("raced_repair")
        cache: ezpkg.EZPkg = ezpkg.EZPkg(root)
        genuine = Path.read_bytes

        def read_then_vanish(self: Path) -> bytes:
            """Read the file, then delete it as a rival would have."""
            data: bytes = genuine(self)
            if self == stray:
                self.unlink()
            return data

        package: Path | None
        with (unittest.mock.patch.object(ezpkg, "__file__", str(stray)),
              unittest.mock.patch.object(Path, "read_bytes",
                                         read_then_vanish)):
            package = cache.repair_module_layout()
        self.assertEqual(package, stray.parent / MODULE)
        assert package is not None          # narrowed for `mypy`
        self.assertTrue((package / "__init__.py").is_file())

    def test_repair_declines_a_package(self) -> None:
        """Once the module is a package the repair does nothing."""
        # A package has a `__path__`, and nesting would eat `__init__.py`.
        root: Path
        stray: Path
        root, stray = self.cached_module("already")
        cache: ezpkg.EZPkg = ezpkg.EZPkg(root)
        with unittest.mock.patch.object(ezpkg, "__path__",
                                        [str(stray.parent)], create=True):
            self.assertIsNone(cache.repair_module_layout())
        self.assertTrue(stray.is_file())

    def test_repair_declines_what_is_not_a_module(self) -> None:
        """Anything but a `.py` file in the cache is left alone."""
        # A frozen or unusual `__file__` must not be moved.
        root: Path
        root, _ = self.cached_module("odd")
        cache: ezpkg.EZPkg = ezpkg.EZPkg(root)
        other: Path = root / "not_python.txt"
        other.write_text("not a module\n")
        with unittest.mock.patch.object(ezpkg, "__file__",
                                        str(other)):
            self.assertIsNone(cache.repair_module_layout())
        with unittest.mock.patch.object(ezpkg, "__file__", None):
            self.assertIsNone(cache.repair_module_layout())
        self.assertTrue(other.is_file())

    def test_cases_refuses_an_unknown_choice(self) -> None:
        """A typo in `EZPKG_TEST` is refused, not ignored."""
        # Silently running the fast tests would be worse than a refusal.
        with (unittest.mock.patch.dict(
                  os.environ, {"EZPKG_TEST": "COMPLEET"}),
              self.assertRaises(ValueError) as caught):
            cases()
        self.assertIn("COMPLEET", str(caught.exception))

        # And the slow choice really does mean every case.
        with unittest.mock.patch.dict(
                os.environ, {"EZPKG_TEST": "COMPLETE"}):
            self.assertEqual(cases(), tuple(bootstrap.MECHANISMS))

    def test_cases_accepts_case_names(self) -> None:
        """Names select those cases, in `bootstrap.py` order."""
        # Out of order and padded, and still read the way it was meant.
        with unittest.mock.patch.dict(
                os.environ, {"EZPKG_TEST": "pip2, venv1"}):
            self.assertEqual(cases(), ("venv1", "pip2"))
            self.assertEqual(selected("nopip1", "pip2"), ("pip2",))
            self.assertEqual(selected("nopip1"), ())

        # The two choices leave a test's own cases alone.
        with unittest.mock.patch.dict(os.environ, {"EZPKG_TEST": "FAST"}):
            self.assertEqual(selected("nopip1", "nopip2"),
                             ("nopip1", "nopip2"))

        # `NONE` is the baseline, and selects nothing anywhere.
        with unittest.mock.patch.dict(os.environ, {"EZPKG_TEST": "none"}):
            self.assertEqual(cases(), ())
            self.assertEqual(selected("nopip1", "nopip2"), ())

        # A name that is not a case is refused like any other typo.
        with (unittest.mock.patch.dict(
                  os.environ, {"EZPKG_TEST": "pip2,venv9"}),
              self.assertRaises(ValueError) as caught):
            cases()
        self.assertIn("venv9", str(caught.exception))

    def test_case_runners_are_marked(self) -> None:
        """A test runs a bootstrap case exactly when it is `runs_cases`.

        Per-case coverage runs only the marked tests for each case, so a
        test that runs a case without the mark would have its coverage
        credited to no case, and a decision to delete a case would rest
        on numbers that are quietly wrong.  Reading the source is crude,
        and that is the point: the three helpers are the only ways a test
        reaches a case, so naming one of them is what has to be marked.
        """
        # Spelled in pieces, so that this test does not match itself.
        calls: list[str] = [f"{name}(" for name in
                            ("run_case", "run_bootstrap_case", "real_case")]
        found: int = 0
        holder: object
        for holder in list(vars(sys.modules[__name__]).values()):
            if not (isinstance(holder, type)
                    and issubclass(holder, unittest.TestCase)):
                continue
            name: str
            for name in dir(holder):
                if not name.startswith("test_"):
                    continue
                method: Callable[..., Any] = getattr(holder, name)
                runs: bool = any(call in inspect.getsource(method)
                                 for call in calls)
                with self.subTest(test=f"{holder.__name__}.{name}"):
                    self.assertEqual(
                        runs, getattr(method, "runs_cases", False),
                        "runs a case" if runs else "marked but runs none")
                found += runs
        self.assertGreater(found, 0)

    def test_make_certificate_without_openssl(self) -> None:
        """A machine with no `openssl` gets `None`, not an exception.

        This is the path that runs where the TLS tests have to skip,
        which is the one machine where a failure here would be hardest
        to work out.  It is untestable except by pretending.
        """
        # Hide `openssl` and check nothing is raised or left behind.
        directory: Path = self.root / "no-openssl"
        with unittest.mock.patch.object(shutil, "which", return_value=None):
            self.assertIsNone(make_certificate(directory))
        self.assertFalse(directory.exists())

    def test_make_certificate_when_openssl_fails(self) -> None:
        """An `openssl` that exits non-zero also gives `None`."""
        # `/bin/false` is a program that is present and always fails,
        # so this needs no mocking of `subprocess` itself.
        directory: Path = self.root / "bad-openssl"
        with unittest.mock.patch.object(shutil, "which",
                                        return_value="/bin/false"):
            self.assertIsNone(make_certificate(directory))

    def test_readme_survives_a_missing_docstring(self) -> None:
        """Under `python3 -OO` the README keeps its title."""
        # `-OO` strips docstrings, so `inspect.getdoc` returns None.
        root: Path = self.root / "no-docstring"
        cache: ezpkg.EZPkg
        with unittest.mock.patch.object(ezpkg.inspect, "getdoc",
                                        return_value=None):
            cache = ezpkg.EZPkg(root)
        self.assertEqual(cache.readme.read_text().splitlines()[0],
                         "# EZPkg Package Cache")

    def test_installed_package_imports(self) -> None:
        """The installed copy imports and exposes `EZPkg`."""
        # Import in a fresh interpreter, so nothing here can help it.
        # HOME is faked because constructing an `EZPkg` with no
        # argument writes into `~/.ezpkg` for real.
        target: Path = self.root / "importable"
        (self.root / "fake_home").mkdir(exist_ok=True)
        self.assertEqual(self.pip_install(target, DISTRIBUTION).returncode, 0)
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-c",
             f"import {MODULE}; print({MODULE}.EZPkg())"],
            env=dict(os.environ, PYTHONPATH=with_path(target),
                     HOME=str(self.root / "fake_home")),
            capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("EZPkg object", done.stdout)

    def test_ezpkg_constructs(self) -> None:
        """Constructing one makes the cache directory and a README."""
        # Never construct without a root: the default is the real
        # `~/.ezpkg`, and a test must not write there.
        cache: Path = self.root / "cache"
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        self.assertTrue(cache.is_dir())
        self.assertEqual(venv.readme, cache / "README.md")

    def test_readme_comes_from_the_docstring(self) -> None:
        """The README is the constructor docstring, retitled."""
        # The summary line becomes the title; `Arguments:` is dropped.
        cache: Path = self.root / "readme"
        text: str = ezpkg.EZPkg(cache).readme.read_text()
        self.assertTrue(
            text.startswith("# EZPkg Package Cache\n"))
        self.assertIn("Deleting this whole directory is safe.", text)
        self.assertNotIn("Arguments:", text)

    def test_the_readme_describes_the_layout(self) -> None:
        """It names the four directories a person will find.

        The file predated the versioned cache of `T.vcbow` and described
        a layout that no longer existed; see 6.10.5 of `T.rd`.
        """
        # Somebody who opens the cache should recognise what is in it.
        cache: Path = self.root / "layout_readme"
        text: str = ezpkg.EZPkg(cache).readme.read_text()
        name: str
        for name in ("versions/", "wheels/", "requests/", "pending/"):
            with self.subTest(directory=name):
                self.assertIn(name, text)

    def test_the_readme_is_not_rewritten_needlessly(self) -> None:
        """Constructing an object twice writes the file once.

        Making an object used to write a file every time, which is a
        side effect nobody asks a constructor for, and which touched the
        modification time of a file somebody might be reading.
        """
        # The modification time is the observable part, so use it.
        cache: Path = self.root / "unchanged_readme"
        readme: Path = ezpkg.EZPkg(cache).readme
        stamp: int = readme.stat().st_mtime_ns
        os.utime(readme, ns=(stamp - 10**9, stamp - 10**9))
        moved: int = readme.stat().st_mtime_ns
        ezpkg.EZPkg(cache)
        self.assertEqual(readme.stat().st_mtime_ns, moved)

    def test_a_stale_readme_is_replaced(self) -> None:
        """An out of date copy is still rewritten.

        The other half of the rule above: editing the docstring has to
        reach a cache that already has an older file in it.
        """
        # Anything that is not what the docstring says is stale.
        cache: Path = self.root / "stale_readme"
        readme: Path = ezpkg.EZPkg(cache).readme
        readme.write_text("# Something else\n")
        ezpkg.EZPkg(cache)
        self.assertTrue(
            readme.read_text().startswith("# EZPkg Package Cache\n"))

    def test_the_quick_start_is_written(self) -> None:
        """The cache holds the Quick Start program, ready to copy."""
        # The constructor writes it beside the README, from the constant.
        cache: Path = self.root / "quick_start"
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        self.assertEqual(venv.quick_start, cache / "quick_start.py")
        self.assertEqual(venv.quick_start.read_text(encoding="utf-8"),
                         ezpkg.QUICK_START)

    def test_default_root_follows_home(self) -> None:
        """With no argument the cache lands under the home directory."""
        # `Path.home()` reads HOME, so a fake HOME keeps this contained.
        home: Path = self.root / "home"
        home.mkdir(exist_ok=True)
        with unittest.mock.patch.dict(os.environ, {"HOME": str(home)}):
            venv: ezpkg.EZPkg = ezpkg.EZPkg()
        self.assertEqual(venv.root, home / ".ezpkg")
        self.assertTrue((home / ".ezpkg" / "README.md").is_file())


class TlsTest(unittest.TestCase):
    """Serve the index over HTTPS and see what the cases make of it.

    This is the one thing a directory index could never test.  Two
    questions are asked, and the first matters more.  Does a case
    refuse a certificate it cannot verify?  A pasted bootstrap that
    accepted any certificate, or quietly fell back to plain HTTP,
    would hand whoever controls the network the contents of somebody
    else's program, with nobody around to notice.  And does a case
    succeed once the certificate is trusted, so that the refusal is a
    real check rather than TLS being broken outright?

    Note what is not tested here.  Task 3 concluded that a bootstrap
    needs `python3-pip` plus a TLS trust store, and that conclusion is
    about trusting the public certificate authorities well enough to
    reach the real PyPI.  A private certificate tests the opposite:
    that the system trust store can be overridden.  The dependency
    claim needs a fetch from the real index and is not settled here.

    Attributes:
    * `certificate` (`Path`):
      The certificate alone, for a client trust store.
    * `chain` (`Path`):
      The certificate and its key, which the server presents.
    * `index` (`Path`):
      The PEP 503 tree being served.
    * `index_url` (`Path`):
      That tree as an `https` URL.
    * `root` (`Path`):
      The temporary directory holding everything.
    * `server` (`_IndexServer`):
      The server publishing `index` over TLS.

    Constructor:
    * `TlsTest()`, by `unittest` rather than by hand.
    """

    # Built once by `setUpClass`, shared by every test below.
    certificate: Path
    chain: Path
    index: Path
    index_url: str
    root: Path
    server: _IndexServer

    @classmethod
    def setUpClass(cls) -> None:
        """Publish the wheel and serve it over HTTPS."""
        # No `openssl` means no certificate, which means no test.
        cls.root = Path(tempfile.mkdtemp(prefix="tls-"))
        made: tuple[Path, Path] | None = make_certificate(cls.root / "tls")
        if made is None:
            shutil.rmtree(cls.root, ignore_errors=True)
            raise unittest.SkipTest("openssl is not available")
        cls.chain, cls.certificate = made

        # Publish as the other classes do, then serve it with TLS.
        module: Path = Path(__file__).resolve().parent / f"{MODULE}.py"
        wheel: Path = build_wheel(module, DISTRIBUTION, VERSION, SUMMARY,
                                  cls.root / "dist")
        cls.index = build_index([wheel], cls.root / "index")
        cls.server, cls.index_url = serve_index(cls.index, cls.chain)

    @classmethod
    def tearDownClass(cls) -> None:
        """Stop the server, then remove everything the class built."""
        # The class may have skipped before there was a server.
        if hasattr(cls, "server"):
            cls.server.shutdown()
            cls.server.server_close()
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_the_url_is_https(self) -> None:
        """The index really is being served over TLS."""
        # Cheap, and it stops the two tests below passing for the
        # wrong reason if the wrapping were ever dropped.
        self.assertTrue(self.index_url.startswith("https://"),
                        self.index_url)
        self.assertEqual(self.server.scheme, "https")

    @runs_cases
    def test_an_untrusted_certificate_is_refused(self) -> None:
        """No case accepts a certificate it cannot verify."""
        # Nothing tells the child about the certificate, so every case
        # meets an issuer it has never heard of.
        label: str
        home: Path
        done: subprocess.CompletedProcess[str]
        output: str
        for label in cases():
            with self.subTest(case=label):
                home = Path(tempfile.mkdtemp(prefix=f"untrusted-{label}-",
                                             dir=self.root))
                done = run_bootstrap_case(label, home, self.index_url)
                self.assertNotEqual(done.returncode, 0, done.stdout)

                # Failing is not enough; it has to fail over the
                # certificate rather than for some unrelated reason.
                output = (done.stderr + done.stdout).lower()
                self.assertIn("certificate", output, output[-400:])

    @runs_cases
    def test_a_trusted_certificate_is_accepted(self) -> None:
        """Every case succeeds once the certificate is trusted.

        `SSL_CERT_FILE` is what `urllib` honours, through OpenSSL's own
        default verify paths, and `PIP_CERT` is what `pip` honours.
        Both are environment variables, so the `nopip` cases need no
        `ssl` context written into them and no case gains a line.
        """
        # One trust store, two spellings, because two clients read it.
        trust: dict[str, str] = {"SSL_CERT_FILE": str(self.certificate),
                                 "PIP_CERT": str(self.certificate)}
        label: str
        home: Path
        done: subprocess.CompletedProcess[str]
        for label in cases():
            with self.subTest(case=label):
                home = Path(tempfile.mkdtemp(prefix=f"trusted-{label}-",
                                             dir=self.root))
                done = run_bootstrap_case(label, home, self.index_url,
                                          trust)
                self.assertEqual(done.returncode, 0, done.stderr[-400:])
                self.assertIn(f"module {MODULE}", done.stdout)


class InstallTest(unittest.TestCase):
    """Exercise `EZPkg.install` against a local index.

    A throwaway package is built and published for these tests, so
    that nothing here depends on PyPI or on the network.

    Attributes:
    * `cache` (`Path`):
      The cache directory that `install` installs into.
    * `index` (`Path`):
      The PEP 503 tree holding the throwaway package.
    * `index_url` (`str`):
      That same tree as an HTTP URL, for `PIP_INDEX_URL`.
    * `root` (`Path`):
      The temporary directory holding everything.
    * `server` (`_IndexServer`):
      The server publishing `index`.

    Constructor:
    * `InstallTest()`, by `unittest` rather than by hand.
    """

    # Built once by `setUpClass`, shared by every test below.
    cache: Path
    index: Path
    index_url: str
    root: Path
    server: _IndexServer

    @classmethod
    def setUpClass(cls) -> None:
        """Publish a throwaway package into a throwaway index."""
        # A module of its own, so no test can pass by accident.
        cls.root = Path(tempfile.mkdtemp(prefix="install-"))
        module: Path = cls.root / "widget.py"
        module.write_text('"""A throwaway."""\n__version__ = "1.2.3"\n')
        wheel: Path = build_wheel(module, "widget", "1.2.3",
                                  "A throwaway.", cls.root / "dist")

        # A second one whose PyPI name and import name differ, the way
        # `python-dateutil` imports as `dateutil`.
        other: Path = cls.root / "gadgetlib.py"
        other.write_text('"""A second throwaway."""\n'
                         '__version__ = "4.5.6"\n')
        two_named: Path = build_wheel(other, "python-gadget", "4.5.6",
                                      "A second throwaway.",
                                      cls.root / "dist")
        # A third package published twice, so that there is something
        # for `pip` to choose between.  One version per project makes
        # every constraint pass trivially, which tests nothing.
        versions: list[Path] = []
        release: str
        for release in ("1.0.0", "2.0.0"):
            source: Path = cls.root / release / "sprocket.py"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text('"""A versioned throwaway."""\n'
                              f'__version__ = "{release}"\n')
            versions.append(build_wheel(source, "sprocket", release,
                                        "A versioned throwaway.",
                                        cls.root / "dist"))

        # A package that depends on another, so that `pip` fetches
        # something nobody asked for.  Without this the difference
        # between "asked for" and "came along" is unreachable, which is
        # what 6.6.4 of `T.sawaw` rests on.
        needy: Path = cls.root / "needy.py"
        needy.write_text('"""Needs a widget."""\n'
                         '__version__ = "1.0.0"\n')
        depending: Path = build_wheel(needy, "needy", "1.0.0",
                                      "Needs a widget.",
                                      cls.root / "dist",
                                      requires=["widget"])

        # A package that ships a `.pth`, which `sys.path.insert` alone
        # never runs.  One line imports and one names a directory, which
        # are the two things a `.pth` can do; see `T.pf`.
        pathy: Path = cls.root / "pathy.py"
        pathy.write_text('"""Ships a .pth."""\n__version__ = "1.0.0"\n')
        shipping: Path = build_wheel(pathy, "pathy", "1.0.0",
                                     "Ships a .pth.", cls.root / "dist")
        add_root_member(shipping, "inner/tucked.py",
                        '"""Reached only through the .pth."""\n'
                        'WHERE = "inner"\n')
        add_root_member(
            shipping, "zz_pathy.pth",
            "import sys; setattr(sys, 'ezpkg_pth_ran', True)\n"
            "inner\n")

        # A package whose name is not the module it holds, the way a
        # squatted name would be, for the guess `sync_dependencies`
        # must prove; see `T.kdaiis`.
        elsewhere: Path = cls.root / "elsewhere.py"
        elsewhere.write_text('"""Not what its name says."""\n')
        decoy: Path = build_wheel(elsewhere, "decoy", "1.0.0",
                                  "Not what its name says.",
                                  cls.root / "dist")

        # This project too, for the bootstrap the no-`pip` test runs.
        project: Path = build_wheel(
            Path(__file__).resolve().parent / f"{MODULE}.py",
            DISTRIBUTION, VERSION, SUMMARY, cls.root / "dist", floor=FLOOR)

        cls.index = build_index([wheel, two_named, depending, shipping,
                                 decoy, project, *versions],
                                cls.root / "index")
        cls.cache = cls.root / "cache"

        # Start the server last, so nothing can fail after it is up.
        cls.server, cls.index_url = serve_index(cls.index)

    @classmethod
    def tearDownClass(cls) -> None:
        """Stop the server, then remove everything the class built."""
        # Stop serving before the tree underneath goes away.
        cls.server.shutdown()
        cls.server.server_close()

        # One directory holds everything, so one removal suffices.
        shutil.rmtree(cls.root, ignore_errors=True)

    def install(self, target: Path, requirements: object,
                *argv: str) -> str:
        """Run `install` in a child interpreter and return its output.

        A child is used because `install` inserts into `sys.path` and
        imports, neither of which should leak between tests.

        Arguments:
        * `target` (`Path`):
          The cache directory to install into.
        * `requirements` (`object`):
          Whatever to hand `install`: one string, or a list of strings
          and `(import_name, requirement)` pairs.  It is passed through
          `repr`, so it has to be something a literal can express.
        * `argv` (`str`):
          Extra arguments for `pip install`.

        Returns:
        * (`str`): The name and version of each module installed, one
          per line, or standard error if it failed.
        """
        # Point pip at the local index and run the whole thing remotely.
        script: str = (
            "import sys, ezpkg\n"
            "from pathlib import Path\n"
            f"v = ezpkg.EZPkg(Path({str(target)!r}))\n"
            f"m = v.install({requirements!r}, {list(argv)!r})\n"
            "for one in (m if isinstance(m, list) else [m]):\n"
            "    print(one.__name__, one.__version__)")
        environment: dict[str, str] = dict(
            os.environ, PIP_INDEX_URL=self.index_url,
            PYTHONPATH=with_path(Path(__file__).resolve().parent),
            HOME=str(self.root / "home"))
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, check=False)
        return done.stdout.strip() if done.returncode == 0 else done.stderr

    def forget(self, entry: str, name: str) -> None:
        """Undo what an in-process `install` did to this interpreter.

        Arguments:
        * `entry` (`str`):
          The cache root; every `sys.path` entry at or under it is taken
          out again.
        * `name` (`str`):
          The module to drop from `sys.modules`.
        """
        # `install` inserts and imports; both have to be undone.  It
        # inserts the version trees inside the cache, not the cache
        # itself, and a tree left behind made the next test's package
        # look installed once `satisfied` began asking.
        sys.path[:] = [one for one in sys.path
                       if one != entry
                       and not one.startswith(entry + os.sep)]
        sys.modules.pop(name, None)
        importlib.invalidate_caches()

    def test_install_works_in_this_interpreter(self) -> None:
        """`install` fetches and imports without a child process.

        Every other test here drives `install` through a child, which
        keeps `sys.path` clean but means the method's own lines are
        never measured.  This one runs it directly and puts the
        interpreter back afterwards.
        """
        # Register the cleanup before anything is inserted or imported.
        cache: Path = self.root / "in-process"
        self.addCleanup(self.forget, str(cache), "widget")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        module: ModuleType
        with unittest.mock.patch.dict(
                os.environ, {"PIP_INDEX_URL": self.index_url}):
            module = venv.install("widget")
        self.assertEqual(module.__name__, "widget")
        self.assertEqual(module.__version__, "1.2.3")
        self.assertTrue(venv.contains("widget"))

    def test_install_in_process_reports_a_failure(self) -> None:
        """A package the index lacks raises with pip's own reason."""
        # This is the no network case, which a caller must be told about.
        cache: Path = self.root / "in-process-missing"
        self.addCleanup(self.forget, str(cache), "nosuchwidget")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        with (unittest.mock.patch.dict(
                  os.environ, {"PIP_INDEX_URL": self.index_url}),
              self.assertRaises(RuntimeError) as caught):
            venv.install("nosuchwidget")
        self.assertIn("could not fetch", str(caught.exception))

    def test_install_fetches_and_imports(self) -> None:
        """A missing package is fetched and handed back imported."""
        # The package does not exist anywhere but the local index.
        self.assertEqual(self.install(self.cache, "widget"), "widget 1.2.3")
        self.assertTrue(any(p.name.startswith("widget-1.2.3")
                            for p in
                            (self.cache / "versions").iterdir()))

    def test_pip_prefers_the_private_copy(self) -> None:
        """A stashed `pip.whl` is what `download` runs, and it runs."""
        # Without the stash, the interpreter's own `pip` is the answer.
        cache: Path = self.root / "stash"
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        self.assertEqual(venv.pip(), [sys.executable, "-m", "pip"])

        # With it, the wheel is run directly, and says so itself.
        (cache / "pip.whl").write_bytes(pip_wheel()[1])
        self.assertEqual(venv.pip(), [sys.executable,
                                      str(cache / "pip.whl" / "pip")])
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [*venv.pip(), "--version"], capture_output=True, text=True,
            check=False)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertIn(str(cache / "pip.whl"), done.stdout)

    def test_pip_prefers_the_newest_refreshed_copy(self) -> None:
        """A refreshed `pip` beats the bootstrap's, and the newest wins."""
        # Two refreshed copies beside the stash, the later one added last.
        cache: Path = self.root / "refreshed"
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        (cache / "pip.whl").write_bytes(pip_wheel()[1])
        older: Path = cache / "pip-1.0-py3-none-any.whl"
        newer: Path = cache / "pip-2.0-py3-none-any.whl"
        older.write_bytes(b"")
        newer.write_bytes(b"")
        os.utime(older, (1000.0, 1000.0))
        os.utime(newer, (2000.0, 2000.0))
        self.assertEqual(venv.pip(), [sys.executable, str(newer / "pip")])

    def test_refresh_pip_leaves_the_interpreters_pip_alone(self) -> None:
        """Without a private `pip` there is nothing to refresh, or stamp."""
        # Every bootstrap but the shipping one is in this position.
        cache: Path = self.root / "no-private-pip"
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        self.assertIsNone(venv.refresh_pip())
        self.assertFalse((cache / "last_pip").exists())

    def stand_in_pip_index(self) -> str:
        """Serve an index whose only `pip` is a stand-in, release 99.0.

        The real `pip` in a cache downloads it as the newest `pip`; it
        cannot run, but nothing that uses this needs it to.  The server
        stops when the test ends.

        Returns:
        * (`str`): The index URL, for `PIP_INDEX_URL`.
        """
        # One stand-in release, alone in an index of its own.
        source: Path = self.root / "pip-99" / "pip.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('"""A stand-in."""\n')
        stand_in: Path = build_wheel(source, "pip", "99.0", "A stand-in.",
                                     self.root / "pip-99-dist",
                                     floor=">=3.0")
        index: Path = build_index([stand_in], self.root / "pip-99-index")
        server: _IndexServer
        url: str
        server, url = serve_index(index)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return url

    def test_refresh_pip_adds_a_newer_pip(self) -> None:
        """A newer `pip` is added beside the old, and the old makes way.

        The index offers a stand-in `pip` 99.0, which the real one in the
        cache downloads; it cannot run, but nothing here needs it to.  An
        older refreshed copy, past its grace period, is removed, and the
        bootstrap's own `pip.whl` is kept.  A second call inside the
        interval does nothing.
        """
        # A cache holding the bootstrap's `pip` and a superseded refresh.
        url: str = self.stand_in_pip_index()
        cache: Path = self.root / "to-refresh"
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        (cache / "pip.whl").write_bytes(pip_wheel()[1])
        superseded: Path = cache / "pip-1.0-py3-none-any.whl"
        superseded.write_bytes(pip_wheel()[1])
        os.utime(superseded, (1000.0, 1000.0))
        with unittest.mock.patch.dict(os.environ, {"PIP_INDEX_URL": url}):
            added: Path | None = venv.refresh_pip()
            again: Path | None = venv.refresh_pip()
        wanted: Path = cache / "pip-99.0-py3-none-any.whl"
        self.assertEqual(added, wanted)
        self.assertIsNone(again)
        self.assertEqual(venv.pip(), [sys.executable, str(wanted / "pip")])
        self.assertFalse(superseded.exists())
        self.assertTrue((cache / "pip.whl").is_file())
        self.assertTrue((cache / "last_pip").is_file())

    def test_refresh_pip_keeps_what_it_already_has(self) -> None:
        """When the newest `pip` is the one in use, nothing is added."""
        # This class's index offers the same `pip` the cache already holds.
        cache: Path = self.root / "up-to-date"
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        (cache / "pip.whl").write_bytes(pip_wheel()[1])
        with unittest.mock.patch.dict(
                os.environ, {"PIP_INDEX_URL": self.index_url}):
            self.assertIsNone(venv.refresh_pip())
        self.assertEqual(sorted(p.name for p in cache.glob("pip*.whl")),
                         ["pip.whl"])

    def test_refresh_pip_survives_a_dead_index(self) -> None:
        """No network is no refresh, quietly, and no retry until next week."""
        # A port nothing listens on stands in for a missing network.
        cache: Path = self.root / "offline"
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        (cache / "pip.whl").write_bytes(pip_wheel()[1])
        with unittest.mock.patch.dict(
                os.environ, {"PIP_INDEX_URL": "http://127.0.0.1:1/"}):
            self.assertIsNone(venv.refresh_pip())
        self.assertTrue((cache / "last_pip").is_file())
        self.assertEqual(sorted(p.name for p in cache.glob("pip*.whl")),
                         ["pip.whl"])

    def test_refresh_pip_survives_a_failed_move(self) -> None:
        """A newer `pip` that cannot be moved into place changes nothing."""
        # A full disk, say, at the last step.
        url: str = self.stand_in_pip_index()
        cache: Path = self.root / "cannot-move"
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        (cache / "pip.whl").write_bytes(pip_wheel()[1])
        with (unittest.mock.patch.dict(os.environ, {"PIP_INDEX_URL": url}),
              unittest.mock.patch.object(Path, "replace",
                                         side_effect=OSError("disk full"))):
            self.assertIsNone(venv.refresh_pip())
        self.assertEqual(sorted(p.name for p in cache.glob("pip*.whl")),
                         ["pip.whl"])

    def test_refresh_pip_keeps_an_old_copy_it_cannot_remove(self) -> None:
        """A superseded copy that will not go is left, not an error."""
        # The new copy still arrives and is the one used.
        url: str = self.stand_in_pip_index()
        cache: Path = self.root / "cannot-remove"
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        (cache / "pip.whl").write_bytes(pip_wheel()[1])
        superseded: Path = cache / "pip-1.0-py3-none-any.whl"
        superseded.write_bytes(pip_wheel()[1])
        os.utime(superseded, (1000.0, 1000.0))
        with (unittest.mock.patch.dict(os.environ, {"PIP_INDEX_URL": url}),
              unittest.mock.patch.object(Path, "unlink",
                                         side_effect=OSError("busy"))):
            added: Path | None = venv.refresh_pip()
        self.assertEqual(added, cache / "pip-99.0-py3-none-any.whl")
        self.assertTrue(superseded.exists())

    @runs_cases
    def test_nothing_but_python_and_the_bootstrap(self) -> None:
        """A machine with no `pip` runs a declaring program anyway.

        This is the claim `README.md` makes: Python and the pasted
        bootstrap are all that is needed.  An interpreter that has never
        had `pip` stands in for such a machine.  `nopip4` fetches `pip`'s
        wheel, keeps it as `pip.whl`, installs this project with it, and
        `EZPkg` then uses that same copy to fetch what the program
        declares.
        """
        # Only when the shipping case is wanted; see `selected`.
        if not selected(SHIPPING):
            self.skipTest(f"{SHIPPING} is not selected")

        # The zipped `pip` only runs alone if its libraries are inside.
        import pip._vendor
        if getattr(pip._vendor, "DEBUNDLED", False):
            self.skipTest("this pip is debundled, so cannot run alone")

        # A virtual environment made without `pip` is the bare machine.
        bare: Path = self.root / "bare"
        made: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-m", "venv", "--without-pip", str(bare)],
            capture_output=True, text=True, check=False)
        if made.returncode != 0:
            self.skipTest(f"no venv here: {made.stderr.strip()[-200:]}")
        python: Path = (bare / "Scripts" / "python.exe" if os.name == "nt"
                        else bare / "bin" / "python")
        missing: subprocess.CompletedProcess[str] = subprocess.run(
            [str(python), "-c", "import pip"], capture_output=True,
            text=True, check=False)
        self.assertNotEqual(missing.returncode, 0, "pip is not missing")

        # The bootstrap installs this project and leaves `pip` behind.
        home: Path = self.root / "bare-home"
        done: subprocess.CompletedProcess[str] = run_bootstrap_case(
            SHIPPING, home, self.index_url, python=str(python))
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        cache: Path = home / ".ezpkg"
        self.assertTrue((cache / "pip.whl").is_file())

        # The program's own declaration is fetched with that same copy.
        program: Path = self.root / "bare-program" / "prog.py"
        program.parent.mkdir(parents=True, exist_ok=True)
        program.write_text(
            "# /// script\n"
            '# dependencies = ["widget"]\n'
            "# ///\n"
            "import sys\n"
            f"sys.path.insert(0, {str(cache)!r})\n"
            "import ezpkg\n"
            "ezpkg.EZPkg().install()\n"
            "import widget\n"
            "print(widget.__version__)\n")
        environment: dict[str, str] = dict(
            os.environ, HOME=str(home), PIP_INDEX_URL=self.index_url)
        environment.pop("VIRTUAL_ENV", None)
        ran: subprocess.CompletedProcess[str] = subprocess.run(
            [str(python), str(program)], env=environment,
            capture_output=True, text=True, check=False)
        self.assertEqual(ran.returncode, 0, ran.stderr[-400:])
        self.assertEqual(ran.stdout.strip(), "1.2.3")

    def test_install_passes_argv_to_pip(self) -> None:
        """Extra arguments reach `pip install`."""
        # `--no-deps` is harmless here, so success proves it parsed.
        target: Path = self.root / "argv"
        self.assertEqual(self.install(target, "widget", "--no-deps"),
                         "widget 1.2.3")

    def test_install_rejects_bad_argv(self) -> None:
        """A bad argument is our mistake, not the index's.

        `pip` exits 2 for a command line it cannot parse and 1 for
        anything the index is responsible for, which is the one bit of
        discrimination its exit codes offer.  See 6.2.2 of `T.spioc`.
        """
        # A `ValueError` on exit code 2, not the `RuntimeError` that a
        # missing package gets.
        target: Path = self.root / "bad"
        self.assertIn("pip rejected the command line",
                      self.install(target, "widget", "--no-such-option"))

    def test_install_refuses_an_option_as_a_requirement(self) -> None:
        """A requirement starting with a dash is refused before `pip` runs.

        This is the one `pip` would accept and should not:
        `--index-url=...` as a requirement would aim the fetch at
        somebody else's index.  See 6.2.4 of `T.spioc`.
        """
        # Nothing is fetched, so this needs no index at all.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "option")
        bad: str
        for bad in ("--index-url=http://127.0.0.1:1/", "-e."):
            with self.subTest(requirement=bad):
                with self.assertRaises(ValueError) as caught:
                    venv.install([bad])
                self.assertIn("reads as an option", str(caught.exception))

    def test_an_installed_requirement_fetches_nothing(self) -> None:
        """Already importable at an allowed version means no `pip` run.

        Under `uv run`, or from the operating system, the packages are
        already on `sys.path`; fetching them again wasted a download,
        and with no network failed.  `pip` is the package every test
        machine has.
        """
        # Any fetch would have to run `pip`, so forbid that outright.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "installed")
        with unittest.mock.patch.object(
                venv, "download", side_effect=AssertionError("fetched")):
            module: ModuleType = venv.install("pip>=1")
        self.assertEqual(module.__name__, "pip")
        self.assertEqual(list(venv.paths()[2].iterdir()), [])

    def test_install_refuses_a_repeated_import_name(self) -> None:
        """Two entries cannot claim one import name."""
        # `pip` cannot catch this: it never sees our import names, and
        # one module would be returned twice while the other went
        # unmentioned.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "repeat")
        with self.assertRaises(ValueError) as caught:
            venv.install(["widget", "widget"])
        self.assertIn("repeated import name: widget", str(caught.exception))

    def test_pip_owns_requirement_syntax(self) -> None:
        """A malformed requirement is `pip`'s to reject.

        This pins the measurement 6.2.4 of `T.spioc` rests on: `pip` refuses
        bad syntax itself, so reimplementing PEP 508 here would only
        add a way to disagree with it.  Were a future `pip` to stop
        doing so, this test would say so.
        """
        # `pip` answers this without consulting any index.
        target: Path = self.root / "malformed"
        self.assertIn("Invalid requirement",
                      self.install(target, ["bad name with spaces"]))

    def test_install_reports_a_missing_package(self) -> None:
        """A package the index does not have raises a clear error."""
        # This is the `I.whwnn` shape: say why, do not just fail to import.
        target: Path = self.root / "missing"
        output: str = self.install(target, "nosuchwidget")
        self.assertIn("could not fetch nosuchwidget", output)

    def test_install_takes_several_at_once(self) -> None:
        """A list installs every requirement and returns them in order."""
        # Both throwaway packages, in one `pip`, unpacked positionally.
        target: Path = self.root / "several"
        self.assertEqual(
            self.install(target, ["widget", ("gadgetlib", "python-gadget")]),
            "widget 1.2.3\ngadgetlib 4.5.6")
        self.assertEqual(sorted(p.name.split("-")[0] for p in
                                (target / "versions").iterdir()),
                         ["python_gadget", "widget"])

    def test_install_accepts_a_version_constraint(self) -> None:
        """A requirement carries its own constraint, as `pip` spells it."""
        # No extra API is needed for a version: PEP 508 already has one.
        target: Path = self.root / "constrained"
        self.assertEqual(self.install(target, ["widget>=1.0,<2"]),
                         "widget 1.2.3")
        self.assertIn("could not fetch widget==9.9.9",
                      self.install(self.root / "impossible",
                                   ["widget==9.9.9"]))

    def test_the_cache_has_three_directories_and_one_rule(self) -> None:
        """Only `versions` is ever put on `sys.path`.

        That one sentence is the jail of 6.3.1 of `T.vcbow`.  A wheel under
        `pending` is an inert zip, so nothing in it can have run, and
        nothing there is importable.
        """
        # Install something, then check where things ended up.
        cache: Path = self.root / "layout"
        self.addCleanup(self.forget, str(cache), "widget")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        pending: Path
        wheels: Path
        versions: Path
        requests: Path
        pending, wheels, versions, requests = venv.paths()
        with unittest.mock.patch.dict(
                os.environ, {"PIP_INDEX_URL": self.index_url}):
            venv.install("widget")

        # The artifact is kept, the tree is unpacked, the holding area
        # is empty, and only the tree is on the path.
        self.assertEqual([p.name for p in sorted(wheels.iterdir())],
                         ["widget-1.2.3-py3-none-any.sha256",
                          "widget-1.2.3-py3-none-any.whl"])
        self.assertEqual(len(list(versions.iterdir())), 1)
        self.assertEqual(list(pending.iterdir()), [])
        tree: Path = next(versions.iterdir())
        self.assertIn(str(tree), sys.path)
        self.assertNotIn(str(pending), sys.path)
        self.assertNotIn(str(wheels), sys.path)
        self.assertNotIn(str(requests), sys.path)
        self.assertNotIn(str(cache), sys.path)

        # One record per request, named by its hash, rather than one
        # shared file two writers would fight over.
        self.assertEqual(len(list(requests.iterdir())), 1)

        # Unpacking happens inside the jail, so `versions` holds only
        # finished trees and never a partial one.
        self.assertEqual([p.name for p in versions.iterdir()],
                         [venv.version_key(next(wheels.glob("*.whl")))])

    def test_unpack_moves_a_data_purelib_beside_the_modules(self) -> None:
        """A wheel's `.data/purelib` contents land beside its modules.

        This is the part of the wheel specification `unpack` took on
        when it stopped using `pip install`; see 6.3.12 of `T.vcbow`.  Coverage
        found it unexercised, because no wheel the suite built had a
        `.data` tree at all.
        """
        # Build a wheel of the awkward shape, then unpack it by hand.
        source: Path = self.root / "dataful" / "dataful.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('"""d."""\n__version__ = "1.0.0"\n')
        wheel: Path = build_wheel(source, "dataful", "1.0.0", "d",
                                  self.root / "dataful-dist")
        add_data_member(wheel, "purelib", "beside.py", "VALUE = 7\n")

        # The member must come out one level up, not under `.data`.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "dataful-cache")
        staged: Path = Path(shutil.copy(wheel, venv.paths()[0]))
        tree: Path = venv.unpack(staged)
        self.assertTrue((tree / "beside.py").is_file())
        self.assertEqual((tree / "beside.py").read_text(), "VALUE = 7\n")
        self.assertEqual(list(tree.glob("*.data")), [])

    def test_unpack_reuses_a_tree_that_is_already_there(self) -> None:
        """Two requests resolving to one version share one tree.

        `sprocket<2` and `sprocket==1.0.0` are different requests, so
        both consult `pip`, but they resolve to the same version and
        must not unpack it twice.
        """
        # Two requests, one tree, and the wheel kept exactly once.
        cache: Path = self.root / "shared"
        self.addCleanup(self.forget, str(cache), "sprocket")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        with unittest.mock.patch.dict(
                os.environ, {"PIP_INDEX_URL": self.index_url}):
            venv.install("sprocket<2")
            # As a second program would start: without the first tree on
            # `sys.path`, which would otherwise satisfy the second request.
            self.forget(str(cache), "sprocket")
            venv.install("sprocket==1.0.0")
        pending: Path
        wheels: Path
        versions: Path
        requests: Path
        pending, wheels, versions, requests = venv.paths()
        self.assertEqual(len(list(versions.iterdir())), 1)
        self.assertEqual([p.name for p in wheels.glob("*.whl")],
                         ["sprocket-1.0.0-py3-none-any.whl"])
        self.assertEqual(list(pending.iterdir()), [])
        empty: tuple[list[str], list[str]] = ([], [])
        self.assertEqual(len((venv.remember("sprocket<2") or empty)[0]), 1)
        self.assertEqual(
            len((venv.remember("sprocket==1.0.0") or empty)[0]), 1)

        # Two requests, so two records, both naming the one tree.
        self.assertEqual(len(list(requests.iterdir())), 2)

    def test_a_second_version_in_one_process_is_refused(self) -> None:
        """Two calls asking for two versions of one module fail loudly.

        `sys.modules` is keyed by name, so the second call used to hand
        back the first version without a word.  Asking again for the
        same version is still fine.  See 6.3.11 of `T.vcbow`.
        """
        # 1.0.0 first, then the same again, then 2.0.0.
        cache: Path = self.root / "two-versions"
        self.addCleanup(self.forget, str(cache), "sprocket")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        with unittest.mock.patch.dict(
                os.environ, {"PIP_INDEX_URL": self.index_url}):
            first: ModuleType = venv.install("sprocket==1.0.0")
            again: ModuleType = venv.install("sprocket==1.0.0")
            with self.assertRaises(RuntimeError) as caught:
                venv.install("sprocket==2.0.0")
        self.assertEqual(first.__version__, "1.0.0")
        self.assertIs(again, first)
        self.assertIn("sprocket is already imported from", str(caught.exception))
        self.assertIn("one process holds one version", str(caught.exception))

    def test_unpack_survives_losing_the_race(self) -> None:
        """A tree appearing mid-unpack is accepted, not fought over.

        Two programs starting at once both unpack, and the loser of the
        rename has to take the winner's tree rather than raise.  This is
        the concurrency answer of 6.3.9 of `T.vcbow`, and coverage found it
        unexercised because one process never loses.
        """
        # Make the rename into place fail exactly as a lost race does.
        cache: Path = self.root / "raced"
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        source: Path = self.root / "raced-src" / "raced.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('"""r."""\n__version__ = "1.0.0"\n')
        wheel: Path = build_wheel(source, "raced", "1.0.0", "r",
                                  self.root / "raced-dist")

        # A `.data` member, so that the unpacking really does rename
        # something besides the tree itself.  Without one, the claim
        # below that only the staging rename fails is untested: the
        # tracer showed the genuine rename was never reached.
        add_data_member(wheel, "purelib", "tucked.py", 'WHERE = "data"\n')
        staged: Path = Path(shutil.copy(wheel, venv.paths()[0]))
        expected: Path = venv.paths()[2] / venv.version_key(staged)

        # Only the staging rename fails; the `.data` moves must not.
        genuine = Path.rename
        allowed: list[str] = []

        def refuse(self: Path, target: "str | PurePath") -> Path:
            """Fail the one rename that puts a tree into place."""
            if Path(target) == expected:
                raise OSError("another process got there first")
            allowed.append(Path(target).name)
            return genuine(self, target)

        with unittest.mock.patch.object(Path, "rename", refuse):
            self.assertEqual(venv.unpack(staged), expected)

        # The `.data` member really was moved, which is what makes the
        # claim above -- that only the one rename fails -- a tested
        # claim rather than a hopeful comment.
        self.assertIn("tucked.py", allowed, allowed)

    def test_a_version_tree_names_the_interpreter(self) -> None:
        """A tree name carries version, interpreter and platform.

        This is the `I.nicav` fix: the same directory reached by a
        different Python would otherwise load whatever the last one
        left behind.
        """
        # The name is built from the wheel's own filename plus this
        # interpreter, so it can be predicted exactly.
        cache: Path = self.root / "named"
        self.addCleanup(self.forget, str(cache), "widget")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        with unittest.mock.patch.dict(
                os.environ, {"PIP_INDEX_URL": self.index_url}):
            venv.install("widget")
        expected: str = (f"widget-1.2.3-{sys.implementation.cache_tag}"
                         f"-{sysconfig.get_platform()}")
        self.assertEqual([p.name for p in venv.paths()[2].iterdir()],
                         [expected])

    def test_a_remembered_request_needs_no_pip(self) -> None:
        """A request answered before costs a read, not an invocation.

        Keyed on what was asked rather than on what it resolved to, so
        no version expression is compared and no PEP 440 parser can
        disagree with `pip`; see 6.3.4 of `T.vcbow`.
        """
        # First call fetches; second must not run `pip` at all.
        cache: Path = self.root / "remembered"
        self.addCleanup(self.forget, str(cache), "sprocket")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        calls: list[Sequence[str]] = []
        genuine = subprocess.run

        def counted(*args: Any, **kwargs: Any) -> Any:
            """Record an invocation and then perform it."""
            calls.append(args[0])
            return genuine(*args, **kwargs)

        with (unittest.mock.patch.dict(
                  os.environ, {"PIP_INDEX_URL": self.index_url}),
              unittest.mock.patch.object(ezpkg.subprocess, "run",
                                         counted)):
            first: ModuleType = venv.install("sprocket<2")
            del sys.modules["sprocket"]
            second: ModuleType = venv.install("sprocket<2")
        self.assertEqual(first.__version__, "1.0.0")
        self.assertEqual(second.__version__, "1.0.0")
        self.assertEqual(len(calls), 1, calls)

    def test_a_deleted_tree_counts_as_a_miss(self) -> None:
        """Deleting the cache is safe, so a stale record is ignored."""
        # The README promises the directory can be removed; a record
        # pointing at a tree that is gone must not be believed.
        cache: Path = self.root / "stale"
        self.addCleanup(self.forget, str(cache), "widget")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        with unittest.mock.patch.dict(
                os.environ, {"PIP_INDEX_URL": self.index_url}):
            venv.install("widget")
            self.assertIsNotNone(venv.remember("widget"))
            shutil.rmtree(next(venv.paths()[2].iterdir()))
            self.assertIsNone(venv.remember("widget"))

    def test_four_processes_share_one_cache(self) -> None:
        """Four real programs fetching at once leave one of everything.

        Everything else here proves concurrency with threads or a forced
        `OSError`, which is simulation; this is observation.  The index
        is made slow on purpose, so the four genuinely overlap rather
        than finishing one after another, and they are started before
        any of them can finish.
        """
        # Delay the wheel itself, not the project page.  The page is
        # read during resolution, long before anything is unpacked, so
        # delaying it lets the four drift apart again; delaying the
        # wheel is what makes them arrive at the unpacking together.
        inject(self, self.server, ".whl", "slow")
        cache: Path = self.root / "four_ways"
        here: str = str(Path(__file__).resolve().parent)
        script: str = (
            "import sys\n"
            f"sys.path.insert(0, {here!r})\n"
            "import ezpkg\n"
            "from pathlib import Path\n"
            f"cache = Path({str(cache)!r})\n"
            "one = ezpkg.EZPkg(cache).install('sprocket<2')\n"
            "print(one.__version__)\n")
        environment: dict[str, str] = dict(
            os.environ, PIP_INDEX_URL=self.index_url,
            HOME=str(self.root / "four_home"))
        environment.pop("VIRTUAL_ENV", None)

        # Start all four, then wait: none can finish before the last
        # one has started.
        started: list[subprocess.Popen[str]] = [
            subprocess.Popen([sys.executable, "-c", script],
                             env=environment, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
            for _ in range(4)]
        finished: list[tuple[int, str, str]] = []
        child: subprocess.Popen[str]
        for child in started:
            out: str
            err: str
            out, err = child.communicate(timeout=300)
            finished.append((child.returncode, out.strip(), err.strip()))

        # Every one of them has to succeed, with the same answer.
        code: int
        out_text: str
        err_text: str
        for code, out_text, err_text in finished:
            self.assertEqual(code, 0, err_text[-400:])
            self.assertEqual(out_text, "1.0.0")

        # And the cache has to hold exactly one of everything.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        pending: Path
        wheels: Path
        versions: Path
        requests: Path
        pending, wheels, versions, requests = venv.paths()
        self.assertEqual(len(list(versions.iterdir())), 1)
        self.assertEqual([p.name for p in wheels.glob("*.whl")],
                         ["sprocket-1.0.0-py3-none-any.whl"])
        self.assertEqual(len(list(requests.iterdir())), 1)
        self.assertEqual(list(pending.iterdir()), [])

    def test_four_processes_collide_on_one_unpack(self) -> None:
        """Four processes entering `unpack` together leave one tree.

        The test above shows four real programs sharing a cache, but it
        does not reach the rename race: the window between asking
        whether a tree exists and renaming one into place is a
        millisecond or two, and four processes started together drift
        further apart than that while `pip` runs.

        So each process downloads first, then waits at a barrier until
        every one of them has arrived, and only then unpacks.  That puts
        them inside the window on purpose.  See 6.4.3 of `T.ci`.
        """
        # Each child downloads, waits for the others, then unpacks.
        # More racers than four, because the window is a millisecond or
        # two wide and the odds of two landing in it rise with the count.
        racers: int = 8
        cache: Path = self.root / "collide"
        here: str = str(Path(__file__).resolve().parent)
        script: str = (
            "import os, sys, time\n"
            f"sys.path.insert(0, {here!r})\n"
            "from pathlib import Path\n"
            "import ezpkg\n"
            f"cache = Path({str(cache)!r})\n"
            "venv = ezpkg.EZPkg(cache)\n"
            "arrived = venv.download(['sprocket<2'])\n"
            "gate = cache / 'gate'\n"
            "gate.mkdir(exist_ok=True)\n"
            "(gate / str(os.getpid())).touch()\n"
            f"while len(list(gate.iterdir())) < {racers}:\n"
            "    time.sleep(0.005)\n"
            "trees = [venv.unpack(one) for one in arrived]\n"
            "print(trees[0].name)\n")
        environment: dict[str, str] = dict(
            os.environ, PIP_INDEX_URL=self.index_url,
            HOME=str(self.root / "collide_home"))
        environment.pop("VIRTUAL_ENV", None)

        # Start all four and collect what each of them said.
        started: list[subprocess.Popen[str]] = [
            subprocess.Popen([sys.executable, "-c", script],
                             env=environment, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
            for _ in range(racers)]
        answers: list[str] = []
        child: subprocess.Popen[str]
        for child in started:
            out: str
            err: str
            out, err = child.communicate(timeout=300)
            self.assertEqual(child.returncode, 0, err[-500:])
            answers.append(out.strip())

        # Every one of them names the same tree, and there is one.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        versions: Path = venv.paths()[2]
        self.assertEqual(len(set(answers)), 1, answers)
        self.assertEqual([p.name for p in versions.iterdir()], answers[:1])

    def test_a_kept_wheel_records_its_hash(self) -> None:
        """The hash of what arrived is written down beside the wheel.

        Not what the index claimed, which is unavailable anyway since
        `pip download` refuses `--report`; see 6.3.7 of `T.vcbow`.  This is the
        identity `T.sawaw` approves, and the only thing that could notice
        a distribution re-uploaded under a version it had already used.
        """
        # Install, then check the sidecar against the file itself.
        cache: Path = self.root / "hashed"
        self.addCleanup(self.forget, str(cache), "widget")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)
        with unittest.mock.patch.dict(
                os.environ, {"PIP_INDEX_URL": self.index_url}):
            venv.install("widget")
        wheels: Path = venv.paths()[1]
        wheel: Path = next(wheels.glob("*.whl"))
        sidecar: Path = wheel.with_suffix(".sha256")
        self.assertTrue(sidecar.is_file())
        self.assertEqual(sidecar.read_text().strip(), venv.digest(wheel))
        self.assertEqual(len(sidecar.read_text().strip()), 64)

    def test_a_wrong_import_name_is_reported(self) -> None:
        """`pip` succeeding and the import failing is its own error.

        `python-gadget` fetches, and its import name is guessed as
        `python_gadget`, but the module inside is `gadgetlib`.  This is
        the mistake a user will actually make, and until now the error
        they would see was never checked.
        """
        # The fetch succeeds; only the import is wrong.
        output: str = self.install(self.root / "wrong_name",
                                   ["python-gadget"])
        self.assertIn("ModuleNotFoundError", output)
        self.assertIn("python_gadget", output)

    def program(self, name: str, requirement: str) -> Path:
        """Write a little program that installs one requirement.

        Approvals live beside the main program, so they can only be
        exercised by a real program in a directory of its own: an
        in-process test would put `ezpkg_test.ezpkg` in the project.

        Arguments:
        * `name` (`str`):
          A directory name, to keep one test's program from another's.
        * `requirement` (`str`):
          What the program should install.

        Returns:
        * (`Path`): The program written.
        """
        # Its own directory, its own cache, its own approvals file.
        where: Path = self.root / name
        where.mkdir(parents=True, exist_ok=True)
        program: Path = where / "prog.py"
        program.write_text(
            "import sys\n"
            f"sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})\n"
            "import ezpkg\n"
            "from pathlib import Path\n"
            f"v = ezpkg.EZPkg(Path({str(where / 'cache')!r}))\n"
            f"print(v.install({requirement!r}).__version__)\n")
        return program

    def run_program(self, program: Path,
                    **extra: str) -> subprocess.CompletedProcess[str]:
        """Run one of those programs against the local index.

        Arguments:
        * `program` (`Path`):
          What `program` returned.
        * `extra` (`str`):
          More environment, such as `EZPKG_APPROVE`.

        Returns:
        * (`subprocess.CompletedProcess[str]`): The finished child.
        """
        # The index is local; everything else is inherited.
        environment: dict[str, str] = dict(
            os.environ, PIP_INDEX_URL=self.index_url, **extra)
        environment.pop("VIRTUAL_ENV", None)
        return subprocess.run([sys.executable, str(program)],
                              env=environment, capture_output=True,
                              text=True, check=False)

    def test_without_approvals_the_user_is_told_not_asked(self) -> None:
        """With no approvals file, what arrived is reported and run.

        The person who merely ran somebody's program cannot judge
        `charset-normalizer 3.3.2` either way, so asking them would be a
        rubber stamp.  See `T.sawaw`.
        """
        # Nothing is prompted, and the listing separates the two kinds.
        program: Path = self.program("told", "widget")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-300:])
        self.assertEqual(done.stdout.strip(), "1.2.3")
        self.assertIn("1 requested, 1 downloaded", done.stderr)
        self.assertIn("widget 1.2.3  asked for", done.stderr)
        self.assertFalse(program.with_suffix(".ezpkg").exists())

    def test_the_author_records_approvals(self) -> None:
        """`EZPKG_APPROVE=write` writes the file beside the program."""
        # Wheel name and digest, one per line, sorted for the diff.
        program: Path = self.program("record", "widget")
        done: subprocess.CompletedProcess[str] = self.run_program(
            program, EZPKG_APPROVE="write")
        self.assertEqual(done.returncode, 0, done.stderr[-300:])
        record: Path = program.with_suffix(".ezpkg")
        self.assertTrue(record.is_file())
        rows: list[str] = [line for line in record.read_text().splitlines()
                           if not line.startswith("#")]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].startswith("widget-1.2.3-py3-none-any.whl "))
        self.assertEqual(len(rows[0].split()[1]), 64)

        # And dated, since the list is what `pip` chose that day.
        self.assertRegex(record.read_text(),
                         r"(?m)^# Resolved: \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_matching_approvals_are_silent(self) -> None:
        """A recipient whose approvals match is not bothered at all."""
        # Record once, then run again from an empty cache.
        program: Path = self.program("silent", "widget")
        self.assertEqual(
            self.run_program(program, EZPKG_APPROVE="write").returncode, 0)
        shutil.rmtree(program.parent / "cache")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-300:])
        self.assertEqual(done.stdout.strip(), "1.2.3")
        self.assertNotIn("not approved", done.stderr)

    def test_an_unapproved_wheel_is_refused(self) -> None:
        """A dependency changed without reapproval stops the program.

        This is the protection the whole step exists for, and it works
        because the author, who could tell one package from another, said
        once what was allowed.
        """
        # Approve `widget`, then ask for `sprocket` without reapproving.
        # The lock says nothing about `sprocket`, so it is fetched, and
        # the check is what stops it.
        program: Path = self.program("refused", "widget")
        self.assertEqual(
            self.run_program(program, EZPKG_APPROVE="write").returncode, 0)
        program.write_text(program.read_text().replace("widget", "sprocket"))
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("is not approved", done.stderr)
        self.assertIn("sprocket-2.0.0", done.stderr)

        # And nothing was unpacked, because the refusal comes first.
        trees: list[Path] = list((program.parent / "cache"
                                  / "versions").iterdir())
        self.assertTrue(all("sprocket" not in tree.name for tree in trees),
                        trees)

    def test_the_approvals_lock_the_versions(self) -> None:
        """A recorded version is fetched even when a newer one exists.

        The approvals record `sprocket` 1.0.0; the program then asks for
        any `sprocket`, and the index has 2.0.0.  Without the lock, `pip`
        would fetch 2.0.0 and the check would refuse it.  See `T.rafal`.
        """
        # Record 1.0.0, then loosen the requirement and start cold.
        program: Path = self.program("locking", "sprocket==1.0.0")
        self.assertEqual(
            self.run_program(program, EZPKG_APPROVE="write").returncode, 0)
        program.write_text(program.read_text().replace("==1.0.0", ""))
        shutil.rmtree(program.parent / "cache")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-300:])
        self.assertEqual(done.stdout.strip(), "1.0.0")

    def test_the_lock_is_not_answered_by_an_unlocked_record(self) -> None:
        """A warm cache from an unlocked run does not bypass the lock.

        `skip` fetches `sprocket` 2.0.0 and remembers the request; the
        ordinary run that follows must still get the recorded 1.0.0.
        """
        # Record 1.0.0, loosen, then warm the cache with 2.0.0.
        program: Path = self.program("warm_lock", "sprocket==1.0.0")
        self.assertEqual(
            self.run_program(program, EZPKG_APPROVE="write").returncode, 0)
        program.write_text(program.read_text().replace("==1.0.0", ""))
        skipped: subprocess.CompletedProcess[str] = self.run_program(
            program, EZPKG_APPROVE="skip")
        self.assertEqual(skipped.stdout.strip(), "2.0.0", skipped.stderr)
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-300:])
        self.assertEqual(done.stdout.strip(), "1.0.0")

    def test_write_upgrades_past_the_lock(self) -> None:
        """`write` resolves afresh, so it is how packages are upgraded."""
        # Record 1.0.0, loosen, and record again from a cold cache.
        program: Path = self.program("upgrade", "sprocket==1.0.0")
        self.assertEqual(
            self.run_program(program, EZPKG_APPROVE="write").returncode, 0)
        program.write_text(program.read_text().replace("==1.0.0", ""))
        shutil.rmtree(program.parent / "cache")
        done: subprocess.CompletedProcess[str] = self.run_program(
            program, EZPKG_APPROVE="write")
        self.assertEqual(done.returncode, 0, done.stderr[-300:])
        self.assertEqual(done.stdout.strip(), "2.0.0")
        self.assertIn("sprocket-2.0.0",
                      program.with_suffix(".ezpkg").read_text())

    def test_a_lock_dependencies_moved_past_names_the_file(self) -> None:
        """A requirement the lock cannot meet says what to regenerate."""
        # Record 1.0.0, then demand 2.0.0 without reapproving.
        program: Path = self.program("moved", "sprocket==1.0.0")
        self.assertEqual(
            self.run_program(program, EZPKG_APPROVE="write").returncode, 0)
        program.write_text(program.read_text().replace("1.0.0", "2.0.0"))
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("may be the conflict", done.stderr)
        self.assertIn("prog.ezpkg", done.stderr)

    def test_write_stamps_the_date_into_the_block(self) -> None:
        """`write` asks, then puts the date in Part 1 as `exclude-newer`.

        The same date as the approvals' `# Resolved:` line, so the `.py`
        carries it when it travels alone.  The question names the line,
        because the file is the author's.  See `T.srdisb`.
        """
        # Asked on a terminal, naming the line, and answered yes.
        program: Path = self.declaring_program(
            "stamped", 'dependencies = ["widget"]',
            "import widget\nprint(widget.__version__)")
        seen: str = self.answer_on_a_terminal(program, b"y\n",
                                              EZPKG_APPROVE="write")
        lines: list[str] = program.read_text().splitlines()
        at: int = next(index for index, line in enumerate(lines, 1)
                       if line.startswith("# exclude-newer = "))
        self.assertIn("could I add `exclude-newer = ", seen)
        self.assertIn(f"at line {at} of prog.py?", seen)
        self.assertIn("resolution date", seen)
        metadata: dict[str, Any] | None = ezpkg.script_metadata(
            program.read_text())
        assert metadata is not None
        when: str = metadata["tool"]["uv"]["exclude-newer"]
        self.assertIn(f"# Resolved: {when}\n",
                      program.with_suffix(".ezpkg").read_text())
        self.assertEqual(metadata["dependencies"], ["widget"])

        # The program still runs, under its lock, where the date is not
        # even tried: the lock already says exactly which versions.
        shutil.rmtree(program.parent / "cache")
        again: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(again.stdout.strip(), "1.2.3", again.stderr[-300:])
        self.assertNotIn("exclude-newer", again.stderr)

    def test_write_leaves_the_program_alone_unless_told(self) -> None:
        """No terminal, or a no, leaves the program exactly as it was.

        Either way the approvals are still written, and the author is
        told how to add the date by hand.
        """
        # No terminal at all: nobody to agree, so no edit.
        program: Path = self.declaring_program(
            "unstamped", 'dependencies = ["widget"]',
            "import widget\nprint(widget.__version__)")
        before: str = program.read_text()
        done: subprocess.CompletedProcess[str] = self.run_program(
            program, EZPKG_APPROVE="write")
        self.assertEqual(done.returncode, 0, done.stderr[-300:])
        self.assertEqual(program.read_text(), before)
        self.assertIn("left as it was", done.stderr)
        self.assertIn("by hand", done.stderr)
        self.assertTrue(program.with_suffix(".ezpkg").is_file())

        # A terminal that answers no.
        seen: str = self.answer_on_a_terminal(program, b"n\n",
                                              EZPKG_APPROVE="write")
        self.assertIn("could I add", seen)
        self.assertEqual(program.read_text(), before)

    def dated_sprocket(self) -> None:
        """Date `sprocket` 1.0.0 to 2020 and 2.0.0 to 2024 on the index.

        And have the index publish upload times, all undone after the
        test, since the index is shared by the whole class.
        """
        # The file times are the upload times; see `send_simple_json`.
        wheel: Path
        for wheel in (self.index / "sprocket").glob("*.whl"):
            held: os.stat_result = wheel.stat()
            self.addCleanup(os.utime, wheel,
                            (held.st_atime, held.st_mtime))
            year: int = 2020 if "-1.0.0-" in wheel.name else 2024
            stamp: float = datetime.datetime(
                year, 1, 1, tzinfo=datetime.UTC).timestamp()
            os.utime(wheel, (stamp, stamp))
        self.server.upload_times = True
        self.addCleanup(setattr, self.server, "upload_times", False)

    def give_pip(self, program: Path, wheel: Path) -> None:
        """Make `wheel` the `pip` that a program's cache runs.

        `last_pip` is written too, so `refresh_pip` does not swap it for
        the older `pip` the local index offers: against PyPI the index's
        is the newest, but here it is the one installed.

        Arguments:
        * `program` (`Path`):
          A program from `declaring_program`.
        * `wheel` (`Path`):
          The `pip` wheel, as `dating_pip` returns it.
        """
        # The cache is beside the program, as `declaring_program` puts it.
        cache: Path = program.parent / "cache"
        cache.mkdir(exist_ok=True)
        shutil.copyfile(wheel, cache / "pip.whl")
        (cache / "last_pip").write_text("")

    @unittest.skipIf(dating_pip() is None,
                     "no pip here filters by upload date")
    def test_the_date_keeps_to_older_releases(self) -> None:
        """A program sent without approvals gets what was newest then.

        `sprocket` 2.0.0 is on the index, but uploaded after the date in
        Part 1, so 1.0.0 is fetched.
        """
        # No approvals, only a date between the two releases, and a
        # `pip` that can apply it.
        self.dated_sprocket()
        program: Path = self.declaring_program(
            "dated", 'dependencies = ["sprocket"]\n[tool.uv]\n'
                     'exclude-newer = "2022-01-01T00:00:00Z"',
            "import sprocket\nprint(sprocket.__version__)")
        dating: Path | None = dating_pip()
        assert dating is not None
        self.give_pip(program, dating)
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-300:])
        self.assertEqual(done.stdout.strip(), "1.0.0", done.stderr)

    def test_an_index_without_upload_times_ignores_the_date(self) -> None:
        """No upload times means no date, said once, rather than failure.

        Twice: with the installed `pip`, which may not know the option at
        all, and with one that does, against an index of plain HTML,
        which carries no upload times.
        """
        # Each `pip` in a cache of its own.
        dating: Path | None = dating_pip()
        label: str
        wheel: Path | None
        for label, wheel in (("installed", None), ("dating", dating)):
            if label == "dating" and wheel is None:
                continue
            with self.subTest(pip=label):
                program: Path = self.declaring_program(
                    f"undated_{label}",
                    'dependencies = ["sprocket"]\n[tool.uv]\n'
                    'exclude-newer = "2022-01-01T00:00:00Z"',
                    "import sprocket\nprint(sprocket.__version__)")
                if wheel is not None:
                    self.give_pip(program, wheel)
                done: subprocess.CompletedProcess[str] = self.run_program(
                    program)
                self.assertEqual(done.returncode, 0, done.stderr[-300:])
                self.assertEqual(done.stdout.strip(), "2.0.0")
                self.assertIn("fetching without the program's exclude-newer",
                              done.stderr)

    def test_an_altered_wheel_is_refused(self) -> None:
        """An approval that no longer matches the artifact is refused."""
        # Corrupt the recorded digest, which is what a swapped wheel
        # would look like from here.
        program: Path = self.program("altered", "widget")
        self.assertEqual(
            self.run_program(program, EZPKG_APPROVE="write").returncode, 0)
        record: Path = program.with_suffix(".ezpkg")
        record.write_text(record.read_text().replace(
            record.read_text().split()[-1], "0" * 64))
        shutil.rmtree(program.parent / "cache")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("does not match its approval", done.stderr)

    def test_skip_bypasses_the_approvals(self) -> None:
        """`EZPKG_APPROVE=skip` is for an author still deciding."""
        # The approvals say 1.0.0; skip installs 2.0.0 anyway.
        program: Path = self.program("skipping", "sprocket==1.0.0")
        self.assertEqual(
            self.run_program(program, EZPKG_APPROVE="write").returncode, 0)
        program.write_text(program.read_text().replace("1.0.0", "2.0.0"))
        done: subprocess.CompletedProcess[str] = self.run_program(
            program, EZPKG_APPROVE="skip")
        self.assertEqual(done.returncode, 0, done.stderr[-300:])
        self.assertEqual(done.stdout.strip(), "2.0.0")

    def test_approvals_are_written_afresh_from_a_warm_cache(self) -> None:
        """`write` fetches even when the cache could answer.

        An author recording approvals is choosing again, and the
        remembered answer may be weeks old, so `write` asks the index
        rather than the cache.  See `T.rafal`.
        """
        # Populate the cache first, with no approvals at all.
        program: Path = self.program("warm", "widget")
        self.assertEqual(self.run_program(program).returncode, 0)
        self.assertFalse(program.with_suffix(".ezpkg").exists())

        # Now record: what arrived is listed, so it was fetched.
        done: subprocess.CompletedProcess[str] = self.run_program(
            program, EZPKG_APPROVE="write")
        self.assertEqual(done.returncode, 0, done.stderr[-300:])
        self.assertIn("1 requested, 1 downloaded", done.stderr)
        self.assertIn("approvals written to", done.stderr)
        rows: list[str] = [line for line in
                           program.with_suffix(".ezpkg").read_text(
                               ).splitlines() if not line.startswith("#")]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].startswith("widget-1.2.3"))

    def answer_on_a_terminal(self, program: Path, reply: bytes,
                             **extra: str) -> str:
        """Run a program with a real terminal and answer its question.

        A pseudoterminal is the only honest way to test a prompt read
        from `/dev/tty`.  `os.login_tty` is what makes the slave the
        child's **controlling** terminal, which is what `/dev/tty`
        resolves to; inheriting the descriptor is not enough, and a
        child started with `start_new_session` alone reports
        `No such device or address`.

        `login_tty` also puts the child's own output on the terminal, so
        everything comes back through the master rather than through
        pipes.

        Arguments:
        * `program` (`Path`):
          The program to run.
        * `reply` (`bytes`):
          What to type, including the newline.
        * `extra` (`str`):
          More environment.

        Returns:
        * (`str`): Everything the child wrote to the terminal.
        """
        # A terminal pair, with the slave as the child's own.  The
        # attaching is done by a launcher after `exec` rather than by
        # `preexec_fn`, which runs between `fork` and `exec` and can
        # deadlock in a process that has threads -- and this one has a
        # server thread.
        master: int
        slave: int
        master, slave = pty.openpty()
        launcher: str = (
            "import os, sys\n"
            "os.login_tty(int(sys.argv[1]))\n"
            "os.execv(sys.executable, [sys.executable, sys.argv[2]])\n")
        environment: dict[str, str] = dict(
            os.environ, PIP_INDEX_URL=self.index_url, **extra)
        environment.pop("VIRTUAL_ENV", None)
        child: subprocess.Popen[bytes] = subprocess.Popen(
            [sys.executable, "-c", launcher, str(slave), str(program)],
            env=environment, pass_fds=(slave,))
        os.close(slave)
        os.write(master, reply)
        child.wait(timeout=300)

        # Read until the terminal has nothing more to give.
        seen: bytes = b""
        block: bytes
        while True:
            try:
                block = os.read(master, 4096)
            except OSError:
                break
            if not block:
                break
            seen += block
            if len(seen) > 8192:
                break
        os.close(master)
        return seen.decode(errors="replace")

    def test_a_terminal_is_asked_once_and_yes_proceeds(self) -> None:
        """With a terminal and no approvals, one question is asked."""
        # The count is on the question, because the count is the part
        # anybody can judge.
        program: Path = self.program("asked_yes", "widget")
        seen: str = self.answer_on_a_terminal(program, b"y\n")
        self.assertIn("1 requested, 1 to install", seen)
        self.assertIn(PROMPT, seen)
        self.assertIn("1.2.3", seen)

    def test_always_writes_the_marker_and_proceeds(self) -> None:
        """`a` installs and records that the question is settled.

        Wayne's reason for wanting this: nearly everybody approves, and
        the point of the question is that a person understands packages
        are being downloaded, not that they are nagged forever.
        """
        # The answer says where the switch is, because one keystroke
        # making a permanent decision deserves a visible way back.
        program: Path = self.program("asked_always", "widget")
        seen: str = self.answer_on_a_terminal(program, b"a\ny\n")
        self.assertIn(PROMPT, seen)
        self.assertIn(CONFIRM, seen)
        self.assertIn("From now on packages will be downloaded silently",
                      seen)
        self.assertIn("ALWAYS safe to delete the whole directory", seen)
        self.assertIn("rm -rf", seen)
        self.assertIn("1.2.3", seen)
        marker: Path = program.parent / "cache" / "FOREVER_APPROVE"
        self.assertTrue(marker.is_file())
        self.assertIn("Delete it to be asked again",
                      marker.read_text())
        self.assertIn(str(marker), seen)

    def test_always_asks_twice_and_takes_no_for_an_answer(self) -> None:
        """Declining the confirmation returns to the question.

        Not wanting this for ever is not the same as not wanting it now,
        so the install is still on offer and the marker is not written.
        """
        # `a`, then no, then plain yes: two questions, one install.
        program: Path = self.program("asked_twice", "widget")
        seen: str = self.answer_on_a_terminal(program, b"a\nn\ny\n")
        self.assertEqual(seen.count(CONFIRM), 1, seen)
        self.assertEqual(seen.count(PROMPT), 2, seen)
        self.assertIn("1.2.3", seen)
        self.assertFalse(
            (program.parent / "cache" / "FOREVER_APPROVE").exists())

    def test_answers_are_case_insensitive(self) -> None:
        """`Y` and `A` work as well as `y` and `a`.

        Somebody with caps lock on, or who has seen prompts that wanted
        capitals, should not be told they made a typo.
        """
        # Capitals throughout, including the confirmation.
        program: Path = self.program("asked_caps", "widget")
        seen: str = self.answer_on_a_terminal(program, b"A\nY\n")
        self.assertNotIn("Please answer", seen)
        self.assertIn("1.2.3", seen)
        self.assertTrue(
            (program.parent / "cache" / "FOREVER_APPROVE").is_file())

    def test_the_marker_means_no_question(self) -> None:
        """With the marker in place nothing is asked, even on a terminal.

        The cache is emptied of packages first, so this is a cold fetch
        that would otherwise ask.
        """
        # `a` once, then a second cold install that must be silent.
        program: Path = self.program("marked", "widget")
        self.answer_on_a_terminal(program, b"a\ny\n")
        shutil.rmtree(program.parent / "cache" / "versions")
        shutil.rmtree(program.parent / "cache" / "requests")
        seen: str = self.answer_on_a_terminal(program, b"")
        self.assertNotIn("go ahead?", seen)
        self.assertIn("1.2.3", seen)

    def test_the_marker_never_hides_a_mismatch(self) -> None:
        """An altered wheel is still refused, marker or no marker.

        The invariant that makes the marker safe: it answers the
        question, and the question is only asked when an author approved
        nothing.  A wheel that fails its approval is a different matter
        and no amount of impatience should conceal it.
        """
        # Approve, corrupt the record, mark forever, then fetch cold.
        program: Path = self.program("marked_mismatch", "widget")
        self.assertEqual(
            self.run_program(program, EZPKG_APPROVE="write").returncode,
            0)
        record: Path = program.with_suffix(".ezpkg")
        record.write_text(record.read_text().replace(
            record.read_text().split()[-1], "0" * 64))
        (program.parent / "cache" / "FOREVER_APPROVE").write_text("x\n")
        shutil.rmtree(program.parent / "cache" / "versions")
        shutil.rmtree(program.parent / "cache" / "requests")

        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("does not match its approval", done.stderr)

    def test_declining_installs_nothing(self) -> None:
        """Saying no installs nothing, and nothing has run.

        The refusal comes before any wheel is unpacked, so declining is
        clean rather than half done; see 6.6.2 of `T.sawaw`.
        """
        # Answer no, then look at what the cache holds.
        program: Path = self.program("asked_no", "widget")
        seen: str = self.answer_on_a_terminal(program, b"n\n")
        self.assertIn(PROMPT, seen)
        self.assertIn("declined", seen)
        versions: Path = program.parent / "cache" / "versions"
        self.assertEqual(list(versions.iterdir()), [])

        # And the download is discarded, because a refusal means do not
        # install this, not keep it for later.
        pending: Path = program.parent / "cache" / "pending"
        self.assertEqual(list(pending.iterdir()), [])

    def test_an_empty_answer_asks_again(self) -> None:
        """A bare newline is no answer at all, so there is no default.

        A distracted Enter neither installs nor declines; it is a typo
        like any other, and enough of them in a row decline, as
        `ATTEMPTS` typos always have.
        """
        # Enter, then yes: asked twice, and installed.
        program: Path = self.program("asked_enter", "widget")
        seen: str = self.answer_on_a_terminal(program, b"\ny\n")
        self.assertEqual(seen.count(PROMPT), 2, seen)
        self.assertIn("Please answer y, n, a for always, or ? for more.",
                      seen)
        self.assertIn("1.2.3", seen)

        # Enter every time: asked until the patience runs out.
        program = self.program("asked_enter_only", "widget")
        seen = self.answer_on_a_terminal(
            program, b"\n" * ezpkg.ATTEMPTS)
        self.assertEqual(seen.count(PROMPT), ezpkg.ATTEMPTS, seen)
        self.assertIn("declined", seen)

    def test_an_unrecognised_answer_asks_again(self) -> None:
        """Something that is neither yes nor no is taken for a typo."""
        # Two bad answers, then yes: the question appears three times.
        program: Path = self.program("asked_again", "widget")
        seen: str = self.answer_on_a_terminal(program, b"x\nmaybe\ny\n")
        self.assertEqual(
            seen.count("Please answer y, n, a for always, or ? for more."),
            2, seen)
        self.assertEqual(seen.count(PROMPT), 3, seen)
        self.assertIn("1.2.3", seen)

    def test_a_question_mark_says_more_and_asks_again(self) -> None:
        """`?` describes each wheel, then puts the question again.

        The terse listing is the default; somebody who wants to know
        more can ask without leaving the program.  What was observed is
        kept apart from what the package claims about itself.
        """
        # Ask for detail, then agree.
        program: Path = self.program("curious", "widget")
        seen: str = self.answer_on_a_terminal(program, b"?\ny\n")
        self.assertEqual(seen.count(PROMPT), 2, seen)
        self.assertIn("fetched from", seen)
        self.assertIn("it says:", seen)
        self.assertIn("sha256:", seen)
        self.assertIn("KB", seen)
        self.assertIn("1.2.3", seen)

    def test_asking_for_detail_is_not_a_typo(self) -> None:
        """`?` does not spend the patience meant for mistakes.

        Curiosity is not punished: the attempt limit counts answers that
        make no sense, and `?` makes sense.
        """
        # More question marks than the limit, then a real answer.
        program: Path = self.program("patient", "widget")
        seen: str = self.answer_on_a_terminal(
            program, b"?\n" * (ezpkg.ATTEMPTS + 2) + b"n\n")
        self.assertEqual(seen.count("fetched from"), ezpkg.ATTEMPTS + 2)
        self.assertIn("declined", seen)
        self.assertNotIn("Please answer", seen)

    def test_a_summary_cannot_rewrite_the_terminal(self) -> None:
        """Escape sequences in a package's own words are removed.

        The summary is written by whoever uploaded the package, which is
        the adversary in the case this is meant to help with, so it is
        never printed as it arrived.
        """
        # A wheel whose summary carries a colour escape.
        source: Path = self.root / "escaping" / "escaping.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('"""e."""\n__version__ = "1.0.0"\n')
        wheel: Path = build_wheel(source, "escaping", "1.0.0",
                                  "Red \x1b[31mtext\x1b[0m here.",
                                  self.root / "escaping-dist")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "escaping-cache")
        told: str = venv.summary(wheel)
        self.assertIn("Red", told)
        self.assertNotIn("\x1b", told)
        self.assertTrue(told.isprintable(), repr(told))

    def test_a_dependency_is_shown_as_having_come_along(self) -> None:
        """What was asked for is told apart from what arrived with it.

        This is what 6.6.4 of `T.sawaw` rests on: nobody ever looks at what a
        single `pip install` actually pulls in, and the listing is the
        first time most people would see the number.  Until a test wheel
        had a dependency, the `came along` branch had never executed at
        all -- found by tracing child processes.
        """
        # `needy` depends on `widget`, so two arrive for one request.
        program: Path = self.program("came_along", "needy")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertIn("1 requested, 2 downloaded", done.stderr)
        self.assertIn("needy 1.0.0  asked for", done.stderr)
        self.assertIn("widget 1.2.3  came along", done.stderr)

    def test_the_detail_also_separates_the_two_kinds(self) -> None:
        """`?` marks a dependency as having come along as well."""
        # The same distinction, in the verbose form.
        program: Path = self.program("came_along_detail", "needy")
        seen: str = self.answer_on_a_terminal(program, b"?\ny\n")
        self.assertIn("needy 1.0.0, asked for,", seen)
        self.assertIn("widget 1.2.3, came along,", seen)
        self.assertIn("Needs a widget.", seen)

    def test_a_summary_that_is_absent_or_unreadable(self) -> None:
        """A wheel with no summary, or no metadata at all, says nothing.

        Both fall back to an empty string rather than raising, because a
        listing must not be the thing that stops a program.
        """
        # A wheel whose METADATA carries no `Summary` header at all.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "quiet-cache")
        bare: Path = self.root / "quiet" / "bare.whl"
        bare.parent.mkdir(parents=True, exist_ok=True)
        archive: zipfile.ZipFile
        with zipfile.ZipFile(bare, "w") as archive:
            archive.writestr("bare-1.0.0.dist-info/METADATA",
                             "Metadata-Version: 2.1\nName: bare\n")
        self.assertEqual(venv.summary(bare), "")

        # And something that is not a zip at all.
        broken: Path = self.root / "quiet" / "broken.whl"
        broken.write_text("this is not a wheel\n")
        self.assertEqual(venv.summary(broken), "")

        # And a wheel with no `.dist-info` in it.
        empty: Path = self.root / "quiet" / "empty.whl"
        with zipfile.ZipFile(empty, "w") as archive:
            archive.writestr("nothing.py", "x = 1\n")
        self.assertEqual(venv.summary(empty), "")

    def test_asking_gives_up_eventually(self) -> None:
        """Nonsense does not keep the question alive forever.

        A terminal feeding rubbish would otherwise hang the program, so
        the question is put `ATTEMPTS` times and then declined.
        """
        # More bad answers than there are attempts.
        program: Path = self.program("asked_enough", "widget")
        seen: str = self.answer_on_a_terminal(
            program, b"x\n" * (ezpkg.ATTEMPTS + 3))
        self.assertEqual(seen.count(PROMPT), ezpkg.ATTEMPTS)
        self.assertIn("declined", seen)

    def test_approvals_replace_the_question(self) -> None:
        """An approved set is verified in silence, not asked about.

        The author's judgement replaces the recipient's prompt rather
        than being added to it: the recipient cannot judge a package
        name, and somebody who could already did.
        """
        # Record approvals, empty the cache, then run with a terminal.
        program: Path = self.program("no_question", "widget")
        self.assertEqual(
            self.run_program(program, EZPKG_APPROVE="write").returncode, 0)
        shutil.rmtree(program.parent / "cache")
        seen: str = self.answer_on_a_terminal(program, b"n\n")
        self.assertNotIn("go ahead?", seen)
        self.assertIn("1.2.3", seen)

    def test_without_a_terminal_nothing_is_asked(self) -> None:
        """No terminal means nobody to ask, so the fetch goes ahead.

        Failing instead would break every program started by `cron`, a
        build or a service manager on its first day.  The approvals file
        is how a guarantee is had; a listing is only a notification.
        """
        # `run_program` uses pipes, so there is no controlling terminal.
        program: Path = self.program("no_terminal", "widget")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-300:])
        self.assertNotIn("go ahead?", done.stderr)
        self.assertEqual(done.stdout.strip(), "1.2.3")

    def test_install_takes_the_newest_version_by_default(self) -> None:
        """With no constraint, `pip` picks the highest version published."""
        # `sprocket` is published twice, so this is a real choice.
        self.assertEqual(self.install(self.root / "newest", ["sprocket"]),
                         "sprocket 2.0.0")

    def test_a_constraint_chooses_among_versions(self) -> None:
        """A constraint picks an older version over a newer one.

        This is what one version per project could never test: the
        constraint has to be what decides, rather than there being
        nothing else to decide between.
        """
        # Each of these has both 1.0.0 and 2.0.0 available to it.
        expectations: dict[str, str] = {
            "sprocket<2": "sprocket 1.0.0",
            "sprocket==1.0.0": "sprocket 1.0.0",
            "sprocket>=2": "sprocket 2.0.0",
            "sprocket!=2.0.0": "sprocket 1.0.0",
        }
        requirement: str
        expected: str
        for requirement, expected in expectations.items():
            with self.subTest(requirement=requirement):
                target: Path = self.root / requirement.replace("<", "_lt_")
                self.assertEqual(self.install(target, [requirement]),
                                 expected)

    def test_an_impossible_constraint_fails(self) -> None:
        """A constraint no published version satisfies is reported."""
        # Both versions exist; neither is 3.0.0.
        self.assertIn("could not fetch sprocket>=3",
                      self.install(self.root / "unsatisfiable",
                                   ["sprocket>=3"]))

    def test_install_runs_pip_once_for_the_set(self) -> None:
        """Several requirements cost one `pip`, not one each.

        This is the point of `T.spioc`: `pip` resolves the set together,
        and one invocation is what makes `T.vcbow`'s freshness check
        affordable.  Counted rather than inferred, by wrapping
        `subprocess.run` and letting the real one do the work.
        """
        # Run it in process, so the call being counted is the real one.
        cache: Path = self.root / "once"
        self.addCleanup(self.forget, str(cache), "widget")
        self.addCleanup(self.forget, str(cache), "gadgetlib")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(cache)

        # Count the invocations without replacing what they do.
        calls: list[Sequence[str]] = []
        genuine = subprocess.run

        def counted(*args: Any, **kwargs: Any) -> Any:
            """Record one `pip` invocation and then perform it."""
            calls.append(args[0])
            return genuine(*args, **kwargs)

        widget: ModuleType
        gadget: ModuleType
        with (unittest.mock.patch.dict(
                  os.environ, {"PIP_INDEX_URL": self.index_url}),
              unittest.mock.patch.object(ezpkg.subprocess, "run",
                                         counted)):
            widget, gadget = venv.install(
                ["widget", ("gadgetlib", "python-gadget")])
        self.assertEqual(len(calls), 1, calls)
        self.assertIn("widget", calls[0])
        self.assertIn("python-gadget", calls[0])
        self.assertEqual(widget.__version__, "1.2.3")
        self.assertEqual(gadget.__version__, "4.5.6")

    def test_install_takes_a_pair_of_names(self) -> None:
        """A distribution named apart from its module still works."""
        # `pip` is asked for `python-gadget`; `import` gets `gadgetlib`.
        target: Path = self.root / "two_names"
        self.assertEqual(
            self.install(target, [("gadgetlib", "python-gadget")]),
            "gadgetlib 4.5.6")
        self.assertTrue(any(p.name.startswith("python_gadget")
                            for p in (target / "versions").iterdir()))

    def test_one_name_is_not_enough(self) -> None:
        """Asking by import name alone fails when the names differ."""
        # This is why the pair form exists rather than being inferred.
        target: Path = self.root / "one_name"
        self.assertIn("could not fetch gadgetlib",
                      self.install(target, "gadgetlib"))

    def test_an_unmet_python_floor_stops_the_install(self) -> None:
        """A program declaring a Python it is not running is told so.

        The service `pip` does for a wheel's `Requires-Python`, done for
        the program's own declaration: a clear line at the top instead of
        a `SyntaxError` in a module the person has never heard of.
        """
        # Nothing is fetched, because the check comes before the fetch.
        program: Path = self.declaring_program(
            "too_old",
            'requires-python = ">=3.99"\ndependencies = ["widget"]',
            "import widget\nprint(widget.__version__)")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("declares requires-python >=3.99", done.stderr)
        self.assertFalse((program.parent / "cache" / "versions").exists())

    def test_a_met_python_floor_is_silent(self) -> None:
        """A floor this interpreter satisfies is not mentioned at all."""
        # `>=3.11` is the floor `ezpkg.py` itself declares.
        program: Path = self.declaring_program(
            "new_enough",
            f'requires-python = "{FLOOR}"\ndependencies = ["widget"]',
            "import widget\nprint(widget.__version__)")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "1.2.3")
        self.assertNotIn("requires-python", done.stderr)

    def test_an_unreadable_floor_is_left_to_pip(self) -> None:
        """A specifier outside the whitelist installs anyway.

        `>=3.9,<4` is satisfied here, but the point is that we do not
        judge it either way: the install proceeds and PEP 440 stays
        `pip`'s business.
        """
        # A shape we deliberately do not interpret.
        program: Path = self.declaring_program(
            "unjudged",
            'requires-python = ">=3.9,<4"\ndependencies = ["widget"]',
            "import widget\nprint(widget.__version__)")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "1.2.3")

    def test_a_floor_of_the_wrong_type_is_refused(self) -> None:
        """TOML permits a number there; PEP 723 does not."""
        # `requires-python = 3.11` is the typo this catches.
        program: Path = self.declaring_program(
            "float_floor", "requires-python = 3.11", "print('ran')")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("must be a string", done.stderr)

    def test_check_python_can_be_asked_directly(self) -> None:
        """`check_python` takes a declaration, for a caller that has one."""
        # The in-process form, which needs no program of its own.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "asked")
        venv.check_python({"requires-python": ">=3.0"})
        venv.check_python({})
        with self.assertRaises(RuntimeError) as caught:
            venv.check_python({"requires-python": ">=99.0"})
        self.assertIn("declares requires-python >=99.0",
                      str(caught.exception))

    def test_writing_approvals_needs_somewhere_to_write(self) -> None:
        """`write` with no program file says so instead of lying.

        Found by the tracer 2026-09-27: `approve` returning `None` was
        an unexercised line, and following it up showed `gate` printing
        "approvals written to None", which claims a file was written.
        """
        # `python3 -c` is the program with nowhere to keep approvals.
        here: str = str(Path(__file__).resolve().parent)
        environment: dict[str, str] = dict(
            os.environ, PIP_INDEX_URL=self.index_url,
            EZPKG_APPROVE="write")
        environment.pop("VIRTUAL_ENV", None)
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-c",
             (f"import sys; sys.path.insert(0, {here!r}); "
              "import ezpkg; from pathlib import Path; "
              f"v = ezpkg.EZPkg(Path({str(self.root / 'nowhere')!r})); "
              "print(v.install('widget').__version__)")],
            env=environment, capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "1.2.3")
        self.assertIn("nowhere to write approvals", done.stderr)

    def test_a_terminal_at_end_of_file_declines(self) -> None:
        """A terminal that reads nothing is not an answer, and stops.

        The tracer found this line unexercised.  A real pseudoterminal
        cannot easily be made to return end of file on demand without a
        race, so `terminal` is patched instead: the case under test is
        `consent`'s handling of an empty read, not the opening of
        `/dev/tty`, which the pty tests cover.
        """
        # An empty read means the terminal went away.  Asking again
        # would loop until `ATTEMPTS` ran out and ask nobody anything.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "hangup")
        spoken: _KeptStringIO = _KeptStringIO()
        with unittest.mock.patch.object(
                ezpkg.EZPkg, "terminal",
                return_value=(spoken, _KeptStringIO(""))):
            self.assertFalse(venv.consent([], ["widget"]))
        self.assertIn(PROMPT, spoken.getvalue())
        self.assertEqual(spoken.getvalue().count("go ahead?"), 1)

    def test_ask_wants_a_yes_and_a_terminal(self) -> None:
        """Only `y` or `yes` is a yes; a typo is asked again, once each.

        No terminal, and a terminal gone away, are both no, since the
        question is about editing a file nobody present agreed to.
        """
        # Answers in turn, each on its own pretend terminal.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "asking")
        typed: str
        expected: bool
        for typed, expected in (("y\n", True), ("YES\n", True),
                                ("n\n", False), ("x\ny\n", True),
                                ("x\nx\nx\ny\n", False), ("", False)):
            with self.subTest(typed=typed):
                spoken: _KeptStringIO = _KeptStringIO()
                with unittest.mock.patch.object(
                        ezpkg.EZPkg, "terminal",
                        return_value=(spoken, _KeptStringIO(typed))):
                    self.assertIs(venv.ask("Edit?"), expected)
                self.assertIn("Edit? [y=>Yes/n=>No] ", spoken.getvalue())
        with unittest.mock.patch.object(ezpkg.EZPkg, "terminal",
                                        return_value=None):
            self.assertFalse(venv.ask("Edit?"))

    def test_verify_without_approvals_checks_nothing(self) -> None:
        """`verify` on its own is silent when there is no approvals file.

        Unreachable through `gate`, which looks before it calls, so this
        guard is for anybody calling the public method directly.  The
        tracer found the line; the guard is worth keeping.
        """
        # This test process is itself a program with no approvals file.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "unchecked")
        self.assertIsNone(venv.approved())
        venv.verify([])

    def test_a_record_for_another_request_is_ignored(self) -> None:
        """A cache record that names a different request is not used.

        One file per request, named after a digest of it, so a mismatch
        means the file was edited or a digest collided.  Either way the
        record is not evidence about this request.
        """
        # Write a good record, then make it claim to be another request.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "mismatch")
        venv.remember("widget", ["widget-1.2.3"], ["widget-1.2.3.whl"])
        records: list[Path] = list(venv.paths()[3].iterdir())
        self.assertEqual(len(records), 1, records)
        records[0].write_text(records[0].read_text().replace(
            '"request": "widget"', '"request": "something else"'))
        self.assertIsNone(venv.remember("widget"))

    def test_a_pth_file_is_executed(self) -> None:
        """A `.pth` import line runs, which `sys.path` alone never does.

        `setuptools` ships `distutils-precedence.pth` and `pytest-cov`
        ships `pytest-cov.pth`; without this both install half working,
        which is the whole of `T.pf`.
        """
        # The `.pth` marks `sys` itself, which the program can see.
        program: Path = self.declaring_program(
            "pth_runs", 'dependencies = ["pathy"]',
            "import pathy\n"
            "print(getattr(sys, 'ezpkg_pth_ran', False))")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "True")

    def test_a_pth_directory_line_is_added(self) -> None:
        """A `.pth` line naming a directory puts it on `sys.path` too.

        The other half of what a `.pth` does, and the half that makes a
        package like `setuptools` find its vendored code.
        """
        # `tucked` exists only inside the directory the `.pth` names.
        program: Path = self.declaring_program(
            "pth_directory", 'dependencies = ["pathy"]',
            "import tucked\nprint(tucked.WHERE)")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "inner")

    def test_the_cache_still_wins_over_the_path(self) -> None:
        """Running `.pth` files must not cost the cache its precedence.

        `site.addsitedir` appends, so calling it alone would put the
        cache **behind** everything already on `sys.path`.  Measured
        2026-09-28, which is why `provide` inserts first and calls it
        second.
        """
        # The tree has to be ahead of the project directory, which is
        # where an installed copy of the same name would otherwise win.
        program: Path = self.declaring_program(
            "precedence", 'dependencies = ["pathy"]',
            "import pathy\n"
            "print(sys.path.index(str(Path(pathy.__file__).parent)))")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "0")

    def age(self, path: Path, seconds: float) -> None:
        """Back-date something, which is how this suite tells time.

        No clock is injected and nothing sleeps: the cache's own notion of
        age is file modification time, so `os.utime` is an exact lever
        where a sleep would be a slow approximation.  See 6.11.1 of `T.gc`.

        Arguments:
        * `path` (`Path`):
          What to back-date.
        * `seconds` (`float`):
          How far into the past to move it.
        """
        # Both times, since something reading `atime` would be as
        # confused as something reading `mtime`.
        when: float = path.stat().st_mtime - seconds
        os.utime(path, (when, when))

    def test_litter_finds_abandoned_staging(self) -> None:
        """A directory left under `pending/` is litter once it is old."""
        # A killed unpack leaves exactly this behind.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "staging")
        pending: Path = venv.paths()[0]
        stale: Path = pending / "unpacking-abandoned"
        stale.mkdir()
        (stale / "half.py").write_text("")
        self.assertEqual(venv.litter(), [])
        self.age(stale, 2 * ezpkg.CULL_GRACE)
        self.assertEqual(venv.litter(), [stale])

    def test_litter_spares_a_young_download(self) -> None:
        """Another program's download in progress is left alone.

        The grace period is about concurrency, not tidiness: a fetch
        happening right now lives in `pending/` and belongs to somebody.
        """
        # Young, therefore somebody else's business.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "young")
        busy: Path = venv.paths()[0] / "tmpsomething"
        busy.mkdir()
        self.assertEqual(venv.litter(), [])

    def test_litter_finds_a_tree_nothing_names(self) -> None:
        """A `versions/` tree no request record names is unreachable."""
        # `install` finds trees through the records, so an unnamed tree
        # can never be found again however good it looks.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "orphan")
        versions: Path = venv.paths()[2]
        orphan: Path = versions / "widget-9.9.9-py3-none-any"
        orphan.mkdir()
        self.age(orphan, 2 * ezpkg.CULL_GRACE)
        self.assertEqual(venv.litter(), [orphan])

    def test_litter_spares_a_tree_a_record_names(self) -> None:
        """A tree still spoken for survives however old it is."""
        # Age is not the test for these; being named is.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "spoken")
        versions: Path = venv.paths()[2]
        kept: Path = versions / "widget-1.2.3-py3-none-any"
        kept.mkdir()
        venv.remember("widget", [kept.name], ["widget-1.2.3.whl"])
        self.age(kept, 100 * ezpkg.CULL_GRACE)
        self.assertEqual(venv.litter(), [])

    def test_cull_removes_the_litter_and_says_what_it_took(self) -> None:
        """`cull` removes what `litter` names and returns it."""
        # One of each kind, and a good tree that must survive.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "sweep")
        pending: Path
        versions: Path
        pending, _, versions, _ = venv.paths()
        junk: Path = pending / "unpacking-dead"
        junk.mkdir()
        orphan: Path = versions / "gone-0.0.1-py3-none-any"
        orphan.mkdir()
        kept: Path = versions / "widget-1.2.3-py3-none-any"
        kept.mkdir()
        venv.remember("widget", [kept.name], ["widget-1.2.3.whl"])
        path: Path
        for path in (junk, orphan, kept):
            self.age(path, 2 * ezpkg.CULL_GRACE)

        self.assertEqual(venv.cull(), sorted([junk, orphan]))
        self.assertFalse(junk.exists())
        self.assertFalse(orphan.exists())
        self.assertTrue(kept.is_dir())

    def test_cull_collects_a_wheel_nothing_names(self) -> None:
        """An unreferenced wheel is litter, like an unreferenced tree.

        This reverses an earlier decision to leave `wheels/` alone, and
        the reason is that records now age out: their wheels would be the
        one thing in the cache that grew for ever.  See `T.gc`.
        """
        # Old and named by no record, so nothing can ever look at it.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "dead_wheel")
        wheel: Path = venv.paths()[1] / "widget-1.2.3-py3-none-any.whl"
        wheel.write_bytes(b"not really a wheel")
        self.age(wheel, 100 * ezpkg.CULL_GRACE)
        self.assertEqual(venv.cull(), [wheel])
        self.assertFalse(wheel.exists())

    def test_cull_keeps_a_wheel_a_record_names(self) -> None:
        """A live record protects its wheels, however old they are.

        Which is what keeps `EZPKG_APPROVE=write` working from a warm
        cache: an author regenerating approvals needs the wheels that
        answered the request.
        """
        # Named, ancient, and still there afterwards.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "live_wheel")
        wheel: Path = venv.paths()[1] / "widget-1.2.3-py3-none-any.whl"
        wheel.write_bytes(b"not really a wheel")
        tree: Path = venv.paths()[2] / "widget-1.2.3-py3-none-any"
        tree.mkdir()
        venv.remember("widget", [tree.name], [wheel.name])
        self.age(wheel, 100 * ezpkg.CULL_GRACE)
        self.age(tree, 100 * ezpkg.CULL_GRACE)
        self.assertEqual(venv.cull(), [])
        self.assertTrue(wheel.is_file())

    def test_a_young_wheel_is_spared(self) -> None:
        """A wheel that has just arrived belongs to somebody.

        The same grace period as the rest: a wheel is renamed into
        `wheels/` a moment before the record naming it is written, so a
        young wheel may belong to a program still running.
        """
        # No record names it, and it survives anyway, because it is new.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "new_wheel")
        wheel: Path = venv.paths()[1] / "widget-1.2.3-py3-none-any.whl"
        wheel.write_bytes(b"not really a wheel")
        self.assertEqual(venv.litter(), [])

    def test_cull_tolerates_a_path_that_vanishes(self) -> None:
        """Another program sweeping first is not an error."""
        # `litter` names it, then it goes away before `cull` gets there.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "vanishing")
        junk: Path = venv.paths()[0] / "unpacking-racing"
        junk.mkdir()
        self.age(junk, 2 * ezpkg.CULL_GRACE)
        named: list[Path] = venv.litter()
        self.assertEqual(named, [junk])
        shutil.rmtree(junk)
        self.assertEqual(venv.cull(), [])

    def test_a_warm_hit_keeps_a_request_alive(self) -> None:
        """Using a package is what stops it going stale.

        The distinction the whole policy rests on: age here means
        unused, not old.  A package fetched long ago and used this
        morning must not be collectable.
        """
        # Back-date the record past the threshold, then use it again.
        target: Path = self.root / "kept_alive"
        self.assertEqual(self.install(target, "widget"), "widget 1.2.3")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(target)
        record: Path = venv.paths()[3].glob("*.json").__next__()
        self.age(record, 2 * ezpkg.CULL_DAYS)
        self.assertEqual(venv.stale(), [record])

        # A warm install is a hit, and a hit is a use.
        self.assertEqual(self.install(target, "widget"), "widget 1.2.3")
        self.assertEqual(venv.stale(), [])

    def test_an_unused_request_goes_stale(self) -> None:
        """A record nothing has touched for long enough is collectable."""
        # Nothing else is aged: the record is the only thing with a clock.
        target: Path = self.root / "unused"
        self.assertEqual(self.install(target, "widget"), "widget 1.2.3")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(target)
        record: Path = venv.paths()[3].glob("*.json").__next__()
        self.assertEqual(venv.stale(), [])
        self.age(record, 2 * ezpkg.CULL_DAYS)
        self.assertEqual(venv.stale(), [record])

    def test_a_stale_request_takes_its_packages_with_it(self) -> None:
        """One sweep removes the record and then the trees it named.

        The two halves are one mechanism: dropping the record makes the
        trees unreachable, and the litter pass in the same sweep collects
        them.
        """
        # Age the record past the threshold and the tree past the grace
        # period, which is what a genuinely disused package looks like.
        target: Path = self.root / "stale_sweep"
        self.assertEqual(self.install(target, "widget"), "widget 1.2.3")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(target)
        record: Path = venv.paths()[3].glob("*.json").__next__()
        trees: list[Path] = list(venv.paths()[2].iterdir())
        self.assertEqual(len(trees), 1, trees)
        self.age(record, 2 * ezpkg.CULL_DAYS)
        self.age(trees[0], 2 * ezpkg.CULL_GRACE)

        removed: list[Path] = venv.cull()
        self.assertIn(record, removed)
        self.assertIn(trees[0], removed)
        self.assertFalse(trees[0].exists())
        self.assertFalse(record.exists())

        # And the package comes back by itself, which is the point.
        self.assertEqual(self.install(target, "widget"), "widget 1.2.3")

    def test_a_tree_two_requests_name_survives_one_going_stale(self) -> None:
        """A shared package outlives the older of its two requests.

        `widget` here is asked for twice, once on its own and once
        alongside another package, so two records name the same tree.
        The tree goes only when the last of them does.
        """
        # Two requests, one shared tree.
        target: Path = self.root / "shared_tree"
        self.assertEqual(self.install(target, "widget"), "widget 1.2.3")
        self.assertEqual(self.install(target, ["widget", "sprocket"]),
                         "widget 1.2.3\nsprocket 2.0.0")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(target)
        records: list[Path] = sorted(venv.paths()[3].glob("*.json"))
        self.assertEqual(len(records), 2, records)
        widget: Path = next(
            tree for tree in venv.paths()[2].iterdir()
            if tree.name.startswith("widget"))

        # Age one record only, and sweep.
        self.age(records[0], 2 * ezpkg.CULL_DAYS)
        self.age(widget, 2 * ezpkg.CULL_GRACE)
        venv.cull()
        self.assertTrue(widget.is_dir())

    def test_the_threshold_is_a_parameter(self) -> None:
        """Both halves take their thresholds as arguments.

        Which is what makes this testable without inventing a clock: a
        test asks for every record to count as stale, or for none to.
        """
        # Nothing has aged at all here; the numbers do the work.
        target: Path = self.root / "thresholds"
        self.assertEqual(self.install(target, "widget"), "widget 1.2.3")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(target)
        self.assertEqual(venv.stale(days=10.0 ** 9), [])
        self.assertEqual(len(venv.stale(days=0.0)), 1)

    def test_litter_ignores_a_record_it_cannot_read(self) -> None:
        """Junk among the records is passed over, not fatal.

        A record half written by a killed program, or a file somebody
        dropped in by hand, must not stop the sweep: the whole point of
        a sweep is that it tidies up after accidents.
        """
        # Three kinds of junk, and a real record that still protects.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "junk")
        requests: Path = venv.paths()[3]
        (requests / "truncated.json").write_text('{"request": "wid')
        (requests / "not_an_object.json").write_text("[1, 2, 3]")
        (requests / "no_trees.json").write_text('{"request": "x"}')
        kept: Path = venv.paths()[2] / "widget-1.2.3-py3-none-any"
        kept.mkdir()
        venv.remember("widget", [kept.name], ["widget-1.2.3.whl"])
        self.age(kept, 2 * ezpkg.CULL_GRACE)
        self.assertEqual(venv.litter(), [])

    def test_litter_steps_over_something_it_cannot_stat(self) -> None:
        """A dangling symlink is skipped rather than crashing the sweep.

        `stat` follows the link and raises, which is also what happens
        when another program removes an entry between the listing and
        the look.  A broken link makes that deterministic.
        """
        # Pointing at nothing, in the two directories that get swept.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "dangling")
        pending: Path = venv.paths()[0]
        (pending / "gone").symlink_to(pending / "never-existed")
        (venv.paths()[2] / "also-gone").symlink_to(pending / "nor-this")
        self.assertEqual(venv.litter(), [])
        self.assertEqual(venv.cull(), [])

    def test_stale_steps_over_something_it_cannot_stat(self) -> None:
        """The same, for the records `stale` looks at."""
        # A dangling link that happens to be named like a record.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "dangling_json")
        requests: Path = venv.paths()[3]
        (requests / "gone.json").symlink_to(requests / "never-existed")
        self.assertEqual(venv.stale(), [])

    def test_cull_survives_a_record_it_cannot_remove(self) -> None:
        """Something unremovable is left behind rather than fatal.

        A directory named like a record is the deterministic version of
        a permission problem: `unlink` refuses it, and the sweep has to
        carry on and collect everything else.
        """
        # One immovable object, one ordinary piece of litter.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "immovable")
        awkward: Path = venv.paths()[3] / "adirectory.json"
        awkward.mkdir()
        self.age(awkward, 2 * ezpkg.CULL_DAYS)
        junk: Path = venv.paths()[0] / "unpacking-dead"
        junk.mkdir()
        self.age(junk, 2 * ezpkg.CULL_GRACE)

        self.assertEqual(venv.stale(), [awkward])
        self.assertEqual(venv.cull(), [junk])
        self.assertTrue(awkward.is_dir())

    def test_cull_survives_litter_it_cannot_remove(self) -> None:
        """A directory it may not write to is left, and the sweep goes on."""
        # Read only staging: the entry is named but cannot be removed.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "protected")
        pending: Path = venv.paths()[0]
        stuck: Path = pending / "unpacking-stuck"
        stuck.mkdir()
        self.age(stuck, 2 * ezpkg.CULL_GRACE)
        pending.chmod(0o500)
        self.addCleanup(pending.chmod, 0o700)
        self.assertEqual(venv.litter(), [stuck])
        self.assertEqual(venv.cull(), [])
        self.assertTrue(stuck.is_dir())

    def test_a_record_that_cannot_be_touched_is_still_used(self) -> None:
        """Failing to record a use is not a reason to refetch.

        Touching the record is how a warm hit keeps a package alive.  If
        that fails -- a read only filesystem, most plausibly -- the hit
        is still a hit: the cache is there and using it is right.
        """
        # `Path.touch` is patched because no ordinary arrangement makes
        # `utime` fail for the owner of a file.
        target: Path = self.root / "untouchable"
        self.assertEqual(self.install(target, "widget"), "widget 1.2.3")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(target)
        with unittest.mock.patch.object(
                ezpkg.Path, "touch",
                side_effect=OSError("read only file system")):
            remembered = venv.remember("widget")
        assert remembered is not None
        self.assertEqual(len(remembered[0]), 1, remembered)

    def test_a_terminal_lost_during_the_confirmation_declines(self) -> None:
        """The terminal going away mid-question is not an answer.

        `a` is answered, the confirmation is asked, and then the
        terminal reads empty.  Nothing is installed and no marker is
        written, because silence must never mean yes.
        """
        # `a` and then end of file, on a terminal that survives reading.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "hangup_twice")
        spoken: _KeptStringIO = _KeptStringIO()
        with unittest.mock.patch.object(
                ezpkg.EZPkg, "terminal",
                return_value=(spoken, _KeptStringIO("a\n"))):
            self.assertFalse(venv.consent([], ["widget"]))
        self.assertIn(CONFIRM, spoken.getvalue())
        self.assertFalse(venv.forever().exists())

    def test_due_is_true_until_a_sweep_happens(self) -> None:
        """The daily gate opens once, then closes until tomorrow."""
        # A cache that has never been swept is due by definition.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "gate")
        self.assertTrue(venv.due())
        venv.cull()
        self.assertFalse(venv.due())
        self.age(venv.root / "last_cull", 2 * ezpkg.CULL_INTERVAL)
        self.assertTrue(venv.due())

    def test_installing_sweeps_at_most_once_a_day(self) -> None:
        """An install sweeps the cache, and the next one does not."""
        # The stamp is the observable part, so watch it rather than the
        # litter: a second install must leave it untouched.
        target: Path = self.root / "install_sweep"
        self.assertEqual(self.install(target, "widget"), "widget 1.2.3")
        stamp: Path = target / "last_cull"
        self.assertTrue(stamp.is_file())
        self.age(stamp, 60.0)
        before: int = stamp.stat().st_mtime_ns
        self.assertEqual(self.install(target, "sprocket"),
                         "sprocket 2.0.0")
        self.assertEqual(stamp.stat().st_mtime_ns, before)

    def test_contains_reports_what_is_cached(self) -> None:
        """`contains` is False before an install and True after."""
        # A single module counts, not only a package directory.
        target: Path = self.root / "contains"
        venv: ezpkg.EZPkg = ezpkg.EZPkg(target)
        self.assertFalse(venv.contains("widget"))
        self.install(target, "widget")
        self.assertTrue(venv.contains("widget"))


    def declaring_program(self, name: str, block: str | None,
                          tail: str) -> Path:
        """Write a program that declares its packages in a PEP 723 block.

        The shape `README.md` will teach: a block at the top, the
        bootstrap's work done by `install()` with no arguments, and the
        program's own imports below it.

        Arguments:
        * `name` (`str`):
          A directory name, to keep one test's program from another's.
        * `block` (`str | None`):
          The TOML to put inside the block, already split into lines by
          newlines, or `None` for a program with no block at all.
        * `tail` (`str`):
          Statements to run after `install()`, such as the imports.

        Returns:
        * (`Path`): The program written.
        """
        # A block is comment lines, which is what makes it PEP 723.
        where: Path = self.root / name
        where.mkdir(parents=True, exist_ok=True)
        lines: list[str] = ["#!/usr/bin/env python3"]
        if block is not None:
            lines.append("# /// script")
            lines.extend(f"# {line}" if line else "#"
                         for line in block.splitlines())
            lines.append("# ///")

        # Then the bootstrap's part, played by an import from the tree.
        here: str = str(Path(__file__).resolve().parent)
        lines.extend([
            "import sys",
            f"sys.path.insert(0, {here!r})",
            "import ezpkg",
            "from pathlib import Path",
            f"v = ezpkg.EZPkg(Path({str(where / 'cache')!r}))",
            "v.install()",
            tail,
        ])
        program: Path = where / "prog.py"
        program.write_text("\n".join(lines) + "\n")
        return program

    def test_a_declared_package_is_installed(self) -> None:
        """`install()` with no arguments fetches what the block declares."""
        # The import is the program's own, below the bootstrap, and it
        # works because the cache is on `sys.path` by then.
        program: Path = self.declaring_program(
            "declared", 'dependencies = ["widget"]',
            "import widget\nprint(widget.__version__)")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "1.2.3")

    def test_a_marker_that_excludes_everything_is_silent(self) -> None:
        """A requirement for another platform installs nothing, quietly.

        `"widget; sys_platform == \'win32\'"` is a real thing to write and
        it is right that nothing happens here.  Before 2026-09-30 it
        printed `1 requested, 0 downloaded` and would have asked a person
        on a terminal whether to install no packages at all.
        """
        # Nothing said, nothing installed, and the program still runs.
        program: Path = self.declaring_program(
            "excluded",
            'dependencies = ["widget; sys_platform == \'win32\'"]',
            "print('ran')")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "ran")
        self.assertEqual(done.stderr.strip(), "")

        # The directory itself is made by `paths`, so emptiness is the
        # thing to check rather than absence.
        versions: Path = program.parent / "cache" / "versions"
        self.assertEqual(list(versions.iterdir()), [])

    def test_a_marker_that_applies_here_installs(self) -> None:
        """The same requirement, with a marker that is true, installs."""
        # The other half, so that the silence above means what it says.
        program: Path = self.declaring_program(
            "included",
            'dependencies = ["widget; python_version >= \'3.11\'"]',
            "import widget\nprint(widget.__version__)")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "1.2.3")

    def test_the_declared_forms_pip_understands(self) -> None:
        """Ranges, compatible releases, exclusions and extras all pass.

        None of this is our work: the string goes to `pip` untouched and
        `pip` resolves it, which is the whole reason `pip` is required.
        This records that nothing on our side mangles the forms.
        """
        # `sprocket` is published twice, so a constraint has to choose.
        form: str
        wanted: str
        for form, wanted in (("sprocket>=1.0,<2", "1.0.0"),
                             ("sprocket~=1.0.0", "1.0.0"),
                             ("sprocket!=2.0.0", "1.0.0"),
                             ("sprocket===1.0.0", "1.0.0"),
                             ("sprocket>1.0.0", "2.0.0")):
            with self.subTest(form=form):
                target: Path = self.root / f"form-{abs(hash(form))}"
                self.assertEqual(self.install(target, form),
                                 f"sprocket {wanted}")

    def test_a_declared_constraint_is_honoured(self) -> None:
        """A PEP 508 constraint in the block reaches `pip` unaltered."""
        # Two versions are published, so the choice is a real one.
        program: Path = self.declaring_program(
            "constrained", 'dependencies = ["sprocket==1.0.0"]',
            "import sprocket\nprint(sprocket.__version__)")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "1.0.0")

    def bootstrapped_program(self, name: str, block: str, tail: str
                             ) -> tuple[Path, Path]:
        """Write a program carrying the real pasted bootstrap, and a HOME.

        `declaring_program` stands in for the bootstrap with an import
        from this tree; a `zipapp` needs the real thing, because the
        build takes it out.  `ezpkg` cannot be fetched from the local
        index the way the bootstrap fetches it from PyPI, so the HOME
        already holds it where the bootstrap looks, as a package.

        Arguments:
        * `name` (`str`):
          A directory name, to keep one test's program from another's.
        * `block` (`str`):
          The TOML inside the PEP 723 block, one line.
        * `tail` (`str`):
          Statements after the bootstrap, such as the imports.

        Returns:
        * (`tuple[Path, Path]`): The program written, and its HOME.
        """
        # Part 1, Part 2's three shared imports, Part 3, then the rest.
        where: Path = self.root / name
        home: Path = where / "home"
        installed: Path = home / ".ezpkg" / MODULE
        installed.mkdir(parents=True)
        shutil.copyfile(Path(__file__).resolve().parent / f"{MODULE}.py",
                        installed / "__init__.py")
        program: Path = where / "prog.py"
        program.write_text(
            f"# /// script\n# {block}\n# ///\n"
            "import importlib\nimport pathlib\nimport sys\n"
            + bootstrap.pasted(SHIPPING) + tail + "\n")
        return program, home

    def test_export_zipapp_after_approving_in_another_run(self) -> None:
        """An export finds what an ordinary, locked run fetched.

        `provide` files the record under the lock and `export` must look
        it up the same way, or a release made in a run of its own, after
        the approvals were written in an earlier one, finds nothing to
        bundle.  See `request_for`.
        """
        # Approve in one run, export in another.
        program: Path
        home: Path
        program, home = self.bootstrapped_program(
            "zipped_later", 'dependencies = ["needy"]',
            "import needy\nprint(needy.__file__)")
        approved: subprocess.CompletedProcess[str] = self.run_program(
            program, HOME=str(home), EZPKG_APPROVE="write")
        self.assertEqual(approved.returncode, 0, approved.stderr[-400:])

        # Forget what `write` filed, as a fresh clone's cache would not
        # have it, so only the locked run's record can answer.
        records: list[Path] = list(home.glob("**/requests/*.json"))
        self.assertTrue(records)
        for record in records:
            record.unlink()
        built: subprocess.CompletedProcess[str] = self.run_program(
            program, HOME=str(home), EZPKG_EXPORT="zipapp")
        self.assertEqual(built.returncode, 0, built.stderr[-400:])
        self.assertTrue(program.with_suffix(".pyz").is_file())

    def test_export_zipapp_runs_without_a_network(self) -> None:
        """`EZPKG_EXPORT=zipapp` writes a `.pyz` that needs nothing.

        Built in one run with the approvals, from a program carrying the
        real bootstrap.  The archive holds neither `ezpkg` nor the
        bootstrap, and is run with an empty HOME and an index nothing
        listens on: every package, `widget` that came along included,
        has to import from inside it, and nothing may be written.
        """
        # Building is not running: the program's own line stays silent.
        program: Path
        home: Path
        program, home = self.bootstrapped_program(
            "zipped", 'requires-python = ">=3.11"\n# dependencies = ["needy"]',
            "import needy\nimport widget\n"
            "print(needy.__file__)\nprint(widget.__file__)")
        built: subprocess.CompletedProcess[str] = self.run_program(
            program, HOME=str(home), EZPKG_APPROVE="write",
            EZPKG_EXPORT="zipapp")
        self.assertEqual(built.returncode, 0, built.stderr[-400:])
        archive: Path = program.with_suffix(".pyz")
        self.assertEqual(built.stdout.strip(), f"ezpkg: wrote {archive}")
        with zipfile.ZipFile(archive) as opened:
            self.assertFalse([name for name in opened.namelist()
                              if name.startswith(MODULE)])
            main: str = opened.read("__main__.py").decode()
        self.assertIsNone(ezpkg.find_bootstrap(main))

        # The bootstrap's place checks the Python version instead, and
        # an older Python is told which it needs.
        guard: str = next(line for line in main.splitlines()
                          if "version_info < (3, 11)" in line)
        with (unittest.mock.patch.object(sys, "version_info", (3, 10, 0)),
              self.assertRaises(SystemExit) as refused):
            exec(guard, {})  # noqa: S102  # The archive's own line.
        self.assertIn("prog.pyz needs Python 3.11 or newer, not 3.",
                      str(refused.exception))
        exec(guard, {})  # noqa: S102  # This Python passes.

        # Run it with an empty HOME and nowhere to fetch from.
        empty: Path = self.root / "zipped" / "empty"
        empty.mkdir()
        environment: dict[str, str] = dict(
            os.environ, HOME=str(empty), PIP_INDEX_URL="http://127.0.0.1:1/")
        environment.pop("VIRTUAL_ENV", None)
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, str(archive)], env=environment,
            capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        lines: list[str] = done.stdout.splitlines()
        self.assertEqual(len(lines), 2, done.stdout)
        self.assertTrue(all(line.startswith(str(archive) + os.sep)
                            for line in lines), done.stdout)
        self.assertEqual(list(empty.iterdir()), [])

    def test_strip_bootstrap_keeps_a_nested_block_valid(self) -> None:
        """A bootstrap inside a function becomes an indented `pass`."""
        # The pasted text, indented one level under a `def`.
        pasted: str = textwrap.indent(bootstrap.pasted(SHIPPING), "    ")
        text: str = "def start():\n" + pasted + "    print('after')\n"
        stripped: str | None = ezpkg.strip_bootstrap(text)
        assert stripped is not None
        compile(stripped, "<stripped>", "exec")
        self.assertIsNone(ezpkg.find_bootstrap(stripped))
        self.assertIn("    pass  # The bootstrap", stripped)
        self.assertIn("    print('after')", stripped)
        self.assertIsNone(ezpkg.strip_bootstrap("print('no bootstrap')\n"))

    def test_zipapp_refuses_what_a_zip_cannot_carry(self) -> None:
        """Compiled, unapproved or `.pth` packages are refused, not bundled.

        Each would be a `.pyz` that fails, or half works, only on the
        machine it was sent to.
        """
        # A program file and a cache holding one tree, set up by hand.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "refuse")
        program: Path = self.root / "refuse" / "prog.py"
        program.write_text(bootstrap.pasted(SHIPPING))
        tree: Path = venv.paths()[2] / "hooked-1.0-py3"
        tree.mkdir(parents=True)
        pure: str = "hooked-1.0-py3-none-any.whl"
        native: str = "fast-1.0-cp312-cp312-linux_x86_64.whl"
        cases: list[tuple[list[str], dict[str, str], bool, str]] = [
            ([native], {native: "0" * 64}, False, "compiled"),
            ([pure], {}, False, "no approvals"),
            ([pure], {"other-1.0-py3-none-any.whl": "0" * 64}, False,
             "not approved"),
            ([pure], {pure: "0" * 64}, True, ".pth file"),
        ]
        wheels: list[str]
        approved: dict[str, str]
        hooked: bool
        expected: str
        for wheels, approved, hooked, expected in cases:
            with self.subTest(expected=expected):
                if hooked:
                    (tree / "hooked.pth").write_text("import os\n")
                with (unittest.mock.patch.object(ezpkg, "main_path",
                                                 return_value=program),
                      unittest.mock.patch.object(venv, "approved",
                                                 return_value=approved),
                      unittest.mock.patch.object(
                          venv, "remember",
                          return_value=([tree.name], wheels)),
                      self.assertRaises(RuntimeError) as caught):
                    venv.build_zipapp(["hooked"])
                self.assertIn(expected, str(caught.exception))
                self.assertFalse(program.with_suffix(".pyz").exists())

        # A program with no bootstrap uses `ezpkg` some other way, and
        # would fail in an archive that leaves it out.
        program.write_text("print('ran')\n")
        with (unittest.mock.patch.object(ezpkg, "main_path",
                                         return_value=program),
              self.assertRaises(RuntimeError) as caught):
            venv.build_zipapp(["hooked"])
        self.assertIn("has none", str(caught.exception))

    @unittest.skipIf(ezpkg.find_uv() is None, "uv is not installed")
    def test_export_uv_writes_a_script_and_its_locks(self) -> None:
        """`EZPKG_EXPORT=uv` writes the two files that `uv run` uses.

        Built in one run with the approvals, from a program carrying the
        real bootstrap.  The script is pinned, has no bootstrap and says
        `no-build`; the lock names `widget`, which came along, and no
        PEP 751 `pylock.toml` is written beside it.  Run with
        `uv run` and an empty HOME, every package comes from `uv`, and
        nothing of `ezpkg` is made.
        """
        # Building is not running: the program's own line stays silent.
        program: Path
        home: Path
        program, home = self.bootstrapped_program(
            "locked", 'dependencies = ["needy"]',
            "import needy\nimport widget\n"
            "print(needy.__file__)\nprint(widget.__file__)")
        built: subprocess.CompletedProcess[str] = self.run_program(
            program, HOME=str(home), EZPKG_APPROVE="write",
            EZPKG_EXPORT="uv")
        self.assertEqual(built.returncode, 0, built.stderr[-400:])
        script: Path = program.with_name("prog-uv.py")
        lock: Path = program.with_name("prog-uv.py.lock")
        self.assertEqual(built.stdout.splitlines(),
                         [f"ezpkg: wrote {path}"
                          for path in (script, lock)])
        self.assertFalse(program.with_name("pylock.prog-uv.toml").exists())
        text: str = script.read_text()
        self.assertIsNone(ezpkg.find_bootstrap(text))
        metadata: dict[str, Any] | None = ezpkg.script_metadata(text)
        assert metadata is not None
        self.assertEqual([pin.split("==")[0]
                          for pin in metadata["dependencies"]],
                         ["needy", "widget"])
        self.assertIs(metadata["tool"]["uv"]["no-build"], True)
        self.assertIn('name = "widget"', lock.read_text())

        # Run it the way a `uv` user would, from an empty HOME.
        empty: Path = self.root / "locked" / "empty"
        empty.mkdir()
        uv: str | None = ezpkg.find_uv()
        assert uv is not None
        environment: dict[str, str] = dict(
            os.environ, HOME=str(empty), UV_DEFAULT_INDEX=self.index_url)
        environment.pop("VIRTUAL_ENV", None)
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [uv, "run", "--python", sys.executable, str(script)],
            env=environment, capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        lines: list[str] = done.stdout.splitlines()
        self.assertEqual(len(lines), 2, done.stdout)
        self.assertFalse([line for line in lines if ".ezpkg" in line])
        self.assertFalse((empty / ".ezpkg").exists())

    def test_export_needs_approvals(self) -> None:
        """Without an approvals file there is nothing to bundle from."""
        # `skip` leaves no file behind, so the export has to refuse.
        program: Path
        home: Path
        program, home = self.bootstrapped_program(
            "unpinned", 'dependencies = ["widget"]', "print('ran')")
        done: subprocess.CompletedProcess[str] = self.run_program(
            program, HOME=str(home), EZPKG_APPROVE="skip",
            EZPKG_EXPORT="zipapp")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("EZPKG_APPROVE=write", done.stderr)
        self.assertNotIn("ran", done.stdout)

    def test_export_refuses_an_undeclared_import(self) -> None:
        """An import that works only on the author's machine fails export.

        `lurker` is installed, as a Linux distribution might install it,
        but Part 1 does not name it; `gadgetlib` is not installed at
        all.  Both are listed with their lines, then the export fails.
        `widget` is declared and `helper.py` sits beside the program, so
        neither is mentioned.  See `T.cibe`.
        """
        # A distribution on `PYTHONPATH`, with the metadata that maps
        # its module to its name, and a module beside the program.
        program: Path = self.declaring_program(
            "undeclared", 'dependencies = ["widget"]',
            "import widget\nimport helper\nimport lurker\n"
            "import gadgetlib\nprint('ran')")
        program.with_name("helper.py").write_text("")
        system: Path = self.root / "undeclared" / "system"
        (system / "lurker").mkdir(parents=True)
        (system / "lurker" / "__init__.py").write_text("")
        info: Path = system / "lurker-1.0.dist-info"
        info.mkdir()
        (info / "METADATA").write_text(
            "Metadata-Version: 2.1\nName: lurker\nVersion: 1.0\n")
        (info / "top_level.txt").write_text("lurker\n")

        # Nothing written, nothing run, and both problems named.
        done: subprocess.CompletedProcess[str] = self.run_program(
            program, PYTHONPATH=str(system), EZPKG_APPROVE="write",
            EZPKG_EXPORT="zipapp")
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "")

        # Lines as the file now stands, since `write` dated Part 1 first.
        lines: list[str] = program.read_text().splitlines()
        lurker: int = lines.index("import lurker") + 1
        self.assertIn(f"line {lurker}: `lurker` comes from lurker, which "
                      "Part 1 does not declare", done.stderr)
        self.assertIn(f"line {lurker + 1}: `gadgetlib` is not importable",
                      done.stderr)
        self.assertIn("2 import(s) in prog.py", done.stderr)
        self.assertNotIn("`helper`", done.stderr)
        self.assertNotIn("`widget`", done.stderr)

    def test_program_imports_leaves_out_what_may_fail(self) -> None:
        """Guarded, type-only and relative imports are not demanded."""
        # One of each kind, and the ones that do count.
        text: str = textwrap.dedent("""\
            import os, sys
            import requests.adapters
            from yaml import safe_load
            from . import sibling
            try:
                import ujson
            except (ValueError, ImportError):
                ujson = None
            try:
                import strict
            except KeyError:
                pass
            if sys.platform == "win32":
                import win32api
            if TYPE_CHECKING:
                import _typeshed
            def later():
                import numpy as np
            import yaml
            """)
        self.assertEqual(ezpkg.program_imports(text), [
            ("os", 1, False), ("sys", 1, False), ("requests", 2, False),
            ("yaml", 3, False), ("strict", 10, False),
            ("win32api", 14, True), ("numpy", 18, False)])

    def test_an_ordinary_run_warns_once_per_change(self) -> None:
        """Uncovered imports are listed together, once per change.

        `lurker` is on this Python but not in Part 1, the case that
        otherwise surfaces only at export.  The program still runs, and
        the warning is not repeated until the imports change; moving
        code does not count.  See `T.siofr`.
        """
        # A distribution only this machine has, as in the export test.
        program: Path = self.declaring_program(
            "scanned", 'dependencies = ["widget"]',
            "import widget\nimport lurker\nprint('ran')")
        system: Path = self.root / "scanned" / "system"
        (system / "lurker").mkdir(parents=True)
        (system / "lurker" / "__init__.py").write_text("")
        info: Path = system / "lurker-1.0.dist-info"
        info.mkdir()
        (info / "METADATA").write_text(
            "Metadata-Version: 2.1\nName: lurker\nVersion: 1.0\n")
        (info / "top_level.txt").write_text("lurker\n")
        warning: str = "`lurker` comes from lurker, which Part 1 does not"

        # Warned and run; then quiet, even after the code moves.
        done: subprocess.CompletedProcess[str] = self.run_program(
            program, PYTHONPATH=str(system))
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout, "ran\n")
        self.assertIn(warning, done.stderr)
        self.assertIn("shown once", done.stderr)
        program.write_text(program.read_text().replace(
            "import lurker\n", "\nimport lurker  # Moved.\n"))
        done = self.run_program(program, PYTHONPATH=str(system))
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertNotIn(warning, done.stderr)

        # A new import is a change, so the warning comes back.
        program.write_text(program.read_text().replace(
            "import widget\n", "import widget\nimport json\n"))
        done = self.run_program(program, PYTHONPATH=str(system))
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertIn(warning, done.stderr)

        # One record, touched on use, which `stale` can age out.
        records: list[Path] = sorted(
            (self.root / "scanned" / "cache" / "scans").glob("*.json"))
        self.assertEqual(len(records), 2)
        venv: ezpkg.EZPkg = ezpkg.EZPkg(
            self.root / "scanned" / "cache")
        self.assertEqual([one for one in venv.stale(-60)
                          if one.parent.name == "scans"], records)

    def synced_program(self, name: str, declared: str, tail: str,
                       comment: str = "") -> Path:
        """Write a program, run it once clean, then change its imports.

        The first run has nothing to raise, so it only records the
        program; the edit is the change that makes `sync_dependencies`
        speak.  Downloads go ahead without the consent question, which
        other tests cover, so that the terminal sees only this one.

        Arguments:
        * `name` (`str`):
          A directory name, as `declaring_program` takes.
        * `declared` (`str`):
          The `dependencies` line, such as `["widget"]`.
        * `tail` (`str`):
          What to put below `import widget` after the first run.
        * `comment` (`str`):
          A comment for the `widget` import, such as a `mypy` one.

        Returns:
        * (`Path`): The program, edited but not run again.
        """
        # Declares and imports `widget`, so the first run is clean.
        program: Path = self.declaring_program(
            name, 'dependencies = ["widget"]',
            f"import widget{comment}\nprint('ran')")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertNotIn("disagree", done.stderr)
        (program.parent / "cache" / "FOREVER_APPROVE").write_text("x\n")
        program.write_text(program.read_text().replace(
            'dependencies = ["widget"]', f"dependencies = {declared}").replace(
            f"import widget{comment}\n",
            f"import widget{comment}\n{tail}\n"))
        return program

    def declared_now(self, program: Path) -> list[str]:
        """Return a program's `dependencies` as its file says now.

        Arguments:
        * `program` (`Path`):
          The program.

        Returns:
        * (`list[str]`): The entries.
        """
        # Read back the way `install` reads it.
        metadata: dict[str, Any] | None = ezpkg.script_metadata(
            program.read_text())
        assert metadata is not None
        found: list[str] = metadata["dependencies"]
        return found

    def test_a_missing_dependency_is_listed_and_added(self) -> None:
        """A new import is named, asked about, shown, approved and added.

        The package is fetched before the program's own import runs, so
        the run that asked succeeds.  See `T.kdaiis`.
        """
        # Once, yes to the addition, yes to the changes.
        program: Path = self.synced_program(
            "added", '["widget"]', "import sprocket")
        seen: str = self.answer_on_a_terminal(program, b"o\ny\ny\n")
        flat: str = " ".join(seen.split())
        self.assertIn("EZPkg: prog.py: its `dependencies` and its imports "
                      "(line 12) disagree.", flat)
        self.assertIn("See the discrepancy list? "
                      "[o=>Once/a=>Always/n=>No/d=>Don't ask again]", flat)
        self.assertIn("line 12: `sprocket` is imported, but not in "
                      'dependencies. Add "sprocket"?', flat)
        self.assertIn('line 3 "widget", add "sprocket", ]', flat)
        self.assertIn('added "sprocket" to dependencies', seen)
        self.assertNotIn("mypy comment", seen)
        self.assertIn("ran", seen)
        self.assertEqual(self.declared_now(program), ["widget", "sprocket"])

        # Settled, so the next run says nothing at all.
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual((done.stdout, done.stderr), ("ran\n", ""))

    def test_the_authors_mypy_comment_is_copied(self) -> None:
        """A new import gets the `type: ignore` the others carry."""
        # The Quick Start's own comment, word for word.
        comment: str = "  # type: ignore[import-not-found]  # For mypy."
        program: Path = self.synced_program(
            "commented", '["widget"]', "import sprocket", comment)
        seen: str = self.answer_on_a_terminal(program, b"o\ny\ny\n")
        self.assertIn("and the mypy comment on its import of sprocket", seen)
        self.assertIn('added "sprocket" to dependencies, and its mypy '
                      "comment", seen)
        self.assertIn(f"\nimport sprocket{comment}\n", program.read_text())

    def test_an_unused_dependency_is_removed_or_kept(self) -> None:
        """Nothing importing a package offers to remove it, or keep it.

        `k` records it in `[tool.ezpkg] unimported`, after which it is
        not raised again.
        """
        # Removed.
        program: Path = self.synced_program(
            "removed", '["widget", "sprocket"]', "")
        seen: str = self.answer_on_a_terminal(program, b"o\ny\ny\n")
        flat: str = " ".join(seen.split())
        self.assertIn('line 3: "sprocket" is in dependencies, but nothing '
                      "imports it. Remove it? [y=>Yes/n=>No/k=>Keep it, and "
                      "stop asking]", flat)
        self.assertIn('remove "sprocket",', flat)
        self.assertIn('removed "sprocket" from dependencies', seen)
        self.assertEqual(self.declared_now(program), ["widget"])

        # Kept, and then left alone.
        program = self.synced_program("kept", '["widget", "sprocket"]', "")
        seen = self.answer_on_a_terminal(program, b"o\nk\ny\n")
        self.assertIn('kept "sprocket" as unimported', seen)
        self.assertEqual(self.declared_now(program), ["widget", "sprocket"])
        self.assertEqual(ezpkg.unimported(program.read_text()), ["sprocket"])
        seen = self.answer_on_a_terminal(program, b"o\n")
        self.assertNotIn("disagree", seen)

    def test_dependencies_follow_the_order_of_the_imports(self) -> None:
        """Out of order is a discrepancy; approving puts it in order."""
        # Nothing to add or remove, so straight to the changes.
        program: Path = self.synced_program(
            "ordered", '["sprocket", "widget"]', "import sprocket")
        seen: str = self.answer_on_a_terminal(program, b"o\ny\n")
        flat: str = " ".join(seen.split())
        self.assertIn("its `dependencies` (line 3) and its imports (line "
                      "11) disagree.", flat)
        self.assertIn('[ move "widget", "sprocket", ]', flat)
        self.assertIn("put dependencies in the order of their imports", seen)
        self.assertEqual(self.declared_now(program), ["widget", "sprocket"])

    def test_an_optional_import_counts_as_used(self) -> None:
        """A declared package imported only under `try` is not unused."""
        # Silent, since the two agree.
        program: Path = self.synced_program(
            "optional", '["widget", "sprocket"]',
            "try:\n    import sprocket\nexcept ImportError:\n    pass")
        seen: str = self.answer_on_a_terminal(program, b"o\n")
        self.assertNotIn("disagree", seen)
        self.assertIn("ran", seen)

    def test_without_a_terminal_it_is_named_once(self) -> None:
        """No terminal, or `n`: named once per change, nothing edited."""
        # Named, then not again for the same imports.
        program: Path = self.synced_program(
            "quiet", '["widget"]', "import sprocket")
        before: str = program.read_text()
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertIn("disagree", done.stderr)
        self.assertEqual(program.read_text(), before)
        done = self.run_program(program)
        self.assertNotIn("disagree", done.stderr)

        # A terminal is still asked, since nobody has answered yet; `n`.
        seen: str = self.answer_on_a_terminal(program, b"n\n")
        self.assertIn("See the discrepancy list?", seen)
        self.assertEqual(program.read_text(), before)
        seen = self.answer_on_a_terminal(program, b"o\n")
        self.assertNotIn("See the discrepancy list?", seen)

    def test_always_and_never_outlive_the_run(self) -> None:
        """`a` skips the question from then on; `d` stops all asking."""
        # Always, confirmed: the list comes straight away next time.
        program: Path = self.synced_program(
            "always", '["widget"]', "import sprocket")
        seen: str = self.answer_on_a_terminal(program, b"a\ny\ny\ny\n")
        self.assertIn("Really show the list from now on", seen)
        self.assertIn("To be asked again, delete", seen)
        program.write_text(program.read_text().replace(
            "import sprocket\n", "import sprocket\nimport needy\n"))
        seen = self.answer_on_a_terminal(program, b"y\ny\n")
        self.assertNotIn("See the discrepancy list?", seen)
        self.assertIn('added "needy" to dependencies', seen)

        # Don't ask again, confirmed: named, never asked.
        program = self.synced_program("never", '["widget"]', "import sprocket")
        before: str = program.read_text()
        seen = self.answer_on_a_terminal(program, b"d\ny\n")
        self.assertIn("Really never ask about prog.py again?", seen)
        program.write_text(program.read_text().replace(
            "import sprocket\n", "import sprocket\nimport needy\n"))
        before = program.read_text()
        seen = self.answer_on_a_terminal(program, b"o\n")
        self.assertNotIn("See the discrepancy list?", seen)
        self.assertIn("disagree", seen)
        self.assertEqual(program.read_text(), before)

    def test_a_wrong_guess_changes_nothing(self) -> None:
        """A package that is not what its name says is refused.

        `decoy` exists but holds `elsewhere`, as a squatted name might,
        so nothing is unpacked and the program is not edited.
        """
        # Approved, fetched, refused.
        program: Path = self.synced_program(
            "decoyed", '["widget"]', "import decoy")
        before: str = program.read_text()
        seen: str = self.answer_on_a_terminal(program, b"o\ny\ny\n")
        self.assertIn("nothing changed", seen)
        self.assertIn("does not provide `decoy`", seen)
        self.assertEqual(program.read_text(), before)
        self.assertFalse(list((program.parent / "cache" / "versions")
                              .glob("decoy-*")))

    def test_imports_above_the_bootstrap_are_found(self) -> None:
        """Only `__future__` and the paste's own imports may precede it.

        The bootstrap's own are recognised by the names it uses, so the
        Part 2 of any bootstrap passes.  See `T.fipab`.
        """
        # Part 2 and a `__future__` pass; the rest are named by line.
        text: str = ("from __future__ import annotations\n"
                     "import os\n"
                     "def early():\n"
                     "    import numpy\n"
                     "if True:\n"
                     "    from cowsay import cow\n"
                     + bootstrap.pasted(SHIPPING)
                     + "import yaml\n")
        self.assertEqual(ezpkg.imports_above_bootstrap(text),
                         [("os", 2), ("cowsay", 6)])
        self.assertEqual(ezpkg.imports_above_bootstrap(
            bootstrap.pasted(SHIPPING)), [])
        self.assertEqual(ezpkg.imports_above_bootstrap("import os\n"), [])

    def test_export_refuses_an_import_above_the_bootstrap(self) -> None:
        """An export refuses a program whose imports precede the paste.

        Even a standard library one, which would work, breaks the rule
        that keeps the rest safe.  See `T.fipab`.
        """
        # `os` above the bootstrap, with its line as written.
        program: Path
        home: Path
        program, home = self.bootstrapped_program(
            "early", 'dependencies = ["widget"]', "print('ran')")
        program.write_text(program.read_text().replace(
            "import importlib\n", "import os\nimport importlib\n", 1))

        # Nothing written, and the import named.
        done: subprocess.CompletedProcess[str] = self.run_program(
            program, HOME=str(home), EZPKG_APPROVE="write",
            EZPKG_EXPORT="zipapp")
        self.assertNotEqual(done.returncode, 0)
        line: int = program.read_text().splitlines().index("import os") + 1
        self.assertIn(f"line {line}: `os` is imported above the "
                      "bootstrap", done.stderr)
        self.assertIn("1 import(s) in prog.py", done.stderr)
        self.assertFalse(program.with_suffix(".pyz").exists())

    def test_export_refuses_an_unknown_form(self) -> None:
        """A misspelt form is refused rather than silently ignored."""
        # In process: the refusal comes before anything is read.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "form")
        with self.assertRaises(ValueError) as caught:
            venv.export("zipap")
        self.assertIn("use zipapp or uv", str(caught.exception))

        # `pins` is gone; the date in Part 1 does its job.
        with self.assertRaises(ValueError):
            venv.export("pins")

    def test_pins_refuse_two_versions_of_one_package(self) -> None:
        """No single `==` can say two versions, so none is guessed."""
        # Approvals as a hand-edited file might have them.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "two")
        approved: dict[str, str] = {
            "sprocket-1.0.0-py3-none-any.whl": "0" * 64,
            "sprocket-2.0.0-py3-none-any.whl": "1" * 64}
        with (unittest.mock.patch.object(venv, "approved",
                                         return_value=approved),
              self.assertRaises(RuntimeError) as caught):
            venv.pins()
        self.assertIn("sprocket", str(caught.exception))

    def test_pins_refuse_what_is_not_a_wheel(self) -> None:
        """A hand-edited line is named, not a `ValueError` on every run."""
        # `locked` pins on every ordinary run, so this is what they see.
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "nonwheel")
        with (unittest.mock.patch.object(venv, "approved",
                                         return_value={"other.whl": "0" * 64}),
              self.assertRaises(RuntimeError) as caught):
            venv.pins()
        self.assertIn("other.whl", str(caught.exception))
        self.assertIn("is not a wheel name", str(caught.exception))

    def test_a_declaration_needs_no_import_name(self) -> None:
        """A distribution named apart from its module just works.

        This is why the no-argument form imports nothing.  PEP 508 names
        `python-gadget`, the module is `gadgetlib`, and no pair form is
        needed because the program's own `import` supplies the module
        name where a module name belongs.
        """
        # The pair form of `install` exists for exactly this and is not
        # wanted here.
        program: Path = self.declaring_program(
            "two_named_block", 'dependencies = ["python-gadget"]',
            "import gadgetlib\nprint(gadgetlib.__version__)")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "4.5.6")

    def test_several_declarations_are_one_pip_run(self) -> None:
        """Everything declared is fetched together, as `install` does."""
        # One `pip` means `pip` resolves the set and can see a conflict.
        program: Path = self.declaring_program(
            "several", 'dependencies = ["widget", "python-gadget"]',
            "import gadgetlib\nimport widget\n"
            "print(widget.__version__, gadgetlib.__version__)")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "1.2.3 4.5.6")

    def test_no_block_declares_nothing(self) -> None:
        """A program without a block asks for nothing, and is not scolded."""
        # Silence is the requirement: most programs have no block, and
        # every test that constructs an `EZPkg` is one of them.
        program: Path = self.declaring_program(
            "blockless", None, "print('ran')")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "ran")
        self.assertFalse((program.parent / "cache" / "versions").exists())

    def test_an_empty_dependency_list_fetches_nothing(self) -> None:
        """A block declaring no dependencies runs no `pip` at all."""
        # `ezpkg.py`'s own block is this shape, so it had better work.
        program: Path = self.declaring_program(
            "nothing_declared", "dependencies = []", "print('ran')")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "ran")
        self.assertFalse((program.parent / "cache" / "versions").exists())

    def test_a_malformed_block_is_reported(self) -> None:
        """A block that will not parse is the author's mistake, said aloud.

        The opposite of the case above: nothing declared is silence, but
        a declaration that cannot be read must not be mistaken for one.
        """
        # An unclosed array is the likeliest typo in a list of packages.
        program: Path = self.declaring_program(
            "malformed", 'dependencies = [\n"widget"', "print('ran')")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("not valid TOML", done.stderr)

    def test_dependencies_must_be_strings(self) -> None:
        """A `dependencies` of the wrong type is refused by name."""
        # TOML permits it; PEP 508 does not, and `pip` would be baffled.
        program: Path = self.declaring_program(
            "wrong_type", "dependencies = [1, 2]", "print('ran')")
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("must be a list of strings", done.stderr)

    def test_declared_reports_without_fetching(self) -> None:
        """`declared` answers what would be fetched, and fetches nothing."""
        # The question a garbage collector or a report wants to ask.
        program: Path = self.declaring_program(
            "asking", 'dependencies = ["widget", "sprocket>=1"]',
            "print(v.declared())")
        program.write_text(program.read_text().replace("v.install()\n", ""))
        done: subprocess.CompletedProcess[str] = self.run_program(program)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(),
                         "['widget', 'sprocket>=1']")
        self.assertFalse((program.parent / "cache" / "versions").exists())

    def test_declarations_survive_stripped_docstrings(self) -> None:
        """`python3 -OO` cannot hurt a declaration, because it is a comment.

        The reason `main_source` reads the file: `-OO` throws away
        docstrings, and comments were never there at run time at all.
        """
        # Same program, harsher interpreter, same answer.
        program: Path = self.declaring_program(
            "stripped_block", 'dependencies = ["widget"]',
            "import widget\nprint(widget.__version__)")
        environment: dict[str, str] = dict(
            os.environ, PIP_INDEX_URL=self.index_url)
        environment.pop("VIRTUAL_ENV", None)
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-OO", str(program)], env=environment,
            capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.strip(), "1.2.3")

    def test_a_program_with_no_file_declares_nothing(self) -> None:
        """`python3 -c` has no file, so `install()` does nothing."""
        # No file, no block, no complaint; see 6.7.6 for why.
        here: str = str(Path(__file__).resolve().parent)
        cache: Path = self.root / "no_file" / "cache"
        environment: dict[str, str] = dict(
            os.environ, PIP_INDEX_URL=self.index_url)
        environment.pop("VIRTUAL_ENV", None)
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-c",
             (f"import sys; sys.path.insert(0, {here!r}); "
              "import ezpkg; from pathlib import Path; "
              f"v = ezpkg.EZPkg(Path({str(cache)!r})); "
              "print(v.declared()); print(v.install())")],
            env=environment, capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertEqual(done.stdout.split(), ["[]", "None"])


class HarnessTest(unittest.TestCase):
    """Exercise `bootstrap.py`'s measurement harness.

    Those functions run when `bootstrap.py` is invoked with no arguments
    to print its table, which the suite never does, so they were the
    largest uncovered region in the project.  Three of the four are pure
    and quick; `run_tests` is not, because it runs every case three
    times, and stays uncovered on purpose.

    Constructor:
    * `HarnessTest()`, by `unittest` rather than by hand.
    """

    def test_measure_source_counts_the_shipping_case(self) -> None:
        """The counts come from parsing the file, not from a table."""
        # `SHIPPING` is the one that ships; see `T.npp`.
        counts: dict[str, tuple[int, int]] = bootstrap.measure_source()
        self.assertEqual(sorted(counts), sorted(bootstrap.MECHANISMS))
        imports: int
        lines: int
        imports, lines = counts[SHIPPING]
        self.assertEqual(imports, 4)
        self.assertGreater(lines, 5)

    def test_the_recorded_table_matches_the_measurement(self) -> None:
        """The table in the docstring agrees with the code it describes.

        This is the test that was missing on 2026-09-29, when the
        `paste` column was found to have been three lines short in every
        row since `SHARED_LINES` changed.  A hand pasted table drifts;
        this is what notices.
        """
        # Parse the table out of the module docstring and compare.
        counts: dict[str, tuple[int, int]] = bootstrap.measure_source()
        document: str = bootstrap.__doc__ or ""
        rows: int = 0
        line: str
        for line in document.splitlines():
            fields: list[str] = [one.strip() for one in line.split("|")]
            if len(fields) != 10 or fields[1] not in bootstrap.MECHANISMS:
                continue
            rows += 1
            label: str = fields[1]
            with self.subTest(case=label):
                self.assertEqual(int(fields[3]), counts[label][0],
                                 "imports column")
                self.assertEqual(int(fields[4]), counts[label][1],
                                 "lines column")
                self.assertEqual(
                    int(fields[5]),
                    counts[label][1] + bootstrap.SHARED_LINES,
                    "paste column")
        self.assertEqual(rows, len(bootstrap.MECHANISMS), document[:200])

    def test_directory_size_steps_over_what_it_cannot_stat(self) -> None:
        """An entry that vanishes mid-walk is skipped, not fatal.

        Only a race reaches this in earnest -- a file removed between the
        listing and the look -- so `lstat` is patched to make it
        deterministic.
        """
        # The tree measures zero rather than raising.
        root: Path = Path(tempfile.mkdtemp(prefix="harness-gone-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "vanishing.bin").write_bytes(b"x" * 4096)
        with unittest.mock.patch.object(
                bootstrap.pathlib.Path, "lstat",
                side_effect=OSError("it went away")):
            self.assertEqual(bootstrap.directory_size(root), 0)

    def test_directory_size_counts_a_tree(self) -> None:
        """A tree measures more than nothing, and a missing one zero."""
        # Blocks rather than apparent size, so only the shape is checked.
        root: Path = Path(tempfile.mkdtemp(prefix="harness-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "inner").mkdir()
        (root / "inner" / "big.bin").write_bytes(b"x" * 40000)
        self.assertGreater(bootstrap.directory_size(root), 0)
        self.assertEqual(bootstrap.directory_size(root / "absent"), 0)

    def test_the_report_names_cases_that_failed(self) -> None:
        """A case that fails is reported as a failure, by name.

        The report's whole purpose is measurement, so the interesting
        path is the one where a case does not work: the numbers are
        meaningless then, and saying which case broke is the only useful
        output.  `subprocess.run` is patched rather than breaking a real
        index, which makes fifteen cases times three repetitions
        instantaneous instead of minutes.
        """
        # Every case "fails", so every case must be named.
        refused: subprocess.CompletedProcess[str] = (
            subprocess.CompletedProcess(
                args=["python3"], returncode=1, stdout="",
                stderr="pretend the index was unreachable"))
        printed: io.StringIO = io.StringIO()
        # `run_tests` imports `subprocess` inside itself, so there is no
        # attribute on `bootstrap` to patch; the module is shared.
        with (unittest.mock.patch.object(subprocess, "run",
                                         return_value=refused),
              contextlib.redirect_stdout(printed),
              contextlib.redirect_stderr(io.StringIO())):
            bootstrap.run_tests()

        report: str = printed.getvalue()
        self.assertIn("FAILURES:", report)
        self.assertIn("pretend the index was unreachable", report)
        label: str
        for label in bootstrap.MECHANISMS:
            with self.subTest(case=label):
                self.assertIn(f"case {label}:", report)

    def test_format_table_is_rectangular(self) -> None:
        """Every line comes out exactly `TABLE_WIDTH` wide.

        Including the continuation lines a long mechanism name wraps
        onto, which is the part that would go wrong unnoticed.
        """
        # One short row and one whose description has to wrap.
        rows: list[list] = [
            ["pip2", "no venv, pip subprocess", 1, 10, 16, "2.7 s", "0.1 s",
             1762],
            ["nopip2", ("venv(no pip), stdlib wheel and a very long tail that "
                    "must wrap"), 7, 51, 57, "1.4 s", "0.2 s", 1714],
        ]
        table: str = bootstrap.format_table(rows)
        rendered: str
        for rendered in table.splitlines():
            with self.subTest(line=rendered):
                self.assertEqual(len(rendered), bootstrap.TABLE_WIDTH)

        # The mechanism column wraps, so the text arrives in pieces;
        # that it wraps at all is what this is checking.
        self.assertIn("no venv, pip", table)
        self.assertIn("subprocess", table)
        self.assertIn("wrap", table)
        self.assertEqual(table.count("| nopip2 |"), 1, table)


class BootstrapCheckTest(unittest.TestCase):
    """Recognise a pasted bootstrap, and say whether it is current.

    `T.fbanwiis`.  The pasted text comes from `bootstrap.pasted`, so these
    tests read the shipping case exactly as a person would paste it.

    Attributes:
    * `root` (`Path`):
      A temporary directory, removed after each test.

    Constructor:
    * `BootstrapCheckTest()`, by `unittest` rather than by hand.
    """

    # Set by `setUp`.
    root: Path

    def setUp(self) -> None:
        """Make a scratch directory."""
        # Programs and caches for the child processes live here.
        self.root = Path(tempfile.mkdtemp(prefix="stale-"))
        self.addCleanup(shutil.rmtree, self.root, True)

    def shipping(self) -> str:
        """Return the shipping case's `try` block as pasted.

        Returns:
        * (`str`): The block.
        """
        # Found the way a running program's would be.
        block: str | None = ezpkg.find_bootstrap(bootstrap.pasted(SHIPPING))
        assert block is not None
        return block

    def test_the_shipping_paste_is_the_current_entry(self) -> None:
        """Changing the bootstrap without updating the table fails here."""
        # The last entry is the current one by definition.
        self.assertEqual(ezpkg.bootstrap_fingerprint(self.shipping()),
                         list(ezpkg.BOOTSTRAPS)[-1])

    def test_the_quick_start_is_current(self) -> None:
        """`README.md` shows `quick_start.py` exactly, bootstrap current.

        The Quick Start asks a person to copy the program whole, so the
        copy in `README.md`, the file beside it, and `QUICK_START`, which
        the cache receives, must not drift apart, and the bootstrap in
        all of them must be the one that ships.  The program's `# Part`
        comments must also run 1 to 5 in order.
        """
        # The file is the authority, and the page must carry it verbatim.
        here: Path = Path(__file__).resolve().parent
        program: str = (here / "quick_start.py").read_text(encoding="utf-8")
        readme: str = (here / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"```python\n{program}```\n", readme)

        # The copy the cache receives is the same program.
        self.assertEqual(ezpkg.QUICK_START, program)

        # The parts are numbered in order.
        landmarks: list[str] = [line[2:] for line in program.splitlines()
                                if line.startswith("# Part ")]
        self.assertEqual([landmark.split(":")[0] for landmark in landmarks],
                         [f"Part {n}" for n in range(1, 6)])

        # Found the way a running program's would be.
        block: str | None = ezpkg.find_bootstrap(program)
        assert block is not None
        self.assertEqual(ezpkg.bootstrap_fingerprint(block),
                         list(ezpkg.BOOTSTRAPS)[-1])

    def test_the_enabling_copy_is_current(self) -> None:
        """`README.md`'s copy-from bootstrap matches `quick_start.py`.

        "Enabling `EZPkg` for Your Program" shows the bootstrap on its
        own, and that is the copy readers paste into their programs.
        Its Part 1 and docstring are placeholders, so only Part 2's
        imports and Part 3's code are compared, the code by fingerprint.
        See `T.trcb`.
        """
        # The section's first Python block is the copy readers take.
        here: Path = Path(__file__).resolve().parent
        program: str = (here / "quick_start.py").read_text(encoding="utf-8")
        readme: str = (here / "README.md").read_text(encoding="utf-8")
        heading: str = "\n## Enabling `EZPkg` for Your Program\n"
        self.assertIn(heading, readme)
        section: str = readme.split(heading, 1)[1].split("\n## ", 1)[0]
        self.assertIn("```python\n", section)
        enabling: str = section.split("```python\n", 1)[1].split("```", 1)[0]

        # Part 2 is the import lines between the Part 2 and Part 3
        # comments, which must be the same lines in the same order.
        def imports(text: str) -> list[str]:
            part2: str = text.split("# Part 2:", 1)[1].split("# Part 3:")[0]
            return [line for line in part2.splitlines()
                    if line.startswith("import ")]

        self.assertTrue(imports(program))
        self.assertEqual(imports(enabling), imports(program))

        # Part 3 is found the way a running program's would be.
        ours: str | None = ezpkg.find_bootstrap(enabling)
        theirs: str | None = ezpkg.find_bootstrap(program)
        assert ours is not None and theirs is not None
        self.assertEqual(ezpkg.bootstrap_fingerprint(ours),
                         ezpkg.bootstrap_fingerprint(theirs),
                         "the bootstrap in README.md's \"Enabling\" section "
                         "is not the one in quick_start.py")

    def test_layout_and_comments_do_not_change_the_fingerprint(self) -> None:
        """Re-indenting, re-wrapping and commenting leave it the same."""
        # Three cosmetic changes, then one real one.
        block: str = self.shipping()
        same: str = ezpkg.bootstrap_fingerprint(block)
        indented: str = textwrap.indent(block, "    ")
        commented: str = block.replace(
            "m = None\n", "m = None  # Fetch it.\n", 1)
        rewrapped: str = block.replace(
            "; t = pathlib", ";\\\n        t = pathlib", 1)
        for variant in (indented, commented, rewrapped):
            with self.subTest(variant=variant[:40]):
                self.assertNotEqual(variant, block)
                self.assertEqual(ezpkg.bootstrap_fingerprint(variant),
                                 same)
        changed: str = block.replace("None, 30", "None, 31", 1)
        self.assertNotEqual(ezpkg.bootstrap_fingerprint(changed), same)

    def test_the_four_states(self) -> None:
        """Current, stale, edited and absent are told apart."""
        # The program's text is supplied directly, as `main_source` would.
        program: str = (f"import sys\nif False:\n"
                        f"{textwrap.indent(self.shipping(), '    ')}\n")
        venv: ezpkg.EZPkg = ezpkg.EZPkg(self.root / "cache")
        mine: str = ezpkg.bootstrap_fingerprint(self.shipping())
        newer: dict[str, str] = {mine: "nopip3 of yesterday",
                                 "0" * 64: "nopip3 of tomorrow"}
        cases: list[tuple[str, dict[str, str], tuple[str, str]]] = [
            (program, dict(ezpkg.BOOTSTRAPS),
             ("current", list(ezpkg.BOOTSTRAPS.values())[-1])),
            (program, newer, ("stale", "nopip3 of yesterday")),
            (program.replace("None, 30", "None, 31"),
             dict(ezpkg.BOOTSTRAPS), ("edited", "")),
            ("print('no bootstrap here')\n", dict(ezpkg.BOOTSTRAPS),
             ("absent", "")),
        ]
        text: str
        table: dict[str, str]
        wanted: tuple[str, str]
        for text, table, wanted in cases:
            with (self.subTest(wanted=wanted[0]),
                  unittest.mock.patch.object(
                      ezpkg, "main_source",
                      return_value=(self.root / "prog.py", text)),
                  unittest.mock.patch.object(ezpkg, "BOOTSTRAPS", table)):
                self.assertEqual(venv.bootstrap_status(), wanted)
                self.assertIn(wanted[0] if wanted[0] != "absent"
                              else "no bootstrap", venv.report_bootstrap())

        # A program that does not parse has no bootstrap to find.
        self.assertIsNone(ezpkg.find_bootstrap("def broken(:\n"))

        # No program at all, as under `python3 -c`, is absent too.
        with unittest.mock.patch.object(ezpkg, "main_source",
                                        return_value=None):
            self.assertEqual(venv.bootstrap_status(), ("absent", ""))

    def test_install_reports_only_when_asked(self) -> None:
        """`EZPKG_BOOTSTRAP=check` prints one line; otherwise nothing."""
        # A real program carrying the paste, which must not run it.  Its
        # imports follow the paste, or the import scan would object.
        program: Path = self.root / "prog.py"
        program.write_text(
            "import sys\n"
            "if False:\n"
            f"{textwrap.indent(self.shipping(), '    ')}\n"
            f"sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})\n"
            "import ezpkg\n"
            "from pathlib import Path\n"
            f"cache = Path({str(self.root / 'cache')!r})\n"
            "ezpkg.EZPkg(cache).install()\n")
        environment: dict[str, str] = dict(os.environ)
        environment.pop("EZPKG_BOOTSTRAP", None)
        quiet: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, str(program)], env=environment,
            capture_output=True, text=True, check=False)
        asked: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, str(program)],
            env=dict(environment, EZPKG_BOOTSTRAP="check"),
            capture_output=True, text=True, check=False)
        self.assertEqual((quiet.returncode, quiet.stderr), (0, ""))
        self.assertEqual(asked.returncode, 0, asked.stderr)
        self.assertEqual(asked.stderr.strip(),
                         "ezpkg: this program's bootstrap is current, "
                         f"{list(ezpkg.BOOTSTRAPS.values())[-1]}")


class CoverageToolTest(unittest.TestCase):
    """Exercise `ezpkg_coverage.py`, the tool that decides what to cull.

    The cull reads saved counts and says which cases add nothing, and
    cases get deleted on its word, so it needs tests as much as anything
    it measures.  Everything here runs on counts written by hand, with
    child processes mocked, so nothing is traced: the suite may itself
    be running under this tool, and a second tracer would switch the
    first one off.

    Attributes:
    * `root` (`Path`):
      A temporary directory, removed after each test.

    Constructor:
    * `CoverageToolTest()`, by `unittest` rather than by hand.
    """

    # Set by `setUp`.
    root: Path

    def setUp(self) -> None:
        """Make a scratch directory, and choose the default cases."""
        # `EZPKG_TEST` may name one case when the cull runs this
        # suite, and `compare` and `measure_cases` both consult it.
        self.root = Path(tempfile.mkdtemp(prefix="cull-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        patcher: Any = unittest.mock.patch.dict(
            os.environ, {"EZPKG_TEST": "FAST"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def save(self, run: str, lines: Sequence[tuple[str, int]]) -> None:
        """Write `lines` as the counts of one run, the way `report` does.

        Arguments:
        * `run` (`str`):
          The run's directory name: a case label or `BASELINE`.
        * `lines` (`Sequence[tuple[str, int]]`):
          Lines of this project's files, as bare names and numbers.
        """
        # The same tuple `trace` reads back through `infile`.
        here: Path = Path(__file__).resolve().parent
        counts: dict[tuple[str, int], int] = {
            (str(here / name), number): 1 for name, number in lines}
        target: Path = self.root / run
        target.mkdir(parents=True, exist_ok=True)
        with open(target / ezpkg_coverage.COUNTS, "wb") as opened:
            pickle.dump((counts, {}, {}), opened)

    def test_flatten_and_marked(self) -> None:
        """Nested suites flatten, and only marked tests are kept."""
        # A class of its own, with one marked test and one not.
        class Sample(unittest.TestCase):
            """Two tests, one of which runs cases."""

            @runs_cases
            def test_marked(self) -> None:
                """Marked."""

            def test_plain(self) -> None:
                """Not marked."""

        inner: unittest.TestSuite = unittest.TestSuite(
            [Sample("test_marked"), Sample("test_plain")])
        outer: unittest.TestSuite = unittest.TestSuite([inner])
        self.assertEqual(len(ezpkg_coverage.flatten(outer)), 2)
        kept: list[unittest.TestCase] = ezpkg_coverage.marked(outer)
        self.assertEqual([test.id().split(".")[-1] for test in kept],
                         ["test_marked"])

    def test_case_bodies_cover_every_case(self) -> None:
        """Each case's range holds its statements but not its `def`."""
        # One entry per case, and no two ranges overlap.
        bodies: dict[str, tuple[set[int], set[int]]] = (
            ezpkg_coverage.case_bodies())
        self.assertEqual(sorted(bodies), sorted(bootstrap.MECHANISMS))
        seen: set[int] = set()
        label: str
        whole: set[int]
        statements: set[int]
        for label, (whole, statements) in bodies.items():
            with self.subTest(case=label):
                self.assertTrue(statements)
                self.assertLessEqual(statements, whole)
                self.assertNotIn(min(whole), statements)
                self.assertFalse(whole & seen)
                seen |= whole

    def test_covered_keeps_only_this_project(self) -> None:
        """Other files, the instrument itself and zero counts are dropped."""
        # Four kinds of key, of which only one survives.
        here: Path = Path(__file__).resolve().parent
        counts: dict[tuple[str, int], int] = {
            (str(here / "ezpkg.py"), 5): 2,
            (str(here / "ezpkg.py"), 6): 0,
            ("/usr/lib/python3/somewhere.py", 1): 3,
            (str(here / "ezpkg_coverage.py"), 1): 1}
        saved: Path = self.root / "counts"
        with open(saved, "wb") as opened:
            pickle.dump((counts, {}, {}), opened)
        self.assertEqual(ezpkg_coverage.covered(saved),
                         {("ezpkg.py", 5)})

    def test_compare_attributes_lines_to_cases(self) -> None:
        """Beyond, only, own body and the greedy order all add up.

        The shipping case goes first in the greedy order however little
        it adds, and a case's `def` line, which runs whenever the file is
        imported, is nobody's.
        """
        # `nopip1` adds 12 and 13, `nopip2` only 12, and the shipping
        # case 12 and 14, all over a baseline of 10 and 11.
        bodies: dict[str, tuple[set[int], set[int]]] = (
            ezpkg_coverage.case_bodies())
        statement: int = min(bodies["nopip1"][1])
        def_line: int = min(bodies["nopip1"][0])
        self.save(ezpkg_coverage.BASELINE,
                  [("ezpkg.py", 10), ("ezpkg.py", 11)])
        self.save("nopip1", [("ezpkg.py", 10), ("ezpkg.py", 12),
                             ("ezpkg.py", 13),
                             ("bootstrap.py", statement)])
        self.save("nopip2", [("ezpkg.py", 12)])
        # `nopip3` no longer ships but is still a fast case, and adds
        # nothing here.
        self.save("nopip3", [])
        self.save(SHIPPING, [("ezpkg.py", 12), ("ezpkg.py", 14),
                             ("bootstrap.py", def_line)])
        text: str = ezpkg_coverage.compare(self.root)

        # The per-case table, the greedy order, and the line listings.
        self.assertIn("The baseline covers 2 lines", text)
        self.assertNotIn("No counts for", text)
        self.assertIn("| nopip1 | 1 of ", text)
        self.assertIn(" | 2 | 2 | 1 | 1 |", text)
        self.assertIn(f"| {SHIPPING} | 0 of ", text)
        self.assertIn(f"| 1 | {SHIPPING} | 2 | 4 |", text)
        self.assertIn("| 2 | nopip1 | 1 | 5 |", text)
        self.assertIn("| 3 | nopip2 | 0 | 5 |", text)
        self.assertIn(f"## Only `{SHIPPING}`", text)
        self.assertIn("ezpkg.py:14:", text)
        self.assertNotIn("## Only `nopip2`", text)
        self.assertNotIn(f"bootstrap.py:{def_line}:", text)

    def test_compare_names_missing_runs(self) -> None:
        """Runs that never finished are named rather than ignored."""
        # An empty directory is missing everything the default selects.
        text: str = ezpkg_coverage.compare(self.root)
        self.assertIn("No counts for: baseline, nopip1, nopip5.", text)

    def test_report_keeps_the_counts(self) -> None:
        """`report` saves what `compare` later reads back."""
        # Counts set by hand, so no second tracer is ever started.  The
        # stubs type `counts` by file name alone, though `trace` keys it
        # by file and line, hence the cast.
        here: Path = Path(__file__).resolve().parent
        tracer: trace.Trace = ezpkg_coverage.build_tracer()
        tracer.counts = cast(Any, {(str(here / "ezpkg.py"), 7): 1,
                                   (str(self.root / "gone.py"), 1): 1})
        with (contextlib.redirect_stdout(io.StringIO()),
              contextlib.redirect_stderr(io.StringIO())):
            ezpkg_coverage.report(tracer, self.root / "out")
        self.assertEqual(ezpkg_coverage.covered(
            self.root / "out" / ezpkg_coverage.COUNTS),
            {("ezpkg.py", 7)})

    def test_merge_children_folds_every_file(self) -> None:
        """Each child's counts are added into the parent's."""
        # Two children counting the same line, and one a second line.
        tracer: trace.Trace = ezpkg_coverage.build_tracer()
        tracer.counts = cast(Any, {("a.py", 1): 1})
        children: Path = self.root / "children"
        children.mkdir()
        child: int
        for child, counts in enumerate(({("a.py", 1): 2},
                                        {("a.py", 1): 3, ("a.py", 2): 1})):
            with open(children / f"counts-{child}", "wb") as opened:
                pickle.dump((counts, {}, {}), opened)
        self.assertEqual(
            ezpkg_coverage.merge_children(tracer, children), 2)
        self.assertEqual(tracer.counts, {("a.py", 1): 6, ("a.py", 2): 1})

    def test_trace_children_sets_the_environment(self) -> None:
        """Children find the hook on `PYTHONPATH` and the directory."""
        # Restored afterwards by the patch, whatever the call sets.
        hook: str = str(Path(__file__).resolve().parent / "trace_hook")
        counts: Path = self.root / "child-counts"
        with unittest.mock.patch.dict(os.environ, {"PYTHONPATH": "x"}):
            ezpkg_coverage.trace_children(counts)
            self.assertEqual(os.environ["PYTHONPATH"],
                             f"{hook}{os.pathsep}x")
            self.assertEqual(os.environ["EZPKG_COVER"], str(counts))
        self.assertTrue(counts.is_dir())

    def test_measure_one_writes_only_under_its_own_name(self) -> None:
        """A run's command, selection and log are all its own."""
        # The child is mocked; what matters is how it would be started.
        finished: subprocess.CompletedProcess[bytes] = (
            subprocess.CompletedProcess([], 0))
        with unittest.mock.patch.object(
                ezpkg_coverage.subprocess, "run",
                return_value=finished) as run:
            name, status, seconds = ezpkg_coverage.measure_one(
                "pip2", "pip2", True, self.root)
        self.assertEqual((name, status), ("pip2", 0))
        self.assertGreaterEqual(seconds, 0.0)
        self.assertTrue((self.root / "pip2" / "log.txt").is_file())
        command: list[str] = run.call_args.args[0]
        self.assertIn(str(self.root / "pip2"), command)
        self.assertIn("--children", command)
        self.assertIn("--marked-only", command)
        self.assertEqual(run.call_args.kwargs["env"]["EZPKG_TEST"],
                         "pip2")

        # The baseline runs everything, so it asks for no narrowing.
        with unittest.mock.patch.object(
                ezpkg_coverage.subprocess, "run",
                return_value=finished) as run:
            ezpkg_coverage.measure_one(ezpkg_coverage.BASELINE,
                                          "NONE", False, self.root)
        self.assertNotIn("--marked-only", run.call_args.args[0])

    def test_measure_cases_runs_the_baseline_and_each_case(self) -> None:
        """One baseline and one run per selected case; failure is told."""
        # Recorded rather than run, with one case made to fail.
        calls: list[tuple[str, str, bool]] = []

        def fake(name: str, selection: str, marked_only: bool,
                 directory: Path) -> tuple[str, int, float]:
            """Record a run instead of making it.

            Arguments:
            * `name` (`str`): The run's name.
            * `selection` (`str`): Its `EZPKG_TEST`.
            * `marked_only` (`bool`): Whether it narrows to marked tests.
            * `directory` (`Path`): Where it would write.

            Returns:
            * (`tuple[str, int, float]`): As `measure_one` returns.
            """
            # Only `nopip1` fails, so the verdict has to notice it.
            calls.append((name, selection, marked_only))
            return name, int(name == "nopip1"), 0.0

        with (unittest.mock.patch.object(ezpkg_coverage, "measure_one",
                                         fake),
              contextlib.redirect_stderr(io.StringIO()) as told):
            passed: bool = ezpkg_coverage.measure_cases(self.root, 2)
        self.assertFalse(passed)
        self.assertIn("FAILED", told.getvalue())
        self.assertEqual(sorted(calls), sorted(
            [(ezpkg_coverage.BASELINE, "NONE", False)]
            + [(label, label, True) for label in FAST_CASES]))

    def test_main_compare_needs_a_directory(self) -> None:
        """`--compare` alone is refused, as `argparse` refuses things."""
        # Exit status 2 is `argparse`'s for a usage error.
        with (unittest.mock.patch.object(sys, "argv", ["x", "--compare"]),
              contextlib.redirect_stderr(io.StringIO()),
              self.assertRaises(SystemExit) as caught):
            ezpkg_coverage.main()
        self.assertEqual(caught.exception.code, 2)

    def test_main_compare_writes_the_report(self) -> None:
        """`--compare` writes `report.md` and prints the same text."""
        # An empty directory still makes a report, saying what is missing.
        with (unittest.mock.patch.object(
                  sys, "argv", ["x", "--compare", str(self.root)]),
              unittest.mock.patch.object(sys, "path", list(sys.path)),
              contextlib.redirect_stdout(io.StringIO()) as printed,
              contextlib.redirect_stderr(io.StringIO())):
            status: int = ezpkg_coverage.main()
        self.assertEqual(status, 0)
        written: str = (self.root / "report.md").read_text()
        self.assertIn("No counts for", written)
        self.assertIn(written.strip(), printed.getvalue())


    def test_per_case_measures_a_copy(self) -> None:
        """`--per-case` copies the project and goes on in the copy.

        So that editing the project during a long run cannot shift the
        line numbers its report attributes.  See 6.16.4 of `T.tsc`.
        """
        # The copy is real; only the run in it is pretended.
        directory: Path = self.root / "per-case"
        ran: unittest.mock.MagicMock
        with (unittest.mock.patch.object(
                  sys, "argv", ["x", "--per-case", str(directory)]),
              unittest.mock.patch.object(
                  ezpkg_coverage.subprocess, "run",
                  return_value=subprocess.CompletedProcess([], 0)) as ran):
            self.assertEqual(ezpkg_coverage.main(), 0)
        copy: Path = directory / ezpkg_coverage.SNAPSHOT
        self.assertTrue((copy / "ezpkg.py").is_file())
        self.assertTrue((copy / "ezpkg_test.py").is_file())
        self.assertFalse((copy / ".git").exists())
        self.assertFalse((copy / "__pycache__").exists())
        self.assertEqual(ran.call_args.args[0][1:], [
            str(copy / "ezpkg_coverage.py"), "--per-case",
            str(directory)])

        # `--compare` on the same directory goes on in the copy too.
        with (unittest.mock.patch.object(
                  sys, "argv", ["x", "--compare", str(directory)]),
              unittest.mock.patch.object(
                  ezpkg_coverage.subprocess, "run",
                  return_value=subprocess.CompletedProcess([], 0)) as ran):
            self.assertEqual(ezpkg_coverage.main(), 0)
        self.assertEqual(ran.call_args.args[0][1],
                         str(copy / "ezpkg_coverage.py"))


@unittest.skipUnless(os.environ.get("EZPKG_REPORT"),
                     "set EZPKG_REPORT to run bootstrap.py's own report")
class ReportTest(unittest.TestCase):
    """Run `bootstrap.py` with no arguments, which prints its table.

    `run_tests` is the largest thing in this project that the suite
    never reaches: it runs every case `REPETITIONS` times, cold and
    warm, which is minutes of virtual environment building.  Opt in for
    that reason, not because it is unimportant -- the table it produces
    is what every `paste` figure in the logbook is quoted from.

    Attributes:
    * `root` (`Path`):
      A temporary directory holding the index it is aimed at.
    * `server` (`_IndexServer`):
      The server publishing that index.
    * `index_url` (`str`):
      Its base URL.

    Constructor:
    * `ReportTest()`, by `unittest` rather than by hand.
    """

    root: Path
    server: _IndexServer
    index_url: str

    @classmethod
    def setUpClass(cls) -> None:
        """Publish this project into a throwaway index."""
        # The cases fetch `ezpkg` itself, so that is what is served.
        cls.root = Path(tempfile.mkdtemp(prefix="report-"))
        module: Path = Path(__file__).resolve().parent / f"{MODULE}.py"
        wheel: Path = build_wheel(module, DISTRIBUTION, VERSION, SUMMARY,
                                  cls.root / "dist", floor=FLOOR)
        cls.server, cls.index_url = serve_index(
            build_index([wheel], cls.root / "index"))

    @classmethod
    def tearDownClass(cls) -> None:
        """Stop the server and remove what the class built."""
        # Stop serving before the tree underneath goes away.
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_the_report_runs_every_case_and_prints_a_table(self) -> None:
        """The whole measurement harness, end to end.

        Every case is run, timed, measured for disk use, and rendered.
        The assertions are deliberately about shape rather than about
        numbers: the numbers are measurements of this machine and will
        differ on the next one.
        """
        # `HOME` is given a throwaway per case by `run_tests` itself, so
        # the real `~/.ezpkg` is untouched.
        script: Path = Path(__file__).resolve().parent / "bootstrap.py"
        environment: dict[str, str] = dict(
            os.environ, PIP_INDEX_URL=self.index_url,
            BOOTSTRAP_PACKAGE=MODULE,
            BOOTSTRAP_JSON_API=f"{self.index_url}pypi",
            EZPKG_APPROVE="skip")
        environment.pop("VIRTUAL_ENV", None)
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, str(script)], env=environment,
            cwd=str(self.root), capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])

        # One row per case, and every line the width the table promises.
        # The label column's width comes from `bootstrap.py` rather than
        # being written down here: it was 4 until the cases were named,
        # and this test went on looking for `| venv1 |` after it became
        # 6, which only an opt-in run could notice.
        width: int = bootstrap.COLUMN_WIDTHS[0]
        label: str
        for label in bootstrap.MECHANISMS:
            with self.subTest(case=label):
                self.assertIn(f"| {label:<{width}} |", done.stdout)
        rules: int = done.stdout.count("+" + "-" * (width + 2) + "+")
        self.assertGreaterEqual(rules, 3, done.stdout[:400])

    def test_a_nonsense_argument_gets_the_usage_line(self) -> None:
        """An argument that names no case is refused, quickly.

        The one branch of the entry point that needs neither a network
        nor a measurement.
        """
        # Fast, and it costs nothing to keep honest.
        script: Path = Path(__file__).resolve().parent / "bootstrap.py"
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, str(script), "not-a-case"],
            capture_output=True, text=True, check=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("takes no arguments", done.stderr)


class MetadataTest(unittest.TestCase):
    """Exercise `script_metadata`, the PEP 723 block reader.

    Nothing here runs a child or touches the disk: the function takes
    source text and returns what it declared, so a string is the whole
    fixture.

    Constructor:
    * `MetadataTest()`, by `unittest` rather than by hand.
    """

    def test_a_block_is_read(self) -> None:
        """The ordinary case, with both keys PEP 723 defines."""
        # Exactly the shape the PEP's own example uses.
        found: dict[str, Any] | None = ezpkg.script_metadata(
            "# /// script\n"
            '# requires-python = ">=3.11"\n'
            "# dependencies = [\n"
            '#   "requests<3",\n'
            '#   "rich",\n'
            "# ]\n"
            "# ///\n"
            "print('hello')\n")
        self.assertEqual(found, {"requires-python": ">=3.11",
                                 "dependencies": ["requests<3", "rich"]})

    def test_no_block_is_not_an_error(self) -> None:
        """A program without a block declares nothing, and that is fine."""
        # `None` rather than an exception: most programs have no block.
        self.assertIsNone(ezpkg.script_metadata("print('hello')\n"))

    def test_an_empty_block_is_indistinguishable_from_none(self) -> None:
        """An empty block reads as no block at all.

        Measured, not intended: PEP 723's regex requires at least one
        commented line between the fences, so `# /// script` followed
        straight by `# ///` matches nothing.  Any tool sharing the
        regex behaves the same way, which is the reason to keep it.
        """
        # A block declaring nothing and no block ask for nothing, so
        # the two being confused costs nothing either.
        self.assertIsNone(ezpkg.script_metadata("# /// script\n# ///\n"))

    def test_a_block_with_one_blank_line_is_read(self) -> None:
        """One commented line inside is enough for the regex."""
        # The boundary of the case above, which is worth pinning.
        self.assertEqual(
            ezpkg.script_metadata("# /// script\n#\n# ///\n"), {})

    def test_a_bare_comment_line_is_allowed(self) -> None:
        """A `#` with nothing after it is a blank line in the TOML.

        The PEP's regex permits it, so the prefix stripping has to take
        one character from such a line and two from every other.
        """
        # A blank line between two keys is the case that catches this.
        found: dict[str, Any] | None = ezpkg.script_metadata(
            "# /// script\n"
            '# requires-python = ">=3.11"\n'
            "#\n"
            "# dependencies = []\n"
            "# ///\n")
        self.assertEqual(found, {"requires-python": ">=3.11",
                                 "dependencies": []})

    def test_another_block_type_is_ignored(self) -> None:
        """A block that is not `script` is passed over, not refused.

        PEP 723 reserves the syntax for types it has not defined, so a
        program carrying one is not making a mistake.
        """
        # One uncommented line between them, which is what separates
        # the two blocks; see the test below for what happens without.
        found: dict[str, Any] | None = ezpkg.script_metadata(
            "# /// pyproject\n"
            "# [tool.something]\n"
            "# ///\n"
            "\n"
            "# /// script\n"
            "# dependencies = []\n"
            "# ///\n")
        self.assertEqual(found, {"dependencies": []})

    def test_an_adjacent_block_hides_the_script_block(self) -> None:
        """A block butted against another swallows it.

        Measured 2026-09-27, and a limit rather than a choice: the
        `content` group matches commented lines greedily and runs
        straight through the closing fence and the next opener, so the
        whole thing is one `pyproject` match and the `script` block is
        invisible.  A tool sharing the PEP's regex reads it the same
        way, and one blank line between the blocks is the cure.
        """
        # No error, which is the uncomfortable part: nothing is declared
        # and nothing complains.
        self.assertIsNone(ezpkg.script_metadata(
            "# /// pyproject\n"
            "# [tool.something]\n"
            "# ///\n"
            "# /// script\n"
            "# dependencies = []\n"
            "# ///\n"))

    def test_two_blocks_are_an_error(self) -> None:
        """PEP 723 allows one `script` block, so two is a mistake."""
        # Separated by code, which is how the regex sees two of them.
        with self.assertRaises(ValueError) as caught:
            ezpkg.script_metadata(
                "# /// script\n"
                "# dependencies = []\n"
                "# ///\n"
                "print('between')\n"
                "# /// script\n"
                '# dependencies = ["widget"]\n'
                "# ///\n")
        self.assertIn("2 PEP 723 script blocks", str(caught.exception))

    def test_two_adjacent_blocks_are_an_error_too(self) -> None:
        """Duplicates are caught whether or not the regex merges them.

        Two blocks with nothing between them match as a single block,
        so counting matches would call this one block with unparseable
        TOML.  `FENCE` counts the openers instead, which is why the
        complaint names the real problem.
        """
        # The diagnosis is the point: the author wrote two blocks.
        with self.assertRaises(ValueError) as caught:
            ezpkg.script_metadata(
                "# /// script\n"
                "# dependencies = []\n"
                "# ///\n"
                "# /// script\n"
                '# dependencies = ["widget"]\n'
                "# ///\n")
        self.assertIn("2 PEP 723 script blocks", str(caught.exception))

    def test_bad_toml_is_an_error(self) -> None:
        """A block that is not TOML is the author's mistake."""
        # Silence here would install nothing and explain nothing.
        with self.assertRaises(ValueError) as caught:
            ezpkg.script_metadata(
                "# /// script\n"
                "# dependencies = [\n"
                "# ///\n")
        self.assertIn("not valid TOML", str(caught.exception))

    def test_an_unclosed_block_is_no_block(self) -> None:
        """Without the closing `# ///` there is nothing to read.

        This is the PEP's regex being taken literally rather than
        guessing where the author meant the block to stop.
        """
        # A program that happens to start with a comment is the risk.
        self.assertIsNone(ezpkg.script_metadata(
            "# /// script\n"
            "# dependencies = []\n"
            "print('hello')\n"))

    def test_a_simple_floor_is_understood(self) -> None:
        """`>=X.Y` and `>=X.Y.Z` are the shapes with an answer."""
        # Whitespace after the operator is legal and appears in the wild.
        self.assertEqual(ezpkg.python_floor(">=3.11"), (3, 11))
        self.assertEqual(ezpkg.python_floor(">= 3.11"), (3, 11))
        self.assertEqual(ezpkg.python_floor(">=3.11.2"), (3, 11, 2))
        self.assertEqual(ezpkg.python_floor("  >=3.9  "), (3, 9))

    def test_anything_else_gets_no_opinion(self) -> None:
        """Everything PEP 440 permits beyond that is left alone.

        The point of the whitelist: a partial reading of somebody
        else's specification disagrees silently, which is what 6.3.3
        refused.  `None` here means "ask `pip` or `uv`".
        """
        # Each of these is a real thing a block may legitimately say.
        specifier: str
        for specifier in (">=3.9,<4", "!=3.9.*", "~=3.11", ">3.10",
                          "==3.11.*", ">=3", "", "3.11", ">=3.x"):
            with self.subTest(specifier=specifier):
                self.assertIsNone(ezpkg.python_floor(specifier))

    def test_satisfied_compares_plain_releases(self) -> None:
        """The common operators decide, against the installed version.

        PEP 440 pads with zeros, so `2.32` and `2.32.0` are equal, and
        `~=2.32.1` means `>=2.32.1` and `==2.32.*`.
        """
        # One installed version, 2.32.3, judged by many requirements.
        cases: dict[str, bool] = {
            "requests": True, "requests>=2.28,<3": True,
            "requests >= 2.28 , < 3": True, "requests<3": True,
            "requests==2.32.3": True, "requests==2.32.3.0": True,
            "requests!=2.31.0": True, "requests~=2.32.0": True,
            "requests~=2.32.4": False, "requests~=2.31": True,
            "requests~=3.0": False, "requests>2.32.3": False,
            "requests<=2.32.2": False, "requests!=2.32.3": False,
            "requests>=3": False}
        requirement: str
        expected: bool
        with unittest.mock.patch.object(
                ezpkg.importlib.metadata, "version",
                return_value="2.32.3"):
            for requirement, expected in cases.items():
                with self.subTest(requirement=requirement):
                    self.assertIs(ezpkg.satisfied(requirement),
                                  expected)

    def test_satisfied_fetches_when_unsure(self) -> None:
        """Anything it cannot be certain about answers `False`.

        A wrong `True` runs the program against the wrong version; a
        wrong `False` costs one download.  See `T.ewar`.
        """
        # Shapes outside the plain-release subset, then odd versions.
        requirement: str
        with unittest.mock.patch.object(
                ezpkg.importlib.metadata, "version",
                return_value="2.32.3"):
            for requirement in ("requests[socks]", "requests==2.32.*",
                                "requests===2.32.3", "requests~=2",
                                "requests; sys_platform == 'linux'",
                                "requests @ https://example.com/r.whl",
                                "requests>=2.32.3rc1"):
                with self.subTest(requirement=requirement):
                    self.assertFalse(ezpkg.satisfied(requirement))
        version: str
        for version in ("2.33.0rc1", "2.32.3.post1", "2.32.3+local"):
            with (self.subTest(version=version),
                  unittest.mock.patch.object(
                      ezpkg.importlib.metadata, "version",
                      return_value=version)):
                self.assertFalse(ezpkg.satisfied("requests>=2"))
        self.assertFalse(ezpkg.satisfied("no-such-distribution-here"))

    def test_pin_dependencies_rewrites_only_the_array(self) -> None:
        """Part 1 is pinned, `no-build` added, and the rest kept.

        A `]` inside a requirement's extras must not end the array, and
        a block that already has a `[tool.uv]` table keeps what it says.
        """
        # Extras, a comment and a trailing key around the array.
        text: str = ("#!/usr/bin/env python3\n# /// script\n"
                     '# requires-python = ">=3.11"\n'
                     '# dependencies = [\n#   "widget[fast]>=1",  # why\n'
                     '#   "needy",\n# ]\n# [tool.other]\n# x = 1\n'
                     "# ///\nprint('ran')\n")
        pins: list[str] = ["needy==2.0", "widget==1.5"]
        pinned: str | None = ezpkg.pin_dependencies(text, pins)
        assert pinned is not None
        metadata: dict[str, Any] | None = ezpkg.script_metadata(pinned)
        self.assertEqual(metadata, {
            "requires-python": ">=3.11", "dependencies": pins,
            "tool": {"other": {"x": 1}, "uv": {"no-build": True}}})
        self.assertTrue(pinned.startswith("#!/usr/bin/env python3\n"))
        self.assertTrue(pinned.endswith("# ///\nprint('ran')\n"))

        # An author's own `[tool.uv]` gains `no-build` beside its keys,
        # unless it already says, either way.
        own: str = text.replace("[tool.other]", "[tool.uv]")
        kept: str | None = ezpkg.pin_dependencies(own, pins)
        assert kept is not None
        self.assertEqual(ezpkg.script_metadata(kept),
                         {"requires-python": ">=3.11", "dependencies": pins,
                          "tool": {"uv": {"x": 1, "no-build": True}}})
        building: str = own.replace("# x = 1", "# no-build = false")
        built: str | None = ezpkg.pin_dependencies(building, pins)
        assert built is not None
        self.assertEqual(ezpkg.script_metadata(built),
                         {"requires-python": ">=3.11", "dependencies": pins,
                          "tool": {"uv": {"no-build": False}}})

        # Nothing to pin: no block, or a block without `dependencies`.
        self.assertIsNone(ezpkg.pin_dependencies("print('ran')\n", pins))
        self.assertIsNone(ezpkg.pin_dependencies(
            '# /// script\n# requires-python = ">=3.11"\n# ///\n', pins))

    def test_with_dependency_list_replaces_the_array(self) -> None:
        """A short array stays on one line; a long one, one per line.

        A missing one is made above the first table, so it is not the
        table's.  See `T.kdaiis`.
        """
        # One line stays one line while it fits.
        text: str = ("# /// script\n"
                     '# requires-python = ">=3.11"\n'
                     '# dependencies = ["widget"]\n'
                     "# ///\nprint('x')\n")
        self.assertEqual(
            ezpkg.with_dependency_list(text, ["PyYAML", "widget"]),
            text.replace('["widget"]', '["PyYAML", "widget"]'))

        # Too long for one line.
        many: list[str] = [f"package-number-{index}" for index in range(5)]
        added: str | None = ezpkg.with_dependency_list(text, many)
        assert added is not None
        metadata: dict[str, Any] | None = ezpkg.script_metadata(added)
        assert metadata is not None
        self.assertEqual(metadata["dependencies"], many)
        self.assertIn('#   "package-number-4",\n# ]\n', added)

        # None yet: made above the first table.
        bare: str = ("# /// script\n"
                     '# requires-python = ">=3.11"\n'
                     "#\n# [tool.uv]\n"
                     '# exclude-newer = "2026-10-12T00:00:00Z"\n'
                     "# ///\n")
        added = ezpkg.with_dependency_list(bare, ["widget"])
        assert added is not None
        metadata = ezpkg.script_metadata(added)
        assert metadata is not None
        self.assertEqual(metadata["dependencies"], ["widget"])
        self.assertEqual(metadata["tool"]["uv"]["exclude-newer"],
                         "2026-10-12T00:00:00Z")

        # No block, nothing to edit; the lines of each entry.
        self.assertIsNone(ezpkg.with_dependency_list("print('x')\n", ["a"]))
        self.assertEqual(ezpkg.dependency_lines(added), [3])
        self.assertEqual(ezpkg.dependency_lines(
            "#!/usr/bin/env python3\n# /// script\n# dependencies = [\n"
            '#   "a",  # A comment, with "quotes".\n#\n#   "b[x]",\n# ]\n'
            "# ///\n"), [4, 6])

    def test_every_import_and_the_fingerprint(self) -> None:
        """Every import, optional ones marked, in order of first use.

        The fingerprint changes with the order or the entries, but not
        with code that moves without changing the order.
        """
        # `b` only under `try` is optional; `a.c` is `a`; relative is out.
        text: str = ("import a\ntry:\n    import b\nexcept ImportError:\n"
                     "    b = None\nfrom a.c import d\nfrom . import e\n"
                     "def f():\n    import g\n")
        self.assertEqual(ezpkg.every_import(text),
                         [("a", 1, False), ("b", 3, True), ("g", 9, False)])
        one: str = ezpkg.dependency_fingerprint(text, ["a"], ())
        self.assertRegex(one, r"^[0-9a-f]{8}$")
        self.assertEqual(ezpkg.dependency_fingerprint(
            "\n" + text, ["a"], ()), one)
        self.assertNotEqual(ezpkg.dependency_fingerprint(
            text, ["a", "g"], ()), one)
        self.assertNotEqual(ezpkg.dependency_fingerprint(
            text.replace("import a\n", "") + "import a\n", ["a"], ()), one)
        self.assertEqual(ezpkg.line_list([9, 5, 6, 5]), "lines 5-6, 9")
        self.assertEqual(ezpkg.line_list([7]), "line 7")

    def test_a_discrepancy_is_arranged_and_shown(self) -> None:
        """Unexplained entries keep their neighbour; changes are shown.

        `widget` and `sprocket` are placed by imports, `PyYAML` is
        added, `rich` is unused, and `pywin32`, whose modules are not
        known here, stays after `widget`, its neighbour now.
        """
        # Entries as written, and what the imports make of them.
        found: ezpkg.Discrepancy = ezpkg.Discrepancy(
            Path("prog.py"), ["rich", "widget", "pywin32", "sprocket"],
            [4, 5, 6, 7],
            [("entry", 3, ""), ("add", 0, "PyYAML"), ("entry", 1, "")],
            {3: 12, 1: 14}, [(13, "yaml", "PyYAML")], [0], {"sprocket"})
        self.assertEqual(found.target(),
                         ["sprocket", "PyYAML", "widget", "pywin32"])
        self.assertEqual(found.arrange((), ()),
                         ["rich", "sprocket", "widget", "pywin32"])
        self.assertIn("EZPkg: prog.py: its `dependencies` (lines 4, 7) and "
                      "its imports (lines 12-13) disagree.",
                      " ".join(found.summary().split()))
        shown: str = found.changes(found.target(), ["pywin32"])
        self.assertIn('   remove     "rich",\n', shown)
        self.assertIn('   move (7)   "sprocket",\n', shown)
        self.assertIn('   add        "PyYAML",\n', shown)
        self.assertIn('   line 5     "widget",\n', shown)
        self.assertIn('   keep       "pywin32" (added to [tool.ezpkg] '
                      "unimported)\n", shown)

    def test_with_type_ignores_copies_the_authors_comment(self) -> None:
        """New imports get the nearest `type: ignore` above, or none.

        A line with a `type: ignore` already, or a backslash, is left
        alone; one with its own comment gets this one in front of it,
        since `mypy` reads only a comment that starts with `type:`.
        """
        # Two habits; each new import takes the nearest one above.
        text: str = (
            "import json\n"
            "import one  # type: ignore[import-not-found]\n"
            "import new_a\n"
            "import two  # type: ignore[import-untyped]  # Note.\n"
            "import new_b  # Mine.\n"
            "import new_c  # type: ignore\n"
            "import new_d, \\\n    json\n")
        result: str
        given: list[str]
        result, given = ezpkg.with_type_ignores(
            text, {"new_a", "new_b", "new_c", "new_d"},
            {"one", "two", "json"})
        self.assertEqual(result, text.replace(
            "import new_a\n",
            "import new_a  # type: ignore[import-not-found]\n").replace(
            "import new_b  # Mine.\n",
            "import new_b  # type: ignore[import-untyped]  # Note.  "
            "# Mine.\n"))
        self.assertEqual(given, ["new_a", "new_b"])

        # The first habit serves an import above every habit.
        result, given = ezpkg.with_type_ignores(
            "import new\nimport one  # type: ignore\n", {"new"}, {"one"})
        self.assertEqual(result, "import new  # type: ignore\n"
                         "import one  # type: ignore\n")

        # No habit, no comment.
        self.assertEqual(ezpkg.with_type_ignores(
            "import one\nimport new\n", {"new"}, {"one"}),
            ("import one\nimport new\n", []))

    def test_wheel_modules_reads_the_top_level_names(self) -> None:
        """A wheel's importable names come from its member names."""
        # A module, a package, an extension and a `.data/purelib` file.
        with tempfile.TemporaryDirectory() as scratch:
            wheel: Path = Path(scratch) / "mixed-1.0-py3-none-any.whl"
            archive: zipfile.ZipFile
            with zipfile.ZipFile(wheel, "w") as archive:
                for member in ("alone.py", "package/__init__.py",
                               "_speed.cpython-312-x86_64-linux-gnu.so",
                               "mixed-1.0.data/purelib/moved.py",
                               "mixed-1.0.data/scripts/tool",
                               "mixed-1.0.dist-info/METADATA"):
                    archive.writestr(member, "")
            self.assertEqual(ezpkg.wheel_modules(wheel),
                             {"alone", "package", "_speed", "moved"})

    def test_uv_setting_changes_one_key(self) -> None:
        """A key is replaced, added under the header, or a table added."""
        # Replaced in place, added under an existing header, or a table.
        table: str = 'dependencies = []\n\n[tool.uv]\nexclude-newer = "old"\n'
        self.assertEqual(ezpkg.uv_setting(table, "exclude-newer", '"new"'),
                         table.replace("old", "new"))
        self.assertEqual(ezpkg.uv_setting(table, "no-build", "true"),
                         table.replace("[tool.uv]\n",
                                       "[tool.uv]\nno-build = true\n"))
        self.assertEqual(
            ezpkg.uv_setting("dependencies = []\n", "no-build", "true"),
            "dependencies = []\n\n[tool.uv]\nno-build = true")

        # A later table is not mistaken for this one.
        later: str = '[tool.uv]\nx = 1\n[tool.other]\nexclude-newer = 1\n'
        updated: str | None = ezpkg.uv_setting(
            later, "exclude-newer", '"new"')
        assert updated is not None
        self.assertEqual(tomllib.loads(updated)["tool"], {
            "uv": {"x": 1, "exclude-newer": "new"},
            "other": {"exclude-newer": 1}})

        # Dotted keys, or a value over several lines, are not guessed at.
        self.assertIsNone(ezpkg.uv_setting(
            "tool.uv.x = 1\n", "no-build", "true"))
        self.assertIsNone(ezpkg.uv_setting(
            "[tool.uv]\nexclude-newer = [\n 1,\n]\n", "exclude-newer", '"x"'))

    def test_stamp_keeps_encoding_and_line_endings(self) -> None:
        """A latin-1 program with CRLF lines is dated and otherwise kept."""
        # Latin-1, CRLF, and a byte that is not valid UTF-8.
        where: Path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        venv: ezpkg.EZPkg = ezpkg.EZPkg(where / "cache")
        program: Path = where / "prog.py"
        source: str = ("# -*- coding: latin-1 -*-\r\n# /// script\r\n"
                       "# dependencies = []\r\n# ///\r\nprint('caf\u00e9')\r\n")
        program.write_bytes(source.encode("latin-1"))
        with (unittest.mock.patch.object(ezpkg, "main_path",
                                         return_value=program),
              unittest.mock.patch.object(venv, "ask", return_value=True)):
            said: str = venv.stamp("2026-10-12T19:05:41Z")
        self.assertIn("written to", said)
        raw: bytes = program.read_bytes()
        self.assertIn(b"caf\xe9", raw)
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
        self.assertIn(b'# exclude-newer = "2026-10-12T19:05:41Z"\r\n', raw)

        # No block is no date and nothing said.
        program.write_text("print('no block')\n")
        with unittest.mock.patch.object(ezpkg, "main_path",
                                        return_value=program):
            self.assertEqual(venv.stamp("2026-10-12T19:05:41Z"), "")

    def test_lock_mismatches_checks_the_approved_wheels(self) -> None:
        """A wheel missing from the lock, or listed differently, is named.

        Other platforms' wheels are in a lock too, and are ignored.  A
        wheel listed with no hash cannot be checked, so it is named too.
        """
        # One package, two wheels, of which one was approved here.
        lock: dict[str, Any] = {"package": [{"name": "widget", "wheels": [
            {"url": "https://x/a/widget-1.0-py3-none-any.whl",
             "hash": "sha256:" + "a" * 64},
            {"url": "https://x/b/widget-1.0-cp312-win_amd64.whl",
             "hash": "sha256:" + "b" * 64}]}]}
        pure: str = "widget-1.0-py3-none-any.whl"
        self.assertEqual(ezpkg.lock_mismatches(lock, {pure: "a" * 64}),
                         [])
        self.assertEqual(
            ezpkg.lock_mismatches(lock, {pure: "c" * 64}),
            [f"{pure}: lock has sha256:{'a' * 64}"])
        self.assertEqual(
            ezpkg.lock_mismatches(lock, {"needy-2.0-py3-none-any.whl":
                                            "a" * 64}),
            ["needy-2.0-py3-none-any.whl: not in the lock"])
        del lock["package"][0]["wheels"][0]["hash"]
        self.assertEqual(ezpkg.lock_mismatches(lock, {pure: "a" * 64}),
                         [f"{pure}: lock has no hash"])

    def test_our_own_block_reads_back(self) -> None:
        """`ezpkg.py`'s own block parses, and declares nothing.

        The dogfooding of 6.7.5 with a consequence attached: `FLOOR`
        comes from this block through this parser, so breaking either
        one fails here rather than quietly shipping a wheel that claims
        the wrong `Requires-Python`.
        """
        # Read from disk, because the comment is gone at run time.
        source: Path = Path(__file__).resolve().parent / f"{MODULE}.py"
        found: dict[str, Any] | None = ezpkg.script_metadata(
            source.read_text(encoding="utf-8"))
        assert found is not None
        self.assertEqual(found["requires-python"], ">=3.11")
        self.assertEqual(found["dependencies"], [])

    def test_the_linters_agree_with_the_block(self) -> None:
        """`ruff.toml` and `mypy.ini` say what the block says.

        Three files state the floor and only one can be the authority.
        The other two are configuration that no parser can derive, so
        this test is what keeps them honest; see 6.7.7 of `T.p7i`.
        """
        # `>=3.11` spelled three ways, which is why this is a test and
        # not an assignment.
        here: Path = Path(__file__).resolve().parent
        self.assertEqual(FLOOR, ">=3.11")
        self.assertIn('target-version = "py311"',
                      (here / "ruff.toml").read_text(encoding="utf-8"))
        self.assertIn("python_version = 3.11",
                      (here / "mypy.ini").read_text(encoding="utf-8"))


class LocatorTest(unittest.TestCase):
    """Exercise `main_path` and `main_source`.

    Every test here runs a child process, because what is being tested
    is what the interpreter puts in `__main__.__file__`, and this test
    suite's own `__main__` is `unittest`.  A child is the only way to
    control that.  Nothing here needs an index or a network.

    Attributes:
    * `root` (`Path`):
      A temporary directory for the throwaway programs.

    Constructor:
    * `LocatorTest()`, by `unittest` rather than by hand.
    """

    # One directory per test, removed by a cleanup.
    root: Path

    def setUp(self) -> None:
        """Make a directory for this test's programs."""
        # `addCleanup` rather than `tearDown`, so a failure still tidies.
        self.root = Path(tempfile.mkdtemp(prefix="locator-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def program(self, name: str, body: str) -> Path:
        """Write a program that reports what the locator found.

        The marker comment matters: comments do not survive compiling,
        so finding it in what `main_source` returned proves the text
        came from the file rather than from the module object.

        Arguments:
        * `name` (`str`):
          The file name to write, without its suffix.
        * `body` (`str`):
          Statements to run before reporting, or the empty string.

        Returns:
        * (`Path`): The program that was written.
        """
        # `sys.path` first, since `ezpkg` is not installed here.
        here: str = str(Path(__file__).resolve().parent)
        where: Path = self.root / f"{name}.py"
        where.write_text(
            "import sys\n"
            f"sys.path.insert(0, {here!r})\n"
            "import ezpkg\n"
            "# MARKER: a comment, which compiling discards.\n"
            f"{body}"
            "found = ezpkg.main_source()\n"
            "print('path=', ezpkg.main_path())\n"
            "print('text=', found is not None and 'MARKER' in found[1])\n")
        return where

    def run_program(self, *arguments: str, stdin: Path | None = None,
                    cwd: Path | None = None) -> str:
        """Run the interpreter and return what it printed.

        Arguments:
        * `arguments` (`str`):
          Arguments after the interpreter.
        * `stdin` (`Path | None`):
          A file to pipe in, for the `python3 -` case.
        * `cwd` (`Path | None`):
          The working directory, which defaults to this test's.

        Returns:
        * (`str`): Everything the child wrote to its standard output.
        """
        # A failing child is a failing test, so say what it printed.
        source: IO[bytes] | None = None
        if stdin is not None:
            source = stdin.open("rb")
            self.addCleanup(source.close)
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, *arguments], stdin=source, text=True,
            capture_output=True, cwd=str(cwd or self.root), check=False)
        self.assertEqual(done.returncode, 0, done.stderr[-500:])
        return done.stdout

    def test_a_script_is_found(self) -> None:
        """A program run by name reports its own file and text."""
        # The ordinary case, and the one every other test varies.
        program: Path = self.program("plain", "")
        output: str = self.run_program(str(program))
        self.assertIn(f"path= {program}", output)
        self.assertIn("text= True", output)

    def test_a_relative_invocation_is_resolved(self) -> None:
        """The path comes back absolute however the program was named."""
        # A cache keyed on a relative path would move with the shell.
        program: Path = self.program("relative", "")
        output: str = self.run_program("relative.py")
        self.assertIn(f"path= {program}", output)

    def test_dash_m_is_found(self) -> None:
        """`python3 -m prog` still leaves a real file behind."""
        # Worth pinning: the module machinery sets `__file__` here.
        program: Path = self.program("moduled", "")
        output: str = self.run_program("-m", "moduled")
        self.assertIn(f"path= {program}", output)

    def test_dash_c_has_no_program(self) -> None:
        """`python3 -c` has no file, so there is nothing to find."""
        # `__main__` has no `__file__` at all in this case.
        here: str = str(Path(__file__).resolve().parent)
        output: str = self.run_program(
            "-c", f"import sys; sys.path.insert(0, {here!r}); "
            "import ezpkg; print('path=', ezpkg.main_path()); "
            "print('source=', ezpkg.main_source())")
        self.assertIn("path= None", output)
        self.assertIn("source= None", output)

    def test_a_piped_program_has_no_program(self) -> None:
        """`python3 - < prog.py` names `<stdin>`, which is not a file.

        This is why the locator insists the path exist.  Resolving
        `<stdin>` produces a believable path in the working directory
        that names nothing, and an approvals file beside *that* would be
        written into whatever directory the reader happened to be in.
        """
        # The file exists; it is simply not what `__file__` says.
        program: Path = self.program("piped", "")
        output: str = self.run_program("-", stdin=program)
        self.assertIn("path= None", output)
        self.assertIn("text= False", output)

    def test_stripped_comments_are_still_found(self) -> None:
        """`-OO` discards docstrings, and the text still has them.

        Reading the file is the whole reason `main_source` exists: a
        PEP 723 block is a comment, and no comment survives compiling
        under any option at all.
        """
        # `-OO` is the most aggressive thing the interpreter offers.
        program: Path = self.program("stripped", "")
        output: str = self.run_program("-OO", str(program))
        self.assertIn(f"path= {program}", output)
        self.assertIn("text= True", output)

    def test_a_deleted_program_is_gone(self) -> None:
        """A program that removes its own file finds nothing."""
        # The interpreter has read it by now; the disk has not got it.
        program: Path = self.program(
            "deleted", "import os; os.unlink(__file__)\n")
        output: str = self.run_program(str(program))
        self.assertIn("path= None", output)
        self.assertIn("text= False", output)

    def test_a_latin_one_program_is_read(self) -> None:
        """A program is not obliged to be UTF-8, and is still read.

        A coding cookie is honoured by the interpreter, so a program
        carrying one runs perfectly and its block is as valid as anyone
        else's.  Found 2026-09-27 by trying it: with `Path.read_text`
        this program declared nothing, silently, and `tokenize.open` is
        the standard library's answer.
        """
        # The byte is in a comment, which is where a PEP 723 block is.
        program: Path = self.root / "latin.py"
        here: str = str(Path(__file__).resolve().parent)
        program.write_bytes(
            "# -*- coding: latin-1 -*-\n"
            "# MARKER: caf\N{LATIN SMALL LETTER E WITH ACUTE}\n"
            "import sys\n"
            f"sys.path.insert(0, {here!r})\n"
            "import ezpkg\n"
            "found = ezpkg.main_source()\n"
            "print('path=', ezpkg.main_path())\n"
            "print('text=', found is not None and 'MARKER' in found[1])\n"
            .encode("latin-1"))
        output: str = self.run_program(str(program))
        self.assertIn(f"path= {program}", output)
        self.assertIn("text= True", output)

    def test_an_unreadable_program_has_no_text(self) -> None:
        """A file that cannot be read is located but not quoted."""
        # This is the `OSError` arm, which `os.chmod` is the way to
        # reach: the interpreter read the file before the mode changed.
        program: Path = self.program(
            "unreadable", "import os; os.chmod(__file__, 0)\n")
        output: str = self.run_program(str(program))
        self.assertIn(f"path= {program}", output)
        self.assertIn("text= False", output)

    def test_approvals_sit_beside_the_program(self) -> None:
        """`approvals` names `prog.ezpkg` beside `prog.py`."""
        # The one caller that wants the path and not the text.
        program: Path = self.program(
            "beside",
            "import pathlib\n"
            "venv = ezpkg.EZPkg(pathlib.Path('cache'))\n"
            "print('approvals=', venv.approvals())\n")
        output: str = self.run_program(str(program))
        self.assertIn(f"approvals= {program.with_suffix('.ezpkg')}",
                      output)

    def test_approvals_need_a_program(self) -> None:
        """`python3 -c` gets no approvals file, and so no verification."""
        # Nowhere to put one means the gate cannot check anything.
        here: str = str(Path(__file__).resolve().parent)
        output: str = self.run_program(
            "-c", f"import sys; sys.path.insert(0, {here!r}); "
            "import ezpkg; "
            "import pathlib; "
            "venv = ezpkg.EZPkg(pathlib.Path('cache')); "
            "print('approvals=', venv.approvals())")
        self.assertIn("approvals= None", output)


class ReleaseWheelTest(unittest.TestCase):
    """Check that the wheel this project would publish is publishable.

    Nothing here reaches an index.  `build` and `twine` are not
    installed on this machine, which is fitting for a project about
    packages that are not preinstalled but does mean `twine check` is
    not the validator; `pip` accepting the wheel is.  See 6.17.2 of `T.ffrp`.

    Attributes:
    * `root` (`Path`):
      A temporary directory holding the wheel.
    * `wheel` (`Path`):
      The wheel under test, built once for the class.

    Constructor:
    * `ReleaseWheelTest()`, by `unittest` rather than by hand.
    """

    root: Path
    wheel: Path

    @classmethod
    def setUpClass(cls) -> None:
        """Build the release wheel once."""
        # One build serves every test here; none of them mutates it.
        cls.root = Path(tempfile.mkdtemp(prefix="release-"))
        cls.wheel = release_wheel(cls.root / "dist")

    @classmethod
    def tearDownClass(cls) -> None:
        """Remove the directory the wheel was built in."""
        # One directory holds everything.
        shutil.rmtree(cls.root, ignore_errors=True)

    def metadata(self) -> str:
        """Return the wheel's `METADATA` as text.

        Returns:
        * (`str`): The whole file, headers and description alike.
        """
        # The name of the `dist-info` directory follows from the wheel.
        archive: zipfile.ZipFile
        with zipfile.ZipFile(self.wheel) as archive:
            name: str = next(item for item in archive.namelist()
                             if item.endswith("/METADATA"))
            return archive.read(name).decode()

    def test_the_filename_is_what_an_index_expects(self) -> None:
        """Name, version and tag, spelled the way a wheel filename is."""
        # `pip` reads this filename before it reads anything inside.
        self.assertEqual(
            self.wheel.name,
            f"{RELEASE_DISTRIBUTION}-{VERSION}-py3-none-any.whl")

    def test_the_metadata_carries_what_an_index_wants(self) -> None:
        """Every field a project page is built from is present."""
        # `Requires-Python` comes from `ezpkg.py`'s own block.
        text: str = self.metadata()
        for line in (f"Name: {RELEASE_DISTRIBUTION}",
                     f"Version: {VERSION}",
                     f"Summary: {SUMMARY}",
                     f"Requires-Python: {FLOOR}",
                     "License: MIT No Attribution",
                     "Author: Wayne C. Gramlich",
                     "Project-URL: Homepage, https://github.com/",
                     "Classifier: Programming Language :: Python :: 3",
                     "Description-Content-Type: text/markdown"):
            with self.subTest(line=line):
                self.assertIn(line, text)

    def test_the_description_is_the_readme(self) -> None:
        """The project page is the `README.md`, not a summary of it."""
        # The body follows a blank line, which is what makes it the body.
        here: Path = Path(__file__).resolve().parent
        readme: str = (here / "README.md").read_text(encoding="utf-8")
        text: str = self.metadata()
        body: str
        body = text.split("\n\n", 1)[1]
        self.assertNotIn("Description-Content-Type", body)
        self.assertEqual(body, readme)

    def test_no_email_address_is_published(self) -> None:
        """An address in metadata is published to everybody.

        Deliberate: the `Author-email` field is the author's to give,
        and a test is the place to notice if one ever appears.
        """
        # `@` would be the giveaway in any of the header fields.
        headers: str = self.metadata().split("\n\n", 1)[0]
        self.assertNotIn("@", headers)

    def test_pip_accepts_the_wheel(self) -> None:
        """`pip` installs it from a local file, which is the validation.

        `twine check` is not available here, so this stands in: `pip`
        reads the filename, the `METADATA`, the `WHEEL` and the `RECORD`,
        and refuses a wheel it cannot make sense of.
        """
        # `--no-index` proves nothing was fetched to make it work.
        target: Path = self.root / "installed"
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet",
             "--no-input", "--disable-pip-version-check", "--no-index",
             "--no-deps", "--target", str(target), str(self.wheel)],
            capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr[-500:])
        self.assertTrue((target / f"{RELEASE_DISTRIBUTION}.py").is_file())

    def test_the_published_module_is_ours(self) -> None:
        """The module inside is `ezpkg.py`, byte for byte.

        A rehearsal upload publishes the same code under another name;
        if these ever differ, the wheel is not what it claims to be.
        """
        # Byte comparison, because a copy is all it is meant to be.
        here: Path = Path(__file__).resolve().parent
        archive: zipfile.ZipFile
        with zipfile.ZipFile(self.wheel) as archive:
            inside: bytes = archive.read(f"{RELEASE_DISTRIBUTION}.py")
        self.assertEqual(inside, (here / f"{MODULE}.py").read_bytes())

    def test_the_name_is_parameterized(self) -> None:
        """A different distribution name builds a different wheel.

        The name is in one constant because it appears in every pasted
        bootstrap; this is the check that nothing else hard-codes it.
        """
        # `ezpkg` itself is what the real upload would use.
        other: Path = release_wheel(self.root / "other",
                                    distribution="ez_pkg",
                                    version="9.9.9")
        self.assertEqual(other.name, "ez_pkg-9.9.9-py3-none-any.whl")
        archive: zipfile.ZipFile
        with zipfile.ZipFile(other) as archive:
            self.assertIn("ez_pkg-9.9.9.dist-info/METADATA",
                          archive.namelist())

    def test_the_module_states_the_wheel_version(self) -> None:
        """A rehearsal's `__version__` is the wheel's, not the source's.

        Otherwise a `0.0.1.dev...` wheel would import as `0.0.1`, and
        nobody could tell which upload a test machine had fetched.
        """
        # Only the one line differs from `ezpkg.py`.
        here: Path = Path(__file__).resolve().parent
        version: str = dev_version()
        other: Path = release_wheel(self.root / "dev",
                                    distribution="ez_pkg",
                                    version=version)
        archive: zipfile.ZipFile
        with zipfile.ZipFile(other) as archive:
            inside: str = archive.read("ez_pkg.py").decode()
        source: str = (here / f"{MODULE}.py").read_text(encoding="utf-8")
        self.assertEqual(
            inside,
            source.replace(f'__version__: str = "{VERSION}"',
                           f'__version__: str = "{version}"'))
        self.assertIn(f'__version__: str = "{version}"\n', inside)


@unittest.skipUnless(os.environ.get("EZPKG_PYPI"),
                     "set EZPKG_PYPI to fetch from the real index")
class PyPITest(unittest.TestCase):
    """Fetch from the real PyPI, which nothing else here does.

    Everything else in this suite runs against wheels this project built
    and served itself, so three things have never been exercised: real
    wheel tag soup, a real transitive closure, and TLS against the public
    certificate authorities.  See `T.ffrp`.

    Opt in, because this is the one class that can fail for reasons
    outside the repository -- no network, a rate limit, a yanked release
    -- and a suite that fails for those reasons teaches people to ignore
    it.  Versions are pinned for the same reason.  Nothing is uploaded
    anywhere; see 6.17.1.

    Attributes:
    * `root` (`Path`):
      A temporary directory holding the program and its cache.

    Constructor:
    * `PyPITest()`, by `unittest` rather than by hand.
    """

    # Pinned, so that the world changing is not a test failure.
    REQUESTS: str = "requests==2.32.3"
    SETUPTOOLS: str = "setuptools==75.1.0"

    root: Path

    def setUp(self) -> None:
        """Make a directory for this test's program and cache."""
        # `addCleanup`, so a failure still tidies up.
        self.root = Path(tempfile.mkdtemp(prefix="pypi-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def fetch(self, requirement: str, tail: str) -> tuple[str, Path]:
        """Run a program that declares `requirement` and fetch it for real.

        Arguments:
        * `requirement` (`str`):
          A pinned PEP 508 requirement for the program's block.
        * `tail` (`str`):
          Statements to run after `install()`.

        Returns:
        * (`tuple[str, Path]`): What the program printed, and the
          `versions` directory of its cache.
        """
        # A block, the bootstrap's part, and then the program's imports.
        here: str = str(Path(__file__).resolve().parent)
        cache: Path = self.root / "cache"
        program: Path = self.root / "prog.py"
        program.write_text(
            "# /// script\n"
            f'# dependencies = ["{requirement}"]\n'
            "# ///\n"
            "import sys\n"
            f"sys.path.insert(0, {here!r})\n"
            "import ezpkg\n"
            "from pathlib import Path\n"
            f"v = ezpkg.EZPkg(Path({str(cache)!r}))\n"
            "v.install()\n"
            f"{tail}\n")

        # No `PIP_INDEX_URL`, which is the whole point: the default is
        # PyPI over TLS, validated against the system trust store.  And
        # `skip`, because a person running this from a terminal would
        # otherwise be asked to approve it; see 6.17.6.
        environment: dict[str, str] = dict(os.environ,
                                           EZPKG_APPROVE="skip")
        environment.pop("PIP_INDEX_URL", None)
        environment.pop("VIRTUAL_ENV", None)
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, str(program)], env=environment,
            cwd=str(self.root), capture_output=True, text=True,
            check=False)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        return done.stdout, cache / "versions"

    def test_a_real_transitive_closure_arrives(self) -> None:
        """`requests` brings four packages nobody asked for.

        `needy` and `widget` are a synthetic pair; this is the real
        thing, resolved by `pip` against the real index.
        """
        # The version proves it is ours and not the system's copy.
        printed: str
        versions: Path
        printed, versions = self.fetch(
            self.REQUESTS, "import requests\nprint(requests.__version__)")
        self.assertEqual(printed.strip(), "2.32.3")

        # Four dependencies, none of them asked for.
        trees: list[str] = sorted(tree.name for tree in versions.iterdir())
        for name in ("certifi", "charset_normalizer", "idna", "urllib3"):
            with self.subTest(package=name):
                self.assertTrue(any(tree.startswith(name)
                                    for tree in trees), trees)

    def test_twine_fetched_by_us_approves_our_wheel(self) -> None:
        """`twine check --strict` passes on the wheel we would publish.

        Two things at once, and both are the point.  `twine` is fetched
        with `install()` rather than with `pip`, which is the largest
        transitive closure this project has ever resolved -- about twenty
        packages -- and is the dogfood 6.17.2 of `T.ffrp` asks for.  Then that
        `twine` judges our handwritten `METADATA`, which is the only
        independent check available here that an index would accept it.
        """
        # Built with a stamped development version, because no index
        # ever lets a filename be uploaded twice.
        printed: str
        printed, _ = self.fetch(
            "twine==5.1.1",
            "import ezpkg_test as avt\n"
            "from twine.cli import dispatch\n"
            "wheel = avt.release_wheel(Path('dist'),"
            " version=avt.dev_version())\n"
            "dispatch(['check', '--strict', str(wheel)])\n"
            "print('checked', wheel.name)")
        self.assertIn("checked", printed)
        self.assertIn(".dev", printed)

    def real_case(self, label: str, package: str) -> str:
        """Run one `bootstrap.py` case against real PyPI.

        `nopip1` and `nopip2` are the two that choose a wheel themselves, with
        the five line matcher of issue `I.wtmifs`, rather than leaving it
        to `pip`.  Everything else has only ever met wheels this project
        built, so this is the first real tag soup they have seen.

        Arguments:
        * `label` (`str`):
          The case to run.
        * `package` (`str`):
          A distribution whose name is also its import name, because
          `bootstrap.py` has one `PACKAGE` for both.

        Returns:
        * (`str`): The last line the case printed, or its diagnosis.
        """
        # A `HOME` of its own, since every case installs into `~`.
        home: Path = Path(tempfile.mkdtemp(prefix=f"real-{label}-",
                                           dir=self.root))
        script: Path = Path(__file__).resolve().parent / "bootstrap.py"
        environment: dict[str, str] = dict(
            os.environ, HOME=str(home), BOOTSTRAP_PACKAGE=package,
            BOOTSTRAP_JSON_API="https://pypi.org/pypi")
        environment.pop("PIP_INDEX_URL", None)
        environment.pop("VIRTUAL_ENV", None)
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, str(script), label], env=environment,
            capture_output=True, text=True, check=False)
        return (done.stdout + done.stderr).strip().splitlines()[-1]

    @runs_cases
    def test_the_shipping_path_against_pypi(self) -> None:
        """No `pip`, the shipping bootstrap, then a real package, for real.

        What `README.md` promises, as close as it can be run before
        `ezpkg` is published.  An interpreter that has never had `pip`
        runs `nopip3`, which chooses and fetches the real `pip` from the
        real PyPI and checks its SHA-256; only `ezpkg` itself comes
        from a local index, because no index has it yet.  A program
        declaring `requests` then has `ezpkg` fetch it, its four
        dependencies with it, from the real PyPI, through that private
        `pip`, since the interpreter has no other.
        """
        # The bare machine, as in the no-`pip` test.
        if not selected(SHIPPING):
            self.skipTest(f"{SHIPPING} is not selected")
        bare: Path = self.root / "bare"
        made: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-m", "venv", "--without-pip", str(bare)],
            capture_output=True, text=True, check=False)
        if made.returncode != 0:
            self.skipTest(f"no venv here: {made.stderr.strip()[-200:]}")
        python: Path = (bare / "Scripts" / "python.exe" if os.name == "nt"
                        else bare / "bin" / "python")

        # `ezpkg` from a local index, everything else from PyPI.
        module: Path = Path(__file__).resolve().parent / f"{MODULE}.py"
        index: Path = build_index(
            [build_wheel(module, DISTRIBUTION, VERSION, SUMMARY,
                         self.root / "dist", floor=FLOOR)],
            self.root / "index")
        server: _IndexServer
        url: str
        server, url = serve_index(index)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        home: Path = self.root / "home"
        done: subprocess.CompletedProcess[str] = run_bootstrap_case(
            SHIPPING, home, url,
            {"BOOTSTRAP_JSON_API": "https://pypi.org/pypi"},
            python=str(python))
        self.assertEqual(done.returncode, 0, done.stderr[-800:])

        # The `pip` kept is PyPI's, not the copy the local index serves.
        # Compared by content, because the local copy is named after this
        # interpreter's own `pip`, which can be the very version PyPI has.
        kept: bytes = (home / ".ezpkg" / "pip.whl").read_bytes()
        self.assertNotEqual(hashlib.sha256(kept).hexdigest(),
                            hashlib.sha256(pip_wheel()[1]).hexdigest())

        # A program that declares a real package, fetched from PyPI.
        cache: Path = home / ".ezpkg"
        program: Path = self.root / "prog.py"
        program.write_text(
            "# /// script\n"
            f'# dependencies = ["{self.REQUESTS}"]\n'
            "# ///\n"
            "import sys\n"
            f"sys.path.insert(0, {str(cache)!r})\n"
            "import ezpkg\n"
            "ezpkg.EZPkg().install()\n"
            "import requests\n"
            "print(requests.__version__)\n")
        environment: dict[str, str] = dict(os.environ, HOME=str(home))
        environment.pop("PIP_INDEX_URL", None)
        environment.pop("VIRTUAL_ENV", None)
        ran: subprocess.CompletedProcess[str] = subprocess.run(
            [str(python), str(program)], env=environment,
            capture_output=True, text=True, check=False)
        self.assertEqual(ran.returncode, 0, ran.stderr[-800:])
        self.assertEqual(ran.stdout.strip(),
                         self.REQUESTS.partition("==")[2])

    @runs_cases
    def test_the_matcher_handles_real_wheels(self) -> None:
        """A pure wheel and a platform wheel both arrive, from PyPI.

        `certifi` is `py3-none-any`; `coverage` ships a `cp312` wheel
        for this machine and a pure fallback, so the preference order
        is doing real work.
        """
        # Both cases that choose for themselves, both packages.
        label: str
        package: str
        wanted: tuple[str, ...] = selected("nopip1", "nopip2")
        if not wanted:
            self.skipTest("neither nopip1 nor nopip2 is selected")
        for label in wanted:
            for package in ("certifi", "coverage"):
                with self.subTest(case=label, package=package):
                    self.assertIn(f"module {package} version",
                                  self.real_case(label, package))

    @(unittest.expectedFailure if ABI3_GAP else lambda method: method)
    @runs_cases
    def test_the_matcher_handles_abi3_wheels(self) -> None:
        """A stable ABI wheel is missed, which is issue `I.wtmifs`.

        Measured 2026-09-28: `cryptography` publishes
        `cp39-abi3` and `cp311-abi3` wheels, because an abi3 wheel is
        tagged with the **lowest** Python it supports and then serves
        every later one.  The matcher looks for `cp312-abi3` on this
        machine and finds nothing, so a package that `pip` installs
        without comment cannot be fetched at all.

        Written as an expected failure on purpose: it documents the gap
        today, and the day the matcher learns about abi3 the suite
        reports an unexpected success rather than staying quiet.  Only
        from 3.12, though: under 3.11 the `cp311-abi3` wheel is an exact
        match, the gap does not show, and the test simply passes; see
        `ABI3_GAP`.
        """
        # `pip` has no difficulty with this package; we do.
        if not selected("nopip1"):
            self.skipTest("nopip1 is not selected")
        self.assertIn("module cryptography version",
                      self.real_case("nopip1", "cryptography"))

    def test_a_real_wheel_carries_a_pth_file(self) -> None:
        """`setuptools` ships `.pth`, which `T.pf` is about.

        Evidence rather than a fix: the file arrives and lands in the
        tree, where `sys.path.insert` will never execute it.
        `setuptools` is the example because it has no dependencies and
        is on nearly every machine, and because `coverage` -- which the
        logbook claimed shipped one -- measurably does not; see 6.9.
        """
        # The import works; what the `.pth` would add is the `distutils`
        # precedence hook, which is 6.9's business.
        printed: str
        versions: Path
        printed, versions = self.fetch(
            self.SETUPTOOLS,
            "import setuptools\nprint(setuptools.__version__)")
        self.assertEqual(printed.strip(), "75.1.0")
        found: list[Path] = [path for tree in versions.iterdir()
                             for path in tree.glob("*.pth")]
        self.assertEqual([path.name for path in found],
                         ["distutils-precedence.pth"])


def main() -> None:
    """Run the `ezpkg` test suite.

    This is the entry point used when the file is executed directly.
    It hands control to `unittest`, which discovers the test methods
    of `EZPkgTest` and reports on them.
    """
    # unittest reads sys.argv itself and exits when it is done.
    unittest.main()


if __name__ == "__main__":
    main()
