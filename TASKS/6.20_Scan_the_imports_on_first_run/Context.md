# LLM Agent Context Log

## 2026-10-11: Proposal agreed in outline with Wayne

* Grew out of `T.rd` and `T.cibe`: Python stops at the first missing
  import, so the author learns of them one run at a time, and a package
  their own Python happens to have is never reported until export.
* Reverses one `T.cibe` decision ("nothing checked while developing"),
  at Wayne's suggestion: the `check_imports` scan also runs during
  ordinary runs, but only when something it depends on has changed.
* Outline: warn only (stderr, then carry on; exports still refuse);
  run at the end of `install()`, after the declared packages arrive, so
  that they are findable; remember in `~/.alt_venv` a fingerprint of
  the program's imports, `dependencies` and approvals, and skip the
  scan while it is unchanged.  Recipients scan on their first run too.
* Cost on Wayne's machine: `packages_distributions()` 167 ms (385
  modules), `ast.parse` of `alt_venv.py` 21 ms, hence remembering.
* Pairs with the bootstrap-first recommendation parked in an
  `<!-- Issue: -->` comment under "Enabling" in `README.md`.

## 2026-10-11: What reading the code uncovered

* Hook point: the no-argument branch of `install()`, after `provide()`
  and only when `ALT_VENV_EXPORT` is unset (an export already checks,
  and refuses).  The explicit `install([...])` form is not scanned.
* `check_imports` both finds and raises; split it so that the finding
  (a list of problems) serves a warning run and a refusing export.
* `packages_distributions()` (the 167 ms) is needed only for an import
  that is not standard library, `alt_venv` or local; call it lazily, so
  a program with no third-party imports costs almost nothing.
* Fingerprint choice: the import names (an `ast.parse` every run, a few
  ms for a normal program; moving code does not rescan) or the file's
  bytes (free, but every edit rescans, so every development run).
* Precedent: `requests/` already remembers "asked and answered" as one
  small file per request, and `cull`/`stale` age it out.  A scan record
  needs the same treatment (Step 6.11 garbage collection), and the
  cache README in `AltVEnv.__init__`'s docstring must list it.
* Open for Wayne: remember a scan that found problems (warn once per
  change), or only a clean one (warn every run until fixed)?

## 2026-10-11 end of session

* The README now teaches the bootstrap-first rule (all imports after
  the bootstrap), so this scan runs before any of the program's own
  imports and can report every problem before Python stops at the
  first `ModuleNotFoundError`.
* Still open for Wayne: fingerprint the import names (Claude's
  recommendation) or the file's bytes; remember a scan that found
  problems (Claude's recommendation: yes, warn once per change) or
  only a clean one.
* `T.fipab` (imports above the bootstrap) is a natural second check in
  the same scan and the same export check.

## 2026-10-12

* No change; still waiting on Wayne's two decisions above.  Note that
  `check_imports` now runs at export for `zipapp` and `uv` only (`pins`
  was removed), and the `.pyz` checks `requires-python` itself.
