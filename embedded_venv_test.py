#!/usr/bin/env python3
"""Test framework for `embedded_venv.py`.

This module is the test half of Experiment 2.  The experiment is a
pipeline rather than a set of alternatives -- publish a package to a
local index, fetch it with the bootstrap stub, and import it -- so
`EmbeddedVEnvTest` is shaped around building and discarding that index
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
import tempfile
import threading
import time
import unittest
import unittest.mock
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import bootstrap
import embedded_venv

# The version comes from the module, so it is written down once.
DISTRIBUTION: str = "embedded-venv"
MODULE: str = "embedded_venv"
VERSION: str = embedded_venv.__version__
SUMMARY: str = "Fetch Python packages that are not preinstalled."

# Which cases the all-case tests exercise.  The full dozen costs most of
# a minute in virtual environment building, so the default is a subset
# that still covers every distinct mechanism: case 3 fetches with
# `urllib` and no virtual environment, case 6 with `pip` in process,
# case 12 with `urllib` inside one, and case 11 is the one whose second
# run used to fail.
FAST_CASES: tuple[str, ...] = ("3", "6", "11", "12")

# How long the `hang` fault waits.  Longer than the client timeouts the
# failure tests set, and short enough not to slow the suite down.
HANG_SECONDS: float = 3.0


def cases() -> tuple[str, ...]:
    """Return the case labels the all-case tests should exercise.

    `EMBEDDEDVEN_TEST` chooses.  Unset or `FAST`, which is the usual
    way to run, gives `FAST_CASES`.  `COMPLETE` gives every case
    `bootstrap.py` defines, which is thorough and slow.

    Returns:
    * (`tuple[str, ...]`): The labels, in `bootstrap.py` order.

    Raises:
    * `ValueError`:
      If `EMBEDDEDVEN_TEST` holds something else, because a typo that
      silently ran the fast tests would be worse than a refusal.
    """
    # An unrecognised value is a mistake rather than a default.
    choice: str = os.environ.get("EMBEDDEDVEN_TEST", "FAST").upper()
    if choice not in ("FAST", "COMPLETE"):
        raise ValueError(
            f"EMBEDDEDVEN_TEST is {choice!r}; use FAST or COMPLETE")
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
    `~/.embedded_venv`, and a fresh `HOME` is what makes a run cold.

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
                summary: str, directory: Path) -> Path:
    """Build a pure Python wheel holding one module.

    A wheel is a zip archive with an agreed layout, so building one
    needs no packaging tools at all.  Three files go in beside the
    module: `METADATA` names the distribution, `WHEEL` declares the
    archive format and its compatibility tag, and `RECORD` lists every
    member with its SHA-256 digest and size.  `RECORD` lists itself
    with both fields left empty, because it cannot contain its own
    digest.

    The tag is `py3-none-any`, meaning any Python 3, any ABI, any
    platform.  That is what makes the wheel `pip` installable
    everywhere without a compiled component.

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
                          b"Generator: embedded_venv_test\n"
                          b"Root-Is-Purelib: true\nTag: py3-none-any\n"),
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
    wheel: Path = directory / f"{escaped}-{version}-py3-none-any.whl"
    archive: zipfile.ZipFile
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in members.items():
            archive.writestr(path, content)
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
      `missing`, which answers 404, `error`, which answers 500, and
      `hang`, which waits `HANG_SECONDS` and then answers normally.
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
          One of `truncate`, `missing`, `error` or `hang`.  See
          `_IndexServer.faults`.

        Returns:
        * (`bool`): True when the request has been answered and the
          caller should stop.  `hang` returns False, because it delays
          a correct answer rather than replacing it.
        """
        # Two of the faults are nothing but a status code.
        if fault == "missing":
            self.send_error(404, "fault: missing")
            return True
        if fault == "error":
            self.send_error(500, "fault: error")
            return True

        # A hang delays the real answer rather than replacing it.
        if fault == "hang":
            time.sleep(HANG_SECONDS)
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
          so that `embedded-venv` and `embedded_venv` both arrive.
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


class EmbeddedVEnvTest(unittest.TestCase):
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
    * `wheel` (`Path`):
      The wheel built from `embedded_venv.py`.

    Constructor:
    * `EmbeddedVEnvTest()`, by `unittest` rather than by hand.
    """

    # Built once by `setUpClass`, shared by every test below.
    index: Path
    index_url: str
    root: Path
    server: _IndexServer
    wheel: Path

    @classmethod
    def setUpClass(cls) -> None:
        """Build the wheel and the index, then publish it over HTTP."""
        # Publish this project into a throwaway index.
        cls.root = Path(tempfile.mkdtemp(prefix="embedded_venv-"))
        module: Path = Path(__file__).resolve().parent / f"{MODULE}.py"
        cls.wheel = build_wheel(module, DISTRIBUTION, VERSION, SUMMARY,
                                cls.root / "dist")
        cls.index = build_index([cls.wheel], cls.root / "index")

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
        # The hyphen of `embedded-venv` becomes an underscore here.
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
        because every case installs into `~/.embedded_venv`.

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
        """Make the server misbehave for the rest of one test only.

        The entry is removed by a cleanup rather than by the test, so a
        failing assertion cannot leave the fault in place for whatever
        test `unittest` runs next.

        Arguments:
        * `suffix` (`str`):
          The path suffix to afflict, such as `.whl`.
        * `fault` (`str`):
          The fault name.  See `_IndexServer.faults`.
        """
        # Register the removal first, so an exception cannot skip it.
        self.addCleanup(self.server.faults.pop, suffix, None)
        self.server.faults[suffix] = fault

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
        self.inject(".whl", "truncate")
        done: subprocess.CompletedProcess[str] = self.run_case("3")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("zipfile", done.stderr)

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

    def test_json_api_lists_the_wheel(self) -> None:
        """The synthesized JSON API answers in the shape case 3 reads."""
        # Ask the way case 3 asks, by import name rather than PyPI name.
        url: str = f"{self.index_url}pypi/{MODULE}/json"
        payload: dict[str, Any]
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.load(response)
        self.assertEqual(len(payload["urls"]), 1)
        self.assertEqual(payload["urls"][0]["filename"], self.wheel.name)
        self.assertTrue(payload["urls"][0]["url"].endswith(self.wheel.name))

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
                self.assertIn(embedded_venv.__version__, done.stdout)
                self.assertIn(".embedded_venv", done.stdout)

    def test_every_case_bootstraps_repeatedly(self) -> None:
        """Three runs in one cache all succeed.

        This is the warm path, which nothing tested before.  It is
        where `0cctfd` lived: the guard every case uses asks whether
        the package is a directory, a single module install is not
        one, and case 11 deletes the `pip` it would need for the
        second fetch.  `EmbeddedVEnv.repair_module_layout` is what
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
        embedded_venv.EmbeddedVEnv(self.root / "elsewhere")
        self.assertTrue(source.is_file())

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
                self.assertIn(embedded_venv.__version__, done.stdout)

    def cached_module(self, name: str) -> tuple[Path, Path]:
        """Plant a copy of this module where a case would install it.

        Arguments:
        * `name` (`str`):
          A directory name to keep one test's cache from another's.

        Returns:
        * (`tuple[Path, Path]`): The cache root, and the planted
          `embedded_venv.py` inside it.  The path is the deep one that
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
        cache: embedded_venv.EmbeddedVEnv = embedded_venv.EmbeddedVEnv(root)
        package: Path | None
        with unittest.mock.patch.object(embedded_venv, "__file__",
                                        str(stray)):
            package = cache.repair_module_layout()
        self.assertEqual(package, stray.parent / MODULE)
        self.assertTrue((stray.parent / MODULE / "__init__.py").is_file())
        self.assertFalse(stray.exists())

    def test_repair_declines_a_package(self) -> None:
        """Once the module is a package the repair does nothing."""
        # A package has a `__path__`, and nesting would eat `__init__.py`.
        root: Path
        stray: Path
        root, stray = self.cached_module("already")
        cache: embedded_venv.EmbeddedVEnv = embedded_venv.EmbeddedVEnv(root)
        with unittest.mock.patch.object(embedded_venv, "__path__",
                                        [str(stray.parent)], create=True):
            self.assertIsNone(cache.repair_module_layout())
        self.assertTrue(stray.is_file())

    def test_repair_declines_what_is_not_a_module(self) -> None:
        """Anything but a `.py` file in the cache is left alone."""
        # A frozen or unusual `__file__` must not be moved.
        root: Path
        root, _ = self.cached_module("odd")
        cache: embedded_venv.EmbeddedVEnv = embedded_venv.EmbeddedVEnv(root)
        other: Path = root / "not_python.txt"
        other.write_text("not a module\n")
        with unittest.mock.patch.object(embedded_venv, "__file__",
                                        str(other)):
            self.assertIsNone(cache.repair_module_layout())
        with unittest.mock.patch.object(embedded_venv, "__file__", None):
            self.assertIsNone(cache.repair_module_layout())
        self.assertTrue(other.is_file())

    def test_cases_refuses_an_unknown_choice(self) -> None:
        """A typo in `EMBEDDEDVEN_TEST` is refused, not ignored."""
        # Silently running the fast tests would be worse than a refusal.
        with (unittest.mock.patch.dict(
                  os.environ, {"EMBEDDEDVEN_TEST": "COMPLEET"}),
              self.assertRaises(ValueError) as caught):
            cases()
        self.assertIn("COMPLEET", str(caught.exception))

        # And the slow choice really does mean every case.
        with unittest.mock.patch.dict(
                os.environ, {"EMBEDDEDVEN_TEST": "COMPLETE"}):
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
        cache: embedded_venv.EmbeddedVEnv
        with unittest.mock.patch.object(embedded_venv.inspect, "getdoc",
                                        return_value=None):
            cache = embedded_venv.EmbeddedVEnv(root)
        self.assertEqual(cache.readme.read_text().splitlines()[0],
                         "# Embedded Virtual Environment Cache")

    def test_installed_package_imports(self) -> None:
        """The installed copy imports and exposes `EmbeddedVEnv`."""
        # Import in a fresh interpreter, so nothing here can help it.
        # HOME is faked because constructing an `EmbeddedVEnv` with no
        # argument writes into `~/.embedded_venv` for real.
        target: Path = self.root / "importable"
        (self.root / "fake_home").mkdir(exist_ok=True)
        self.assertEqual(self.pip_install(target, DISTRIBUTION).returncode, 0)
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-c",
             f"import {MODULE}; print({MODULE}.EmbeddedVEnv())"],
            env=dict(os.environ, PYTHONPATH=str(target),
                     HOME=str(self.root / "fake_home")),
            capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("EmbeddedVEnv object", done.stdout)

    def test_embedded_venv_constructs(self) -> None:
        """Constructing one makes the cache directory and a README."""
        # Never construct without a root: the default is the real
        # `~/.embedded_venv`, and a test must not write there.
        cache: Path = self.root / "cache"
        venv: embedded_venv.EmbeddedVEnv = embedded_venv.EmbeddedVEnv(cache)
        self.assertTrue(cache.is_dir())
        self.assertEqual(venv.readme, cache / "README.md")

    def test_readme_comes_from_the_docstring(self) -> None:
        """The README is the constructor docstring, retitled."""
        # The summary line becomes the title; `Arguments:` is dropped.
        cache: Path = self.root / "readme"
        text: str = embedded_venv.EmbeddedVEnv(cache).readme.read_text()
        self.assertTrue(
            text.startswith("# Embedded Virtual Environment Cache\n"))
        self.assertIn("Deleting this directory is safe.", text)
        self.assertNotIn("Arguments:", text)

    def test_default_root_follows_home(self) -> None:
        """With no argument the cache lands under the home directory."""
        # `Path.home()` reads HOME, so a fake HOME keeps this contained.
        home: Path = self.root / "home"
        home.mkdir(exist_ok=True)
        with unittest.mock.patch.dict(os.environ, {"HOME": str(home)}):
            venv: embedded_venv.EmbeddedVEnv = embedded_venv.EmbeddedVEnv()
        self.assertEqual(venv.root, home / ".embedded_venv")
        self.assertTrue((home / ".embedded_venv" / "README.md").is_file())


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


class IncludeTest(unittest.TestCase):
    """Exercise `EmbeddedVEnv.include` against a local index.

    A throwaway package is built and published for these tests, so
    that nothing here depends on PyPI or on the network.

    Attributes:
    * `cache` (`Path`):
      The cache directory that `include` installs into.
    * `index` (`Path`):
      The PEP 503 tree holding the throwaway package.
    * `index_url` (`str`):
      That same tree as an HTTP URL, for `PIP_INDEX_URL`.
    * `root` (`Path`):
      The temporary directory holding everything.
    * `server` (`_IndexServer`):
      The server publishing `index`.

    Constructor:
    * `IncludeTest()`, by `unittest` rather than by hand.
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
        cls.root = Path(tempfile.mkdtemp(prefix="include-"))
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
        cls.index = build_index([wheel, two_named], cls.root / "index")
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

    def include(self, target: Path, package: str, *argv: str,
                distribution: str | None = None) -> str:
        """Run `include` in a child interpreter and return its output.

        A child is used because `include` inserts into `sys.path` and
        imports, neither of which should leak between tests.

        Arguments:
        * `target` (`Path`):
          The cache directory to install into.
        * `package` (`str`):
          What to include.
        * `argv` (`str`):
          Extra arguments for `pip install`.
        * `distribution` (`str | None`):
          The PyPI name, when it differs from the import name.

        Returns:
        * (`str`): Standard output, or standard error if it failed.
        """
        # Point pip at the local index and run the whole thing remotely.
        script: str = (
            "import sys, embedded_venv;"
            "from pathlib import Path;"
            f"v = embedded_venv.EmbeddedVEnv(Path({str(target)!r}));"
            f"m = v.include({package!r}, {list(argv)!r}, "
            f"{distribution!r});"
            "print(m.__name__, m.__version__)")
        environment: dict[str, str] = dict(
            os.environ, PIP_INDEX_URL=self.index_url,
            PYTHONPATH=str(Path(__file__).resolve().parent),
            HOME=str(self.root / "home"))
        done: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, check=False)
        return done.stdout.strip() if done.returncode == 0 else done.stderr

    def forget(self, entry: str, name: str) -> None:
        """Undo what an in-process `include` did to this interpreter.

        Arguments:
        * `entry` (`str`):
          The `sys.path` entry to take out again.
        * `name` (`str`):
          The module to drop from `sys.modules`.
        """
        # `include` inserts and imports; both have to be undone.
        while entry in sys.path:
            sys.path.remove(entry)
        sys.modules.pop(name, None)
        importlib.invalidate_caches()

    def test_include_works_in_this_interpreter(self) -> None:
        """`include` fetches and imports without a child process.

        Every other test here drives `include` through a child, which
        keeps `sys.path` clean but means the method's own lines are
        never measured.  This one runs it directly and puts the
        interpreter back afterwards.
        """
        # Register the cleanup before anything is inserted or imported.
        cache: Path = self.root / "in-process"
        self.addCleanup(self.forget, str(cache), "widget")
        venv: embedded_venv.EmbeddedVEnv = embedded_venv.EmbeddedVEnv(cache)
        module: ModuleType
        with unittest.mock.patch.dict(
                os.environ, {"PIP_INDEX_URL": self.index_url}):
            module = venv.include("widget")
        self.assertEqual(module.__name__, "widget")
        self.assertEqual(module.__version__, "1.2.3")
        self.assertTrue(venv.contains("widget"))

    def test_include_in_process_reports_a_failure(self) -> None:
        """A package the index lacks raises with pip's own reason."""
        # This is the no network case, which a caller must be told about.
        cache: Path = self.root / "in-process-missing"
        self.addCleanup(self.forget, str(cache), "nosuchwidget")
        venv: embedded_venv.EmbeddedVEnv = embedded_venv.EmbeddedVEnv(cache)
        with (unittest.mock.patch.dict(
                  os.environ, {"PIP_INDEX_URL": self.index_url}),
              self.assertRaises(RuntimeError) as caught):
            venv.include("nosuchwidget")
        self.assertIn("could not fetch", str(caught.exception))

    def test_include_fetches_and_imports(self) -> None:
        """A missing package is fetched and handed back imported."""
        # The package does not exist anywhere but the local index.
        self.assertEqual(self.include(self.cache, "widget"), "widget 1.2.3")
        self.assertTrue((self.cache / "widget.py").is_file())

    def test_include_passes_argv_to_pip(self) -> None:
        """Extra arguments reach `pip install`."""
        # `--no-deps` is harmless here, so success proves it parsed.
        target: Path = self.root / "argv"
        self.assertEqual(self.include(target, "widget", "--no-deps"),
                         "widget 1.2.3")

    def test_include_rejects_bad_argv(self) -> None:
        """A bad argument fails loudly rather than silently."""
        # pip exits non-zero, and `include` turns that into an error.
        target: Path = self.root / "bad"
        self.assertIn("could not fetch",
                      self.include(target, "widget", "--no-such-option"))

    def test_include_reports_a_missing_package(self) -> None:
        """A package the index does not have raises a clear error."""
        # This is the `0whwnn` shape: say why, do not just fail to import.
        target: Path = self.root / "missing"
        output: str = self.include(target, "nosuchwidget")
        self.assertIn("could not fetch 'nosuchwidget'", output)

    def test_include_takes_two_names(self) -> None:
        """A distribution named apart from its module still works."""
        # `pip` is asked for `python-gadget`; `import` gets `gadgetlib`.
        target: Path = self.root / "two_names"
        self.assertEqual(
            self.include(target, "gadgetlib", distribution="python-gadget"),
            "gadgetlib 4.5.6")
        self.assertTrue((target / "gadgetlib.py").is_file())

    def test_one_name_is_not_enough(self) -> None:
        """Asking by import name alone fails when the names differ."""
        # This is why `distribution` exists rather than being inferred.
        target: Path = self.root / "one_name"
        self.assertIn("could not fetch 'gadgetlib'",
                      self.include(target, "gadgetlib"))

    def test_contains_reports_what_is_cached(self) -> None:
        """`contains` is False before an include and True after."""
        # A single module counts, not only a package directory.
        target: Path = self.root / "contains"
        venv: embedded_venv.EmbeddedVEnv = embedded_venv.EmbeddedVEnv(target)
        self.assertFalse(venv.contains("widget"))
        self.include(target, "widget")
        self.assertTrue(venv.contains("widget"))


def main() -> None:
    """Run the `embedded_venv` test suite.

    This is the entry point used when the file is executed directly.
    It hands control to `unittest`, which discovers the test methods
    of `EmbeddedVEnvTest` and reports on them.
    """
    # unittest reads sys.argv itself and exits when it is done.
    unittest.main()


if __name__ == "__main__":
    main()
