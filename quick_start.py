#!/usr/bin/env python3
# Part 1: The packages this program needs.
# /// script
# requires-python = ">=3.11"
# dependencies = ["ezpkg>=0.0.1.dev0,<0.1", "cowsay"]
# ///
"""Try `EZPkg`: fetch the `cowsay` package on first use, then run."""

# Part 2: EZPkg required imports are immediately below.
import hashlib
import importlib
import json
import pathlib
import subprocess
import sys
import urllib.request as req

# All other imports are added after the EZPkg bootstrap.

# Part 3: The EZPkg bootstrap.  Never edit it.
try:  # Do not edit try block!  See https://pypi.org/project/ezpkg/
    s = "find ezpkg"; t = pathlib.Path.home()/".ezpkg"; w = t/"ezpkg.whl"
    def g(u):  # Fetch u, with curl if this Python has no certificates.
        try: return req.urlopen(u, None, 60).read()
        except req.URLError as y: z = y  # As on python.org's macOS Python.
        try: return subprocess.run(["curl", "-fsSL", u],
                                   capture_output=True, check=True).stdout
        except Exception: raise z from None
    try: m = None; m = importlib.import_module("ezpkg")  # Already importable?
    except ImportError: pass
    if m is None and not w.is_file():  # Not downloaded yet.
        s = "download ezpkg"; d = g("https://pypi.org/pypi/ezpkg/json")
        e = next(e for e in json.loads(d)["urls"] if e["url"][-4:] == ".whl")
        r = g(e["url"])
        if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
            raise ValueError(f"{e['filename']} fails its SHA-256 check")
        t.mkdir(parents=True, exist_ok=True); p = t/"ezpkg.part"
        p.write_bytes(r); p.replace(w)  # The rename is atomic.
    if m is None:  # Python imports it straight from the wheel.
        s = "import ezpkg"; sys.path.insert(0, str(w))
        m = importlib.import_module("ezpkg")
    s = "fetch packages"; m.EZPkg().install(bootstrap="nopip8")
except Exception as x:
    raise SystemExit(f"ezpkg: {s} failed: {x!r}")  # Do not edit try block!

# Part 4: Your imports, all after the bootstrap.
import cowsay  # type: ignore[import-not-found]  # For mypy.

# Part 5: The program itself.
cowsay.cow("EZPkg works!")
print(f"The cow above was drawn by cowsay {cowsay.__version__}.")
