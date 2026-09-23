#!/usr/bin/env python3
"""Test framework for `embeddedenv.py`.

This module is the test half of Experiment 2.  The experiment is a
pipeline rather than a set of alternatives -- publish a package to a
local index, fetch it with the bootstrap stub, and import it -- so
`EmbeddedEnvTest` is shaped around building and discarding that index
rather than around a table of measurements.

The index is a [PEP 503](https://peps.python.org/pep-0503/) directory
tree rather than a running web server, which `pip --index-url` accepts
directly.  Nothing has to be started or stopped.  Testing against a
real web server is deferred.

This file is a placeholder.  `EmbeddedEnvTest` is deliberately empty
until there is something in `EmbeddedEnv` worth testing.

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


class EmbeddedEnvTest:
    """Build, exercise and discard the Experiment 2 pipeline.

    The class is empty until there is something in `EmbeddedEnv` worth
    testing.  What it eventually holds is the fixtures that lay out a
    PEP 503 directory tree, publish a package into it, point the
    bootstrap stub at it through `PIP_INDEX_URL`, and remove it again
    -- together with the failure cases that matter, such as an index
    that does not contain the requested package.

    Attributes:
    * None yet.

    Constructor:
    * `EmbeddedEnvTest()`
    """


def main() -> None:
    """Run the `embeddedenv` test suite.

    This is the entry point used when the file is executed directly.
    For now it only instantiates `EmbeddedEnvTest`, which is enough to
    prove that the module imports and that the class can be
    constructed.
    """
    EmbeddedEnvTest()


if __name__ == "__main__":
    main()
