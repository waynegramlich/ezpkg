#!/usr/bin/env python3
"""Test framework for `embedded_venv.py`.

This module is the test half of Experiment 2.  The experiment is a
pipeline rather than a set of alternatives -- publish a package to a
local index, fetch it with the bootstrap stub, and import it -- so
`EmbeddedVEnvTest` is shaped around building and discarding that index
rather than around a table of measurements.

The index is a [PEP 503](https://peps.python.org/pep-0503/) directory
tree rather than a running web server, which `pip --index-url` accepts
directly.  Nothing has to be started or stopped.  Testing against a
real web server is deferred.

This file is a placeholder.  `EmbeddedVEnvTest` is deliberately empty
until there is something in `EmbeddedVEnv` worth testing.

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

import pathlib
import shutil
import tempfile
import unittest

import embedded_venv


class EmbeddedVEnvTest(unittest.TestCase):
    """Build, exercise and discard the Experiment 2 pipeline.

    The suite is nearly empty until there is something in
    `EmbeddedVEnv` worth testing.  What it eventually holds is the
    tests that lay out a PEP 503 directory tree, publish a package
    into it, point the bootstrap stub at it through `PIP_INDEX_URL`,
    and check what comes back -- together with the failure cases that
    matter, such as an index that does not contain the requested
    package.

    The index directory is created once for the whole class and
    removed afterwards, because building it is the expensive part and
    no test needs a private copy.

    Attributes:
    * `index` (`pathlib.Path`):
      The root of the PEP 503 directory tree that stands in for a
      package server.  Empty for now.

    Constructor:
    * `EmbeddedVEnvTest()`, by `unittest` rather than by hand.
    """

    index: pathlib.Path

    @classmethod
    def setUpClass(cls) -> None:
        """Create the temporary PEP 503 index directory."""
        cls.index = pathlib.Path(tempfile.mkdtemp(prefix="embedded_venv-"))

    @classmethod
    def tearDownClass(cls) -> None:
        """Remove the temporary PEP 503 index directory."""
        shutil.rmtree(cls.index, ignore_errors=True)

    def test_index_exists(self) -> None:
        """The index directory is created before the tests run."""
        self.assertTrue(self.index.is_dir())

    def test_embedded_venv_constructs(self) -> None:
        """`EmbeddedVEnv` can be imported and constructed."""
        self.assertIsInstance(embedded_venv.EmbeddedVEnv(),
                              embedded_venv.EmbeddedVEnv)


def main() -> None:
    """Run the `embedded_venv` test suite.

    This is the entry point used when the file is executed directly.
    It hands control to `unittest`, which discovers the test methods
    of `EmbeddedVEnvTest` and reports on them.
    """
    unittest.main()


if __name__ == "__main__":
    main()
