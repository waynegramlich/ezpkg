# `EZPkg`: Easy Python Packages

`EZPkg` (pronounced "easy package") grew out of the desire to send a simple
one-file Python program to a friend.  When said friend tried to run it,
a few packages were missing, so the friend had to create a virtual environment
and install them.  It worked, but it was annoying.  So the question became
"Could this be made really easy for the recipient?"  Thus was born `EZPkg`,
which lets a single-file Python program to download its missing packages all
by itself.

To get started with `EZPkg`, you paste a modest bootstrap at the front of
your program and go.  After that, `EZPkg` fetches your packages over the
net on demand, without a virtual environment or the needing administrative
privileges to install packages.  Once everything is working with `EZPkg`,
then either email the single `.py` file to a friend or let `EZPkg` package it
up in either `zipapp` or `uv` format.  Done!

<!--Claude: Put a table of contents for the `##` headings here. -->

## Quick Start

To get started please take the program below and paste into a file named
`quick_start.py` on your computer.  The bulk of this program is the `EZPkg`
bootstrap that start at Part 3.  This is the "magic" that skips the hassle
of virtual environments.

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

# All other needed imports are added after the EZPkg bootstrap.

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
* Linux/macOS: `python3 --version`

The `quick_start.py` program is run as follows:
* Windows: `python quick_start.py`
* Linux/macOS: `python3 quick_start.py`

The first time the `quick_start.py` runs, it outputs following: 

```
The author of `quick_start.py` has selected some software packages from the
internet.  If you agree, they are retained in `~/.ezpkg`.  If you do not trust
the author, answer `n` and `quick_start.py` will not be run.

Retain `~/.ezpkg` and run `quick_start.py`?
[y=>Yes|n=>No|?=>Explain]:
```

The three options are:
* `y=>Yes`:
  This ensures the downloaded packages are retained prior to execution.
* `n=>No`:
  This ensures that newly downloaded packages are not retained and the program
  terminates immediately thereafter.
* `?=Explain`:
  This lists the packages in question and repeats the question.

The next time the program is executed, you will not be nagged again.

There are basically 3 things that can go wrong:
* **No Network**:
  Without a network connect or previously downloaded packages, the program
  will terminate due missing packages.  Note that the network is only needed
  to do the initial package downloading.  After that they are cached in the
  `.ezpkg` directory and no further network access is needed.
* **No Version Available**:
  Packages have to be compiled for a specific computer instruction set.
  If the appropriate version is not available, the program can not run.
* **PIP Failure**:
  PIP is a recursive acronym that stands for "PIP Installs Packages".
  It is the fundamental tool used to fetch Python packages.  When this program
  fails, there the error from PIP is printed out verbatim and exits.

<!--Claude: What is last_failure.txt? -->
Talk about last_failure.txt`:

If you want remove the `.ezpkg` directory and its contents, do the following:
* Windows: `python $HOME\.ezpkg\remove.py`
* Linux/macOS: `python3 $HOME/.ezpkg/remove.py`

One final note.  If you run `quick_start.py` again, the `.ezpkg` directory
will return.

## Enabling `EZPkg` for a Program

The easiest way to enable `EZPkg` in your program is to copy and paste code
from `quick_start.py`:

1. Take Parts 1, 2, and 3 from `quick_start.py` immediately paste at the
   front of the program, immediately after the `#!/usr/bin/env...` line,
   if it is present.

2. Create an initial empty `EZPkg` `.toml` configuration program.
   Replace `PROG_NAME` with your actual program name:
   * Windows: `ni PROG_NAME.py`
   * Linux/macOS: `touch PROG_NAME.py`

3. Execute your program the first time.  In most cases, your program will
   simply work the first time.  Even if the program fails, an empty
   `PROG_NAME.toml` file is created and populated with options.

The created `.py.toml` file contains options that can be edited to modify
your `EZPkg` program behavior.

### What are packages and where do they come from?

A package is a Python module that can be downloaded from the internet.
The most common place to fetch packages from is the
[PYthon Package Index](https://pypi.org), which is where the Python community
submits freely accessible packages.

One thing about packages is that they get updated and improved over time.
Thus, each improved package has a new version number.  Version numbers are
important because some package versions are incompatible with others.

The good news is that `EZPkg` scans your program for all `import` statements
and does its best attempt to populate the `dependencies=[...]` portion of the
metadata so you don't have to deal with all this hassle!  This data is needed
if you want to package your program up to be compatible with `uv` (see further
below.) 

If you want a mountain of additional information, please see:
* [Python Package Index](https://pypi.org/):
  The most common place to store freely accessible Python packages.
* [Inline script metadata](
  https://packaging.python.org/en/latest/specifications/inline-script-metadata/#inline-script-metadata):
  The Python standard in-line configuration information.
* [TOML](https://toml.io/en/) format:
  This is the syntax used for the inline script metadata.
* [Dependency specifiers](
  https://packaging.python.org/en/latest/specifications/dependency-specifiers/):

In short, the metadata is encoded in TOML format, where each TOML line is
preceded by a `# `.  The `dependencies=[...]` section is the place where
package version dependency specifiers are recorded.


<!--Claude: Please attempt to write a summary of the EZPkg TOML commands in
one section below.  Remove from `### Verbosity` up to, but not including, `## Realising a Program` -->

### Verbosity

<!-- none, low, medium, high, with what each shows (ux19, ux21). -->

### Frozen Versions and Upgrading

<!-- The exclude-newer date and [tool.ezpkg] approved checksums; delete the date line to upgrade; a package newer than the date (ux22). -->


### Choosing Versions

See [PEP 508](https://peps.python.org/pep-0508/) to see how version numbers
are generally selected.

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

<!-- Cluade: Most of this is done previously.  Indicate what you think is missing here:

One bullet per stage: pip.whl, ezpkg, the versioned cache, approvals, cull. -->

## Conclusion

<!-- Claude: Fetch the previous conclusion.  It was pretty reasonable. We'll
work form there. -->
