# 17 What happens with no network?

(CLOSED 2026-09-26)  Undefined in all twelve cases.  Should the bootstrap fail,
or fall back to whatever the system already provides?

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
