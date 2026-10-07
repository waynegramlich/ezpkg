# Summary of `I.hmmdrpe` How many machines does requiring `pip` exclude?

The decision to require `pip`, recorded under the preinstalled environment
conclusions in Experiment 2, removed `pip`'s absence from the design space, so
this no longer decides what gets built. What remains is reach: a machine
without `pip` now gets a diagnosed failure instead of a bootstrap, and nobody
has measured how many machines that is.  The question is also narrower than it
was.  It is not "what is installed on a stock machine" but "is `pip` inside the
distribution's base `python3` package," which is one `dnf repoquery`, `apk
info` or `pacman -Qi` per distribution and needs no container runtime.

Last thought: Claude (2026-10-01): Closed with Wayne's agreement: `nopip3`
ships, so nothing requires `pip` and the count this issue wanted no longer
matters. Its one live part, Wayne's note that Windows and macOS are untried,
carries on as `I.wmau`.
