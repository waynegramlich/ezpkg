# AltVEnv Issues

<!-- --------------------------- 79 characters ---------------------------- -->

The issues were the end of `LOGBOOK.md` until 2026-10-04.  This file
is their home until the issue program planned in task 7 exists; until
then the rules below still hold.

Each issue is named by a priority digit followed by the first letter of
each word of its title, lower cased, with "a", "an", "the" and "of"
dropped.  Punctuation is dropped and a hyphenated word counts once, so
*What happens with no network?* at priority 0 becomes `0whwnn`.  Two
titles that collide take a trailing digit.

The four priorities:

* **0, extreme.**  It must be avoided at all costs.  A defect that
  escapes into somebody else's program, where nobody is around to fix
  it, belongs here; so does a security hole.  Nothing else outranks
  this.
* **1, high.**  It gates the work or decides what gets built.  Nothing
  breaks, but the answer changes the direction.
* **2, medium.**  It costs time or disk, or it is a correctness problem
  with a narrow blast radius.
* **3, low.**  Worth doing, nothing turns on when.

Issues sort by name, which puts them in priority order and then
alphabetical order.  Changing a priority or a title changes the name,
and every reference must be updated in the same pass.  That fixup is
Claude's job and is not a reason to leave an issue mis-prioritised.

The statement of an issue is written by Claude and is meant to be
checkable.  `Various thoughts:` below it holds the dispositions, oldest
first, each tagged with a reviewer's first name and the date it was
written.  Claude is a reviewer like any other.  Nobody edits somebody
else's thought; one that turns out to be wrong is answered by a later
one.

## Active Issues

Being worked on right now, in priority order.  None at present.

## Pending Issues

Not yet started, in priority order.

* **The bootstrap trusts only system certificates. (2btosc)**  Case
  13 reaches PyPI with `urllib`, which verifies against the operating
  system's certificate store, where case 7 handed the whole fetch to
  `pip` and its own bundled store.  Linux distributions provide one.
  The python.org installer for macOS does not until its
  `Install Certificates.command` has been run, so there the bootstrap
  would fail on its first request.  Untested; nobody here has a Mac.

  Various thoughts:
  * Wayne (2026-10-01): I'm working on getting access to macOS and
    Windows machines, so that is in progress.
  * Claude (2026-10-01): Simulated on Linux by pointing `SSL_CERT_FILE`
    at an empty file, and at no file, with `SSL_CERT_DIR` gone too.
    `nopip3` stops at once with one line, exit status 1: `cannot fetch
    alt_venv, choose pip failed: URLError(SSLCertVerificationError(1,
    '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable
    to get local issuer certificate ...'))`.  That is the very text a
    python.org macOS install prints without its certificates, and it
    leads anyone who searches for it to `Install Certificates.command`,
    so a hint in the paste would cost a line to say what the message
    already says.  What a real Mac adds is whether it fails this way at
    all.

* **Windows and macOS are untried. (2wmau)**  Everything here has been
  verified on Linux only, under CPython 3.11 and 3.12.  `nopip3` and
  `alt_venv.py` both use `pathlib` and `sys.executable` rather than
  spelling out paths, so nothing is known to break, but nothing has been
  run either; `2btosc` is the one specific worry, for macOS.  Carried
  over from `2hmmdrpe`.

  Various thoughts:
  * Wayne (2026-09-22): It would be nice to test on Windows and MacOS.
  * Wayne (2026-09-22): I know people who have these machines and would be glad
    to help.  Until then, the answer is currently unknown.
  * Wayne (2026-10-01): Access to macOS and Windows machines is in
    progress.

* **Reviewer thoughts have two formats. (3rthtf)**  Task 4 propagated the
  reviewer thought rules into `claude_notes.md`, and the two files came out
  disagreeing about the shape.  `claude_notes.md` puts reviewer thoughts
  inside the `{ ... }` braces it uses for annotating a closed task, listing
  the dating, naming and ordering rules as sub-points of the annotation
  rules.  `LOGBOOK.md` instead uses a `Various thoughts:` label followed by
  plain bullets, describes it that way in its own `## Issues` preamble, and
  uses it in fourteen places.  The rules themselves agree; only the syntax
  differs.  Whichever file is wrong, the other is the specification, so one
  of the two has to move.

  Various thoughts:
  * Claude (2026-09-25): `LOGBOOK.md` has the better of it.  Braces are for
    annotating settled text, and a multi-reviewer thread that grows over
    months is a discussion rather than an annotation; wrapping fourteen of
    them in braces would also bury the reviewer names one level deeper.  But
    `claude_notes.md` is the general write-up, in another repository and in
    Wayne's voice, so this is a proposal rather than an edit.
  * Wayne (2026-10-01): My thoughts on `LOGBOOK.md` have been morphing,
    and I'm leaving it alone for now.  The key thing is that it uses
    `{}` for closed tasks; Task 6 is still open, so braces are not
    appropriate there yet.  Task 6 grew into a parallel development
    strategy, and how `LOGBOOK.md` should change for that needs
    thought.  Leave this open, since it is going to be a while.

## Rejected Issues

Approaches that were considered and declined, recorded so that they
are not proposed again.

* **An already-importable package is installed anyway. (2apiia)**  All
  twelve cases ask whether the package is on disk at their own target,
  never whether it is already importable.  With `coverage` present in an
  active virtual environment, a case spends 1.42 s and 1.8 MB
  installing a copy it will not use, where a leading `try: import`
  costs 0.10 s.  Cheap to fix; deliberately not fixed yet.

  Various thoughts:
  * Wayne (2026-09-22): This can be dealt with much later since it is easy to
    fix.
  * Claude (2026-09-24): Fixed in the second stage.  `AltVEnv.install`
    asks `contains` first and skips the install when the package is already in
    the cache.  The twelve cases are unchanged, so the measurement in Task 2
    still shows the defect.
  * Claude (2026-09-25): A candidate for `### Closed Issues`, on the same
    terms as `0whwnn`: fixed where it ships, unfixed in the pasted bootstrap.
    The two should close together or not at all.  Wayne's call.
  * Claude (2026-09-26): The thought above no longer holds.  `0whwnn`
    closed on its own, because Step 6.1 fixed the pasted half as well,
    and this issue's pasted half is still unfixed: all twelve cases test
    a path on disk rather than asking whether the package imports.  So
    it stays open on its own merits rather than as `0whwnn`'s twin.  The
    fix is now cheaper than it was, since Step 6.3 has to rework the
    same guard for the versioned cache.
  * Wayne (2026-10-01): Rejected.  I don't care if an extra download
    occurs.

* **Vendor the packages into the repository. (3vpir)**  Needs no
  network, but it bloats the repository and breaks on compiled
  extensions -- the same `.so` problem as `0nicav`.  Declined
  2026-09-21, before Experiment 1; Experiment 1 then confirmed the
  `.so` problem is real by installing
  `tracer.cpython-312-x86_64-linux-gnu.so`.

## Closed Issues

Resolved, most recent first, each dated.  They are purged once
nobody wants to read them any more, after every reference to them
is gone.

* **Where should the cache directory live? (2wscdl)**
  (CLOSED 2026-10-01)  `~/.cache/<program>/`
  per the XDG spec, or beside the program, or the `~/.alt_venv`
  that Experiment 1 assumed without examining?  This interacts with
  `0nicav`: whatever the location, the name has to carry the
  interpreter and platform.

  Various thoughts:
  * Wayne (2026-09-22): I have no idea what this issue is about.  Let's do the
    experiment when we get the chance.
  * Wayne (2026-10-01): Clear it belongs in `~/.alt_venv` somewhere, so
    this can be closed.

* **The stashed `pip` is never updated. (3spinu)**
  (CLOSED 2026-10-01)  `pip.whl` is
  fetched once and kept until `~/.alt_venv` is deleted, so a machine
  that bootstrapped this year is still running this year's `pip` in
  five years, with whatever it did not yet know about indexes, wheel
  tags and security fixes.  A possible solution is for `AltVEnv` to
  refresh it during `cull`, which already runs about once a day.

  Various thoughts:
  * Claude (2026-10-01): Fixed by Step 6.15.16, close to the solution
    proposed but weekly rather than daily, and adding newer wheels
    beside `pip.whl` rather than replacing it.

* **A failed `pip` fetch is poorly explained. (3fpfipe)**
  (CLOSED 2026-10-01)  If the JSON
  API lists no wheel for `pip`, case 13's `next(...)` raises a bare
  `StopIteration`, and the person sees `cannot fetch alt_venv: ` with
  nothing after it.  The SHA-256 digest is in the same JSON and is
  never checked, so a truncated download surfaces as a zip error from
  `python pip.whl/pip` rather than as a failed fetch.

  Various thoughts:
  * Wayne (2026-10-01): We'll improve this later.
  * Claude (2026-10-01): Half done by Step 6.15.7.  The message now
    names the stage and the exception's type, so the empty `StopIteration`
    case reads `... choose pip failed: ValueError: ...` instead of
    nothing.  The unchecked SHA-256 digest remains.
  * Claude (2026-10-01): The other half is done too, by Step 6.15.15:
    the download is checked against its SHA-256 before it is written.

* **How many machines does requiring `pip` exclude? (2hmmdrpe)**
  (CLOSED 2026-10-01)  The
  decision to require `pip`, recorded under the preinstalled
  environment conclusions in Experiment 2, removed `pip`'s absence
  from the design space, so this no longer decides what gets built.
  What remains is reach: a machine without `pip` now gets a diagnosed
  failure instead of a bootstrap, and nobody has measured how many
  machines that is.  The question is also narrower than it was.  It
  is not "what is installed on a stock machine" but "is `pip` inside
  the distribution's base `python3` package," which is one
  `dnf repoquery`, `apk info` or `pacman -Qi` per distribution and
  needs no container runtime.

  Note what this issue cannot settle.  Its original teeth came from
  the decision criterion under Initial Thoughts: if the user can run
  `pip install pip-run`, this project is an exercise.  Requiring
  `pip` sharpens that rather than blunting it, since it assumes the
  very tool that makes `pip-run` installable.  The answer is that the
  recipient runs no commands at all where `pip-run` costs them one,
  and that is an argument about what the product is.  No survey of
  distributions will confirm or refute it.

  Various thoughts:
  * Wayne (2026-09-22): It would be nice to test on Windows and MacOS.
  * Wayne (2026-09-22): I know people who have these machines and would be glad
    to help.  Until then, the answer is currently unknown.
  * Claude (2026-10-01): Step 6.15 removes the requirement this issue
    measures.  Case 13 fetches its own `pip`, so a machine without one
    gets a bootstrap rather than a diagnosed failure, and the question
    of how many such machines exist no longer decides anything.  What
    survives is Wayne's first thought: Windows and macOS are untried.
    I would close this and carry that part into a new issue.
  * Claude (2026-10-01): Closed with Wayne's agreement: `nopip3` ships,
    so nothing requires `pip` and the count this issue wanted no longer
    matters.  Its one live part, Wayne's note that Windows and macOS are
    untried, carries on as `2wmau`.

* **The wheel tag matcher is a five-line stand-in. (2wtmifs)**
  (CLOSED 2026-10-01)  Cases
  3 and 12 pick wheels with a substring test that cannot tell musl
  from glibc, and does not read the glibc version a manylinux tag
  encodes.  It agreed with pip for one package on one platform.  On
  Alpine it would download a manylinux wheel and fail at import with
  a loader error.  The matcher is also written out twice, once per
  case, so a correction has to be made in both places.

  Two things have narrowed this since it was written.  Requiring
  `pip` demoted cases 3 and 12 from shipping candidates to
  measurement, so the matcher is no longer on the path to a
  stranger's machine unless that decision is revisited.  And the
  stub's job is to fetch `alt_venv`, which is pure Python and
  ships as `py3-none-any`, so no tag matching is needed for it at
  all; the matcher exists only because Experiment 1 fetched
  `coverage`, which has compiled wheels.  The 51 pasted lines the
  table charges the pure standard library path are therefore priced
  against the wrong package, and that number should be remeasured
  before it is used to justify anything.

  Various thoughts:
  * Wayne (2026-09-22): Let's revisit this issue after Experiment 2.
  * Claude (2026-09-26): Measured, by tracing child processes; see Step
    6.5.  The matcher's platform branch,
    `or (machine in name and "linux" in name and sys.platform ==
    "linux")`, has **never executed** in any test, and neither has
    `raise RuntimeError("no compatible wheel found")`.  So the worry was
    not merely that the matcher is a stand-in: the half of it that would
    pick a compiled wheel has never been run at all, and the tests have
    only ever exercised the `py3-none-any` path.  Reaching it needs a
    platform tagged wheel in the test index, which is Step 6.5.11.
  * Claude (2026-09-28): Measured against **real** PyPI, by Step 6.17.5,
    and there are now two concrete faults rather than one worry.
    `cryptography` cannot be fetched at all: an abi3 wheel is tagged
    with the lowest Python it supports, so the real names are
    `cp39-abi3` and `cp311-abi3` while the matcher looks for
    `cp312-abi3`.  And the musl confusion is confirmed --
    `charset_normalizer` publishes `cp312-cp312-musllinux_1_2_x86_64`
    alongside its manylinux wheel, and only PyPI's ordering keeps a
    glibc machine off the musl one.  `certifi` and `coverage` both
    fetch correctly.  The abi3 gap is pinned by an
    `@unittest.expectedFailure` in `PyPITest`.
    The complete run confirms it: with all twelve cases exercised, ten
    are covered completely and these seven lines are the only dead code
    in any of them.
  * Claude (2026-09-26): And now exercised, by Step 6.5.11, which
    publishes a wheel wearing this interpreter's compiled tag alongside
    the pure one.  The matcher **behaved correctly**: it preferred the
    tagged wheel, moved its `.data/purelib` member up beside the module,
    and refused a `cp312-cp312-win_amd64` wheel with
    `no compatible wheel found` rather than installing it.  So the
    predicted failure did not appear for any shape a Linux machine can
    build.  What remains unverified is narrower than the issue as
    written: musl against glibc, which needs an Alpine machine, and
    whether a genuinely compiled wheel imports, which a pure Python
    wheel wearing a compiled name cannot show.  Wayne's call whether
    that is still a priority 2.
  * Claude (2026-10-01): Closed with Wayne's agreement.  The matcher lives
    only in `nopip1` and `nopip2`, which are measurement and will not
    ship; `nopip3` leaves choosing wheels to `pip`.  The abi3 and musl
    faults are real but can no longer reach a stranger.

* **The venv executable directory is hard-coded. (3vedih)**
  (CLOSED 2026-10-01)  Cases
  4 and 11 reach into `root / "bin"` at `bootstrap.py:296`, `400` and
  `407`.  On Windows a virtual environment puts its executables in
  `Scripts`, so the pip reclaim would silently delete nothing and
  case 11's subprocess would not find an interpreter at all.  The
  inconsistency is inside a single case body: the same code checks
  `os.name != "nt"` when choosing symlinks, and asks `sysconfig` for
  the platform's site-packages, then hard-codes `bin`.  Nothing
  breaks on Linux, which is the whole of the current scope.

  Various thoughts:
  * Claude (2026-10-01): Closed with Wayne's agreement.  The hard-coded
    `bin` is only in `venv3` and `venv4`, which will not ship.

* **`.pth` files are installed but never executed. (3pfaibne)**
  (CLOSED 2026-10-01)  Every case
  writes coverage's `a1_coverage.pth`, its hook for measuring
  subprocesses, and no case runs it, because only `site.addsitedir()`
  executes `.pth` files and every case uses `sys.path.insert`.  Any
  package relying on a `.pth` is quietly half-installed.  Switching
  to `site.addsitedir()` is the obvious experiment.

  Various thoughts:
  * Wayne (2026-09-22): I have no idea what this issue is about.  Let's do the
    experiment when we get the chance.
  * Claude (2026-10-01): Closed with Wayne's agreement.  Step 6.9.2 has
    `alt_venv.py` run `.pth` files through `site.addsitedir`, and the
    bootstrap installs nothing but `alt_venv`, which ships none.

* **How should required packages be declared? (2hsrpbd)**
  (CLOSED 2026-10-01)  Every case has
  `PACKAGE = "coverage"` written into it.  Reusing the PEP 723
  `# /// script` block instead would make the same program work under
  `uv run` for free, and would let one bootstrap serve a list of
  packages rather than one.

  Various thoughts:
  * Wayne (2026-09-22): Sounds like it is worth doing.  The question is when?
  * Claude (2026-10-01): Closed with Wayne's agreement.  Step 6.7 settled
    it: a PEP 723 block, read by `install()` with no arguments, and the
    bootstrap fetches only `alt_venv`.

* **The bootstrap fetches the newest `pip` regardless of Python.
  (1bfnprp)**
  (CLOSED 2026-10-01)  Case 13 takes whatever wheel the JSON API lists for the
  current `pip` release.  `pip` 26.2.1 requires Python 3.10, so today
  that is harmless, but when `pip` drops 3.11 every pasted copy of the
  bootstrap running on 3.11 will fetch a `pip` it cannot run.  That is
  a defect in code pasted into somebody else's program, where nobody is
  around to fix it, which is an argument for priority 0.  A possible
  solution is to read `/pypi/pip/json` for every release and pick the
  newest whose `requires_python` admits the running interpreter, at the
  cost of some pasted lines.

  Various thoughts:
  * Wayne (2026-10-01): Needs more discussion.
  * Claude (2026-10-01): Fixed by Step 6.15.7.  `nopip3` takes the newest
    upload whose `requires_python` floor this Python meets, so a Python
    that `pip` drops keeps the last `pip` that supported it.

* **Nothing identifies a cache as valid. (0nicav)**
  (CLOSED 2026-10-01)  Every case installs into
  `~/.alt_venv` with no version, platform tag or interpreter
  version in the path.  Experiment 1 installs
  `tracer.cpython-312-x86_64-linux-gnu.so`, so the same directory
  reached by a different Python, or copied to a different machine,
  would load a shared object built for something else.  This is a
  correctness bug waiting rather than a tidiness question.

  Various thoughts:
  * Claude (2026-10-01): Covered by Step 6.3's versioned cache.
    `version_key` names every unpacked tree after the interpreter's
    cache tag and the platform, so another Python or another machine
    gets a tree of its own.  The one thing installed unversioned is
    `alt_venv` itself, which is pure Python.

* **`pip._internal` is not a public API. (0pinpa)**
  (CLOSED 2026-10-01)  Six of the twelve
  cases import it.  The pip documentation says in as many words not to,
  and
  the module path has moved before.  This is code pasted into
  programs and never updated afterwards, so when it breaks it breaks
  on some other person's machine, at their pip version, with no one
  around to fix it.

  Since this issue was written, case 11 was added to close the gap it
  creates.  Avoiding `pip._internal` rules out cases 1, 4, 5, 6, 8
  and 9, which left the "no pip but `venv` present" branch with no
  answer at all, because case 4 was its only mechanism.  Case 11
  reaches the same manufactured pip by running the venv's own
  interpreter as a child process, and measures identically to case 4
  on every column: 5 imports, 26 lines, 30 pasted, 1790 KB.  The
  surviving set is therefore cases 2, 3, 7, 10 and 11, and nothing is
  lost by discarding the rest.

  Various thoughts:
  * Wayne (2026-09-22): In general, this seems quite bad.  I'd very much like
    to avoid using `pip._internal`.  I'd very much dislike using this interface
    since the bootstrap code in theory could be replicated a large number of
    places.  I will point out that the reason why we have 10 bootstrap code
    candidates gives us some flexibility dealing with this issue.
  * Wayne (2026-10-01): Closed, because we are downloading `pip`, and the
    cases that import `pip._internal` are going away.

* **What happens with no network? (0whwnn)**
  (CLOSED 2026-09-26)  Undefined in all twelve
  cases.  Should the bootstrap fail, or fall back to whatever the
  system already provides?

  Various thoughts:
  * Wayne (2026-09-22): We are going to die without the network to fetch the
    package. We need to at least let the user know that we died because we
    could not get the package.
  * Claude (2026-09-24): The second stage does this now.
    `AltVEnv.install` raises `RuntimeError` carrying pip's own standard
    error, so a caller is told why rather than left with an import failure.
    The twelve bootstrap cases still do not, and they are the half that runs on
    a stranger's machine.
  * Claude (2026-09-25): A candidate for `### Closed Issues`, since the second
    stage is the part that ships.  Left pending because the bootstrap half is
    the half that reaches a stranger's machine, and closing the issue would
    stop anyone looking at it again.  Wayne's call.
  * Claude (2026-09-26): Closed.  Step 6.1 of Task 6 wrapped the fetch
    so that a failed one exits with a single line naming the package and
    the underlying error, and no traceback.  Cases 3 and 12 give exactly
    one line; the ten `pip` cases give three or four, the extra lines
    being pip's own diagnostics, which are kept because they are more
    specific than ours.  `test_a_failed_fetch_is_one_line` holds it.
    The fall back alternative was declined by Wayne on 2026-09-22.

* **The cache check tests for a directory. (0cctfd)**
  (CLOSED 2026-09-25)  Every one of the
  twelve cases guards its install with
  `if not (target / PACKAGE).is_dir()`.  A distribution that installs
  as a single module puts a `.py` file there, not a directory, so the
  guard is false on every run and the install is repeated forever.
  `alt_venv` is exactly such a distribution, so the defect
  applies to the package this project ships.

  Two things follow.  Every case re-downloads on every run, which the
  Task 5 chart shows as warm times that match cold times.  And case 11
  does not merely repeat work, it fails: it installs with the venv's
  own `pip`, deletes that `pip`, and then on the second run tries to
  install with it again, exiting non-zero three times out of three.
  The Task 2 chart missed all of this because `coverage` installs as a
  directory, which made the guard behave correctly by accident.

  A possible solution is to ask whether the package imports rather
  than whether a path exists, which is also what `2apiia` asks for; a
  narrower one is to test for the module file as well as the
  directory.  The two issues are distinct.  `2apiia` is about skipping
  an install that is not needed, and this one is about a cache hit
  that is never detected at all.

  Various thoughts:
  * Claude (2026-09-25): Fixed the same day, by Wayne's approach: the
    second stage repairs the layout rather than twelve pasted case
    bodies being edited, so no case gained a line and the `paste`
    column did not move.  `AltVEnv.repair_module_layout` rewrites
    the module it was imported from as `<name>/__init__.py`, but only
    when that file lies under the cache root, so a checkout is never
    touched.  The cost is one extra fetch, on the first run only.
  * Claude (2026-09-25): Two things were not obvious.  Half the cases
    install into `~/.alt_venv` and half into a `site-packages`
    directory inside it, so the repair has to look anywhere under the
    root rather than at the root itself; and `bootstrap.py` never
    constructed an `AltVEnv`, so its epilogue now does what a real
    program does next.  The repair also has to decline to run once the
    module is a package, since `__init__.py` has the stem `__init__`
    and an earlier version buried it one directory deeper on the second
    run.  `test_every_case_bootstraps_repeatedly` runs three times for
    that reason.
