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
