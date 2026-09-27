#!/usr/bin/env python3
"""Test framework for `alt_venv.py`.

This module is the test half of Experiment 2.  The experiment is a
pipeline rather than a set of alternatives -- publish a package to a
local index, fetch it with the bootstrap stub, and import it -- so
`AltVEnvTest` is shaped around building and discarding that index
rather than around a table of measurements.

The index is a [PEP 503](https://peps.python.org/pep-0503/) directory
tree, published over HTTP by `serve_index` so that `pip` reaches it
through a socket rather than reading the files directly.  Step 5.1
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

import base64
import csv
import functools
import hashlib
import html
import http.server
import importlib
import io
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import sysconfig
import tempfile
import threading
import time
import unittest
import unittest.mock
import urllib.error
import urllib.request
import zipfile
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import alt_venv
import bootstrap

# The version comes from the module, so it is written down once.
DISTRIBUTION: str = "alt-venv"
MODULE: str = "alt_venv"
VERSION: str = alt_venv.__version__
SUMMARY: str = "Fetch Python packages that are not preinstalled."

# Which cases the all-case tests exercise.  The full dozen costs most of
# a minute in virtual environment building, so the default is a subset
# that still covers every distinct mechanism: case 3 fetches with
# `urllib` and no virtual environment, case 6 with `pip` in process,
# case 12 with `urllib` inside one, and case 11 is the one whose second
# run used to fail.
FAST_CASES: tuple[str, ...] = ("3", "6", "11", "12")

def platform_tag() -> str:
    """Return a compatibility tag this interpreter would accept.

    Built from the running interpreter rather than written down, so the
    wheel it names is one `pip` will install and one the matcher in
    cases 3 and 12 of `bootstrap.py` will recognise: that matcher looks
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

    `ALT_VENV_TEST` chooses.  Unset or `FAST`, which is the usual
    way to run, gives `FAST_CASES`.  `COMPLETE` gives every case
    `bootstrap.py` defines, which is thorough and slow.

    Returns:
    * (`tuple[str, ...]`): The labels, in `bootstrap.py` order.

    Raises:
    * `ValueError`:
      If `ALT_VENV_TEST` holds something else, because a typo that
      silently ran the fast tests would be worse than a refusal.
    """
    # An unrecognised value is a mistake rather than a default.
    choice: str = os.environ.get("ALT_VENV_TEST", "FAST").upper()
    if choice not in ("FAST", "COMPLETE"):
        raise ValueError(
            f"ALT_VENV_TEST is {choice!r}; use FAST or COMPLETE")
    if choice == "COMPLETE":
        return tuple(bootstrap.MECHANISMS)
    return FAST_CASES


def run_bootstrap_case(label: str, home: Path, index_url: str,
                       extra: dict[str, str] | None = None
                       ) -> subprocess.CompletedProcess[str]:
    """Run one `bootstrap.py` case against a local index.

    The case is aimed at the index entirely through the environment,
    which is what `bootstrap.py` documents that `BOOTSTRAP_PACKAGE` and
    `BOOTSTRAP_JSON_API` are for, so no case body is edited to make it
    testable.  `HOME` is given because every case installs into
    `~/.alt_venv`, and a fresh `HOME` is what makes a run cold.

    Arguments:
    * `label` (`str`):
      The case label, as `bootstrap.py` spells it in `MECHANISMS`.
    * `home` (`Path`):
      The `HOME` for the child.  Reusing one makes a warm run.
    * `index_url` (`str`):
      The base URL of the index, ending in a slash.
    * `extra` (`dict[str, str] | None`):
      More environment, such as the trust store the TLS tests set.

    Returns:
    * (`subprocess.CompletedProcess[str]`): The finished child.
    """
    # Aim it at the index, for `pip` and for the JSON API alike.
    script: Path = Path(__file__).resolve().parent / "bootstrap.py"
    environment: dict[str, str] = dict(
        os.environ, HOME=str(home), PIP_INDEX_URL=index_url,
        BOOTSTRAP_PACKAGE=MODULE, BOOTSTRAP_JSON_API=f"{index_url}pypi",
        **(extra or {}))
    environment.pop("VIRTUAL_ENV", None)
    return subprocess.run(
        [sys.executable, str(script), label],
        env=environment, capture_output=True, text=True, check=False)


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
                tag: str = "py3-none-any") -> Path:
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
    such as the matcher in cases 3 and 12 of `bootstrap.py`, because
    that code never opens the archive; it is not a substitute for a
    genuinely compiled wheel.  See Step 6.5.11 in `LOGBOOK.md`.

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
            f"Version: {version}\nSummary: {summary}\n").encode(),
        f"{info}/WHEEL": (b"Wheel-Version: 1.0\n"
                          b"Generator: alt_venv_test\n"
                          b"Root-Is-Purelib: true\n"
                          + f"Tag: {tag}\n".encode()),
    }

    # Hash every member, then append the self referential RECORD row.
    record: io.StringIO = io.StringIO()
    writer: Any = csv.writer(record, lineterminator="\n")
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


def add_data_member(wheel: Path, sub: str, name: str,
                    text: str) -> Path:
    """Rewrite a wheel with one extra member under its `.data` tree.

    `build_wheel` makes the simple shape, a module and a `.dist-info`.
    A real wheel may also carry a `{distribution}-{version}.data`
    directory whose `purelib` and `platlib` contents belong beside the
    modules rather than under `.data`, and moving them is the one part
    of the wheel specification `AltVEnv.unpack` has to know; see Step
    6.3.12 in `LOGBOOK.md`.  Nothing here can test that without a wheel
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

    Arguments:
    * `wheels` (`list[Path]`):
      The wheels to publish.  Each is copied into the tree.
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
            f'<a href="{html.escape(wheel.name)}">{wheel.name}</a><br>'
            for wheel in files)
        (directory / "index.html").write_text(
            f"<!DOCTYPE html><html><body>{links}</body></html>")
        for wheel in files:
            (directory / wheel.name).write_bytes(wheel.read_bytes())

    # Finish with the root page that lists the projects.
    links = "".join(f'<a href="{project}/">{project}</a><br>'
                    for project in sorted(projects))
    (root / "index.html").write_text(
        f"<!DOCTYPE html><html><body>{links}</body></html>")
    return root


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
    `/pypi/{project}/json` is answered from the tree, because cases 3
    and 12 of `bootstrap.py` read that endpoint with `urllib` rather
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

        # `/pypi/<project>/json` is the only synthesized path.
        parts: list[str] = self.path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "pypi" and parts[2] == "json":
            self.send_json(parts[1])
            return
        super().do_GET()

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
          so that `alt-venv` and `alt_venv` both arrive.
        """
        # Find the project's wheels, which are the whole of the answer.
        normalized: str = re.sub(r"[-_.]+", "-", project).lower()
        directory: Path = Path(self.directory) / normalized
        wheels: list[Path] = sorted(directory.glob("*.whl"))

        # A project with no files is a 404, exactly as PyPI answers.
        if not wheels:
            self.send_error(404, f"no project {normalized}")
            return

        # Build the subset of the payload that cases 3 and 12 read.
        host: str = self.headers.get("Host", "127.0.0.1")
        payload: dict[str, Any] = {"urls": [
            {"filename": wheel.name, "yanked": False,
             "packagetype": "bdist_wheel",
             "url": f"{cast(_IndexServer, self.server).scheme}"
                    f"://{host}/{normalized}/{wheel.name}"}
            for wheel in wheels]}
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
    handler: Any = functools.partial(_IndexHandler, directory=str(root))
    server: _IndexServer = _IndexServer(("127.0.0.1", 0), handler)
    server.faults = {}
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
    # `socketserver` address may be a path or a string, so this reads
    # the two fields an internet socket actually has.
    address: Any = server.server_address
    return server, f"{server.scheme}://{address[0]}:{address[1]}/"


def with_path(*entries: Path) -> str:
    """Return `PYTHONPATH` with `entries` put in front of it.

    Replacing `PYTHONPATH` outright would discard whatever is already
    there, and what is already there may be the `trace_hook` directory
    that `alt_venv_coverage.py` uses to measure this very child; see
    Step 6.6 in `LOGBOOK.md`.

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


class AltVEnvTest(unittest.TestCase):
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
      The wheel built from `alt_venv.py`, tagged `py3-none-any`.

    Constructor:
    * `AltVEnvTest()`, by `unittest` rather than by hand.
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
        cls.root = Path(tempfile.mkdtemp(prefix="alt_venv-"))
        module: Path = Path(__file__).resolve().parent / f"{MODULE}.py"
        cls.wheel = build_wheel(module, DISTRIBUTION, VERSION, SUMMARY,
                                cls.root / "dist")
        # A second wheel, wearing this interpreter's compiled tag and
        # carrying a `.data/purelib` member.  Cases 3 and 12 prefer it,
        # which is the only way to reach their platform branch and their
        # `.data` move; see Step 6.5.11 in `LOGBOOK.md`.
        cls.tagged = build_wheel(module, DISTRIBUTION, VERSION, SUMMARY,
                                 cls.root / "dist", tag=platform_tag())
        add_data_member(cls.tagged, "purelib", "beside_alt_venv.py",
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
        environment: dict[str, str] = dict(
            os.environ, PIP_INDEX_URL=self.index_url, **(extra or {}))
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

    def test_wheel_is_named_correctly(self) -> None:
        """The wheel filename escapes the hyphen and carries the tag."""
        # The hyphen of `alt-venv` becomes an underscore here.
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
        because every case installs into `~/.alt_venv`.

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

    def test_a_truncated_wheel_fails_case_3(self) -> None:
        """Case 3 unzips the wheel itself, so it must fail too."""
        # `zipfile` is what notices, since the fetch itself succeeded.
        # Step 6.1 replaced the traceback with one line, so the
        # assertion reads the message rather than the module name.
        self.inject(".whl", "truncate")
        done: subprocess.CompletedProcess[str] = self.run_case("3")
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

    def test_a_failed_fetch_is_one_line(self) -> None:
        """A case that cannot reach the index says so, without a traceback.

        This is the `0whwnn` issue.  Before Step 6.1 case 3 buried
        `Connection refused` under 47 lines of traceback and case 6
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
                self.assertIn(f"cannot fetch {MODULE}", done.stderr)

    def test_json_api_lists_the_wheel(self) -> None:
        """The synthesized JSON API answers in the shape case 3 reads."""
        # Ask the way case 3 asks, by import name rather than PyPI name.
        url: str = f"{self.index_url}pypi/{MODULE}/json"
        payload: dict[str, Any]
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.load(response)

        # Both wheels are listed, the pure one and the tagged one, so
        # that cases 3 and 12 have something to choose between.
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
                self.assertIn(alt_venv.__version__, done.stdout)
                self.assertIn(".alt_venv", done.stdout)

    def test_every_case_bootstraps_repeatedly(self) -> None:
        """Three runs in one cache all succeed.

        This is the warm path, which nothing tested before.  It is
        where `0cctfd` lived: the guard every case uses asks whether
        the package is a directory, a single module install is not
        one, and case 11 deletes the `pip` it would need for the
        second fetch.  `AltVEnv.repair_module_layout` is what
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
        alt_venv.AltVEnv(self.root / "elsewhere")
        self.assertTrue(source.is_file())

    def test_the_stdlib_cases_choose_the_tagged_wheel(self) -> None:
        """Cases 3 and 12 prefer the compiled tag, and move its `.data`.

        Both regions were dead until the index carried a wheel with this
        interpreter's tag: the matcher's platform branch short-circuits
        on `py3-none-any`, and its `.data` move needs a wheel with a
        `.data` tree.  See `2wtmifs` and Step 6.5.11.

        What this cannot check is that a genuinely compiled wheel would
        import, since ours is pure Python wearing a compiled name.
        """
        # The `.data/purelib` member is the evidence: it only appears
        # beside the module if the move ran.
        label: str
        home: Path
        done: subprocess.CompletedProcess[str]
        for label in ("3", "12"):
            with self.subTest(case=label):
                home = Path(tempfile.mkdtemp(prefix=f"tagged-{label}-",
                                             dir=self.root))
                done = run_bootstrap_case(label, home, self.index_url)
                self.assertEqual(done.returncode, 0, done.stderr[-400:])
                moved: list[Path] = list(
                    (home / ".alt_venv").rglob("beside_alt_venv.py"))
                self.assertEqual(len(moved), 1, done.stdout)
                self.assertNotIn(".data", str(moved[0]))

    def test_no_compatible_wheel_is_reported(self) -> None:
        """A wheel for another platform is refused, not installed.

        The `raise RuntimeError("no compatible wheel found")` in cases 3
        and 12 had never executed.  This is as close as a Linux machine
        can get to the failure `2wtmifs` predicts, which is a manylinux
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
        # up.  Case 12 as well as case 3, because each carries its own
        # copy of the matcher and its own `raise`.
        label: str
        home: Path
        done: subprocess.CompletedProcess[str]
        for label in ("3", "12"):
            with self.subTest(case=label):
                home = Path(tempfile.mkdtemp(prefix=f"wrong-{label}-",
                                             dir=self.root))
                done = run_bootstrap_case(label, home, url)
                self.assertNotEqual(done.returncode, 0)
                self.assertIn("no compatible wheel found", done.stderr)
                self.assertNotIn("Traceback", done.stderr)

    def test_json_api_cases_bootstrap_end_to_end(self) -> None:
        """Cases 3 and 12 fetch and import through the JSON API."""
        # These two are the only cases that bypass pip entirely.
        label: str
        done: subprocess.CompletedProcess[str]
        for label in ("3", "12"):
            with self.subTest(case=label):
                done = self.run_case(label)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn(f"module {MODULE}", done.stdout)
                self.assertIn(alt_venv.__version__, done.stdout)

    def cached_module(self, name: str) -> tuple[Path, Path]:
        """Plant a copy of this module where a case would install it.

        Arguments:
        * `name` (`str`):
          A directory name to keep one test's cache from another's.

        Returns:
        * (`tuple[Path, Path]`): The cache root, and the planted
          `alt_venv.py` inside it.  The path is the deep one that
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
        cache: alt_venv.AltVEnv = alt_venv.AltVEnv(root)
        package: Path | None
        with unittest.mock.patch.object(alt_venv, "__file__",
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
        cache: alt_venv.AltVEnv = alt_venv.AltVEnv(root)
        genuine = Path.read_bytes

        def read_then_vanish(self: Path) -> bytes:
            """Read the file, then delete it as a rival would have."""
            data: bytes = genuine(self)
            if self == stray:
                self.unlink()
            return data

        package: Path | None
        with (unittest.mock.patch.object(alt_venv, "__file__", str(stray)),
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
        cache: alt_venv.AltVEnv = alt_venv.AltVEnv(root)
        with unittest.mock.patch.object(alt_venv, "__path__",
                                        [str(stray.parent)], create=True):
            self.assertIsNone(cache.repair_module_layout())
        self.assertTrue(stray.is_file())

    def test_repair_declines_what_is_not_a_module(self) -> None:
        """Anything but a `.py` file in the cache is left alone."""
        # A frozen or unusual `__file__` must not be moved.
        root: Path
        root, _ = self.cached_module("odd")
        cache: alt_venv.AltVEnv = alt_venv.AltVEnv(root)
        other: Path = root / "not_python.txt"
        other.write_text("not a module\n")
        with unittest.mock.patch.object(alt_venv, "__file__",
                                        str(other)):
            self.assertIsNone(cache.repair_module_layout())
        with unittest.mock.patch.object(alt_venv, "__file__", None):
            self.assertIsNone(cache.repair_module_layout())
        self.assertTrue(other.is_file())

    def test_cases_refuses_an_unknown_choice(self) -> None:
        """A typo in `ALT_VENV_TEST` is refused, not ignored."""
        # Silently running the fast tests would be worse than a refusal.
        with (unittest.mock.patch.dict(
                  os.environ, {"ALT_VENV_TEST": "COMPLEET"}),
              self.assertRaises(ValueError) as caught):
            cases()
        self.assertIn("COMPLEET", str(caught.exception))

        # And the slow choice really does mean every case.
        with unittest.mock.patch.dict(
                os.environ, {"ALT_VENV_TEST": "COMPLETE"}):
            self.assertEqual(cases(), tuple(bootstrap.MECHANISMS))

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
        cache: alt_venv.AltVEnv
        with unittest.mock.patch.object(alt_venv.inspect, "getdoc",
                                        return_value=None):
            cache = alt_venv.AltVEnv(root)
        self.assertEqual(cache.readme.read_text().splitlines()[0],
                         "# AltVEnv Package Cache")

    def test_installed_package_imports(self) -> None:
        """The installed copy imports and exposes `AltVEnv`."""
        # Import in a fresh interpreter, so nothing here can help it.
        # HOME is faked because constructing an `AltVEnv` with no
        # argument writes into `~/.alt_venv` for real.
        target: Path = self.root / "importable"
        (self.root / "fake_home").mkdir(exist_ok=True)
        self.assertEqual(self.pip_install(target, DISTRIBUTION).returncode, 0)
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-c",
             f"import {MODULE}; print({MODULE}.AltVEnv())"],
            env=dict(os.environ, PYTHONPATH=with_path(target),
                     HOME=str(self.root / "fake_home")),
            capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("AltVEnv object", done.stdout)

    def test_alt_venv_constructs(self) -> None:
        """Constructing one makes the cache directory and a README."""
        # Never construct without a root: the default is the real
        # `~/.alt_venv`, and a test must not write there.
        cache: Path = self.root / "cache"
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(cache)
        self.assertTrue(cache.is_dir())
        self.assertEqual(venv.readme, cache / "README.md")

    def test_readme_comes_from_the_docstring(self) -> None:
        """The README is the constructor docstring, retitled."""
        # The summary line becomes the title; `Arguments:` is dropped.
        cache: Path = self.root / "readme"
        text: str = alt_venv.AltVEnv(cache).readme.read_text()
        self.assertTrue(
            text.startswith("# AltVEnv Package Cache\n"))
        self.assertIn("Deleting this directory is safe.", text)
        self.assertNotIn("Arguments:", text)

    def test_default_root_follows_home(self) -> None:
        """With no argument the cache lands under the home directory."""
        # `Path.home()` reads HOME, so a fake HOME keeps this contained.
        home: Path = self.root / "home"
        home.mkdir(exist_ok=True)
        with unittest.mock.patch.dict(os.environ, {"HOME": str(home)}):
            venv: alt_venv.AltVEnv = alt_venv.AltVEnv()
        self.assertEqual(venv.root, home / ".alt_venv")
        self.assertTrue((home / ".alt_venv" / "README.md").is_file())


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

    def test_a_trusted_certificate_is_accepted(self) -> None:
        """Every case succeeds once the certificate is trusted.

        `SSL_CERT_FILE` is what `urllib` honours, through OpenSSL's own
        default verify paths, and `PIP_CERT` is what `pip` honours.
        Both are environment variables, so cases 3 and 12 need no
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
    """Exercise `AltVEnv.install` against a local index.

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

        cls.index = build_index([wheel, two_named, *versions],
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
            "import sys, alt_venv\n"
            "from pathlib import Path\n"
            f"v = alt_venv.AltVEnv(Path({str(target)!r}))\n"
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
          The `sys.path` entry to take out again.
        * `name` (`str`):
          The module to drop from `sys.modules`.
        """
        # `install` inserts and imports; both have to be undone.
        while entry in sys.path:
            sys.path.remove(entry)
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
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(cache)
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
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(cache)
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
        discrimination its exit codes offer.  See Step 6.2.2.
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
        somebody else's index.  See Step 6.2.4.
        """
        # Nothing is fetched, so this needs no index at all.
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(self.root / "option")
        bad: str
        for bad in ("--index-url=http://127.0.0.1:1/", "-e."):
            with self.subTest(requirement=bad):
                with self.assertRaises(ValueError) as caught:
                    venv.install([bad])
                self.assertIn("reads as an option", str(caught.exception))

    def test_install_refuses_a_repeated_import_name(self) -> None:
        """Two entries cannot claim one import name."""
        # `pip` cannot catch this: it never sees our import names, and
        # one module would be returned twice while the other went
        # unmentioned.
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(self.root / "repeat")
        with self.assertRaises(ValueError) as caught:
            venv.install(["widget", "widget"])
        self.assertIn("repeated import name: widget", str(caught.exception))

    def test_pip_owns_requirement_syntax(self) -> None:
        """A malformed requirement is `pip`'s to reject.

        This pins the measurement Step 6.2.4 rests on: `pip` refuses
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
        # This is the `0whwnn` shape: say why, do not just fail to import.
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

        That one sentence is the jail of Step 6.3.1.  A wheel under
        `pending` is an inert zip, so nothing in it can have run, and
        nothing there is importable.
        """
        # Install something, then check where things ended up.
        cache: Path = self.root / "layout"
        self.addCleanup(self.forget, str(cache), "widget")
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(cache)
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
        when it stopped using `pip install`; see Step 6.3.12.  Coverage
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
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(self.root / "dataful-cache")
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
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(cache)
        with unittest.mock.patch.dict(
                os.environ, {"PIP_INDEX_URL": self.index_url}):
            venv.install("sprocket<2")
            del sys.modules["sprocket"]
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
        self.assertEqual(len(venv.remember("sprocket<2") or []), 1)
        self.assertEqual(len(venv.remember("sprocket==1.0.0") or []), 1)

        # Two requests, so two records, both naming the one tree.
        self.assertEqual(len(list(requests.iterdir())), 2)

    def test_unpack_survives_losing_the_race(self) -> None:
        """A tree appearing mid-unpack is accepted, not fought over.

        Two programs starting at once both unpack, and the loser of the
        rename has to take the winner's tree rather than raise.  This is
        the concurrency answer of Step 6.3.9, and coverage found it
        unexercised because one process never loses.
        """
        # Make the rename into place fail exactly as a lost race does.
        cache: Path = self.root / "raced"
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(cache)
        source: Path = self.root / "raced-src" / "raced.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('"""r."""\n__version__ = "1.0.0"\n')
        wheel: Path = build_wheel(source, "raced", "1.0.0", "r",
                                  self.root / "raced-dist")
        staged: Path = Path(shutil.copy(wheel, venv.paths()[0]))
        expected: Path = venv.paths()[2] / venv.version_key(staged)

        # Only the staging rename fails; the `.data` moves must not.
        genuine = Path.rename

        def refuse(self: Path, target: Any) -> Path:
            """Fail the one rename that puts a tree into place."""
            if Path(target) == expected:
                raise OSError("another process got there first")
            return genuine(self, target)

        with unittest.mock.patch.object(Path, "rename", refuse):
            self.assertEqual(venv.unpack(staged), expected)

    def test_a_version_tree_names_the_interpreter(self) -> None:
        """A tree name carries version, interpreter and platform.

        This is the `0nicav` fix: the same directory reached by a
        different Python would otherwise load whatever the last one
        left behind.
        """
        # The name is built from the wheel's own filename plus this
        # interpreter, so it can be predicted exactly.
        cache: Path = self.root / "named"
        self.addCleanup(self.forget, str(cache), "widget")
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(cache)
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
        disagree with `pip`; see Step 6.3.4.
        """
        # First call fetches; second must not run `pip` at all.
        cache: Path = self.root / "remembered"
        self.addCleanup(self.forget, str(cache), "sprocket")
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(cache)
        calls: list[Sequence[str]] = []
        genuine = subprocess.run

        def counted(*args: Any, **kwargs: Any) -> Any:
            """Record an invocation and then perform it."""
            calls.append(args[0])
            return genuine(*args, **kwargs)

        with (unittest.mock.patch.dict(
                  os.environ, {"PIP_INDEX_URL": self.index_url}),
              unittest.mock.patch.object(alt_venv.subprocess, "run",
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
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(cache)
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
            "import alt_venv\n"
            "from pathlib import Path\n"
            f"cache = Path({str(cache)!r})\n"
            "one = alt_venv.AltVEnv(cache).install('sprocket<2')\n"
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
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(cache)
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
        them inside the window on purpose.  See Step 6.4.3.
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
            "import alt_venv\n"
            f"cache = Path({str(cache)!r})\n"
            "venv = alt_venv.AltVEnv(cache)\n"
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
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(cache)
        versions: Path = venv.paths()[2]
        self.assertEqual(len(set(answers)), 1, answers)
        self.assertEqual([p.name for p in versions.iterdir()], answers[:1])

    def test_a_kept_wheel_records_its_hash(self) -> None:
        """The hash of what arrived is written down beside the wheel.

        Not what the index claimed, which is unavailable anyway since
        `pip download` refuses `--report`; see Step 6.3.7.  This is the
        identity Step 6.6 approves, and the only thing that could notice
        a distribution re-uploaded under a version it had already used.
        """
        # Install, then check the sidecar against the file itself.
        cache: Path = self.root / "hashed"
        self.addCleanup(self.forget, str(cache), "widget")
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(cache)
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

        This is the point of Step 6.2: `pip` resolves the set together,
        and one invocation is what makes Step 6.3's freshness check
        affordable.  Counted rather than inferred, by wrapping
        `subprocess.run` and letting the real one do the work.
        """
        # Run it in process, so the call being counted is the real one.
        cache: Path = self.root / "once"
        self.addCleanup(self.forget, str(cache), "widget")
        self.addCleanup(self.forget, str(cache), "gadgetlib")
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(cache)

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
              unittest.mock.patch.object(alt_venv.subprocess, "run",
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

    def test_contains_reports_what_is_cached(self) -> None:
        """`contains` is False before an install and True after."""
        # A single module counts, not only a package directory.
        target: Path = self.root / "contains"
        venv: alt_venv.AltVEnv = alt_venv.AltVEnv(target)
        self.assertFalse(venv.contains("widget"))
        self.install(target, "widget")
        self.assertTrue(venv.contains("widget"))


def main() -> None:
    """Run the `alt_venv` test suite.

    This is the entry point used when the file is executed directly.
    It hands control to `unittest`, which discovers the test methods
    of `AltVEnvTest` and reports on them.
    """
    # unittest reads sys.argv itself and exits when it is done.
    unittest.main()


if __name__ == "__main__":
    main()
