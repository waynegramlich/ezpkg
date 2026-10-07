# 9 How many machines does requiring `pip` exclude?

(CLOSED 2026-10-01)  The decision to require `pip`, recorded under the
preinstalled environment conclusions in Experiment 2, removed `pip`'s absence
from the design space, so this no longer decides what gets built. What remains
is reach: a machine without `pip` now gets a diagnosed failure instead of a
bootstrap, and nobody has measured how many machines that is.  The question is
also narrower than it was.  It is not "what is installed on a stock machine"
but "is `pip` inside the distribution's base `python3` package," which is one
`dnf repoquery`, `apk info` or `pacman -Qi` per distribution and needs no
container runtime.

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
  untried, carries on as `I.wmau`.
