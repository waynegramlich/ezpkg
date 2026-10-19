# 6.17 A fetch from the real PyPI: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.17 of `LOGBOOK.md` on 2026-10-04.

* Step 6.17: A fetch from the real PyPI, carried over from Task 5.

  It is the only thing that can settle Task 3's conclusion that a
  bootstrap needs `python3-pip` plus a TLS trust store, since that claim
  is about trusting the public certificate authorities and a private
  certificate tests the opposite.  It is also just `install` against the
  real index.

  Early rather than late, because of how much it retires at once.
  Everything measured so far has been against wheels this project built
  itself: real tag soup, a real transitive closure rather than the
  synthetic `needy` and `widget`, and TLS against the public
  authorities are all unexamined.  One opt-in test reaches all of them,
  and settles a claim that has been open since 2026-09-24.
  * 6.17.1 - Done 2026-09-27.  `PyPITest`, skipped unless
    `ALT_VENV_PYPI` is set, fetches from the real index in a child
    process with `PIP_INDEX_URL` removed, so the default applies: PyPI
    over TLS against the system trust store.  Two tests, 5.4 s.
    `requests==2.32.3` arrives with `certifi`, `charset-normalizer`,
    `idna` and `urllib3`, which is the first real transitive closure this
    project has seen, and Task 3's trust store claim is settled in the
    affirmative: nothing about the fetch needed arranging.

    Download only; upload nothing.  Wayne asked on 2026-09-27
    whether PyPI has a scratch area that ages out after about a week, to
    hold wheels of our own.  It would not help here: the three unknowns
    are real tag soup, a real transitive closure and TLS against the
    public authorities, and all three come from **fetching** something
    that already exists.  Nothing this project does publishes a package.

    The nearest real thing is `test.pypi.org`, a separate instance whose
    database may be pruned, but not on a schedule anybody should rely on,
    and real PyPI refuses to reuse a filename once deleted.  Unverified
    recollection rather than measurement; one fetch of their
    documentation would settle it if it ever matters.
  * 6.17.2 - Uploading belongs to a different question, kept separate so
    it is not confused with this one: publishing `alt-venv` itself, so
    that `PACKAGE = "alt_venv"` in a pasted bootstrap resolves for a
    stranger with no local index.  That is the true end to end test and
    it is a release decision, with `test.pypi.org` as its rehearsal.

    **Who does what.**  Wayne uploads, by hand, exactly as with `git`.
    Two factor authentication is **not** the gate here and it was worth
    finding out before relying on it: it protects the web login, while
    an upload authenticates with an API token and is entirely
    non-interactive.  So the boundary has to be the token itself --
    Claude prepares and verifies the artifact and never holds the
    credential.

    **Ready as of 2026-09-27**, so that tomorrow is only the parts that
    need a person:

    * `release_wheel` builds the artifact: the module copied under the
      published name so one word is both the `pip` name and the import
      name, `Requires-Python` from `alt_venv.py`'s own block, `README.md`
      as the project page, a `License` field as free text and five trove
      classifiers.  Seven tests in `ReleaseWheelTest`, including `pip`
      accepting it and no `@` anywhere in the headers.
    * `dev_version()` stamps a version to the minute, because **no index
      lets a filename be uploaded twice**, even after a deletion.  Every
      rehearsal therefore gets a name of its own for free.
    * `twine` is fetched with our own `install()` -- about twenty
      packages, the largest closure this project has resolved -- and
      then judges our own handwritten `METADATA`.  Measured:
      `twine check --strict` **passes**.  The rejection 6.17.7 expected
      did not happen, which retires the main risk of the whole exercise.
      The test is opt in behind `ALT_VENV_PYPI`.

    **What is left for a person, in order.**

    * An account on `test.pypi.org`, which is separate from PyPI's, with
      2FA by authenticator application rather than SMS as far as anybody
      here knows; the signup page settles it.
    * An API token from that account, kept out of the repository.
      `TWINE_USERNAME=__token__` and `TWINE_PASSWORD=<token>` in the
      environment is the least permanent way to hold one.
    * Build with a stamped version, then `twine upload --repository-url
      https://test.pypi.org/legacy/ <wheel>`, under the trial name
      `alt_venv_trial` rather than `alt-venv`.
    * Fetch it back the way a stranger would: a pasted bootstrap with
      `PIP_INDEX_URL=https://test.pypi.org/simple/` and no local index at
      all.  That is the step nothing has ever tested.
    * Then, and only then, `alt-venv` at `0.0.1.dev1` on real PyPI, which
      claims the name that every pasted bootstrap carries while leaving
      `0.0.1` clean for the first real release.

    **One asymmetry to keep in mind**: `test.pypi.org` may be pruned,
    unscheduled, so a mistake there does fade; PyPI never forgets, and
    the protection there is the version suffix and nothing else.
  * 6.17.3 - Opt in, and pin.  This is the one test that can fail because
    the world changed rather than because we did, so it stays out of the
    default suite behind an environment variable, and it names exact
    versions.  Rate limiting and a machine with no network are both
    ordinary outcomes here, not faults.
  * 6.17.4 - Which packages, and why each.  `requests` brings a real
    transitive closure -- `certifi`, `idna`, `urllib3`,
    `charset-normalizer` -- which the synthetic `needy` cannot imitate.
    `setuptools` is the other, because it ships `distutils-precedence.pth`
    and so doubles as Step 6.9's evidence, and because it has no
    dependencies of its own.  `coverage` was the first choice and turned
    out to ship no `.pth` at all; see 6.9.
  * 6.17.5 - Done 2026-09-28, and it found what it was meant to find.
    `install` hands resolution and tag matching to `pip`, so a real index
    tests our plumbing; cases 3 and 12 choose for themselves with the
    five line matcher of `I.wtmifs`, and those are the ones worth aiming
    at real tag soup.  Four packages, both cases:

    * `certifi`, pure `py3-none-any`: fetched.
    * `coverage`, a `cp312` wheel for this machine plus a pure fallback:
      fetched, so the preference order does real work.
    * `charset_normalizer`: fetched, but **by luck**.  It publishes
      `cp312-cp312-manylinux...` and `cp312-cp312-musllinux_1_2_x86_64`,
      and a musl name contains both `linux` and `x86_64`, so the matcher
      accepts either; PyPI happens to list manylinux first.  A project
      listing them the other way round would hand a glibc machine a musl
      wheel whose shared objects cannot load.  That is `I.wtmifs`
      predicted and now confirmed against real data.
    * `cryptography`: **cannot be fetched at all.**  An abi3 wheel is
      tagged with the **lowest** Python it supports and serves every
      later one, so the real names are `cp39-abi3` and `cp311-abi3`; the
      matcher looks for `cp312-abi3` and gives up with `no compatible
      wheel found`.  `pip` installs it without comment.

    The abi3 gap is now a `@unittest.expectedFailure` in `PyPITest`, so
    it documents itself and reports an unexpected success the day the
    matcher learns about abi3.  Both faults belong to `I.wtmifs` and the
    fix is pasted code, so it is Wayne's call: matching `cpXY-abi3` for
    any `XY` at or below the running version is a comparison, not a
    parser, and costs a line or two of paste.
  * 6.17.6 - The prompt is a hazard here, not in the suite.  Under
    `unittest` there is no controlling terminal, so `consent` returns
    True and nothing hangs; a person running this test from a terminal
    with no approvals file gets asked, and the answer they give decides
    whether the test passes.  Set `ALT_VENV_APPROVE` in the test rather
    than leaving that to chance.
  * 6.17.7 - Done 2026-09-28, and the suspicion was wrong in a useful
    way.  `ATTEMPTS` is the consent prompt's and nothing fetches with
    it; the time is `pip`'s own five retries with backoff.  Measured
    against a server whose certificate nothing trusts, one case each:

    | flags                       | time  | names the certificate |
    |-----------------------------|-------|-----------------------|
    | `--quiet`, default retries  | 8.4 s | yes                   |
    | `--quiet --retries 0`       | 0.7 s | **no**                |
    | loud, `--retries 0`         | 0.7 s | yes                   |
    | loud, `--retries 1`         | 0.7 s | yes                   |

    The middle row is the finding, and it is worse than slowness: under
    `--quiet` the word certificate appears **only in the retry
    warnings**, so a user with `PIP_RETRIES=0` set, or a future pip that
    words its warnings differently, is told `no matching distribution
    found` -- a confident lie about the cause, which is exactly the
    failure Step 6.1 exists to prevent.  The good message we have today
    is luck.

    So `download` drops `--quiet` and passes `--retries 1`.  Everything
    pip prints is captured, so the caller sees no extra noise; the
    diagnosis now comes from the error rather than from a warning; and
    one retry remains for a genuinely flaky network.  `argv` still wins,
    for a caller who wants pip's defaults back.

    **Left for Wayne, because it changes the pasted code:**
    `bootstrap.py`'s cases still pass `--quiet` and still take 8.4 s on
    a bad certificate, and `TlsTest` measures them rather than
    `download`.  Dropping `--quiet` there costs **no** pasted line and a
    few characters, and would additionally show a person that something
    is being fetched, which Step 6.13 wants anyway.

## `Context.md` entries moved here on 2026-10-19

### 2026-10-12

* Moved from 6.17 at Wayne's word, with children 7.1 Reconnect to git
  (`T.rtg`), 7.2 Upload to test.pypi (`T.uttat`), 7.3 Upload to pypi
  (`T.utpat`).  The project is now `ezpkg` (`T.rp`); `ezpkg`, `ez-pkg`
  and `ez_pkg` were free on pypi.org and test.pypi.org on 2026-10-12.

### 2026-10-13: Publishing by Trusted Publishing, not tokens

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

### 2026-10-14

* `T.suh2` and `T.p2rc` are closed.  Most Trusted Publishing facts above
  were checked against docs.pypi.org (not the 15-minute token or the
  attestations); see `T.wrw`'s `Context.md`.

### 2026-10-15: The release procedure moved here

* Wayne's five-step procedure moved here from `T.wrw`, each step naming
  its task.  `T.utt` and `T.utp` were renamed "... and test", since
  testing against the index is part of each upload.
* Reordered so the tag comes after the test.pypi.org rehearsal: a pushed
  tag should never move, and `dev` uploads need no tag.
* Wayne: `v0.N.M` versions are disposable; a bad one is followed by the
  next number rather than repaired.

### 2026-10-15: `PyPI_Via_GitHub.md`

* Wayne asked for a reusable write-up of what was learned, for another
  project: `PyPI_Via_GitHub.md` at the top level, git-ignored for now.
  Bring it up to date when the `pypi` half works (`T.utpat`).

### 2026-10-15: Windows and macOS block shipping

* Wayne: `I.wmau` (Windows and macOS are untried) has to be closed
  before shipping to pypi.org (`T.utpat`).  Work on it starts after
  `T.kdaiis` closes.

### 2026-10-15: State at the end of the day

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

### 2026-10-16: State at the end of the day

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

### 2026-10-17

* Opened `T.eui`, `T.reb`, `T.abfd`, `T.towam`, `T.gar` (Wayne: open
  what is being worked on).  README "Download Prompt" now says what CI
  is.  Newest test.pypi.org upload: `0.0.1.dev202610171424` (from
  `7f9fe8c`, with `T.eui`), passed `release_check` and `check.yml`.

### 2026-10-17: State at the end of the session

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

### 2026-10-17: `I.ffspo` blocks `T.utpat`

* `T.kdaiis`'s batch question built (not yet committed or rehearsed).
  `I.ffspo` (a failed fetch shows `pip`'s output) filed, priority 1,
  open; must close before `T.utpat`, beside `I.wmau`.

### 2026-10-18: State at the end of the session

* The UX review (`T.abfd`, `ux/`): `ux01`-`ux09` agreed and built;
  `ux10`-`ux15` waiting on Wayne.  Big changes: developer mode is
  asked ("Are you working on `prog.py`?"), breaking imports explained
  every run, the program restarts after every `ezpkg` edit, every
  question asked once.  `ux/drive.py --only STEP` runs single steps.
* Not rehearsed on test.pypi.org since `1efdcae`; a rehearsal is due
  once the UX review settles.

### 2026-10-18: The UX review is done

* `ux01`-`ux27` built and agreed (`T.abfd`'s `Context.md` has the
  decisions).  Next: Wayne's README read, then a test.pypi.org
  rehearsal (none since `1efdcae`), then closing `T.abfd`, `T.kdaiis`,
  `T.reb`, `T.eui`.
