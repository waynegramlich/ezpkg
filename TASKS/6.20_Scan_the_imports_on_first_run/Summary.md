# Summary of `T.siofr` Scan the imports on first run

Ordinary runs now check imports too.  `import_problems` finds what
Part 1 does not cover; `check_imports` refuses an export on it
(`T.cibe`); `scan_imports`, at the end of the no-argument `install()`
when not exporting, prints every problem at once on standard error and
carries on.  Wayne's decisions (2026-10-12): the fingerprint is the
import names, not the file's bytes (plus the program path,
`sys.executable`, Part 1 and the approvals), and every scan is
remembered, so a warning is shown once per change.  Records live in
`~/.alt_venv/scans/<sha256>.json`, are touched on use and age out via
`stale`/`cull`.  `packages_distributions()` is now called lazily.
README "Enabling" steps 3 and 4 describe the warning.  Related:
`T.cibe`, `T.fipab`, `T.rd`.
