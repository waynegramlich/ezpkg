# History of `I.mlmfpn` A missing local module fetches a PyPI namesake

Moved from `Context.md` on 2026-10-26, after the 0.0.5 release.

## 2026-10-25

Reported by another Opus 5.5 instance using `ezpkg`: in a scratch copy
of a program without its local `scplot.py`, `ezpkg` fetched PyPI's
unrelated `scplot` 0.0.16 ("Single cell plotting").  Wayne: priority
1; gather data first, then decide.  His first thought: prefer a local
file to PyPI.

How it works now (developer mode, a `prog.py.toml`): `exempt`
(`ezpkg.py`, near line 5897) skips the standard library, `ezpkg`, and
a `MODULE.py` or `MODULE/` beside the program; `find_spec` skips what
is already importable.  Anything else with no metadata and no
`MODULE_PACKAGES` entry is guessed to be the package of the same name
(`discrepancy`, near line 5319; `add_missing`, near 8274), and `prove`
only checks that its wheel holds the module.  Then it is added,
fetched and imported, with no question.  `main_path` resolves
symlinks, as `sys.path[0]` does, so a symlinked script is not a trap.

Probes in `ezpkg_test.py` (`InstallTest`), all passing, so they record
today's behaviour:
* `test_a_missing_local_module_fetches_its_namesake`: no
  `sprocket.py`, so the index's `sprocket` is added, fetched and run.
* `test_a_local_module_beats_its_namesake`: with `sprocket.py` beside
  the program, nothing is added or fetched and the local one runs.
  A local file already wins when it is there.
* `test_a_local_module_on_an_added_path`: a program that puts its own
  `lib/` on `sys.path` (after the bootstrap, so `ezpkg` cannot see
  it): the namesake is added and fetched, though the local one runs.
  So a release would carry the stranger's package to end users.

Not yet tried: `add_missing` (a module loaded without an `import`
statement, such as `importlib.import_module`), which guesses the same
way.

## 2026-10-25, more data (Wayne: "collect as much as you can")

Probes (throwaway, now deleted; the three kept tests are above):
* A. `add_missing` (a name computed at run time, `import_module('sprock'
  + 'et')`): the same hole.  First run: "`prog.py` needed `sprocket`,
  so `ezpkg` added `sprocket`... run `prog.py` again"; second run
  fetches and runs the namesake.
* B. A literal `import_module('sprocket')` is optional: no guess,
  Python's traceback.
* C. The `lib/` case, released as `email`: the end user's Part 1 gets
  `"sprocket>=2.0.0,<3"` and its checksum, so every end user fetches
  the stranger's package (the end user is shown its name and summary
  in the "now retained" list).
* D. A local `sprocket.py` beside the author's program: the `email`
  release leaves it out without a word, and the friend gets a
  `ModuleNotFoundError` traceback.  A separate gap.
* E. An end user's program never guesses: an import Part 1 lacks is
  Python's traceback.  End users are safe.

Surveys (scripts in the session scratchpad, not kept):
* This machine's installed packages: 99 of 160 top-level modules have
  their distribution's name.
* pipreqs' mapping (1,078 module names whose package differs): 496
  have no PyPI namesake, 8 are aliases of the real package, 289 are a
  different project with source only (which `prove` rejects), and 285
  are a different project with a wheel.  Of a sample of 58 of those,
  37 hold the module, so `prove` passes them; some are only renamed
  projects (`msgpack`, `bcrypt`, `docker`), others are real traps:
  `cups` (not `pycups`), `github` (not `PyGithub`), `xdg` (not
  `pyxdg`); `jwt` and `serial` are in `MODULE_PACKAGES` already.
* Wayne's own projects: 212 local module names imported by a sibling
  script; 36 are taken on PyPI, 17 with a wheel, and 14 of those hold
  the module.  Three are the same project (`ezpkg`, `kicost`,
  `kipart`); the 10 strangers that would be fetched if the local file
  were missing are `auth`, `config`, `femtools`, `folders`,
  `generate_licenses`, `involute`, `node`, `package_list`, `scplot`,
  `template`.  `scplot` is the reporter's.

Elsewhere:
* pipreqs had the same hole, CVE-2023-31543 (CVSS 9.8); its fix
  resolves locally first and warns when it guesses from PyPI.
* marimo guesses from the module name too, but asks before installing.
* Pyodide's `loadPackagesFromImports` fetches only from its own curated
  list, never PyPI.
* PEP 794 (accepted 2025-09-05, metadata 2.5) adds `Import-Name`; it
  would confirm a wheel provides a module (as `prove` does), but not
  that it is the one meant, so it does not help here.
* LLM "slopsquatting" (Spracklen et al., USENIX Security 2025): about
  20% of generated code samples named a package that did not exist,
  43% of those repeatably; programs written by AI make name-only
  guesses more dangerous.

Cost of asking: the developer's everyday new imports (`cowsay`,
`tabulate`, `humanize` in `ux/drive.py`) are all name-only guesses, so
any change to them changes the `ux` steps 2.x and about 5 tests.

## 2026-10-25, Wayne's decisions and what was built

Wayne: #1 ask, listing every option (usually 2) for the developer to
choose; #2 a `local` setting; #3 a release fails at build time when the
program imports its own modules; #4 (`cups`, `github`, `xdg` in
`MODULE_PACKAGES`) was explained, not decided: Claude suggested folding
it into #1, since an ambiguous name like `xdg` (two real packages)
wants both as options.

Built (not yet released):
* #2: `Settings.local`, checked by `read_settings` (identifiers only);
  `EZPkg.local_module` says where a program's own module comes from
  (beside it, or "listed in `prog.py.toml` line N, ..."); `exempt`
  uses it, so `local` modules are never guessed.  Template entry under
  "rarely needed", in README and `SETTINGS_TEMPLATE`.
* #3: `EZPkg.local_imports`, called by `build_release` after
  `check_imports`: every required import of the program's own (beside
  or `local`) stops the release, all named in one message; the program
  still runs, and nothing is recorded.  Every form is refused (a
  `zipapp` could carry them one day; it does not today).
* #1: `EZPkg.choose` asks a developer at the terminal about a guess from
  a module's name alone (not in `MODULE_PACKAGES`, not installed,
  `prove` passed): "`prog.py` line 12 imports `sprocket`, which is
  neither beside `prog.py` nor installed.  Which is it?  1. PyPI's
  sprocket 2.0.0: A versioned throwaway.  2. A module of `prog.py`'s
  own  [1=>PyPI|2=>Own]:".  No default; a typo asks again (`ATTEMPTS`); no answer
  or no terminal (or `CI`) fetches nothing and `unchosen` says how to
  choose by hand (`dependencies`, or `local`/a file beside).  A `1` is
  kept in the stash's `chosen`, so the module is never asked again.
  `prove` keeps each wheel's name, version and summary (`proved`).
  Both `reconcile` and `add_missing` ask.  The `ezpkg` file never
  writes `prog.py.toml`, so `2` cannot add to `local` itself.
* Tests: `test_a_name_only_guess_is_not_fetched_unasked`,
  `..._is_chosen_on_the_terminal`, `test_a_module_loaded_at_run_time_
  is_chosen_too`, `test_local_names_a_module_on_an_added_path`,
  `test_a_release_refuses_the_programs_own_modules`, plus `local` in
  the settings table.  Tests that add `sprocket` for other reasons use
  `chose` / `synced_program(chosen=...)`, which writes the stash as an
  earlier `1` would.
* `ux/drive.py`: steps 2.1 (`cowsay`!), 2.2 (`tabulate`) and 2.7
  (`humanize`) answer `1`.  A developer's very first run of the Quick
  Start now asks about `cowsay`.
* README: the template entry is in place (the test needs it); the prose
  changes are proposals in `<!-- Proposed by Claude for I.mlmfpn -->`
  comments for Wayne (Enabling, Releasing, Security).

## 2026-10-25, end of session: where things stand

Built and verified, not committed: quick suite 349 OK (4 skipped),
`ux/drive.py` 29/29, CI-pinned `ruff` and `mypy` clean.  Checkpointed
in `hg`.  The report was given to Wayne; he has not answered yet.

Waiting on Wayne:
1. README proposals in `<!-- Proposed by Claude for I.mlmfpn -->`
   comments (Enabling, Releasing, Security; recompute line numbers).
2. #4: let a `MODULE_PACKAGES` entry name several candidates (e.g.
   `xdg`: `pyxdg` or PyPI's `xdg`), offered as options in the same
   question.  Not built.
3. The question's wording (his to edit; keep the `[1=>PyPI|2=>Own]:`
   form, which `ux/drive.py`'s `QUESTION` regex needs).
4. Whether to change `R.vcr` so Claude may run `git commit` (asked,
   unanswered).
5. Whether to draft a reply to the reporter.

Next, after Wayne commits: write `Summary.md` and close `I.mlmfpn`
just before the commit; release 0.0.5 by `T.ffrp`'s procedure (pypi
at Wayne's go).  The committed `ux13`, `ux14`, `ux19` transcripts are
stale (they now show the question); fresh ones are in the session
scratchpad `ux.kLYF/`, for Wayne's batch read later.

## 2026-10-26

Wayne: a PyPI name clash needs nothing beyond the development
question, so the proposed first-sight notice for a module beside the
program is dropped.  Carrying the program's own modules in a `zipapp`
(and `local_imports` refusing only `email` and `uv`) moved to
`T.zcpom~9`, after this issue's 0.0.5 release.

#4 built (Wayne: "fix this now"): `MODULE_CHOICES` (`cups`: `pycups`
or `cups`; `github`: `PyGithub` or `github`; `xdg`: `pyxdg` or `xdg`)
and `module_packages`.  `prove_each` proves every candidate;
`choose` takes the proved list and offers each by number, with the
brackets naming them (`[1=>pyxdg|2=>xdg|3=>Own]:`; one package keeps
`[1=>PyPI|2=>Own]:`), and a "Not offered:" line for each refused one
(PyPI's `pycups` is source only, so `import cups` offers only the
stranger's `cups`, with that line).  It returns the package chosen,
`OWN`, or empty; `Discrepancy.replace` puts a choice in the guess's
place.  `reconcile` and `add_missing` both use it.  Tests are
in-process (`test_several_packages_are_offered_by_name`,
`test_reconcile_adds_the_package_chosen`), since Ubuntu's Python has
its own `xdg` and `cups`, so a child never asks.

Shadowing (Wayne, 2026-10-26: "test and fix this"): a package brings a
module (`needy` brings `widget`) and the developer then writes a
`widget.py`.  Probe: the cache comes first on `sys.path`, so `import
widget` got PyPI's and `widget.py` was silently never used.  Fix:
`EZPkg.refuse_shadowing`, after `scan_imports` in a developer's run,
stops when an import of the program's own module (`local_module`:
beside it or in `local`) is also found in a cached tree on `sys.path`,
naming each with its line and PyPI's name and version, and asking for
another name.  Tests `test_a_local_module_shadowed_by_a_package_stops`
and `test_a_local_listed_module_shadowed_by_a_package_stops`.  Not
covered: imports inside the program's own modules (`T.zcpom~9`'s
recursive scan should run the same check).

Question reworded (Wayne, 2026-10-26): "`prog.py` line 43 imports
`cowsay`.  Where should it come from?", options "1. PyPI's ...", last
"N. A local `cowsay.py`, a file that has not been created yet", and
brackets ending `N=>Create Locally`.  That answer creates the empty
file (no second question), and `unchosen` says "Created an empty
`cowsay.py` beside `prog.py`; fill it in", with the `local` way for a
module on an added path.  "Not offered:" became, for a source-only
package only (`UNCOMPILED`, `prove_each`'s third list): "(PyPI's pycups
also provides `cups`, but it must be compiled before it can be used,
and EZPkg does not compile packages.)"; other refused candidates are
left out silently.  `ux/drive.py`'s `WHICH` follows the new wording.
