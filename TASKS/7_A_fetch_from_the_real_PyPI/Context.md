# LLM Agent Context Log

## 2026-10-12

* Moved from 6.17 at Wayne's word, with children 7.1 Reconnect to git
  (`T.rtg`), 7.2 Upload to test.pypi (`T.uttat`), 7.3 Upload to pypi
  (`T.utpat`).  The project is now `ezpkg` (`T.rp`); `ezpkg`, `ez-pkg`
  and `ez_pkg` were free on pypi.org and test.pypi.org on 2026-10-12.

## 2026-10-13: Publishing by Trusted Publishing, not tokens

* Wayne wants PyPI updated semi-automatically from GitHub, and the
  test.pypi upload to rehearse the final one.  So the children became
  7.1 `T.rtg` (closed), 7.2 `T.suh2` hardware 2FA, 7.3 `T.wrw` the
  release workflow, 7.4 `T.uttat` test.pypi, 7.5 `T.utpat` pypi.
* Trusted Publishing: PyPI trusts a named GitHub owner, repository,
  workflow file and (optionally) environment, and swaps GitHub's OIDC
  token for a 15-minute upload token.  A "pending publisher" can create
  a project that does not exist yet, so no API token is ever needed.
  test.pypi.org is configured separately.  `pypa/gh-action-pypi-publish`
  also attaches attestations.  From Claude's knowledge, not yet checked
  against docs.pypi.org/trusted-publishers.

## 2026-10-14

* `T.suh2` and `T.p2rc` are closed.  Most Trusted Publishing facts above
  were checked against docs.pypi.org (not the 15-minute token or the
  attestations); see `T.wrw`'s `Context.md`.

## 2026-10-15: The release procedure moved here

* Wayne's five-step procedure moved here from `T.wrw`, each step naming
  its task.  `T.utt` and `T.utp` were renamed "... and test", since
  testing against the index is part of each upload.
* Reordered so the tag comes after the test.pypi.org rehearsal: a pushed
  tag should never move, and `dev` uploads need no tag.
* Wayne: `v0.N.M` versions are disposable; a bad one is followed by the
  next number rather than repaired.

## 2026-10-15: `PyPI_Via_GitHub.md`

* Wayne asked for a reusable write-up of what was learned, for another
  project: `PyPI_Via_GitHub.md` at the top level, git-ignored for now.
  Bring it up to date when the `pypi` half works (`T.utpat`).

## 2026-10-15: Windows and macOS block shipping

* Wayne: `I.wmau` (Windows and macOS are untried) has to be closed
  before shipping to pypi.org (`T.utpat`).  Work on it starts after
  `T.kdaiis` closes.

## 2026-10-15: State at the end of the day

* Children: `T.rtg` 7.1, `T.suh2` 7.2, `T.uttat` 7.4 and `T.p2rc` 7.7
  closed; `T.wrw` 7.3 open (Wayne keeps it open; the `pypi`
  environment, tag ruleset and pypi.org publisher belong to
  `T.utpat`); `T.kdaiis` 7.5 open, nearly done (see its
  `Context.md`); `T.utpat` 7.6 pending.
* Release procedure (this `Details.md`) works end to end on
  test.pypi.org: six rehearsal uploads so far, newest
  `0.0.1.dev202610160145`.  Claude starts and approves `testpypi` runs
  on its own (Wayne, 2026-10-15); a `pypi` run needs Wayne's approval.
* Before `T.utpat`: `I.wmau` (Windows and macOS) must be closed
  (Wayne).
* `PyPI_Via_GitHub.md` (git-ignored) is the reusable write-up; keep
  it current.
* Commits now carry `Assisted-by: Claude Code:claude-opus-5-5` from
  `git_hooks/` (`core.hooksPath`); update the model there when it
  changes.

## 2026-10-16: State at the end of the day

* Done today: `I.btosc` closed (`nopip6`, `curl` fallback);
  `I.owenabd` closed (`CONIN$`/`CONOUT$`, `CI`, 5-minute answer
  limit); `T.qvm` rejected; `T.reb` (refuse an edited bootstrap) built
  and rehearsed; `T.eui` (each program's Part 1 chooses its `ezpkg`)
  built, NOT yet rehearsed.
* Children now: 7.3 `T.wrw` open; 7.5 `T.kdaiis` open (Wayne's dogfood
  left); 7.6 `T.towam` with 7.6.1 `T.gar` (done but for "release.yml
  calls check.yml", deferred), 7.6.2 `T.qvm` rejected, 7.6.3 `T.fwrm`
  (friends, days); 7.7 `T.reb` (dogfood left); 7.8 `T.eui`; 7.9
  `T.abfd` (designed, not built); 7.10 `T.utpat`; 7.11 `T.p2rc`.
* Newest test.pypi.org upload: `0.0.1.dev202610170307` (from
  `8ede14b`), which has `T.reb` and `I.owenabd` but not `T.eui`.
* Next session, in order: (1) push Wayne's `T.eui` commit, rehearse
  (`gh workflow run release.yml -f target=testpypi`, approve with
  `gh api .../pending_deployments`), `./release_check.py testpypi`,
  `gh workflow run check.yml -f target=testpypi -f version=V`;
  (2) close `T.eui`, verify and close `I.uedepi`; (3) build `T.abfd`
  (Wayne may want its messages first, before the bootstrap part);
  (4) close `T.reb`, `T.kdaiis` after Wayne's dogfood.
* Before `T.utpat` (Wayne, on GitHub and pypi.org): the `pypi`
  environment, the `v*` tag ruleset, the pypi.org pending publisher.
* Open README proposal: line 167, "Download Prompt" reworded to say
  what CI is (Wayne did not know the term).

## 2026-10-17

* Opened `T.eui`, `T.reb`, `T.abfd`, `T.towam`, `T.gar` (Wayne: open
  what is being worked on).  README "Download Prompt" now says what CI
  is.  Newest test.pypi.org upload: `0.0.1.dev202610171424` (from
  `7f9fe8c`, with `T.eui`), passed `release_check` and `check.yml`.

## 2026-10-17: State at the end of the session

* Newest test.pypi.org upload: `0.0.1.dev202610171830` (from
  `1efdcae`: `nopip7`, the 7.9 prompt, `for_export`), `release_check`
  passed, `check.yml` run 39058484123 passed all 25.  Since then
  (committed, not uploaded): the kept resolution date (`T.kdaiis`).
* Rehearsal, as Claude runs it in the background (about 6 minutes):
  `git push github main`; `gh workflow run release.yml -f
  target=testpypi`; approve via `gh api -X POST
  repos/waynegramlich/ezpkg/actions/runs/R/pending_deployments -F
  "environment_ids[]=E" -f state=approved` (E from a GET of the same
  URL, `.[0].environment.id`); `gh run watch R --exit-status`;
  `./release_check.py testpypi` (its last line names the version);
  `gh workflow run check.yml -f target=testpypi -f version=V`; watch.
* Next session, in order:
  1. Build `T.kdaiis`'s agreed batch question (its `Context.md`,
     "Agreed, NOT built"), then rehearse.
  2. `T.abfd` part 2 (its `Context.md`, "Next").
  3. Keep asking Wayne for his dogfood: `zipapp`/`uv` exports, with and
     without `import ezpkg` (closes `T.eui`, `I.uedepi`, and `T.reb`'s
     last open point); the ranges offer (`T.kdaiis`).
* Before `T.utpat` (Wayne, later): the `pypi` environment, the `v*` tag
  ruleset, the pypi.org pending publisher; `I.wmau` closed.

## 2026-10-17: `I.ffspo` blocks `T.utpat`

* `T.kdaiis`'s batch question built (not yet committed or rehearsed).
  `I.ffspo` (a failed fetch shows `pip`'s output) filed, priority 1,
  open; must close before `T.utpat`, beside `I.wmau`.

## 2026-10-18: State at the end of the session

* The UX review (`T.abfd`, `ux/`): `ux01`-`ux09` agreed and built;
  `ux10`-`ux15` waiting on Wayne.  Big changes: developer mode is
  asked ("Are you working on `prog.py`?"), breaking imports explained
  every run, the program restarts after every `ezpkg` edit, every
  question asked once.  `ux/drive.py --only STEP` runs single steps.
* Not rehearsed on test.pypi.org since `1efdcae`; a rehearsal is due
  once the UX review settles.
