# LLM Agent Context Log

## 2026-10-16: Built

* `meets(version, specifier)`: releases and `.devN` (before their
  release), the common operators; `satisfied` now uses it, keeping its
  plain-release-only rule.  `RELEASE`, `DEV_CLAUSE`.
* `own_entry(asking)`; `EZPkg.chosen(entry)` (entry met by
  `__version__`, and an approvals pin of `ezpkg` equal to it);
  `EZPkg.switch(trees)` (the `ezpkg-V-...` tree `provide` returned; if
  V is not `__version__`, `os.execve` with `[sys.executable,
  *sys.orig_argv[1:]]`, `PYTHONPATH` = tree first, `EZPKG_SWITCHED=V`,
  `EZPKG_PYTHONPATH` = the old one; Windows `subprocess.run` and exit
  with its status; a second switch stops); `EZPkg.switched()` at the
  start of `install` restores the environment and stops if the wrong
  `ezpkg` runs.
* `install()` order: if this `ezpkg` is `chosen`, `T.reb`'s check
  first and the entry left out of `provide`; otherwise `provide` all,
  `switch`, and if no switch happened, the check.
* `discrepancy`: a bootstrap is an import of `ezpkg` at its line, so
  the entry is wanted, first.
* No new lock: `switch` writes nothing, and `provide` already copes
  with concurrent installs (6.4).
* Quick Start Part 1: `["ezpkg>=0.0.1.dev0,<0.1", "cowsay"]` in all
  three copies (`.dev0` admits test.pypi.org rehearsals).
* Tried by hand: the project's `ezpkg` 0.0.1 running a copy asking
  `ezpkg==0.0.1.dev202610170307` switched to that tree and ran.
* Tests: `test_meets_orders_development_releases`,
  `test_the_quick_start_asks_for_this_ezpkg`,
  `test_a_bootstrap_wants_an_ezpkg_entry_first`,
  `test_chosen_needs_the_entry_and_the_pin`,
  `test_switch_runs_the_program_again_once`,
  `test_switched_puts_the_environment_back`; one test's program gained
  the entry.  Quick suite 288 OK, 18 skipped.
* README proposals (HTML comments): the Quick Start paragraph (88-92),
  the Enabling template's `dependencies` (208), and a sub-bullet on
  the `ezpkg` entry (after the `dependencies` bullet).
* Left: rehearsal and check; `I.uedepi` should now be settled (a `uv`
  export keeps the entry), to verify; `-I`/`-E` ignore `PYTHONPATH`,
  so a switch then stops with a message.

## 2026-10-16: Where this stopped

* Wayne approved the README wording (the Quick Start paragraph, the
  Enabling template's `ezpkg` entry, one sentence on the entry) and
  is committing everything.  Not pushed; not rehearsed; Claude's
  watcher was stopped before the `/clear`.
* Next: push, rehearsal, `release_check.py testpypi`, `check.yml`.
  The rehearsal's `ezpkg` must not switch away from itself in
  `release_check.py` (the Quick Start's entry admits `.dev`), and
  Wayne's dogfood `prog.py`, which has no `ezpkg` entry, should be
  offered one.  Then `Summary.md` and close; then `I.uedepi`.
* Remember at the real release: the Quick Start's entry
  (`ezpkg>=0.0.1.dev0,<0.1`) and the Enabling template's become the
  released version's range, in all copies.
