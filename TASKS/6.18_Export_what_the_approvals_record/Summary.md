# Summary of `T.ewar` Export what the approvals record

`ALT_VENV_EXPORT` turns a working program into a release instead of
running it, after `check_imports` (`T.cibe`) confirms Part 1 covers
every import.  `zipapp[:PATH]` writes `prog.pyz`: pure-Python approved
packages only (compiled or `.pth` packages are named and refused), the
bootstrap replaced by a check of Part 1's `requires-python`; runs with
no network and no `~/.alt_venv`.  `uv[:PATH]` writes `prog-uv.py`
(Part 1 pinned, `no-build`, no bootstrap, no `exclude-newer`) and
`uv lock --script`'s `prog-uv.py.lock`, checked against the approvals
by SHA-256 (`lock_mismatches`); compiled packages are fine.  The
`pins` form and the `pylock.toml` file were later dropped (Wayne,
2026-10-12): the `exclude-newer` date of `T.srdisb` serves a `.py`
sent alone.  The bootstrap became `nopip4`, which uses an importable
`alt_venv` first; its row in `bootstrap.py` was measured 2026-10-12
with `coverage`, since `alt_venv` is not yet on PyPI.  Both exports
were dogfooded with `quick_start.py` against PyPI and documented in
README "Using `zipapp`" and "Using `uv`" (`T.rd`).  Related:
`T.rafal`, `T.srdisb`, `T.cibe`.
