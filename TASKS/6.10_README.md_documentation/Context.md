# LLM Agent Context Log

As of 2026-10-02, `README.md` is nearly finished.  It is Wayne's file;
help when asked, do not edit it unasked, and rewrap his over-long
lines.  Its sections now run: the hook
(problem, answer, happy ending), Quick Start (copy and run
`quick_start.py`, then a read-along of its five `# Part` comments),
Download Prompt, Author Package Management, Miscellaneous,
Alternatives, Conclusion.  What is left:
* **Conclusion.**  Claude proposed, and Wayne was too tired to read:
  (1) replace it with four lines closing the opening story -- list
  packages in Part 1, copy Parts 2 and 3, a single file you can
  e-mail; (2) add short `## Status` and `## License` sections; (3)
  say under Status that Windows never shows the download prompt.
  Also: the repository has no `LICENSE` file, which PyPI and GitHub
  look for.
* **Author Package Management** is a placeholder.  Wayne wants a
  true freeze, to be "functionally equivalent to" `zipapp` (he wrote
  `appap`; Claude read it as `zipapp` and said so).  An HTML comment
  in the section records what a freeze needs: `==` pins in Part 1
  plus the approvals file, perhaps with `ALT_VENV_APPROVE=write`
  printing the pins.  Approvals are keyed by wheel file name, so a
  compiled package approved on one platform is refused on another.
* **Alternatives** is a first pass, unreviewed.  Settled overnight:
  `quick_start.py` does run under `uv run`, but redundantly -- `uv`
  installs `cowsay` into its environment, then the bootstrap fetches
  `alt_venv`, downloads `cowsay` again into `~/.alt_venv`, asks, and
  imports its own copy.  Fixed 2026-10-10: `nopip4` uses an importable
  `alt_venv`, and `provide()` skips what `satisfied()` says is already
  installed.  Better still, `ALT_VENV_EXPORT=uv` writes a stripped,
  pinned `prog-uv.py` with its locks (`T.ewar`), so the README can say
  "start with `AltVEnv`, export for `uv`".
* **The PyPI names are free**, checked 2026-10-02: `alt_venv`,
  `alt-venv` and `altvenv` all return 404.  The bootstrap installs
  whatever PyPI serves under `alt_venv`, so anyone who registers it
  first owns every program that pastes it.  Worth claiming soon.
* The facts the README rests on:
  * The shipping bootstrap is `nopip4` (since 2026-10-10; `nopip3`
    before): **35 pasted lines** -- its 32 line body plus
    `import importlib`, `import pathlib` and `import sys`.  It first
    uses an `alt_venv` that is already importable.  Since 2026-10-02
    it calls `AltVEnv().install(bootstrap=...)` itself, so a program's
    author never touches `AltVEnv` or names `alt_venv`.  The label is
    read by nothing, but Wayne wants it; there is no `package=`.
  * What a machine needs: Python 3.11 or later, and a network that
    reaches PyPI on the first run.  No `pip`, no virtual environment,
    no administrator rights.  Verified on Linux only, under 3.11 and
    3.12; Windows and macOS are untried (`I.wmau`, `I.btosc`).
  * The Quick Start cannot work until `alt_venv` is on PyPI.  It was
    verified end to end with `alt_venv` from a local index and `pip`
    and `cowsay` from the real PyPI.
  * `README.md` says the bootstrap's first-run `pip` output is
    visible on purpose, at Wayne's word, and that `AltVEnv` hides
    `pip`'s output unless `pip` fails, which is what the code does.
  * Wayne wants `pip` kept out of the opening sections.

As of 2026-10-10: Wayne chose Claude's Conclusion, which replaced his
(`README.md:332-338`).  Wayne skipped `## Status` and `## License`
(nobody reads them); `LICENSE` now holds the MIT-0 text copied from
`alt_venv.py:37-54`.  Wayne now thinks Author Package Management and
Alternatives (the `uv` double download) are related; they come after the
Conclusion.

Later on 2026-10-10, after `ALT_VENV_EXPORT=uv` shipped, Wayne reopened the
README for a section-by-section pass:
* **Done:** the introduction (problem, solution, life-cycle: paste the
  35-line bootstrap, fetch on demand, then email the `.py` or export as
  `zipapp` or `uv`), the Quick Start, and the Download Prompt (now one
  paragraph).  `~/.alt_venv/` is introduced at first use.  The "Your Own
  Program" stub moved into the intro of "Anatomy of an `AltVEnv`
  Program", which now sits after Alternatives with `###` Parts.
* `QUICK_START`, `quick_start.py` and the README use
  `# type: ignore[import-not-found]  # For mypy.`; mypy rejects text
  appended inside a `type: ignore` comment.
* **Next:** Author Package Management, which Wayne has not read.  Its
  HTML freeze note is stale; it should present the `pins`, `zipapp` and
  `uv` exports and say why `zipapp` is pure Python only.  Then the
  Alternatives `zipapp` and "Why not just use `uv`?" bullets (say
  `AltVEnv` exports to both), and Miscellaneous.
* Claiming the PyPI name and making the Quick Start work wait for the
  very end of the project, at Wayne's word.

## 2026-10-11: State saved for Wayne's return this evening

Wayne reordered `README.md` lines 1-176 himself (committed as "Reworking
the README.md.").  Plan: W1 = review the top part (through "Enabling
`AltVEnv` for Your Program"); W2 = the rest, following the road map
`S1`-`S6` that sits in an `<!-- Issue: -->` comment right after
"Enabling" (S1 Anatomy, S2 Packaging (new: `zipapp`/`uv`, and
`ALT_VENV_EXPORT=pins` as the check for an emailed `.py`), S3 Author
Package Management, S4 Miscellaneous, S5 Alternatives / Why not `uv`,
S6 Conclusion fixes).

Convention: open items in `README.md` are `<!-- Issue: ... -->`
comments (Wayne's "mini-issue" scheme), found with `grep -n 'Issue:'`.
They name no line numbers, since those shift.

Done in W1 so far:
* L15 "35-line" became "modest" (approved).
* "Enabling `AltVEnv` for Your Program" was rewritten around the
  export-time import check, `T.cibe` (built and closed today): every
  added import goes right after the bootstrap; a `ModuleNotFoundError`
  means add the package to `dependencies`; packaging lists what the
  metadata misses.  An `Issue:` comment asks Wayne to review it.  The
  "is it preinstalled on every OS?" question was dropped as having no
  stable answer.
* Download Prompt: Enter no longer declines; it is a typo and the
  question is asked again (`AltVEnv.consent`, test
  `test_an_empty_answer_asks_again`).  README says "There is no default
  answer".  The `Claude:` note about it was deleted.

Open, deferred or waiting on Wayne:
* Waiting: the no-terminal sentence says "treated as `Always`", but the
  code treats it as a one-time yes and writes no `FOREVER_APPROVE`.
  Claude proposed "treated as `Yes`" (and fixing "with out").  Wayne has
  not answered.
* Deferred by Wayne: intro paragraph promising `zipapp`/`uv` packaging
  (verify before the README wrapup; S2 covers it).
* "See Meta Data section below" must point at the metadata section once
  its title is settled.
* Still in W1, not yet reviewed: anything else in lines 1-176; the
  `<!-- Claude: I'd like to review the stuff above.  First. -->` note
  remains.
* `test_the_quick_start_is_current` fails (5 subtests) because it wants
  `#### Part N` headings and the README now has `### Part N: ...`.  Fix
  with S1 (Anatomy).  Otherwise the quick suite (`ALT_VENV_TEST=NONE`)
  passes: 236 tests.
* Idea, not filed: the export check could also flag a declared
  third-party import placed before the bootstrap (works for the author,
  fails for the recipient before the bootstrap runs).
* Uncommitted in git since Wayne's last commit: the README Enabling
  rewrite, the Download Prompt change, and the `consent` code and test
  change.

## 2026-10-11 evening: bootstrap first, and a first-run import scan

* Wayne approved the simplified import strategy in "Enabling".
* Claude's recommendation to put the bootstrap in front of all of the
  program's imports (only `__future__` and Part 2 precede it) is parked
  in an `<!-- Issue: -->` comment under the "Enabling" heading for
  Wayne to review.  Not yet applied to the text or `quick_start.py`.
* Agreed to open a task: run the `check_imports` scan on a program's
  first run, warn only (exports still refuse), at the end of `install()`
  so declared packages are findable, and remember it in `~/.alt_venv`
  keyed on a fingerprint of the imports, `dependencies` and approvals,
  so it reruns only when those change.  Timing on Wayne's machine:
  `packages_distributions()` 167 ms (385 modules), `ast.parse` of
  `alt_venv.py` 21 ms.

## 2026-10-11 late evening: "Enabling" rewritten around one rule

* The reader's whole job: paste the bootstrap block at the very top
  (Wayne widened "the bootstrap" to mean `#!`, metadata, docstring
  placeholder, a `__future__` placeholder comment, Part 2's 7 imports
  and Part 3); put all imports after it; add a `dependencies` line each
  time a `ModuleNotFoundError` appears.  Plus a module-vs-package
  paragraph and the packaging catch-all (`T.cibe`).  Verified by running
  a pasted copy: fails with `dependencies = []`, runs once `cowsay` is
  added.  Wayne's old attempt is kept in an HTML comment below it.
* `quick_start.py`, the README's Quick Start copy and `QUICK_START` got
  Wayne's new Part 2/3 comments and "Part 4: Your imports, all after the
  bootstrap."; the Anatomy headings and Part 2/4 paragraphs follow.
  `test_the_quick_start_is_current` now wants `### Part N` and passes;
  the quick suite is green (236 tests).
* Download Prompt: the no-terminal case now says `Yes` for that run only
  (no `FOREVER_APPROVE`), matching `consent`.
* Not yet done: nothing tests the Enabling section's copy of the
  bootstrap against `quick_start.py`.  The Part 2 heading is long
  (Wayne: cosmetic, later).

## 2026-10-11: Stale README comments flushed

* Guiding principle, moved here from a comment at the top of
  `README.md`: the README is a short advertisement, followed by an
  instruction manual.
* Deleted as resolved: the TBD reminder (none left), Wayne's old
  "Enabling" attempt and its review issue, Wayne's "review the stuff
  above first" note (W1 done), and the freeze discussion in Author
  Package Management (built as `ALT_VENV_EXPORT=pins` in `T.ewar`).
* Folded into the road map: S2 must name `ALT_VENV_EXPORT=pins` as the
  check for an emailed `.py` and settle the "see Packaging below"
  reference; S3 must mention the platform catch of approvals.
* Comments left in `README.md`: the intro's packaging promise issue and
  the road map.

## 2026-10-11: Road map relabelled S1-S7 in the order of work

S1 Author Package Management (approvals), S2 Packaging, S3
Miscellaneous, S4 Alternatives, S5 Conclusion, S6 Anatomy (last, since
S1 and S2 may change the parts), S7 Wrapup.  Earlier entries above use
the old labels (old S1 Anatomy, S2 Packaging, S3 Approvals, S4 Misc,
S5 Alternatives, S6 Conclusion).

## 2026-10-11: Releasing Programs drafted; Anatomy removed

* New `## Releasing Programs` replaces Author Package Management:
  "Steps in Common" drafted (approve with `ALT_VENV_APPROVE=write`, keep
  `prog.altvenv`, export with `ALT_VENV_EXPORT`, the import check, the
  compiled-package platform catch); "As a Single `.py` File", "Using
  `zipapp`", "Using `uv`" are headings with Issue notes.  Finding:
  `write` replaces `prog.altvenv`, so a compiled package cannot be
  approved for more than one platform.
* Anatomy deleted at Wayne's word.  Kept: its Part 1 text as "###
  Choosing Versions" at the end of Enabling; its Part 3 text as "##
  How `AltVEnv` Actually Works" before the Conclusion (Wayne expects a
  full rewrite); the `mypy` note after the Quick Start.
  `test_the_quick_start_is_current` no longer wants `### Part N`
  headings, only Parts 1-5 in order in `quick_start.py`.
* Road map now S1 Releasing, S2 Miscellaneous, S3 Alternatives, S4
  Conclusion, S5 Wrapup.

## 2026-10-11 end of session: where to pick up

* Next: road map S1, the three "Releasing Programs" subsections ("As a
  Single `.py` File", "Using `zipapp`", "Using `uv`"), each with the
  same four parts: the command, the files it writes, how the recipient
  runs the result, its limits.  Their `<!-- Issue: -->` notes say what
  goes in each.  Compiled packages decide between `zipapp` and `uv`:
  see `I.htdwcp`.  Unsuspend `T.ewar` when S1 is done.
* Wayne's working style for README text: put Claude's proposal in an
  HTML comment beside the text it would replace, and give the line
  numbers of both chunks, so he can compare before choosing.
* Deferred as cosmetic (Wayne): the long Part 2 heading/comment
  "AltVEnv required imports are immediately below".
* "How `AltVEnv` Actually Works" (before the Conclusion) is a holding
  place; Wayne expects to rewrite it completely.
* Related open tasks born from this README work: `T.siofr` (scan the
  imports on ordinary runs), `T.trcb` (test the Enabling copy of the
  bootstrap), `T.fipab` (flag imports above the bootstrap).

## 2026-10-12: suspended for `T.rafal`

* "Releasing Programs" is now "Releasing a Program", rewritten by
  Wayne: email the single `.py` first (friend gets the download
  prompt), then the `zipapp` (pure only, e.g. not `numpy`) and `uv`
  bullets, then recording with `ALT_VENV_APPROVE=write` (Linux/macOS
  and a PowerShell line; Wayne's friends will test Windows before
  release).  Typos and grammar fixed above the fence.
* The fence is `### Make your Release`: text above it is settled,
  text below it (the leftover `4.` step, "One catch" about compiled
  packages) is not yet reworked.  An HTML comment above the fence says
  to settle the text before diving into `zipapp` and `uv`.
* Wayne's paragraph on what `YOUR_PROG.altvenv` is for says it lets
  you "exactly recreate the packages", so a bug from a new package can
  be told apart from one in your code.  The code could not do that
  (it only refuses changes; `pins` is separate), which is why
  `T.rafal` exists.  Recheck the paragraph once `T.rafal` is done;
  `pins` is then only for the email-the-`.py` case.
* Wayne kept version control in the paragraph on purpose: it is how
  these problems get debugged.  The typosquatting point
  (`requests`/`reqeusts`) was dropped as too obscure for the README.
* Download Prompt section: Wayne's comment says it needs shortening
  later.
* Heading rename: the road map, the intro's Issue note and the S1
  notes above still say "Releasing Programs".

## 2026-10-12: back from `T.rafal` and `T.srdisb` (both closed)

* The "exactly recreate" promise in Wayne's `.altvenv` paragraph is now
  true: the approvals lock the versions, and `write` always fetches
  afresh ("upgrade and record").
* New for the README to cover: `write` offers (with a y/n prompt naming
  the line) to add `# [tool.uv]` / `# exclude-newer = "<date>"` to
  Part 1, so an emailed `.py` fetches what was newest on that date.
  The approvals file has a `# Resolved:` date line.
* Wayne declined: suggesting the `.altvenv` go along with an emailed
  `.py`, and caveats about compiled packages on other machines.

## 2026-10-12: `ALT_VENV_EXPORT=pins` removed

* Wayne: `pins` is no longer needed, since the `exclude-newer` date in
  Part 1 covers the emailed `.py`.  Removed from `export`, its tests and
  the docs; earlier notes above that mention `pins` are history.  The
  `uv` export no longer writes `pylock.*.toml` either.  The zipapp
  version check, the network sentence and the `uv` dogfood are done.

## 2026-10-12 end of session: where to pick up

* S1, "Releasing a Program", is drafted and closed in the road map
  (README lines ~271-287): the email case, one-line format bullets, the
  `write` step (PowerShell `powershell -Command { $env:...; & python
  ... }`, tested with PowerShell 7.6.6 on Linux), the network sentence,
  the `exclude-newer` date sentence, then "Using `zipapp`" (limit
  first, `.pyz` checks `requires-python`, Windows `py`) and "Using
  `uv`" (needs `uv` on both ends; script plus `YOUR_PROG-uv.py.lock`;
  "That is all there is to it.").  Wayne declined: the one-run form,
  "One catch", a "Single `.py`" subsection, and a flow read by Claude
  (he will do careful end-to-end reads himself).
* Next: road map S2, Miscellaneous (`~/.alt_venv` behaviour), then S3
  Alternatives, S4 Conclusion, S5 Wrapup.  The intro's Issue note was
  removed.  Later: a bootstrap anatomy section, which will bring
  `nopip5` (`T.m`), and the rename to perhaps `EZPkg` (`T.rp`) at the
  very end, before publishing (`T.ffrp`).
* `alt_venv` is not on PyPI, so the Quick Start cannot work for a new
  user yet; dogfood runs use `PYTHONPATH` pointing at the project.
* Working style unchanged: proposals in HTML comments beside the old
  text with both line ranges; when Wayne says delete, delete.

## 2026-10-12 evening: road map finished; suspended

* Alternatives deleted at Wayne's word (the tool survey was going stale
  and `AltVEnv` now exports to `zipapp` and `uv`); so was "Why not just
  use `uv`?" (Wayne: nobody will ask, since `uv` is supported).
* "How `AltVEnv` Actually Works" rewritten from Wayne's draft: one
  bullet per bootstrap stage `s`, checked against `quick_start.py`;
  ends with "Never edit the bootstrap" and `ALT_VENV_BOOTSTRAP=check`.
  There is no prompt for an edited bootstrap; the check only reports.
* Conclusion: "Paste the bootstrap, list your packages in Part 1";
  `zipapp` (pure Python only) or `uv` (compiled packages like `numpy`).
* Road map comment and Wayne's "shorten the Download Prompt" note
  deleted: the prompt section is fine as is.  No `Issue:` or `Claude:`
  comments remain in `README.md`.
* `install()` docstring now says `nopip4` ships.
* Still later: a bootstrap anatomy section with `nopip5` (`T.m`), the
  rename (`T.rp`), and making the Quick Start work once `alt_venv` is
  on PyPI (`T.ffrp`).
