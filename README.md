# `EZPkg`: Easy Python Packages

`EZPkg` (pronounced "easy package") grew out of the desire to send a simple
one-file Python program to a friend.  When said friend tried to run it,
a few packages were missing, so my friend had to create a virtual environment
and install them.  It worked, but it was annoying.  So the question became
"Could this be made really easy for the recipient?"  Thus was born `EZPkg`,
which lets a single-file Python program download its missing packages all
by itself.

To get started with `EZPkg`, you paste a modest bootstrap at the front of
your program and go.  After that, `EZPkg` fetches your packages over the
net on demand, without a virtual environment or the needing administrative
privileges to install packages.  Once everything is working with `EZPkg`,
then either email the single `.py` file to a friend or let `EZPkg` package it
up in either `zipapp` or `uv` format.  You can remove the bootstrap `try`
block at any time.  If you are not going to use `uv`, the standard PEP 723
metadata at the font should probably be retained, since `uv run` needs it.
Also note that once the require packages have been downloaded, a network
connection is no longer needed.

## Quick Start

<!-- Save, run, the one question, the cow.  Note that it works only once ezpkg is on pypi.org. -->

To get started please take the program below and paste into a file named
`quick_start.py`.

```python
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
    s = "find home"; t = pathlib.Path.home()/".ezpkg"; w = t/"pip.whl"
    m = n = None
    def g(u):  # Fetch u, with curl if this Python has no certificates.
        try: return req.urlopen(u, None, 60).read()
        except req.URLError as y: z = y  # As on python.org's macOS Python.
        try: return subprocess.run(["curl", "-fsSL", u],
                                   capture_output=True, check=True).stdout
        except Exception: raise z from None
    try: m = importlib.import_module("ezpkg")  # Already importable?
    except ImportError: pass
    if m is None and not (t/"ezpkg").is_dir():  # Not installed yet.
        s = "choose pip"; v = sys.version_info[1]
        d = json.loads(g("https://pypi.org/pypi/pip/json"))
        e = max((e for f in d["releases"].values() for e in f  # Newest pip ...
                 if e["url"][-4:] == ".whl" and not e["yanked"]
                 and (q := e["requires_python"] or "")[:4] == ">=3."
                 and "," not in q and int(q.split(".")[1]) <= v),
                key=lambda e: e["upload_time"])  # ... whose floor we meet.
        s = "download pip"; r = g(e["url"])
        if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
            raise ValueError(f"{e['filename']} fails its SHA-256 check")
        t.mkdir(parents=True, exist_ok=True); p = t/"pip.part"
        p.write_bytes(r); p.replace(w)  # The rename is atomic.
        s = "install ezpkg"; n = subprocess.run([sys.executable, w/"pip",
            "install", "--no-input", "-t", t, "--disable-pip-version-check",
            "ezpkg"], check=False, capture_output=True, text=True)
        if n.returncode: raise RuntimeError(n.stderr.strip()[-300:])
    if m is None:
        s = "import ezpkg"; sys.path.insert(0, str(t))
        importlib.invalidate_caches(); m = importlib.import_module("ezpkg")
    s = "fetch packages"; m.EZPkg(pip=n).install(bootstrap="nopip7")
except Exception as x:
    raise SystemExit(f"ezpkg: {s} failed: {x!r}")  # Do not edit try block!

# Part 4: Your imports, all after the bootstrap.
import cowsay  # type: ignore[import-not-found]  # For mypy.

# Part 5: The program itself.
cowsay.cow("EZPkg works!")
print(f"The cow above was drawn by cowsay {cowsay.__version__}.")
```

## Running a Program That Uses `EZPkg`

Prior to running, you should verify Python 3.11 or greater is available:
* Windows: `python --version`
* Linux/macOS: `python3 --version
`quick_start.py` is run as follows;:
* Windows: `python quick_start.py`
* Linux/macOS: `python3 quick_start.py`
You can literally email this program to a friend and it will run.
You do not have to install anything else.  It just works.

### The One Question

<!-- The paragraph and `Retain ~/.ezpkg and run prog.py? [y=>Yes|n=>No|?=>Explain]:`; y, n, ?, Enter, Control-C, no answer in 5 minutes; asked once per program, ever (ux01, ux06-ux12). -->

### Later Runs and New Versions

<!-- Silent from then on; a newer prog.py from its author fetches what it needs silently; a second program is asked for itself, and n then keeps ~/.ezpkg (ux02-ux04). -->

### When Something Goes Wrong

<!-- The four one-line messages (no network, a version PyPI dropped, no version for this computer, anything else) and last_failure.txt for the author (I.ffspo). -->

### Removing `~/.ezpkg`

<!-- Always safe.  python3 ~/.ezpkg/remove.py; Windows PowerShell py $HOME\.ezpkg\remove.py; cmd.exe py %USERPROFILE%\.ezpkg\remove.py (ux05). -->

## Enabling `EZPkg` for Your Program

<!-- For the developer.  The bootstrap block below is checked by the test suite against quick_start.py; keep it verbatim.  Then the paste-in steps: Part 1, Part 2, never edit the bootstrap, imports after it. -->

```python
#!/usr/bin/env python3
# Part 1: The packages this program needs.
# /// script
# requires-python = ">=3.11"
# dependencies = ["ezpkg>=0.0.1.dev0,<0.1"]
# ///
"""TOP_LEVEL_DOCSTRING"""
# Any `from __future__ import ...` goes here.

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
    s = "find home"; t = pathlib.Path.home()/".ezpkg"; w = t/"pip.whl"
    m = n = None
    def g(u):  # Fetch u, with curl if this Python has no certificates.
        try: return req.urlopen(u, None, 60).read()
        except req.URLError as y: z = y  # As on python.org's macOS Python.
        try: return subprocess.run(["curl", "-fsSL", u],
                                   capture_output=True, check=True).stdout
        except Exception: raise z from None
    try: m = importlib.import_module("ezpkg")  # Already importable?
    except ImportError: pass
    if m is None and not (t/"ezpkg").is_dir():  # Not installed yet.
        s = "choose pip"; v = sys.version_info[1]
        d = json.loads(g("https://pypi.org/pypi/pip/json"))
        e = max((e for f in d["releases"].values() for e in f  # Newest pip ...
                 if e["url"][-4:] == ".whl" and not e["yanked"]
                 and (q := e["requires_python"] or "")[:4] == ">=3."
                 and "," not in q and int(q.split(".")[1]) <= v),
                key=lambda e: e["upload_time"])  # ... whose floor we meet.
        s = "download pip"; r = g(e["url"])
        if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
            raise ValueError(f"{e['filename']} fails its SHA-256 check")
        t.mkdir(parents=True, exist_ok=True); p = t/"pip.part"
        p.write_bytes(r); p.replace(w)  # The rename is atomic.
        s = "install ezpkg"; n = subprocess.run([sys.executable, w/"pip",
            "install", "--no-input", "-t", t, "--disable-pip-version-check",
            "ezpkg"], check=False, capture_output=True, text=True)
        if n.returncode: raise RuntimeError(n.stderr.strip()[-300:])
    if m is None:
        s = "import ezpkg"; sys.path.insert(0, str(t))
        importlib.invalidate_caches(); m = importlib.import_module("ezpkg")
    s = "fetch packages"; m.EZPkg(pip=n).install(bootstrap="nopip7")
except Exception as x:
    raise SystemExit(f"ezpkg: {s} failed: {x!r}")  # Do not edit try block!

# Your imports go here, followed by the rest of your program.
```

### Becoming the Developer: `prog.py.toml`

<!-- touch prog.py.toml; the filled-in template (T.ept edits it); the file is the only thing that decides the mode; a misspelt setting stops the run (ux13, ux20). -->

### Keeping `dependencies` in Sync

<!-- New imports get entries with ranges, removed imports lose them, order follows the imports, marks for entries no import explains, any comment keeps an entry, a misspelt import (ux14-ux18). -->

### Verbosity

<!-- none, low, medium, high, with what each shows (ux19, ux21). -->

### Frozen Versions and Upgrading

<!-- The exclude-newer date and [tool.ezpkg] approved checksums; delete the date line to upgrade; a package newer than the date (ux22). -->

### Choosing Versions

<!-- PEP 508 ranges, ==, extras, markers; the ranges ezpkg writes. -->

## Releasing a Program

<!-- release = "X.Y.Z" and exports; what a release checks and changes; the next release is the next number (ux23). -->

### Emailing the `.py`

<!-- The program alone, frozen by its date and approvals. -->

### Using `zipapp`

<!-- prog-X.Y.Z.pyz: no network, no ~/.ezpkg; pure-Python packages only (ux24, I.htdwcp). -->

### Using `uv`

<!-- prog-X.Y.Z-uv.py and its lock; uv run (ux25). -->

## The Bootstrap

<!-- Never edit it; an edited one is refused, naming the line; a newer one is offered to the developer and replaced at release; ezpkg in Part 1 chooses which ezpkg runs (T.reb, T.eui). -->

## How `EZPkg` Actually Works

<!-- One bullet per stage: pip.whl, ezpkg, the versioned cache, approvals, cull. -->

## Conclusion

<!-- Wayne. -->
