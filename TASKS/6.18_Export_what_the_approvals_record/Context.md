# LLM Agent Context Log

As of 2026-10-10: Wayne saw that a freeze (`README.md` Author Package
Management) and the Alternatives section need the same data.  After
`ALT_VENV_APPROVE=write`, `AltVEnv` knows every wheel's name, version,
tags and SHA-256 (`approve()`), and has the wheels in the cache: in
effect a lock file.  Exports are views of it.  Agreed design points:
* One variable with a format, e.g. `ALT_VENV_EXPORT=zipapp:prog.pyz`,
  `=pylock`, `=pins`, rather than a variable per target (Wayne first
  wrote `ALT_VENV_ZAPP`; "zapp" is taken to mean `zipapp`, unconfirmed).
* `install()` writes the export and exits before Part 5 runs, so
  building an export never runs the program itself.
* An export requires the approvals to verify first, so only approved
  wheels are packaged.
* Order: skip importable, pins, `zipapp`, `pylock.toml` (below).
`T.rd` is suspended until these exist; the README describes only what
the code does.

The steps, one task (Wayne collapsed the 6.18.1-4 children on
2026-10-10):
1. **Skip packages that are already importable.**  This reverses
   `I.apiia`, which Wayne rejected on 2026-10-01 because an extra
   download did not matter to him.  The reason now is different:
   inside a `zipapp` the packages are already on `sys.path` and may
   have no network, and under `uv run` the same packages are otherwise
   downloaded twice.  `I.apiia`'s Summary measured a leading
   `try: import` at 0.10 s against 1.42 s to install.
   **Bootstrap half done 2026-10-10:** `nopip4` ships (35 pasted
   lines), tries `import alt_venv` first, and is in `quick_start.py`,
   `QUICK_START`, README Part 3 and `BOOTSTRAPS`.  Test harness runs
   cases with `python -P`;
   `test_the_shipping_case_uses_an_importable_alt_venv` covers it.
   **Package half done 2026-10-10:** `satisfied()` in `alt_venv.py`
   checks the installed version against plain-release specifiers
   (`== != >= <= > < ~=`) and answers `False` when unsure; `provide()`
   skips fetching only when *every* requirement is satisfied (all or
   nothing, so `pip` still resolves the set together) and no `argv` was
   given.  Wayne chose the version check over "importable is enough".
   Still to do: measuring `nopip4`'s cold/warm/size row in
   `bootstrap.py` (now `--`).
2. **Pins for Part 1.**  The freeze from the note at
   `README.md:252-261`: `==` pins for every wheel, including those that
   come along, derived from the wheel names in `prog.altvenv`.
   Possibly also a `requirements.txt` with `--hash=sha256:` lines,
   which both `pip` and `uv pip install -r` accept.  Catch: approvals
   are keyed by wheel file name, so a compiled package is
   platform-specific.
   **Done 2026-10-10:** `ALT_VENV_EXPORT=pins` (no-argument `install`
   only) runs `provide()`, then `AltVEnv.export("pins")` prints
   `# dependencies = [ ... ]` with every approved wheel pinned
   (`AltVEnv.pins()`, from the wheel names in `prog.altvenv`), then
   `sys.exit(0)` before Part 5.  Refuses with no approvals file, and
   with two versions of one distribution.  One run does both:
   `ALT_VENV_APPROVE=write ALT_VENV_EXPORT=pins python3 prog.py`.  The
   `requirements.txt --hash` form was not done.
3. **A `zipapp` export.**  **Done 2026-10-10, pure Python only:**
   `ALT_VENV_EXPORT=zipapp[:PATH]` → `build_zipapp()`.  At Wayne's
   request the archive leaves `alt_venv` out: `strip_bootstrap()`
   replaces the pasted bootstrap in `__main__.py` with `pass`, so the
   `.pyz` never runs `alt_venv` and writes nothing to `~`.  A program
   with no bootstrap is refused.  Verified with real PyPI packages
   (cowsay, humanize, pyfiglet, python-slugify, tabulate, termcolor,
   text-unidecode) from an empty HOME with a dead index.  Found:
   `prettytable` needs `wcwidth` 0.9.2, now a compiled abi3 wheel, so
   it cannot be zipped yet.  `find_bootstrap` matches any `try`
   naming `alt_venv` and `import_module`, first in source order.
   Original notes:  Pure-Python wheels unpack straight into the
   `.pyz`.  Compiled ones cannot be imported from a zip; the `.pyz`
   could carry those wheels and unpack them into `~/.alt_venv` on first
   run, which is what the bootstrap already does, but offline.  The
   result is per-platform.  Needs step 1.
4. **A `pylock.toml` export for `uv`.**  Target PEP 751 `pylock.toml`,
   the standard lock file, not `uv.lock`, which is `uv`'s own and
   changes at its whim.  `pylock.toml` wants each wheel's download URL,
   which `AltVEnv` does not record today: capture it at download or ask
   PyPI.  Cheaper fallback: write the pins into the `# /// script`
   block, which `uv run` reads.
   **Done 2026-10-10, by having `uv` write the locks:**
   `ALT_VENV_EXPORT=uv[:PATH]` → `build_uv()` writes three files beside
   the program (Wayne: "3 files is fine"; no subdirectory):
   `prog-uv.py` (Part 1 pinned by `pin_dependencies()`, plus
   `[tool.uv] no-build = true` unless the block has a `[tool.uv]`;
   bootstrap stripped), then runs `uv lock --script` → `prog-uv.py.lock`
   and `uv export --format pylock.toml` → `pylock.prog-uv.toml`.
   `uv` supplies the download URLs and every platform's wheels, so
   compiled packages are fine here.  `lock_mismatches()` checks each
   approved wheel is in the lock with the same SHA-256 (missing or
   hashless is refused).  `PIP_INDEX_URL` is passed on as
   `UV_DEFAULT_INDEX`.  `find_uv()` looks on `PATH`, then
   `~/.local/bin`; without `uv` the script is still written and the two
   commands are printed.  The test index now gives `#sha256=` links, as
   PyPI does.  Verified with the 7-package demo: `uv run demo-uv.py`
   from an empty HOME loads all 7 from `uv`'s environment and creates
   no `~/.alt_venv`.  `no-build` still lets a lock list an sdist; it
   only stops `uv` building one.
