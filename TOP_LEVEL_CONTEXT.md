# Top Level Context

<!-- --------------------------- 79 characters ---------------------------- -->

`CLAUDE.md` holds only `@` imports; project facts that every session
needs live here instead.

## The Files

* `ezpkg.py`: The `ezpkg` package itself (the `EZPkg` class).
* `quick_start.py`: The Quick Start program, and the authority for the
  bootstrap text.
* `bootstrap.py`: The shipping bootstrap, `2026-10-26`, as the
  function `bootstrap_2026_10_26` (`MECHANISMS` maps the name to it;
  `python3 bootstrap.py 2026-10-26` runs it, for the suite only).  It
  fetches only `ezpkg`'s wheel, keeps it as `~/.ezpkg/ezpkg.whl` and
  imports from it; `EZPkg.own_pip` fetches `pip`.  The older cases
  were deleted on 2026-10-24 (Wayne).  `ux/drive.py` installs a
  wheel of the project's `ezpkg.py` (`PIP_FIND_LINKS`) rather than
  pypi.org's, so it tests the code as it is now.
* `ezpkg_test.py`: The test suite.  Its module docstring is the
  contributor's guide (Wayne, 2026-10-24): "Fixing a Bug or Adding a
  Feature" (the steps before a pull request), then "How To Test
  `EZPkg`" (five layers: lint, the suite against its local server,
  coverage, `ux/drive.py`, GitHub Actions).  Keep it current when a
  test tool or workflow changes; README's Project Information links it.
* `ezpkg_test_all.py [DIR]`: Every local test in one command (about 35
  minutes): `ruff`, `mypy`, the suite under `ezpkg_coverage.py
  --children` with a scratch home holding a fresh `pip.whl`,
  `ux/drive.py --ux-dir DIR/ux`, and `email_check.py build`/`friend`;
  each step logs into `DIR`, then a summary.  Claude runs it in the
  background.
* `ezpkg_coverage.py`: Coverage with the standard library `trace`
  (`trace_hook/` carries it into child processes).
* `README.md`: The user documentation, rewritten by Wayne since
  2026-10-19; Wayne leads it.  `README.md.old` is the README before the
  redesign, from which lost text was restored (2026-10-20).
* `release.py`: Builds the wheel to publish (`./release.py
  testpypi|pypi DIR`), using `release_wheel` from `ezpkg_test.py`.
* `.github/workflows/release.yml`: Publishes it with Trusted
  Publishing, after Wayne approves on GitHub (`T.wrw`).
* `release_check.py`: Runs the Quick Start as a new user against a
  published `ezpkg` (`./release_check.py [--python PY] [--console]
  testpypi|pypi [VERSION]`).  `--console` gives it a real terminal
  (a pseudoterminal, or ConPTY via `pywinpty` on Windows) and answers
  the download prompt.
* `.github/workflows/check.yml`: Runs `release_check.py` on GitHub's
  Linux, Windows, Apple Silicon and Intel macOS runners, Python 3.11
  to 3.15, plus python.org's macOS Python without certificates and a
  `--console` job per system: `gh workflow run check.yml -f
  target=testpypi -f version=V` (25 jobs, about 3 minutes; Claude
  starts it).  `release.yml` also runs it after every upload, for
  the version it built (`T.utpat`).
* `email_check.py build DIR` / `friend DIR OUT` and
  `.github/workflows/email_check.yml`: `email` and `zipapp` releases
  (`T.ee`) built on every runner kind (Linux and Windows x86_64/ARM,
  macOS ARM/Intel, Alpine in Docker), each fetching `uv` itself
  (`EZPKG_UV=fetch`), then Linux's run as a friend's on Windows, macOS
  and Linux (`gh workflow run email_check.yml`, 13 jobs; Claude
  starts it).
* `ux/drive.py [--keep] [--until STEP | --only STEP...] [--ux-dir
  DIR]`: Runs the scripted UX steps (end user 1.1-1.12, developer
  2.1-2.17, whose program is the Quick Start without Part 1) on a
  pseudoterminal in a temporary copy of the Quick
  Start, as a stranger's real first run: a fresh home, the bootstrap
  fetching `pip` from pypi.org and installing a wheel of the project's
  `ezpkg.py` (`PIP_FIND_LINKS`), everything else from real pypi.org.
  Each step declares the program's mode (`end-user`, `developer`, or
  `gone` when `~/.ezpkg` must be removed) and is checked against it.
  Claude runs it (about 7 minutes, in the background).  The transcript,
  with framed steps, is `ux/drive_output.txt` (ignored); each step is
  also written unframed to `ux/uxNN_NAME.txt` (`NN` is the step's
  position, not its number), which Wayne edits into the agreed output
  and commits, so `git diff ux/` after a rerun shows what is left to
  build (`T.abfd`'s `Context.md`).  A rerun overwrites them; while
  Wayne may be editing them, run with `--ux-dir` into the scratchpad
  and copy back.  Each step also leaves `uxNN_prog.py` (as it ran),
  named on the `.txt`'s third line, so Wayne can `diff` the
  transitions; a step fails if `ezpkg` edits `prog.py`.
  `--only 1.4` runs one step from the snapshot the step before left
  in `ux/.snapshots/` (ignored; dropped when the code changes), or
  after running the earlier steps as unrecorded setup.
  A step can set more environment, such as `EZPKG_ANSWER_SECONDS=3`
  for the no-answer step.  The `ux/uxNN_prog*.py` snapshots are excluded from `ruff` and `mypy`.
* `git_hooks/`: `prepare-commit-msg` adds `Assisted-by: Claude
  Code:claude-opus-5-5` to Wayne's commit messages (deletable in the
  editor), and `commit-msg` refuses a message that is only that
  trailer.  On per clone with `git config core.hooksPath git_hooks`.
  Update the trailer when the model changes.

## The Bootstrap Has Three Copies

`quick_start.py` is the authority, and the test suite fails until these
match it:

* The Quick Start copy in `README.md`.  Its "Enabling `EZPkg` for a
  Program" says to copy Part 2, the bootstrap from `# Begin` to `# End`
  (its imports included), from `quick_start.py`, so it has no copy of
  its own (Wayne, 2026-10-22).  A developer writes no Part 1.
* `QUICK_START` in `ezpkg.py`.
* `bootstrap_2026_10_26` in `bootstrap.py` (which spells the package
  name as `PACKAGE` and the index as `JSON_API`; `pasted` renders it).

A changed bootstrap is a new one, comments and spaces included
(`T.reb`: `EZPkg` refuses any bootstrap that is not, line for line once
trimmed, a published one).  It needs a new name, the date it is published
(`DATED`; `nopip3`-`nopip7` were never released and stay only as test
fixtures), its
fingerprint added to the end of `BOOTSTRAPS` in `ezpkg.py`, its name
and the `ezpkg` version first carrying it added to `BOOTSTRAP_FLOORS`,
and the previous text kept whole in `OLD_BOOTSTRAP_TEXTS` (the last
line's comment included; `I.r2birae`).  The Quick Start's Part 1 floor
moves to that version too.  `bootstrap.py`'s copy
spells things as variables, so the suite runs it with
`EZPKG_BOOTSTRAP=unchecked`.

Since 0.0.6 (2026-10-26): a bootstrap dated after every one this
`ezpkg` knows fetches the newest `ezpkg` into `ezpkg.whl` and restarts
(`outgrown`, `I.cernb`); a developer's stash pin older than the
bootstrap's floor or Part 1's entry gives way (`stale_pin`, `fetch`,
`I.dspef`); a bootstrap in an imported module is checked against that
module (`calling_module`, `DECLARED`, `I.mbicamp`).

Part 1 of every released program lists `ezpkg` first (the Quick
Start's is `ezpkg>=0.0.4,<0.1`, the first `ezpkg` that knows
`2026-10-26`), and that
entry chooses which `ezpkg` runs it (`T.eui`).  A release writes Part 1
into its copy when the program has none (`with_script_block`), with a
`requires-python` worked out from the syntax and the packages
(`python_range`), or the setting.

`SETTINGS_TEMPLATE` in `ezpkg.py` is what an empty `prog.py.toml` is
filled with, and `README.md`'s "`prog.py.toml` Settings" shows it
verbatim, from `# Start of PROG_NAME.py.toml:` to `# End of ...` (a
test fails otherwise, or on a line over 79 columns).  Since 2026-10-23
Wayne writes it in the README, for people new to EZPkg, and Claude
copies the block into `SETTINGS_TEMPLATE`.  It names no program:
`PROG_NAME` is the README's word (Wayne, 2026-10-22).  Its keys use
hyphens, as PEP 723 does (Wayne, 2026-10-23).

## The Two Modes (`T.abfd`, 2026-10-19)

A `prog.py.toml` beside `prog.py` makes it its developer's: the
packages kept in step with the imports, and the versions frozen.  The
one question (`I.mlmfpn`, 2026-10-25; reworded 2026-10-26, "Where
should it come from?", its last option `Create Locally` making an empty
`MODULE.py`): an import matched to a PyPI
package by its name alone (not beside the program, not installed, not
in `MODULE_PACKAGES`) is the developer's to choose, from numbered
options (`EZPkg.choose`; a package chosen is kept in the stash's
`chosen`); with no terminal nothing is fetched.  An import that
several real packages provide (`MODULE_CHOICES`, such as `xdg`:
`pyxdg` or `xdg`) offers each one `prove` passes, and says why any
other is not offered (2026-10-26).  `local` in `prog.py.toml` names the
program's own modules that `ezpkg` cannot see, and a release refuses a
program that imports its own modules (`local_imports`).  There is no `auto-dependencies` any more (Wayne,
2026-10-22): `dependencies` in `prog.py.toml` names what the imports
cannot (extras, exact versions), and Part 1's or its entries are never
removed.  A platform-guarded import gets a marker (`import_markers`);
an uncaught `ModuleNotFoundError` adds its package to the stash and
asks for another run (`add_missing`).  Dropped entries are noted in
the stash (`noted`; a guessed name is proved, so not noted), and the
next release lists them, with its own warnings (`warn`), under `warnings` in its
`prog.py.releases` entry; its one "Released" line counts them.  The developer's `prog.py` is never
edited (Wayne, 2026-10-22; the editing code, `EDIT_PROGRAM`, `restart`
and the `@editing` tests were deleted on 2026-10-24, S4.2).  What `ezpkg` works out (entries
for imports Part 1 lacks, `checksums`, `exclude-newer`, `released`)
is the program's stash in its `~/.ezpkg/develop/` record
(`EZPkg.stash`), seeded from Part 1 or the newest `email` build; Part
1's own entries and a hand-written date are read, never changed;
`update-frequency` (`"never"`, the default, `"monthly"`, `"weekly"`
or `"daily"`) drops the stash's date once it is older than that, so
that run takes the newest versions and dates them afresh, and so
does a new import whose package is newer than the stash's date
(`too_new`, with a notice; a date written into Part 1 stops the run
instead; Wayne, 2026-10-24); a release merges the stash into a staged copy (`staged`) that its forms
are built from.  Releases are off until `release` in
`prog.py.toml` names a form and `version` names a version (the
template leaves `release = [` open with each form's line commented
out, and `version` commented out; a `release` list without a
`version` is refused, as is any key set twice, naming both lines).
Then a developer's run where `version` differs from the newest entry
of `prog.py.releases` builds that release (the forms `release` names,
in `EXPORT_FORMS` order:
`email`, `zipapp`, `uv`) beside `prog.py` as `prog-X.Y.Z.py`,
`.pyz`, `-uv.py` and its lock (`release_files`), removes the last
release's files, appends a `[[release]]` entry (version, date, commit,
`exclude-newer`, `dependencies`; `release_entry`) to
`prog.py.releases`, and then runs the program (Wayne, 2026-10-22: one
file for version control, no folder).  A lost stash is seeded from the
newest entry.  `cull` uses one number, 30 days (`CULL_DAYS`), except
for a program's latest request, which gets that program's own
`purge-unused-after` (`"month"`, `"week"` or `"day"`; shorter than 30
days too, Wayne, 2026-10-23), and keeps a `develop/` record while its
program exists; `~/.ezpkg/list.py` lists what the cache holds.  An entry nothing imports goes once the latest recorded run
declared it and none of the last 10 loaded it (`unused_lately`,
`note_loaded`); a comment keeps it.  Without one, `prog.py` is an end user's: one question per
program, ever, and the program is never edited.  `prog.ezpkg`,
`EZPKG_APPROVE`, `EZPKG_EXPORT` and `EZPKG_BOOTSTRAP=check` are gone.

## Testing and Linting

* Everything local at once: `./ezpkg_test_all.py DIR` (see above).
* Quick tests, during development (about 6 minutes): `./ezpkg_test.py`
  (`EZPKG_TEST=FAST`, the default), which runs everything, the
  bootstrap `2026-10-26` in `bootstrap.py` included.  The quick suite
  must run the latest bootstrap (Wayne, 2026-10-23); `EZPKG_TEST=NONE`
  skips it and is only the coverage tool's baseline.  A single class
  or method can be named after it.
* Coverage: `./ezpkg_coverage.py --children DIR` (about 23 minutes,
  in the background, scratch `HOME`) annotates into `DIR` and lists the
  unrun lines not marked `# pragma: no cover` in `DIR/missing.txt`.
  Keep pragmas few (Wayne).  On 2026-10-24, after S4.2 removed the
  Part 1 editing, `ezpkg.py` had 17 lines unrun (342 tests); four
  unreachable guards are marked, and what is left is another
  computer's packages and rare release and bootstrap-check branches.
  Don't edit `ezpkg_test.py`
  during a coverage run: `test_case_runners_are_marked` reads its
  source and fails spuriously.
* End-user tests get approvals in Part 1 the way an end user does:
  `run_as_developer` builds an `email` release and puts its copy in
  place of the program (S4.2), so `InstallTest.program` carries the
  real pasted bootstrap and runs with its directory as `HOME` (cache
  `.ezpkg` there, `cache_of`) and this tree on `PYTHONPATH`.
* The date tests need a `pip` 26 or newer in `~/.ezpkg`, and skip
  without one.  This machine has no `~/.ezpkg`, so run the suite with
  `HOME` set to a scratch home whose `.ezpkg/pip.whl` is a current
  `pip` (`pip download pip --no-deps`).
* `ruff check .` and `mypy .`; both check against the Python 3.11 floor,
  and both must pass (`release.yml` runs `ruff`; the bootstrap's
  imports need their blank line before `try:`).  `mypy.ini` sets
  `strict = True` (2026-10-25), because a stranger who runs `mypy
  --strict` on a program checks its pasted bootstrap too; `2026-10-25`
  is the bootstrap rewritten to pass it (`g` typed, `URLError` from
  `urllib.error`), released in `ezpkg` 0.0.3.  `2026-10-26` keeps its
  comment lines to 72 columns, as `R.pcr` asks (`I.bce7c`, `ezpkg`
  0.0.4).  The tests patch the
  standard modules themselves (`os`, not `ezpkg.os`), as strict needs.

## Working With Wayne

* `README.md`'s table of contents lists every `##` heading; keep it in
  step when a heading changes (Wayne's README note, moved here
  2026-10-24).
* `README.md` rewrites are proposed in HTML comments beside the old
  text, with the line ranges of both (recheck them, since they shift);
  when Wayne says delete, delete.  Never nest HTML comments: an inner
  `-->` ends the outer one.  Wayne answers with `<!-- Claude: ... -->`
  notes, and open items are `<!-- Issue: ... -->` comments.  Re-read
  the file before editing, since Wayne edits it between turns.
* Wayne does his own end-to-end reads of `README.md`.
* Wayne prefers discussing in chat to notes in `Details.md` files.
* Startup context must stay under 150k characters.  Near the end of a
  major session, move superseded `Context.md` entries into the item's
  `History.md` (not loaded at startup), leaving `Context.md` as the
  current state, decisions still in force, open questions and next
  steps.
* Wayne's only git step is `git commit` (2026-10-25): Claude pushes,
  tags `v*` releases, starts and approves the release runs (`pypi`
  included, at Wayne's word for that release), and does GitHub's
  settings with `gh api` rather than sending Wayne to the web pages.
* `ezpkg` is on pypi.org: 0.0.1 (2026-10-25, `T.utpat`), 0.0.2, 0.0.3
  and 0.0.4 (the same day, `I.srlfnp`, `I.bfms` and `I.bce7c`), and
  0.0.5 and 0.0.6 (2026-10-26, `I.mlmfpn`; `I.cernb`, `I.mbicamp`,
  `I.dspef`, `I.r2birae`), so the
  Quick Start works for a new user; `release_check.py pypi|testpypi
  VERSION` checks what was published.  A release follows `T.ffrp`'s procedure: bump
  `__version__`, Wayne commits, Claude pushes, rehearses on
  test.pypi.org, tags `vX.Y.Z`, starts the `pypi` run and approves it
  (Claude Code's permission check may want Wayne's "go" first).
  pypi.org's `/pypi/ezpkg/json`, which the bootstrap reads, can name
  the previous release for a minute or more after an upload, so
  `release.yml`'s `listed` job and `release_check.py` (`newest_named`)
  wait until it names the new version (S5.1, S5.2).

## Next Steps (2026-10-26, after 0.0.6)

0.0.6 is on pypi.org (`v0.0.6`, `c615a2e`), fixing what Wayne's
`solidcraftcnc` demo found (`I.cernb~27`, `I.mbicamp~28`, `I.dspef~29`,
`I.r2birae~30`).  Wayne is the one user, and wants real-use failures
found and fixed, not worked around.  His own `~/.ezpkg/ezpkg.whl` is
0.0.1, which no new code can rescue: deleting it once is the repair.

`T.zcpom~9` (a `zipapp` carries the program's own modules) is
Pending, agreed but not built; Wayne's decisions are in its
`Context.md`, which startup does not load while it is Pending, so read
it first.  The `6fd240c` commit message says this was built; it was
not.  Nothing else is open.  The `ux13`, `ux14` and `ux19`
transcripts are stale (the question was reworded); Wayne will batch
read fresh ones (`ux/drive.py --ux-dir` into the scratchpad).

Older offers (2026-10-25, after 0.0.3), in this order of
recommendation; Wayne has not chosen yet:

1. Settle `R.pcr` (Python Coding Rules), switched on mid-session on
   2026-10-25, probably by Wayne's other Claude instance.  `--strict`
   already passes (`I.bfms`), but the rest does not yet hold: 78
   comment lines exceed 72 columns (68 in `ezpkg.py`, 3 each in
   `release_check.py` and `ezpkg_coverage.py`, 2 each in
   `quick_start.py` and `ux/drive.py`; the bootstrap's cannot change
   without a new bootstrap), and docstrings lack `Arguments:` and
   `Returns:` sections.  Wayne decides: keep it active and bring the
   code into line, or make it InActive here.
2. The release-time warning when a compiled package has no wheel for a
   computer that `requires-python` admits (left from `T.ee`).
3. `T.abfd`'s small UX items in its `History.md`: S2.2b, S2.4g, S2.4h,
   S3.3c, S3.3d, S5.1d.
4. Bring `ux/` transcripts up to date: the committed ones show old
   wording (`upgrade = true`, `release = "1.0.0"`, `exports`, 0.0.1).
   Rerun `ux/drive.py --ux-dir` into the scratchpad and give Wayne the
   list to read in one batch.
5. Housekeeping: delete old test.pypi.org dev uploads, and read
   pypi.org's project page as a stranger.

Also 2026-10-25: `R.gsr` (GitHub Setup Rules) and `R.gwr` (GitHub
Workflow Rules, first called GitHub Actions Rules) were written from
this project's tasks, for the next project to go to pypi.org
(`aicontexts`, formerly `ai_contexts`; Wayne cleans it up in another
session), and are Active here and there.  They replace
`PyPI_Via_GitHub.md`, which Wayne will retire; leave it until he says.
Every rule here takes its source from `../aicontexts/rule_sources/`
(Wayne, 2026-10-25), as `aicontexts`' own rules do; a rule's copy is
now its `Details.md`.  `../claude_code_rules/` is deleted.
`rule_sources/` also holds `General_AI_Rules.md`, not a rule here.
`aic` and `ai_contexts` come from `uv tool install aicontexts` (in
`~/.local/bin`, Wayne, 2026-10-26); the project has no links to
them.  `aicontexts` builds from a
`pyproject.toml`, so `R.gwr`'s `build` job (written from `ezpkg`'s
hand-built wheel) may need a `python -m build` note when it goes to
pypi.org.
