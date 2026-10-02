#!/usr/bin/env python3
# Part 1: The packages this program needs.
# /// script
# requires-python = ">=3.11"
# dependencies = ["cowsay"]
# ///
"""Try `AltVEnv`: fetch the `cowsay` package on first use, then run."""

# Part 2: The standard library imports that the bootstrap uses.
import hashlib
import importlib
import json
import pathlib
import subprocess
import sys
import urllib.request as req

# Part 3: The bootstrap.  Copy it exactly, and never edit it.
try:
    s = "find home"; t = pathlib.Path.home()/".alt_venv"; w = t/"pip.whl"
    if not (t/"alt_venv").is_dir():  # Not installed yet.
        s = "choose pip"; v = sys.version_info[1]
        d = json.load(req.urlopen("https://pypi.org/pypi/pip/json", None, 30))
        e = max((e for f in d["releases"].values() for e in f  # Newest pip
                 if e["url"][-4:] == ".whl" and not e["yanked"]
                 and (q := e["requires_python"] or "")[:4] == ">=3."
                 and "," not in q and int(q.split(".")[1]) <= v),
                key=lambda e: e["upload_time"])  # whose floor we meet.
        s = "download pip"; r = req.urlopen(e["url"], None, 60).read()
        if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
            raise ValueError(f"{e['filename']} fails its SHA-256 check")
        t.mkdir(parents=True, exist_ok=True); p = t/"pip.part"
        p.write_bytes(r); p.replace(w)  # The rename is atomic.
        s = "install alt_venv"; subprocess.run([
            sys.executable, w/"pip", "install", "--no-input", "-t", t,
            "--disable-pip-version-check", "alt_venv"], check=True)
    s = "import alt_venv"; sys.path.insert(0, str(t))
    importlib.invalidate_caches(); importlib.import_module("alt_venv")
except Exception as x:
    raise SystemExit(f"cannot fetch alt_venv, {s} failed: {x!r}")

# Part 4: Fetch the packages listed in Part 1, then import them.
import alt_venv  # type: ignore[import-not-found]

alt_venv.AltVEnv().install()
import cowsay  # type: ignore[import-not-found]

# Part 5: The program itself.
cowsay.cow("AltVEnv works!")
print(f"cowsay {cowsay.__version__} was loaded from {cowsay.__file__}")
