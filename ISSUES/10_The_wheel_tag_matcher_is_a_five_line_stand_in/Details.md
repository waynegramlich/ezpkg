# 10 The wheel tag matcher is a five-line stand-in

(CLOSED 2026-10-01)  Cases 3 and 12 pick wheels with a substring test that
cannot tell musl from glibc, and does not read the glibc version a manylinux
tag encodes.  It agreed with pip for one package on one platform.  On Alpine it
would download a manylinux wheel and fail at import with a loader error.  The
matcher is also written out twice, once per case, so a correction has to be
made in both places.

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
